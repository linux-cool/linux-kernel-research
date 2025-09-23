# 第7章 内核安全机制与漏洞研究（projects/内核安全）

本章以 Linux 6.6 LTS 为基线，采用“先动手、再深入”的新手教程体例，围绕 LSM（SELinux/AppArmor/Landlock）、Capabilities、Namespaces/cgroups、seccomp、审核（audit/tracefs security 事件）、内核硬化（lockdown、kptr_restrict、SMEP/SMAP、CFI）等核心机制，介绍如何安全地观测与验证，并给出可复现实验与参考资料。配套代码/脚本计划补充于 projects/内核安全/（如：cap_inspect.sh、security_events_trace.sh、seccomp_demo.c）。

> 环境建议：非生产环境（QEMU/实验机/容器）；需要 sudo/root（tracefs、namespaces 操作）；尽量避免永久更改系统策略。本章默认仅做“只读观测+最小化实验”。

---
## 7.0 给新手的快速入门教程（10–20分钟）

学习目标
- 一眼判断本机启用了哪些 LSM、是否启用了 lockdown、关键内核安全 sysctl 的状态
- 用 tracefs 捕获一次 security/* 事件最小样本
- 用 user namespace 演示“去特权”的效果，直观理解 capabilities 的收敛

前置准备
- 挂载 tracefs：`sudo mount -t tracefs nodev /sys/kernel/tracing 2>/dev/null || true`

步骤一：安全“体检”清单
```bash
# 1) 启用的 LSM 列表
cat /sys/kernel/security/lsm 2>/dev/null || echo "no /sys/kernel/security/lsm"
# 2) Lockdown 状态（若内核支持）
cat /sys/kernel/security/lockdown 2>/dev/null || echo "no lockdown"
# 3) 关键 sysctl：隐藏内核地址/限制 dmesg
sysctl kernel.kptr_restrict 2>/dev/null || cat /proc/sys/kernel/kptr_restrict
sysctl kernel.dmesg_restrict 2>/dev/null || cat /proc/sys/kernel/dmesg_restrict
# 4) 本进程能力（Capabilities）与 seccomp 状态
awk '/Cap(Prm|Eff|Inh|Bnd|Amb)|Seccomp/ {print}' /proc/self/status
# 5) CPU 硬化特性（x86 常见：SMEP/SMAP/IBRS 等）
grep -E "(^flags| smep| smap| ibpb| ibrs| stibp)" /proc/cpuinfo | head -n 5
```
简要解读
- /sys/kernel/security/lsm：列出启用顺序（如 apparmor,selinux,bpf,landlock,yama,integrity）
- lockdown：integrity/confidentiality 等状态可能限制某些内核接口
- CapEff/CapPrm：当前进程的有效/许可能力；容器/非 root 场景常见为收敛集
- Seccomp：0=未启用；1=严格模式；2=过滤器模式（需应用设置）

步骤二：打开 security/* 事件并捕获最小样本
```bash
cd /sys/kernel/tracing
# 关闭、清空、打开 security 事件分组（若存在）
echo 0 | sudo tee tracing_on >/dev/null
: | sudo tee trace >/dev/null
[ -d events/security ] && echo 1 | sudo tee events/security/enable >/dev/null || echo "no events/security"
# 触发一次文件操作（期望产生 security_inode_* 等事件）
(touch /tmp/sec_demo && rm -f /tmp/sec_demo) 2>/dev/null
# 停止并查看最近事件
echo 0 | sudo tee tracing_on >/dev/null
sudo tail -n 60 trace | sed -n '1,60p'
```
观察到 security_inode_*（若内核裁剪包含）表示 LSM 钩子处的 tracepoints 生效。

步骤三：user namespace 去特权演示
```bash
# 创建 userns 并映射 root→当前用户（-r），同时新建 mount/ns，尝试执行特权操作
unshare -Urnm sh -c '
  id; \
  echo "CapEff in userns:"; awk "/CapEff/ {print}" /proc/self/status; \
  echo "Try privileged op (mount tmpfs)"; mount -t tmpfs tmpfs /mnt 2>&1 | sed -n "1,2p"; \
  exit 0'
```
预期：即使 shell 内显示 uid=0（root），但因 userns 去特权，mount 等需要 CAP_SYS_ADMIN 的操作仍会失败。

常见错误与排错
- events/security 不存在 → 与内核裁剪有关；可退回 dmesg/audit（若运行）或仅做 sysctl/LSM 状态观测
- unshare: Operation not permitted → 宿主限制了 userns；在容器/宿主调整 sysctl 或仅阅读理论部分

学习检查点
- 能读懂 /sys/kernel/security/lsm 与 /proc/self/status 的关键字段
- 能用 tracefs 捕获至少一个 security/* 事件（若内核支持）
- 理解 userns 对特权行为的影响（uid=0 ≠ 拥有全能能力）

---
## 7.1 内核安全模型总览
- LSM：SELinux/AppArmor/Landlock/Yama/Integrity（IMA/EVM）等通过钩子扩展安全策略
- 能力（Capabilities）：将 root 的“全能”拆分为细粒度能力位；配合 Ambient/Bounding 限制
- Namespaces/cgroups：隔离资源视图与限制资源使用，形成容器技术基石
- seccomp：以过滤器方式限制进程可用的系统调用/参数
- 审核与可观测性：audit 子系统（可选）与 tracefs 的 security/* 事件
- 硬化：lockdown、KASLR、kptr_restrict、SMEP/SMAP、PAN/MTE（ARM）、CFI/LTO 等

---
## 7.2 能力（Capabilities）实践
### 能力模型详解
Linux capabilities将传统root权限细分为多个独立的能力位，实现最小权限原则。

只读观测
```bash
# 查看当前进程的能力
awk '/Cap(Prm|Eff|Inh|Bnd|Amb)/ {print}' /proc/$$/status
# 查看所有能力定义
capsh --print 2>/dev/null | sed -n '1,60p' || echo "capsh not installed"
```

能力类型说明：
- CapPrm（Permitted）：进程可使用的最大能力集
- CapEff（Effective）：当前生效的能力
- CapBnd（Bounding）：系统范围的能力限制
- CapAmb（Ambient）：环境继承能力
- CapInh（Inheritable）：继承自父进程的能力

代码片段（能力检查模块）：
```c
// 摘自 projects/内核安全/cap_inspect.c
static void inspect_capabilities(void)
{
    struct cred *cred = current_cred();
    kernel_cap_t cap_permitted = cred->cap_permitted;
    kernel_cap_t cap_effective = cred->cap_effective;
    
    printk(KERN_INFO "Process %s capabilities:\n", current->comm);
    printk(KERN_INFO "  Permitted: %016llx\n", cap_to_64(cap_permitted));
    printk(KERN_INFO "  Effective: %016llx\n", cap_to_64(cap_effective));
    
    // 检查特定能力
    if (cap_raised(cap_effective, CAP_SYS_ADMIN))
        printk(KERN_INFO "  Has CAP_SYS_ADMIN\n");
    if (cap_raised(cap_effective, CAP_NET_RAW))
        printk(KERN_INFO "  Has CAP_NET_RAW\n");
}
```

### 能力管理工具
```bash
# 为二进制文件授予特定能力
sudo setcap cap_net_raw+ep /usr/bin/ping
# 查看文件能力
getcap /usr/bin/ping
# 移除文件能力
sudo setcap -r /usr/bin/ping
# 查看能力帮助
man capabilities
```

### 容器与能力
```bash
# Docker默认能力列表
docker run --rm alpine sh -c "grep Cap /proc/self/status"
# 移除所有能力
docker run --rm --cap-drop=ALL alpine sh -c "grep Cap /proc/self/status"
# 添加特定能力
docker run --rm --cap-drop=ALL --cap-add=NET_RAW alpine ping -c 1 8.8.8.8
```

---
## 7.3 命名空间与隔离（user/mount/net 等）
### 命名空间类型详解
Linux提供8种命名空间实现不同层面的隔离：
- User namespace：用户和权限隔离
- Mount namespace：文件系统挂载点隔离
- PID namespace：进程ID隔离
- Network namespace：网络栈隔离
- IPC namespace：System V IPC隔离
- UTS namespace：主机名隔离
- Cgroup namespace：cgroup视图隔离
- Time namespace：系统时间隔离

简单演示（user+mount）
```bash
unshare -Urnm sh -c 'id; mount -t tmpfs tmpfs /mnt 2>&1 | sed -n "1,2p"'
```

网络命名空间（如本书第3章）
```bash
sudo ip netns add ns1; sudo ip link add veth0 type veth peer name veth1
sudo ip link set veth1 netns ns1
sudo ip addr add 10.10.0.1/24 dev veth0; sudo ip link set veth0 up
sudo ip netns exec ns1 ip addr add 10.10.0.2/24 dev veth1; sudo ip netns exec ns1 ip link set veth1 up
ping -c 1 10.10.0.2; sudo ip netns del ns1; sudo ip link del veth0
```

### 命名空间安全性分析
要点：命名空间提供"视图隔离"，并非"绝对安全"；需与 cgroups/LSM/能力共同使用。

代码片段（命名空间创建监控）：
```c
// 摘自 projects/内核安全/ns_monitor.c
static int ns_install_handler(struct nsproxy *ns, struct ns_common *ns_common)
{
    const char *ns_type;
    
    switch (ns_common->ops->type) {
    case CLONE_NEWUSER:
        ns_type = "user";
        break;
    case CLONE_NEWPID:
        ns_type = "pid";
        break;
    case CLONE_NEWNET:
        ns_type = "net";
        break;
    default:
        ns_type = "unknown";
    }
    
    printk(KERN_INFO "New %s namespace created by %s\n", 
           ns_type, current->comm);
    return 0;
}
```

### PID命名空间演示
```bash
# 创建新的PID命名空间
sudo unshare --pid --fork --mount-proc bash
echo "New PID: $$"
ps aux | head -10
exit
```

### Mount命名空间与chroot
```bash
# 创建隔离的文件系统视图
sudo unshare --mount bash
mkdir /tmp/mnt_isolation
mount --bind /tmp/mnt_isolation /tmp/mnt_isolation
# 在此命名空间内的挂载不会影响外部
exit
```

---
## 7.4 seccomp（系统调用过滤）
### seccomp模式详解
seccomp提供三种安全模式：
- mode 0：禁用seccomp
- mode 1：严格模式（只允许exit、sigreturn、read、write）
- mode 2：过滤模式（通过BPF程序自定义过滤规则）

只读观测
```bash
# 查看当前进程 Seccomp 状态（0/1/2）
awk '/Seccomp/ {print}' /proc/$$/status
# 查看seccomp过滤器统计
cat /proc/sys/kernel/seccomp/actions_avail 2>/dev/null || echo "seccomp not available"
```

代码片段（seccomp过滤器实现）：
```c
// 摘自 projects/内核安全/seccomp_demo.c
#include <linux/seccomp.h>
#include <sys/prctl.h>
#include <linux/filter.h>
#include <linux/audit.h>

static int install_filter(void)
{
    struct sock_filter filter[] = {
        /* 加载系统调用号 */
        BPF_STMT(BPF_LD + BPF_W + BPF_ABS, offsetof(struct seccomp_data, nr)),
        
        /* 允许write系统调用 */
        BPF_JUMP(BPF_JMP + BPF_JEQ + BPF_K, __NR_write, 0, 1),
        BPF_STMT(BPF_RET + BPF_K, SECCOMP_RET_ALLOW),
        
        /* 允许exit系统调用 */
        BPF_JUMP(BPF_JMP + BPF_JEQ + BPF_K, __NR_exit_group, 0, 1),
        BPF_STMT(BPF_RET + BPF_K, SECCOMP_RET_ALLOW),
        
        /* 默认拒绝 */
        BPF_STMT(BPF_RET + BPF_K, SECCOMP_RET_KILL),
    };
    
    struct sock_fprog prog = {
        .len = (unsigned short)(sizeof(filter) / sizeof(filter[0])),
        .filter = filter,
    };
    
    return prctl(PR_SET_SECCOMP, SECCOMP_MODE_FILTER, &prog);
}
```

### seccomp使用场景
```bash
# 查看常见应用的seccomp状态
ps aux | grep -E "(chrome|firefox|containerd)" | head -5 | while read line; do
    pid=$(echo $line | awk '{print $2}')
    echo "Process $pid: $(awk '/Seccomp/ {print $2}' /proc/$pid/status 2>/dev/null || echo 'unknown')"
