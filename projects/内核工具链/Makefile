# Linux内核调试与开发工具链 Makefile
# 用于构建和管理内核调试工具链

# 基本配置
SHELL := /bin/bash
.PHONY: all clean install help setup-env check-deps

# 工具版本配置
KERNEL_VERSION ?= 6.1
QEMU_VERSION ?= 7.0
GDB_VERSION ?= 12.1

# 目录配置
TOOLS_DIR := $(PWD)
BUILD_DIR := $(TOOLS_DIR)/build
INSTALL_DIR := $(TOOLS_DIR)/install
SCRIPTS_DIR := $(TOOLS_DIR)/实用脚本
DOCS_DIR := $(TOOLS_DIR)/文档

# 颜色输出
RED := \033[31m
GREEN := \033[32m
YELLOW := \033[33m
BLUE := \033[34m
RESET := \033[0m

# 默认目标
all: help

# 帮助信息
help:
	@echo -e "$(BLUE)Linux内核调试与开发工具链$(RESET)"
	@echo -e "$(BLUE)================================$(RESET)"
	@echo ""
	@echo -e "$(GREEN)可用目标:$(RESET)"
	@echo -e "  $(YELLOW)setup-env$(RESET)     - 设置开发环境"
	@echo -e "  $(YELLOW)check-deps$(RESET)    - 检查依赖项"
	@echo -e "  $(YELLOW)install-tools$(RESET) - 安装调试工具"
	@echo -e "  $(YELLOW)build-kernel$(RESET)  - 编译调试内核"
	@echo -e "  $(YELLOW)setup-qemu$(RESET)    - 配置QEMU环境"
	@echo -e "  $(YELLOW)test-tools$(RESET)    - 测试工具链"
	@echo -e "  $(YELLOW)clean$(RESET)         - 清理构建文件"
	@echo -e "  $(YELLOW)help$(RESET)          - 显示此帮助信息"
	@echo ""
	@echo -e "$(GREEN)使用示例:$(RESET)"
	@echo -e "  make setup-env        # 初始化开发环境"
	@echo -e "  make install-tools    # 安装所有调试工具"
	@echo -e "  make build-kernel     # 编译调试版内核"

# 检查依赖项
check-deps:
	@echo -e "$(BLUE)检查系统依赖项...$(RESET)"
	@command -v gcc >/dev/null 2>&1 || { echo -e "$(RED)错误: 需要安装 gcc$(RESET)"; exit 1; }
	@command -v make >/dev/null 2>&1 || { echo -e "$(RED)错误: 需要安装 make$(RESET)"; exit 1; }
	@command -v git >/dev/null 2>&1 || { echo -e "$(RED)错误: 需要安装 git$(RESET)"; exit 1; }
	@echo -e "$(GREEN)✓ 基础依赖项检查通过$(RESET)"

# 设置开发环境
setup-env: check-deps
	@echo -e "$(BLUE)设置内核调试开发环境...$(RESET)"
	@mkdir -p $(BUILD_DIR) $(INSTALL_DIR)
	@mkdir -p 调试工具/{kgdb,ftrace,crash_analysis,dynamic_debug}
	@mkdir -p 静态分析/{sparse,coccinelle,clang_analyzer,checkpatch}
	@mkdir -p 性能分析/{perf,ebpf,systemtap,flame_graphs}
	@mkdir -p 开发环境/{kernel_build,qemu_setup,cross_compile,docker_env}
	@mkdir -p 实用脚本/{build_scripts,test_scripts,analysis_scripts,automation}
	@mkdir -p 文档
	@echo -e "$(GREEN)✓ 目录结构创建完成$(RESET)"

# 安装调试工具
install-tools: setup-env
	@echo -e "$(BLUE)安装内核调试工具...$(RESET)"
	@if command -v apt-get >/dev/null 2>&1; then \
		sudo apt-get update && \
		sudo apt-get install -y \
			build-essential git vim \
			linux-headers-$$(uname -r) \
			gdb crash kexec-tools \
			linux-tools-common linux-tools-generic \
			sparse coccinelle clang-tools \
			qemu-system-x86 qemu-utils \
			bison flex libssl-dev libelf-dev \
			dwarves zstd; \
	elif command -v yum >/dev/null 2>&1; then \
		sudo yum groupinstall -y "Development Tools" && \
		sudo yum install -y \
			kernel-devel kernel-headers \
			gdb crash kexec-tools \
			perf sparse \
			qemu-kvm qemu-img \
			bison flex openssl-devel elfutils-libelf-devel; \
	else \
		echo -e "$(RED)错误: 不支持的包管理器$(RESET)"; \
		exit 1; \
	fi
	@echo -e "$(GREEN)✓ 调试工具安装完成$(RESET)"

# 编译调试内核
build-kernel:
	@echo -e "$(BLUE)编译内核调试版本...$(RESET)"
	@if [ ! -d "$(BUILD_DIR)/linux-$(KERNEL_VERSION)" ]; then \
		echo -e "$(YELLOW)下载内核源码...$(RESET)"; \
		cd $(BUILD_DIR) && \
		wget -q https://cdn.kernel.org/pub/linux/kernel/v6.x/linux-$(KERNEL_VERSION).tar.xz && \
		tar -xf linux-$(KERNEL_VERSION).tar.xz; \
	fi
	@cd $(BUILD_DIR)/linux-$(KERNEL_VERSION) && \
		cp /boot/config-$$(uname -r) .config 2>/dev/null || make defconfig && \
		scripts/config --enable DEBUG_KERNEL && \
		scripts/config --enable DEBUG_INFO && \
		scripts/config --enable DEBUG_INFO_DWARF4 && \
		scripts/config --enable KGDB && \
		scripts/config --enable KGDB_SERIAL_CONSOLE && \
		scripts/config --enable FRAME_POINTER && \
		scripts/config --enable FUNCTION_TRACER && \
		scripts/config --enable DYNAMIC_DEBUG && \
		make olddefconfig && \
		make -j$$(nproc) 2>/dev/null || make -j1
	@echo -e "$(GREEN)✓ 内核编译完成$(RESET)"

# 配置QEMU环境
setup-qemu: build-kernel
	@echo -e "$(BLUE)配置QEMU调试环境...$(RESET)"
	@mkdir -p $(BUILD_DIR)/qemu-env
	@cat > $(BUILD_DIR)/qemu-env/start-debug.sh << 'EOF'
#!/bin/bash
# QEMU内核调试启动脚本

KERNEL_DIR="$(BUILD_DIR)/linux-$(KERNEL_VERSION)"
KERNEL_IMAGE="$$KERNEL_DIR/arch/x86/boot/bzImage"
INITRD="/boot/initrd.img-$$(uname -r)"

if [ ! -f "$$KERNEL_IMAGE" ]; then
    echo "错误: 内核镜像不存在: $$KERNEL_IMAGE"
    exit 1
fi

echo "启动QEMU内核调试环境..."
qemu-system-x86_64 \
    -kernel "$$KERNEL_IMAGE" \
    -initrd "$$INITRD" \
    -append "console=ttyS0 kgdboc=ttyS0,115200 kgdbwait nokaslr" \
    -serial stdio \
    -m 1G \
    -smp 2 \
    -s -S \
    -display none
EOF
	@chmod +x $(BUILD_DIR)/qemu-env/start-debug.sh
	@cat > $(BUILD_DIR)/qemu-env/gdb-debug.sh << 'EOF'
#!/bin/bash
# GDB调试脚本

KERNEL_DIR="$(BUILD_DIR)/linux-$(KERNEL_VERSION)"
VMLINUX="$$KERNEL_DIR/vmlinux"

if [ ! -f "$$VMLINUX" ]; then
    echo "错误: vmlinux不存在: $$VMLINUX"
    exit 1
fi

echo "启动GDB调试会话..."
gdb -ex "target remote :1234" \
    -ex "set architecture i386:x86-64" \
    -ex "set disassembly-flavor intel" \
    "$$VMLINUX"
EOF
	@chmod +x $(BUILD_DIR)/qemu-env/gdb-debug.sh
	@echo -e "$(GREEN)✓ QEMU环境配置完成$(RESET)"

# 测试工具链
test-tools:
	@echo -e "$(BLUE)测试内核调试工具链...$(RESET)"
	@echo -e "$(YELLOW)测试GDB...$(RESET)"
	@gdb --version | head -1
	@echo -e "$(YELLOW)测试Sparse...$(RESET)"
	@sparse --version 2>/dev/null || echo "Sparse未安装"
	@echo -e "$(YELLOW)测试perf...$(RESET)"
	@perf --version 2>/dev/null || echo "perf未安装"
	@echo -e "$(YELLOW)测试QEMU...$(RESET)"
	@qemu-system-x86_64 --version | head -1
	@echo -e "$(GREEN)✓ 工具链测试完成$(RESET)"

# 创建开发脚本
create-scripts: setup-env
	@echo -e "$(BLUE)创建开发辅助脚本...$(RESET)"
	@cat > $(SCRIPTS_DIR)/build_scripts/build-debug-kernel.sh << 'EOF'
#!/bin/bash
# 构建调试版内核脚本

set -e

KERNEL_VERSION=${1:-6.1}
BUILD_DIR="$(pwd)/build"
JOBS=${2:-$(nproc)}

echo "构建内核 v$KERNEL_VERSION (使用 $JOBS 个并行任务)..."

cd "$BUILD_DIR/linux-$KERNEL_VERSION"

# 配置调试选项
scripts/config --enable DEBUG_KERNEL
scripts/config --enable DEBUG_INFO
scripts/config --enable KGDB
scripts/config --enable FRAME_POINTER
scripts/config --enable FUNCTION_TRACER

make olddefconfig
make -j$JOBS

echo "内核构建完成!"
EOF
	@chmod +x $(SCRIPTS_DIR)/build_scripts/build-debug-kernel.sh
	@echo -e "$(GREEN)✓ 开发脚本创建完成$(RESET)"

# 清理构建文件
clean:
	@echo -e "$(BLUE)清理构建文件...$(RESET)"
	@rm -rf $(BUILD_DIR)
	@echo -e "$(GREEN)✓ 清理完成$(RESET)"

# 完整安装
install: setup-env install-tools build-kernel setup-qemu create-scripts
	@echo -e "$(GREEN)✓ 内核调试工具链安装完成!$(RESET)"
	@echo ""
	@echo -e "$(BLUE)使用方法:$(RESET)"
	@echo -e "1. 启动QEMU调试: $(BUILD_DIR)/qemu-env/start-debug.sh"
	@echo -e "2. 连接GDB调试: $(BUILD_DIR)/qemu-env/gdb-debug.sh"
	@echo -e "3. 查看文档: cat 文档/debugging_guide.md"

# 显示状态
status:
	@echo -e "$(BLUE)内核调试工具链状态$(RESET)"
	@echo -e "$(BLUE)==================$(RESET)"
	@echo -e "构建目录: $(BUILD_DIR)"
	@echo -e "安装目录: $(INSTALL_DIR)"
	@echo -e "内核版本: $(KERNEL_VERSION)"
	@echo ""
	@echo -e "$(GREEN)已安装工具:$(RESET)"
	@command -v gdb >/dev/null 2>&1 && echo -e "  ✓ GDB" || echo -e "  ✗ GDB"
	@command -v sparse >/dev/null 2>&1 && echo -e "  ✓ Sparse" || echo -e "  ✗ Sparse"
	@command -v perf >/dev/null 2>&1 && echo -e "  ✓ perf" || echo -e "  ✗ perf"
	@command -v qemu-system-x86_64 >/dev/null 2>&1 && echo -e "  ✓ QEMU" || echo -e "  ✗ QEMU"
