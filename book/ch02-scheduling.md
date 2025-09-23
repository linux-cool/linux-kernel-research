# 第2章 进程调度与同步机制研究（projects/进程调度）

本章以 Linux 6.6 LTS 为基线，系统阐述 CFS/EEVDF、RT/DL 调度，负载均衡，多核扩展性，以及同步原语与 RCU。理论叙述中穿插来自仓库 projects/进程调度/ 的简短代码片段；完整实现以仓库源码为准。

> 环境建议：可在 QEMU/KVM 或物理机上运行；建议启用 ftrace/perf；需要 root 以打开 /sys/kernel/debug/ 接口与 /proc 观测；针对 RT/DL 章节可使用 `chrt`、`sched_tool` 进行实验。

## 2.0 给新手的快速入门教程（5–15分钟）

学习目标
- 认识调度类（fair/rt/deadline）与 CFS 的基本概念
- 会加载本章的 CFS 观测模块，读取 /proc/cfs_status 并理解字段
- 会用 ftrace 打开几个常用调度事件，抓一次“切换—唤醒—迁移”的最小轨迹

前置准备
- 已具备 sudo/root；建议在非生产环境
- 工具建议：`taskset`、`chrt`（在 util-linux 包中）、tracefs（/sys/kernel/tracing）

步骤一：编译并加载 CFS 观测模块
```bash
cd projects/进程调度
make -C /lib/modules/$(uname -r)/build M=$(pwd) modules
ls -l *.ko
sudo insmod cfs_analysis.ko || sudo insmod ./$(ls *.ko | head -n1)
dmesg | tail -n 20
```

步骤二：读取 /proc/cfs_status 并理解字段
```bash
cat /proc/cfs_status | sed -n '1,200p'
```
输出解读（面向入门者）
- CPU N: 这一段是第 N 号 CPU 的运行队列信息（rq）
- Running tasks / Load weight: 该 CPU 上 CFS 任务数量与权重；任务越多或权重越大，竞争越激烈
- Min vruntime: 红黑树最左节点（“理应最先被运行”的任务）的基准；值越小说明“应当被调度”的任务更“紧迫”
- Current: 当前正在 CPU 上运行的任务及其 vruntime（理解为“已经吃到的 CPU 时间”的一种度量）

步骤三：制造一点负载再观察
```bash
# 启动两个 CPU 密集的小负载（按需调小秒数）
(yes >/dev/null &) ; (yes >/dev/null &)
sleep 1
# 再看一次 /proc/cfs_status（nr_running 应上升）
head -n 40 /proc/cfs_status
# 清理后台任务
pkill -f '^yes$' || true
```

步骤四：用 ftrace 捕获一次“调度切换/唤醒/迁移”
```bash
# 挂载 tracefs（若已挂载可忽略）
sudo mount -t tracefs nodev /sys/kernel/tracing 2>/dev/null || true
cd /sys/kernel/tracing
echo 0 | sudo tee tracing_on >/dev/null
echo nop | sudo tee current_tracer >/dev/null
for e in sched_switch sched_wakeup sched_wakeup_new sched_migrate_task; do
  echo 1 | sudo tee events/sched/$e/enable >/dev/null
done
echo 1 | sudo tee tracing_on >/dev/null
# 制造一次负载和迁移
( taskset -c 0 yes >/dev/null & ); sleep 1; ( taskset -c 1 yes >/dev/null & ); sleep 1
# 关闭并查看
echo 0 | sudo tee tracing_on >/dev/null
sudo head trace
pkill -f '^yes$' || true
```

常见错误与排错
- invalid module format → 构建用头文件与当前内核不一致
- /sys/kernel/tracing 不存在 → 内核未启用或未挂载 tracefs，尝试上述 mount 命令
- 无法使用 chrt → 缺少 CAP_SYS_NICE（请用 sudo）

学习检查点
- 你能解释 /proc/cfs_status 里的 nr_running、load.weight、min_vruntime
- 你能打开 ftrace 的 sched_* 事件并抓到一次“唤醒—切换—迁移”的最小样本
- 你知道如何用 yes 与 taskset 快速制造 CPU 竞争与迁移

---
## 2.1 概览与调度架构
### 调度目标与策略
- 调度目标：在吞吐、响应、尾延迟与公平性之间取得平衡；支持多核、cgroup、异构硬件。
- 调度类：`stop`、`deadline`、`rt`、`fair`（CFS/EEVDF）、`idle`；按优先级从高到低匹配。
- 关键数据结构：`struct rq`（每 CPU 运行队列）、`struct cfs_rq`、`struct sched_entity`（SE）。

### 调度类层次结构详解
```bash
# 查看系统调度类信息
cat /proc/sched_debug | grep -A5 -B5 "sched_class" 2>/dev/null | head -20 || echo "需要启用CONFIG_SCHED_DEBUG"
# 查看调度器统计信息
cat /proc/schedstat 2>/dev/null | head -10 || echo "调度统计未启用"
# 查看运行时调度参数
cat /proc/sys/kernel/sched_* 2>/dev/null | grep -E "(latency|granularity)" | head -5
```

