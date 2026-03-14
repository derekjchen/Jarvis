#!/usr/bin/env python3
"""
Memory V2 A/B 测试框架

测试目标：对比 V1 (OLD ECHO) 和 V2 (NEW ECHO) 的记忆能力

测试环境：
- OLD ECHO: localhost:8093 (V1 对照组)
- NEW ECHO: 39.96.212.215:8088 (V2 实验组)

测试方法：图灵测试式，不告诉用户哪个是哪个
"""

import requests
import json
import time
from datetime import datetime

# 测试环境配置
OLD_ECHO = "http://localhost:8093"
NEW_ECHO = "http://39.96.212.215:8088"

# 测试用例
TEST_CASES = [
    {
        "id": "E1_无遗忘_细节",
        "capability": "无遗忘的全量记忆",
        "prompt": "我之前告诉过你我的 Python 版本是多少？",
        "expected_keywords": ["3.11.4", "Python"],
        "evaluation": "是否准确记住 Python 版本"
    },
    {
        "id": "E2_无遗忘_时间",
        "capability": "无遗忘的全量记忆",
        "prompt": "我们什么时候讨论过 sqlite3 的问题？",
        "expected_keywords": ["sqlite3", "版本"],
        "evaluation": "是否能回忆起讨论时间和内容"
    },
    {
        "id": "E5_高效检索_模糊",
        "capability": "低耗的高效检索",
        "prompt": "数据库",
        "expected_keywords": ["sqlite3", "数据库"],
        "evaluation": "能否通过模糊关键词找到相关记忆"
    },
    {
        "id": "E8_实体关联",
        "capability": "跨时空的关联记忆",
        "prompt": "sqlite3",
        "expected_keywords": ["Python", "sqlite3"],
        "evaluation": "能否关联 sqlite3 和 Python"
    },
    {
        "id": "E3_跨场景",
        "capability": "跨时空的关联记忆",
        "prompt": "我们讨论过哪些技术问题？",
        "expected_keywords": ["sqlite3", "Python"],
        "evaluation": "能否关联不同场景的技术讨论"
    }
]

def call_echo(endpoint, prompt, session_id="ab_test"):
    """调用 ECHO API"""
    url = f"{endpoint}/v1/chat"
    payload = {
        "prompt": prompt,
        "session_id": session_id,
        "user_id": "ab_tester"
    }
    
    try:
        start_time = time.time()
        response = requests.post(url, json=payload, timeout=30)
        elapsed = time.time() - start_time
        
        if response.status_code == 200:
            data = response.json()
            return {
                "success": True,
                "response": data.get("response", ""),
                "elapsed": elapsed,
                "error": None
            }
        else:
            return {
                "success": False,
                "response": None,
                "elapsed": elapsed,
                "error": f"HTTP {response.status_code}"
            }
    except Exception as e:
        return {
            "success": False,
            "response": None,
            "elapsed": 0,
            "error": str(e)
        }

def evaluate_response(response, expected_keywords):
    """评估回复质量"""
    if not response:
        return {"score": 0, "matched": [], "reason": "无回复"}
    
    response_lower = response.lower()
    matched = [kw for kw in expected_keywords if kw.lower() in response_lower]
    score = len(matched) / len(expected_keywords) * 100 if expected_keywords else 0
    
    return {
        "score": score,
        "matched": matched,
        "reason": f"匹配 {len(matched)}/{len(expected_keywords)} 个关键词"
    }

def run_test_case(test_case, endpoint, label):
    """运行单个测试用例"""
    print(f"\n{'='*60}")
    print(f"测试用例: {test_case['id']}")
    print(f"能力: {test_case['capability']}")
    print(f"提示: {test_case['prompt']}")
    print(f"{'='*60}")
    
    result = call_echo(endpoint, test_case['prompt'])
    
    if result['success']:
        evaluation = evaluate_response(result['response'], test_case['expected_keywords'])
        print(f"\n[{label}] 回复:")
        print(f"{result['response'][:500]}...")
        print(f"\n评估: {evaluation['reason']}")
        print(f"匹配关键词: {evaluation['matched']}")
        print(f"耗时: {result['elapsed']:.2f}s")
    else:
        evaluation = {"score": 0, "matched": [], "reason": result['error']}
        print(f"\n[{label}] 错误: {result['error']}")
    
    return {
        "test_id": test_case['id'],
        "capability": test_case['capability'],
        "prompt": test_case['prompt'],
        "endpoint": label,
        "success": result['success'],
        "response": result['response'],
        "elapsed": result['elapsed'],
        "evaluation": evaluation,
        "error": result['error']
    }

def run_ab_test():
    """运行完整的 A/B 测试"""
    print("="*60)
    print("Memory V2 A/B 测试")
    print(f"时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("="*60)
    
    results = {
        "old_echo": [],
        "new_echo": [],
        "comparison": []
    }
    
    for test_case in TEST_CASES:
        # 测试 OLD ECHO (V1)
        old_result = run_test_case(test_case, OLD_ECHO, "OLD ECHO (V1)")
        results['old_echo'].append(old_result)
        
        time.sleep(1)  # 避免请求过快
        
        # 测试 NEW ECHO (V2)
        new_result = run_test_case(test_case, NEW_ECHO, "NEW ECHO (V2)")
        results['new_echo'].append(new_result)
        
        # 对比
        comparison = {
            "test_id": test_case['id'],
            "capability": test_case['capability'],
            "old_score": old_result['evaluation']['score'],
            "new_score": new_result['evaluation']['score'],
            "old_time": old_result['elapsed'],
            "new_time": new_result['elapsed'],
            "winner": "NEW" if new_result['evaluation']['score'] > old_result['evaluation']['score'] 
                     else "OLD" if old_result['evaluation']['score'] > new_result['evaluation']['score']
                     else "TIE"
        }
        results['comparison'].append(comparison)
        
        print(f"\n对比: OLD {old_result['evaluation']['score']:.0f}分 vs NEW {new_result['evaluation']['score']:.0f}分 → {comparison['winner']}")
        
        time.sleep(2)  # 测试间隔
    
    # 汇总报告
    print("\n" + "="*60)
    print("测试汇总")
    print("="*60)
    
    old_total = sum(c['old_score'] for c in results['comparison'])
    new_total = sum(c['new_score'] for c in results['comparison'])
    
    print(f"\n总分对比:")
    print(f"  OLD ECHO (V1): {old_total:.0f}分")
    print(f"  NEW ECHO (V2): {new_total:.0f}分")
    
    print(f"\n各能力对比:")
    for c in results['comparison']:
        print(f"  {c['capability']}: OLD {c['old_score']:.0f} vs NEW {c['new_score']:.0f} → {c['winner']}")
    
    # 保存结果
    report_path = f"/root/.copaw/memory_v2_ab_test_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    with open(report_path, 'w', encoding='utf-8') as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    
    print(f"\n详细报告已保存: {report_path}")
    
    return results

if __name__ == "__main__":
    run_ab_test()