# 第5章 设备驱动程序开发研究（projects/设备驱动）

本章以 Linux 6.6 LTS 为基线，面向入门读者，采用“先动手、再深入”的体例讲解字符/块/网络驱动框架、设备模型与 sysfs、主次设备号、file_operations、用户空间交互、平台总线与设备树、中断与下半部、DMA API 及常见调试手段。理论段落穿插极短代码片段与可复现实验；完整工程实践将补充至 projects/设备驱动/（计划文件：char_device.c、block_device.c、platform_driver.c、interrupt_handler.c 等）。

> 环境建议：非生产环境（QEMU/KVM/实验机）；需要 sudo/root；建议安装 build-essential、linux-headers-$(uname -r)、iproute2、util-linux、bpfcc/bpftrace（若有）、tracefs 可用。

---
## 5.0 给新手的快速入门教程（10–25分钟）

学习目标
- 用无需自编译代码的方式“触摸”驱动：加载内核自带模块并观测行为
- 认识字符/块/网络驱动的差异，理解“设备节点—驱动—内核—硬件”的链路
- 打开常用观测接口：/proc、/sys、tracefs；掌握基本排错

前置准备
- 已具备 sudo；tracefs 可挂载：`sudo mount -t tracefs nodev /sys/kernel/tracing 2>/dev/null || true`

路径A（网络：dummy 驱动，无需源码）
```bash
# 加载 dummy 网络驱动并创建网卡
sudo modprobe dummy
sudo ip link add dummy0 type dummy || sudo ip link set dummy0 up
ip -s link show dummy0 | sed -n '1,20p'
# 发送本机 ICMP（需 lo/dummy 可达，仅做示例）
ping -c 2 127.0.0.1 >/dev/null || true
# 观测：包统计、/proc/interrupts 与 tracefs 网络事件
cat /proc/interrupts | sed -n '1,5p'
cd /sys/kernel/tracing; echo 0 | sudo tee tracing_on >/dev/null
echo 1 | sudo tee events/net/enable >/dev/null; echo 1 | sudo tee events/napi/enable 2>/dev/null || true
sleep 1; echo 0 | sudo tee tracing_on >/dev/null; tail -n 20 trace
```

路径B（块：loop 驱动与镜像）
```bash
# 使用内核 loop 块驱动，创建镜像并挂载
sudo modprobe loop
mkdir -p /tmp/loopd; cd /tmp/loopd
dd if=/dev/zero of=img bs=1M count=64 status=none
sudo losetup -fP img; lp=$(losetup -a | tail -n1 | cut -d: -f1)
sudo mkfs.ext4 -F $lp >/dev/null; sudo mkdir -p /mnt/loopd; sudo mount $lp /mnt/loopd
# 写入并观察
( dd if=/dev/zero of=/mnt/loopd/f bs=1M count=8 status=none ); grep -E 'Dirty|Writeback' /proc/meminfo
sudo umount /mnt/loopd; sudo losetup -d $lp
```

常见错误与排错
- modprobe: module not found → 发行版未提供；选择另一条路径或安装相应内核模块
- 权限不足 → 使用 sudo；某些 tracefs 事件可能依赖内核裁剪
- losetup/mkfs 失败 → 文件系统工具未安装（e2fsprogs/util-linux）

学习检查点
- 能解释 dummy/loop 分别属于网络/块驱动，并通过 /proc、/sys、tracefs 找到关键证据
- 知道如何在无源码情况下“触摸”驱动行为并读取统计

---
## 5.1 驱动分类与设备模型总览
### Linux驱动架构分类
- 驱动分类：字符（/dev/ttyS0、/dev/null）、块（/dev/sda、loop）、网络（eth0/dummy）
- 设备模型：kobject/driver/device/bus 层次，sysfs 暴露层级（/sys/devices、/sys/class、/sys/bus/...）
- 用户空间节点：主/次设备号（major/minor），udev 根据 sysfs 事件创建设备节点

### 设备模型核心数据结构
```c
// 摘自 projects/设备驱动/device_model_analyzer.c
static void analyze_device_hierarchy(struct device *dev)
{
    struct device *parent;
    struct kobject *kobj;
    
    printk(KERN_INFO "=== Device Hierarchy Analysis ===\n");
    printk(KERN_INFO "Device: %s\n", dev_name(dev));
    
    // 分析kobject层次
    kobj = &dev->kobj;
    printk(KERN_INFO "Kobject name: %s\n", kobj->name ? kobj->name : "none");
    
    // 分析父设备
    parent = dev->parent;
    while (parent) {
        printk(KERN_INFO "Parent: %s\n", dev_name(parent));
        parent = parent->parent;
        if (parent == dev) break; // 防止循环
    }
    
    // 分析所属总线
    if (dev->bus) {
        printk(KERN_INFO "Bus: %s\n", dev->bus->name);
    }
    
    // 分析所属驱动
    if (dev->driver) {
        printk(KERN_INFO "Driver: %s\n", dev->driver->name);
    }
}

// 设备驱动匹配追踪
static int trace_driver_match(struct device *dev, struct device_driver *drv)
{
    printk(KERN_INFO "Driver match attempt:\n");
    printk(KERN_INFO "  Device: %s\n", dev_name(dev));
    printk(KERN_INFO "  Driver: %s\n", drv->name);
    
    if (dev->bus && drv->bus && dev->bus != drv->bus) {
        printk(KERN_INFO "  Result: FAILED (bus mismatch)\n");
        return 0;
    }
    
    return 1; // 继续匹配过程
}
```

