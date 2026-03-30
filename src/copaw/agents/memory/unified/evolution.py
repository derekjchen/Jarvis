# -*- coding: utf-8 -*-
"""Memory Evolution System - M5.0

This module implements the memory evolution capabilities:
- Quality evaluation
- Forgetting mechanism
- Memory integration
- Evolution scheduling

Author: sm-co (AI Assistant)
Date: 2026-03-21
"""
import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Optional, Callable
from collections import Counter

from .models import Entity, EntityType, EntitySource
from .store import UnifiedEntityStore

logger = logging.getLogger(__name__)


# =============================================================================
# Configuration
# =============================================================================

@dataclass
class EvolutionConfig:
    """Configuration for memory evolution."""
    
    # Quality thresholds
    quality_threshold: float = 0.3  # Below this, entity is candidate for forgetting
    high_quality_threshold: float = 0.7  # Above this, entity is high quality
    
    # Time-based parameters
    event_retention_days: int = 365  # Events kept for 1 year
    preference_half_life_days: int = 90  # Preferences decay with 90-day half-life
    fact_retention_days: int = 180  # Facts kept for 6 months
    
    # Safety parameters
    never_forget_types: tuple = (
        EntityType.ALLERGY,
        EntityType.CONSTRAINT,
    )
    
    # Integration parameters
    similarity_threshold: float = 0.8  # For merging similar entities
    max_entities: int = 1000  # Maximum entities before triggering cleanup
    
    # Evolution schedule
    evolution_interval_hours: int = 24  # Run evolution every 24 hours


# =============================================================================
# Evolution Report
# =============================================================================

@dataclass
class EvolutionReport:
    """Report of an evolution cycle."""
    
    timestamp: datetime = field(default_factory=datetime.now)
    
    # Entity counts
    total_entities: int = 0
    processed_entities: int = 0
    
    # Quality assessment
    high_quality_count: int = 0
    low_quality_count: int = 0
    
    # Actions taken
    forgotten_count: int = 0
    merged_count: int = 0
    archived_count: int = 0
    
    # Errors
    errors: list[str] = field(default_factory=list)
    
    def to_dict(self) -> dict:
        return {
            "timestamp": self.timestamp.isoformat(),
            "total_entities": self.total_entities,
            "processed_entities": self.processed_entities,
            "high_quality_count": self.high_quality_count,
            "low_quality_count": self.low_quality_count,
            "forgotten_count": self.forgotten_count,
            "merged_count": self.merged_count,
            "archived_count": self.archived_count,
            "errors": self.errors,
        }
    
    def summary(self) -> str:
        lines = [
            f"📊 Evolution Report ({self.timestamp.strftime('%Y-%m-%d %H:%M')})",
            f"   Total entities: {self.total_entities}",
            f"   High quality: {self.high_quality_count}",
            f"   Low quality: {self.low_quality_count}",
            f"   Forgotten: {self.forgotten_count}",
            f"   Merged: {self.merged_count}",
        ]
        if self.errors:
            lines.append(f"   ⚠️ Errors: {len(self.errors)}")
        return "\n".join(lines)


# =============================================================================
# Phase 1: Quality Evaluator
# =============================================================================

