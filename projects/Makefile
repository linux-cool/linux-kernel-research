# Linux内核研究项目通用Makefile
# 支持编译各个子项目的内核模块

# 内核源码路径
KERNEL_DIR := /lib/modules/$(shell uname -r)/build

# 子项目目录
SUBDIRS := 内核内存管理 进程调度 网络子系统 文件系统 设备驱动 内核性能 内核安全 内核工具链

# 默认目标
all: modules

# 编译所有子项目
modules:
	@echo "Building all kernel research modules..."
	@for dir in $(SUBDIRS); do \
		if [ -d "$$dir" ] && [ -f "$$dir/Makefile" ]; then \
			echo "Building $$dir..."; \
			$(MAKE) -C $(KERNEL_DIR) M=$(PWD)/$$dir modules; \
		fi; \
	done

# 清理所有子项目
clean:
	@echo "Cleaning all kernel research modules..."
	@for dir in $(SUBDIRS); do \
		if [ -d "$$dir" ]; then \
			echo "Cleaning $$dir..."; \
			$(MAKE) -C $(KERNEL_DIR) M=$(PWD)/$$dir clean; \
		fi; \
	done

# 安装所有模块
install: modules
	@echo "Installing all kernel research modules..."
	@for dir in $(SUBDIRS); do \
		if [ -d "$$dir" ] && [ -f "$$dir/Makefile" ]; then \
			echo "Installing $$dir..."; \
			$(MAKE) -C $(KERNEL_DIR) M=$(PWD)/$$dir modules_install; \
		fi; \
	done

# 编译特定子项目
memory:
	$(MAKE) -C $(KERNEL_DIR) M=$(PWD)/内核内存管理 modules

scheduler:
	$(MAKE) -C $(KERNEL_DIR) M=$(PWD)/进程调度 modules

network:
	$(MAKE) -C $(KERNEL_DIR) M=$(PWD)/网络子系统 modules

filesystem:
	$(MAKE) -C $(KERNEL_DIR) M=$(PWD)/文件系统 modules

driver:
	$(MAKE) -C $(KERNEL_DIR) M=$(PWD)/设备驱动 modules

performance:
	$(MAKE) -C $(KERNEL_DIR) M=$(PWD)/内核性能 modules

security:
	$(MAKE) -C $(KERNEL_DIR) M=$(PWD)/内核安全 modules

toolchain:
	$(MAKE) -C 内核工具链

# 设置调试工具链
setup-toolchain:
	$(MAKE) -C 内核工具链 install

# 帮助信息
help:
	@echo "Linux内核研究项目构建系统"
	@echo "=========================="
	@echo ""
	@echo "可用目标:"
	@echo "  all           - 编译所有内核模块"
	@echo "  memory        - 编译内存管理模块"
	@echo "  scheduler     - 编译进程调度模块"
	@echo "  network       - 编译网络子系统模块"
	@echo "  filesystem    - 编译文件系统模块"
	@echo "  driver        - 编译设备驱动模块"
	@echo "  performance   - 编译性能分析模块"
	@echo "  security      - 编译安全机制模块"
	@echo "  toolchain     - 设置内核工具链"
	@echo "  setup-toolchain - 安装和配置调试工具链"
	@echo "  install       - 安装所有模块"
	@echo "  clean         - 清理编译文件"
	@echo "  help          - 显示此帮助信息"

.PHONY: all modules clean install memory scheduler network filesystem driver performance security toolchain setup-toolchain help

tools:
	$(MAKE) -C $(KERNEL_DIR) M=$(PWD)/内核工具链 modules

# 帮助信息
help:
	@echo "Linux Kernel Research Project Makefile"
	@echo "======================================="
	@echo ""
	@echo "Available targets:"
	@echo "  all        - Build all kernel modules"
	@echo "  modules    - Build all kernel modules (same as all)"
	@echo "  clean      - Clean all build artifacts"
	@echo "  install    - Install all modules"
	@echo ""
	@echo "Individual project targets:"
	@echo "  memory     - Build memory management modules"
	@echo "  scheduler  - Build process scheduler modules"
	@echo "  network    - Build network subsystem modules"
	@echo "  filesystem - Build filesystem modules"
	@echo "  driver     - Build device driver modules"
	@echo "  performance- Build performance analysis modules"
	@echo "  security   - Build security modules"
	@echo "  tools      - Build toolchain modules"
	@echo ""
	@echo "Usage examples:"
	@echo "  make all           # Build all modules"
	@echo "  make memory        # Build only memory management modules"
	@echo "  make clean         # Clean all build artifacts"

.PHONY: all modules clean install memory scheduler network filesystem driver performance security tools help
