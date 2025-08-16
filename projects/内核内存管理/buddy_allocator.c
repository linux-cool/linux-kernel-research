/*
 * Linux内核Buddy分配器分析和测试模块
 * 
 * 本模块用于分析Linux内核的buddy分配器实现
 * 包括页面分配、释放和碎片分析
 */

#include <linux/module.h>
#include <linux/kernel.h>
#include <linux/init.h>
#include <linux/mm.h>
#include <linux/gfp.h>
#include <linux/slab.h>
#include <linux/proc_fs.h>
#include <linux/seq_file.h>

MODULE_LICENSE("GPL");
MODULE_AUTHOR("Kernel Research Team");
MODULE_DESCRIPTION("Buddy Allocator Analysis Module");
MODULE_VERSION("1.0");

static struct proc_dir_entry *proc_entry;

/* 分析buddy分配器状态 */
static void analyze_buddy_system(void)
{
    struct zone *zone;
    int order;
    
    printk(KERN_INFO "=== Buddy Allocator Analysis ===\n");
    
    for_each_populated_zone(zone) {
        printk(KERN_INFO "Zone: %s\n", zone->name);
        printk(KERN_INFO "  Free pages: %lu\n", zone_page_state(zone, NR_FREE_PAGES));
        printk(KERN_INFO "  Managed pages: %lu\n", zone_managed_pages(zone));
        
        /* 分析各个order的空闲页面数量 */
        for (order = 0; order < MAX_ORDER; order++) {
            unsigned long free_count = zone->free_area[order].nr_free;
            if (free_count > 0) {
                printk(KERN_INFO "  Order %d: %lu free blocks (%lu pages)\n",
                       order, free_count, free_count << order);
            }
        }
        printk(KERN_INFO "\n");
    }
}

/* 测试页面分配和释放 */
static void test_page_allocation(void)
{
    struct page *page;
    int order;
    
    printk(KERN_INFO "=== Page Allocation Test ===\n");
    
    /* 测试不同order的页面分配 */
    for (order = 0; order <= 3; order++) {
        page = alloc_pages(GFP_KERNEL, order);
        if (page) {
            printk(KERN_INFO "Successfully allocated %d pages (order %d)\n",
                   1 << order, order);
            printk(KERN_INFO "  Page address: 0x%lx\n", page_to_pfn(page));
            
            /* 立即释放页面 */
            __free_pages(page, order);
            printk(KERN_INFO "  Pages freed\n");
        } else {
            printk(KERN_ERR "Failed to allocate pages (order %d)\n", order);
        }
    }
}

/* 内存碎片分析 */
static void analyze_fragmentation(void)
{
    struct zone *zone;
    int order;
    unsigned long total_free = 0;
    unsigned long largest_block = 0;
    
    printk(KERN_INFO "=== Memory Fragmentation Analysis ===\n");
    
    for_each_populated_zone(zone) {
        total_free = 0;
        largest_block = 0;
        
        for (order = 0; order < MAX_ORDER; order++) {
            unsigned long free_count = zone->free_area[order].nr_free;
            unsigned long free_pages = free_count << order;
            
            total_free += free_pages;
            if (free_count > 0 && order > largest_block) {
                largest_block = order;
            }
        }
        
        printk(KERN_INFO "Zone %s:\n", zone->name);
        printk(KERN_INFO "  Total free pages: %lu\n", total_free);
        printk(KERN_INFO "  Largest free block: order %lu (%lu pages)\n",
               largest_block, 1UL << largest_block);
        
        /* 计算碎片指数 */
        if (total_free > 0) {
            unsigned long fragmentation = 100 - (100 * (1UL << largest_block)) / total_free;
            printk(KERN_INFO "  Fragmentation index: %lu%%\n", fragmentation);
        }
    }
}

/* proc文件系统接口 */
static int buddy_proc_show(struct seq_file *m, void *v)
{
    struct zone *zone;
    int order;
    
    seq_printf(m, "Buddy Allocator Status\n");
    seq_printf(m, "======================\n\n");
    
    for_each_populated_zone(zone) {
        seq_printf(m, "Zone: %s\n", zone->name);
        seq_printf(m, "Free pages: %lu\n", zone_page_state(zone, NR_FREE_PAGES));
        
        for (order = 0; order < MAX_ORDER; order++) {
            unsigned long free_count = zone->free_area[order].nr_free;
            if (free_count > 0) {
                seq_printf(m, "Order %d: %lu blocks\n", order, free_count);
            }
        }
        seq_printf(m, "\n");
    }
    
    return 0;
}

static int buddy_proc_open(struct inode *inode, struct file *file)
{
    return single_open(file, buddy_proc_show, NULL);
}

static const struct proc_ops buddy_proc_ops = {
    .proc_open = buddy_proc_open,
    .proc_read = seq_read,
    .proc_lseek = seq_lseek,
    .proc_release = single_release,
};

static int __init buddy_analysis_init(void)
{
    printk(KERN_INFO "Buddy Allocator Analysis Module loaded\n");
    
    /* 创建proc文件 */
    proc_entry = proc_create("buddy_status", 0444, NULL, &buddy_proc_ops);
    if (!proc_entry) {
        printk(KERN_ERR "Failed to create proc entry\n");
        return -ENOMEM;
    }
    
    /* 执行分析 */
    analyze_buddy_system();
    test_page_allocation();
    analyze_fragmentation();
    
    return 0;
}

static void __exit buddy_analysis_exit(void)
{
    if (proc_entry) {
        proc_remove(proc_entry);
    }
    
    printk(KERN_INFO "Buddy Allocator Analysis Module unloaded\n");
}

module_init(buddy_analysis_init);
module_exit(buddy_analysis_exit);
