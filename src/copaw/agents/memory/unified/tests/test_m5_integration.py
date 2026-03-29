# -*- coding: utf-8 -*-
"""Test M5.0 Integration in MemoryIntegration.

This test verifies that M5.0 MemoryEvolver is properly integrated
into the MemoryIntegration class.
"""
import asyncio
import tempfile
import shutil
from pathlib import Path
import pytest

from ..models import Entity, EntityType, EntitySource
from ..integration import MemoryIntegration
from ..evolution import EvolutionConfig, EvolutionReport


class TestM5Integration:
    """Test M5.0 integration in MemoryIntegration."""
    
    def setup_method(self):
        """Setup test environment."""
        self.test_dir = tempfile.mkdtemp()
        self.integration = MemoryIntegration(
            self.test_dir,
            enable_llm=False,
            enable_evolution=True
        )
    
    def teardown_method(self):
        """Cleanup test environment."""
        shutil.rmtree(self.test_dir, ignore_errors=True)
    
    def test_evolver_initialized(self):
        """Test that MemoryEvolver is initialized."""
        assert self.integration.evolver is not None
        assert self.integration.enable_evolution is True
    
    def test_evolver_disabled(self):
        """Test that evolution can be disabled."""
        integration = MemoryIntegration(
            self.test_dir,
            enable_evolution=False
        )
        assert integration.evolver is None
        assert integration.enable_evolution is False
    
    def test_evolve_sync_empty_store(self):
        """Test evolve on empty store."""
        report = self.integration.evolve_sync(force=True)
        
        assert report is not None
        assert isinstance(report, EvolutionReport)
        assert report.total_entities == 0
        assert report.forgotten_count == 0
    
    def test_evolve_sync_with_entities(self):
        """Test evolve with some entities."""
        # Add some entities
        entities = [
            Entity(
                type=EntityType.ALLERGY,
                name="花生过敏",
                content="用户对花生过敏",
                priority=100,
                source=EntitySource.REGEX,
            ),
            Entity(
                type=EntityType.PREFERENCE,
                name="喜欢Python",
                content="用户喜欢使用Python编程",
                priority=50,
                source=EntitySource.REGEX,
            ),
            Entity(
                type=EntityType.FACT,
                name="临时事实",
                content="这是一条临时事实",
                priority=20,
                source=EntitySource.REGEX,
            ),
        ]
        
        for entity in entities:
            self.integration.store.add_entity(entity)
        
        # Run evolution
        report = self.integration.evolve_sync(force=True)
        
        assert report is not None
        assert report.total_entities == 3
        # Safety entity should never be forgotten
        assert report.forgotten_count == 0  # low quality fact might be forgotten
    
    def test_safety_entities_protected(self):
        """Test that safety entities are never forgotten."""
        # Add a safety entity
        safety_entity = Entity(
            type=EntityType.ALLERGY,
            name="海鲜过敏",
            content="用户对海鲜严重过敏",
            priority=100,
            source=EntitySource.REGEX,
        )
        self.integration.store.add_entity(safety_entity)
        
        # Run multiple evolutions
        for _ in range(5):
            self.integration.evolve_sync(force=True)
        
        # Safety entity should still exist
        entities = self.integration.store.get_all_entities()
        assert len(entities) == 1
        assert entities[0].type == EntityType.ALLERGY
    
    def test_should_evolve(self):
        """Test should_evolve method."""
        # First time should always be True
        assert self.integration.should_evolve() is True
        
        # Run evolution
        self.integration.evolve_sync(force=True)
        
        # After evolution, should be False (interval not reached)
        assert self.integration.should_evolve() is False
    
    def test_get_evolution_summary(self):
        """Test get_evolution_summary method."""
        summary = self.integration.get_evolution_summary()
        
        assert summary["enabled"] is True
        assert "last_evolution" in summary
        assert "config" in summary
    
    def test_get_quality_summary(self):
        """Test get_quality_summary method."""
        # Add some entities
        entities = [
            Entity(type=EntityType.ALLERGY, name="过敏", content="过敏", priority=100, source=EntitySource.REGEX),
            Entity(type=EntityType.DECISION, name="决策", content="决策", priority=80, source=EntitySource.REGEX),
            Entity(type=EntityType.FACT, name="事实", content="事实", priority=20, source=EntitySource.REGEX),
        ]
        
        for entity in entities:
            self.integration.store.add_entity(entity)
        
        summary = self.integration.get_quality_summary()
        
        assert summary["total"] == 3
        assert summary["high_quality"] >= 1  # Safety entity
        assert summary["average_score"] > 0
    
    def test_evaluate_entity_quality(self):
        """Test evaluate_entity_quality method."""
        # Safety entity should have max quality
        safety_entity = Entity(
            type=EntityType.ALLERGY,
            name="过敏",
            content="严重过敏",
            priority=100,
            source=EntitySource.REGEX,
        )
        
        quality = self.integration.evaluate_entity_quality(safety_entity)
        assert quality == 1.0  # Safety entities always get max score
    
    def test_evolution_with_custom_config(self):
        """Test evolution with custom EvolutionConfig."""
        config = EvolutionConfig(
            quality_threshold=0.5,  # Higher threshold
            evolution_interval_hours=1,
        )
        
        integration = MemoryIntegration(
            self.test_dir,
            enable_evolution=True,
            evolution_config=config
        )
        
        assert integration.evolver is not None
        assert integration.evolver.config.quality_threshold == 0.5
    
    @pytest.mark.asyncio
    async def test_evolve_async(self):
        """Test async evolve method."""
        # Add an entity
        entity = Entity(
            type=EntityType.PREFERENCE,
            name="测试偏好",
            content="测试偏好内容",
            priority=50,
            source=EntitySource.REGEX,
        )
        self.integration.store.add_entity(entity)
        
        # Run async evolution
        report = await self.integration.evolve(force=True)
        
        assert report is not None
        assert report.total_entities == 1
    
    def test_evolution_disabled_returns_none(self):
        """Test that evolve returns None when evolution is disabled."""
        integration = MemoryIntegration(
            self.test_dir,
            enable_evolution=False
        )
        
        report = integration.evolve_sync(force=True)
        assert report is None
        
        should = integration.should_evolve()
        assert should is False
        
        summary = integration.get_evolution_summary()
        assert summary["enabled"] is False
    
    def test_full_integration_flow(self):
        """Test full integration flow: process -> store -> inject -> evolve."""
        # 1. Process message (extract)
        message = "我对花生过敏，喜欢吃Python编程"
        
        entities = asyncio.run(self.integration.process_message(message))
        
        # Should have extracted allergy and preference
        assert len(entities) >= 1
        
        # 2. Check store stats
        stats = self.integration.get_store_stats()
        assert stats["total_entities"] >= 1
        
        # 3. Inject to prompt
        prompt = "You are a helpful assistant."
        enhanced = self.integration.inject_to_prompt_sync(prompt)
        
        # Should contain entity context
        assert len(enhanced) > len(prompt)
        
        # 4. Run evolution
        report = self.integration.evolve_sync(force=True)
        
        assert report is not None
        # Safety entities should be preserved
        assert report.forgotten_count == 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])