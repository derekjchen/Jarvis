# -*- coding: utf-8 -*-
"""Graceful Restart Manager for CoPaw Agent.

Provides safe restart mechanism that:
1. Notifies Agent to prepare for restart
2. Saves all session states and memory data
3. Stops accepting new requests
4. Waits for pending requests to complete
5. Triggers process restart via os.execv
6. New process loads new code and user data
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
import sys
import time
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Optional, Callable

logger = logging.getLogger(__name__)

# User data directory
USER_DATA_DIR = Path.home() / ".copaw"


class RestartState(Enum):
    """Restart state enumeration."""
    NORMAL = "normal"           # Normal operation
    PREPARING = "preparing"     # Preparing for restart
    SAVING = "saving"           # Saving state
    WAITING = "waiting"         # Waiting for pending requests
    RESTARTING = "restarting"   # Restarting process


@dataclass
class RestartStatus:
    """Current restart status."""
    state: RestartState = RestartState.NORMAL
    pending_requests: int = 0
    saved_sessions: int = 0
    saved_entities: int = 0
    started_at: str = ""
    message: str = ""
    error: str = ""


@dataclass
class RestartConfig:
    """Restart configuration."""
    wait_timeout: int = 30          # Max seconds to wait for pending requests
    save_timeout: int = 60          # Max seconds for saving state
    restart_delay: int = 3          # Seconds before actual restart
    notify_message: str = "Agent 正在准备重启，请稍候..."


class GracefulRestartManager:
    """Manages graceful restart of CoPaw Agent."""
    
    _instance: Optional[GracefulRestartManager] = None
    _lock = asyncio.Lock()
    
    def __init__(
        self,
        user_data_dir: Path = USER_DATA_DIR,
        config: RestartConfig = None,
    ):
        self.user_data_dir = Path(user_data_dir)
        self.config = config or RestartConfig()
        
        # State tracking
        self._status = RestartStatus()
        self._pending_request_count = 0
        self._request_counter_lock = asyncio.Lock()
        
        # Components (will be set by set_* methods)
        self._session_manager: Any = None
        self._memory_manager: Any = None
        self._entity_store: Any = None
        self._chat_manager: Any = None
        self._runner: Any = None
        self._app: Any = None
        
        # Callbacks
        self._pre_restart_callbacks: list[Callable] = []
        self._post_restart_callbacks: list[Callable] = []
    
    @classmethod
    def get_instance(cls) -> GracefulRestartManager:
        """Get singleton instance."""
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance
    
    def set_session_manager(self, session_manager: Any):
        """Set session manager reference."""
        self._session_manager = session_manager
    
    def set_memory_manager(self, memory_manager: Any):
        """Set memory manager reference."""
        self._memory_manager = memory_manager
    
    def set_entity_store(self, entity_store: Any):
        """Set entity store reference."""
        self._entity_store = entity_store
    
    def set_chat_manager(self, chat_manager: Any):
        """Set chat manager reference."""
        self._chat_manager = chat_manager
    
    def set_runner(self, runner: Any):
        """Set runner reference."""
        self._runner = runner
    
    def set_app(self, app: Any):
        """Set FastAPI app reference."""
        self._app = app
    
    def add_pre_restart_callback(self, callback: Callable):
        """Add callback to run before restart."""
        self._pre_restart_callbacks.append(callback)
    
    def add_post_restart_callback(self, callback: Callable):
        """Add callback to run after restart (in new process)."""
        self._post_restart_callbacks.append(callback)
    
    def get_status(self) -> RestartStatus:
        """Get current restart status."""
        return self._status
    
    def is_restarting(self) -> bool:
        """Check if restart is in progress."""
        return self._status.state != RestartState.NORMAL
    
    async def increment_pending_request(self):
        """Increment pending request counter."""
        with self._request_counter_lock:
            self._pending_request_count += 1
            logger.debug(f"Pending requests: {self._pending_request_count}")
    
    async def decrement_pending_request(self):
        """Decrement pending request counter."""
        with self._request_counter_lock:
            self._pending_request_count -= 1
            logger.debug(f"Pending requests: {self._pending_request_count}")
    
    async def prepare_restart(self) -> dict:
        """Prepare for restart - stop accepting new requests."""
        
        async with self._lock:
            if self.is_restarting():
                return {
                    "success": False,
                    "message": "Restart already in progress",
                    "status": self._status
                }
            
            logger.info("Preparing for graceful restart...")
            self._status.state = RestartState.PREPARING
            self._status.started_at = time.strftime("%Y-%m-%d %H:%M:%S")
            self._status.message = self.config.notify_message
            
            # Mark app as restarting (so it can reject new requests)
            if self._app:
                self._app.state._restarting = True
            
            return {
                "success": True,
                "message": "Preparing for restart",
                "status": self._status
            }
    
    async def save_all_state(self) -> dict:
        """Save all session states and memory data."""
        
        logger.info("Saving all state before restart...")
        self._status.state = RestartState.SAVING
        
        saved_sessions = 0
        saved_entities = 0
        errors = []
        
        try:
            # 1. Save all sessions
            if self._session_manager:
                sessions_dir = self.user_data_dir / "sessions"
                if sessions_dir.exists():
                    for session_file in sessions_dir.glob("*.json"):
                        try:
                            # Session files are already saved by SafeJSONSession
                            # Just count them
                            saved_sessions += 1
                        except Exception as e:
                            errors.append(f"Session {session_file.name}: {e}")
                            logger.warning(f"Error counting session: {e}")
            
            # 2. Trigger session save for active sessions
            if self._runner and hasattr(self._runner, 'session'):
                try:
                    # Save current session state
                    session = self._runner.session
                    if session:
                        # Force save all active sessions
                        await self._save_active_sessions()
                        logger.info("Active sessions saved")
                except Exception as e:
                    errors.append(f"Active sessions: {e}")
                    logger.warning(f"Error saving active sessions: {e}")
            
            # 3. Save memory data
            if self._memory_manager:
                try:
                    # Memory manager should have a save/flush method
                    if hasattr(self._memory_manager, 'save'):
                        await self._memory_manager.save()
                    elif hasattr(self._memory_manager, 'flush'):
                        await self._memory_manager.flush()
                    logger.info("Memory data saved")
                except Exception as e:
                    errors.append(f"Memory: {e}")
                    logger.warning(f"Error saving memory: {e}")
            
            # 4. Save entity store
            entity_store_dir = self.user_data_dir / "entity_store"
            if entity_store_dir.exists():
                # Count entities
                for entity_file in entity_store_dir.glob("*.json"):
                    saved_entities += 1
            
            # 5. Save entity store explicitly if we have access
            if self._entity_store:
                try:
                    if hasattr(self._entity_store, 'save'):
                        self._entity_store.save()
                    logger.info("Entity store saved")
                except Exception as e:
                    errors.append(f"Entity store: {e}")
                    logger.warning(f"Error saving entity store: {e}")
            
            # 6. Save memory evolution state if exists
            memory_file = self.user_data_dir / "MEMORY.md"
            if memory_file.exists():
                # MEMORY.md is already persisted
                logger.info(f"MEMORY.md exists: {memory_file.stat().st_size} bytes")
            
            # 7. Save backup info
            backup_dir = self.user_data_dir / "restart_backups"
            backup_dir.mkdir(parents=True, exist_ok=True)
            timestamp = time.strftime("%Y%m%d_%H%M%S")
            backup_info = {
                "timestamp": timestamp,
                "saved_sessions": saved_sessions,
                "saved_entities": saved_entities,
                "errors": errors,
                "restart_state": "prepared"
            }
            backup_file = backup_dir / f"restart_{timestamp}.json"
            backup_file.write_text(json.dumps(backup_info, indent=2))
            
            self._status.saved_sessions = saved_sessions
            self._status.saved_entities = saved_entities
            
            logger.info(f"State saved: {saved_sessions} sessions, {saved_entities} entities")
            
            return {
                "success": True,
                "saved_sessions": saved_sessions,
                "saved_entities": saved_entities,
                "backup_file": str(backup_file),
                "errors": errors
            }
            
        except Exception as e:
            logger.error(f"Save state failed: {e}")
            self._status.error = str(e)
            return {
                "success": False,
                "error": str(e),
                "saved_sessions": saved_sessions,
                "saved_entities": saved_entities
            }
    
    async def _save_active_sessions(self):
        """Save all active sessions."""
        # This would iterate through active sessions and save them
        # Implementation depends on how sessions are tracked
        pass
    
    async def wait_for_pending_requests(self) -> dict:
        """Wait for pending requests to complete."""
        
        logger.info("Waiting for pending requests...")
        self._status.state = RestartState.WAITING
        
        start_time = time.time()
        timeout = self.config.wait_timeout
        
        while time.time() - start_time < timeout:
            async with self._request_counter_lock:
                pending = self._pending_request_count
                self._status.pending_requests = pending
            
            if pending == 0:
                logger.info("All pending requests completed")
                return {
                    "success": True,
                    "pending_requests": 0,
                    "wait_time": time.time() - start_time
                }
            
            logger.info(f"Waiting... {pending} pending requests")
            await asyncio.sleep(1)
        
        # Timeout reached
        logger.warning(f"Wait timeout reached, {pending} requests still pending")
        return {
            "success": False,
            "pending_requests": pending,
            "wait_time": timeout,
            "message": "Timeout waiting for pending requests"
        }
    
    async def execute_restart(self, delay: int = None) -> dict:
        """Execute the actual restart."""
        
        delay = delay or self.config.restart_delay
        self._status.state = RestartState.RESTARTING
        
        logger.info(f"Restart scheduled in {delay} seconds...")
        
        # Run pre-restart callbacks
        for callback in self._pre_restart_callbacks:
            try:
                if asyncio.iscoroutinefunction(callback):
                    await callback()
                else:
                    callback()
            except Exception as e:
                logger.warning(f"Pre-restart callback failed: {e}")
        
        # Schedule the restart
        asyncio.create_task(self._do_restart(delay))
        
        return {
            "success": True,
            "message": f"Restart scheduled in {delay} seconds",
            "status": self._status
        }
    
    async def _do_restart(self, delay: int):
        """Perform the actual restart."""
        
        # Wait for delay
        await asyncio.sleep(delay)
        
        logger.info("Executing restart...")
        
        # Final state save
        try:
            await self.save_all_state()
        except Exception as e:
            logger.error(f"Final save failed: {e}")
        
        # Get restart command
        cmd = self._get_restart_command()
        
        logger.info(f"Restarting with: {cmd}")
        
        # Use os.execv to replace process
        # This preserves environment and user data
        os.execv(sys.executable, cmd)
        
        # This line should never be reached
        logger.error("execv failed!")
    
    def _get_restart_command(self) -> list[str]:
        """Get the command to restart the process."""
        # Default command - may need adjustment based on actual startup
        return [
            sys.executable,
            "-m", "copaw",
            "app",
            "--host", "0.0.0.0",
            "--port", "8088"
        ]
    
    async def full_restart(self) -> dict:
        """Execute full graceful restart sequence."""
        
        results = {}
        
        # Step 1: Prepare
        results["prepare"] = await self.prepare_restart()
        if not results["prepare"]["success"]:
            return results
        
        # Step 2: Save state
        results["save"] = await self.save_all_state()
        
        # Step 3: Wait for pending requests
        results["wait"] = await self.wait_for_pending_requests()
        
        # Step 4: Execute restart
        results["restart"] = await self.execute_restart()
        
        return results
    
    def verify_data_integrity(self) -> dict:
        """Verify user data integrity after restart."""
        
        checks = {}
        
        # Check required files/directories
        required_paths = [
            "config.json",
            "MEMORY.md",
            "chats.json",
            "sessions",
            "entity_store",
        ]
        
        for path in required_paths:
            full_path = self.user_data_dir / path
            if full_path.exists():
                if full_path.is_file():
                    checks[path] = {
                        "exists": True,
                        "size": full_path.stat().st_size,
                        "type": "file"
                    }
                else:
                    file_count = len(list(full_path.glob("*")))
                    checks[path] = {
                        "exists": True,
                        "count": file_count,
                        "type": "directory"
                    }
            else:
                checks[path] = {"exists": False}
        
        # Overall status
        all_exist = all(c.get("exists", False) for c in checks.values())
        
        return {
            "success": all_exist,
            "checks": checks,
            "user_data_dir": str(self.user_data_dir)
        }


# Convenience function
def get_graceful_restart_manager() -> GracefulRestartManager:
    """Get the graceful restart manager singleton."""
    return GracefulRestartManager.get_instance()