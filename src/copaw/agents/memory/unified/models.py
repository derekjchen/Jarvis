# -*- coding: utf-8 -*-
"""Unified data models for Memory V3.5.

This module defines the core data structures for the unified memory system,
including Entity and Relation models that can represent all types of
extracted information.
"""
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional, Any
import uuid
import json


class EntityType(Enum):
    """Types of entities that can be stored."""
    # Safety related (highest priority)
    ALLERGY = "allergy"           # Allergy information
    CONSTRAINT = "constraint"     # Dietary or other constraints
    
    # Preferences
    PREFERENCE = "preference"     # Positive preference
    DISLIKE = "dislike"          # Negative preference
    
    # Decisions
    DECISION = "decision"        # Important decisions
    
    # People and relationships
    PERSON = "person"            # Person entity
    RELATION = "relation"        # Relationship between people
    
    # Projects
    PROJECT = "project"          # Project information
    
    # Events
    EVENT = "event"              # Important events
    MILESTONE = "milestone"      # Milestones
    
    # Contact information
    CONTACT = "contact"          # Contact details
    
    # Other
    FACT = "fact"                # General facts
    OTHER = "other"              # Uncategorized


class EntitySource(Enum):
    """Source of entity extraction."""
    REGEX = "regex"        # Extracted via regex patterns
    LLM = "llm"            # Extracted via LLM (V4.0)
    MANUAL = "manual"      # Manually added
    IMPORT = "import"      # Imported from external source


class EntityPriority(Enum):
    """Priority levels for entity injection."""
    CRITICAL = 100   # Safety related, must inject
    HIGH = 80        # Important information, prioritize
    MEDIUM = 50      # General information, inject as needed
    LOW = 20         # Minor information, optional


# Priority mapping by entity type
TYPE_PRIORITY_MAP = {
    EntityType.ALLERGY: EntityPriority.CRITICAL,
    EntityType.CONSTRAINT: EntityPriority.CRITICAL,
    EntityType.DECISION: EntityPriority.HIGH,
    EntityType.MILESTONE: EntityPriority.HIGH,
    EntityType.PERSON: EntityPriority.MEDIUM,
    EntityType.RELATION: EntityPriority.MEDIUM,
    EntityType.PREFERENCE: EntityPriority.MEDIUM,
    EntityType.DISLIKE: EntityPriority.MEDIUM,
    EntityType.PROJECT: EntityPriority.MEDIUM,
    EntityType.EVENT: EntityPriority.MEDIUM,
    EntityType.CONTACT: EntityPriority.LOW,
    EntityType.FACT: EntityPriority.LOW,
    EntityType.OTHER: EntityPriority.LOW,
}


