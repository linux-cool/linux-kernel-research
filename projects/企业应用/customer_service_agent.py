#!/usr/bin/env python3
"""
企业级智能客服Agent示例代码
展示AI Agent在客服场景中的应用
"""

import time
import json
import uuid
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, asdict
from enum import Enum
import re

class IntentType(Enum):
    """意图类型"""
    GREETING = "greeting"
    PRODUCT_INQUIRY = "product_inquiry"
    ORDER_STATUS = "order_status"
    COMPLAINT = "complaint"
    TECHNICAL_SUPPORT = "technical_support"
    BILLING = "billing"
    CANCELLATION = "cancellation"
    UNKNOWN = "unknown"

class Priority(Enum):
    """优先级"""
    LOW = 1
    MEDIUM = 2
    HIGH = 3
    URGENT = 4

@dataclass
class CustomerContext:
    """客户上下文信息"""
    customer_id: str
    name: str
    email: str
    phone: str
    membership_level: str  # "bronze", "silver", "gold", "platinum"
    order_history: List[Dict[str, Any]]
    previous_interactions: List[Dict[str, Any]]
    current_session_id: str

@dataclass
class Conversation:
    """对话记录"""
    session_id: str
    customer_id: str
    messages: List[Dict[str, Any]]
    intent: IntentType
    priority: Priority
    status: str  # "active", "resolved", "escalated"
    created_at: float
    updated_at: float
    resolution_time: Optional[float] = None

class IntentClassifier:
    """意图识别器"""
    
    def __init__(self):
        self.intent_patterns = {
            IntentType.GREETING: [
                r"hello|hi|hey|good morning|good afternoon|good evening",
                r"how are you|nice to meet you"
            ],
            IntentType.PRODUCT_INQUIRY: [
                r"product|item|what.*sell|catalog|price|cost|buy|purchase",
                r"tell me about|information about|details about"
            ],
            IntentType.ORDER_STATUS: [
                r"order|delivery|shipping|track|status|when.*arrive",
                r"where.*order|order.*number"
            ],
            IntentType.COMPLAINT: [
                r"complaint|problem|issue|wrong|broken|defective|unhappy",
                r"not working|disappointed|terrible|awful"
            ],
            IntentType.TECHNICAL_SUPPORT: [
                r"technical|support|help|how to|tutorial|setup|install",
                r"not working|error|bug|crash"
            ],
            IntentType.BILLING: [
                r"bill|invoice|payment|charge|refund|money|credit card",
                r"subscription|renewal|cancel.*subscription"
            ],
            IntentType.CANCELLATION: [
                r"cancel|return|refund|exchange|give back",
                r"don't want|change mind"
            ]
        }
    
    def classify(self, message: str) -> IntentType:
        """分类用户意图"""
        message_lower = message.lower()
        
        for intent, patterns in self.intent_patterns.items():
            for pattern in patterns:
                if re.search(pattern, message_lower):
                    return intent
        
        return IntentType.UNKNOWN

class KnowledgeBase:
    """知识库"""
    
    def __init__(self):
        self.faq = {
            "shipping_time": "Standard shipping takes 3-5 business days, express shipping takes 1-2 business days.",
            "return_policy": "You can return items within 30 days of purchase for a full refund.",
            "warranty": "All products come with a 1-year manufacturer warranty.",
            "payment_methods": "We accept credit cards, PayPal, and bank transfers.",
            "customer_support_hours": "Our customer support is available 24/7.",
            "order_tracking": "You can track your order using the tracking number sent to your email.",
            "product_availability": "Product availability is updated in real-time on our website.",
            "discount_codes": "Discount codes can be applied at checkout and cannot be combined."
        }
        
        self.product_catalog = {
            "laptop_001": {
                "name": "Professional Laptop Pro",
                "price": 1299.99,
                "description": "High-performance laptop for professionals",
                "specs": "Intel i7, 16GB RAM, 512GB SSD",
                "availability": "In Stock"
            },
            "phone_001": {
                "name": "Smart Phone X",
                "price": 899.99,
                "description": "Latest smartphone with advanced features",
                "specs": "6.5\" display, 128GB storage, 48MP camera",
                "availability": "In Stock"
            },
            "tablet_001": {
                "name": "Tablet Air",
                "price": 599.99,
                "description": "Lightweight tablet for work and entertainment",
                "specs": "10.9\" display, 64GB storage, Wi-Fi + Cellular",
                "availability": "Limited Stock"
            }
        }
    
    def search_faq(self, query: str) -> Optional[str]:
        """搜索FAQ"""
        query_lower = query.lower()
        
        for key, answer in self.faq.items():
            if any(keyword in query_lower for keyword in key.split('_')):
                return answer
        
        return None
    
    def search_products(self, query: str) -> List[Dict[str, Any]]:
        """搜索产品"""
        query_lower = query.lower()
        results = []
        
        for product_id, product_info in self.product_catalog.items():
            if (query_lower in product_info["name"].lower() or 
                query_lower in product_info["description"].lower()):
                results.append({
                    "id": product_id,
                    **product_info
                })
        
        return results

