/*
 * Linux内核CFS调度器分析模块
 * 
 * 本模块用于分析CFS(完全公平调度器)的实现机制
 * 包括虚拟运行时间、负载均衡等核心算法
 */

#include <linux/module.h>
#include <linux/kernel.h>
#include <linux/init.h>
#include <linux/sched.h>
#include <linux/proc_fs.h>
#include <linux/seq_file.h>
#include <linux/slab.h>
#include <linux/cpumask.h>

MODULE_LICENSE("GPL");
MODULE_AUTHOR("Scheduler Research Team");
MODULE_DESCRIPTION("CFS Scheduler Analysis Module");
MODULE_VERSION("1.0");

static struct proc_dir_entry *proc_entry;

/* 分析CFS运行队列状态 */
static void analyze_cfs_runqueue(void)
{
    int cpu;
    struct rq *rq;
    struct cfs_rq *cfs_rq;
    
    printk(KERN_INFO "=== CFS Runqueue Analysis ===\n");
    
    for_each_online_cpu(cpu) {
        rq = cpu_rq(cpu);
        cfs_rq = &rq->cfs;
        
        printk(KERN_INFO "CPU %d:\n", cpu);
        printk(KERN_INFO "  CFS tasks: %d\n", cfs_rq->nr_running);
        printk(KERN_INFO "  Load weight: %lu\n", cfs_rq->load.weight);
        
        if (cfs_rq->curr) {
            printk(KERN_INFO "  Current task: %s (PID: %d)\n",
                   cfs_rq->curr->comm, task_pid_nr(cfs_rq->curr));
            printk(KERN_INFO "  Current vruntime: %llu\n",
                   cfs_rq->curr->se.vruntime);
        }
        
        printk(KERN_INFO "  Min vruntime: %llu\n", cfs_rq->min_vruntime);
        printk(KERN_INFO "  RB tree leftmost: %s\n",
               cfs_rq->rb_leftmost ? "Yes" : "No");
        printk(KERN_INFO "\n");
    }
}

/* 分析调度实体的权重和优先级 */
static void analyze_sched_entity_weights(void)
{
    struct task_struct *task;
    int count = 0;
    
    printk(KERN_INFO "=== Scheduling Entity Weights Analysis ===\n");
    
    rcu_read_lock();
    for_each_process(task) {
        if (count++ > 10) break; /* 限制输出数量 */
        
        if (task->sched_class == &fair_sched_class) {
            printk(KERN_INFO "Task: %s (PID: %d)\n", task->comm, task->pid);
            printk(KERN_INFO "  Nice value: %d\n", task_nice(task));
            printk(KERN_INFO "  Weight: %lu\n", task->se.load.weight);
            printk(KERN_INFO "  Vruntime: %llu\n", task->se.vruntime);
            printk(KERN_INFO "  Sum exec runtime: %llu\n", task->se.sum_exec_runtime);
            printk(KERN_INFO "\n");
        }
    }
    rcu_read_unlock();
}

/* 计算负载均衡统计信息 */
static void analyze_load_balance(void)
{
    int cpu;
    struct rq *rq;
    unsigned long total_load = 0;
    unsigned long max_load = 0;
    unsigned long min_load = ULONG_MAX;
    int max_cpu = -1, min_cpu = -1;
    
    printk(KERN_INFO "=== Load Balance Analysis ===\n");
    
    for_each_online_cpu(cpu) {
        rq = cpu_rq(cpu);
        unsigned long cpu_load = cpu_rq_load_avg(rq);
        
        total_load += cpu_load;
        
        if (cpu_load > max_load) {
            max_load = cpu_load;
            max_cpu = cpu;
        }
        
        if (cpu_load < min_load) {
            min_load = cpu_load;
            min_cpu = cpu;
        }
        
        printk(KERN_INFO "CPU %d load: %lu\n", cpu, cpu_load);
    }
    
    printk(KERN_INFO "Total load: %lu\n", total_load);
    printk(KERN_INFO "Average load: %lu\n", total_load / num_online_cpus());
    printk(KERN_INFO "Max load: %lu (CPU %d)\n", max_load, max_cpu);
    printk(KERN_INFO "Min load: %lu (CPU %d)\n", min_load, min_cpu);
    
    if (max_load > 0 && min_load < ULONG_MAX) {
        unsigned long imbalance = (max_load - min_load) * 100 / max_load;
        printk(KERN_INFO "Load imbalance: %lu%%\n", imbalance);
    }
}

