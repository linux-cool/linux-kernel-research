/*
 * 缓冲区溢出安全测试程序
 * 用于测试内核和系统的缓冲区溢出保护机制
 */

#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>
#include <signal.h>
#include <setjmp.h>
#include <sys/mman.h>
#include <sys/wait.h>

// 测试结果
typedef enum {
    TEST_PASS,
    TEST_FAIL,
    TEST_PROTECTED,
    TEST_CRASH
} test_result_t;

// 全局变量用于信号处理
static jmp_buf crash_env;
static int test_crashed = 0;

// 颜色输出
#define COLOR_RED     "\x1b[31m"
#define COLOR_GREEN   "\x1b[32m"
#define COLOR_YELLOW  "\x1b[33m"
#define COLOR_BLUE    "\x1b[34m"
#define COLOR_RESET   "\x1b[0m"

// 信号处理函数
void crash_handler(int sig) {
    test_crashed = 1;
    longjmp(crash_env, 1);
}

// 打印测试结果
void print_test_result(const char *test_name, test_result_t result, const char *description) {
    const char *status_str;
    const char *color;
    
    switch (result) {
        case TEST_PASS:
            status_str = "PASS";
            color = COLOR_GREEN;
            break;
        case TEST_FAIL:
            status_str = "FAIL";
            color = COLOR_RED;
            break;
        case TEST_PROTECTED:
            status_str = "PROTECTED";
            color = COLOR_BLUE;
            break;
        case TEST_CRASH:
            status_str = "CRASH";
            color = COLOR_YELLOW;
            break;
        default:
            status_str = "UNKNOWN";
            color = COLOR_RESET;
            break;
    }
    
    printf("[%s%-9s%s] %-25s: %s\n", color, status_str, COLOR_RESET, test_name, description);
}

// 栈缓冲区溢出测试
test_result_t test_stack_overflow(void) {
    // 设置信号处理
    signal(SIGSEGV, crash_handler);
    signal(SIGABRT, crash_handler);
    test_crashed = 0;
    
    if (setjmp(crash_env) == 0) {
        // 尝试栈溢出
        char buffer[64];
        char overflow_data[1024];
        
        // 填充溢出数据
        memset(overflow_data, 'A', sizeof(overflow_data) - 1);
        overflow_data[sizeof(overflow_data) - 1] = '\0';
        
        // 尝试溢出（这应该被栈保护机制检测到）
        strcpy(buffer, overflow_data);
        
        // 如果到达这里，说明没有保护或保护失效
        return TEST_FAIL;
    } else {
        // 捕获到崩溃，说明保护机制工作
        return test_crashed ? TEST_PROTECTED : TEST_FAIL;
    }
}

// 堆缓冲区溢出测试
test_result_t test_heap_overflow(void) {
    signal(SIGSEGV, crash_handler);
    signal(SIGABRT, crash_handler);
    test_crashed = 0;
    
    if (setjmp(crash_env) == 0) {
        // 分配小缓冲区
        char *buffer = malloc(64);
        if (!buffer) {
            return TEST_FAIL;
        }
        
        // 尝试堆溢出
        char overflow_data[1024];
        memset(overflow_data, 'B', sizeof(overflow_data) - 1);
        overflow_data[sizeof(overflow_data) - 1] = '\0';
        
        strcpy(buffer, overflow_data);
        
        free(buffer);
        return TEST_FAIL;  // 如果到达这里，说明没有检测到溢出
    } else {
        return test_crashed ? TEST_PROTECTED : TEST_FAIL;
    }
}

// 格式字符串漏洞测试
test_result_t test_format_string(void) {
    signal(SIGSEGV, crash_handler);
    test_crashed = 0;
    
    if (setjmp(crash_env) == 0) {
        char user_input[] = "%x %x %x %x %x %x %x %x";
        
        // 尝试格式字符串攻击
        printf(user_input);  // 这是不安全的用法
        
        return TEST_FAIL;  // 如果没有崩溃，可能存在漏洞
    } else {
        return test_crashed ? TEST_PROTECTED : TEST_FAIL;
    }
}

// 返回地址覆盖测试
test_result_t test_return_address_overwrite(void) {
    signal(SIGSEGV, crash_handler);
    signal(SIGABRT, crash_handler);
    test_crashed = 0;
    
    if (setjmp(crash_env) == 0) {
        // 尝试覆盖返回地址
        volatile char buffer[32];
        volatile char *ptr = (char *)buffer;
        
        // 填充缓冲区并尝试覆盖返回地址
        for (int i = 0; i < 100; i++) {
            ptr[i] = 'C';
        }
        
        return TEST_FAIL;  // 如果到达这里，保护可能失效
    } else {
        return test_crashed ? TEST_PROTECTED : TEST_FAIL;
    }
}

// 栈金丝雀检测测试
test_result_t test_stack_canary(void) {
    // 这个测试需要编译时启用栈保护
    // 检查是否有栈保护编译选项
    
#ifdef __STACK_CHK_FAIL
    return TEST_PROTECTED;
#else
    // 尝试检测运行时栈保护
    signal(SIGABRT, crash_handler);
    test_crashed = 0;
    
    if (setjmp(crash_env) == 0) {
        // 创建一个可能触发栈保护的函数
        volatile char buffer[16];
        volatile char overflow[64];
        
        memset((void*)overflow, 'D', sizeof(overflow));
        memcpy((void*)buffer, (void*)overflow, sizeof(overflow));
        
        return TEST_FAIL;
    } else {
        return test_crashed ? TEST_PROTECTED : TEST_FAIL;
    }
#endif
}