### sysfs文件系统分析
```bash
# 查看设备层次结构
find /sys/devices -type d -name "*usb*" -o -name "*pci*" | head -10

# 查看设备属性
ls -la /sys/class/ | head -20
ls -la /sys/bus/ | head -20

# 查看特定设备信息
ls -la /sys/class/net/eth0/ 2>/dev/null || echo "网络设备不存在"
ls -la /sys/block/sda/ 2>/dev/null || echo "块设备不存在"

# 查看设备驱动信息
ls /sys/bus/pci/drivers/ | head -10
ls /sys/bus/usb/drivers/ | head -10

# 查看设备资源
ls /sys/devices/pci0000:00/ -la 2>/dev/null | head -10 || echo "PCI设备不可用"
```

### 设备号管理分析
```c
// 摘自 projects/设备驱动/char_device.c - 设备号分配
static int __init char_device_init(void)
{
    int ret;
    dev_t dev;
    
    // 动态分配设备号
    ret = alloc_chrdev_region(&char_dev, 0, 1, "mychardev");
    if (ret < 0) {
        printk(KERN_ERR "Failed to allocate device number\n");
        return ret;
    }
    
    major = MAJOR(char_dev);
    minor = MINOR(char_dev);
    
    printk(KERN_INFO "Allocated device: major=%d, minor=%d\n", major, minor);
    
    // 注册字符设备
    cdev_init(&char_cdev, &char_fops);
    char_cdev.owner = THIS_MODULE;
    ret = cdev_add(&char_cdev, char_dev, 1);
    
    if (ret) {
        unregister_chrdev_region(char_dev, 1);
        return ret;
    }
    
    // 创建设备类
    char_class = class_create(THIS_MODULE, "mycharclass");
    if (IS_ERR(char_class)) {
        cdev_del(&char_cdev);
        unregister_chrdev_region(char_dev, 1);
        return PTR_ERR(char_class);
    }
    
    // 创建设备节点
    device_create(char_class, NULL, char_dev, NULL, "mychardev");
    
    return 0;
}
```

### 设备热插拔机制
```bash
# 查看设备热插拔事件
udevadm monitor --kernel --subsystem-match=usb &  # 监控USB事件
udevadm monitor --kernel --subsystem-match=block &  # 监控块设备事件

# 查看设备属性
udevadm info -a -p /sys/class/net/eth0 2>/dev/null | head -20 || echo "设备不存在"

# 手动触发设备事件
sudo udevadm trigger --subsystem-match=usb --action=add

# 查看设备序列号
ls /sys/bus/usb/devices/*/serial 2>/dev/null | head -5
```

### 内核模块自动加载
```bash
# 查看模块依赖
modprobe -c | grep "^alias" | head -10

# 查看模块参数
ls /sys/module/ | head -10
ls /sys/module/e1000/parameters/ 2>/dev/null || echo "模块不存在"

# 查看模块信息
modinfo e1000 2>/dev/null || echo "模块不存在"
lsmod | grep -E "(e1000|usb|pci)" | head -5
```

---
## 5.2 字符设备：主次号、cdev 与 file_operations
### 字符设备注册流程
流程：申请主次号 → 初始化 cdev → 绑定 file_operations → 创建设备节点（class/device）
- 关键 API：alloc_chrdev_region、cdev_init/cdev_add、class_create、device_create、copy_to_user/from_user

### 字符设备驱动框架详解
```c
// 摘自 projects/设备驱动/char_device.c - 完整字符设备实现
static struct class *char_class;
static dev_t char_dev;
static struct cdev char_cdev;

static int device_open = 0;
static char device_buffer[256];
static int buffer_size = 0;

static int char_device_open(struct inode *inode, struct file *file)
{
    if (device_open) {
        printk(KERN_WARNING "Device already opened\n");
        return -EBUSY;
    }
    
    device_open++;
    printk(KERN_INFO "Character device opened\n");
    return 0;
}

static int char_device_release(struct inode *inode, struct file *file)
{
    device_open--;
    printk(KERN_INFO "Character device released\n");
    return 0;
}

static ssize_t char_device_read(struct file *file, char __user *user_buffer,
                               size_t size, loff_t *offset)
{
    int bytes_to_read;
    
    if (*offset >= buffer_size) {
        return 0; // EOF
    }
    
    bytes_to_read = min(size, buffer_size - *offset);
    
    if (copy_to_user(user_buffer, device_buffer + *offset, bytes_to_read)) {
        return -EFAULT;
    }
    
    *offset += bytes_to_read;
    printk(KERN_INFO "Read %d bytes from device\n", bytes_to_read);
    
    return bytes_to_read;
}

static ssize_t char_device_write(struct file *file, const char __user *user_buffer,
                                size_t size, loff_t *offset)
{
    int bytes_to_write;
    
    bytes_to_write = min(size, sizeof(device_buffer) - *offset);
    
    if (copy_from_user(device_buffer + *offset, user_buffer, bytes_to_write)) {
        return -EFAULT;
    }
    
    buffer_size = *offset + bytes_to_write;
    printk(KERN_INFO "Written %d bytes to device\n", bytes_to_write);
    
    return bytes_to_write;
}

static long char_device_ioctl(struct file *file, unsigned int cmd, unsigned long arg)
{
    int ret = 0;
    
    switch (cmd) {
    case CHAR_DEVICE_CLEAR:
        buffer_size = 0;
        printk(KERN_INFO "Device buffer cleared\n");
        break;
        
    case CHAR_DEVICE_GET_SIZE:
        ret = put_user(buffer_size, (int __user *)arg);
        break;
        
    default:
        return -EINVAL;
    }
    
    return ret;
}

static struct file_operations char_fops = {
    .owner = THIS_MODULE,
    .open = char_device_open,
    .release = char_device_release,
    .read = char_device_read,
    .write = char_device_write,
    .unlocked_ioctl = char_device_ioctl,
    .llseek = default_llseek,
};
```