done
```

### libseccomp工具使用
```bash
# 安装libseccomp工具
sudo apt-get install libseccomp-dev seccomp
# 查看系统调用列表
scmp_sys_resolver -a x86_64 -s
# 测试seccomp过滤器
scmp_bpf_disasm < /path/to/filter.bin

---
## 7.5 LSM：SELinux、AppArmor 与 Landlock
### Linux安全模块框架
LSM（Linux Security Modules）提供内核安全策略的可插拔框架，主要实现包括：

检测状态
```bash
# 查看启用的LSM模块
cat /sys/kernel/security/lsm
cat /sys/module/apparmor/parameters/enabled 2>/dev/null || true
getenforce 2>/dev/null || cat /sys/fs/selinux/enforce 2>/dev/null || echo "selinux not enabled"
cat /sys/kernel/security/lsm | tr ',' '\n' | grep -i landlock || true
```

### SELinux深入分析
```bash
# 查看SELinux状态
sestatus 2>/dev/null || echo "SELinux not available"
# 查看当前上下文
id -Z 2>/dev/null || echo "No SELinux context"
# 查看文件上下文
ls -Z /etc/passwd 2>/dev/null || echo "No file contexts"
# 查看SELinux策略模块
semodule -l 2>/dev/null | head -10 || echo "Cannot list modules"
```

