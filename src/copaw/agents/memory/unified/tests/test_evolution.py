# -*- coding: utf-8 -*-
"""Tests for M5.0 Memory Evolution System.

Run with: pytest src/copaw/agents/memory/unified/tests/test_evolution.py -v
"""
import pytest
from datetime import datetime, timedelta
import tempfile
import os
import sys

# Add src to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../../../.."))

from copaw.agents.memory.unified.models import Entity, EntityType, EntitySource
from copaw.agents.memory.unified.store import UnifiedEntityStore
from copaw.agents.memory.unified.evolution import (
    EvolutionConfig,
    EvolutionReport,
    MemoryQualityEvaluator,
    MemoryForgetter,
    MemoryIntegrator,
    MemoryEvolver,
)


# =============================================================================
# Fixtures
# =============================================================================

@pytest.fixture
def temp_store():
    """Create a temporary entity store."""
    with tempfile.TemporaryDirectory() as tmpdir:
        store = UnifiedEntityStore(tmpdir, auto_save=True)
        yield store


@pytest.fixture
def sample_entities():
    """Create sample entities for testing."""
    now = datetime.now()
    
    return [
        # Safety entity - should never be forgotten
        Entity(
            id="allergy1",
            type=EntityType.ALLERGY,
            name="花生过敏",
            content="用户对花生严重过敏",
            priority=100,
            source=EntitySource.REGEX,
            access_count=10,
            created_at=now - timedelta(days=100),
        ),
        
        # High quality preference
        Entity(
            id="pref1",
            type=EntityType.PREFERENCE,
            name="喜欢川菜",
            content="用户喜欢辣的川菜",
            priority=80,
            source=EntitySource.LLM,
            access_count=5,
            created_at=now - timedelta(days=10),
        ),
        
        # Low quality, rarely accessed
        Entity(
            id="fact1",
            type=EntityType.FACT,
            name="某个随机事实",
            content="这是一个不太重要的事实",
            priority=20,
            source=EntitySource.REGEX,
            access_count=0,
            created_at=now - timedelta(days=200),
        ),
        
        # Duplicate preference (similar to pref1)
        Entity(
            id="pref2",
            type=EntityType.PREFERENCE,
            name="喜欢吃辣",
            content="喜欢吃辣的菜",
            priority=70,
            source=EntitySource.LLM,
            access_count=2,
            created_at=now - timedelta(days=5),
        ),
        
        # Expired event
        Entity(
            id="event1",
            type=EntityType.EVENT,
            name="旧会议",
            content="三个月前的会议",
            priority=50,
            source=EntitySource.REGEX,
            access_count=1,
            created_at=now - timedelta(days=400),
            valid_until=now - timedelta(days=300),
        ),
    ]


# =============================================================================
# Quality Evaluator Tests
# =============================================================================

