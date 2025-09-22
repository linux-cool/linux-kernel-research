# Linux内核性能分析与优化 Makefile

# 内核源码路径
KERNEL_DIR := /lib/modules/$(shell uname -r)/build

# 编译器设置
CC := gcc
CFLAGS := -Wall -O2 -g

# 目录设置
SRC_DIR := .
BUILD_DIR := build
BIN_DIR := bin

# 颜色输出
GREEN := \033[32m
YELLOW := \033[33m
RED := \033[31m
NC := \033[0m

# 性能测试程序
BENCHMARK_PROGS := cpu_benchmark memory_benchmark io_benchmark network_benchmark
ANALYSIS_PROGS := hotspot_analyzer bottleneck_detector performance_monitor

# 内核模块
KERNEL_MODULES := performance_tracer.ko latency_monitor.ko

.PHONY: all clean install benchmark analysis modules help

# 默认目标
all: help

# 帮助信息
help:
	@echo -e "$(GREEN)Linux内核性能分析与优化构建系统$(NC)"
	@echo -e "$(GREEN)=====================================$(NC)"
	@echo ""
	@echo -e "$(YELLOW)可用目标:$(NC)"
	@echo "  benchmark     - 构建性能基准测试程序"
	@echo "  analysis      - 构建性能分析工具"
	@echo "  modules       - 构建内核模块"
	@echo "  install       - 安装所有程序和模块"
	@echo "  test          - 运行性能测试套件"
	@echo "  monitor       - 启动性能监控"
	@echo "  clean         - 清理构建文件"
	@echo "  help          - 显示此帮助信息"
	@echo ""
	@echo -e "$(YELLOW)使用示例:$(NC)"
	@echo "  make benchmark    # 构建基准测试程序"
	@echo "  make test         # 运行性能测试"
	@echo "  make monitor      # 启动性能监控"

# 创建目录
$(BUILD_DIR) $(BIN_DIR):
	@mkdir -p $@

# 构建基准测试程序
benchmark: $(BIN_DIR) 基准测试/cpu_benchmark.c 基准测试/memory_benchmark.c 基准测试/io_benchmark.c
	@echo -e "$(GREEN)构建性能基准测试程序...$(NC)"
	@$(CC) $(CFLAGS) 基准测试/cpu_benchmark.c -o $(BIN_DIR)/cpu_benchmark -lm
	@$(CC) $(CFLAGS) 基准测试/memory_benchmark.c -o $(BIN_DIR)/memory_benchmark
	@$(CC) $(CFLAGS) 基准测试/io_benchmark.c -o $(BIN_DIR)/io_benchmark
	@echo -e "$(GREEN)✓ 基准测试程序构建完成$(NC)"

# 构建性能分析工具
analysis: $(BIN_DIR) 性能分析/hotspot_analyzer.c 性能分析/performance_monitor.c
	@echo -e "$(GREEN)构建性能分析工具...$(NC)"
	@$(CC) $(CFLAGS) 性能分析/hotspot_analyzer.c -o $(BIN_DIR)/hotspot_analyzer
	@$(CC) $(CFLAGS) 性能分析/performance_monitor.c -o $(BIN_DIR)/performance_monitor -lpthread
	@echo -e "$(GREEN)✓ 性能分析工具构建完成$(NC)"

# 构建内核模块
modules: 性能分析/performance_tracer.c 监控系统/latency_monitor.c
	@echo -e "$(GREEN)构建内核模块...$(NC)"
	@$(MAKE) -C $(KERNEL_DIR) M=$(PWD)/性能分析 modules
	@$(MAKE) -C $(KERNEL_DIR) M=$(PWD)/监控系统 modules
	@echo -e "$(GREEN)✓ 内核模块构建完成$(NC)"

# 安装程序和模块
install: benchmark analysis modules
	@echo -e "$(GREEN)安装性能分析工具...$(NC)"
	@sudo cp $(BIN_DIR)/* /usr/local/bin/ 2>/dev/null || true
	@sudo $(MAKE) -C $(KERNEL_DIR) M=$(PWD)/性能分析 modules_install
	@sudo $(MAKE) -C $(KERNEL_DIR) M=$(PWD)/监控系统 modules_install
	@sudo depmod -a
	@echo -e "$(GREEN)✓ 安装完成$(NC)"

# 运行性能测试套件
test: benchmark
	@echo -e "$(GREEN)运行性能测试套件...$(NC)"
	@./测试用例/run_benchmarks.sh

# 启动性能监控
monitor: analysis
	@echo -e "$(GREEN)启动性能监控系统...$(NC)"
	@./监控系统/start_monitoring.sh

# 运行CPU基准测试
test-cpu: benchmark
	@echo -e "$(GREEN)运行CPU性能测试...$(NC)"
	@$(BIN_DIR)/cpu_benchmark

# 运行内存基准测试
test-memory: benchmark
	@echo -e "$(GREEN)运行内存性能测试...$(NC)"
	@$(BIN_DIR)/memory_benchmark

# 运行I/O基准测试
test-io: benchmark
	@echo -e "$(GREEN)运行I/O性能测试...$(NC)"
	@$(BIN_DIR)/io_benchmark

# 性能分析
analyze: analysis
	@echo -e "$(GREEN)运行性能分析...$(NC)"
	@$(BIN_DIR)/hotspot_analyzer

# 生成性能报告
report:
	@echo -e "$(GREEN)生成性能报告...$(NC)"
	@./文档/generate_report.sh

# 清理构建文件
clean:
	@echo -e "$(GREEN)清理构建文件...$(NC)"
	@rm -rf $(BUILD_DIR) $(BIN_DIR)
	@$(MAKE) -C $(KERNEL_DIR) M=$(PWD)/性能分析 clean 2>/dev/null || true
	@$(MAKE) -C $(KERNEL_DIR) M=$(PWD)/监控系统 clean 2>/dev/null || true
	@find . -name "*.o" -delete
	@find . -name "*.ko" -delete
	@find . -name "*.mod.c" -delete
	@find . -name "*.mod" -delete
	@find . -name ".*.cmd" -delete
	@find . -name "modules.order" -delete
	@find . -name "Module.symvers" -delete
	@echo -e "$(GREEN)✓ 清理完成$(NC)"

# 检查依赖
check-deps:
	@echo -e "$(GREEN)检查依赖项...$(NC)"
	@command -v gcc >/dev/null 2>&1 || { echo -e "$(RED)错误: 需要安装 gcc$(NC)"; exit 1; }
	@command -v make >/dev/null 2>&1 || { echo -e "$(RED)错误: 需要安装 make$(NC)"; exit 1; }
	@command -v perf >/dev/null 2>&1 || { echo -e "$(YELLOW)警告: 建议安装 perf 工具$(NC)"; }
	@echo -e "$(GREEN)✓ 依赖检查完成$(NC)"

# 设置性能测试环境
setup-env:
	@echo -e "$(GREEN)设置性能测试环境...$(NC)"
	@sudo sysctl -w kernel.perf_event_paranoid=1
	@sudo sysctl -w kernel.kptr_restrict=0
	@echo -e "$(GREEN)✓ 环境设置完成$(NC)"

# 显示性能统计
stats:
	@echo -e "$(GREEN)系统性能统计$(NC)"
	@echo -e "$(GREEN)============$(NC)"
	@echo "CPU信息:"
	@lscpu | grep -E "(Model name|CPU\(s\)|Thread|Core)"
	@echo ""
	@echo "内存信息:"
	@free -h
	@echo ""
	@echo "磁盘信息:"
	@df -h | head -5
	@echo ""
	@echo "网络信息:"
	@ip link show | grep -E "(^[0-9]|state UP)"

# 压力测试
stress-test:
	@echo -e "$(GREEN)运行系统压力测试...$(NC)"
	@stress-ng --cpu $(shell nproc) --vm 2 --vm-bytes 1G --timeout 60s --metrics-brief

# 性能回归测试
regression-test:
	@echo -e "$(GREEN)运行性能回归测试...$(NC)"
	@./测试用例/regression_test.sh

# 生成火焰图
flamegraph:
	@echo -e "$(GREEN)生成性能火焰图...$(NC)"
	@perf record -g sleep 10
	@perf script | ./优化技术/flamegraph/stackcollapse-perf.pl | ./优化技术/flamegraph/flamegraph.pl > performance.svg
	@echo -e "$(GREEN)✓ 火焰图已生成: performance.svg$(NC)"
