#!/usr/bin/env python3
"""
Memory V2 A/B 测试框架

用法:
    python run_ab_test.py --old http://old-echo:8088 --new http://new-echo:8088
    python run_ab_test.py --old http://localhost:8093 --new http://localhost:8094
"""
import argparse
import json
import time
import requests
from pathlib import Path


def chat(endpoint: str, user_id: str, session_id: str, message: str, timeout: int = 90) -> str:
    """发送消息并返回响应"""
    try:
        resp = requests.post(
            f"{endpoint}/api/agent/process",
            json={
                "user_id": user_id,
                "session_id": session_id,
                "input": [{"role": "user", "content": [{"type": "text", "text": message}]}]
            },
            timeout=timeout,
            stream=True
        )
        
        # 读取流式响应，获取最终回复
        full_response = ""
        for line in resp.iter_lines():
            if line:
                line = line.decode('utf-8')
                if line.startswith('data: '):
                    try:
                        data = json.loads(line[6:])
                        if data.get('object') == 'content' and data.get('type') == 'text':
                            if data.get('delta'):
                                full_response += data.get('text', '')
                            elif data.get('text'):
                                full_response = data.get('text', '')
                    except json.JSONDecodeError:
                        pass
        return full_response
    except Exception as e:
        return f"ERROR: {e}"


def run_test_case(old_echo: str, new_echo: str, test_case: dict) -> dict:
    """执行单个测试用例"""
    test_id = f"{int(time.time())}-{test_case['id']}"
    
    print(f"\n{'='*60}")
    print(f"测试用例: {test_case['id']} - {test_case['name']}")
    print(f"{'='*60}")
    
    # === OLD ECHO (Memory V1) ===
    print("\n【OLD ECHO (V1)】")
    session_a = f"old-{test_id}-a"
    session_b = f"old-{test_id}-b"
    
    print(f"  前置对话: {test_case['preamble'][:50]}...")
    resp = chat(old_echo, f"test-{test_id}", session_a, test_case['preamble'])
    print(f"  响应: {resp[:100]}...")
    time.sleep(1)
    
    print(f"  测试问题: {test_case['test_question']}")
    old_resp = chat(old_echo, f"test-{test_id}", session_b, test_case['test_question'])
    print(f"  响应: {old_resp[:200]}...")
    
    # === NEW ECHO (Memory V2) ===
    print("\n【NEW ECHO (V2)】")
    session_a = f"new-{test_id}-a"
    session_b = f"new-{test_id}-b"
    
    print(f"  前置对话: {test_case['preamble'][:50]}...")
    resp = chat(new_echo, f"test-{test_id}", session_a, test_case['preamble'])
    print(f"  响应: {resp[:100]}...")
    time.sleep(3)  # 等待实体提取完成
    
    print(f"  测试问题: {test_case['test_question']}")
    new_resp = chat(new_echo, f"test-{test_id}", session_b, test_case['test_question'])
    print(f"  响应: {new_resp[:200]}...")
    
    # === 分析结果 ===
    expected = test_case['expected_keywords']
    print(f"\n【分析】")
    print(f"  期望关键词: {expected}")
    
    old_resp_lower = old_resp.lower()
    new_resp_lower = new_resp.lower()
    
    old_hits = [kw for kw in expected if kw.lower() in old_resp_lower]
    new_hits = [kw for kw in expected if kw.lower() in new_resp_lower]
    
    old_hit = len(old_hits) > 0
    new_hit = len(new_hits) > 0
    
    print(f"  OLD ECHO 命中: {'✅ ' + str(old_hits) if old_hit else '❌'}")
    print(f"  NEW ECHO 命中: {'✅ ' + str(new_hits) if new_hit else '❌'}")
    
    return {
        "id": test_case['id'],
        "name": test_case['name'],
        "category": test_case['category'],
        "old_hit": old_hit,
        "new_hit": new_hit,
        "old_hits": old_hits,
        "new_hits": new_hits,
        "old_response": old_resp[:500],
        "new_response": new_resp[:500]
    }


def main():
    parser = argparse.ArgumentParser(description='Memory V2 A/B 测试')
    parser.add_argument('--old', default='http://localhost:8093', help='OLD ECHO 地址 (Memory V1)')
    parser.add_argument('--new', default='http://localhost:8094', help='NEW ECHO 地址 (Memory V2)')
    parser.add_argument('--cases', default=None, help='测试用例 JSON 文件路径')
    parser.add_argument('--output', default='ab_test_results.json', help='结果输出文件')
    args = parser.parse_args()
    
    # 加载测试用例
    if args.cases:
        cases_path = Path(args.cases)
    else:
        cases_path = Path(__file__).parent / 'test_cases.json'
    
    with open(cases_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    test_cases = data['test_cases']
    
    print("="*60)
    print("Memory V2 A/B 测试")
    print("="*60)
    print(f"OLD ECHO: {args.old}")
    print(f"NEW ECHO: {args.new}")
    print(f"测试用例: {len(test_cases)} 个")
    print("="*60)
    
    # 执行测试
    results = []
    for tc in test_cases:
        result = run_test_case(args.old, args.new, tc)
        results.append(result)
        time.sleep(2)  # 测试间隔
    
    # 汇总统计
    print("\n" + "="*60)
    print("测试汇总")
    print("="*60)
    
    categories = {}
    for r in results:
        cat = r['category']
        if cat not in categories:
            categories[cat] = {'old': 0, 'new': 0, 'total': 0}
        categories[cat]['total'] += 1
        if r['old_hit']:
            categories[cat]['old'] += 1
        if r['new_hit']:
            categories[cat]['new'] += 1
    
    for cat, stats in categories.items():
        print(f"\n{cat}:")
        print(f"  OLD ECHO: {stats['old']}/{stats['total']}")
        print(f"  NEW ECHO: {stats['new']}/{stats['total']}")
    
    # 总计
    total_old = sum(r['old_hit'] for r in results)
    total_new = sum(r['new_hit'] for r in results)
    print(f"\n总计:")
    print(f"  OLD ECHO: {total_old}/{len(results)}")
    print(f"  NEW ECHO: {total_new}/{len(results)}")
    
    # 保存结果
    output = {
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        "config": {
            "old_echo": args.old,
            "new_echo": args.new
        },
        "summary": {
            "total": len(results),
            "old_hits": total_old,
            "new_hits": total_new
        },
        "by_category": categories,
        "results": results
    }
    
    with open(args.output, 'w', encoding='utf-8') as f:
        json.dump(output, f, ensure_ascii=False, indent=2)
    
    print(f"\n结果已保存到: {args.output}")


if __name__ == "__main__":
    main()