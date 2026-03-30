#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
V4.0 LLM 语义提取引擎

核心功能：
- 突破正则模式限制，实现语义理解
- 支持项目背景、技术决策、人际关系等复杂信息
- 成本优化：智能触发 + 批量处理

设计要点：
1. 分层提取：正则优先（无成本），LLM 按需（有成本）
2. 成本优化：智能触发 + 批量处理 + 去重
3. 统一存储：与 V3.5 的 UnifiedEntityStore 集成
"""
import json
import time
import asyncio
from datetime import datetime
from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any, Tuple
from enum import Enum
import uuid
import logging

logger = logging.getLogger(__name__)


# ============================================================
# 数据模型
# ============================================================

class LLMEntityType(Enum):
    """LLM 提取的实体类型"""
    # 项目相关
    PROJECT = "project"              # 项目背景
    TECH_DECISION = "tech_decision"  # 技术决策
    
    # 人际关系
    PERSON = "person"                # 人物
    RELATION = "relation"            # 关系
    
    # 偏好
    PREFERENCE = "preference"        # 偏好（含条件偏好）
    
    # 事件
    EVENT = "event"                  # 重要事件
    MILESTONE = "milestone"          # 里程碑
    
    # 其他
    FACT = "fact"                    # 事实
    CONTEXT = "context"              # 上下文信息
    OTHER = "other"                  # 其他


class ExtractionSource(Enum):
    """提取来源"""
    REGEX = "regex"    # 正则提取
    LLM = "llm"        # LLM 提取
    MANUAL = "manual"  # 手动添加


@dataclass
class LLMExtractedEntity:
    """LLM 提取的实体"""
    # 基本信息
    id: str = field(default_factory=lambda: f"llm_{uuid.uuid4().hex[:8]}")
    type: LLMEntityType = LLMEntityType.OTHER
    name: str = ""
    content: str = ""
    
    # 结构化属性
    attributes: Dict[str, Any] = field(default_factory=dict)
    
    # 提取信息
    source: ExtractionSource = ExtractionSource.LLM
    confidence: float = 1.0
    extractor_model: str = ""
    
    # 时间信息
    created_at: datetime = field(default_factory=datetime.now)
    
    # 来源上下文
    context: str = ""
    session_id: str = ""
    
    # 重要性
    importance: int = 50
    
    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "type": self.type.value,
            "name": self.name,
            "content": self.content,
            "attributes": self.attributes,
            "source": self.source.value,
            "confidence": self.confidence,
            "extractor_model": self.extractor_model,
            "created_at": self.created_at.isoformat(),
            "context": self.context,
            "session_id": self.session_id,
            "importance": self.importance,
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> "LLMExtractedEntity":
        return cls(
            id=data.get("id", ""),
            type=LLMEntityType(data.get("type", "other")),
            name=data.get("name", ""),
            content=data.get("content", ""),
            attributes=data.get("attributes", {}),
            source=ExtractionSource(data.get("source", "llm")),
            confidence=data.get("confidence", 1.0),
            extractor_model=data.get("extractor_model", ""),
            created_at=datetime.fromisoformat(data["created_at"]) if data.get("created_at") else datetime.now(),
            context=data.get("context", ""),
            session_id=data.get("session_id", ""),
            importance=data.get("importance", 50),
        )


@dataclass
class ExtractionResult:
    """提取结果"""
    entities: List[LLMExtractedEntity] = field(default_factory=list)
    trigger_reason: str = ""
    model_used: str = ""
    tokens_used: int = 0
    latency_ms: int = 0
    
    def to_dict(self) -> dict:
        return {
            "entities": [e.to_dict() for e in self.entities],
            "trigger_reason": self.trigger_reason,
            "model_used": self.model_used,
            "tokens_used": self.tokens_used,
            "latency_ms": self.latency_ms,
        }


# ============================================================
# 提取 Prompt
# ============================================================

EXTRACTION_PROMPT_TEMPLATE = """你是一个信息提取专家。请从以下对话中提取所有重要的结构化信息。

## 对话内容
{conversation}

## 提取规则

