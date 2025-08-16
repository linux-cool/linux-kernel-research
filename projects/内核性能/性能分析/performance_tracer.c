/*
 * 内核性能跟踪模块
 * 用于跟踪内核函数调用性能和系统调用延迟
 */

#include <linux/module.h>
#include <linux/kernel.h>
#include <linux/init.h>
#include <linux/proc_fs.h>
#include <linux/seq_file.h>
#include <linux/uaccess.h>
#include <linux/kprobes.h>
#include <linux/time.h>
#include <linux/slab.h>
#include <linux/spinlock.h>
#include <linux/hashtable.h>

#define MODULE_NAME "performance_tracer"
#define HASH_BITS 8
#define MAX_FUNCTION_NAME 64
#define MAX_TRACE_ENTRIES 1000

// 性能跟踪条目
struct perf_trace_entry {
    char function_name[MAX_FUNCTION_NAME];
    unsigned long call_count;
    unsigned long total_time_ns;
    unsigned long min_time_ns;
    unsigned long max_time_ns;
    struct hlist_node hash_node;
};

// 函数调用上下文
struct function_call_context {
    ktime_t start_time;
    char function_name[MAX_FUNCTION_NAME];
};

// 全局变量
static DEFINE_HASHTABLE(perf_hash_table, HASH_BITS);
static DEFINE_SPINLOCK(perf_lock);
static struct proc_dir_entry *proc_entry;
static bool tracing_enabled = true;
static unsigned long trace_count = 0;

// 内核探针结构
static struct kprobe kp_sys_open;
static struct kprobe kp_sys_read;
static struct kprobe kp_sys_write;
static struct kprobe kp_do_fork;

// 查找或创建性能跟踪条目
static struct perf_trace_entry *find_or_create_entry(const char *func_name) {
    struct perf_trace_entry *entry;
    unsigned long hash_key = jhash(func_name, strlen(func_name), 0);
    
    // 查找现有条目
    hash_for_each_possible(perf_hash_table, entry, hash_node, hash_key) {
        if (strcmp(entry->function_name, func_name) == 0) {
            return entry;
        }
    }
    
    // 创建新条目
    entry = kmalloc(sizeof(*entry), GFP_ATOMIC);
    if (!entry)
        return NULL;
    
    strncpy(entry->function_name, func_name, MAX_FUNCTION_NAME - 1);
    entry->function_name[MAX_FUNCTION_NAME - 1] = '\0';
    entry->call_count = 0;
    entry->total_time_ns = 0;
    entry->min_time_ns = ULONG_MAX;
    entry->max_time_ns = 0;
    
    hash_add(perf_hash_table, &entry->hash_node, hash_key);
    return entry;
}

// 更新性能统计
static void update_perf_stats(const char *func_name, unsigned long duration_ns) {
    struct perf_trace_entry *entry;
    unsigned long flags;
    
    if (!tracing_enabled || trace_count >= MAX_TRACE_ENTRIES)
        return;
    
    spin_lock_irqsave(&perf_lock, flags);
    
    entry = find_or_create_entry(func_name);
    if (entry) {
        entry->call_count++;
        entry->total_time_ns += duration_ns;
        
        if (duration_ns < entry->min_time_ns)
            entry->min_time_ns = duration_ns;
        
        if (duration_ns > entry->max_time_ns)
            entry->max_time_ns = duration_ns;
        
        trace_count++;
    }
    
    spin_unlock_irqrestore(&perf_lock, flags);
}

// kprobe处理函数 - 函数入口
static int kprobe_pre_handler(struct kprobe *p, struct pt_regs *regs) {
    struct function_call_context *ctx;
    
    ctx = kmalloc(sizeof(*ctx), GFP_ATOMIC);
    if (!ctx)
        return 0;
    
    ctx->start_time = ktime_get();
    strncpy(ctx->function_name, p->symbol_name, MAX_FUNCTION_NAME - 1);
    ctx->function_name[MAX_FUNCTION_NAME - 1] = '\0';
    
    // 将上下文存储在寄存器中（简化实现）
    regs->ax = (unsigned long)ctx;
    
    return 0;
}

// kprobe处理函数 - 函数出口
static void kprobe_post_handler(struct kprobe *p, struct pt_regs *regs, 
                                unsigned long flags) {
    struct function_call_context *ctx;
    ktime_t end_time;
    unsigned long duration_ns;
    
    ctx = (struct function_call_context *)regs->ax;
    if (!ctx)
        return;
    
    end_time = ktime_get();
    duration_ns = ktime_to_ns(ktime_sub(end_time, ctx->start_time));
    
    update_perf_stats(ctx->function_name, duration_ns);
    
    kfree(ctx);
}

// sys_open探针
static int sys_open_pre_handler(struct kprobe *p, struct pt_regs *regs) {
    return kprobe_pre_handler(p, regs);
}

static void sys_open_post_handler(struct kprobe *p, struct pt_regs *regs, 
                                  unsigned long flags) {
    kprobe_post_handler(p, regs, flags);
}

// 初始化kprobe
static int init_kprobes(void) {
    int ret;
    
    // sys_open探针
    kp_sys_open.symbol_name = "do_sys_open";
    kp_sys_open.pre_handler = sys_open_pre_handler;
    kp_sys_open.post_handler = sys_open_post_handler;
    
    ret = register_kprobe(&kp_sys_open);
    if (ret < 0) {
        pr_err("register_kprobe failed for sys_open: %d\n", ret);
        return ret;
    }
    
    pr_info("kprobe registered for %s\n", kp_sys_open.symbol_name);
    return 0;
}