### 内存管理分析
```c
// 摘自 projects/设备驱动/memory_analysis.c
static void analyze_copy_performance(void)
{
    char *kernel_buffer;
    char __user *user_buffer;
    unsigned long start, end;
    int i;
    
    kernel_buffer = kmalloc(PAGE_SIZE, GFP_KERNEL);
    if (!kernel_buffer) return;
    
    // 填充测试数据
    for (i = 0; i < PAGE_SIZE; i++) {
        kernel_buffer[i] = i & 0xFF;
    }
    
    start = jiffies;
    
    // 测试copy_to_user性能
    if (copy_to_user(user_buffer, kernel_buffer, PAGE_SIZE)) {
        printk(KERN_ERR "copy_to_user failed\n");
    }
    
    end = jiffies;
    printk(KERN_INFO "copy_to_user: %lu jiffies for %d bytes\n", 
           end - start, PAGE_SIZE);
    
    // 测试copy_from_user性能
    start = jiffies;
    
    if (copy_from_user(kernel_buffer, user_buffer, PAGE_SIZE)) {
        printk(KERN_ERR "copy_from_user failed\n");
    }
    
    end = jiffies;
    printk(KERN_INFO "copy_from_user: %lu jiffies for %d bytes\n", 
           end - start, PAGE_SIZE);
    
    kfree(kernel_buffer);
}
```

### 并发访问控制
```c
// 摘自 projects/设备驱动/concurrent_access.c
static DEFINE_MUTEX(device_mutex);
static atomic_t device_available = ATOMIC_INIT(1);

static int concurrent_device_open(struct inode *inode, struct file *file)
{
    if (!atomic_dec_and_test(&device_available)) {
        atomic_inc(&device_available);
        return -EBUSY;
    }
    
    mutex_lock(&device_mutex);
    // 设备初始化代码
    mutex_unlock(&device_mutex);
    
    return 0;
}

static int concurrent_device_release(struct inode *inode, struct file *file)
{
    mutex_lock(&device_mutex);
    // 设备清理代码
    mutex_unlock(&device_mutex);
    
    atomic_inc(&device_available);
    return 0;
}
```

### 字符设备调试技巧
```bash
# 查看字符设备信息
ls -la /dev/ | grep "^c" | head -10

# 查看设备主次号
ls -la /dev/mychardev 2>/dev/null || echo "设备不存在"
stat /dev/mychardev 2>/dev/null | grep -E "(Device|Major|Minor)" || echo "设备不存在"

# 查看设备驱动
ls /sys/class/mycharclass/ 2>/dev/null || echo "设备类不存在"
cat /proc/devices | grep "mychardev" || echo "设备未注册"

# 测试字符设备功能
echo "Hello, kernel!" > /dev/mychardev 2>/dev/null || echo "写入失败"
cat /dev/mychardev 2>/dev/null || echo "读取失败"

# 使用ioctl
./test_char_device /dev/mychardev clear
./test_char_device /dev/mychardev get_size
```

极短代码片段（字符设备注册框架）：

极短代码片段（字符设备注册框架）：
<augment_code_snippet mode="EXCERPT">
````c
static dev_t devno; static struct cdev c;
alloc_chrdev_region(&devno, 0, 1, "mychardev");
 cdev_init(&c, &fops); c.owner = THIS_MODULE;
 cdev_add(&c, devno, 1);
// 配合 class_create()/device_create() 自动创建设备节点
````
</augment_code_snippet>

极短代码片段（file_operations 读写骨架）：
<augment_code_snippet mode="EXCERPT">
````c
static ssize_t my_read(struct file *f, char __user *ubuf, size_t n, loff_t *ppos){
  char kbuf[32] = "hello\n"; size_t len = min(n, strlen(kbuf));
  if (copy_to_user(ubuf, kbuf, len)) return -EFAULT; return len;
}
static ssize_t my_write(struct file *f, const char __user *ubuf, size_t n, loff_t *ppos){
  char kbuf[32]; size_t len = min(n,(size_t)31);
  if (copy_from_user(kbuf, ubuf, len)) return -EFAULT; kbuf[len]=0; return len;
}
````
</augment_code_snippet>

---
## 5.3 设备节点与 udev：从 cdev 到 /dev/xxx
- 使用 class_create/device_create 可在 /dev 下自动创建设备节点（udev 规则）
- 手工创建：`mknod /dev/mychardev c <major> <minor>`；权限用 `chmod` 管理
- 常见问题：主次号冲突/权限不足；udev 规则匹配与命名

---
## 5.4 平台设备与设备树（ARM/嵌入式常见）
### 平台设备模型详解
平台总线：platform_device ↔ platform_driver；通过 compatible 匹配
- 设备树（Device Tree）：硬件描述从硬编码内核转向 .dts 文件，编译为 .dtb 由 bootloader 传递
- 匹配方式：of_match_table、ACPI、设备 ID 表；probe 中申请资源（内存/IRQ/DMA）、注册中断、创建设备节点

