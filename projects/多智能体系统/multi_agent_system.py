#!/usr/bin/env python3
"""
多智能体系统协作机制示例代码
展示智能体间的通信、协作和任务分配
"""

import asyncio
import json
import time
import uuid
from enum import Enum
from typing import Dict, List, Any, Optional
from dataclasses import dataclass
from abc import ABC, abstractmethod

# 消息类型枚举
class MessageType(Enum):
    TASK_REQUEST = "task_request"
    TASK_RESPONSE = "task_response"
    COLLABORATION_REQUEST = "collaboration_request"
    STATUS_UPDATE = "status_update"
    RESOURCE_REQUEST = "resource_request"

# 智能体状态枚举
class AgentStatus(Enum):
    IDLE = "idle"
    BUSY = "busy"
    OFFLINE = "offline"
    ERROR = "error"

@dataclass
class Message:
    """智能体间通信消息"""
    id: str
    sender_id: str
    receiver_id: str
    message_type: MessageType
    content: Dict[str, Any]
    timestamp: float
    priority: int = 1

@dataclass
class Task:
    """任务定义"""
    id: str
    title: str
    description: str
    required_skills: List[str]
    priority: int
    deadline: Optional[float] = None
    dependencies: List[str] = None

class CommunicationProtocol:
    """智能体通信协议"""
    
    def __init__(self):
        self.message_queue = asyncio.Queue()
        self.subscribers = {}
    
    async def send_message(self, message: Message):
        """发送消息"""
        await self.message_queue.put(message)
    
    async def subscribe(self, agent_id: str, callback):
        """订阅消息"""
        if agent_id not in self.subscribers:
            self.subscribers[agent_id] = []
        self.subscribers[agent_id].append(callback)
    
    async def process_messages(self):
        """处理消息队列"""
        while True:
            try:
                message = await asyncio.wait_for(self.message_queue.get(), timeout=1.0)
                await self.deliver_message(message)
            except asyncio.TimeoutError:
                continue
    
    async def deliver_message(self, message: Message):
        """投递消息"""
        if message.receiver_id in self.subscribers:
            for callback in self.subscribers[message.receiver_id]:
                await callback(message)

class BaseAgent(ABC):
    """智能体基类"""
    
    def __init__(self, agent_id: str, name: str, skills: List[str]):
        self.agent_id = agent_id
        self.name = name
        self.skills = skills
        self.status = AgentStatus.IDLE
        self.current_tasks = []
        self.completed_tasks = []
        self.communication = None
        self.knowledge_base = {}
    
    def set_communication(self, protocol: CommunicationProtocol):
        """设置通信协议"""
        self.communication = protocol
    
    @abstractmethod
    async def process_task(self, task: Task) -> Dict[str, Any]:
        """处理任务的抽象方法"""
        pass
    
    async def handle_message(self, message: Message):
        """处理接收到的消息"""
        if message.message_type == MessageType.TASK_REQUEST:
            await self.handle_task_request(message)
        elif message.message_type == MessageType.COLLABORATION_REQUEST:
            await self.handle_collaboration_request(message)
        elif message.message_type == MessageType.STATUS_UPDATE:
            await self.handle_status_update(message)
    
    async def handle_task_request(self, message: Message):
        """处理任务请求"""
        task_data = message.content
        task = Task(**task_data)
        
        # 检查是否有能力处理该任务
        if self.can_handle_task(task):
            self.status = AgentStatus.BUSY
            self.current_tasks.append(task)
            
            # 发送接受消息
            response = Message(
                id=str(uuid.uuid4()),
                sender_id=self.agent_id,
                receiver_id=message.sender_id,
                message_type=MessageType.TASK_RESPONSE,
                content={"status": "accepted", "task_id": task.id},
                timestamp=time.time()
            )
            await self.communication.send_message(response)
            
            # 处理任务
            result = await self.process_task(task)
            
            # 发送完成消息
            completion_response = Message(
                id=str(uuid.uuid4()),
                sender_id=self.agent_id,
                receiver_id=message.sender_id,
                message_type=MessageType.TASK_RESPONSE,
                content={"status": "completed", "task_id": task.id, "result": result},
                timestamp=time.time()
            )
            await self.communication.send_message(completion_response)
            
            self.current_tasks.remove(task)
            self.completed_tasks.append(task)
            self.status = AgentStatus.IDLE
        else:
            # 发送拒绝消息
            response = Message(
                id=str(uuid.uuid4()),
                sender_id=self.agent_id,
                receiver_id=message.sender_id,
                message_type=MessageType.TASK_RESPONSE,
                content={"status": "rejected", "task_id": task.id, "reason": "insufficient_skills"},
                timestamp=time.time()
            )
            await self.communication.send_message(response)
    
    def can_handle_task(self, task: Task) -> bool:
        """检查是否能处理任务"""
        return any(skill in self.skills for skill in task.required_skills)
    
    async def handle_collaboration_request(self, message: Message):
        """处理协作请求"""
        # 简单的协作逻辑
        collaboration_data = message.content
        if self.status == AgentStatus.IDLE:
            response = Message(
                id=str(uuid.uuid4()),
                sender_id=self.agent_id,
                receiver_id=message.sender_id,
                message_type=MessageType.TASK_RESPONSE,
                content={"status": "available", "skills": self.skills},
                timestamp=time.time()
            )
            await self.communication.send_message(response)
    
    async def handle_status_update(self, message: Message):
        """处理状态更新"""
        # 更新对其他智能体的了解
        agent_id = message.sender_id
        status_info = message.content
        self.knowledge_base[agent_id] = status_info

