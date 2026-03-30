# A/B 测试方案

> 创建时间: 2026-03-08
> 状态: 准备中

## 1. 测试目标

对比 Memory V2 启用/禁用的效果差异：
- 实体提取准确率
- 记忆召回率
- 跨会话记忆能力
- 响应时间

## 2. 测试环境

| 环境 | 地址 | Memory V2 | 用途 |
|------|------|-----------|------|
| NEW ECHO | 39.96.212.215:8088 | 启用 (enable_v2=true) | 实验组 |
| OLD ECHO | localhost:8093 | 禁用 (enable_v2=false) | 对照组 |

## 3. 测试用例

位于 `/root/copaw/tests/e2e/memory_v2/test_cases/`

| 文件 | 用例数 | 测试内容 |
|------|--------|---------|
| entity_extraction.json | 7 | 人名、地点、项目、技术、日期、概念、组织 |
| memory_type.json | 4 | 不同类型记忆的存储和召回 |
| relation_extraction.json | 3 | 实体关系提取 |
| cross_session.json | 4 | 跨会话记忆能力 |
| edge_cases.json | 4 | 边界情况处理 |

**总计**: 22 个测试用例

## 4. 并行测试方案

### 4.1 测试脚本

```python
# ab_test_runner.py
import asyncio
import aiohttp
import json
from datetime import datetime

NEW_ECHO = "http://39.96.212.215:8088"
OLD_ECHO = "http://localhost:8093"

async def send_request(session, url, test_case):
    """发送测试请求"""
    payload = {
        "session_id": test_case["test_id"],
        "user_id": "ab_test",
        "input": [{"role": "user", "type": "message", "content": [{"type": "text", "text": test_case["input"]}]}]
    }
    start = datetime.now()
    async with session.post(f"{url}/api/agent/process", json=payload) as resp:
        result = await resp.text()
    elapsed = (datetime.now() - start).total_seconds()
    return {"response": result, "elapsed": elapsed}

async def run_parallel_test(test_case):
    """并行测试两组"""
    async with aiohttp.ClientSession() as session:
        tasks = [
            send_request(session, NEW_ECHO, test_case),
            send_request(session, OLD_ECHO, test_case)
        ]
        results = await asyncio.gather(*tasks)
        return {
            "test_id": test_case["test_id"],
            "new_echo": results[0],
            "old_echo": results[1]
        }
```

### 4.2 执行顺序

1. 按测试文件顺序执行
2. 每个用例并行发送到两组
3. 记录响应时间和结果
4. 生成对比报告

## 5. 结果报告格式

### 5.1 对比指标

| 指标 | NEW ECHO | OLD ECHO | 差异 |
|------|----------|----------|------|
| 平均响应时间 | Xs | Ys | +Z% |
| 实体提取准确率 | X% | Y% | +Z% |
| 记忆召回率 | X% | Y% | +Z% |

### 5.2 报告模板

```markdown
# A/B 测试报告

**测试时间**: YYYY-MM-DD HH:MM
**测试用例数**: 22

## 结果汇总

| 指标 | NEW ECHO | OLD ECHO | 结论 |
|------|----------|----------|------|
| 响应时间 | | | |
| 准确率 | | | |

## 详细分析

### 实体提取
- ...

### 跨会话记忆
- ...

## 结论

Memory V2 效果评估：显著提升 / 无明显差异 / 需要优化
```

## 6. 执行前检查清单

- [ ] NEW ECHO 服务正常
- [ ] OLD ECHO 服务正常
- [ ] 测试用例文件存在
- [ ] LLM API key 配置正确
- [ ] 网络连通性正常

## 7. 执行命令

```bash
# 启动测试
cd /root/copaw/tests/e2e/memory_v2
python run_ab_test.py --new-echo http://39.96.212.215:8088 --old-echo http://localhost:8093

# 查看报告
cat /root/copaw/agent_coordination/wiki/AB_TEST_REPORT.md
```