### 平台驱动框架实现
```c
// 摘自 projects/设备驱动/platform_driver.c
static struct platform_device_id my_platform_ids[] = {
    { "my-platform-device", 0 },
    { },
};

static const struct of_device_id my_of_match[] = {
    { .compatible = "mycompany,my-platform-device" },
    { },
};
MODULE_DEVICE_TABLE(of, my_of_match);
MODULE_DEVICE_TABLE(platform, my_platform_ids);

static int my_platform_probe(struct platform_device *pdev)
{
    struct resource *res_mem, *res_irq;
    int ret = 0;
    
    printk(KERN_INFO "Platform device probed: %s\n", pdev->name);
    
    // 获取内存资源
    res_mem = platform_get_resource(pdev, IORESOURCE_MEM, 0);
    if (!res_mem) {
        printk(KERN_ERR "Failed to get memory resource\n");
        return -ENODEV;
    }
    
    printk(KERN_INFO "Memory resource: start=0x%llx, size=0x%llx\n",
           res_mem->start, resource_size(res_mem));
    
    // 获取IRQ资源
    res_irq = platform_get_resource(pdev, IORESOURCE_IRQ, 0);
    if (!res_irq) {
        printk(KERN_WARNING "No IRQ resource found\n");
    } else {
        printk(KERN_INFO "IRQ resource: %lld\n", res_irq->start);
    }
    
    // 获取设备树属性
    if (pdev->dev.of_node) {
        const char *prop_value;
        u32 prop_u32;
        
        if (of_property_read_string(pdev->dev.of_node, "my-string-prop", &prop_value) == 0) {
            printk(KERN_INFO "String property: %s\n", prop_value);
        }
        
        if (of_property_read_u32(pdev->dev.of_node, "my-int-prop", &prop_u32) == 0) {
            printk(KERN_INFO "Integer property: %u\n", prop_u32);
        }
    }
    
    // 创建字符设备
    ret = create_platform_char_device(pdev);
    if (ret) {
        return ret;
    }
    
    return 0;
}

static int my_platform_remove(struct platform_device *pdev)
{
    printk(KERN_INFO "Platform device removed: %s\n", pdev->name);
    
    // 清理工作
    destroy_platform_char_device(pdev);
    
    return 0;
}

static struct platform_driver my_platform_driver = {
    .driver = {
        .name = "my-platform-device",
        .of_match_table = my_of_match,
    },
    .probe = my_platform_probe,
    .remove = my_platform_remove,
    .id_table = my_platform_ids,
};

module_platform_driver(my_platform_driver);
```

### 设备树分析
```bash
# 查看设备树信息
ls /proc/device-tree/ 2>/dev/null || echo "设备树不可用"
cat /proc/device-tree/model 2>/dev/null || echo "设备树模型不可用"

# 查看特定设备节点
find /proc/device-tree/ -name "*usb*" -o -name "*pci*" | head -5

# 查看设备树源（需要编译器）
dtc -I fs /proc/device-tree 2>/dev/null | head -20 || echo "dtc不可用"

# 设备树编译示例
# dtc -I dts -O dtb -o mydevice.dtb mydevice.dts
# dtc -I dtb -O dts -o mydevice.dts mydevice.dtb
```

### ACPI设备分析
```bash
# 查看ACPI设备（x86系统）
acpi -V 2>/dev/null | head -20 || echo "ACPI工具不可用"
ls /sys/bus/acpi/devices/ | head -10

# 查看ACPI表
acpidump 2>/dev/null | head -5 || echo "acpidump不可用"

# ACPI调试
sudo cat /sys/firmware/acpi/tables/DSDT 2>/dev/null | head -10 || echo "ACPI表不可用"
```

### 资源管理分析
```c
// 摘自 projects/设备驱动/resource_manager.c
static int manage_device_resources(struct platform_device *pdev)
{
    struct resource *res;
    void __iomem *base_addr;
    int irq_num;
    int ret = 0;
    
    // 获取内存资源
    res = platform_get_resource(pdev, IORESOURCE_MEM, 0);
    if (res) {
        base_addr = devm_ioremap_resource(&pdev->dev, res);
        if (IS_ERR(base_addr)) {
            return PTR_ERR(base_addr);
        }
        
        printk(KERN_INFO "Memory mapped: %p (phys: 0x%llx)\n", 
               base_addr, res->start);
    }
    
    // 获取IRQ资源
    irq_num = platform_get_irq(pdev, 0);
    if (irq_num > 0) {
        ret = devm_request_irq(&pdev->dev, irq_num, my_irq_handler,
                              IRQF_SHARED, "my-device", pdev);
        if (ret) {
            printk(KERN_ERR "Failed to request IRQ %d\n", irq_num);
            return ret;
        }
        
        printk(KERN_INFO "IRQ requested: %d\n", irq_num);
    }
    
    // 获取DMA资源
    res = platform_get_resource(pdev, IORESOURCE_DMA, 0);
    if (res) {
        printk(KERN_INFO "DMA channel: %lld\n", res->start);
    }
    
    return 0;
}
```

### 平台设备调试
```bash
# 查看平台设备
ls /sys/bus/platform/devices/ | head -10

# 查看平台驱动
ls /sys/bus/platform/drivers/ | head -10

# 查看设备资源
cat /sys/bus/platform/devices/*/resource 2>/dev/null | head -20 || echo "平台设备资源不可用"

# 查看设备驱动绑定
cat /sys/bus/platform/devices/*/driver_override 2>/dev/null || echo "驱动覆盖不可用"

# 手动绑定/解绑驱动
echo "my-platform-driver" > /sys/bus/platform/devices/my-device/driver_override 2>/dev/null || echo "绑定失败"
echo "my-platform-driver" > /sys/bus/platform/drivers/my-platform-driver/bind 2>/dev/null || echo "绑定失败"
echo "my-device" > /sys/bus/platform/drivers/my-platform-driver/unbind 2>/dev/null || echo "解绑失败"
```
- 设备树（DT）：of_match_table、of_property_* 获取配置

极短代码片段（platform_driver 与 DT 匹配）：
<augment_code_snippet mode="EXCERPT">
````c
static const struct of_device_id my_of_match[] = {
  { .compatible = "vendor,mydev" }, {}
};
MODULE_DEVICE_TABLE(of, my_of_match);
static struct platform_driver mydrv = {
  .probe = my_probe, .remove = my_remove,
  .driver = { .name = "mydev", .of_match_table = my_of_match },
};
````
</augment_code_snippet>

