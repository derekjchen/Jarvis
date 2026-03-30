# -*- coding: utf-8 -*-
"""
向量存储 - Vector Store

提供基础的语义检索能力：
- 对话向量提取
- 相似度检索
- 使用内存存储（V1.0 简化版本）

V2.0 将升级为 ChromaDB
"""

from typing import List, Dict, Any, Optional
import hashlib
import json


class VectorStore:
    """向量存储（简化版本）"""
    
    def __init__(self, storage_dir: str = "/root/.copaw/vector_store"):
        """
        初始化向量存储
        
        Args:
            storage_dir: 存储目录
        """
        from pathlib import Path
        self.storage_dir = Path(storage_dir)
        self.storage_dir.mkdir(parents=True, exist_ok=True)
        
        self.vectors_file = self.storage_dir / "vectors.json"
        self.vectors = self._load_vectors()
    
    def add_message(self, message: Dict[str, Any]) -> str:
        """
        添加消息向量
        
        V1.0 简化版本：使用模拟向量
        V2.0 将使用真实的 embedding
        
        Args:
            message: 消息字典
        
        Returns:
            vector_id: 向量 ID
        """
        # 生成向量 ID
        vector_id = self._generate_vector_id(message)
        
        # 简化版本：存储消息的关键词作为"向量"
        content = message.get("content", "")
        if isinstance(content, str):
            keywords = self._extract_keywords(content)
        else:
            keywords = []
        
        self.vectors[vector_id] = {
            "id": vector_id,
            "message_id": message.get("id", ""),
            "keywords": keywords,
            "timestamp": message.get("timestamp", ""),
            "role": message.get("role", "")
        }
        
        self._save_vectors()
        return vector_id
    
    def search_similar(
        self, 
        query: str, 
        top_k: int = 10
    ) -> List[Dict[str, Any]]:
        """
        搜索相似消息
        
        V1.0 简化版本：使用关键词匹配
        V2.0 将使用向量相似度
        
        Args:
            query: 查询文本
            top_k: 返回数量
        
        Returns:
            results: 相似消息列表
        """
        query_keywords = set(self._extract_keywords(query))
        
        results = []
        for vector_id, vector_data in self.vectors.items():
            vector_keywords = set(vector_data.get("keywords", []))
            
            # 计算关键词重叠
            overlap = len(query_keywords & vector_keywords)
            if overlap > 0:
                results.append({
                    **vector_data,
                    "similarity": overlap / max(len(query_keywords), 1)
                })
        
        # 按相似度排序
        results.sort(key=lambda x: x.get("similarity", 0), reverse=True)
        
        return results[:top_k]
    
    def _extract_keywords(self, text: str) -> List[str]:
        """
        提取关键词（简化版本）
        
        Args:
            text: 文本内容
        
        Returns:
            keywords: 关键词列表
        """
        # 简化版本：分词并过滤停用词
        # 实际版本应使用 jieba 等分词工具
        
        # 简单分割
        words = text.lower().split()
        
        # 过滤短词
        keywords = [w for w in words if len(w) > 2]
        
        return keywords[:20]  # 最多 20 个关键词
    
    def _generate_vector_id(self, message: Dict[str, Any]) -> str:
        """生成向量 ID"""
        content = json.dumps(message, sort_keys=True, ensure_ascii=False)
        return hashlib.md5(content.encode()).hexdigest()[:16]
    
    def _load_vectors(self) -> Dict[str, Dict[str, Any]]:
        """加载向量"""
        if self.vectors_file.exists():
            try:
                with open(self.vectors_file, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                return {}
        return {}
    
    def _save_vectors(self) -> None:
        """保存向量"""
        with open(self.vectors_file, "w", encoding="utf-8") as f:
            json.dump(self.vectors, f, ensure_ascii=False, indent=2)