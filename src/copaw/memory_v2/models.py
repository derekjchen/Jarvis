# -*- coding: utf-8 -*-
"""Data models for semantic memory layer.

This module defines the core data structures for semantic memory:
- Entity: Extracted entities (people, projects, technologies, etc.)
- Relation: Relationships between entities
- SemanticMemory: Structured memory with entities, relations, and summary
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional
import uuid


class MemoryType(Enum):
    """Type of semantic memory."""
    DECISION = "decision"    # 重要决策
    EVENT = "event"          # 事件/里程碑
    KNOWLEDGE = "knowledge"  # 知识/信息
    TODO = "todo"            # 待办事项


class EntityType(Enum):
    """Type of extracted entity."""
    PERSON = "person"        # 人物
    PROJECT = "project"      # 项目
    TECHNOLOGY = "technology"  # 技术
    DATE = "date"            # 日期
    CONCEPT = "concept"      # 概念
    ORGANIZATION = "organization"  # 组织
    LOCATION = "location"    # 地点


@dataclass
class Entity:
    """Extracted entity from conversation.
    
    Attributes:
        id: Unique identifier
        name: Entity name
        type: Entity type (person, project, etc.)
        description: Brief description
        attributes: Additional attributes (e.g., {"role": "developer"})
        related_memory_ids: IDs of memories mentioning this entity
    """
    id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    name: str = ""
    type: EntityType = EntityType.CONCEPT
    description: str = ""
    attributes: dict = field(default_factory=dict)
    related_memory_ids: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        """Convert to dictionary for serialization."""
        return {
            "id": self.id,
            "name": self.name,
            "type": self.type.value,
            "description": self.description,
            "attributes": self.attributes,
            "related_memory_ids": self.related_memory_ids,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Entity":
        """Create from dictionary."""
        return cls(
            id=data.get("id", str(uuid.uuid4())[:8]),
            name=data.get("name", ""),
            type=EntityType(data.get("type", "concept")),
            description=data.get("description", ""),
            attributes=data.get("attributes", {}),
            related_memory_ids=data.get("related_memory_ids", []),
        )


@dataclass
class Relation:
    """Relationship between two entities.
    
    Attributes:
        source_id: Source entity ID
        target_id: Target entity ID
        relation_type: Type of relation (e.g., "works_on", "depends_on")
        confidence: Confidence score (0-1)
    """
    source_id: str = ""
    target_id: str = ""
    relation_type: str = ""
    confidence: float = 1.0

    def to_dict(self) -> dict:
        """Convert to dictionary for serialization."""
        return {
            "source_id": self.source_id,
            "target_id": self.target_id,
            "relation_type": self.relation_type,
            "confidence": self.confidence,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Relation":
        """Create from dictionary."""
        return cls(
            source_id=data.get("source_id", ""),
            target_id=data.get("target_id", ""),
            relation_type=data.get("relation_type", ""),
            confidence=data.get("confidence", 1.0),
        )


@dataclass
class SemanticMemory:
    """Structured semantic memory.
    
    A semantic memory is a processed, structured representation of
    conversation content, including summary, entities, and relations.
    
    Attributes:
        id: Unique identifier
        type: Memory type (decision, event, knowledge, todo)
        summary: Brief summary of the memory
        entities: List of extracted entities
        relations: List of relations between entities
        source_ids: IDs of source atomic memories
        created_at: Creation timestamp
        importance: Importance score (0-1) for ranking
        tags: Optional tags for categorization
    """
    id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    type: MemoryType = MemoryType.KNOWLEDGE
    summary: str = ""
    entities: list[Entity] = field(default_factory=list)
    relations: list[Relation] = field(default_factory=list)
    source_ids: list[str] = field(default_factory=list)
    created_at: datetime = field(default_factory=datetime.now)
    importance: float = 0.5
    tags: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        """Convert to dictionary for serialization."""
        return {
            "id": self.id,
            "type": self.type.value,
            "summary": self.summary,
            "entities": [e.to_dict() for e in self.entities],
            "relations": [r.to_dict() for r in self.relations],
            "source_ids": self.source_ids,
            "created_at": self.created_at.isoformat(),
            "importance": self.importance,
            "tags": self.tags,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "SemanticMemory":
        """Create from dictionary."""
        return cls(
            id=data.get("id", str(uuid.uuid4())[:8]),
            type=MemoryType(data.get("type", "knowledge")),
            summary=data.get("summary", ""),
            entities=[Entity.from_dict(e) for e in data.get("entities", [])],
            relations=[Relation.from_dict(r) for r in data.get("relations", [])],
            source_ids=data.get("source_ids", []),
            created_at=datetime.fromisoformat(data["created_at"]) if "created_at" in data else datetime.now(),
            importance=data.get("importance", 0.5),
            tags=data.get("tags", []),
        )

    def add_entity(self, entity: Entity) -> None:
        """Add an entity to this memory."""
        if entity.id not in [e.id for e in self.entities]:
            self.entities.append(entity)

    def add_relation(self, relation: Relation) -> None:
        """Add a relation to this memory."""
        self.relations.append(relation)