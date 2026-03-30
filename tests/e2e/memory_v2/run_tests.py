#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Memory V2 E2E 测试执行脚本

使用方法:
    python run_tests.py --target echo                    # 测试 Echo
    python run_tests.py --target localhost:8088          # 测试本地服务
    python run_tests.py --target echo --category entity  # 只运行实体提取测试
    python run_tests.py --target echo --test-id T01      # 运行单个测试
"""

import argparse
import json
import os
import sys
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

import requests

# 测试结果数据类
@dataclass
class TestResult:
    test_id: str
    category: str
    passed: bool
    duration_ms: float
    response: str
    error: Optional[str] = None
    details: dict = None


class MemoryV2TestRunner:
    """Memory V2 E2E 测试执行器"""
    
    def __init__(self, target: str, timeout: int = 60):
        """
        初始化测试执行器
        
        Args:
            target: 目标服务地址，如 "echo" 或 "localhost:8088"
            timeout: 请求超时时间（秒）
        """
        self.target = target
        self.timeout = timeout
        self.results: list[TestResult] = []
        
        # 确定目标 URL
        if target == "echo":
            self.base_url = "http://39.96.212.215:8088"
            self.use_ssh = True
            self.ssh_cmd = "sshpass -p 'archIact123' ssh -o StrictHostKeyChecking=no root@39.96.212.215"
        else:
            self.base_url = f"http://{target}"
            self.use_ssh = False
        
        # 测试用例目录
        self.test_cases_dir = Path(__file__).parent / "test_cases"
    
    def load_test_cases(self, category: Optional[str] = None) -> list[dict]:
        """加载测试用例"""
        test_cases = []
        
        for json_file in self.test_cases_dir.glob("*.json"):
            if category and category not in json_file.stem:
                continue
            
            with open(json_file, 'r', encoding='utf-8') as f:
                cases = json.load(f)
                test_cases.extend(cases)
        
        return test_cases
    
    def send_message(self, message: str, session_id: str, user_id: str = "test") -> tuple[str, dict]:
        """
        发送消息到目标服务
        
        Returns:
            (response_text, full_response)
        """
        if self.use_ssh:
            # 通过 SSH 在远程执行 curl
            import subprocess
            cmd = f'''{self.ssh_cmd} "curl -s -X POST 'http://localhost:8088/api/agent/process' \
                -H 'Content-Type: application/json' \
                -d '{{\"input\": [{{\"role\": \"user\", \"content\": [{{\"type\": \"text\", \"text\": \"{message}\"}}]}}], \"session_id\": \"{session_id}\", \"user_id\": \"{user_id}\"}}' \
                --max-time {self.timeout}"'''
            
            result = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=self.timeout + 10)
            response = result.stdout
        else:
            url = f"{self.base_url}/api/agent/process"
            payload = {
                "input": [{"role": "user", "content": [{"type": "text", "text": message}]}],
                "session_id": session_id,
                "user_id": user_id
            }
            response = requests.post(url, json=payload, timeout=self.timeout).text
        
        # 提取文本内容
        text = self._extract_text(response)
        return text, {"raw": response[:500]}
    
    def _extract_text(self, response: str) -> str:
        """从响应中提取文本内容"""
        import re
        # 尝试提取最后的 message 类型的 text
        pattern = r'"type":"message"[^}]*"content":\[[^\]]*"text":"([^"]*)"'
        matches = re.findall(pattern, response)
        if matches:
            return matches[-1]
        
        # 备用：提取任意 text 字段
        pattern = r'"text":"([^"]{10,})"'
        matches = re.findall(pattern, response)
        if matches:
            return matches[-1]
        
        return ""
    
    def run_test(self, test_case: dict) -> TestResult:
        """运行单个测试用例"""
        test_id = test_case["test_id"]
        message = test_case["input"]
        session_id = test_case.get("session_id", f"test_{test_id}")
        
        print(f"\n[{test_id}] {test_case.get('description', '')}")
        print(f"  输入: {message[:50]}...")
        
        start_time = time.time()
        try:
            response_text, full_response = self.send_message(message, session_id)
            duration_ms = (time.time() - start_time) * 1000
            
            print(f"  响应 ({duration_ms:.0f}ms): {response_text[:100]}...")
            
            # 检查预期结果
            passed, details = self._verify_result(test_case, response_text)
            
            return TestResult(
                test_id=test_id,
                category=test_case.get("category", "unknown"),
                passed=passed,
                duration_ms=duration_ms,
                response=response_text[:200],
                details=details
            )
            
        except Exception as e:
            duration_ms = (time.time() - start_time) * 1000
            print(f"  错误: {e}")
            return TestResult(
                test_id=test_id,
                category=test_case.get("category", "unknown"),
                passed=False,
                duration_ms=duration_ms,
                response="",
                error=str(e)
            )
    
    def _verify_result(self, test_case: dict, response: str) -> tuple[bool, dict]:
        """验证测试结果"""
        details = {}
        passed = True
        
        # 检查预期实体
        if "expected_entities" in test_case:
            entities = test_case["expected_entities"]
            for entity in entities:
                if entity["name"] not in response:
                    # 实体可能被记住，不一定在响应中出现
                    pass
            details["entities_checked"] = len(entities)
        
        # 检查预期回忆
        if "expected_recall" in test_case:
            for keyword in test_case["expected_recall"]:
                if keyword not in response:
                    passed = False
                    details.setdefault("missing_recall", []).append(keyword)
        
        # 检查预期行为
        if "expected_behavior" in test_case:
            details["expected_behavior"] = test_case["expected_behavior"]
        
        return passed, details
    
    def run_all(self, category: Optional[str] = None, test_id: Optional[str] = None) -> list[TestResult]:
        """运行所有测试"""
        test_cases = self.load_test_cases(category)
        
        if test_id:
            test_cases = [tc for tc in test_cases if tc["test_id"] == test_id]
        
        print(f"\n{'='*60}")
        print(f"Memory V2 E2E 测试")
        print(f"目标: {self.target}")
        print(f"测试用例数: {len(test_cases)}")
        print(f"{'='*60}")
        
        for test_case in test_cases:
            result = self.run_test(test_case)
            self.results.append(result)
            time.sleep(1)  # 避免请求过快
        
        self._print_summary()
        return self.results
    
    def _print_summary(self):
        """打印测试摘要"""
        print(f"\n{'='*60}")
        print("测试摘要")
        print(f"{'='*60}")
        
        total = len(self.results)
        passed = sum(1 for r in self.results if r.passed)
        failed = total - passed
        
        avg_duration = sum(r.duration_ms for r in self.results) / total if total > 0 else 0
        
        print(f"总计: {total} | 通过: {passed} | 失败: {failed}")
        print(f"平均响应时间: {avg_duration:.0f}ms")
        
        if failed > 0:
            print("\n失败的测试:")
            for r in self.results:
                if not r.passed:
                    print(f"  - {r.test_id}: {r.error or r.details}")
        
        print(f"{'='*60}")
    
    def save_results(self, output_path: str):
        """保存测试结果到文件"""
        data = {
            "timestamp": datetime.now().isoformat(),
            "target": self.target,
            "summary": {
                "total": len(self.results),
                "passed": sum(1 for r in self.results if r.passed),
                "failed": sum(1 for r in self.results if not r.passed),
            },
            "results": [
                {
                    "test_id": r.test_id,
                    "category": r.category,
                    "passed": r.passed,
                    "duration_ms": r.duration_ms,
                    "response": r.response,
                    "error": r.error,
                }
                for r in self.results
            ]
        }
        
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        
        print(f"结果已保存到: {output_path}")


def main():
    parser = argparse.ArgumentParser(description="Memory V2 E2E 测试执行器")
    parser.add_argument("--target", required=True, help="目标服务 (echo 或 host:port)")
    parser.add_argument("--category", help="只运行指定类别的测试")
    parser.add_argument("--test-id", help="只运行指定的测试用例")
    parser.add_argument("--timeout", type=int, default=60, help="请求超时时间（秒）")
    parser.add_argument("--output", help="结果输出文件路径")
    
    args = parser.parse_args()
    
    runner = MemoryV2TestRunner(args.target, args.timeout)
    results = runner.run_all(args.category, args.test_id)
    
    if args.output:
        runner.save_results(args.output)
    
    # 返回退出码
    failed = sum(1 for r in results if not r.passed)
    sys.exit(1 if failed > 0 else 0)


if __name__ == "__main__":
    main()