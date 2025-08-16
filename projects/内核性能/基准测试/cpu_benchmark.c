/*
 * CPU性能基准测试程序
 * 测试CPU计算性能、缓存性能、分支预测性能等
 */

#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>
#include <unistd.h>
#include <math.h>
#include <sys/time.h>

#define ITERATIONS 1000000
#define ARRAY_SIZE 1024*1024

// 时间测量函数
double get_time() {
    struct timeval tv;
    gettimeofday(&tv, NULL);
    return tv.tv_sec + tv.tv_usec / 1000000.0;
}

// 整数运算性能测试
void test_integer_performance() {
    printf("=== 整数运算性能测试 ===\n");
    
    double start_time = get_time();
    volatile long long result = 0;
    
    for (int i = 0; i < ITERATIONS; i++) {
        result += i * i;
        result -= i / 2;
        result *= 3;
        result /= 2;
    }
    
    double end_time = get_time();
    double duration = end_time - start_time;
    
    printf("整数运算时间: %.6f 秒\n", duration);
    printf("运算速度: %.2f MOPS (百万次操作/秒)\n", 
           (ITERATIONS * 4.0) / (duration * 1000000));
    printf("结果: %lld\n\n", result);
}

// 浮点运算性能测试
void test_floating_point_performance() {
    printf("=== 浮点运算性能测试 ===\n");
    
    double start_time = get_time();
    volatile double result = 0.0;
    
    for (int i = 0; i < ITERATIONS; i++) {
        result += sin(i * 0.001);
        result += cos(i * 0.001);
        result += sqrt(i);
        result += log(i + 1);
    }
    
    double end_time = get_time();
    double duration = end_time - start_time;
    
    printf("浮点运算时间: %.6f 秒\n", duration);
    printf("运算速度: %.2f MFLOPS (百万次浮点操作/秒)\n", 
           (ITERATIONS * 4.0) / (duration * 1000000));
    printf("结果: %.6f\n\n", result);
}

// 内存访问性能测试
void test_memory_access_performance() {
    printf("=== 内存访问性能测试 ===\n");
    
    int *array = malloc(ARRAY_SIZE * sizeof(int));
    if (!array) {
        printf("内存分配失败\n");
        return;
    }
    
    // 初始化数组
    for (int i = 0; i < ARRAY_SIZE; i++) {
        array[i] = i;
    }
    
    // 顺序访问测试
    double start_time = get_time();
    volatile long long sum = 0;
    
    for (int iter = 0; iter < 100; iter++) {
        for (int i = 0; i < ARRAY_SIZE; i++) {
            sum += array[i];
        }
    }
    
    double end_time = get_time();
    double duration = end_time - start_time;
    
    printf("顺序访问时间: %.6f 秒\n", duration);
    printf("内存带宽: %.2f MB/s\n", 
           (ARRAY_SIZE * sizeof(int) * 100.0) / (duration * 1024 * 1024));
    
    // 随机访问测试
    start_time = get_time();
    sum = 0;
    
    for (int iter = 0; iter < 100; iter++) {
        for (int i = 0; i < ARRAY_SIZE; i++) {
            int index = rand() % ARRAY_SIZE;
            sum += array[index];
        }
    }
    
    end_time = get_time();
    duration = end_time - start_time;
    
    printf("随机访问时间: %.6f 秒\n", duration);
    printf("随机访问速度: %.2f M访问/秒\n", 
           (ARRAY_SIZE * 100.0) / (duration * 1000000));
    printf("结果: %lld\n\n", sum);
    
    free(array);
}

