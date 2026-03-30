#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
记忆系统完整测试套件

包含：
- V3.5 所有测试
- V4.0 所有测试
- 端到端测试
"""
import subprocess
import sys
import time
from pathlib import Path

# 测试文件列表（按依赖顺序）
TEST_FILES = [
    # V3.5 测试
    ("V3.5 基础测试", "test_v35.py"),
    ("V3.5 集成测试", "test_integration.py"),
    ("V3.5 A/B测试", "test_v35_ab_test.py"),
    ("V3.5 大型场景测试", "test_v35_large_scenario.py"),
    ("V3.5 Prompt构建测试", "test_v35_prompt_building.py"),
    ("V3.5 端到端A/B测试", "test_v35_e2e_ab.py"),
    
    # V4.0 测试
    ("V4.0 LLM提取测试", "test_v40_llm_extraction.py"),
    ("V4.0 A/B测试", "test_v40_ab.py"),
]


def run_test(name: str, file: str) -> tuple:
    """运行单个测试文件"""
    print(f"\n{'=' * 70}")
    print(f"🧪 {name}")
    print(f"{'=' * 70}")
    
    start_time = time.time()
    
    result = subprocess.run(
        [sys.executable, file],
        cwd=Path(__file__).parent,
        capture_output=True,
        text=True,
        timeout=120,
    )
    
    elapsed = time.time() - start_time
    
    # 打印输出
    if result.stdout:
        print(result.stdout)
    
    if result.returncode != 0:
        print(f"\n❌ 测试失败")
        if result.stderr:
            print(f"错误: {result.stderr}")
        return False, elapsed
    else:
        print(f"\n✅ 测试通过 ({elapsed:.1f}s)")
        return True, elapsed


def main():
    """运行所有测试"""
    print("=" * 70)
    print("🚀 记忆系统完整测试套件")
    print("=" * 70)
    print(f"\n测试文件数: {len(TEST_FILES)}")
    
    results = []
    total_start = time.time()
    
    for name, file in TEST_FILES:
        file_path = Path(__file__).parent / file
        if not file_path.exists():
            print(f"\n⚠️ 跳过 {name}: 文件不存在")
            results.append((name, False, 0, "文件不存在"))
            continue
        
        success, elapsed = run_test(name, str(file_path))
        results.append((name, success, elapsed, ""))
    
    total_elapsed = time.time() - total_start
    
    # 打印总结
    print("\n" + "=" * 70)
    print("📊 测试结果总结")
    print("=" * 70)
    
    passed = sum(1 for _, s, _, _ in results if s)
    failed = len(results) - passed
    
    print(f"\n  总计: {len(results)} 个测试")
    print(f"  通过: {passed}")
    print(f"  失败: {failed}")
    print(f"  总耗时: {total_elapsed:.1f}s")
    
    print("\n  详细结果:")
    print("  " + "-" * 60)
    for name, success, elapsed, error in results:
        status = "✅" if success else "❌"
        print(f"  {status} {name:<30} ({elapsed:.1f}s)")
        if error:
            print(f"      错误: {error}")
    
    # 按版本统计
    print("\n  按版本统计:")
    v35_tests = [r for r in results if "V3.5" in r[0]]
    v40_tests = [r for r in results if "V4.0" in r[0]]
    
    v35_passed = sum(1 for _, s, _, _ in v35_tests if s)
    v40_passed = sum(1 for _, s, _, _ in v40_tests if s)
    
    print(f"    V3.5: {v35_passed}/{len(v35_tests)} 通过")
    print(f"    V4.0: {v40_passed}/{len(v40_tests)} 通过")
    
    if failed == 0:
        print("\n  🎉 所有测试通过！")
    else:
        print(f"\n  ⚠️ {failed} 个测试失败")
    
    return failed == 0


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)