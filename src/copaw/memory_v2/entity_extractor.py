# -*- coding: utf-8 -*-
"""Entity Extractor for extracting entities from text.

This module provides the EntityExtractor class that:
1. Extracts entities from text using LLM
2. Maintains an entity knowledge base
3. Merges and updates existing entities
"""

import json
import logging
from typing import Optional

from .models import Entity, EntityType

logger = logging.getLogger(__name__)


EXTRACTION_PROMPT = """请从以下文本中提取所有重要实体。

文本：
{text}

请以 JSON 格式返回实体列表：
[
  {
    "name": "实体名称",
    "type": "person|project|technology|date|concept|organization|location",
    "description": "简短描述",
    "attributes": {"key": "value"}
  }
]

注意：
1. 只返回 JSON 数组，不要其他内容
2. 只提取重要实体，不要提取普通词汇
3. attributes 可包含额外信息（如职位、状态等）
"""


class EntityExtractor:
    """Extracts and manages entities from text.

    Uses LLM to extract entities and maintains a knowledge base
    of known entities that can be updated over time.
    """

    def __init__(self, chat_model):
        """Initialize the entity extractor.

        Args:
            chat_model: The chat model to use for extraction
        """
        self.chat_model = chat_model
        self.entity_store: dict[str, Entity] = {}  # name -> Entity

    async def extract(
        self,
        text: str,
        update_store: bool = True,
    ) -> list[Entity]:
        """Extract entities from text.

        Args:
            text: The text to extract entities from
            update_store: Whether to update the entity store

        Returns:
            List of extracted entities
        """
        try:
            # Call LLM for extraction
            prompt = EXTRACTION_PROMPT.format(text=text)
            response = await self._call_llm(prompt)

            # Debug: log raw LLM response
            logger.debug(f"LLM response for entity extraction (len={len(response)}): {response[:500]}...")

            # Parse response
            entities = self._parse_response(response)

            # Update store if requested
            if update_store:
                self.merge_entities(entities)

            logger.info(f"Extracted {len(entities)} entities from text")
            return entities

        except Exception as e:
            logger.error(f"Failed to extract entities: {e}")
            logger.debug(f"Exception type: {type(e).__name__}, text preview: {text[:100]}")
            return []

    async def _call_llm(self, prompt: str) -> str:
        """Call the LLM with the given prompt.

        Args:
            prompt: The prompt to send

        Returns:
            The LLM response text
        """
        from agentscope.message import Msg

        msg = Msg(role="user", content=prompt)
        response = self.chat_model(msg)

        if hasattr(response, "content"):
            return response.content
        elif hasattr(response, "text"):
            return response.text
        else:
            return str(response)

    def _parse_response(self, response: str) -> list[Entity]:
        """Parse LLM response to extract entities.

        Args:
            response: The LLM response text

        Returns:
            List of Entity objects
        """
        data = None
        parse_error = None

        try:
            # Try direct JSON parse
            data = json.loads(response)
        except json.JSONDecodeError as e:
            parse_error = e
            # Try to extract JSON from markdown - each attempt protected
            try:
                if "```json" in response:
                    start = response.find("```json") + 7
                    end = response.find("```", start)
                    if end > start:
                        data = json.loads(response[start:end].strip())
            except json.JSONDecodeError:
                pass

            if data is None:
                try:
                    if "```" in response:
                        start = response.find("```") + 3
                        end = response.find("```", start)
                        if end > start:
                            data = json.loads(response[start:end].strip())
                except json.JSONDecodeError:
                    pass

            if data is None:
                try:
                    if "[" in response:
                        start = response.find("[")
                        end = response.rfind("]") + 1
                        if end > start:
                            data = json.loads(response[start:end])
                except json.JSONDecodeError:
                    pass

        if data is None:
            logger.warning(f"Failed to parse entity extraction response: {parse_error}")
            logger.debug(f"Response preview: {response[:200]}...")
            return []

        # Build Entity objects
        entities = []
        type_map = {
            "person": EntityType.PERSON,
            "project": EntityType.PROJECT,
            "technology": EntityType.TECHNOLOGY,
            "date": EntityType.DATE,
            "concept": EntityType.CONCEPT,
            "organization": EntityType.ORGANIZATION,
            "location": EntityType.LOCATION,
        }

        for item in data if isinstance(data, list) else [data]:
            if not isinstance(item, dict):
                continue

            name = item.get("name", "")
            if not name:
                continue

            entity = Entity(
                name=name,
                type=type_map.get(item.get("type", "concept"), EntityType.CONCEPT),
                description=item.get("description", ""),
                attributes=item.get("attributes", {}),
            )
            entities.append(entity)

        return entities

    def merge_entities(self, new_entities: list[Entity]) -> list[Entity]:
        """Merge new entities into the knowledge base.

        Updates existing entities or adds new ones.

        Args:
            new_entities: List of new entities to merge

        Returns:
            List of merged entities (both existing and new)
        """
        merged = []

        for entity in new_entities:
            if entity.name in self.entity_store:
                # Update existing entity
                existing = self.entity_store[entity.name]

                # Merge description (keep longer one)
                if len(entity.description) > len(existing.description):
                    existing.description = entity.description

                # Merge attributes
                existing.attributes.update(entity.attributes)

                merged.append(existing)
            else:
                # Add new entity
                self.entity_store[entity.name] = entity
                merged.append(entity)

        logger.debug(f"Merged {len(new_entities)} entities, total: {len(self.entity_store)}")
        return merged

    def get_entity(self, name: str) -> Optional[Entity]:
        """Get an entity by name.

        Args:
            name: Entity name

        Returns:
            Entity if found, None otherwise
        """
        return self.entity_store.get(name)

    def get_all_entities(self) -> list[Entity]:
        """Get all known entities.

        Returns:
            List of all entities in the store
        """
        return list(self.entity_store.values())

    def get_entities_by_type(self, entity_type: EntityType) -> list[Entity]:
        """Get all entities of a specific type.

        Args:
            entity_type: The type to filter by

        Returns:
            List of entities of the given type
        """
        return [e for e in self.entity_store.values() if e.type == entity_type]

    def clear_store(self) -> None:
        """Clear the entity store."""
        self.entity_store.clear()
        logger.info("Entity store cleared")

    def to_dict(self) -> dict:
        """Serialize the entity store to a dictionary.

        Returns:
            Dictionary representation of the store
        """
        return {
            name: entity.to_dict()
            for name, entity in self.entity_store.items()
        }

    def from_dict(self, data: dict) -> None:
        """Load the entity store from a dictionary.

        Args:
            data: Dictionary representation of the store
        """
        self.entity_store = {
            name: Entity.from_dict(entity_data)
            for name, entity_data in data.items()
        }
        logger.info(f"Loaded {len(self.entity_store)} entities from data")