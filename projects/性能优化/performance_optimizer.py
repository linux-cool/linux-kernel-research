#!/usr/bin/env python3
"""
AI Agent性能优化工具
实现性能监控、资源管理、缓存优化等功能
"""

import time
import psutil
import threading
import asyncio
from typing import Dict, List, Any, Optional, Callable
from dataclasses import dataclass, field
from collections import deque, defaultdict
from enum import Enum
import json
import hashlib

class MetricType(Enum):
    """指标类型"""
    RESPONSE_TIME = "response_time"
    THROUGHPUT = "throughput"
    CPU_USAGE = "cpu_usage"
    MEMORY_USAGE = "memory_usage"
    CACHE_HIT_RATE = "cache_hit_rate"
    ERROR_RATE = "error_rate"

@dataclass
class PerformanceMetric:
    """性能指标"""
    metric_type: MetricType
    value: float
    timestamp: float
    tags: Dict[str, str] = field(default_factory=dict)

@dataclass
class ResourceUsage:
    """资源使用情况"""
    cpu_percent: float
    memory_percent: float
    memory_used_mb: float
    disk_io_read: float
    disk_io_write: float
    network_sent: float
    network_recv: float
    timestamp: float

class PerformanceMonitor:
    """性能监控器"""
    
    def __init__(self, max_history: int = 1000):
        self.metrics: Dict[MetricType, deque] = {
            metric_type: deque(maxlen=max_history)
            for metric_type in MetricType
        }
        self.resource_history: deque = deque(maxlen=max_history)
        self.monitoring = False
        self.monitor_thread = None
        self.callbacks: Dict[MetricType, List[Callable]] = defaultdict(list)
    
    def start_monitoring(self, interval: float = 1.0):
        """开始监控"""
        if self.monitoring:
            return
        
        self.monitoring = True
        self.monitor_thread = threading.Thread(
            target=self._monitor_loop,
            args=(interval,),
            daemon=True
        )
        self.monitor_thread.start()
        print("性能监控已启动")
    
    def stop_monitoring(self):
        """停止监控"""
        self.monitoring = False
        if self.monitor_thread:
            self.monitor_thread.join()
        print("性能监控已停止")
    
    def _monitor_loop(self, interval: float):
        """监控循环"""
        while self.monitoring:
            try:
                # 收集系统资源使用情况
                cpu_percent = psutil.cpu_percent(interval=0.1)
                memory = psutil.virtual_memory()
                disk_io = psutil.disk_io_counters()
                network_io = psutil.net_io_counters()
                
                resource_usage = ResourceUsage(
                    cpu_percent=cpu_percent,
                    memory_percent=memory.percent,
                    memory_used_mb=memory.used / 1024 / 1024,
                    disk_io_read=disk_io.read_bytes if disk_io else 0,
                    disk_io_write=disk_io.write_bytes if disk_io else 0,
                    network_sent=network_io.bytes_sent if network_io else 0,
                    network_recv=network_io.bytes_recv if network_io else 0,
                    timestamp=time.time()
                )
                
                self.resource_history.append(resource_usage)
                
                # 记录系统指标
                self.record_metric(MetricType.CPU_USAGE, cpu_percent)
                self.record_metric(MetricType.MEMORY_USAGE, memory.percent)
                
                time.sleep(interval)
                
            except Exception as e:
                print(f"监控错误: {e}")
                time.sleep(interval)
    
    def record_metric(self, metric_type: MetricType, value: float, tags: Dict[str, str] = None):
        """记录指标"""
        metric = PerformanceMetric(
            metric_type=metric_type,
            value=value,
            timestamp=time.time(),
            tags=tags or {}
        )
        
        self.metrics[metric_type].append(metric)
        
        # 触发回调
        for callback in self.callbacks[metric_type]:
            try:
                callback(metric)
            except Exception as e:
                print(f"回调执行错误: {e}")
    
    def add_callback(self, metric_type: MetricType, callback: Callable):
        """添加指标回调"""
        self.callbacks[metric_type].append(callback)
    
    def get_metric_stats(self, metric_type: MetricType, time_window: float = 300) -> Dict[str, float]:
        """获取指标统计"""
        current_time = time.time()
        recent_metrics = [
            m for m in self.metrics[metric_type]
            if current_time - m.timestamp <= time_window
        ]
        
        if not recent_metrics:
            return {"count": 0}
        
        values = [m.value for m in recent_metrics]
        
        return {
            "count": len(values),
            "min": min(values),
            "max": max(values),
            "avg": sum(values) / len(values),
            "latest": values[-1] if values else 0
        }
    
    def get_system_health(self) -> Dict[str, Any]:
        """获取系统健康状况"""
        if not self.resource_history:
            return {"status": "no_data"}
        
        latest = self.resource_history[-1]
        
        # 健康评分
        health_score = 100
        warnings = []
        
        if latest.cpu_percent > 80:
            health_score -= 20
            warnings.append("CPU使用率过高")
        
        if latest.memory_percent > 85:
            health_score -= 25
            warnings.append("内存使用率过高")
        
        # 确定健康状态
        if health_score >= 80:
            status = "healthy"
        elif health_score >= 60:
            status = "warning"
        else:
            status = "critical"
        
        return {
            "status": status,
            "health_score": health_score,
            "warnings": warnings,
            "resource_usage": {
                "cpu_percent": latest.cpu_percent,
                "memory_percent": latest.memory_percent,
                "memory_used_mb": latest.memory_used_mb
            }
        }