---
## 5.5 中断与下半部：request_irq、threaded IRQ、tasklet/workqueue
### 中断处理机制详解
- 注册中断：request_irq/devm_request_irq；threaded IRQ 便于在可睡眠上下文处理
- 下半部：tasklet（轻量、不可睡眠）与 workqueue（可睡眠、延后处理）

### 中断处理框架实现
```c
// 摘自 projects/设备驱动/interrupt_handler.c
static struct workqueue_struct *my_workqueue;
static struct work_struct my_work;
static atomic_t interrupt_count = ATOMIC_INIT(0);
static int irq_number = -1;

// 中断处理函数（上半部）
static irqreturn_t my_irq_handler(int irq, void *dev_id)
{
    struct my_device_data *data = (struct my_device_data *)dev_id;
    
    // 快速处理，不能睡眠
    atomic_inc(&interrupt_count);
    
    // 读取中断状态（假设是寄存器）
    u32 status = readl(data->reg_base + IRQ_STATUS_REG);
    
    // 清除中断
    writel(status, data->reg_base + IRQ_CLEAR_REG);
    
    // 调度工作队列进行繁重处理
    if (status & IMPORTANT_IRQ_MASK) {
        schedule_work(&my_work);
    }
    
    return IRQ_HANDLED;
}

// 工作队列处理函数（下半部）
static void my_work_handler(struct work_struct *work)
{
    struct my_device_data *data = container_of(work, struct my_device_data, work);
    
    // 可以睡眠的繁重处理
    printk(KERN_INFO "Processing interrupt in workqueue\n");
    
    // 模拟耗时操作
    msleep(10);
    
    // 处理数据
    process_interrupt_data(data);
}

// Threaded IRQ实现
static irqreturn_t my_threaded_irq_handler(int irq, void *dev_id)
{
    struct my_device_data *data = (struct my_device_data *)dev_id;
    
    // 上半部：快速检查
    u32 status = readl(data->reg_base + IRQ_STATUS_REG);
    if (!(status & IRQ_PENDING_MASK)) {
        return IRQ_NONE;
    }
    
    return IRQ_WAKE_THREAD;
}

static irqreturn_t my_thread_fn(int irq, void *dev_id)
{
    struct my_device_data *data = (struct my_device_data *)dev_id;
    
    // 下半部：可以睡眠的完整处理
    printk(KERN_INFO "Processing in threaded IRQ\n");
    
    // 清除中断
    writel(IRQ_CLEAR_MASK, data->reg_base + IRQ_CLEAR_REG);
    
    // 处理数据
    process_interrupt_data(data);
    
    return IRQ_HANDLED;
}

// 中断注册函数
static int register_interrupt_handler(struct my_device_data *data)
{
    int ret;
    
    // 创建工作队列
    my_workqueue = create_workqueue("my_workqueue");
    if (!my_workqueue) {
        return -ENOMEM;
    }
    
    // 初始化工作
    INIT_WORK(&my_work, my_work_handler);
    
    // 获取IRQ号
    irq_number = platform_get_irq(data->pdev, 0);
    if (irq_number < 0) {
        destroy_workqueue(my_workqueue);
        return irq_number;
    }
    
    // 注册中断
    ret = request_irq(irq_number, my_irq_handler, IRQF_SHARED,
                     "my-device", data);
    if (ret) {
        destroy_workqueue(my_workqueue);
        return ret;
    }
    
    // 或者使用threaded IRQ
    ret = request_threaded_irq(irq_number, my_threaded_irq_handler,
                              my_thread_fn, IRQF_SHARED | IRQF_ONESHOT,
                              "my-device-threaded", data);
    if (ret) {
        free_irq(irq_number, data);
        destroy_workqueue(my_workqueue);
        return ret;
    }
    
    printk(KERN_INFO "Registered IRQ handler for IRQ %d\n", irq_number);
    
    return 0;
}
```

### Tasklet机制分析
```c
// 摘自 projects/设备驱动/tasklet_demo.c
static struct tasklet_struct my_tasklet;
static atomic_t tasklet_count = ATOMIC_INIT(0);

// Tasklet处理函数（不能睡眠）
static void my_tasklet_handler(unsigned long data)
{
    struct my_device_data *dev_data = (struct my_device_data *)data;
    
    atomic_inc(&tasklet_count);
    
    // 快速处理，不能睡眠
    printk(KERN_INFO "Tasklet executed, count: %d\n", 
           atomic_read(&tasklet_count));
    
    // 处理数据（轻量级）
    if (dev_data->pending_work) {
        process_light_work(dev_data);
        dev_data->pending_work = false;
    }
}

// 调度tasklet
static void schedule_tasklet_work(struct my_device_data *data)
{
    tasklet_schedule(&my_tasklet);
}

static int __init tasklet_demo_init(void)
{
    // 初始化tasklet
    tasklet_init(&my_tasklet, my_tasklet_handler, (unsigned long)&global_device_data);
    
    return 0;
}
```

### 中断统计与调试
```c
// 摘自 projects/设备驱动/irq_stats.c
static void show_interrupt_statistics(void)
{
    int cpu;
    
    printk(KERN_INFO "=== Interrupt Statistics ===\n");
    printk(KERN_INFO "Total interrupts: %d\n", atomic_read(&interrupt_count));
    
    // 显示每个CPU的中断统计
    for_each_online_cpu(cpu) {
        printk(KERN_INFO "CPU %d: %llu interrupts\n", 
               cpu, per_cpu(irq_per_cpu, cpu));
    }
    
    // 显示中断分布
    if (irq_number >= 0) {
        struct irq_desc *desc = irq_to_desc(irq_number);
        if (desc) {
            printk(KERN_INFO "IRQ %d action count: %d\n", 
                   irq_number, desc->action ? 1 : 0);
        }
    }
}

// 中断亲和性设置
static int set_irq_affinity(int irq, int cpu)
{
    cpumask_t mask;
    
    cpumask_clear(&mask);
    cpumask_set_cpu(cpu, &mask);
    
    return irq_set_affinity(irq, &mask);
}
```