代码片段（SELinux策略查询）：
```c
// 摘自 projects/内核安全/selinux_probe.c
#ifdef CONFIG_SECURITY_SELINUX
static void selinux_info(void)
{
    char *context;
    int rc;
    
    rc = security_secid_to_secin(current_security(), &context);
    if (rc == 0) {
        printk(KERN_INFO "Current SELinux context: %s\n", context);
        kfree(context);
    }
    
    printk(KERN_INFO "SELinux enforcing: %d\n", 
           security_getenforce());
}
#endif
```

### AppArmor分析
```bash
# 查看AppArmor状态
aa-status 2>/dev/null || echo "AppArmor not available"
# 列出加载的配置文件
aa-status 2>/dev/null | grep -E "profiles|processes" || true
# 查看特定配置
aa-exec -p unconfined id 2>/dev/null || echo "aa-exec not available"
```

### Landlock：新一代安全模块
Landlock提供基于eBPF的自主访问控制：
```bash
# 检查Landlock支持
uname -r | awk -F. '{if ($1 >= 5 && $2 >= 13) print "Kernel supports Landlock"}'
# 查看Landlock文档
ls /usr/include/linux/landlock* 2>/dev/null || echo "Landlock headers not found"
```

代码片段（Landlock规则创建）：
```c
// 摘自 projects/内核安全/landlock_demo.c
#ifdef CONFIG_SECURITY_LANDLOCK
#include <linux/landlock.h>

static int create_landlock_rule(void)
{
    struct landlock_ruleset_attr ruleset_attr = {
        .handled_access_fs = LANDLOCK_ACCESS_FS_READ_FILE |
                             LANDLOCK_ACCESS_FS_WRITE_FILE,
    };
    
    int ruleset_fd = landlock_create_ruleset(&ruleset_attr, sizeof(ruleset_attr), 0);
    
    if (ruleset_fd >= 0) {
        printk(KERN_INFO "Landlock ruleset created: fd=%d\n", ruleset_fd);
        // 添加路径规则...
    }
    
    return ruleset_fd;
}
#endif
```

