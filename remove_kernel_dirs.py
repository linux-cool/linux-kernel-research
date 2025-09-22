#!/usr/bin/env python3
import os
import shutil
import subprocess

def run_command(cmd):
    try:
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
        return result.returncode == 0, result.stdout, result.stderr
    except Exception as e:
        return False, "", str(e)

def main():
    print("强制删除Linux内核相关目录...")
    
    # 要删除的目录
    dirs_to_remove = [
        "projects/内核安全",
        "projects/内核性能", 
        "projects/文件系统"
    ]
    
    # 首先尝试用git rm删除
    for dir_path in dirs_to_remove:
        if os.path.exists(dir_path):
            print(f"删除 {dir_path}...")
            
            # 尝试git rm
            success, stdout, stderr = run_command(f'git rm -rf "{dir_path}"')
            if success:
                print(f"  ✅ git rm成功")
            else:
                # 如果git rm失败，使用普通rm
                try:
                    shutil.rmtree(dir_path)
                    print(f"  ✅ 普通删除成功")
                except Exception as e:
                    print(f"  ❌ 删除失败: {e}")
        else:
            print(f"  ⚠️  {dir_path} 不存在")
    
    # 检查结果
    print("\n检查删除结果:")
    remaining_kernel_dirs = []
    
    if os.path.exists("projects"):
        for item in os.listdir("projects"):
            if "内核" in item or "文件系统" in item:
                remaining_kernel_dirs.append(item)
    
    if remaining_kernel_dirs:
        print(f"❌ 仍有内核相关目录: {remaining_kernel_dirs}")
    else:
        print("✅ 所有内核相关目录已删除")
    
    # 提交更改
    print("\n提交更改...")
    success, stdout, stderr = run_command("git add -A")
    if success:
        success, stdout, stderr = run_command('git commit -m "Final cleanup: remove all Linux kernel related directories"')
        if success:
            print("✅ 更改已提交")
        else:
            print(f"❌ 提交失败: {stderr}")
    else:
        print(f"❌ git add失败: {stderr}")

if __name__ == "__main__":
    main()
