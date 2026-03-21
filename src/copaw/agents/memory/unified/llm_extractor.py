# -*- coding: utf-8 -*-
"""LLM-based Entity Extractor for Memory System.

This module provides semantic extraction using LLM, enabling:
- Project context extraction
- Technical decision extraction  
- Relationship extraction
- Complex preference extraction

Usage:
    extractor = LLMEntityExtractor(model)
    entities = await extractor.extract("我正在做一个卫星计算项目")
"""
import json
import logging
import asyncio
from datetime import datetime
from typing import List, Optional, Dict, Any, Tuple
from dataclasses import dataclass, field
from enum import Enum

logger = logging.getLogger(__name__)


# ============================================================
# LLM Extraction Prompt
# ============================================================

EXTRACTION_PROMPT = """你是一个信息提取专家。请从以下用户消息中提取所有重要的结构化信息。

## 用户消息
{message}

## 提取规则

1. **项目信息 (project)** - 项目名称、背景、目标、进度
2. **技术决策 (tech_decision)** - 技术选型、架构决策
3. **人物信息 (person)** - 人物名称、角色、与用户的关系
4. **偏好 (preference)** - 喜欢/不喜欢，包括条件偏好
5. **事件 (event)** - 重要事件、里程碑、时间
6. **事实 (fact)** - 客观事实、数字

## 输出格式

请输出 JSON 数组：
[
  {{
    "type": "project|tech_decision|person|preference|event|fact",
    "name": "简短名称",
    "content": "完整描述",
    "attributes": {{"key": "value"}},
    "confidence": 0.9,
    "importance": 50
  }}
]

如果没有重要信息，输出空数组：[]
只输出 JSON，不要其他内容。"""


# ============================================================
# LLM Entity Extractor
# ============================================================

class LLMEntityExtractor:
    """LLM-based entity extractor using the configured model."""
    
    def __init__(self, model=None, model_name: str = ""):
        """Initialize LLM extractor.
        
        Args:
            model: The chat model instance (from ProviderManager)
            model_name: Model name for logging
        """
        self.model = model
        self.model_name = model_name or getattr(model, 'model_name', 'unknown')
        
    async def extract(self, message: str, session_id: str = "") -> List[dict]:
        """Extract entities from message using LLM.
        
        Args:
            message: User message to extract from
            session_id: Session ID for tracking
            
        Returns:
            List of entity dictionaries
        """
        if not self.model:
            logger.warning("No model configured for LLM extraction")
            return []
        
        try:
            # Build prompt
            prompt = EXTRACTION_PROMPT.format(message=message)
            
            # Build messages
            msgs = [
                {"role": "system", "content": "你是一个信息提取专家，擅长从对话中提取结构化信息。输出纯JSON格式，不要包含```json标记。"},
                {"role": "user", "content": prompt}
            ]
            
            # Call model - it may return a stream
            response = self.model(msgs)
            
            # Handle both sync and async, stream and non-stream
            full_content = ""
            last_text = ""
            
            # Check if it's a coroutine
            if hasattr(response, '__await__'):
                response = await response
            
            # Check if it's a stream (async generator)
            if hasattr(response, '__aiter__'):
                async for chunk in response:
                    chunk_content = getattr(chunk, 'content', None)
                    if chunk_content:
                        # Handle list content (thinking + text types)
                        if isinstance(chunk_content, list):
                            for item in chunk_content:
                                if isinstance(item, dict) and item.get('type') == 'text':
                                    text = item.get('text', '')
                                    if text:
                                        last_text = text  # Keep track of latest text
            elif hasattr(response, 'content'):
                # Non-streaming response
                response_content = response.content
                if isinstance(response_content, list):
                    for item in response_content:
                        if isinstance(item, dict) and item.get('type') == 'text':
                            last_text = item.get('text', '')
                elif isinstance(response_content, str):
                    last_text = response_content
            else:
                logger.warning(f"Unexpected response type: {type(response)}")
                return []
            
            # Use the last text as the final response
            content = last_text
            
            if not content or not content.strip():
                logger.warning("Empty response from LLM")
                return []
            
            logger.debug(f"LLM response: {content[:200]}...")
            
            # Parse response
            entities_data = self._parse_json(content)
            
            # Convert to entity format
            entities = []
            for item in entities_data:
                entity = self._create_entity_dict(item, message, session_id)
                if entity:
                    entities.append(entity)
            
            logger.info(f"LLM extracted {len(entities)} entities from message")
            return entities
            
        except Exception as e:
            logger.error(f"LLM extraction failed: {e}")
            import traceback
            traceback.print_exc()
            return []
    
    def _parse_json(self, content: str) -> List[dict]:
        """Parse JSON from LLM response."""
        try:
            # Try direct parse
            text = content.strip()
            
            # Handle markdown code blocks
            if "```json" in text:
                start = text.find("```json") + 7
                end = text.find("```", start)
                text = text[start:end].strip()
            elif "```" in text:
                start = text.find("```") + 3
                end = text.find("```", start)
                text = text[start:end].strip()
            
            # Clean control characters
            import re
            # Remove control characters except newlines and tabs within strings
            text = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f]', '', text)
            
            data = json.loads(text)
            
            if isinstance(data, list):
                return data
            elif isinstance(data, dict) and "entities" in data:
                return data["entities"]
            else:
                return []
                
        except json.JSONDecodeError as e:
            logger.warning(f"Failed to parse LLM response: {e}")
            # Try to extract JSON using regex as fallback
            try:
                # Find array pattern
                import re
                match = re.search(r'\[[\s\S]*?\]', text)
                if match:
                    json_str = match.group(0)
                    data = json.loads(json_str)
                    if isinstance(data, list):
                        return data
            except Exception:
                pass
            return []
    
    def _create_entity_dict(self, item: dict, context: str, session_id: str) -> Optional[dict]:
        """Create entity dictionary from parsed data."""
        try:
            return {
                "type": item.get("type", "other"),
                "name": item.get("name", ""),
                "content": item.get("content", ""),
                "attributes": item.get("attributes", {}),
                "confidence": float(item.get("confidence", 0.9)),
                "importance": int(item.get("importance", 50)),
                "source": "llm",
                "context": context[:200],
                "session_id": session_id,
                "model": self.model_name,
            }
        except Exception as e:
            logger.warning(f"Failed to create entity: {e}")
            return None


