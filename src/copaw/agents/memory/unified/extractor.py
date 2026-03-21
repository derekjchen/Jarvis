# -*- coding: utf-8 -*-
"""Unified Extractor for Memory System.

This module provides a unified extraction pipeline that integrates:
- M2.1: KeyInfo extraction (regex-based)
- M3.0: Preference extraction
- M3.0: Event extraction
- M4.0: LLM-based extraction

All extraction results are converted to the unified Entity format.
"""
import logging
import re
from datetime import datetime, date, timedelta
from typing import List, Optional, Tuple
from dataclasses import dataclass, field

from .models import Entity, EntityType, EntitySource, EntityPriority

logger = logging.getLogger(__name__)


@dataclass
class ExtractionResult:
    """Result of an extraction operation."""
    entities: List[Entity] = field(default_factory=list)
    extraction_type: str = ""
    message: str = ""


class UnifiedExtractor:
    """Unified extraction pipeline for all entity types.
    
    This class integrates all extractors and provides a single entry point
    for message processing.
    
    Usage:
        extractor = UnifiedExtractor()
        entities = await extractor.extract("我对花生过敏")
        # entities[0].type == EntityType.ALLERGY
        # entities[0].content == "花生"
    """
    
    # ============================================================
    # M2.1: KeyInfo Patterns (Safety-critical)
    # ============================================================
    
    SAFETY_PATTERNS = [
        # Allergies (highest priority)
        (r"对(.{1,8}?)过敏", "allergy", EntityPriority.CRITICAL.value),
        (r"(.{1,8}?)过敏", "allergy", EntityPriority.CRITICAL.value),
        (r"(.{1,8}?)过敏体质", "allergy", EntityPriority.CRITICAL.value),
        
        # Dietary constraints
        (r"不能吃(.{1,15})", "constraint", EntityPriority.CRITICAL.value),
        (r"不吃(.{1,15})", "constraint", EntityPriority.CRITICAL.value),
        (r"禁止(.{1,15})", "constraint", EntityPriority.CRITICAL.value),
        (r"忌口(.{1,15})", "constraint", EntityPriority.CRITICAL.value),
        
        # Health conditions
        (r"患有(.{1,15})", "constraint", EntityPriority.CRITICAL.value),
        (r"有(.{1,15})病", "constraint", EntityPriority.CRITICAL.value),
        (r"在吃(.{1,15})药", "constraint", EntityPriority.CRITICAL.value),
    ]
    
    # ============================================================
    # M3.0: Preference Patterns
    # ============================================================
    
    PREFERENCE_PATTERNS = [
        # Positive preferences
        (r"我喜欢(.{1,15}?)(?:，|。|！|？|$)", "preference", "like"),
        (r"爱(?:吃|喝|看|听)(.{1,15}?)(?:，|。|！|？|$)", "preference", "like"),
        (r"偏爱(.{1,15}?)(?:，|。|！|？|$)", "preference", "prefer"),
        (r"更(?:喜欢|爱)(.{1,15}?)(?:，|。|！|？|$)", "preference", "prefer"),
        (r"(?:很|非常|特别)喜欢(.{1,15}?)(?:，|。|！|？|$)", "preference", "like"),
        
        # Negative preferences
        (r"不喜欢(.{1,15}?)(?:，|。|！|？|$)", "dislike", "dislike"),
        (r"讨厌(.{1,15}?)(?:，|。|！|？|$)", "dislike", "dislike"),
        (r"不爱(?:吃|喝|看|听)(.{1,15}?)(?:，|。|！|？|$)", "dislike", "dislike"),
        (r"不想(?:吃|喝|看|听)(.{1,15}?)(?:，|。|！|？|$)", "dislike", "dislike"),
    ]
    
    # Preference change patterns
    CHANGE_PATTERNS = [
        (r"我现在(?:喜欢|爱)(.{1,15})", "change_to_like"),
        (r"我现在不喜欢(.{1,15})", "change_to_dislike"),
        (r"我改(?:喜欢|爱)(.{1,15})了", "change_to_like"),
        (r"以前喜欢，现在不喜欢(.{1,15})", "change_to_dislike"),
        (r"以前不喜欢，现在喜欢(.{1,15})", "change_to_like"),
    ]
    
    # ============================================================
    # M3.0: Event Patterns
    # ============================================================
    
    DATE_PATTERNS = [
        (r"今天", 0),
        (r"明天", 1),
        (r"后天", 2),
        (r"大后天", 3),
        (r"下周([一二三四五六日天])", "next_week_day"),
        (r"这周([一二三四五六日天])", "this_week_day"),
        (r"(\d{1,2})月(\d{1,2})[日号]", "month_day"),
        (r"(\d{4})年(\d{1,2})月(\d{1,2})[日号]?", "full_date"),
    ]
    
    EVENT_KEYWORDS = {
        "milestone": ["毕业", "入职", "升职", "结婚", "达成", "完成"],
        "deadline": ["截止", "到期", "最后期限", "之前要"],
        "appointment": ["约会", "会议", "见面", "预约", "开会"],
        "travel": ["旅行", "出差", "旅游", "度假"],
        "project": ["项目", "上线", "发布", "验收"],
    }
    
    # ============================================================
    # M4.0: LLM Trigger Keywords
    # ============================================================
    
    LLM_TRIGGER_KEYWORDS = [
        "项目", "老板", "团队", "同事", "公司",
        "决定", "选择", "方案", "计划",
        "背景", "情况", "问题", "原因",
        "记住", "别忘了", "重要的",
    ]
    
    # Topic keywords for categorization
    TOPIC_KEYWORDS = {
        "food": ["吃", "喝", "菜", "餐", "食物", "味道", "口味", "辣", "甜", "咸", "酸"],
        "drink": ["喝", "饮", "茶", "咖啡", "酒", "饮料"],
        "color": ["颜色", "色", "蓝", "红", "绿", "黄", "白", "黑", "紫"],
        "music": ["音乐", "歌", "曲", "听", "乐队", "歌手"],
        "movie": ["电影", "剧", "看", "演员", "导演"],
        "tech": ["技术", "框架", "语言", "工具", "软件", "系统"],
        "work": ["工作", "项目", "团队", "公司"],
    }
    
    def __init__(self, session_id: str = ""):
        """Initialize the unified extractor.
        
        Args:
            session_id: Current session ID for tracking
        """
        self.session_id = session_id
        self._compiled_safety = [(re.compile(p), t, pr) for p, t, pr in self.SAFETY_PATTERNS]
        self._compiled_prefs = [(re.compile(p), t, s) for p, t, s in self.PREFERENCE_PATTERNS]
        self._compiled_changes = [(re.compile(p), t) for p, t in self.CHANGE_PATTERNS]
    
    def extract(self, message: str, msg_id: str = "") -> ExtractionResult:
        """Extract all entities from a message.
        
        This is the main entry point for extraction.
        
        Args:
            message: The message to extract from
            msg_id: Message ID for tracking
        
        Returns:
            ExtractionResult with extracted entities
        """
        entities = []
        
        # 1. Extract safety-critical info (M2.1)
        safety_entities = self._extract_safety(message, msg_id)
        entities.extend(safety_entities)
        
        # 2. Extract preferences (M3.0)
        pref_entities = self._extract_preferences(message, msg_id)
        entities.extend(pref_entities)
        
        # 3. Extract events (M3.0)
        event_entities = self._extract_events(message, msg_id)
        entities.extend(event_entities)
        
        # 4. Extract decisions
        decision_entities = self._extract_decisions(message, msg_id)
        entities.extend(decision_entities)
        
        # 5. Extract contact info
        contact_entities = self._extract_contacts(message, msg_id)
        entities.extend(contact_entities)
        
        logger.info(f"Extracted {len(entities)} entities from message")
        
        return ExtractionResult(
            entities=entities,
            extraction_type="unified",
            message=f"Extracted {len(entities)} entities"
        )
    
    def _extract_safety(self, message: str, msg_id: str) -> List[Entity]:
        """Extract safety-critical information.
        
        M2.1 patterns for allergies, constraints, health conditions.
        These have highest priority (100) and must always be injected.
        """
        entities = []
        
        for pattern, info_type, priority in self._compiled_safety:
            matches = pattern.findall(message)
            for match in matches:
                content = self._clean_content(match)
                if content and len(content) >= 1:
                    entity_type = EntityType.ALLERGY if info_type == "allergy" else EntityType.CONSTRAINT
                    
                    entity = Entity(
                        type=entity_type,
                        name=content,
                        content=f"用户{info_type}: {content}",
                        priority=priority,
                        source=EntitySource.REGEX,
                        confidence=1.0,
                        context=message,
                        msg_id=msg_id,
                        session_id=self.session_id,
                    )
                    entities.append(entity)
                    logger.debug(f"Extracted safety entity: {content} (type={entity_type})")
        
        return entities
    
    def _extract_preferences(self, message: str, msg_id: str) -> List[Entity]:
        """Extract user preferences.
        
        M3.0 patterns for likes, dislikes, and preference changes.
        """
        entities = []
        now = datetime.now()
        
        # Check for preference changes first
        is_change = False
        for pattern, change_type in self._compiled_changes:
            if pattern.search(message):
                is_change = True
                break
        
        # Extract preferences
        for pattern, pref_type, sentiment in self._compiled_prefs:
            matches = pattern.findall(message)
            for match in matches:
                content = self._clean_content(match)
                if content and len(content) >= 2:
                    entity_type = EntityType.PREFERENCE if sentiment == "like" or sentiment == "prefer" else EntityType.DISLIKE
                    
                    topic = self._infer_topic(content)
                    
                    # Determine priority based on change
                    priority = EntityPriority.HIGH.value if is_change else EntityPriority.MEDIUM.value
                    
                    entity = Entity(
                        type=entity_type,
                        name=content,
                        content=content,
                        category=topic,
                        priority=priority,
                        source=EntitySource.REGEX,
                        confidence=1.0,
                        context=message,
                        msg_id=msg_id,
                        session_id=self.session_id,
                        tags=[topic, sentiment],
                        attributes={
                            "sentiment": sentiment,
                            "is_change": is_change,
                        }
                    )
                    entities.append(entity)
                    logger.debug(f"Extracted preference: {content} (sentiment={sentiment})")
        
        return entities
    
    def _extract_events(self, message: str, msg_id: str) -> List[Entity]:
        """Extract events and milestones.
        
        M3.0 patterns for dates and event types.
        """
        entities = []
        
        # Extract dates
        dates = self._extract_dates(message)
        
        # Determine event type
        event_type = self._detect_event_type(message)
        importance = self._detect_importance(message)
        
        # Extract title
        title = self._extract_event_title(message)
        
        if title and dates:
            for event_date in dates:
                priority = EntityPriority.HIGH.value if importance == "critical" else EntityPriority.MEDIUM.value
                
                entity = Entity(
                    type=EntityType.EVENT if event_type != "milestone" else EntityType.MILESTONE,
                    name=title,
                    content=f"{title} ({event_date})",
                    priority=priority,
                    source=EntitySource.REGEX,
                    confidence=0.8,
                    context=message,
                    msg_id=msg_id,
                    session_id=self.session_id,
                    attributes={
                        "event_date": str(event_date),
                        "event_type": event_type,
                        "importance": importance,
                    }
                )
                entities.append(entity)
                logger.debug(f"Extracted event: {title} ({event_date})")
        
        return entities
    
    def _extract_decisions(self, message: str, msg_id: str) -> List[Entity]:
        """Extract important decisions."""
        entities = []
        
        decision_patterns = [
            r"决定(.{1,30})",
            r"确定了(.{1,30})",
            r"选定(.{1,30})",
            r"最终方案是(.{1,30})",
        ]
        
        for pattern in decision_patterns:
            match = re.search(pattern, message)
            if match:
                content = self._clean_content(match.group(1))
                if content:
                    entity = Entity(
                        type=EntityType.DECISION,
                        name=content,
                        content=f"用户决定: {content}",
                        priority=EntityPriority.HIGH.value,
                        source=EntitySource.REGEX,
                        confidence=0.9,
                        context=message,
                        msg_id=msg_id,
                        session_id=self.session_id,
                    )
                    entities.append(entity)
                    logger.debug(f"Extracted decision: {content}")
        
        return entities
    
    def _extract_contacts(self, message: str, msg_id: str) -> List[Entity]:
        """Extract contact information."""
        entities = []
        
        # Phone numbers
        phone_pattern = r"电话[号码]?[是为]?(\d{11})"
        for match in re.finditer(phone_pattern, message):
            phone = match.group(1)
            entity = Entity(
                type=EntityType.CONTACT,
                name=f"电话: {phone}",
                content=phone,
                category="phone",
                priority=EntityPriority.LOW.value,
                source=EntitySource.REGEX,
                confidence=1.0,
                context=message,
                msg_id=msg_id,
                session_id=self.session_id,
            )
            entities.append(entity)
        
        # Email
        email_pattern = r"邮箱[是为]?([\w\.]+@[\w\.]+)"
        for match in re.finditer(email_pattern, message):
            email = match.group(1)
            entity = Entity(
                type=EntityType.CONTACT,
                name=f"邮箱: {email}",
                content=email,
                category="email",
                priority=EntityPriority.LOW.value,
                source=EntitySource.REGEX,
                confidence=1.0,
                context=message,
                msg_id=msg_id,
                session_id=self.session_id,
            )
            entities.append(entity)
        
        return entities
    
    def _extract_dates(self, text: str) -> List[date]:
        """Extract dates from text."""
        dates = []
        today = date.today()
        
        for pattern, value in self.DATE_PATTERNS:
            match = re.search(pattern, text)
            if match:
                if isinstance(value, int):
                    dates.append(today + timedelta(days=value))
                elif value == "next_week_day":
                    day_map = {"一": 0, "二": 1, "三": 2, "四": 3, "五": 4, "六": 5, "日": 6, "天": 6}
                    target_day = day_map.get(match.group(1), 0)
                    current_day = today.weekday()
                    days_ahead = target_day - current_day + 7
                    dates.append(today + timedelta(days=days_ahead))
                elif value == "this_week_day":
                    day_map = {"一": 0, "二": 1, "三": 2, "四": 3, "五": 4, "六": 5, "日": 6, "天": 6}
                    target_day = day_map.get(match.group(1), 0)
                    current_day = today.weekday()
                    days_ahead = target_day - current_day
                    if days_ahead < 0:
                        days_ahead += 7
                    dates.append(today + timedelta(days=days_ahead))
                elif value == "month_day":
                    month = int(match.group(1))
                    day = int(match.group(2))
                    try:
                        event_date = date(today.year, month, day)
                        if event_date < today:
                            event_date = date(today.year + 1, month, day)
                        dates.append(event_date)
                    except ValueError:
                        pass
                elif value == "full_date":
                    year = int(match.group(1))
                    month = int(match.group(2))
                    day = int(match.group(3))
                    try:
                        dates.append(date(year, month, day))
                    except ValueError:
                        pass
        
        return dates
    
    def _detect_event_type(self, text: str) -> str:
        """Detect event type from text."""
        for event_type, keywords in self.EVENT_KEYWORDS.items():
            for keyword in keywords:
                if keyword in text:
                    return event_type
        return "other"
    
    def _detect_importance(self, text: str) -> str:
        """Detect importance level from text."""
        if any(k in text for k in ["必须", "重要", "关键", "不能错过"]):
            return "critical"
        if any(k in text for k in ["记得", "别忘了", "提醒我"]):
            return "high"
        return "medium"
    
    def _extract_event_title(self, text: str) -> str:
        """Extract event title from text."""
        clean_text = text
        for prefix in ["我", "我的", "我要", "记得", "别忘了", "提醒我"]:
            if clean_text.startswith(prefix):
                clean_text = clean_text[len(prefix):]
        
        for pattern, _ in self.DATE_PATTERNS:
            clean_text = re.sub(pattern, "", clean_text)
        
        clean_text = clean_text.strip()
        
        for stop in ["，", "。", "！", "？", "和", "还有"]:
            if stop in clean_text:
                clean_text = clean_text.split(stop)[0]
                break
        
        return clean_text[:50] if clean_text else ""
    
    def _clean_content(self, content: str) -> str:
        """Clean extracted content."""
        content = content.strip()
        
        for prefix in ["了", "的", "这个", "那个"]:
            while content.startswith(prefix):
                content = content[1:]
        
        for suffix in ["了", "的", "吧", "啊", "哦"]:
            while content.endswith(suffix):
                content = content[:-1]
        
        return content.strip()
    
    def _infer_topic(self, content: str) -> str:
        """Infer the topic category from content."""
        content_lower = content.lower()
        
        for topic, keywords in self.TOPIC_KEYWORDS.items():
            for keyword in keywords:
                if keyword in content_lower:
                    return topic
        
        return "other"
    
    def should_trigger_llm(self, message: str) -> Tuple[bool, str]:
        """Determine if LLM extraction should be triggered.
        
        M4.0 trigger strategy for cost optimization.
        
        Args:
            message: The message to analyze
        
        Returns:
            Tuple of (should_trigger, reason)
        """
        # Check for explicit markers
        explicit_markers = ["记住", "别忘了", "重要的", "记一下"]
        for marker in explicit_markers:
            if marker in message:
                return True, f"Explicit marker: {marker}"
        
        # Check for LLM trigger keywords
        for keyword in self.LLM_TRIGGER_KEYWORDS:
            if keyword in message:
                return True, f"Trigger keyword: {keyword}"
        
        # Check message length
        if len(message) > 200:
            return True, "Long message, may contain complex info"
        
        return False, "No trigger condition met"


# Convenience function
def extract_entities(message: str, session_id: str = "", msg_id: str = "") -> List[Entity]:
    """Extract entities from a message.
    
    Args:
        message: The message to extract from
        session_id: Current session ID
        msg_id: Message ID
    
    Returns:
        List of extracted entities
    """
    extractor = UnifiedExtractor(session_id)
    result = extractor.extract(message, msg_id)
    return result.entities