class EscalationManager:
    """升级管理器"""
    
    def __init__(self):
        self.escalation_rules = {
            IntentType.COMPLAINT: Priority.HIGH,
            IntentType.BILLING: Priority.MEDIUM,
            IntentType.TECHNICAL_SUPPORT: Priority.MEDIUM,
            IntentType.CANCELLATION: Priority.HIGH
        }
        
        self.human_agents = {
            "agent_001": {"name": "Alice Johnson", "specialization": "technical", "available": True},
            "agent_002": {"name": "Bob Smith", "specialization": "billing", "available": True},
            "agent_003": {"name": "Carol Davis", "specialization": "general", "available": False}
        }
    
    def should_escalate(self, intent: IntentType, customer_context: CustomerContext, 
                       conversation_length: int) -> bool:
        """判断是否需要升级到人工"""
        # VIP客户优先升级
        if customer_context.membership_level in ["gold", "platinum"]:
            return True
        
        # 复杂问题升级
        if intent in [IntentType.COMPLAINT, IntentType.BILLING, IntentType.CANCELLATION]:
            return True
        
        # 对话轮次过多升级
        if conversation_length > 5:
            return True
        
        return False
    
    def assign_human_agent(self, intent: IntentType) -> Optional[str]:
        """分配人工客服"""
        # 根据专业领域分配
        specialization_map = {
            IntentType.TECHNICAL_SUPPORT: "technical",
            IntentType.BILLING: "billing"
        }
        
        required_specialization = specialization_map.get(intent, "general")
        
        for agent_id, agent_info in self.human_agents.items():
            if (agent_info["available"] and 
                agent_info["specialization"] in [required_specialization, "general"]):
                agent_info["available"] = False  # 标记为忙碌
                return agent_id
        
        return None

