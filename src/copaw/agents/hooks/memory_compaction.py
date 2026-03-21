# -*- coding: utf-8 -*-
"""Memory compaction hook for managing context window.

This hook monitors token usage and automatically compacts older messages
when the context window approaches its limit, preserving recent messages
and the system prompt.

Enhanced in V2.1 to preserve key information during compaction:
- Extracts key info (allergies, preferences, decisions) before compaction
- Validates compacted summary contains key info
- Auto-enhances summary if key info is missing

Enhanced in V3.5 to persist key information:
- Stores extracted key info in UnifiedEntityStore
- Enables cross-session information retrieval
"""
import logging
from typing import TYPE_CHECKING, Any

from agentscope.agent._react_agent import _MemoryMark, ReActAgent

from copaw.config import load_config
from copaw.constant import MEMORY_COMPACT_KEEP_RECENT, WORKING_DIR
from ..utils import (
    check_valid_messages,
    safe_count_str_tokens,
)
from .key_info_extractor import KeyInfoExtractor
from .compact_validator import CompactValidator

if TYPE_CHECKING:
    from ..memory import MemoryManager
    from ..memory.unified.integration import MemoryIntegration
    from reme.memory.file_based import ReMeInMemoryMemory

logger = logging.getLogger(__name__)


class MemoryCompactionHook:
    """Hook for automatic memory compaction when context is full.

    This hook monitors the token count of messages and triggers compaction
    when it exceeds the threshold. It preserves the system prompt and recent
    messages while summarizing older conversation history.

    Enhanced features (V2.1):
    - Key information extraction before compaction
    - Validation of compacted summary
    - Auto-enhancement if key info is missing

    Enhanced features (V3.5):
    - Persistence of key info to UnifiedEntityStore
    - Cross-session entity retrieval
    """

    def __init__(self, memory_manager: "MemoryManager"):
        """Initialize memory compaction hook.

        Args:
            memory_manager: Memory manager instance for compaction
        """
        self.memory_manager = memory_manager
        self.key_info_extractor = KeyInfoExtractor()
        self.compact_validator = CompactValidator(
            strict_safety=True,
            auto_enhance=True,
        )
        # V3.5: Lazy load MemoryIntegration
        self._memory_integration: "MemoryIntegration | None" = None
    
    @property
    def memory_integration(self) -> "MemoryIntegration | None":
        """Lazy load MemoryIntegration for V3.5 entity persistence."""
        if self._memory_integration is None:
            try:
                from ..memory.unified.integration import get_memory_integration
                self._memory_integration = get_memory_integration(WORKING_DIR)
            except Exception as e:
                logger.warning(f"Failed to load MemoryIntegration: {e}")
        return self._memory_integration

    async def __call__(
        self,
        agent: ReActAgent,
        kwargs: dict[str, Any],
    ) -> dict[str, Any] | None:
        """Pre-reasoning hook to check and compact memory if needed.

        This hook extracts system prompt messages and recent messages,
        builds an estimated full context prompt, and triggers compaction
        when the total estimated token count exceeds the threshold.

        Memory structure:
            [System Prompt (preserved)] + [Compactable (counted)] +
            [Recent (preserved)]

        Args:
            agent: The agent instance
            kwargs: Input arguments to the _reasoning method

        Returns:
            None (hook doesn't modify kwargs)
        """
        try:
            memory: "ReMeInMemoryMemory" = agent.memory
            token_counter = self.memory_manager.token_counter

            system_prompt = agent.sys_prompt
            compressed_summary = memory.get_compressed_summary()
            str_token_count = safe_count_str_tokens(
                system_prompt + compressed_summary,
            )

            config = load_config()
            memory_compact_threshold = (
                config.agents.running.memory_compact_threshold
            )
            left_compact_threshold = memory_compact_threshold - str_token_count

            if left_compact_threshold <= 0:
                logger.warning(
                    "The memory_compact_threshold is set too low; "
                    "the combined token length of system_prompt and "
                    "compressed_summary exceeds the configured threshold. "
                    "Alternatively, you could use /clear to reset the context "
                    "and compressed_summary, ensuring the total remains "
                    "below the threshold.",
                )
                return None

            messages = await memory.get_memory(prepend_summary=False)

            enable_tool_result_compact = (
                config.agents.running.enable_tool_result_compact
            )
            tool_result_compact_keep_n = (
                config.agents.running.tool_result_compact_keep_n
            )
            if enable_tool_result_compact and tool_result_compact_keep_n > 0:
                compact_msgs = messages[:-tool_result_compact_keep_n]
                await self.memory_manager.compact_tool_result(compact_msgs)

            memory_compact_reserve = (
                config.agents.running.memory_compact_reserve
            )
            (
                messages_to_compact,
                _,
                is_valid,
            ) = await self.memory_manager.check_context(
                messages=messages,
                memory_compact_threshold=left_compact_threshold,
                memory_compact_reserve=memory_compact_reserve,
                token_counter=token_counter,
            )

            if not messages_to_compact:
                return None

            if not is_valid:
                logger.warning(
                    "Please include the output of the /history command when "
                    "reporting the bug to the community. Invalid "
                    "messages=%s",
                    messages,
                )
                keep_length: int = MEMORY_COMPACT_KEEP_RECENT
                messages_length = len(messages)
                while keep_length > 0 and not check_valid_messages(
                    messages[max(messages_length - keep_length, 0) :],
                ):
                    keep_length -= 1

                if keep_length > 0:
                    messages_to_compact = messages[
                        : max(messages_length - keep_length, 0)
                    ]
                else:
                    messages_to_compact = messages

            if not messages_to_compact:
                return None

            # ============================================================
            # V2.1 Enhancement: Extract key information before compaction
            # ============================================================
            logger.info("Extracting key information before compaction...")
            key_infos = self.key_info_extractor.extract(messages_to_compact)
            
            if key_infos:
                logger.info(f"Found {len(key_infos)} key info items to preserve")
                # Log key info for debugging
                for info in key_infos[:5]:  # Only log first 5
                    logger.debug(f"  - [{info.info_type}] {info.content} (priority: {info.priority})")
                
                # ============================================================
                # V3.5 Enhancement: Persist key info to UnifiedEntityStore
                # ============================================================
                try:
                    integration = self.memory_integration
                    if integration:
                        entity_ids = integration.add_key_infos(key_infos)
                        if entity_ids:
                            logger.info(
                                f"V3.5: Stored {len(entity_ids)} entities in UnifiedEntityStore"
                            )
                except Exception as e:
                    logger.warning(f"V3.5: Failed to store entities: {e}")
            else:
                logger.info("No key information found in messages to compact")

            # Perform compaction with key info injection (V2.1 Layer 1: Prevention)
            compact_content = await self.memory_manager.compact_memory(
                messages=messages_to_compact,
                previous_summary=memory.get_compressed_summary(),
                key_infos=key_infos,  # V2.1: Inject key info into prompt
            )

            # ============================================================
            # V2.1 Enhancement: Validate and enhance compacted summary
            # ============================================================
            if key_infos:
                logger.info("Validating compacted summary for key information...")
                validation_result = self.compact_validator.validate(
                    summary=compact_content,
                    key_infos=key_infos,
                    min_priority=50,  # Check preference level and above
                )
                
                if not validation_result.passed:
                    logger.warning(
                        f"Compact validation failed: {len(validation_result.missing)} key info items missing"
                    )
                    # Use enhanced summary if available
                    if validation_result.enhanced_summary:
                        compact_content = validation_result.enhanced_summary
                        logger.info("Using enhanced summary with key info appended")
                else:
                    logger.info(
                        f"Compact validation passed: {len(validation_result.found)} key info items preserved"
                    )
                    
                # Log missing items for debugging
                for info in validation_result.missing:
                    logger.debug(f"  Missing: [{info.info_type}] {info.content}")

            await agent.memory.update_compressed_summary(compact_content)
            updated_count = await memory.update_messages_mark(
                new_mark=_MemoryMark.COMPRESSED,
                msg_ids=[msg.id for msg in messages_to_compact],
            )
            logger.info(f"Marked {updated_count} messages as compacted")

        except Exception as e:
            logger.error(
                "Failed to compact memory in pre_reasoning hook: %s",
                e,
                exc_info=True,
            )

        return None