# -*- coding: utf-8 -*-
"""Large scenario integration test for V3.5 Dynamic Injection.

This test simulates a real conversation scenario:
1. Multiple sessions with different conversations
2. Memory compaction triggered multiple times
3. Entity extraction and persistence
4. Cross-session entity retrieval
5. System prompt injection
"""
import asyncio
import tempfile
import time
from datetime import datetime
from pathlib import Path

import sys
sys.path.insert(0, '/app/working/src')

from copaw.agents.memory.unified.models import Entity, EntityType, EntityPriority
from copaw.agents.memory.unified.integration import MemoryIntegration, get_memory_integration, reset_memory_integration
from copaw.agents.hooks.key_info_extractor import KeyInfoExtractor, KeyInfoPriority


class MockMsg:
    """Mock message for testing."""
    def __init__(self, content: str, role: str = "user", msg_id: str = ""):
        self.content = content
        self.role = role
        self.id = msg_id or f"msg_{id(self)}"


def generate_large_conversation(num_messages: int = 100) -> list[MockMsg]:
    """Generate a large conversation with key info scattered throughout."""
    messages = []
    
    # Intro messages
    messages.append(MockMsg("你好，我是新用户。", "user"))
    messages.append(MockMsg("你好！很高兴认识你。有什么我可以帮助你的吗？", "assistant"))
    
    # Key info at different positions
    key_info_messages = [
        "我对花生过敏，请注意这点。",
        "我喜欢蓝色的杯子和笔记本。",
        "我决定下周三去上海出差。",
        "我的电话是13812345678。",
        "我有糖尿病，需要注意饮食。",
        "我不能吃海鲜，会过敏。",
        "我偏爱简洁的设计风格。",
        "我决定使用Python做后端开发。",
        "我喜欢喝咖啡，特别是美式。",
        "我决定把项目命名为'星云计划'。",
    ]
    
    # Interleave key info with regular messages
    for i in range(num_messages - 20):
        # Regular conversation
        messages.append(MockMsg(f"这是一段普通的对话内容 {i}。", "user"))
        messages.append(MockMsg(f"我理解你的意思，让我来帮你处理。", "assistant"))
        
        # Insert key info at specific positions
        if i < len(key_info_messages):
            messages.append(MockMsg(key_info_messages[i], "user"))
            messages.append(MockMsg(f"好的，我记住了。", "assistant"))
    
    return messages


def test_large_conversation_compaction():
    """Test V3.5 with large conversation and multiple compactions."""
    print("\n" + "=" * 70)
    print("Large Scenario Test: Multiple Sessions with Compaction")
    print("=" * 70)
    
    with tempfile.TemporaryDirectory() as tmpdir:
        # Reset global integration
        reset_memory_integration()
        
        # Initialize integration
        integration = MemoryIntegration(tmpdir)
        extractor = KeyInfoExtractor()
        
        # Generate large conversation
        print("\n[Phase 1] Generating large conversation...")
        messages = generate_large_conversation(200)
        print(f"  Generated {len(messages)} messages")
        
        # Simulate multiple compaction cycles
        print("\n[Phase 2] Simulating compaction cycles...")
        
        all_key_infos = []
        cycle_size = 50  # Messages per compaction cycle
        
        for cycle in range(4):
            start_idx = cycle * cycle_size
            end_idx = min((cycle + 1) * cycle_size, len(messages))
            batch = messages[start_idx:end_idx]
            
            # Extract key info
            key_infos = extractor.extract(batch)
            
            if key_infos:
                # Store in UnifiedEntityStore
                entity_ids = integration.add_key_infos(key_infos, session_id=f"session_{cycle}")
                all_key_infos.extend(key_infos)
                print(f"  Cycle {cycle + 1}: Extracted {len(key_infos)} key info, stored {len(entity_ids)} entities")
            else:
                print(f"  Cycle {cycle + 1}: No key info extracted")
        
        # Check final state
        stats = integration.get_store_stats()
        print(f"\n[Phase 3] Final Statistics:")
        print(f"  Total entities: {stats['total_entities']}")
        print(f"  By type: {stats['by_type']}")
        print(f"  Safety entities: {stats['safety_entities']}")
        
        # Test injection
        print(f"\n[Phase 4] Testing prompt injection...")
        base_prompt = "你是一个AI助手。"
        enhanced = integration.inject_to_prompt_sync(base_prompt)
        
        # Verify safety entities are injected
        safety_entities = integration.store.get_safety_entities()
        print(f"  Safety entities found: {len(safety_entities)}")
        
        for entity in safety_entities:
            assert entity.name in enhanced or entity.content in enhanced, \
                f"Safety entity '{entity.name}' not in enhanced prompt"
        print(f"  ✅ All safety entities injected")
        
        # Print enhanced prompt preview
        print(f"\n  Enhanced prompt preview:")
        for line in enhanced.split('\n')[:15]:
            print(f"    {line}")
        
        return stats