class MemoryQualityEvaluator:
    """Evaluates the quality and importance of memory entities.
    
    Quality Score = weighted average of:
    - Access frequency (0.25)
    - Time decay (0.20)
    - Safety priority (0.25)
    - Source credibility (0.15)
    - Content completeness (0.15)
    """
    
    def __init__(self, config: Optional[EvolutionConfig] = None):
        self.config = config or EvolutionConfig()
    
    def evaluate(self, entity: Entity) -> float:
        """Evaluate entity quality (0.0 to 1.0).
        
        Args:
            entity: Entity to evaluate
        
        Returns:
            Quality score from 0.0 (lowest) to 1.0 (highest)
        """
        # Safety entities always get maximum score
        if entity.type in self.config.never_forget_types:
            return 1.0
        
        # Calculate component scores
        access_score = self._access_score(entity)
        time_score = self._time_decay_score(entity)
        safety_score = self._safety_priority_score(entity)
        source_score = self._source_credibility_score(entity)
        content_score = self._content_completeness_score(entity)
        
        # Weighted average
        quality = (
            access_score * 0.25 +
            time_score * 0.20 +
            safety_score * 0.25 +
            source_score * 0.15 +
            content_score * 0.15
        )
        
        return round(min(max(quality, 0.0), 1.0), 3)
    
    def _access_score(self, entity: Entity) -> float:
        """Score based on access frequency.
        
        - More accesses = higher score
        - Recent access boosts score
        """
        # Base score from access count (logarithmic scale)
        import math
        base_score = min(math.log10(entity.access_count + 1) / 2, 1.0)
        
        # Boost for recent access
        days_since_access = (datetime.now() - entity.last_accessed).days
        recency_boost = max(0, 1 - days_since_access / 30) * 0.3
        
        return min(base_score + recency_boost, 1.0)
    
    def _time_decay_score(self, entity: Entity) -> float:
        """Score based on time decay.
        
        Different entity types have different decay rates.
        """
        days_old = (datetime.now() - entity.created_at).days
        
        # Get decay half-life based on type
        if entity.type in (EntityType.EVENT, EntityType.MILESTONE):
            half_life = 180  # 6 months
        elif entity.type in (EntityType.PREFERENCE, EntityType.DISLIKE):
            half_life = self.config.preference_half_life_days
        elif entity.type == EntityType.FACT:
            half_life = self.config.fact_retention_days / 2
        else:
            half_life = 90  # Default 3 months
        
        # Exponential decay
        if half_life > 0:
            decay = 0.5 ** (days_old / half_life)
        else:
            decay = 1.0
        
        return decay
    
    def _safety_priority_score(self, entity: Entity) -> float:
        """Score based on safety priority."""
        # Priority 100 = safety = 1.0
        # Priority 80 = high = 0.8
        # Priority 50 = medium = 0.5
        # Priority 20 = low = 0.2
        return entity.priority / 100.0
    
    def _source_credibility_score(self, entity: Entity) -> float:
        """Score based on extraction source."""
        # LLM extraction is more reliable than regex
        if entity.source == EntitySource.LLM:
            return 0.9 * entity.confidence
        elif entity.source == EntitySource.MANUAL:
            return 1.0  # User explicitly added
        elif entity.source == EntitySource.IMPORT:
            return 0.7 * entity.confidence
        else:  # REGEX
            return 0.6 * entity.confidence
    
    def _content_completeness_score(self, entity: Entity) -> float:
        """Score based on content completeness."""
        score = 0.0
        
        # Has name
        if entity.name:
            score += 0.3
        
        # Has content/description
        if entity.content and len(entity.content) > 10:
            score += 0.3
        
        # Has context
        if entity.context:
            score += 0.2
        
        # Has tags
        if entity.tags:
            score += 0.1
        
        # Has relations
        if entity.related_entities:
            score += 0.1
        
        return score
    
    def evaluate_all(self, entities: list[Entity]) -> dict[str, float]:
        """Evaluate all entities and return quality map."""
        return {e.id: self.evaluate(e) for e in entities}


# =============================================================================
# Phase 2: Forgetting Mechanism
# =============================================================================

