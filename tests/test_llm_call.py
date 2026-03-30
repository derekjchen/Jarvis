#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
测试 LLM 调用方式

验证 chat_model 的正确调用方法
"""
import asyncio
import sys
import os

# 添加 src 路径
sys.path.insert(0, "/root/copaw/src")
os.chdir("/root/copaw")

from agentscope.message import Msg


async def test_llm_call():
    """测试 LLM 调用的正确方式"""
    
    # 导入模型工厂
    from copaw.agents.model_factory import create_model_and_formatter
    
    print("=" * 60)
    print("创建模型...")
    print("=" * 60)
    
    model, formatter = create_model_and_formatter()
    print(f"模型类型: {type(model).__name__}")
    print(f"Formatter类型: {type(formatter).__name__}")
    
    # 测试消息
    test_prompt = "请从这句话中提取实体，返回JSON格式：我叫张三，今年25岁"
    msg = Msg(name="user", role="user", content=test_prompt)
    
    print("\n" + "=" * 60)
    print("测试 1: 没有 await 的调用方式 (错误)")
    print("=" * 60)
    
    try:
        response = model(msg)  # 没有 await
        print(f"返回类型: {type(response).__name__}")
        print(f"返回值: {response}")
        if hasattr(response, '__await__'):
            print("⚠️  这是一个 coroutine 对象! 需要 await!")
        print(f"str(response): {str(response)[:100]}")
    except Exception as e:
        print(f"错误: {type(e).__name__}: {e}")
    
    print("\n" + "=" * 60)
    print("测试 2: 使用 await 的调用方式 (正确)")
    print("=" * 60)
    
    try:
        response = await model(msg)  # 正确使用 await
        print(f"返回类型: {type(response).__name__}")
        if hasattr(response, 'content'):
            print(f"content 前200字符: {response.content[:200]}")
        if hasattr(response, 'text'):
            print(f"text 前200字符: {response.text[:200]}")
        print("✅ 调用成功!")
    except Exception as e:
        print(f"错误: {type(e).__name__}: {e}")
    
    print("\n" + "=" * 60)
    print("测试 3: 测试 EntityExtractor")
    print("=" * 60)
    
    try:
        from copaw.memory_v2.entity_extractor import EntityExtractor
        
        extractor = EntityExtractor(model)
        print(f"EntityExtractor 创建成功")
        print(f"_call_llm 方法: {extractor._call_llm}")
        print(f"是否是协程函数: {asyncio.iscoroutinefunction(extractor._call_llm)}")
        
        # 测试提取
        print("\n开始提取实体...")
        entities = await extractor.extract("我叫李四，今年30岁，在北京工作")
        print(f"提取结果: {len(entities)} 个实体")
        for e in entities:
            print(f"  - {e.type}: {e.name}")
            
    except Exception as e:
        import traceback
        print(f"错误: {type(e).__name__}: {e}")
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(test_llm_call())