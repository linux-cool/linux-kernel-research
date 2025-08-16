#!/bin/bash
# kernel-build-helper.sh - 内核构建辅助脚本
# 提供内核下载、配置、编译、安装的一站式解决方案

set -e

# 脚本配置
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
WORK_DIR="${WORK_DIR:-$HOME/kernel-dev}"
LOG_FILE="$WORK_DIR/build.log"

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# 日志函数
log() {
    echo -e "${BLUE}[$(date '+%Y-%m-%d %H:%M:%S')]${NC} $1" | tee -a "$LOG_FILE"
}

error() {
    echo -e "${RED}[ERROR]${NC} $1" | tee -a "$LOG_FILE"
    exit 1
}

warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1" | tee -a "$LOG_FILE"
}

success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1" | tee -a "$LOG_FILE"
}

# 显示帮助信息
show_help() {
    cat << EOF
内核构建辅助脚本

用法: $0 [选项] <命令>

命令:
    download <version>    - 下载指定版本的内核源码
    config <type>         - 配置内核 (defconfig|localmod|current|debug)
    build                 - 编译内核
    install               - 安装内核
    clean                 - 清理构建文件
    full <version>        - 完整构建流程 (下载+配置+编译)
    status                - 显示构建状态

选项:
    -j, --jobs <num>      - 并行编译任务数 (默认: $(nproc))
    -w, --workdir <dir>   - 工作目录 (默认: $HOME/kernel-dev)
    -v, --verbose         - 详细输出
    -h, --help            - 显示此帮助信息

示例:
    $0 download 6.1.0
    $0 config debug
    $0 build -j8
    $0 full 6.1.0
EOF
}

# 检查依赖
check_dependencies() {
    local deps=("wget" "tar" "make" "gcc" "git")
    local missing=()
    
    for dep in "${deps[@]}"; do
        if ! command -v "$dep" >/dev/null 2>&1; then
            missing+=("$dep")
        fi
    done
    
    if [ ${#missing[@]} -ne 0 ]; then
        error "缺少依赖: ${missing[*]}"
    fi
}

# 创建工作目录
setup_workdir() {
    mkdir -p "$WORK_DIR"
    cd "$WORK_DIR"
    log "工作目录: $WORK_DIR"
}

# 下载内核源码
download_kernel() {
    local version="$1"
    local major_version="${version%%.*}"
    local tarball="linux-${version}.tar.xz"
    local url="https://cdn.kernel.org/pub/linux/kernel/v${major_version}.x/${tarball}"
    
    if [ -z "$version" ]; then
        error "请指定内核版本"
    fi
    
    log "下载内核版本: $version"
    
    if [ -d "linux-$version" ]; then
        warning "内核源码目录已存在: linux-$version"
        return 0
    fi
    
    if [ ! -f "$tarball" ]; then
        log "从 $url 下载内核源码..."
        wget -c "$url" || error "下载失败"
    fi
    
    log "解压内核源码..."
    tar -xf "$tarball" || error "解压失败"
    
    success "内核源码下载完成: linux-$version"
}

# 配置内核
configure_kernel() {
    local config_type="$1"
    local kernel_dir
    
    # 查找内核目录
    kernel_dir=$(find . -maxdepth 1 -type d -name "linux-*" | head -1)
    if [ -z "$kernel_dir" ]; then
        error "未找到内核源码目录"
    fi
    
    cd "$kernel_dir"
    log "配置内核: $config_type (目录: $kernel_dir)"
    
    case "$config_type" in
        "defconfig")
            make defconfig
            ;;
        "localmod")
            make localmodconfig
            ;;
        "current")
            if [ -f "/boot/config-$(uname -r)" ]; then
                cp "/boot/config-$(uname -r)" .config
                make olddefconfig
            else
                warning "当前系统配置文件不存在，使用defconfig"
                make defconfig
            fi
            ;;
        "debug")
            # 使用当前配置或默认配置作为基础
            if [ -f "/boot/config-$(uname -r)" ]; then
                cp "/boot/config-$(uname -r)" .config
            else
                make defconfig
            fi
            
            # 启用调试选项
            log "启用内核调试选项..."
            scripts/config --enable CONFIG_DEBUG_KERNEL
            scripts/config --enable CONFIG_DEBUG_INFO
            scripts/config --enable CONFIG_DEBUG_INFO_DWARF4
            scripts/config --enable CONFIG_FRAME_POINTER
            scripts/config --enable CONFIG_KGDB
            scripts/config --enable CONFIG_KGDB_SERIAL_CONSOLE
            scripts/config --enable CONFIG_MAGIC_SYSRQ
            scripts/config --enable CONFIG_DYNAMIC_DEBUG
            scripts/config --enable CONFIG_FUNCTION_TRACER
            scripts/config --enable CONFIG_FUNCTION_GRAPH_TRACER
            scripts/config --enable CONFIG_PERF_EVENTS
            
            # 禁用可能导致问题的选项
            scripts/config --disable CONFIG_SYSTEM_TRUSTED_KEYS
            scripts/config --disable CONFIG_SYSTEM_REVOCATION_KEYS
            
            make olddefconfig
            ;;
        *)
            error "未知配置类型: $config_type"
            ;;
    esac
    
    success "内核配置完成: $config_type"
    cd "$WORK_DIR"
}

