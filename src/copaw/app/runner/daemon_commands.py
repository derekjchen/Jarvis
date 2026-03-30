# -*- coding: utf-8 -*-
"""Daemon command execution layer and DaemonCommandHandlerMixin.

Shared by in-chat /daemon <sub> and CLI `copaw daemon <sub>`.
Logs: tail WORKING_DIR / "copaw.log". Restart: in-process reload of channels,
cron and MCP (no process exit); works on Mac/Windows without a process manager.

Added graceful restart support for safe process restart with state persistence.
"""
# pylint: disable=too-many-return-statements
from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Awaitable, Callable, Optional

from agentscope.message import Msg, TextBlock

from ...constant import WORKING_DIR
from ...config import load_config

RestartCallback = Callable[[], Awaitable[None]]
logger = logging.getLogger(__name__)


class RestartInProgressError(Exception):
    """Raised when /daemon restart is invoked while another restart runs."""


DAEMON_PREFIX = "/daemon"
DAEMON_SUBCOMMANDS = frozenset(
    {"status", "restart", "reload-config", "version", "logs", "graceful-restart"},
)
# Short names: /restart -> /daemon restart, etc.
DAEMON_SHORT_ALIASES = {
    "restart": "restart",
    "status": "status",
    "reload-config": "reload-config",
    "reload_config": "reload-config",
    "version": "version",
    "logs": "logs",
    "graceful-restart": "graceful-restart",
    "graceful_restart": "graceful-restart",
    "grestart": "graceful-restart",
}


@dataclass
class DaemonContext:
    """Context for daemon commands (inject deps from runner or CLI)."""

    working_dir: Path = WORKING_DIR
    load_config_fn: Callable[[], Any] = load_config
    memory_manager: Optional[Any] = None
    # Optional: async restart (channels, cron, MCP) in-process.
    restart_callback: Optional[RestartCallback] = None
    # Graceful restart manager
    graceful_manager: Optional[Any] = None


def _get_last_lines(
    path: Path,
    lines: int = 100,
    max_bytes: int = 512 * 1024,
) -> str:
    """Read last N lines from a text file (tail) with bounded memory.

    Reads at most max_bytes from the end of the file so large logs
    do not cause high memory usage or latency.
    """
    path = Path(path)
    if not path.exists() or not path.is_file():
        return f"(Log file not found: {path})"
    try:
        size = path.stat().st_size
        if size == 0:
            return "(empty)"
        with open(path, "rb") as f:
            if size <= max_bytes:
                content = f.read().decode("utf-8", errors="replace")
            else:
                f.seek(size - max_bytes)
                content = f.read().decode("utf-8", errors="replace")
                first_nl = content.find("\n")
                if first_nl != -1:
                    content = content[first_nl + 1 :]
                else:
                    content = ""
        all_lines = content.splitlines()
        last = all_lines[-lines:] if len(all_lines) > lines else all_lines
        return "\n".join(last) if last else "(empty)"
    except OSError as e:
        return f"(Error reading log: {e})"


def run_daemon_status(context: DaemonContext) -> str:
    """Return status text (health, config, memory_manager)."""
    parts = ["**Daemon Status**", ""]
    try:
        cfg = context.load_config_fn()
        parts.append("- Config loaded: yes")
        if getattr(cfg, "agents", None) and getattr(
            cfg.agents,
            "running",
            None,
        ):
            max_in = getattr(cfg.agents.running, "max_input_length", "N/A")
            parts.append(f"- Max input length: {max_in}")
    except Exception as e:
        parts.append(f"- Config loaded: no ({e})")

    parts.append(f"- Working dir: {context.working_dir}")
    if context.memory_manager is not None:
        parts.append("- Memory manager: running")
    else:
        parts.append("- Memory manager: not attached")
    
    # Add graceful restart status
    if context.graceful_manager is not None:
        status = context.graceful_manager.get_status()
        parts.append(f"- Restart state: {status.state.value}")
        parts.append(f"- Pending requests: {status.pending_requests}")
    else:
        parts.append("- Graceful restart: not available")
    
    return "\n".join(parts)


