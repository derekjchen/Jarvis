#!/bin/bash
# super-mem-copaw 启动脚本
# Memory System M2.1-M4.0 部署

set -e

CONTAINER_NAME="super-mem-copaw"
IMAGE_NAME="super-mem-copaw-snapshot:latest"
PORT="${PORT:-18794}"

# 检查容器是否已存在
if docker ps -a --format '{{.Names}}' | grep -q "^${CONTAINER_NAME}$"; then
    echo "容器 ${CONTAINER_NAME} 已存在"
    read -p "是否重启? (y/n) " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        docker restart ${CONTAINER_NAME}
        echo "容器已重启"
    fi
    exit 0
fi

# 创建必要目录
echo "创建配置目录..."
docker run --rm -v ${CONTAINER_NAME}_data:/root/.copaw alpine mkdir -p /root/.copaw.secret/providers/builtin

# 启动容器
echo "启动容器 ${CONTAINER_NAME}..."
docker run -d \
    --name ${CONTAINER_NAME} \
    -p ${PORT}:8088 \
    -e ENABLE_UNIFIED_MEMORY=true \
    -e ENABLE_LLM_EXTRACTION=true \
    --restart unless-stopped \
    ${IMAGE_NAME} \
    bash -c "source /venv/bin/activate && cd /workspace/copaw && export PYTHONPATH=/workspace/copaw/src && python -m copaw app --host 0.0.0.0 --port 8088"

echo "等待服务启动..."
sleep 10

# 检查服务状态
if curl -s http://localhost:${PORT}/api/version > /dev/null; then
    echo "✅ 服务启动成功!"
    echo "   Console: http://localhost:${PORT}/"
    echo "   API: http://localhost:${PORT}/api/agent/process"
else
    echo "⚠️ 服务可能未完全启动，请检查日志:"
    echo "   docker logs ${CONTAINER_NAME}"
fi
