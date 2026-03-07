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
        analyze_every_n_messages: int = 1,
    ):
        """Initialize semantic memory hook.

        Args:
            memory_manager: Memory manager instance
            analyze_every_n_messages: Analyze every N messages (default: 1)
        """
        self.memory_manager = memory_manager
        self.analyze_every_n_messages = analyze_every_n_messages
        self.message_count = 0

    async def __call__(
        self,
        agent,
        kwargs: dict[str, Any],
        output: Any = None,
    ) -> Any:
        """Post-reasoning hook to analyze and store semantic memories.

        Args:
            agent: The agent instance
            kwargs: Input arguments to the _reasoning method
            output: The output from _reasoning (the response message)

        Returns:
            The output (unchanged, hook doesn't modify output)
        """
        try:
            self.message_count += 1

            # Check if V2 is enabled
            if not hasattr(self.memory_manager, 'enable_v2'):
                logger.debug("V2 not available (no enable_v2 attribute)")
                return output

            if not self.memory_manager.enable_v2:
                logger.debug("V2 disabled")
                return output

            # Analyze every N messages
            if self.message_count % self.analyze_every_n_messages != 0:
                return output

            logger.info(f"[SemanticMemoryHook] Triggering V2 analysis (message #{self.message_count})")

            # Get text from the output message (agent's response)
            # We extract entities from the conversation, focusing on user input
            text_parts = []
            
            # Get text from kwargs (user input)
            if 'x' in kwargs:
                msgs = kwargs['x']
                if isinstance(msgs, list):
                    for msg in msgs:
                        if hasattr(msg, 'content'):
                            if isinstance(msg.content, str):
                                text_parts.append(msg.content)
                            elif isinstance(msg.content, list):
                                for item in msg.content:
                                    if isinstance(item, dict) and item.get('type') == 'text':
                                        text_parts.append(item.get('text', ''))

            if not text_parts:
                logger.debug("[SemanticMemoryHook] No text content found")
                return output

            combined_text = "\n".join(text_parts)
            logger.info(f"[SemanticMemoryHook] Analyzing text: {combined_text[:100]}...")

            # Extract entities using V2
            entities = await self.memory_manager.extract_entities(combined_text)

            if entities:
                entity_names = [getattr(e, 'name', str(e)) for e in entities[:5]]
                logger.info(f"[SemanticMemoryHook] Extracted {len(entities)} entities: {entity_names}")
            else:
                logger.debug("[SemanticMemoryHook] No entities extracted")

        except Exception as e:
            logger.error(f"[SemanticMemoryHook] Failed: {e}", exc_info=True)

        return output