# -*- coding: utf-8 -*-
"""Unified Memory System - Integrated Milestones M2.1, M3.0, M3.5, M4.0, M5.0.

This module provides a unified memory system integrating all milestones:

Milestones:
- M2.1: KeyInfo Extraction - Safety-critical info (allergies, taboos) with priority 100
- M3.0: Preference Evolution & Event Tracking - User preferences and temporal events
- M3.5: Dynamic Injection - Unified storage, retrieval, and prompt injection
- M4.0: LLM Semantic Extraction - AI-powered entity extraction from complex messages
- M5.0: Memory Evolution - Quality evaluation, forgetting, and integration

Components:
- Entity: Unified data model for all memory items
- UnifiedEntityStore: Centralized storage with persistence
- EntityRetriever: Hybrid search (keyword + vector)
- DynamicInjector: Prompt injection with prioritization
- MemoryIntegration: Unified entry point for all extractors
- LLMEntityExtractor: M4.0 LLM-based semantic extraction
- LLMTriggerStrategy: Smart trigger for LLM extraction
- MemoryQualityEvaluator: M5.0 Quality assessment
- MemoryForgetter: M5.0 Forgetting mechanism
- MemoryIntegrator: M5.0 Memory integration
- MemoryEvolver: M5.0 Evolution orchestrator

Data Flow:
    User Message → UnifiedExtractor → UnifiedEntityStore → DynamicInjector → System Prompt
                        │
                        ├── M2.1: Regex extraction (allergies, taboos)
                        ├── M3.0: Regex extraction (preferences, events)
                        └── M4.0: LLM extraction (projects, decisions, etc.)
    
    Evolution (M5.0):
    Entity Store → Quality Evaluation → Forgetting → Integration → Persisted Store
"""

from .models import Entity, EntityType, EntitySource, EntityPriority, Relation
from .store import UnifiedEntityStore
from .retriever import EntityRetriever
from .injector import DynamicInjector
from .integration import MemoryIntegration
from .llm_extractor import LLMEntityExtractor, LLMTriggerStrategy
from .evolution import (
    EvolutionConfig,
    EvolutionReport,
    MemoryQualityEvaluator,
    MemoryForgetter,
    MemoryIntegrator,
    MemoryEvolver,
    create_evolver_for_agent,
)

__all__ = [
    # Core models
    "Entity",
    "EntityType",
    "EntitySource",
    "EntityPriority",
    "Relation",
    # Storage & Retrieval (M3.5)
    "UnifiedEntityStore",
    "EntityRetriever",
    "DynamicInjector",
    # Integration
    "MemoryIntegration",
    # M4.0 LLM Extraction
    "LLMEntityExtractor",
    "LLMTriggerStrategy",
    # M5.0 Memory Evolution
    "EvolutionConfig",
    "EvolutionReport",
    "MemoryQualityEvaluator",
    "MemoryForgetter",
    "MemoryIntegrator",
    "MemoryEvolver",
    "create_evolver_for_agent",
]