class MemoryForgetter:
    """Decides which entities should be forgotten.
    
    Forgetting criteria:
    - Quality score below threshold
    - Expired (past valid_until)
    - Too old for entity type
    - Not a safety entity
    """
    
    def __init__(self, config: Optional[EvolutionConfig] = None):
        self.config = config or EvolutionConfig()
        self.evaluator = MemoryQualityEvaluator(config)
    
    def should_forget(self, entity: Entity, quality_score: Optional[float] = None) -> bool:
        """Determine if an entity should be forgotten.
        
        Args:
            entity: Entity to check
            quality_score: Pre-computed quality score (optional)
        
        Returns:
            True if entity should be forgotten
        """
        # Safety entities are never forgotten
        if entity.type in self.config.never_forget_types:
            return False
        
        # Priority 100 entities are never forgotten
        if entity.priority >= 100:
            return False
        
        # Check expiration
        if entity.is_expired():
            logger.debug(f"Entity {entity.id} expired, should forget")
            return True
        
        # Check quality threshold
        if quality_score is None:
            quality_score = self.evaluator.evaluate(entity)
        
        if quality_score < self.config.quality_threshold:
            logger.debug(f"Entity {entity.id} quality {quality_score:.2f} below threshold")
            return True
        
        # Check age-based retention
        age_days = (datetime.now() - entity.created_at).days
        max_age = self._get_max_age(entity.type)
        
        if max_age and age_days > max_age:
            logger.debug(f"Entity {entity.id} age {age_days} exceeds max {max_age}")
            return True
        
        return False
    
    def _get_max_age(self, entity_type: EntityType) -> Optional[int]:
        """Get maximum age in days for entity type."""
        age_map = {
            EntityType.EVENT: self.config.event_retention_days,
            EntityType.MILESTONE: self.config.event_retention_days,
            EntityType.FACT: self.config.fact_retention_days,
            EntityType.CONTACT: 365 * 2,  # 2 years
            EntityType.PERSON: 365 * 2,
            EntityType.PROJECT: 365,
            EntityType.DECISION: 365 * 2,
        }
        return age_map.get(entity_type)
    
    def find_forgettable(self, entities: list[Entity]) -> list[tuple[Entity, str]]:
        """Find all entities that should be forgotten.
        
        Returns:
            List of (entity, reason) tuples
        """
        # Pre-evaluate all
        quality_map = self.evaluator.evaluate_all(entities)
        
        forgettable = []
        for entity in entities:
            reason = None
            
            # Safety entities never forgotten
            if entity.type in self.config.never_forget_types:
                continue
            
            if entity.priority >= 100:
                continue
            
            if entity.is_expired():
                reason = "expired"
            elif quality_map[entity.id] < self.config.quality_threshold:
                reason = "low_quality"
            else:
                age_days = (datetime.now() - entity.created_at).days
                max_age = self._get_max_age(entity.type)
                if max_age and age_days > max_age:
                    reason = "too_old"
            
            if reason:
                forgettable.append((entity, reason))
        
        return forgettable


# =============================================================================
# Phase 3: Memory Integration
# =============================================================================