def test_cross_session_retrieval():
    """Test entity retrieval across multiple sessions."""
    print("\n" + "=" * 70)
    print("Large Scenario Test: Cross-Session Retrieval")
    print("=" * 70)
    
    with tempfile.TemporaryDirectory() as tmpdir:
        reset_memory_integration()
        
        # Session 1: User mentions allergy
        print("\n[Session 1] User mentions peanut allergy...")
        integration1 = MemoryIntegration(tmpdir)
        
        session1_msgs = [MockMsg("我对花生过敏。")]
        extractor = KeyInfoExtractor()
        key_infos = extractor.extract(session1_msgs)
        integration1.add_key_infos(key_infos, session_id="session_1")
        
        stats1 = integration1.get_store_stats()
        print(f"  Stored {stats1['total_entities']} entities")
        
        # Session 2: User mentions preference (new session)
        print("\n[Session 2] User mentions preference (new session)...")
        integration2 = MemoryIntegration(tmpdir)  # Load from disk
        
        stats2 = integration2.get_store_stats()
        print(f"  Loaded {stats2['total_entities']} entities from previous session")
        
        session2_msgs = [MockMsg("我喜欢蓝色的杯子。")]
        key_infos2 = extractor.extract(session2_msgs)
        integration2.add_key_infos(key_infos2, session_id="session_2")
        
        stats2_after = integration2.get_store_stats()
        print(f"  Now have {stats2_after['total_entities']} entities")
        
        # Session 3: User asks for recommendation (verify all entities available)
        print("\n[Session 3] User asks for recommendation...")
        integration3 = MemoryIntegration(tmpdir)
        
        stats3 = integration3.get_store_stats()
        print(f"  Loaded {stats3['total_entities']} entities from all sessions")
        
        # Verify both allergy and preference are available
        enhanced = integration3.inject_to_prompt_sync("你是一个AI助手。")
        
        has_allergy = "花生" in enhanced or "过敏" in enhanced
        has_preference = "蓝色" in enhanced or "杯子" in enhanced
        
        print(f"  Allergy info in prompt: {has_allergy}")
        print(f"  Preference info in prompt: {has_preference}")
        
        assert has_allergy, "Allergy info not in prompt!"
        assert has_preference, "Preference info not in prompt!"
        
        print(f"\n  ✅ Cross-session retrieval works!")


def test_conflict_resolution():
    """Test handling of conflicting/updated information."""
    print("\n" + "=" * 70)
    print("Large Scenario Test: Conflict Resolution")
    print("=" * 70)
    
    with tempfile.TemporaryDirectory() as tmpdir:
        reset_memory_integration()
        integration = MemoryIntegration(tmpdir)
        extractor = KeyInfoExtractor()
        
        # Day 1: User likes blue
        print("\n[Day 1] User likes blue cups...")
        msgs1 = [MockMsg("我喜欢蓝色的杯子。")]
        key_infos1 = extractor.extract(msgs1)
        integration.add_key_infos(key_infos1, session_id="day1")
        
        entities = list(integration.store.entities.values())
        print(f"  Stored: {entities[0].name if entities else 'none'}")
        
        # Day 2: User changes preference
        print("\n[Day 2] User preference changed...")
        msgs2 = [MockMsg("我现在喜欢红色的杯子了。")]
        key_infos2 = extractor.extract(msgs2)
        integration.add_key_infos(key_infos2, session_id="day2")
        
        entities_after = list(integration.store.entities.values())
        print(f"  Total entities: {len(entities_after)}")
        
        # Check deduplication
        cup_prefs = [e for e in entities_after if "杯子" in e.name or "杯子" in e.content]
        print(f"  Cup-related entities: {len(cup_prefs)}")
        for e in cup_prefs:
            print(f"    - {e.name}: {e.content}")
        
        # Both should be stored (history preserved)
        stats = integration.get_store_stats()
        print(f"\n  Final stats: {stats['by_type']}")


