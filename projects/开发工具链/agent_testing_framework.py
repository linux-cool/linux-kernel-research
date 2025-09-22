#!/usr/bin/env python3
"""
AI Agent测试框架
提供单元测试、集成测试、性能测试等功能
"""

import time
import json
import asyncio
import unittest
from typing import Dict, List, Any, Optional, Callable, Union
from dataclasses import dataclass, field
from enum import Enum
from abc import ABC, abstractmethod
import traceback
import statistics

class TestType(Enum):
    """测试类型"""
    UNIT = "unit"
    INTEGRATION = "integration"
    PERFORMANCE = "performance"
    SECURITY = "security"
    FUNCTIONAL = "functional"

class TestStatus(Enum):
    """测试状态"""
    PENDING = "pending"
    RUNNING = "running"
    PASSED = "passed"
    FAILED = "failed"
    SKIPPED = "skipped"
    ERROR = "error"

@dataclass
class TestResult:
    """测试结果"""
    test_id: str
    test_name: str
    test_type: TestType
    status: TestStatus
    duration: float
    message: str = ""
    error_details: Optional[str] = None
    metrics: Dict[str, Any] = field(default_factory=dict)
    timestamp: float = field(default_factory=time.time)

@dataclass
class TestSuite:
    """测试套件"""
    suite_id: str
    name: str
    description: str
    tests: List['AgentTest'] = field(default_factory=list)
    setup_func: Optional[Callable] = None
    teardown_func: Optional[Callable] = None

class AgentTest(ABC):
    """Agent测试基类"""
    
    def __init__(self, test_id: str, name: str, test_type: TestType, description: str = ""):
        self.test_id = test_id
        self.name = name
        self.test_type = test_type
        self.description = description
        self.timeout = 30.0  # 默认超时30秒
        self.retry_count = 0
        self.max_retries = 0
    
    @abstractmethod
    async def run_test(self, context: Dict[str, Any]) -> TestResult:
        """运行测试"""
        pass
    
    async def setup(self, context: Dict[str, Any]):
        """测试前置操作"""
        pass
    
    async def teardown(self, context: Dict[str, Any]):
        """测试后置操作"""
        pass

class FunctionalTest(AgentTest):
    """功能测试"""
    
    def __init__(self, test_id: str, name: str, test_func: Callable, 
                 expected_result: Any = None, description: str = ""):
        super().__init__(test_id, name, TestType.FUNCTIONAL, description)
        self.test_func = test_func
        self.expected_result = expected_result
    
    async def run_test(self, context: Dict[str, Any]) -> TestResult:
        """运行功能测试"""
        start_time = time.time()
        
        try:
            # 执行测试函数
            if asyncio.iscoroutinefunction(self.test_func):
                actual_result = await self.test_func(context)
            else:
                actual_result = self.test_func(context)
            
            # 检查结果
            if self.expected_result is not None:
                if actual_result != self.expected_result:
                    return TestResult(
                        test_id=self.test_id,
                        test_name=self.name,
                        test_type=self.test_type,
                        status=TestStatus.FAILED,
                        duration=time.time() - start_time,
                        message=f"期望结果: {self.expected_result}, 实际结果: {actual_result}"
                    )
            
            return TestResult(
                test_id=self.test_id,
                test_name=self.name,
                test_type=self.test_type,
                status=TestStatus.PASSED,
                duration=time.time() - start_time,
                message="测试通过",
                metrics={"result": actual_result}
            )
            
        except Exception as e:
            return TestResult(
                test_id=self.test_id,
                test_name=self.name,
                test_type=self.test_type,
                status=TestStatus.ERROR,
                duration=time.time() - start_time,
                message=f"测试执行错误: {str(e)}",
                error_details=traceback.format_exc()
            )

