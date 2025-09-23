# 第6章 内核性能分析与优化研究（projects/内核性能）

本章以 Linux 6.6 LTS 为基线，面向刚入门的工程师，采用“先动手、再深入”的教程体例，围绕 CPU/调度、内存/回收、I/O/块层、网络与中断等关键面向，讲解如何安全地观测、定位与改进系统性能。我们优先使用系统自带接口（/proc、/sys、tracefs），可选使用 perf/bpftrace 等用户态工具（若已安装）。配套脚本与示例将补充在 projects/内核性能/ 下（计划：cfs_fairness.sh、ftrace_sched_sample.sh、perf_cpu_hotspots.sh、psi_watch.sh）。

> 环境建议：非生产环境（QEMU/KVM/实验机/容器）；需要 sudo/root（tracefs 观测）；尽量避免修改系统永久配置。涉及可能改动状态的命令，始终提供“还原/停止”步骤。

---
## 6.0 给新手的快速入门教程（10–20分钟）

学习目标
- 会用 3–4 条命令快速判断“CPU 繁忙在哪、是否有调度/中断/软中断背压”
- 会抓取一次最小的调度与软中断轨迹（tracefs），并阅读关键字段
- 会用 taskset 构造“可复现”的 CPU 负载，进行对照实验

前置准备
- 挂载 tracefs：`sudo mount -t tracefs nodev /sys/kernel/tracing 2>/dev/null || true`

步骤一：CPU/中断/软中断“体检”
```bash
# 1) CPU 总览与上下文切换
sed -n '1,3p' /proc/loadavg; vmstat 1 2 | sed -n '1,4p' || true
# 2) 中断/软中断
sed -n '1,5p' /proc/interrupts; sed -n '1,20p' /proc/softirqs
# 3) PSI（Pressure Stall Information，若内核启用）
for t in cpu io memory; do [ -f /proc/pressure/$t ] && { echo ">>> $t"; cat /proc/pressure/$t; }; done
```
输出解读（入门要点）
- vmstat 的 r（就绪队列）大、cs（切换）极高 → 调度切换频繁；b（阻塞）大 → I/O 等待可能性高
- /proc/softirqs 的 NET_RX/NET_TX/RCU/BLOCK 等计数快速增长 → 相应子系统压力较大
- /proc/pressure/* 的 some/avg10、full/avg10 升高 → 存在可观测 stall，对尾延迟不利

步骤二：用 taskset 构造可复现 CPU 负载
```bash
# 在 CPU0 上制造 2 个忙循环（yes），并在 5 秒后清理
( taskset -c 0 sh -c 'yes >/dev/null' & ); P1=$!
( taskset -c 0 sh -c 'yes >/dev/null' & ); P2=$!
sleep 5; kill $P1 $P2 2>/dev/null || true
```
观测：重复步骤一；r、cs、/proc/schedstat（若可用）会有所变化。

步骤三：抓取最小调度/软中断轨迹（tracefs）
```bash
cd /sys/kernel/tracing
echo 0 | sudo tee tracing_on >/dev/null
: | sudo tee trace >/dev/null
# 打开关键事件：调度切换、唤醒、迁移；以及软中断入口（若存在）
for e in sched_switch sched_wakeup sched_migrate_task; do echo 1 | sudo tee events/sched/$e/enable >/dev/null; done
[ -d events/irq ] && echo 1 | sudo tee events/irq/enable >/dev/null || true
# 触发一次短负载
( taskset -c 0 sh -c 'dd if=/dev/zero of=/dev/null bs=1M count=256 status=none' & )
sleep 1; echo 0 | sudo tee tracing_on >/dev/null
sudo tail -n 60 trace | sed -n '1,60p'
```
你应当看到 sched_switch（上下文切换）、sched_wakeup（唤醒）、sched_migrate_task（迁移）等事件，能帮助回答“哪个线程在跑/为什么被切换/是否频繁迁移”。

常见错误与排错
- tracefs 事件目录缺失 → 与内核裁剪有关；换用已存在的事件组，或退回使用 vmstat/ps/top 等用户态观测
- 背景负载残留 → 使用 `pkill yes` 清理；用 `ps -eo psr,comm` 检查线程所在 CPU

学习检查点
- 能结合 vmstat、/proc/interrupts、/proc/softirqs、/proc/pressure/* 给出“初步性能画像”
- 能抓取一次最小 tracefs 轨迹并定位一次上下文切换

---
## 6.1 观测与工具地图（从零到一）
- /proc 与 /sys：系统状态与内核统计的首选入口（轻量、通用）
- tracefs：函数级/事件级可观测；事件如 sched/*、irq/*、net/*、block/*、writeback/*
- perf（若已安装）：CPU 周期采样、调用栈、热点函数、锁与调度分析
- eBPF/bpftrace（若已安装）：低开销、可编程的观测脚本；适合动态问题与根因定位
- 辅助：taskset/chrt（调度策略/亲和）、cgroups（隔离与限额）、numactl（NUMA 策略）

---
## 6.2 CPU 与调度：热点与调度行为
### CPU性能分析框架
CPU性能分析遵循"自上而下"的方法：系统级→进程级→函数级→指令级。关键指标包括利用率、IPC（每时钟周期指令数）、缓存命中率、分支预测准确率等。

### 热点（Hotspot）快速观察
```bash
# 系统级CPU统计
sudo perf stat -a -- sleep 3 | sed -n '1,40p'
# 采样并打印前若干热点（可能需要更大权限）
sudo perf record -a -g -- sleep 3 && sudo perf report --stdio | head -n 40
```

### 高级CPU性能分析
```c
// 摘自 projects/内核性能/cpu_performance_analyzer.c
static void analyze_cpu_performance(void)
{
    struct cpu_perf_stats {
        u64 instructions;
        u64 cycles;
        u64 cache_misses;
        u64 branch_misses;
        u64 context_switches;
    } stats;
    
    // 读取性能计数器
    rdmsrl(MSR_IA32_PERFCTR0, stats.instructions);
    rdmsrl(MSR_IA32_PERFCTR1, stats.cycles);
    rdmsrl(MSR_IA32_PERFCTR2, stats.cache_misses);
    
    // 计算关键指标
    u64 ipc = stats.instructions / max(stats.cycles, 1);
    u64 cache_miss_rate = (stats.cache_misses * 100) / max(stats.instructions, 1);
    
    printk(KERN_INFO "=== CPU Performance Analysis ===\n");
    printk(KERN_INFO "IPC: %llu (instructions/cycle)\n", ipc);
    printk(KERN_INFO "Cache miss rate: %llu%%\n", cache_miss_rate);
    printk(KERN_INFO "Context switches: %llu\n", stats.context_switches);
    
    // 性能评估
    if (ipc < 1) {
        printk(KERN_WARNING "Low IPC detected - possible memory bottleneck\n");
    }
    if (cache_miss_rate > 5) {
        printk(KERN_WARNING "High cache miss rate - consider data locality optimization\n");
    }
}

// CPU拓扑分析
static void analyze_cpu_topology(void)
{
    int cpu;
    
    printk(KERN_INFO "=== CPU Topology Analysis ===\n");
    
    for_each_online_cpu(cpu) {
        struct cpuinfo_x86 *c = &cpu_data(cpu);
        
        printk(KERN_INFO "CPU %d:\n", cpu);
        printk(KERN_INFO "  Vendor: %s\n", c->x86_vendor_id);
        printk(KERN_INFO "  Model: %s\n", c->x86_model_id);
        printk(KERN_INFO "  Cores: %d\n", c->booted_cores);
        printk(KERN_INFO "  Siblings: %d\n", c->x86_max_cores);
        printk(KERN_INFO "  Cache size: %d KB\n", c->x86_cache_size);
        
        // NUMA拓扑
        printk(KERN_INFO "  NUMA node: %d\n", cpu_to_node(cpu));
        
        // 频率信息
        if (c->x86_power & (1 << 8)) {
            printk(KERN_INFO "  Turbo boost: supported\n");
        }
    }
}
```

### tracefs 的函数图（function_graph）
```bash
cd /sys/kernel/tracing
echo function_graph | sudo tee current_tracer >/dev/null
echo 1 | sudo tee tracing_on >/dev/null; sleep 1; echo 0 | sudo tee tracing_on >/dev/null
sudo tail -n 80 trace | sed -n '1,80p'
```

### 调度行为深度分析（上下文切换/迁移/唤醒）
```c
// 摘自 projects/内核性能/sched_behavior_analyzer.c
static void analyze_scheduling_behavior(void)
{
    struct sched_stats {
        unsigned long context_switches;
        unsigned long migrations;
        unsigned long wakeups;
        unsigned long wakeups_idle;
        unsigned long wakeups_affine;
    } stats;
    
    int cpu;
    
    printk(KERN_INFO "=== Scheduling Behavior Analysis ===\n");
    
    for_each_online_cpu(cpu) {
        struct rq *rq = cpu_rq(cpu);
        struct cfs_rq *cfs_rq = &rq->cfs;
        
        printk(KERN_INFO "CPU %d:\n", cpu);
        printk(KERN_INFO "  Running tasks: %d\n", cfs_rq->nr_running);
        printk(KERN_INFO "  Load avg: %lu\n", cfs_rq->rq_avg.load_avg);
        printk(KERN_INFO "  Util avg: %lu\n", cfs_rq->rq_avg.util_avg);
        
        // 分析负载均衡
        if (cpu > 0) {
            struct rq *prev_rq = cpu_rq(cpu - 1);
            long load_diff = (long)cfs_rq->rq_avg.load_avg - 
                           (long)prev_rq->cfs.rq_avg.load_avg;
            
            if (abs(load_diff) > 100) {
                printk(KERN_WARNING "  Load imbalance with CPU%d: %ld\n", 
                       cpu - 1, load_diff);
            }
        }
    }
    
    // 分析调度延迟
    analyze_sched_latency();
}

// 调度延迟分析
static void analyze_sched_latency(void)
{
    struct task_struct *p;
    
    printk(KERN_INFO "=== Scheduling Latency Analysis ===\n");
    
    for_each_process(p) {
        if (p->sched_class == &fair_sched_class) {
            struct sched_entity *se = &p->se;
            u64 wait_time = se->sum_exec_runtime - se->prev_sum_exec_runtime;
            
            if (wait_time > NSEC_PER_SEC) {
                printk(KERN_WARNING "Task %s (PID: %d) high wait time: %llums\n",
                       p->comm, p->pid, wait_time / NSEC_PER_MSEC);
            }
        }
    }
}
```

### 调度行为（上下文切换/迁移/唤醒）
```bash
cd /sys/kernel/tracing
for e in sched_switch sched_migrate_task sched_wakeup; do echo 1 | sudo tee events/sched/$e/enable >/dev/null; done
( taskset -c 0 yes >/dev/null & ); sleep 1; pkill yes
sudo tail -n 60 trace | sed -n '1,60p'
```

### CPU性能调优策略
```bash
# CPU频率调节
cat /sys/devices/system/cpu/cpu*/cpufreq/scaling_governor
# 性能模式
echo performance | sudo tee /sys/devices/system/cpu/cpu*/cpufreq/scaling_governor
# 节能模式
echo powersave | sudo tee /sys/devices/system/cpu/cpu*/cpufreq/scaling_governor