class CustomerServiceAgent:
    """智能客服Agent"""
    
    def __init__(self):
        self.intent_classifier = IntentClassifier()
        self.knowledge_base = KnowledgeBase()
        self.escalation_manager = EscalationManager()
        self.active_conversations: Dict[str, Conversation] = {}
        self.customer_database = {}
        self.response_templates = self._load_response_templates()
    
    def _load_response_templates(self) -> Dict[str, List[str]]:
        """加载响应模板"""
        return {
            IntentType.GREETING.value: [
                "Hello! Welcome to our customer service. How can I help you today?",
                "Hi there! I'm here to assist you. What can I do for you?",
                "Good day! Thank you for contacting us. How may I assist you?"
            ],
            IntentType.PRODUCT_INQUIRY.value: [
                "I'd be happy to help you with product information. Let me search our catalog for you.",
                "Great! I can provide you with detailed product information. What specific product are you interested in?",
                "I'll help you find the perfect product. Could you tell me more about what you're looking for?"
            ],
            IntentType.ORDER_STATUS.value: [
                "I'll check your order status right away. Could you please provide your order number?",
                "Let me look up your order information. What's your order number or email address?",
                "I can help you track your order. Please share your order details with me."
            ],
            IntentType.UNKNOWN.value: [
                "I'm not sure I understand. Could you please rephrase your question?",
                "I'd like to help you better. Can you provide more details about what you need?",
                "Let me connect you with a human agent who can better assist you with this inquiry."
            ]
        }
    
    def start_conversation(self, customer_context: CustomerContext) -> str:
        """开始对话"""
        session_id = str(uuid.uuid4())
        
        conversation = Conversation(
            session_id=session_id,
            customer_id=customer_context.customer_id,
            messages=[],
            intent=IntentType.UNKNOWN,
            priority=Priority.LOW,
            status="active",
            created_at=time.time(),
            updated_at=time.time()
        )
        
        self.active_conversations[session_id] = conversation
        
        # 个性化问候
        greeting = self._generate_personalized_greeting(customer_context)
        self._add_message(session_id, "agent", greeting)
        
        return session_id
    
    def _generate_personalized_greeting(self, customer_context: CustomerContext) -> str:
        """生成个性化问候"""
        base_greeting = f"Hello {customer_context.name}!"
        
        if customer_context.membership_level == "platinum":
            return f"{base_greeting} As our valued Platinum member, I'm here to provide you with priority support. How can I assist you today?"
        elif customer_context.membership_level == "gold":
            return f"{base_greeting} Thank you for being a Gold member. How can I help you today?"
        else:
            return f"{base_greeting} Welcome to our customer service. How can I assist you today?"
    
    def process_message(self, session_id: str, message: str, 
                       customer_context: CustomerContext) -> Dict[str, Any]:
        """处理客户消息"""
        if session_id not in self.active_conversations:
            return {"error": "Invalid session ID"}
        
        conversation = self.active_conversations[session_id]
        
        # 添加客户消息
        self._add_message(session_id, "customer", message)
        
        # 识别意图
        intent = self.intent_classifier.classify(message)
        conversation.intent = intent
        
        # 更新优先级
        conversation.priority = self._calculate_priority(intent, customer_context)
        
        # 检查是否需要升级
        if self.escalation_manager.should_escalate(
            intent, customer_context, len(conversation.messages)
        ):
            return self._escalate_to_human(session_id, customer_context)
        
        # 生成响应
        response = self._generate_response(intent, message, customer_context)
        self._add_message(session_id, "agent", response["text"])
        
        conversation.updated_at = time.time()
        
        return {
            "session_id": session_id,
            "response": response["text"],
            "intent": intent.value,
            "priority": conversation.priority.value,
            "suggestions": response.get("suggestions", []),
            "escalated": False
        }
    
    def _calculate_priority(self, intent: IntentType, customer_context: CustomerContext) -> Priority:
        """计算优先级"""
        base_priority = Priority.LOW
        
        # 根据意图调整优先级
        if intent == IntentType.COMPLAINT:
            base_priority = Priority.HIGH
        elif intent in [IntentType.BILLING, IntentType.CANCELLATION]:
            base_priority = Priority.MEDIUM
        
        # 根据会员等级调整
        if customer_context.membership_level in ["gold", "platinum"]:
            if base_priority == Priority.LOW:
                base_priority = Priority.MEDIUM
            elif base_priority == Priority.MEDIUM:
                base_priority = Priority.HIGH
        
        return base_priority
    
    def _generate_response(self, intent: IntentType, message: str, 
                          customer_context: CustomerContext) -> Dict[str, Any]:
        """生成响应"""
        response = {"text": "", "suggestions": []}
        
        if intent == IntentType.GREETING:
            response["text"] = "Thank you for your greeting! How can I help you today?"
            response["suggestions"] = [
                "Check order status",
                "Product information",
                "Technical support",
                "Billing inquiry"
            ]
        
        elif intent == IntentType.PRODUCT_INQUIRY:
            products = self.knowledge_base.search_products(message)
            if products:
                response["text"] = "I found these products that might interest you:\n\n"
                for product in products[:3]:  # 限制显示数量
                    response["text"] += f"• {product['name']} - ${product['price']}\n"
                    response["text"] += f"  {product['description']}\n"
                    response["text"] += f"  Status: {product['availability']}\n\n"
            else:
                response["text"] = "I couldn't find specific products matching your query. Let me connect you with our product specialist."
        
        elif intent == IntentType.ORDER_STATUS:
            # 模拟订单查询
            if customer_context.order_history:
                latest_order = customer_context.order_history[-1]
                response["text"] = f"Your latest order #{latest_order['order_id']} is currently {latest_order['status']}. "
                response["text"] += f"Estimated delivery: {latest_order.get('estimated_delivery', 'TBD')}"
            else:
                response["text"] = "I don't see any recent orders in your account. Could you please provide your order number?"
        
        elif intent == IntentType.TECHNICAL_SUPPORT:
            faq_answer = self.knowledge_base.search_faq(message)
            if faq_answer:
                response["text"] = faq_answer
            else:
                response["text"] = "I understand you need technical support. Let me gather some information to better assist you. What specific issue are you experiencing?"
        
        elif intent == IntentType.BILLING:
            response["text"] = "I can help you with billing inquiries. For security reasons, I'll need to verify your account. Could you please confirm your email address?"
        
        elif intent == IntentType.COMPLAINT:
            response["text"] = f"I sincerely apologize for any inconvenience, {customer_context.name}. Your concern is very important to us. Let me escalate this to our specialized team to ensure it's resolved quickly."
        
        else:  # UNKNOWN
            templates = self.response_templates[IntentType.UNKNOWN.value]
            response["text"] = templates[0]  # 使用第一个模板
        
        return response
    
    def _escalate_to_human(self, session_id: str, customer_context: CustomerContext) -> Dict[str, Any]:
        """升级到人工客服"""
        conversation = self.active_conversations[session_id]
        agent_id = self.escalation_manager.assign_human_agent(conversation.intent)
        
        if agent_id:
            agent_info = self.escalation_manager.human_agents[agent_id]
            escalation_message = f"I'm connecting you with {agent_info['name']}, our {agent_info['specialization']} specialist. They'll be with you shortly."
        else:
            escalation_message = "I'm adding you to the queue for our next available human agent. Thank you for your patience."
        
        self._add_message(session_id, "agent", escalation_message)
        conversation.status = "escalated"
        conversation.updated_at = time.time()
        
        return {
            "session_id": session_id,
            "response": escalation_message,
            "escalated": True,
            "assigned_agent": agent_id
        }
    
    def _add_message(self, session_id: str, sender: str, content: str):
        """添加消息到对话"""
        conversation = self.active_conversations[session_id]
        message = {
            "sender": sender,
            "content": content,
            "timestamp": time.time()
        }
        conversation.messages.append(message)
    
    def get_conversation_history(self, session_id: str) -> Optional[Conversation]:
        """获取对话历史"""
        return self.active_conversations.get(session_id)
    
    def get_analytics(self) -> Dict[str, Any]:
        """获取分析数据"""
        total_conversations = len(self.active_conversations)
        intent_distribution = {}
        priority_distribution = {}
        escalation_rate = 0
        
        for conv in self.active_conversations.values():
            intent_key = conv.intent.value
            intent_distribution[intent_key] = intent_distribution.get(intent_key, 0) + 1
            
            priority_key = conv.priority.value
            priority_distribution[priority_key] = priority_distribution.get(priority_key, 0) + 1
            
            if conv.status == "escalated":
                escalation_rate += 1
        
        if total_conversations > 0:
            escalation_rate = escalation_rate / total_conversations * 100
        
        return {
            "total_conversations": total_conversations,
            "intent_distribution": intent_distribution,
            "priority_distribution": priority_distribution,
            "escalation_rate": f"{escalation_rate:.1f}%",
            "active_conversations": sum(1 for c in self.active_conversations.values() if c.status == "active")
        }