1. **项目信息 (project)**
   - 项目名称、背景、目标
   - 用户在项目中的角色
   - 项目状态、进度
   
   示例：
   - "我正在做一个卫星计算项目" → project: 卫星计算项目, attributes={role: 参与者}
   - "后端开发完成了80%" → project: 后端开发, attributes={status: 进行中, progress: 80%}

2. **技术决策 (tech_decision)**
   - 技术选型、架构决策
   - 工具、框架选择
   
   示例：
   - "我们用 Python 做后端" → tech_decision: Python, attributes={domain: 后端}
   - "选择了 PostgreSQL 而不是 MySQL" → tech_decision: PostgreSQL, attributes={alternative: MySQL}

3. **人际关系 (person)**
   - 人物名称、角色
   - 与用户的关系
   
   示例：
   - "我老板叫张三" → person: 张三, attributes={relation: 老板}
   - "同事李四负责前端" → person: 李四, attributes={relation: 同事, role: 前端}

4. **偏好 (preference)**
   - 喜欢/不喜欢
   - 条件偏好（在什么情况下）
   
   示例：
   - "加班时我喜欢喝咖啡" → preference: 咖啡, attributes={sentiment: like, condition: 加班时}
   - "我不太能吃辣" → preference: 辣, attributes={sentiment: dislike, intensity: 轻微}

5. **事件 (event)**
   - 重要事件、里程碑
   - 时间、地点
   
   示例：
   - "上周我们发布了v2.0" → event: 发布v2.0, attributes={time: 上周}
   - "下个月要上线" → event: 上线, attributes={time: 下个月}

6. **事实 (fact)**
   - 客观事实、数字、状态
   
   示例：
   - "团队有5个人" → fact: 团队规模, attributes={value: 5}
   - "预算100万" → fact: 预算, attributes={value: 100万}

## 输出格式

请输出 JSON 数组，每个元素包含：
```json
[
  {{
    "type": "project|tech_decision|person|preference|event|fact|other",
    "name": "实体名称（简短）",
    "content": "实体描述（完整句子）",
    "attributes": {{
      "key": "value"
    }},
    "confidence": 0.0-1.0,
    "importance": 0-100
  }}
]
```

如果没有重要信息，输出空数组：[]

