# -*- coding: utf-8 -*-
"""Semantic memory hook for V2 memory system.

This hook periodically analyzes conversations and extracts semantic memories.
"""
import logging
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from ..memory import MemoryManager

logger = logging.getLogger(__name__)


class SemanticMemoryHook:
    """Hook for triggering V2 semantic memory analysis.

    This hook is called after each agent response to potentially
    extract and store semantic memories.
    """

    def __init__(
        self,
        memory_manager: "MemoryManager",
        analyze_every_n_messages: int = 5,
    ):
        """Initialize semantic memory hook.

        Args:
            memory_manager: Memory manager instance
            analyze_every_n_messages: Analyze every N messages
        """
        self.memory_manager = memory_manager
        self.analyze_every_n_messages = analyze_every_n_messages
        self.message_count = 0

    async def __call__(
        self,
        agent,
        kwargs: dict[str, Any],
    ) -> dict[str, Any] | None:
        """Post-response hook to analyze and store semantic memories.

        Args:
            agent: The agent instance
            kwargs: Input arguments

        Returns:
            None (hook doesn't modify kwargs)
        """
        try:
            self.message_count += 1

            # Check if V2 is enabled
            if not hasattr(self.memory_manager, 'is_v2_enabled'):
                return None

            if not self.memory_manager.is_v2_enabled():
                return None

            # Analyze every N messages
            if self.message_count % self.analyze_every_n_messages != 0:
                return None

            logger.info(f"Triggering V2 semantic analysis (message #{self.message_count})")

            # Get recent messages
            messages = await agent.memory.get_memory(
                exclude_mark=None,
                prepend_summary=False,
            )

            if not messages:
                return None

            # Get last few messages for analysis
            recent_messages = messages[-self.analyze_every_n_messages:]

            # Extract text from messages
            text_parts = []
            for msg in recent_messages:
                if hasattr(msg, 'content'):
                    if isinstance(msg.content, list):
                        for item in msg.content:
                            if isinstance(item, dict) and item.get('type') == 'text':
                                text_parts.append(item.get('text', ''))
                    elif isinstance(msg.content, str):
                        text_parts.append(msg.content)

            if not text_parts:
                return None

            combined_text = "\n".join(text_parts)

            # Extract entities
            entities = await self.memory_manager.extract_entities(combined_text)

            if entities:
                logger.info(f"V2 extracted {len(entities)} entities: {[e.name for e in entities[:5]]}")

        except Exception as e:
            logger.error(f"Semantic memory hook failed: {e}", exc_info=True)

        return None