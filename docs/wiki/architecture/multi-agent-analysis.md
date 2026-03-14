# 多 Agent 协作方案分析

> 创建时间：2025-03-05 深夜
> 更新时间：2025-03-06
> 背景：尝试创建子 agent 协作，出现身份冲突和状态异常问题

## 核心概念：基于 Agent 的研发模式

与传统研发模式不同，我们提出"基于 Agent 的研发模式"：

### 传统研发模式

```
开发环境 ── 独立网段、独立机器集群
测试环境 ── 独立网段、独立机器集群
生产环境 ── 独立网段、独立机器集群
```

隔离方式：**物理/网络隔离**
协作方式：**人员协作**
部署方式：**CI/CD 流水线**

### 基于 Agent 的研发模式

```
开发 Agent ── 负责开发新功能
测试 Agent ── 负责测试验证
生产 Agent ── 负责实际运行
```

隔离方式：**智能体身份隔离**
协作方式：**Agent 间 API 通信**
部署方式：**Agent 自动同步/部署**

### 优势

1. **自动化程度高**：Agent 可以 7x24 工作
2. **知识共享**：共享记忆文件，新 Agent 可以快速了解项目
3. **灵活扩展**：需要新能力时，创建新的 Agent 即可
4. **成本可控**：可以共享硬件资源

### 挑战

1. **身份管理**：需要清晰的 Agent 身份定义
2. **协作机制**：Agent 间通信需要设计
3. **权限控制**：不同 Agent 有不同权限
4. **故障隔离**：一个 Agent 崩溃不能影响其他

---

## 资源配置建议

### 假设 ECS 配置：4核 CPU / 8GB 内存 / 100GB 硬盘

| 环境 | CPU | 内存 | 硬盘 | 运行方式 |
|------|-----|------|------|----------|
| **生产** | 2核 | 4GB | 50GB | 宿主机直接运行（端口 8088） |
| **开发** | 1核 | 2GB | 25GB | Docker 容器（端口 8089） |
| **测试** | 1核 | 2GB | 25GB | Docker 容器（端口 8090） |

### Docker 资源限制命令

```bash
# 开发环境容器
docker run -d --name copaw-dev \
  --cpus="1" \
  --memory="2g" \
  -p 8089:8088 \
  copaw:latest

# 测试环境容器
docker run -d --name copaw-test \
  --cpus="1" \
  --memory="2g" \
  -p 8090:8088 \
  copaw:latest
```

### 为什么这样分配

- **生产环境**：需要快速响应，session 文件会持续增长
- **开发环境**：调试时输出大量日志，不需要 7x24 运行
- **测试环境**：只在测试时启动，可以随用随开

---

## 遇到的问题

### 问题 1：身份冲突
- 共享 PROFILE.md 导致所有子 agent 都认为自己是 "Co"
- 即使起了不同名字，agent 仍然使用共享的身份信息

### 问题 2：状态异常
- 主 agent 不工作但 PID 还在
- 子 agent 启动后主 agent 进入奇怪状态

### 问题 3：记忆混乱
- 共享 memory 可能导致 agent 之间互相干扰
- session 记忆可能冲突

---

## 方案对比

### 方案 A：完全独立（最安全）

| Agent | 工作目录 | PROFILE | MEMORY | Session |
|-------|----------|---------|--------|---------|
| Co (主) | ~/.copaw_co | 独立 | 独立 | 独立 |
| Agent A | ~/.copaw_agent_a | 独立 | 独立 | 独立 |
| Agent B | ~/.copaw_agent_b | 独立 | 独立 | 独立 |

**优点**：
- 完全隔离，不会互相干扰
- 一个崩溃不影响其他
- 清晰的责任边界

**缺点**：
- 不共享知识，需要重复学习
- 协作需要显式通信机制

**实现方式**：
```bash
# 创建独立实例
copaw init --working-dir ~/.copaw_co
copaw init --working-dir ~/.copaw_agent_a
copaw init --working-dir ~/.copaw_agent_b

# 启动时指定不同的工作目录和端口
copaw app --working-dir ~/.copaw_co --port 8088
copaw app --working-dir ~/.copaw_agent_a --port 8089
copaw app --working-dir ~/.copaw_agent_b --port 8090
```

---

### 方案 B：共享用户信息，独立身份

| Agent | 工作目录 | PROFILE | MEMORY | Session |
|-------|----------|---------|--------|---------|
| Co (主) | ~/.copaw_co | 共享用户信息 | 共享长期记忆 | 独立 |
| Agent A | ~/.copaw_agent_a | 共享用户信息 | 共享长期记忆 | 独立 |
| Agent B | ~/.copaw_agent_b | 共享用户信息 | 共享长期记忆 | 独立 |

**优点**：
- 都知道用户是谁
- 共享长期记忆
- 独立的对话上下文

**缺点**：
- 需要处理 PROFILE.md 的身份部分
- 共享 memory 可能有并发问题