### LSM钩子点分析
```bash
# 查看可用的安全事件
cd /sys/kernel/tracing 2>/dev/null
echo 'available_events' | sudo tee events/security/enable 2>/dev/null | grep security || true
# 监控安全事件
echo 1 | sudo tee events/security/enable 2>/dev/null
# 触发事件并查看
touch /tmp/test_security; rm /tmp/test_security
sudo cat trace | grep security | head -10
```

---
## 7.6 审核与 tracefs security 事件
### 内核审计系统
Linux审计系统提供系统调用的详细审计日志：

若系统启用 auditd，可通过 ausearch/aureport 分析；本章以 tracefs 为主：
```bash
cd /sys/kernel/tracing
[ -d events/security ] && echo 1 | sudo tee events/security/enable >/dev/null || true
(touch /tmp/sec_demo && rm -f /tmp/sec_demo) 2>/dev/null
sudo tail -n 60 trace | sed -n '1,60p'
```

### auditd系统使用
```bash
# 检查auditd状态
systemctl status auditd 2>/dev/null || echo "auditd not running"
# 查看审计规则
sudo auditctl -l 2>/dev/null || echo "Cannot list audit rules"
# 搜索审计日志
sudo ausearch -sc openat -ts recent 2>/dev/null | head -10 || echo "No audit records"
# 生成审计报告
sudo aureport --summary 2>/dev/null || echo "Cannot generate report"
```

