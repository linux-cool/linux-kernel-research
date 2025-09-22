# KGDB内核调试器使用指南

## 概述

KGDB (Kernel GNU Debugger) 是Linux内核的远程调试器，允许开发者使用GDB调试运行中的内核。它通过串口、网络或其他通信接口连接调试主机和目标机器。

## 配置要求

### 内核配置选项

编译内核时需要启用以下配置选项：

```bash
CONFIG_DEBUG_KERNEL=y          # 启用内核调试支持
CONFIG_DEBUG_INFO=y            # 包含调试信息
CONFIG_KGDB=y                  # 启用KGDB支持
CONFIG_KGDB_SERIAL_CONSOLE=y   # 串口控制台支持
CONFIG_KGDB_KDB=y              # 启用KDB支持
CONFIG_FRAME_POINTER=y         # 启用帧指针(便于调试)
CONFIG_MAGIC_SYSRQ=y           # 启用SysRq魔术键
```

### 内核启动参数

```bash
# 通过串口调试
kgdboc=ttyS0,115200

# 等待调试器连接
kgdbwait

# 禁用KASLR(地址随机化)
nokaslr

# 完整启动参数示例
console=ttyS0,115200 kgdboc=ttyS0,115200 kgdbwait nokaslr
```

## 使用方法

### 1. QEMU环境调试

#### 启动QEMU虚拟机

```bash
#!/bin/bash
# start-qemu-debug.sh

qemu-system-x86_64 \
    -kernel arch/x86/boot/bzImage \
    -initrd /boot/initrd.img \
    -append "console=ttyS0 kgdboc=ttyS0,115200 kgdbwait nokaslr" \
    -serial stdio \
    -m 1G \
    -smp 2 \
    -s -S \
    -display none
```

#### 连接GDB调试器

```bash
#!/bin/bash
# connect-gdb.sh

# 启动GDB并连接到QEMU
gdb vmlinux \
    -ex "target remote :1234" \
    -ex "set architecture i386:x86-64" \
    -ex "set disassembly-flavor intel"
```

### 2. 物理机调试

#### 目标机器配置

```bash
# 在目标机器上配置串口
echo ttyS0 > /sys/module/kgdboc/parameters/kgdboc

# 触发调试断点
echo g > /proc/sysrq-trigger
```

#### 调试主机连接

```bash
# 通过串口连接
gdb vmlinux
(gdb) target remote /dev/ttyS0
(gdb) set serial baud 115200
```

## 常用GDB命令

### 基本调试命令

```gdb
# 连接目标
(gdb) target remote :1234

# 继续执行
(gdb) continue
(gdb) c

# 单步执行
(gdb) step
(gdb) s

# 下一步(不进入函数)
(gdb) next
(gdb) n

# 查看调用栈
(gdb) backtrace
(gdb) bt

# 查看寄存器
(gdb) info registers
(gdb) i r

# 查看内存
(gdb) x/10x $rsp
(gdb) x/s 0xffffffff81234567
```

### 断点管理

```gdb
# 设置函数断点
(gdb) break sys_open
(gdb) b do_fork

# 设置地址断点
(gdb) break *0xffffffff81234567

# 设置条件断点
(gdb) break sys_read if fd == 1

# 查看断点
(gdb) info breakpoints
(gdb) i b

# 删除断点
(gdb) delete 1
(gdb) d 1

# 禁用/启用断点
(gdb) disable 1
(gdb) enable 1
```

### 内核特定命令

```gdb
# 查看当前进程
(gdb) p $lx_current()

# 查看进程列表
(gdb) lx-ps

# 查看内核模块
(gdb) lx-lsmod

# 查看内存映射
(gdb) lx-mounts

# 查看设备树
(gdb) lx-device-tree-show

# 查看内核日志
(gdb) lx-dmesg
```

## 调试技巧

### 1. 内核数据结构分析

