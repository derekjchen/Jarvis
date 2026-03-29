# -*- coding: utf-8 -*-
"""Memory Integration for V3.5+.

This module provides the unified entry point for the Memory system,
integrating all milestones:
- M2.1: KeyInfo extraction (safety-critical)
- M3.0: Preference evolution and event tracking
- M3.5: Unified storage and dynamic injection
- M4.0: LLM-based extraction
- M5.0: Memory evolution (quality evaluation, forgetting, integration)

Usage:
    integration = MemoryIntegration(working_dir)
    
    # Process a message (extract + store)
    entities = await integration.process_message("我对花生过敏")
    
    # Inject relevant entities into prompt
    enhanced_prompt = integration.inject_to_prompt_sync(original_prompt)
    
    # Run memory evolution (M5.0)
    report = await integration.evolve()
"""
import asyncio
import logging
from datetime import datetime
from pathlib import Path
from typing import Optional, List, TYPE_CHECKING

from .models import Entity, EntityType, EntitySource
from .store import UnifiedEntityStore
from .retriever import EntityRetriever
from .injector import DynamicInjector
from .extractor import UnifiedExtractor, extract_entities
from .llm_extractor import LLMEntityExtractor, LLMTriggerStrategy
from .evolution import MemoryEvolver, EvolutionConfig, EvolutionReport

if TYPE_CHECKING:
    from agentscope.message import Msg

logger = logging.getLogger(__name__)


