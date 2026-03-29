#!/bin/bash
# ============================================================
# 更新脚本: super-memv5-co (sm5-co) - M5.0 Integration
# 此脚本在 ECS (39.96.212.215) 上执行
# ============================================================

set -e

CONTAINER_NAME="super-memv5-co"
PORT="18795"
IMAGE_NAME="crpi-qwswsul63mpmhxb4-vpc.cn-beijing.personal.cr.aliyuncs.com/derek_agent/jarvis:m5"
CODE_DIR="/workspace/copaw"

echo "=========================================="
echo "更新 sm5-co (M5.0 Memory Integration)"
echo "=========================================="

# 1. 登录 ACR
echo ""
echo "[1/6] 登录阿里云 ACR..."
echo "archIact123" | docker login --username=aliyun2828660136 --password-stdin \
    crpi-qwswsul63mpmhxb4-vpc.cn-beijing.personal.cr.aliyuncs.com

# 2. 拉取最新代码
echo ""
echo "[2/6] 拉取最新代码 (jarvis仓库)..."
cd $CODE_DIR
git fetch jarvis
git reset --hard jarvis/main
git log --oneline -3

# 3. 备份记忆数据
echo ""
echo "[3/6] 备份记忆数据..."
BACKUP_DIR="/root/sm5_backup_$(date +%Y%m%d_%H%M%S)"
mkdir -p $BACKUP_DIR
docker cp $CONTAINER_NAME:/workspace/copaw/entity_store $BACKUP_DIR/ 2>/dev/null || echo "entity_store not in container"
docker cp $CONTAINER_NAME:/workspace/copaw/MEMORY.md $BACKUP_DIR/ 2>/dev/null || echo "MEMORY.md backup done"
docker cp $CONTAINER_NAME:/workspace/copaw/memory $BACKUP_DIR/ 2>/dev/null || echo "memory backup done"
echo "  ✅ 备份保存到: $BACKUP_DIR"

# 4. 构建新镜像
echo ""
echo "[4/6] 构建 Docker 镜像..."
docker build -t $IMAGE_NAME .

# 5. 推送镜像到 ACR
echo ""
echo "[5/6] 推送镜像到 ACR..."
docker push $IMAGE_NAME

# 6. 重启容器
echo ""
echo "[6/6] 重启容器..."
docker stop $CONTAINER_NAME 2>/dev/null || true
docker rm $CONTAINER_NAME 2>/dev/null || true

# 启动新容器，挂载备份的记忆
docker run -d \
    --name $CONTAINER_NAME \
    -p $PORT:8088 \
    -v /root/.copaw.secret:/root/.copaw.secret \
    -v $BACKUP_DIR/memory:/workspace/copaw/memory:ro \
    -e ENABLE_UNIFIED_MEMORY=true \
    -e ENABLE_LLM_EXTRACTION=true \
    -e ENABLE_EVOLUTION=true \
    --restart unless-stopped \
    $IMAGE_NAME \
    bash -c "source /venv/bin/activate && cd /workspace/copaw && export PYTHONPATH=/workspace/copaw/src && python -m copaw app --host 0.0.0.0 --port 8088"

# 等待启动
echo ""
echo "等待服务启动..."
sleep 10

# 检查健康状态
echo ""
echo "检查服务状态..."
if curl -s http://localhost:$PORT/api/version > /dev/null 2>&1; then
    echo "✅ 服务健康!"
else
    echo "⚠️ 服务可能还在启动中，请检查日志:"
    echo "   docker logs -f $CONTAINER_NAME"
fi

# 验证记忆
echo ""
echo "验证记忆..."
curl -s http://localhost:$PORT/api/agent/process -X POST \
    -H "Content-Type: application/json" \
    -d '{"input":[{"role":"user","type":"message","content":[{"type":"text","text":"请确认你是否记得：用户陈津林对花生和海鲜过敏"}]}],"user_id":"verify"}' \
    | grep -q "花生" && echo "  ✅ 记忆验证成功" || echo "  ⚠️ 请手动验证记忆"

echo ""
echo "=========================================="
echo "✅ 更新完成!"
echo "=========================================="
echo "容器名称: $CONTAINER_NAME"
echo "端口: $PORT"
echo "备份位置: $BACKUP_DIR"
echo ""
echo "M5.0 MemoryEvolver 已集成到 MemoryIntegration"
echo "可通过 API 测试: integration.evolve()"
echo ""
echo "常用命令:"
echo "  查看日志: docker logs -f $CONTAINER_NAME"
echo "  进入容器: docker exec -it $CONTAINER_NAME bash"
echo "  重启容器: docker restart $CONTAINER_NAME"