class CacheManager:
    """缓存管理器"""
    
    def __init__(self, max_size: int = 1000, ttl: float = 3600):
        self.max_size = max_size
        self.ttl = ttl
        self.cache: Dict[str, Dict[str, Any]] = {}
        self.access_times: Dict[str, float] = {}
        self.hit_count = 0
        self.miss_count = 0
        self._lock = threading.RLock()
    
    def get(self, key: str) -> Optional[Any]:
        """获取缓存值"""
        with self._lock:
            if key not in self.cache:
                self.miss_count += 1
                return None
            
            cache_entry = self.cache[key]
            
            # 检查TTL
            if time.time() - cache_entry["timestamp"] > self.ttl:
                del self.cache[key]
                del self.access_times[key]
                self.miss_count += 1
                return None
            
            # 更新访问时间
            self.access_times[key] = time.time()
            self.hit_count += 1
            
            return cache_entry["value"]
    
    def set(self, key: str, value: Any):
        """设置缓存值"""
        with self._lock:
            current_time = time.time()
            
            # 如果缓存已满，移除最久未访问的项
            if len(self.cache) >= self.max_size and key not in self.cache:
                self._evict_lru()
            
            self.cache[key] = {
                "value": value,
                "timestamp": current_time
            }
            self.access_times[key] = current_time
    
    def _evict_lru(self):
        """移除最久未访问的项"""
        if not self.access_times:
            return
        
        lru_key = min(self.access_times.keys(), key=lambda k: self.access_times[k])
        del self.cache[lru_key]
        del self.access_times[lru_key]
    
    def clear(self):
        """清空缓存"""
        with self._lock:
            self.cache.clear()
            self.access_times.clear()
            self.hit_count = 0
            self.miss_count = 0
    
    def get_stats(self) -> Dict[str, Any]:
        """获取缓存统计"""
        total_requests = self.hit_count + self.miss_count
        hit_rate = self.hit_count / total_requests if total_requests > 0 else 0
        
        return {
            "size": len(self.cache),
            "max_size": self.max_size,
            "hit_count": self.hit_count,
            "miss_count": self.miss_count,
            "hit_rate": hit_rate,
            "utilization": len(self.cache) / self.max_size
        }

class ResourceManager:
    """资源管理器"""
    
    def __init__(self):
        self.resource_pools: Dict[str, asyncio.Semaphore] = {}
        self.resource_usage: Dict[str, int] = {}
        self.resource_limits: Dict[str, int] = {}
    
    def create_resource_pool(self, resource_name: str, max_concurrent: int):
        """创建资源池"""
        self.resource_pools[resource_name] = asyncio.Semaphore(max_concurrent)
        self.resource_usage[resource_name] = 0
        self.resource_limits[resource_name] = max_concurrent
    
    async def acquire_resource(self, resource_name: str) -> bool:
        """获取资源"""
        if resource_name not in self.resource_pools:
            return False
        
        semaphore = self.resource_pools[resource_name]
        acquired = await semaphore.acquire()
        
        if acquired:
            self.resource_usage[resource_name] += 1
        
        return acquired
    
    def release_resource(self, resource_name: str):
        """释放资源"""
        if resource_name in self.resource_pools:
            self.resource_pools[resource_name].release()
            self.resource_usage[resource_name] = max(0, self.resource_usage[resource_name] - 1)
    
    def get_resource_stats(self) -> Dict[str, Dict[str, Any]]:
        """获取资源统计"""
        stats = {}
        
        for resource_name in self.resource_pools:
            stats[resource_name] = {
                "current_usage": self.resource_usage[resource_name],
                "max_limit": self.resource_limits[resource_name],
                "utilization": self.resource_usage[resource_name] / self.resource_limits[resource_name],
                "available": self.resource_limits[resource_name] - self.resource_usage[resource_name]
            }
        
        return stats