class MemoryIntegrator:
    """Integrates similar memories and resolves conflicts.
    
    Operations:
    - Merge similar entities
    - Resolve conflicting preferences
    - Consolidate duplicate information
    """
    
    def __init__(self, config: Optional[EvolutionConfig] = None):
        self.config = config or EvolutionConfig()
    
    def integrate(self, entities: list[Entity]) -> list[Entity]:
        """Integrate entities by merging similar ones.
        
        Args:
            entities: List of entities to integrate
        
        Returns:
            Integrated list with duplicates merged
        """
        if len(entities) < 2:
            return entities
        
        # Group by type
        by_type: dict[EntityType, list[Entity]] = {}
        for entity in entities:
            if entity.type not in by_type:
                by_type[entity.type] = []
            by_type[entity.type].append(entity)
        
        # Process each type
        integrated = []
        for entity_type, type_entities in by_type.items():
            if entity_type in self.config.never_forget_types:
                # Don't merge safety entities
                integrated.extend(type_entities)
            else:
                merged = self._merge_group(type_entities)
                integrated.extend(merged)
        
        return integrated
    
    def _merge_group(self, entities: list[Entity]) -> list[Entity]:
        """Merge similar entities in a group."""
        if len(entities) < 2:
            return entities
        
        # Build similarity clusters
        clusters = self._cluster_similar(entities)
        
        # Merge each cluster
        result = []
        for cluster in clusters:
            if len(cluster) == 1:
                result.append(cluster[0])
            else:
                merged = self._merge_cluster(cluster)
                result.append(merged)
        
        return result
    
    def _cluster_similar(self, entities: list[Entity]) -> list[list[Entity]]:
        """Cluster similar entities together."""
        # Simple approach: group by normalized name
        name_groups: dict[str, list[Entity]] = {}
        
        for entity in entities:
            # Normalize name
            norm_name = self._normalize_name(entity.name)
            
            if norm_name not in name_groups:
                name_groups[norm_name] = []
            name_groups[norm_name].append(entity)
        
        return list(name_groups.values())
    
    def _normalize_name(self, name: str) -> str:
        """Normalize entity name for comparison."""
        # Lowercase, remove extra spaces
        name = name.lower().strip()
        name = " ".join(name.split())
        return name
    
    def _merge_cluster(self, cluster: list[Entity]) -> Entity:
        """Merge a cluster of similar entities into one."""
        # Sort by quality indicators
        def sort_key(e: Entity) -> tuple:
            return (
                -e.priority,  # Higher priority first
                -e.access_count,  # More accesses first
                -e.created_at.timestamp(),  # More recent first
            )
        
        cluster.sort(key=sort_key)
        
        # Use first entity as base
        base = cluster[0]
        
        # Merge information from others
        all_contexts = [base.context] if base.context else []
        all_tags = list(base.tags)
        all_attrs = dict(base.attributes)
        
        for other in cluster[1:]:
            # Collect contexts
            if other.context and other.context not in all_contexts:
                all_contexts.append(other.context)
            
            # Collect tags
            for tag in other.tags:
                if tag not in all_tags:
                    all_tags.append(tag)
            
            # Merge attributes
            for key, value in other.attributes.items():
                if key not in all_attrs:
                    all_attrs[key] = value
        
        # Update base entity
        base.context = " | ".join(all_contexts) if all_contexts else base.context
        base.tags = all_tags
        base.attributes = all_attrs
        
        # Update access count (sum of all)
        base.access_count = sum(e.access_count for e in cluster)
        
        # Update timestamp
        base.last_updated = datetime.now()
        
        logger.debug(f"Merged {len(cluster)} entities into {base.id}")
        
        return base
    
    def detect_conflicts(self, entities: list[Entity]) -> list[tuple[Entity, Entity, str]]:
        """Detect conflicting entities.
        
        Returns:
            List of (entity1, entity2, conflict_type) tuples
        """
        conflicts = []
        
        # Check for preference/dislike conflicts
        prefs = [e for e in entities if e.type == EntityType.PREFERENCE]
        dislikes = [e for e in entities if e.type == EntityType.DISLIKE]
        
        for pref in prefs:
            for dislike in dislikes:
                if self._names_similar(pref.name, dislike.name):
                    conflicts.append((pref, dislike, "preference_dislike_conflict"))
        
        return conflicts
    
    def _names_similar(self, name1: str, name2: str) -> bool:
        """Check if two names are similar."""
        n1 = self._normalize_name(name1)
        n2 = self._normalize_name(name2)
        
        # Exact match
        if n1 == n2:
            return True
        
        # One contains the other
        if n1 in n2 or n2 in n1:
            return True
        
        # Simple word overlap
        words1 = set(n1.split())
        words2 = set(n2.split())
        overlap = len(words1 & words2)
        
        if overlap > 0 and overlap / max(len(words1), len(words2), 1) > 0.5:
            return True
        
        return False


# =============================================================================
# Phase 4: Evolution Orchestrator
# =============================================================================