async def run_daemon_restart(context: DaemonContext) -> str:
    """Trigger in-process restart (channels, cron, MCP) or instruct user."""
    if context.restart_callback is not None:
        try:
            await context.restart_callback()
            return (
                "**Restart completed**\n\n"
                "- Channels, cron and MCP reloaded in-process (no exit)."
            )
        except RestartInProgressError:
            return (
                "**Restart skipped**\n\n"
                "- A restart is already in progress. Please wait for it to "
                "finish."
            )
        except Exception as e:
            return f"**Restart failed**\n\n- {e}"
    return (
        "**Restart**\n\n"
        "- No restart callback (e.g. not running inside app). "
        "Run the app (e.g. `copaw app`) and use /daemon restart in chat, "
        "or restart the process with systemd/supervisor/docker."
    )


async def run_daemon_graceful_restart(
    context: DaemonContext,
    delay: int = 3,
    force: bool = False,
) -> str:
    """Trigger graceful restart with state persistence.
    
    This performs a safe restart that:
    1. Stops accepting new requests
    2. Saves all session states and memory data
    3. Waits for pending requests to complete
    4. Restarts the process (os.execv)
    5. New process loads saved state
    
    Args:
        context: Daemon context with graceful_manager
        delay: Seconds to wait before restart
        force: Force restart even with pending requests
    """
    if context.graceful_manager is None:
        return (
            "**Graceful restart not available**\n\n"
            "- Graceful restart manager not initialized.\n"
            "- Use `/daemon restart` for in-process reload instead."
        )
    
    manager = context.graceful_manager
    status = manager.get_status()
    
    # Check if already restarting
    from .graceful_restart import RestartState
    if status.state != RestartState.NORMAL:
        return (
            f"**Restart already in progress**\n\n"
            f"- Current state: {status.state.value}\n"
            f"- Pending requests: {status.pending_requests}\n"
            f"- Started at: {status.started_at}\n"
            f"- Use `/daemon status` to monitor progress."
        )
    
    # Execute graceful restart
    try:
        # Step 1: Prepare
        logger.info("Starting graceful restart...")
        prepare_result = await manager.prepare_restart()
        if not prepare_result["success"]:
            return f"**Prepare failed**\n\n- {prepare_result.get('message', 'Unknown error')}"
        
        # Step 2: Save state
        logger.info("Saving state...")
        save_result = await manager.save_all_state()
        
        # Step 3: Wait for pending requests
        logger.info("Waiting for pending requests...")
        wait_result = await manager.wait_for_pending_requests()
        
        if not wait_result["success"] and not force:
            # Cancel restart
            manager._status.state = RestartState.NORMAL
            if manager._app:
                manager._app.state._restarting = False
            return (
                f"**Restart cancelled**\n\n"
                f"- {wait_result['pending_requests']} requests still pending\n"
                f"- Wait timeout: {wait_result['wait_time']}s\n"
                f"- Use `/daemon graceful-restart --force` to force restart."
            )
        
        # Step 4: Execute restart
        logger.info(f"Executing restart in {delay}s...")
        restart_result = await manager.execute_restart(delay=delay)
        
        # Build response
        parts = [
            "**Graceful restart initiated**",
            "",
            f"- Restart in: {delay} seconds",
            f"- Sessions saved: {save_result.get('saved_sessions', 0)}",
            f"- Entities saved: {save_result.get('saved_entities', 0)}",
            f"- Pending requests: {wait_result.get('pending_requests', 0)}",
        ]
        
        if save_result.get("backup_file"):
            parts.append(f"- Backup: {save_result['backup_file']}")
        
        if save_result.get("errors"):
            parts.append(f"- Warnings: {len(save_result['errors'])}")
        
        parts.extend([
            "",
            "**Process will restart and load saved state.**",
            "- All sessions and memory data preserved",
            "- New code will be loaded",
            "",
            "Please wait for the service to come back online...",
        ])
        
        return "\n".join(parts)
        
    except Exception as e:
        logger.error(f"Graceful restart failed: {e}")
        # Reset state
        manager._status.state = RestartState.NORMAL
        if manager._app:
            manager._app.state._restarting = False
        return f"**Graceful restart failed**\n\n- Error: {e}\n- State reset to normal."