# ============================================================
# Trigger Strategy
# ============================================================

class LLMTriggerStrategy:
    """Strategy for when to trigger LLM extraction."""
    
    TRIGGER_KEYWORDS = [
        # Explicit markers
        "记住", "别忘了", "重要的", "记一下",
        # Project/context keywords
        "项目", "团队", "公司", "老板", "同事",
        # Decision keywords
        "决定", "选择", "方案", "计划",
        # Background keywords
        "背景", "情况", "问题", "原因",
    ]
    
    def __init__(self, message_length_threshold: int = 100):
        self.message_length_threshold = message_length_threshold
    
    def should_trigger(self, message: str) -> Tuple[bool, str]:
        """Determine if LLM extraction should be triggered.
        
        Returns:
            (should_trigger, reason)
        """
        # Check explicit markers
        explicit = ["记住", "别忘了", "重要的", "记一下"]
        for kw in explicit:
            if kw in message:
                return True, f"explicit: {kw}"
        
        # Check context keywords
        for kw in self.TRIGGER_KEYWORDS:
            if kw in message:
                return True, f"keyword: {kw}"
        
        # Check message length
        if len(message) > self.message_length_threshold:
            return True, "long_message"
        
        return False, ""


# ============================================================
# Test
# ============================================================

async def test_llm_extraction():
    """Test LLM extraction with the active model."""
    from src.copaw.providers import ProviderManager
    
    print("=" * 60)
    print("测试 LLM 提取")
    print("=" * 60)
    
    # Get active model
    pm = ProviderManager()
    model = pm.get_active_chat_model()
    
    if not model:
        print("❌ 没有激活的模型")
        return
    
    print(f"使用模型: {getattr(model, 'model_name', 'unknown')}")
    
    # Create extractor
    extractor = LLMEntityExtractor(model)
    
    # Test cases
    test_messages = [
        "我正在做一个卫星计算项目，团队有5个人",
        "我老板叫张三，他负责产品方向",
        "我们决定用Python做后端，选择了PostgreSQL数据库",
        "记住，下周三要上线新功能",
    ]
    
    for msg in test_messages:
        print(f"\n消息: {msg}")
        entities = await extractor.extract(msg)
        print(f"提取结果: {len(entities)} 个实体")
        for e in entities:
            print(f"  - [{e['type']}] {e['name']}: {e['content']}")


if __name__ == "__main__":
    asyncio.run(test_llm_extraction())