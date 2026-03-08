# -*- coding: utf-8 -*-
"""Safe JSON session with filename sanitization for cross-platform
compatibility.

Windows filenames cannot contain: \\ / : * ? " < > |
This module wraps agentscope's JSONSession so that session_id and user_id
are sanitized before being used as filenames.

Added: Session inheritance support for loading summaries from previous sessions.
"""
import json
import os
import re
from datetime import datetime
from pathlib import Path
from typing import Optional

from agentscope.session import JSONSession


# Characters forbidden in Windows filenames
_UNSAFE_FILENAME_RE = re.compile(r'[\\/:*?"<>|]')


def sanitize_filename(name: str) -> str:
    """Replace characters that are illegal in Windows filenames with ``--``.

    >>> sanitize_filename('discord:dm:12345')
    'discord--dm--12345'
    >>> sanitize_filename('normal-name')
    'normal-name'
    """
    return _UNSAFE_FILENAME_RE.sub("--", name)


class SafeJSONSession(JSONSession):
    """JSONSession subclass that sanitizes session_id / user_id before
    building file paths.

    All other behaviour (save / load / state management) is inherited
    unchanged from :class:`JSONSession`.
    """

    def _get_save_path(self, session_id: str, user_id: str) -> str:
        """Return a filesystem-safe save path.

        Overrides the parent implementation to ensure the generated
        filename is valid on Windows, macOS and Linux.
        """
        os.makedirs(self.save_dir, exist_ok=True)
        safe_sid = sanitize_filename(session_id)
        safe_uid = sanitize_filename(user_id) if user_id else ""
        if safe_uid:
            file_path = f"{safe_uid}_{safe_sid}.json"
        else:
            file_path = f"{safe_sid}.json"
        return os.path.join(self.save_dir, file_path)

    def session_exists(self, session_id: str, user_id: str = "") -> bool:
        """Check if a session file exists."""
        filepath = self._get_save_path(session_id, user_id)
        return os.path.exists(filepath)

    def get_latest_session_summary(
        self,
        user_id: str = "",
        max_length: Optional[int] = None,
        exclude_session_id: Optional[str] = None,
    ) -> str:
        """Get the compressed summary from the latest session for a user."""
        latest_session_id = find_latest_session(
            self.save_dir, user_id, exclude_session_id
        )
        if not latest_session_id:
            return ""
        return load_session_summary(
            self.save_dir, latest_session_id, user_id, max_length
        )


def find_latest_session(
    save_dir: str,
    user_id: str = "default",
    exclude_session_id: Optional[str] = None,
) -> Optional[str]:
    """Find the most recently modified session for a user."""
    sessions_path = Path(save_dir)
    if not sessions_path.exists():
        return None

    safe_uid = sanitize_filename(user_id) if user_id else ""
    pattern = f"{safe_uid}_*.json" if safe_uid else "*.json"
    session_files = list(sessions_path.glob(pattern))

    if not session_files:
        return None

    if exclude_session_id:
        safe_exclude = sanitize_filename(exclude_session_id)
        exclude_filename = f"{safe_uid}_{safe_exclude}.json" if safe_uid else f"{safe_exclude}.json"
        session_files = [f for f in session_files if f.name != exclude_filename]

    if not session_files:
        return None

    latest_file = max(session_files, key=lambda f: f.stat().st_mtime)
    filename = latest_file.stem
    if safe_uid and filename.startswith(safe_uid + "_"):
        return filename[len(safe_uid) + 1:]
    return filename


def load_session_summary(
    save_dir: str,
    session_id: str,
    user_id: str = "default",
    max_length: Optional[int] = None,
) -> str:
    """Load the compressed summary from a session file."""
    safe_sid = sanitize_filename(session_id)
    safe_uid = sanitize_filename(user_id) if user_id else ""
    filename = f"{safe_uid}_{safe_sid}.json" if safe_uid else f"{safe_sid}.json"
    filepath = Path(save_dir) / filename

    if not filepath.exists():
        return ""

    try:
        with open(filepath, "r", encoding="utf-8") as f:
            data = json.load(f)
        summary = data.get("agent", {}).get("memory", {}).get("_compressed_summary", "")
        if max_length and len(summary) > max_length:
            summary = summary[:max_length] + "...[truncated]"
        return summary
    except (json.JSONDecodeError, KeyError, IOError):
        return ""