```gdb
# 查看task_struct结构
(gdb) p *(struct task_struct *)$lx_current()

# 查看进程内存描述符
(gdb) p ((struct task_struct *)$lx_current())->mm

# 查看文件描述符表
(gdb) p ((struct task_struct *)$lx_current())->files
```

### 2. 内存调试

```gdb
# 查看页表项
(gdb) p/x *(pte_t *)0xffff888012345678

# 查看物理内存
(gdb) x/10x __va(0x1000000)

# 查看虚拟内存映射
(gdb) p ((struct mm_struct *)mm)->mmap
```

### 3. 中断和异常调试

```gdb
# 在中断处理函数设置断点
(gdb) break do_IRQ

# 查看中断描述符表
(gdb) x/256x idt_table

# 查看异常处理
(gdb) break do_page_fault
```

## 调试脚本示例

### 自动化调试脚本

```bash
#!/bin/bash
# auto-debug.sh

# 创建GDB命令文件
cat > debug.gdb << 'EOF'
# 连接目标
target remote :1234

# 设置常用断点
break sys_open
break sys_read
break sys_write
break do_page_fault

# 定义便捷命令
define show_current
    p $lx_current()
    p ((struct task_struct *)$lx_current())->comm
end

define show_regs
    info registers
    x/10i $rip
end

# 继续执行
continue
EOF

# 启动GDB
gdb -x debug.gdb vmlinux
```

### 内核崩溃分析脚本

```gdb
# crash-analysis.gdb

# 分析内核崩溃
define analyze_crash
    echo \n=== 崩溃分析 ===\n
    
    # 显示寄存器状态
    echo \n--- 寄存器状态 ---\n
    info registers
    
    # 显示调用栈
    echo \n--- 调用栈 ---\n
    backtrace
    
    # 显示崩溃指令
    echo \n--- 崩溃指令 ---\n
    x/10i $rip-20
    
    # 显示当前进程
    echo \n--- 当前进程 ---\n
    p $lx_current()
end
```

## 故障排除

### 常见问题

1. **无法连接到目标**
   ```bash
   # 检查串口配置
   stty -F /dev/ttyS0 115200
   
   # 检查QEMU是否启动
   ps aux | grep qemu
   ```

2. **符号信息缺失**
   ```bash
   # 确保编译时包含调试信息
   CONFIG_DEBUG_INFO=y
   
   # 检查vmlinux文件
   file vmlinux
   objdump -h vmlinux | grep debug
   ```

3. **断点无法命中**
   ```bash
   # 检查KASLR是否禁用
   cat /proc/cmdline | grep nokaslr
   
   # 使用函数名而非地址设置断点
   (gdb) break function_name
   ```

### 调试日志

```bash
# 启用KGDB调试日志
echo 1 > /sys/module/kgdb/parameters/debug

# 查看调试信息
dmesg | grep kgdb
```

## 高级用法

### 1. 多核调试

```gdb
# 查看所有CPU状态
(gdb) info threads

# 切换到特定CPU
(gdb) thread 2

# 在所有CPU上设置断点
(gdb) break function_name thread all
```

### 2. 内核模块调试

```gdb
# 加载模块符号
(gdb) add-symbol-file module.ko 0xffffffffa0000000

# 在模块函数设置断点
(gdb) break module_function
```

### 3. 实时跟踪

```gdb
# 设置跟踪点
(gdb) trace sys_open
(gdb) actions
> collect $regs
> end

# 开始跟踪
(gdb) tstart

# 查看跟踪结果
(gdb) tfind
```

## 参考资源

- [Linux内核文档 - KGDB](https://www.kernel.org/doc/html/latest/dev-tools/kgdb.html)
- [GDB用户手册](https://sourceware.org/gdb/documentation/)
- [内核调试技术](https://lwn.net/Articles/87538/)

---

**注意**: KGDB调试会显著影响系统性能，仅在开发和调试环境中使用。
