# -*- coding: utf-8 -*-
"""Agent hooks package.

This package provides hook implementations for CoPawAgent that follow
AgentScope's hook interface (any Callable).

Available Hooks:
    - BootstrapHook: First-time setup guidance
    - MemoryCompactionHook: Automatic context window management
    - SemanticMemoryHook: V2 semantic memory extraction (post_reasoning)

Example:
    >>> from copaw.agents.hooks import BootstrapHook, MemoryCompactionHook, SemanticMemoryHook
    >>> from pathlib import Path
    >>>
    >>> # Create hooks (they are callables following AgentScope's interface)
    >>> bootstrap = BootstrapHook(Path("~/.copaw"), language="zh")
    >>> memory_compact = MemoryCompactionHook(
    ...     memory_manager=mm,
    ...     memory_compact_threshold=100000,
    ... )
    >>> semantic_memory = SemanticMemoryHook(memory_manager=mm)
    >>>
    >>> # Register with agent using AgentScope's register_instance_hook
    >>> agent.register_instance_hook("pre_reasoning", "bootstrap", bootstrap)
    >>> agent.register_instance_hook(
    ...     "pre_reasoning", "compact", memory_compact
    ... )
    >>> agent.register_instance_hook(
    ...     "post_reasoning", "semantic_memory", semantic_memory
    ... )
"""

from .bootstrap import BootstrapHook
from .memory_compaction import MemoryCompactionHook
from .semantic_memory import SemanticMemoryHook

__all__ = [
    "BootstrapHook",
    "MemoryCompactionHook",
    "SemanticMemoryHook",
]
