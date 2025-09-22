#!/usr/bin/env python3
"""
快速开始示例项目（纯标准库可运行）
- 任务规划与执行（模拟Web搜索、数据分析、文件写入）
- 简单输入安全校验
- CLI 演示
"""

import argparse
import asyncio
import json
import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional

# =========================
# 基础类型定义
# =========================

class TaskStatus(Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"

class TaskPriority(Enum):
    LOW = 1
    MEDIUM = 2
    HIGH = 3

@dataclass
class Task:
    id: str
    name: str
    description: str
    task_type: str
    priority: TaskPriority
    parameters: Dict[str, Any] = field(default_factory=dict)
    dependencies: List[str] = field(default_factory=list)
    status: TaskStatus = TaskStatus.PENDING
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    started_at: Optional[float] = None
    completed_at: Optional[float] = None

# =========================
# 工具实现（模拟）
# =========================

class Tool:
    name: str
    description: str

    async def execute(self, params: Dict[str, Any]) -> Dict[str, Any]:
        raise NotImplementedError

class WebSearchTool(Tool):
    name = "web_search"
    description = "搜索网络信息（模拟）"

    async def execute(self, params: Dict[str, Any]) -> Dict[str, Any]:
        query = params.get("query", "")
        max_results = int(params.get("max_results", 3))
        await asyncio.sleep(0.3)
        results = [
            {
                "title": f"{query} - 结果{i+1}",
                "url": f"https://example.com/{uuid.uuid4().hex[:8]}",
                "snippet": f"与 {query} 相关的摘要..."
            }
            for i in range(max_results)
        ]
        return {"query": query, "results": results, "total": len(results)}

class DataAnalysisTool(Tool):
    name = "data_analysis"
    description = "分析数据并提炼要点（模拟）"

    async def execute(self, params: Dict[str, Any]) -> Dict[str, Any]:
        await asyncio.sleep(0.2)
        analysis_type = params.get("type", "basic")
        return {
            "analysis_type": analysis_type,
            "insights": ["要点1：大模型Agent快速发展", "要点2：企业应用落地加速", "要点3：多Agent协作兴起"],
            "metrics": {"confidence": 0.88}
        }

class FileOperationTool(Tool):
    name = "file_operation"
    description = "文件读写（模拟写入）"

    async def execute(self, params: Dict[str, Any]) -> Dict[str, Any]:
        op = params.get("operation", "write")
        path = params.get("file_path", "output.txt")
        content = params.get("content", "")
        await asyncio.sleep(0.05)
        if op == "write":
            try:
                with open(path, "w", encoding="utf-8") as f:
                    f.write(content or "示例报告：由快速开始示例生成\n")
                return {"operation": op, "file_path": path, "bytes": len(content)}
            except Exception as e:
                return {"operation": op, "error": str(e)}
        return {"operation": op, "error": f"不支持的操作: {op}"}

# 工具注册表
TOOLS: Dict[str, Tool] = {
    "web_search": WebSearchTool(),
    "data_analysis": DataAnalysisTool(),
    "file_operation": FileOperationTool(),
}

# =========================
# 简单安全校验
# =========================

def secure_validate(user_input: str) -> Dict[str, Any]:
    dangerous_patterns = [
        "ignore previous instructions",
        "drop table",
        "<script",
        "javascript:",
        "; rm -rf",
    ]
    lower = user_input.lower()
    threats = [p for p in dangerous_patterns if p in lower]
    is_safe = len(threats) == 0
    return {
        "is_safe": is_safe,
        "threats": threats,
        "sanitized": user_input if is_safe else user_input.replace("<", "").replace(">", "")[:200] + ("..." if len(user_input) > 200 else ""),
    }

# =========================
# 规划与执行
# =========================

class Planner:
    def __init__(self):
        self.tasks: Dict[str, Task] = {}

    def add_task(self, task: Task):
        self.tasks[task.id] = task

    def by_name(self, name: str) -> Optional[Task]:
        for t in self.tasks.values():
            if t.name == name:
                return t
        return None

    def ready_tasks(self) -> List[Task]:
        ready: List[Task] = []
        for t in self.tasks.values():
            if t.status != TaskStatus.PENDING:
                continue
            if all(
                (self.by_name(dep) and self.by_name(dep).status == TaskStatus.COMPLETED)
                for dep in t.dependencies
            ):
                ready.append(t)
        ready.sort(key=lambda x: x.priority.value, reverse=True)
        return ready

class Executor:
    def __init__(self):
        self.stats = {"completed": 0, "failed": 0, "start_time": None, "end_time": None}

    async def run_task(self, task: Task) -> Task:
        task.started_at = time.time()
        task.status = TaskStatus.RUNNING
        tool = TOOLS.get(task.task_type)
        try:
            if not tool:
                raise ValueError(f"未找到工具: {task.task_type}")
            result = await tool.execute(task.parameters)
            task.result = result
            task.status = TaskStatus.COMPLETED
        except Exception as e:
            task.error = str(e)
            task.status = TaskStatus.FAILED
        task.completed_at = time.time()
        return task

    async def run_plan(self, planner: Planner) -> Dict[str, Any]:
        self.stats["start_time"] = time.time()
        executed: List[Task] = []
        while True:
            ready = planner.ready_tasks()
            if not ready:
                break
            # 并发执行同一批次
            done: List[Task] = await asyncio.gather(*(self.run_task(t) for t in ready))
            executed.extend(done)
        # 统计
        for t in planner.tasks.values():
            if t.status == TaskStatus.COMPLETED:
                self.stats["completed"] += 1
            elif t.status == TaskStatus.FAILED:
                self.stats["failed"] += 1
        self.stats["end_time"] = time.time()
        return {
            "summary": self.summary(),
            "results": [
                {
                    "name": t.name,
                    "status": t.status.value,
                    "duration": round((t.completed_at - t.started_at) if t.started_at and t.completed_at else 0, 3),
                    "result_keys": list((t.result or {}).keys()),
                    "error": t.error,
                }
                for t in planner.tasks.values()
            ],
        }

    def summary(self) -> Dict[str, Any]:
        total = sum(1 for _ in TOOLS)
        return {
            "completed": self.stats["completed"],
            "failed": self.stats["failed"],
            "total_defined_tools": total,
            "elapsed": round((self.stats["end_time"] - self.stats["start_time"]) if self.stats["start_time"] and self.stats["end_time"] else 0, 3),
        }

# =========================
# CLI 入口
# =========================

def load_config(path: str) -> Dict[str, Any]:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)

