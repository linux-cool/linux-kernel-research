#!/bin/bash
# 性能基准测试运行脚本

set -e

# 脚本配置
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
RESULTS_DIR="$PROJECT_DIR/results"
LOG_FILE="$RESULTS_DIR/benchmark_$(date +%Y%m%d_%H%M%S).log"

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# 日志函数
log() {
    echo -e "${BLUE}[$(date '+%Y-%m-%d %H:%M:%S')]${NC} $1" | tee -a "$LOG_FILE"
}

error() {
    echo -e "${RED}[ERROR]${NC} $1" | tee -a "$LOG_FILE"
    exit 1
}

success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1" | tee -a "$LOG_FILE"
}

warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1" | tee -a "$LOG_FILE"
}

# 创建结果目录
setup_results_dir() {
    mkdir -p "$RESULTS_DIR"
    log "结果目录: $RESULTS_DIR"
    log "日志文件: $LOG_FILE"
}

# 检查依赖
check_dependencies() {
    log "检查依赖项..."
    
    local deps=("perf" "stress-ng" "iozone" "netperf")
    local missing=()
    
    for dep in "${deps[@]}"; do
        if ! command -v "$dep" >/dev/null 2>&1; then
            missing+=("$dep")
        fi
    done
    
    if [ ${#missing[@]} -ne 0 ]; then
        warning "缺少依赖: ${missing[*]}"
        log "尝试安装缺少的依赖..."
        
        if command -v apt-get >/dev/null 2>&1; then
            sudo apt-get update
            for dep in "${missing[@]}"; do
                case "$dep" in
                    "perf")
                        sudo apt-get install -y linux-tools-common linux-tools-generic
                        ;;
                    "stress-ng")
                        sudo apt-get install -y stress-ng
                        ;;
                    "iozone")
                        sudo apt-get install -y iozone3
                        ;;
                    "netperf")
                        sudo apt-get install -y netperf
                        ;;
                esac
            done
        else
            error "无法自动安装依赖，请手动安装: ${missing[*]}"
        fi
    fi
    
    success "依赖检查完成"
}

# 系统信息收集
collect_system_info() {
    log "收集系统信息..."
    
    {
        echo "=== 系统信息 ==="
        echo "时间: $(date)"
        echo "主机名: $(hostname)"
        echo "内核版本: $(uname -r)"
        echo "发行版: $(lsb_release -d 2>/dev/null | cut -f2 || echo "Unknown")"
        echo ""
        
        echo "=== CPU信息 ==="
        lscpu | grep -E "(Model name|CPU\(s\)|Thread|Core|MHz)"
        echo ""
        
        echo "=== 内存信息 ==="
        free -h
        echo ""
        
        echo "=== 磁盘信息 ==="
        df -h | head -5
        echo ""
        
        echo "=== 网络信息 ==="
        ip link show | grep -E "(^[0-9]|state UP)"
        echo ""
        
    } | tee -a "$LOG_FILE"
    
    success "系统信息收集完成"
}

# CPU性能测试
run_cpu_benchmark() {
    log "运行CPU性能测试..."
    
    if [ -x "$PROJECT_DIR/bin/cpu_benchmark" ]; then
        log "运行自定义CPU基准测试..."
        "$PROJECT_DIR/bin/cpu_benchmark" | tee -a "$LOG_FILE"
    else
        warning "自定义CPU基准测试程序不存在，使用stress-ng..."
        stress-ng --cpu $(nproc) --timeout 60s --metrics-brief | tee -a "$LOG_FILE"
    fi
    
    log "使用perf进行CPU性能分析..."
    perf stat -e cycles,instructions,cache-misses,cache-references,branch-misses,branches \
        stress-ng --cpu 1 --timeout 30s 2>&1 | tee -a "$LOG_FILE"
    
    success "CPU性能测试完成"
}

# 内存性能测试
run_memory_benchmark() {
    log "运行内存性能测试..."
    
    if [ -x "$PROJECT_DIR/bin/memory_benchmark" ]; then
        log "运行自定义内存基准测试..."
        "$PROJECT_DIR/bin/memory_benchmark" | tee -a "$LOG_FILE"
    else
        warning "自定义内存基准测试程序不存在，使用stress-ng..."
        stress-ng --vm 2 --vm-bytes 1G --timeout 60s --metrics-brief | tee -a "$LOG_FILE"
    fi
    
    log "使用perf进行内存性能分析..."
    perf stat -e cache-misses,cache-references,LLC-loads,LLC-load-misses,dTLB-loads,dTLB-load-misses \
        stress-ng --vm 1 --vm-bytes 512M --timeout 30s 2>&1 | tee -a "$LOG_FILE"
    
    success "内存性能测试完成"
}