### 中断调试技巧
```bash
# 查看中断信息
cat /proc/interrupts | grep -E "(CPU|my-device)" | head -10

# 查看特定中断
watch -n 1 "cat /proc/interrupts | grep 'my-device'" 2>/dev/null || echo "中断未找到"

# 查看中断亲和性
cat /proc/irq/*/smp_affinity 2>/dev/null | head -5

# 设置中断亲和性（需要root）
echo 1 > /proc/irq/16/smp_affinity 2>/dev/null || echo "设置亲和性失败"

# 查看IRQ统计
cat /proc/irq/*/spurious 2>/dev/null | head -10 || echo "IRQ统计不可用"

# 使用ftrace跟踪中断
cd /sys/kernel/tracing 2>/dev/null
echo 1 > events/irq/enable 2>/dev/null || echo "ftrace不可用"
echo 1 > tracing_on 2>/dev/null
echo 0 > tracing_on 2>/dev/null
cat trace | grep -E "(irq|interrupt)" | head -20
```

极短代码片段（注册中断与工作队列）：

---
## 5.6 DMA 基础：coherent vs streaming、cache 与方向
### DMA API架构与分类
DMA（Direct Memory Access）允许外设直接与内存交换数据，无需CPU干预。Linux提供两类DMA API：

**一致性DMA（Coherent DMA）**：
- `dma_alloc_coherent()` 分配CPU和DMA设备都可直接访问的缓存一致性内存
- 无需显式缓存管理，适合小数据量和控制结构
- 实现原理：通过MMU页表属性设置非缓存（UC）或写合并（WC）属性

**流式DMA（Streaming DMA）**：
- `dma_map_single()` / `dma_unmap_single()` 用于已存在内存的临时DMA映射
- 需要显式处理缓存一致性，适合大数据传输
- 支持DMA_TO_DEVICE、DMA_FROM_DEVICE、DMA_BIDIRECTIONAL三种方向

### DMA实现机制详解
```c
// 摘自 projects/设备驱动/dma_coherent_demo.c
static void *coherent_buffer;
static dma_addr_t coherent_dma_addr;

static int init_coherent_dma(struct device *dev, size_t size)
{
    // 分配一致性DMA缓冲区
    coherent_buffer = dma_alloc_coherent(dev, size, &coherent_dma_addr, GFP_KERNEL);
    if (!coherent_buffer) {
        printk(KERN_ERR "Failed to allocate coherent DMA buffer\n");
        return -ENOMEM;
    }
    
    printk(KERN_INFO "Coherent DMA buffer allocated:\n");
    printk(KERN_INFO "  CPU address: %p\n", coherent_buffer);
    printk(KERN_INFO "  DMA address: 0x%llx\n", (unsigned long long)coherent_dma_addr);
    printk(KERN_INFO "  Size: %zu bytes\n", size);
    
    return 0;
}

static void cleanup_coherent_dma(struct device *dev, size_t size)
{
    if (coherent_buffer) {
        dma_free_coherent(dev, size, coherent_buffer, coherent_dma_addr);
        coherent_buffer = NULL;
        printk(KERN_INFO "Coherent DMA buffer freed\n");
    }
}
```

### 流式DMA映射分析
```c
// 摘自 projects/设备驱动/dma_streaming_demo.c
static int perform_streaming_dma(struct device *dev, void *buffer, size_t size, 
                                enum dma_data_direction direction)
{
    dma_addr_t dma_addr;
    
    // 映射内存供DMA使用
    dma_addr = dma_map_single(dev, buffer, size, direction);
    if (dma_mapping_error(dev, dma_addr)) {
        printk(KERN_ERR "DMA mapping failed\n");
        return -EIO;
    }
    
    printk(KERN_INFO "Streaming DMA mapping:\n");
    printk(KERN_INFO "  CPU address: %p\n", buffer);
    printk(KERN_INFO "  DMA address: 0x%llx\n", (unsigned long long)dma_addr);
    printk(KERN_INFO "  Direction: %s\n", 
           direction == DMA_TO_DEVICE ? "TO_DEVICE" :
           direction == DMA_FROM_DEVICE ? "FROM_DEVICE" : "BIDIRECTIONAL");
    
    // 执行DMA传输（硬件操作）
    // ... 触发硬件DMA ...
    
    // 等待传输完成
    // ... 等待中断或轮询状态 ...
    
    // 解除映射
    dma_unmap_single(dev, dma_addr, size, direction);
    printk(KERN_INFO "Streaming DMA unmapped\n");
    
    return 0;
}
```

### 缓存一致性与内存屏障
```c
// 摘自 projects/设备驱动/dma_cache_management.c
static void handle_dma_cache_consistency(struct device *dev, void *buffer, 
                                        size_t size, enum dma_data_direction dir)
{
    switch (dir) {
    case DMA_TO_DEVICE:
        // CPU写入数据后，需要刷新缓存到内存
        dma_sync_single_for_device(dev, dma_handle, size, dir);
        
        // 确保内存写入完成
        wmb();
        
        // 通知设备可以开始DMA读取
        writel(DMA_START_FLAG, device_control_reg);
        break;
        
    case DMA_FROM_DEVICE:
        // 设备DMA写入完成后，CPU需要使缓存失效
        dma_sync_single_for_cpu(dev, dma_handle, size, dir);
        
        // 确保内存读取看到最新数据
        rmb();
        break;
        
    case DMA_BIDIRECTIONAL:
        // 双向需要特殊处理
        dma_sync_single_for_device(dev, dma_handle, size, DMA_TO_DEVICE);
        // ... 设备操作 ...
        dma_sync_single_for_cpu(dev, dma_handle, size, DMA_FROM_DEVICE);
        break;
    }
}
```