class MemoryEvolver:
    """Orchestrates the memory evolution process.
    
    Evolution cycle:
    1. Load all entities
    2. Evaluate quality
    3. Identify entities to forget
    4. Integrate similar entities
    5. Persist changes
    """
    
    def __init__(self, store: UnifiedEntityStore, 
                 config: Optional[EvolutionConfig] = None):
        self.store = store
        self.config = config or EvolutionConfig()
        
        self.evaluator = MemoryQualityEvaluator(self.config)
        self.forgetter = MemoryForgetter(self.config)
        self.integrator = MemoryIntegrator(self.config)
        
        # Track last evolution
        self._last_evolution: Optional[datetime] = None
        self._last_report: Optional[EvolutionReport] = None
    
    def should_evolve(self) -> bool:
        """Check if evolution should run."""
        if self._last_evolution is None:
            return True
        
        hours_since = (datetime.now() - self._last_evolution).total_seconds() / 3600
        return hours_since >= self.config.evolution_interval_hours
    
    async def evolve(self) -> EvolutionReport:
        """Execute one evolution cycle.
        
        Returns:
            EvolutionReport with statistics
        """
        logger.info("Starting memory evolution cycle...")
        report = EvolutionReport()
        
        try:
            # 1. Load all entities
            entities = self.store.get_all_entities()
            report.total_entities = len(entities)
            logger.info(f"Loaded {len(entities)} entities")
            
            if len(entities) == 0:
                return report
            
            # 2. Evaluate quality
            quality_map = self.evaluator.evaluate_all(entities)
            
            report.high_quality_count = sum(
                1 for q in quality_map.values() 
                if q >= self.config.high_quality_threshold
            )
            report.low_quality_count = sum(
                1 for q in quality_map.values() 
                if q < self.config.quality_threshold
            )
            
            # 3. Find entities to forget
            forgettable = self.forgetter.find_forgettable(entities)
            report.forgotten_count = len(forgettable)
            
            # 4. Execute forgetting
            forget_ids = {e.id for e, _ in forgettable}
            remaining = [e for e in entities if e.id not in forget_ids]
            
            for entity, reason in forgettable:
                self.store.delete_entity(entity.id)
                logger.debug(f"Forgot entity {entity.id}: {reason}")
            
            # 5. Integrate remaining entities
            integrated = self.integrator.integrate(remaining)
            report.merged_count = len(remaining) - len(integrated) + len(
                [e for e in remaining if e.id not in {ie.id for ie in integrated}]
            )
            
            # 6. Update quality scores in attributes
            for entity in integrated:
                entity.attributes["_quality_score"] = quality_map.get(entity.id, 0.5)
                entity.attributes["_last_evolution"] = datetime.now().isoformat()
            
            report.processed_entities = len(integrated)
            
            # 7. Save
            self.store.save()
            
            # 8. Update tracking
            self._last_evolution = datetime.now()
            self._last_report = report
            
            logger.info(f"Evolution complete: {report.summary()}")
            
        except Exception as e:
            logger.error(f"Evolution failed: {e}")
            report.errors.append(str(e))
        
        return report
    
    def get_last_report(self) -> Optional[EvolutionReport]:
        """Get the last evolution report."""
        return self._last_report
    
    def get_evolution_summary(self) -> dict:
        """Get summary of evolution state."""
        return {
            "last_evolution": self._last_evolution.isoformat() if self._last_evolution else None,
            "should_evolve": self.should_evolve(),
            "config": {
                "quality_threshold": self.config.quality_threshold,
                "max_entities": self.config.max_entities,
                "evolution_interval_hours": self.config.evolution_interval_hours,
            },
            "last_report": self._last_report.to_dict() if self._last_report else None,
        }


# =============================================================================
# Utility Functions
# =============================================================================

def create_evolver_for_agent(storage_dir: str, 
                             config: Optional[EvolutionConfig] = None) -> MemoryEvolver:
    """Create a MemoryEvolver for an agent.
    
    Args:
        storage_dir: Directory for entity storage
        config: Optional evolution configuration
    
    Returns:
        Configured MemoryEvolver
    """
    store = UnifiedEntityStore(storage_dir, auto_save=False)
    return MemoryEvolver(store, config)