# 编译内核
build_kernel() {
    local jobs="${JOBS:-$(nproc)}"
    local kernel_dir
    
    kernel_dir=$(find . -maxdepth 1 -type d -name "linux-*" | head -1)
    if [ -z "$kernel_dir" ]; then
        error "未找到内核源码目录"
    fi
    
    cd "$kernel_dir"
    
    if [ ! -f ".config" ]; then
        error "内核未配置，请先运行配置命令"
    fi
    
    log "开始编译内核 (使用 $jobs 个并行任务)..."
    local start_time=$(date +%s)
    
    # 编译内核
    if [ "$VERBOSE" = "1" ]; then
        make -j"$jobs" V=1
    else
        make -j"$jobs"
    fi
    
    local end_time=$(date +%s)
    local duration=$((end_time - start_time))
    
    success "内核编译完成 (耗时: ${duration}秒)"
    
    # 显示编译结果
    log "编译结果:"
    log "  内核镜像: $(pwd)/arch/x86/boot/bzImage"
    log "  vmlinux: $(pwd)/vmlinux"
    log "  模块数量: $(find . -name "*.ko" | wc -l)"
    
    cd "$WORK_DIR"
}

# 安装内核
install_kernel() {
    local kernel_dir
    
    kernel_dir=$(find . -maxdepth 1 -type d -name "linux-*" | head -1)
    if [ -z "$kernel_dir" ]; then
        error "未找到内核源码目录"
    fi
    
    cd "$kernel_dir"
    
    if [ ! -f "arch/x86/boot/bzImage" ]; then
        error "内核镜像不存在，请先编译内核"
    fi
    
    log "安装内核模块..."
    sudo make modules_install
    
    log "安装内核..."
    sudo make install
    
    log "更新引导加载器..."
    if command -v update-grub >/dev/null 2>&1; then
        sudo update-grub
    elif command -v grub2-mkconfig >/dev/null 2>&1; then
        sudo grub2-mkconfig -o /boot/grub2/grub.cfg
    else
        warning "未找到引导加载器更新命令"
    fi
    
    success "内核安装完成"
    log "请重启系统以使用新内核"
    
    cd "$WORK_DIR"
}

# 清理构建文件
clean_build() {
    local kernel_dir
    
    kernel_dir=$(find . -maxdepth 1 -type d -name "linux-*" | head -1)
    if [ -z "$kernel_dir" ]; then
        warning "未找到内核源码目录"
        return 0
    fi
    
    cd "$kernel_dir"
    
    log "清理构建文件..."
    make clean
    make mrproper
    
    success "构建文件清理完成"
    cd "$WORK_DIR"
}

# 显示构建状态
show_status() {
    log "构建状态信息"
    log "=============="
    log "工作目录: $WORK_DIR"
    log "日志文件: $LOG_FILE"
    
    # 检查内核源码
    local kernel_dirs=($(find . -maxdepth 1 -type d -name "linux-*" 2>/dev/null))
    if [ ${#kernel_dirs[@]} -eq 0 ]; then
        log "内核源码: 未下载"
    else
        log "内核源码: ${kernel_dirs[*]}"
        
        for dir in "${kernel_dirs[@]}"; do
            cd "$dir"
            if [ -f ".config" ]; then
                log "  $dir: 已配置"
                if [ -f "arch/x86/boot/bzImage" ]; then
                    log "  $dir: 已编译"
                else
                    log "  $dir: 未编译"
                fi
            else
                log "  $dir: 未配置"
            fi
            cd "$WORK_DIR"
        done
    fi
    
    # 显示系统信息
    log ""
    log "系统信息:"
    log "  当前内核: $(uname -r)"
    log "  CPU核心数: $(nproc)"
    log "  可用内存: $(free -h | awk '/^Mem:/ {print $7}')"
    log "  磁盘空间: $(df -h . | awk 'NR==2 {print $4}')"
}

# 完整构建流程
full_build() {
    local version="$1"
    
    if [ -z "$version" ]; then
        error "请指定内核版本"
    fi
    
    log "开始完整构建流程: $version"
    
    download_kernel "$version"
    configure_kernel "debug"
    build_kernel
    
    success "完整构建流程完成"
    log "如需安装内核，请运行: $0 install"
}

# 解析命令行参数
JOBS=$(nproc)
VERBOSE=0

while [[ $# -gt 0 ]]; do
    case $1 in
        -j|--jobs)
            JOBS="$2"
            shift 2
            ;;
        -w|--workdir)
            WORK_DIR="$2"
            shift 2
            ;;
        -v|--verbose)
            VERBOSE=1
            shift
            ;;
        -h|--help)
            show_help
            exit 0
            ;;
        *)
            break
            ;;
    esac
done

# 主程序
main() {
    local command="$1"
    shift
    
    # 检查依赖和设置环境
    check_dependencies
    setup_workdir
    
    case "$command" in
        "download")
            download_kernel "$1"
            ;;
        "config")
            configure_kernel "${1:-defconfig}"
            ;;
        "build")
            build_kernel
            ;;
        "install")
            install_kernel
            ;;
        "clean")
            clean_build
            ;;
        "status")
            show_status
            ;;
        "full")
            full_build "$1"
            ;;
        *)
            echo "未知命令: $command"
            show_help
            exit 1
            ;;
    esac
}

# 如果没有参数，显示帮助
if [ $# -eq 0 ]; then
    show_help
    exit 1
fi

# 执行主程序
main "$@"