class ResearchAgent(BaseAgent):
    """研究型智能体"""
    
    def __init__(self, agent_id: str, name: str):
        super().__init__(agent_id, name, ["research", "analysis", "data_collection"])
        self.research_database = {}
    
    async def process_task(self, task: Task) -> Dict[str, Any]:
        """处理研究任务"""
        print(f"[{self.name}] 开始研究任务: {task.title}")
        
        # 模拟研究过程
        await asyncio.sleep(2)  # 模拟研究时间
        
        research_result = {
            "task_id": task.id,
            "findings": f"关于'{task.description}'的研究发现",
            "data_sources": ["学术论文", "行业报告", "专家访谈"],
            "confidence": 0.85,
            "recommendations": ["建议1", "建议2", "建议3"]
        }
        
        # 存储研究结果
        self.research_database[task.id] = research_result
        
        print(f"[{self.name}] 完成研究任务: {task.title}")
        return research_result

class AnalysisAgent(BaseAgent):
    """分析型智能体"""
    
    def __init__(self, agent_id: str, name: str):
        super().__init__(agent_id, name, ["analysis", "modeling", "statistics"])
        self.analysis_tools = ["统计分析", "机器学习", "数据挖掘"]
    
    async def process_task(self, task: Task) -> Dict[str, Any]:
        """处理分析任务"""
        print(f"[{self.name}] 开始分析任务: {task.title}")
        
        # 模拟分析过程
        await asyncio.sleep(1.5)
        
        analysis_result = {
            "task_id": task.id,
            "analysis_type": "综合分析",
            "metrics": {
                "accuracy": 0.92,
                "precision": 0.88,
                "recall": 0.90
            },
            "insights": f"基于'{task.description}'的分析洞察",
            "visualizations": ["图表1", "图表2", "仪表板"]
        }
        
        print(f"[{self.name}] 完成分析任务: {task.title}")
        return analysis_result

class CoordinatorAgent(BaseAgent):
    """协调型智能体"""
    
    def __init__(self, agent_id: str, name: str):
        super().__init__(agent_id, name, ["coordination", "planning", "management"])
        self.agent_registry = {}
        self.task_assignments = {}
    
    async def process_task(self, task: Task) -> Dict[str, Any]:
        """处理协调任务"""
        print(f"[{self.name}] 开始协调任务: {task.title}")
        
        # 分解复杂任务
        subtasks = self.decompose_task(task)
        
        # 分配子任务给合适的智能体
        assignment_results = []
        for subtask in subtasks:
            assigned_agent = await self.assign_subtask(subtask)
            if assigned_agent:
                assignment_results.append({
                    "subtask": subtask.title,
                    "assigned_to": assigned_agent,
                    "status": "assigned"
                })
        
        coordination_result = {
            "task_id": task.id,
            "subtasks_created": len(subtasks),
            "assignments": assignment_results,
            "coordination_strategy": "分布式协作",
            "estimated_completion": time.time() + 300  # 5分钟后
        }
        
        print(f"[{self.name}] 完成协调任务: {task.title}")
        return coordination_result
    
    def decompose_task(self, task: Task) -> List[Task]:
        """分解任务为子任务"""
        subtasks = []
        
        if "research" in task.description.lower():
            subtasks.append(Task(
                id=str(uuid.uuid4()),
                title=f"研究子任务: {task.title}",
                description=f"深入研究{task.description}",
                required_skills=["research"],
                priority=task.priority
            ))
        
        if "analysis" in task.description.lower():
            subtasks.append(Task(
                id=str(uuid.uuid4()),
                title=f"分析子任务: {task.title}",
                description=f"分析{task.description}的数据",
                required_skills=["analysis"],
                priority=task.priority
            ))
        
        return subtasks
    
    async def assign_subtask(self, subtask: Task) -> Optional[str]:
        """分配子任务"""
        # 寻找合适的智能体
        for agent_id, agent_info in self.knowledge_base.items():
            if agent_info.get("status") == "idle":
                agent_skills = agent_info.get("skills", [])
                if any(skill in agent_skills for skill in subtask.required_skills):
                    # 发送任务请求
                    task_request = Message(
                        id=str(uuid.uuid4()),
                        sender_id=self.agent_id,
                        receiver_id=agent_id,
                        message_type=MessageType.TASK_REQUEST,
                        content=subtask.__dict__,
                        timestamp=time.time()
                    )
                    await self.communication.send_message(task_request)
                    return agent_id
        
        return None
    
    def register_agent(self, agent_id: str, agent_info: Dict[str, Any]):
        """注册智能体"""
        self.agent_registry[agent_id] = agent_info

