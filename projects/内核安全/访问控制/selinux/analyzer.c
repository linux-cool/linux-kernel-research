/*
 * SELinux安全策略分析器
 * 用于分析SELinux策略配置和安全状态
 */

#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>
#include <errno.h>
#include <sys/stat.h>
#include <selinux/selinux.h>
#include <selinux/context.h>
#include <selinux/get_context_list.h>

#define MAX_CONTEXT_LENGTH 256
#define MAX_PATH_LENGTH 512
#define MAX_LINE_LENGTH 1024

// SELinux模式
typedef enum {
    SELINUX_DISABLED = 0,
    SELINUX_PERMISSIVE = 1,
    SELINUX_ENFORCING = 2
} selinux_mode_t;

// 分析结果
typedef struct {
    int total_contexts;
    int user_contexts;
    int role_contexts;
    int type_contexts;
    int domain_transitions;
    int policy_violations;
} selinux_analysis_t;

// 颜色输出
#define COLOR_RED     "\x1b[31m"
#define COLOR_GREEN   "\x1b[32m"
#define COLOR_YELLOW  "\x1b[33m"
#define COLOR_BLUE    "\x1b[34m"
#define COLOR_RESET   "\x1b[0m"

// 检查SELinux状态
int check_selinux_status(void) {
    printf("=== SELinux状态检查 ===\n");
    
    if (!is_selinux_enabled()) {
        printf("%sSELinux状态: 禁用%s\n", COLOR_RED, COLOR_RESET);
        printf("建议: 启用SELinux以增强系统安全性\n\n");
        return -1;
    }
    
    int mode = security_getenforce();
    const char *mode_str;
    const char *color;
    
    switch (mode) {
        case SELINUX_ENFORCING:
            mode_str = "强制模式";
            color = COLOR_GREEN;
            break;
        case SELINUX_PERMISSIVE:
            mode_str = "宽松模式";
            color = COLOR_YELLOW;
            break;
        default:
            mode_str = "未知模式";
            color = COLOR_RED;
            break;
    }
    
    printf("%sSELinux状态: 启用%s\n", COLOR_GREEN, COLOR_RESET);
    printf("%s当前模式: %s%s\n", color, mode_str, COLOR_RESET);
    
    // 获取策略版本
    int policy_version = security_policyvers();
    printf("策略版本: %d\n", policy_version);
    
    // 获取策略类型
    char *policy_type = NULL;
    if (selinux_getpolicytype(&policy_type) == 0) {
        printf("策略类型: %s\n", policy_type);
        free(policy_type);
    }
    
    printf("\n");
    return 0;
}

// 分析进程安全上下文
void analyze_process_contexts(selinux_analysis_t *analysis) {
    printf("=== 进程安全上下文分析 ===\n");
    
    FILE *proc_file = fopen("/proc/self/attr/current", "r");
    if (!proc_file) {
        printf("%s错误: 无法读取当前进程安全上下文%s\n", COLOR_RED, COLOR_RESET);
        return;
    }
    
    char context[MAX_CONTEXT_LENGTH];
    if (fgets(context, sizeof(context), proc_file)) {
        // 移除换行符
        context[strcspn(context, "\n")] = 0;
        printf("当前进程上下文: %s%s%s\n", COLOR_BLUE, context, COLOR_RESET);
        
        // 解析上下文组件
        context_t ctx = context_new(context);
        if (ctx) {
            printf("  用户: %s\n", context_user_get(ctx));
            printf("  角色: %s\n", context_role_get(ctx));
            printf("  类型: %s\n", context_type_get(ctx));
            printf("  级别: %s\n", context_range_get(ctx));
            context_free(ctx);
            
            analysis->total_contexts++;
        }
    }
    fclose(proc_file);
    
    // 分析系统进程上下文
    printf("\n系统进程上下文示例:\n");
    system("ps -eZ | head -10 | while read line; do echo \"  $line\"; done");
    
    printf("\n");
}

// 分析文件安全上下文
void analyze_file_contexts(selinux_analysis_t *analysis) {
    printf("=== 文件安全上下文分析 ===\n");
    
    const char *important_paths[] = {
        "/etc/passwd",
        "/etc/shadow",
        "/bin/bash",
        "/usr/bin/sudo",
        "/var/log/messages",
        NULL
    };
    
    for (int i = 0; important_paths[i] != NULL; i++) {
        char *context = NULL;
        if (getfilecon(important_paths[i], &context) >= 0) {
            printf("%-20s: %s%s%s\n", important_paths[i], COLOR_BLUE, context, COLOR_RESET);
            freecon(context);
            analysis->total_contexts++;
        } else {
            printf("%-20s: %s无法获取上下文%s\n", important_paths[i], COLOR_RED, COLOR_RESET);
        }
    }
    
    printf("\n");
}

// 检查SELinux策略规则
void check_policy_rules(selinux_analysis_t *analysis) {
    printf("=== SELinux策略规则检查 ===\n");
    
    // 检查常见的策略违规
    printf("检查常见策略配置:\n");
    
    // 检查是否允许execmem
    int result = security_check_context("system_u:system_r:unconfined_t:s0");
    if (result == 0) {
        printf("  %s警告: 发现unconfined域，可能存在安全风险%s\n", COLOR_YELLOW, COLOR_RESET);
        analysis->policy_violations++;
    }
    
    // 检查布尔值设置
    printf("\n重要SELinux布尔值状态:\n");
    const char *important_booleans[] = {
        "httpd_execmem",
        "httpd_enable_cgi",
        "allow_execstack",
        "allow_execmem",
        NULL
    };
    
    for (int i = 0; important_booleans[i] != NULL; i++) {
        int active, pending;
        if (security_get_boolean_active(important_booleans[i], &active) == 0) {
            security_get_boolean_pending(important_booleans[i], &pending);
            const char *color = active ? COLOR_YELLOW : COLOR_GREEN;
            printf("  %-20s: %s%s%s (pending: %s)\n", 
                   important_booleans[i], color, active ? "开启" : "关闭", COLOR_RESET,
                   pending ? "开启" : "关闭");
        }
    }
    
    printf("\n");
}