class PerformanceOptimizer:
    """性能优化器"""
    
    def __init__(self):
        self.monitor = PerformanceMonitor()
        self.cache = CacheManager()
        self.resource_manager = ResourceManager()
        self.optimization_rules: List[Dict[str, Any]] = []
        self.auto_optimization = False
        
        # 设置默认优化规则
        self._setup_default_rules()
        
        # 设置默认资源池
        self._setup_default_resources()
    
    def _setup_default_rules(self):
        """设置默认优化规则"""
        self.optimization_rules = [
            {
                "name": "高CPU使用率优化",
                "condition": lambda health: health.get("resource_usage", {}).get("cpu_percent", 0) > 80,
                "action": self._optimize_cpu_usage,
                "priority": 1
            },
            {
                "name": "高内存使用率优化",
                "condition": lambda health: health.get("resource_usage", {}).get("memory_percent", 0) > 85,
                "action": self._optimize_memory_usage,
                "priority": 1
            },
            {
                "name": "缓存命中率优化",
                "condition": lambda stats: stats.get("hit_rate", 1) < 0.7,
                "action": self._optimize_cache,
                "priority": 2
            }
        ]
    
    def _setup_default_resources(self):
        """设置默认资源池"""
        self.resource_manager.create_resource_pool("api_calls", 10)
        self.resource_manager.create_resource_pool("database_connections", 5)
        self.resource_manager.create_resource_pool("file_operations", 3)
    
    def start_optimization(self, auto_optimize: bool = True):
        """启动性能优化"""
        self.auto_optimization = auto_optimize
        self.monitor.start_monitoring()
        
        if auto_optimize:
            # 添加自动优化回调
            self.monitor.add_callback(MetricType.CPU_USAGE, self._check_optimization_triggers)
            self.monitor.add_callback(MetricType.MEMORY_USAGE, self._check_optimization_triggers)
        
        print("性能优化器已启动")
    
    def stop_optimization(self):
        """停止性能优化"""
        self.auto_optimization = False
        self.monitor.stop_monitoring()
        print("性能优化器已停止")
    
    def _check_optimization_triggers(self, metric: PerformanceMetric):
        """检查优化触发条件"""
        if not self.auto_optimization:
            return
        
        health = self.monitor.get_system_health()
        
        # 按优先级排序规则
        sorted_rules = sorted(self.optimization_rules, key=lambda r: r["priority"])
        
        for rule in sorted_rules:
            try:
                if rule["condition"](health):
                    print(f"触发优化规则: {rule['name']}")
                    rule["action"]()
                    break  # 一次只执行一个优化规则
            except Exception as e:
                print(f"优化规则执行错误 {rule['name']}: {e}")
    
    def _optimize_cpu_usage(self):
        """优化CPU使用率"""
        print("执行CPU优化策略...")
        
        # 减少并发任务数
        for resource_name in ["api_calls", "database_connections"]:
            if resource_name in self.resource_manager.resource_limits:
                current_limit = self.resource_manager.resource_limits[resource_name]
                new_limit = max(1, int(current_limit * 0.8))
                self.resource_manager.create_resource_pool(resource_name, new_limit)
                print(f"  减少 {resource_name} 并发限制: {current_limit} -> {new_limit}")
    
    def _optimize_memory_usage(self):
        """优化内存使用率"""
        print("执行内存优化策略...")
        
        # 清理缓存
        cache_stats = self.cache.get_stats()
        if cache_stats["utilization"] > 0.8:
            # 清理一半的缓存
            items_to_remove = len(self.cache.cache) // 2
            keys_to_remove = list(self.cache.cache.keys())[:items_to_remove]
            
            for key in keys_to_remove:
                if key in self.cache.cache:
                    del self.cache.cache[key]
                if key in self.cache.access_times:
                    del self.cache.access_times[key]
            
            print(f"  清理缓存项: {items_to_remove} 个")
    
    def _optimize_cache(self):
        """优化缓存策略"""
        print("执行缓存优化策略...")
        
        # 增加缓存大小
        current_size = self.cache.max_size
        new_size = min(current_size * 2, 5000)  # 最大不超过5000
        self.cache.max_size = new_size
        
        print(f"  增加缓存大小: {current_size} -> {new_size}")
    
    async def cached_operation(self, operation_id: str, operation_func: Callable, *args, **kwargs):
        """缓存操作结果"""
        # 生成缓存键
        cache_key = self._generate_cache_key(operation_id, args, kwargs)
        
        # 尝试从缓存获取
        cached_result = self.cache.get(cache_key)
        if cached_result is not None:
            return cached_result
        
        # 执行操作
        start_time = time.time()
        try:
            result = await operation_func(*args, **kwargs) if asyncio.iscoroutinefunction(operation_func) else operation_func(*args, **kwargs)
            
            # 缓存结果
            self.cache.set(cache_key, result)
            
            # 记录性能指标
            execution_time = time.time() - start_time
            self.monitor.record_metric(MetricType.RESPONSE_TIME, execution_time, {"operation": operation_id})
            
            return result
            
        except Exception as e:
            # 记录错误率
            self.monitor.record_metric(MetricType.ERROR_RATE, 1, {"operation": operation_id})
            raise e
    
    def _generate_cache_key(self, operation_id: str, args: tuple, kwargs: dict) -> str:
        """生成缓存键"""
        key_data = {
            "operation_id": operation_id,
            "args": str(args),
            "kwargs": str(sorted(kwargs.items()))
        }
        key_string = json.dumps(key_data, sort_keys=True)
        return hashlib.md5(key_string.encode()).hexdigest()
    
    def get_performance_report(self) -> Dict[str, Any]:
        """获取性能报告"""
        return {
            "system_health": self.monitor.get_system_health(),
            "cache_stats": self.cache.get_stats(),
            "resource_stats": self.resource_manager.get_resource_stats(),
            "metrics": {
                metric_type.value: self.monitor.get_metric_stats(metric_type)
                for metric_type in MetricType
            },
            "optimization_status": {
                "auto_optimization": self.auto_optimization,
                "rules_count": len(self.optimization_rules)
            }
        }