class MultiAgentSystem:
    """多智能体系统"""
    
    def __init__(self):
        self.agents = {}
        self.communication = CommunicationProtocol()
        self.task_queue = []
        self.system_metrics = {
            "tasks_completed": 0,
            "tasks_failed": 0,
            "average_response_time": 0.0
        }
    
    def add_agent(self, agent: BaseAgent):
        """添加智能体"""
        self.agents[agent.agent_id] = agent
        agent.set_communication(self.communication)
        
        # 订阅消息
        asyncio.create_task(
            self.communication.subscribe(agent.agent_id, agent.handle_message)
        )
    
    async def start_system(self):
        """启动系统"""
        print("启动多智能体系统...")
        
        # 启动消息处理
        asyncio.create_task(self.communication.process_messages())
        
        # 定期更新系统状态
        asyncio.create_task(self.update_system_status())
        
        print("多智能体系统已启动")
    
    async def submit_task(self, task: Task):
        """提交任务"""
        print(f"提交任务: {task.title}")
        
        # 寻找合适的智能体
        suitable_agents = []
        for agent in self.agents.values():
            if agent.can_handle_task(task):
                suitable_agents.append(agent)
        
        if suitable_agents:
            # 选择负载最轻的智能体
            selected_agent = min(suitable_agents, key=lambda a: len(a.current_tasks))
            
            # 发送任务请求
            task_request = Message(
                id=str(uuid.uuid4()),
                sender_id="system",
                receiver_id=selected_agent.agent_id,
                message_type=MessageType.TASK_REQUEST,
                content=task.__dict__,
                timestamp=time.time()
            )
            
            await self.communication.send_message(task_request)
        else:
            print(f"没有找到合适的智能体处理任务: {task.title}")
    
    async def update_system_status(self):
        """更新系统状态"""
        while True:
            # 收集系统指标
            total_tasks = sum(len(agent.completed_tasks) for agent in self.agents.values())
            active_agents = sum(1 for agent in self.agents.values() if agent.status != AgentStatus.OFFLINE)
            
            print(f"系统状态 - 活跃智能体: {active_agents}, 已完成任务: {total_tasks}")
            
            await asyncio.sleep(10)  # 每10秒更新一次

# 示例使用
async def main():
    """主函数演示"""
    print("多智能体系统协作示例")
    print("=" * 50)
    
    # 创建多智能体系统
    mas = MultiAgentSystem()
    
    # 创建不同类型的智能体
    research_agent = ResearchAgent("agent_001", "研究员Alice")
    analysis_agent = AnalysisAgent("agent_002", "分析师Bob")
    coordinator_agent = CoordinatorAgent("agent_003", "协调员Charlie")
    
    # 添加智能体到系统
    mas.add_agent(research_agent)
    mas.add_agent(analysis_agent)
    mas.add_agent(coordinator_agent)
    
    # 启动系统
    await mas.start_system()
    
    # 等待系统初始化
    await asyncio.sleep(1)
    
    # 创建测试任务
    tasks = [
        Task(
            id=str(uuid.uuid4()),
            title="AI市场研究",
            description="研究2024年AI Agent市场趋势",
            required_skills=["research"],
            priority=1
        ),
        Task(
            id=str(uuid.uuid4()),
            title="数据分析报告",
            description="分析用户行为数据",
            required_skills=["analysis"],
            priority=2
        ),
        Task(
            id=str(uuid.uuid4()),
            title="项目协调",
            description="协调多个研究和分析任务",
            required_skills=["coordination"],
            priority=1
        )
    ]
    
    # 提交任务
    for task in tasks:
        await mas.submit_task(task)
        await asyncio.sleep(0.5)  # 间隔提交
    
    # 等待任务完成
    await asyncio.sleep(10)
    
    print("\n任务执行完成!")

if __name__ == "__main__":
    asyncio.run(main())
