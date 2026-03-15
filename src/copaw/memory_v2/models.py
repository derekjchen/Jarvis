# -*- coding: utf-8 -*-
"""Data models for semantic memory layer.

This module defines the core data structures for semantic memory:
- Entity: Extracted entities (people, projects, technologies, etc.)
- Relation: Relationships between entities
- SemanticMemory: Structured memory with entities, relations, and summary
- Scene: Contextual scene for memory organization

V2 Enhancement: 
- Added temporal indexing for entities
- Added scene classification (Milestone 2.0)
- Added relation types (Milestone 2.0)
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional
import uuid


class MemoryType(Enum):
    """Type of semantic memory."""
    DECISION = "decision"
    EVENT = "event"
    KNOWLEDGE = "knowledge"
    TODO = "todo"


class EntityType(Enum):
    """Type of extracted entity."""
    PERSON = "person"
    PROJECT = "project"
    TECHNOLOGY = "technology"
    DATE = "date"
    CONCEPT = "concept"
    ORGANIZATION = "organization"
    LOCATION = "location"


class SceneType(Enum):
    """Type of conversation scene.
    
    Milestone 2.0: Scene classification for better memory organization.
    """
    DEVELOPMENT = "development"  # 开发：编码、调试、实现功能
    DESIGN = "design"           # 设计：架构讨论、方案设计
    DECISION = "decision"       # 决策：重要决定、方向选择
    CHAT = "chat"               # 闲聊：日常交流、非正式话题
    DEBUGGING = "debugging"     # 调试：问题排查、错误修复
    UNKNOWN = "unknown"         # 未知：无法确定类型


class RelationType(Enum):
    """Type of relationship between entities.
    
    Milestone 2.0: Relation extraction for knowledge graph.
    """
    BELONGS_TO = "belongs_to"     # 属于：A 属于 B（项目属于组织）
    PARTICIPATES = "participates" # 参与：A 参与 B（人参与项目）
    LIKES = "likes"               # 喜欢：A 喜欢 B（人喜欢技术）
    USES = "uses"                 # 使用：A 使用 B（项目使用技术）
    KNOWS = "knows"               # 认识：A 认识 B（人认识人）
    CREATES = "creates"           # 创建：A 创建 B（人创建项目）
    DEPENDS_ON = "depends_on"     # 依赖：A 依赖 B（模块依赖模块）
    RELATED_TO = "related_to"     # 相关：A 与 B 相关（通用关系）


@dataclass
class Entity:
    """Extracted entity from conversation.
    
    V2 Enhancement: Added temporal indexing fields.
    
    Attributes:
        id: Unique identifier
        name: Entity name
        type: Entity type (person, project, etc.)
        description: Brief description
        attributes: Additional attributes
        related_memory_ids: IDs of memories mentioning this entity
        first_mentioned: When this entity was first mentioned
        last_mentioned: When this entity was last mentioned
        mention_count: How many times this entity has been mentioned
    """
    id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    name: str = ""
    type: EntityType = EntityType.CONCEPT
    description: str = ""
    attributes: dict = field(default_factory=dict)
    related_memory_ids: list[str] = field(default_factory=list)
    # V2: Temporal indexing
    first_mentioned: Optional[datetime] = None
    last_mentioned: Optional[datetime] = None
    mention_count: int = 0

    def update_mention(self) -> None:
        """Update mention timestamp and count."""
        now = datetime.now()
        if self.first_mentioned is None:
            self.first_mentioned = now
        self.last_mentioned = now
        self.mention_count += 1

    def to_dict(self) -> dict:
        """Convert to dictionary for serialization."""
        return {
            "id": self.id,
            "name": self.name,
            "type": self.type.value,
            "description": self.description,
            "attributes": self.attributes,
            "related_memory_ids": self.related_memory_ids,
            "first_mentioned": self.first_mentioned.isoformat() if self.first_mentioned else None,
            "last_mentioned": self.last_mentioned.isoformat() if self.last_mentioned else None,
            "mention_count": self.mention_count,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Entity":
        """Create from dictionary."""
        def parse_datetime(val):
            if val is None:
                return None
            try:
                return datetime.fromisoformat(val)
            except (ValueError, TypeError):
                return None

        return cls(
            id=data.get("id", str(uuid.uuid4())[:8]),
            name=data.get("name", ""),
            type=EntityType(data.get("type", "concept")),
            description=data.get("description", ""),
            attributes=data.get("attributes", {}),
            related_memory_ids=data.get("related_memory_ids", []),
            first_mentioned=parse_datetime(data.get("first_mentioned")),
            last_mentioned=parse_datetime(data.get("last_mentioned")),
            mention_count=data.get("mention_count", 0),
        )


@dataclass
class Relation:
    """Relationship between two entities.
    
    V2 Enhancement: 
    - Added relation types
    - Added temporal context
    - Added confidence scoring
    """
    id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    source_id: str = ""
    target_id: str = ""
    relation_type: RelationType = RelationType.RELATED_TO
    description: str = ""
    confidence: float = 1.0
    evidence: str = ""  # 证据文本
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "source_id": self.source_id,
            "target_id": self.target_id,
            "relation_type": self.relation_type.value,
            "description": self.description,
            "confidence": self.confidence,
            "evidence": self.evidence,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Relation":
        def parse_datetime(val):
            if val is None:
                return datetime.now()
            try:
                return datetime.fromisoformat(val)
            except (ValueError, TypeError):
                return datetime.now()
        
        return cls(
            id=data.get("id", str(uuid.uuid4())[:8]),
            source_id=data.get("source_id", ""),
            target_id=data.get("target_id", ""),
            relation_type=RelationType(data.get("relation_type", "related_to")),
            description=data.get("description", ""),
            confidence=data.get("confidence", 1.0),
            evidence=data.get("evidence", ""),
            created_at=parse_datetime(data.get("created_at")),
            updated_at=parse_datetime(data.get("updated_at")),
        )


@dataclass
class Scene:
    """Conversation scene for memory organization.
    
    Milestone 2.0: Scene-based memory organization.
    
    Attributes:
        id: Unique identifier
        scene_type: Type of scene (development, design, etc.)
        title: Brief title of the scene
        summary: Summary of what happened
        entities: Entities mentioned in this scene
        relations: Relations discovered in this scene
        start_time: When the scene started
        end_time: When the scene ended
        context_snapshot: Key context at scene start
        parent_scene_id: Parent scene if this is a sub-scene
        child_scene_ids: Child scenes if this contains sub-scenes
    """
    id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    scene_type: SceneType = SceneType.UNKNOWN
    title: str = ""
    summary: str = ""
    entities: list[str] = field(default_factory=list)  # Entity IDs
    relations: list[str] = field(default_factory=list)  # Relation IDs
    start_time: datetime = field(default_factory=datetime.now)
    end_time: Optional[datetime] = None
    context_snapshot: dict = field(default_factory=dict)
    parent_scene_id: Optional[str] = None
    child_scene_ids: list[str] = field(default_factory=list)
    
    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "scene_type": self.scene_type.value,
            "title": self.title,
            "summary": self.summary,
            "entities": self.entities,
            "relations": self.relations,
            "start_time": self.start_time.isoformat(),
            "end_time": self.end_time.isoformat() if self.end_time else None,
            "context_snapshot": self.context_snapshot,
            "parent_scene_id": self.parent_scene_id,
            "child_scene_ids": self.child_scene_ids,
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> "Scene":
        def parse_datetime(val):
            if val is None:
                return None
            try:
                return datetime.fromisoformat(val)
            except (ValueError, TypeError):
                return None
        
        return cls(
            id=data.get("id", str(uuid.uuid4())[:8]),
            scene_type=SceneType(data.get("scene_type", "unknown")),
            title=data.get("title", ""),
            summary=data.get("summary", ""),
            entities=data.get("entities", []),
            relations=data.get("relations", []),
            start_time=parse_datetime(data.get("start_time")) or datetime.now(),
            end_time=parse_datetime(data.get("end_time")),
            context_snapshot=data.get("context_snapshot", {}),
            parent_scene_id=data.get("parent_scene_id"),
            child_scene_ids=data.get("child_scene_ids", []),
        )


@dataclass
class SemanticMemory:
    """Structured semantic memory."""
    id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    type: MemoryType = MemoryType.KNOWLEDGE
    summary: str = ""
    entities: list[Entity] = field(default_factory=list)
    relations: list[Relation] = field(default_factory=list)
    source_ids: list[str] = field(default_factory=list)
    created_at: datetime = field(default_factory=datetime.now)
    importance: float = 0.5
    tags: list[str] = field(default_factory=list)
    # V2: Scene reference
    scene_id: Optional[str] = None

    def to_dict(self) -> dict:
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
            "scene_id": self.scene_id,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "SemanticMemory":
        created_at = datetime.now()
        if "created_at" in data:
            try:
                created_at = datetime.fromisoformat(data["created_at"])
            except (ValueError, TypeError):
                pass
        return cls(
            id=data.get("id", str(uuid.uuid4())[:8]),
            type=MemoryType(data.get("type", "knowledge")),
            summary=data.get("summary", ""),
            entities=[Entity.from_dict(e) for e in data.get("entities", [])],
            relations=[Relation.from_dict(r) for r in data.get("relations", [])],
            source_ids=data.get("source_ids", []),
            created_at=created_at,
            importance=data.get("importance", 0.5),
            tags=data.get("tags", []),
            scene_id=data.get("scene_id"),
        )

    def add_entity(self, entity: Entity) -> None:
        if entity.id not in [e.id for e in self.entities]:
            self.entities.append(entity)

    def add_relation(self, relation: Relation) -> None:
        self.relations.append(relation)

