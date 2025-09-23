/* Minimal platform driver + device pair to demonstrate probe/remove */
#include <linux/module.h>
#include <linux/init.h>
#include <linux/platform_device.h>
#include <linux/of.h>

#define DRV_NAME "augment_platform_demo"

static int demo_probe(struct platform_device *pdev)
{
	dev_info(&pdev->dev, "probe: name=%s id=%d\n", pdev->name, pdev->id);
	return 0;
}

static int demo_remove(struct platform_device *pdev)
{
	dev_info(&pdev->dev, "remove\n");
	return 0;
}

static const struct of_device_id demo_of_match[] = {
	{ .compatible = "augment,mydev" },
	{ }
};
MODULE_DEVICE_TABLE(of, demo_of_match);

static struct platform_driver demo_driver = {
	.probe = demo_probe,
	.remove = demo_remove,
	.driver = {
		.name = DRV_NAME,
		.of_match_table = of_match_ptr(demo_of_match),
	},
};

/* For non-DT environments, create a software platform_device with same name */
static struct platform_device *demo_pdev;

static int __init demo_init(void)
{
	int ret = platform_driver_register(&demo_driver);
	if (ret)
		return ret;
	demo_pdev = platform_device_register_simple(DRV_NAME, -1, NULL, 0);
	if (IS_ERR(demo_pdev)) {
		platform_driver_unregister(&demo_driver);
		return PTR_ERR(demo_pdev);
	}
	pr_info(DRV_NAME ": loaded (driver+device registered)\n");
	return 0;
}

static void __exit demo_exit(void)
{
	platform_device_unregister(demo_pdev);
	platform_driver_unregister(&demo_driver);
	pr_info(DRV_NAME ": unloaded\n");
}

MODULE_LICENSE("GPL");
MODULE_AUTHOR("Kernel Research Team");
MODULE_DESCRIPTION("Minimal platform driver demo");
MODULE_VERSION("1.0");
module_init(demo_init);
module_exit(demo_exit);