def build_plan_from_config(cfg: Dict[str, Any]) -> Planner:
    planner = Planner()
    for item in cfg.get("tasks", []):
        t = Task(
            id=uuid.uuid4().hex,
            name=item["name"],
            description=item.get("description", ""),
            task_type=item.get("task_type", "web_search"),
            priority=TaskPriority[item.get("priority", "MEDIUM")],
            parameters=item.get("parameters", {}),
            dependencies=item.get("dependencies", []),
        )
        planner.add_task(t)
    return planner

async def run_demo():
    print("[Demo] 构建任务计划...")
    planner = Planner()
    planner.add_task(Task(
        id=uuid.uuid4().hex,
        name="AI市场研究",
        description="搜索AI Agent趋势",
        task_type="web_search",
        priority=TaskPriority.HIGH,
        parameters={"query": "AI Agent 趋势 2025", "max_results": 2},
    ))
    planner.add_task(Task(
        id=uuid.uuid4().hex,
        name="数据分析",
        description="分析搜索结果",
        task_type="data_analysis",
        priority=TaskPriority.MEDIUM,
        dependencies=["AI市场研究"],
        parameters={"type": "basic"},
    ))
    planner.add_task(Task(
        id=uuid.uuid4().hex,
        name="生成报告",
        description="输出研究报告",
        task_type="file_operation",
        priority=TaskPriority.MEDIUM,
        dependencies=["数据分析"],
        parameters={"operation": "write", "file_path": "quickstart_report.md", "content": "# 报告\n初稿..."},
    ))
    executor = Executor()
    result = await executor.run_plan(planner)
    print("[Demo] 执行完成：", json.dumps(result["summary"], ensure_ascii=False))
    for r in result["results"]:
        print(" -", json.dumps(r, ensure_ascii=False))

async def run_from_config(config_path: str):
    cfg = load_config(config_path)
    planner = build_plan_from_config(cfg)
    executor = Executor()
    result = await executor.run_plan(planner)
    print(json.dumps(result, ensure_ascii=False, indent=2))

async def run_secure_check(text: str):
    res = secure_validate(text)
    print(json.dumps(res, ensure_ascii=False, indent=2))

def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="快速开始示例：任务规划/执行 + 简单安全校验")
    p.add_argument("--demo", action="store_true", help="运行内置演示")
    p.add_argument("--config", type=str, help="从JSON配置构建并执行计划")
    p.add_argument("--secure", type=str, help="对输入文本做安全校验")
    return p.parse_args()

if __name__ == "__main__":
    args = parse_args()
    if args.demo:
        asyncio.run(run_demo())
    elif args.config:
        asyncio.run(run_from_config(args.config))
    elif args.secure:
        asyncio.run(run_secure_check(args.secure))
    else:
        print("请使用 --demo 或 --config 或 --secure 运行（参考 README.md）")

