# -*- coding: utf-8 -*-
"""Dynamic Injector for Memory V3.5.

This module provides dynamic injection of relevant entities into prompts,
with prioritization and token budget management.
"""
import logging
from datetime import datetime
from typing import Optional

from .models import Entity, EntityType
from .store import UnifiedEntityStore
from .retriever import EntityRetriever

logger = logging.getLogger(__name__)


class DynamicInjector:
    """Dynamic prompt injector with prioritization.
    
    This class:
    1. Retrieves relevant entities based on query
    2. Prioritizes safety entities (always injected)
    3. Formats entities for prompt injection
    4. Manages token budget
    """
    
    # Token estimation: ~4 characters per token for Chinese
    CHARS_PER_TOKEN = 4
    
    def __init__(self, store: UnifiedEntityStore, retriever: EntityRetriever):
        """Initialize the injector.
        
        Args:
            store: The entity store
            retriever: The entity retriever
        """
        self.store = store
        self.retriever = retriever
    
    async def inject_to_prompt(self,
                                current_prompt: str,
                                query: str = "",
                                max_entities: int = 20,
                                max_tokens: int = 2000) -> str:
        """Inject relevant entities into the prompt.
        
        Args:
            current_prompt: The current system prompt
            query: User query for relevance matching
            max_entities: Maximum entities to inject
            max_tokens: Maximum tokens for injection
        
        Returns:
            Enhanced prompt with entity context
        """
        # Get entities to inject
        entities = await self._get_entities_to_inject(query, max_entities)
        
        if not entities:
            return current_prompt
        
        # Format entities
        entity_text = self._format_entities(entities, max_tokens)
        
        if not entity_text:
            return current_prompt
        
        # Create injection block
        injection = f"\n\n## 已知的关键信息\n\n{entity_text}\n"
        
        # Append to prompt
        return current_prompt + injection
    
    async def _get_entities_to_inject(self, query: str, max_entities: int) -> list[Entity]:
        """Determine which entities to inject.
        
        Strategy:
        1. Always include safety entities (priority >= 100)
        2. Include entities relevant to the query
        3. Fill remaining slots with high-priority entities
        
        Args:
            query: User query
            max_entities: Maximum entities
        
        Returns:
            List of entities to inject
        """
        entities = []
        included_ids = set()
        
        # 1. Safety entities (always included)
        safety_entities = self.store.get_safety_entities()
        for entity in safety_entities:
            if entity.id not in included_ids:
                entities.append(entity)
                included_ids.add(entity.id)
        
        # 2. Query-relevant entities
        remaining = max_entities - len(entities)
        if query and remaining > 0:
            relevant = await self.retriever.search(query, top_k=remaining)
            for entity, score in relevant:
                if entity.id not in included_ids:
                    entities.append(entity)
                    included_ids.add(entity.id)
        
        # 3. High-priority entities (priority >= 50)
        remaining = max_entities - len(entities)
        if remaining > 0:
            # Include entities with priority >= 50 (decisions, preferences, etc.)
            other_entities = self.store.get_entities_by_priority(min_priority=50)
            for entity in other_entities:
                if entity.id not in included_ids:
                    entities.append(entity)
                    included_ids.add(entity.id)
                    remaining -= 1
                    if remaining <= 0:
                        break
        
        # 4. Update access statistics
        now = datetime.now()
        for entity in entities:
            entity.last_accessed = now
            entity.access_count += 1
        
        self.store.save()
        
        return entities
    
    def _format_entities(self, entities: list[Entity], max_tokens: int) -> str:
        """Format entities for prompt injection.
        
        Groups by priority and formats as readable text.
        Respects token budget.
        
        Args:
            entities: Entities to format
            max_tokens: Token budget
        
        Returns:
            Formatted text
        """
        if not entities:
            return ""
        
        # Group by priority
        safety = []
        important = []
        normal = []
        
        for entity in entities:
            if entity.priority >= 100:
                safety.append(entity)
            elif entity.priority >= 80:
                important.append(entity)
            else:
                normal.append(entity)
        
        lines = []
        estimated_tokens = 0
        
        # Safety section
        if safety:
            header = "### ⚠️ 安全相关（必须注意）"
            lines.append(header)
            estimated_tokens += len(header) // self.CHARS_PER_TOKEN
            
            for entity in safety:
                text = self._format_single_entity(entity, is_safety=True)
                token_cost = len(text) // self.CHARS_PER_TOKEN
                
                if estimated_tokens + token_cost > max_tokens:
                    break
                
                lines.append(text)
                estimated_tokens += token_cost
        
        # Important section
        if important and estimated_tokens < max_tokens:
            lines.append("")  # Blank line
            header = "### 重要信息"
            lines.append(header)
            estimated_tokens += len(header) // self.CHARS_PER_TOKEN + 1
            
            for entity in important:
                text = self._format_single_entity(entity, is_safety=False)
                token_cost = len(text) // self.CHARS_PER_TOKEN
                
                if estimated_tokens + token_cost > max_tokens:
                    break
                
                lines.append(text)
                estimated_tokens += token_cost
        
        # Normal section
        if normal and estimated_tokens < max_tokens:
            lines.append("")  # Blank line
            header = "### 其他信息"
            lines.append(header)
            estimated_tokens += len(header) // self.CHARS_PER_TOKEN + 1
            
            for entity in normal:
                text = self._format_single_entity(entity, is_safety=False)
                token_cost = len(text) // self.CHARS_PER_TOKEN
                
                if estimated_tokens + token_cost > max_tokens:
                    break
                
                lines.append(text)
                estimated_tokens += token_cost
        
        return "\n".join(lines)
    
    def _format_single_entity(self, entity: Entity, is_safety: bool = False) -> str:
        """Format a single entity.
        
        Args:
            entity: Entity to format
            is_safety: Whether it's a safety entity
        
        Returns:
            Formatted string
        """
        if is_safety:
            # Safety entities get special formatting
            prefix = "- **"
            suffix = "**"
        else:
            prefix = "- "
            suffix = ""
        
        # Use name if available, otherwise content
        if entity.name and entity.name != entity.content:
            return f"{prefix}{entity.name}{suffix}: {entity.content}"
        else:
            return f"{prefix}{entity.content}"
    
    def get_entity_summary(self, entity_types: Optional[list[EntityType]] = None) -> str:
        """Get a summary of stored entities.
        
        Useful for debugging or quick overview.
        
        Args:
            entity_types: Optional filter by types
        
        Returns:
            Summary string
        """
        entities = self.store.get_all_entities()
        
        if entity_types:
            entities = [e for e in entities if e.type in entity_types]
        
        if not entities:
            return "暂无记忆信息"
        
        # Group by type
        by_type: dict[EntityType, list[Entity]] = {}
        for entity in entities:
            if entity.type not in by_type:
                by_type[entity.type] = []
            by_type[entity.type].append(entity)
        
        lines = [f"共 {len(entities)} 条记忆："]
        
        for entity_type, type_entities in by_type.items():
            type_name = entity_type.value
            lines.append(f"\n**{type_name}** ({len(type_entities)}条)")
            for entity in type_entities[:5]:  # Show max 5 per type
                lines.append(f"  - {entity.get_display_text()}")
            if len(type_entities) > 5:
                lines.append(f"  - ... 还有 {len(type_entities) - 5} 条")
        
        return "\n".join(lines)
    
    def get_safety_summary(self) -> str:
        """Get summary of safety-related entities only.
        
        Returns:
            Safety summary string
        """
        safety_entities = self.store.get_safety_entities()
        
        if not safety_entities:
            return ""
        
        lines = ["⚠️ 安全相关："]
        for entity in safety_entities:
            lines.append(f"  - {entity.get_display_text()}")
        
        return "\n".join(lines)