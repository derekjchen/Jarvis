#!/bin/bash
# 配置 LLM 模型到容器
# 用法: ./configure_llm.sh <container_name> <api_key> [model]

set -e

CONTAINER="${1:-super-mem-copaw}"
API_KEY="${2}"
MODEL="${3:-qwen3-max-2026-01-23}"
PROVIDER="aliyun-codingplan"
BASE_URL="https://coding.dashscope.aliyuncs.com/v1"

if [ -z "$API_KEY" ]; then
    echo "用法: $0 <container_name> <api_key> [model]"
    echo "示例: $0 super-mem-copaw sk-sp-xxxx qwen3-max-2026-01-23"
    exit 1
fi

echo "配置 LLM 到容器 ${CONTAINER}..."
echo "  Provider: ${PROVIDER}"
echo "  Model: ${MODEL}"

# 创建配置目录
docker exec ${CONTAINER} mkdir -p /root/.copaw.secret/providers/builtin

# 写入 active_model.json
docker exec ${CONTAINER} bash -c "cat > /root/.copaw.secret/providers/active_model.json << 'JSONEOF'
{
  \"provider_id\": \"${PROVIDER}\",
  \"model\": \"${MODEL}\"
}
JSONEOF"

# 写入 builtin provider 配置
docker exec ${CONTAINER} bash -c "cat > /root/.copaw.secret/providers/builtin/${PROVIDER}.json << 'JSONEOF'
{
  \"id\": \"${PROVIDER}\",
  \"name\": \"Aliyun Coding Plan\",
  \"api_key\": \"${API_KEY}\",
  \"base_url\": \"${BASE_URL}\"
}
JSONEOF"

echo "✅ LLM 配置完成"
echo "重启容器以生效: docker restart ${CONTAINER}"