### 核心数据结构分析
```c
// 摘自 projects/进程调度/cfs_analysis.c - 调度实体结构
struct sched_entity {
    struct load_weight  load;           /* 负载权重 */
    struct rb_node      run_node;       /* 红黑树节点 */
    u64                 vruntime;       /* 虚拟运行时间 */
    u64                 exec_start;     /* 开始执行时间 */
    u64                 sum_exec_runtime; /* 总执行时间 */
    u64                 prev_sum_exec_runtime; /* 前期执行时间 */
    struct sched_entity *parent;        /* 父实体（组调度）*/
    struct cfs_rq       *cfs_rq;        /* 所属CFS运行队列 */
};

// CFS运行队列结构
struct cfs_rq {
    struct load_weight load;            /* 队列负载 */
    struct rb_root_cached tasks_timeline; /* 任务红黑树 */
    struct rb_node *rb_leftmost;        /* 最左节点（下一个运行任务）*/
    u64 min_vruntime;                   /* 最小虚拟运行时间 */
    int nr_running;                     /* 运行任务数 */
    u64 exec_clock;                     /* 执行时钟 */
    u64 avg_vruntime;                   /* 平均虚拟运行时间 */
};
```

### 调度域与拓扑结构
```bash
# 查看CPU调度域信息
cat /proc/sys/kernel/sched_domain/* 2>/dev/null | head -20 || echo "调度域信息未启用"
# 查看CPU拓扑
cat /proc/cpuinfo | grep -E "(processor|physical id|core id)" | head -20
# 查看NUMA拓扑
numactl --hardware 2>/dev/null || echo "NUMA不可用"
```

---
## 2.2 CFS 与 EEVDF 原理
### CFS（完全公平调度器）核心机制
- CFS：基于红黑树按虚拟运行时间（vruntime）选择最左节点；粒度/延迟参数通过 sysctl 控制（`sched_latency`、`sched_min_granularity`）。
- EEVDF：基于虚拟截止期的公平调度（Earliest Eligible Virtual Deadline First），在交互延迟与公平性上改进选择策略；Linux 近期演进逐步引入。
- cgroup v2：通过权重/份额实现层级公平；NUMA/能效调度与 CPU 亲和影响负载分布。

### vruntime计算与补偿机制
```c
// 摘自 projects/进程调度/cfs_analysis.c - vruntime计算
static void update_vruntime_analysis(struct sched_entity *se)
{
    u64 now = sched_clock();
    u64 delta = now - se->exec_start;
    u64 weight_delta;
    
    // 根据权重计算虚拟时间
    weight_delta = div64_u64(delta * NICE_0_LOAD, se->load.weight);
    se->vruntime += weight_delta;
    
    printk(KERN_INFO "Task %s: real_time=%llu vruntime=%llu weight=%lu\n",
           current->comm, delta, weight_delta, se->load.weight);
}
```

### CFS关键参数调优
```bash
# 查看当前CFS参数
cat /proc/sys/kernel/sched_latency_ns
cat /proc/sys/kernel/sched_min_granularity_ns
cat /proc/sys/kernel/sched_wakeup_granularity_ns
# 查看调度统计
cat /proc/schedstat 2>/dev/null | grep -E "(cpu|domain)" | head -10
```

### EEVDF算法详解
EEVDF通过虚拟截止期来改善交互式任务的响应性：
```c
// 摘自 projects/进程调度/eevdf_analysis.c
static u64 eevdf_virtual_deadline(struct sched_entity *se)
{
    u64 elig_time = se->start_time;  //  eligible time
    u64 slice = se->slice;           //  allocated time slice
    u64 weight = se->load.weight;    //  weight
    
    // 计算虚拟截止期
    return elig_time + div64_u64(slice * NICE_0_LOAD, weight);
}
```

### 红黑树操作分析
```c
// 摘自 projects/进程调度/cfs_analysis.c - 红黑树遍历
static void analyze_cfs_rb_tree(struct cfs_rq *cfs_rq)
{
    struct rb_node *node;
    struct sched_entity *se;
    int count = 0;
    
    printk(KERN_INFO "=== CFS Red-Black Tree Analysis ===\n");
    
    // 遍历红黑树（中序遍历，按vruntime排序）
    for (node = rb_first_cached(&cfs_rq->tasks_timeline); node; node = rb_next(node)) {
        se = rb_entry(node, struct sched_entity, run_node);
        printk(KERN_INFO "  [%d] %s vruntime=%llu weight=%lu\n",
               ++count, se->my_q->pid, se->vruntime, se->load.weight);
    }
    
    printk(KERN_INFO "Total tasks in tree: %d\n", count);
}
```

代码片段（观测每 CPU CFS 队列与关键指标）：
```c
// 摘自 projects/进程调度/cfs_analysis.c
for_each_online_cpu(cpu) {
    struct rq *rq = cpu_rq(cpu);
    struct cfs_rq *c = &rq->cfs;
    printk(KERN_INFO, "CPU %d nr=%d min_vr=%llu\n", cpu, c->nr_running, c->min_vruntime);
}
```

---
## 2.3 权重与优先级（nice→weight）
### nice值与权重转换机制
- nice 值影响 `sched_entity.load.weight`，进而影响 vruntime 增速（权重大者 vruntime 增速慢，获得更多 CPU 时间）。
- CFS 的权重表非线性设计，近似每降低 1 个 nice 提供约 10% 份额提升。
- 每 CPU 负载统计：`cpu_load[]`、PELT（per-entity load tracking）与窗口衰减。