def run_daemon_reload_config(context: DaemonContext) -> str:
    """Reload config (re-call load_config); no process restart."""
    try:
        context.load_config_fn()
        return (
            "**Config reloaded**\n\n- load_config() re-invoked successfully."
        )
    except Exception as e:
        return f"**Reload failed**\n\n- {e}"


def run_daemon_version(context: DaemonContext) -> str:
    """Return version and paths."""
    try:
        from ...__version__ import __version__ as ver
    except ImportError:
        ver = "unknown"
    
    parts = [
        f"**Daemon version**",
        "",
        f"- Version: {ver}",
        f"- Working dir: {context.working_dir}",
        f"- Log file: {context.working_dir / 'copaw.log'}",
    ]
    
    # Add graceful restart info
    if context.graceful_manager is not None:
        status = context.graceful_manager.get_status()
        parts.append(f"- Graceful restart: available")
        parts.append(f"- Restart state: {status.state.value}")
    else:
        parts.append("- Graceful restart: not available")
    
    return "\n".join(parts)


def run_daemon_logs(context: DaemonContext, lines: int = 100) -> str:
    """Tail last N lines from WORKING_DIR / copaw.log."""
    log_path = context.working_dir / "copaw.log"
    content = _get_last_lines(log_path, lines=lines)
    return f"**Console log (last {lines} lines)**\n\n```\n{content}\n```"


def parse_daemon_query(query: str) -> Optional[tuple[str, list[str]]]:
    """Parse /daemon <sub> or /<short>. Return (subcommand, args) or None."""
    if not query or not isinstance(query, str):
        return None
    raw = query.strip()
    if not raw.startswith("/"):
        return None
    rest = raw.lstrip("/").strip()
    if not rest:
        return None
    parts = rest.split()
    first = parts[0].lower() if parts else ""

    if first == "daemon":
        if len(parts) < 2:
            return ("status", [])
        sub = parts[1].lower().replace("_", "-")
        if sub not in DAEMON_SUBCOMMANDS and "reload" in sub:
            sub = "reload-config"
        if sub not in DAEMON_SUBCOMMANDS:
            return None
        args = parts[2:] if len(parts) > 2 else []
        return (sub, args)
    if first in DAEMON_SHORT_ALIASES:
        sub = DAEMON_SHORT_ALIASES[first]
        return (sub, parts[1:] if len(parts) > 1 else [])
    return None


class DaemonCommandHandlerMixin:
    """Mixin for daemon commands: /daemon status, restart, logs, etc."""

    def is_daemon_command(self, query: str | None) -> bool:
        """True if query is /daemon <sub> or short name (/restart, etc.)."""
        return parse_daemon_query(query or "") is not None

    async def handle_daemon_command(
        self,
        query: str,
        context: DaemonContext,
    ) -> Msg:
        """Run daemon subcommand; return a single assistant Msg."""
        parsed = parse_daemon_query(query)
        if not parsed:
            return Msg(
                name="Friday",
                role="assistant",
                content=[
                    TextBlock(type="text", text="Unknown daemon command."),
                ],
            )
        sub, args = parsed
        if sub == "status":
            text = run_daemon_status(context)
        elif sub == "restart":
            text = await run_daemon_restart(context)
        elif sub == "graceful-restart":
            # Parse delay and force from args
            delay = 3
            force = False
            for arg in args:
                if arg.isdigit():
                    delay = max(1, min(int(arg), 60))
                elif arg == "--force" or arg == "-f":
                    force = True
            text = await run_daemon_graceful_restart(context, delay=delay, force=force)
        elif sub == "reload-config":
            text = run_daemon_reload_config(context)
        elif sub == "version":
            text = run_daemon_version(context)
        elif sub == "logs":
            n = 100
            for a in args:
                if a.isdigit():
                    n = max(1, min(int(a), 2000))
                    break
            text = run_daemon_logs(context, lines=n)
        else:
            text = "Unknown daemon subcommand."
        logger.info("handle_daemon_command %s completed", query)
        return Msg(
            name="Friday",
            role="assistant",
            content=[TextBlock(type="text", text=text)],
        )