@dataclass
class Entity:
    """Unified entity model for all memory items.
    
    This class represents a single piece of information extracted from
    conversation, with full metadata for retrieval and injection.
    """
    # Basic information
    id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    type: EntityType = EntityType.OTHER
    name: str = ""                    # Entity name (short identifier)
    content: str = ""                 # Full content/description
    
    # Classification
    category: str = ""                # Category tag (e.g., "food", "work")
    priority: int = 50                # Priority 0-100 for injection
    
    # Source information
    source: EntitySource = EntitySource.REGEX
    confidence: float = 1.0           # Extraction confidence (0.0-1.0)
    
    # Time information
    created_at: datetime = field(default_factory=datetime.now)
    last_updated: datetime = field(default_factory=datetime.now)
    last_accessed: datetime = field(default_factory=datetime.now)
    valid_until: Optional[datetime] = None  # Expiration time (optional)
    
    # Usage statistics
    access_count: int = 0             # How many times accessed
    
    # Context
    context: str = ""                 # Original context when extracted
    msg_id: str = ""                  # Source message ID
    session_id: str = ""              # Source session ID
    
    # Vector embedding for semantic search
    embedding: Optional[list[float]] = None
    
    # Relations
    related_entities: list[str] = field(default_factory=list)
    tags: list[str] = field(default_factory=list)
    
    # Additional attributes
    attributes: dict[str, Any] = field(default_factory=dict)
    
    def __post_init__(self):
        """Set default priority based on type if not specified."""
        if self.priority == 50 and self.type in TYPE_PRIORITY_MAP:
            self.priority = TYPE_PRIORITY_MAP[self.type].value
    
    def to_dict(self) -> dict:
        """Convert to dictionary for serialization."""
        return {
            "id": self.id,
            "type": self.type.value,
            "name": self.name,
            "content": self.content,
            "category": self.category,
            "priority": self.priority,
            "source": self.source.value,
            "confidence": self.confidence,
            "created_at": self.created_at.isoformat(),
            "last_updated": self.last_updated.isoformat(),
            "last_accessed": self.last_accessed.isoformat(),
            "valid_until": self.valid_until.isoformat() if self.valid_until else None,
            "access_count": self.access_count,
            "context": self.context,
            "msg_id": self.msg_id,
            "session_id": self.session_id,
            "related_entities": self.related_entities,
            "tags": self.tags,
            "attributes": self.attributes,
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> "Entity":
        """Create from dictionary."""
        def parse_datetime(value: Optional[str]) -> datetime:
            if value:
                try:
                    return datetime.fromisoformat(value)
                except (ValueError, TypeError):
                    pass
            return datetime.now()
        
        def parse_type(value: str) -> EntityType:
            try:
                return EntityType(value)
            except ValueError:
                return EntityType.OTHER
        
        def parse_source(value: str) -> EntitySource:
            try:
                return EntitySource(value)
            except ValueError:
                return EntitySource.REGEX
        
        return cls(
            id=data.get("id", str(uuid.uuid4())[:8]),
            type=parse_type(data.get("type", "other")),
            name=data.get("name", ""),
            content=data.get("content", ""),
            category=data.get("category", ""),
            priority=data.get("priority", 50),
            source=parse_source(data.get("source", "regex")),
            confidence=data.get("confidence", 1.0),
            created_at=parse_datetime(data.get("created_at")),
            last_updated=parse_datetime(data.get("last_updated")),
            last_accessed=parse_datetime(data.get("last_accessed")),
            valid_until=parse_datetime(data.get("valid_until")) if data.get("valid_until") else None,
            access_count=data.get("access_count", 0),
            context=data.get("context", ""),
            msg_id=data.get("msg_id", ""),
            session_id=data.get("session_id", ""),
            related_entities=data.get("related_entities", []),
            tags=data.get("tags", []),
            attributes=data.get("attributes", {}),
        )
    
    def update_access(self):
        """Update access statistics."""
        self.last_accessed = datetime.now()
        self.access_count += 1
    
    def is_expired(self) -> bool:
        """Check if entity has expired."""
        if self.valid_until is None:
            return False
        return datetime.now() > self.valid_until
    
    def is_safety_related(self) -> bool:
        """Check if this is a safety-related entity."""
        return self.type in (EntityType.ALLERGY, EntityType.CONSTRAINT) or self.priority >= 100
    
    def get_display_text(self) -> str:
        """Get display text for prompt injection."""
        if self.name and self.content and self.name != self.content:
            return f"{self.name}: {self.content}"
        return self.name or self.content


@dataclass
class Relation:
    """Relation between two entities."""
    id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    source_id: str = ""               # Source entity ID
    target_id: str = ""               # Target entity ID
    relation_type: str = ""           # Type of relation
    weight: float = 1.0               # Relation strength
    context: str = ""                 # Context where relation was established
    created_at: datetime = field(default_factory=datetime.now)
    
    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "id": self.id,
            "source_id": self.source_id,
            "target_id": self.target_id,
            "relation_type": self.relation_type,
            "weight": self.weight,
            "context": self.context,
            "created_at": self.created_at.isoformat(),
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> "Relation":
        """Create from dictionary."""
        created_at = datetime.now()
        if "created_at" in data:
            try:
                created_at = datetime.fromisoformat(data["created_at"])
            except (ValueError, TypeError):
                pass
        
        return cls(
            id=data.get("id", str(uuid.uuid4())[:8]),
            source_id=data.get("source_id", ""),
            target_id=data.get("target_id", ""),
            relation_type=data.get("relation_type", ""),
            weight=data.get("weight", 1.0),
            context=data.get("context", ""),
            created_at=created_at,
        )


def create_entity_from_key_info(info_type: str, content: str, 
                                 context: str = "", priority: int = 50,
                                 msg_id: str = "", session_id: str = "") -> Entity:
    """Create an Entity from KeyInfo-like data.
    
    Args:
        info_type: Type of information (safety, preference, decision, etc.)
        content: The content/value
        context: Original context
        priority: Priority level
        msg_id: Source message ID
        session_id: Source session ID
    
    Returns:
        Entity object
    """
    type_map = {
        "safety": EntityType.ALLERGY,
        "allergy": EntityType.ALLERGY,
        "constraint": EntityType.CONSTRAINT,
        "preference": EntityType.PREFERENCE,
        "dislike": EntityType.DISLIKE,
        "decision": EntityType.DECISION,
        "contact": EntityType.CONTACT,
        "person": EntityType.PERSON,
        "event": EntityType.EVENT,
        "milestone": EntityType.MILESTONE,
        "project": EntityType.PROJECT,
        "fact": EntityType.FACT,
    }
    
    entity_type = type_map.get(info_type.lower(), EntityType.OTHER)
    
    return Entity(
        type=entity_type,
        name=content[:50] if len(content) > 50 else content,
        content=content,
        priority=priority,
        source=EntitySource.REGEX,
        context=context,
        msg_id=msg_id,
        session_id=session_id,
    )