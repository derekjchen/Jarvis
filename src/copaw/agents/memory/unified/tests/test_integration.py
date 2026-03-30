# -*- coding: utf-8 -*-
"""Integration tests for V3.5 Dynamic Injection.

Tests the complete flow:
1. KeyInfo extraction from messages
2. Storage in UnifiedEntityStore
3. Injection into system prompt
"""
import asyncio
import tempfile
from pathlib import Path
from datetime import datetime

import sys
sys.path.insert(0, '/app/working/src')

from copaw.agents.memory.unified.models import Entity, EntityType, EntityPriority
from copaw.agents.memory.unified.store import UnifiedEntityStore
from copaw.agents.memory.unified.retriever import EntityRetriever
from copaw.agents.memory.unified.injector import DynamicInjector
from copaw.agents.memory.unified.integration import MemoryIntegration


def test_entity_store_integration():
    """Test UnifiedEntityStore basic operations."""
    print("\n" + "=" * 60)
    print("Test 1: Entity Store Integration")
    print("=" * 60)
    
    with tempfile.TemporaryDirectory() as tmpdir:
        store = UnifiedEntityStore(tmpdir)
        
        # Add entities
        entity1 = store.add_entity(Entity(
            type=EntityType.ALLERGY,
            name="花生过敏",
            content="用户对花生过敏",
            priority=EntityPriority.CRITICAL.value,
        ))
        
        entity2 = store.add_entity(Entity(
            type=EntityType.PREFERENCE,
            name="蓝色杯子",
            content="用户喜欢蓝色的杯子",
            priority=EntityPriority.MEDIUM.value,
        ))
        
        entity3 = store.add_entity(Entity(
            type=EntityType.DECISION,
            name="Python后端",
            content="决定使用Python做后端开发",
            priority=EntityPriority.HIGH.value,
        ))
        
        # Verify storage
        assert len(store.entities) == 3, f"Expected 3 entities, got {len(store.entities)}"
        print(f"  ✅ Stored 3 entities")
        
        # Verify retrieval
        allergies = store.get_entities_by_type(EntityType.ALLERGY)
        assert len(allergies) == 1
        assert allergies[0].name == "花生过敏"
        print(f"  ✅ Retrieved allergy: {allergies[0].name}")
        
        # Verify search
        results = store.search("花生")
        assert len(results) == 1
        print(f"  ✅ Search works: found '{results[0][0].name}'")
        
        # Verify persistence (create new store)
        store2 = UnifiedEntityStore(tmpdir)
        assert len(store2.entities) == 3
        print(f"  ✅ Persistence works: {len(store2.entities)} entities")


def test_key_info_to_entity():
    """Test KeyInfo to Entity conversion."""
    print("\n" + "=" * 60)
    print("Test 2: KeyInfo to Entity Conversion")
    print("=" * 60)
    
    with tempfile.TemporaryDirectory() as tmpdir:
        integration = MemoryIntegration(tmpdir)
        
        # Create mock KeyInfo objects
        from copaw.agents.hooks.key_info_extractor import KeyInfo, KeyInfoPriority
        
        key_infos = [
            KeyInfo(
                info_type="safety",
                content="花生过敏",
                priority=KeyInfoPriority.SAFETY,
            ),
            KeyInfo(
                info_type="preference",
                content="蓝色的杯子",
                priority=KeyInfoPriority.PREFERENCE,
            ),
            KeyInfo(
                info_type="decision",
                content="明天去上海",
                priority=KeyInfoPriority.DECISION,
            ),
        ]
        
        # Add to store
        entity_ids = integration.add_key_infos(key_infos)
        assert len(entity_ids) == 3
        print(f"  ✅ Added {len(entity_ids)} entities from KeyInfo")
        
        # Verify types
        entities = list(integration.store.entities.values())
        types = {e.type for e in entities}
        assert EntityType.ALLERGY in types or EntityType.CONSTRAINT in types
        assert EntityType.PREFERENCE in types or EntityType.DECISION in types
        print(f"  ✅ Entity types: {[e.type.value for e in entities]}")


