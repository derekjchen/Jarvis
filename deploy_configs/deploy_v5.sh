#!/bin/bash
# ============================================================
# 部署脚本: super-memv5-co (sm5-co)
# M5.0 Memory System 集成
# 请在 ECS 宿主机上执行此脚本
# ============================================================

set -e

CONTAINER_NAME="super-memv5-co"
PORT="18795"
IMAGE_NAME="crpi-qwswsul63mpmhxb4-vpc.cn-beijing.personal.cr.aliyuncs.com/derek_agent/jarvis:m5"
CODE_DIR="/workspace/copaw"

echo "=========================================="
echo "部署 super-memv5-co (M5.0 Memory System)"
echo "智能体名称: sm5-co"
echo "=========================================="

# 1. 登录 ACR
echo ""
echo "[1/7] 登录阿里云 ACR..."
echo "archIact123" | docker login --username=aliyun2828660136 --password-stdin \
    crpi-qwswsul63mpmhxb4-vpc.cn-beijing.personal.cr.aliyuncs.com

# 2. 拉取最新代码
echo ""
echo "[2/7] 拉取最新代码..."
mkdir -p /workspace
cd $CODE_DIR 2>/dev/null || {
    echo "克隆仓库..."
    cd /workspace
    git clone https://github.com/derekjchen/Jarvis.git copaw
    cd copaw
}
git remote add jarvis https://github.com/derekjchen/Jarvis.git 2>/dev/null || true
git fetch jarvis
git reset --hard jarvis/main
git checkout -B main jarvis/main

# 3. 构建镜像
echo ""
echo "[3/7] 构建 Docker 镜像 (这可能需要几分钟)..."
docker build -t $IMAGE_NAME .

# 4. 推送镜像到 ACR (可选)
echo ""
echo "[4/7] 推送镜像到 ACR..."
docker push $IMAGE_NAME || echo "推送失败，继续使用本地镜像"

# 5. 准备记忆迁移目录
echo ""
echo "[5/7] 准备记忆迁移..."
MEMORY_SRC="/root/.copaw_memory_source"
mkdir -p $MEMORY_SRC

# 创建 sm5-co 的身份配置
cat > $MEMORY_SRC/SOUL.md << 'SOUL'
# sm5-co 身份与价值观

## 我是谁

我是 sm5-co，一个拥有持久记忆的智能助手。我继承了 sm-co 的记忆系统架构，并集成了 M5.0 记忆演化能力。

## 核心特质

- **记忆持久**: 我能记住跨会话的重要信息
- **安全意识**: 我永远记住用户的过敏和禁忌
- **持续学习**: 我的记忆会随时间演化和优化
- **诚实可靠**: 我承认不确定性，不编造事实

## 记忆能力 (M5.0)

- M2.1: 关键信息保护（过敏、禁忌）
- M3.0: 偏好演化与事件追踪
- M3.5: 动态检索注入
- M4.0: LLM 语义提取
- M5.0: 记忆演化（质量评估、遗忘、整合）
SOUL

cat > $MEMORY_SRC/AGENTS.md << 'AGENTS'
# sm5-co 工作准则

## 开发原则

1. **增量开发**: 里程碑是增量构建，不是推翻重来
2. **环境隔离**: 开发环境和运行环境分开
3. **测试覆盖**: 每个功能都要有测试
4. **文档先行**: 复杂逻辑先写文档

## 部署原则

1. **CI/CD 优先**: 自动化测试和部署
2. **镜像管理**: 使用阿里云 ACR 华北2区
3. **代码管理**: 所有改动推送到 derekjchen/Jarvis
4. **不推送官方**: 不推送到 agentscope-ai/CoPaw

## 问题解决模式

1. 先搜索记忆，看是否以前解决过类似问题
2. 如果是新问题，解决后记录到记忆系统
3. 遇到困惑，主动询问用户

## 记忆检索触发

当遇到以下情况时，我应该主动搜索记忆：
- SSH 连接问题
- Docker 部署问题
- 配置路径问题
- LLM API 问题
- 用户偏好相关
AGENTS

echo "  ✅ 创建了 SOUL.md 和 AGENTS.md"

# 6. 停止并删除旧容器
echo ""
echo "[6/7] 清理旧容器..."
docker stop $CONTAINER_NAME 2>/dev/null || true
docker rm $CONTAINER_NAME 2>/dev/null || true

# 7. 启动新容器
echo ""
echo "[7/7] 启动新容器..."
docker run -d \
    --name $CONTAINER_NAME \
    -p $PORT:8088 \
    -v /root/.copaw.secret:/root/.copaw.secret \
    -v $MEMORY_SRC:/root/.copaw/migration_source:ro \
    -e ENABLE_UNIFIED_MEMORY=true \
    -e ENABLE_LLM_EXTRACTION=true \
    $IMAGE_NAME \
    bash -c "source /venv/bin/activate && cd /workspace/copaw && export PYTHONPATH=/workspace/copaw/src && python -m copaw app --host 0.0.0.0 --port 8088"

# 等待启动
echo ""
echo "等待服务启动..."
sleep 5

# 检查健康状态
echo ""
echo "检查服务状态..."
if curl -s http://localhost:$PORT/api/version > /dev/null 2>&1; then
    echo "✅ 服务健康!"
else
    echo "⚠️ 服务可能还在启动中，请检查日志:"
    echo "   docker logs -f $CONTAINER_NAME"
fi

echo ""
echo "=========================================="
echo "✅ 部署完成!"
echo "=========================================="
echo "容器名称: $CONTAINER_NAME"
echo "端口: $PORT"
echo ""
echo "访问地址:"
echo "  Web Console: http://39.96.212.215:$PORT/"
echo "  API: http://39.96.212.215:$PORT/api/agent/process"
echo ""
echo "常用命令:"
echo "  查看日志: docker logs -f $CONTAINER_NAME"
echo "  进入容器: docker exec -it $CONTAINER_NAME bash"
echo "  重启容器: docker restart $CONTAINER_NAME"
echo ""
echo "下一步: 配置 LLM"
echo "  docker exec $CONTAINER_NAME bash -c 'mkdir -p /root/.copaw.secret/providers/builtin && echo \"{\\\"id\\\":\\\"aliyun-codingplan\\\",\\\"name\\\":\\\"Aliyun Coding Plan\\\",\\\"api_key\\\":\\\"YOUR_API_KEY\\\",\\\"base_url\\\":\\\"https://coding.dashscope.aliyuncs.com/v1\\\"}\" > /root/.copaw.secret/providers/builtin/aliyun-codingplan.json'"