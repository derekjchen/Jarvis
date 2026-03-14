#!/bin/bash
# A/B 测试 Docker 部署脚本
# 在 ECS 宿主机执行

set -e

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
RED='\033[0;31m'
NC='\033[0m'

echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}  A/B 测试 Docker 部署${NC}"
echo -e "${GREEN}========================================${NC}"

DEPLOY_DIR="/root/ab_test_deploy"
DEV_CONTAINER_ID="5241d649524d"

# Step 1: 创建目录结构
echo -e "\n${YELLOW}Step 1: 创建目录结构...${NC}"
mkdir -p $DEPLOY_DIR/{config/old_echo,config/new_echo,config/test_agent}
mkdir -p $DEPLOY_DIR/data/old_echo/{memory,file_store,prompts}
mkdir -p $DEPLOY_DIR/data/new_echo/{memory,file_store,prompts}
mkdir -p $DEPLOY_DIR/logs
mkdir -p $DEPLOY_DIR/tests/ab_test

# Step 2: 克隆/更新代码
echo -e "\n${YELLOW}Step 2: 更新代码仓库...${NC}"
if [ -d "$DEPLOY_DIR/src" ]; then
    cd $DEPLOY_DIR/src
    git fetch origin
    git checkout dev-ab-test-setup
    git pull origin dev-ab-test-setup
else
    git clone -b dev-ab-test-setup https://github.com/derekjchen/Jarvis.git $DEPLOY_DIR/src
fi

# Step 3: 复制配置文件
echo -e "\n${YELLOW}Step 3: 复制配置文件...${NC}"

# OLD ECHO 配置
cp $DEPLOY_DIR/src/deploy/old_echo/config.json $DEPLOY_DIR/config/old_echo/
cp /root/.copaw/providers.json $DEPLOY_DIR/config/old_echo/
cp -r /root/.copaw.secret $DEPLOY_DIR/config/old_echo/

# NEW ECHO 配置
cp $DEPLOY_DIR/src/deploy/new_echo/config.json $DEPLOY_DIR/config/new_echo/
cp /root/.copaw/providers.json $DEPLOY_DIR/config/new_echo/
cp -r /root/.copaw.secret $DEPLOY_DIR/config/new_echo/

# Test Agent 配置
cp $DEPLOY_DIR/src/deploy/new_echo/config.json $DEPLOY_DIR/config/test_agent/
cp /root/.copaw/providers.json $DEPLOY_DIR/config/test_agent/
cp -r /root/.copaw.secret $DEPLOY_DIR/config/test_agent/

# Step 4: 复制数据文件
echo -e "\n${YELLOW}Step 4: 复制数据文件...${NC}"
cp -r /root/.copaw/memory/* $DEPLOY_DIR/data/old_echo/memory/ 2>/dev/null || true
cp -r /root/.copaw/memory/* $DEPLOY_DIR/data/new_echo/memory/ 2>/dev/null || true
cp -r /root/.copaw/file_store/* $DEPLOY_DIR/data/old_echo/file_store/ 2>/dev/null || true
cp -r /root/.copaw/file_store/* $DEPLOY_DIR/data/new_echo/file_store/ 2>/dev/null || true

# 系统提示文件
for f in AGENTS.md SOUL.md PROFILE.md MEMORY.md; do
    [ -f "/root/.copaw/$f" ] && cp /root/.copaw/$f $DEPLOY_DIR/data/old_echo/prompts/
    [ -f "/root/.copaw/$f" ] && cp /root/.copaw/$f $DEPLOY_DIR/data/new_echo/prompts/
done

# Step 5: 复制测试文件
echo -e "\n${YELLOW}Step 5: 复制测试文件...${NC}"
cp -r $DEPLOY_DIR/src/tests/ab_test/* $DEPLOY_DIR/tests/ab_test/

# Step 6: 复制 Docker Compose 配置
echo -e "\n${YELLOW}Step 6: 复制 Docker 配置...${NC}"
cp $DEPLOY_DIR/src/deploy/docker-compose.yml $DEPLOY_DIR/
cp $DEPLOY_DIR/src/deploy/Dockerfile $DEPLOY_DIR/

# Step 7: 构建 Docker 镜像
echo -e "\n${YELLOW}Step 7: 构建 Docker 镜像...${NC}"
cd $DEPLOY_DIR
if [ -f "/root/copaw/deploy/Dockerfile" ]; then
    # 使用现有代码构建
    cd /root/copaw
    docker build -t copaw:latest -f deploy/Dockerfile .
else
    echo -e "${YELLOW}使用 Jarvis 仓库的 Dockerfile...${NC}"
    cd $DEPLOY_DIR/src
    docker build -t copaw:latest -f deploy/Dockerfile .
fi

# Step 8: 创建 Docker Network
echo -e "\n${YELLOW}Step 8: 创建 Docker Network...${NC}"
docker network create copaw-network 2>/dev/null || echo "Network already exists"

# Step 9: 连接开发容器到网络
echo -e "\n${YELLOW}Step 9: 连接开发容器到网络...${NC}"
docker network connect copaw-network $DEV_CONTAINER_ID 2>/dev/null || echo "Container already connected"

# Step 10: 启动服务
echo -e "\n${YELLOW}Step 10: 启动 A/B 测试服务...${NC}"
cd $DEPLOY_DIR
docker-compose down 2>/dev/null || true
docker-compose up -d

# Step 11: 等待服务启动
echo -e "\n${YELLOW}Step 11: 等待服务启动...${NC}"
sleep 10

# Step 12: 验证服务
echo -e "\n${YELLOW}Step 12: 验证服务状态...${NC}"
echo ""
echo "OLD ECHO (Memory V2 禁用):"
curl -s http://localhost:8093/health 2>/dev/null && echo -e " ${GREEN}✓ 运行正常${NC}" || echo -e " ${RED}✗ 未就绪${NC}"

echo "NEW ECHO (Memory V2 启用):"
curl -s http://localhost:8094/health 2>/dev/null && echo -e " ${GREEN}✓ 运行正常${NC}" || echo -e " ${RED}✗ 未就绪${NC}"

# 显示网络信息
echo ""
echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}  部署完成！${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""
echo -e "服务地址 (宿主机访问):"
echo -e "  OLD ECHO: ${BLUE}http://localhost:8093${NC}"
echo -e "  NEW ECHO: ${BLUE}http://localhost:8094${NC}"
echo -e "  主 Agent: ${BLUE}http://localhost:8088${NC} (已运行)"
echo ""
echo -e "服务地址 (Docker Network 内部访问):"
echo -e "  OLD ECHO: ${BLUE}http://old-echo:8088${NC}"
echo -e "  NEW ECHO: ${BLUE}http://new-echo:8088${NC}"
echo ""
echo -e "当前开发容器 ($DEV_CONTAINER_ID) 已连接到 copaw-network"
echo ""
echo -e "${YELLOW}查看日志:${NC}"
echo "  docker logs copaw-old-echo -f"
echo "  docker logs copaw-new-echo -f"
echo ""
echo -e "${YELLOW}停止服务:${NC}"
echo "  cd $DEPLOY_DIR && docker-compose down"