class TestMemoryQualityEvaluator:
    
    def test_safety_entity_max_quality(self):
        """Safety entities should always have quality 1.0."""
        evaluator = MemoryQualityEvaluator()
        
        entity = Entity(
            type=EntityType.ALLERGY,
            name="花生过敏",
            content="严重过敏",
            priority=100,
        )
        
        quality = evaluator.evaluate(entity)
        assert quality == 1.0
    
    def test_constraint_max_quality(self):
        """Constraint entities should also have max quality."""
        evaluator = MemoryQualityEvaluator()
        
        entity = Entity(
            type=EntityType.CONSTRAINT,
            name="海鲜禁忌",
            content="不能吃海鲜",
            priority=100,
        )
        
        quality = evaluator.evaluate(entity)
        assert quality == 1.0
    
    def test_high_access_high_quality(self):
        """Entities with more accesses should have higher quality."""
        evaluator = MemoryQualityEvaluator()
        
        entity_low = Entity(
            type=EntityType.PREFERENCE,
            name="喜欢苹果",
            access_count=0,
        )
        
        entity_high = Entity(
            type=EntityType.PREFERENCE,
            name="喜欢苹果",
            access_count=100,
        )
        
        quality_low = evaluator.evaluate(entity_low)
        quality_high = evaluator.evaluate(entity_high)
        
        assert quality_high > quality_low
    
    def test_recent_access_boost(self):
        """Recently accessed entities should have quality boost."""
        evaluator = MemoryQualityEvaluator()
        
        now = datetime.now()
        
        entity_recent = Entity(
            type=EntityType.PREFERENCE,
            name="最近访问",
            last_accessed=now - timedelta(hours=1),
        )
        
        entity_old = Entity(
            type=EntityType.PREFERENCE,
            name="很久没访问",
            last_accessed=now - timedelta(days=100),
        )
        
        quality_recent = evaluator.evaluate(entity_recent)
        quality_old = evaluator.evaluate(entity_old)
        
        assert quality_recent > quality_old
    
    def test_llm_source_higher_quality(self):
        """LLM-extracted entities should have higher quality than regex."""
        evaluator = MemoryQualityEvaluator()
        
        entity_regex = Entity(
            type=EntityType.FACT,
            name="某个事实",
            source=EntitySource.REGEX,
            confidence=1.0,
        )
        
        entity_llm = Entity(
            type=EntityType.FACT,
            name="某个事实",
            source=EntitySource.LLM,
            confidence=1.0,
        )
        
        quality_regex = evaluator.evaluate(entity_regex)
        quality_llm = evaluator.evaluate(entity_llm)
        
        assert quality_llm > quality_regex
    
    def test_time_decay(self):
        """Older entities should have lower quality due to decay."""
        evaluator = MemoryQualityEvaluator()
        
        now = datetime.now()
        
        entity_new = Entity(
            type=EntityType.PREFERENCE,
            name="新偏好",
            created_at=now - timedelta(days=1),
        )
        
        entity_old = Entity(
            type=EntityType.PREFERENCE,
            name="旧偏好",
            created_at=now - timedelta(days=180),
        )
        
        quality_new = evaluator.evaluate(entity_new)
        quality_old = evaluator.evaluate(entity_old)
        
        assert quality_new > quality_old


# =============================================================================
# Forgetter Tests
# =============================================================================

class TestMemoryForgetter:
    
    def test_never_forget_safety(self):
        """Safety entities should never be forgotten."""
        forgetter = MemoryForgetter()
        
        entity = Entity(
            type=EntityType.ALLERGY,
            name="花生过敏",
            priority=100,
        )
        
        assert not forgetter.should_forget(entity)
    
    def test_forget_low_quality(self):
        """Low quality entities should be forgotten."""
        config = EvolutionConfig(quality_threshold=0.5)
        forgetter = MemoryForgetter(config)
        
        entity = Entity(
            type=EntityType.FACT,
            name="不重要的事实",
            priority=10,
            access_count=0,
            source=EntitySource.REGEX,
            created_at=datetime.now() - timedelta(days=300),
        )
        
        assert forgetter.should_forget(entity)
    
    def test_forget_expired(self):
        """Expired entities should be forgotten."""
        forgetter = MemoryForgetter()
        
        entity = Entity(
            type=EntityType.EVENT,
            name="过期事件",
            valid_until=datetime.now() - timedelta(days=1),
        )
        
        assert forgetter.should_forget(entity)
    
    def test_not_forget_valid_event(self):
        """Valid events should not be forgotten."""
        forgetter = MemoryForgetter()
        
        entity = Entity(
            type=EntityType.EVENT,
            name="近期事件",
            priority=80,
            access_count=5,
            created_at=datetime.now() - timedelta(days=10),
        )
        
        assert not forgetter.should_forget(entity)
    
    def test_find_forgettable(self, sample_entities):
        """Test finding all forgettable entities."""
        forgetter = MemoryForgetter()
        
        forgettable = forgetter.find_forgettable(sample_entities)
        forget_ids = {e.id for e, _ in forgettable}
        
        # Allergy should not be in forgettable
        assert "allergy1" not in forget_ids
        
        # Expired event should be in forgettable
        assert "event1" in forget_ids


# =============================================================================
# Integrator Tests
# =============================================================================

