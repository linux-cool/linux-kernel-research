#!/usr/bin/env python3
"""
AI Agent记忆与推理系统示例代码
展示记忆存储、检索和推理能力的实现
"""

import numpy as np
import time
import json
import hashlib
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass, asdict
from abc import ABC, abstractmethod
from collections import defaultdict
import heapq

@dataclass
class Memory:
    """记忆单元"""
    id: str
    content: str
    embedding: np.ndarray
    memory_type: str  # 'episodic', 'semantic', 'procedural'
    importance: float
    timestamp: float
    access_count: int = 0
    last_accessed: float = 0.0
    tags: List[str] = None
    
    def __post_init__(self):
        if self.tags is None:
            self.tags = []

@dataclass
class Fact:
    """事实单元"""
    subject: str
    predicate: str
    object: str
    confidence: float
    source: str
    timestamp: float

class MemoryEncoder:
    """记忆编码器"""
    
    def __init__(self, embedding_dim: int = 768):
        self.embedding_dim = embedding_dim
        # 模拟预训练的编码器
        self.vocab_size = 10000
        self.word_to_idx = {}
        self.idx_to_word = {}
        self._build_vocab()
    
    def _build_vocab(self):
        """构建词汇表"""
        common_words = [
            "the", "a", "an", "and", "or", "but", "in", "on", "at", "to", "for",
            "of", "with", "by", "from", "about", "into", "through", "during",
            "before", "after", "above", "below", "up", "down", "out", "off",
            "over", "under", "again", "further", "then", "once", "here", "there",
            "when", "where", "why", "how", "all", "any", "both", "each", "few",
            "more", "most", "other", "some", "such", "no", "nor", "not", "only",
            "own", "same", "so", "than", "too", "very", "can", "will", "just",
            "should", "now", "AI", "agent", "memory", "reasoning", "knowledge",
            "learning", "intelligence", "system", "data", "information"
        ]
        
        for i, word in enumerate(common_words):
            self.word_to_idx[word] = i
            self.idx_to_word[i] = word
    
    def encode(self, text: str) -> np.ndarray:
        """将文本编码为向量"""
        # 简化的编码逻辑，实际应用中会使用预训练模型
        words = text.lower().split()
        word_indices = [self.word_to_idx.get(word, 0) for word in words[:10]]  # 取前10个词
        
        # 创建简单的词袋向量
        embedding = np.zeros(self.embedding_dim)
        for idx in word_indices:
            if idx < self.embedding_dim:
                embedding[idx] = 1.0
        
        # 添加一些随机性以模拟语义信息
        noise = np.random.normal(0, 0.1, self.embedding_dim)
        embedding += noise
        
        # 归一化
        norm = np.linalg.norm(embedding)
        if norm > 0:
            embedding = embedding / norm
            
        return embedding

class VectorMemoryStore:
    """向量记忆存储"""
    
    def __init__(self, embedding_dim: int = 768):
        self.embedding_dim = embedding_dim
        self.memories: Dict[str, Memory] = {}
        self.embeddings = np.array([]).reshape(0, embedding_dim)
        self.memory_ids = []
        self.encoder = MemoryEncoder(embedding_dim)
    
    def store_memory(self, content: str, memory_type: str = "episodic", 
                    importance: float = 1.0, tags: List[str] = None) -> str:
        """存储记忆"""
        # 生成记忆ID
        memory_id = hashlib.md5(f"{content}{time.time()}".encode()).hexdigest()
        
        # 编码内容
        embedding = self.encoder.encode(content)
        
        # 创建记忆对象
        memory = Memory(
            id=memory_id,
            content=content,
            embedding=embedding,
            memory_type=memory_type,
            importance=importance,
            timestamp=time.time(),
            tags=tags or []
        )
        
        # 存储记忆
        self.memories[memory_id] = memory
        
        # 更新向量索引
        if len(self.embeddings) == 0:
            self.embeddings = embedding.reshape(1, -1)
        else:
            self.embeddings = np.vstack([self.embeddings, embedding])
        
        self.memory_ids.append(memory_id)
        
        return memory_id
    
    def retrieve_memories(self, query: str, top_k: int = 5) -> List[Tuple[Memory, float]]:
        """检索相关记忆"""
        if len(self.memories) == 0:
            return []
        
        # 编码查询
        query_embedding = self.encoder.encode(query)
        
        # 计算相似度
        similarities = np.dot(self.embeddings, query_embedding)
        
        # 获取top-k最相似的记忆
        top_indices = np.argsort(similarities)[-top_k:][::-1]
        
        results = []
        for idx in top_indices:
            memory_id = self.memory_ids[idx]
            memory = self.memories[memory_id]
            similarity = similarities[idx]
            
            # 更新访问信息
            memory.access_count += 1
            memory.last_accessed = time.time()
            
            results.append((memory, similarity))
        
        return results
    
    def get_memory_by_id(self, memory_id: str) -> Optional[Memory]:
        """根据ID获取记忆"""
        return self.memories.get(memory_id)
    
    def update_memory_importance(self, memory_id: str, importance: float):
        """更新记忆重要性"""
        if memory_id in self.memories:
            self.memories[memory_id].importance = importance

