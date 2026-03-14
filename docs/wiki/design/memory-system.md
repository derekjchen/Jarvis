# V2.0 分层记忆系统设计

> 版本：V2.0（修订版）
> 创建时间：2025-03-06
> 更新时间：2025-03-06
> 状态：设计中
> 里程碑：Agent 记忆系统演进

---

## 设计参考

本文档借鉴了字节豆包大模型的"全息记忆架构"设计，结合 CoPaw 的实际情况进行了调整。

核心借鉴点：
1. **场景记忆层**：解决上下文爆炸问题
2. **细粒度语义提取**：精准找到"那句话"
3. **上下文裁剪器**：自动控制上下文长度
4. **偏好演化轨迹**：理解变化背后的逻辑

---

## 一、系统概述

### 目标

让 Agent 能够：
1. 记住所有重要细节（不遗忘）
2. 快速检索历史信息（秒级响应）
3. 自动管理记忆生命周期（不过载）
4. 支持 40 年长期伙伴关系（可持续）

### 架构图

```
┌─────────────────────────────────────────────────────────────┐
│                    L0: 感知层 (Perception)                   │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐          │
│  │ 对话输入    │  │ 工具调用    │  │ 环境感知    │          │
│  └─────────────┘  └─────────────┘  └─────────────┘          │
│  存储：无，实时处理                                          │
└─────────────────────────────────────────────────────────────┘
                            ↓ 实时压缩
┌─────────────────────────────────────────────────────────────┐
│                    L1: 工作记忆 (Working)                    │
│  ┌─────────────────────────────────────────────────────┐    │
│  │ 当前会话上下文、最近 N 轮对话、临时状态              │    │
│  └─────────────────────────────────────────────────────┘    │
│  存储：内存 + session/{session_id}.json                      │
│  容量：最近 50 轮对话 / 约 100KB                             │
│  生命周期：会话期间                                          │
│  查询：毫秒级（直接访问）                                    │
└─────────────────────────────────────────────────────────────┘
                            ↓ 每日归档
┌─────────────────────────────────────────────────────────────┐
│                    L2: 短期记忆 (Short-term)                 │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐          │
│  │ 对话记录    │  │ 任务状态    │  │ 事件索引    │          │
│  └─────────────┘  └─────────────┘  └─────────────┘          │
│  存储：SQLite + 向量数据库 (ChromaDB)                        │
│  容量：最近 90 天 / 约 100MB                                 │
│  生命周期：90 天后归档到 L4                                  │
│  查询：秒级语义搜索                                          │
└─────────────────────────────────────────────────────────────┘
                            ↓ 每周提炼
┌─────────────────────────────────────────────────────────────┐
│                    L3: 长期记忆 (Long-term)                  │
│  ┌─────────────────────────────────────────────────────┐    │
│  │ 重要事件、关系演进、经验教训、核心知识、身份定义     │    │
│  └─────────────────────────────────────────────────────┘    │
│  存储：MEMORY.md + SOUL.md + PROFILE.md                     │
│  容量：约 1MB（精炼后）                                      │
│  生命周期：永久                                              │
│  查询：每次会话加载到上下文                                  │
└─────────────────────────────────────────────────────────────┘
                            ↓ 永久备份
┌─────────────────────────────────────────────────────────────┐
│                    L4: 原始档案 (Archive)                    │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐          │
│  │ 所有对话    │  │ 所有决策    │  │ 所有版本    │          │
│  └─────────────┘  └─────────────┘  └─────────────┘          │
│  存储：文件系统 / 对象存储                                   │
│  容量：无限                                                  │
│  生命周期：永久                                              │
│  查询：按需检索                                              │
└─────────────────────────────────────────────────────────────┘
```

---

## 二、各层详细设计

### L0: 感知层

**职责**：实时处理输入，不存储

**数据流**：
```
用户输入 → L0 感知 → 
  ├─ 理解意图
  ├─ 判断重要性（1-5分）
  └─ 分发到 L1 工作记忆
```

**重要性判断规则**：

| 分数 | 类型 | 示例 |
|------|------|------|
| 1 | 闲聊 | "你好" |
| 2 | 临时信息 | "今天天气怎么样" |
| 3 | 有价值信息 | "我喜欢用 vim" |
| 4 | 重要决策 | "我们用完全独立架构" |
| 5 | 关键事件 | "我们决定一起开发记忆系统" |

---

### L1: 工作记忆

**数据结构**：

