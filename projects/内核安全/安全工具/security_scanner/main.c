/*
 * Linux内核安全扫描器
 * 用于检测内核配置、系统状态和潜在安全问题
 */

#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>
#include <sys/utsname.h>
#include <sys/stat.h>
#include <fcntl.h>
#include <errno.h>
#include <getopt.h>

#define MAX_LINE_LENGTH 1024
#define MAX_PATH_LENGTH 256

// 安全检查结果
typedef enum {
    SECURITY_PASS,
    SECURITY_WARN,
    SECURITY_FAIL,
    SECURITY_INFO
} security_result_t;

// 安全检查项
typedef struct {
    const char *name;
    const char *description;
    security_result_t (*check_func)(void);
} security_check_t;

// 全局选项
static int verbose = 0;
static int full_scan = 0;
static int json_output = 0;

// 颜色输出
#define COLOR_RED     "\x1b[31m"
#define COLOR_GREEN   "\x1b[32m"
#define COLOR_YELLOW  "\x1b[33m"
#define COLOR_BLUE    "\x1b[34m"
#define COLOR_RESET   "\x1b[0m"

// 打印结果
void print_result(const char *check_name, security_result_t result, const char *message) {
    const char *status_str;
    const char *color;
    
    switch (result) {
        case SECURITY_PASS:
            status_str = "PASS";
            color = COLOR_GREEN;
            break;
        case SECURITY_WARN:
            status_str = "WARN";
            color = COLOR_YELLOW;
            break;
        case SECURITY_FAIL:
            status_str = "FAIL";
            color = COLOR_RED;
            break;
        case SECURITY_INFO:
            status_str = "INFO";
            color = COLOR_BLUE;
            break;
        default:
            status_str = "UNKNOWN";
            color = COLOR_RESET;
            break;
    }
    
    if (json_output) {
        printf("  {\n");
        printf("    \"check\": \"%s\",\n", check_name);
        printf("    \"result\": \"%s\",\n", status_str);
        printf("    \"message\": \"%s\"\n", message);
        printf("  },\n");
    } else {
        printf("[%s%-4s%s] %-30s: %s\n", color, status_str, COLOR_RESET, check_name, message);
    }
}

// 读取文件内容
int read_file_content(const char *path, char *buffer, size_t buffer_size) {
    FILE *file = fopen(path, "r");
    if (!file) {
        return -1;
    }
    
    size_t bytes_read = fread(buffer, 1, buffer_size - 1, file);
    buffer[bytes_read] = '\0';
    fclose(file);
    
    return 0;
}

// 检查文件是否存在
int file_exists(const char *path) {
    return access(path, F_OK) == 0;
}

// 检查内核版本
security_result_t check_kernel_version(void) {
    struct utsname uts;
    if (uname(&uts) != 0) {
        return SECURITY_FAIL;
    }
    
    printf("    内核版本: %s %s\n", uts.sysname, uts.release);
    
    // 简单的版本检查（实际应该检查已知漏洞）
    int major, minor, patch;
    if (sscanf(uts.release, "%d.%d.%d", &major, &minor, &patch) == 3) {
        if (major >= 5 || (major == 4 && minor >= 19)) {
            return SECURITY_PASS;
        } else {
            return SECURITY_WARN;
        }
    }
    
    return SECURITY_INFO;
}

// 检查ASLR状态
security_result_t check_aslr(void) {
    char buffer[32];
    if (read_file_content("/proc/sys/kernel/randomize_va_space", buffer, sizeof(buffer)) != 0) {
        return SECURITY_FAIL;
    }
    
    int aslr_level = atoi(buffer);
    printf("    ASLR级别: %d\n", aslr_level);
    
    if (aslr_level == 2) {
        return SECURITY_PASS;
    } else if (aslr_level == 1) {
        return SECURITY_WARN;
    } else {
        return SECURITY_FAIL;
    }
}

// 检查DEP/NX位
security_result_t check_nx_bit(void) {
    if (file_exists("/proc/cpuinfo")) {
        FILE *file = fopen("/proc/cpuinfo", "r");
        char line[MAX_LINE_LENGTH];
        
        while (fgets(line, sizeof(line), file)) {
            if (strstr(line, "flags") && strstr(line, "nx")) {
                fclose(file);
                return SECURITY_PASS;
            }
        }
        fclose(file);
    }
    
    return SECURITY_WARN;
}

