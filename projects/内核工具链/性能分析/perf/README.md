# perf性能分析工具使用指南

## 概述

perf是Linux内核提供的强大性能分析工具，支持CPU性能计数器、软件事件、硬件事件等多种性能数据收集和分析功能。它是内核性能调优的核心工具。

## 安装配置

### 安装perf工具

```bash
# Ubuntu/Debian
sudo apt-get install linux-tools-common linux-tools-generic
sudo apt-get install linux-tools-$(uname -r)

# CentOS/RHEL
sudo yum install perf

# 验证安装
perf --version
```

### 内核配置要求

```bash
CONFIG_PERF_EVENTS=y              # 启用perf事件
CONFIG_HW_PERF_EVENTS=y           # 硬件性能事件
CONFIG_HAVE_PERF_EVENTS=y         # perf事件支持
CONFIG_PERF_USE_VMALLOC=y         # 使用vmalloc
CONFIG_DEBUG_INFO=y               # 调试信息(符号解析)
```

## 基本概念

### 事件类型

- **硬件事件**: CPU周期、指令数、缓存命中/失效
- **软件事件**: 页面错误、上下文切换、CPU迁移
- **跟踪点事件**: 内核静态跟踪点
- **动态事件**: kprobes、uprobes

### 采样模式

- **计数模式**: 统计事件发生次数
- **采样模式**: 周期性采样，生成详细的性能数据

## 基本使用

### 查看可用事件

```bash
# 列出所有可用事件
perf list

# 查看硬件事件
perf list hw

# 查看软件事件
perf list sw

# 查看跟踪点事件
perf list tracepoint

# 搜索特定事件
perf list | grep cache
```

### 基本性能统计

```bash
# 统计程序性能
perf stat ls -la

# 统计特定事件
perf stat -e cycles,instructions,cache-misses ls -la

# 统计系统性能(10秒)
perf stat -a sleep 10

# 详细统计信息
perf stat -d ls -la
```

### 性能采样

```bash
# 采样CPU性能(默认99Hz)
perf record ls -la

# 指定采样频率
perf record -F 1000 ls -la

# 采样特定事件
perf record -e cycles ls -la

# 采样所有CPU
perf record -a sleep 10

# 采样特定进程
perf record -p 1234 sleep 10
```

## 高级功能

### CPU性能分析

```bash
# CPU热点分析
perf record -g ./my_program
perf report

# 实时CPU监控
perf top

# 指定CPU采样
perf record -C 0,1 sleep 10

# 采样调用图
perf record --call-graph dwarf ./my_program
```

### 内存性能分析

```bash
# 内存访问模式分析
perf record -e cache-misses,cache-references ./my_program

# 页面错误分析
perf record -e page-faults ./my_program

# TLB性能分析
perf record -e dTLB-loads,dTLB-load-misses ./my_program

# 内存带宽分析
perf stat -e cache-misses,cache-references,LLC-loads,LLC-load-misses ./my_program
```

### 系统调用分析

```bash
# 跟踪系统调用
perf trace ls -la

# 跟踪特定系统调用
perf trace -e open,read,write ls -la

# 跟踪进程系统调用
perf trace -p 1234

# 统计系统调用
perf trace -s ls -la
```

### 内核函数分析

```bash
# 跟踪内核函数
perf record -e probe:do_sys_open ls -la

# 添加动态探针
perf probe -a do_sys_open

# 跟踪探针事件
perf record -e probe:do_sys_open ls -la

# 删除探针
perf probe -d do_sys_open
```

## 数据分析

### 报告生成

```bash
# 生成性能报告
perf report

# 按函数排序
perf report --sort=symbol

# 按进程排序
perf report --sort=pid

# 显示调用图
perf report -g

# 生成文本报告
perf report --stdio > report.txt
```

### 数据过滤

```bash
# 过滤特定进程
perf report --pid=1234

# 过滤特定时间段
perf report --time=10.0,20.0

# 过滤特定CPU
perf report --cpu=0

# 过滤特定符号
perf report --symbols=main,foo
```

### 差异分析

```bash
# 记录基线性能
perf record -o baseline.data ./my_program

# 记录优化后性能
perf record -o optimized.data ./my_program_v2

# 比较性能差异
perf diff baseline.data optimized.data
```

## 实用脚本

### CPU热点分析脚本

```bash
#!/bin/bash
# cpu-hotspot.sh - CPU热点分析

PROGRAM=${1:-""}
DURATION=${2:-10}

if [ -z "$PROGRAM" ]; then
    echo "用法: $0 <程序> [持续时间]"
    exit 1
fi

echo "分析程序: $PROGRAM"
echo "持续时间: $DURATION 秒"

# 记录性能数据
perf record -g -F 999 $PROGRAM &
PERF_PID=$!

sleep $DURATION
kill $PERF_PID 2>/dev/null

# 生成报告
echo "=== CPU热点分析报告 ==="
perf report --stdio | head -50

# 生成火焰图数据
perf script > perf.out
echo "性能数据已保存到 perf.out"
```