# CPU亲和性设置
# 查看当前亲和性
taskset -p $(pgrep -f "test_program")
# 设置CPU亲和性
taskset -c 0-3 ./test_program

# 中断亲和性
cat /proc/irq/*/smp_affinity_list | head -10
# 设置中断亲和性
echo 1 | sudo tee /proc/irq/16/smp_affinity
```

要点
- 过多迁移（migrate）通常不利于缓存局部性；可用 taskset/affinity 控制
- 上下文切换极高可能指示线程过多/时间片过短/锁争用
- IPC低于1通常表示内存瓶颈，需要优化数据局部性
- 缓存命中率低于95%可能需要考虑数据结构和算法优化

---
## 6.3 内存与回收：缺页/回收/压力
### 内存性能分析框架
内存性能分析关注四个核心维度：容量、带宽、延迟、一致性。关键指标包括缺页率、内存带宽利用率、TLB命中率、NUMA访问延迟等。

### 基础内存观测
```bash
# 缺页统计
grep -E 'pgfault|pgmajfault' /proc/vmstat | sed -n '1,20p'
[ -f /proc/pressure/memory ] && cat /proc/pressure/memory || true
# 回收与直接回收
grep -E 'pgscan|pgsteal|kswapd|pgrefill|pgactivate|pgdeactivate' /proc/vmstat | sed -n '1,40p'
```

### 高级内存分析
```c
// 摘自 projects/内核性能/memory_performance_analyzer.c
static void analyze_memory_performance(void)
{
    struct mem_stats {
        unsigned long pgfault;
        unsigned long pgmajfault;
        unsigned long pgscan_kswapd;
        unsigned long pgscan_direct;
        unsigned long pgsteal_kswapd;
        unsigned long pgsteal_direct;
        unsigned long oom_kill;
    } stats;
    
    // 读取内存统计
    stats.pgfault = global_node_page_state(NR_PGFAULT);
    stats.pgmajfault = global_node_page_state(NR_PGMAJFAULT);
    stats.pgscan_kswapd = global_node_page_state(NR_PGSCAN_KSWAPD);
    stats.pgscan_direct = global_node_page_state(NR_PGSCAN_DIRECT);
    
    printk(KERN_INFO "=== Memory Performance Analysis ===\n");
    printk(KERN_INFO "Page faults: %lu (major: %lu)\n", 
           stats.pgfault, stats.pgmajfault);
    printk(KERN_INFO "Page scans - kswapd: %lu, direct: %lu\n",
           stats.pgscan_kswapd, stats.pgscan_direct);
    
    // 计算缺页率
    if (stats.pgfault > 0) {
        u64 major_fault_rate = (stats.pgmajfault * 100) / stats.pgfault;
        printk(KERN_INFO "Major fault rate: %llu%%\n", major_fault_rate);
        
        if (major_fault_rate > 10) {
            printk(KERN_WARNING "High major fault rate - consider increasing memory\n");
        }
    }
    
    // 分析内存回收压力
    if (stats.pgscan_direct > stats.pgscan_kswapd) {
        printk(KERN_WARNING "High direct reclaim pressure detected\n");
    }
}

// NUMA内存分析
static void analyze_numa_memory(void)
{
    int nid;
    
    printk(KERN_INFO "=== NUMA Memory Analysis ===\n");
    
    for_each_online_node(nid) {
        struct pglist_data *pgdat = NODE_DATA(nid);
        unsigned long free_pages = 0;
        unsigned long total_pages = 0;
        int zone_type;
        
        printk(KERN_INFO "NUMA Node %d:\n", nid);
        
        for (zone_type = 0; zone_type < MAX_NR_ZONES; zone_type++) {
            struct zone *zone = &pgdat->node_zones[zone_type];
            if (!populated_zone(zone)) continue;
            
            free_pages += zone_page_state(zone, NR_FREE_PAGES);
            total_pages += zone->present_pages;
            
            printk(KERN_INFO "  Zone %s: free=%lu total=%lu\n",
                   zone->name, zone_page_state(zone, NR_FREE_PAGES),
                   zone->present_pages);
        }
        
        if (total_pages > 0) {
            u64 utilization = ((total_pages - free_pages) * 100) / total_pages;
            printk(KERN_INFO "  Total utilization: %llu%%\n", utilization);
            
            if (utilization > 90) {
                printk(KERN_WARNING "Node %d memory utilization high\n", nid);
            }
        }
    }
}

// TLB性能分析
static void analyze_tlb_performance(void)
{
    struct tlb_stats {
        unsigned long tlb_flush_batched;
        unsigned long tlb_flush_remote;
        unsigned long tlb_local_flush_all;
        unsigned long tlb_local_flush_one;
    } stats;
    
    printk(KERN_INFO "=== TLB Performance Analysis ===\n");
    
    // 读取TLB统计（需要架构支持）
    stats.tlb_flush_batched = global_node_page_state(NR_TLB_FLUSH_BATCHED);
    stats.tlb_flush_remote = global_node_page_state(NR_TLB_FLUSH_REMOTE);
    
    printk(KERN_INFO "TLB flushes - batched: %lu, remote: %lu\n",
           stats.tlb_flush_batched, stats.tlb_flush_remote);
    
    // TLB命中率估算（基于刷新频率）
    if (stats.tlb_flush_remote > 1000) {
        printk(KERN_WARNING "High remote TLB flushes - consider NUMA affinity\n");
    }
}
```

### 内存回收机制分析
```c
// 摘自 projects/内核性能/reclaim_analyzer.c
static void analyze_memory_reclaim(void)
{
    struct reclaim_stats {
        unsigned long kswapd_wakeups;
        unsigned long direct_reclaim_scans;
        unsigned long slab_reclaimed;
        unsigned long pageout_run;
    } stats;
    
    printk(KERN_INFO "=== Memory Reclaim Analysis ===\n");
    
    // 读取回收统计
    stats.kswapd_wakeups = global_node_page_state(NR_KSWAPD_WAKEUP);
    stats.direct_reclaim_scans = global_node_page_state(NR_DIRECT_SCAN);
    
    printk(KERN_INFO "Kswapd wakeups: %lu\n", stats.kswapd_wakeups);
    printk(KERN_INFO "Direct reclaim scans: %lu\n", stats.direct_reclaim_scans);
    
    // 回收压力评估
    if (stats.direct_reclaim_scans > stats.kswapd_wakeups * 10) {
        printk(KERN_WARNING "Excessive direct reclaim - memory pressure high\n");
        printk(KERN_WARNING "Consider:\n");
        printk(KERN_WARNING "  1. Increasing system memory\n");
        printk(KERN_WARNING "  2. Tuning vm.swappiness\n");
        printk(KERN_WARNING "  3. Optimizing application memory usage\n");
    }
    
    // 分析slab回收
    analyze_slab_reclaim();
}

// Slab回收分析
static void analyze_slab_reclaim(void)
{
    struct kmem_cache *s;
    unsigned long total_slab = 0;
    unsigned long reclaimable_slab = 0;
    
    printk(KERN_INFO "=== Slab Reclaim Analysis ===\n");
    
    mutex_lock(&slab_mutex);
    list_for_each_entry(s, &slab_caches, list) {
        struct kmem_cache_node *n;
        int node;
        
        for_each_online_node(node) {
            n = get_node(s, node);
            if (!n) continue;
            
            total_slab += n->nr_slabs * s->size;
            reclaimable_slab += n->free_objects * s->size;
        }
    }
    mutex_unlock(&slab_mutex);
    
    printk(KERN_INFO "Total slab memory: %lu KB\n", total_slab / 1024);
    printk(KERN_INFO "Reclaimable slab: %lu KB\n", reclaimable_slab / 1024);
    
    if (total_slab > 0) {
        u64 reclaim_ratio = (reclaimable_slab * 100) / total_slab;
        printk(KERN_INFO "Slab reclaim ratio: %llu%%\n", reclaim_ratio);
        
        if (reclaim_ratio > 50) {
            printk(KERN_INFO "Consider slab reclaim for memory optimization\n");
        }
    }
}
```

tracefs（若内核提供 mm/* 相关事件）
```bash
cd /sys/kernel/tracing
[ -d events/mm ] && echo 1 | sudo tee events/mm/enable >/dev/null || true
# 触发一次内存分配/释放工作负载（安全：分配->释放）
python3 - <<'PY' 2>/dev/null || true
x=[b'X'*1024*1024 for _ in range(256)]; del x
PY
sudo tail -n 60 trace | sed -n '1,60p'
```

### PSI（Pressure Stall Information）深度分析
```bash
# PSI指标解读
cat /proc/pressure/cpu
cat /proc/pressure/memory
cat /proc/pressure/io

# PSI监控脚本
#!/bin/bash
while true; do
    echo "=== $(date) ==="
    echo "CPU pressure:"
    cat /proc/pressure/cpu
    echo "Memory pressure:"
    cat /proc/pressure/memory
    echo "IO pressure:"
    cat /proc/pressure/io
    sleep 5
done
```

### 内存性能调优
```bash
# 内存回收参数调优
# 查看当前设置
cat /proc/sys/vm/swappiness
cat /proc/sys/vm/dirty_ratio
cat /proc/sys/vm/dirty_background_ratio

# 调优建议
echo 10 | sudo tee /proc/sys/vm/swappiness  # 降低交换倾向
echo 15 | sudo tee /proc/sys/vm/dirty_ratio  # 降低脏页比例
echo 5 | sudo tee /proc/sys/vm/dirty_background_ratio

# 透明大页设置
cat /sys/kernel/mm/transparent_hugepage/enabled
echo always | sudo tee /sys/kernel/mm/transparent_hugepage/enabled

# NUMA内存策略
numactl --hardware
numactl --show
```

要点
- major fault（pgmajfault）偏高：磁盘 I/O 压力或工作集不在内存
- 持续直接回收（direct reclaim）与 memory PSI 上升：内存紧张，影响尾延迟
- TLB刷新频繁可能表示内存访问模式碎片化，需要优化数据布局
- NUMA节点间内存访问不平衡可能导致性能下降，需要考虑NUMA亲和性

---
## 6.4 I/O 与块层：队列/回写/延迟
### I/O性能分析框架
I/O性能分析关注四个关键维度：吞吐量、延迟、IOPS（每秒I/O操作数）、队列深度。现代Linux内核采用blk-mq（多队列块层）架构，支持高并发SSD设备。

### 基础I/O观测
```bash
# 写回与脏页
grep -E 'Dirty|Writeback' /proc/meminfo
# 块层（若存在 blktrace/perf，可选使用；此处仅提供 tracefs 路径）
cd /sys/kernel/tracing
for g in block writeback filemap; do echo 1 | sudo tee events/$g/enable 2>/dev/null || true; done
( dd if=/dev/zero of=/tmp/io_test bs=1M count=64 oflag=direct 2>/dev/null ); sync
sudo tail -n 80 trace | sed -n '1,80p'
rm -f /tmp/io_test
```

### 高级I/O性能分析
```c
// 摘自 projects/内核性能/io_performance_analyzer.c
static void analyze_io_performance(void)
{
    struct io_stats {
        unsigned long pages_read;
        unsigned long pages_written;
        unsigned long io_wait_time;
        unsigned long io_queue_depth;
        unsigned long io_merges;
        unsigned long io_ticks;
    } stats;
    
    printk(KERN_INFO "=== I/O Performance Analysis ===\n");
    
    // 读取块层统计
    stats.pages_read = global_node_page_state(NR_FILE_READ);
    stats.pages_written = global_node_page_state(NR_FILE_WRITE);
    
    printk(KERN_INFO "Pages read: %lu, written: %lu\n", 
           stats.pages_read, stats.pages_written);
    
    // 分析I/O等待时间
    analyze_io_wait_time();
    
    // 分析块设备队列
    analyze_block_queues();
    
    // 分析回写机制
    analyze_writeback_mechanism();
}

// I/O等待时间分析
static void analyze_io_wait_time(void)
{
    int cpu;
    u64 total_iowait = 0;
    
    printk(KERN_INFO "=== I/O Wait Time Analysis ===\n");
    
    for_each_online_cpu(cpu) {
        struct kernel_cpustat *kcs = &kcpustat_cpu(cpu);
        u64 iowait = kcs->cpustat[CPUTIME_IOWAIT];
        
        total_iowait += iowait;
        printk(KERN_INFO "CPU %d iowait: %llu jiffies\n", cpu, iowait);
    }
    
    if (total_iowait > NSEC_PER_SEC) {
        printk(KERN_WARNING "High total I/O wait time detected\n");
        printk(KERN_WARNING "Consider:\n");
        printk(KERN_WARNING "  1. Upgrading to faster storage\n");
        printk(KERN_WARNING "  2. Optimizing I/O patterns\n");
        printk(KERN_WARNING "  3. Increasing I/O queue depth\n");
    }
}

// 块设备队列分析
static void analyze_block_queues(void)
{
    struct gendisk *disk;
    
    printk(KERN_INFO "=== Block Device Queue Analysis ===\n");
    
    // 遍历所有块设备
    list_for_each_entry(disk, &disk_list, list) {
        struct request_queue *q = disk->queue;
        if (!q) continue;
        
        printk(KERN_INFO "Device %s:\n", disk->disk_name);
        printk(KERN_INFO "  Queue depth: %u\n", q->nr_requests);
        printk(KERN_INFO "  Max sectors: %u\n", q->limits.max_sectors);
        printk(KERN_INFO "  Max segments: %u\n", q->limits.max_segments);
        
        // 分析队列利用率
        if (q->nr_requests > 0) {
            unsigned long inflight = q->nr_inflight[0] + q->nr_inflight[1];
            u64 utilization = (inflight * 100) / q->nr_requests;
            
            printk(KERN_INFO "  Inflight requests: %lu\n", inflight);
            printk(KERN_INFO "  Queue utilization: %llu%%\n", utilization);
            
            if (utilization > 80) {
                printk(KERN_WARNING "High queue utilization on %s\n", disk->disk_name);
            }
        }
    }
}

// 回写机制分析
static void analyze_writeback_mechanism(void)
{
    struct bdi_writeback *wb;
    unsigned long total_dirty = 0;
    unsigned long total_writeback = 0;
    
    printk(KERN_INFO "=== Writeback Mechanism Analysis ===\n");
    
    // 读取脏页统计
    total_dirty = global_node_page_state(NR_FILE_DIRTY);
    total_writeback = global_node_page_state(NR_WRITEBACK);
    
    printk(KERN_INFO "Total dirty pages: %lu\n", total_dirty);
    printk(KERN_INFO "Total writeback pages: %lu\n", total_writeback);
    
    // 分析回写压力
    if (total_dirty > 10000) {
        printk(KERN_WARNING "High dirty page count detected\n");
        
        // 检查回写限制
        unsigned long dirty_thresh = global_dirty_threshold;
        unsigned long dirty_background_thresh = dirty_background_threshold;
        
        printk(KERN_INFO "Dirty threshold: %lu\n", dirty_thresh);
        printk(KERN_INFO "Background threshold: %lu\n", dirty_background_thresh);
        
        if (total_dirty > dirty_thresh) {
            printk(KERN_CRITICAL "Dirty pages exceed threshold - blocking I/O\n");
        }
    }
    
    // 分析回写拥塞
    analyze_writeback_congestion();
}

// 回写拥塞分析
static void analyze_writeback_congestion(void)
{
    struct bdi_writeback_congested *congested;
    int congested_count = 0;
    
    // 检查回写拥塞状态
    list_for_each_entry(congested, &wb_congested_list, list) {
        if (time_after(jiffies, congested->timeout)) {
            congested_count++;
        }
    }
    
    if (congested_count > 0) {
        printk(KERN_WARNING "Writeback congestion detected: %d congested\n", 
               congested_count);
        printk(KERN_WARNING "Consider:\n");
        printk(KERN_WARNING "  1. Increasing writeback threads\n");
        printk(KERN_WARNING "  2. Adjusting dirty_ratio parameters\n");
        printk(KERN_WARNING "  3. Upgrading storage performance\n");
    }
}
```

### I/O调度器分析
```bash
# 查看当前I/O调度器
cat /sys/block/sda/queue/scheduler
# 查看I/O统计
cat /sys/block/sda/stat
# 查看队列深度
cat /sys/block/sda/queue/nr_requests
# 查看最大扇区大小
cat /sys/block/sda/queue/max_sectors_kb

# I/O延迟分析工具（需要blktrace）
blktrace -d /dev/sda -w 10
blkparse sda.blktrace.* > sda.dump

# I/O性能测试
fio --name=randread --ioengine=libaio --iodepth=16 --rw=randread --bs=4k --direct=1 --size=1G --numjobs=4 --runtime=60 --group_reporting
```

### 高级I/O监控
```c
// 摘自 projects/内核性能/advanced_io_monitor.c
static void monitor_io_latency(void)
{
    struct io_latency_stats {
        u64 read_latency_sum;
        u64 write_latency_sum;
        u64 read_count;
        u64 write_count;
        u64 max_read_latency;
        u64 max_write_latency;
    } stats = {0};
    
    printk(KERN_INFO "=== I/O Latency Monitoring ===\n");
    
    // 监控I/O完成事件
    void trace_io_completion(struct request *req, u64 latency)
    {
        if (rq_data_dir(req) == READ) {
            stats.read_latency_sum += latency;
            stats.read_count++;
            if (latency > stats.max_read_latency)
                stats.max_read_latency = latency;
        } else {
            stats.write_latency_sum += latency;
            stats.write_count++;
            if (latency > stats.max_write_latency)
                stats.max_write_latency = latency;
        }
    }
    
    // 计算平均延迟
    if (stats.read_count > 0) {
        u64 avg_read_latency = stats.read_latency_sum / stats.read_count;
        printk(KERN_INFO "Average read latency: %llu us (max: %llu us)\n",
               avg_read_latency, stats.max_read_latency);
    }
    
    if (stats.write_count > 0) {
        u64 avg_write_latency = stats.write_latency_sum / stats.write_count;
        printk(KERN_INFO "Average write latency: %llu us (max: %llu us)\n",
               avg_write_latency, stats.max_write_latency);
    }
}
```

### I/O性能调优
```bash
# I/O调度器选择
echo mq-deadline | sudo tee /sys/block/sda/queue/scheduler
echo bfq | sudo tee /sys/block/sda/queue/scheduler
echo none | sudo tee /sys/block/sda/queue/scheduler

# 队列深度调优
echo 256 | sudo tee /sys/block/sda/queue/nr_requests
echo 1024 | sudo tee /sys/block/sda/queue/nr_requests

# 回写参数调优
echo 10 | sudo tee /proc/sys/vm/dirty_ratio
echo 5 | sudo tee /proc/sys/vm/dirty_background_ratio
echo 3000 | sudo tee /proc/sys/vm/dirty_expire_centisecs

# NUMA I/O亲和性
numactl --cpunodebind=0 --membind=0 dd if=/dev/zero of=test bs=1M count=1000

# 中断亲和性设置
echo 2 | sudo tee /proc/irq/24/smp_affinity  # SATA中断绑定到CPU1
```

要点
- 写路径可分：写入页缓存→标记 dirty→后台回写/显式 fsync→块层 I/O
- 观察 filemap* 与 writeback* 事件有助于定位“卡在谁”
- 高I/O等待时间（iowait）通常表示存储性能瓶颈
- 队列深度和调度器选择对SSD性能影响显著
- 回写拥塞可能导致应用阻塞，需要适当调整回写参数

---
## 6.5 网络与软中断：NET_RX/RCU 压力
### 网络性能分析框架
网络性能分析关注五个关键维度：带宽、延迟、丢包率、连接数、CPU利用率。现代Linux内核采用NAPI（New API）机制处理高吞吐量网络负载，通过软中断和轮询机制平衡延迟和吞吐量。

### 基础网络观测
```bash
sed -n '1,20p' /proc/softirqs | sed -n '1,20p'
# 开启网络与软中断事件（若存在）
cd /sys/kernel/tracing
[ -d events/net ] && echo 1 | sudo tee events/net/enable >/dev/null || true
[ -d events/irq ] && echo 1 | sudo tee events/irq/enable >/dev/null || true
# 制造本地 UDP 负载（可能丢包，属演示）
( nc -u -l -p 9001 >/dev/null & ); sleep 1; dd if=/dev/zero bs=16K count=256 2>/dev/null | nc -u 127.0.0.1 9001; pkill -f '^nc -u -l -p 9001'
sudo tail -n 60 trace | sed -n '1,60p'
```

### 高级网络性能分析
```c
// 摘自 projects/内核性能/network_performance_analyzer.c
static void analyze_network_performance(void)
{
    struct net_perf_stats {
        unsigned long net_rx_packets;
        unsigned long net_tx_packets;
        unsigned long net_rx_dropped;
        unsigned long net_tx_dropped;
        unsigned long net_rx_errors;
        unsigned long net_tx_errors;
        unsigned long softirq_net_rx;
        unsigned long softirq_net_tx;
        unsigned long softirq_rcu;
    } stats;
    
    int cpu;
    
    printk(KERN_INFO "=== Network Performance Analysis ===\n");
    
    // 统计每个CPU的软中断
    for_each_online_cpu(cpu) {
        stats.softirq_net_rx += kstat_softirqs_cpu(NET_RX_SOFTIRQ, cpu);
        stats.softirq_net_tx += kstat_softirqs_cpu(NET_TX_SOFTIRQ, cpu);
        stats.softirq_rcu += kstat_softirqs_cpu(RCU_SOFTIRQ, cpu);
    }
    
    printk(KERN_INFO "SoftIRQ counts:\n");
    printk(KERN_INFO "  NET_RX: %lu\n", stats.softirq_net_rx);
    printk(KERN_INFO "  NET_TX: %lu\n", stats.softirq_net_tx);
    printk(KERN_INFO "  RCU: %lu\n", stats.softirq_rcu);
    
    // 分析网络设备统计
    analyze_net_devices();
    
    // 分析NAPI性能
    analyze_napi_performance();
    
    // 分析RCU性能
    analyze_rcu_performance();
}

// 网络设备分析
static void analyze_net_devices(void)
{
    struct net_device *dev;
    
    printk(KERN_INFO "=== Network Device Analysis ===\n");
    
    rcu_read_lock();
    for_each_netdev_rcu(&init_net, dev) {
        struct rtnl_link_stats64 *stats = &dev->stats64;
        
        printk(KERN_INFO "Device %s:\n", dev->name);
        printk(KERN_INFO "  RX packets: %llu, bytes: %llu\n",
               stats->rx_packets, stats->rx_bytes);
        printk(KERN_INFO "  TX packets: %llu, bytes: %llu\n",
               stats->tx_packets, stats->tx_bytes);
        printk(KERN_INFO "  RX dropped: %llu, errors: %llu\n",
               stats->rx_dropped, stats->rx_errors);
        printk(KERN_INFO "  TX dropped: %llu, errors: %llu\n",
               stats->tx_dropped, stats->tx_errors);
        
        // 分析丢包率
        if (stats->rx_packets > 0) {
            u64 rx_drop_rate = (stats->rx_dropped * 100) / stats->rx_packets;
            if (rx_drop_rate > 1) {
                printk(KERN_WARNING "  High RX drop rate: %llu%%\n", rx_drop_rate);
            }
        }
        
        // 分析队列状态
        if (dev->qdisc) {
            printk(KERN_INFO "  Queuing discipline: %s\n", dev->qdisc->ops->id);
            printk(KERN_INFO "  Queue length: %u\n", dev->qdisc->q.qlen);
            
            if (dev->qdisc->q.qlen > 1000) {
                printk(KERN_WARNING "  High queue length detected\n");
            }
        }
    }
    rcu_read_unlock();
}

// NAPI性能分析
static void analyze_napi_performance(void)
{
    int cpu;
    
    printk(KERN_INFO "=== NAPI Performance Analysis ===\n");
    
    for_each_online_cpu(cpu) {
        struct softnet_data *sd = &per_cpu(softnet_data, cpu);
        struct napi_struct *napi;
        int napi_count = 0;
        
        printk(KERN_INFO "CPU %d softnet data:\n", cpu);
        printk(KERN_INFO "  processed: %u\n", sd->processed);
        printk(KERN_INFO "  dropped: %u\n", sd->dropped);
        printk(KERN_INFO "  time_squeeze: %u\n", sd->time_squeeze);
        
        // 分析NAPI状态
        list_for_each_entry(napi, &sd->poll_list, poll_list) {
            napi_count++;
            if (napi_count <= 5) {  // 只显示前5个
                printk(KERN_INFO "  NAPI %s: weight=%d, gro_count=%u\n",
                       napi->dev ? napi->dev->name : "unknown",
                       napi->weight, napi->gro_count);
            }
        }
        
        if (napi_count > 0) {
            printk(KERN_INFO "  Total NAPI instances: %d\n", napi_count);
        }
        
        // 分析性能问题
        if (sd->dropped > 1000) {
            printk(KERN_WARNING "CPU %d high packet drop count\n", cpu);
        }
        
        if (sd->time_squeeze > 1000) {
            printk(KERN_WARNING "CPU %d frequent time squeeze - consider increasing NAPI budget\n", cpu);
        }
    }
}

// RCU性能分析
static void analyze_rcu_performance(void)
{
    printk(KERN_INFO "=== RCU Performance Analysis ===\n");
    
    // 分析RCU回调队列
    struct rcu_state *rsp = &rcu_state;
    struct rcu_node *rnp;
    int cpu;
    
    printk(KERN_INFO "RCU state:\n");
    printk(KERN_INFO "  completed: %lu\n", rsp->completed);
    printk(KERN_INFO "  gpnum: %lu\n", rsp->gpnum);
    
    // 检查每个CPU的RCU状态
    for_each_online_cpu(cpu) {
        struct rcu_data *rdp = per_cpu_ptr(rsp->rda, cpu);
        
        printk(KERN_INFO "CPU %d RCU:\n", cpu);
        printk(KERN_INFO "  completed: %lu\n", rdp->completed);
        printk(KERN_INFO "  gpnum: %lu\n", rdp->gpnum);
        printk(KERN_INFO "  qlen: %lu\n", rdp->qlen);
        
        // 检测RCU积压
        if (rdp->qlen > 1000) {
            printk(KERN_WARNING "CPU %d high RCU callback backlog\n", cpu);
        }
        
        // 检测RCU停滞
        if (rdp->cpu_no_qs.b.norm) {
            printk(KERN_WARNING "CPU %d RCU quiescent state overdue\n", cpu);
        }
    }
}
```

### 网络协议栈性能分析
```c
// 摘自 projects/内核性能/network_stack_analyzer.c
static void analyze_network_stack(void)
{
    struct net_stack_stats {
        unsigned long skbs_allocated;
        unsigned long skbs_freed;
        unsigned long skbs_cloned;
        unsigned long skbs_shared;
        unsigned long gro_merged;
        unsigned long gso_segmented;
    } stats;
    
    printk(KERN_INFO "=== Network Stack Analysis ===\n");
    
    // 分析sk_buff使用情况
    stats.skbs_allocated = atomic_long_read(&skb_total_allocated);
    stats.skbs_freed = atomic_long_read(&skb_total_freed);
    
    printk(KERN_INFO "SKB statistics:\n");
    printk(KERN_INFO "  Allocated: %lu\n", stats.skbs_allocated);
    printk(KERN_INFO "  Freed: %lu\n", stats.skbs_freed);
    printk(KERN_INFO "  In-use: %lu\n", stats.skbs_allocated - stats.skbs_freed);
    
    // 分析GRO/GSO性能
    analyze_gro_gso_performance();
    
    // 分析网络内存使用
    analyze_network_memory();
}

// GRO/GSO性能分析
static void analyze_gro_gso_performance(void)
{
    printk(KERN_INFO "=== GRO/GSO Performance Analysis ===\n");
    
    // 分析GRO合并效果
    struct net_device *dev;
    unsigned long total_gro_merged = 0;
    unsigned long total_gso_segmented = 0;
    
    rcu_read_lock();
    for_each_netdev_rcu(&init_net, dev) {
        if (dev->rx_napi_gro_merged > 0) {
            printk(KERN_INFO "Device %s GRO merged: %lu\n", 
                   dev->name, dev->rx_napi_gro_merged);
            total_gro_merged += dev->rx_napi_gro_merged;
        }
        
        if (dev->tx_napi_gso_segmented > 0) {
            printk(KERN_INFO "Device %s GSO segmented: %lu\n",
                   dev->name, dev->tx_napi_gso_segmented);
            total_gso_segmented += dev->tx_napi_gso_segmented;
        }
    }
    rcu_read_unlock();
    
    printk(KERN_INFO "Total GRO merged: %lu\n", total_gro_merged);
    printk(KERN_INFO "Total GSO segmented: %lu\n", total_gso_segmented);
    
    // 评估优化效果
    if (total_gro_merged > 1000) {
        printk(KERN_INFO "GRO optimization effective - reducing packet processing overhead\n");
    }
}

// 网络内存分析
static void analyze_network_memory(void)
{
    struct net_mem_stats {
        unsigned long sk_mem_alloc;
        unsigned long sk_mem_limit;
        unsigned long tcp_mem_allocated;
        unsigned long tcp_mem_limit;
    } stats;
    
    printk(KERN_INFO "=== Network Memory Analysis ===\n");
    
    // 读取网络内存统计（全局）
    stats.sk_mem_alloc = atomic_long_read(&sk_memory_allocated);
    stats.sk_mem_limit = sysctl_sk_mem_max;
    
    printk(KERN_INFO "Socket memory:\n");
    printk(KERN_INFO "  Allocated: %lu KB\n", stats.sk_mem_alloc / 1024);
    printk(KERN_INFO "  Limit: %lu KB\n", stats.sk_mem_limit / 1024);
    
    if (stats.sk_mem_limit > 0) {
        u64 mem_usage = (stats.sk_mem_alloc * 100) / stats.sk_mem_limit;
        printk(KERN_INFO "  Usage: %llu%%\n", mem_usage);
        
        if (mem_usage > 80) {
            printk(KERN_WARNING "High network memory usage\n");
        }
    }
}
```

### 网络性能调优
```bash
# 网络栈参数调优
# 查看当前设置
cat /proc/sys/net/core/rmem_max
cat /proc/sys/net/core/wmem_max
cat /proc/sys/net/ipv4/tcp_rmem
cat /proc/sys/net/ipv4/tcp_wmem

# 调优建议
echo 134217728 | sudo tee /proc/sys/net/core/rmem_max  # 128MB
echo 134217728 | sudo tee /proc/sys/net/core/wmem_max  # 128MB
echo "4096 87380 134217728" | sudo tee /proc/sys/net/ipv4/tcp_rmem
echo "4096 65536 134217728" | sudo tee /proc/sys/net/ipv4/tcp_wmem

# NAPI参数调优
echo 600 | sudo tee /proc/sys/net/core/netdev_budget  # 增加NAPI预算
echo 2000 | sudo tee /proc/sys/net/core/netdev_budget_usecs

# 中断亲和性设置
cat /proc/interrupts | grep -E "(eth|ens|eno)" | head -5
echo 2 | sudo tee /proc/irq/24/smp_affinity  # 网络中断绑定到CPU1

# 启用RPS/RSS（多队列网络）
echo f | sudo tee /sys/class/net/eth0/queues/rx-0/rps_cpus
```

### 网络性能监控脚本
```bash
#!/bin/bash
# 网络性能监控脚本

echo "=== Network Performance Monitor ==="

# 1. 软中断统计
echo "1. SoftIRQ Statistics:"
cat /proc/softirqs | grep -E "(NET_RX|NET_TX|RCU)" | head -10

# 2. 网络设备统计
echo "2. Network Device Statistics:"
ip -s link show | grep -A10 -B5 "eth0\|ens" | head -20

# 3. 网络连接状态
echo "3. Connection Status:"
ss -tan | awk '{print $1}' | sort | uniq -c

# 4. TCP统计
echo "4. TCP Statistics:"
cat /proc/net/snmp | grep -A20 Tcp:

# 5. 网络缓冲区和队列
echo "5. Network Queues:"
cat /proc/net/softnet_stat | head -10

# 6. 持续监控
while true; do
    echo "=== $(date) ==="
    echo "SoftIRQ rates:"
    cat /proc/softirqs | grep -E "(NET_RX|NET_TX)" | awk '{print $1, $2+$3}' | head -5
    sleep 5
done
```

要点
- NET_RX 计数快速增长且 backlog 偏高 → 需关注 NAPI 预算、队列、qdisc、GRO/GSO
- RCU 回调堆积（/proc/softirqs 的 RCU）可能导致抖动
- 高丢包率通常表示网络拥塞或处理能力不足
- NAPI time_squeeze频繁表示预算不足，需要增加NAPI预算
- 网络内存使用过高可能导致OOM，需要适当调整缓冲区大小

---
## 6.6 锁与争用：低侵入式定位
### 锁性能分析框架
锁争用分析是性能调优的关键环节，主要关注自旋锁、互斥锁、读写锁等同步原语的使用效率。高锁争用会导致CPU时间浪费在忙等待上，降低系统整体吞吐量。

### 基础锁观测
只读观测（若启用 lock_stat）
```bash
[ -f /proc/lock_stat ] && head -n 40 /proc/lock_stat || echo "lock_stat not available"
```

### 高级锁分析
```c
// 摘自 projects/内核性能/lock_contention_analyzer.c
static void analyze_lock_contention(void)
{
    struct lock_stats {
        unsigned long spinlock_contention;
        unsigned long mutex_contention;
        unsigned long rwlock_contention;
        unsigned long total_lock_waits;
        unsigned long max_lock_hold_time;
        unsigned long avg_lock_hold_time;
    } stats;
    
    printk(KERN_INFO "=== Lock Contention Analysis ===\n");
    
    // 分析自旋锁争用
    analyze_spinlock_contention();
    
    // 分析互斥锁争用
    analyze_mutex_contention();
    
    // 分析读写锁争用
    analyze_rwlock_contention();
    
    // 分析RCU使用情况
    analyze_rcu_usage();
}

// 自旋锁争用分析
static void analyze_spinlock_contention(void)
{
    struct spinlock_stats {
        unsigned long total_spins;
        unsigned long total_contention_time;
        unsigned long max_contention_time;
        unsigned long contention_count;
    } stats = {0};
    
    printk(KERN_INFO "=== Spinlock Contention Analysis ===\n");
    
    // 遍历所有CPU的自旋锁统计
    int cpu;
    for_each_online_cpu(cpu) {
        struct spinlock_percpu_stats *percpu_stats = per_cpu_ptr(&spinlock_stats, cpu);
        
        stats.total_spins += percpu_stats->total_spins;
        stats.total_contention_time += percpu_stats->total_contention_time;
        stats.contention_count += percpu_stats->contention_count;
        
        if (percpu_stats->max_contention_time > stats.max_contention_time) {
            stats.max_contention_time = percpu_stats->max_contention_time;
        }
    }
    
    printk(KERN_INFO "Total spinlock statistics:\n");
    printk(KERN_INFO "  Total spins: %lu\n", stats.total_spins);
    printk(KERN_INFO "  Total contention time: %lu ns\n", stats.total_contention_time);
    printk(KERN_INFO "  Contention count: %lu\n", stats.contention_count);
    
    if (stats.contention_count > 0) {
        u64 avg_contention_time = stats.total_contention_time / stats.contention_count;
        printk(KERN_INFO "  Average contention time: %llu ns\n", avg_contention_time);
        printk(KERN_INFO "  Max contention time: %lu ns\n", stats.max_contention_time);
        
        if (avg_contention_time > 1000) {  // 1微秒
            printk(KERN_WARNING "High average spinlock contention time detected\n");
            printk(KERN_WARNING "Consider:\n");
            printk(KERN_WARNING "  1. Reducing lock hold time\n");
            printk(KERN_WARNING "  2. Using finer-grained locking\n");
            printk(KERN_WARNING "  3. Optimizing lock ordering\n");
        }
    }
}

// 互斥锁争用分析
static void analyze_mutex_contention(void)
{
    struct mutex_stats {
        unsigned long total_waits;
        unsigned long total_wait_time;
        unsigned long max_wait_time;
        unsigned long contention_count;
    } stats = {0};
    
    printk(KERN_INFO "=== Mutex Contention Analysis ===\n");
    
    // 分析全局互斥锁统计
    stats.total_waits = atomic_long_read(&mutex_total_waits);
    stats.total_wait_time = atomic_long_read(&mutex_total_wait_time);
    stats.contention_count = atomic_long_read(&mutex_contention_count);
    
    printk(KERN_INFO "Total mutex statistics:\n");
    printk(KERN_INFO "  Total waits: %lu\n", stats.total_waits);
    printk(KERN_INFO "  Total wait time: %lu ns\n", stats.total_wait_time);
    printk(KERN_INFO "  Contention count: %lu\n", stats.contention_count);
    
    if (stats.contention_count > 0) {
        u64 avg_wait_time = stats.total_wait_time / stats.contention_count;
        printk(KERN_INFO "  Average wait time: %llu ns\n", avg_wait_time);
        
        if (avg_wait_time > 10000) {  // 10微秒
            printk(KERN_WARNING "High average mutex wait time detected\n");
            printk(KERN_WARNING "Consider using RCU or other lock-free algorithms\n");
        }
    }
}

// 读写锁争用分析
static void analyze_rwlock_contention(void)
{
    struct rwlock_stats {
        unsigned long read_locks;
        unsigned long write_locks;
        unsigned long read_contention;
        unsigned long write_contention;
        unsigned long total_read_time;
        unsigned long total_write_time;
    } stats = {0};
    
    printk(KERN_INFO "=== RWLock Contention Analysis ===\n");
    
    // 分析读写锁使用模式
    stats.read_locks = atomic_long_read(&rwlock_read_locks);
    stats.write_locks = atomic_long_read(&rwlock_write_locks);
    stats.read_contention = atomic_long_read(&rwlock_read_contention);
    stats.write_contention = atomic_long_read(&rwlock_write_contention);
    
    printk(KERN_INFO "RWLock statistics:\n");
    printk(KERN_INFO "  Read locks: %lu (contention: %lu)\n", 
           stats.read_locks, stats.read_contention);
    printk(KERN_INFO "  Write locks: %lu (contention: %lu)\n",
           stats.write_locks, stats.write_contention);
    
    // 分析读写比例
    if (stats.read_locks + stats.write_locks > 0) {
        u64 read_ratio = (stats.read_locks * 100) / (stats.read_locks + stats.write_locks);
        printk(KERN_INFO "  Read ratio: %llu%%\n", read_ratio);
        
        if (read_ratio > 90) {
            printk(KERN_INFO "High read ratio - consider RCU for better scalability\n");
        }
    }
}

// RCU使用分析
static void analyze_rcu_usage(void)
{
    struct rcu_usage_stats {
        unsigned long rcu_read_locks;
        unsigned long rcu_sync_calls;
        unsigned long rcu_call_backs;
        unsigned long rcu_stalls;
    } stats = {0};
    
    printk(KERN_INFO "=== RCU Usage Analysis ===\n");
    
    // 分析RCU使用统计
    stats.rcu_read_locks = atomic_long_read(&rcu_read_lock_count);
    stats.rcu_sync_calls = atomic_long_read(&rcu_sync_call_count);
    stats.rcu_call_backs = atomic_long_read(&rcu_callback_count);
    
    printk(KERN_INFO "RCU statistics:\n");
    printk(KERN_INFO "  Read locks: %lu\n", stats.rcu_read_locks);
    printk(KERN_INFO "  Sync calls: %lu\n", stats.rcu_sync_calls);
    printk(KERN_INFO "  Callbacks: %lu\n", stats.rcu_call_backs);
    
    // 检查RCU停滞
    if (stats.rcu_stalls > 0) {
        printk(KERN_WARNING "RCU stalls detected: %lu\n", stats.rcu_stalls);
        printk(KERN_WARNING "Check for long-running RCU read-side critical sections\n");
    }
    
    // 推荐优化策略
    if (stats.rcu_sync_calls > stats.rcu_read_locks / 10) {
        printk(KERN_INFO "Consider reducing RCU sync calls for better performance\n");
    }
}
```

### 高级锁监控工具
```c
// 摘自 projects/内核性能/lock_monitor.c
static void monitor_lock_latency(void)
{
    struct lock_latency_tracker {
        struct hlist_head lock_hash[LOCK_HASH_SIZE];
        spinlock_t tracker_lock;
        u64 total_samples;
        u64 total_latency;
    } tracker;
    
    // 锁延迟采样函数
    void sample_lock_latency(void *lock, u64 latency, enum lock_type type)
    {
        struct lock_sample *sample;
        unsigned long flags;
        
        spin_lock_irqsave(&tracker.tracker_lock, flags);
        
        // 查找或创建锁样本
        sample = find_or_create_lock_sample(lock, type);
        if (sample) {
            sample->latency_sum += latency;
            sample->sample_count++;
            
            if (latency > sample->max_latency) {
                sample->max_latency = latency;
            }
            
            tracker.total_samples++;
            tracker.total_latency += latency;
        }
        
        spin_unlock_irqrestore(&tracker.tracker_lock, flags);
    }
    
    // 生成锁延迟报告
    void generate_lock_report(void)
    {
        int i;
        struct lock_sample *sample;
        
        printk(KERN_INFO "=== Lock Latency Report ===\n");
        printk(KERN_INFO "Total samples: %llu\n", tracker.total_samples);
        
        if (tracker.total_samples > 0) {
            u64 avg_latency = tracker.total_latency / tracker.total_samples;
            printk(KERN_INFO "Average latency: %llu ns\n", avg_latency);
        }
        
        // 输出热点锁
        for (i = 0; i < LOCK_HASH_SIZE; i++) {
            struct hlist_node *tmp;
            
            hlist_for_each_entry_safe(sample, tmp, &tracker.lock_hash[i], hash_node) {
                if (sample->sample_count > 100) {  // 高频锁
                    u64 avg_latency = sample->latency_sum / sample->sample_count;
                    
                    printk(KERN_INFO "Hot lock %p (type=%d):\n", 
                           sample->lock, sample->type);
                    printk(KERN_INFO "  Samples: %lu\n", sample->sample_count);
                    printk(KERN_INFO "  Avg latency: %llu ns\n", avg_latency);
                    printk(KERN_INFO "  Max latency: %llu ns\n", sample->max_latency);
                    
                    if (avg_latency > 1000) {
                        printk(KERN_WARNING "  High average latency detected\n");
                    }
                }
            }
        }
    }
}
```

### 锁争用调优策略
```bash
# 启用锁统计
echo 1 | sudo tee /proc/sys/kernel/lock_stat
echo 0 | sudo tee /proc/sys/kernel/lock_stat  # 禁用

# perf锁分析
sudo perf lock record -- sleep 3
sudo perf lock report --stdio | head -50

# 查看锁信息
cat /proc/lock_stat | head -30

# 锁调优建议
# 1. 减少锁持有时间
# 2. 使用更细粒度的锁
# 3. 考虑无锁算法（RCU、原子操作）
# 4. 优化锁顺序避免死锁
# 5. 使用读写锁优化读多写少场景
```

perf（若已安装）
```bash
sudo perf lock record -- sleep 3 && sudo perf lock report | head -n 40
```

要点
- 高频自旋/长等待提示临界区过长或抢占/NUMA 影响；考虑缩短临界区、提升局部性
- 锁争用监控应该关注平均等待时间和最大等待时间
- 读写比例分析有助于选择合适的同步机制
- RCU适合读多写少场景，可以显著提高可扩展性
- 锁延迟采样可以帮助识别性能瓶颈的具体位置

---
## 6.7 可复现实验与对照设计
### 性能分析实验框架
```bash
#!/bin/bash
# 内核性能综合测试框架

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
RESULT_DIR="${SCRIPT_DIR}/../results/performance_$(date +%Y%m%d_%H%M%S)"

# 创建结果目录
mkdir -p "$RESULT_DIR"

check_environment() {
    echo "检查性能测试环境..."
    
    # 检查工具
    for tool in perf fio iostat vmstat; do
        if ! command -v $tool >/dev/null 2>&1; then
            echo "警告: $tool 未找到"
        fi
    done
    
    # 检查内核配置
    if [ ! -f /sys/kernel/debug/tracing/available_events ]; then
        echo "警告: ftrace 不可用"
    fi
    
    # 保存系统信息
    uname -a > "$RESULT_DIR/system_info.txt"
    cat /proc/cpuinfo > "$RESULT_DIR/cpuinfo.txt"
    cat /proc/meminfo > "$RESULT_DIR/meminfo.txt"
    cat /proc/cmdline > "$RESULT_DIR/cmdline.txt"
}

# 1) CFS 公平性与迁移对缓存的影响
run_cfs_migration_experiment() {
    echo "运行CFS迁移实验..."
    
    cd /sys/kernel/tracing
    echo 0 > tracing_on
    echo nop > current_tracer
    echo 1 > events/sched/sched_switch/enable
    echo 1 > events/sched/sched_migrate_task/enable
    
    # 实验1：同一CPU运行多个任务
    echo "实验1：同一CPU多个任务"
    echo 1 > tracing_on
    ( taskset -c 0 sh -c 'yes >/dev/null' & ); P1=$!
    ( taskset -c 0 sh -c 'yes >/dev/null' & ); P2=$!
    sleep 10
    kill $P1 $P2 2>/dev/null || true
    echo 0 > tracing_on
    
    # 保存结果
    cp trace "$RESULT_DIR/cfs_same_cpu.trace"
    
    # 实验2：不同CPU运行任务
    echo "实验2：不同CPU任务"
    echo 1 > tracing_on
    ( taskset -c 0 sh -c 'yes >/dev/null' & ); P1=$!
    ( taskset -c 1 sh -c 'yes >/dev/null' & ); P2=$!
    sleep 10
    kill $P1 $P2 2>/dev/null || true
    echo 0 > tracing_on
    
    # 保存结果
    cp trace "$RESULT_DIR/cfs_diff_cpu.trace"
    
    # 分析结果
    echo "分析迁移事件..."
    grep -c "sched_migrate_task" "$RESULT_DIR/cfs_same_cpu.trace" > "$RESULT_DIR/migration_count_same.txt" || echo "0" > "$RESULT_DIR/migration_count_same.txt"
    grep -c "sched_migrate_task" "$RESULT_DIR/cfs_diff_cpu.trace" > "$RESULT_DIR/migration_count_diff.txt" || echo "0" > "$RESULT_DIR/migration_count_diff.txt"
    
    echo "CFS迁移实验完成"
}

# 2) 写回与尾延迟
run_writeback_latency_experiment() {
    echo "运行写回延迟实验..."
    
    cd /sys/kernel/tracing
    echo 0 > tracing_on
    echo nop > current_tracer
    echo 1 > events/writeback/enable
    echo 1 > events/block/block_rq_issue/enable
    echo 1 > events/block/block_rq_complete/enable
    
    # 实验1：小块+fsync
    echo "实验1：小块+fsync"
    echo 1 > tracing_on
    dd if=/dev/zero of=/tmp/writeback_test1 bs=4K count=1000 2>/dev/null
    sync
    echo 0 > tracing_on
    cp trace "$RESULT_DIR/writeback_small_fsync.trace"
    
    # 实验2：大块顺序写
    echo "实验2：大块顺序写"
    echo 1 > tracing_on
    dd if=/dev/zero of=/tmp/writeback_test2 bs=1M count=100 2>/dev/null
    sync
    echo 0 > tracing_on
    cp trace "$RESULT_DIR/writeback_large_seq.trace"
    
    # 清理
    rm -f /tmp/writeback_test1 /tmp/writeback_test2
    
    # 分析延迟
    echo "分析写回延迟..."
    ./scripts/analyze_writeback_latency.sh "$RESULT_DIR/writeback_small_fsync.trace" > "$RESULT_DIR/writeback_latency_small.txt"
    ./scripts/analyze_writeback_latency.sh "$RESULT_DIR/writeback_large_seq.trace" > "$RESULT_DIR/writeback_latency_large.txt"
    
    echo "写回延迟实验完成"
}

# 3) 软中断压力（UDP 本地突发）
run_softirq_pressure_experiment() {
    echo "运行软中断压力实验..."
    
    cd /sys/kernel/tracing
    echo 0 > tracing_on
    echo nop > current_tracer
    echo 1 > events/net/enable
    echo 1 > events/irq/enable
    echo 1 > events/napi/enable
    
    # 记录实验前软中断统计
    cat /proc/softirqs > "$RESULT_DIR/softirq_before.txt"
    
    # 产生UDP突发流量
    echo "产生UDP突发流量..."
    echo 1 > tracing_on
    ( nc -u -l -p 9001 >/dev/null & ); SERVER_PID=$!
    sleep 1
    dd if=/dev/zero bs=64K count=100 2>/dev/null | nc -u 127.0.0.1 9001
    sleep 2
    kill $SERVER_PID 2>/dev/null || true
    echo 0 > tracing_on
    
    # 记录实验后软中断统计
    cat /proc/softirqs > "$RESULT_DIR/softirq_after.txt"
    cp trace "$RESULT_DIR/softirq_pressure.trace"
    
    # 分析结果
    echo "分析软中断压力..."
    ./scripts/analyze_softirq_pressure.sh "$RESULT_DIR/softirq_before.txt" "$RESULT_DIR/softirq_after.txt" > "$RESULT_DIR/softirq_analysis.txt"
    
    echo "软中断压力实验完成"
}

# 4) 综合性能基准测试
run_comprehensive_benchmark() {
    echo "运行综合性能基准测试..."
    
    # CPU基准测试
    echo "CPU基准测试..."
    sysbench cpu --cpu-max-prime=20000 run > "$RESULT_DIR/cpu_benchmark.txt" 2>&1 || true
    
    # 内存基准测试
    echo "内存基准测试..."
    sysbench memory --memory-block-size=1K --memory-total-size=10G run > "$RESULT_DIR/memory_benchmark.txt" 2>&1 || true
    
    # I/O基准测试
    echo "I/O基准测试..."
    fio --name=randread --ioengine=libaio --iodepth=16 --rw=randread --bs=4k --direct=1 --size=1G --numjobs=4 --runtime=60 --group_reporting > "$RESULT_DIR/io_benchmark.txt" 2>&1 || true
    
    echo "综合基准测试完成"
}

# 生成报告
generate_report() {
    echo "生成性能分析报告..."
    
    cat > "$RESULT_DIR/performance_report.md" << 'EOF'
# 内核性能分析报告

生成时间: $(date)
系统信息: $(uname -a)

## 实验结果摘要

### CFS调度实验
- 同CPU任务迁移次数: $(cat "$RESULT_DIR/migration_count_same.txt")
- 不同CPU任务迁移次数: $(cat "$RESULT_DIR/migration_count_diff.txt")

### 写回延迟实验
- 小块+fsync延迟: $(grep "Average" "$RESULT_DIR/writeback_latency_small.txt" | head -1)
- 大块顺序写延迟: $(grep "Average" "$RESULT_DIR/writeback_latency_large.txt" | head -1)

### 软中断压力实验
- NET_RX增长: $(grep "NET_RX" "$RESULT_DIR/softirq_analysis.txt" | tail -1)
- 丢包统计: $(grep "dropped" "$RESULT_DIR/softirq_analysis.txt" | tail -1)

## 性能建议

1. **调度优化**: $(if [ "$(cat "$RESULT_DIR/migration_count_same.txt")" -gt "$(cat "$RESULT_DIR/migration_count_diff.txt")" ]; then echo "考虑CPU亲和性优化"; else echo "当前迁移策略合理"; fi)

2. **I/O优化**: $(if grep -q "High latency" "$RESULT_DIR/writeback_latency_small.txt"; then echo "考虑减少fsync频率"; else echo "I/O延迟正常"; fi)

3. **网络优化**: $(if grep -q "High drop" "$RESULT_DIR/softirq_analysis.txt"; then echo "需要增加NAPI预算或优化网络栈"; else echo "网络性能良好"; fi)

详细数据请查看对应的结果文件。
EOF
    
    echo "报告生成完成: $RESULT_DIR/performance_report.md"
}

# 主函数
main() {
    echo "=== Linux内核性能综合测试 ==="
    echo "结果将保存到: $RESULT_DIR"
    
    check_environment
    run_cfs_migration_experiment
    run_writeback_latency_experiment
    run_softirq_pressure_experiment
    run_comprehensive_benchmark
    generate_report
    
    echo "性能测试完成!"
    echo "结果位置: $RESULT_DIR"
}

main "$@"
```

### 实验结果分析
```bash
# 分析脚本示例
#!/bin/bash
# 分析写回延迟

TRACE_FILE="$1"
if [ -z "$TRACE_FILE" ]; then
    echo "Usage: $0 <trace_file>"
    exit 1
fi

echo "=== Writeback Latency Analysis ==="

# 提取写回事件
grep -E "writeback|block_rq" "$TRACE_FILE" > /tmp/writeback_events.txt

# 计算延迟
total_events=$(wc -l < /tmp/writeback_events.txt)
echo "Total I/O events: $total_events"

# 分析事件类型
writeback_events=$(grep -c "writeback" /tmp/writeback_events.txt)
block_events=$(grep -c "block_rq" /tmp/writeback_events.txt)
echo "Writeback events: $writeback_events"
echo "Block I/O events: $block_events"

# 估算平均延迟（简化计算）
if [ "$block_events" -gt 0 ]; then
    echo "Average I/O operations per event: $((total_events / block_events))"
fi

# 检查高延迟事件
high_latency=$(grep -c "latency.*[0-9]\{6,\}" /tmp/writeback_events.txt || echo "0")
echo "High latency events (>1ms): $high_latency"

if [ "$high_latency" -gt 10 ]; then
    echo "WARNING: High number of latency events detected"
fi

rm -f /tmp/writeback_events.txt
```

### 性能优化建议生成器
```bash
#!/bin/bash
# 根据实验结果生成优化建议

RESULT_DIR="$1"
if [ -z "$RESULT_DIR" ]; then
    echo "Usage: $0 <result_directory>"
    exit 1
fi

echo "=== Performance Optimization Recommendations ==="

# 分析CFS调度结果
if [ -f "$RESULT_DIR/migration_count_same.txt" ] && [ -f "$RESULT_DIR/migration_count_diff.txt" ]; then
    same_count=$(cat "$RESULT_DIR/migration_count_same.txt")
    diff_count=$(cat "$RESULT_DIR/migration_count_diff.txt")
    
    if [ "$same_count" -gt "$diff_count" ]; then
        echo "1. CPU调度优化:"
        echo "   - 当前同CPU任务迁移较多 ($same_count vs $diff_count)"
        echo "   - 建议：使用taskset设置CPU亲和性"
        echo "   - 建议：调整sched_migration_cost参数"
    fi
fi

# 分析I/O延迟结果
if [ -f "$RESULT_DIR/writeback_latency_small.txt" ]; then
    if grep -q "High latency" "$RESULT_DIR/writeback_latency_small.txt"; then
        echo "2. I/O优化:"
        echo "   - 检测到高I/O延迟"
        echo "   - 建议：调整vm.dirty_ratio和vm.dirty_background_ratio"
        echo "   - 建议：使用更合适的I/O调度器（mq-deadline/bfq）"
        echo "   - 建议：优化应用fsync调用频率"
    fi
fi

# 分析网络性能
if [ -f "$RESULT_DIR/softirq_analysis.txt" ]; then
    if grep -q "High drop" "$RESULT_DIR/softirq_analysis.txt"; then
        echo "3. 网络优化:"
        echo "   - 检测到高丢包率"
        echo "   - 建议：增加netdev_budget参数"
        echo "   - 建议：启用RPS/RSS多队列处理"
        echo "   - 建议：调整网络缓冲区大小"
    fi
fi

# 通用建议
echo "4. 通用优化:"
echo "   - 定期监控系统性能指标"
echo "   - 使用cgroup进行资源隔离"
echo "   - 考虑NUMA拓扑优化"
echo "   - 启用适当的内核调优参数"
```

### 实验结论
- **CFS调度**: 跨CPU迁移增加缓存失效；适度亲和可改善稳定性
- **写回延迟**: fsync频繁会放大尾延迟；顺序合并可改善吞吐
- **软中断压力**: 突发高峰下NAPI轮询与队列长度变化影响尾延迟
- **综合性能**: 需要系统性地考虑CPU、内存、I/O、网络的相互影响

---
## 6.8 优化方法论（安全优先）
- 先观测后优化：确认瓶颈面（CPU/内存/I/O/网络/锁）；避免“拍脑袋”调参
- 隔离与亲和：taskset/cgroup cpuset/irq affinity，减少迁移与争用（注意不要影响系统守护进程）
- 负载整形：批量化（合并小请求）、异步化（io_uring/工作队列）、限速（防止过载）
- 数据局部性：减少跨 NUMA 访问；必要时采用 numactl 策略与大页（THP/hugeTLB）评估
- 写路径：合并与延迟分配策略；避免“每次都 fsync”
- 风险提示：慎用 chrt/SCHED_FIFO 在通用系统；慎改 sysctl 永久参数；改动前后应有 A/B 与回退

---
## 6.9 常见坑与偏差
- 观测开销：function_graph、过密采样会扰动系统；先用轻量指标（vmstat/pressure），逐步加深
- 频率与节能：CPU 频率/睿频与 C 状态会影响测量；必要时固定策略后再评估
- 容器环境：cgroup 限额与命名空间隔离导致统计口径变化；建议对照宿主机
- 构造负载：yes/dd/nc 仅用于演示，生产负载特征差异巨大

---
## 6.10 小结
本章从“最小体检—目标采样—专项定位—对照实验”逐步深入，强调“先观测后优化”的流程与“安全可回退”的实践。配套脚本将落在 projects/内核性能/，用于一键复现实验与生成采样报告。

---
## 6.11 参考文献
[1] Linux kernel Documentation: admin-guide/perf*, tracing/*, scheduler/*, block/*, mm/*
[2] Brendan Gregg, Systems Performance (2nd), Addison-Wesley, 2020.
[3] Brendan Gregg, BPF Performance Tools, Addison-Wesley, 2019.
[4] Ingo Molnar 等：perf 工具与文档
[5] Steven Rostedt：ftrace/trace-cmd 文档与演讲
[6] LWN 专题：PSI、EEVDF、io_uring、blk-mq、BBR 等

