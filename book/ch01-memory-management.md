# 第1章 内核内存管理子系统研究（projects/内核内存管理）

本章以 Linux 6.6 LTS 为基线，对伙伴系统（Buddy）、slab 系列分配器、虚拟内存与页表、内存回收（LRU/MGLRU、kswapd、OOM）进行系统阐述。理论叙述中穿插来自仓库 projects/内核内存管理/ 的简短代码片段；完整实现以仓库源码为准。

> 环境建议：QEMU/KVM 或物理机；Ubuntu/Debian；内核头文件匹配正在运行的内核；具备 root 权限以加载内核模块用于观测。

## 1.0 给新手的快速入门教程（5–15分钟）

学习目标
- 能看懂“伙伴系统/阶（order）/zone/碎片指数”等术语在输出中的含义
- 会编译并加载本章的观测模块，读取 /proc 接口并解读关键字段
- 会用 2–3 条命令粗略评估系统的内存碎片与回收状态

前置准备
- 系统为 Debian/Ubuntu 或类似发行版；具备 sudo/root
- 已安装内核头文件与工具链：`sudo apt-get install build-essential linux-headers-$(uname -r)`
- 建议在虚拟机或非生产环境中进行

步骤一：编译与加载内核观测模块
```bash
cd projects/内核内存管理
# 使用内核 Kbuild 方式构建当前目录下的 .c 模块
make -C /lib/modules/$(uname -r)/build M=$(pwd) modules
# 查看生成的模块
ls -l *.ko
# 加载模块（若模块名不确定，可用上一行输出的 .ko 文件名）
sudo insmod buddy_allocator.ko || sudo insmod ./$(ls *.ko | head -n1)
# 查看内核日志中模块启动信息
dmesg | tail -n 20
```

步骤二：读取 /proc 输出并理解字段
```bash
# 由模块创建的只读接口
cat /proc/buddy_status | sed -n '1,120p'
```
输出解读（面向入门者）
- Zone: 系统中的内存分区（例如 DMA/Normal）；不同分区的可用页与碎片情况不同
- Free pages: 该分区当前空闲页总数
- Order N: 以 2^N 页为单位的空闲块数量（例如 order 3 表示 8 页的连续块）
- 最大连续块越大，越容易成功分配大页/THP；若只看到低阶有空闲而高阶为 0，说明外部碎片较多

步骤三：触发一次小型分配-释放测试并观察日志
```bash
# 模块加载后会自动做一次多阶分配/释放并打印日志
# 你也可以多看几行日志了解不同 order 的成功/失败情况
dmesg | tail -n 60
```

步骤四：快速“体检”系统内存碎片
```bash
# 官方接口，适合与 /proc/buddy_status 交叉验证
cat /proc/buddyinfo
# 各 zone 的更多细节
sed -n '1,200p' /proc/zoneinfo
```
看到高阶（如 8、9、10）长期为 0，且分配大块（高 order）经常失败，往往意味着需要 compaction 或工作负载层面的优化（可读 1.6、附C）。

常见错误与排错
- error: linux headers not found → 安装 `linux-headers-$(uname -r)` 后重试
- insmod: invalid module format → 当前内核与构建用头文件版本不一致
- permission denied/operation not permitted → 使用 sudo/root；或检查内核启用了必要的 /proc 调试接口
- /proc/buddy_status 不存在 → 模块未成功加载，先 `dmesg` 查错

学习检查点（完成以下项代表你已入门）
- 能解释 /proc/buddy_status 中 Zone/Free pages/Order 的含义
- 能说出“为什么高阶空闲块数重要”，以及“碎片高时会影响哪些类型的分配（如 THP）”
- 知道用哪 2–3 条命令快速判断系统是否处于内存压力/碎片状态

