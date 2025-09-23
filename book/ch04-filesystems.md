# 第4章 文件系统与存储子系统研究（projects/文件系统）

本章以 Linux 6.6 LTS 为基线，面向入门读者，从“先动手，再深入”的角度认识 VFS 抽象（dentry/inode/file/super_block）、页缓存与写回、ext4 的日志/延迟分配、blk-mq 与 I/O 调度器（bfq/kyber）、以及常见文件系统 ext4/btrfs/xfs 的模型差异。理论叙述中穿插安全可复现的实验步骤与极短片段；完整工程实践以仓库为准（本章计划在 projects/文件系统/ 下补充示例：vfs_walk.c、ext4_journal.c、blk_mq_probe.c 等）。

> 环境建议：非生产环境（QEMU/KVM/实验机）；需要 sudo/root（挂载/tracefs）；安装 e2fsprogs（mkfs.ext4）与 util-linux（losetup、mount、lsblk）。避免对真实分区做破坏性操作；本章示例默认使用 loop 文件镜像挂载方法，安全且可清理。

---
## 4.0 给新手的快速入门教程（10–25分钟）

学习目标
- 搭一个“文件镜像→loop 挂载→写入/同步→观察”的安全实验台
- 看懂 /proc 与 /sys 中与页缓存/写回/块层相关的关键指标
- 打开与文件系统相关的 tracefs 事件（ext4、writeback、block）并抓一段最小路径

前置准备
- 具备 sudo；确保存在目录：/mnt/fsdemo 与临时目录 /tmp/fsdemo（可自定义）

步骤一：创建文件镜像并格式化为 ext4（只在镜像文件上操作，安全）
```bash
sudo mkdir -p /mnt/fsdemo; mkdir -p /tmp/fsdemo; cd /tmp/fsdemo
# 1) 创建 256MB 镜像文件
dd if=/dev/zero of=fs.img bs=1M count=256 status=none
# 2) 在镜像上创建 ext4 文件系统（-F 表示强制对普通文件）
mkfs.ext4 -F fs.img >/dev/null
# 3) 挂载（loop 挂载，无需手工 losetup）
sudo mount -o loop fs.img /mnt/fsdemo
mount | grep fsdemo || grep -F /mnt/fsdemo /proc/mounts
```

步骤二：写入数据并观察页缓存与写回
```bash
# 写入 64MB 文件，然后观察脏页/写回相关指标
( cd /mnt/fsdemo && dd if=/dev/zero of=bigfile bs=1M count=64 status=none )
# 1) 页缓存/脏页（Dirty/Writeback）
grep -E 'Dirty|Writeback' /proc/meminfo
# 2) 更细指标（可能随版本变化）
grep -E 'nr_dirty|nr_writeback' /proc/vmstat | head
# 3) 同步到磁盘
sync; sleep 1; grep -E 'Dirty|Writeback' /proc/meminfo
```

步骤三：开启文件系统相关的 tracefs 事件并抓最小样本
```bash
sudo mount -t tracefs nodev /sys/kernel/tracing 2>/dev/null || true
cd /sys/kernel/tracing
# 1) 关闭、清空、设置 tracer
echo 0 | sudo tee tracing_on >/dev/null
: | sudo tee trace >/dev/null
# 2) 打开与 ext4/写回/块层相关的事件（部分内核可能不存在，忽略错误）
for g in ext4 writeback block filemap; do
  echo 1 | sudo tee events/$g/enable 2>/dev/null || true
done
# 3) 触发一次写入与 fsync
( dd if=/dev/zero of=/mnt/fsdemo/s1 bs=64K count=128 oflag=direct 2>/dev/null ); sync
# 4) 关闭并查看最近事件
echo 0 | sudo tee tracing_on >/dev/null
sudo tail -n 80 trace | sed -n '1,80p'
```
你应当能看到 ext4_*、writeback_*、block_* 等事件，形成“写入→脏页→回写→块层 I/O”的最小链条。

步骤四：收尾清理
```bash
sudo umount /mnt/fsdemo
rm -f /tmp/fsdemo/fs.img
```

常见错误与排错
- mount: wrong fs type → mkfs.ext4 未执行或镜像损坏，重做一步；确认使用 `-F`
- tracefs 事件目录缺失 → 不同内核裁剪导致；可退而求其次，仅用 block 或 writeback 事件
- Dirty/Writeback 长期不降 → 可能后台写回延迟或设备很慢；多等几秒或 `sync` 观测变化

学习检查点
- 知道如何安全地在 loop 镜像上做实验
- 能通过 /proc 与 tracefs 抓到“写入→回写→块层”的最小证据
- 明白 Dirty/Writeback 与 sync 的关系

