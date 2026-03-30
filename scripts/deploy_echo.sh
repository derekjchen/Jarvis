#!/bin/bash
# Echo 部署脚本

ECHO_IP="39.96.212.215"
ECHO_USER="root"
ECHO_PASS="archIact123"

echo "=== 打包代码 ==="
cd /root/copaw
tar -czf /tmp/echo_deploy.tar.gz \
    src/copaw/agents/memory/memory_manager.py \
    src/copaw/memory_v2/ \
    src/copaw/agents/hooks/semantic_memory.py

echo ""
echo "=== 传输到 Echo ==="
sshpass -p "$ECHO_PASS" scp -o StrictHostKeyChecking=no \
    /tmp/echo_deploy.tar.gz $ECHO_USER@$ECHO_IP:/root/

echo ""
echo "=== 部署并重启 ==="
sshpass -p "$ECHO_PASS" ssh -o StrictHostKeyChecking=no $ECHO_USER@$ECHO_IP '
cd /root/copaw
tar -xzf /root/echo_deploy.tar.gz

echo "文件已部署"

# 保留记忆文件
echo "保留记忆文件..."

# 重启服务
pkill -f "start_copaw.py" 2>/dev/null
sleep 3

source venv/bin/activate
nohup python /root/start_copaw.py app --host 0.0.0.0 --port 8088 > /tmp/copaw.log 2>&1 &
echo "服务已重启，PID: $!"

sleep 10

echo ""
echo "=== 检查状态 ==="
ps aux | grep copaw | grep -v grep | head -1
netstat -tlnp | grep 8088

echo ""
echo "=== V2 初始化日志 ==="
grep -i "memory_v2\|V2 semantic" /tmp/copaw.log
'

echo ""
echo "=== 部署完成 ==="