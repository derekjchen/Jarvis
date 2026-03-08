# -*- coding: utf-8 -*-
"""Semantic memory hook for V2 memory system.

This hook periodically analyzes conversations and extracts semantic memories.
"""
import asyncio
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
        self.message_count += 1

        # Check if V2 is enabled
        if not hasattr(self.memory_manager, 'enable_v2'):
            return output

        if not self.memory_manager.enable_v2:
            return output

        # Analyze every N messages
        if self.message_count % self.analyze_every_n_messages != 0:
            return output

        logger.info(f"[SemanticMemoryHook] Triggering V2 analysis (message #{self.message_count})")

        # Get recent messages from agent's memory (non-blocking)
        text_parts = []
        
        try:
            # Get all messages from memory
            all_messages = await agent.memory.get_memory(
                exclude_mark=None,
                prepend_summary=False,
            )
            
            # Get the last user message (most recent)
            if all_messages:
                for msg in reversed(all_messages):
                    if hasattr(msg, 'role') and msg.role == 'user':
                        content = msg.content
                        if isinstance(content, str):
                            text_parts.append(content)
                        elif isinstance(content, list):
                            for item in content:
                                if isinstance(item, dict) and item.get('type') == 'text':
                                    text_parts.append(item.get('text', ''))
                        break  # Only get the last user message
        except Exception as e:
            logger.warning(f"[SemanticMemoryHook] Failed to get messages from memory: {e}")

        if not text_parts:
            logger.debug("[SemanticMemoryHook] No user text found in memory")
            return output

        combined_text = "\n".join(text_parts)
        logger.info(f"[SemanticMemoryHook] Analyzing: {combined_text[:100]}...")

        # Fire-and-forget: extract entities in background to avoid blocking main flow
        asyncio.create_task(
            self._extract_entities_async(combined_text)
        )

        return output

    async def _extract_entities_async(self, text: str) -> None:
        """Extract entities asynchronously without blocking main flow.

        Args:
            text: Text to extract entities from
        """
        try:
            entities = await self.memory_manager.extract_entities(text)

            if entities:
                entity_names = [getattr(e, 'name', str(e)) for e in entities[:5]]
                logger.info(f"[SemanticMemoryHook] Extracted {len(entities)} entities: {entity_names}")
            else:
                logger.debug("[SemanticMemoryHook] No entities extracted from this message")

        except asyncio.CancelledError:
            logger.debug("[SemanticMemoryHook] Entity extraction cancelled")
        except Exception as e:
            logger.error(f"[SemanticMemoryHook] Entity extraction failed: {e}", exc_info=True)