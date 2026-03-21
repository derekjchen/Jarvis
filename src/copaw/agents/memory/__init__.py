# -*- coding: utf-8 -*-
"""Unified memory management module for CoPaw agents.

This module provides a unified memory system that combines:
- Original memory manager (ReMe-based compression, file-based memory)
- Unified entity store (semantic storage and retrieval)
- Dynamic injection (context-aware prompt enhancement)

Key Components:
- MemoryManager: Main memory management class
- UnifiedEntityStore: Semantic entity storage
- EntityRetriever: Vector-based entity retrieval
- DynamicInjector: Context-aware prompt injection
- MemoryIntegration: Integration layer for extractors

Milestones:
- M2.1: Key info extraction (allergies, taboos)
- M3.0: Preference evolution and event tracking
- M3.5: Dynamic retrieval and injection
- M4.0: LLM-based semantic extraction
"""

from .memory_manager import MemoryManager
from .agent_md_manager import AgentMdManager

# Unified components (M3.5/M4.0)
from .models import Entity, EntityType, EntityPriority, EntitySource
from .store import UnifiedEntityStore
from .retriever import EntityRetriever
from .injector import DynamicInjector
from .integration import MemoryIntegration

__all__ = [
    # Core
    "MemoryManager",
    "AgentMdManager",
    # Unified components
    "Entity",
    "EntityType",
    "EntityPriority",
    "EntitySource",
    "UnifiedEntityStore",
    "EntityRetriever",
    "DynamicInjector",
    "MemoryIntegration",
]
