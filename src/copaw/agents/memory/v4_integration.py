#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
V4.0 LLM 提取与 V3.5 存储集成

功能：
1. LLM 提取的实体转换为 V3.5 Entity 格式
2. 存储到 UnifiedEntityStore
3. 集成到现有的记忆流程
"""
import json
import time
import logging
from datetime import datetime
from pathlib import Path
from typing import List, Optional, Dict, Any

from .models import Entity, EntityType, EntityPriority
from .store import UnifiedEntityStore
from .llm_extractor import (
    LLMExtractor, 
    LLMExtractedEntity, 
    LLMEntityType,
    ExtractionSource,
    ExtractionResult,
    TriggerStrategy,
    UnifiedExtractor as BaseUnifiedExtractor,
)

logger = logging.getLogger(__name__)


# ============================================================
# 类型映射：LLM 实体类型 → V3.5 Entity 类型
# ============================================================

LLM_TO_V3_TYPE_MAP = {
    LLMEntityType.PROJECT: EntityType.PROJECT,
    LLMEntityType.TECH_DECISION: EntityType.DECISION,
    LLMEntityType.PERSON: EntityType.PERSON,
    LLMEntityType.RELATION: EntityType.PERSON,
    LLMEntityType.PREFERENCE: EntityType.PREFERENCE,
    LLMEntityType.EVENT: EntityType.EVENT,
    LLMEntityType.MILESTONE: EntityType.EVENT,
    LLMEntityType.FACT: EntityType.CONSTRAINT,
    LLMEntityType.CONTEXT: EntityType.CONSTRAINT,
    LLMEntityType.OTHER: EntityType.CONSTRAINT,
}

# 优先级映射
LLM_TO_V3_PRIORITY_MAP = {
    LLMEntityType.PROJECT: EntityPriority.HIGH.value,
    LLMEntityType.TECH_DECISION: EntityPriority.HIGH.value,
    LLMEntityType.PERSON: EntityPriority.MEDIUM.value,
    LLMEntityType.RELATION: EntityPriority.MEDIUM.value,
    LLMEntityType.PREFERENCE: EntityPriority.MEDIUM.value,
    LLMEntityType.EVENT: EntityPriority.HIGH.value,
    LLMEntityType.MILESTONE: EntityPriority.HIGH.value,
    LLMEntityType.FACT: EntityPriority.MEDIUM.value,
    LLMEntityType.CONTEXT: EntityPriority.LOW.value,
    LLMEntityType.OTHER: EntityPriority.LOW.value,
}


def llm_entity_to_v3_entity(llm_entity: LLMExtractedEntity) -> Entity:
    """
    将 LLM 提取的实体转换为 V3.5 Entity 格式
    
    Args:
        llm_entity: LLM 提取的实体
        
    Returns:
        V3.5 Entity
    """
    # 类型映射
    entity_type = LLM_TO_V3_TYPE_MAP.get(llm_entity.type, EntityType.CONSTRAINT)
    
    # 优先级映射
    priority = LLM_TO_V3_PRIORITY_MAP.get(llm_entity.type, EntityPriority.LOW.value)
    
    # 如果实体本身有 importance，可以覆盖
    if llm_entity.importance >= 80:
        priority = EntityPriority.HIGH.value
    elif llm_entity.importance >= 50:
        priority = EntityPriority.MEDIUM.value
    
    # 构建 content
    content = llm_entity.content or llm_entity.name
    if llm_entity.attributes:
        # 将属性追加到 content
        attr_str = ", ".join(f"{k}={v}" for k, v in llm_entity.attributes.items())
        content = f"{content} ({attr_str})"
    
    # 构建 attributes
    attributes = {
        "source": llm_entity.source.value,
        "confidence": llm_entity.confidence,
        "extractor_model": llm_entity.extractor_model,
        "llm_type": llm_entity.type.value,
        **llm_entity.attributes,  # 合并原始属性
    }
    
    from .models import EntitySource
    
    return Entity(
        type=entity_type,
        name=llm_entity.name[:50] if llm_entity.name else "未命名实体",
        content=content[:500] if content else "",
        priority=priority,
        source=EntitySource.LLM if llm_entity.source == ExtractionSource.LLM else EntitySource.REGEX,
        confidence=llm_entity.confidence,
        attributes=attributes,
    )


def v3_entity_to_llm_entity(entity: Entity) -> LLMExtractedEntity:
    """
    将 V3.5 Entity 转换为 LLM 实体格式（反向转换）
    """
    attributes = entity.attributes or {}
    
    # 推断 LLM 类型
    llm_type = LLMEntityType.OTHER
    if attributes.get("llm_type"):
        try:
            llm_type = LLMEntityType(attributes["llm_type"])
        except ValueError:
            pass
    
    return LLMExtractedEntity(
        id=attributes.get("original_id", entity.id),
        type=llm_type,
        name=entity.name,
        content=entity.content,
        attributes={k: v for k, v in attributes.items() if k not in ["source", "confidence", "extractor_model", "llm_type"]},
        source=ExtractionSource.LLM if entity.source.value == "llm" else ExtractionSource.REGEX,
        confidence=entity.confidence,
        extractor_model=attributes.get("extractor_model", ""),
        created_at=entity.created_at if entity.created_at else datetime.now(),
        importance=entity.priority,
    )


# ============================================================
# V4.0 集成提取器
# ============================================================

class V4IntegratedExtractor:
    """
    V4.0 集成提取器
    
    整合：
    1. 正则提取（V2.1 KeyInfoExtractor）
    2. LLM 语义提取（V4.0）
    3. 统一存储（V3.5 UnifiedEntityStore）
    """
    
    def __init__(
        self,
        store_dir: str = "",
        llm_model: str = "gpt-4o-mini",
        enable_llm: bool = True,
        trigger_strategy: Optional[TriggerStrategy] = None,
    ):
        """
        初始化
        
        Args:
            store_dir: 实体存储目录
            llm_model: LLM 模型
            enable_llm: 是否启用 LLM 提取
            trigger_strategy: 触发策略
        """
        # 初始化存储
        self.store = UnifiedEntityStore(store_dir) if store_dir else UnifiedEntityStore()
        
        # 初始化提取器
        self.llm_extractor = LLMExtractor(model=llm_model) if enable_llm else None
        self.trigger_strategy = trigger_strategy or TriggerStrategy()
        self.enable_llm = enable_llm
        
        # 统计
        self.stats = {
            "total_messages": 0,
            "llm_triggered": 0,
            "entities_extracted": 0,
            "tokens_used": 0,
        }
    
    def process_message(
        self,
        message: str,
        context: str = "",
        session_id: str = "",
        force_llm: bool = False,
    ) -> List[Entity]:
        """
        处理消息，提取并存储实体
        
        Args:
            message: 用户消息
            context: 对话上下文
            session_id: 会话ID
            force_llm: 是否强制使用 LLM
            
        Returns:
            提取的实体列表（V3.5 格式）
        """
        self.stats["total_messages"] += 1
        
        entities = []
        
        # 判断是否触发 LLM
        should_trigger_llm = False
        trigger_reason = ""
        
        if self.enable_llm and self.llm_extractor:
            if force_llm:
                should_trigger_llm = True
                trigger_reason = "force_llm"
            else:
                should_trigger_llm, trigger_reason = self.trigger_strategy.should_trigger(message)
        
        # 执行 LLM 提取
        if should_trigger_llm:
            self.stats["llm_triggered"] += 1
            
            conversation = f"{context}\n\n当前消息：{message}" if context else message
            result = self.llm_extractor.extract(conversation, session_id)
            
            # 更新统计
            self.stats["tokens_used"] += result.tokens_used
            
            # 转换并存储
            for llm_entity in result.entities:
                v3_entity = llm_entity_to_v3_entity(llm_entity)
                self.store.add_entity(v3_entity)
                entities.append(v3_entity)
            
            # 重置缓冲区
            self.trigger_strategy.reset_buffer()
            
            logger.info(f"LLM extraction triggered: {trigger_reason}, found {len(entities)} entities")
        
        self.stats["entities_extracted"] += len(entities)
        return entities
    
    def process_batch(
        self,
        messages: List[str],
        session_id: str = "",
    ) -> List[Entity]:
        """
        批量处理消息
        
        Args:
            messages: 消息列表
            session_id: 会话ID
            
        Returns:
            提取的实体列表
        """
        if not self.enable_llm or not self.llm_extractor:
            return []
        
        self.stats["llm_triggered"] += 1
        
        conversation = "\n".join(messages)
        result = self.llm_extractor.extract(conversation, session_id)
        
        self.stats["tokens_used"] += result.tokens_used
        
        entities = []
        for llm_entity in result.entities:
            v3_entity = llm_entity_to_v3_entity(llm_entity)
            self.store.add_entity(v3_entity)
            entities.append(v3_entity)
        
        self.stats["entities_extracted"] += len(entities)
        return entities
    
    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        store_stats = self.store.get_stats()
        return {
            **self.stats,
            "store_stats": store_stats,
        }
    
    def get_all_entities(self) -> List[Entity]:
        """获取所有存储的实体"""
        return self.store.get_all_entities()


# ============================================================
# 测试
# ============================================================

def test_llm_to_v3_conversion():
    """测试 LLM 实体到 V3 实体的转换"""
    print("=" * 60)
    print("测试 LLM 实体转换")
    print("=" * 60)
    
    # 创建 LLM 实体
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
            content="我们决定用 Python 做后端",
            attributes={"domain": "后端"},
            confidence=0.9,
            importance=75,
        ),
        LLMExtractedEntity(
            type=LLMEntityType.PERSON,
            name="张三",
            content="我老板叫张三",
            attributes={"relation": "老板"},
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
    ]
    
    print("\n转换结果:")
    for llm_entity in llm_entities:
        v3_entity = llm_entity_to_v3_entity(llm_entity)
        print(f"\n  LLM实体: [{llm_entity.type.value}] {llm_entity.name}")
        print(f"  V3实体:  [{v3_entity.type.value}] {v3_entity.name}")
        print(f"    优先级: {v3_entity.priority}")
        print(f"    内容: {v3_entity.content[:60]}...")


def test_v4_integrated_extractor():
    """测试 V4 集成提取器"""
    print("\n" + "=" * 60)
    print("测试 V4 集成提取器")
    print("=" * 60)
    
    import tempfile
    with tempfile.TemporaryDirectory() as tmpdir:
        extractor = V4IntegratedExtractor(
            store_dir=tmpdir,
            llm_model="gpt-4o-mini",
            enable_llm=False,  # 测试时不启用 LLM
        )
        
        # 测试触发策略
        test_messages = [
            ("帮我查天气", False),
            ("记住，我老板叫张三", True),
            ("我正在做一个卫星计算项目", True),
        ]
        
        print("\n触发策略测试:")
        for msg, expected in test_messages:
            should_trigger, reason = extractor.trigger_strategy.should_trigger(msg)
            status = "✅" if should_trigger == expected else "❌"
            print(f"  {status} '{msg[:30]}...' -> 触发={should_trigger}, 原因={reason}")
        
        print(f"\n统计: {extractor.get_stats()}")


if __name__ == "__main__":
    test_llm_to_v3_conversion()
    test_v4_integrated_extractor()