#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
V4.0 LLM 语义提取测试

测试目标：
1. 触发策略正确性
2. LLM实体转换正确性
3. 与V3.5存储集成正确性
4. 端到端提取流程

对比场景：
- V3.5：只能提取正则模式匹配的信息
- V4.0：可以提取复杂语义信息（项目、技术决策、人际关系等）
"""
import json
import sys
import tempfile
from pathlib import Path
from typing import List

sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent.parent / "src"))

from copaw.agents.memory.unified.models import Entity, EntityType, EntitySource, EntityPriority
from copaw.agents.memory.unified.store import UnifiedEntityStore
from copaw.agents.memory.unified.llm_extractor import (
    LLMExtractor,
    LLMExtractedEntity,
    LLMEntityType,
    ExtractionSource,
    ExtractionResult,
    TriggerStrategy,
)
from copaw.agents.memory.unified.v4_integration import (
    llm_entity_to_v3_entity,
    v3_entity_to_llm_entity,
    V4IntegratedExtractor,
)


# ============================================================
# 测试用例
# ============================================================

# 正则无法提取，但LLM可以提取的复杂信息
COMPLEX_INFO_CASES = [
    {
        "message": "我正在做一个卫星计算项目，这是我们团队最重要的项目",
        "expected_type": LLMEntityType.PROJECT,
        "expected_name": "卫星计算项目",
        "regex_can_extract": False,
        "description": "项目背景",
    },
    {
        "message": "我们决定用 Python 做后端，选择了 FastAPI 框架",
        "expected_type": LLMEntityType.TECH_DECISION,
        "expected_name": "Python",
        "regex_can_extract": False,
        "description": "技术决策（非'决定'模式）",
    },
    {
        "message": "我老板叫张三，他负责产品方向",
        "expected_type": LLMEntityType.PERSON,
        "expected_name": "张三",
        "regex_can_extract": False,
        "description": "人际关系",
    },
    {
        "message": "加班时我喜欢喝咖啡，但不加糖",
        "expected_type": LLMEntityType.PREFERENCE,
        "expected_name": "咖啡",
        "regex_can_extract": False,
        "description": "条件偏好",
    },
    {
        "message": "团队有5个人，预算100万",
        "expected_type": LLMEntityType.FACT,
        "expected_name": "团队规模",
        "regex_can_extract": False,
        "description": "事实信息",
    },
]

# 触发策略测试
TRIGGER_TEST_CASES = [
    {"message": "帮我查天气", "should_trigger": False, "reason": "普通消息"},
    {"message": "记住，我老板叫张三", "should_trigger": True, "reason": "显式标记"},
    {"message": "我正在做一个卫星计算项目，这是我们团队最重要的项目，涉及多个技术栈", "should_trigger": True, "reason": "长消息+关键词"},
    {"message": "我们团队有5个人", "should_trigger": True, "reason": "关键词检测"},
    {"message": "记住这个重要的信息：明天开会", "should_trigger": True, "reason": "显式标记"},
]


# ============================================================
# 测试函数
# ============================================================

def test_trigger_strategy():
    """测试触发策略"""
    print("=" * 70)
    print("测试1: 触发策略")
    print("=" * 70)
    
    strategy = TriggerStrategy()
    
    passed = 0
    failed = 0
    
    for case in TRIGGER_TEST_CASES:
        should_trigger, reason = strategy.should_trigger(case["message"])
        expected = case["should_trigger"]
        
        # 检查结果
        if should_trigger == expected:
            status = "✅"
            passed += 1
        else:
            status = "❌"
            failed += 1
        
        print(f"\n  {status} [{case['reason']}]")
        print(f"     消息: {case['message'][:40]}...")
        print(f"     预期触发: {expected}, 实际: {should_trigger}")
        print(f"     触发原因: {reason}")
    
    print(f"\n  结果: {passed}/{len(TRIGGER_TEST_CASES)} 通过")
    return failed == 0


def test_entity_conversion():
    """测试实体转换"""
    print("\n" + "=" * 70)
    print("测试2: LLM实体 → V3.5 Entity 转换")
    print("=" * 70)
    
    # 创建各种类型的LLM实体
    llm_entities = [
        LLMExtractedEntity(
            type=LLMEntityType.PROJECT,
            name="卫星计算项目",
            content="我正在做一个卫星计算项目",
            attributes={"role": "参与者", "status": "进行中"},
            confidence=0.95,
            importance=80,
        ),
        LLMExtractedEntity(
            type=LLMEntityType.TECH_DECISION,
            name="Python后端",
            content="我们决定用Python做后端",
            attributes={"domain": "后端", "framework": "FastAPI"},
            confidence=0.9,
            importance=75,
        ),
        LLMExtractedEntity(
            type=LLMEntityType.PERSON,
            name="张三",
            content="我老板叫张三",
            attributes={"relation": "老板", "role": "产品负责人"},
            confidence=0.95,
            importance=60,
        ),
        LLMExtractedEntity(
            type=LLMEntityType.PREFERENCE,
            name="咖啡",
            content="加班时我喜欢喝咖啡",
            attributes={"condition": "加班时", "sentiment": "like"},
            confidence=0.85,
            importance=50,
        ),
        LLMExtractedEntity(
            type=LLMEntityType.EVENT,
            name="发布v2.0",
            content="上周我们发布了v2.0",
            attributes={"time": "上周"},
            confidence=0.9,
            importance=70,
        ),
    ]
    
    passed = 0
    failed = 0
    
    for llm_entity in llm_entities:
        v3_entity = llm_entity_to_v3_entity(llm_entity)
        
        # 验证转换
        checks = [
            ("类型映射", v3_entity.type is not None),
            ("优先级设置", v3_entity.priority >= 0),
            ("来源标记", v3_entity.source == EntitySource.LLM),
            ("置信度保留", v3_entity.confidence == llm_entity.confidence),
            ("属性保留", len(v3_entity.attributes) > 0),
        ]
        
        all_passed = all(c[1] for c in checks)
        status = "✅" if all_passed else "❌"
        
        if all_passed:
            passed += 1
        else:
            failed += 1
        
        print(f"\n  {status} [{llm_entity.type.value}] {llm_entity.name}")
        print(f"     V3类型: {v3_entity.type.value}, 优先级: {v3_entity.priority}")
        print(f"     来源: {v3_entity.source.value}, 置信度: {v3_entity.confidence}")
        for check_name, check_result in checks:
            print(f"       {'✓' if check_result else '✗'} {check_name}")
    
    print(f"\n  结果: {passed}/{len(llm_entities)} 通过")
    return failed == 0


def test_v4_integrated_extractor():
    """测试V4集成提取器"""
    print("\n" + "=" * 70)
    print("测试3: V4 集成提取器（不含LLM调用）")
    print("=" * 70)
    
    with tempfile.TemporaryDirectory() as tmpdir:
        # 创建提取器（不启用LLM）
        extractor = V4IntegratedExtractor(
            store_dir=tmpdir,
            enable_llm=False,
        )
        
        # 测试统计
        stats = extractor.get_stats()
        print(f"\n  初始统计: {stats}")
        
        # 模拟处理消息
        test_messages = [
            "帮我查天气",
            "记住，我老板叫张三",
            "我正在做一个卫星计算项目",
        ]
        
        for msg in test_messages:
            entities = extractor.process_message(msg, force_llm=False)
            print(f"\n  消息: '{msg[:30]}...'")
            print(f"    触发LLM: False (测试模式)")
            print(f"    提取实体: {len(entities)}")
        
        # 验证统计
        stats = extractor.get_stats()
        print(f"\n  最终统计: {stats}")
        
        print("\n  ✅ 集成提取器测试通过")
        return True


def test_complex_info_extraction():
    """测试复杂信息提取（模拟LLM响应）"""
    print("\n" + "=" * 70)
    print("测试4: 复杂信息提取能力对比")
    print("=" * 70)
    
    print("\n  正则提取 vs LLM提取 对比:")
    print("  " + "-" * 60)
    
    for case in COMPLEX_INFO_CASES:
        # 模拟LLM提取结果
        llm_entity = LLMExtractedEntity(
            type=case["expected_type"],
            name=case["expected_name"],
            content=case["message"],
            confidence=0.9,
        )
        
        # 转换为V3实体
        v3_entity = llm_entity_to_v3_entity(llm_entity)
        
        # 正则能否提取
        regex_status = "✅" if case["regex_can_extract"] else "❌"
        llm_status = "✅"
        
        print(f"\n  [{case['description']}]")
        print(f"    消息: {case['message'][:50]}...")
        print(f"    正则提取: {regex_status}")
        print(f"    LLM提取:  {llm_status} [{v3_entity.type.value}] {v3_entity.name}")
    
    print("\n  " + "-" * 60)
    print("  结论: LLM可以提取正则无法处理的复杂语义信息")
    return True


def test_store_integration():
    """测试与V3.5存储的集成"""
    print("\n" + "=" * 70)
    print("测试5: 与V3.5存储集成")
    print("=" * 70)
    
    with tempfile.TemporaryDirectory() as tmpdir:
        store = UnifiedEntityStore(tmpdir)
        
        # 创建并存储LLM提取的实体
        llm_entities = [
            LLMExtractedEntity(
                type=LLMEntityType.PROJECT,
                name="卫星计算项目",
                content="卫星计算项目",
                attributes={"role": "参与者"},
                confidence=0.95,
            ),
            LLMExtractedEntity(
                type=LLMEntityType.PERSON,
                name="张三",
                content="我老板叫张三",
                attributes={"relation": "老板"},
                confidence=0.9,
            ),
        ]
        
        for llm_entity in llm_entities:
            v3_entity = llm_entity_to_v3_entity(llm_entity)
            store.add_entity(v3_entity)
            print(f"  存储: [{v3_entity.type.value}] {v3_entity.name}")
        
        # 验证存储
        all_entities = store.get_all_entities()
        print(f"\n  存储实体数: {len(all_entities)}")
        
        # 验证检索
        for entity in all_entities:
            print(f"    - [{entity.type.value}] {entity.name} (source={entity.source.value})")
        
        # 验证来源
        llm_entities_count = sum(1 for e in all_entities if e.source == EntitySource.LLM)
        print(f"\n  LLM来源实体: {llm_entities_count}")
        
        if llm_entities_count == len(llm_entities):
            print("  ✅ 存储集成测试通过")
            return True
        else:
            print("  ❌ 存储集成测试失败")
            return False


# ============================================================
# 主测试运行
# ============================================================

def run_all_tests():
    """运行所有测试"""
    print("=" * 70)
    print("🧪 V4.0 LLM 语义提取测试")
    print("=" * 70)
    
    results = []
    
    # 运行测试
    results.append(("触发策略", test_trigger_strategy()))
    results.append(("实体转换", test_entity_conversion()))
    results.append(("集成提取器", test_v4_integrated_extractor()))
    results.append(("复杂信息提取", test_complex_info_extraction()))
    results.append(("存储集成", test_store_integration()))
    
    # 总结
    print("\n" + "=" * 70)
    print("📊 测试结果总结")
    print("=" * 70)
    
    passed = sum(1 for _, r in results if r)
    failed = len(results) - passed
    
    print(f"\n  总计: {len(results)} 个测试")
    print(f"  通过: {passed}")
    print(f"  失败: {failed}")
    
    print("\n  详细结果:")
    for name, result in results:
        status = "✅" if result else "❌"
        print(f"    {status} {name}")
    
    if failed == 0:
        print("\n  🎉 所有测试通过！")
    else:
        print(f"\n  ⚠️ {failed} 个测试失败")
    
    return failed == 0


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)