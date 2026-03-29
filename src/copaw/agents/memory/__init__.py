# -*- coding: utf-8 -*-
"""Memory management module for CoPaw agents.

This module provides:
- MemoryManager: Traditional memory management
- AgentMdManager: Agent markdown file management
- unified: Unified memory system (M2.1-M5.0)

For standalone usage of unified memory system:
    from copaw.agents.memory.unified import MemoryIntegration
"""

# Lazy imports to avoid circular dependencies
def __getattr__(name):
    if name == "MemoryManager":
        from .memory_manager import MemoryManager
        return MemoryManager
    elif name == "AgentMdManager":
        from .agent_md_manager import AgentMdManager
        return AgentMdManager
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")

__all__ = [
    "AgentMdManager",
    "MemoryManager",
]
