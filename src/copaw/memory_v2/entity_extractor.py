# -*- coding: utf-8 -*-
"""Entity Extractor for extracting entities from text.

This module provides the EntityExtractor class that:
1. Extracts entities from text using LLM
2. Maintains an entity knowledge base
3. Merges and updates existing entities
"""

import json
import logging
import re
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

            # Debug: log raw LLM response with full content
            logger.info(f"[EntityExtractor] Raw LLM response (len={len(response)}):")
            logger.debug(f"[EntityExtractor] Full response: {response}")

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

    # =========================================================================
    # WORKAROUND: _extract_entities_with_regex
    # -------------------------------------------------------------------------
    # Issue: LLM (glm-5) sometimes returns malformed JSON that cannot be parsed
    # Error pattern: '\n    "name"' - suggests partial/broken JSON output
    #
    # This workaround uses regex to extract entity information directly from
    # the LLM response when JSON parsing fails. It's less strict but more
    # resilient to malformed output.
    #
    # TODO: Remove this workaround once LLM JSON output is stable
    # Tracked in: Memory V2 entity extraction issues
    # =========================================================================
    def _extract_entities_with_regex(self, response: str) -> list[dict]:
        """WORKAROUND: Extract entities using regex when JSON parsing fails.
        
        This is a fallback method that tries to extract entity-like structures
        directly from the text using pattern matching. It handles cases where
        the LLM returns malformed or partial JSON.
        
        Args:
            response: The raw LLM response text
            
        Returns:
            List of entity dictionaries extracted from the response
        """
        entities = []
        
        # Pattern 1: Match complete JSON objects with name field
        # Handles: {"name": "xxx", "type": "yyy", ...}
        pattern1 = r'\{\s*"name"\s*:\s*"([^"]+)"[^}]*\}'
        matches1 = re.findall(pattern1, response, re.DOTALL)
        
        for name in matches1:
            entity = {"name": name}
            # Try to extract type
            type_match = re.search(rf'\{{\s*"name"\s*:\s*"{re.escape(name)}"[^}}]*"type"\s*:\s*"([^"]+)"', response)
            if type_match:
                entity["type"] = type_match.group(1)
            # Try to extract description
            desc_match = re.search(rf'\{{\s*"name"\s*:\s*"{re.escape(name)}"[^}}]*"description"\s*:\s*"([^"]+)"', response)
            if desc_match:
                entity["description"] = desc_match.group(1)
            entities.append(entity)
        
        if entities:
            logger.info(f"[WORKAROUND] Extracted {len(entities)} entities using regex pattern 1")
            return entities
        
        # Pattern 2: Match name-value pairs in any format
        # Handles: name: "xxx" or name = "xxx" or "name": "xxx"
        pattern2 = r'(?:name|"name")\s*[:=]\s*"([^"]+)"'
        names = re.findall(pattern2, response, re.IGNORECASE)
        
        for name in names:
            if name and len(name) > 1 and name not in [e.get("name") for e in entities]:
                entities.append({"name": name, "type": "concept"})
        
        if entities:
            logger.info(f"[WORKAROUND] Extracted {len(entities)} entities using regex pattern 2")
        
        return entities
    # =========================================================================
    # END WORKAROUND
    # =========================================================================

    def _try_repair_truncated_json(self, json_str: str) -> Optional[list]:
        """Try to repair and parse truncated JSON.

        Handles cases where LLM returns incomplete JSON:
        - Missing closing brackets (] or })
        - Incomplete string values
        - Missing commas between objects

        Args:
            json_str: The JSON string to repair

        Returns:
            Parsed list if successful, None otherwise
        """
        if not json_str or "[" not in json_str:
            return None

        # Find the start of JSON array
        start = json_str.find("[")
        work_str = json_str[start:]

        # Count brackets to determine what's missing
        open_brackets = work_str.count("[")
        close_brackets = work_str.count("]")
        open_braces = work_str.count("{")
        close_braces = work_str.count("}")

        # Try to repair by adding missing closing brackets
        repaired = work_str.rstrip()

        # Add missing closing braces for objects
        if open_braces > close_braces:
            repaired += "}" * (open_braces - close_braces)

        # Add missing closing brackets for arrays
        if open_brackets > close_brackets:
            repaired += "]" * (open_brackets - close_brackets)

        try:
            return json.loads(repaired)
        except json.JSONDecodeError:
            pass

        # Try a more aggressive approach: extract complete objects
        # Pattern: find all {...} blocks that look like entity objects
        objects = []
        # Match objects with "name" field
        pattern = r'\{\s*"name"\s*:\s*"[^"]*"[^}]*\}'
        matches = re.findall(pattern, work_str)

        for match in matches:
            try:
                obj = json.loads(match)
                if isinstance(obj, dict) and "name" in obj:
                    objects.append(obj)
            except json.JSONDecodeError:
                continue

        if objects:
            logger.info(f"Extracted {len(objects)} entities from truncated JSON using pattern matching")
            return objects

        return None

    def _parse_response(self, response: str) -> list[Entity]:
        """Parse LLM response to extract entities.

        Args:
            response: The LLM response text

        Returns:
            List of Entity objects
        """
        try:
            data = None
            parse_error = None

            # Log response for debugging
            logger.debug(f"[EntityExtractor] Parsing response of length {len(response)}")

            try:
                # Try direct JSON parse
                data = json.loads(response)
            except json.JSONDecodeError as e:
                parse_error = e
                logger.debug(f"Direct JSON parse failed: {e}")

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

                # Try to repair truncated JSON
                if data is None:
                    logger.info("Attempting truncated JSON repair...")
                    try:
                        data = self._try_repair_truncated_json(response)
                        if data:
                            logger.info(f"Successfully repaired truncated JSON, got {len(data)} entities")
                    except Exception as repair_error:
                        logger.warning(f"Truncated JSON repair failed: {repair_error}")

                # WORKAROUND: Use regex extraction as last resort
                if data is None:
                    logger.warning("[WORKAROUND] All JSON parsing methods failed, trying regex extraction")
                    try:
                        data = self._extract_entities_with_regex(response)
                    except Exception as regex_error:
                        logger.warning(f"Regex extraction also failed: {regex_error}")

            if data is None:
                logger.warning(f"Failed to parse entity extraction response: {parse_error}")
                logger.warning(f"Response preview: {response[:500]}...")
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

        except Exception as e:
            logger.error(f"Unexpected error in _parse_response: {type(e).__name__}: {e}")
            logger.debug(f"Response that caused error: {response[:500] if response else 'None'}...")
            return []

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