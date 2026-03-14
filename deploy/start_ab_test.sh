#!/bin/bash
# 启动 A/B 测试服务
# 在 ECS 宿主机执行

set -e

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

DEPLOY_DIR="/root/ab_test_deploy"
OLD_ECHO_PORT=8093
NEW_ECHO_PORT=8088

echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}  启动 A/B 测试服务${NC}"
echo -e "${GREEN}========================================${NC}"

# 检查是否已部署
if [ ! -d "$DEPLOY_DIR" ]; then
    echo -e "${YELLOW}错误: 请先运行部署脚本 deploy_ab_test.sh${NC}"
    exit 1
fi

cd $DEPLOY_DIR

# 创建 Python 虚拟环境（如果不存在）
if [ ! -d "venv" ]; then
    echo -e "\n${YELLOW}创建 Python 虚拟环境...${NC}"
    python3 -m venv venv
    source venv/bin/activate
    pip install -e .
else
    source venv/bin/activate
fi

# 停止已有进程
echo -e "\n${YELLOW}停止已有服务进程...${NC}"
pkill -f "copaw.*--port $OLD_ECHO_PORT" 2>/dev/null || true
pkill -f "copaw.*--port $NEW_ECHO_PORT" 2>/dev/null || true

# 启动 OLD ECHO (Memory V2 禁用)
echo -e "\n${YELLOW}启动 OLD ECHO (Memory V2 禁用, 端口 $OLD_ECHO_PORT)...${NC}"
COPAW_DATA_DIR=$DEPLOY_DIR/data/old_echo \
COPAW_SECRET_DIR=$DEPLOY_DIR/config/old_echo/.copaw.secret \
nohup python -m copaw run --config $DEPLOY_DIR/config/old_echo/config.json > $DEPLOY_DIR/logs/old_echo.log 2>&1 &
echo "OLD ECHO PID: $!"

# 等待启动
sleep 3

# 启动 NEW ECHO (Memory V2 启用)
echo -e "\n${YELLOW}启动 NEW ECHO (Memory V2 启用, 端口 $NEW_ECHO_PORT)...${NC}"
COPAW_DATA_DIR=$DEPLOY_DIR/data/new_echo \
COPAW_SECRET_DIR=$DEPLOY_DIR/config/new_echo/.copaw.secret \
nohup python -m copaw run --config $DEPLOY_DIR/config/new_echo/config.json > $DEPLOY_DIR/logs/new_echo.log 2>&1 &
echo "NEW ECHO PID: $!"

# 等待服务启动
echo -e "\n${YELLOW}等待服务启动...${NC}"
sleep 5

# 验证服务
echo -e "\n${YELLOW}验证服务状态...${NC}"

check_service() {
    local port=$1
    local name=$2
    if curl -s "http://localhost:$port/health" > /dev/null 2>&1; then
        echo -e "  ${GREEN}✓ $name (端口 $port) 运行正常${NC}"
        return 0
    else
        echo -e "  ${YELLOW}⚠ $name (端口 $port) 可能未就绪${NC}"
        return 1
    fi
}

check_service $OLD_ECHO_PORT "OLD ECHO"
check_service $NEW_ECHO_PORT "NEW ECHO"

echo ""
echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}  A/B 测试服务已启动${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""
echo -e "服务地址:"
echo -e "  OLD ECHO (Memory V1): ${BLUE}http://localhost:$OLD_ECHO_PORT${NC}"
echo -e "  NEW ECHO (Memory V2): ${BLUE}http://localhost:$NEW_ECHO_PORT${NC}"
echo ""
echo -e "日志文件:"
echo "  $DEPLOY_DIR/logs/old_echo.log"
echo "  $DEPLOY_DIR/logs/new_echo.log"
echo ""
echo -e "${YELLOW}运行测试:${NC}"
echo "  cd $DEPLOY_DIR/tests/ab_test"
echo "  python run_ab_test.py"