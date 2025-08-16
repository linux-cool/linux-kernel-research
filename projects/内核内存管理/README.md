# Linux内核内存管理子系统研究

## 项目概述

本项目深入研究Linux内核内存管理机制，包括页面分配器、slab分配器、虚拟内存管理、内存回收等核心技术。

## 研究内容

### 1. 页面分配器 (Buddy System)
- buddy算法的实现原理
- 页面分配和释放机制
- 内存碎片问题分析
- 大页面(hugepage)支持

### 2. Slab分配器
- slab/slub/slob分配器对比
- 对象缓存机制
- 内存池管理
- 分配器性能优化

### 3. 虚拟内存管理
- 页表管理机制
- 虚拟地址空间布局
- 内存映射(mmap)实现
- 写时复制(COW)机制

### 4. 内存回收
- LRU算法实现
- kswapd内核线程
- 内存压缩和迁移
- OOM killer机制

## 技术特点

- 内核源码级别的深度分析
- 内存管理性能优化策略
- 内存泄漏和内存碎片问题研究
- 多架构内存管理差异分析

## 文件说明

- `buddy_allocator.c` - buddy算法分析和测试
- `slab_analysis.c` - slab分配器性能分析
- `vmm_research.c` - 虚拟内存管理研究
- `memory_reclaim.c` - 内存回收机制分析

## 编译和运行

```bash
# 编译内核模块
make -C /lib/modules/$(uname -r)/build M=$(pwd) modules

# 加载模块
sudo insmod memory_research.ko

# 查看内核日志
dmesg | tail -20
```

## 参考资料

- Linux内核源码 (mm/ 目录)
- Understanding the Linux Kernel
- Linux Kernel Development
- 内核文档 Documentation/vm/
