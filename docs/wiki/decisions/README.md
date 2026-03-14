# 关键决策记录

## 2025-03-06 Agent 架构决策

### 决策：DevAgent 和 TestAgent 不直接通信

**背景**：设计 Agent 协作架构时，需要确定 DevAgent 和 TestAgent 是否需要直接通信。

**选项**：
1. DevAgent 和 TestAgent 直接通信
2. 都通过主 Agent (Co) 协调

**决策**：选择方案 2 - 都通过主 Agent 协调

**原因**：
1. Co 是协调者，掌握全局
2. 解耦 - 各 Agent 互不依赖
3. 决策集中 - 便于追踪
4. 简化架构 - 不需要容器间直接通信

**工作流**：
```
DevAgent 完成 → 通知 Co → Co 通知 TestAgent 测试
                                    ↓
                              TestAgent 汇报 Co
                                    ↓
                              Co 做决策
```

---

## 2025-03-06 开发环境架构决策

### 决策：Git 仓库放在宿主机，DevAgent 在 Docker 中通过挂载访问

**背景**：需要确定 Git 仓库和 DevAgent 的部署位置。

**选项**：
1. Git 仓库在宿主机，DevAgent 在 Docker（挂载）
2. Git 仓库在 DevAgent 容器内

**决策**：选择方案 1

**架构**：
```
ECS 宿主机
├── /root/copaw/          # Git 仓库（持久化）
│         │
│         │ 挂载 (volume)
│         ▼
│  ┌─────────────────────┐
│  │ copaw-dev 容器      │
│  │ /app/repo ← 挂载    │
│  │ 管理 Git 操作       │
│  │ Token 存储在容器内  │
│  └─────────────────────┘
```

**原因**：
- Git 仓库持久化，不会因容器删除丢失
- DevAgent 隔离在容器内（Token 安全）
- 主 Agent 可以读取代码

---

## 2025-03-06 文档系统决策

### 决策：选择 DokuWiki 作为知识库

**背景**：需要一个文档系统来记录关键决策、架构设计等。

**选项**：
1. DokuWiki - 无数据库，纯文件
2. Wiki.js - 现代化，需要数据库
3. BookStack - 需要 MySQL

**决策**：选择 DokuWiki

**原因**：
- 无需数据库，最轻量
- Agent 可以直接编辑文件
- 部署简单，资源占用少

**状态**：待部署（Docker Hub 被墙）

---

*最后更新: 2025-03-06*