// 清理kprobe
static void cleanup_kprobes(void) {
    unregister_kprobe(&kp_sys_open);
    pr_info("kprobe unregistered\n");
}

// proc文件显示函数
static int perf_proc_show(struct seq_file *m, void *v) {
    struct perf_trace_entry *entry;
    unsigned long flags;
    int bucket;
    
    seq_printf(m, "Linux内核性能跟踪报告\n");
    seq_printf(m, "======================\n\n");
    seq_printf(m, "跟踪状态: %s\n", tracing_enabled ? "启用" : "禁用");
    seq_printf(m, "总跟踪次数: %lu\n\n", trace_count);
    
    seq_printf(m, "%-20s %10s %15s %15s %15s %15s\n",
               "函数名", "调用次数", "总时间(ns)", "平均时间(ns)", 
               "最小时间(ns)", "最大时间(ns)");
    seq_printf(m, "%-20s %10s %15s %15s %15s %15s\n",
               "--------------------", "----------", "---------------",
               "---------------", "---------------", "---------------");
    
    spin_lock_irqsave(&perf_lock, flags);
    
    hash_for_each(perf_hash_table, bucket, entry, hash_node) {
        unsigned long avg_time = entry->call_count > 0 ? 
                                entry->total_time_ns / entry->call_count : 0;
        
        seq_printf(m, "%-20s %10lu %15lu %15lu %15lu %15lu\n",
                   entry->function_name,
                   entry->call_count,
                   entry->total_time_ns,
                   avg_time,
                   entry->min_time_ns == ULONG_MAX ? 0 : entry->min_time_ns,
                   entry->max_time_ns);
    }
    
    spin_unlock_irqrestore(&perf_lock, flags);
    
    seq_printf(m, "\n使用方法:\n");
    seq_printf(m, "  echo 1 > /proc/perf_tracer  # 启用跟踪\n");
    seq_printf(m, "  echo 0 > /proc/perf_tracer  # 禁用跟踪\n");
    seq_printf(m, "  echo clear > /proc/perf_tracer  # 清空统计\n");
    
    return 0;
}

// proc文件写入函数
static ssize_t perf_proc_write(struct file *file, const char __user *buffer,
                               size_t count, loff_t *pos) {
    char cmd[16];
    unsigned long flags;
    struct perf_trace_entry *entry;
    struct hlist_node *tmp;
    int bucket;
    
    if (count >= sizeof(cmd))
        return -EINVAL;
    
    if (copy_from_user(cmd, buffer, count))
        return -EFAULT;
    
    cmd[count] = '\0';
    
    if (strncmp(cmd, "1", 1) == 0) {
        tracing_enabled = true;
        pr_info("Performance tracing enabled\n");
    } else if (strncmp(cmd, "0", 1) == 0) {
        tracing_enabled = false;
        pr_info("Performance tracing disabled\n");
    } else if (strncmp(cmd, "clear", 5) == 0) {
        spin_lock_irqsave(&perf_lock, flags);
        
        hash_for_each_safe(perf_hash_table, bucket, tmp, entry, hash_node) {
            hash_del(&entry->hash_node);
            kfree(entry);
        }
        
        trace_count = 0;
        spin_unlock_irqrestore(&perf_lock, flags);
        pr_info("Performance statistics cleared\n");
    }
    
    return count;
}

// proc文件操作
static int perf_proc_open(struct inode *inode, struct file *file) {
    return single_open(file, perf_proc_show, NULL);
}

static const struct proc_ops perf_proc_ops = {
    .proc_open = perf_proc_open,
    .proc_read = seq_read,
    .proc_write = perf_proc_write,
    .proc_lseek = seq_lseek,
    .proc_release = single_release,
};

// 模块初始化
static int __init perf_tracer_init(void) {
    int ret;
    
    pr_info("Loading %s module\n", MODULE_NAME);
    
    // 初始化哈希表
    hash_init(perf_hash_table);
    
    // 创建proc文件
    proc_entry = proc_create("perf_tracer", 0666, NULL, &perf_proc_ops);
    if (!proc_entry) {
        pr_err("Failed to create proc entry\n");
        return -ENOMEM;
    }
    
    // 初始化kprobe
    ret = init_kprobes();
    if (ret < 0) {
        proc_remove(proc_entry);
        return ret;
    }
    
    pr_info("%s module loaded successfully\n", MODULE_NAME);
    return 0;
}

// 模块清理
static void __exit perf_tracer_exit(void) {
    struct perf_trace_entry *entry;
    struct hlist_node *tmp;
    unsigned long flags;
    int bucket;
    
    pr_info("Unloading %s module\n", MODULE_NAME);
    
    // 清理kprobe
    cleanup_kprobes();
    
    // 删除proc文件
    proc_remove(proc_entry);
    
    // 清理哈希表
    spin_lock_irqsave(&perf_lock, flags);
    hash_for_each_safe(perf_hash_table, bucket, tmp, entry, hash_node) {
        hash_del(&entry->hash_node);
        kfree(entry);
    }
    spin_unlock_irqrestore(&perf_lock, flags);
    
    pr_info("%s module unloaded\n", MODULE_NAME);
}

module_init(perf_tracer_init);
module_exit(perf_tracer_exit);

MODULE_LICENSE("GPL");
MODULE_AUTHOR("Linux Kernel Research Team");
MODULE_DESCRIPTION("Kernel Performance Tracer Module");
MODULE_VERSION("1.0");
