#!/usr/bin/env python3
"""
强制清理projects目录中的Linux内核相关内容
"""

import os
import shutil
import sys

def force_remove(path):
    """强制删除文件或目录"""
    try:
        if os.path.isdir(path):
            shutil.rmtree(path)
            print(f"✅ 已删除目录: {path}")
        elif os.path.isfile(path):
            os.remove(path)
            print(f"✅ 已删除文件: {path}")
        else:
            print(f"⚠️  路径不存在: {path}")
        return True
    except Exception as e:
        print(f"❌ 删除失败 {path}: {e}")
        return False

def main():
    print("强制清理projects目录中的Linux内核相关内容...")
    
    # 要删除的项目
    items_to_delete = [
        "projects/内核安全",
        "projects/内核性能", 
        "projects/文件系统"
    ]
    
    success_count = 0
    
    for item in items_to_delete:
        print(f"\n处理: {item}")
        if force_remove(item):
            success_count += 1
    
    print(f"\n清理结果: {success_count}/{len(items_to_delete)} 个项目已删除")
    
    # 检查最终结果
    print("\n最终projects目录内容:")
    print("=" * 40)
    
    try:
        items = os.listdir("projects")
        ai_related = []
        non_ai_related = []
        
        ai_keywords = ['AI', '企业', '多智能', '安全', '开发', '性能', '规划', '记忆']
        
        for item in sorted(items):
            if item == 'projects.json':
                continue
                
            is_ai_related = any(keyword in item for keyword in ai_keywords)
            
            if is_ai_related:
                ai_related.append(item)
            else:
                non_ai_related.append(item)
        
        print(f"\n✅ AI Agent相关目录 ({len(ai_related)}):")
        for item in ai_related:
            print(f"   - {item}")
        
        if non_ai_related:
            print(f"\n❌ 仍存在的非AI相关项目 ({len(non_ai_related)}):")
            for item in non_ai_related:
                print(f"   - {item}")
        else:
            print(f"\n🎉 完美！projects目录现在只包含AI Agent相关内容！")
            
    except Exception as e:
        print(f"检查目录时出错: {e}")

if __name__ == "__main__":
    main()
