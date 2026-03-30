# -*- coding: utf-8 -*-
"""Tests for Memory V3.5 - Dynamic Injection.

This test suite verifies:
1. Entity storage and retrieval
2. Deduplication
3. Keyword search
4. Prompt injection
5. Integration with existing extractors
"""
import asyncio
import tempfile
from datetime import datetime

from copaw.agents.memory.unified.models import (
    Entity, EntityType, EntitySource, EntityPriority, Relation
)
from copaw.agents.memory.unified.store import UnifiedEntityStore
from copaw.agents.memory.unified.retriever import EntityRetriever
from copaw.agents.memory.unified.injector import DynamicInjector
from copaw.agents.memory.unified.integration import MemoryIntegration


def test_entity_create():
    """Test basic entity creation."""
    entity = Entity(
        type=EntityType.ALLERGY,
        name="花生过敏",
        content="用户对花生过敏",
        priority=100,
    )
    
    assert entity.type == EntityType.ALLERGY
    assert entity.name == "花生过敏"
    assert entity.priority == 100
    assert entity.source == EntitySource.REGEX
    print("  ✅ 实体创建测试通过")


def test_entity_to_dict():
    """Test entity serialization."""
    entity = Entity(
        type=EntityType.PREFERENCE,
        name="蓝色杯子",
        content="用户喜欢蓝色的杯子",
        priority=50,
    )
    
    data = entity.to_dict()
    
    assert data["type"] == "preference"
    assert data["name"] == "蓝色杯子"
    assert data["priority"] == 50
    print("  ✅ 实体序列化测试通过")


def test_entity_from_dict():
    """Test entity deserialization."""
    data = {
        "id": "test123",
        "type": "decision",
        "name": "使用Python",
        "content": "决定使用Python做后端",
        "priority": 60,
    }
    
    entity = Entity.from_dict(data)
    
    assert entity.id == "test123"
    assert entity.type == EntityType.DECISION
    assert entity.name == "使用Python"
    print("  ✅ 实体反序列化测试通过")


def test_entity_is_safety():
    """Test safety entity detection."""
    allergy = Entity(type=EntityType.ALLERGY, name="花生", priority=100)
    preference = Entity(type=EntityType.PREFERENCE, name="蓝色", priority=50)
    
    assert allergy.is_safety_related() is True
    assert preference.is_safety_related() is False
    print("  ✅ 安全实体检测测试通过")


def test_store_add_entity():
    """Test adding an entity."""
    with tempfile.TemporaryDirectory() as tmpdir:
        store = UnifiedEntityStore(tmpdir)
        
        entity = Entity(
            type=EntityType.ALLERGY,
            name="花生过敏",
            content="用户对花生过敏",
            priority=100,
        )
        
        entity_id = store.add_entity(entity)
        
        assert entity_id is not None
        assert len(store.entities) == 1
    print("  ✅ 实体添加测试通过")


def test_store_deduplication():
    """Test that duplicate entities are merged."""
    with tempfile.TemporaryDirectory() as tmpdir:
        store = UnifiedEntityStore(tmpdir)
        
        # Add first entity
        entity1 = Entity(
            type=EntityType.ALLERGY,
            name="花生过敏",
            content="用户对花生过敏",
            priority=100,
        )
        id1 = store.add_entity(entity1)
        
        # Add duplicate
        entity2 = Entity(
            type=EntityType.ALLERGY,
            name="花生过敏",
            content="用户对花生过敏",
            priority=100,
        )
        id2 = store.add_entity(entity2)
        
        # Should be same ID (updated, not new)
        assert id1 == id2
        assert len(store.entities) == 1
        
        # Access count should be incremented
        retrieved = store.get_entity(id1)
        assert retrieved.access_count >= 1
    print("  ✅ 实体去重测试通过")


def test_store_get_by_type():
    """Test filtering by entity type."""
    with tempfile.TemporaryDirectory() as tmpdir:
        store = UnifiedEntityStore(tmpdir)
        
        store.add_entity(Entity(type=EntityType.ALLERGY, name="花生", priority=100))
        store.add_entity(Entity(type=EntityType.PREFERENCE, name="蓝色", priority=50))
        store.add_entity(Entity(type=EntityType.ALLERGY, name="海鲜", priority=100))
        
        allergies = store.get_entities_by_type(EntityType.ALLERGY)
        
        assert len(allergies) == 2
    print("  ✅ 按类型过滤测试通过")


def test_store_get_by_priority():
    """Test filtering by priority."""
    with tempfile.TemporaryDirectory() as tmpdir:
        store = UnifiedEntityStore(tmpdir)
        
        store.add_entity(Entity(type=EntityType.ALLERGY, name="花生", priority=100))
        store.add_entity(Entity(type=EntityType.DECISION, name="决策A", priority=80))
        store.add_entity(Entity(type=EntityType.PREFERENCE, name="蓝色", priority=50))
        
        high_priority = store.get_entities_by_priority(min_priority=80)
        
        assert len(high_priority) == 2
    print("  ✅ 按优先级过滤测试通过")