# 示例使用
def main():
    """主函数演示"""
    print("企业级智能客服Agent示例")
    print("=" * 50)
    
    # 创建客服Agent
    agent = CustomerServiceAgent()
    
    # 模拟客户信息
    customer = CustomerContext(
        customer_id="cust_001",
        name="张三",
        email="zhangsan@example.com",
        phone="+86-138-0000-0000",
        membership_level="gold",
        order_history=[
            {
                "order_id": "ORD-2024-001",
                "status": "shipped",
                "estimated_delivery": "2024-01-15"
            }
        ],
        previous_interactions=[],
        current_session_id=""
    )
    
    # 开始对话
    session_id = agent.start_conversation(customer)
    print(f"对话开始，会话ID: {session_id}")
    
    # 模拟客户消息
    test_messages = [
        "Hello, I need help",
        "I want to check my order status",
        "I'm looking for a new laptop",
        "I have a complaint about my recent purchase"
    ]
    
    for message in test_messages:
        print(f"\n客户: {message}")
        response = agent.process_message(session_id, message, customer)
        
        if "error" in response:
            print(f"错误: {response['error']}")
        else:
            print(f"客服: {response['response']}")
            print(f"识别意图: {response['intent']}")
            print(f"优先级: {response['priority']}")
            
            if response.get("escalated"):
                print("*** 已升级到人工客服 ***")
                break
    
    # 显示分析数据
    print(f"\n系统分析数据:")
    analytics = agent.get_analytics()
    for key, value in analytics.items():
        print(f"  {key}: {value}")

if __name__ == "__main__":
    main()