### 权重计算与PELT分析
```c
// 摘自 projects/进程调度/weight_calculator.c
static const int prio_to_weight[40] = {
 /* -20 */ 88761, 71755, 56483, 46273, 36291,
 /* -15 */ 29154, 23254, 18705, 14949, 11916,
 /* -10 */ 9548,  7620,  6100,  4904,  3906,
 /*  -5 */ 3121,  2501,  1991,  1586,  1277,
 /*   0 */ 1024,  820,   655,   526,   423,
 /*   5 */ 335,   272,   215,   172,   137,
 /*  10 */ 110,   87,    70,    56,    45,
 /*  15 */ 36,    29,    23,    18,    15,
};

static void analyze_weight_impact(struct sched_entity *se, int nice)
{
    int idx = nice + 20;  // nice值范围：-20到19
    unsigned long weight = prio_to_weight[idx];
    
    printk(KERN_INFO "nice=%d weight=%lu (ratio=%lu%%)\n",
           nice, weight, (weight * 100) / prio_to_weight[20]);
}

// PELT负载追踪分析
static void analyze_pelt_tracking(struct sched_entity *se)
{
    struct sched_avg *sa = &se->avg;
    
    printk(KERN_INFO "PELT tracking for %s:\n", current->comm);
    printk(KERN_INFO "  load_avg=%lu util_avg=%lu\n",
           sa->load_avg, sa->util_avg);
    printk(KERN_INFO "  load_sum=%llu util_sum=%llu\n",
           sa->load_sum, sa->util_sum);
    printk(KERN_INFO "  period_contrib=%u\n", sa->period_contrib);
}
```

### 权重对调度的影响测试
```bash
# 创建不同nice值的任务并观察权重影响
for nice in -20 -10 0 10 19; do
    nice -n $nice bash -c 'while true; do :; done' &
done

# 查看进程权重信息
ps -eo pid,ni,pri,psr,comm | grep bash
# 查看调度实体权重
cat /proc/$(pgrep -f "nice.*bash")/sched 2>/dev/null | grep -E "(weight|load)" || echo "需要CONFIG_SCHED_DEBUG"
```

代码片段（遍历部分 CFS 任务的权重、vruntime）：
```c
// 摘自 projects/进程调度/cfs_analysis.c
for_each_process(task) {
    if (task->sched_class == &fair_sched_class) {
        printk(KERN_INFO, "PID=%d nice=%d w=%lu vr=%llu\n",
               task->pid, task_nice(task), task->se.load.weight, task->se.vruntime);
    }
}
```

---
## 2.4 负载均衡与调度域
### 调度域层次结构
- 调度域/组：按拓扑（NUMA 节点、LLC 共享域）分层；周期性平衡任务与迁移内核线程（`stop`/`balance`）。
- 指标：每 CPU 负载、rq 深度、迁移代价、cache 亲和；对任务唤醒与亲和（`sched_setaffinity`）敏感。

### 负载均衡算法分析
```c
// 摘自 projects/进程调度/load_balance_analyzer.c
static void analyze_load_balance(struct sched_domain *sd, int cpu)
{
    struct sched_group *sg;
    unsigned long group_load = 0, group_capacity = 0;
    
    printk(KERN_INFO "=== Load Balance Analysis for CPU %d ===\n", cpu);
    printk(KERN_INFO "Domain: %s\n", sd->name);
    
    // 遍历调度组
    for_each_sched_group(sg, sd) {
        struct sg_lb_stats sgs;
        
        // 计算组负载统计
        update_sg_lb_stats(sg, &sgs);
        
        printk(KERN_INFO "Group %d: load=%lu capacity=%lu flags=0x%x\n",
               group_first_cpu(sg), sgs.avg_load, sgs.group_capacity, sg->sg_flags);
        
        group_load += sgs.avg_load;
        group_capacity += sgs.group_capacity;
    }
    
    printk(KERN_INFO "Domain total: load=%lu capacity=%lu imbalance=%ld\n",
           group_load, group_capacity, (long)group_load - (long)group_capacity);
}
```

### 负载计算与PELT
```c
// 摘自 projects/进程调度/cfs_analysis.c - 增强版负载计算
static void analyze_cpu_load_detailed(int cpu)
{
    struct rq *rq = cpu_rq(cpu);
    struct cfs_rq *cfs_rq = &rq->cfs;
    unsigned long load_avg = cfs_rq->rq_avg.load_avg;
    unsigned long util_avg = cfs_rq->rq_avg.util_avg;
    
    printk(KERN_INFO "CPU %d Load Analysis:\n", cpu);
    printk(KERN_INFO "  runnable_load_avg=%lu\n", cfs_rq->runnable_load_avg);
    printk(KERN_INFO "  load_avg=%lu util_avg=%lu\n", load_avg, util_avg);
    printk(KERN_INFO "  nr_running=%d h_nr_running=%d\n",
           cfs_rq->nr_running, cfs_rq->h_nr_running);
    
    // 分析不平衡度
    if (cpu > 0) {
        unsigned long prev_load = cpu_rq(cpu-1)->cfs.rq_avg.load_avg;
        long imbalance = (long)load_avg - (long)prev_load;
        printk(KERN_INFO "  imbalance with CPU%d: %ld\n", cpu-1, imbalance);
    }
}
```

### 调度域与拓扑感知
```bash
# 查看调度域层次结构
cat /proc/sys/kernel/sched_domain/cpu*/domain*/name 2>/dev/null | head -20
cat /proc/sys/kernel/sched_domain/cpu*/domain*/flags 2>/dev/null | head -20

# 查看NUMA调度域信息
numactl --hardware
lscpu | grep -E "(NUMA|Socket|Core)"

# 查看CPU缓存拓扑
ls /sys/devices/system/cpu/cpu*/cache/index*/ 2>/dev/null | head -10
```

### 负载均衡触发条件
```c
// 摘自 projects/进程调度/load_balance_tracer.c
static void trace_load_balance_trigger(struct rq *busiest, struct rq *target)
{
    unsigned long busiest_load = busiest->cfs.rq_avg.load_avg;
    unsigned long target_load = target->cfs.rq_avg.load_avg;
    unsigned long imbalance;
    
    // 计算不平衡度
    imbalance = (busiest_load * 100) / (busiest_load + target_load);
    
    if (imbalance > 125) {  // 不平衡度超过25%
        printk(KERN_INFO "Load balance triggered: CPU%d->CPU%d imbalance=%lu%%\n",
               cpu_of(busiest), cpu_of(target), imbalance - 100);
    }
}
```