def test_store_search():
    """Test keyword search."""
    with tempfile.TemporaryDirectory() as tmpdir:
        store = UnifiedEntityStore(tmpdir)
        
        store.add_entity(Entity(
            type=EntityType.ALLERGY,
            name="花生过敏",
            content="用户对花生过敏",
            priority=100,
        ))
        store.add_entity(Entity(
            type=EntityType.PREFERENCE,
            name="蓝色杯子",
            content="用户喜欢蓝色的杯子",
            priority=50,
        ))
        
        results = store.search("花生")
        
        assert len(results) == 1
        assert results[0][0].name == "花生过敏"
    print("  ✅ 关键词搜索测试通过")


def test_store_persistence():
    """Test that entities persist across store instances."""
    with tempfile.TemporaryDirectory() as tmpdir:
        # Create store and add entity
        store1 = UnifiedEntityStore(tmpdir)
        entity = Entity(
            type=EntityType.ALLERGY,
            name="花生过敏",
            content="用户对花生过敏",
            priority=100,
        )
        entity_id = store1.add_entity(entity)
        
        # Create new store instance
        store2 = UnifiedEntityStore(tmpdir)
        
        # Entity should be loaded
        assert len(store2.entities) == 1
        retrieved = store2.get_entity(entity_id)
        assert retrieved is not None
        assert retrieved.name == "花生过敏"
    print("  ✅ 持久化测试通过")


def test_retriever_keyword_search():
    """Test keyword-based search."""
    with tempfile.TemporaryDirectory() as tmpdir:
        store = UnifiedEntityStore(tmpdir)
        
        store.add_entity(Entity(
            type=EntityType.ALLERGY,
            name="花生过敏",
            content="用户对花生过敏",
            priority=100,
        ))
        store.add_entity(Entity(
            type=EntityType.PREFERENCE,
            name="蓝色杯子",
            content="用户喜欢蓝色的杯子",
            priority=50,
        ))
        
        retriever = EntityRetriever(store)
        
        results = asyncio.run(retriever.search("花生"))
        
        assert len(results) == 1
        assert results[0][0].name == "花生过敏"
    print("  ✅ 检索器关键词搜索测试通过")


def test_retriever_search_with_type_filter():
    """Test search with entity type filter."""
    with tempfile.TemporaryDirectory() as tmpdir:
        store = UnifiedEntityStore(tmpdir)
        
        store.add_entity(Entity(
            type=EntityType.ALLERGY,
            name="花生",
            content="花生过敏",
            priority=100,
        ))
        store.add_entity(Entity(
            type=EntityType.PREFERENCE,
            name="花生酱",
            content="喜欢花生酱",  # Same keyword, different type
            priority=50,
        ))
        
        retriever = EntityRetriever(store)
        
        results = asyncio.run(retriever.search(
            "花生", 
            entity_types=[EntityType.ALLERGY]
        ))
        
        assert len(results) == 1
        assert results[0][0].type == EntityType.ALLERGY
    print("  ✅ 检索器类型过滤测试通过")


def test_retriever_get_safety_entities():
    """Test getting safety entities."""
    with tempfile.TemporaryDirectory() as tmpdir:
        store = UnifiedEntityStore(tmpdir)
        
        store.add_entity(Entity(type=EntityType.ALLERGY, name="花生", priority=100))
        store.add_entity(Entity(type=EntityType.PREFERENCE, name="蓝色", priority=50))
        
        retriever = EntityRetriever(store)
        
        safety = retriever.get_safety_entities()
        
        assert len(safety) == 1
        assert safety[0].name == "花生"
    print("  ✅ 检索器安全实体获取测试通过")


def test_injector_inject_safety_entities():
    """Test that safety entities are always injected."""
    with tempfile.TemporaryDirectory() as tmpdir:
        store = UnifiedEntityStore(tmpdir)
        
        store.add_entity(Entity(
            type=EntityType.ALLERGY,
            name="花生过敏",
            content="用户对花生过敏",
            priority=100,
        ))
        store.add_entity(Entity(
            type=EntityType.PREFERENCE,
            name="蓝色杯子",
            content="用户喜欢蓝色的杯子",
            priority=50,
        ))
        
        retriever = EntityRetriever(store)
        injector = DynamicInjector(store, retriever)
        
        prompt = "你是一个AI助手。"
        enhanced = asyncio.run(injector.inject_to_prompt(prompt))
        
        assert "花生过敏" in enhanced
        assert "安全相关" in enhanced
    print("  ✅ 注入器安全实体注入测试通过")


def test_injector_inject_query_relevant():
    """Test that query-relevant entities are injected."""
    with tempfile.TemporaryDirectory() as tmpdir:
        store = UnifiedEntityStore(tmpdir)
        
        store.add_entity(Entity(
            type=EntityType.PREFERENCE,
            name="蓝色杯子",
            content="用户喜欢蓝色的杯子",
            priority=50,
        ))
        
        retriever = EntityRetriever(store)
        injector = DynamicInjector(store, retriever)
        
        prompt = "你是一个AI助手。"
        enhanced = asyncio.run(injector.inject_to_prompt(prompt, query="杯子"))
        
        assert "蓝色杯子" in enhanced
    print("  ✅ 注入器查询相关实体注入测试通过")