### 自定义审计规则
```bash
# 审计所有文件删除操作
sudo auditctl -a always,exit -F arch=b64 -S unlink -S unlinkat -k file_delete
# 审计特定文件的访问
sudo auditctl -w /etc/passwd -p rwxa -k passwd_changes
# 审计特定用户的操作
sudo auditctl -a always,exit -F uid=1000 -S all -k user_1000
```

代码片段（审计事件分析）：
```c
// 摘自 projects/内核安全/audit_analyzer.c
static int audit_event_handler(struct audit_buffer *ab)
{
    struct audit_context *ctx = ab->ctx;
    
    if (ctx->syscalls != NULL) {
        printk(KERN_INFO "Audit: syscall=%d pid=%d uid=%d\n",
               ctx->syscalls->arch.arch,
               ctx->current_pid,
               ctx->uid.val);
    }
    return 0;
}
```

---
## 7.7 内核硬化与安全相关 sysctl
### 内核地址空间保护
只读观测与提示
```bash
sysctl kernel.kptr_restrict 2>/dev/null || cat /proc/sys/kernel/kptr_restrict
sysctl kernel.dmesg_restrict 2>/dev/null || cat /proc/sys/kernel/dmesg_restrict
[ -f /sys/kernel/security/lockdown ] && cat /sys/kernel/security/lockdown || true
# x86: SMEP/SMAP
grep -E "(^flags| smep| smap)" /proc/cpuinfo | head -n 5
```

### 硬件安全特性
```bash
# Intel硬件安全特性
grep -E "(smep|smap|ibpb|ibrs|stibp|tsxldtrk|md_clear)" /proc/cpuinfo | head -1
# AMD硬件安全特性
grep -E "(smep|smap|ibpb|ibrs|stibp|ssbd)" /proc/cpuinfo | head -1
# ARM硬件安全特性（如MTE、PAN）
[ -f /proc/cpuinfo ] && grep -E "(mte|pan)" /proc/cpuinfo | head -1 || true
```

### 内核锁定机制
```bash
# 查看锁定状态
[ -f /sys/kernel/security/lockdown ] && echo "Lockdown: $(cat /sys/kernel/security/lockdown)"
# 查看锁定原因
[ -f /sys/kernel/security/lockdown_reason ] && cat /sys/kernel/security/lockdown_reason || true
```

### KASLR（内核地址空间布局随机化）
```bash
# 查看KASLR状态
cat /proc/cmdline | grep -E "(kaslr|nokaslr)" || echo "KASLR status unclear"
# 检查内核符号地址随机化
grep -E "(__ksymtab|_text)" /proc/kallsyms | head -5 || echo "kallsyms restricted"
```

