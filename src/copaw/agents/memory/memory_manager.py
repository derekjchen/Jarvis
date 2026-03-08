# -*- coding: utf-8 -*-
# pylint: disable=too-many-branches
"""Memory Manager for CoPaw agents with V2 semantic memory integration.

Inherits from ReMeCopaw to provide memory management capabilities including:
- Message compaction and summarization
- Semantic memory search
- Memory file retrieval
- Tool result compaction
- V2: Semantic analysis, entity extraction, structured memory
"""
import logging
import os
from pathlib import Path

from agentscope.formatter import FormatterBase
from agentscope.message import Msg
from agentscope.model import ChatModelBase
from agentscope.token import HuggingFaceTokenCounter
from agentscope.tool import Toolkit

from ...config.utils import load_config
from ...constant import MEMORY_COMPACT_RATIO

logger = logging.getLogger(__name__)

# Try to import reme, log warning if it fails
try:
    from reme.reme_copaw import ReMeCopaw

    _REME_AVAILABLE = True

except ImportError:
    _REME_AVAILABLE = False
    logger.warning("reme package not installed.")

    class ReMeCopaw:  # type: ignore
        """Placeholder when reme is not available."""


# Try to import memory_v2 modules
try:
    from ...memory_v2 import SemanticAnalyzer, EntityExtractor, SemanticStore
    from ...memory_v2.models import SemanticMemory, Entity

    _MEMORY_V2_AVAILABLE = True
    logger.info("memory_v2 module loaded successfully")
except ImportError as e:
    _MEMORY_V2_AVAILABLE = False
    logger.warning(f"memory_v2 module not available: {e}")


