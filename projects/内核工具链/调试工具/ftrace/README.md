# ftrace内核跟踪工具使用指南

## 概述

ftrace是Linux内核内置的跟踪框架，提供了强大的内核函数跟踪、事件跟踪和性能分析功能。它是内核调试和性能分析的重要工具。

## 基本概念

### 跟踪器类型

- **function**: 跟踪内核函数调用
- **function_graph**: 跟踪函数调用图和执行时间
- **irqsoff**: 跟踪中断禁用时间
- **preemptoff**: 跟踪抢占禁用时间
- **wakeup**: 跟踪进程唤醒延迟
- **blk**: 跟踪块设备I/O
- **mmiotrace**: 跟踪内存映射I/O

### 事件跟踪

- **tracepoints**: 内核静态跟踪点
- **kprobes**: 动态内核探针
- **uprobes**: 用户空间探针
- **syscalls**: 系统调用跟踪

## 配置要求

### 内核配置选项

```bash
CONFIG_FTRACE=y                    # 启用ftrace框架
CONFIG_FUNCTION_TRACER=y           # 函数跟踪器
CONFIG_FUNCTION_GRAPH_TRACER=y     # 函数图跟踪器
CONFIG_IRQSOFF_TRACER=y           # 中断延迟跟踪器
CONFIG_PREEMPT_TRACER=y           # 抢占延迟跟踪器
CONFIG_SCHED_TRACER=y             # 调度跟踪器
CONFIG_ENABLE_DEFAULT_TRACERS=y    # 默认启用跟踪器
CONFIG_DYNAMIC_FTRACE=y           # 动态ftrace
CONFIG_FUNCTION_PROFILER=y        # 函数性能分析
```

### 挂载debugfs

```bash
# 挂载debugfs文件系统
mount -t debugfs none /sys/kernel/debug

# 或添加到/etc/fstab
echo "none /sys/kernel/debug debugfs defaults 0 0" >> /etc/fstab
```

## 基本使用

### ftrace文件系统接口

```bash
# ftrace根目录
cd /sys/kernel/debug/tracing

# 主要控制文件
ls -la
# available_tracers      - 可用的跟踪器
# current_tracer         - 当前跟踪器
# tracing_on            - 启用/禁用跟踪
# trace                 - 跟踪输出
# trace_pipe            - 实时跟踪输出
# set_ftrace_filter     - 函数过滤器
# set_ftrace_notrace    - 函数排除过滤器
```

### 基本操作流程

```bash
# 1. 查看可用跟踪器
cat available_tracers

# 2. 设置跟踪器
echo function > current_tracer

# 3. 启用跟踪
echo 1 > tracing_on

# 4. 执行要跟踪的操作
ls /tmp

# 5. 禁用跟踪
echo 0 > tracing_on

# 6. 查看跟踪结果
cat trace | head -20
```

## 函数跟踪

### 基本函数跟踪

```bash
# 启用函数跟踪器
echo function > current_tracer

# 跟踪所有函数
echo 1 > tracing_on

# 查看跟踪结果
cat trace_pipe &
PIPE_PID=$!

# 执行测试命令
echo "test" > /tmp/test.txt

# 停止跟踪
echo 0 > tracing_on
kill $PIPE_PID
```

### 函数过滤

```bash
# 只跟踪特定函数
echo sys_open > set_ftrace_filter
echo sys_read >> set_ftrace_filter

# 排除特定函数
echo schedule > set_ftrace_notrace

# 使用通配符
echo 'sys_*' > set_ftrace_filter

# 清空过滤器
echo > set_ftrace_filter
echo > set_ftrace_notrace
```

### 函数图跟踪

```bash
# 启用函数图跟踪器
echo function_graph > current_tracer

# 设置跟踪深度
echo 5 > max_graph_depth

# 过滤特定函数
echo sys_open > set_graph_function

# 启用跟踪
echo 1 > tracing_on

# 查看结果(显示函数调用图和执行时间)
cat trace
```

## 事件跟踪

### 查看可用事件

```bash
# 查看所有可用事件
cat available_events | head -20

# 查看特定子系统事件
ls events/
# block/    - 块设备事件
# sched/    - 调度事件
# syscalls/ - 系统调用事件
# irq/      - 中断事件
```

### 启用事件跟踪

```bash
# 启用特定事件
echo 1 > events/syscalls/sys_enter_open/enable
echo 1 > events/syscalls/sys_exit_open/enable

# 启用所有系统调用事件
echo 1 > events/syscalls/enable

# 启用所有调度事件
echo 1 > events/sched/enable

# 启用所有事件(谨慎使用)
echo 1 > events/enable
```

### 事件过滤

```bash
# 设置事件过滤条件
echo 'filename ~ "*.txt"' > events/syscalls/sys_enter_open/filter

# 过滤特定PID
echo 'pid == 1234' > events/sched/sched_switch/filter

# 复合条件
echo 'pid == 1234 && comm ~ "bash*"' > events/sched/sched_wakeup/filter

# 查看过滤器
cat events/syscalls/sys_enter_open/filter
```