---
## 1.1 概览与关键抽象
- 物理页（page）与“页阶数（order）”：伙伴系统按 2^order 的块进行分配与合并；
- 内核对象分配：slab/slub/slob 针对小对象的缓存与重用；
- 虚拟内存（VMA/Maple Tree）、页表层级（x86-64: PGD/P4D/PUD/PMD/PTE）、缺页异常与写时复制（COW）；
- 回收与压缩：传统 LRU、MGLRU（Multi-Gen LRU）、kswapd 背景回收、zswap/zram；
- OOM（内存不足）：基于 OOM 分数的淘汰策略与 cgroup 约束。

---
## 1.2 伙伴系统（Buddy）原理
- 空闲内存以按阶（order）分类的链表/位图维护；分配时自高阶向下分裂，释放时自底向上尝试与“伙伴”合并；
- 以区域（zone）为单位维护（DMA/Normal/HighMem 等），NUMA 场景需考虑节点亲和与远程访问代价；
- 优点：分配/释放的对数复杂度、易于大块分配；缺点：外部碎片，难以长期维持大连续块。

代码片段（从 buddy 分配观测模块中摘取，查看各阶空闲块）：

```c
// 摘自 projects/内核内存管理/buddy_allocator.c
for_each_populated_zone(zone) {
    for (order = 0; order < MAX_ORDER; order++) {
        unsigned long n = zone->free_area[order].nr_free;
        if (n > 0)
            printk(KERN_INFO, "Order %d: %lu blocks\n", order, n);
    }
}
```

---
## 1.3 实现要点与观测
- 关键数据结构：`struct zone`、`free_area[order]`、`struct page` 标志位（buddy/迁移类型等）；
- 分配路径：`alloc_pages(gfp, order)` → 可能触发回收/压缩；释放路径：`__free_pages(page, order)`；
- 碎片度衡量：最大可用阶 vs. 总空闲页；
- 实践建议：分配失败时探查 `dmesg`、`/proc/zoneinfo`、`/proc/buddyinfo`。

代码片段（演示按不同阶分配并立刻释放，用于快速健诊）：

```c
// 摘自 projects/内核内存管理/buddy_allocator.c
define order from 0..3: page = alloc_pages(GFP_KERNEL, order);
if (page) __free_pages(page, order);
```

---
## 1.4 slab/slub 分配器
- slab 家族面向小对象，提供对象缓存（kmem_cache），支持构造/析构回调、着色、离 CPU/NUMA 亲和；
- SLUB 是主流默认实现，强调简化元数据与并发扩展性；SLOB 面向极小内存设备；
- 典型 API：`kmem_cache_create`、`kmem_cache_alloc/free`、`kmalloc/kzalloc/kfree`；
- 观测：`/sys/kernel/slab/*/` 统计；结合 ftrace `kmalloc` 事件与 eBPF 跟踪热点对象。

计划补充实现：`projects/内核内存管理/slab_analysis.c`，用于比较 kmem_cache 与 kmalloc 的延迟、失败率与 cache 命中特征。

---
## 1.5 虚拟内存与页表（VMA/Maple Tree）
- 进程地址空间由 VMA 片段描述（6.1 起引入 Maple Tree 取代 VMA 红黑树）；
- 缺页处理：缺页异常 → 查找 VMA → 建立页表项（可能触发 COW/分配）；
- TLB、一致性与 shootdown；透明大页（THP）与 hugeTLB 的取舍。

计划补充实现：`projects/内核内存管理/vmm_research.c`，在缺页路径注入 tracepoint 并统计 COW/匿名页/文件页比例。

---
## 1.6 内存回收与压力（LRU/MGLRU、kswapd、OOM）
- LRU：活跃/不活跃链表，冷热分层；回收优先匿名/文件页的策略权衡；
- MGLRU：多代模型以更精细刻画热度，显著改进回收效率与尾延迟；
- kswapd：后台回收线程，水位线触发；direct reclaim：分配路径直接回收；
- OOM：基于分数选择牺牲进程，cgroup 限制与 PSI 内存压力指标。

计划补充实现：`projects/内核内存管理/memory_reclaim.c`，配合 eBPF 脚本记录回收事件、页错误与 kswapd 活动关联。

