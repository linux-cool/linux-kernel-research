# 内核模块Makefile

obj-m += performance_tracer.o

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
	sudo insmod performance_tracer.ko

# 卸载模块
unload:
	sudo rmmod performance_tracer

# 重新加载模块
reload: unload load

.PHONY: all clean install load unload reload