代码片段（内核硬化特性检测）：
```c
// 摘自 projects/内核安全/hardening_check.c
static void check_hardening_features(void)
{
    printk(KERN_INFO "Kernel Hardening Features:\n");
    
#ifdef CONFIG_RANDOMIZE_BASE
    printk(KERN_INFO "  KASLR: enabled\n");
#endif
#ifdef CONFIG_SECURITY_LOCKDOWN_LSM
    printk(KERN_INFO "  Lockdown LSM: available\n");
#endif
#ifdef CONFIG_STACKPROTECTOR_STRONG
    printk(KERN_INFO "  Stack Protector: strong\n");
#endif
#ifdef CONFIG_SLAB_FREELIST_RANDOM
    printk(KERN_INFO "  Slab freelist randomization: enabled\n");
#endif
}
```

### 重要安全sysctl参数
```bash
# 地址空间随机化
cat /proc/sys/kernel/randomize_va_space
# 内核指针限制
cat /proc/sys/kernel/kptr_restrict
# dmesg限制
cat /proc/sys/kernel/dmesg_restrict
# 模块签名验证
cat /proc/sys/kernel/modules_disabled 2>/dev/null || echo "Module signing not enforced"
# 性能计数器限制
cat /proc/sys/kernel/perf_event_paranoid
```

不要轻易降低安全阈值（例如将 kptr_restrict 置 0），除非在隔离实验环境并明确回退步骤。

---
## 7.8 高级安全机制
### eBPF与安全
```bash
# 查看eBPF程序类型支持
ls /sys/kernel/debug/tracing/events/syscalls/*bpf* 2>/dev/null || echo "BPF events not available"
# 查看已加载的eBPF程序
sudo bpftool prog list 2>/dev/null | head -10 || echo "bpftool not available"
# 查看eBPF map
sudo bpftool map list 2>/dev/null | head -5 || echo "No BPF maps"
```

### 控制流完整性(CFI)
```bash
# 检查CFI支持（需要较新内核）
grep -i cfi /boot/config-$(uname -r) 2>/dev/null || echo "CFI config not found"
# 查看内核编译选项
zcat /proc/config.gz 2>/dev/null | grep -E "(CFI|SHADOW_CALL_STACK)" || cat /boot/config-$(uname -r) 2>/dev/null | grep -E "(CFI|SHADOW_CALL_STACK)"
```

### 内存安全机制
```bash
# 检查SLAB/SLUB安全特性
grep -E "(SLAB_FREELIST_RANDOM|SLAB_FREELIST_HARDENED)" /boot/config-$(uname -r) 2>/dev/null || echo "SLAB hardening not found"
# 检查堆栈保护
grep "STACKPROTECTOR" /boot/config-$(uname -r) 2>/dev/null || echo "Stack protector config not found"
```

代码片段（CFI检测模块）：
```c
// 摘自 projects/内核安全/cfi_check.c
#ifdef CONFIG_CFI_CLANG
static int cfi_check_function(void *func)
{
    // 检查函数指针的有效性
    if (!cfi_check_hash(func)) {
        printk(KERN_ERR "CFI violation detected: invalid function pointer\n");
        return -EINVAL;
    }
    return 0;
}
#endif
```

