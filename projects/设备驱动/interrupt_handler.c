/* Interrupt handler demo: request_irq if 'irq' param set, otherwise simulate
 * bottom-half with hrtimer + workqueue. Exposes /proc/irq_demo for counters. */
#include <linux/module.h>
#include <linux/init.h>
#include <linux/interrupt.h>
#include <linux/workqueue.h>
#include <linux/hrtimer.h>
#include <linux/ktime.h>
#include <linux/proc_fs.h>
#include <linux/seq_file.h>

static int irq = -1;
module_param(irq, int, 0444);
MODULE_PARM_DESC(irq, "IRQ number to hook; -1 to use timer simulation");

static atomic64_t top_cnt, bh_cnt;
static struct workqueue_struct *wq;
static struct work_struct bh_work;
static struct hrtimer tick;
static struct proc_dir_entry *proc_entry;

static void bh_func(struct work_struct *ws)
{
	atomic64_inc(&bh_cnt);
}

static irqreturn_t demo_irq_handler(int irqnum, void *dev)
{
	atomic64_inc(&top_cnt);
	queue_work(wq, &bh_work);
	return IRQ_HANDLED; /* demo assumes shared-compatible line if used with IRQF_SHARED */
}

/* /proc interface */
static int irqdemo_show(struct seq_file *m, void *v)
{
	seq_printf(m, "irq=%d\n", irq);
	seq_printf(m, "top-half:  %lld\n", (long long)atomic64_read(&top_cnt));
	seq_printf(m, "bottom-half(work): %lld\n", (long long)atomic64_read(&bh_cnt));
	return 0;
}
static int irqdemo_open(struct inode *inode, struct file *file)
{
	return single_open(file, irqdemo_show, NULL);
}
static const struct proc_ops irqdemo_ops = {
	.proc_open = irqdemo_open,
	.proc_read = seq_read,
	.proc_lseek = seq_lseek,
	.proc_release = single_release,
};

/* hrtimer path for simulation */
static enum hrtimer_restart tick_fn(struct hrtimer *t)
{
	atomic64_inc(&top_cnt);
	queue_work(wq, &bh_work);
	hrtimer_forward_now(t, ms_to_ktime(200));
	return HRTIMER_RESTART;
}

static int __init irqdemo_init(void)
{
	int ret = 0;
	atomic64_set(&top_cnt, 0);
	atomic64_set(&bh_cnt, 0);
	wq = alloc_workqueue("irqdemo_wq", WQ_UNBOUND, 0);
	if (!wq) return -ENOMEM;
	INIT_WORK(&bh_work, bh_func);
	proc_entry = proc_create("irq_demo", 0444, NULL, &irqdemo_ops);
	if (!proc_entry) { ret = -ENOMEM; goto err_wq; }
	if (irq >= 0) {
		/* Be conservative: use IRQF_SHARED and dev_id as module ptr */
		ret = request_irq(irq, demo_irq_handler, IRQF_SHARED, "irqdemo", THIS_MODULE);
		if (ret) { pr_err("request_irq failed: %d\n", ret); goto err_proc; }
		pr_info("irqdemo: hooked IRQ %d\n", irq);
	} else {
		hrtimer_init(&tick, CLOCK_MONOTONIC, HRTIMER_MODE_REL_PINNED);
		tick.function = tick_fn;
		hrtimer_start(&tick, ms_to_ktime(200), HRTIMER_MODE_REL_PINNED);
		pr_info("irqdemo: using hrtimer simulation (no real IRQ)\n");
	}
	return 0;
err_proc:
	remove_proc_entry("irq_demo", NULL);
err_wq:
	flush_workqueue(wq);
	destroy_workqueue(wq);
	return ret;
}

static void __exit irqdemo_exit(void)
{
	if (irq >= 0) {
		free_irq(irq, THIS_MODULE);
	} else {
		hrtimer_cancel(&tick);
	}
	remove_proc_entry("irq_demo", NULL);
	flush_workqueue(wq);
	destroy_workqueue(wq);
	pr_info("irqdemo: unloaded\n");
}

MODULE_LICENSE("GPL");
MODULE_AUTHOR("Kernel Research Team");
MODULE_DESCRIPTION("Interrupt handler demo (request_irq or hrtimer simulation)");
MODULE_VERSION("1.0");
module_init(irqdemo_init);
module_exit(irqdemo_exit);