## 高级功能

### 动态探针(kprobes)

```bash
# 在函数入口设置探针
echo 'p:myprobe do_sys_open filename=+0(%si):string' > kprobe_events

# 在函数返回处设置探针
echo 'r:myretprobe do_sys_open $retval' >> kprobe_events

# 启用探针
echo 1 > events/kprobes/myprobe/enable
echo 1 > events/kprobes/myretprobe/enable

# 查看探针事件
cat events/kprobes/myprobe/format
```

### 用户空间探针(uprobes)

```bash
# 在用户程序中设置探针
echo 'p:/bin/bash:0x12345' > uprobe_events

# 启用用户探针
echo 1 > events/uprobes/enable
```

### 跟踪标记

```bash
# 在跟踪中添加标记
echo "开始测试" > trace_marker

# 执行测试
ls /tmp

echo "结束测试" > trace_marker
```

## 实用脚本

### 系统调用跟踪脚本

```bash
#!/bin/bash
# syscall-trace.sh - 跟踪指定进程的系统调用

PID=${1:-$$}
DURATION=${2:-10}

cd /sys/kernel/debug/tracing

# 清空跟踪缓冲区
echo > trace

# 设置跟踪器
echo nop > current_tracer

# 启用系统调用事件
echo 1 > events/syscalls/enable

# 设置PID过滤器
echo "pid == $PID" > events/syscalls/filter

# 启用跟踪
echo 1 > tracing_on

echo "跟踪PID $PID，持续 $DURATION 秒..."
sleep $DURATION

# 禁用跟踪
echo 0 > tracing_on

# 显示结果
echo "=== 系统调用跟踪结果 ==="
cat trace

# 清理
echo > events/syscalls/filter
echo 0 > events/syscalls/enable
```

### 函数性能分析脚本

```bash
#!/bin/bash
# function-profile.sh - 分析函数执行时间

FUNCTION=${1:-"sys_*"}
DURATION=${2:-5}

cd /sys/kernel/debug/tracing

# 启用函数图跟踪器
echo function_graph > current_tracer

# 设置跟踪函数
echo "$FUNCTION" > set_graph_function

# 清空缓冲区
echo > trace

# 启用跟踪
echo 1 > tracing_on

echo "分析函数 $FUNCTION，持续 $DURATION 秒..."
sleep $DURATION

# 禁用跟踪
echo 0 > tracing_on

# 分析结果
echo "=== 函数执行时间分析 ==="
cat trace | grep -E '\|.*us' | head -20

# 清理
echo > set_graph_function
echo nop > current_tracer
```

### 中断延迟分析脚本

```bash
#!/bin/bash
# irq-latency.sh - 分析中断延迟

DURATION=${1:-10}

cd /sys/kernel/debug/tracing

# 启用中断延迟跟踪器
echo irqsoff > current_tracer

# 清空缓冲区
echo > trace

# 启用跟踪
echo 1 > tracing_on

echo "分析中断延迟，持续 $DURATION 秒..."
sleep $DURATION

# 禁用跟踪
echo 0 > tracing_on

# 显示最大延迟
echo "=== 最大中断延迟 ==="
cat tracing_max_latency

echo "=== 延迟跟踪详情 ==="
cat trace

# 重置最大延迟
echo 0 > tracing_max_latency
echo nop > current_tracer
```

## 性能优化建议

### 减少跟踪开销

```bash
# 使用函数过滤器减少跟踪量
echo 'sys_*' > set_ftrace_filter

# 设置合适的缓冲区大小
echo 1024 > buffer_size_kb

# 使用per-CPU缓冲区
echo 1 > options/overwrite
```

### 实时分析

```bash
# 使用trace_pipe进行实时分析
cat trace_pipe | while read line; do
    echo "$(date): $line"
done
```

## 故障排除

### 常见问题

1. **权限不足**
   ```bash
   # 需要root权限
   sudo su -
   ```

2. **debugfs未挂载**
   ```bash
   mount -t debugfs none /sys/kernel/debug
   ```

3. **跟踪器不可用**
   ```bash
   # 检查内核配置
   cat available_tracers
   ```

### 调试技巧

```bash
# 检查ftrace状态
cat tracing_on

# 查看错误信息
dmesg | grep ftrace

# 重置ftrace状态
echo nop > current_tracer
echo 0 > tracing_on
echo > trace
```

## 参考资源

- [Linux内核文档 - ftrace](https://www.kernel.org/doc/html/latest/trace/ftrace.html)
- [ftrace设计文档](https://www.kernel.org/doc/Documentation/trace/ftrace-design.txt)
- [使用ftrace调试内核](https://lwn.net/Articles/365835/)

---

**注意**: ftrace会产生大量跟踪数据，在生产环境中使用时要注意性能影响。