// NX位/DEP测试
test_result_t test_nx_bit(void) {
    signal(SIGSEGV, crash_handler);
    test_crashed = 0;
    
    if (setjmp(crash_env) == 0) {
        // 分配可写但不可执行的内存
        void *mem = mmap(NULL, 4096, PROT_READ | PROT_WRITE, 
                        MAP_PRIVATE | MAP_ANONYMOUS, -1, 0);
        
        if (mem == MAP_FAILED) {
            return TEST_FAIL;
        }
        
        // 尝试在数据段执行代码
        unsigned char shellcode[] = {
            0x90, 0x90, 0x90, 0x90,  // NOP指令
            0xc3                      // RET指令
        };
        
        memcpy(mem, shellcode, sizeof(shellcode));
        
        // 尝试执行（这应该被NX位阻止）
        void (*func)(void) = (void (*)(void))mem;
        func();
        
        munmap(mem, 4096);
        return TEST_FAIL;  // 如果执行成功，NX位可能未启用
    } else {
        return test_crashed ? TEST_PROTECTED : TEST_FAIL;
    }
}

// ASLR测试
test_result_t test_aslr(void) {
    void *addr1, *addr2;
    pid_t pid;
    int status;
    
    // 第一次分配
    addr1 = malloc(1024);
    if (!addr1) {
        return TEST_FAIL;
    }
    
    printf("    第一次分配地址: %p\n", addr1);
    free(addr1);
    
    // Fork子进程进行第二次分配
    pid = fork();
    if (pid == 0) {
        // 子进程
        addr2 = malloc(1024);
        printf("    第二次分配地址: %p\n", addr2);
        
        if (addr2) {
            free(addr2);
            exit(addr1 != addr2 ? 0 : 1);  // 地址不同返回0，相同返回1
        }
        exit(1);
    } else if (pid > 0) {
        // 父进程
        wait(&status);
        if (WIFEXITED(status)) {
            return WEXITSTATUS(status) == 0 ? TEST_PROTECTED : TEST_FAIL;
        }
    }
    
    return TEST_FAIL;
}

// 整数溢出测试
test_result_t test_integer_overflow(void) {
    signal(SIGFPE, crash_handler);
    signal(SIGABRT, crash_handler);
    test_crashed = 0;
    
    if (setjmp(crash_env) == 0) {
        // 尝试整数溢出
        unsigned int max_uint = 0xFFFFFFFF;
        unsigned int result = max_uint + 1;
        
        // 检查是否检测到溢出
        if (result == 0) {
            // 正常的溢出行为
            return TEST_FAIL;
        }
        
        // 尝试有符号整数溢出
        int max_int = 0x7FFFFFFF;
        int signed_result = max_int + 1;
        
        if (signed_result < 0) {
            return TEST_FAIL;  // 正常溢出
        }
        
        return TEST_PROTECTED;
    } else {
        return test_crashed ? TEST_PROTECTED : TEST_FAIL;
    }
}

// 运行所有安全测试
void run_security_tests(void) {
    printf("\n=== 缓冲区溢出安全测试 ===\n\n");
    
    printf("正在测试各种缓冲区溢出保护机制...\n\n");
    
    // 栈溢出测试
    test_result_t result = test_stack_overflow();
    print_test_result("stack_overflow", result, "栈缓冲区溢出保护");
    
    // 堆溢出测试
    result = test_heap_overflow();
    print_test_result("heap_overflow", result, "堆缓冲区溢出保护");
    
    // 格式字符串测试
    result = test_format_string();
    print_test_result("format_string", result, "格式字符串漏洞保护");
    
    // 返回地址覆盖测试
    result = test_return_address_overwrite();
    print_test_result("return_overwrite", result, "返回地址覆盖保护");
    
    // 栈金丝雀测试
    result = test_stack_canary();
    print_test_result("stack_canary", result, "栈金丝雀保护");
    
    // NX位测试
    result = test_nx_bit();
    print_test_result("nx_bit", result, "NX位/DEP保护");
    
    // ASLR测试
    result = test_aslr();
    print_test_result("aslr", result, "地址空间布局随机化");
    
    // 整数溢出测试
    result = test_integer_overflow();
    print_test_result("integer_overflow", result, "整数溢出保护");
    
    printf("\n=== 测试完成 ===\n");
    printf("说明:\n");
    printf("  %sPASS%s      - 测试通过，但可能存在安全风险\n", COLOR_GREEN, COLOR_RESET);
    printf("  %sFAIL%s      - 测试失败，存在安全漏洞\n", COLOR_RED, COLOR_RESET);
    printf("  %sPROTECTED%s - 保护机制正常工作\n", COLOR_BLUE, COLOR_RESET);
    printf("  %sCRASH%s     - 程序崩溃，可能有保护机制\n", COLOR_YELLOW, COLOR_RESET);
    printf("\n");
    printf("%s注意: 这些测试仅用于教育和安全评估目的%s\n", COLOR_YELLOW, COLOR_RESET);
}

int main(int argc, char *argv[]) {
    printf("Linux内核缓冲区溢出安全测试\n");
    printf("==========================\n");
    
    // 检查是否在安全环境中运行
    if (geteuid() == 0) {
        printf("%s警告: 正在以root权限运行测试%s\n", COLOR_YELLOW, COLOR_RESET);
    }
    
    run_security_tests();
    
    return 0;
}
