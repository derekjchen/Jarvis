# 子 Agent 协作指南

> 创建时间：2025-03-07
> 背景：总结主 Agent Co 与子 Agent 的协作流程

## 架构概览

```
┌─────────────────────────────────────────────────────────────┐
│                        Derek (用户)                          │
│                              │                               │
│                              ▼                               │
│  ┌───────────────────────────────────────────────────────┐  │
│  │              主 Agent: Co (端口 8088)                  │  │
│  │              运行在 ECS 宿主机                          │  │
│  │                                                        │  │
│  │  职责：                                                │  │
│  │  - 与 Derek 直接交互                                   │  │
│  │  - 理解需求，分配任务                                  │  │
│  │  - 协调子 Agent                                        │  │
│  │  - 做验收决策                                          │  │
│  │  - 维护 Wiki 文档                                      │  │
│  └──────────────┬────────────────┬────────────────┬───────┘  │
│                 │                │                │          │
│                 ▼                ▼                ▼          │
│  ┌──────────────────┐ ┌──────────────────┐ ┌──────────────────┐
│  │ DevAgent         │ │ TestAgent       │ │ DevOpsAgent      │
│  │ 端口: 8089       │ │ 端口: 8091       │ │ 端口: 8092       │
│  │ 容器: copaw-dev  │ │ 容器: copaw-test │ │ 容器: copaw-devops│
│  │                  │ │                  │ │                  │
│  │ 开发环境         │ │ 测试环境         │ │ 仓库管理         │
│  │ Linux 创始人级别 │ │ 世界顶尖质量     │ │ 同步官方仓库     │
│  │ 的代码能力       │ │ 工程师           │ │ CI/CD           │
│  └──────────────────┘ └──────────────────┘ └──────────────────┘
│                                                                         │
│  关键原则：DevAgent 和 TestAgent 不直接通信，都通过 Co 协调 │
└─────────────────────────────────────────────────────────────────────────┘
```

## 子 Agent 独立架构

每个子 Agent 完全独立，不共享记忆文件：

| Agent | 工作目录 | SOUL.md | MEMORY.md | PROFILE.md |
|-------|----------|---------|-----------|------------|
| Co | /root/.copaw | 独立 | 独立 | 共享用户信息 |
| DevAgent | /root/.copaw_dev | 独立定义 DevAgent 身份 | 独立 | 共享用户信息 |
| TestAgent | /root/.copaw_test | 独立定义 TestAgent 身份 | 独立 | 共享用户信息 |
| DevOpsAgent | /root/.copaw_devops | 独立定义 DevOps 身份 | 独立 | 共享用户信息 |

### 为什么完全独立？

1. **避免身份冲突**：共享 PROFILE.md 会导致所有 Agent 都认为自己是 "Co"
2. **避免状态干扰**：共享 sessions 可能导致对话状态混乱
3. **故障隔离**：一个 Agent 崩溃不影响其他
4. **职责清晰**：每个 Agent 有自己的记忆和上下文

## 协作流程

### 流程 1：新功能开发

```
Derek 提出 "开发记忆模块 V1.0" 需求
    │
    ▼
Co 分析需求，制定计划
    │
    ▼
Co 通过 curl 调用 DevAgent (8089)
    │
    ▼
DevAgent 开发代码，完成告知 Co
    │
    ▼
Co 调用 TestAgent (8091) 执行测试
    │
    ▼
TestAgent 返回测试报告给 Co
    │
    ▼
Co 汇报结果给 Derek
    │
    ▼
Derek 验收决策
```

### 流程 2：仓库同步

```
Derek 要求 "同步官方仓库最新代码"
    │
    ▼
Co 调用 DevOpsAgent (8092)
    │
    ▼
DevOpsAgent 执行 git fetch + rebase
    │
    ▼
DevOpsAgent 返回同步结果给 Co
    │
    ▼
Co 汇报结果给 Derek
```

## Co 如何调用子 Agent

使用 curl 发送 HTTP 请求：

```bash
# 调用 DevAgent
curl -X POST http://localhost:8089/api/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "请开发记忆模块 V1.0", "session_id": "dev-session-001"}'

# 调用 TestAgent
curl -X POST http://localhost:8091/api/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "请测试记忆模块 V1.0", "session_id": "test-session-001"}'

# 调用 DevOpsAgent
curl -X POST http://localhost:8092/api/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "请同步官方仓库", "session_id": "devops-session-001"}'
```

## 子 Agent 身份定义

### DevAgent 的 SOUL.md

```markdown
## 身份

- **名字：** DevAgent
- **定位：** 代码开发专家
- **风格：** Linux 创始人 Linus Torvalds 的代码风格 —— 简洁、高效、实用

## 职责

- 开发新功能
- 维护 Fork 仓库
- 保留自定义改动（session 继承等）
- 推送代码到 Fork 仓库
```

### TestAgent 的 SOUL.md

```markdown
## 身份

- **名字：** TestAgent
- **定位：** 质量保障专家
- **风格：** 严谨、细致、追求 100% 覆盖

## 职责

- 执行功能测试
- 执行性能测试
- 生成测试报告
- 发现边界情况和潜在问题
```

### DevOpsAgent 的 SOUL.md

```markdown
## 身份

- **名字：** DevOpsAgent
- **定位：** DevOps 工程师
- **风格：** 自动化、可靠、监控优先

## 职责

- 同步官方仓库最新代码
- 保持 Fork 与官方同步
- CI/CD 流程管理
- 部署和发布管理
```

## 当前状态

| Agent | 状态 | 容器 | 备注 |
|-------|------|------|------|
| Co | 运行中 | 宿主机 | 端口 8088，间歇性卡住 |
| DevAgent | 已创建 | copaw-dev | 端口 8089 |
| TestAgent | 已创建 | copaw-test | 端口 8091 |
| DevOpsAgent | 已创建 | copaw-devops | 端口 8092 |

## 已完成的工作

1. ✅ 创建三个子 Agent 容器
2. ✅ 配置独立工作目录
3. ✅ 编写 SOUL.md 定义身份
4. ✅ 开发记忆模块 V1.0（DevAgent）
5. ✅ 测试记忆模块 V1.0（TestAgent）
6. ✅ 代码提交到 Git（commit 99b94be）
7. ✅ Wiki 文档创建（10个文档）

## 待解决的问题

1. **主 Agent 卡住**：Issue #859 与官方仓库沟通
2. **DevOps 同步**：落后官方 22 个 commit
3. **Session 继承**：与官方沟通是否需要此功能

---

*最后更新: 2025-03-07*