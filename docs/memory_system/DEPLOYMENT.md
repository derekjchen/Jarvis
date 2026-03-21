# Memory System 部署指南

## 快速开始

### 1. 使用快照镜像

```bash
# 拉取镜像 (假设已推送到仓库)
docker pull your-registry/super-mem-copaw-snapshot:latest

# 启动容器
docker run -d \
    --name super-mem-copaw \
    -p 18794:8088 \
    -e ENABLE_UNIFIED_MEMORY=true \
    -e ENABLE_LLM_EXTRACTION=true \
    super-mem-copaw-snapshot:latest \
    bash -c "source /venv/bin/activate && cd /workspace/copaw && export PYTHONPATH=/workspace/copaw/src && python -m copaw app --host 0.0.0.0 --port 8088"
```

### 2. 配置 LLM

```bash
# 方式1: 使用配置脚本
./deploy_configs/configure_llm.sh super-mem-copaw sk-sp-xxxx

# 方式2: 手动配置
docker exec super-mem-copaw mkdir -p /root/.copaw.secret/providers/builtin

# active_model.json
docker exec super-mem-copaw bash -c 'cat > /root/.copaw.secret/providers/active_model.json << EOF
{"provider_id": "aliyun-codingplan", "model": "qwen3-max-2026-01-23"}
EOF'

# builtin provider
docker exec super-mem-copaw bash -c 'cat > /root/.copaw.secret/providers/builtin/aliyun-codingplan.json << EOF
{"id": "aliyun-codingplan", "name": "Aliyun Coding Plan", "api_key": "sk-sp-xxxx", "base_url": "https://coding.dashscope.aliyuncs.com/v1"}
EOF'
```

### 3. 重启服务

```bash
docker restart super-mem-copaw
```

---

## 环境变量

### 核心配置

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `ENABLE_UNIFIED_MEMORY` | `true` | 启用统一记忆系统 |
| `ENABLE_LLM_EXTRACTION` | `true` | 启用 LLM 语义提取 (M4.0) |
| `ENABLE_MEMORY_MANAGER` | `true` | 启用记忆管理器 |

### Embedding 配置

| 变量 | 说明 |
|------|------|
| `EMBEDDING_API_KEY` | Embedding API 密钥 |
| `EMBEDDING_BASE_URL` | Embedding API 地址 |
| `EMBEDDING_MODEL_NAME` | Embedding 模型名称 |
| `EMBEDDING_DIMENSIONS` | 向量维度 (默认 1024) |

---

## 目录结构

```
/root/.copaw/
├── MEMORY.md              # 主记忆文件
├── PROFILE.md             # 用户资料
├── SOUL.md                # Agent 身份
├── memory/                # 按日期的记忆文件
├── sessions/              # 会话历史
├── entity_store/          # 统一实体存储 (M3.5)
│   └── entities.json
└── .secret/
    └── providers/         # LLM 配置
        ├── active_model.json
        └── builtin/
            └── aliyun-codingplan.json
```

---

## API 端点

| 端点 | 方法 | 说明 |
|------|------|------|
| `/` | GET | Web Console |
| `/api/version` | GET | 版本信息 |
| `/api/chats` | GET | 聊天列表 |
| `/api/agent/process` | POST | Agent 对话 (SSE) |

### 对话请求示例

```bash
curl -X POST http://localhost:18794/api/agent/process \
  -H "Content-Type: application/json" \
  -d '{
    "session_id": "test-session",
    "input": [{
      "role": "user",
      "type": "message",
      "content": [{"type": "text", "text": "你好"}]
    }]
  }'
```

---

## 故障排查

### 1. "No active model configured"

检查 LLM 配置文件路径：
```bash
docker exec super-mem-copaw cat /root/.copaw.secret/providers/active_model.json
docker exec super-mem-copaw cat /root/.copaw.secret/providers/builtin/aliyun-codingplan.json
```

### 2. "Web Console not available"

构建前端：
```bash
docker exec super-mem-copaw bash -c "cd /workspace/copaw/console && npm ci && npm run build"
```

### 3. "Vector search disabled"

配置 Embedding：
```bash
docker run ... \
  -e EMBEDDING_API_KEY="sk-xxx" \
  -e EMBEDDING_BASE_URL="https://dashscope.aliyuncs.com/compatible-mode/v1" \
  -e EMBEDDING_MODEL_NAME="text-embedding-v3" \
  ...
```

---

## 版本历史

| 版本 | 里程碑 | 功能 |
|------|--------|------|
| v2.1 | M2.1 | 关键信息保护 (过敏、禁忌) |
| v3.0 | M3.0 | 偏好演化 + 事件追踪 |
| v3.5 | M3.5 | 动态检索注入 |
| v4.0 | M4.0 | LLM 语义提取 |
| v5.0 | M5.0 | 记忆演化 (计划中) |
