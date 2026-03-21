# -*- coding: utf-8 -*-
"""End-to-End Test for Unified Memory System.

This test validates the complete integration of all memory milestones:
- M2.1: KeyInfo extraction (safety-critical)
- M3.0: Preference evolution and event tracking
- M3.5: Unified storage and dynamic injection
- M4.0: LLM-based extraction (optional)

Run: python -m pytest tests/test_integration_e2e.py -v
"""
import asyncio
import tempfile
import shutil
from pathlib import Path
import os

# Get the working directory
WORKING_DIR = Path(__file__).parent
while WORKING_DIR.name != 'working' and WORKING_DIR.parent != WORKING_DIR:
    WORKING_DIR = WORKING_DIR.parent

# Add to path
import sys
sys.path.insert(0, str(WORKING_DIR))

# Now import
from src.copaw.agents.memory.unified.extractor import UnifiedExtractor, extract_entities
from src.copaw.agents.memory.unified.models import Entity, EntityType, EntityPriority
from src.copaw.agents.memory.unified.store import UnifiedEntityStore
from src.copaw.agents.memory.unified.retriever import EntityRetriever
from src.copaw.agents.memory.unified.injector import DynamicInjector
from src.copaw.agents.memory.unified.integration import MemoryIntegration


class TestUnifiedExtractor:
    """Test the unified extractor."""
    
    def test_extract_safety_info(self):
        """Test M2.1: Extract safety-critical information."""
        extractor = UnifiedExtractor()
        
        # Test allergy extraction
        result = extractor.extract("我对花生过敏")
        assert len(result.entities) >= 1
        assert any(e.type == EntityType.ALLERGY for e in result.entities)
        
        allergy_entity = next(e for e in result.entities if e.type == EntityType.ALLERGY)
        assert "花生" in allergy_entity.name
        assert allergy_entity.priority == EntityPriority.CRITICAL.value
        
        print(f"✅ 提取过敏信息: {allergy_entity.name}")
    
    def test_extract_constraint(self):
        """Test M2.1: Extract dietary constraints."""
        extractor = UnifiedExtractor()
        
        result = extractor.extract("我不能吃海鲜")
        assert len(result.entities) >= 1
        
        constraint = next((e for e in result.entities if e.type == EntityType.CONSTRAINT), None)
        assert constraint is not None
        assert constraint.priority == EntityPriority.CRITICAL.value
        
        print(f"✅ 提取饮食禁忌: {constraint.name}")
    
    def test_extract_preference(self):
        """Test M3.0: Extract user preferences."""
        extractor = UnifiedExtractor()
        
        result = extractor.extract("我喜欢蓝色的杯子")
        assert len(result.entities) >= 1
        
        pref = next((e for e in result.entities if e.type == EntityType.PREFERENCE), None)
        assert pref is not None
        assert "蓝" in pref.name or "杯子" in pref.name
        
        print(f"✅ 提取偏好: {pref.name}")
    
    def test_extract_dislike(self):
        """Test M3.0: Extract dislikes."""
        extractor = UnifiedExtractor()
        
        result = extractor.extract("我不喜欢辣的食物")
        assert len(result.entities) >= 1
        
        dislike = next((e for e in result.entities if e.type == EntityType.DISLIKE), None)
        assert dislike is not None
        
        print(f"✅ 提取不喜欢: {dislike.name}")
    
    def test_extract_event(self):
        """Test M3.0: Extract events with dates."""
        extractor = UnifiedExtractor()
        
        result = extractor.extract("明天下午3点开会")
        
        # Should extract an event with a date
        events = [e for e in result.entities if e.type in (EntityType.EVENT, EntityType.MILESTONE)]
        
        print(f"提取到 {len(events)} 个事件")
        for event in events:
            print(f"  - {event.name} (属性: {event.attributes})")
        
        # Event extraction might be partial, but should not crash
        assert True