/* 分析调度延迟 */
static void analyze_sched_latency(void)
{
    int cpu;
    struct rq *rq;
    
    printk(KERN_INFO "=== Scheduling Latency Analysis ===\n");
    
    for_each_online_cpu(cpu) {
        rq = cpu_rq(cpu);
        
        printk(KERN_INFO "CPU %d:\n", cpu);
        printk(KERN_INFO "  Clock: %llu\n", rq->clock);
        printk(KERN_INFO "  Clock task: %llu\n", rq->clock_task);
        
        if (rq->curr) {
            u64 delta = rq->clock_task - rq->curr->se.exec_start;
            printk(KERN_INFO "  Current task runtime: %llu ns\n", delta);
        }
        
        /* 分析CFS相关的延迟参数 */
        printk(KERN_INFO "  CFS period: %u ns\n", sysctl_sched_latency);
        printk(KERN_INFO "  CFS slice: %u ns\n", sysctl_sched_min_granularity);
        printk(KERN_INFO "\n");
    }
}

/* proc文件系统接口 */
static int cfs_proc_show(struct seq_file *m, void *v)
{
    int cpu;
    struct rq *rq;
    struct cfs_rq *cfs_rq;
    
    seq_printf(m, "CFS Scheduler Status\n");
    seq_printf(m, "===================\n\n");
    
    for_each_online_cpu(cpu) {
        rq = cpu_rq(cpu);
        cfs_rq = &rq->cfs;
        
        seq_printf(m, "CPU %d:\n", cpu);
        seq_printf(m, "  Running tasks: %d\n", cfs_rq->nr_running);
        seq_printf(m, "  Load weight: %lu\n", cfs_rq->load.weight);
        seq_printf(m, "  Min vruntime: %llu\n", cfs_rq->min_vruntime);
        
        if (cfs_rq->curr) {
            seq_printf(m, "  Current: %s (vruntime: %llu)\n",
                      cfs_rq->curr->comm, cfs_rq->curr->se.vruntime);
        }
        
        seq_printf(m, "\n");
    }
    
    return 0;
}

static int cfs_proc_open(struct inode *inode, struct file *file)
{
    return single_open(file, cfs_proc_show, NULL);
}

static const struct proc_ops cfs_proc_ops = {
    .proc_open = cfs_proc_open,
    .proc_read = seq_read,
    .proc_lseek = seq_lseek,
    .proc_release = single_release,
};

static int __init cfs_analysis_init(void)
{
    printk(KERN_INFO "CFS Scheduler Analysis Module loaded\n");
    
    /* 创建proc文件 */
    proc_entry = proc_create("cfs_status", 0444, NULL, &cfs_proc_ops);
    if (!proc_entry) {
        printk(KERN_ERR "Failed to create proc entry\n");
        return -ENOMEM;
    }
    
    /* 执行分析 */
    analyze_cfs_runqueue();
    analyze_sched_entity_weights();
    analyze_load_balance();
    analyze_sched_latency();
    
    return 0;
}

static void __exit cfs_analysis_exit(void)
{
    if (proc_entry) {
        proc_remove(proc_entry);
    }
    
    printk(KERN_INFO "CFS Scheduler Analysis Module unloaded\n");
}

module_init(cfs_analysis_init);
module_exit(cfs_analysis_exit);