class KnowledgeGraph:
    """知识图谱"""
    
    def __init__(self):
        self.facts: Dict[str, Fact] = {}
        self.entity_relations: Dict[str, List[str]] = defaultdict(list)
        self.relation_facts: Dict[str, List[str]] = defaultdict(list)
    
    def add_fact(self, subject: str, predicate: str, obj: str, 
                confidence: float = 1.0, source: str = "user") -> str:
        """添加事实"""
        fact_id = hashlib.md5(f"{subject}_{predicate}_{obj}".encode()).hexdigest()
        
        fact = Fact(
            subject=subject,
            predicate=predicate,
            object=obj,
            confidence=confidence,
            source=source,
            timestamp=time.time()
        )
        
        self.facts[fact_id] = fact
        self.entity_relations[subject].append(fact_id)
        self.entity_relations[obj].append(fact_id)
        self.relation_facts[predicate].append(fact_id)
        
        return fact_id
    
    def query_facts(self, subject: str = None, predicate: str = None, 
                   obj: str = None) -> List[Fact]:
        """查询事实"""
        results = []
        
        for fact in self.facts.values():
            if (subject is None or fact.subject == subject) and \
               (predicate is None or fact.predicate == predicate) and \
               (obj is None or fact.object == obj):
                results.append(fact)
        
        return results
    
    def get_related_entities(self, entity: str, max_depth: int = 2) -> List[str]:
        """获取相关实体"""
        visited = set()
        queue = [(entity, 0)]
        related_entities = []
        
        while queue:
            current_entity, depth = queue.pop(0)
            
            if current_entity in visited or depth > max_depth:
                continue
                
            visited.add(current_entity)
            if depth > 0:  # 不包括起始实体
                related_entities.append(current_entity)
            
            # 获取相关事实
            for fact_id in self.entity_relations[current_entity]:
                fact = self.facts[fact_id]
                
                # 添加相关实体到队列
                if fact.subject != current_entity:
                    queue.append((fact.subject, depth + 1))
                if fact.object != current_entity:
                    queue.append((fact.object, depth + 1))
        
        return related_entities