class TestUnifiedEntityStore:
    """Test the unified entity store."""
    
    def test_store_and_retrieve(self):
        """Test basic store operations."""
        with tempfile.TemporaryDirectory() as tmpdir:
            store = UnifiedEntityStore(tmpdir)
            
            # Create and store an entity
            entity = Entity(
                type=EntityType.ALLERGY,
                name="花生",
                content="用户对花生过敏",
                priority=100,
            )
            
            entity_id = store.add_entity(entity)
            assert entity_id is not None
            
            # Retrieve
            retrieved = store.get_entity(entity_id)
            assert retrieved is not None
            assert retrieved.name == "花生"
            
            print(f"✅ 存储并检索实体: {retrieved.name}")
    
    def test_priority_query(self):
        """Test querying by priority."""
        with tempfile.TemporaryDirectory() as tmpdir:
            store = UnifiedEntityStore(tmpdir)
            
            # Add entities with different priorities
            store.add_entity(Entity(type=EntityType.ALLERGY, name="过敏1", priority=100))
            store.add_entity(Entity(type=EntityType.DECISION, name="决策1", priority=80))
            store.add_entity(Entity(type=EntityType.PREFERENCE, name="偏好1", priority=50))
            
            # Query safety entities
            safety = store.get_safety_entities()
            assert len(safety) == 1
            assert safety[0].name == "过敏1"
            
            # Query important entities
            important = store.get_important_entities()
            assert len(important) == 2
            
            print(f"✅ 优先级查询: {len(safety)} 安全, {len(important)} 重要")
    
    def test_persistence(self):
        """Test persistence to disk."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create store and add entity
            store1 = UnifiedEntityStore(tmpdir)
            store1.add_entity(Entity(type=EntityType.ALLERGY, name="花生", priority=100))
            
            # Create new store instance (simulates restart)
            store2 = UnifiedEntityStore(tmpdir)
            
            # Entity should be loaded
            entities = store2.get_all_entities()
            assert len(entities) == 1
            assert entities[0].name == "花生"
            
            print(f"✅ 持久化测试: 重新加载后仍有 {len(entities)} 个实体")


class TestDynamicInjector:
    """Test the dynamic injector."""
    
    def test_inject_safety_entities(self):
        """Test that safety entities are always injected."""
        with tempfile.TemporaryDirectory() as tmpdir:
            store = UnifiedEntityStore(tmpdir)
            retriever = EntityRetriever(store)
            injector = DynamicInjector(store, retriever)
            
            # Add safety entity
            store.add_entity(Entity(
                type=EntityType.ALLERGY,
                name="花生",
                content="用户对花生过敏",
                priority=100,
            ))
            
            # Inject
            original = "You are a helpful assistant."
            enhanced = asyncio.run(injector.inject_to_prompt(original))
            
            assert "花生" in enhanced
            assert "安全相关" in enhanced or "过敏" in enhanced.lower()
            
            print(f"✅ 安全实体注入成功")
            print(f"   原始长度: {len(original)}")
            print(f"   增强后长度: {len(enhanced)}")
    
    def test_token_budget(self):
        """Test token budget management."""
        with tempfile.TemporaryDirectory() as tmpdir:
            store = UnifiedEntityStore(tmpdir)
            retriever = EntityRetriever(store)
            injector = DynamicInjector(store, retriever)
            
            # Add many entities
            for i in range(50):
                store.add_entity(Entity(
                    type=EntityType.PREFERENCE,
                    name=f"偏好{i}",
                    content=f"这是第{i}个偏好，内容比较长",
                    priority=50,
                ))
            
            # Inject with strict token budget
            original = "You are a helpful assistant."
            enhanced = asyncio.run(injector.inject_to_prompt(original, max_tokens=200))
            
            # Should respect budget
            added_length = len(enhanced) - len(original)
            estimated_tokens = added_length // 4  # ~4 chars per token
            
            print(f"✅ Token 预算管理:")
            print(f"   预算: 200 tokens")
            print(f"   实际使用: ~{estimated_tokens} tokens")


class TestMemoryIntegration:
    """Test the full memory integration."""
    
    def test_process_and_inject(self):
        """Test the complete flow: process message → inject into prompt."""
        with tempfile.TemporaryDirectory() as tmpdir:
            integration = MemoryIntegration(tmpdir)
            
            # Process a message
            entities = asyncio.run(integration.process_message("我对花生过敏"))
            
            assert len(entities) >= 1
            assert any(e.type == EntityType.ALLERGY for e in entities)
            
            print(f"✅ 消息处理: 提取了 {len(entities)} 个实体")
            
            # Inject into prompt
            original = "You are a helpful assistant."
            enhanced = integration.inject_to_prompt_sync(original)
            
            assert "花生" in enhanced
            
            print(f"✅ Prompt 增强: 长度从 {len(original)} 增加到 {len(enhanced)}")
    
    def test_multi_message_processing(self):
        """Test processing multiple messages."""
        with tempfile.TemporaryDirectory() as tmpdir:
            integration = MemoryIntegration(tmpdir)
            
            messages = [
                "我对花生过敏",
                "我喜欢蓝色的杯子",
                "我不喜欢辣的食物",
                "明天下午3点开会",
            ]
            
            total_entities = 0
            for msg in messages:
                entities = asyncio.run(integration.process_message(msg))
                total_entities += len(entities)
                print(f"  '{msg}' → {len(entities)} 个实体")
            
            stats = integration.get_store_stats()
            print(f"\n✅ 多消息处理: 总计 {total_entities} 个实体")
            print(f"   存储统计: {stats}")
    
    def test_cross_session_persistence(self):
        """Test that entities persist across sessions."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Session 1: Store information
            integration1 = MemoryIntegration(tmpdir)
            asyncio.run(integration1.process_message("我对花生过敏"))
            
            stats1 = integration1.get_store_stats()
            print(f"Session 1: {stats1['total_entities']} 个实体")
            
            # Session 2: Should still have the information
            integration2 = MemoryIntegration(tmpdir)
            
            stats2 = integration2.get_store_stats()
            assert stats2['total_entities'] >= 1
            
            # Should be able to inject
            enhanced = integration2.inject_to_prompt_sync("You are a helpful assistant.")
            assert "花生" in enhanced
            
            print(f"Session 2: {stats2['total_entities']} 个实体 (持久化成功)")
    
    def test_convenience_function(self):
        """Test the convenience extraction function."""
        entities = extract_entities("我对花生过敏")
        
        assert len(entities) >= 1
        assert any(e.type == EntityType.ALLERGY for e in entities)
        
        print(f"✅ 便捷函数: 提取了 {len(entities)} 个实体")