### IOMMU与地址转换
```c
// 摘自 projects/设备驱动/iommu_analysis.c
static int analyze_iommu_mapping(struct device *dev)
{
    struct iommu_domain *domain;
    struct iommu_ops *ops;
    
    if (!dev->iommu_group) {
        printk(KERN_INFO "Device has no IOMMU group\n");
        return 0;
    }
    
    printk(KERN_INFO "=== IOMMU Analysis ===\n");
    printk(KERN_INFO "IOMMU group: %d\n", dev->iommu_group->id);
    
    // 获取IOMMU域
    domain = iommu_get_domain_for_dev(dev);
    if (domain) {
        ops = domain->ops;
        printk(KERN_INFO "IOMMU domain: %p\n", domain);
        printk(KERN_INFO "IOMMU ops: %pf\n", ops);
        
        if (ops && ops->iova_to_phys) {
            // 分析IOVA到物理地址的映射
            dma_addr_t iova = 0x10000000; // 示例IOVA
            phys_addr_t phys = ops->iova_to_phys(domain, iova);
            printk(KERN_INFO "IOVA 0x%llx -> PA 0x%llx\n", 
                   (unsigned long long)iova, (unsigned long long)phys);
        }
    }
    
    return 0;
}
```

### DMA性能优化技术
```c
// 摘自 projects/设备驱动/dma_optimization.c
static void optimize_dma_performance(struct device *dev)
{
    // 1. 使用DMA池减少分配开销
    struct dma_pool *pool = dma_pool_create("my_dma_pool", dev, 
                                            4096, 64, 0);
    if (pool) {
        void *vaddr;
        dma_addr_t dma_addr;
        
        // 从DMA池快速分配
        vaddr = dma_pool_alloc(pool, GFP_KERNEL, &dma_addr);
        if (vaddr) {
            // 使用DMA内存
            // ... 执行DMA操作 ...
            
            // 释放回池
            dma_pool_free(pool, vaddr, dma_addr);
        }
        dma_pool_destroy(pool);
    }
    
    // 2. 使用分散-聚集DMA减少拷贝
    struct scatterlist sg[4];
    struct sg_table sgt;
    int i;
    
    sg_init_table(sg, 4);
    for (i = 0; i < 4; i++) {
        sg_dma_address(&sg[i]) = dma_handles[i];
        sg_dma_len(&sg[i]) = sizes[i];
    }
    
    if (sg_alloc_table(&sgt, 4, GFP_KERNEL) == 0) {
        // 映射scatter-gather列表
        int nents = dma_map_sg(dev, sgt.sgl, sgt.nents, DMA_TO_DEVICE);
        if (nents > 0) {
            // 执行分散-聚集DMA
            // ... 硬件操作 ...
            
            // 解除映射
            dma_unmap_sg(dev, sgt.sgl, sgt.orig_nents, DMA_TO_DEVICE);
        }
        sg_free_table(&sgt);
    }
}
```

### DMA错误处理与调试
```c
// 摘自 projects/设备驱动/dma_debugging.c
static void debug_dma_operations(struct device *dev)
{
    // 启用DMA调试
    #ifdef CONFIG_DMA_API_DEBUG
    dma_debug_init();
    #endif
    
    // 检测DMA映射错误
    dma_addr_t dma_addr = dma_map_single(dev, buffer, size, DMA_TO_DEVICE);
    if (dma_mapping_error(dev, dma_addr)) {
        printk(KERN_ERR "DMA mapping error detected!\n");
        printk(KERN_ERR "  Device: %s\n", dev_name(dev));
        printk(KERN_ERR "  Buffer: %p\n", buffer);
        printk(KERN_ERR "  Size: %zu\n", size);
        
        // 检查DMA一致性
        if (!dma_capable(dev, dma_addr, size, DMA_TO_DEVICE)) {
            printk(KERN_ERR "Device not capable of this DMA operation\n");
        }
        
        return -EIO;
    }
    
    // 设置DMA掩码调试
    u64 mask = DMA_BIT_MASK(32); // 32位DMA
    if (dma_supported(dev, mask)) {
        printk(KERN_INFO "Device supports 32-bit DMA\n");
    }
    
    // 检查DMA属性
    const struct dma_map_ops *ops = get_dma_ops(dev);
    if (ops) {
        printk(KERN_INFO "DMA operations: %pf\n", ops);
    }
}
```

### DMA性能监控
```bash
# 查看DMA相关统计
cat /proc/dma 2>/dev/null || echo "DMA信息不可用"

# 查看设备DMA能力
lspci -vvv | grep -A5 -B5 "DMA\|IOMMU" | head -20

# 查看IOMMU状态
dmesg | grep -i "iommu\|dmar" | head -10

# 查看DMA映射调试信息（需要CONFIG_DMA_API_DEBUG）
cat /sys/kernel/debug/dma-api/ 2>/dev/null || echo "DMA调试未启用"

# 监控DMA传输性能
cat /proc/interrupts | grep -E "(dma|DMAR)" | head -5

# 查看设备DMA掩码设置
for device in /sys/class/*/device*/; do
    if [ -f "$device/dma_mask_bits" ]; then
        echo "$(basename $device): $(cat $device/dma_mask_bits) bits"
    fi
done | head -10
```

