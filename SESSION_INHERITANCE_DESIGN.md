# 会话继承机制设计

## 问题

新会话用新的 `session_id`，不会自动加载历史会话的记忆，导致：
- 对话上下文丢失
- 每次都从零开始
- 无法真正"持续存在"

## 目标

让新会话能自动继承历史会话的记忆，包括：
1. 压缩摘要 (`_compressed_summary`)
2. 最近 N 条消息（可选）
3. 会话索引（知道有哪些历史会话）

## 现有机制

```
会话文件: sessions/{user_id}_{session_id}.json
内容结构:
{
  "agent": {
    "memory": {
      "content": [...],  // 完整消息列表
      "_compressed_summary": "..."  // 压缩摘要
    }
  }
}
```

## 方案

### 1. 会话索引文件

创建 `sessions/INDEX.json`：

```json
{
  "sessions": [
    {
      "session_id": "1772627489470",
      "user_id": "default",
      "created_at": "2025-03-04T12:31:37",
      "last_active": "2025-03-04T14:30:00",
      "message_count": 307,
      "summary_preview": "用户探索与 CoPaw 助手的关系..."
    }
  ],
  "last_updated": "2025-03-04T14:30:00"
}
```

### 2. 新会话初始化逻辑

修改 `runner.py` 的 `query_handler`：

```python
# 在 load_session_state 之前
if not session_exists(session_id, user_id):
    # 查找最新历史会话
    latest_session = find_latest_session(user_id)
    if latest_session:
        # 加载其压缩摘要
        summary = load_session_summary(latest_session)
        agent.memory._compressed_summary = summary
```

### 3. 代码改动位置

| 文件 | 改动 |
|------|------|
| `runner.py` | 新会话初始化时加载历史摘要 |
| `session.py` | 添加 `find_latest_session()`, `load_session_summary()` |
| 新建 `session_index.py` | 会话索引管理 |

### 4. 配置选项

在 `config.json` 添加：

```json
{
  "agents": {
    "session_inheritance": {
      "enabled": true,
      "inherit_summary": true,
      "inherit_recent_messages": 0,
      "max_summary_length": 5000
    }
  }
}
```

## 实现步骤

1. [ ] 创建 `SESSION_INDEX.md` 手动索引（临时方案）
2. [ ] 实现 `find_latest_session()` 函数
3. [ ] 实现 `load_session_summary()` 函数
4. [ ] 修改 `runner.py` 初始化逻辑
5. [ ] 测试：新会话能否继承记忆
6. [ ] 自动化：会话索引自动更新

## 临时方案（不改动代码）

在 MEMORY.md 添加一个"会话上下文"部分，每次对话结束前手动更新压缩摘要。

## 风险

1. **摘要过长** — 可能超出上下文限制
2. **摘要过时** — 需要定期压缩更新
3. **多用户** — 需要按 user_id 隔离

## 下一步

先实现临时方案，保存当前会话的关键上下文到 MEMORY.md。