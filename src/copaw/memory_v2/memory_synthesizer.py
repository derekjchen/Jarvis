# -*- coding: utf-8 -*-
"""Memory Synthesizer for combining atomic memories into semantic memories.

This module provides the MemorySynthesizer class that:
1. Combines multiple atomic memories into coherent semantic memories
2. Merges similar entities across memories
3. Generates structured content for MEMORY.md
"""

import logging
from datetime import datetime
from typing import Optional

from .models import Entity, MemoryType, Relation, SemanticMemory

logger = logging.getLogger(__name__)


class MemorySynthesizer:
    """Synthesizes multiple atomic memories into semantic memories.

    Takes atomic memories (compressed summaries) and combines them
    into higher-level semantic memories with extracted entities
    and relations.
    """

    def __init__(self, chat_model=None):
        """Initialize the memory synthesizer.

        Args:
            chat_model: Optional chat model for synthesis
        """
        self.chat_model = chat_model

    def synthesize(
        self,
        memories: list[dict],
        existing_entities: Optional[dict[str, Entity]] = None,
    ) -> list[SemanticMemory]:
        """Synthesize multiple atomic memories into semantic memories.

        Args:
            memories: List of atomic memories (dict with 'content', 'timestamp', etc.)
            existing_entities: Existing entity knowledge base (name -> Entity)

        Returns:
            List of synthesized SemanticMemory objects
        """
        if not memories:
            return []

        # Group memories by topic or time
        groups = self._group_memories(memories)

        # Synthesize each group
        semantic_memories = []
        for group in groups:
            memory = self._synthesize_group(group, existing_entities)
            if memory:
                semantic_memories.append(memory)

        logger.info(f"Synthesized {len(semantic_memories)} semantic memories from {len(memories)} atomic memories")
        return semantic_memories

    def _group_memories(
        self,
        memories: list[dict],
        time_window_hours: int = 24,
    ) -> list[list[dict]]:
        """Group memories by time window.

        Args:
            memories: List of memories
            time_window_hours: Hours to group together

        Returns:
            List of memory groups
        """
        if not memories:
            return []

        # Sort by timestamp
        sorted_memories = sorted(
            memories,
            key=lambda m: m.get('timestamp', ''),
        )

        groups = []
        current_group = [sorted_memories[0]]

        for i in range(1, len(sorted_memories)):
            prev = sorted_memories[i - 1]
            curr = sorted_memories[i]

            # Check if within time window
            try:
                prev_time = datetime.fromisoformat(prev.get('timestamp', ''))
                curr_time = datetime.fromisoformat(curr.get('timestamp', ''))
                diff_hours = (curr_time - prev_time).total_seconds() / 3600

                if diff_hours <= time_window_hours:
                    current_group.append(curr)
                else:
                    groups.append(current_group)
                    current_group = [curr]
            except:
                # If timestamp parsing fails, add to current group
                current_group.append(curr)

        if current_group:
            groups.append(current_group)

        return groups

    def _synthesize_group(
        self,
        memories: list[dict],
        existing_entities: Optional[dict[str, Entity]] = None,
    ) -> Optional[SemanticMemory]:
        """Synthesize a group of memories into one semantic memory.

        Args:
            memories: List of related memories
            existing_entities: Existing entity knowledge base

        Returns:
            SemanticMemory or None
        """
        if not memories:
            return None

        # Combine content
        combined_content = "\n".join([
            m.get('content', '') or m.get('summary', '')
            for m in memories
            if m.get('content') or m.get('summary')
        ])

        if not combined_content:
            return None

        # Determine memory type based on content
        memory_type = self._determine_type(combined_content)

        # Generate summary
        summary = self._generate_summary(memories)

        # Extract source IDs
        source_ids = [m.get('id', '') for m in memories if m.get('id')]

        # Calculate importance
        importance = self._calculate_importance(memories, memory_type)

        return SemanticMemory(
            type=memory_type,
            summary=summary,
            source_ids=source_ids,
            importance=importance,
        )

    def _determine_type(self, content: str) -> MemoryType:
        """Determine memory type from content.

        Args:
            content: Memory content

        Returns:
            MemoryType enum value
        """
        content_lower = content.lower()

        # Decision keywords
        decision_keywords = ['决定', '选择', '方案', 'decision', 'chose', 'plan']
        if any(kw in content_lower for kw in decision_keywords):
            return MemoryType.DECISION

        # Event keywords
        event_keywords = ['完成', '发生', '启动', 'completed', 'started', 'happened']
        if any(kw in content_lower for kw in event_keywords):
            return MemoryType.EVENT

        # Todo keywords
        todo_keywords = ['待办', '计划', '需要', 'todo', 'plan to', 'need to']
        if any(kw in content_lower for kw in todo_keywords):
            return MemoryType.TODO

        return MemoryType.KNOWLEDGE

    def _generate_summary(self, memories: list[dict]) -> str:
        """Generate summary from memory group.

        Args:
            memories: List of memories

        Returns:
            Summary string
        """
        if len(memories) == 1:
            content = memories[0].get('content', '') or memories[0].get('summary', '')
            return content[:200] if len(content) > 200 else content

        # Multiple memories - create combined summary
        summaries = []
        for m in memories[:3]:  # Limit to first 3
            content = m.get('content', '') or m.get('summary', '')
            if content:
                summaries.append(content[:100])

        return " | ".join(summaries)

    def _calculate_importance(
        self,
        memories: list[dict],
        memory_type: MemoryType,
    ) -> float:
        """Calculate importance score for the memory.

        Args:
            memories: List of memories
            memory_type: Type of the memory

        Returns:
            Importance score (0-1)
        """
        base_score = {
            MemoryType.DECISION: 0.8,
            MemoryType.EVENT: 0.6,
            MemoryType.KNOWLEDGE: 0.5,
            MemoryType.TODO: 0.4,
        }.get(memory_type, 0.5)

        # Adjust based on number of memories
        if len(memories) > 5:
            base_score += 0.1
        elif len(memories) > 10:
            base_score += 0.15

        return min(base_score, 1.0)

    def to_markdown(self, memories: list[SemanticMemory]) -> str:
        """Convert semantic memories to MEMORY.md format.

        Args:
            memories: List of semantic memories

        Returns:
            Markdown formatted string
        """
        lines = ["# 语义记忆\n"]

        # Group by type
        by_type = {}
        for m in memories:
            type_name = m.type.value
            if type_name not in by_type:
                by_type[type_name] = []
            by_type[type_name].append(m)

        # Format each type
        type_names = {
            'decision': '决策',
            'event': '事件',
            'knowledge': '知识',
            'todo': '待办',
        }

        for type_key, type_memories in by_type.items():
            type_label = type_names.get(type_key, type_key)
            lines.append(f"\n## {type_label}\n")

            for m in sorted(type_memories, key=lambda x: x.importance, reverse=True):
                lines.append(f"- **{m.summary[:100]}**")
                if m.entities:
                    entity_names = [e.name for e in m.entities[:5]]
                    lines.append(f"  - 相关实体: {', '.join(entity_names)}")
                lines.append(f"  - 时间: {m.created_at.strftime('%Y-%m-%d %H:%M')}")
                lines.append("")

        return "\n".join(lines)