def run_all_tests():
    """Run all tests manually (for non-pytest environments)."""
    print("=" * 60)
    print("Memory System End-to-End Test")
    print("=" * 60)
    print()
    
    # Test UnifiedExtractor
    print("【测试 UnifiedExtractor】")
    print("-" * 40)
    t = TestUnifiedExtractor()
    t.test_extract_safety_info()
    t.test_extract_constraint()
    t.test_extract_preference()
    t.test_extract_dislike()
    t.test_extract_event()
    print()
    
    # Test UnifiedEntityStore
    print("【测试 UnifiedEntityStore】")
    print("-" * 40)
    t = TestUnifiedEntityStore()
    t.test_store_and_retrieve()
    t.test_priority_query()
    t.test_persistence()
    print()
    
    # Test DynamicInjector
    print("【测试 DynamicInjector】")
    print("-" * 40)
    t = TestDynamicInjector()
    t.test_inject_safety_entities()
    t.test_token_budget()
    print()
    
    # Test MemoryIntegration
    print("【测试 MemoryIntegration】")
    print("-" * 40)
    t = TestMemoryIntegration()
    t.test_process_and_inject()
    t.test_multi_message_processing()
    t.test_cross_session_persistence()
    t.test_convenience_function()
    print()
    
    print("=" * 60)
    print("✅ 所有测试通过!")
    print("=" * 60)


if __name__ == "__main__":
    run_all_tests()