// 检查栈保护
security_result_t check_stack_protection(void) {
    // 检查内核配置中的栈保护选项
    if (file_exists("/boot/config-" + strlen("/boot/config-"))) {
        char config_path[MAX_PATH_LENGTH];
        struct utsname uts;
        uname(&uts);
        snprintf(config_path, sizeof(config_path), "/boot/config-%s", uts.release);
        
        FILE *file = fopen(config_path, "r");
        if (file) {
            char line[MAX_LINE_LENGTH];
            int stack_protector = 0;
            
            while (fgets(line, sizeof(line), file)) {
                if (strstr(line, "CONFIG_STACKPROTECTOR=y") ||
                    strstr(line, "CONFIG_STACKPROTECTOR_STRONG=y")) {
                    stack_protector = 1;
                    break;
                }
            }
            fclose(file);
            
            return stack_protector ? SECURITY_PASS : SECURITY_WARN;
        }
    }
    
    return SECURITY_INFO;
}

// 检查SMEP/SMAP
security_result_t check_smep_smap(void) {
    if (file_exists("/proc/cpuinfo")) {
        FILE *file = fopen("/proc/cpuinfo", "r");
        char line[MAX_LINE_LENGTH];
        int smep = 0, smap = 0;
        
        while (fgets(line, sizeof(line), file)) {
            if (strstr(line, "flags")) {
                if (strstr(line, "smep")) smep = 1;
                if (strstr(line, "smap")) smap = 1;
            }
        }
        fclose(file);
        
        printf("    SMEP: %s, SMAP: %s\n", smep ? "支持" : "不支持", smap ? "支持" : "不支持");
        
        if (smep && smap) {
            return SECURITY_PASS;
        } else if (smep || smap) {
            return SECURITY_WARN;
        } else {
            return SECURITY_FAIL;
        }
    }
    
    return SECURITY_INFO;
}

// 检查内核指针限制
security_result_t check_kptr_restrict(void) {
    char buffer[32];
    if (read_file_content("/proc/sys/kernel/kptr_restrict", buffer, sizeof(buffer)) != 0) {
        return SECURITY_FAIL;
    }
    
    int kptr_restrict = atoi(buffer);
    printf("    kptr_restrict: %d\n", kptr_restrict);
    
    if (kptr_restrict >= 2) {
        return SECURITY_PASS;
    } else if (kptr_restrict == 1) {
        return SECURITY_WARN;
    } else {
        return SECURITY_FAIL;
    }
}

// 检查dmesg限制
security_result_t check_dmesg_restrict(void) {
    char buffer[32];
    if (read_file_content("/proc/sys/kernel/dmesg_restrict", buffer, sizeof(buffer)) != 0) {
        return SECURITY_FAIL;
    }
    
    int dmesg_restrict = atoi(buffer);
    printf("    dmesg_restrict: %d\n", dmesg_restrict);
    
    return dmesg_restrict ? SECURITY_PASS : SECURITY_WARN;
}

// 检查perf事件限制
security_result_t check_perf_paranoid(void) {
    char buffer[32];
    if (read_file_content("/proc/sys/kernel/perf_event_paranoid", buffer, sizeof(buffer)) != 0) {
        return SECURITY_FAIL;
    }
    
    int perf_paranoid = atoi(buffer);
    printf("    perf_event_paranoid: %d\n", perf_paranoid);
    
    if (perf_paranoid >= 2) {
        return SECURITY_PASS;
    } else if (perf_paranoid == 1) {
        return SECURITY_WARN;
    } else {
        return SECURITY_FAIL;
    }
}

// 检查SELinux状态
security_result_t check_selinux(void) {
    if (file_exists("/sys/fs/selinux/enforce")) {
        char buffer[32];
        if (read_file_content("/sys/fs/selinux/enforce", buffer, sizeof(buffer)) == 0) {
            int enforcing = atoi(buffer);
            printf("    SELinux: %s\n", enforcing ? "强制模式" : "宽松模式");
            return enforcing ? SECURITY_PASS : SECURITY_WARN;
        }
    }
    
    printf("    SELinux: 未安装或未启用\n");
    return SECURITY_INFO;
}

// 检查AppArmor状态
security_result_t check_apparmor(void) {
    if (file_exists("/sys/kernel/security/apparmor/profiles")) {
        printf("    AppArmor: 已启用\n");
        return SECURITY_PASS;
    }
    
    printf("    AppArmor: 未启用\n");
    return SECURITY_INFO;
}

// 检查模块签名验证
security_result_t check_module_signature(void) {
    char buffer[32];
    if (read_file_content("/proc/sys/kernel/modules_disabled", buffer, sizeof(buffer)) == 0) {
        int modules_disabled = atoi(buffer);
        if (modules_disabled) {
            printf("    模块加载: 已禁用\n");
            return SECURITY_PASS;
        }
    }
    
    // 检查模块签名验证
    if (file_exists("/proc/keys")) {
        FILE *file = fopen("/proc/keys", "r");
        char line[MAX_LINE_LENGTH];
        int has_module_key = 0;
        
        while (fgets(line, sizeof(line), file)) {
            if (strstr(line, "asymmetric") && strstr(line, "module")) {
                has_module_key = 1;
                break;
            }
        }
        fclose(file);
        
        printf("    模块签名验证: %s\n", has_module_key ? "启用" : "未启用");
        return has_module_key ? SECURITY_PASS : SECURITY_WARN;
    }
    
    return SECURITY_INFO;
}