class LogicalReasoner:
    """逻辑推理器"""
    
    def __init__(self, knowledge_graph: KnowledgeGraph):
        self.kg = knowledge_graph
        self.inference_rules = []
        self._setup_basic_rules()
    
    def _setup_basic_rules(self):
        """设置基本推理规则"""
        # 传递性规则
        self.inference_rules.append({
            'name': 'transitivity',
            'pattern': [('X', 'is_a', 'Y'), ('Y', 'is_a', 'Z')],
            'conclusion': ('X', 'is_a', 'Z'),
            'confidence_func': lambda c1, c2: min(c1, c2) * 0.9
        })
        
        # 对称性规则
        self.inference_rules.append({
            'name': 'symmetry',
            'pattern': [('X', 'similar_to', 'Y')],
            'conclusion': ('Y', 'similar_to', 'X'),
            'confidence_func': lambda c1: c1 * 0.95
        })
    
    def forward_chaining(self, max_iterations: int = 10) -> List[Fact]:
        """前向链式推理"""
        new_facts = []
        
        for iteration in range(max_iterations):
            iteration_facts = []
            
            for rule in self.inference_rules:
                rule_facts = self._apply_rule(rule)
                iteration_facts.extend(rule_facts)
            
            if not iteration_facts:
                break  # 没有新事实产生
            
            new_facts.extend(iteration_facts)
        
        return new_facts
    
    def _apply_rule(self, rule: Dict[str, Any]) -> List[Fact]:
        """应用推理规则"""
        new_facts = []
        pattern = rule['pattern']
        conclusion_template = rule['conclusion']
        confidence_func = rule['confidence_func']
        
        if len(pattern) == 1:
            # 单前提规则
            premise = pattern[0]
            matching_facts = self.kg.query_facts(
                subject=premise[0] if premise[0] != 'X' and premise[0] != 'Y' else None,
                predicate=premise[1],
                obj=premise[2] if premise[2] != 'X' and premise[2] != 'Y' else None
            )
            
            for fact in matching_facts:
                # 生成结论
                conclusion_subject = fact.subject if conclusion_template[0] == 'X' else fact.object
                conclusion_object = fact.object if conclusion_template[2] == 'Y' else fact.subject
                
                # 检查是否已存在
                existing_facts = self.kg.query_facts(
                    subject=conclusion_subject,
                    predicate=conclusion_template[1],
                    obj=conclusion_object
                )
                
                if not existing_facts:
                    new_confidence = confidence_func(fact.confidence)
                    fact_id = self.kg.add_fact(
                        conclusion_subject,
                        conclusion_template[1],
                        conclusion_object,
                        new_confidence,
                        f"inferred_by_{rule['name']}"
                    )
                    new_facts.append(self.kg.facts[fact_id])
        
        elif len(pattern) == 2:
            # 双前提规则（如传递性）
            premise1, premise2 = pattern
            
            # 查找匹配的事实对
            facts1 = self.kg.query_facts(predicate=premise1[1])
            facts2 = self.kg.query_facts(predicate=premise2[1])
            
            for f1 in facts1:
                for f2 in facts2:
                    if f1.object == f2.subject:  # Y匹配
                        # 生成结论
                        conclusion_subject = f1.subject
                        conclusion_object = f2.object
                        
                        # 检查是否已存在
                        existing_facts = self.kg.query_facts(
                            subject=conclusion_subject,
                            predicate=conclusion_template[1],
                            obj=conclusion_object
                        )
                        
                        if not existing_facts:
                            new_confidence = confidence_func(f1.confidence, f2.confidence)
                            fact_id = self.kg.add_fact(
                                conclusion_subject,
                                conclusion_template[1],
                                conclusion_object,
                                new_confidence,
                                f"inferred_by_{rule['name']}"
                            )
                            new_facts.append(self.kg.facts[fact_id])
        
        return new_facts