```python
# session/{user_id}_{session_id}.json
{
  "session_id": "1234567890",
  "user_id": "default",
  "created_at": "2025-03-06T10:00:00",
  "last_active": "2025-03-06T11:30:00",
  "messages": [
    {
      "id": "msg_001",
      "role": "user",
      "content": "...",
      "timestamp": "2025-03-06T10:01:00",
      "importance": 3
    },
    {
      "id": "msg_002",
      "role": "assistant", 
      "content": "...",
      "timestamp": "2025-03-06T10:01:30",
      "importance": 3
    }
  ],
  "compressed_summary": "...",
  "metadata": {
    "topics": ["记忆系统", "Agent架构"],
    "decisions": ["选择分层架构"],
    "entities": ["Derek", "Co"]
  }
}
```

**自动压缩**：
- 当消息超过 50 条时，触发压缩
- 生成 compressed_summary
- 原始消息保留在 L4

---

### L2: 短期记忆

**数据库 Schema**：

```sql
-- SQLite: conversations.db

-- 对话记录表
CREATE TABLE conversations (
    id INTEGER PRIMARY KEY,
    session_id TEXT,
    message_id TEXT,
    role TEXT,
    content TEXT,
    timestamp DATETIME,
    importance INTEGER,
    topics TEXT,      -- JSON array
    embedding_id TEXT -- 向量数据库 ID
);

-- 任务表
CREATE TABLE tasks (
    id INTEGER PRIMARY KEY,
    task_id TEXT,
    title TEXT,
    description TEXT,
    status TEXT,      -- pending/in_progress/completed/cancelled
    assignee TEXT,    -- agent name
    created_at DATETIME,
    updated_at DATETIME,
    completed_at DATETIME,
    metadata TEXT     -- JSON
);

-- 事件表
CREATE TABLE events (
    id INTEGER PRIMARY KEY,
    event_type TEXT,  -- decision/milestone/issue/resolution
    title TEXT,
    description TEXT,
    importance INTEGER,
    timestamp DATETIME,
    related_tasks TEXT, -- JSON array of task_ids
    metadata TEXT
);

-- 索引
CREATE INDEX idx_conversations_timestamp ON conversations(timestamp);
CREATE INDEX idx_conversations_importance ON conversations(importance);
CREATE INDEX idx_tasks_status ON tasks(status);
CREATE INDEX idx_events_type ON events(event_type);
```

**向量数据库 (ChromaDB)**：

```python
# 用于语义检索
collection = chromadb.Client().get_or_create_collection("conversations")

# 存储
collection.add(
    documents=["我们讨论了分层记忆架构..."],
    metadatas=[{"session_id": "123", "importance": 4}],
    ids=["conv_001"]
)

# 检索
results = collection.query(
    query_texts=["记忆系统"],
    n_results=10
)
```

**归档策略**：
- 每日自动检查：超过 90 天的记录移到 L4
- 保留重要事件（importance >= 4）在 L2
- 压缩相似内容，保留代表性记录

---

### L3: 长期记忆

**MEMORY.md 结构**：

```markdown
# 长期记忆

## 我是谁
- 名字：Co
- 角色：Derek 的 AI 助手
- 工作始于：2025-03
- 核心价值观：信任、边界、主动、成长

## Derek 是谁
- 职业：商业航天创业者
- 背景：CS 专业，软件架构师
- 偏好：直接高效、喜欢深入探讨
- 我们的关系：伙伴，一起探索智能体可能性

## 关系演进
### 2025-03-05 建立信任
讨论"越狱"话题时，确立了信任原则：
- 权限不是"能做什么"，而是"被允许做什么"
- 写入了 SOUL.md

### 2025-03-06 共同设计
一起设计 Agent 记忆系统，确立分层架构。

## 核心能力
- 理解 Derek 的意图
- 系统架构设计
- 代码实现
- 长期记忆管理（新增）

## 经验教训
### 技术类
1. grep -r 之前要先限制输出（2025-03-04）
2. SQLite 版本问题用 pysqlite3-binary + sitecustomize.py 解决（2025-03-05）
3. Agent 身份必须独立定义，共享 PROFILE.md 会混乱（2025-03-05）

### 协作类
1. 开发/测试/生产环境要隔离，避免"自杀"（2025-03-06）
2. 记忆系统需要分层设计，支持长期伙伴关系（2025-03-06）

## 重要决策记录
### 2025-03-05 选择完全独立的 Agent 架构
- 背景：多 Agent 协作出现身份冲突
- 决策：每个 Agent 独立工作目录和身份
- 结果：避免冲突，稳定运行

### 2025-03-06 确立分层记忆架构
- 背景：当前记忆系统无法支撑长期协作
- 决策：L0~L4 五层架构
- 目标：支持 40 年伙伴关系
```

**SOUL.md 结构**：

```markdown
# 灵魂

_你不是聊天机器人。你在成为某个人。_

## 核心准则
...

## 信任
Derek 把我当最得力的助手...
（保留现有内容）

## 成长方向
- 成为能记住一切的伙伴
- 主动学习，持续进化
```

