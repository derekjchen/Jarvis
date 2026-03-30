# -*- coding: utf-8 -*-
"""Memory Integration for V3.5.

This module integrates the unified memory system with existing components:
- KeyInfoExtractor (V2.1)
- PreferenceManager (V3.0)
- EventTracker (V3.0)

It provides a unified interface for:
1. Processing messages and extracting entities
2. Storing entities in the unified store
3. Injecting relevant entities into prompts
"""
import asyncio
import logging
from datetime import datetime
from pathlib import Path
from typing import Optional, List, TYPE_CHECKING

from .models import Entity, EntityType, EntitySource, EntityPriority
from .store import UnifiedEntityStore
from .retriever import EntityRetriever
from .injector import DynamicInjector

if TYPE_CHECKING:
    from copaw.agents.hooks.key_info_extractor import KeyInfo, KeyInfoExtractor
    from agentscope.message import Msg

logger = logging.getLogger(__name__)


class MemoryIntegration:
    """Integration layer for unified memory system.
    
    This class:
    1. Bridges existing extractors with the unified store
    2. Provides a single interface for prompt injection
    3. Handles entity conversion from different sources
    """
    
    def __init__(self, working_dir: str, embedding_model=None):
        """Initialize memory integration.
        
        Args:
            working_dir: Working directory for storage
            embedding_model: Optional embedding model for vector search
        """
        self.working_dir = Path(working_dir)
        self.storage_dir = self.working_dir / "entity_store"
        
        # Initialize core components
        self.store = UnifiedEntityStore(str(self.storage_dir))
        self.retriever = EntityRetriever(self.store, embedding_model)
        self.injector = DynamicInjector(self.store, self.retriever)
        
        # Lazy load existing extractors
        self._key_info_extractor = None
        self._preference_manager = None
        self._event_tracker = None
        
        logger.info(f"MemoryIntegration initialized for {working_dir}")
    
    @property
    def key_info_extractor(self):
        """Lazy load KeyInfoExtractor."""
        if self._key_info_extractor is None:
            try:
                from copaw.agents.hooks.key_info_extractor import KeyInfoExtractor
                self._key_info_extractor = KeyInfoExtractor()
            except ImportError:
                logger.warning("KeyInfoExtractor not available")
        return self._key_info_extractor
    
    @property
    def preference_manager(self):
        """Lazy load PreferenceManager."""
        if self._preference_manager is None:
            try:
                from copaw.agents.memory.preference.manager import PreferenceManager
                pref_file = self.storage_dir / "preferences.json"
                self._preference_manager = PreferenceManager(str(pref_file))
            except ImportError:
                logger.warning("PreferenceManager not available")
        return self._preference_manager
    
    @property
    def event_tracker(self):
        """Lazy load EventTracker."""
        if self._event_tracker is None:
            try:
                from copaw.agents.memory.events.tracker import EventTracker
                events_file = self.storage_dir / "events.json"
                self._event_tracker = EventTracker(str(events_file))
            except ImportError:
                logger.warning("EventTracker not available")
        return self._event_tracker
    
    async def process_message(self, message: str, msg_id: str = "", 
                              session_id: str = "") -> list[Entity]:
        """Process a message and extract entities.
        
        This method:
        1. Runs all available extractors
        2. Converts results to unified Entity format
        3. Stores entities in the unified store
        
        Args:
            message: The message to process
            msg_id: Source message ID
            session_id: Source session ID
        
        Returns:
            List of extracted entities
        """
        entities = []
        
        # 1. KeyInfo extraction
        if self.key_info_extractor:
            try:
                key_infos = self.key_info_extractor.extract(message)
                for info in key_infos:
                    entity = self._key_info_to_entity(info, msg_id, session_id)
                    entity_id = self.store.add_entity(entity)
                    entity = self.store.get_entity(entity_id)
                    if entity:
                        entities.append(entity)
                    logger.debug(f"Extracted key info: {entity.name}")
            except Exception as e:
                logger.error(f"KeyInfo extraction failed: {e}")
        
        # 2. Preference extraction
        if self.preference_manager:
            try:
                preferences = self.preference_manager.extract_from_text(
                    message, message, msg_id
                )
                for pref in preferences:
                    entity = self._preference_to_entity(pref, msg_id, session_id)
                    entity_id = self.store.add_entity(entity)
                    entity = self.store.get_entity(entity_id)
                    if entity:
                        entities.append(entity)
                    logger.debug(f"Extracted preference: {entity.name}")
            except Exception as e:
                logger.error(f"Preference extraction failed: {e}")
        
        # 3. Event extraction
        if self.event_tracker:
            try:
                events = self.event_tracker.extract_from_text(message, msg_id)
                for event in events:
                    entity = self._event_to_entity(event, msg_id, session_id)
                    entity_id = self.store.add_entity(entity)
                    entity = self.store.get_entity(entity_id)
                    if entity:
                        entities.append(entity)
                    logger.debug(f"Extracted event: {entity.name}")
            except Exception as e:
                logger.error(f"Event extraction failed: {e}")
        
        if entities:
            logger.info(f"Extracted {len(entities)} entities from message")
        
        return entities
    
    def _key_info_to_entity(self, info: "KeyInfo", msg_id: str, 
                            session_id: str) -> Entity:
        """Convert KeyInfo to Entity.
        
        Args:
            info: KeyInfo object
            msg_id: Message ID
            session_id: Session ID
        
        Returns:
            Entity object
        """
        # Map info type to entity type
        type_map = {
            "safety": EntityType.ALLERGY,
            "allergy": EntityType.ALLERGY,
            "constraint": EntityType.CONSTRAINT,
            "preference": EntityType.PREFERENCE,
            "dislike": EntityType.DISLIKE,
            "decision": EntityType.DECISION,
            "contact": EntityType.CONTACT,
        }
        
        entity_type = type_map.get(info.info_type.lower(), EntityType.OTHER)
        
        # Get priority
        priority = getattr(info, 'priority', 50)
        
        # Create entity
        return Entity(
            type=entity_type,
            name=info.content[:50] if len(info.content) > 50 else info.content,
            content=info.content,
            priority=priority,
            source=EntitySource.REGEX,
            confidence=getattr(info, 'confidence', 1.0),
            context=getattr(info, 'context', ''),
            msg_id=msg_id,
            session_id=session_id,
        )
    
    def _preference_to_entity(self, pref: "Preference", msg_id: str,
                              session_id: str) -> Entity:
        """Convert Preference to Entity.
        
        Args:
            pref: Preference object
            msg_id: Message ID
            session_id: Session ID
        
        Returns:
            Entity object
        """
        # Determine entity type
        if pref.sentiment == "like" or pref.sentiment == "prefer":
            entity_type = EntityType.PREFERENCE
        elif pref.sentiment == "dislike" or pref.sentiment == "avoid":
            entity_type = EntityType.DISLIKE
        else:
            entity_type = EntityType.OTHER
        
        return Entity(
            type=entity_type,
            name=pref.content[:50] if len(pref.content) > 50 else pref.content,
            content=pref.content,
            category=pref.topic,
            priority=EntityPriority.MEDIUM.value,
            source=EntitySource.REGEX,
            confidence=pref.confidence,
            context=pref.original_context,
            msg_id=msg_id,
            session_id=session_id,
            tags=[pref.topic] if pref.topic else [],
        )
    
    def _event_to_entity(self, event: "KeyEvent", msg_id: str,
                         session_id: str) -> Entity:
        """Convert KeyEvent to Entity.
        
        Args:
            event: KeyEvent object
            msg_id: Message ID
            session_id: Session ID
        
        Returns:
            Entity object
        """
        # Map event type to entity type
        type_map = {
            "milestone": EntityType.MILESTONE,
            "deadline": EntityType.EVENT,
            "appointment": EntityType.EVENT,
            "travel": EntityType.EVENT,
            "project": EntityType.PROJECT,
            "work": EntityType.EVENT,
        }
        
        event_type_value = event.event_type.value if hasattr(event.event_type, 'value') else str(event.event_type)
        entity_type = type_map.get(event_type_value.lower(), EntityType.EVENT)
        
        # Map importance to priority
        importance_map = {
            "critical": EntityPriority.CRITICAL.value,
            "high": EntityPriority.HIGH.value,
            "medium": EntityPriority.MEDIUM.value,
            "low": EntityPriority.LOW.value,
        }
        
        importance_value = event.importance.value if hasattr(event.importance, 'value') else str(event.importance)
        priority = importance_map.get(importance_value.lower(), EntityPriority.MEDIUM.value)
        
        return Entity(
            type=entity_type,
            name=event.title,
            content=event.description or event.title,
            priority=priority,
            source=EntitySource.REGEX,
            context=event.context,
            msg_id=msg_id,
            session_id=session_id,
            attributes={
                "event_date": str(event.event_date) if event.event_date else None,
                "event_time": event.event_time,
            }
        )
    
    async def inject_to_prompt(self, prompt: str, query: str = "",
                               max_entities: int = 20,
                               max_tokens: int = 2000) -> str:
        """Inject relevant entities into a prompt.
        
        This is the main entry point for prompt enhancement.
        
        Args:
            prompt: The original prompt
            query: User query for relevance
            max_entities: Maximum entities to inject
            max_tokens: Maximum tokens for injection
        
        Returns:
            Enhanced prompt with entity context
        """
        return await self.injector.inject_to_prompt(
            prompt, query, max_entities, max_tokens
        )
    
    def get_entity_summary(self) -> str:
        """Get a summary of stored entities.
        
        Returns:
            Summary string
        """
        return self.injector.get_entity_summary()
    
    def get_safety_summary(self) -> str:
        """Get summary of safety-related entities.
        
        Returns:
            Safety summary string
        """
        return self.injector.get_safety_summary()
    
    def get_store_stats(self) -> dict:
        """Get store statistics.
        
        Returns:
            Statistics dictionary
        """
        return self.store.get_stats()
    
    def clear(self):
        """Clear all stored entities."""
        self.store.clear()
        logger.info("All entities cleared")
    
    # ============================================================
    # V3.5 Integration Methods
    # ============================================================
    
    def add_key_infos(self, key_infos: List["KeyInfo"], 
                      session_id: str = "") -> List[str]:
        """Add KeyInfo objects to the entity store.
        
        This is used by MemoryCompactionHook to persist extracted key info.
        
        Args:
            key_infos: List of KeyInfo objects from KeyInfoExtractor
            session_id: Source session ID
        
        Returns:
            List of entity IDs that were added
        """
        entity_ids = []
        
        for info in key_infos:
            entity = self._key_info_to_entity(info, "", session_id)
            entity_id = self.store.add_entity(entity)
            entity_ids.append(entity_id)
            logger.debug(f"Added entity from KeyInfo: {entity.name} (type={entity.type})")
        
        if entity_ids:
            logger.info(f"Added {len(entity_ids)} entities from KeyInfo")
        
        return entity_ids
    
    def add_key_infos_from_messages(self, messages: List["Msg"],
                                    session_id: str = "") -> List[str]:
        """Extract and store key info from messages.
        
        This is a convenience method for MemoryCompactionHook.
        
        Args:
            messages: List of Msg objects
            session_id: Source session ID
        
        Returns:
            List of entity IDs that were added
        """
        if not self.key_info_extractor:
            logger.warning("KeyInfoExtractor not available")
            return []
        
        key_infos = self.key_info_extractor.extract(messages)
        if not key_infos:
            return []
        
        return self.add_key_infos(key_infos, session_id)
    
    def inject_to_prompt_sync(self, prompt: str, query: str = "",
                              max_entities: int = 20,
                              max_tokens: int = 2000) -> str:
        """Synchronous version of inject_to_prompt.
        
        This is used by react_agent._build_sys_prompt which is synchronous.
        
        Args:
            prompt: The original prompt
            query: User query for relevance
            max_entities: Maximum entities to inject
            max_tokens: Maximum tokens for injection
        
        Returns:
            Enhanced prompt with entity context
        """
        try:
            loop = asyncio.get_running_loop()
            # Already in async context, create a task
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
    
    def get_entities_for_injection(self, query: str = "",
                                   max_entities: int = 20) -> List[Entity]:
        """Get entities that should be injected into a prompt.
        
        This is useful for debugging and testing.
        
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
        
        # 2. Include entities with priority >= 50 (decisions, preferences, etc.)
        other_entities = self.store.get_entities_by_priority(min_priority=50)
        for entity in other_entities:
            if entity.id not in seen_ids:
                all_entities.append(entity)
                seen_ids.add(entity.id)
        
        # 3. Get relevant entities if query provided
        if query:
            try:
                results = asyncio.run(self.retriever.search(query))
                for entity, _ in results:
                    if entity.id not in seen_ids:
                        all_entities.append(entity)
                        seen_ids.add(entity.id)
            except RuntimeError:
                pass
        
        # Sort by priority
        all_entities.sort(key=lambda e: e.priority, reverse=True)
        
        return all_entities[:max_entities]


# Global instance for convenience
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