### DMA池管理分析
```c
// 摘自 projects/设备驱动/dma_pool_manager.c
static struct dma_pool_manager {
    struct dma_pool *pools[DMA_POOL_MAX];
    int pool_count;
    spinlock_t lock;
} pool_mgr;

static int create_dma_pools(struct device *dev)
{
    int i;
    unsigned long sizes[] = {64, 256, 1024, 4096};
    const char *names[] = {"pool_64", "pool_256", "pool_1k", "pool_4k"};
    
    spin_lock_init(&pool_mgr.lock);
    
    for (i = 0; i < ARRAY_SIZE(sizes); i++) {
        pool_mgr.pools[i] = dma_pool_create(names[i], dev, 
                                           sizes[i], 64, 0);
        if (!pool_mgr.pools[i]) {
            printk(KERN_ERR "Failed to create DMA pool %s\n", names[i]);
            // 清理已创建的池
            while (--i >= 0) {
                dma_pool_destroy(pool_mgr.pools[i]);
            }
            return -ENOMEM;
        }
        pool_mgr.pool_count++;
        printk(KERN_INFO "Created DMA pool %s (size=%lu)\n", names[i], sizes[i]);
    }
    
    return 0;
}

// 从合适的池中分配内存
static void *dma_pool_alloc_optimized(struct device *dev, size_t size, 
                                     dma_addr_t *dma_addr)
{
    int i;
    void *vaddr = NULL;
    
    spin_lock(&pool_mgr.lock);
    
    // 找到最适合的池
    for (i = 0; i < pool_mgr.pool_count; i++) {
        struct dma_pool *pool = pool_mgr.pools[i];
        if (size <= dma_pool_size(pool)) {
            vaddr = dma_pool_alloc(pool, GFP_KERNEL, dma_addr);
            if (vaddr) {
                printk(KERN_INFO "Allocated %zu bytes from pool %d\n", size, i);
                break;
            }
        }
    }
    
    spin_unlock(&pool_mgr.lock);
    return vaddr;
}
```

---
## 5.7 调试与观测：dmesg、tracefs、dynamic debug、/proc、/sys
- dmesg/printk：模块加载、错误路径首选证据
- tracefs：`events/irq/*`、`events/block/*`、`events/drivers/*`、`events/kmem/*`
- 动态调试：`echo 'file drivers/* +p' > /sys/kernel/debug/dynamic_debug/control`
- /proc/interrupts：中断分布；/sys/class/*：设备属性；debugfs：驱动自定义调试接口

示例（tracefs 捕获 IRQ）：
```bash
cd /sys/kernel/tracing; echo 0 | sudo tee tracing_on >/dev/null
for g in irq sched; do echo 1 | sudo tee events/$g/enable >/dev/null; done
sleep 1; echo 0 | sudo tee tracing_on >/dev/null; tail -n 40 trace
```

---
## 5.8 可复现实验与评测设计
1) 字符设备通路验证（projects/设备驱动/char_device.c）
- 构建与加载
```bash
cd projects/设备驱动
make
sudo insmod char_device.ko
ls -l /dev/mychardev || true
echo hello > /dev/mychardev; cat /dev/mychardev
sudo rmmod char_device
```

2) 平台驱动 probe/remove（projects/设备驱动/platform_driver.c）
```bash
cd projects/设备驱动 && make
sudo insmod platform_driver.ko
dmesg | tail -n 20   # 观察 probe
sudo rmmod platform_driver
```

3) 中断/下半部演示（projects/设备驱动/interrupt_handler.c）
- 方式A（安全、默认）：定时器+workqueue 模拟
```bash
cd projects/设备驱动 && make
sudo insmod interrupt_handler.ko
cat /proc/irq_demo | sed -n '1,5p'
sleep 1; cat /proc/irq_demo | sed -n '1,5p'
sudo rmmod interrupt_handler
```
- 方式B（需要指定可共享的 IRQ，谨慎）：例如 irq=...（仅在了解风险时使用）
```bash
sudo insmod interrupt_handler.ko irq=<IRQ_NUMBER>
cat /proc/irq_demo
sudo rmmod interrupt_handler
```

4) DMA 路径（概念验证，需硬件）
- 步骤：在 probe 中分配 coherent/streaming 缓冲并提交给硬件（或模拟）；
- 指标：cache 失效/一致性问题的复现与测试

---
## 5.9 常见错误与排错
- invalid module format：构建头文件与正在运行内核不一致
- EBUSY/ENODEV：probe 失败或资源冲突；确认 of_match/id_table 与硬件/DT 匹配
- -EFAULT/-EACCES：copy_to/from_user 或权限问题；检查用户态缓冲与访问模式
- 软死锁/竞态：注意自旋锁/睡眠上下文边界；必要时使用 mutex/完成量/等待队列

---
## 5.10 当前研究趋势与难点
- VFIO/SR-IOV：用户态直通与虚函数资源隔离
- DPDK vs 内核网络驱动：栈旁高吞吐与通用性/安全性权衡
- Rust for Linux：在驱动层的安全与可维护性探索
- IOMMU/ATS/PCIe 新特性：一致性、地址转换与性能

---
## 5.11 参考文献
[1] Linux kernel Documentation: driver-api/*、core-api/*、admin-guide/*
[2] Linux Device Drivers, 3rd Edition (LDD3)
[3] Documentation/core-api/dma-api.rst（DMA API）
[4] devicetree.org 规范、Documentation/devicetree/bindings
[5] Documentation/PCI、/interrupts、/RCU、/locking
[6] LWN 驱动开发专题与 Rust for Linux 专栏

