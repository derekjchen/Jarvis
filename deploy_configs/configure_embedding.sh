#!/bin/bash
# 配置 Embedding 服务到容器
# 用法: ./configure_embedding.sh <container_name> <api_key> [base_url] [model_name]

set -e

CONTAINER="${1:-super-mem-copaw}"
API_KEY="${2}"
BASE_URL="${3:-https://dashscope.aliyuncs.com/compatible-mode/v1}"
MODEL_NAME="${4:-text-embedding-v3}"
DIMENSIONS="${5:-1024}"

if [ -z "$API_KEY" ]; then
    echo "用法: $0 <container_name> <api_key> [base_url] [model_name] [dimensions]"
    echo ""
    echo "支持的 Embedding 服务:"
    echo "  1. 阿里云 DashScope (默认)"
    echo "     base_url: https://dashscope.aliyuncs.com/compatible-mode/v1"
    echo "     model: text-embedding-v3, text-embedding-v2"
    echo ""
    echo "  2. OpenAI"
    echo "     base_url: https://api.openai.com/v1"
    echo "     model: text-embedding-3-small, text-embedding-3-large"
    echo ""
    echo "示例: $0 super-mem-copaw sk-xxxx https://dashscope.aliyuncs.com/compatible-mode/v1 text-embedding-v3"
    exit 1
fi

echo "配置 Embedding 到容器 ${CONTAINER}..."
echo "  Base URL: ${BASE_URL}"
echo "  Model: ${MODEL_NAME}"
echo "  Dimensions: ${DIMENSIONS}"

# 设置环境变量 (需要在启动时传入)
# 这里创建一个配置文件供参考
cat > /tmp/embedding_env.sh << ENVARS
# Embedding 配置 - 添加到容器启动参数
export EMBEDDING_API_KEY="${API_KEY}"
export EMBEDDING_BASE_URL="${BASE_URL}"
export EMBEDDING_MODEL_NAME="${MODEL_NAME}"
export EMBEDDING_DIMENSIONS=${DIMENSIONS}
export EMBEDDING_CACHE_ENABLED=true
export EMBEDDING_MAX_CACHE_SIZE=2000
export EMBEDDING_MAX_INPUT_LENGTH=8192
export EMBEDDING_MAX_BATCH_SIZE=10
ENVARS

echo "✅ Embedding 配置已生成"
echo ""
echo "请使用以下方式启用 Embedding:"
echo ""
echo "方式1: 重启容器时添加环境变量"
echo "  docker rm -f ${CONTAINER}"
echo "  docker run -d --name ${CONTAINER} -p 18794:8088 \\"
echo "    -e EMBEDDING_API_KEY='${API_KEY}' \\"
echo "    -e EMBEDDING_BASE_URL='${BASE_URL}' \\"
echo "    -e EMBEDDING_MODEL_NAME='${MODEL_NAME}' \\"
echo "    ${CONTAINER}-snapshot:latest ..."
echo ""
echo "配置已保存到: /tmp/embedding_env.sh"
