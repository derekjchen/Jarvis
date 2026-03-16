# -*- coding: utf-8 -*-
"""Memory V2 Bridge - Integration layer between Jarvis and Memory V2.

This module provides a bridge that:
1. Intercepts messages from Jarvis conversation
2. Processes them through Memory V2 pipeline
3. Provides enhanced context for responses

Integration Points:
- Called from MemoryManager or Agent hooks
- Works alongside existing ReMe system
- Provides A/B testing capability
"""

import logging
from datetime import datetime
from pathlib import Path
from typing import Optional
from .models import Entity, EntityType, Relation, RelationType, Scene, SceneType
from .semantic_store import SemanticStore
from .scene_classifier import SceneClassifier
from .relation_extractor import RelationExtractor
from .entity_extractor import EntityExtractor

logger = logging.getLogger(__name__)


class MemoryV2Bridge:
    """Bridge between Jarvis conversation flow and Memory V2.
    
    Usage:
        bridge = MemoryV2Bridge(chat_model)
        
        # Process each message
        context = bridge.process_message(
            user_id="derek",
            message="我正在开发 Memory V2",
            session_id="session_123"
        )
        
        # Get context for response
        entity_context = bridge.get_relevant_context("Memory V2")
    """
    
    def __init__(
        self,
        chat_model,
        storage_dir: Optional[Path] = None,
        enable_scene: bool = True,
        enable_relation: bool = True,
    ):
        """Initialize Memory V2 bridge.
        
        Args:
            chat_model: LLM for entity extraction
            storage_dir: Directory for persistent storage
            enable_scene: Whether to enable scene classification
            enable_relation: Whether to enable relation extraction
        """
        self.chat_model = chat_model
        self.enable_scene = enable_scene
        self.enable_relation = enable_relation
        
        # Initialize components
        self.store = SemanticStore(storage_dir=storage_dir)
        self.scene_classifier = SceneClassifier() if enable_scene else None
        self.entity_extractor = EntityExtractor(chat_model) if chat_model else None
        self.relation_extractor = RelationExtractor() if enable_relation else None
        
        # Current scene tracking
        self._current_scene: Optional[Scene] = None
        self._scene_buffer: list[str] = []  # Messages in current scene
        
        logger.info(
            f"MemoryV2Bridge initialized (scene={enable_scene}, relation={enable_relation})"
        )
    
    async def process_message(
        self,
        user_id: str,
        message: str,
        session_id: Optional[str] = None,
    ) -> dict:
        """Process a message through Memory V2 pipeline.
        
        Args:
            user_id: User identifier
            message: The message text
            session_id: Optional session identifier
            
        Returns:
            Processing results including scene, entities, relations
        """
        results = {
            "user_id": user_id,
            "message": message[:100],  # Truncated for logging
            "scene": None,
            "entities": [],
            "relations": [],
            "scene_changed": False,
        }
        
        try:
            # 1. Scene classification
            if self.enable_scene and self.scene_classifier:
                scene_type, confidence, title = self.scene_classifier.classify(message)
                results["scene"] = {
                    "type": scene_type.value,
                    "confidence": confidence,
                    "title": title,
                }
                
                # Check if scene changed
                if self._should_start_new_scene(scene_type, confidence):
                    self._start_new_scene(scene_type, title, user_id, session_id)
                    results["scene_changed"] = True
                
                # Add message to scene buffer
                self._scene_buffer.append(message)
            
            # 2. Entity extraction (async, requires LLM)
            if self.entity_extractor:
                try:
                    entities = await self.entity_extractor.extract(message)
                    for entity in entities:
                        stored = self.store.add_entity(entity)
                        results["entities"].append({
                            "name": stored.name,
                            "type": stored.type.value,
                            "description": stored.description,
                        })
                        
                        # Add to current scene
                        if self._current_scene:
                            self._current_scene.entities.append(stored.id)
                except Exception as e:
                    logger.warning(f"Entity extraction failed: {e}")
            
            # 3. Relation extraction
            if self.enable_relation and self.relation_extractor and results["entities"]:
                recent_entities = self.store.get_all_entities()[-10:]  # Last 10 entities
                relations = self.relation_extractor.extract(message, recent_entities)
                for relation in relations:
                    stored = self.store.add_relation(relation)
                    results["relations"].append({
                        "source": stored.source_id[:8],
                        "target": stored.target_id[:8],
                        "type": stored.relation_type.value,
                    })
                    
                    # Add to current scene
                    if self._current_scene:
                        self._current_scene.relations.append(stored.id)
            
            logger.debug(f"Processed message: {results}")
            
        except Exception as e:
            logger.error(f"Error processing message: {e}", exc_info=True)
        
        return results
    
    def _should_start_new_scene(self, scene_type: SceneType, confidence: float) -> bool:
        """Check if we should start a new scene."""
        if not self._current_scene:
            return True
        
        # Start new scene if type changed and confidence is high
        if (
            self._current_scene.scene_type != scene_type
            and confidence > 0.8
        ):
            return True
        
        return False
    
    def _start_new_scene(
        self,
        scene_type: SceneType,
        title: str,
        user_id: str,
        session_id: Optional[str],
    ):
        """Start a new scene."""
        # Save current scene if exists
        if self._current_scene:
            self._current_scene.end_time = datetime.now()
            self.store.add_scene(self._current_scene)
            logger.info(f"Ended scene: {self._current_scene.title}")
        
        # Create new scene
        self._current_scene = Scene(
            scene_type=scene_type,
            title=title,
            summary="",
            entities=[],
            relations=[],
            metadata={
                "user_id": user_id,
                "session_id": session_id,
            }
        )
        self._scene_buffer = []
        
        logger.info(f"Started new scene: {title} ({scene_type.value})")
    
    def get_relevant_context(self, query: str, max_entities: int = 5) -> str:
        """Get relevant context for a query.
        
        Args:
            query: The query text
            max_entities: Maximum entities to include
            
        Returns:
            Context string for LLM prompt
        """
        context_parts = []
        
        # 1. Search for relevant entities
        entities = self.store.search_entities(query, limit=max_entities)
        if entities:
            context_parts.append("相关实体:")
            for entity in entities:
                entity_context = self.store.get_entity_context(entity.name, max_chars=200)
                context_parts.append(f"- {entity_context}")
        
        # 2. Add current scene info
        if self._current_scene:
            context_parts.append(f"\n当前场景: {self._current_scene.title}")
            if self._current_scene.entities:
                context_parts.append(f"涉及实体: {len(self._current_scene.entities)} 个")
        
        return "\n".join(context_parts) if context_parts else ""
    
    def get_entity_history(self, entity_name: str) -> dict:
        """Get history of an entity across scenes.
        
        Args:
            entity_name: Name of the entity
            
        Returns:
            History including scenes and relations
        """
        entity = self.store.get_entity_by_name(entity_name)
        if not entity:
            return {"error": f"Entity not found: {entity_name}"}
        
        # Get scenes mentioning this entity
        scenes = self.store.get_scenes_by_entity(entity.id)
        
        # Get relations
        related = self.store.get_related_entities(entity.id)
        
        return {
            "entity": {
                "name": entity.name,
                "type": entity.type.value,
                "description": entity.description,
                "mention_count": entity.mention_count,
                "first_seen": entity.created_at.isoformat(),
            },
            "scenes": [
                {
                    "title": s.title,
                    "type": s.scene_type.value,
                    "time": s.start_time.isoformat(),
                }
                for s in scenes
            ],
            "relations": [
                {
                    "entity": e.name,
                    "relation": r.relation_type.value,
                    "description": r.description,
                }
                for e, r in related
            ],
        }
    
    def get_stats(self) -> dict:
        """Get Memory V2 statistics."""
        return self.store.get_stats()
    
    def end_session(self):
        """End the current session and save state."""
        if self._current_scene:
            self._current_scene.end_time = datetime.now()
            self.store.add_scene(self._current_scene)
            logger.info(f"Ended session with scene: {self._current_scene.title}")
            self._current_scene = None

