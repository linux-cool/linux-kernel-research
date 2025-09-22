#!/usr/bin/env python3
import os
import shutil

# 要删除的目录
dirs_to_remove = [
    "projects/内核安全",
    "projects/内核性能", 
    "projects/文件系统"
]

print("最终清理Linux内核相关目录...")

for dir_path in dirs_to_remove:
    if os.path.exists(dir_path):
        try:
            shutil.rmtree(dir_path)
            print(f"✅ 已删除: {dir_path}")
        except Exception as e:
            print(f"❌ 删除失败 {dir_path}: {e}")
    else:
        print(f"⚠️  目录不存在: {dir_path}")

print("\n检查最终结果:")
items = os.listdir("projects")
print(f"projects目录包含 {len(items)} 个项目:")
for item in sorted(items):
    print(f"  - {item}")

# 检查是否还有内核相关内容
kernel_related = [item for item in items if "内核" in item or "文件系统" in item]
if kernel_related:
    print(f"\n❌ 仍有内核相关内容: {kernel_related}")
else:
    print(f"\n🎉 完美！所有Linux内核相关内容已清理完毕！")