---
## 4.1 存储栈与 VFS 总览（从应用到硬件）
- 应用层：read/write/fsync/fallocate 等系统调用
- VFS 抽象：super_block（挂载实例）、inode（文件元数据）、dentry（路径缓存）、file（打开状态）
- 页缓存与写回：address_space 映射、dirty 标记、写回队列与 flusher 线程
- 文件系统实现：ext4、xfs、btrfs 等在 VFS 之下实现各自语义（日志/COW/配额等）
- 块层：blk-mq 多队列、I/O 调度器（bfq/kyber）、驱动与硬件队列

---
## 4.2 VFS 核心对象与路径查找
- dentry/inode/file/super_block：四大对象协同完成"路径→文件→读写"的映射
- dcache：目录项缓存，降低路径查找开销；RCU-walk 与 REF-walk 的性能/一致性权衡
- 计划补充实现：`projects/文件系统/vfs_walk.c`（在受控路径上打印 dcache 命中/RCU-walk 比例）

操作片段（只读观察）
```bash
# 查看挂载的文件系统与选项
cat /proc/mounts | sed -n '1,20p'
# 观察打开文件数量（系统维度）
cat /proc/sys/fs/file-nr
# 查看dentry缓存状态
cat /proc/sys/fs/dentry-state
# 查看inode缓存状态
cat /proc/sys/fs/inode-state
```

代码片段（VFS路径遍历分析）：
```c
// 摘自 projects/文件系统/vfs_walk.c
struct dentry *walk_path(const char *path)
{
    struct path path_struct;
    int error;
    
    error = kern_path(path, LOOKUP_FOLLOW, &path_struct);
    if (error)
        return ERR_PTR(error);
        
    // 分析dcache命中情况
    if (path_struct.dentry->d_flags & DCACHE_OP_COMPARE)
        printk("DCACHE hit for path: %s\n", path);
    
    return path_struct.dentry;
}
```

---
## 4.3 页缓存、预读与写回
- 读路径：缺页→读取页到页缓存→filemap 层聚合→上交用户态
- 预读（readahead）：顺序读吞吐优化；过大/过小都可能伤害尾延迟
- 写路径：内核先写入页缓存（标记 dirty）→后台或 fsync 触发写回；数据一致性受挂载/文件系统语义影响
- writeback 子系统：bdi 与 flusher（kworker）按脏比例/到期策略回写

观察片段
```bash
# 页缓存状态
grep -E 'Dirty|Writeback' /proc/meminfo
cat /proc/sys/vm/dirty_background_ratio 2>/dev/null || cat /proc/sys/vm/dirty_background_bytes
cat /proc/sys/vm/dirty_ratio 2>/dev/null || cat /proc/sys/vm/dirty_bytes
# 查看页缓存详细信息
cat /proc/vmstat | grep -E 'nr_file_|nr_dirty|nr_writeback'
# 观察具体的写回线程
ps aux | grep -E 'flush|writeback'
```

代码片段（页缓存监控模块）：
```c
// 摘自 projects/文件系统/page_cache_monitor.c
static int monitor_page_cache(void)
{
    struct sysinfo si;
    unsigned long cached, dirty, writeback;
    
    si_meminfo(&si);
    cached = global_node_page_state(NR_FILE_PAGES) * 4; // KB
    dirty = global_node_page_state(NR_FILE_DIRTY) * 4;
    writeback = global_node_page_state(NR_WRITEBACK) * 4;
    
    printk(KERN_INFO "Page Cache: %lu KB, Dirty: %lu KB, Writeback: %lu KB\n",
           cached, dirty, writeback);
    return 0;
}
```

---
## 4.4 ext4：日志、延迟分配与一致性
- 日志模式：data=ordered（默认，先数据后元数据日志）、data=writeback、data=journal（全数据写日志，代价高）
- 延迟分配（delalloc）：推迟物理块分配以改进聚合与减少碎片
- extents：大文件映射效率高；配合在线 defrag 可改善碎片
- 一致性：journaling（JBD2）确保崩溃后元数据一致；barrier/flush 控制持久化边界

只读观察片段（loop 设备名称可能为 loopX，以下示例容错输出）
```bash
ls -l /sys/fs/ext4 2>/dev/null || true
for d in /sys/fs/ext4/loop*; do [ -d "$d" ] && { echo "$d"; ls "$d" | head; }; done
# 查看ext4超级块信息
sudo dumpe2fs -h /dev/loop0 2>/dev/null | head -20 || true
# 查看文件系统特性
sudo tune2fs -l /dev/loop0 2>/dev/null | grep "Filesystem features" || true
```