// 分析域转换
void analyze_domain_transitions(selinux_analysis_t *analysis) {
    printf("=== 域转换分析 ===\n");
    
    // 检查常见的域转换路径
    printf("常见域转换检查:\n");
    
    // 检查sudo域转换
    char *sudo_context = NULL;
    if (getfilecon("/usr/bin/sudo", &sudo_context) >= 0) {
        printf("  sudo程序上下文: %s\n", sudo_context);
        freecon(sudo_context);
        analysis->domain_transitions++;
    }
    
    // 检查shell域转换
    char *shell_context = NULL;
    if (getfilecon("/bin/bash", &shell_context) >= 0) {
        printf("  shell程序上下文: %s\n", shell_context);
        freecon(shell_context);
        analysis->domain_transitions++;
    }
    
    printf("\n");
}

// 检查SELinux日志
void check_selinux_logs(selinux_analysis_t *analysis) {
    printf("=== SELinux审计日志分析 ===\n");
    
    // 检查最近的AVC拒绝记录
    printf("最近的AVC拒绝记录:\n");
    
    FILE *audit_log = popen("grep 'avc.*denied' /var/log/audit/audit.log 2>/dev/null | tail -5", "r");
    if (audit_log) {
        char line[MAX_LINE_LENGTH];
        int denial_count = 0;
        
        while (fgets(line, sizeof(line), audit_log)) {
            printf("  %s", line);
            denial_count++;
            analysis->policy_violations++;
        }
        
        if (denial_count == 0) {
            printf("  %s未发现最近的AVC拒绝记录%s\n", COLOR_GREEN, COLOR_RESET);
        } else {
            printf("  %s发现 %d 条AVC拒绝记录%s\n", COLOR_YELLOW, denial_count, COLOR_RESET);
        }
        
        pclose(audit_log);
    } else {
        printf("  %s无法访问审计日志%s\n", COLOR_YELLOW, COLOR_RESET);
    }
    
    printf("\n");
}

// 生成安全建议
void generate_security_recommendations(const selinux_analysis_t *analysis) {
    printf("=== 安全建议 ===\n");
    
    if (!is_selinux_enabled()) {
        printf("1. %s启用SELinux%s\n", COLOR_RED, COLOR_RESET);
        printf("   编辑 /etc/selinux/config，设置 SELINUX=enforcing\n");
        printf("   重启系统以应用更改\n\n");
        return;
    }
    
    int mode = security_getenforce();
    if (mode != SELINUX_ENFORCING) {
        printf("1. %s切换到强制模式%s\n", COLOR_YELLOW, COLOR_RESET);
        printf("   执行: setenforce 1\n");
        printf("   永久设置: 编辑 /etc/selinux/config\n\n");
    }
    
    if (analysis->policy_violations > 0) {
        printf("2. %s解决策略违规%s\n", COLOR_YELLOW, COLOR_RESET);
        printf("   发现 %d 个策略违规，建议:\n", analysis->policy_violations);
        printf("   - 检查AVC拒绝日志\n");
        printf("   - 使用audit2allow生成策略规则\n");
        printf("   - 考虑使用sealert分析问题\n\n");
    }
    
    printf("3. %s定期监控%s\n", COLOR_BLUE, COLOR_RESET);
    printf("   - 定期检查审计日志\n");
    printf("   - 监控策略违规\n");
    printf("   - 更新SELinux策略\n");
    printf("   - 培训管理员SELinux知识\n\n");
    
    printf("4. %s最佳实践%s\n", COLOR_GREEN, COLOR_RESET);
    printf("   - 使用最小权限原则\n");
    printf("   - 定制化策略规则\n");
    printf("   - 定期备份策略配置\n");
    printf("   - 测试策略更改\n\n");
}

// 显示分析结果汇总
void show_analysis_summary(const selinux_analysis_t *analysis) {
    printf("=== 分析结果汇总 ===\n");
    printf("总上下文数量: %d\n", analysis->total_contexts);
    printf("域转换数量: %d\n", analysis->domain_transitions);
    printf("策略违规数量: %d\n", analysis->policy_violations);
    
    if (analysis->policy_violations == 0) {
        printf("%s整体安全状态: 良好%s\n", COLOR_GREEN, COLOR_RESET);
    } else if (analysis->policy_violations < 5) {
        printf("%s整体安全状态: 需要关注%s\n", COLOR_YELLOW, COLOR_RESET);
    } else {
        printf("%s整体安全状态: 需要立即处理%s\n", COLOR_RED, COLOR_RESET);
    }
    
    printf("\n");
}

int main(int argc, char *argv[]) {
    selinux_analysis_t analysis = {0};
    
    printf("SELinux安全策略分析器\n");
    printf("====================\n\n");
    
    // 检查是否有足够权限
    if (geteuid() != 0) {
        printf("%s警告: 建议以root权限运行以获得完整的分析结果%s\n\n", 
               COLOR_YELLOW, COLOR_RESET);
    }
    
    // 执行各项分析
    if (check_selinux_status() == 0) {
        analyze_process_contexts(&analysis);
        analyze_file_contexts(&analysis);
        check_policy_rules(&analysis);
        analyze_domain_transitions(&analysis);
        check_selinux_logs(&analysis);
    }
    
    show_analysis_summary(&analysis);
    generate_security_recommendations(&analysis);
    
    return 0;
}