// 分支预测性能测试
void test_branch_prediction_performance() {
    printf("=== 分支预测性能测试 ===\n");
    
    int *data = malloc(ARRAY_SIZE * sizeof(int));
    if (!data) {
        printf("内存分配失败\n");
        return;
    }
    
    // 生成随机数据
    srand(time(NULL));
    for (int i = 0; i < ARRAY_SIZE; i++) {
        data[i] = rand() % 256;
    }
    
    // 有序数据测试（分支预测友好）
    qsort(data, ARRAY_SIZE, sizeof(int), 
          (int(*)(const void*, const void*))strcmp);
    
    double start_time = get_time();
    volatile long long sum = 0;
    
    for (int iter = 0; iter < 100; iter++) {
        for (int i = 0; i < ARRAY_SIZE; i++) {
            if (data[i] >= 128) {
                sum += data[i];
            }
        }
    }
    
    double end_time = get_time();
    double sorted_duration = end_time - start_time;
    
    printf("有序数据处理时间: %.6f 秒\n", sorted_duration);
    
    // 重新生成随机数据（分支预测不友好）
    for (int i = 0; i < ARRAY_SIZE; i++) {
        data[i] = rand() % 256;
    }
    
    start_time = get_time();
    sum = 0;
    
    for (int iter = 0; iter < 100; iter++) {
        for (int i = 0; i < ARRAY_SIZE; i++) {
            if (data[i] >= 128) {
                sum += data[i];
            }
        }
    }
    
    end_time = get_time();
    double random_duration = end_time - start_time;
    
    printf("随机数据处理时间: %.6f 秒\n", random_duration);
    printf("分支预测影响: %.2fx 性能差异\n", 
           random_duration / sorted_duration);
    printf("结果: %lld\n\n", sum);
    
    free(data);
}

// 缓存性能测试
void test_cache_performance() {
    printf("=== 缓存性能测试 ===\n");
    
    // L1缓存测试 (32KB)
    int l1_size = 8 * 1024;  // 32KB / 4 bytes
    int *l1_array = malloc(l1_size * sizeof(int));
    
    double start_time = get_time();
    volatile int sum = 0;
    
    for (int iter = 0; iter < 10000; iter++) {
        for (int i = 0; i < l1_size; i++) {
            sum += l1_array[i];
        }
    }
    
    double end_time = get_time();
    double l1_duration = end_time - start_time;
    
    printf("L1缓存访问时间: %.6f 秒\n", l1_duration);
    
    // L3缓存测试 (8MB)
    int l3_size = 2 * 1024 * 1024;  // 8MB / 4 bytes
    int *l3_array = malloc(l3_size * sizeof(int));
    
    start_time = get_time();
    sum = 0;
    
    for (int iter = 0; iter < 100; iter++) {
        for (int i = 0; i < l3_size; i++) {
            sum += l3_array[i];
        }
    }
    
    end_time = get_time();
    double l3_duration = end_time - start_time;
    
    printf("L3缓存访问时间: %.6f 秒\n", l3_duration);
    
    // 内存访问测试 (64MB)
    int mem_size = 16 * 1024 * 1024;  // 64MB / 4 bytes
    int *mem_array = malloc(mem_size * sizeof(int));
    
    start_time = get_time();
    sum = 0;
    
    for (int iter = 0; iter < 10; iter++) {
        for (int i = 0; i < mem_size; i++) {
            sum += mem_array[i];
        }
    }
    
    end_time = get_time();
    double mem_duration = end_time - start_time;
    
    printf("内存访问时间: %.6f 秒\n", mem_duration);
    printf("缓存层次性能比: L1:L3:MEM = 1:%.1f:%.1f\n", 
           l3_duration/l1_duration * 100, 
           mem_duration/l1_duration * 10);
    
    free(l1_array);
    free(l3_array);
    free(mem_array);
    printf("\n");
}

// 系统信息显示
void show_system_info() {
    printf("=== 系统信息 ===\n");
    
    FILE *fp = fopen("/proc/cpuinfo", "r");
    if (fp) {
        char line[256];
        while (fgets(line, sizeof(line), fp)) {
            if (strncmp(line, "model name", 10) == 0) {
                printf("CPU: %s", strchr(line, ':') + 2);
                break;
            }
        }
        fclose(fp);
    }
    
    printf("CPU核心数: %d\n", sysconf(_SC_NPROCESSORS_ONLN));
    
    fp = fopen("/proc/meminfo", "r");
    if (fp) {
        char line[256];
        while (fgets(line, sizeof(line), fp)) {
            if (strncmp(line, "MemTotal", 8) == 0) {
                printf("总内存: %s", strchr(line, ':') + 2);
                break;
            }
        }
        fclose(fp);
    }
    
    printf("\n");
}

int main() {
    printf("Linux内核CPU性能基准测试\n");
    printf("========================\n\n");
    
    show_system_info();
    
    test_integer_performance();
    test_floating_point_performance();
    test_memory_access_performance();
    test_branch_prediction_performance();
    test_cache_performance();
    
    printf("=== 测试完成 ===\n");
    printf("建议使用 perf 工具进行更详细的性能分析:\n");
    printf("  perf stat ./cpu_benchmark\n");
    printf("  perf record -g ./cpu_benchmark\n");
    
    return 0;
}
