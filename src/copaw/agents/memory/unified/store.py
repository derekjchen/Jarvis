# -*- coding: utf-8 -*-
"""Unified Entity Store for Memory V3.5.

This module provides a centralized storage for all extracted entities,
with persistence, deduplication, and efficient retrieval capabilities.
"""
import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Optional, Callable

from .models import Entity, Relation, EntityType

logger = logging.getLogger(__name__)


class UnifiedEntityStore:
    """Centralized storage for all memory entities.
    
    This class provides:
    - Persistent storage (JSON files)
    - Automatic deduplication
    - Type-based queries
    - Priority-based queries
    - Full-text search support
    """
    
    def __init__(self, storage_dir: str, auto_save: bool = True):
        """Initialize the entity store.
        
        Args:
            storage_dir: Directory for storage files
            auto_save: Whether to auto-save on changes
        """
        self.storage_dir = Path(storage_dir)
        self.storage_dir.mkdir(parents=True, exist_ok=True)
        
        self.entities_file = self.storage_dir / "entities.json"
        self.relations_file = self.storage_dir / "relations.json"
        
        self.auto_save = auto_save
        
        # In-memory storage
        self.entities: dict[str, Entity] = {}
        self.relations: dict[str, Relation] = {}
        
        # Index for faster lookups
        self._type_index: dict[EntityType, set[str]] = {}
        self._priority_index: dict[int, set[str]] = {}  # priority bucket -> entity ids
        
        # Load existing data
        self._load()
        
        logger.info(f"UnifiedEntityStore initialized with {len(self.entities)} entities")
    
    def _load(self):
        """Load entities and relations from disk."""
        # Load entities
        if self.entities_file.exists():
            try:
                data = json.loads(self.entities_file.read_text(encoding="utf-8"))
                for entity_id, entity_data in data.items():
                    try:
                        self.entities[entity_id] = Entity.from_dict(entity_data)
                    except Exception as e:
                        logger.warning(f"Failed to load entity {entity_id}: {e}")
                logger.info(f"Loaded {len(self.entities)} entities from disk")
            except Exception as e:
                logger.error(f"Failed to load entities: {e}")
        
        # Load relations
        if self.relations_file.exists():
            try:
                data = json.loads(self.relations_file.read_text(encoding="utf-8"))
                for relation_id, relation_data in data.items():
                    try:
                        self.relations[relation_id] = Relation.from_dict(relation_data)
                    except Exception as e:
                        logger.warning(f"Failed to load relation {relation_id}: {e}")
                logger.info(f"Loaded {len(self.relations)} relations from disk")
            except Exception as e:
                logger.error(f"Failed to load relations: {e}")
        
        # Build indexes
        self._rebuild_indexes()
    
    def _rebuild_indexes(self):
        """Rebuild search indexes."""
        self._type_index.clear()
        self._priority_index.clear()
        
        for entity in self.entities.values():
            # Type index
            if entity.type not in self._type_index:
                self._type_index[entity.type] = set()
            self._type_index[entity.type].add(entity.id)
            
            # Priority index (bucket by 10s)
            bucket = (entity.priority // 10) * 10
            if bucket not in self._priority_index:
                self._priority_index[bucket] = set()
            self._priority_index[bucket].add(entity.id)
    
    def save(self):
        """Save entities and relations to disk."""
        # Save entities
        entities_data = {
            entity_id: entity.to_dict() 
            for entity_id, entity in self.entities.items()
        }
        self.entities_file.write_text(
            json.dumps(entities_data, ensure_ascii=False, indent=2),
            encoding="utf-8"
        )
        
        # Save relations
        relations_data = {
            relation_id: relation.to_dict()
            for relation_id, relation in self.relations.items()
        }
        self.relations_file.write_text(
            json.dumps(relations_data, ensure_ascii=False, indent=2),
            encoding="utf-8"
        )
        
        logger.debug(f"Saved {len(self.entities)} entities and {len(self.relations)} relations")
    
    def add_entity(self, entity: Entity) -> str:
        """Add an entity to the store.
        
        If a similar entity exists, updates it instead of creating duplicate.
        
        Args:
            entity: Entity to add
        
        Returns:
            Entity ID (either new or existing)
        """
        # Check for similar entity
        existing = self._find_similar(entity)
        if existing:
            # Update existing entity
            existing.last_updated = datetime.now()
            existing.access_count += 1
            if entity.context and not existing.context:
                existing.context = entity.context
            if entity.attributes:
                existing.attributes.update(entity.attributes)
            
            logger.debug(f"Updated existing entity: {existing.id}")
            
            if self.auto_save:
                self.save()
            
            return existing.id
        
        # Add new entity
        self.entities[entity.id] = entity
        
        # Update indexes
        if entity.type not in self._type_index:
            self._type_index[entity.type] = set()
        self._type_index[entity.type].add(entity.id)
        
        bucket = (entity.priority // 10) * 10
        if bucket not in self._priority_index:
            self._priority_index[bucket] = set()
        self._priority_index[bucket].add(entity.id)
        
        logger.debug(f"Added new entity: {entity.id} ({entity.type.value})")
        
        if self.auto_save:
            self.save()
        
        return entity.id
    
    def get_entity(self, entity_id: str) -> Optional[Entity]:
        """Get an entity by ID."""
        return self.entities.get(entity_id)
    
    def get_all_entities(self) -> list[Entity]:
        """Get all entities."""
        return list(self.entities.values())
    
    def get_entities_by_type(self, entity_type: EntityType) -> list[Entity]:
        """Get entities by type."""
        if entity_type not in self._type_index:
            return []
        return [
            self.entities[eid] 
            for eid in self._type_index[entity_type] 
            if eid in self.entities
        ]
    
    def get_entities_by_priority(self, min_priority: int = 0, 
                                   max_priority: int = 100) -> list[Entity]:
        """Get entities within priority range."""
        result = []
        for bucket, entity_ids in self._priority_index.items():
            if bucket >= min_priority:
                for eid in entity_ids:
                    if eid in self.entities:
                        entity = self.entities[eid]
                        if min_priority <= entity.priority <= max_priority:
                            result.append(entity)
        return result
    
    def get_safety_entities(self) -> list[Entity]:
        """Get all safety-related entities (priority >= 100)."""
        return self.get_entities_by_priority(min_priority=100)
    
    def get_important_entities(self) -> list[Entity]:
        """Get all important entities (priority >= 80)."""
        return self.get_entities_by_priority(min_priority=80)
    
    def delete_entity(self, entity_id: str) -> bool:
        """Delete an entity by ID."""
        if entity_id not in self.entities:
            return False
        
        entity = self.entities[entity_id]
        
        # Remove from indexes
        if entity.type in self._type_index:
            self._type_index[entity.type].discard(entity_id)
        
        bucket = (entity.priority // 10) * 10
        if bucket in self._priority_index:
            self._priority_index[bucket].discard(entity_id)
        
        # Remove from storage
        del self.entities[entity_id]
        
        # Remove related relations
        relations_to_remove = [
            rid for rid, r in self.relations.items()
            if r.source_id == entity_id or r.target_id == entity_id
        ]
        for rid in relations_to_remove:
            del self.relations[rid]
        
        if self.auto_save:
            self.save()
        
        logger.debug(f"Deleted entity: {entity_id}")
        return True
    
    def update_entity(self, entity_id: str, 
                      update_fn: Callable[[Entity], None]) -> bool:
        """Update an entity using a callback function.
        
        Args:
            entity_id: Entity ID
            update_fn: Function that modifies the entity
        
        Returns:
            True if entity was updated, False if not found
        """
        if entity_id not in self.entities:
            return False
        
        entity = self.entities[entity_id]
        old_type = entity.type
        old_priority = entity.priority
        
        update_fn(entity)
        entity.last_updated = datetime.now()
        
        # Update indexes if type or priority changed
        if entity.type != old_type:
            if old_type in self._type_index:
                self._type_index[old_type].discard(entity_id)
            if entity.type not in self._type_index:
                self._type_index[entity.type] = set()
            self._type_index[entity.type].add(entity_id)
        
        if entity.priority != old_priority:
            old_bucket = (old_priority // 10) * 10
            new_bucket = (entity.priority // 10) * 10
            
            if old_bucket in self._priority_index:
                self._priority_index[old_bucket].discard(entity_id)
            if new_bucket not in self._priority_index:
                self._priority_index[new_bucket] = set()
            self._priority_index[new_bucket].add(entity_id)
        
        if self.auto_save:
            self.save()
        
        return True
    
    def search(self, query: str, top_k: int = 10) -> list[tuple[Entity, float]]:
        """Search entities by keyword.
        
        Args:
            query: Search query
            top_k: Maximum results
        
        Returns:
            List of (entity, score) tuples
        """
        query_lower = query.lower()
        query_words = set(query_lower.split())
        
        results = []
        
        for entity in self.entities.values():
            if entity.is_expired():
                continue
            
            score = 0.0
            
            # Name exact match
            if query_lower == entity.name.lower():
                score += 1.0
            # Name contains query
            elif query_lower in entity.name.lower():
                score += 0.7
            
            # Content match
            if query_lower in entity.content.lower():
                score += 0.5
            
            # Tags match
            for tag in entity.tags:
                if query_lower in tag.lower():
                    score += 0.3
                    break
            
            # Category match
            if query_lower in entity.category.lower():
                score += 0.2
            
            # Word overlap
            entity_words = set(entity.name.lower().split()) | set(entity.content.lower().split())
            overlap = len(query_words & entity_words) / max(len(query_words), 1)
            score += overlap * 0.3
            
            if score > 0:
                results.append((entity, min(score, 1.0)))
        
        # Sort by score, then by priority
        results.sort(key=lambda x: (x[1], x[0].priority), reverse=True)
        
        return results[:top_k]
    
    def add_relation(self, relation: Relation) -> str:
        """Add a relation between entities."""
        self.relations[relation.id] = relation
        
        if self.auto_save:
            self.save()
        
        return relation.id
    
    def get_relations_for_entity(self, entity_id: str) -> list[Relation]:
        """Get all relations involving an entity."""
        return [
            r for r in self.relations.values()
            if r.source_id == entity_id or r.target_id == entity_id
        ]
    
    def clear(self):
        """Clear all entities and relations."""
        self.entities.clear()
        self.relations.clear()
        self._type_index.clear()
        self._priority_index.clear()
        
        if self.auto_save:
            self.save()
    
    def get_stats(self) -> dict:
        """Get store statistics."""
        type_counts = {}
        for entity_type, ids in self._type_index.items():
            type_counts[entity_type.value] = len(ids)
        
        return {
            "total_entities": len(self.entities),
            "total_relations": len(self.relations),
            "by_type": type_counts,
            "safety_entities": len(self.get_safety_entities()),
            "important_entities": len(self.get_important_entities()),
        }
    
    def _find_similar(self, entity: Entity) -> Optional[Entity]:
        """Find a similar existing entity.
        
        Two entities are considered similar if:
        - Same type
        - Same or very similar name
        """
        # Check entities of the same type
        if entity.type not in self._type_index:
            return None
        
        entity_name_lower = entity.name.lower().strip()
        
        for existing_id in self._type_index[entity.type]:
            if existing_id not in self.entities:
                continue
            
            existing = self.entities[existing_id]
            existing_name_lower = existing.name.lower().strip()
            
            # Exact match
            if entity_name_lower == existing_name_lower:
                return existing
            
            # One contains the other
            if (entity_name_lower in existing_name_lower or 
                existing_name_lower in entity_name_lower):
                return existing
        
        return None