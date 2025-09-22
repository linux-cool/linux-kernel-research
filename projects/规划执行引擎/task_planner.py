#!/usr/bin/env python3
"""
AI Agent任务规划与执行引擎
实现分层任务规划、动态执行和工具调用
"""

import time
import json
import uuid
from typing import Dict, List, Any, Optional, Callable
from dataclasses import dataclass, asdict
from enum import Enum
from abc import ABC, abstractmethod
import asyncio

class TaskStatus(Enum):
    """任务状态"""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"

class TaskPriority(Enum):
    """任务优先级"""
    LOW = 1
    MEDIUM = 2
    HIGH = 3
    URGENT = 4

@dataclass
class Task:
    """任务定义"""
    id: str
    name: str
    description: str
    task_type: str
    priority: TaskPriority
    dependencies: List[str]
    parameters: Dict[str, Any]
    estimated_duration: float
    max_retries: int = 3
    status: TaskStatus = TaskStatus.PENDING
    created_at: float = 0.0
    started_at: Optional[float] = None
    completed_at: Optional[float] = None
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    retry_count: int = 0
    
    def __post_init__(self):
        if self.created_at == 0.0:
            self.created_at = time.time()

class Tool(ABC):
    """工具基类"""
    
    def __init__(self, name: str, description: str):
        self.name = name
        self.description = description
    
    @abstractmethod
    async def execute(self, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """执行工具"""
        pass
    
    def validate_parameters(self, parameters: Dict[str, Any]) -> bool:
        """验证参数"""
        return True

class WebSearchTool(Tool):
    """网络搜索工具"""
    
    def __init__(self):
        super().__init__("web_search", "搜索网络信息")
    
    async def execute(self, parameters: Dict[str, Any]) -> Dict[str, Any]:
        query = parameters.get("query", "")
        max_results = parameters.get("max_results", 5)
        
        # 模拟网络搜索
        await asyncio.sleep(1)  # 模拟网络延迟
        
        results = [
            {
                "title": f"搜索结果 {i+1}: {query}",
                "url": f"https://example.com/result{i+1}",
                "snippet": f"关于'{query}'的相关信息..."
            }
            for i in range(max_results)
        ]
        
        return {
            "query": query,
            "results": results,
            "total_found": max_results
        }

class DataAnalysisTool(Tool):
    """数据分析工具"""
    
    def __init__(self):
        super().__init__("data_analysis", "分析数据并生成报告")
    
    async def execute(self, parameters: Dict[str, Any]) -> Dict[str, Any]:
        data = parameters.get("data", [])
        analysis_type = parameters.get("type", "basic")
        
        # 模拟数据分析
        await asyncio.sleep(2)
        
        if analysis_type == "basic":
            result = {
                "summary": {
                    "total_records": len(data),
                    "analysis_type": analysis_type,
                    "key_insights": ["洞察1", "洞察2", "洞察3"]
                },
                "metrics": {
                    "accuracy": 0.92,
                    "confidence": 0.87
                }
            }
        else:
            result = {
                "summary": {
                    "total_records": len(data),
                    "analysis_type": analysis_type,
                    "advanced_insights": ["高级洞察1", "高级洞察2"]
                }
            }
        
        return result

class FileOperationTool(Tool):
    """文件操作工具"""
    
    def __init__(self):
        super().__init__("file_operation", "执行文件读写操作")
    
    async def execute(self, parameters: Dict[str, Any]) -> Dict[str, Any]:
        operation = parameters.get("operation", "read")
        file_path = parameters.get("file_path", "")
        content = parameters.get("content", "")
        
        # 模拟文件操作
        await asyncio.sleep(0.5)
        
        if operation == "read":
            return {
                "operation": "read",
                "file_path": file_path,
                "content": f"模拟读取的文件内容: {file_path}",
                "size": 1024
            }
        elif operation == "write":
            return {
                "operation": "write",
                "file_path": file_path,
                "bytes_written": len(content),
                "success": True
            }
        else:
            return {
                "operation": operation,
                "error": f"不支持的操作: {operation}"
            }

class TaskPlanner:
    """任务规划器"""
    
    def __init__(self):
        self.tasks: Dict[str, Task] = {}
        self.task_graph: Dict[str, List[str]] = {}  # 任务依赖图
        self.execution_history: List[Dict[str, Any]] = []
    
    def add_task(self, task: Task) -> str:
        """添加任务"""
        self.tasks[task.id] = task
        self.task_graph[task.id] = task.dependencies.copy()
        return task.id
    
    def create_task(self, name: str, description: str, task_type: str,
                   priority: TaskPriority = TaskPriority.MEDIUM,
                   dependencies: List[str] = None,
                   parameters: Dict[str, Any] = None,
                   estimated_duration: float = 60.0) -> str:
        """创建任务"""
        task = Task(
            id=str(uuid.uuid4()),
            name=name,
            description=description,
            task_type=task_type,
            priority=priority,
            dependencies=dependencies or [],
            parameters=parameters or {},
            estimated_duration=estimated_duration
        )
        return self.add_task(task)
    
    def get_ready_tasks(self) -> List[Task]:
        """获取可执行的任务（依赖已满足）"""
        ready_tasks = []
        
        for task_id, task in self.tasks.items():
            if task.status != TaskStatus.PENDING:
                continue
            
            # 检查依赖是否都已完成
            dependencies_met = True
            for dep_id in task.dependencies:
                if dep_id not in self.tasks:
                    dependencies_met = False
                    break
                if self.tasks[dep_id].status != TaskStatus.COMPLETED:
                    dependencies_met = False
                    break
            
            if dependencies_met:
                ready_tasks.append(task)
        
        # 按优先级排序
        ready_tasks.sort(key=lambda t: t.priority.value, reverse=True)
        return ready_tasks
    
    def decompose_complex_task(self, task: Task) -> List[Task]:
        """分解复杂任务为子任务"""
        subtasks = []
        
        if task.task_type == "research_project":
            # 研究项目分解
            subtasks.extend([
                Task(
                    id=str(uuid.uuid4()),
                    name=f"{task.name} - 信息收集",
                    description="收集相关信息和资料",
                    task_type="web_search",
                    priority=task.priority,
                    dependencies=[],
                    parameters={"query": task.parameters.get("topic", "")},
                    estimated_duration=30.0
                ),
                Task(
                    id=str(uuid.uuid4()),
                    name=f"{task.name} - 数据分析",
                    description="分析收集到的数据",
                    task_type="data_analysis",
                    priority=task.priority,
                    dependencies=[],  # 将在添加时设置依赖
                    parameters={"type": "research"},
                    estimated_duration=45.0
                ),
                Task(
                    id=str(uuid.uuid4()),
                    name=f"{task.name} - 报告生成",
                    description="生成研究报告",
                    task_type="file_operation",
                    priority=task.priority,
                    dependencies=[],  # 将在添加时设置依赖
                    parameters={"operation": "write", "file_path": f"{task.name}_report.md"},
                    estimated_duration=20.0
                )
            ])
            
            # 设置子任务间的依赖关系
            if len(subtasks) >= 2:
                subtasks[1].dependencies = [subtasks[0].id]
            if len(subtasks) >= 3:
                subtasks[2].dependencies = [subtasks[1].id]
        
        elif task.task_type == "data_pipeline":
            # 数据管道分解
            subtasks.extend([
                Task(
                    id=str(uuid.uuid4()),
                    name=f"{task.name} - 数据提取",
                    description="从数据源提取数据",
                    task_type="file_operation",
                    priority=task.priority,
                    dependencies=[],
                    parameters={"operation": "read"},
                    estimated_duration=15.0
                ),
                Task(
                    id=str(uuid.uuid4()),
                    name=f"{task.name} - 数据处理",
                    description="清洗和转换数据",
                    task_type="data_analysis",
                    priority=task.priority,
                    dependencies=[],
                    parameters={"type": "preprocessing"},
                    estimated_duration=30.0
                ),
                Task(
                    id=str(uuid.uuid4()),
                    name=f"{task.name} - 数据存储",
                    description="存储处理后的数据",
                    task_type="file_operation",
                    priority=task.priority,
                    dependencies=[],
                    parameters={"operation": "write"},
                    estimated_duration=10.0
                )
            ])
            
            # 设置依赖关系
            for i in range(1, len(subtasks)):
                subtasks[i].dependencies = [subtasks[i-1].id]
        
        return subtasks
    
    def get_execution_plan(self) -> List[List[str]]:
        """获取执行计划（拓扑排序）"""
        # 简化的拓扑排序实现
        plan = []
        remaining_tasks = set(self.tasks.keys())
        
        while remaining_tasks:
            # 找到没有依赖或依赖已满足的任务
            ready_in_round = []
            for task_id in remaining_tasks:
                task = self.tasks[task_id]
                if all(dep_id not in remaining_tasks for dep_id in task.dependencies):
                    ready_in_round.append(task_id)
            
            if not ready_in_round:
                # 检测循环依赖
                break
            
            plan.append(ready_in_round)
            remaining_tasks -= set(ready_in_round)
        
        return plan

class TaskExecutor:
    """任务执行器"""
    
    def __init__(self):
        self.tools: Dict[str, Tool] = {}
        self.running_tasks: Dict[str, asyncio.Task] = {}
        self.max_concurrent_tasks = 3
        
        # 注册默认工具
        self.register_tool(WebSearchTool())
        self.register_tool(DataAnalysisTool())
        self.register_tool(FileOperationTool())
    
    def register_tool(self, tool: Tool):
        """注册工具"""
        self.tools[tool.name] = tool
    
    async def execute_task(self, task: Task) -> Dict[str, Any]:
        """执行单个任务"""
        print(f"开始执行任务: {task.name}")
        
        task.status = TaskStatus.RUNNING
        task.started_at = time.time()
        
        try:
            # 根据任务类型选择工具
            tool_name = self._get_tool_for_task_type(task.task_type)
            if tool_name not in self.tools:
                raise ValueError(f"未找到适合的工具: {tool_name}")
            
            tool = self.tools[tool_name]
            
            # 验证参数
            if not tool.validate_parameters(task.parameters):
                raise ValueError("任务参数验证失败")
            
            # 执行工具
            result = await tool.execute(task.parameters)
            
            task.status = TaskStatus.COMPLETED
            task.completed_at = time.time()
            task.result = result
            
            print(f"任务完成: {task.name}")
            return result
            
        except Exception as e:
            task.status = TaskStatus.FAILED
            task.error = str(e)
            task.completed_at = time.time()
            
            print(f"任务失败: {task.name}, 错误: {e}")
            
            # 重试逻辑
            if task.retry_count < task.max_retries:
                task.retry_count += 1
                task.status = TaskStatus.PENDING
                print(f"任务将重试: {task.name} (第{task.retry_count}次)")
            
            raise e
    
    def _get_tool_for_task_type(self, task_type: str) -> str:
        """根据任务类型获取工具名称"""
        mapping = {
            "web_search": "web_search",
            "data_analysis": "data_analysis",
            "file_operation": "file_operation",
            "research_project": "web_search",  # 默认使用搜索工具
            "data_pipeline": "data_analysis"   # 默认使用分析工具
        }
        return mapping.get(task_type, "web_search")
    
    async def execute_tasks_parallel(self, tasks: List[Task], max_concurrent: int = None) -> List[Dict[str, Any]]:
        """并行执行多个任务"""
        if max_concurrent is None:
            max_concurrent = self.max_concurrent_tasks
        
        semaphore = asyncio.Semaphore(max_concurrent)
        
        async def execute_with_semaphore(task):
            async with semaphore:
                return await self.execute_task(task)
        
        # 创建任务协程
        task_coroutines = [execute_with_semaphore(task) for task in tasks]
        
        # 并行执行
        results = await asyncio.gather(*task_coroutines, return_exceptions=True)
        
        return results

class PlanningExecutionEngine:
    """规划执行引擎"""
    
    def __init__(self):
        self.planner = TaskPlanner()
        self.executor = TaskExecutor()
        self.execution_stats = {
            "total_tasks": 0,
            "completed_tasks": 0,
            "failed_tasks": 0,
            "total_execution_time": 0.0
        }
    
    async def execute_plan(self, auto_decompose: bool = True) -> Dict[str, Any]:
        """执行整个计划"""
        start_time = time.time()
        
        print("开始执行任务计划...")
        
        # 自动分解复杂任务
        if auto_decompose:
            await self._auto_decompose_tasks()
        
        # 获取执行计划
        execution_plan = self.planner.get_execution_plan()
        
        print(f"执行计划包含 {len(execution_plan)} 个阶段")
        
        results = []
        
        # 按阶段执行
        for stage_idx, stage_task_ids in enumerate(execution_plan):
            print(f"\n执行阶段 {stage_idx + 1}: {len(stage_task_ids)} 个任务")
            
            # 获取当前阶段的任务
            stage_tasks = [self.planner.tasks[task_id] for task_id in stage_task_ids]
            
            # 并行执行当前阶段的任务
            stage_results = await self.executor.execute_tasks_parallel(stage_tasks)
            results.extend(stage_results)
        
        # 更新统计信息
        end_time = time.time()
        self.execution_stats["total_execution_time"] = end_time - start_time
        self.execution_stats["total_tasks"] = len(self.planner.tasks)
        self.execution_stats["completed_tasks"] = sum(
            1 for task in self.planner.tasks.values() 
            if task.status == TaskStatus.COMPLETED
        )
        self.execution_stats["failed_tasks"] = sum(
            1 for task in self.planner.tasks.values() 
            if task.status == TaskStatus.FAILED
        )
        
        print(f"\n计划执行完成! 总耗时: {self.execution_stats['total_execution_time']:.2f}秒")
        print(f"成功: {self.execution_stats['completed_tasks']}, 失败: {self.execution_stats['failed_tasks']}")
        
        return {
            "execution_stats": self.execution_stats,
            "results": results
        }
    
    async def _auto_decompose_tasks(self):
        """自动分解复杂任务"""
        complex_task_types = ["research_project", "data_pipeline"]
        tasks_to_decompose = [
            task for task in self.planner.tasks.values()
            if task.task_type in complex_task_types
        ]
        
        for complex_task in tasks_to_decompose:
            print(f"分解复杂任务: {complex_task.name}")
            
            # 分解任务
            subtasks = self.planner.decompose_complex_task(complex_task)
            
            # 添加子任务
            for subtask in subtasks:
                self.planner.add_task(subtask)
            
            # 移除原始复杂任务
            del self.planner.tasks[complex_task.id]
            if complex_task.id in self.planner.task_graph:
                del self.planner.task_graph[complex_task.id]
    
    def add_task(self, name: str, description: str, task_type: str, **kwargs) -> str:
        """添加任务的便捷方法"""
        return self.planner.create_task(name, description, task_type, **kwargs)
    
    def get_task_status(self, task_id: str) -> Optional[TaskStatus]:
        """获取任务状态"""
        task = self.planner.tasks.get(task_id)
        return task.status if task else None
    
    def get_execution_summary(self) -> Dict[str, Any]:
        """获取执行摘要"""
        return {
            "stats": self.execution_stats,
            "task_count_by_status": {
                status.value: sum(
                    1 for task in self.planner.tasks.values()
                    if task.status == status
                )
                for status in TaskStatus
            },
            "average_task_duration": (
                sum(
                    (task.completed_at or 0) - (task.started_at or 0)
                    for task in self.planner.tasks.values()
                    if task.started_at and task.completed_at
                ) / max(1, self.execution_stats["completed_tasks"])
            )
        }

# 示例使用
async def main():
    """主函数演示"""
    print("AI Agent规划执行引擎示例")
    print("=" * 50)
    
    # 创建规划执行引擎
    engine = PlanningExecutionEngine()
    
    # 添加一些示例任务
    task1_id = engine.add_task(
        name="AI市场研究",
        description="研究2024年AI Agent市场趋势",
        task_type="research_project",
        priority=TaskPriority.HIGH,
        parameters={"topic": "AI Agent市场趋势"}
    )
    
    task2_id = engine.add_task(
        name="用户数据分析",
        description="分析用户行为数据",
        task_type="data_pipeline",
        priority=TaskPriority.MEDIUM,
        parameters={"data_source": "user_behavior.csv"}
    )
    
    task3_id = engine.add_task(
        name="竞品分析报告",
        description="生成竞品分析报告",
        task_type="web_search",
        priority=TaskPriority.MEDIUM,
        dependencies=[task1_id],
        parameters={"query": "AI Agent竞品分析"}
    )
    
    # 执行计划
    results = await engine.execute_plan()
    
    # 显示执行摘要
    summary = engine.get_execution_summary()
    print(f"\n执行摘要:")
    print(f"  总任务数: {summary['stats']['total_tasks']}")
    print(f"  成功任务: {summary['stats']['completed_tasks']}")
    print(f"  失败任务: {summary['stats']['failed_tasks']}")
    print(f"  总执行时间: {summary['stats']['total_execution_time']:.2f}秒")
    print(f"  平均任务时长: {summary['average_task_duration']:.2f}秒")

if __name__ == "__main__":
    asyncio.run(main())
