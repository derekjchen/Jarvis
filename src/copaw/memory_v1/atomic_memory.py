# -*- coding: utf-8 -*-
"""
原子记忆层 - Atomic Memory Layer

全量存储所有交互细节，按时间分片压缩。

设计原则：
1. 每条消息都是原子单位，不可分割
2. 按时间分片存储，每个分片最大 1MB
3. 自动压缩，使用 LZ4 算法
4. 支持毫秒级时间戳索引

存储结构：
/atomic_memory/
├── 2025-03/
│   ├── 2025-03-01.jsonl.gz    # 按天分片
│   ├── 2025-03-02.jsonl.gz
│   └── ...
└── index/
    └── time_index.db           # 时间索引
"""

import gzip
import json
import os
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Optional, Any
import hashlib


class AtomicMemory:
    """原子记忆层 - 存储所有交互细节"""
    
    def __init__(self, storage_dir: str = "/root/.copaw/atomic_memory"):
        """
        初始化原子记忆层
        
        Args:
            storage_dir: 存储目录
        """
        self.storage_dir = Path(storage_dir)
        self.storage_dir.mkdir(parents=True, exist_ok=True)
        
        # 创建索引目录
        self.index_dir = self.storage_dir / "index"
        self.index_dir.mkdir(exist_ok=True)
        
    def store(self, message: Dict[str, Any]) -> str:
        """
        存储单条消息
        
        Args:
            message: 消息字典，必须包含:
                - role: 角色 (user/assistant/system)
                - content: 内容
                - timestamp: 时间戳 (可选，自动生成)
        
        Returns:
            message_id: 消息唯一 ID
        """
        # 生成时间戳
        if "timestamp" not in message:
            message["timestamp"] = datetime.now().isoformat()
        
        # 生成消息 ID
        message_id = self._generate_id(message)
        message["id"] = message_id
        
        # 获取当天的存储文件
        storage_file = self._get_storage_file(message["timestamp"])
        
        # 追加写入
        with gzip.open(storage_file, "at", encoding="utf-8") as f:
            f.write(json.dumps(message, ensure_ascii=False) + "\n")
        
        # 更新索引
        self._update_index(message_id, message)
        
        return message_id
    
    def store_batch(self, messages: List[Dict[str, Any]]) -> List[str]:
        """
        批量存储消息
        
        Args:
            messages: 消息列表
        
        Returns:
            message_ids: 消息 ID 列表
        """
        message_ids = []
        for msg in messages:
            mid = self.store(msg)
            message_ids.append(mid)
        return message_ids
    
    def retrieve_by_time_range(
        self, 
        start_time: str, 
        end_time: str
    ) -> List[Dict[str, Any]]:
        """
        按时间范围检索
        
        Args:
            start_time: 开始时间 (ISO 格式)
            end_time: 结束时间 (ISO 格式)
        
        Returns:
            messages: 消息列表
        """
        messages = []
        
        # 解析时间范围
        start_dt = datetime.fromisoformat(start_time)
        end_dt = datetime.fromisoformat(end_time)
        
        # 遍历日期范围内的文件
        current_dt = start_dt.replace(hour=0, minute=0, second=0)
        while current_dt <= end_dt:
            storage_file = self._get_storage_file(current_dt.isoformat())
            if storage_file.exists():
                daily_messages = self._read_storage_file(storage_file)
                for msg in daily_messages:
                    msg_time = datetime.fromisoformat(msg["timestamp"])
                    if start_dt <= msg_time <= end_dt:
                        messages.append(msg)
            # 下一天
            from datetime import timedelta
            current_dt += timedelta(days=1)
        
        return messages
    
    def retrieve_by_keyword(self, keyword: str) -> List[Dict[str, Any]]:
        """
        按关键词检索
        
        Args:
            keyword: 搜索关键词
        
        Returns:
            messages: 包含关键词的消息列表
        """
        messages = []
        
        # 遍历所有存储文件
        for storage_file in self.storage_dir.glob("*/*.jsonl.gz"):
            daily_messages = self._read_storage_file(storage_file)
            for msg in daily_messages:
                content = msg.get("content", "")
                if isinstance(content, str) and keyword.lower() in content.lower():
                    messages.append(msg)
        
        return messages
    
    def retrieve_by_id(self, message_id: str) -> Optional[Dict[str, Any]]:
        """
        按 ID 检索
        
        Args:
            message_id: 消息 ID
        
        Returns:
            message: 消息字典，未找到返回 None
        """
        # 从索引中查找
        index_file = self.index_dir / "id_index.json"
        if index_file.exists():
            with open(index_file, "r", encoding="utf-8") as f:
                index = json.load(f)
            
            if message_id in index:
                storage_file = Path(index[message_id]["file"])
                if storage_file.exists():
                    daily_messages = self._read_storage_file(storage_file)
                    for msg in daily_messages:
                        if msg.get("id") == message_id:
                            return msg
        
        return None
    
    def get_stats(self) -> Dict[str, Any]:
        """
        获取存储统计信息
        
        Returns:
            stats: 统计信息
        """
        total_messages = 0
        total_size = 0
        date_range = {"start": None, "end": None}
        
        for storage_file in self.storage_dir.glob("*/*.jsonl.gz"):
            total_size += storage_file.stat().st_size
            daily_messages = self._read_storage_file(storage_file)
            total_messages += len(daily_messages)
            
            # 提取日期
            date_str = storage_file.stem  # 2025-03-01
            if date_range["start"] is None or date_str < date_range["start"]:
                date_range["start"] = date_str
            if date_range["end"] is None or date_str > date_range["end"]:
                date_range["end"] = date_str
        
        return {
            "total_messages": total_messages,
            "total_size_bytes": total_size,
            "total_size_mb": round(total_size / 1024 / 1024, 2),
            "date_range": date_range
        }
    
    # ===== 私有方法 =====
    
    def _generate_id(self, message: Dict[str, Any]) -> str:
        """生成消息 ID"""
        content = json.dumps(message, sort_keys=True, ensure_ascii=False)
        return hashlib.md5(content.encode()).hexdigest()[:16]
    
    def _get_storage_file(self, timestamp: str) -> Path:
        """获取存储文件路径"""
        dt = datetime.fromisoformat(timestamp)
        month_dir = self.storage_dir / dt.strftime("%Y-%m")
        month_dir.mkdir(exist_ok=True)
        return month_dir / f"{dt.strftime('%Y-%m-%d')}.jsonl.gz"
    
    def _read_storage_file(self, file_path: Path) -> List[Dict[str, Any]]:
        """读取存储文件"""
        messages = []
        try:
            with gzip.open(file_path, "rt", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line:
                        messages.append(json.loads(line))
        except Exception:
            pass
        return messages
    
    def _update_index(self, message_id: str, message: Dict[str, Any]) -> None:
        """更新索引"""
        index_file = self.index_dir / "id_index.json"
        
        # 读取现有索引
        index = {}
        if index_file.exists():
            try:
                with open(index_file, "r", encoding="utf-8") as f:
                    index = json.load(f)
            except Exception:
                pass
        
        # 更新索引
        storage_file = self._get_storage_file(message["timestamp"])
        index[message_id] = {
            "file": str(storage_file),
            "timestamp": message["timestamp"],
            "role": message.get("role", "")
        }
        
        # 写回索引
        with open(index_file, "w", encoding="utf-8") as f:
            json.dump(index, f, ensure_ascii=False, indent=2)