---
## 7.9 可复现实验与评测设计
1) 捕获一次 security/* 事件
- 步骤：开启 events/security → 执行 touch/rm → 查看 trace
- 指标：事件是否产生、事件类型与参数字段

2) userns 去特权验证
- 步骤：unshare -Urnm → 观察 id/CapEff → 尝试 mount 并预期失败
- 指标：权限错误返回与能力面变化

3) Capabilities 与 setcap（可选）
- 步骤：为 /bin/ping 设置 cap_net_raw（需策略允许）→ 在非 root 下 ping
- 指标：程序最小必要权限运行；测试完成后 `sudo setcap -r /bin/ping` 恢复

4) seccomp 只读观测
- 步骤：检查常见沙箱化进程的 Seccomp 字段（如浏览器/容器 runtime）
- 指标：Seccomp: 2 的进程比例

5) 安全策略对比分析
- 步骤：对比不同LSM（SELinux/AppArmor）的策略复杂度
- 指标：策略规则数量、拒绝事件频率、性能开销

6) 内核硬化特性检测
- 步骤：编写脚本检测内核安全配置
- 指标：硬化特性启用率、安全参数设置合规性

脚本片段（安全审计自动化）：
```bash
#!/bin/bash
# 内核安全状态检查脚本

echo "=== Kernel Security Audit ==="
echo

echo "1. LSM Status:"
cat /sys/kernel/security/lsm
echo

echo "2. Capabilities (current process):"
grep Cap /proc/self/status
echo

echo "3. Seccomp Status:"
grep Seccomp /proc/self/status
echo

echo "4. Kernel Hardening:"
echo "  kptr_restrict: $(cat /proc/sys/kernel/kptr_restrict)"
echo "  dmesg_restrict: $(cat /proc/sys/kernel/dmesg_restrict)"
echo "  randomize_va_space: $(cat /proc/sys/kernel/randomize_va_space)"
echo

echo "5. Hardware Security Features:"
grep -E "(smep|smap)" /proc/cpuinfo | head -1
echo

echo "6. Lockdown Status:"
[ -f /sys/kernel/security/lockdown ] && cat /sys/kernel/security/lockdown || echo "Not available"
echo

echo "7. Audit System:"
systemctl is-active auditd 2>/dev/null || echo "auditd not running"
echo "  Active rules: $(sudo auditctl -l 2>/dev/null | wc -l)"
echo

echo "=== Security Score ==="
total_checks=7
passed_checks=0

[ "$(cat /proc/sys/kernel/kptr_restrict)" -ge 1 ] && ((passed_checks++))
[ "$(cat /proc/sys/kernel/randomize_va_space)" -ge 2 ] && ((passed_checks++))
grep -q smep /proc/cpuinfo && ((passed_checks++))
grep -q smap /proc/cpuinfo && ((passed_checks++))
[ -f /sys/kernel/security/lockdown ] && ((passed_checks++))
systemctl is-active auditd >/dev/null 2>&1 && ((passed_checks++))
[ "$(sudo auditctl -l 2>/dev/null | wc -l)" -gt 0 ] && ((passed_checks++))

echo "Passed: $passed_checks/$total_checks checks"
echo "Security Score: $(( passed_checks * 100 / total_checks ))%"
```

---
## 7.10 当前研究趋势与难点
- eBPF LSM 与安全可编程化：在 LSM 钩子上以 eBPF 施加策略（受内核与发行版支持限制）
- Landlock：以用户空间能力为粒度的最小权限文件访问控制
- CFI/Shadow Call Stack 与全链接时优化（LTO）：控制流完整性与硬化
- 内存安全语言：Rust for Linux 在驱动/内核子系统的安全性探索
- ARM MTE、Intel PKS 等硬件特性与 Linux 支持进展

---
## 7.11 小结
本章从"安全体检→最小事件捕获→去特权演示"入手，配合 LSM/Capabilities/Namespaces/seccomp 的理论梳理，给出可在通用发行版安全执行的观察步骤。通过深入分析各种安全机制的工作原理和实践方法，读者可以全面理解Linux内核的安全体系结构。实践中应坚持"最小权限原则"和"先观测后变更"的准则，并为任何策略调整准备可回退路径。

---
## 7.12 参考文献
[1] Linux kernel Documentation: admin-guide/LSM/*, security/*, trace/events/security/*, core-api/*
[2] SELinux Project Docs；AppArmor Docs；Landlock 文档（Documentation/userspace-api/landlock.rst）
[3] Linux Capabilities（man 7 capabilities）；libcap/capsh 工具
[4] seccomp 文档与 libseccomp；`Documentation/userspace-api/seccomp_filter.rst`
[5] Kernel Lockdown 设计与实现（Documentation/admin-guide/lockdown.rst）
[6] SMEP/SMAP/MTE/PKS 等硬件特性文档与 LWN 专题
[7] "Understanding the Linux Kernel", Daniel P. Bovet & Marco Cesati
[8] "Linux Security Module (LSM) Framework" - Linux Kernel Documentation
[9] "Linux Capabilities: Making Them Work for You" - Linux Journal
[10] "Seccomp BPF (SECure COMPuting with filters)" - Linux Kernel Documentation
[11] "Control Flow Integrity for the Linux Kernel" - Linux Security Summit
[12] "Rust for Linux: Writing Safe Kernel Code" - Linux Plumbers Conference