# 示例使用
async def example_operation(data: str, delay: float = 1.0) -> str:
    """示例操作函数"""
    await asyncio.sleep(delay)
    return f"处理结果: {data.upper()}"

async def main():
    """主函数演示"""
    print("AI Agent性能优化工具示例")
    print("=" * 50)
    
    # 创建性能优化器
    optimizer = PerformanceOptimizer()
    
    # 启动优化
    optimizer.start_optimization(auto_optimize=True)
    
    # 等待监控启动
    await asyncio.sleep(2)
    
    print("\n执行一些操作来测试性能监控...")
    
    # 测试缓存操作
    for i in range(5):
        result = await optimizer.cached_operation(
            "example_op",
            example_operation,
            f"数据{i}",
            delay=0.5
        )
        print(f"操作 {i}: {result}")
    
    # 重复执行相同操作（应该命中缓存）
    print("\n重复执行相同操作（测试缓存）...")
    for i in range(3):
        result = await optimizer.cached_operation(
            "example_op",
            example_operation,
            "数据0",  # 相同的数据，应该命中缓存
            delay=0.5
        )
        print(f"缓存操作 {i}: {result}")
    
    # 等待一些监控数据
    await asyncio.sleep(3)
    
    # 生成性能报告
    print(f"\n性能报告:")
    print("-" * 30)
    
    report = optimizer.get_performance_report()
    
    # 系统健康状况
    health = report["system_health"]
    print(f"系统状态: {health['status']}")
    print(f"健康评分: {health['health_score']}")
    if health.get("warnings"):
        print(f"警告: {', '.join(health['warnings'])}")
    
    # 缓存统计
    cache_stats = report["cache_stats"]
    print(f"\n缓存统计:")
    print(f"  大小: {cache_stats['size']}/{cache_stats['max_size']}")
    print(f"  命中率: {cache_stats['hit_rate']:.2%}")
    print(f"  利用率: {cache_stats['utilization']:.2%}")
    
    # 资源统计
    resource_stats = report["resource_stats"]
    print(f"\n资源使用:")
    for resource_name, stats in resource_stats.items():
        print(f"  {resource_name}: {stats['current_usage']}/{stats['max_limit']} ({stats['utilization']:.2%})")
    
    # 性能指标
    metrics = report["metrics"]
    print(f"\n性能指标:")
    for metric_name, stats in metrics.items():
        if stats.get("count", 0) > 0:
            print(f"  {metric_name}: 平均={stats.get('avg', 0):.3f}, 最新={stats.get('latest', 0):.3f}")
    
    # 停止优化
    optimizer.stop_optimization()

if __name__ == "__main__":
    asyncio.run(main())
