#!/usr/bin/env python3
"""
简化版 A/B 测试脚本 - 边测边输出
"""
import json
import requests
import time
from datetime import datetime

NEW_ECHO = "http://39.96.212.215:8088/api/agent/process"
OLD_ECHO = "http://localhost:8093/api/agent/process"

def test_endpoint(url, message, session_id):
    """发送请求并返回结果"""
    payload = {
        "user_id": "ab_test",
        "session_id": session_id,
        "input": [{"role": "user", "content": [{"type": "text", "text": message}]}]
    }
    try:
        start = time.time()
        r = requests.post(url, json=payload, stream=True, timeout=30)
        response_text = ""
        for line in r.iter_lines():
            if line and line.startswith(b'data: '):
                try:
                    d = json.loads(line[6:])
                    if d.get('object') == 'content' and d.get('type') == 'text':
                        response_text += d.get('text', '')
                except: pass
        return {"ok": True, "text": response_text[:500], "ms": int((time.time()-start)*1000)}
    except Exception as e:
        return {"ok": False, "error": str(e)[:100], "ms": 0}

def run_test(tid, message, round_num):
    """运行单个测试"""
    print(f"\n[{tid}] {message[:40]}...")
    
    # NEW ECHO
    r1 = test_endpoint(NEW_ECHO, message, f"r{round_num}_{tid}_new")
    status1 = "✓" if r1["ok"] else "✗"
    print(f"  NEW: {status1} {r1.get('ms',0)}ms - {r1.get('text',r1.get('error',''))[:100]}")
    
    # OLD ECHO
    r2 = test_endpoint(OLD_ECHO, message, f"r{round_num}_{tid}_old")
    status2 = "✓" if r2["ok"] else "✗"
    print(f"  OLD: {status2} {r2.get('ms',0)}ms - {r2.get('text',r2.get('error',''))[:100]}")
    
    return {"tid": tid, "input": message, "new": r1, "old": r2, "time": datetime.now().isoformat()}

if __name__ == "__main__":
    import sys
    round_num = int(sys.argv[1]) if len(sys.argv) > 1 else 1
    
    # 读取所有测试用例
    import glob
    results = []
    
    for f in sorted(glob.glob("/root/copaw/tests/e2e/memory_v2/test_cases/*.json")):
        print(f"\n{'='*50}\n文件: {f.split('/')[-1]}\n{'='*50}")
        with open(f) as fp:
            cases = json.load(fp)
        for c in cases:
            r = run_test(c['test_id'], c['input'], round_num)
            results.append(r)
            time.sleep(0.5)
    
    # 保存结果
    out = {"round": round_num, "time": datetime.now().isoformat(), "results": results}
    with open(f"/root/copaw/agent_coordination/wiki/ab_test_results/round_{round_num}.json", "w") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
    print(f"\n结果已保存到 round_{round_num}.json")