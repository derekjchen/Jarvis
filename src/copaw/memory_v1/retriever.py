# -*- coding: utf-8 -*-
"""
检索器 - Retriever

提供基础的检索功能：
- 关键词检索
- 时间范围检索
- 语义检索（向量）

上下文裁剪器：确保返回结果不超过模型窗口限制
"""

from typing import List, Dict, Any, Optional
from datetime import datetime
import re


class Retriever:
    """记忆检索器"""
    
    def __init__(
        self, 
        atomic_memory,
        max_context_length: int = 4000
    ):
        """
        初始化检索器
        
        Args:
            atomic_memory: 原子记忆层实例
            max_context_length: 最大上下文长度（字符数）
        """
        self.atomic_memory = atomic_memory
        self.max_context_length = max_context_length
    
    def search(
        self,
        query: str,
        search_type: str = "keyword",
        start_time: Optional[str] = None,
        end_time: Optional[str] = None,
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """
        统一检索接口
        
        Args:
            query: 查询内容
            search_type: 检索类型 (keyword/time/semantic)
            start_time: 开始时间（时间范围检索）
            end_time: 结束时间（时间范围检索）
            limit: 返回数量限制
        
        Returns:
            messages: 消息列表
        """
        if search_type == "keyword":
            messages = self.atomic_memory.retrieve_by_keyword(query)
        elif search_type == "time":
            if not start_time or not end_time:
                raise ValueError("时间范围检索需要 start_time 和 end_time")
            messages = self.atomic_memory.retrieve_by_time_range(start_time, end_time)
        else:
            raise ValueError(f"不支持的检索类型: {search_type}")
        
        # 应用上下文裁剪
        messages = self._trim_context(messages, limit)
        
        return messages
    
    def _trim_context(
        self, 
        messages: List[Dict[str, Any]], 
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """
        上下文裁剪 - 确保不超过模型窗口
        
        Args:
            messages: 消息列表
            limit: 最大消息数量
        
        Returns:
            trimmed_messages: 裁剪后的消息列表
        """
        if not messages:
            return []
        
        # 限制消息数量
        messages = messages[:limit]
        
        # 限制总字符数
        total_length = 0
        trimmed = []
        
        for msg in reversed(messages):  # 从最新的开始
            content = msg.get("content", "")
            if isinstance(content, str):
                msg_length = len(content)
            else:
                msg_length = len(str(content))
            
            if total_length + msg_length <= self.max_context_length:
                trimmed.insert(0, msg)
                total_length += msg_length
            else:
                break
        
        return trimmed
    
    def get_context_summary(
        self,
        messages: List[Dict[str, Any]]
    ) -> str:
        """
        生成上下文摘要
        
        Args:
            messages: 消息列表
        
        Returns:
            summary: 摘要文本
        """
        if not messages:
            return "无相关记忆"
        
        summary_parts = []
        summary_parts.append(f"找到 {len(messages)} 条相关记忆：")
        
        for i, msg in enumerate(messages[:5], 1):  # 只显示前5条
            role = msg.get("role", "unknown")
            content = msg.get("content", "")
            timestamp = msg.get("timestamp", "")
            
            if isinstance(content, str):
                content_preview = content[:100] + "..." if len(content) > 100 else content
            else:
                content_preview = str(content)[:100]
            
            summary_parts.append(f"{i}. [{timestamp}] {role}: {content_preview}")
        
        if len(messages) > 5:
            summary_parts.append(f"... 还有 {len(messages) - 5} 条")
        
        return "\n".join(summary_parts)


class ContextWindowManager:
    """上下文窗口管理器"""
    
    def __init__(self, max_tokens: int = 4000):
        """
        初始化
        
        Args:
            max_tokens: 最大 token 数量
        """
        self.max_tokens = max_tokens
        # 简化的 token 估算：中文约 1.5 字符/token，英文约 4 字符/token
        self.chars_per_token = 2.0
    
    def estimate_tokens(self, text: str) -> int:
        """
        估算文本的 token 数量
        
        Args:
            text: 文本内容
        
        Returns:
            token_count: 估算的 token 数量
        """
        return int(len(text) / self.chars_per_token)
    
    def fit_messages(
        self, 
        messages: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        调整消息列表以适应上下文窗口
        
        Args:
            messages: 消息列表
        
        Returns:
            fitted_messages: 调整后的消息列表
        """
        fitted = []
        total_tokens = 0
        
        # 从最新的消息开始添加
        for msg in reversed(messages):
            content = msg.get("content", "")
            if isinstance(content, str):
                msg_tokens = self.estimate_tokens(content)
            else:
                msg_tokens = self.estimate_tokens(str(content))
            
            if total_tokens + msg_tokens <= self.max_tokens:
                fitted.insert(0, msg)
                total_tokens += msg_tokens
            else:
                break
        
        return fitted