代码片段（简要计算各 CPU 负载并估算不均衡）：
```c
// 摘自 projects/进程调度/cfs_analysis.c
unsigned long total=0, max=0, min=~0UL; int cmax=-1,cmin=-1;
for_each_online_cpu(cpu) {
    unsigned long l = cpu_rq_load_avg(cpu_rq(cpu));
    total+=l; if (l>max){max=l;cmax=cpu;} if (l<min){min=l;cmin=cpu;}
}
printf("avg=%lu max=%lu(CPU%d) min=%lu(CPU%d)\n", total/num_online_cpus(),max,cmax,min,cmin);
```

---
## 2.5 调度延迟与关键参数
- 延迟相关 sysctl：`sched_latency_ns`、`sched_min_granularity_ns`、`sched_wakeup_granularity_ns`；在任务数与交互性间权衡。
- 观测方法：ftrace 的 `sched:*` 事件、perf sched、/proc/schedstat；CFS period/slice 对尾延迟敏感。

代码片段（以当前任务运行时间与 CFS 参数为例）：
```c
// 摘自 projects/进程调度/cfs_analysis.c
u64 delta = rq->clock_task - rq->curr->se.exec_start;
printk(KERN_INFO, "curr runtime=%lluns period=%u slice=%u\n",
       delta, sysctl_sched_latency, sysctl_sched_min_granularity);
```

---
## 2.6 实时调度（RT）与截止时间（DL）
### 实时调度策略详解
- RT：`SCHED_FIFO/RR`，优先级固定（1–99），无饥饿保护，需谨慎防止优先级反转（使用 PI mutex）。
- DL：`SCHED_DEADLINE`，基于最早截止期（EDF）与运行时/周期保证；参数：运行时（runtime）、周期（period）、截止时间（deadline）。
- 工具：`chrt` 设置 RT，`schedtool`/`chrt` 或 `sys_sched_setattr` 设置 DL；需要 CAP_SYS_NICE。

### RT调度器实现分析
```c
// 摘自 projects/进程调度/rt_scheduler.c
static void analyze_rt_rq(struct rt_rq *rt_rq)
{
    struct rt_prio_array *array = &rt_rq->active;
    int prio;
    
    printk(KERN_INFO "=== RT Runqueue Analysis ===\n");
    printk(KERN_INFO "RT tasks: %d\n", rt_rq->rt_nr_running);
    
    // 分析每个优先级队列
    for (prio = 0; prio < MAX_RT_PRIO; prio++) {
        struct list_head *queue = array->queue + prio;
        int queue_len = 0;
        struct task_struct *p;
        
        list_for_each_entry(p, queue, run_list) {
            queue_len++;
        }
        
        if (queue_len > 0) {
            printk(KERN_INFO "  Priority %d: %d tasks\n", prio, queue_len);
        }
    }
}
```

### DL调度器参数配置
```c
// 摘自 projects/进程调度/dl_scheduler.c
static int configure_deadline_task(pid_t pid, __u64 runtime, __u64 period, __u64 deadline)
{
    struct sched_attr attr = {
        .size = sizeof(attr),
        .sched_policy = SCHED_DEADLINE,
        .sched_runtime = runtime,
        .sched_period = period,
        .sched_deadline = deadline,
        .sched_flags = 0,
    };
    
    return sched_setattr(pid, &attr, 0);
}

static void analyze_dl_rq(struct dl_rq *dl_rq)
{
    struct dl_entity *dl_se;
    
    printk(KERN_INFO "=== DL Runqueue Analysis ===\n");
    printk(KERN_INFO "DL tasks: %d\n", dl_rq->dl_nr_running);
    
    // 遍历DL实体
    list_for_each_entry(dl_se, &dl_rq->root, root_node) {
        printk(KERN_INFO "  Task: runtime=%llu period=%llu deadline=%llu\n",
               dl_se->runtime, dl_se->period, dl_se->deadline);
    }
}
```

### RT/DL实验与测试
```bash
# RT调度测试
sudo chrt -f 50 bash -c 'while true; do echo RT Task; sleep 1; done' &
task_pid=$!
chrt -p $task_pid  # 查看优先级

# DL调度测试（需要较新内核）
cat > dl_test.c << 'EOF'
#define _GNU_SOURCE
#include <sched.h>
#include <stdio.h>
#include <unistd.h>
#include <stdlib.h>

int main() {
    struct sched_attr attr = {
        .size = sizeof(attr),
        .sched_policy = SCHED_DEADLINE,
        .sched_runtime = 10 * 1000 * 1000,  // 10ms
        .sched_period = 100 * 1000 * 1000,  // 100ms
        .sched_deadline = 100 * 1000 * 1000, // 100ms
    };
    
    if (sched_setattr(0, &attr, 0) < 0) {
        perror("sched_setattr");
        exit(1);
    }
    
    printf("SCHED_DEADLINE task started\n");
    while (1) {
        printf("DL Task running\n");
        usleep(5000000); // 5s
    }
}
EOF
gcc -o dl_test dl_test.c
sudo ./dl_test
```