class MemoryIntegration:
    """Unified memory integration layer.
    
    This class provides:
    1. Single entry point for message processing
    2. Unified extraction from all extractors
    3. Persistent storage in UnifiedEntityStore
    4. Dynamic injection into prompts
    
    Architecture:
    
        Message → UnifiedExtractor → UnifiedEntityStore → DynamicInjector → Prompt
    
    Example:
        >>> integration = MemoryIntegration("/path/to/working_dir")
        >>> 
        >>> # Process a message
        >>> entities = await integration.process_message("我对花生过敏")
        >>> print(entities[0].type)  # EntityType.ALLERGY
        >>> 
        >>> # Inject into prompt
        >>> prompt = integration.inject_to_prompt_sync("You are a helpful assistant.")
        >>> print(prompt)  # Contains "用户allergy: 花生"
    """
    
    def __init__(self, working_dir: str, embedding_model=None, session_id: str = "", 
                 llm_model=None, enable_llm: bool = True,
                 evolution_config: Optional[EvolutionConfig] = None,
                 enable_evolution: bool = True):
        """Initialize memory integration.
        
        Args:
            working_dir: Working directory for storage
            embedding_model: Optional embedding model for vector search
            session_id: Current session ID for tracking
            llm_model: Optional LLM model for semantic extraction (M4.0)
            enable_llm: Whether to enable LLM extraction
            evolution_config: Optional configuration for memory evolution (M5.0)
            enable_evolution: Whether to enable memory evolution (M5.0)
        """
        self.working_dir = Path(working_dir)
        self.storage_dir = self.working_dir / "entity_store"
        self.session_id = session_id
        self.enable_llm = enable_llm
        self.enable_evolution = enable_evolution
        
        # Initialize core components
        self.store = UnifiedEntityStore(str(self.storage_dir))
        self.retriever = EntityRetriever(self.store, embedding_model)
        self.injector = DynamicInjector(self.store, self.retriever)
        self.extractor = UnifiedExtractor()
        
        # Initialize LLM extractor (M4.0)
        self.llm_extractor = None
        self.llm_trigger = LLMTriggerStrategy()
        if enable_llm and llm_model:
            self.llm_extractor = LLMEntityExtractor(llm_model)
            logger.info("LLM extraction enabled")
        
        # Initialize Memory Evolver (M5.0)
        self.evolver = None
        self._evolution_config = evolution_config
        if enable_evolution:
            self.evolver = MemoryEvolver(self.store, evolution_config)
            logger.info("Memory evolution enabled")
        
        logger.info(f"MemoryIntegration initialized for {working_dir}")
        logger.info(f"Existing entities: {len(self.store.get_all_entities())}")
    
    # ============================================================
    # Main API: Process and Inject
    # ============================================================
    
    async def process_message(self, message: str, msg_id: str = "", 
                              session_id: str = "", force_llm: bool = False) -> List[Entity]:
        """Process a message and extract entities.
        
        This is the main entry point for message processing.
        It extracts entities using all available extractors and stores them.
        
        Args:
            message: The message to process
            msg_id: Source message ID
            session_id: Source session ID
            force_llm: Force LLM extraction regardless of trigger
        
        Returns:
            List of extracted and stored entities
        """
        if not message or not message.strip():
            return []
        
        # 1. Extract entities using regex extractor (M2.1 + M3.0)
        result = self.extractor.extract(message, msg_id)
        entities = result.entities
        
        # 2. LLM extraction if enabled and triggered (M4.0)
        if self.llm_extractor:
            should_trigger, reason = self.llm_trigger.should_trigger(message)
            if force_llm or should_trigger:
                logger.debug(f"LLM extraction triggered: {reason}")
                try:
                    llm_entities = await self.llm_extractor.extract(message, session_id)
                    for entity_data in llm_entities:
                        # Convert to Entity
                        entity = self._dict_to_entity(entity_data, msg_id, session_id)
                        entities.append(entity)
                except Exception as e:
                    logger.warning(f"LLM extraction failed: {e}")
        
        # 3. Store all extracted entities
        stored_entities = []
        for entity in entities:
            # Ensure session_id is set
            entity.session_id = session_id or self.session_id
            
            # Add to store
            entity_id = self.store.add_entity(entity)
            stored_entity = self.store.get_entity(entity_id)
            if stored_entity:
                stored_entities.append(stored_entity)
        
        if stored_entities:
            logger.info(f"Processed message: extracted {len(stored_entities)} entities")
        
        return stored_entities
    
    def _dict_to_entity(self, data: dict, msg_id: str, session_id: str) -> Entity:
        """Convert dictionary to Entity object."""
        type_map = {
            "project": EntityType.PROJECT,
            "tech_decision": EntityType.DECISION,
            "person": EntityType.PERSON,
            "preference": EntityType.PREFERENCE,
            "event": EntityType.EVENT,
            "fact": EntityType.FACT,
        }
        
        type_str = data.get("type", "other")
        entity_type = type_map.get(type_str, EntityType.OTHER)
        
        importance = data.get("importance", 50)
        priority = 80 if importance >= 70 else (50 if importance >= 40 else 30)
        
        return Entity(
            type=entity_type,
            name=data.get("name", ""),
            content=data.get("content", ""),
            priority=priority,
            source=EntitySource.LLM,
            confidence=data.get("confidence", 0.9),
            context=data.get("context", ""),
            msg_id=msg_id,
            session_id=session_id,
            attributes=data.get("attributes", {}),
        )
    
    def inject_to_prompt_sync(self, prompt: str, query: str = "",
                              max_entities: int = 20,
                              max_tokens: int = 2000) -> str:
        """Synchronously inject relevant entities into a prompt.
        
        This is used by react_agent._build_sys_prompt which is synchronous.
        
        Args:
            prompt: The original prompt
            query: User query for relevance matching
            max_entities: Maximum entities to inject
            max_tokens: Maximum tokens for injection
        
        Returns:
            Enhanced prompt with entity context
        """
        try:
            loop = asyncio.get_running_loop()
            # Already in async context, use thread pool
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor() as executor:
                future = executor.submit(
                    asyncio.run,
                    self.injector.inject_to_prompt(prompt, query, max_entities, max_tokens)
                )
                return future.result()
        except RuntimeError:
            # No running loop, can use asyncio.run directly
            return asyncio.run(
                self.injector.inject_to_prompt(prompt, query, max_entities, max_tokens)
            )
    
    async def inject_to_prompt(self, prompt: str, query: str = "",
                               max_entities: int = 20,
                               max_tokens: int = 2000) -> str:
        """Asynchronously inject relevant entities into a prompt.
        
        Args:
            prompt: The original prompt
            query: User query for relevance matching
            max_entities: Maximum entities to inject
            max_tokens: Maximum tokens for injection
        
        Returns:
            Enhanced prompt with entity context
        """
        return await self.injector.inject_to_prompt(prompt, query, max_entities, max_tokens)
    
    # ============================================================
    # Convenience Methods
    # ============================================================
    
    def get_entity_summary(self) -> str:
        """Get a summary of stored entities."""
        return self.injector.get_entity_summary()
    
    def get_safety_summary(self) -> str:
        """Get summary of safety-related entities."""
        return self.injector.get_safety_summary()
    
    def get_store_stats(self) -> dict:
        """Get store statistics."""
        return self.store.get_stats()
    
    def get_all_entities(self) -> List[Entity]:
        """Get all stored entities."""
        return self.store.get_all_entities()
    
    def set_llm_model(self, model) -> None:
        """Set the LLM model for M4.0 semantic extraction.
        
        Args:
            model: The chat model instance
        """
        self.llm_extractor = LLMEntityExtractor(model)
        logger.info("LLM model configured for semantic extraction")
    
    def clear(self):
        """Clear all stored entities."""
        self.store.clear()
        logger.info("All entities cleared")
    
    # ============================================================
    # M5.0 Memory Evolution Methods
    # ============================================================
    
    async def evolve(self, force: bool = False) -> Optional[EvolutionReport]:
        """Run memory evolution cycle (M5.0).
        
        Evolution performs:
        1. Quality evaluation of all entities
        2. Forgetting low-quality/expired entities
        3. Merging similar entities
        
        Args:
            force: Force evolution even if interval not reached
        
        Returns:
            EvolutionReport if evolution ran, None if skipped
        """
        if not self.evolver:
            logger.warning("Memory evolution not enabled")
            return None
        
        # Check if evolution should run
        if not force and not self.evolver.should_evolve():
            logger.debug("Evolution interval not reached, skipping")
            return None
        
        # Run evolution
        report = await self.evolver.evolve()
        
        # Log results
        if report and not report.errors:
            logger.info(f"Evolution complete: {report.summary()}")
        elif report and report.errors:
            logger.warning(f"Evolution had errors: {report.errors}")
        
        return report
    
    def evolve_sync(self, force: bool = False) -> Optional[EvolutionReport]:
        """Synchronously run memory evolution cycle (M5.0).
        
        Args:
            force: Force evolution even if interval not reached
        
        Returns:
            EvolutionReport if evolution ran, None if skipped
        """
        try:
            loop = asyncio.get_running_loop()
            # Already in async context, use thread pool
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor() as executor:
                future = executor.submit(
                    asyncio.run,
                    self.evolve(force)
                )
                return future.result()
        except RuntimeError:
            # No running loop, can use asyncio.run directly
            return asyncio.run(self.evolve(force))
    
    def should_evolve(self) -> bool:
        """Check if memory evolution should run.
        
        Returns:
            True if evolution interval has been reached
        """
        if not self.evolver:
            return False
        return self.evolver.should_evolve()
    
    def get_evolution_summary(self) -> dict:
        """Get summary of evolution state.
        
        Returns:
            Dict with evolution statistics and last report
        """
        if not self.evolver:
            return {"enabled": False}
        
        summary = self.evolver.get_evolution_summary()
        summary["enabled"] = True
        return summary
    
    def get_last_evolution_report(self) -> Optional[EvolutionReport]:
        """Get the last evolution report.
        
        Returns:
            EvolutionReport from last evolution, or None
        """
        if not self.evolver:
            return None
        return self.evolver.get_last_report()
    
    def evaluate_entity_quality(self, entity: Entity) -> float:
        """Evaluate quality score for a single entity.
        
        Args:
            entity: Entity to evaluate
        
        Returns:
            Quality score from 0.0 to 1.0
        """
        if not self.evolver:
            return 0.5  # Default mid score if evolution not enabled
        
        return self.evolver.evaluator.evaluate(entity)
    
    def get_quality_summary(self) -> dict:
        """Get quality summary of all entities.
        
        Returns:
            Dict with quality distribution statistics
        """
        entities = self.store.get_all_entities()
        if not entities:
            return {"total": 0}
        
        quality_scores = []
        if self.evolver:
            quality_map = self.evolver.evaluator.evaluate_all(entities)
            quality_scores = list(quality_map.values())
        else:
            # Fallback: use priority as proxy
            quality_scores = [e.priority / 100.0 for e in entities]
        
        high_quality = sum(1 for q in quality_scores if q >= 0.7)
        medium_quality = sum(1 for q in quality_scores if 0.3 <= q < 0.7)
        low_quality = sum(1 for q in quality_scores if q < 0.3)
        
        return {
            "total": len(entities),
            "high_quality": high_quality,
            "medium_quality": medium_quality,
            "low_quality": low_quality,
            "average_score": sum(quality_scores) / len(quality_scores) if quality_scores else 0,
        }
    
    # ============================================================
    # Compatibility Methods (for existing code)
    # ============================================================
    
    def add_key_infos(self, key_infos: List, session_id: str = "") -> List[str]:
        """Add KeyInfo objects to the entity store.
        
        This method provides compatibility with the M2.1 KeyInfoExtractor.
        
        Args:
            key_infos: List of KeyInfo objects
            session_id: Source session ID
        
        Returns:
            List of entity IDs that were added
        """
        entity_ids = []
        
        for info in key_infos:
            # Convert KeyInfo to Entity
            info_type = getattr(info, 'info_type', 'other')
            content = getattr(info, 'content', str(info))
            context = getattr(info, 'context', '')
            priority = getattr(info, 'priority', 50)
            
            type_map = {
                "safety": EntityType.ALLERGY,
                "allergy": EntityType.ALLERGY,
                "constraint": EntityType.CONSTRAINT,
                "preference": EntityType.PREFERENCE,
                "dislike": EntityType.DISLIKE,
                "decision": EntityType.DECISION,
                "contact": EntityType.CONTACT,
            }
            
            entity_type = type_map.get(info_type.lower(), EntityType.OTHER)
            
            entity = Entity(
                type=entity_type,
                name=content[:50] if len(content) > 50 else content,
                content=content,
                priority=priority,
                source=EntitySource.REGEX,
                context=context,
                session_id=session_id,
            )
            
            entity_id = self.store.add_entity(entity)
            entity_ids.append(entity_id)
        
        if entity_ids:
            logger.info(f"Added {len(entity_ids)} entities from KeyInfo")
        
        return entity_ids
    
    def get_entities_for_injection(self, query: str = "",
                                   max_entities: int = 20) -> List[Entity]:
        """Get entities that should be injected into a prompt.
        
        Priority order:
        1. Safety entities (allergy, constraint) - always included
        2. Important decisions (priority >= 80)
        3. Preferences and other info (if space allows)
        
        Args:
            query: User query for relevance
            max_entities: Maximum entities to return
        
        Returns:
            List of entities sorted by priority
        """
        all_entities = []
        seen_ids = set()
        
        # 1. Always include safety entities (priority >= 100)
        safety_entities = self.store.get_safety_entities()
        for entity in safety_entities:
            if entity.id not in seen_ids:
                all_entities.append(entity)
                seen_ids.add(entity.id)
        
        # 2. Include entities with priority >= 50
        other_entities = self.store.get_entities_by_priority(min_priority=50)
        for entity in other_entities:
            if entity.id not in seen_ids:
                all_entities.append(entity)
                seen_ids.add(entity.id)
        
        # Sort by priority
        all_entities.sort(key=lambda e: e.priority, reverse=True)
        
        return all_entities[:max_entities]


# ============================================================
# Global Instance Management
# ============================================================

_global_integration: Optional[MemoryIntegration] = None


def get_memory_integration(working_dir: Optional[str] = None,
                           embedding_model=None) -> Optional[MemoryIntegration]:
    """Get or create the global MemoryIntegration instance.
    
    Args:
        working_dir: Working directory (required on first call)
        embedding_model: Optional embedding model
    
    Returns:
        MemoryIntegration instance or None if not initialized
    """
    global _global_integration
    
    if _global_integration is None and working_dir:
        _global_integration = MemoryIntegration(working_dir, embedding_model)
    
    return _global_integration


def reset_memory_integration():
    """Reset the global MemoryIntegration instance."""
    global _global_integration
    _global_integration = None


def init_memory_integration(working_dir: str, embedding_model=None) -> MemoryIntegration:
    """Initialize the global MemoryIntegration instance.
    
    This should be called during agent initialization.
    
    Args:
        working_dir: Working directory for storage
        embedding_model: Optional embedding model
    
    Returns:
        The initialized MemoryIntegration instance
    """
    global _global_integration
    _global_integration = MemoryIntegration(working_dir, embedding_model)
    return _global_integration