### 内存性能分析脚本

```bash
#!/bin/bash
# memory-analysis.sh - 内存性能分析

PROGRAM=${1:-""}

if [ -z "$PROGRAM" ]; then
    echo "用法: $0 <程序>"
    exit 1
fi

echo "内存性能分析: $PROGRAM"

# 分析缓存性能
echo "=== 缓存性能分析 ==="
perf stat -e cache-misses,cache-references,LLC-loads,LLC-load-misses $PROGRAM

# 分析页面错误
echo "=== 页面错误分析 ==="
perf stat -e page-faults,minor-faults,major-faults $PROGRAM

# 分析TLB性能
echo "=== TLB性能分析 ==="
perf stat -e dTLB-loads,dTLB-load-misses,iTLB-loads,iTLB-load-misses $PROGRAM
```

### 系统性能监控脚本

```bash
#!/bin/bash
# system-monitor.sh - 系统性能监控

DURATION=${1:-60}
INTERVAL=${2:-5}

echo "系统性能监控 - 持续时间: $DURATION 秒，间隔: $INTERVAL 秒"

# 创建监控循环
for ((i=0; i<$((DURATION/INTERVAL)); i++)); do
    echo "=== 时间点: $(date) ==="
    
    # CPU使用率
    perf stat -a -e cycles,instructions,cache-misses sleep $INTERVAL 2>&1 | \
        grep -E "(cycles|instructions|cache-misses)"
    
    echo ""
done
```

### 进程性能跟踪脚本

```bash
#!/bin/bash
# process-trace.sh - 进程性能跟踪

PID=${1:-""}
DURATION=${2:-30}

if [ -z "$PID" ]; then
    echo "用法: $0 <PID> [持续时间]"
    exit 1
fi

echo "跟踪进程 PID: $PID，持续时间: $DURATION 秒"

# 记录进程性能
perf record -p $PID -g sleep $DURATION

# 生成报告
echo "=== 进程性能报告 ==="
perf report --stdio

# 系统调用统计
echo "=== 系统调用统计 ==="
perf trace -p $PID -s sleep 10 2>&1 | tail -20
```

## 可视化分析

### 火焰图生成

```bash
# 安装火焰图工具
git clone https://github.com/brendangregg/FlameGraph.git

# 生成火焰图
perf record -g ./my_program
perf script | ./FlameGraph/stackcollapse-perf.pl | ./FlameGraph/flamegraph.pl > flame.svg

# 在浏览器中查看
firefox flame.svg
```

### 热力图生成

```bash
# 生成热力图数据
perf record -e cache-misses -g ./my_program
perf script | ./FlameGraph/stackcollapse-perf.pl | \
    ./FlameGraph/flamegraph.pl --color=mem > heatmap.svg
```

## 性能调优技巧

### CPU优化

```bash
# 分析CPU绑定问题
perf record -e cycles,instructions ./cpu_intensive_program

# 分析分支预测
perf stat -e branch-misses,branches ./my_program

# 分析指令级并行
perf stat -e cycles,instructions ./my_program
# IPC = instructions / cycles (理想值接近CPU的发射宽度)
```

### 内存优化

```bash
# 分析缓存友好性
perf stat -e cache-misses,cache-references ./my_program
# 缓存命中率 = (cache-references - cache-misses) / cache-references

# 分析内存访问模式
perf record -e mem:0x1000000:rw ./my_program
```

### I/O优化

```bash
# 分析块设备I/O
perf record -e block:block_rq_issue,block:block_rq_complete ./io_program

# 分析网络I/O
perf record -e net:netif_rx,net:net_dev_xmit ./network_program
```

## 故障排除

### 常见问题

1. **权限不足**
   ```bash
   # 设置perf权限
   echo 0 | sudo tee /proc/sys/kernel/perf_event_paranoid
   
   # 或使用sudo
   sudo perf record ./my_program
   ```

2. **符号信息缺失**
   ```bash
   # 安装调试符号
   sudo apt-get install libc6-dbg
   
   # 编译时包含调试信息
   gcc -g -O2 program.c -o program
   ```

3. **采样频率过高**
   ```bash
   # 降低采样频率
   perf record -F 99 ./my_program
   ```

### 调试技巧

```bash
# 检查perf状态
perf --debug verbose=3 record ./my_program

# 查看perf配置
cat /proc/sys/kernel/perf_event_max_sample_rate
cat /proc/sys/kernel/perf_event_paranoid
```

## 参考资源

- [perf官方文档](https://perf.wiki.kernel.org/)
- [perf教程](https://www.brendangregg.com/perf.html)
- [Linux性能分析工具](https://www.kernel.org/doc/html/latest/admin-guide/perf-security.html)

---

**注意**: perf分析会产生性能开销，在生产环境中使用时要控制采样频率和持续时间。