### 优先级反转与PI-Mutex
```c
// 摘自 projects/进程调度/pi_mutex_demo.c
static void demonstrate_priority_inversion(void)
{
    printk(KERN_INFO "Demonstrating priority inversion...\n");
    
    // 低优先级任务持有锁
    struct task_struct *low_task = kthread_create(low_priority_thread, NULL, "low_prio");
    kthread_bind(low_task, 0);
    wake_up_process(low_task);
    
    // 中等优先级任务
    struct task_struct *med_task = kthread_create(medium_priority_thread, NULL, "med_prio");
    kthread_bind(med_task, 0);
    wake_up_process(med_task);
    
    // 高优先级任务等待锁（将被阻塞）
    struct task_struct *high_task = kthread_create(high_priority_thread, NULL, "high_prio");
    kthread_bind(high_task, 0);
    wake_up_process(high_task);
    
    msleep(1000); // 观察优先级反转
    
    // 清理
    kthread_stop(low_task);
    kthread_stop(med_task);
    kthread_stop(high_task);
}
```

---
## 2.7 同步原语与锁竞争
### 锁机制详解
- 自旋锁（spinlock）：短临界区、不可睡眠；ticket/queued spinlock 降低争用开销。
- 互斥锁（mutex）：可睡眠；支持优先级继承（PI）。
- 读写锁（rwlock/rcu_read_lock）：读多写少场景；seqlock 适合读多写少但读重试可接受场景。
- 内存屏障：`smp_mb()/rmb()/wmb()`；原子操作与竞态检测（KCSAN）。

### 自旋锁实现分析
```c
// 摘自 projects/进程调度/spinlock_analyzer.c
static void analyze_spinlock_contention(raw_spinlock_t *lock)
{
#ifdef CONFIG_DEBUG_SPINLOCK
    struct spinlock_debug *debug = lock->debug;
    
    printk(KERN_INFO "Spinlock Analysis:\n");
    printk(KERN_INFO "  lock: %p\n", lock);
    printk(KERN_INFO "  owner: %s (PID: %d)\n", 
           debug->owner_comm, debug->owner_pid);
    printk(KERN_INFO "  acquire_time: %llu ns\n", debug->acquire_time);
#endif
}

// 测试自旋锁争用
static void test_spinlock_contention(void)
{
    raw_spinlock_t test_lock;
    unsigned long flags;
    
    raw_spin_lock_init(&test_lock);
    
    // 模拟高争用场景
    raw_spin_lock_irqsave(&test_lock, flags);
    mdelay(10); // 持有锁10ms
    raw_spin_unlock_irqrestore(&test_lock, flags);
}
```

### 互斥锁与优先级继承
```c
// 摘自 projects/进程调度/mutex_pi_demo.c
static struct mutex test_mutex;
static struct task_struct *low_task, *high_task;

static int low_priority_thread(void *data)
{
    mutex_lock(&test_mutex);
    printk(KERN_INFO "Low priority task acquired mutex\n");
    msleep(1000); // 长时间持有锁
    mutex_unlock(&test_mutex);
    return 0;
}

static int high_priority_thread(void *data)
{
    msleep(100); // 让低优先级任务先获取锁
    printk(KERN_INFO "High priority task waiting for mutex\n");
    mutex_lock(&test_mutex); // 将被阻塞，触发优先级继承
    printk(KERN_INFO "High priority task acquired mutex\n");
    mutex_unlock(&test_mutex);
    return 0;
}

static void demonstrate_pi_mutex(void)
{
    mutex_init(&test_mutex);
    
    // 创建低优先级任务
    low_task = kthread_create(low_priority_thread, NULL, "low_prio");
    sched_set_fifo_low(low_task);
    wake_up_process(low_task);
    
    // 创建高优先级任务
    high_task = kthread_create(high_priority_thread, NULL, "high_prio");
    sched_set_fifo(high_task);
    wake_up_process(high_task);
    
    msleep(2000);
    
    kthread_stop(low_task);
    kthread_stop(high_task);
}
```

### RCU机制深入分析
```c
// 摘自 projects/进程调度/rcu_analyzer.c
static void analyze_rcu_state(void)
{
    int cpu;
    
    printk(KERN_INFO "=== RCU State Analysis ===\n");
    
    for_each_online_cpu(cpu) {
        struct rcu_data *rdp = per_cpu_ptr(rcu_state.rda, cpu);
        struct rcu_node *rnp = rdp->mynode;
        
        printk(KERN_INFO "CPU %d:\n", cpu);
        printk(KERN_INFO "  completed=%lu gpnum=%lu\n",
               rdp->completed, rdp->gpnum);
        printk(KERN_INFO "  qs_pending=%d passed_quiesce=%d\n",
               rdp->qs_pending, rdp->passed_quiesce);
        printk(KERN_INFO "  Node: level=%d grplo=%d grphi=%d\n",
               rnp->level, rnp->grplo, rnp->grphi);
    }
}

// RCU宽限期追踪
static void trace_rcu_grace_period(void)
{
    unsigned long old_completed = rcu_state.completed;
    
    printk(KERN_INFO "Waiting for RCU grace period...\n");
    synchronize_rcu();
    
    printk(KERN_INFO "Grace period completed: %lu -> %lu\n",
           old_completed, rcu_state.completed);
}
```

### 锁竞争检测工具
```bash
# 使用lockstat检测锁争用（需要CONFIG_LOCK_STAT）
cat /proc/lock_stat 2>/dev/null | head -20 || echo "lockstat未启用"

# 使用perf检测锁事件
perf record -e lock:lock_acquire -e lock:lock_release -a sleep 5
perf report --stdio | head -30

# 查看锁的持有者
grep -r "lock" /proc/$(pgrep -f "test_program")/ 2>/dev/null | head -10

# KCSAN竞态检测（需要CONFIG_KCSAN）
dmesg | grep -i kcsan | tail -10
```