// 安全检查项列表
static security_check_t security_checks[] = {
    {"kernel_version", "内核版本检查", check_kernel_version},
    {"aslr", "地址空间布局随机化", check_aslr},
    {"nx_bit", "NX位支持", check_nx_bit},
    {"stack_protection", "栈保护", check_stack_protection},
    {"smep_smap", "SMEP/SMAP支持", check_smep_smap},
    {"kptr_restrict", "内核指针限制", check_kptr_restrict},
    {"dmesg_restrict", "dmesg访问限制", check_dmesg_restrict},
    {"perf_paranoid", "perf事件限制", check_perf_paranoid},
    {"selinux", "SELinux状态", check_selinux},
    {"apparmor", "AppArmor状态", check_apparmor},
    {"module_signature", "模块签名验证", check_module_signature},
    {NULL, NULL, NULL}
};

// 运行安全检查
void run_security_checks(void) {
    int total_checks = 0;
    int passed_checks = 0;
    int warned_checks = 0;
    int failed_checks = 0;
    
    if (json_output) {
        printf("{\n");
        printf("  \"security_scan_results\": [\n");
    } else {
        printf("\n=== Linux内核安全扫描 ===\n\n");
    }
    
    for (int i = 0; security_checks[i].name != NULL; i++) {
        security_result_t result = security_checks[i].check_func();
        print_result(security_checks[i].name, result, security_checks[i].description);
        
        total_checks++;
        switch (result) {
            case SECURITY_PASS:
                passed_checks++;
                break;
            case SECURITY_WARN:
                warned_checks++;
                break;
            case SECURITY_FAIL:
                failed_checks++;
                break;
            default:
                break;
        }
    }
    
    if (json_output) {
        printf("  ],\n");
        printf("  \"summary\": {\n");
        printf("    \"total\": %d,\n", total_checks);
        printf("    \"passed\": %d,\n", passed_checks);
        printf("    \"warned\": %d,\n", warned_checks);
        printf("    \"failed\": %d\n", failed_checks);
        printf("  }\n");
        printf("}\n");
    } else {
        printf("\n=== 扫描结果汇总 ===\n");
        printf("总检查项: %d\n", total_checks);
        printf("通过: %s%d%s\n", COLOR_GREEN, passed_checks, COLOR_RESET);
        printf("警告: %s%d%s\n", COLOR_YELLOW, warned_checks, COLOR_RESET);
        printf("失败: %s%d%s\n", COLOR_RED, failed_checks, COLOR_RESET);
        
        if (failed_checks > 0) {
            printf("\n%s建议立即修复失败的安全检查项！%s\n", COLOR_RED, COLOR_RESET);
        } else if (warned_checks > 0) {
            printf("\n%s建议关注警告的安全检查项。%s\n", COLOR_YELLOW, COLOR_RESET);
        } else {
            printf("\n%s系统安全状态良好！%s\n", COLOR_GREEN, COLOR_RESET);
        }
    }
}

// 显示帮助信息
void show_help(const char *program_name) {
    printf("Linux内核安全扫描器\n\n");
    printf("用法: %s [选项]\n\n", program_name);
    printf("选项:\n");
    printf("  -f, --full-scan     执行完整扫描\n");
    printf("  -v, --verbose       详细输出\n");
    printf("  -j, --json          JSON格式输出\n");
    printf("  -h, --help          显示此帮助信息\n");
    printf("\n");
    printf("示例:\n");
    printf("  %s                  # 基本安全扫描\n", program_name);
    printf("  %s -f               # 完整安全扫描\n", program_name);
    printf("  %s -j > report.json # JSON格式输出\n", program_name);
}

int main(int argc, char *argv[]) {
    int opt;
    static struct option long_options[] = {
        {"full-scan", no_argument, 0, 'f'},
        {"verbose", no_argument, 0, 'v'},
        {"json", no_argument, 0, 'j'},
        {"help", no_argument, 0, 'h'},
        {0, 0, 0, 0}
    };
    
    while ((opt = getopt_long(argc, argv, "fvjh", long_options, NULL)) != -1) {
        switch (opt) {
            case 'f':
                full_scan = 1;
                break;
            case 'v':
                verbose = 1;
                break;
            case 'j':
                json_output = 1;
                break;
            case 'h':
                show_help(argv[0]);
                return 0;
            default:
                show_help(argv[0]);
                return 1;
        }
    }
    
    // 检查是否有足够权限
    if (geteuid() != 0 && !json_output) {
        printf("%s警告: 建议以root权限运行以获得完整的扫描结果%s\n\n", 
               COLOR_YELLOW, COLOR_RESET);
    }
    
    run_security_checks();
    
    return 0;
}
