#!/bin/bash
# A/B 测试环境部署脚本
# 在宿主机上执行

set -e

# 配置
NETWORK_NAME="ab-test-net"
OLD_ECHO_NAME="old-echo"
NEW_ECHO_NAME="new-echo"
OLD_ECHO_PORT=8093
NEW_ECHO_PORT=8094
JARVIS_REPO="https://github.com/derekjchen/Jarvis.git"
DEV_BRANCH="dev-ab-test-setup"

# 颜色输出
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

log_info() { echo -e "${GREEN}[INFO]${NC} $1"; }
log_warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }
log_error() { echo -e "${RED}[ERROR]${NC} $1"; }

# 检查 Docker
check_docker() {
    if ! command -v docker &> /dev/null; then
        log_error "Docker 未安装"
        exit 1
    fi
    log_info "Docker 已安装"
}

# 创建网络
create_network() {
    if docker network ls | grep -q "$NETWORK_NAME"; then
        log_info "网络 $NETWORK_NAME 已存在"
    else
        docker network create "$NETWORK_NAME"
        log_info "网络 $NETWORK_NAME 创建成功"
    fi
}

# 部署 OLD ECHO (baseline, Memory V1)
deploy_old_echo() {
    log_info "部署 OLD ECHO (Memory V1 baseline)..."
    
    # 检查是否已存在
    if docker ps -a | grep -q "$OLD_ECHO_NAME"; then
        log_warn "容器 $OLD_ECHO_NAME 已存在，删除中..."
        docker rm -f "$OLD_ECHO_NAME"
    fi
    
    # 创建工作目录
    mkdir -p /root/old_echo_working
    
    # 创建配置文件 (禁用 Memory V2)
    cat > /root/old_echo_working/config.json << 'EOF'
{
  "agents": {
    "memory": {
      "enable_v2": false
    }
  }
}
EOF
    
    # 获取当前镜像
    IMAGE=$(docker inspect copaw-new --format '{{.Config.Image}}' 2>/dev/null || echo "agentscope-registry.ap-southeast-1.cr.aliyuncs.com/agentscope/copaw:latest")
    log_info "使用镜像: $IMAGE"
    
    # 启动容器
    docker run -d \
        --name "$OLD_ECHO_NAME" \
        --network "$NETWORK_NAME" \
        -p $OLD_ECHO_PORT:8088 \
        -v /root/old_echo_working:/app/working \
        -v /root/copaw_old_echo_secret:/app/working.secret \
        --memory="1g" \
        "$IMAGE"
    
    log_info "OLD ECHO 启动成功，端口: $OLD_ECHO_PORT"
}

# 部署 NEW ECHO (experimental, Memory V2)
deploy_new_echo() {
    log_info "部署 NEW ECHO (Memory V2 experimental)..."
    
    # 检查是否已存在
    if docker ps -a | grep -q "$NEW_ECHO_NAME"; then
        log_warn "容器 $NEW_ECHO_NAME 已存在，删除中..."
        docker rm -f "$NEW_ECHO_NAME"
    fi
    
    # 清理旧的工作目录（全新部署）
    rm -rf /root/new_echo_working
    mkdir -p /root/new_echo_working
    
    # 创建配置文件 (启用 Memory V2)
    cat > /root/new_echo_working/config.json << 'EOF'
{
  "agents": {
    "memory": {
      "enable_v2": true
    }
  }
}
EOF
    
    # 克隆或更新 Jarvis 仓库
    if [ -d "/root/copaw-jarvis-dev" ]; then
        log_info "更新 Jarvis 仓库..."
        cd /root/copaw-jarvis-dev
        git fetch origin
        git checkout "$DEV_BRANCH"
        git pull origin "$DEV_BRANCH"
    else
        log_info "克隆 Jarvis 仓库..."
        cd /root
        git clone -b "$DEV_BRANCH" "$JARVIS_REPO" copaw-jarvis-dev
        cd copaw-jarvis-dev
    fi
    
    # 构建镜像（包含最新代码）
    log_info "构建 Docker 镜像..."
    docker build -t copaw:dev-latest .
    
    # 启动容器
    docker run -d \
        --name "$NEW_ECHO_NAME" \
        --network "$NETWORK_NAME" \
        -p $NEW_ECHO_PORT:8088 \
        -v /root/new_echo_working:/app/working \
        -v /root/copaw_new_echo_secret:/app/working.secret \
        --memory="1g" \
        copaw:dev-latest
    
    log_info "NEW ECHO 启动成功，端口: $NEW_ECHO_PORT"
}

# 验证部署
verify_deployment() {
    log_info "验证部署..."
    
    sleep 10  # 等待服务启动
    
    # 检查 OLD ECHO
    if curl -s -m 5 "http://localhost:$OLD_ECHO_PORT/api/health" > /dev/null 2>&1; then
        log_info "OLD ECHO 健康检查通过 ✅"
    else
        log_warn "OLD ECHO 健康检查失败，可能需要等待更长时间"
    fi
    
    # 检查 NEW ECHO
    if curl -s -m 5 "http://localhost:$NEW_ECHO_PORT/api/health" > /dev/null 2>&1; then
        log_info "NEW ECHO 健康检查通过 ✅"
    else
        log_warn "NEW ECHO 健康检查失败，可能需要等待更长时间"
    fi
}

# 显示使用说明
show_usage() {
    echo ""
    echo "========================================"
    echo "A/B 测试环境已就绪"
    echo "========================================"
    echo ""
    echo "容器信息:"
    echo "  OLD ECHO (V1): localhost:$OLD_ECHO_PORT"
    echo "  NEW ECHO (V2): localhost:$NEW_ECHO_PORT"
    echo ""
    echo "Docker 网络内访问:"
    echo "  OLD ECHO: http://$OLD_ECHO_NAME:8088"
    echo "  NEW ECHO: http://$NEW_ECHO_NAME:8088"
    echo ""
    echo "运行测试:"
    echo "  cd /root/copaw-jarvis-dev/tests/ab_test"
    echo "  python run_ab_test.py --old http://localhost:$OLD_ECHO_PORT --new http://localhost:$NEW_ECHO_PORT"
    echo ""
}

# 主函数
main() {
    log_info "开始部署 A/B 测试环境..."
    
    check_docker
    create_network
    deploy_old_echo
    deploy_new_echo
    verify_deployment
    show_usage
    
    log_info "部署完成！"
}

# 解析参数
case "$1" in
    old)
        deploy_old_echo
        ;;
    new)
        deploy_new_echo
        ;;
    verify)
        verify_deployment
        ;;
    all|*)
        main
        ;;
esac