def test_priority_based_injection():
    """Test that high priority entities are always injected."""
    print("\n" + "=" * 70)
    print("Large Scenario Test: Priority-Based Injection")
    print("=" * 70)
    
    with tempfile.TemporaryDirectory() as tmpdir:
        reset_memory_integration()
        integration = MemoryIntegration(tmpdir)
        
        # Add entities with different priorities
        entities_to_add = [
            (EntityType.ALLERGY, "花生过敏", "用户对花生过敏", EntityPriority.CRITICAL.value),
            (EntityType.CONSTRAINT, "海鲜禁忌", "不能吃海鲜", EntityPriority.CRITICAL.value),
            (EntityType.DECISION, "Python后端", "决定用Python做后端", EntityPriority.HIGH.value),
            (EntityType.PREFERENCE, "蓝色杯子", "喜欢蓝色杯子", EntityPriority.MEDIUM.value),
            (EntityType.PREFERENCE, "咖啡口味", "喜欢美式咖啡", EntityPriority.MEDIUM.value),
            (EntityType.CONTACT, "电话号码", "13812345678", EntityPriority.LOW.value),
        ]
        
        for entity_type, name, content, priority in entities_to_add:
            integration.store.add_entity(Entity(
                type=entity_type,
                name=name,
                content=content,
                priority=priority,
            ))
        
        stats = integration.get_store_stats()
        print(f"\n  Added {stats['total_entities']} entities")
        
        # Test injection with limited entities
        print("\n  Testing injection with max_entities=3...")
        entities = integration.get_entities_for_injection(max_entities=3)
        
        print(f"  Selected {len(entities)} entities:")
        for e in entities:
            print(f"    - [{e.priority}] {e.name}")
        
        # Verify critical entities are always included
        critical_names = [e.name for e in entities if e.priority >= 100]
        print(f"\n  Critical entities in selection: {critical_names}")
        
        assert "花生过敏" in [e.name for e in entities], "Critical allergy not included!"
        assert "海鲜禁忌" in [e.name for e in entities], "Critical constraint not included!"
        
        print(f"\n  ✅ Priority-based injection works!")


def test_memory_pressure():
    """Test system under memory pressure (many entities)."""
    print("\n" + "=" * 70)
    print("Large Scenario Test: Memory Pressure")
    print("=" * 70)
    
    with tempfile.TemporaryDirectory() as tmpdir:
        reset_memory_integration()
        integration = MemoryIntegration(tmpdir)
        
        # Add 100 entities
        print("\n  Adding 100 entities...")
        start_time = time.time()
        
        for i in range(100):
            entity_type = [
                EntityType.PREFERENCE,
                EntityType.DECISION,
                EntityType.EVENT,
                EntityType.PROJECT,
            ][i % 4]
            
            priority = [50, 60, 70, 80][i % 4]
            
            integration.store.add_entity(Entity(
                type=entity_type,
                name=f"Entity_{i}",
                content=f"这是第 {i} 个实体的内容描述",
                priority=priority,
            ))
        
        add_time = time.time() - start_time
        print(f"  Added 100 entities in {add_time:.3f}s")
        
        stats = integration.get_store_stats()
        print(f"  Stats: {stats['total_entities']} entities")
        
        # Test search performance
        print("\n  Testing search performance...")
        start_time = time.time()
        
        results = integration.store.search("实体")
        
        search_time = time.time() - start_time
        print(f"  Search returned {len(results)} results in {search_time:.3f}s")
        
        # Test injection performance
        print("\n  Testing injection performance...")
        start_time = time.time()
        
        enhanced = integration.inject_to_prompt_sync("你是一个AI助手。", max_entities=20)
        
        injection_time = time.time() - start_time
        print(f"  Injection completed in {injection_time:.3f}s")
        print(f"  Enhanced prompt length: {len(enhanced)} chars")
        
        # Verify performance is acceptable
        assert add_time < 5.0, f"Add too slow: {add_time}s"
        assert search_time < 1.0, f"Search too slow: {search_time}s"
        assert injection_time < 1.0, f"Injection too slow: {injection_time}s"
        
        print(f"\n  ✅ Performance test passed!")


def main():
    """Run all large scenario tests."""
    print("\n" + "=" * 70)
    print("V3.5 Large Scenario Integration Tests")
    print("=" * 70)
    
    results = []
    
    tests = [
        ("Large Conversation Compaction", test_large_conversation_compaction),
        ("Cross-Session Retrieval", test_cross_session_retrieval),
        ("Conflict Resolution", test_conflict_resolution),
        ("Priority-Based Injection", test_priority_based_injection),
        ("Memory Pressure", test_memory_pressure),
    ]
    
    for name, test_func in tests:
        try:
            result = test_func()
            results.append((name, "✅ PASS", result))
        except Exception as e:
            results.append((name, "❌ FAIL", str(e)))
            print(f"\n  Error: {e}")
    
    # Summary
    print("\n" + "=" * 70)
    print("Test Summary")
    print("=" * 70)
    
    passed = sum(1 for _, status, _ in results if status == "✅ PASS")
    failed = sum(1 for _, status, _ in results if status == "❌ FAIL")
    
    for name, status, _ in results:
        print(f"  {status} {name}")
    
    print(f"\n  Total: {passed} passed, {failed} failed")
    print("=" * 70)
    
    if failed > 0:
        raise AssertionError(f"{failed} tests failed")


if __name__ == "__main__":
    main()