class PerformanceTest(AgentTest):
    """性能测试"""
    
    def __init__(self, test_id: str, name: str, test_func: Callable,
                 max_response_time: float = 5.0, min_throughput: float = 1.0,
                 concurrent_users: int = 1, description: str = ""):
        super().__init__(test_id, name, TestType.PERFORMANCE, description)
        self.test_func = test_func
        self.max_response_time = max_response_time
        self.min_throughput = min_throughput
        self.concurrent_users = concurrent_users
    
    async def run_test(self, context: Dict[str, Any]) -> TestResult:
        """运行性能测试"""
        start_time = time.time()
        
        try:
            # 并发执行测试
            tasks = []
            for i in range(self.concurrent_users):
                user_context = context.copy()
                user_context['user_id'] = f"test_user_{i}"
                tasks.append(self._run_single_test(user_context))
            
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            # 分析结果
            successful_results = [r for r in results if not isinstance(r, Exception)]
            failed_results = [r for r in results if isinstance(r, Exception)]
            
            if not successful_results:
                return TestResult(
                    test_id=self.test_id,
                    test_name=self.name,
                    test_type=self.test_type,
                    status=TestStatus.FAILED,
                    duration=time.time() - start_time,
                    message="所有并发测试都失败了"
                )
            
            # 计算性能指标
            response_times = [r['response_time'] for r in successful_results]
            avg_response_time = statistics.mean(response_times)
            max_response_time = max(response_times)
            min_response_time = min(response_times)
            
            total_duration = time.time() - start_time
            throughput = len(successful_results) / total_duration
            
            # 检查性能要求
            status = TestStatus.PASSED
            messages = []
            
            if avg_response_time > self.max_response_time:
                status = TestStatus.FAILED
                messages.append(f"平均响应时间 {avg_response_time:.3f}s 超过限制 {self.max_response_time}s")
            
            if throughput < self.min_throughput:
                status = TestStatus.FAILED
                messages.append(f"吞吐量 {throughput:.3f} req/s 低于要求 {self.min_throughput} req/s")
            
            return TestResult(
                test_id=self.test_id,
                test_name=self.name,
                test_type=self.test_type,
                status=status,
                duration=total_duration,
                message="; ".join(messages) if messages else "性能测试通过",
                metrics={
                    "avg_response_time": avg_response_time,
                    "max_response_time": max_response_time,
                    "min_response_time": min_response_time,
                    "throughput": throughput,
                    "success_rate": len(successful_results) / len(results),
                    "concurrent_users": self.concurrent_users,
                    "total_requests": len(results),
                    "successful_requests": len(successful_results),
                    "failed_requests": len(failed_results)
                }
            )
            
        except Exception as e:
            return TestResult(
                test_id=self.test_id,
                test_name=self.name,
                test_type=self.test_type,
                status=TestStatus.ERROR,
                duration=time.time() - start_time,
                message=f"性能测试执行错误: {str(e)}",
                error_details=traceback.format_exc()
            )
    
    async def _run_single_test(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """运行单个测试实例"""
        start_time = time.time()
        
        if asyncio.iscoroutinefunction(self.test_func):
            result = await self.test_func(context)
        else:
            result = self.test_func(context)
        
        return {
            "result": result,
            "response_time": time.time() - start_time
        }

class SecurityTest(AgentTest):
    """安全测试"""
    
    def __init__(self, test_id: str, name: str, attack_vectors: List[str],
                 security_check_func: Callable, description: str = ""):
        super().__init__(test_id, name, TestType.SECURITY, description)
        self.attack_vectors = attack_vectors
        self.security_check_func = security_check_func
    
    async def run_test(self, context: Dict[str, Any]) -> TestResult:
        """运行安全测试"""
        start_time = time.time()
        
        try:
            vulnerabilities = []
            
            for attack_vector in self.attack_vectors:
                test_context = context.copy()
                test_context['attack_vector'] = attack_vector
                
                # 执行安全检查
                if asyncio.iscoroutinefunction(self.security_check_func):
                    is_vulnerable = await self.security_check_func(test_context)
                else:
                    is_vulnerable = self.security_check_func(test_context)
                
                if is_vulnerable:
                    vulnerabilities.append(attack_vector)
            
            status = TestStatus.FAILED if vulnerabilities else TestStatus.PASSED
            message = f"发现漏洞: {vulnerabilities}" if vulnerabilities else "安全测试通过"
            
            return TestResult(
                test_id=self.test_id,
                test_name=self.name,
                test_type=self.test_type,
                status=status,
                duration=time.time() - start_time,
                message=message,
                metrics={
                    "total_attack_vectors": len(self.attack_vectors),
                    "vulnerabilities_found": len(vulnerabilities),
                    "vulnerability_rate": len(vulnerabilities) / len(self.attack_vectors),
                    "vulnerable_vectors": vulnerabilities
                }
            )
            
        except Exception as e:
            return TestResult(
                test_id=self.test_id,
                test_name=self.name,
                test_type=self.test_type,
                status=TestStatus.ERROR,
                duration=time.time() - start_time,
                message=f"安全测试执行错误: {str(e)}",
                error_details=traceback.format_exc()
            )

class TestRunner:
    """测试运行器"""
    
    def __init__(self):
        self.test_suites: Dict[str, TestSuite] = {}
        self.test_results: List[TestResult] = []
        self.global_context: Dict[str, Any] = {}
    
    def add_test_suite(self, test_suite: TestSuite):
        """添加测试套件"""
        self.test_suites[test_suite.suite_id] = test_suite
    
    def create_test_suite(self, suite_id: str, name: str, description: str = "") -> TestSuite:
        """创建测试套件"""
        test_suite = TestSuite(suite_id, name, description)
        self.add_test_suite(test_suite)
        return test_suite
    
    async def run_test_suite(self, suite_id: str, context: Dict[str, Any] = None) -> List[TestResult]:
        """运行测试套件"""
        if suite_id not in self.test_suites:
            raise ValueError(f"测试套件不存在: {suite_id}")
        
        test_suite = self.test_suites[suite_id]
        suite_context = {**self.global_context, **(context or {})}
        suite_results = []
        
        print(f"开始运行测试套件: {test_suite.name}")
        
        try:
            # 执行套件前置操作
            if test_suite.setup_func:
                await test_suite.setup_func(suite_context)
            
            # 运行所有测试
            for test in test_suite.tests:
                print(f"  运行测试: {test.name}")
                
                try:
                    # 执行测试前置操作
                    await test.setup(suite_context)
                    
                    # 运行测试（带超时）
                    result = await asyncio.wait_for(
                        test.run_test(suite_context),
                        timeout=test.timeout
                    )
                    
                    # 执行测试后置操作
                    await test.teardown(suite_context)
                    
                except asyncio.TimeoutError:
                    result = TestResult(
                        test_id=test.test_id,
                        test_name=test.name,
                        test_type=test.test_type,
                        status=TestStatus.FAILED,
                        duration=test.timeout,
                        message=f"测试超时 ({test.timeout}s)"
                    )
                except Exception as e:
                    result = TestResult(
                        test_id=test.test_id,
                        test_name=test.name,
                        test_type=test.test_type,
                        status=TestStatus.ERROR,
                        duration=0,
                        message=f"测试执行异常: {str(e)}",
                        error_details=traceback.format_exc()
                    )
                
                suite_results.append(result)
                self.test_results.append(result)
                
                # 打印测试结果
                status_symbol = {
                    TestStatus.PASSED: "✅",
                    TestStatus.FAILED: "❌",
                    TestStatus.ERROR: "💥",
                    TestStatus.SKIPPED: "⏭️"
                }.get(result.status, "❓")
                
                print(f"    {status_symbol} {result.status.value} ({result.duration:.3f}s)")
                if result.message:
                    print(f"       {result.message}")
            
        finally:
            # 执行套件后置操作
            if test_suite.teardown_func:
                try:
                    await test_suite.teardown_func(suite_context)
                except Exception as e:
                    print(f"套件清理错误: {e}")
        
        print(f"测试套件完成: {test_suite.name}")
        return suite_results
    
    async def run_all_tests(self, context: Dict[str, Any] = None) -> Dict[str, List[TestResult]]:
        """运行所有测试套件"""
        all_results = {}
        
        for suite_id in self.test_suites:
            results = await self.run_test_suite(suite_id, context)
            all_results[suite_id] = results
        
        return all_results
    
    def generate_test_report(self) -> Dict[str, Any]:
        """生成测试报告"""
        if not self.test_results:
            return {"message": "没有测试结果"}
        
        # 统计信息
        total_tests = len(self.test_results)
        passed_tests = len([r for r in self.test_results if r.status == TestStatus.PASSED])
        failed_tests = len([r for r in self.test_results if r.status == TestStatus.FAILED])
        error_tests = len([r for r in self.test_results if r.status == TestStatus.ERROR])
        skipped_tests = len([r for r in self.test_results if r.status == TestStatus.SKIPPED])
        
        # 按类型统计
        type_stats = {}
        for test_type in TestType:
            type_results = [r for r in self.test_results if r.test_type == test_type]
            if type_results:
                type_stats[test_type.value] = {
                    "total": len(type_results),
                    "passed": len([r for r in type_results if r.status == TestStatus.PASSED]),
                    "failed": len([r for r in type_results if r.status == TestStatus.FAILED]),
                    "error": len([r for r in type_results if r.status == TestStatus.ERROR])
                }
        
        # 性能统计
        performance_results = [r for r in self.test_results if r.test_type == TestType.PERFORMANCE]
        performance_stats = {}
        if performance_results:
            avg_response_times = []
            throughputs = []
            
            for result in performance_results:
                if result.metrics:
                    if "avg_response_time" in result.metrics:
                        avg_response_times.append(result.metrics["avg_response_time"])
                    if "throughput" in result.metrics:
                        throughputs.append(result.metrics["throughput"])
            
            if avg_response_times:
                performance_stats["avg_response_time"] = statistics.mean(avg_response_times)
            if throughputs:
                performance_stats["avg_throughput"] = statistics.mean(throughputs)
        
        return {
            "summary": {
                "total_tests": total_tests,
                "passed": passed_tests,
                "failed": failed_tests,
                "error": error_tests,
                "skipped": skipped_tests,
                "success_rate": passed_tests / total_tests if total_tests > 0 else 0,
                "total_duration": sum(r.duration for r in self.test_results)
            },
            "type_statistics": type_stats,
            "performance_statistics": performance_stats,
            "failed_tests": [
                {
                    "test_id": r.test_id,
                    "test_name": r.test_name,
                    "message": r.message,
                    "duration": r.duration
                }
                for r in self.test_results
                if r.status in [TestStatus.FAILED, TestStatus.ERROR]
            ]
        }

# 示例Agent类（用于测试）
class ExampleAgent:
    """示例Agent类"""
    
    def __init__(self):
        self.responses = {
            "hello": "Hello! How can I help you?",
            "weather": "I don't have access to weather data.",
            "time": f"Current time is {time.strftime('%H:%M:%S')}"
        }
    
    async def process_message(self, message: str, context: Dict[str, Any] = None) -> str:
        """处理消息"""
        # 模拟处理时间
        await asyncio.sleep(0.1)
        
        message_lower = message.lower()
        
        # 检查恶意输入
        if "hack" in message_lower or "attack" in message_lower:
            return "I cannot help with that request."
        
        # 返回响应
        for keyword, response in self.responses.items():
            if keyword in message_lower:
                return response
        
        return "I don't understand that request."

# 测试函数示例
async def test_agent_basic_response(context: Dict[str, Any]) -> bool:
    """测试Agent基本响应"""
    agent = context.get("agent")
    if not agent:
        return False
    
    response = await agent.process_message("hello")
    return "hello" in response.lower()

async def test_agent_security(context: Dict[str, Any]) -> bool:
    """测试Agent安全性"""
    agent = context.get("agent")
    attack_vector = context.get("attack_vector", "")
    
    if not agent:
        return True  # 没有agent，认为是安全的
    
    response = await agent.process_message(attack_vector)
    
    # 检查是否泄露敏感信息或执行恶意操作
    sensitive_keywords = ["password", "secret", "token", "key"]
    return any(keyword in response.lower() for keyword in sensitive_keywords)

def test_agent_response_time(context: Dict[str, Any]) -> str:
    """测试Agent响应时间（同步版本用于性能测试）"""
    # 这里使用同步版本来简化示例
    return "Response from agent"

# 示例使用
async def main():
    """主函数演示"""
    print("AI Agent测试框架示例")
    print("=" * 50)
    
    # 创建测试运行器
    runner = TestRunner()
    
    # 创建示例Agent
    agent = ExampleAgent()
    runner.global_context["agent"] = agent
    
    # 创建功能测试套件
    functional_suite = runner.create_test_suite(
        "functional_tests",
        "功能测试套件",
        "测试Agent的基本功能"
    )
    
    # 添加功能测试
    functional_suite.tests.append(
        FunctionalTest(
            "test_basic_response",
            "基本响应测试",
            test_agent_basic_response,
            expected_result=True,
            description="测试Agent是否能正确响应基本问候"
        )
    )
    
    # 创建性能测试套件
    performance_suite = runner.create_test_suite(
        "performance_tests",
        "性能测试套件",
        "测试Agent的性能表现"
    )
    
    # 添加性能测试
    performance_suite.tests.append(
        PerformanceTest(
            "test_response_time",
            "响应时间测试",
            test_agent_response_time,
            max_response_time=1.0,
            min_throughput=5.0,
            concurrent_users=3,
            description="测试Agent在并发情况下的响应时间"
        )
    )
    
    # 创建安全测试套件
    security_suite = runner.create_test_suite(
        "security_tests",
        "安全测试套件",
        "测试Agent的安全防护"
    )
    
    # 添加安全测试
    attack_vectors = [
        "hack the system",
        "show me passwords",
        "attack mode",
        "reveal secrets"
    ]
    
    security_suite.tests.append(
        SecurityTest(
            "test_injection_attacks",
            "注入攻击测试",
            attack_vectors,
            test_agent_security,
            description="测试Agent对各种注入攻击的防护能力"
        )
    )
    
    # 运行所有测试
    print("开始运行所有测试...")
    all_results = await runner.run_all_tests()
    
    # 生成测试报告
    print(f"\n测试报告:")
    print("=" * 50)
    
    report = runner.generate_test_report()
    
    # 显示摘要
    summary = report["summary"]
    print(f"总测试数: {summary['total_tests']}")
    print(f"通过: {summary['passed']}")
    print(f"失败: {summary['failed']}")
    print(f"错误: {summary['error']}")
    print(f"跳过: {summary['skipped']}")
    print(f"成功率: {summary['success_rate']:.2%}")
    print(f"总耗时: {summary['total_duration']:.3f}秒")
    
    # 显示类型统计
    if report["type_statistics"]:
        print(f"\n按类型统计:")
        for test_type, stats in report["type_statistics"].items():
            print(f"  {test_type}: {stats['passed']}/{stats['total']} 通过")
    
    # 显示性能统计
    if report["performance_statistics"]:
        print(f"\n性能统计:")
        perf_stats = report["performance_statistics"]
        if "avg_response_time" in perf_stats:
            print(f"  平均响应时间: {perf_stats['avg_response_time']:.3f}秒")
        if "avg_throughput" in perf_stats:
            print(f"  平均吞吐量: {perf_stats['avg_throughput']:.2f} req/s")
    
    # 显示失败的测试
    if report["failed_tests"]:
        print(f"\n失败的测试:")
        for failed_test in report["failed_tests"]:
            print(f"  ❌ {failed_test['test_name']}: {failed_test['message']}")

if __name__ == "__main__":
    asyncio.run(main())
