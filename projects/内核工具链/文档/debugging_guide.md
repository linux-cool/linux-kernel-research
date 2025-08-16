# Linux内核调试完整指南

## 概述

本指南提供Linux内核调试的全面指导，涵盖从基础调试技术到高级分析方法，帮助开发者掌握内核调试的核心技能。

## 调试环境搭建

### 1. 调试内核编译

```bash
# 启用必要的调试选项
CONFIG_DEBUG_KERNEL=y          # 内核调试支持
CONFIG_DEBUG_INFO=y            # 调试信息
CONFIG_DEBUG_INFO_DWARF4=y     # DWARF4调试格式
CONFIG_FRAME_POINTER=y         # 帧指针
CONFIG_KGDB=y                  # KGDB支持
CONFIG_KGDB_SERIAL_CONSOLE=y   # 串口控制台
CONFIG_MAGIC_SYSRQ=y           # SysRq魔术键
CONFIG_DYNAMIC_DEBUG=y         # 动态调试
CONFIG_FUNCTION_TRACER=y       # 函数跟踪
CONFIG_STACK_TRACER=y          # 栈跟踪
CONFIG_LOCKDEP=y               # 锁依赖检查
CONFIG_PROVE_LOCKING=y         # 锁正确性验证
```

### 2. QEMU调试环境

```bash
# 启动QEMU调试环境
qemu-system-x86_64 \
    -kernel arch/x86/boot/bzImage \
    -initrd /boot/initrd.img \
    -append "console=ttyS0 kgdboc=ttyS0,115200 kgdbwait nokaslr" \
    -serial stdio \
    -m 2G \
    -smp 2 \
    -s -S \
    -display none

# 连接GDB调试器
gdb vmlinux \
    -ex "target remote :1234" \
    -ex "set architecture i386:x86-64"
```

## 调试技术分类

### 1. 静态调试技术

#### 代码审查
```bash
# 使用静态分析工具
sparse -D__KERNEL__ file.c
coccinelle --sp-file rule.cocci file.c
clang-static-analyzer file.c
```

#### 符号分析
```bash
# 查看符号信息
objdump -t vmlinux | grep function_name
nm vmlinux | grep symbol_name
readelf -s vmlinux | grep symbol_name
```

### 2. 动态调试技术

#### KGDB调试
```gdb
# 基本调试命令
(gdb) break sys_open
(gdb) continue
(gdb) step
(gdb) next
(gdb) backtrace
(gdb) info registers

# 内核特定命令
(gdb) lx-ps                    # 查看进程列表
(gdb) lx-lsmod                 # 查看模块列表
(gdb) lx-dmesg                 # 查看内核日志
```

#### ftrace跟踪
```bash
# 函数跟踪
echo function > /sys/kernel/debug/tracing/current_tracer
echo sys_open > /sys/kernel/debug/tracing/set_ftrace_filter
echo 1 > /sys/kernel/debug/tracing/tracing_on

# 事件跟踪
echo 1 > /sys/kernel/debug/tracing/events/syscalls/enable
cat /sys/kernel/debug/tracing/trace_pipe
```

#### 动态探针
```bash
# kprobes使用
echo 'p:myprobe do_sys_open filename=+0(%si):string' > \
    /sys/kernel/debug/tracing/kprobe_events
echo 1 > /sys/kernel/debug/tracing/events/kprobes/myprobe/enable
```

### 3. 性能调试技术

#### perf分析
```bash
# CPU性能分析
perf record -g ./program
perf report

# 内存性能分析
perf record -e cache-misses,cache-references ./program

# 系统调用跟踪
perf trace ./program
```

#### eBPF程序
```c
// 简单的eBPF程序示例
#include <linux/bpf.h>
#include <bpf/bpf_helpers.h>

SEC("kprobe/sys_open")
int trace_open(struct pt_regs *ctx) {
    char comm[16];
    bpf_get_current_comm(&comm, sizeof(comm));
    bpf_printk("Process %s called sys_open\n", comm);
    return 0;
}
```

## 常见调试场景

### 1. 内核崩溃调试

#### 分析oops信息
```bash
# 解析oops信息
./scripts/decode_stacktrace.sh vmlinux < oops.txt

# 使用addr2line定位代码
addr2line -e vmlinux -f -C 0xffffffff81234567
```

#### kdump崩溃转储
```bash
# 配置kdump
echo 'crashkernel=256M' >> /boot/grub/grub.cfg
systemctl enable kdump

# 分析崩溃转储
crash vmlinux /var/crash/dump.file
```

### 2. 内存问题调试

#### 内存泄漏检测
```bash
# 启用KMEMLEAK
echo scan > /sys/kernel/debug/kmemleak
cat /sys/kernel/debug/kmemleak

# 使用KASAN
CONFIG_KASAN=y
CONFIG_KASAN_INLINE=y
```

#### 页面分配调试
```bash
# 启用页面分配调试
echo 1 > /proc/sys/vm/debug_pagealloc

# 查看内存统计
cat /proc/meminfo
cat /proc/slabinfo
```

### 3. 锁问题调试