def test_injection_integration():
    """Test complete injection flow."""
    print("\n" + "=" * 60)
    print("Test 3: Injection Integration")
    print("=" * 60)
    
    with tempfile.TemporaryDirectory() as tmpdir:
        integration = MemoryIntegration(tmpdir)
        
        # Add entities
        integration.store.add_entity(Entity(
            type=EntityType.ALLERGY,
            name="花生过敏",
            content="用户对花生过敏",
            priority=EntityPriority.CRITICAL.value,
        ))
        
        integration.store.add_entity(Entity(
            type=EntityType.PREFERENCE,
            name="蓝色杯子",
            content="用户喜欢蓝色的杯子",
            priority=EntityPriority.MEDIUM.value,
        ))
        
        integration.store.add_entity(Entity(
            type=EntityType.DECISION,
            name="Python后端",
            content="决定使用Python做后端开发",
            priority=EntityPriority.HIGH.value,
        ))
        
        # Test injection
        base_prompt = "你是一个AI助手。"
        enhanced = integration.inject_to_prompt_sync(base_prompt)
        
        assert "花生过敏" in enhanced, f"Expected '花生过敏' in enhanced prompt"
        assert "安全相关" in enhanced, f"Expected '安全相关' in enhanced prompt"
        print(f"  ✅ Injection works")
        print(f"\n  Enhanced prompt preview:")
        for line in enhanced.split('\n')[:12]:
            print(f"    {line}")


def test_full_flow():
    """Test the full V3.5 flow: extract -> store -> inject."""
    print("\n" + "=" * 60)
    print("Test 4: Full V3.5 Flow")
    print("=" * 60)
    
    with tempfile.TemporaryDirectory() as tmpdir:
        integration = MemoryIntegration(tmpdir)
        
        # Simulate user messages
        messages_text = """
        我对花生过敏，请注意。
        我喜欢蓝色的杯子。
        我决定使用Python做后端开发。
        """
        
        # Extract and store
        from copaw.agents.hooks.key_info_extractor import KeyInfoExtractor
        extractor = KeyInfoExtractor()
        
        # Create mock message objects
        class MockMsg:
            def __init__(self, content):
                self.content = content
                self.role = "user"
                self.id = f"msg_{id(self)}"
        
        messages = [MockMsg(messages_text)]
        key_infos = extractor.extract(messages)
        
        print(f"  Extracted {len(key_infos)} key info items:")
        for info in key_infos:
            print(f"    - [{info.info_type}] {info.content} (priority: {info.priority})")
        
        # Store in UnifiedEntityStore
        if key_infos:
            entity_ids = integration.add_key_infos(key_infos)
            print(f"\n  ✅ Stored {len(entity_ids)} entities")
        
        # Verify storage
        stats = integration.get_store_stats()
        print(f"  Store stats: {stats}")
        
        # Inject into prompt
        base_prompt = "你是一个AI助手。"
        enhanced = integration.inject_to_prompt_sync(base_prompt)
        
        print(f"\n  Enhanced prompt preview:")
        for line in enhanced.split('\n')[:15]:
            print(f"    {line}")
        
        # Verify injection
        assert "花生" in enhanced or "过敏" in enhanced, "Expected allergy info in enhanced prompt"
        print(f"\n  ✅ Full flow works!")


def test_cross_session_persistence():
    """Test that entities persist across sessions."""
    print("\n" + "=" * 60)
    print("Test 5: Cross-Session Persistence")
    print("=" * 60)
    
    with tempfile.TemporaryDirectory() as tmpdir:
        # Session 1: Add entity
        integration1 = MemoryIntegration(tmpdir)
        integration1.store.add_entity(Entity(
            type=EntityType.ALLERGY,
            name="海鲜过敏",
            content="用户对海鲜过敏",
            priority=EntityPriority.CRITICAL.value,
        ))
        
        stats1 = integration1.get_store_stats()
        print(f"  Session 1: {stats1['total_entities']} entities")
        
        # Session 2: Load entity
        integration2 = MemoryIntegration(tmpdir)
        stats2 = integration2.get_store_stats()
        print(f"  Session 2: {stats2['total_entities']} entities")
        
        assert stats2['total_entities'] == 1, "Expected 1 entity to persist"
        
        # Verify injection in new session
        enhanced = integration2.inject_to_prompt_sync("你是一个AI助手。")
        assert "海鲜过敏" in enhanced or "海鲜" in enhanced
        print(f"  ✅ Entity persisted and injected across sessions")


def main():
    """Run all integration tests."""
    print("\n" + "=" * 60)
    print("V3.5 Integration Tests")
    print("=" * 60)
    
    test_entity_store_integration()
    test_key_info_to_entity()
    test_injection_integration()
    test_full_flow()
    test_cross_session_persistence()
    
    print("\n" + "=" * 60)
    print("All V3.5 integration tests passed! ✅")
    print("=" * 60)


if __name__ == "__main__":
    main()