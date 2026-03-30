# -*- coding: utf-8 -*-
"""Entity Retriever for Memory V3.5.

This module provides hybrid search capabilities for entities,
combining keyword-based and vector-based retrieval.
"""
import logging
import math
from typing import Optional, TYPE_CHECKING

from .models import Entity, EntityType
from .store import UnifiedEntityStore

if TYPE_CHECKING:
    from agentscope.model import EmbeddingModelBase

logger = logging.getLogger(__name__)


class EntityRetriever:
    """Hybrid entity retriever with keyword and vector search.
    
    This class provides:
    - Keyword-based search (always available)
    - Vector-based semantic search (requires embedding model)
    - Hybrid search combining both methods
    """
    
    def __init__(self, store: UnifiedEntityStore, 
                 embedding_model: Optional["EmbeddingModelBase"] = None):
        """Initialize the retriever.
        
        Args:
            store: The entity store to search in
            embedding_model: Optional embedding model for vector search
        """
        self.store = store
        self.embedding_model = embedding_model
        
        # Cache for embeddings
        self._embedding_cache: dict[str, list[float]] = {}
    
    async def search(self, query: str, top_k: int = 10, 
                     min_score: float = 0.0,
                     entity_types: Optional[list[EntityType]] = None) -> list[tuple[Entity, float]]:
        """Search for entities using hybrid search.
        
        Args:
            query: Search query
            top_k: Maximum number of results
            min_score: Minimum score threshold
            entity_types: Optional filter by entity types
        
        Returns:
            List of (entity, score) tuples sorted by relevance
        """
        results = []
        
        # 1. Keyword search
        keyword_results = self._keyword_search(query, top_k * 2)
        results.extend(keyword_results)
        
        # 2. Vector search (if available)
        if self.embedding_model:
            vector_results = await self._vector_search(query, top_k * 2)
            results.extend(vector_results)
        
        # 3. Merge results
        merged = self._merge_results(results)
        
        # 4. Filter by type if specified
        if entity_types:
            merged = [(e, s) for e, s in merged if e.type in entity_types]
        
        # 5. Filter by score
        merged = [(e, s) for e, s in merged if s >= min_score]
        
        # 6. Sort and limit
        merged.sort(key=lambda x: (x[1], x[0].priority), reverse=True)
        
        return merged[:top_k]
    
    def _keyword_search(self, query: str, top_k: int) -> list[tuple[Entity, float]]:
        """Keyword-based search.
        
        Scoring:
        - Exact name match: 1.0
        - Name contains query: 0.8
        - Content contains query: 0.5
        - Tag match: 0.3
        - Word overlap: 0.0-0.3
        """
        query_lower = query.lower().strip()
        query_words = set(query_lower.split())
        
        results = []
        
        for entity in self.store.get_all_entities():
            if entity.is_expired():
                continue
            
            score = 0.0
            name_lower = entity.name.lower()
            content_lower = entity.content.lower()
            
            # Exact name match
            if query_lower == name_lower:
                score = 1.0
            # Name contains query
            elif query_lower in name_lower:
                score = 0.8
            # Query contains name
            elif name_lower and name_lower in query_lower:
                score = 0.7
            else:
                # Content match
                if query_lower in content_lower:
                    score = 0.5
                else:
                    # Word overlap
                    entity_words = set(name_lower.split()) | set(content_lower.split())
                    if query_words and entity_words:
                        overlap = len(query_words & entity_words) / len(query_words)
                        score = overlap * 0.3
            
            # Tag bonus
            for tag in entity.tags:
                if query_lower in tag.lower():
                    score = max(score, 0.3)
                    break
            
            if score > 0:
                # Priority boost
                if entity.priority >= 100:
                    score = min(score * 1.2, 1.0)
                elif entity.priority >= 80:
                    score = min(score * 1.1, 1.0)
                
                results.append((entity, score))
        
        results.sort(key=lambda x: x[1], reverse=True)
        return results[:top_k]
    
    async def _vector_search(self, query: str, top_k: int) -> list[tuple[Entity, float]]:
        """Vector-based semantic search.
        
        Requires embedding model to be configured.
        """
        if not self.embedding_model:
            return []
        
        try:
            # Get query embedding
            query_embedding = await self._get_embedding(query)
            if not query_embedding:
                return []
            
            results = []
            
            for entity in self.store.get_all_entities():
                if entity.is_expired():
                    continue
                
                # Get entity embedding
                entity_embedding = await self._get_entity_embedding(entity)
                if not entity_embedding:
                    continue
                
                # Calculate similarity
                similarity = self._cosine_similarity(query_embedding, entity_embedding)
                
                if similarity > 0.1:  # Minimum threshold
                    results.append((entity, similarity))
            
            results.sort(key=lambda x: x[1], reverse=True)
            return results[:top_k]
            
        except Exception as e:
            logger.error(f"Vector search failed: {e}")
            return []
    
    async def _get_embedding(self, text: str) -> Optional[list[float]]:
        """Get embedding for text.
        
        Uses cache to avoid redundant API calls.
        """
        if not self.embedding_model or not text:
            return None
        
        text = text.strip()
        if not text:
            return None
        
        # Check cache
        cache_key = text[:100]  # Use first 100 chars as key
        if cache_key in self._embedding_cache:
            return self._embedding_cache[cache_key]
        
        try:
            # Call embedding model
            if hasattr(self.embedding_model, 'embed'):
                embedding = self.embedding_model.embed(text)
            elif hasattr(self.embedding_model, '__call__'):
                result = self.embedding_model([text])
                embedding = result[0] if result else None
            else:
                logger.warning("Embedding model has no embed or __call__ method")
                return None
            
            # Cache result
            if embedding:
                self._embedding_cache[cache_key] = embedding
            
            return embedding
            
        except Exception as e:
            logger.error(f"Failed to get embedding: {e}")
            return None
    
    async def _get_entity_embedding(self, entity: Entity) -> Optional[list[float]]:
        """Get embedding for an entity.
        
        Uses stored embedding if available, otherwise generates and stores it.
        """
        # Use stored embedding if available
        if entity.embedding:
            return entity.embedding
        
        # Generate embedding
        text = f"{entity.name} {entity.content}"
        embedding = await self._get_embedding(text)
        
        # Store for future use
        if embedding:
            entity.embedding = embedding
            self.store.save()
        
        return embedding
    
    def _cosine_similarity(self, a: list[float], b: list[float]) -> float:
        """Calculate cosine similarity between two vectors."""
        if not a or not b or len(a) != len(b):
            return 0.0
        
        dot_product = sum(x * y for x, y in zip(a, b))
        norm_a = math.sqrt(sum(x * x for x in a))
        norm_b = math.sqrt(sum(x * x for x in b))
        
        if norm_a == 0 or norm_b == 0:
            return 0.0
        
        return dot_product / (norm_a * norm_b)
    
    def _merge_results(self, results: list[tuple[Entity, float]]) -> list[tuple[Entity, float]]:
        """Merge and deduplicate results from multiple search methods.
        
        Uses reciprocal rank fusion for scoring.
        """
        entity_scores: dict[str, list[float]] = {}
        
        for entity, score in results:
            if entity.id not in entity_scores:
                entity_scores[entity.id] = []
            entity_scores[entity.id].append(score)
        
        merged = []
        for entity_id, scores in entity_scores.items():
            entity = self.store.get_entity(entity_id)
            if entity:
                # Combine scores: take max and add small bonus for multiple matches
                max_score = max(scores)
                bonus = min(0.1 * (len(scores) - 1), 0.2)
                final_score = min(max_score + bonus, 1.0)
                merged.append((entity, final_score))
        
        return merged
    
    def get_by_type(self, entity_type: EntityType) -> list[Entity]:
        """Get all entities of a specific type."""
        return self.store.get_entities_by_type(entity_type)
    
    def get_safety_entities(self) -> list[Entity]:
        """Get all safety-related entities."""
        return self.store.get_safety_entities()
    
    def get_important_entities(self) -> list[Entity]:
        """Get all important entities (priority >= 80)."""
        return self.store.get_important_entities()
    
    def get_recent_entities(self, limit: int = 20) -> list[Entity]:
        """Get most recently accessed entities."""
        entities = self.store.get_all_entities()
        entities.sort(key=lambda e: e.last_accessed, reverse=True)
        return entities[:limit]
    
    def get_most_accessed(self, limit: int = 20) -> list[Entity]:
        """Get most frequently accessed entities."""
        entities = self.store.get_all_entities()
        entities.sort(key=lambda e: e.access_count, reverse=True)
        return entities[:limit]