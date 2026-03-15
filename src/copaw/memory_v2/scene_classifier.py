# -*- coding: utf-8 -*-
"""Scene classifier for Memory V2 Milestone 2.0.

Automatically classifies conversation context into scene types:
- development: coding, implementing features
- design: architecture discussion, solution design
- decision: important decisions, direction choices
- chat: casual conversation, informal topics
- debugging: troubleshooting, error fixing
"""

import re
from typing import Optional
from .models import SceneType


class SceneClassifier:
    """Classify conversation into scene types.
    
    Uses keyword matching and pattern recognition to determine
    the type of conversation scene.
    """
    
    # 关键词权重字典
    KEYWORDS = {
        SceneType.DEVELOPMENT: {
            "high": ["代码", "实现", "开发", "写", "coding", "implement", "develop", "function", "函数", "模块", "module"],
            "medium": ["添加", "修改", "创建", "add", "modify", "create", "feature", "功能"],
            "low": ["git", "commit", "push", "pull", "分支", "branch"],
        },
        SceneType.DESIGN: {
            "high": ["设计", "架构", "方案", "design", "architecture", "方案设计", "系统设计"],
            "medium": ["考虑", "规划", "结构", "structure", "规划", "计划"],
            "low": ["思路", "想法", "方向"],
        },
        SceneType.DECISION: {
            "high": ["决定", "选择", "决策", "decide", "choice", "确定", "拍板"],
            "medium": ["最终", "确认", "确定", "final", "confirm"],
            "low": ["优先", "重要", "priority", "important"],
        },
        SceneType.DEBUGGING: {
            "high": ["错误", "bug", "调试", "debug", "问题", "报错", "error", "exception", "异常"],
            "medium": ["修复", "fix", "排查", "解决", "solve", "troubleshoot"],
            "low": ["日志", "log", "测试", "test"],
        },
        SceneType.CHAT: {
            "high": ["哈哈", "呵呵", "嗯嗯", "好的", "谢谢", "晚安", "早安", "lol", "haha", "thanks"],
            "medium": ["觉得", "感觉", "想", "觉得", "think", "feel"],
            "low": ["今天", "昨天", "明天", "天气", "生活"],
        },
    }
    
    # 场景转换关键词
    TRANSITION_KEYWORDS = [
        "对了", "顺便", "换个话题", "说起来", "另外",
        "by the way", "btw", "anyway", "change topic"
    ]
    
    def __init__(self):
        pass
    
    def classify(self, text: str) -> tuple[SceneType, float]:
        """Classify text into a scene type with confidence.
        
        Args:
            text: Input text to classify
            
        Returns:
            Tuple of (SceneType, confidence)
        """
        if not text or not text.strip():
            return SceneType.UNKNOWN, 0.0
        
        text_lower = text.lower()
        scores = {}
        
        for scene_type, weight_dict in self.KEYWORDS.items():
            score = 0.0
            for weight_level, keywords in weight_dict.items():
                multiplier = {"high": 3.0, "medium": 2.0, "low": 1.0}[weight_level]
                for keyword in keywords:
                    # 计算关键词出现次数
                    count = len(re.findall(re.escape(keyword.lower()), text_lower))
                    score += count * multiplier
            scores[scene_type] = score
        
        # 找到最高分
        if not scores or max(scores.values()) == 0:
            return SceneType.UNKNOWN, 0.0
        
        best_type = max(scores, key=scores.get)
        total_score = sum(scores.values())
        
        # 计算置信度
        if total_score > 0:
            confidence = scores[best_type] / total_score
        else:
            confidence = 0.0
        
        return best_type, confidence
    
    def classify_with_context(
        self, 
        current_text: str, 
        previous_texts: list[str] = None,
        window_size: int = 3
    ) -> tuple[SceneType, float]:
        """Classify with context from previous messages.
        
        Args:
            current_text: Current message
            previous_texts: List of previous messages
            window_size: How many previous messages to consider
            
        Returns:
            Tuple of (SceneType, confidence)
        """
        # 检查是否有场景转换
        for keyword in self.TRANSITION_KEYWORDS:
            if keyword.lower() in current_text.lower():
                # 有转换关键词，主要看当前文本
                return self.classify(current_text)
        
        # 没有转换，考虑上下文
        if previous_texts:
            all_text = " ".join(previous_texts[-window_size:] + [current_text])
        else:
            all_text = current_text
        
        return self.classify(all_text)
    
    def suggest_title(self, text: str, scene_type: SceneType) -> str:
        """Suggest a title for the scene.
        
        Args:
            text: Scene text
            scene_type: Classified scene type
            
        Returns:
            Suggested title string
        """
        # 提取关键实体作为标题
        if scene_type == SceneType.DEVELOPMENT:
            # 尝试提取功能名或模块名
            patterns = [
                r"实现(.+?)功能",
                r"开发(.+?)模块",
                r"添加(.+?)支持",
                r"implement\s+(\w+)",
                r"develop\s+(\w+)",
            ]
            for pattern in patterns:
                match = re.search(pattern, text, re.IGNORECASE)
                if match:
                    return f"开发: {match.group(1)}"
            return "开发任务"
        
        elif scene_type == SceneType.DESIGN:
            patterns = [
                r"设计(.+?)方案",
                r"(.+?)架构设计",
                r"design\s+(\w+)",
            ]
            for pattern in patterns:
                match = re.search(pattern, text, re.IGNORECASE)
                if match:
                    return f"设计: {match.group(1)}"
            return "设计讨论"
        
        elif scene_type == SceneType.DECISION:
            patterns = [
                r"决定(.+)",
                r"选择(.+)",
                r"确认(.+)",
            ]
            for pattern in patterns:
                match = re.search(pattern, text)
                if match:
                    return f"决策: {match.group(1)[:20]}"
            return "决策"
        
        elif scene_type == SceneType.DEBUGGING:
            # 尝试提取错误类型
            patterns = [
                r"修复(.+?)问题",
                r"解决(.+?)错误",
                r"debug\s+(\w+)",
            ]
            for pattern in patterns:
                match = re.search(pattern, text, re.IGNORECASE)
                if match:
                    return f"调试: {match.group(1)}"
            return "调试排查"
        
        elif scene_type == SceneType.CHAT:
            return "日常交流"
        
        else:
            return "未知场景"


def classify_scene(text: str, context: list[str] = None) -> tuple[SceneType, float, str]:
    """Convenience function for scene classification.
    
    Args:
        text: Text to classify
        context: Optional previous messages for context
        
    Returns:
        Tuple of (SceneType, confidence, suggested_title)
    """
    classifier = SceneClassifier()
    if context:
        scene_type, confidence = classifier.classify_with_context(text, context)
    else:
        scene_type, confidence = classifier.classify(text)
    title = classifier.suggest_title(text, scene_type)
    return scene_type, confidence, title

