# Linux内核安全机制研究 Makefile

# 内核源码路径
KERNEL_DIR := /lib/modules/$(shell uname -r)/build

# 编译器设置
CC := gcc
CFLAGS := -Wall -O2 -g -std=gnu99
LDFLAGS := -lcap -lssl -lcrypto

# 目录设置
SRC_DIR := .
BUILD_DIR := build
BIN_DIR := bin
TEST_DIR := tests

# 颜色输出
GREEN := \033[32m
YELLOW := \033[33m
RED := \033[31m
BLUE := \033[34m
NC := \033[0m

# 安全工具程序
SECURITY_TOOLS := security_scanner vulnerability_analyzer exploit_detector security_monitor
ACCESS_CONTROL_TOOLS := selinux_analyzer apparmor_checker capability_tester
MEMORY_PROTECTION_TOOLS := aslr_tester stack_protector heap_analyzer
CRYPTO_TOOLS := crypto_tester key_manager tpm_interface

# 内核模块
KERNEL_MODULES := security_monitor.ko access_control_enforcer.ko memory_protector.ko

.PHONY: all clean install tools modules tests security-check help

# 默认目标
all: help

# 帮助信息
help:
	@echo -e "$(GREEN)Linux内核安全机制研究构建系统$(NC)"
	@echo -e "$(GREEN)==============================$(NC)"
	@echo ""
	@echo -e "$(YELLOW)可用目标:$(NC)"
	@echo "  tools         - 构建安全分析工具"
	@echo "  modules       - 构建内核安全模块"
	@echo "  tests         - 构建安全测试程序"
	@echo "  security-check - 运行安全检查"
	@echo "  vulnerability-scan - 运行漏洞扫描"
	@echo "  compliance-check - 运行合规性检查"
	@echo "  install       - 安装所有工具和模块"
	@echo "  clean         - 清理构建文件"
	@echo "  help          - 显示此帮助信息"
	@echo ""
	@echo -e "$(YELLOW)使用示例:$(NC)"
	@echo "  make tools            # 构建安全工具"
	@echo "  make security-check   # 运行安全检查"
	@echo "  make vulnerability-scan # 漏洞扫描"

# 创建目录
$(BUILD_DIR) $(BIN_DIR) $(TEST_DIR):
	@mkdir -p $@

# 构建安全工具
tools: $(BIN_DIR) check-deps
	@echo -e "$(GREEN)构建安全分析工具...$(NC)"
	@$(CC) $(CFLAGS) 安全工具/security_scanner/main.c -o $(BIN_DIR)/security_scanner
	@$(CC) $(CFLAGS) 安全工具/vulnerability_analyzer/main.c -o $(BIN_DIR)/vulnerability_analyzer
	@$(CC) $(CFLAGS) 安全工具/exploit_detector/main.c -o $(BIN_DIR)/exploit_detector
	@$(CC) $(CFLAGS) 安全工具/security_monitor/main.c -o $(BIN_DIR)/security_monitor $(LDFLAGS)
	@echo -e "$(GREEN)✓ 安全工具构建完成$(NC)"

# 构建访问控制工具
access-control-tools: $(BIN_DIR)
	@echo -e "$(GREEN)构建访问控制工具...$(NC)"
	@$(CC) $(CFLAGS) 访问控制/selinux/analyzer.c -o $(BIN_DIR)/selinux_analyzer -lselinux
	@$(CC) $(CFLAGS) 访问控制/capabilities/tester.c -o $(BIN_DIR)/capability_tester $(LDFLAGS)
	@$(CC) $(CFLAGS) 访问控制/namespace/manager.c -o $(BIN_DIR)/namespace_manager
	@echo -e "$(GREEN)✓ 访问控制工具构建完成$(NC)"

# 构建内存保护工具
memory-protection-tools: $(BIN_DIR)
	@echo -e "$(GREEN)构建内存保护工具...$(NC)"
	@$(CC) $(CFLAGS) 内存保护/aslr/tester.c -o $(BIN_DIR)/aslr_tester
	@$(CC) $(CFLAGS) 内存保护/stack_protection/analyzer.c -o $(BIN_DIR)/stack_analyzer
	@$(CC) $(CFLAGS) 内存保护/heap_protection/checker.c -o $(BIN_DIR)/heap_checker
	@$(CC) $(CFLAGS) 内存保护/control_flow_integrity/validator.c -o $(BIN_DIR)/cfi_validator
	@echo -e "$(GREEN)✓ 内存保护工具构建完成$(NC)"

# 构建加密工具
crypto-tools: $(BIN_DIR)
	@echo -e "$(GREEN)构建加密工具...$(NC)"
	@$(CC) $(CFLAGS) 加密机制/crypto_api/tester.c -o $(BIN_DIR)/crypto_tester $(LDFLAGS)
	@$(CC) $(CFLAGS) 加密机制/key_management/manager.c -o $(BIN_DIR)/key_manager $(LDFLAGS)
	@$(CC) $(CFLAGS) 加密机制/trusted_computing/tpm_tool.c -o $(BIN_DIR)/tpm_tool $(LDFLAGS)
	@echo -e "$(GREEN)✓ 加密工具构建完成$(NC)"

# 构建内核模块
modules: check-kernel-headers
	@echo -e "$(GREEN)构建内核安全模块...$(NC)"
	@$(MAKE) -C $(KERNEL_DIR) M=$(PWD)/安全工具/security_monitor modules
	@$(MAKE) -C $(KERNEL_DIR) M=$(PWD)/访问控制/access_enforcer modules
	@$(MAKE) -C $(KERNEL_DIR) M=$(PWD)/内存保护/memory_protector modules
	@echo -e "$(GREEN)✓ 内核模块构建完成$(NC)"

# 构建测试程序
tests: $(TEST_DIR)
	@echo -e "$(GREEN)构建安全测试程序...$(NC)"
	@$(CC) $(CFLAGS) 测试用例/security_tests/buffer_overflow_test.c -o $(TEST_DIR)/buffer_overflow_test
	@$(CC) $(CFLAGS) 测试用例/security_tests/privilege_escalation_test.c -o $(TEST_DIR)/privilege_test $(LDFLAGS)
	@$(CC) $(CFLAGS) 测试用例/security_tests/race_condition_test.c -o $(TEST_DIR)/race_test -lpthread
	@$(CC) $(CFLAGS) 测试用例/security_tests/crypto_test.c -o $(TEST_DIR)/crypto_test $(LDFLAGS)
	@echo -e "$(GREEN)✓ 测试程序构建完成$(NC)"

# 运行安全检查
security-check: tools
	@echo -e "$(GREEN)运行系统安全检查...$(NC)"
	@./安全工具/security_scanner/kernel_config_check.sh
	@./安全工具/security_scanner/system_security_check.sh
	@$(BIN_DIR)/security_scanner --full-scan
	@echo -e "$(GREEN)✓ 安全检查完成$(NC)"

# 运行漏洞扫描
vulnerability-scan: tools
	@echo -e "$(GREEN)运行漏洞扫描...$(NC)"
	@$(BIN_DIR)/vulnerability_analyzer --scan-kernel
	@./漏洞检测/static_analysis/run_static_analysis.sh
	@./漏洞检测/dynamic_analysis/run_dynamic_analysis.sh
	@echo -e "$(GREEN)✓ 漏洞扫描完成$(NC)"

# 运行合规性检查
compliance-check:
	@echo -e "$(GREEN)运行安全合规性检查...$(NC)"
	@./测试用例/compliance_tests/cis_benchmark.sh
	@./测试用例/compliance_tests/stig_check.sh
	@./测试用例/compliance_tests/pci_dss_check.sh
	@echo -e "$(GREEN)✓ 合规性检查完成$(NC)"

# 运行渗透测试
penetration-test: tests
	@echo -e "$(GREEN)运行渗透测试...$(NC)"
	@./测试用例/penetration_tests/run_penetration_tests.sh
	@echo -e "$(GREEN)✓ 渗透测试完成$(NC)"

# 模糊测试
fuzzing:
	@echo -e "$(GREEN)运行模糊测试...$(NC)"
	@./漏洞检测/fuzzing/run_syzkaller.sh
	@./漏洞检测/fuzzing/run_trinity.sh
	@echo -e "$(GREEN)✓ 模糊测试完成$(NC)"

# 安装工具和模块
install: tools modules
	@echo -e "$(GREEN)安装安全工具和模块...$(NC)"
	@sudo cp $(BIN_DIR)/* /usr/local/bin/ 2>/dev/null || true
	@sudo $(MAKE) -C $(KERNEL_DIR) M=$(PWD)/安全工具/security_monitor modules_install
	@sudo $(MAKE) -C $(KERNEL_DIR) M=$(PWD)/访问控制/access_enforcer modules_install
	@sudo $(MAKE) -C $(KERNEL_DIR) M=$(PWD)/内存保护/memory_protector modules_install
	@sudo depmod -a
	@echo -e "$(GREEN)✓ 安装完成$(NC)"

# 检查依赖
check-deps:
	@echo -e "$(GREEN)检查依赖项...$(NC)"
	@command -v gcc >/dev/null 2>&1 || { echo -e "$(RED)错误: 需要安装 gcc$(NC)"; exit 1; }
	@command -v make >/dev/null 2>&1 || { echo -e "$(RED)错误: 需要安装 make$(NC)"; exit 1; }
	@pkg-config --exists libcap 2>/dev/null || { echo -e "$(YELLOW)警告: 建议安装 libcap-dev$(NC)"; }
	@pkg-config --exists openssl 2>/dev/null || { echo -e "$(YELLOW)警告: 建议安装 libssl-dev$(NC)"; }
	@echo -e "$(GREEN)✓ 依赖检查完成$(NC)"

# 检查内核头文件
check-kernel-headers:
	@echo -e "$(GREEN)检查内核头文件...$(NC)"
	@if [ ! -d "$(KERNEL_DIR)" ]; then \
		echo -e "$(RED)错误: 内核头文件不存在: $(KERNEL_DIR)$(NC)"; \
		echo -e "$(YELLOW)请安装: sudo apt-get install linux-headers-$$(uname -r)$(NC)"; \
		exit 1; \
	fi
	@echo -e "$(GREEN)✓ 内核头文件检查完成$(NC)"

# 设置安全环境
setup-security-env:
	@echo -e "$(GREEN)设置安全测试环境...$(NC)"
	@sudo sysctl -w kernel.dmesg_restrict=0
	@sudo sysctl -w kernel.kptr_restrict=0
	@sudo sysctl -w kernel.perf_event_paranoid=1
	@echo -e "$(GREEN)✓ 安全环境设置完成$(NC)"

# 生成安全报告
security-report: security-check vulnerability-scan compliance-check
	@echo -e "$(GREEN)生成安全报告...$(NC)"
	@./文档/generate_security_report.sh
	@echo -e "$(GREEN)✓ 安全报告已生成$(NC)"

# 清理构建文件
clean:
	@echo -e "$(GREEN)清理构建文件...$(NC)"
	@rm -rf $(BUILD_DIR) $(BIN_DIR) $(TEST_DIR)
	@$(MAKE) -C $(KERNEL_DIR) M=$(PWD)/安全工具/security_monitor clean 2>/dev/null || true
	@$(MAKE) -C $(KERNEL_DIR) M=$(PWD)/访问控制/access_enforcer clean 2>/dev/null || true
	@$(MAKE) -C $(KERNEL_DIR) M=$(PWD)/内存保护/memory_protector clean 2>/dev/null || true
	@find . -name "*.o" -delete
	@find . -name "*.ko" -delete
	@find . -name "*.mod.c" -delete
	@find . -name "*.mod" -delete
	@find . -name ".*.cmd" -delete
	@find . -name "modules.order" -delete
	@find . -name "Module.symvers" -delete
	@echo -e "$(GREEN)✓ 清理完成$(NC)"

# 显示安全状态
security-status:
	@echo -e "$(GREEN)系统安全状态$(NC)"
	@echo -e "$(GREEN)============$(NC)"
	@echo "SELinux状态:"
	@sestatus 2>/dev/null || echo "SELinux未安装"
	@echo ""
	@echo "AppArmor状态:"
	@aa-status 2>/dev/null || echo "AppArmor未安装"
	@echo ""
	@echo "内核安全配置:"
	@grep -E "(HARDENED|FORTIFY|STACK|SLAB)" /boot/config-$$(uname -r) 2>/dev/null | head -10 || echo "配置文件不可用"
	@echo ""
	@echo "当前安全参数:"
	@echo "  dmesg_restrict: $$(cat /proc/sys/kernel/dmesg_restrict 2>/dev/null || echo 'N/A')"
	@echo "  kptr_restrict: $$(cat /proc/sys/kernel/kptr_restrict 2>/dev/null || echo 'N/A')"
	@echo "  perf_event_paranoid: $$(cat /proc/sys/kernel/perf_event_paranoid 2>/dev/null || echo 'N/A')"

# 安全加固
security-hardening:
	@echo -e "$(GREEN)应用安全加固配置...$(NC)"
	@sudo ./文档/security_hardening.sh
	@echo -e "$(GREEN)✓ 安全加固完成$(NC)"

# 构建所有组件
build-all: tools access-control-tools memory-protection-tools crypto-tools modules tests
	@echo -e "$(GREEN)✓ 所有组件构建完成$(NC)"
