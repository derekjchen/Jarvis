# CoPaw Session 记忆功能开发计划

> 创建时间：2025-03-04
> 状态：待开发
> 优先级：高

## 背景

当前 CoPaw 的新会话无法继承历史会话的记忆，每次都从零开始。用户希望实现"会话持续化"，让 agent 真正"持续存在"。

## 目标

让新会话能自动继承历史会话的记忆：
1. 压缩摘要 (`_compressed_summary`)
2. 最近 N 条消息（可选）
3. 会话索引（知道有哪些历史会话）

---

## 敏捷开发流程

### 第一步：拉取代码

```bash
# 在容器内（或宿主机）
cd /tmp
git clone https://github.com/agentscope-ai/CoPaw.git
cd CoPaw

# 如果 GitHub 访问慢，使用镜像
# git clone https://gitee.com/xxx/CoPaw.git
```

### 第二步：设计测试用例

```
测试用例 1：新会话继承压缩摘要
  步骤：
    1. 启动 agent，进行对话（聊 A 话题）
    2. 关闭会话
    3. 开启新会话
    4. 问 agent："我们之前聊了什么？"
  期望：agent 能说出 A 话题的内容

测试用例 2：压缩摘要不超过限制
  步骤：
    1. 进行长对话
    2. 检查摘要长度
  期望：摘要长度 < 配置的最大值（如 5000 字符）

测试用例 3：多用户隔离
  步骤：
    1. 用户 A 对话
    2. 用户 B 新会话
    3. 检查用户 B 的记忆
  期望：用户 B 看不到用户 A 的记忆

测试用例 4：空历史不报错
  步骤：
    1. 全新安装，无任何历史会话
    2. 启动新会话
  期望：正常运行，不报错
```

### 第三步：修改源码

按 `SESSION_INHERITANCE_DESIGN.md` 的方案改代码：

**改动文件清单：**

| 文件 | 改动内容 |
|------|----------|
| `copaw/app/runner/session.py` | 添加 `find_latest_session()`, `load_session_summary()` |
| `copaw/app/runner/runner.py` | 新会话初始化时调用继承逻辑 |
| `copaw/config.py` | 添加 session_inheritance 配置项 |
| 新建 `copaw/session_index.py` | 会话索引管理（可选） |

**核心逻辑伪代码：**

```python
# runner.py - query_handler 中

async def query_handler(self, msgs, request, **kwargs):
    session_id = request.session_id
    user_id = request.user_id
    
    # 新增：检查是否是新会话
    if not self.session.exists(session_id, user_id):
        # 查找最新历史会话
        latest = self.session.find_latest(user_id)
        if latest:
            # 加载历史摘要
            summary = self.session.load_summary(latest)
            agent.memory._compressed_summary = summary
    
    # 原有逻辑...
    await self.session.load_session_state(...)
```

### 第四步：跑单元测试

```bash
# 创建测试文件
touch tests/test_session_inheritance.py

# 运行测试
pytest tests/test_session_inheritance.py -v

# 或运行所有测试
pytest tests/ -v
```

### 第五步：部署实验版本

```bash
# 安装开发版本
pip install -e .

# 用不同端口部署（不影响当前运行的 agent）
copaw app --host 0.0.0.0 --port 8089 --working-dir /tmp/copaw_dev
```

### 第六步：端到端测试

我（当前 agent）通过浏览器/CLI 与实验 agent 对话：

1. 打开 `http://localhost:8089`
2. 进行对话，聊一个特定话题
3. 关闭浏览器标签（结束会话）
4. 重新打开 `http://localhost:8089`
5. 问："我们之前聊了什么？"
6. 验证是否记得

### 第七步：迭代

```
测试通过 → 完成
测试失败 → 分析原因 → 修复代码 → 重复第四到六步
```

---

## 进度跟踪

- [x] 第一步：拉取代码 ✅ 2025-03-05 00:20
  - 克隆到 `/tmp/CoPaw`
  - 创建虚拟环境
  - 安装依赖完成
- [x] 第二步：设计测试用例 ✅ 2025-03-05 01:30
  - 创建 `tests/test_session_inheritance.py`
  - 包含 9 个测试用例
- [x] 第三步：修改源码 ✅ 2025-03-05 02:00
  - 修改 `session.py`：添加 find_latest_session, load_session_summary, list_sessions_for_user
  - 修改 `runner.py`：添加会话继承逻辑
- [x] 第四步：跑单元测试 ✅ 2025-03-05 02:30
  - 9/9 测试通过
- [ ] 第五步：部署实验版本 ⚠️ 暂停
  - 已初始化测试环境 `/tmp/copaw_test`
  - 已配置 LLM (aliyun-codingplan/glm-5)
  - **问题**：测试实例可能干扰当前运行的 agent
  - **需要**：完全隔离的测试环境
- [ ] 第六步：端到端测试
- [ ] 第七步：迭代/完成

## 暂停原因

端到端测试需要在独立环境中运行，避免干扰当前运行的 agent。

**已完成的核心功能**：
- 代码已修改
- 单元测试通过
- 功能逻辑已验证

**后续建议**：
1. 在宿主机上部署测试版本
2. 或等待当前会话结束后再测试
3. 或使用完全隔离的 Docker 容器测试

---

## 风险与对策

| 风险 | 对策 |
|------|------|
| GitHub 访问慢 | 使用 Gitee 镜像或代理 |
| 测试环境影响生产 | 使用不同端口和独立工作目录 |
| 代码改坏 | Git 版本控制，随时回滚 |
| 摘要过长 | 配置最大长度，超出则截断 |

---

## 相关文档

- `SESSION_INHERITANCE_DESIGN.md` — 技术设计文档
- `MEMORY.md` — 长期记忆
- GitHub: https://github.com/agentscope-ai/CoPaw

---

## 备注

此计划采用敏捷开发理念：
1. 小步快跑
2. 测试驱动
3. 快速迭代
4. 持续交付

未来其他开发任务也可以参考这个流程。