### 内存屏障与原子操作
```c
// 摘自 projects/进程调度/memory_barrier_demo.c
static void demonstrate_memory_barriers(void)
{
    volatile int x = 0, y = 0;
    
    // 没有内存屏障的情况
    x = 1;
    y = 1;  // 编译器或CPU可能重排这两条指令
    
    // 使用内存屏障
    x = 1;
    smp_mb(); // 全内存屏障
    y = 1;    // 保证在x=1之后执行
    
    printk(KERN_INFO "Memory barrier demonstration completed\n");
}

// 原子操作示例
static void demonstrate_atomic_ops(void)
{
    atomic_t counter = ATOMIC_INIT(0);
    int old_val, new_val;
    
    // 原子递增
    old_val = atomic_inc_return(&counter);
    
    // CAS操作
    do {
        old_val = atomic_read(&counter);
        new_val = old_val + 10;
    } while (!atomic_cmpxchg(&counter, old_val, new_val));
    
    printk(KERN_INFO "Atomic counter: %d\n", atomic_read(&counter));
}
```

---
## 2.8 RCU（Read-Copy Update）
### RCU核心概念
- 读侧无锁，写侧通过复制与宽限期（Grace Period）在不阻塞读者的情况下更新数据结构。
- 变体：Tree RCU、SRCU；GP/qs（quiescent state）跟踪；适于读密集、写较少的路径（如 VFS dcache）。
- 观测：`/sys/kernel/rcu/`、ftrace `rcu:*` 事件；调优参数与 stall 诊断。

### RCU实现机制分析
```c
// 摘自 projects/进程调度/rcu_implementation.c
static void demonstrate_rcu_usage(void)
{
    struct rcu_head *head;
    void *old_ptr, *new_ptr;
    
    // RCU读侧临界区
    rcu_read_lock();
    old_ptr = rcu_dereference(global_ptr);
    // 安全地访问old_ptr
    printk(KERN_INFO "RCU read: %p\n", old_ptr);
    rcu_read_unlock();
    
    // RCU更新侧
    new_ptr = kmalloc(sizeof(struct data), GFP_KERNEL);
    if (new_ptr) {
        memcpy(new_ptr, old_ptr, sizeof(struct data));
        // 修改new_ptr
        
        rcu_assign_pointer(global_ptr, new_ptr);
        call_rcu(&((struct data *)old_ptr)->rcu, rcu_callback);
    }
}

static void rcu_callback(struct rcu_head *head)
{
    struct data *p = container_of(head, struct data, rcu);
    printk(KERN_INFO "RCU callback: freeing %p\n", p);
    kfree(p);
}
```

### RCU性能监控
```bash
# 查看RCU状态
ls /sys/kernel/rcu/ 2>/dev/null || echo "RCU调试未启用"
cat /sys/kernel/rcu/rcu*/gpnum 2>/dev/null || echo "RCU信息不可用"
cat /sys/kernel/rcu/rcu*/completed 2>/dev/null

# 查看RCU回调队列
cat /sys/kernel/debug/rcu/rcu/tree_node_entry 2>/dev/null | head -20

# RCU stall检测
dmesg | grep -i "rcu.*stall" | tail -5
```

### SRCU（Sleepable RCU）分析
```c
// 摘自 projects/进程调度/srcu_demo.c
static DEFINE_SRCU(test_srcu);
static int srcu_idx;

static void demonstrate_srcu(void)
{
    int idx;
    
    // SRCU读侧（可以睡眠）
    idx = srcu_read_lock(&test_srcu);
    printk(KERN_INFO "SRCU read lock: idx=%d\n", idx);
    
    // 可以安全睡眠
    msleep(100);
    
    srcu_read_unlock(&test_srcu, idx);
    
    // SRCU更新侧
    synchronize_srcu(&test_srcu);
    printk(KERN_INFO "SRCU synchronize completed\n");
}

static void cleanup_srcu_data(void)
{
    cleanup_srcu_struct(&test_srcu);
}
```

### RCU调优与诊断
```bash
# RCU调优参数
cat /proc/sys/kernel/rcu* 2>/dev/null | head -10

# RCU CPU stall超时设置
cat /proc/sys/kernel/rcu_cpu_stall_timeout

# 查看RCU使用的回调类型
cat /sys/kernel/debug/rcu/rcu/rcudata.csv 2>/dev/null | head -5

# RCU树形结构
cat /sys/kernel/debug/rcu/rcu/rcutree 2>/dev/null | grep -E "(c|g|j|l|q|s)" | head -20
```

### ftrace RCU事件追踪
```bash
# 启用RCU ftrace事件
echo 1 > /sys/kernel/debug/tracing/events/rcu/enable 2>/dev/null || true
echo 1 > /sys/kernel/debug/tracing/events/rcu/rcu_grace_period/enable 2>/dev/null || true

# 触发RCU活动并查看
echo 1 > /sys/kernel/debug/tracing/tracing_on
sleep 5
echo 0 > /sys/kernel/debug/tracing/tracing_on
cat /sys/kernel/debug/tracing/trace | grep -E "(rcu|grace)" | head -20
```

---
## 2.9 可复现实验与评测设计
### 实验环境与工具准备
```bash
# 实验环境检查
./scripts/check_sched_env.sh  # 检查调度相关配置
./scripts/setup_sched_test.sh # 设置测试环境

# 工具安装检查
command -v perf >/dev/null || echo "perf未安装"
command -v taskset >/dev/null || echo "taskset未安装"
command -v chrt >/dev/null || echo "chrt未安装"
```