---
## 1.7 可复现实验与评测设计
1) 碎片与大块分配能力
- 步骤：逐步升高 order 进行分配；记录成功阶、碎片指数、kswapd 活动；
- 指标：最大连续块、失败率、分配延迟、回收触发率。

2) slab 与 kmalloc 对比
- 步骤：构建 kmem_cache 与循环分配/释放；统计每秒分配数与平均/尾延迟；
- 工具：ftrace function_graph、perf stat/record、BPF tracepoints。

3) MGLRU 效果
- 步骤：开启/关闭 MGLRU，对比压力场景（filescan/anon）；
- 指标：回收量、缺页率、尾延迟；
- 参考：admin-guide/mm/multigen_lru.rst。

实验脚本示例（片段）：

```bash
# 观察 buddy 与回收相关接口
cat /proc/buddyinfo
cat /proc/zoneinfo | sed -n '1,120p'
# ftrace 跟踪 alloc/free（需 root）
echo 1 > /sys/kernel/debug/tracing/events/kmem/enable
sleep 5; cat /sys/kernel/debug/tracing/trace | head
```

---
## 1.8 当前研究趋势与难点
- Folio 改造持续推进，减少 page 元数据开销并统一文件/匿名页路径；
- Maple Tree 在 VMA 管理中的可维护性与性能收益；
- MGLRU、DAMON 在大规模内存场景的观测与回收决策；
- THP/hugeTLB 的策略优化与 NUMA-aware 分配；
- Rust for Linux 在内存子系统中的探索（以驱动/外围为主，核心路径谨慎推进）。

---
## 1.9 小结
本章以理论为先，结合仓库中 buddy 分配器观测模块阐明了 Linux 内核的内存分配、缓存与回收路径；配套实验提供了可复现的方法以量化各策略对吞吐与延迟的影响，为后续章节（调度、文件系统、性能、安全）中的跨主题关联分析奠定基础。

---

---
### 附：进阶补充与实务细节（扩展理论与代码片段）

#### A. GFP 标志与迁移类型（theory）
- 常见 GFP：`GFP_KERNEL`（可睡眠，最常用）、`GFP_ATOMIC`（不可睡眠，中断/自旋锁内）、`GFP_NOWAIT`、`GFP_HIGHUSER_MOVABLE`（适合可迁移页）。
- 迁移类型（migratetype）：`MIGRATE_UNMOVABLE/MOVABLE/RECLAIMABLE/CMA/ISOLATE` 等，影响大块分配与碎片。
- 实务：优先使用与上下文匹配的 GFP 掩码；在持锁/中断上下文避免可能睡眠的分配。

代码片段（片段化示例，按语境选择 GFP）：
```c
// 不能睡眠的上下文（如中断）中，避免 GFP_KERNEL：
void *p = kmalloc(256, GFP_ATOMIC);
// 常规内核线程/进程上下文可用：
void *q = kmalloc(256, GFP_KERNEL);
```

#### B. Per-CPU Page List（PCP）、水位线与回收（theory）
- PCP：降低分配/释放热点锁争用的每 CPU 页缓存；批量出入队提升吞吐。
- 水位线：`min/low/high` 控制回收触发；`kswapd` 试图维持在 `high` 以上。
- 直接回收与压缩：分配路径可能触发 direct reclaim 与 compaction，严重时导致明显延迟抖动。

#### C. 内存紧缩与 kcompactd（theory）
- 目的：通过页迁移将分散的空闲页“整形”为高阶连续块，提升 THP/大块分配成功率。
- 守护线程：`kcompactd` 按需工作；也可通过 sysfs/proc 接口显式触发。

#### D. 伙伴碎片度指标（code+theory）
- 指标思想：总空闲页 vs. 最大连续块所占比例，比例越低碎片越严重。
- 代码片段（摘自碎片分析逻辑）：
```c
// 摘自 projects/内核内存管理/buddy_allocator.c
if (total_free > 0) {
    unsigned long frag = 100 - (100 * (1UL << largest_block)) / total_free;
    printk(KERN_INFO, "  Fragmentation index: %lu%%\n", frag);
}
```