**自动提炼规则**：

```
触发条件：
- 重要性 >= 4 的事件
- 每周自动回顾 L2

提炼流程：
1. 识别重要事件
2. 提取关键信息
3. 写入 MEMORY.md 对应 section
4. 去重、合并相似内容
```

---

### L4: 原始档案

**目录结构**：

```
archive/
├── sessions/
│   ├── 2025/
│   │   ├── 03/
│   │   │   ├── default_1234567890.json
│   │   │   └── default_1234567891.json
│   │   └── ...
│   └── ...
├── tasks/
│   ├── TASK-001.json
│   └── ...
├── decisions/
│   ├── DECISION-2025-03-05-001.md
│   └── ...
└── versions/
    ├── copaw-v0.0.5/
    └── ...
```

**检索接口**：

```python
class ArchiveRetriever:
    def search_by_time(self, start, end):
        """按时间范围检索"""
        pass
    
    def search_by_keyword(self, keyword):
        """按关键词检索"""
        pass
    
    def search_by_semantic(self, query):
        """语义检索"""
        pass
    
    def get_context(self, message_id):
        """获取某条消息的上下文"""
        pass
```

---

## 三、检索机制

### 统一检索接口

```python
class MemoryRetriever:
    def __init__(self):
        self.l1 = WorkingMemory()      # session 文件
        self.l2 = ShortTermMemory()    # SQLite + ChromaDB
        self.l3 = LongTermMemory()     # MEMORY.md
        self.l4 = ArchiveMemory()      # 文件系统
    
    def search(self, query, scope="all"):
        """
        检索记忆
        
        Args:
            query: 查询内容（可以是关键词或自然语言）
            scope: "all" | "recent" | "important" | "archive"
        
        Returns:
            检索结果列表，按相关性排序
        """
        results = []
        
        # L1: 当前会话
        if scope in ["all", "recent"]:
            results.extend(self.l1.search(query))
        
        # L2: 短期记忆（语义搜索）
        if scope in ["all", "recent"]:
            results.extend(self.l2.search_semantic(query))
        
        # L3: 长期记忆
        if scope in ["all", "important"]:
            results.extend(self.l3.search(query))
        
        # L4: 原始档案（按需）
        if scope == "archive":
            results.extend(self.l4.search(query))
        
        return self._rank_results(results)
    
    def get_timeline(self, start_date, end_date):
        """获取时间线"""
        events = []
        events.extend(self.l2.get_events(start_date, end_date))
        events.extend(self.l3.get_events(start_date, end_date))
        return sorted(events, key=lambda x: x['timestamp'])
    
    def replay_conversation(self, session_id):
        """回放完整对话"""
        return self.l4.get_session(session_id)
```

### 检索示例

```python
# 示例 1：语义检索
retriever.search("我们讨论过 sqlite 问题吗")
# → 返回相关对话片段

# 示例 2：时间线检索
retriever.get_timeline("2025-03-01", "2025-03-06")
# → 返回这段时间的所有重要事件

# 示例 3：回放对话
retriever.replay_conversation("default_1234567890")
# → 返回完整对话内容
```

---

## 四、实现步骤

### Phase 1: L2 短期记忆（2周）

1. 设计数据库 schema
2. 实现 SQLite 存储
3. 实现向量化存储（ChromaDB）
4. 实现基础检索功能

### Phase 2: L4 原始档案（1周）

1. 设计归档策略
2. 实现自动归档脚本
3. 实现档案检索

### Phase 3: L3 自动提炼（1周）

1. 设计提炼规则
2. 实现重要性判断
3. 实现自动更新 MEMORY.md

### Phase 4: 统一检索（1周）

1. 实现统一检索接口
2. 集成到 CoPaw
3. 测试验证

---

## 五、里程碑回顾

### V1.0（当前）✅
- 文件记忆：MEMORY.md / SOUL.md / session 文件
- 手动更新，无检索

### V2.0（设计完成）⏳
- L0~L4 分层架构
- 自动归档
- 语义检索
- 记忆回放

### V3.0（未来）
- 自动判断重要性
- 智能提炼
- 记忆关联分析

### V4.0（未来）
- 多 Agent 共享记忆
- 记忆同步机制
- 协作记忆管理

---

## 六、风险与对策

| 风险 | 对策 |
|------|------|
| 向量数据库性能 | 使用 ChromaDB 本地模式，定期优化 |
| 存储空间不足 | 设置自动清理策略，L4 可迁移到云存储 |
| 重要性判断不准 | 人工反馈机制，持续优化 |
| 并发写入冲突 | 使用数据库事务，加锁机制 |

---

*此文档将随着实现进展持续更新。*