### 1) CFS/EEVDF 延迟-吞吐权衡
- **目标**：分析调度参数对交互性和吞吐量的影响
- **步骤**：调节 `sched_latency`/`min_granularity`，运行交互/批处理混合工作负载；
- **指标**：tail latency（P95/P99）、吞吐、上下文切换率、cache miss。

```bash
#!/bin/bash
# CFS参数调优实验脚本
# 保存原始参数
ORIG_LATENCY=$(cat /proc/sys/kernel/sched_latency_ns)
ORIG_GRANULARITY=$(cat /proc/sys/kernel/sched_min_granularity_ns)

# 测试不同参数组合
for latency in 10000000 20000000 40000000; do  # 10ms, 20ms, 40ms
    for granularity in 1000000 2000000 4000000; do  # 1ms, 2ms, 4ms
        echo "Testing: latency=${latency}ns granularity=${granularity}ns"
        
        # 设置参数
        echo $latency > /proc/sys/kernel/sched_latency_ns
        echo $granularity > /proc/sys/kernel/sched_min_granularity_ns
        
        # 运行测试负载
        ./bin/mixed_workload_test.sh > results/lat_${latency}_gran_${granularity}.txt
        
        sleep 2
    done
done

# 恢复原始参数
echo $ORIG_LATENCY > /proc/sys/kernel/sched_latency_ns
echo $ORIG_GRANULARITY > /proc/sys/kernel/sched_min_granularity_ns
```

### 2) 负载均衡与亲和实验
- **目标**：分析CPU亲和性对负载均衡的影响
- **步骤**：绑定/解除任务 CPU 亲和，观察迁移次数与 LLC 命中；
- **工具**：`taskset`、perf `sched`、ftrace `sched/sched_migrate_task`。

```bash
#!/bin/bash
# 负载均衡实验脚本

echo "=== Load Balance Experiment ==="

# 设置ftrace监控迁移事件
cd /sys/kernel/tracing
echo 0 > tracing_on
echo nop > current_tracer
echo 1 > events/sched/sched_migrate_task/enable
echo 1 > events/sched/sched_load_balance/enable

# 实验1：CPU密集型任务
for cpu_affinity in "0-3" "0-7" "all"; do
    echo "Testing CPU affinity: $cpu_affinity"
    echo 1 > tracing_on
    
    # 启动CPU密集型任务
    if [ "$cpu_affinity" = "all" ]; then
        taskset -c 0-15 ./bin/cpu_intensive_test &
    else
        taskset -c $cpu_affinity ./bin/cpu_intensive_test &
    fi
    
    sleep 10
    killall cpu_intensive_test
    echo 0 > tracing_on
    
    # 分析结果
    grep -c "sched_migrate_task" trace > migration_count_${cpu_affinity}.txt
done
```

### 3) RT/DL 实验
- **目标**：验证实时调度的确定性和截止时间保证
- **步骤**：以 `chrt` 设置多个 RT 任务与 background CFS 任务；或用 `sched_deadline` 跑周期任务；
- **指标**：deadline miss、RT 抢占次数、对 CFS 尾延迟的影响。

```bash
#!/bin/bash
# RT/DL调度实验

echo "=== RT/DL Scheduling Experiment ==="

# RT实验
setup_rt_experiment() {
    echo "Setting up RT experiment..."
    
    # 启动后台CFS任务
    for i in {1..4}; do
        ./bin/background_load.sh &
done
    
    # 启动RT任务
    sudo chrt -f 90 ./bin/rt_task 1000 > rt_f90.log &  # 高优先级RT
    sudo chrt -f 70 ./bin/rt_task 2000 > rt_f70.log &  # 中优先级RT
    sudo chrt -f 50 ./bin/rt_task 3000 > rt_f50.log &  # 低优先级RT
    
    sleep 30
    
    # 清理
    killall rt_task background_load.sh
}

# DL实验
setup_dl_experiment() {
    echo "Setting up DL experiment..."
    
    # 编译DL测试程序
    gcc -o dl_task ./src/dl_task.c -lrt
    
    # 启动DL任务
    sudo ./dl_task 10000000 100000000 100000000 > dl_task1.log &  # 10ms/100ms/100ms
    sudo ./dl_task 5000000 50000000 50000000 > dl_task2.log &    # 5ms/50ms/50ms
    
    sleep 20
    
    # 清理
    killall dl_task
}

# 运行实验
setup_rt_experiment
setup_dl_experiment

echo "Experiment completed. Check *.log files for results."
```

### 4) 锁竞争分析实验
- **目标**：分析不同锁机制的性能特征
- **步骤**：使用lockstat、perf等工具检测锁争用情况
- **指标**：锁等待时间、争用频率、CPU利用率

```bash
#!/bin/bash
# 锁竞争分析实验

echo "=== Lock Contention Analysis ==="

# 启用lockstat（如果可用）
if [ -f /proc/lock_stat ]; then
    echo 1 > /proc/sys/kernel/lock_stat
    echo "Lockstat enabled"
fi

# 运行锁竞争测试
echo "Testing spinlock contention..."
./bin/test_spinlock_contention > spinlock_test.log

echo "Testing mutex contention..."
./bin/test_mutex_contention > mutex_test.log

echo "Testing RCU performance..."
./bin/test_rcu_performance > rcu_test.log

# 收集结果
if [ -f /proc/lock_stat ]; then
cat /proc/lock_stat > lock_stat_results.txt
echo 0 > /proc/sys/kernel/lock_stat
fi

# perf锁事件分析
perf record -e lock:lock_acquire -e lock:lock_release -a ./bin/test_all_locks
perf report --stdio > perf_lock_analysis.txt
```