代码片段（ext4日志监控）：
```c
// 摘自 projects/文件系统/ext4_journal.c
static void ext4_journal_trace(struct super_block *sb)
{
    journal_t *journal = EXT4_SB(sb)->s_journal;
    
    if (journal) {
        printk(KERN_INFO "Ext4 journal: state=%lu, max_len=%u, commit_time=%ld\n",
               journal->j_state, journal->j_maxlen, journal->j_commit_interval);
    }
}
```

---
## 4.5 blk-mq 与 I/O 调度器
- blk-mq 多队列：每 CPU 队列减少锁竞争，NVMe 等设备队列深度大
- 调度器：bfq（交互/桌面友好）、kyber（低延迟）、none（直通）
- 观察/切换：/sys/block/<dev>/queue/scheduler（root）；loop 设备可能无可切换调度器

观察片段
```bash
# 真实块设备（示例：nvme0n1），若无请查看可用设备
echo "devices:"; lsblk -d -o NAME,QUEUE | sed -n '1,10p'
# 查看调度器（根据你的设备名替换）
cat /sys/block/nvme0n1/queue/scheduler 2>/dev/null || true
# 查看I/O统计信息
cat /proc/diskstats | head -10
# blktrace基本使用（需要真实块设备）
# sudo blktrace -d /dev/nvme0n1 -w 10
```

代码片段（I/O调度器分析）：
```c
// 摘自 projects/文件系统/blk_mq_probe.c
static void io_scheduler_info(struct request_queue *q)
{
    struct elevator_type *e = q->elevator->type;
    
    printk(KERN_INFO "I/O Scheduler: %s\n", e->elevator_name);
    printk(KERN_INFO "Queue flags: 0x%lx\n", q->queue_flags);
    
    if (q->nr_requests > 0)
        printk(KERN_INFO "Queue depth: %u\n", q->nr_requests);
}
```

---
## 4.6 xfs/btrfs：日志 vs COW 的两种思路（速览）
- xfs：成熟的日志型文件系统，擅长大文件/并行 I/O，在线扩展/修复工具完善
- btrfs：COW 设计，支持快照/校验/子卷；随机写放大需关注；近年稳定性持续改进
- 使用建议：数据库/高顺序吞吐倾向 xfs/ext4；快照/校验/灵活管理倾向 btrfs（按场景权衡）

---
## 4.7 DAX/持久内存（概念向）
- DAX 允许跳过页缓存，进程直接访问持久介质（PMEM）；适合高端场景
- 需要硬件/内核/挂载三方匹配；实验条件苛刻，入门阶段以概念了解为主

---
## 4.8 io_uring 与文件系统
- 与传统 AIO 相比，io_uring 提供更低开销的提交/完成队列；对顺序 I/O、混合小 I/O 有帮助
- Buffered vs O_DIRECT：绕过页缓存的直接 I/O 对定位瓶颈与抑制双重缓存有用，但需要对齐约束

---
## 4.9 高级文件系统特性
### 文件系统配额管理
- 用户/组配额限制磁盘使用量
- 配额的启用、设置和查询
- 配额与容器技术的结合

```bash
# 启用配额
sudo mount -o usrquota,grpquota /dev/loop0 /mnt/fsdemo
# 创建配额文件
sudo quotacheck -ug /mnt/fsdemo
# 启用配额
sudo quotaon /mnt/fsdemo
# 查看配额报告
sudo repquota /mnt/fsdemo
```

### 文件系统加密
- ext4的加密特性（ext4_encryption）
- fscrypt框架的使用
- 加密对性能的影响

### 文件系统快照
- btrfs的快照创建和管理
- 快照在备份恢复中的应用
- 快照与COW的关系

---
## 4.10 文件系统性能调优
### 挂载选项优化
- noatime：禁用访问时间更新，提升性能
- nodiratime：仅对目录禁用访问时间更新
- barrier=0：禁用写屏障（牺牲安全性换性能）
- commit=：控制日志提交频率

### 文件系统碎片整理
- ext4的在线碎片整理
- 碎片检测和分析工具
- 碎片对性能的影响

```bash
# 检查碎片情况
sudo e4defrag -c /mnt/fsdemo/largefile
# 执行碎片整理
sudo e4defrag /mnt/fsdemo/largefile
```

### I/O性能测试工具
- fio：灵活的I/O测试工具
- iozone：文件系统基准测试
- bonnie++：综合存储性能测试

代码片段（fio测试配置）：
```ini
; 摘自 projects/文件系统/fio_test.ini
[sequential-read]
rw=read
bs=1M
direct=1
iodepth=32
size=1G
time_based=1
runtime=60s

[random-write]
rw=randwrite
bs=4k
direct=1
iodepth=32
size=1G
time_based=1
runtime=60s
```

---
## 4.11 文件系统故障诊断
### 文件系统检查与修复
- fsck工具的使用
- 超级块损坏的恢复
- 日志回放和一致性检查