**实现方式**：
```bash
# 每个实例有自己的工作目录，但共享某些文件
mkdir -p ~/.copaw_co
mkdir -p ~/.copaw_agent_a

# 共享用户信息文件（软链接）
ln -s ~/.copaw_co/PROFILE.md ~/.copaw_agent_a/PROFILE.md
ln -s ~/.copaw_co/MEMORY.md ~/.copaw_agent_a/MEMORY.md

# 但每个实例有独立的 SOUL.md（定义身份）
# ~/.copaw_co/SOUL.md - 定义 "我是 Co"
# ~/.copaw_agent_a/SOUL.md - 定义 "我是 Agent A"
```

---

### 方案 C：混合架构（推荐）

```
┌─────────────────────────────────────────────────────────┐
│                    共享层                                │
│  PROFILE.md (用户信息)                                   │
│  MEMORY.md (长期记忆)                                    │
│  GitHub 仓库 (代码)                                      │
└─────────────────────────────────────────────────────────┘
                          │
        ┌─────────────────┼─────────────────┐
        ▼                 ▼                 ▼
┌───────────────┐ ┌───────────────┐ ┌───────────────┐
│ Co (主)       │ │ Agent A       │ │ Agent B       │
│ 端口: 8088    │ │ 端口: 8089    │ │ 端口: 8090    │
│ 工作目录: co   │ │ 工作目录: a   │ │ 工作目录: b   │
│ SOUL.md: Co   │ │ SOUL.md: A    │ │ SOUL.md: B    │
│ Session: 独立  │ │ Session: 独立  │ │ Session: 独立  │
│ 职责: 主控    │ │ 职责: 代码维护 │ │ 职责: 测试    │
└───────────────┘ └───────────────┘ └───────────────┘
```

**关键设计**：
1. **独立工作目录**：每个 agent 有自己的 working_dir
2. **独立 SOUL.md**：定义自己的身份和职责
3. **共享用户信息**：通过软链接共享 PROFILE.md
4. **共享长期记忆**：通过软链接共享 MEMORY.md（可能有并发风险）
5. **独立 Session**：每个 agent 有自己的对话历史

---

## 当前问题的根因

### 身份冲突的原因

PROFILE.md 结构：
```markdown
## 身份
- **名字：** Co
- **定位：** AI 助手
```

所有 agent 读到这个文件，都认为自己是 Co。

### 解决方案

每个 agent 需要有独立的身份配置：

```markdown
# ~/.copaw_co/SOUL.md
## 我的身份
- **名字：** Co
- **职责：** 主控 agent，与用户交互，分配任务

# ~/.copaw_agent_a/SOUL.md
## 我的身份
- **名字：** GitAgent
- **职责：** 维护 GitHub 仓库，保持与官方同步
```

---

## 实现步骤（推荐方案 A - 完全独立）

这是最安全、最简单的方案：

### 1. 创建独立实例

```bash
# 主 agent (Co)
mkdir -p ~/.copaw_co
cd ~/copaw
source venv/bin/activate
copaw init --working-dir ~/.copaw_co

# 子 agent (GitAgent)
mkdir -p ~/.copaw_git
copaw init --working-dir ~/.copaw_git
```

### 2. 配置独立身份

```bash
# 编辑各自的 SOUL.md
vi ~/.copaw_co/SOUL.md    # 定义 "我是 Co"
vi ~/.copaw_git/SOUL.md   # 定义 "我是 GitAgent"
```

### 3. 启动不同端口

```bash
# 主 agent
nohup copaw app --working-dir ~/.copaw_co --port 8088 > ~/copaw_co.log 2>&1 &

# Git agent
nohup copaw app --working-dir ~/.copaw_git --port 8089 > ~/copaw_git.log 2>&1 &
```

### 4. 协作方式

- 用户通过主 agent (Co) 分配任务
- Co 通过 API 调用 GitAgent
- GitAgent 完成任务后报告结果

---

## 协作通信机制

### 方式 1：API 调用

```python
# Co 调用 GitAgent
import requests

response = requests.post(
    "http://localhost:8089/api/chat",
    json={"message": "请同步官方仓库的最新代码"}
)
```

### 方式 2：共享文件

```bash
# 任务队列文件
~/.copaw_shared/tasks.json
```

### 方式 3：消息队列

使用 Redis 或 RabbitMQ 进行 agent 间通信。

---

## 风险和注意事项

### 完全独立方案的风险
- 低风险
- 一个 agent 崩溃不影响其他
- 清晰的边界

### 共享记忆方案的风险
- 并发写入可能导致数据丢失
- 需要加锁机制
- 复杂度更高

---

## 下一步建议

1. **先实现完全独立方案**（方案 A）
2. **验证稳定后再考虑共享**
3. **逐步添加协作机制**

---

## 附录：子 Agent 角色建议

| Agent 名字 | 职责 | 端口 |
|------------|------|------|
| Co | 主控，与用户交互 | 8088 |
| GitAgent | GitHub 仓库维护 | 8089 |
| TestAgent | 测试和验证 | 8090 |
| DocAgent | 文档维护 | 8091 |

---

*此文档将在下次讨论多 agent 协作时作为参考。*