#### E. THP/hugeTLB 与策略开关（theory+ops）
- THP：透明大页，匿名页路径为主；`madvise(MADV_HUGEPAGE/MADV_NOHUGEPAGE)` 可控粒度。
- hugeTLB：显式保留大页池，确定性更强；适合数据库/高性能场景。
- 常用开关（root）：
```bash
# THP 策略
cat /sys/kernel/mm/transparent_hugepage/enabled
# 建议按 workload 控制：always / madvise / never
# khugepaged 扫描
cat /sys/kernel/mm/transparent_hugepage/khugepaged/* | head -n 5
```

#### F. zswap/zram（theory）
- zswap：压缩的 swap 缓冲，写回后端 swap 之前的内存压缩层。
- zram：基于 RAM 的压缩块设备，常作无后端 swap 的内存压力缓冲。
- 权衡：zswap 扩容弹性更好；zram 配置简便但占用内存上限需谨慎评估。

#### G. NUMA 策略（theory）
- `mpol`：`preferred/interleave/bind` 等策略；远程访问代价影响延迟与带宽。
- 实务：长生命周期、带宽敏感对象宜倾向本地节点；跨核/跨进程共享冷热分层。

#### H. /proc 接口与 seq_file（code）
- 通过 `proc_create` + `seq_file` 输出观测数据，避免一次性分配大缓冲。
- 代码片段（只展示关键行）：
```c
// 摘自 projects/内核内存管理/buddy_allocator.c
static int buddy_proc_show(struct seq_file *m, void *v)
{
    seq_printf(m, "Buddy Allocator Status\n\n");
    for_each_populated_zone(zone) {
        seq_printf(m, "Zone: %s\n", zone->name);
        // ...逐阶输出...
    }
    return 0;
}
```

#### I. 调试与观测建议（ops）
```bash
# LRU/MGLRU 观测
cat /sys/kernel/mm/lru_gen/enabled 2>/dev/null || echo "MGLRU not available"
# PSI 内存压力
cat /proc/pressure/memory
# kmalloc 跟踪（ftrace）
echo 1 > /sys/kernel/debug/tracing/events/kmem/enable
# 伙伴与 zone
cat /proc/buddyinfo; cat /proc/zoneinfo | sed -n '1,200p'
```

#### J. 常见陷阱（tips）
- 在自旋锁/中断上下文分配使用 `GFP_ATOMIC`，切勿调用可能睡眠的 API。
- 大块分配（高阶）成功率对碎片/紧缩高度敏感，尽量采用可迁移类型与预热紧缩。
- 与 slab/SLUB 配合时关注对象对齐与构造/析构成本，避免“大对象”落入伙伴系统。

（延伸阅读）
- LWN: Folios/Maple Tree/MGLRU 系列文章
- admin-guide/mm/*：THP、multigen LRU、damon、zswap、zram 等专题
- Mel Gorman: compaction 与碎片化系列分析

## 1.10 参考文献
[1] Linux kernel Documentation: mm/ 与 admin-guide/mm/*，https://www.kernel.org/doc/html/latest/
[2] Ulrich Drepper, What Every Programmer Should Know About Memory, 2007.
[3] Matthew Wilcox, Folios（LWN 系列与演讲），https://lwn.net/
[4] Liam R. Howlett, Maple Tree（LSFMM/Plumbers 资料），https://lwn.net/ and conference proceedings
[5] Yu Zhao, Multi-Gen LRU（内核文档与 LWN 报道），admin-guide/mm/multigen_lru.rst
[6] SeongJae Park, DAMON: Data Access MONitor（文档与 LWN），Documentation/admin-guide/mm/damon/
[7] Mel Gorman, Understanding the Linux Virtual Memory Manager, 2004.
[8] Robert Love, Linux Kernel Development, 3rd, 2010（内存章节）.
[9] Transparent Huge Pages（内核文档与社区讨论），Documentation/admin-guide/mm/transhuge.rst
[10] Linux 源码：mm/、include/linux/mm*.h（以对应版本为准）

