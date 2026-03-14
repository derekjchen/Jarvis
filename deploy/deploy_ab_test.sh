#!/bin/bash
# A/B 测试环境部署脚本
# 在 ECS 宿主机执行

set -e

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}  A/B 测试环境部署脚本${NC}"
echo -e "${GREEN}========================================${NC}"

# 配置
JARVIS_REPO="https://github.com/derekjchen/Jarvis.git"
BRANCH="dev-ab-test-setup"
DEPLOY_DIR="/root/ab_test_deploy"
OLD_ECHO_PORT=8093
NEW_ECHO_PORT=8088

# Step 1: 克隆代码
echo -e "\n${YELLOW}Step 1: 克隆代码仓库...${NC}"
if [ -d "$DEPLOY_DIR" ]; then
    echo -e "${BLUE}目录已存在，更新代码...${NC}"
    cd $DEPLOY_DIR
    git fetch origin
    git checkout $BRANCH
    git pull origin $BRANCH
else
    echo -e "${BLUE}克隆仓库...${NC}"
    git clone -b $BRANCH $JARVIS_REPO $DEPLOY_DIR
    cd $DEPLOY_DIR
fi

# Step 2: 创建配置目录
echo -e "\n${YELLOW}Step 2: 创建配置目录...${NC}"
mkdir -p $DEPLOY_DIR/config/old_echo
mkdir -p $DEPLOY_DIR/config/new_echo
mkdir -p $DEPLOY_DIR/data/old_echo/memory
mkdir -p $DEPLOY_DIR/data/old_echo/file_store
mkdir -p $DEPLOY_DIR/data/new_echo/memory
mkdir -p $DEPLOY_DIR/data/new_echo/file_store

# Step 3: 复制配置文件
echo -e "\n${YELLOW}Step 3: 复制配置文件...${NC}"

# OLD ECHO 配置
cat > $DEPLOY_DIR/config/old_echo/config.json << 'CONFIG_EOF'
{
  "channels": {"console": {"enabled": true}},
  "mcp": {"clients": {}},
  "tools": {
    "builtin_tools": {
      "execute_shell_command": {"enabled": true},
      "read_file": {"enabled": true},
      "write_file": {"enabled": true},
      "edit_file": {"enabled": true},
      "browser_use": {"enabled": true},
      "desktop_screenshot": {"enabled": true},
      "send_file_to_user": {"enabled": true},
      "get_current_time": {"enabled": true},
      "get_token_usage": {"enabled": true},
      "memory_search": {"enabled": true}
    }
  },
  "last_api": {"host": "0.0.0.0", "port": 8093},
  "agents": {
    "defaults": {"heartbeat": {"enabled": false}},
    "running": {
      "max_iters": 50,
      "max_input_length": 131072,
      "memory_compact_ratio": 0.75,
      "memory_reserve_ratio": 0.1
    },
    "llm_routing": {"enabled": false},
    "language": "zh"
  },
  "security": {"tool_guard": {"enabled": true}},
  "show_tool_details": true,
  "memory": {"enable_v2": false}
}
CONFIG_EOF

# NEW ECHO 配置
cat > $DEPLOY_DIR/config/new_echo/config.json << 'CONFIG_EOF'
{
  "channels": {"console": {"enabled": true}},
  "mcp": {"clients": {}},
  "tools": {
    "builtin_tools": {
      "execute_shell_command": {"enabled": true},
      "read_file": {"enabled": true},
      "write_file": {"enabled": true},
      "edit_file": {"enabled": true},
      "browser_use": {"enabled": true},
      "desktop_screenshot": {"enabled": true},
      "send_file_to_user": {"enabled": true},
      "get_current_time": {"enabled": true},
      "get_token_usage": {"enabled": true},
      "memory_search": {"enabled": true}
    }
  },
  "last_api": {"host": "0.0.0.0", "port": 8088},
  "agents": {
    "defaults": {"heartbeat": {"enabled": false}},
    "running": {
      "max_iters": 50,
      "max_input_length": 131072,
      "memory_compact_ratio": 0.75,
      "memory_reserve_ratio": 0.1
    },
    "llm_routing": {"enabled": false},
    "language": "zh"
  },
  "security": {"tool_guard": {"enabled": true}},
  "show_tool_details": true,
  "memory": {"enable_v2": true}
}
CONFIG_EOF

# 复制 providers.json
echo -e "${BLUE}复制 providers.json...${NC}"
cp /root/.copaw/providers.json $DEPLOY_DIR/config/old_echo/
cp /root/.copaw/providers.json $DEPLOY_DIR/config/new_echo/

# 复制 secret 配置
echo -e "${BLUE}复制密钥配置...${NC}"
cp -r /root/.copaw.secret $DEPLOY_DIR/config/old_echo/
cp -r /root/.copaw.secret $DEPLOY_DIR/config/new_echo/

# Step 4: 复制数据文件
echo -e "\n${YELLOW}Step 4: 复制数据文件...${NC}"

# 复制记忆文件
cp -r /root/.copaw/memory/* $DEPLOY_DIR/data/old_echo/memory/
cp -r /root/.copaw/memory/* $DEPLOY_DIR/data/new_echo/memory/

# 复制向量数据库
cp -r /root/.copaw/file_store/* $DEPLOY_DIR/data/old_echo/file_store/
cp -r /root/.copaw/file_store/* $DEPLOY_DIR/data/new_echo/file_store/

# Step 5: 复制系统提示文件
echo -e "\n${YELLOW}Step 5: 复制系统提示文件...${NC}"
mkdir -p $DEPLOY_DIR/data/old_echo/prompts
mkdir -p $DEPLOY_DIR/data/new_echo/prompts

for file in AGENTS.md SOUL.md PROFILE.md MEMORY.md; do
    if [ -f "/root/.copaw/$file" ]; then
        cp /root/.copaw/$file $DEPLOY_DIR/data/old_echo/prompts/
        cp /root/.copaw/$file $DEPLOY_DIR/data/new_echo/prompts/
    fi
done

# Step 6: 显示部署信息
echo -e "\n${GREEN}========================================${NC}"
echo -e "${GREEN}  部署准备完成！${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""
echo -e "部署目录: ${YELLOW}$DEPLOY_DIR${NC}"
echo ""
echo -e "目录结构:"
echo "  config/"
echo "    old_echo/   (Memory V2 禁用, 端口 $OLD_ECHO_PORT)"
echo "    new_echo/   (Memory V2 启用, 端口 $NEW_ECHO_PORT)"
echo "  data/"
echo "    old_echo/memory/"
echo "    old_echo/file_store/"
echo "    new_echo/memory/"
echo "    new_echo/file_store/"
echo ""
echo -e "${YELLOW}下一步: 运行启动脚本${NC}"
echo "  cd $DEPLOY_DIR/deploy"
echo "  ./start_ab_test.sh"