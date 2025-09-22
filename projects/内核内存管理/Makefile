# Linux内核内存管理研究模块Makefile

# 模块名称
obj-m += buddy_allocator.o
obj-m += slab_analysis.o
obj-m += vmm_research.o
obj-m += memory_reclaim.o

# 编译标志
ccflags-y := -DDEBUG

# 内核源码路径
KERNEL_DIR := /lib/modules/$(shell uname -r)/build

# 当前目录
PWD := $(shell pwd)

# 默认目标
all:
	$(MAKE) -C $(KERNEL_DIR) M=$(PWD) modules

# 清理
clean:
	$(MAKE) -C $(KERNEL_DIR) M=$(PWD) clean

# 安装模块
install:
	$(MAKE) -C $(KERNEL_DIR) M=$(PWD) modules_install

# 加载模块
load:
	sudo insmod buddy_allocator.ko
	sudo insmod slab_analysis.ko
	sudo insmod vmm_research.ko
	sudo insmod memory_reclaim.ko

# 卸载模块
unload:
	sudo rmmod memory_reclaim
	sudo rmmod vmm_research
	sudo rmmod slab_analysis
	sudo rmmod buddy_allocator

# 查看模块信息
info:
	lsmod | grep -E "(buddy|slab|vmm|memory)"
	dmesg | tail -20

.PHONY: all clean install load unload info