只输出 JSON，不要输出其他内容。"""


# ============================================================
# LLM 提取器
# ============================================================

class LLMExtractor:
    """LLM 语义提取器"""
    
    def __init__(self, model: str = "gpt-4o-mini", api_key: str = "", base_url: str = ""):
        """
        初始化 LLM 提取器
        
        Args:
            model: 使用的模型，默认 gpt-4o-mini（成本优化）
            api_key: API Key（可选，从环境变量读取）
            base_url: API Base URL（可选）
        """
        self.model = model
        self.api_key = api_key
        self.base_url = base_url
        self._client = None
    
    def _get_client(self):
        """延迟初始化 OpenAI 客户端"""
        if self._client is None:
            try:
                from openai import OpenAI
                self._client = OpenAI(
                    api_key=self.api_key or None,
                    base_url=self.base_url or None,
                )
            except ImportError:
                logger.warning("openai package not installed")
                self._client = None
        return self._client
    
    def extract(self, conversation: str, session_id: str = "") -> ExtractionResult:
        """
        从对话中提取实体
        
        Args:
            conversation: 对话内容
            session_id: 会话ID
            
        Returns:
            ExtractionResult
        """
        start_time = time.time()
        
        client = self._get_client()
        if client is None:
            logger.warning("LLM client not available, returning empty result")
            return ExtractionResult(
                entities=[],
                trigger_reason="llm_unavailable",
                model_used="none",
            )
        
        prompt = EXTRACTION_PROMPT_TEMPLATE.format(conversation=conversation)
        
        try:
            response = client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "你是一个信息提取专家，擅长从对话中提取结构化信息。"},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.1,  # 低温度，更确定性
                max_tokens=1000,
            )
            
            content = response.choices[0].message.content
            tokens_used = response.usage.total_tokens if response.usage else 0
            
            # 解析 JSON
            entities = self._parse_response(content, conversation, session_id)
            
            latency_ms = int((time.time() - start_time) * 1000)
            
            return ExtractionResult(
                entities=entities,
                trigger_reason="llm_extraction",
                model_used=self.model,
                tokens_used=tokens_used,
                latency_ms=latency_ms,
            )
            
        except Exception as e:
            logger.error(f"LLM extraction failed: {e}")
            return ExtractionResult(
                entities=[],
                trigger_reason=f"error: {str(e)}",
                model_used=self.model,
            )
    
    async def extract_async(self, conversation: str, session_id: str = "") -> ExtractionResult:
        """异步提取"""
        # 在线程池中执行同步方法
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self.extract, conversation, session_id)
    
    def _parse_response(self, content: str, context: str, session_id: str) -> List[LLMExtractedEntity]:
        """解析 LLM 响应"""
        entities = []
        
        # 提取 JSON
        try:
            # 尝试直接解析
            json_str = content.strip()
            
            # 如果被 ```json 包裹，提取内容
            if "```json" in json_str:
                start = json_str.find("```json") + 7
                end = json_str.find("```", start)
                json_str = json_str[start:end].strip()
            elif "```" in json_str:
                start = json_str.find("```") + 3
                end = json_str.find("```", start)
                json_str = json_str[start:end].strip()
            
            data = json.loads(json_str)
            
            if isinstance(data, list):
                for item in data:
                    entity = self._create_entity(item, context, session_id)
                    if entity:
                        entities.append(entity)
                        
        except json.JSONDecodeError as e:
            logger.warning(f"Failed to parse LLM response as JSON: {e}")
            # 尝试修复常见问题
            # ...
        
        return entities
    
    def _create_entity(self, item: dict, context: str, session_id: str) -> Optional[LLMExtractedEntity]:
        """从解析的数据创建实体"""
        try:
            type_str = item.get("type", "other")
            try:
                entity_type = LLMEntityType(type_str)
            except ValueError:
                entity_type = LLMEntityType.OTHER
            
            return LLMExtractedEntity(
                type=entity_type,
                name=item.get("name", ""),
                content=item.get("content", ""),
                attributes=item.get("attributes", {}),
                source=ExtractionSource.LLM,
                confidence=float(item.get("confidence", 0.9)),
                extractor_model=self.model,
                context=context[:200],  # 限制上下文长度
                session_id=session_id,
                importance=int(item.get("importance", 50)),
            )
        except Exception as e:
            logger.warning(f"Failed to create entity: {e}")
            return None


# ============================================================
# 成本优化触发策略
# ============================================================

class TriggerStrategy:
    """LLM 提取触发策略"""
    
    def __init__(
        self,
        long_message_threshold: int = 100,
        batch_size: int = 5,
        max_interval_seconds: int = 300,
        enable_keywords: bool = True,
    ):
        self.long_message_threshold = long_message_threshold
        self.batch_size = batch_size
        self.max_interval_seconds = max_interval_seconds
        self.enable_keywords = enable_keywords
        
        # 触发关键词
        self.trigger_keywords = [
            "记住", "别忘了", "重要的", "重要信息",
            "项目", "团队", "决定", "选择", "老板", "同事",
            "计划", "目标", "进度", "上线", "发布",
        ]
        
        # 状态
        self.message_buffer: List[str] = []
        self.last_extraction_time = datetime.now()
    
    def should_trigger(self, message: str) -> Tuple[bool, str]:
        """
        判断是否需要触发 LLM 提取
        
        Returns:
            (should_trigger, reason)
        """
        # 规则1：显式标记
        explicit_keywords = ["记住", "别忘了", "重要的", "重要信息"]
        if any(kw in message for kw in explicit_keywords):
            return True, "explicit_mark"
        
        # 规则2：消息长度阈值
        if len(message) > self.long_message_threshold:
            return True, "long_message"
        
        # 规则3：关键词检测
        if self.enable_keywords:
            if any(kw in message for kw in self.trigger_keywords):
                return True, "keyword_detected"
        
        # 规则4：批量处理
        self.message_buffer.append(message)
        if len(self.message_buffer) >= self.batch_size:
            return True, "batch_trigger"
        
        # 规则5：时间间隔
        elapsed = (datetime.now() - self.last_extraction_time).seconds
        if elapsed > self.max_interval_seconds:
            return True, "interval_trigger"
        
        return False, ""
    
    def reset_buffer(self):
        """重置消息缓冲区"""
        self.message_buffer = []
        self.last_extraction_time = datetime.now()
    
    def get_buffered_messages(self) -> List[str]:
        """获取缓冲的消息"""
        return self.message_buffer.copy()


# ============================================================
# 统一提取器
# ============================================================

class UnifiedExtractor:
    """统一提取器：整合正则提取 + LLM 提取"""
    
    def __init__(
        self,
        llm_model: str = "gpt-4o-mini",
        enable_llm: bool = True,
        trigger_strategy: Optional[TriggerStrategy] = None,
    ):
        self.llm_extractor = LLMExtractor(model=llm_model) if enable_llm else None
        self.trigger_strategy = trigger_strategy or TriggerStrategy()
        self.enable_llm = enable_llm
    
    def extract(
        self, 
        message: str, 
        context: str = "",
        session_id: str = "",
        force_llm: bool = False,
    ) -> ExtractionResult:
        """
        统一提取入口
        
        Args:
            message: 用户消息
            context: 对话上下文
            session_id: 会话ID
            force_llm: 是否强制使用 LLM
            
        Returns:
            ExtractionResult
        """
        all_entities = []
        
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
            conversation = f"{context}\n\n当前消息：{message}" if context else message
            result = self.llm_extractor.extract(conversation, session_id)
            
            # 重置缓冲区
            self.trigger_strategy.reset_buffer()
            
            return result
        
        return ExtractionResult(
            entities=all_entities,
            trigger_reason="no_trigger" if not trigger_reason else trigger_reason,
        )
    
    def extract_batch(
        self, 
        messages: List[str], 
        session_id: str = "",
    ) -> ExtractionResult:
        """
        批量提取
        
        Args:
            messages: 消息列表
            session_id: 会话ID
            
        Returns:
            ExtractionResult
        """
        if not self.enable_llm or not self.llm_extractor:
            return ExtractionResult(entities=[], trigger_reason="llm_disabled")
        
        conversation = "\n".join(messages)
        return self.llm_extractor.extract(conversation, session_id)


# ============================================================
# 测试
# ============================================================

def test_llm_extractor():
    """测试 LLM 提取器"""
    print("=" * 60)
    print("测试 LLM 提取器")
    print("=" * 60)
    
    extractor = LLMExtractor(model="gpt-4o-mini")
    
    test_cases = [
        "我正在做一个卫星计算项目，我们团队有5个人",
        "我老板叫张三，他负责产品方向",
        "我们决定用 Python 做后端，选择了 PostgreSQL 数据库",
        "加班时我喜欢喝咖啡，但不加糖",
        "上周我们发布了v2.0，下个月要上线新功能",
    ]
    
    for i, case in enumerate(test_cases):
        print(f"\n[{i+1}] 输入: {case}")
        result = extractor.extract(case)
        
        print(f"    触发原因: {result.trigger_reason}")
        print(f"    使用模型: {result.model_used}")
        print(f"    Token消耗: {result.tokens_used}")
        print(f"    延迟: {result.latency_ms}ms")
        print(f"    提取实体:")
        for entity in result.entities:
            print(f"      - [{entity.type.value}] {entity.name}: {entity.content}")
            if entity.attributes:
                print(f"        属性: {entity.attributes}")


def test_trigger_strategy():
    """测试触发策略"""
    print("\n" + "=" * 60)
    print("测试触发策略")
    print("=" * 60)
    
    strategy = TriggerStrategy()
    
    test_cases = [
        ("帮我查天气", "普通消息"),
        ("记住，我老板叫张三", "显式标记"),
        ("我正在做一个卫星计算项目，这是我们团队最重要的项目，涉及多个技术栈包括Python、Go、Rust等", "长消息"),
        ("我们团队有5个人", "关键词检测"),
    ]
    
    for message, description in test_cases:
        should_trigger, reason = strategy.should_trigger(message)
        status = "✅ 触发" if should_trigger else "⏸️ 跳过"
        print(f"\n  [{description}]")
        print(f"    消息: {message[:40]}...")
        print(f"    结果: {status} (原因: {reason})")


if __name__ == "__main__":
    test_trigger_strategy()
    # test_llm_extractor()  # 需要 API Key