# I/O性能测试
run_io_benchmark() {
    log "运行I/O性能测试..."
    
    local test_file="/tmp/iozone_test_$$"
    
    if [ -x "$PROJECT_DIR/bin/io_benchmark" ]; then
        log "运行自定义I/O基准测试..."
        "$PROJECT_DIR/bin/io_benchmark" | tee -a "$LOG_FILE"
    else
        warning "自定义I/O基准测试程序不存在，使用iozone..."
        if command -v iozone >/dev/null 2>&1; then
            iozone -a -s 1G -r 4k -r 16k -r 64k -r 256k -r 1m -f "$test_file" | tee -a "$LOG_FILE"
            rm -f "$test_file"
        else
            warning "iozone不可用，使用dd进行简单测试..."
            log "写入测试:"
            dd if=/dev/zero of="$test_file" bs=1M count=1024 conv=fdatasync 2>&1 | tee -a "$LOG_FILE"
            log "读取测试:"
            dd if="$test_file" of=/dev/null bs=1M 2>&1 | tee -a "$LOG_FILE"
            rm -f "$test_file"
        fi
    fi
    
    log "使用perf进行I/O性能分析..."
    perf stat -e block:block_rq_issue,block:block_rq_complete \
        dd if=/dev/zero of=/tmp/perf_io_test bs=1M count=100 conv=fdatasync 2>&1 | tee -a "$LOG_FILE"
    rm -f /tmp/perf_io_test
    
    success "I/O性能测试完成"
}

# 网络性能测试
run_network_benchmark() {
    log "运行网络性能测试..."
    
    if command -v netperf >/dev/null 2>&1; then
        log "启动netserver..."
        sudo netserver -D >/dev/null 2>&1 || true
        sleep 2
        
        log "TCP流测试:"
        netperf -H localhost -t TCP_STREAM -l 30 2>&1 | tee -a "$LOG_FILE"
        
        log "TCP请求-响应测试:"
        netperf -H localhost -t TCP_RR -l 30 2>&1 | tee -a "$LOG_FILE"
        
        log "UDP流测试:"
        netperf -H localhost -t UDP_STREAM -l 30 2>&1 | tee -a "$LOG_FILE"
        
        # 停止netserver
        sudo pkill netserver >/dev/null 2>&1 || true
    else
        warning "netperf不可用，跳过网络性能测试"
    fi
    
    success "网络性能测试完成"
}

# 系统调用性能测试
run_syscall_benchmark() {
    log "运行系统调用性能测试..."
    
    log "使用perf跟踪系统调用..."
    perf trace -s stress-ng --cpu 1 --timeout 10s 2>&1 | tee -a "$LOG_FILE"
    
    log "系统调用延迟分析..."
    perf stat -e syscalls:sys_enter_open,syscalls:sys_exit_open \
        find /usr -name "*.so" -type f | head -100 >/dev/null 2>&1 | tee -a "$LOG_FILE"
    
    success "系统调用性能测试完成"
}

# 上下文切换性能测试
run_context_switch_benchmark() {
    log "运行上下文切换性能测试..."
    
    log "进程创建性能测试..."
    perf stat -e task-clock,context-switches,cpu-migrations,page-faults \
        stress-ng --fork 4 --timeout 30s 2>&1 | tee -a "$LOG_FILE"
    
    log "线程切换性能测试..."
    perf stat -e sched:sched_switch \
        stress-ng --pthread 4 --timeout 30s 2>&1 | tee -a "$LOG_FILE"
    
    success "上下文切换性能测试完成"
}

# 生成性能报告
generate_report() {
    log "生成性能报告..."
    
    local report_file="$RESULTS_DIR/performance_report_$(date +%Y%m%d_%H%M%S).html"
    
    cat > "$report_file" << 'EOF'
<!DOCTYPE html>
<html>
<head>
    <title>Linux内核性能测试报告</title>
    <style>
        body { font-family: Arial, sans-serif; margin: 20px; }
        h1, h2 { color: #333; }
        .section { margin: 20px 0; padding: 15px; border: 1px solid #ddd; }
        .metric { background: #f5f5f5; padding: 10px; margin: 5px 0; }
        pre { background: #f0f0f0; padding: 10px; overflow-x: auto; }
    </style>
</head>
<body>
    <h1>Linux内核性能测试报告</h1>
    <div class="section">
        <h2>测试概要</h2>
        <div class="metric">测试时间: $(date)</div>
        <div class="metric">测试主机: $(hostname)</div>
        <div class="metric">内核版本: $(uname -r)</div>
    </div>
    
    <div class="section">
        <h2>详细结果</h2>
        <p>详细的测试结果请查看日志文件: <code>$LOG_FILE</code></p>
    </div>
</body>
</html>
EOF
    
    log "性能报告已生成: $report_file"
    success "报告生成完成"
}

# 清理函数
cleanup() {
    log "清理临时文件..."
    # 停止可能运行的服务
    sudo pkill netserver >/dev/null 2>&1 || true
    # 清理临时文件
    rm -f /tmp/iozone_test_* /tmp/perf_io_test
}

# 主函数
main() {
    log "开始Linux内核性能基准测试"
    log "============================="
    
    # 设置清理陷阱
    trap cleanup EXIT
    
    setup_results_dir
    check_dependencies
    collect_system_info
    
    log "开始性能测试..."
    
    run_cpu_benchmark
    run_memory_benchmark
    run_io_benchmark
    run_network_benchmark
    run_syscall_benchmark
    run_context_switch_benchmark
    
    generate_report
    
    success "所有性能测试完成!"
    log "结果保存在: $RESULTS_DIR"
    log "详细日志: $LOG_FILE"
}

# 检查是否以root权限运行某些测试
if [ "$EUID" -ne 0 ]; then
    warning "某些测试需要root权限，可能会提示输入密码"
fi

# 运行主函数
main "$@"