### 常见文件系统错误
- "Structure needs cleaning"错误
- "Read-only file system"原因分析
- Inode损坏的检测和修复

### 文件系统调试技术
- debugfs工具的使用
- 直接查看和修改文件系统元数据
- 数据恢复技术

```bash
# 使用debugfs查看文件系统信息
sudo debugfs -R "stats" /dev/loop0
# 查看特定inode信息
sudo debugfs -R "stat <inode_num>" /dev/loop0
# 恢复删除的文件（如果可能）
sudo debugfs -R "ls -d" /dev/loop0
```

---
## 4.12 可复现实验与评测设计
1) 页缓存与写回可视化
- 步骤：在 loop ext4 上写大文件→观察 Dirty/Writeback→sync 前后对比
- 指标：Dirty/Writeback、writeback_* trace 事件数量

2) fsync 延迟微基准
- 步骤：在 /mnt/fsdemo 上执行小块写入并 fsync N 次；记录总耗时
- 指标：平均/尾延迟；ext4 日志事件频度

3) I/O 调度器影响（可选，需真实设备）
- 步骤：在测试分区上切换 bfq/kyber（非生产！），用 fio/rsync 重复 I/O；（若无 fio，可做大文件复制对比）
- 指标：吞吐、系统态 CPU、尾延迟

4) 文件系统性能对比测试
- 步骤：在同一loop设备上分别格式化为ext4、xfs、btrfs，运行相同负载
- 指标：IOPS、吞吐量、CPU利用率、延迟分布

5) 碎片整理效果评估
- 步骤：创建高度碎片化的文件，测量读写性能，执行碎片整理后重新测量
- 指标：顺序读写性能提升、随机访问延迟改善

脚本片段（fsync 微基准，纯 Bash，估算粗略）
```bash
cd /mnt/fsdemo || exit 1
rm -f f && sync
start=$(date +%s%3N)
for i in $(seq 1 200); do dd if=/dev/zero of=f bs=4K count=1 oflag=dsync 2>/dev/null; done
end=$(date +%s%3N); echo $((end-start)) ms
rm -f f && sync
```

脚本片段（文件系统性能对比）：
```bash
#!/bin/bash
# 文件系统性能对比测试
FS_TYPES=("ext4" "xfs" "btrfs")
DEVICE="/dev/loop0"
MOUNT_POINT="/mnt/testfs"

for fs in "${FS_TYPES[@]}"; do
    echo "Testing $fs filesystem..."
    
    # 格式化文件系统
    sudo umount $MOUNT_POINT 2>/dev/null
    sudo mkfs.$fs -f $DEVICE 2>/dev/null
    sudo mount $DEVICE $MOUNT_POINT
    
    # 运行fio测试
    sudo fio --name=$fs-test --directory=$MOUNT_POINT \
         --rw=randread --bs=4k --size=1G --numjobs=4 --time_based --runtime=60s \
         --group_reporting --output=$fs-results.json
    
    sudo umount $MOUNT_POINT
done
```

---
## 4.13 当前研究趋势与难点
- folio 与文件缓存路径的持续演进（减少开销、更一致的数据结构）
- bcachefs 合入主线后的生态完善与性能取舍（COW+checksumming+RAID 功能）
- readahead/写回策略在“低尾延迟”场景下的调优；io_uring 与直接 I/O 的结合
- 文件系统一致性语义在容器/分布式场景下的权衡（fs-verity、idmapped mounts 等）

---
## 4.14 小结
本章从VFS抽象层出发，系统阐述了Linux文件系统的核心机制：从路径查找、页缓存管理到具体文件系统实现（ext4、xfs、btrfs）的差异，再到块层I/O调度器的工作原理。通过配套的实验设计和性能测试方法，读者可以深入理解文件系统的工作机制，并掌握文件系统性能调优和故障诊断的实用技能。

---
## 4.15 参考文献
[1] Linux kernel Documentation: filesystems/*、admin-guide/block/*、admin-guide/mm/*
[2] Theodore Ts'o：ext4 设计与实践（内核文档/LWN/演讲资料）
[3] Dave Chinner：XFS 文档与演讲
[4] btrfs wiki 与官方文档
[5] Jens Axboe：blk-mq 与 io_uring（LWN/Plumbers/工具链）
[6] fio 与 blktrace 文档；`man mount`, `man 8 losetup`
[7] Daniel P. Bovet & Marco Cesati, "Understanding the Linux Kernel", 3rd Edition
[8] Maurice J. Bach, "The Design of the UNIX Operating System"
[9] Linux Storage Stack Diagram (https://www.thomas-krenn.com/en/wiki/Linux_Storage_Stack_Diagram)
[10] Filesystem Performance Tuning Guide (kernel.org documentation)