### 5) 综合性能基准测试
```bash
#!/bin/bash
# 综合调度性能测试

echo "=== Comprehensive Scheduler Benchmark ==="

# 系统信息收集
mkdir -p benchmark_results
cat /proc/cpuinfo > benchmark_results/cpuinfo.txt
cat /proc/cmdline > benchmark_results/cmdline.txt
cat /sys/devices/system/cpu/cpu*/cpufreq/scaling_governor > benchmark_results/governors.txt

# 运行hackbench（调度延迟测试）
echo "Running hackbench..."
hackbench -l 1000 -p 20 -s 100 -g 15 -f 25 -i > benchmark_results/hackbench.txt

# 运行schbench（调度性能测试）
echo "Running schbench..."
./bin/schbench -m 1000 -r 100 -s 300000 -c 0 -t 16 > benchmark_results/schbench.txt

# 运行perf bench调度测试
echo "Running perf bench..."
perf bench sched messaging -l 1000 -p 20 -s 100 > benchmark_results/perf_messaging.txt
perf bench sched pipe -l 1000 > benchmark_results/perf_pipe.txt

# 生成报告
echo "Generating benchmark report..."
./scripts/generate_sched_report.sh benchmark_results/
```

### 自动化实验脚本
```bash
#!/bin/bash
# 调度子系统自动测试框架

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
RESULT_DIR="${SCRIPT_DIR}/../results/$(date +%Y%m%d_%H%M%S)"

# 创建结果目录
mkdir -p "$RESULT_DIR"

# 环境检查
check_environment() {
    echo "Checking environment..."
    
    # 检查工具
    for tool in perf taskset chrt fio; do
        if ! command -v $tool >/dev/null 2>&1; then
            echo "Warning: $tool not found"
        fi
    done
    
    # 检查内核配置
    if [ ! -f /sys/kernel/debug/tracing/available_events ]; then
        echo "Warning: ftrace not available"
    fi
    
    # 保存系统信息
    uname -a > "$RESULT_DIR/system_info.txt"
    cat /proc/cmdline > "$RESULT_DIR/cmdline.txt"
    zcat /proc/config.gz 2>/dev/null > "$RESULT_DIR/config.txt" || \
    cat /boot/config-$(uname -r) 2>/dev/null > "$RESULT_DIR/config.txt" || \
    echo "Kernel config not available" > "$RESULT_DIR/config.txt"
}

# 运行所有实验
run_all_experiments() {
    echo "Running all scheduling experiments..."
    
    cd "$SCRIPT_DIR"
    
    # 基础实验
    ./experiments/cfs_parameter_test.sh "$RESULT_DIR"
    ./experiments/load_balance_test.sh "$RESULT_DIR"
    ./experiments/rt_dl_test.sh "$RESULT_DIR"
    ./experiments/lock_contention_test.sh "$RESULT_DIR"
    
    # 高级实验
    ./experiments/numa_aware_test.sh "$RESULT_DIR"
    ./experiments/energy_aware_test.sh "$RESULT_DIR"
    ./experiments/cgroup_fairness_test.sh "$RESULT_DIR"
    
    echo "All experiments completed. Results saved to: $RESULT_DIR"
}

# 主函数
main() {
    echo "=== Linux Scheduler Comprehensive Test Suite ==="
    echo "Results will be saved to: $RESULT_DIR"
    
    check_environment
    run_all_experiments
    
    echo "Generating summary report..."
    ./scripts/generate_summary_report.sh "$RESULT_DIR"
    
    echo "Test suite completed successfully!"
    echo "Results location: $RESULT_DIR"
}

main "$@"
```

脚本片段（观测常用调度事件）：
```bash
# ftrace：启用调度相关事件
mount -t tracefs nodev /sys/kernel/tracing 2>/dev/null || true
cd /sys/kernel/tracing
echo 0 > tracing_on; echo nop > current_tracer
for e in sched_switch sched_wakeup sched_wakeup_new sched_migrate_task; do
  echo 1 > events/sched/$e/enable
done
echo 1 > tracing_on; sleep 3; echo 0 > tracing_on
head trace
```

---
## 2.10 当前研究趋势与难点
- EEVDF 在主线的推进与交互延迟优化；公平性与吞吐的再平衡。
- PREEMPT_RT 常态化：实时补丁合入主线后对锁、抢占模型的影响。
- 能效/异构调度（EAS、big.LITTLE）、核心调度（core scheduling）与 SMT 安全。
- io_uring 驱动的用户态 I/O 与调度交互；cgroup v2 的层级公平与抢占策略。

---
## 2.11 小结
本章围绕 CFS/EEVDF、RT/DL 与多核负载均衡给出理论—实现—实验闭环范式；配合仓库中的观测模块，可定量分析调度参数与亲和策略对尾延迟与吞吐的影响，并为后续性能优化与跨子系统（内存/文件系统/网络）分析提供依据。

---
## 2.12 参考文献
[1] Documentation/scheduler/ 下的设计与参数说明，https://www.kernel.org/doc/html/latest/
[2] Peter Zijlstra 等，EEVDF 讨论与补丁（LKML/LWN 专题）。
[3] Paul E. McKenney, Is Parallel Programming Hard, And, If So, What Can You Do About It?（RCU 书稿）。
[4] Torvalds 等：kernel/sched/ 源码与提交说明。
[5] Thomas Gleixner：PREEMPT_RT（内核文档与 LWN 报道）。
[6] Ingo Molnár：CFS 设计讨论（LKML/LWN）。
[7] Brendan Gregg, Systems Performance (2nd Edition), 2020/2023。
[8] perf/ftrace 文档与 `tools/` 源码。

