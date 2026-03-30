# -*- coding: utf-8 -*-
"""Task-based intelligent model routing.

This module provides dynamic model selection based on task characteristics,
allowing the agent to use the most suitable model for each task type.

Design:
1. TaskClassifier: Analyzes incoming task to determine its type
2. ModelSelector: Maps task type to optimal model
3. DynamicModelSwitcher: Handles model switching during task execution

Example flow:
    User: "帮我分析一下这个复杂的系统架构问题"
    → TaskClassifier detects: COMPLEX_REASONING
    → ModelSelector selects: qwen3-max
    → Switch to qwen3-max, execute task
    → Return result
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional, Callable

logger = logging.getLogger(__name__)


class TaskType(Enum):
    """Classification of task types for model routing."""
    
    # Complex tasks requiring strong reasoning
    COMPLEX_REASONING = "complex_reasoning"
    
    # Code-related tasks
    CODE_GENERATION = "code_generation"
    CODE_DEBUGGING = "code_debugging"
    CODE_REVIEW = "code_review"
    
    # Simple/fast tasks
    SIMPLE_QA = "simple_qa"
    QUICK_COMMAND = "quick_command"
    
    # Document/long text tasks
    LONG_DOCUMENT = "long_document"
    
    # Memory/reflection tasks
    MEMORY_EVOLUTION = "memory_evolution"
    
    # Default/fallback
    GENERAL = "general"


@dataclass
class TaskAnalysis:
    """Result of task analysis."""
    
    task_type: TaskType
    confidence: float = 0.8
    reasons: list[str] = field(default_factory=list)
    keywords: list[str] = field(default_factory=list)
    
    # Estimated complexity (1-10)
    complexity_score: int = 5
    
    # Whether task requires tools
    requires_tools: bool = True
    
    # Estimated token usage
    estimated_tokens: int = 1000


@dataclass
class ModelSelection:
    """Result of model selection."""
    
    model_id: str
    provider_id: str
    reasons: list[str] = field(default_factory=list)
    
    # Estimated cost tier (1=cheap, 3=expensive)
    cost_tier: int = 2
    
    # Expected quality (1-10)
    expected_quality: int = 8


class TaskClassifier:
    """Analyzes tasks to determine their type and characteristics."""
    
    # Keywords/patterns for each task type
    TASK_PATTERNS = {
        TaskType.COMPLEX_REASONING: [
            r"分析.*问题",
            r"深入.*研究",
            r"复杂.*逻辑",
            r"多步骤",
            r"系统性",
            r"架构.*设计",
            r"决策.*分析",
            r"权衡.*方案",
            r"比较.*优劣",
            r"综合.*考虑",
            # English patterns
            r"analyze.*complex",
            r"deep.*analysis",
            r"architecture",
            r"decision",
            r"step-by-step",
        ],
        
        TaskType.CODE_GENERATION: [
            r"写.*代码",
            r"生成.*脚本",
            r"实现.*功能",
            r"创建.*模块",
            r"开发.*组件",
            r"编写.*程序",
            # English
            r"write.*code",
            r"generate.*script",
            r"implement",
            r"create.*module",
        ],
        
        TaskType.CODE_DEBUGGING: [
            r"调试",
            r"修复.*bug",
            r"解决.*错误",
            r"排查.*问题",
            r"为什么.*不工作",
            r"报错",
            r"异常",
            # English
            r"debug",
            r"fix.*bug",
            r"error",
            r"why.*not.*work",
        ],
        
        TaskType.CODE_REVIEW: [
            r"检查.*代码",
            r"审查",
            r"优化.*代码",
            r"重构",
            r"改进.*实现",
            r"代码.*质量",
            # English
            r"review.*code",
            r"optimize",
            r"refactor",
            r"improve",
        ],
        
        TaskType.SIMPLE_QA: [
            r"是什么",
            r"怎么用",
            r"简单.*问",
            r"快速",
            r"查询",
            r"获取",
            # English
            r"what is",
            r"how to",
            r"quick",
            r"simple",
        ],
        
        TaskType.QUICK_COMMAND: [
            r"执行",
            r"运行",
            r"查看.*文件",
            r"读取",
            r"列出",
            # Short command indicators
            # (messages < 20 chars)
        ],
        
        TaskType.LONG_DOCUMENT: [
            r"文档",
            r"长文",
            r"报告",
            r"总结.*全文",
            r"分析.*内容",
            r"处理.*文本",
            # English
            r"document",
            r"long.*text",
            r"report",
            r"summarize",
        ],
        
        TaskType.MEMORY_EVOLUTION: [
            r"记忆.*进化",
            r"evolve",
            r"进化",
            r"质量.*评估",
        ],
    }
    
    # Complexity indicators
    COMPLEXITY_INDICATORS = {
        "high": [
            r"深入", r"详细", r"全面", r"系统性",
            r"架构", r"设计", r"优化", r"重构",
        ],
        "low": [
            r"简单", r"快速", r"简要", r"概要",
        ],
    }
    
    def analyze(
        self,
        text: str,
        *,
        context: Optional[dict] = None,
        tool_count: int = 0,
    ) -> TaskAnalysis:
        """Analyze a task text to determine its type.
        
        Args:
            text: The task/query text
            context: Additional context (previous messages, etc.)
            tool_count: Number of tools available
            
        Returns:
            TaskAnalysis with type, confidence, and characteristics
        """
        text_lower = text.lower()
        matched_types: list[tuple[TaskType, float, list[str]]] = []
        matched_keywords: list[str] = []
        
        # Match patterns for each task type
        for task_type, patterns in self.TASK_PATTERNS.items():
            matches = []
            for pattern in patterns:
                if re.search(pattern, text_lower):
                    matches.append(pattern)
            
            if matches:
                confidence = min(0.9, 0.5 + len(matches) * 0.15)
                matched_types.append((task_type, confidence, matches))
                matched_keywords.extend(matches)
        
        # Determine primary task type
        if matched_types:
            # Sort by confidence, pick highest
            matched_types.sort(key=lambda x: x[1], reverse=True)
            primary_type, confidence, reasons = matched_types[0]
        else:
            primary_type = TaskType.GENERAL
            confidence = 0.5
            reasons = ["no specific pattern matched"]
        
        # Estimate complexity
        complexity_score = 5  # Default medium
        for indicator in self.COMPLEXITY_INDICATORS["high"]:
            if re.search(indicator, text_lower):
                complexity_score = min(10, complexity_score + 2)
        for indicator in self.COMPLEXITY_INDICATORS["low"]:
            if re.search(indicator, text_lower):
                complexity_score = max(1, complexity_score - 2)
        
        # Check for code-related keywords more carefully
        code_keywords = ["代码", "脚本", "实现", "编写", "开发", "code", "script", "implement", "write"]
        if any(kw in text_lower for kw in code_keywords):
            if primary_type in [TaskType.GENERAL, TaskType.QUICK_COMMAND, TaskType.SIMPLE_QA]:
                primary_type = TaskType.CODE_GENERATION
                reasons.append("code-related keywords detected")
                complexity_score = max(5, complexity_score)  # Code tasks are at least medium complexity
        
        # Adjust for message length
        if len(text) > 500:
            complexity_score = min(10, complexity_score + 1)
        elif len(text) < 50:
            complexity_score = max(1, complexity_score - 1)
            # Don't downgrade code tasks based on length
            if primary_type not in [TaskType.CODE_GENERATION, TaskType.CODE_DEBUGGING]:
                if primary_type == TaskType.GENERAL:
                    primary_type = TaskType.QUICK_COMMAND
                    reasons.append("short message")
        
        # Estimate tokens
        estimated_tokens = len(text) * 2  # Rough estimate
        if complexity_score > 7:
            estimated_tokens *= 3  # Complex tasks need more context
        
        return TaskAnalysis(
            task_type=primary_type,
            confidence=confidence,
            reasons=reasons,
            keywords=matched_keywords,
            complexity_score=complexity_score,
            requires_tools=tool_count > 0,
            estimated_tokens=estimated_tokens,
        )


class ModelSelector:
    """Selects optimal model based on task analysis."""
    
    # Model recommendations for each task type
    # Format: (model_id, cost_tier, expected_quality)
    MODEL_RECOMMENDATIONS = {
        # GLM-5: 逻辑推理最强 (MMLU/MATH/GPQA 高分)
        TaskType.COMPLEX_REASONING: ("glm-5", 3, 9),
        
        # Qwen3 Coder Next: 代码生成最强 (HumanEval/MBPP 高分)
        TaskType.CODE_GENERATION: ("qwen3-coder-next", 2, 9),
        
        # GLM-5: 调试需要推理 + 代码理解
        TaskType.CODE_DEBUGGING: ("glm-5", 3, 9),
        
        # Qwen3 Coder Plus: 代码审查性价比高
        TaskType.CODE_REVIEW: ("qwen3-coder-plus", 2, 8),
        
        # Qwen3.5 Plus: 简单问答性价比最高
        TaskType.SIMPLE_QA: ("qwen3.5-plus", 1, 7),
        
        # Qwen3.5 Plus: 快速命令响应快
        TaskType.QUICK_COMMAND: ("qwen3.5-plus", 1, 6),
        
        # Kimi K2.5: 长文档理解最强 (128K context benchmark 高分)
        TaskType.LONG_DOCUMENT: ("kimi-k2.5", 2, 9),
        
        # Qwen3.5 Plus: 后台任务用便宜模型
        TaskType.MEMORY_EVOLUTION: ("qwen3.5-plus", 1, 7),
        
        # GLM-5: 默认用推理强的模型
        TaskType.GENERAL: ("glm-5", 2, 8),
    }

    # Provider ID for all models
    DEFAULT_PROVIDER = "aliyun-codingplan"
    
    def select(
        self,
        analysis: TaskAnalysis,
        *,
        current_model: Optional[str] = None,
        prefer_cheaper: bool = False,
    ) -> ModelSelection:
        """Select optimal model for the task.
        
        Args:
            analysis: Task analysis result
            current_model: Currently active model (for comparison)
            prefer_cheaper: Whether to prefer cheaper models
            
        Returns:
            ModelSelection with recommended model
        """
        # Get base recommendation
        model_id, cost_tier, quality = self.MODEL_RECOMMENDATIONS.get(
            analysis.task_type,
            ("qwen3-max", 2, 8)
        )
        
        # Adjust based on preferences
        if prefer_cheaper and analysis.complexity_score < 5:
            # Use cheaper model for simple tasks
            model_id = "qwen3.5-plus"
            cost_tier = 1
        
        # Build reasons
        reasons = [
            f"task_type: {analysis.task_type.value}",
            f"complexity: {analysis.complexity_score}/10",
            f"model_strength: {quality}/10",
        ]
        
        if analysis.keywords:
            reasons.append(f"keywords: {', '.join(analysis.keywords[:3])}")
        
        return ModelSelection(
            model_id=model_id,
            provider_id=self.DEFAULT_PROVIDER,
            reasons=reasons,
            cost_tier=cost_tier,
            expected_quality=quality,
        )


class DynamicModelSwitcher:
    """Handles dynamic model switching during task execution."""
    
    def __init__(
        self,
        provider_manager: Any = None,
    ):
        """Initialize the switcher.
        
        Args:
            provider_manager: ProviderManager instance for model switching
        """
        self.provider_manager = provider_manager
        self.classifier = TaskClassifier()
        self.selector = ModelSelector()
        
        # Track model usage for logging
        self._switch_history: list[dict] = []
        
    async def switch_for_task(
        self,
        task_text: str,
        *,
        context: Optional[dict] = None,
        force_model: Optional[str] = None,
    ) -> tuple[str, TaskAnalysis, ModelSelection]:
        """Analyze task and switch to optimal model.
        
        Args:
            task_text: The task text to analyze
            context: Additional context
            force_model: Force specific model (skip analysis)
            
        Returns:
            Tuple of (new_model_id, analysis, selection)
        """
        if force_model:
            # Skip analysis, use specified model
            analysis = TaskAnalysis(
                task_type=TaskType.GENERAL,
                reasons=["forced model"],
            )
            selection = ModelSelection(
                model_id=force_model,
                provider_id=self.selector.DEFAULT_PROVIDER,
                reasons=["user specified"],
            )
        else:
            # Analyze task
            analysis = self.classifier.analyze(task_text, context=context or {})
            
            # Select model
            selection = self.selector.select(analysis)
        
        # Perform switch if provider manager available
        new_model_id = selection.model_id
        
        if self.provider_manager:
            try:
                await self.provider_manager.activate_model(
                    selection.provider_id,
                    selection.model_id,
                )
                logger.info(
                    "Model switched for task: %s → %s (type: %s, complexity: %d)",
                    getattr(self.provider_manager.get_active_model(), "model", "unknown"),
                    new_model_id,
                    analysis.task_type.value,
                    analysis.complexity_score,
                )
                
                # Record switch
                self._switch_history.append({
                    "from_model": getattr(
                        self.provider_manager.get_active_model(),
                        "model",
                        "unknown"
                    ),
                    "to_model": new_model_id,
                    "task_type": analysis.task_type.value,
                    "reasons": selection.reasons,
                })
                
            except Exception as e:
                logger.warning("Failed to switch model: %s", e)
        
        return new_model_id, analysis, selection
    
    def get_switch_history(self) -> list[dict]:
        """Get history of model switches."""
        return self._switch_history.copy()
    
    def clear_history(self) -> None:
        """Clear switch history."""
        self._switch_history.clear()


# Convenience function for quick task-based model selection
def recommend_model_for_task(task_text: str) -> str:
    """Quick function to get recommended model for a task.
    
    Args:
        task_text: The task text
        
    Returns:
        Recommended model ID
    """
    classifier = TaskClassifier()
    selector = ModelSelector()
    
    analysis = classifier.analyze(task_text)
    selection = selector.select(analysis)
    
    return selection.model_id


__all__ = [
    "TaskType",
    "TaskAnalysis",
    "ModelSelection",
    "TaskClassifier",
    "ModelSelector",
    "DynamicModelSwitcher",
    "recommend_model_for_task",
]