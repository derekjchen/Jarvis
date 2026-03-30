# -*- coding: utf-8 -*-
"""
记忆模块 V1.0 测试用例

测试范围：
- 原子记忆层功能测试
- 检索功能测试
- 性能测试
"""

import os
import sys
import tempfile
import time
from datetime import datetime, timedelta

# 添加源码路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'src'))

from copaw.memory_v1.atomic_memory import AtomicMemory
from copaw.memory_v1.retriever import Retriever
from copaw.memory_v1.vector_store import VectorStore


class TestAtomicMemory:
    """原子记忆层测试"""
    
    def setup_method(self):
        """每个测试方法前执行"""
        self.temp_dir = tempfile.mkdtemp()
        self.memory = AtomicMemory(self.temp_dir)
    
    def teardown_method(self):
        """每个测试方法后执行"""
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def test_store_single_message(self):
        """测试存储单条消息"""
        message = {
            "role": "user",
            "content": "你好，这是一条测试消息"
        }
        msg_id = self.memory.store(message)
        
        assert msg_id is not None
        assert len(msg_id) == 16
        
        # 验证可以检索到
        retrieved = self.memory.retrieve_by_id(msg_id)
        assert retrieved is not None
        assert retrieved["content"] == "你好，这是一条测试消息"
    
    def test_store_with_timestamp(self):
        """测试存储带时间戳的消息"""
        message = {
            "role": "assistant",
            "content": "你好！",
            "timestamp": "2025-03-07T10:00:00"
        }
        msg_id = self.memory.store(message)
        
        retrieved = self.memory.retrieve_by_id(msg_id)
        assert retrieved["timestamp"] == "2025-03-07T10:00:00"
    
    def test_store_batch_messages(self):
        """测试批量存储消息"""
        messages = [
            {"role": "user", "content": f"消息 {i}"}
            for i in range(10)
        ]
        msg_ids = self.memory.store_batch(messages)
        
        assert len(msg_ids) == 10
        assert all(len(mid) == 16 for mid in msg_ids)
    
    def test_retrieve_by_time_range(self):
        """测试时间范围检索"""
        # 存储不同时间的消息
        base_time = datetime(2025, 3, 1, 10, 0, 0)
        for i in range(5):
            msg_time = base_time + timedelta(days=i)
            self.memory.store({
                "role": "user",
                "content": f"第{i+1}天消息",
                "timestamp": msg_time.isoformat()
            })
        
        # 检索前3天
        results = self.memory.retrieve_by_time_range(
            "2025-03-01T00:00:00",
            "2025-03-03T23:59:59"
        )
        
        assert len(results) == 3
    
    def test_retrieve_by_keyword(self):
        """测试关键词检索"""
        # 存储多条消息
        messages = [
            {"role": "user", "content": "我想了解 Python 编程"},
            {"role": "assistant", "content": "Python 是一门优秀的编程语言"},
            {"role": "user", "content": "推荐一些学习资料"},
        ]
        self.memory.store_batch(messages)
        
        # 搜索关键词
        results = self.memory.retrieve_by_keyword("Python")
        assert len(results) == 2
        
        results = self.memory.retrieve_by_keyword("学习")
        assert len(results) == 1
    
    def test_get_stats(self):
        """测试统计信息"""
        messages = [
            {"role": "user", "content": f"消息 {i}"}
            for i in range(5)
        ]
        self.memory.store_batch(messages)
        
        stats = self.memory.get_stats()
        assert stats["total_messages"] == 5
        assert stats["total_size_bytes"] > 0


class TestRetriever:
    """检索器测试"""
    
    def setup_method(self):
        """每个测试方法前执行"""
        self.temp_dir = tempfile.mkdtemp()
        self.memory = AtomicMemory(self.temp_dir)
        self.retriever = Retriever(self.memory, max_context_length=1000)
    
    def teardown_method(self):
        """每个测试方法后执行"""
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def test_keyword_search(self):
        """测试关键词检索"""
        messages = [
            {"role": "user", "content": "Python 编程"},
            {"role": "assistant", "content": "Java 编程"},
            {"role": "user", "content": "Go 编程"},
        ]
        self.memory.store_batch(messages)
        
        results = self.retriever.search("Python", search_type="keyword")
        assert len(results) == 1
        assert "Python" in results[0]["content"]
    
    def test_context_trimming(self):
        """测试上下文裁剪"""
        # 存储大量消息
        for i in range(100):
            self.memory.store({
                "role": "user",
                "content": "x" * 100  # 每条 100 字符
            })
        
        # 检索所有
        results = self.memory.retrieve_by_keyword("x")
        
        # 应用裁剪
        trimmed = self.retriever._trim_context(results, limit=5)
        
        assert len(trimmed) <= 5
    
    def test_get_context_summary(self):
        """测试上下文摘要"""
        messages = [
            {"role": "user", "content": "测试消息", "timestamp": "2025-03-07T10:00:00"}
        ]
        
        summary = self.retriever.get_context_summary(messages)
        assert "1 条" in summary
        assert "测试消息" in summary


class TestPerformance:
    """性能测试"""
    
    def setup_method(self):
        """每个测试方法前执行"""
        self.temp_dir = tempfile.mkdtemp()
        self.memory = AtomicMemory(self.temp_dir)
    
    def teardown_method(self):
        """每个测试方法后执行"""
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def test_store_latency(self):
        """测试存储延迟 < 100ms"""
        start_time = time.time()
        
        for i in range(100):
            self.memory.store({
                "role": "user",
                "content": f"测试消息 {i}"
            })
        
        elapsed = (time.time() - start_time) * 1000 / 100  # 平均每条
        assert elapsed < 100, f"存储延迟 {elapsed}ms > 100ms"
    
    def test_retrieve_latency(self):
        """测试检索延迟 < 1s"""
        # 存储大量消息
        for i in range(1000):
            self.memory.store({
                "role": "user",
                "content": f"测试消息 {i}"
            })
        
        # 测试检索延迟
        start_time = time.time()
        results = self.memory.retrieve_by_keyword("测试")
        elapsed = (time.time() - start_time) * 1000
        
        assert elapsed < 1000, f"检索延迟 {elapsed}ms > 1000ms"
    
    def test_large_message_storage(self):
        """测试大消息存储"""
        large_content = "x" * 100000  # 10万字符
        
        msg_id = self.memory.store({
            "role": "user",
            "content": large_content
        })
        
        assert msg_id is not None
        
        retrieved = self.memory.retrieve_by_id(msg_id)
        assert len(retrieved["content"]) == 100000


# 可以用 pytest 运行
if __name__ == "__main__":
    import pytest
    pytest.main([__file__, "-v"])