class MemoryReasoningSystem:
    """记忆推理系统"""
    
    def __init__(self, embedding_dim: int = 768):
        self.memory_store = VectorMemoryStore(embedding_dim)
        self.knowledge_graph = KnowledgeGraph()
        self.reasoner = LogicalReasoner(self.knowledge_graph)
        self.working_memory = []
        self.reasoning_history = []
    
    def learn_from_text(self, text: str, extract_facts: bool = True):
        """从文本中学习"""
        # 存储为记忆
        memory_id = self.memory_store.store_memory(
            content=text,
            memory_type="semantic",
            importance=1.0
        )
        
        if extract_facts:
            # 简单的事实抽取（实际应用中会使用NLP技术）
            facts = self._extract_facts_from_text(text)
            for subject, predicate, obj in facts:
                self.knowledge_graph.add_fact(subject, predicate, obj, source=memory_id)
    
    def _extract_facts_from_text(self, text: str) -> List[Tuple[str, str, str]]:
        """从文本中抽取事实（简化版本）"""
        facts = []
        
        # 简单的模式匹配
        if "is a" in text.lower():
            parts = text.lower().split("is a")
            if len(parts) == 2:
                subject = parts[0].strip()
                obj = parts[1].strip()
                facts.append((subject, "is_a", obj))
        
        if "similar to" in text.lower():
            parts = text.lower().split("similar to")
            if len(parts) == 2:
                subject = parts[0].strip()
                obj = parts[1].strip()
                facts.append((subject, "similar_to", obj))
        
        return facts
    
    def answer_question(self, question: str) -> Dict[str, Any]:
        """回答问题"""
        start_time = time.time()
        
        # 检索相关记忆
        relevant_memories = self.memory_store.retrieve_memories(question, top_k=5)
        
        # 查询知识图谱
        # 简单的关键词提取
        keywords = question.lower().split()
        relevant_facts = []
        
        for keyword in keywords:
            facts = self.knowledge_graph.query_facts(subject=keyword)
            facts.extend(self.knowledge_graph.query_facts(obj=keyword))
            relevant_facts.extend(facts)
        
        # 执行推理
        inferred_facts = self.reasoner.forward_chaining()
        
        # 构建答案
        answer = {
            "question": question,
            "relevant_memories": [
                {
                    "content": mem.content,
                    "similarity": float(sim),
                    "type": mem.memory_type
                }
                for mem, sim in relevant_memories
            ],
            "relevant_facts": [
                {
                    "subject": fact.subject,
                    "predicate": fact.predicate,
                    "object": fact.object,
                    "confidence": fact.confidence
                }
                for fact in relevant_facts[:5]  # 限制数量
            ],
            "inferred_facts": [
                {
                    "subject": fact.subject,
                    "predicate": fact.predicate,
                    "object": fact.object,
                    "confidence": fact.confidence,
                    "source": fact.source
                }
                for fact in inferred_facts[:3]  # 限制数量
            ],
            "reasoning_time": time.time() - start_time
        }
        
        # 记录推理历史
        self.reasoning_history.append(answer)
        
        return answer
    
    def get_system_stats(self) -> Dict[str, Any]:
        """获取系统统计信息"""
        return {
            "total_memories": len(self.memory_store.memories),
            "total_facts": len(self.knowledge_graph.facts),
            "reasoning_sessions": len(self.reasoning_history),
            "memory_types": {
                memory_type: sum(1 for m in self.memory_store.memories.values() 
                               if m.memory_type == memory_type)
                for memory_type in ["episodic", "semantic", "procedural"]
            }
        }

# 示例使用
def main():
    """主函数演示"""
    print("AI Agent记忆推理系统示例")
    print("=" * 50)
    
    # 创建记忆推理系统
    mrs = MemoryReasoningSystem()
    
    # 学习一些知识
    knowledge_texts = [
        "Python is a programming language",
        "Machine learning is a subset of artificial intelligence",
        "Neural networks are similar to biological neurons",
        "Deep learning uses neural networks",
        "AI agents can learn from experience"
    ]
    
    print("学习知识...")
    for text in knowledge_texts:
        mrs.learn_from_text(text)
        print(f"  学习: {text}")
    
    # 添加一些直接的事实
    mrs.knowledge_graph.add_fact("Python", "used_for", "AI development", 0.9)
    mrs.knowledge_graph.add_fact("TensorFlow", "is_a", "machine learning framework", 0.95)
    mrs.knowledge_graph.add_fact("PyTorch", "similar_to", "TensorFlow", 0.8)
    
    print(f"\n系统统计: {mrs.get_system_stats()}")
    
    # 回答问题
    questions = [
        "What is Python?",
        "Tell me about machine learning",
        "What are neural networks similar to?",
        "What frameworks are available for AI?"
    ]
    
    print("\n回答问题:")
    print("-" * 30)
    
    for question in questions:
        print(f"\n问题: {question}")
        answer = mrs.answer_question(question)
        
        print("相关记忆:")
        for mem in answer["relevant_memories"][:2]:
            print(f"  - {mem['content']} (相似度: {mem['similarity']:.3f})")
        
        print("相关事实:")
        for fact in answer["relevant_facts"][:2]:
            print(f"  - {fact['subject']} {fact['predicate']} {fact['object']} (置信度: {fact['confidence']:.2f})")
        
        if answer["inferred_facts"]:
            print("推理得出的事实:")
            for fact in answer["inferred_facts"]:
                print(f"  - {fact['subject']} {fact['predicate']} {fact['object']} (推理来源: {fact['source']})")
        
        print(f"推理时间: {answer['reasoning_time']:.4f}秒")

if __name__ == "__main__":
    main()
