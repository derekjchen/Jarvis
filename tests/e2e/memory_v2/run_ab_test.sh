#!/bin/bash
# A/B 测试脚本 - 通过 SSH 执行

RESULTS_DIR="/root/copaw/agent_coordination/wiki/ab_test_results"
mkdir -p "$RESULTS_DIR"

ROUND=$1
[ -z "$ROUND" ] && ROUND=1

LOG_FILE="$RESULTS_DIR/round_${ROUND}_$(date +%Y%m%d_%H%M%S).log"
JSON_FILE="$RESULTS_DIR/round_${ROUND}.json"

echo "A/B 测试 - 第 $ROUND 轮" | tee "$LOG_FILE"
echo "开始时间: $(date)" | tee -a "$LOG_FILE"
echo "========================================" | tee -a "$LOG_FILE"

# 测试用例
declare -a TESTS=(
    "T01:张伟是我的同事，他在北京工作"
    "T02:我们正在开发火星探测项目，预计明年完成"
    "T03:系统使用Python和Kubernetes构建，数据库用PostgreSQL"
    "T04:项目将在2025年6月15日正式发布"
    "T05:这是一个分布式系统的设计，采用了微服务架构"
    "T06:阿里巴巴和腾讯都在投资航天领域"
    "T07:我们在北京、上海和深圳都有研发中心"
)

# JSON 结果
echo '{"round": '$ROUND', "timestamp": "'$(date -Iseconds)'", "results": [' > "$JSON_FILE"

FIRST=1
for TEST in "${TESTS[@]}"; do
    TID=$(echo $TEST | cut -d: -f1)
    MSG=$(echo $TEST | cut -d: -f2-)
    
    echo "" | tee -a "$LOG_FILE"
    echo "[$TID] $MSG" | tee -a "$LOG_FILE"
    
    # OLD ECHO (本地)
    echo "  OLD ECHO..." | tee -a "$LOG_FILE"
    OLD_RESP=$(curl -s -X POST http://localhost:8093/api/agent/process \
        -H "Content-Type: application/json" \
        -d "{\"user_id\": \"ab_test\", \"session_id\": \"r${ROUND}_${TID}_old\", \"input\": [{\"role\": \"user\", \"content\": [{\"type\": \"text\", \"text\": \"$MSG\"}]}]}" \
        2>&1 | python3 -c "
import sys, json
text = ''
for line in sys.stdin:
    if line.startswith('data: '):
        try:
            d = json.loads(line[6:])
            if d.get('object') == 'content' and d.get('type') == 'text':
                text += d.get('text', '')
        except: pass
print(text[:300])
")
    echo "    -> $OLD_RESP" | tee -a "$LOG_FILE"
    
    # NEW ECHO (通过 SSH)
    echo "  NEW ECHO..." | tee -a "$LOG_FILE"
    NEW_RESP=$(sshpass -p 'archIact123' ssh -o StrictHostKeyChecking=no root@39.96.212.215 "
        curl -s -X POST http://localhost:8088/api/agent/process \
        -H 'Content-Type: application/json' \
        -d '{\"user_id\": \"ab_test\", \"session_id\": \"r${ROUND}_${TID}_new\", \"input\": [{\"role\": \"user\", \"content\": [{\"type\": \"text\", \"text\": \"$MSG\"}]}]}' \
        2>&1
    " | python3 -c "
import sys, json
text = ''
for line in sys.stdin:
    if line.startswith('data: '):
        try:
            d = json.loads(line[6:])
            if d.get('object') == 'content' and d.get('type') == 'text':
                text += d.get('text', '')
        except: pass
print(text[:300])
")
    echo "    -> $NEW_RESP" | tee -a "$LOG_FILE"
    
    # 写入 JSON
    [ $FIRST -eq 0 ] && echo ',' >> "$JSON_FILE"
    FIRST=0
    echo '{"test_id": "'$TID'", "input": "'$MSG'", "old_echo": "'$OLD_RESP'", "new_echo": "'$NEW_RESP'"}' >> "$JSON_FILE"
    
    sleep 1
done

echo ']}' >> "$JSON_FILE"
echo "" | tee -a "$LOG_FILE"
echo "========================================" | tee -a "$LOG_FILE"
echo "完成时间: $(date)" | tee -a "$LOG_FILE"
echo "日志文件: $LOG_FILE" | tee -a "$LOG_FILE"
echo "JSON文件: $JSON_FILE" | tee -a "$LOG_FILE"