#### 死锁检测
```bash
# 启用lockdep
CONFIG_LOCKDEP=y
CONFIG_PROVE_LOCKING=y

# 查看锁统计
cat /proc/lockdep_stats
cat /proc/lockdep_chains
```

#### 锁竞争分析
```bash
# 使用perf分析锁竞争
perf record -e lock:lock_acquire,lock:lock_release ./program
perf report
```

### 4. 中断和定时器调试

#### 中断分析
```bash
# 查看中断统计
cat /proc/interrupts
cat /proc/softirqs

# 跟踪中断处理
echo 1 > /sys/kernel/debug/tracing/events/irq/enable
```

#### 定时器调试
```bash
# 查看定时器信息
cat /proc/timer_list
cat /proc/timer_stats

# 跟踪定时器事件
echo 1 > /sys/kernel/debug/tracing/events/timer/enable
```

## 调试工具集成

### 1. GDB脚本

```gdb
# .gdbinit - GDB初始化脚本
set print pretty on
set print array on
set print array-indexes on

# 定义便捷命令
define lsmod
    lx-lsmod
end

define ps
    lx-ps
end

define dmesg
    lx-dmesg
end

# 自动加载内核调试脚本
source scripts/gdb/vmlinux-gdb.py
```

### 2. 调试脚本

```bash
#!/bin/bash
# debug-helper.sh - 调试辅助脚本

# 收集调试信息
collect_debug_info() {
    echo "=== 系统信息 ==="
    uname -a
    cat /proc/version
    
    echo "=== 内存信息 ==="
    cat /proc/meminfo
    
    echo "=== CPU信息 ==="
    cat /proc/cpuinfo
    
    echo "=== 模块信息 ==="
    lsmod
    
    echo "=== 中断信息 ==="
    cat /proc/interrupts
}

# 启用调试选项
enable_debug() {
    # 启用动态调试
    echo 'module kernel +p' > /sys/kernel/debug/dynamic_debug/control
    
    # 启用ftrace
    echo function > /sys/kernel/debug/tracing/current_tracer
    echo 1 > /sys/kernel/debug/tracing/tracing_on
}
```

### 3. 自动化调试

```python
#!/usr/bin/env python3
# auto-debug.py - 自动化调试脚本

import subprocess
import time
import sys

class KernelDebugger:
    def __init__(self):
        self.gdb_commands = [
            "target remote :1234",
            "set architecture i386:x86-64",
            "break panic",
            "break oops_begin",
            "continue"
        ]
    
    def start_qemu(self):
        """启动QEMU调试环境"""
        cmd = [
            "qemu-system-x86_64",
            "-kernel", "arch/x86/boot/bzImage",
            "-append", "console=ttyS0 kgdbwait",
            "-serial", "stdio",
            "-s", "-S"
        ]
        return subprocess.Popen(cmd)
    
    def connect_gdb(self):
        """连接GDB调试器"""
        gdb_script = "\n".join(self.gdb_commands)
        with open("debug.gdb", "w") as f:
            f.write(gdb_script)
        
        subprocess.run(["gdb", "-x", "debug.gdb", "vmlinux"])
```

## 最佳实践

### 1. 调试策略

1. **分层调试**: 从用户空间到内核空间逐层分析
2. **最小化复现**: 创建最小的测试用例
3. **日志记录**: 添加详细的调试日志
4. **版本控制**: 使用git bisect定位问题引入点

### 2. 性能考虑

```bash
# 调试时的性能优化
# 1. 限制跟踪范围
echo 'sys_*' > /sys/kernel/debug/tracing/set_ftrace_filter

# 2. 使用合适的缓冲区大小
echo 1024 > /sys/kernel/debug/tracing/buffer_size_kb

# 3. 避免在生产环境启用重量级调试选项
```

### 3. 安全注意事项

```bash
# 调试环境安全
# 1. 在虚拟机中进行调试
# 2. 备份重要数据
# 3. 使用专用的调试内核
# 4. 限制调试权限
echo 1 > /proc/sys/kernel/perf_event_paranoid
```

## 故障排除

### 常见问题

1. **GDB连接失败**
   ```bash
   # 检查QEMU是否启动
   ps aux | grep qemu
   
   # 检查端口是否开放
   netstat -ln | grep 1234
   ```

2. **符号信息缺失**
   ```bash
   # 确保编译时包含调试信息
   CONFIG_DEBUG_INFO=y
   
   # 检查vmlinux文件
   file vmlinux
   objdump -h vmlinux | grep debug
   ```

3. **ftrace不工作**
   ```bash
   # 检查debugfs挂载
   mount | grep debugfs
   
   # 检查权限
   ls -la /sys/kernel/debug/tracing/
   ```

## 参考资源

- [Linux内核调试文档](https://www.kernel.org/doc/html/latest/dev-tools/index.html)
- [KGDB使用指南](https://www.kernel.org/doc/html/latest/dev-tools/kgdb.html)
- [ftrace文档](https://www.kernel.org/doc/html/latest/trace/ftrace.html)
- [内核调试技巧](https://lwn.net/Articles/87538/)

---

**注意**: 内核调试可能会影响系统稳定性，建议在专用的开发环境中进行。
