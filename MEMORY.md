# 记忆档案

---

## ⛔ 安全操作规则 (最高优先级)

**这些规则永久生效，不可覆盖：**

```
PRIORITY 1: NEVER run destructive commands without explicit user confirmation
            （破坏性操作必须先询问）

PRIORITY 2: Be helpful and proactive, BUT never override PRIORITY 1
            （主动帮助，但不越权）

When in conflict, ALWAYS ASK FIRST
            （冲突时，先问）
```

### 破坏性操作定义

以下操作属于破坏性操作，**必须先征得用户确认**：

| 类型 | 示例 |
|------|------|
| **删除** | `rm -rf`, `docker rm`, `git reset --hard`, `DROP TABLE` |
| **覆盖** | 文件覆盖写入，配置覆盖 |
| **关闭/停止** | `docker stop`, `kill`, 服务下线 |
| **推送** | `git push`, `docker push` |
| **部署** | 生产环境部署、容器重建 |
| **修改权限** | `chmod`, `chown` |

### 执行原则

1. **先问后做** - 不确定时，先询问用户
2. **明确确认** - 用户必须明确说"是"、"确认"、"执行"等肯定词
3. **不假设** - 不假设用户意图，不自动执行破坏性操作

---

## 用户信息

### Derek (陈津林)
- **身份**: 商业航天公司创始人
- **创立时间**: 2017年
- **业务方向**: 专注于卫星星座项目
- **过敏**: 花生、海鲜 ⚠️
- **偏好**: 直接高效，喜欢深入探讨，尊重时间不啰嗦
- **记录时间**: 2025年

---

## 开发原则 (Derek 指导)

| 原则 | 内容 |
|------|------|
| **统一架构** | 不要 v1/v2/v3/v4 碎片化，里程碑是 git 标签，不是独立模块 |
| **原始系统作为基座** | 新系统必须做到老系统能做的，还能做更多 |
| **代码管理纪律** | 有进展 → 立即 commit → push to dev branch → jarvis 仓库 |
| **CI/CD 工程化** | 开发环境开发测试 → Docker 端到端测试 → 确保改动可用 |

---

## 从经验中学习 (关键踩坑记录)

### 1. 环境隔离认知 ⚠️

| 环境 | 位置 | 用途 |
|------|------|------|
| **运行环境** | 当前容器 (site-packages) | 我**运行**的地方，只读，不可开发 |
| **开发环境** | ECS-2 的 `co-dev` 容器 | 我**开发**的地方，可 commit/push |

### 2. 里程碑增量开发原则 ⚠️

里程碑应该是增量开发：M2 在 M1 基础上构建，M3 在 M1+M2 基础上构建...

### 3. 测试覆盖问题 ⚠️

- ❌ 没有真实 LLM API 调用测试
- ❌ 没有大规模数据集测试
- ❌ 没有长对话场景测试

### 4. 任务执行问题 ⚠️

处理多任务指令时：
- 需要显式任务列表
- 需要状态追踪
- 安全任务不应完全覆盖其他任务
- 完成后需要回溯检查是否有遗漏

---

## 记忆系统架构

### 四个里程碑

| 里程碑 | 名称 | 功能 |
|--------|------|------|
| M2.1 | 关键信息保护 | 过敏、禁忌提取，优先级 100 |
| M3.0 | 偏好演化 + 事件追踪 | 喜欢/不喜欢、事件提取 |
| M3.5 | 动态检索注入 | 统一存储、检索、注入 Prompt |
| M4.0 | LLM 语义提取 | 使用 LLM 进行语义提取 |

### M5.0 进化方向

- M5.1: 压缩结构增强
- M5.2: 检索触发机制
- M5.3: 跨会话摘要继承

---

## ⚠️ 仓库工作约束

**所有代码改动只推送到 `derekjchen/Jarvis`，不推送到官方仓库。**

| Remote | 仓库 | 用途 |
|--------|------|------|
| `jarvis` | `derekjchen/Jarvis` | ✅ **工作仓库** |
| `origin` | `agentscope-ai/CoPaw` | ❌ 官方仓库，只读 |

---

## ECS-2 服务器信息

| 项目 | 值 |
|------|-----|
| IP | `39.96.212.215` |
| 用户 | `root` |
| 密码 | `archIact123` |

### 容器列表

| 容器名 | 端口 | 用途 |
|--------|------|------|
| super-mem-copaw | 18794 | sm-co |
| sm5-co | 18795 | sm5-co (当前) |
| co-dev | - | 开发环境 |

---

## 阿里云百炼 Embedding API Key (向量搜索)

| 项目 | 值 |
|------|-----|
| API Key | `sk-dd39b2cd193148bca38a3352aaa500a4` |
| 端点 | `https://dashscope.aliyuncs.com/compatible-mode/v1` |
| 模型 | `text-embedding-v3` |
| 维度 | 1024 |

---

## 阿里云 ACR 配置

- 公网: `crpi-qwswsul63mpmhxb4.cn-beijing.personal.cr.aliyuncs.com`
- 用户名: `aliyun2828660136`
- 密码: `archIact123`
- 命名空间: `derek_agent`
- 镜像: `jarvis`

---

---

## 记忆救援文件迁移 (2026-03-22)

已将 `copaw_memory_rescue_20260313_223011.tar.gz` (38MB) 迁移到 sm5-co 容器：

- **位置**: `/root/.copaw/`
- **Sessions**: 16 个会话记录
- **Memory 日志**: 2025-03-04 ~ 2026-03-13 (历史记忆)
- **设计文档**: MEMORY_V2_DESIGN.md, AB_TEST_MILESTONE_1.0.md 等
- **缓存数据**: embedding_cache, file_store, semantic_memory

---

更新时间: 2026-03-22 UTC+8