class MemoryManager(ReMeCopaw):
    """Memory manager that extends ReMeCopaw with V2 semantic memory.

    This class provides memory management capabilities including:
    - Memory compaction for long conversations
    - Semantic memory search using vector and full-text search
    - Memory file retrieval with pagination
    - Tool result compaction with file-based storage
    - V2: Semantic analysis, entity extraction, structured memory storage
    """

    def __init__(
        self,
        working_dir: str,
        chat_model: ChatModelBase,
        formatter: FormatterBase,
        token_counter: HuggingFaceTokenCounter,
        toolkit: Toolkit,
        max_input_length: int,
        memory_compact_ratio: float,
        vector_weight: float = 0.7,
        candidate_multiplier: float = 3.0,
        tool_result_threshold: int = 1000,
        retention_days: int = 7,
        enable_v2: bool = True,
    ):
        """Initialize MemoryManager with ReMeCopaw configuration.

        Args:
            working_dir: Working directory path for memory storage
            chat_model: Language model for generating summaries
            formatter: Formatter for structuring model inputs/outputs
            token_counter: Token counting utility for length management
            toolkit: Collection of tools available to the application
            max_input_length: Maximum allowed input length in tokens
            memory_compact_ratio: Ratio at which to trigger compaction
            vector_weight: Weight for vector search in hybrid search
            candidate_multiplier: Multiplier for candidate retrieval
            tool_result_threshold: Size threshold for tool result compaction
            retention_days: Number of days to retain tool result files
            enable_v2: Whether to enable V2 semantic memory features
        """
        if not _REME_AVAILABLE:
            raise RuntimeError("reme package not installed.")

        # Get language from config if not provided
        global_config = load_config()
        language = "zh" if global_config.agents.language == "zh" else ""

        # Initialize parent ReMeCopaw class
        super().__init__(
            working_dir=working_dir,
            chat_model=chat_model,
            formatter=formatter,
            token_counter=token_counter,
            toolkit=toolkit,
            max_input_length=max_input_length,
            memory_compact_ratio=memory_compact_ratio,
            language=language,
            vector_weight=vector_weight,
            candidate_multiplier=candidate_multiplier,
            tool_result_threshold=tool_result_threshold,
            retention_days=retention_days,
        )

        # Initialize V2 components
        self.enable_v2 = enable_v2 and _MEMORY_V2_AVAILABLE
        self.semantic_analyzer = None
        self.entity_extractor = None
        self.semantic_store = None

        if self.enable_v2:
            try:
                self.semantic_analyzer = SemanticAnalyzer(chat_model)
                self.entity_extractor = EntityExtractor(chat_model)
                
                # Initialize semantic store
                store_dir = Path(working_dir) / "semantic_memory"
                self.semantic_store = SemanticStore(store_dir)
                
                logger.info("V2 semantic memory initialized successfully")
            except Exception as e:
                logger.error(f"Failed to initialize V2 semantic memory: {e}")
                self.enable_v2 = False

    def update_config_params(self):
        global_config = load_config()

        super().update_params(
            max_input_length=global_config.agents.running.max_input_length,
            memory_compact_ratio=MEMORY_COMPACT_RATIO,
            language=global_config.agents.language,
        )

    async def compact_memory(
        self,
        messages: list[Msg],
        previous_summary: str = "",
    ) -> str:
        """
        Compact a list of messages into a condensed summary.

        This method uses the Compactor to reduce the length of message history
        while preserving essential information.
        """
        self.update_config_params()
        return await super().compact_memory(
            messages=messages,
            previous_summary=previous_summary,
        )

    async def summary_memory(self, messages: list[Msg]) -> str:
        """
        Generate a comprehensive summary of the given messages.

        This method uses the Summarizer to create a detailed summary of the
        conversation history, which can be stored as persistent memory.

        V2 Enhancement: Also performs semantic analysis and entity extraction.
        """
        self.update_config_params()
        
        # Call parent summarization (this is the main functionality)
        summary = await super().summary_memory(messages)

        # V2: Perform semantic analysis on the summary (best effort, non-blocking)
        if self.enable_v2 and summary and self.semantic_analyzer:
            try:
                import asyncio
                logger.info("Attempting V2 semantic analysis on summary")
                
                # Run V2 analysis with timeout to prevent blocking
                async def run_v2_analysis():
                    try:
                        semantic_memory = await asyncio.wait_for(
                            self.semantic_analyzer.analyze(summary),
                            timeout=30.0  # 30 second timeout
                        )
                        return semantic_memory
                    except asyncio.TimeoutError:
                        logger.warning("V2 semantic analysis timed out")
                        return None
                    except Exception as e:
                        logger.error(f"V2 semantic analysis error: {e}")
                        return None
                
                semantic_memory = await run_v2_analysis()
                
                # Store the semantic memory
                if self.semantic_store and semantic_memory:
                    self.semantic_store.add_memory(semantic_memory)
                    logger.info(f"Stored semantic memory: {semantic_memory.id}")
                    
                    # Log extracted entities
                    if semantic_memory.entities:
                        entity_names = [e.name for e in semantic_memory.entities[:5]]
                        logger.info(f"Extracted entities: {entity_names}")
                        
            except Exception as e:
                # Log but don't fail the main summary
                logger.error(f"V2 semantic analysis failed (non-fatal): {e}")

        return summary

    async def extract_entities(self, text: str) -> list[Entity]:
        """
        Extract entities from text using V2 entity extractor.

        Args:
            text: Text to extract entities from

        Returns:
            List of extracted entities
        """
        if not self.enable_v2 or not self.entity_extractor:
            logger.warning("V2 entity extraction not available")
            return []

        try:
            entities = await self.entity_extractor.extract(text)
            logger.info(f"Extracted {len(entities)} entities from text")
            return entities
        except Exception as e:
            logger.error(f"Entity extraction failed: {e}")
            return []

    def get_semantic_memories(self, limit: int = 10) -> list[SemanticMemory]:
        """
        Get recent semantic memories from V2 store.

        Args:
            limit: Maximum number of memories to return

        Returns:
            List of semantic memories
        """
        if not self.enable_v2 or not self.semantic_store:
            return []

        return self.semantic_store.get_recent_memories(limit)

    def search_semantic_memories(self, query: str) -> list[SemanticMemory]:
        """
        Search semantic memories by query.

        Args:
            query: Search query

        Returns:
            List of matching semantic memories
        """
        if not self.enable_v2 or not self.semantic_store:
            return []

        return self.semantic_store.search_memories(query)

    def get_entity_knowledge_base(self) -> list[Entity]:
        """
        Get all known entities from the entity knowledge base.

        Returns:
            List of all known entities
        """
        if not self.enable_v2 or not self.semantic_store:
            return []

        return self.semantic_store.get_all_entities()

    def is_v2_enabled(self) -> bool:
        """Check if V2 semantic memory is enabled and working."""
        return self.enable_v2 and self.semantic_analyzer is not None