def test_injector_get_summary():
    """Test entity summary generation."""
    with tempfile.TemporaryDirectory() as tmpdir:
        store = UnifiedEntityStore(tmpdir)
        
        store.add_entity(Entity(type=EntityType.ALLERGY, name="花生", priority=100))
        store.add_entity(Entity(type=EntityType.PREFERENCE, name="蓝色", priority=50))
        
        retriever = EntityRetriever(store)
        injector = DynamicInjector(store, retriever)
        
        summary = injector.get_entity_summary()
        
        assert "2 条记忆" in summary
        assert "allergy" in summary
        assert "preference" in summary
    print("  ✅ 注入器摘要生成测试通过")


def test_integration_init():
    """Test integration initialization."""
    with tempfile.TemporaryDirectory() as tmpdir:
        integration = MemoryIntegration(tmpdir)
        
        assert integration.store is not None
        assert integration.retriever is not None
        assert integration.injector is not None
    print("  ✅ 集成初始化测试通过")


def test_integration_get_stats():
    """Test getting store statistics."""
    with tempfile.TemporaryDirectory() as tmpdir:
        integration = MemoryIntegration(tmpdir)
        
        integration.store.add_entity(Entity(
            type=EntityType.ALLERGY,
            name="花生",
            priority=100,
        ))
        
        stats = integration.get_store_stats()
        
        assert stats["total_entities"] == 1
        assert stats["safety_entities"] == 1
    print("  ✅ 集成统计测试通过")


def test_integration_inject_to_prompt():
    """Test prompt injection through integration."""
    with tempfile.TemporaryDirectory() as tmpdir:
        integration = MemoryIntegration(tmpdir)
        
        integration.store.add_entity(Entity(
            type=EntityType.ALLERGY,
            name="花生过敏",
            content="用户对花生过敏",
            priority=100,
        ))
        
        prompt = "你是一个AI助手。"
        enhanced = asyncio.run(integration.inject_to_prompt(prompt))
        
        assert "花生过敏" in enhanced
    print("  ✅ 集成Prompt注入测试通过")


def main():
    """Run all tests."""
    print("=" * 70)
    print("🧪 V3.5 基础测试")
    print("=" * 70)
    
    tests = [
        ("实体创建", test_entity_create),
        ("实体序列化", test_entity_to_dict),
        ("实体反序列化", test_entity_from_dict),
        ("安全实体检测", test_entity_is_safety),
        ("实体添加", test_store_add_entity),
        ("实体去重", test_store_deduplication),
        ("按类型过滤", test_store_get_by_type),
        ("按优先级过滤", test_store_get_by_priority),
        ("关键词搜索", test_store_search),
        ("持久化", test_store_persistence),
        ("检索器关键词搜索", test_retriever_keyword_search),
        ("检索器类型过滤", test_retriever_search_with_type_filter),
        ("检索器安全实体", test_retriever_get_safety_entities),
        ("注入器安全实体注入", test_injector_inject_safety_entities),
        ("注入器查询相关注入", test_injector_inject_query_relevant),
        ("注入器摘要生成", test_injector_get_summary),
        ("集成初始化", test_integration_init),
        ("集成统计", test_integration_get_stats),
        ("集成Prompt注入", test_integration_inject_to_prompt),
    ]
    
    passed = 0
    failed = 0
    
    print("\n📦 模型测试:")
    for name, test in tests[:4]:
        try:
            test()
            passed += 1
        except Exception as e:
            print(f"  ❌ {name} 失败: {e}")
            failed += 1
    
    print("\n📦 存储测试:")
    for name, test in tests[4:10]:
        try:
            test()
            passed += 1
        except Exception as e:
            print(f"  ❌ {name} 失败: {e}")
            failed += 1
    
    print("\n📦 检索器测试:")
    for name, test in tests[10:13]:
        try:
            test()
            passed += 1
        except Exception as e:
            print(f"  ❌ {name} 失败: {e}")
            failed += 1
    
    print("\n📦 注入器测试:")
    for name, test in tests[13:16]:
        try:
            test()
            passed += 1
        except Exception as e:
            print(f"  ❌ {name} 失败: {e}")
            failed += 1
    
    print("\n📦 集成测试:")
    for name, test in tests[16:]:
        try:
            test()
            passed += 1
        except Exception as e:
            print(f"  ❌ {name} 失败: {e}")
            failed += 1
    
    print("\n" + "=" * 70)
    print("📊 测试结果总结")
    print("=" * 70)
    print(f"\n  总计: {len(tests)} 个测试")
    print(f"  通过: {passed}")
    print(f"  失败: {failed}")
    
    if failed == 0:
        print("\n  🎉 所有测试通过！")
    else:
        print(f"\n  ⚠️ {failed} 个测试失败")
    
    return failed == 0


if __name__ == "__main__":
    import sys
    success = main()
    sys.exit(0 if success else 1)