class TestMemoryIntegrator:
    
    def test_merge_similar_entities(self):
        """Similar entities should be merged."""
        integrator = MemoryIntegrator()
        
        entities = [
            Entity(
                id="p1",
                type=EntityType.PREFERENCE,
                name="喜欢川菜",
                content="喜欢吃辣",
                access_count=5,
            ),
            Entity(
                id="p2",
                type=EntityType.PREFERENCE,
                name="喜欢川菜",
                content="喜欢麻辣口味",
                access_count=3,
            ),
        ]
        
        merged = integrator.integrate(entities)
        
        # Should be merged into one
        assert len(merged) == 1
        # Access counts should be combined
        assert merged[0].access_count == 8
    
    def test_not_merge_safety_entities(self):
        """Safety entities should not be merged."""
        integrator = MemoryIntegrator()
        
        entities = [
            Entity(
                id="a1",
                type=EntityType.ALLERGY,
                name="花生过敏",
                content="严重过敏",
            ),
            Entity(
                id="a2",
                type=EntityType.ALLERGY,
                name="花生过敏",
                content="轻度过敏",
            ),
        ]
        
        merged = integrator.integrate(entities)
        
        # Safety entities should not be merged
        assert len(merged) == 2
    
    def test_detect_conflicts(self):
        """Test conflict detection between preferences and dislikes."""
        integrator = MemoryIntegrator()
        
        entities = [
            Entity(
                id="pref",
                type=EntityType.PREFERENCE,
                name="香菜",
                content="喜欢吃香菜",
            ),
            Entity(
                id="dislike",
                type=EntityType.DISLIKE,
                name="香菜",
                content="讨厌香菜",
            ),
        ]
        
        conflicts = integrator.detect_conflicts(entities)
        
        assert len(conflicts) == 1
        assert conflicts[0][2] == "preference_dislike_conflict"


# =============================================================================
# Evolver Tests
# =============================================================================

class TestMemoryEvolver:
    
    @pytest.mark.asyncio
    async def test_evolution_cycle(self, temp_store, sample_entities):
        """Test complete evolution cycle."""
        # Add entities to store
        for entity in sample_entities:
            temp_store.add_entity(entity)
        
        # Create evolver
        evolver = MemoryEvolver(temp_store)
        
        # Run evolution
        report = await evolver.evolve()
        
        # Check report
        assert report.total_entities == 5
        assert report.forgotten_count >= 1  # At least the expired event
        assert "allergy1" in temp_store.entities  # Safety entity preserved
    
    @pytest.mark.asyncio
    async def test_should_evolve_timing(self, temp_store):
        """Test evolution timing."""
        evolver = MemoryEvolver(temp_store)
        
        # Should evolve initially
        assert evolver.should_evolve()
        
        # Run evolution
        await evolver.evolve()
        
        # Should not need evolution immediately after
        assert not evolver.should_evolve()
    
    @pytest.mark.asyncio
    async def test_evolution_report(self, temp_store, sample_entities):
        """Test evolution report generation."""
        for entity in sample_entities:
            temp_store.add_entity(entity)
        
        evolver = MemoryEvolver(temp_store)
        report = await evolver.evolve()
        
        # Check report has expected fields
        assert report.timestamp is not None
        assert report.total_entities > 0
        assert isinstance(report.errors, list)
        
        # Get summary
        summary = report.summary()
        assert "Evolution Report" in summary


# =============================================================================
# Config Tests
# =============================================================================

class TestEvolutionConfig:
    
    def test_default_config(self):
        """Test default configuration values."""
        config = EvolutionConfig()
        
        assert config.quality_threshold == 0.3
        assert config.high_quality_threshold == 0.7
        assert config.event_retention_days == 365
        assert config.preference_half_life_days == 90
        assert EntityType.ALLERGY in config.never_forget_types
    
    def test_custom_config(self):
        """Test custom configuration."""
        config = EvolutionConfig(
            quality_threshold=0.5,
            max_entities=500,
            evolution_interval_hours=12,
        )
        
        assert config.quality_threshold == 0.5
        assert config.max_entities == 500
        assert config.evolution_interval_hours == 12


# =============================================================================
# Run Tests
# =============================================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v"])