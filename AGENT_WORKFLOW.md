# Agent CI/CD 工作流程

> 版本: 1.0
> 创建时间: 2026-03-08
> 状态: 生效

## 概述

本文档定义了主 Agent 与子 Agent 之间的协作流程，确保代码开发、测试、部署的标准化。

## 核心原则

1. **职责分离**: 每个 Agent 有明确的职责边界
2. **环境隔离**: 子 Agent 运行在容器中，通过 GitHub API 协作
3. **标准化流程**: 所有代码变更必须遵循同一流程
4. **可追溯**: 每个步骤都有明确的标记和记录

## Agent 职责定义

### 主 Agent (Co)

**执行环境**: 宿主机

**职责**:
- 任务分配和协调
- 开发和本地测试
- 推送代码到 feature 分支
- 最终决策和审核

**操作方式**: 本地 Git + GitHub API

### DevAgent

**执行环境**: 宿主机（或容器）

**职责**:
- 接收开发任务
- 编写代码
- 本地单元测试
- 推送到 feature 分支

**操作方式**: 本地 Git

### TestAgent

**执行环境**: 容器内 (端口 8091)

**职责**:
- 拉取 feature 分支
- 构建和部署测试环境
- 执行集成测试、E2E 测试
- 标注测试结果

**操作方式**: Git (容器内) + GitHub API

### DevOpsAgent

**执行环境**: 容器内 (端口 8092)

**职责**:
- 监控 ready-to-merge 标签
- 创建和管理 Pull Request
- 合并分支到 main
- 同步 fork 与上游仓库

**操作方式**: **仅使用 GitHub API**（不操作本地 Git）

## 标准工作流程

```
┌─────────────────────────────────────────────────────────────────┐
│                    Feature 开发流程                              │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  1. 开发阶段                                                     │
│     主 Agent / DevAgent                                          │
│     ├── 创建分支: git checkout -b feature/xxx                   │
│     ├── 开发代码                                                 │
│     ├── 本地测试: pytest tests/                                  │
│     └── 推送: git push fork feature/xxx                         │
│                                                                  │
│  2. 测试阶段                                                     │
│     TestAgent (容器内)                                           │
│     ├── 拉取: git fetch && git checkout feature/xxx             │
│     ├── 构建: pip install -e .                                   │
│     ├── 测试: pytest tests/e2e/                                  │
│     └── 标注: 添加 GitHub Label "ready-to-merge" 或 "test-failed"│
│                                                                  │
│  3. 合并阶段                                                     │
│     DevOpsAgent (容器内, GitHub API)                             │
│     ├── 监控: 检查 "ready-to-merge" 标签                        │
│     ├── 创建 PR (如需要)                                         │
│     ├── 合并: PUT /repos/.../pulls/{n}/merge                    │
│     └── 同步: fork ← origin/main                                │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

## GitHub Label 定义

| Label | 含义 | 添加者 |
|-------|------|--------|
| `ready-to-merge` | 测试通过，可以合并 | TestAgent |
| `test-failed` | 测试失败，需要修复 | TestAgent |
| `in-progress` | 开发中 | DevAgent |
| `needs-review` | 需要主 Agent 审核 | DevAgent |

## GitHub API 操作指南

### DevOpsAgent 常用操作

#### 1. 列出待合并的 PR
```bash
curl -s "https://api.github.com/repos/derekjchen/Jarvis/pulls?state=open&labels=ready-to-merge"
```

#### 2. 合并 PR
```bash
curl -X PUT "https://api.github.com/repos/derekjchen/Jarvis/pulls/{number}/merge" \
  -H "Authorization: Bearer $GITHUB_TOKEN" \
  -H "Accept: application/json" \
  -d '{"merge_method": "squash"}'
```

#### 3. 同步 fork 与上游
```bash
# 方法 1: GitHub Sync API (需要 admin 权限)
curl -X POST "https://api.github.com/repos/derekjchen/Jarvis/git/refs/heads/main" \
  -H "Authorization: Bearer $GITHUB_TOKEN" \
  -d '{"sha": "<upstream-main-sha>"}'

# 方法 2: 创建同步 PR
# 1. 获取上游最新 commit
# 2. 创建 PR 从 origin/main 到 fork/main
```

#### 4. 添加 Label
```bash
curl -X POST "https://api.github.com/repos/derekjchen/Jarvis/issues/{number}/labels" \
  -H "Authorization: Bearer $GITHUB_TOKEN" \
  -d '{"labels": ["ready-to-merge"]}'
```

## 分支命名规范

| 类型 | 格式 | 示例 |
|------|------|------|
| 功能 | `feature/xxx` | `feature/semantic-memory-v2` |
| 修复 | `fix/xxx` | `fix/entity-extractor` |
| 重构 | `refactor/xxx` | `refactor/memory-module` |
| 测试 | `test/xxx` | `test/e2e-framework` |

## 仓库配置

- **origin**: https://github.com/agentscope-ai/CoPaw.git (官方仓库)
- **fork**: https://github.com/derekjchen/Jarvis.git (我们的仓库)

## 异常处理

### 测试失败
1. TestAgent 添加 `test-failed` label
2. 通知主 Agent（通过 agent_coordination/tasks/）
3. 主 Agent 分配修复任务
4. 修复后重新推送，TestAgent 重新测试

### 合并冲突
1. DevOpsAgent 检测到冲突
2. 通知主 Agent
3. 主 Agent 在宿主机解决冲突
4. 重新推送

### 同步失败
1. DevOpsAgent 记录错误
2. 主 Agent 手动同步
3. 分析原因，更新流程

## 附录: Agent 端口映射

| Agent | 端口 | 容器名 |
|-------|------|--------|
| DevAgent | 8089 | copaw-dev |
| TestAgent | 8091 | copaw-test |
| DevOpsAgent | 8092 | copaw-devops |
| OLD ECHO | 8093 | copaw-old-echo |

---

## 版本历史

| 版本 | 日期 | 变更 |
|------|------|------|
| 1.0 | 2026-03-08 | 初始版本 |