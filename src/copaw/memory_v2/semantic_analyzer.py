# -*- coding: utf-8 -*-
"""Semantic Analyzer for extracting structured memory from text.

This module provides the SemanticAnalyzer class that uses LLM to:
1. Analyze text and extract entities
2. Identify relations between entities
3. Generate structured SemanticMemory
"""

import json
import logging
from typing import Optional

from .models import Entity, EntityType, MemoryType, Relation, SemanticMemory

logger = logging.getLogger(__name__)


ANALYSIS_PROMPT = """请分析以下文本，提取结构化信息。

文本：
{text}

请以 JSON 格式返回以下信息：
{{
  "type": "decision|event|knowledge|todo",
  "summary": "一句话总结",
  "importance": 0.0-1.0,
  "entities": [
    {{
      "name": "实体名称",
      "type": "person|project|technology|date|concept|organization|location",
      "description": "简短描述"
    }}
  ],
  "relations": [
    {{
      "source": "源实体名称",
      "target": "目标实体名称",
      "relation": "关系类型"
    }}
  ],
  "tags": ["标签1", "标签2"]
}}

注意：
1. 只返回 JSON，不要其他内容
2. importance 根据重要性打分（决策和重要事件为 0.7-1.0）
3. 如果没有实体或关系，返回空数组
"""


class SemanticAnalyzer:
    """Analyzes text to extract structured semantic memory.

    Uses LLM to analyze text and extract:
    - Memory type (decision, event, knowledge, todo)
    - Summary
    - Entities (people, projects, technologies, etc.)
    - Relations between entities
    - Importance score
    """

    def __init__(self, chat_model):
        """Initialize the semantic analyzer.

        Args:
            chat_model: The chat model to use for analysis
        """
        self.chat_model = chat_model

    async def analyze(
        self,
        text: str,
        source_ids: Optional[list[str]] = None,
    ) -> SemanticMemory:
        """Analyze text and return structured semantic memory.

        Args:
            text: The text to analyze
            source_ids: Optional list of source atomic memory IDs

        Returns:
            SemanticMemory object with extracted information
        """
        try:
            # Call LLM for analysis
            prompt = ANALYSIS_PROMPT.format(text=text)
            response = await self._call_llm(prompt)

            # Parse response
            result = self._parse_response(response)

            # Build SemanticMemory
            memory = self._build_memory(result, source_ids)

            logger.info(f"Analyzed text, extracted {len(memory.entities)} entities")
            return memory

        except Exception as e:
            logger.error(f"Failed to analyze text: {e}")
            # Return a basic memory on failure
            return SemanticMemory(
                type=MemoryType.KNOWLEDGE,
                summary=text[:200] if len(text) > 200 else text,
                source_ids=source_ids or [],
            )

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

        # Extract text from response
        if hasattr(response, "content"):
            return response.content
        elif hasattr(response, "text"):
            return response.text
        else:
            return str(response)

    def _parse_response(self, response: str) -> dict:
        """Parse LLM response to extract JSON.

        Args:
            response: The LLM response text

        Returns:
            Parsed dictionary
        """
        # Try to find JSON in response
        try:
            # Direct JSON parse
            return json.loads(response)
        except json.JSONDecodeError:
            pass

        # Try to extract JSON from markdown code block
        if "```json" in response:
            start = response.find("```json") + 7
            end = response.find("```", start)
            if end > start:
                return json.loads(response[start:end].strip())

        if "```" in response:
            start = response.find("```") + 3
            end = response.find("```", start)
            if end > start:
                return json.loads(response[start:end].strip())

        # Try to find JSON object
        start = response.find("{")
        end = response.rfind("}") + 1
        if start >= 0 and end > start:
            return json.loads(response[start:end])

        # Return default on failure
        logger.warning(f"Failed to parse LLM response as JSON")
        return {
            "type": "knowledge",
            "summary": response[:100],
            "importance": 0.5,
            "entities": [],
            "relations": [],
            "tags": [],
        }

    def _build_memory(
        self,
        result: dict,
        source_ids: Optional[list[str]] = None,
    ) -> SemanticMemory:
        """Build SemanticMemory from parsed result.

        Args:
            result: Parsed LLM response
            source_ids: Optional source memory IDs

        Returns:
            SemanticMemory object
        """
        # Parse memory type
        type_map = {
            "decision": MemoryType.DECISION,
            "event": MemoryType.EVENT,
            "knowledge": MemoryType.KNOWLEDGE,
            "todo": MemoryType.TODO,
        }
        memory_type = type_map.get(result.get("type", "knowledge"), MemoryType.KNOWLEDGE)

        # Parse entities
        entities = []
        entity_names = set()
        for e in result.get("entities", []):
            name = e.get("name", "")
            if name and name not in entity_names:
                entity_names.add(name)
                type_map_entity = {
                    "person": EntityType.PERSON,
                    "project": EntityType.PROJECT,
                    "technology": EntityType.TECHNOLOGY,
                    "date": EntityType.DATE,
                    "concept": EntityType.CONCEPT,
                    "organization": EntityType.ORGANIZATION,
                    "location": EntityType.LOCATION,
                }
                entity = Entity(
                    name=name,
                    type=type_map_entity.get(e.get("type", "concept"), EntityType.CONCEPT),
                    description=e.get("description", ""),
                )
                entities.append(entity)

        # Parse relations
        relations = []
        entity_name_to_id = {e.name: e.id for e in entities}
        for r in result.get("relations", []):
            source_name = r.get("source", "")
            target_name = r.get("target", "")
            if source_name and target_name:
                source_id = entity_name_to_id.get(source_name, "")
                target_id = entity_name_to_id.get(target_name, "")
                if source_id and target_id:
                    relation = Relation(
                        source_id=source_id,
                        target_id=target_id,
                        relation_type=r.get("relation", "related_to"),
                    )
                    relations.append(relation)

        # Build memory
        return SemanticMemory(
            type=memory_type,
            summary=result.get("summary", ""),
            entities=entities,
            relations=relations,
            source_ids=source_ids or [],
            importance=result.get("importance", 0.5),
            tags=result.get("tags", []),
        )