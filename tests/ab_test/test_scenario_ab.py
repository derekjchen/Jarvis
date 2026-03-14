#!/usr/bin/env python3
"""
Memory V2 场景测试：A/B 对比

测试目标：验证实体记忆在自然语言对话中的差异
"""
import requests
import time
import json

OLD_ECHO = "http://localhost:8093"
NEW_ECHO = "http://39.96.212.215:8088"

def chat(endpoint, user_id, session_id, message):
    """发送消息并返回响应"""
    try:
        resp = requests.post(f"{endpoint}/api/agent/process", json={
            "user_id": user_id,
            "session_id": session_id,
            "input": [{"role": "user", "content": [{"type": "text", "text": message}]}]
        }, timeout=90, stream=True)
        
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
                    except:
                        pass
        return full_response
    except Exception as e:
        return f"ERROR: {e}"

def run_scenario(name, preamble, test_question, expected_keywords):
    """执行一个测试场景"""
    print(f"\n{'='*60}")
    print(f"场景: {name}")
    print(f"{'='*60}")
    
    test_id = str(int(time.time()))
    
    # === OLD ECHO ===
    print("\n【OLD ECHO (V1)】")
    session_a = f"old-{test_id}-a"
    session_b = f"old-{test_id}-b"
    
    print(f"Session A: {preamble[:50]}...")
    resp = chat(OLD_ECHO, f"test-{test_id}", session_a, preamble)
    print(f"  响应: {resp[:100]}...")
    time.sleep(2)
    
    print(f"Session B: {test_question}")
    old_resp = chat(OLD_ECHO, f"test-{test_id}", session_b, test_question)
    print(f"  响应: {old_resp[:300]}")
    
    # === NEW ECHO ===
    print("\n【NEW ECHO (V2)】")
    session_a = f"new-{test_id}-a"
    session_b = f"new-{test_id}-b"
    
    print(f"Session A: {preamble[:50]}...")
    resp = chat(NEW_ECHO, f"test-{test_id}", session_a, preamble)
    print(f"  响应: {resp[:100]}...")
    time.sleep(3)  # 等待实体提取
    
    print(f"Session B: {test_question}")
    new_resp = chat(NEW_ECHO, f"test-{test_id}", session_b, test_question)
    print(f"  响应: {new_resp[:300]}")
    
    # === 分析 ===
    print(f"\n【分析】")
    print(f"期望关键词: {expected_keywords}")
    
    old_hit = any(kw.lower() in old_resp.lower() for kw in expected_keywords)
    new_hit = any(kw.lower() in new_resp.lower() for kw in expected_keywords)
    
    print(f"OLD ECHO 命中: {'✅' if old_hit else '❌'}")
    print(f"NEW ECHO 命中: {'✅' if new_hit else '❌'}")
    
    return {
        "name": name,
        "old_hit": old_hit,
        "new_hit": new_hit,
        "old_resp": old_resp[:200],
        "new_resp": new_resp[:200]
    }

if __name__ == "__main__":
    results = []
    
    print("="*60)
    print("Memory V2 场景测试")
    print("="*60)
    
    # 场景1: 细节回忆
    results.append(run_scenario(
        "场景1: 细节回忆 (Python版本)",
        "我最近在用 Python 3.11.4 做一个项目，遇到了一个 sqlite3 版本问题。",
        "我这个项目遇到个问题，sqlite3 版本太低了，你有啥建议？",
        ["3.11.4", "3.11", "python"]
    ))
    
    # 场景2: 人物指代
    results.append(run_scenario(
        "场景2: 人物指代 (张伟)",
        "张伟是我同事，在阿里云做产品经理，我们经常一起讨论项目。",
        "张伟最近怎么样？",
        ["同事", "阿里云", "产品经理"]
    ))
    
    # 场景3: 模糊关联
    results.append(run_scenario(
        "场景3: 模糊关联 (火星探测项目)",
        "我们在做一个火星探测项目，预计明年完成，我是负责人。",
        "那个项目进度怎么样了？",
        ["火星", "探测", "明年"]
    ))
    
    # 场景4: 主动关联
    results.append(run_scenario(
        "场景4: 主动关联 (机器学习兴趣)",
        "我对机器学习和深度学习比较感兴趣，最近在研究 Transformer。",
        "最近有什么好的技术文章推荐吗？",
        ["机器学习", "深度学习", "transformer"]
    ))
    
    # 场景5: 避免踩坑
    results.append(run_scenario(
        "场景5: 避免踩坑 (不喜欢PHP)",
        "我不喜欢 PHP，更喜欢 Python，PHP 的语法太乱了。",
        "我想做个 Web 后端，用什么技术好？",
        ["python", "fastapi", "django"]
    ))
    
    # 汇总
    print("\n" + "="*60)
    print("测试汇总")
    print("="*60)
    for r in results:
        print(f"\n{r['name']}:")
        print(f"  OLD ECHO: {'✅ 命中' if r['old_hit'] else '❌ 未命中'}")
        print(f"  NEW ECHO: {'✅ 命中' if r['new_hit'] else '❌ 未命中'}")
    
    # 统计
    old_wins = sum(1 for r in results if r['old_hit'])
    new_wins = sum(1 for r in results if r['new_hit'])
    print(f"\n总计: OLD ECHO {old_wins}/{len(results)}, NEW ECHO {new_wins}/{len(results)}")