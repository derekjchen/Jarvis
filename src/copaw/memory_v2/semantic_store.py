# -*- coding: utf-8 -*-
"""Semantic Store for persisting semantic memories.

This module provides the SemanticStore class that:
1. Persists semantic memories to files
2. Loads semantic memories from files
3. Manages the entity knowledge base
"""

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Optional

from .models import Entity, EntityType, MemoryType, Relation, SemanticMemory

logger = logging.getLogger(__name__)


class SemanticStore:
    """Store for semantic memories and entity knowledge base.

    Persists memories to JSON files and manages the entity
    knowledge base for cross-session entity tracking.
    """

    def __init__(self, store_dir: str | Path):
        """Initialize the semantic store.

        Args:
            store_dir: Directory to store semantic memories
        """
        self.store_dir = Path(store_dir)
        self.store_dir.mkdir(parents=True, exist_ok=True)

        # Entity knowledge base
        self.entities_file = self.store_dir / "entities.json"
        self.entity_kb: dict[str, Entity] = {}

        # Memories file
        self.memories_file = self.store_dir / "semantic_memories.json"
        self.memories: list[SemanticMemory] = []

        # Load existing data
        self._load()

    def _load(self) -> None:
        """Load existing data from files."""
        # Load entities
        if self.entities_file.exists():
            try:
                with open(self.entities_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                self.entity_kb = {
                    name: Entity.from_dict(e)
                    for name, e in data.items()
                }
                logger.info(f"Loaded {len(self.entity_kb)} entities from store")
            except Exception as e:
                logger.error(f"Failed to load entities: {e}")

        # Load memories
        if self.memories_file.exists():
            try:
                with open(self.memories_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                self.memories = [
                    SemanticMemory.from_dict(m)
                    for m in data
                ]
                logger.info(f"Loaded {len(self.memories)} memories from store")
            except Exception as e:
                logger.error(f"Failed to load memories: {e}")

    def _save_entities(self) -> None:
        """Save entity knowledge base to file."""
        try:
            data = {
                name: entity.to_dict()
                for name, entity in self.entity_kb.items()
            }
            with open(self.entities_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"Failed to save entities: {e}")

    def _save_memories(self) -> None:
        """Save memories to file."""
        try:
            data = [m.to_dict() for m in self.memories]
            with open(self.memories_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"Failed to save memories: {e}")

    # === Entity Management ===

    def add_entity(self, entity: Entity) -> None:
        """Add or update an entity in the knowledge base.

        Args:
            entity: Entity to add
        """
        if entity.name in self.entity_kb:
            # Merge with existing
            existing = self.entity_kb[entity.name]
            if len(entity.description) > len(existing.description):
                existing.description = entity.description
            existing.attributes.update(entity.attributes)
            existing.related_memory_ids.extend(entity.related_memory_ids)
            # Remove duplicates
            existing.related_memory_ids = list(set(existing.related_memory_ids))
        else:
            self.entity_kb[entity.name] = entity

        self._save_entities()
        logger.debug(f"Added/updated entity: {entity.name}")

    def get_entity(self, name: str) -> Optional[Entity]:
        """Get an entity by name.

        Args:
            name: Entity name

        Returns:
            Entity if found, None otherwise
        """
        return self.entity_kb.get(name)

    def get_all_entities(self) -> list[Entity]:
        """Get all entities.

        Returns:
            List of all entities
        """
        return list(self.entity_kb.values())

    def get_entities_by_type(self, entity_type: EntityType) -> list[Entity]:
        """Get entities of a specific type.

        Args:
            entity_type: Type to filter by

        Returns:
            List of matching entities
        """
        return [e for e in self.entity_kb.values() if e.type == entity_type]

    # === Memory Management ===

    def add_memory(self, memory: SemanticMemory) -> None:
        """Add a semantic memory to the store.

        Args:
            memory: Memory to add
        """
        self.memories.append(memory)

        # Update entity knowledge base
        for entity in memory.entities:
            if memory.id not in entity.related_memory_ids:
                entity.related_memory_ids.append(memory.id)
            self.add_entity(entity)

        self._save_memories()
        logger.info(f"Added memory: {memory.id}")

    def get_memory(self, memory_id: str) -> Optional[SemanticMemory]:
        """Get a memory by ID.

        Args:
            memory_id: Memory ID

        Returns:
            Memory if found, None otherwise
        """
        for m in self.memories:
            if m.id == memory_id:
                return m
        return None

    def get_memories_by_type(self, memory_type: MemoryType) -> list[SemanticMemory]:
        """Get memories of a specific type.

        Args:
            memory_type: Type to filter by

        Returns:
            List of matching memories
        """
        return [m for m in self.memories if m.type == memory_type]

    def get_recent_memories(self, limit: int = 10) -> list[SemanticMemory]:
        """Get most recent memories.

        Args:
            limit: Maximum number to return

        Returns:
            List of recent memories
        """
        sorted_memories = sorted(
            self.memories,
            key=lambda m: m.created_at,
            reverse=True,
        )
        return sorted_memories[:limit]

    def get_important_memories(self, min_importance: float = 0.7) -> list[SemanticMemory]:
        """Get high-importance memories.

        Args:
            min_importance: Minimum importance threshold

        Returns:
            List of important memories
        """
        return [m for m in self.memories if m.importance >= min_importance]

    def search_memories(self, query: str) -> list[SemanticMemory]:
        """Search memories by content.

        Args:
            query: Search query

        Returns:
            List of matching memories
        """
        query_lower = query.lower()
        results = []

        for m in self.memories:
            # Search in summary
            if query_lower in m.summary.lower():
                results.append(m)
                continue

            # Search in entities
            for e in m.entities:
                if query_lower in e.name.lower() or query_lower in e.description.lower():
                    results.append(m)
                    break

            # Search in tags
            if any(query_lower in tag.lower() for tag in m.tags):
                results.append(m)

        return results

    def clear_memories(self) -> None:
        """Clear all memories."""
        self.memories.clear()
        self._save_memories()
        logger.info("Cleared all memories")

    def get_stats(self) -> dict:
        """Get statistics about the store.

        Returns:
            Dictionary with statistics
        """
        type_counts = {}
        for m in self.memories:
            type_name = m.type.value
            type_counts[type_name] = type_counts.get(type_name, 0) + 1

        entity_type_counts = {}
        for e in self.entity_kb.values():
            type_name = e.type.value
            entity_type_counts[type_name] = entity_type_counts.get(type_name, 0) + 1

        return {
            "total_memories": len(self.memories),
            "total_entities": len(self.entity_kb),
            "memory_types": type_counts,
            "entity_types": entity_type_counts,
        }