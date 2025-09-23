/* Minimal character device demo: creates /dev/mychardev and echoes data */
#include <linux/module.h>
#include <linux/init.h>
#include <linux/fs.h>
#include <linux/cdev.h>
#include <linux/device.h>
#include <linux/uaccess.h>

#define DRV_NAME "mychardev"
static dev_t devno;
static struct cdev chardev;
static struct class *chardev_class;
static struct device *chardev_dev;

#define KBUF_SZ 256
static char kbuf[KBUF_SZ];
static size_t kbuf_len;

static int cd_open(struct inode *inode, struct file *filp)
{
	try_module_get(THIS_MODULE);
	return 0;
}

static int cd_release(struct inode *inode, struct file *filp)
{
	module_put(THIS_MODULE);
	return 0;
}

static ssize_t cd_read(struct file *f, char __user *ubuf, size_t n, loff_t *ppos)
{
	size_t copy = min(n, kbuf_len - (size_t)*ppos);
	if (*ppos >= kbuf_len)
		return 0;
	if (copy && copy_to_user(ubuf, kbuf + *ppos, copy))
		return -EFAULT;
	*ppos += copy;
	return copy;
}

static ssize_t cd_write(struct file *f, const char __user *ubuf, size_t n, loff_t *ppos)
{
	size_t copy = min_t(size_t, n, KBUF_SZ - 1);
	if (copy_from_user(kbuf, ubuf, copy))
		return -EFAULT;
	kbuf[copy] = '\0';
	kbuf_len = copy;
	*ppos = 0;
	return copy;
}

static const struct file_operations cd_fops = {
	.owner = THIS_MODULE,
	.open = cd_open,
	.release = cd_release,
	.read = cd_read,
	.write = cd_write,
};

static int __init cd_init(void)
{
	int ret;
	ret = alloc_chrdev_region(&devno, 0, 1, DRV_NAME);
	if (ret)
		return ret;
	cdev_init(&chardev, &cd_fops);
	chardev.owner = THIS_MODULE;
	ret = cdev_add(&chardev, devno, 1);
	if (ret)
		goto err_unreg;
	chardev_class = class_create(THIS_MODULE, DRV_NAME);
	if (IS_ERR(chardev_class)) { ret = PTR_ERR(chardev_class); goto err_cdev; }
	chardev_dev = device_create(chardev_class, NULL, devno, NULL, DRV_NAME);
	if (IS_ERR(chardev_dev)) { ret = PTR_ERR(chardev_dev); goto err_class; }
	pr_info("%s loaded: /dev/%s major=%d minor=%d\n", DRV_NAME, DRV_NAME,
		MAJOR(devno), MINOR(devno));
	strscpy(kbuf, "hello\n", KBUF_SZ);
	kbuf_len = strlen(kbuf);
	return 0;
err_class:
	class_destroy(chardev_class);
err_cdev:
	cdev_del(&chardev);
err_unreg:
	unregister_chrdev_region(devno, 1);
	return ret;
}

static void __exit cd_exit(void)
{
	device_destroy(chardev_class, devno);
	class_destroy(chardev_class);
	cdev_del(&chardev);
	unregister_chrdev_region(devno, 1);
	pr_info("%s unloaded\n", DRV_NAME);
}

MODULE_LICENSE("GPL");
MODULE_AUTHOR("Kernel Research Team");
MODULE_DESCRIPTION("Minimal character device demo");
MODULE_VERSION("1.0");
module_init(cd_init);
module_exit(cd_exit);

