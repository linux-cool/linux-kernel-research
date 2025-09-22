#!/usr/bin/env python3
"""
检查和清理projects目录，确保只包含AI Agent相关内容
"""

import os
import shutil

def main():
    projects_dir = "projects"
    
    # AI Agent相关的目录
    ai_related_dirs = [
        'AI框架研究',
        '企业应用', 
        '多智能体系统',
        '安全隐私',
        '开发工具链',
        '性能优化',
        '规划执行引擎',
        '记忆推理系统'
    ]
    
    # 允许的文件
    allowed_files = ['projects.json']
    
    print("检查projects目录内容...")
    
    if not os.path.exists(projects_dir):
        print(f"错误: {projects_dir} 目录不存在")
        return
    
    # 获取所有项目
    all_items = os.listdir(projects_dir)
    
    print(f"发现 {len(all_items)} 个项目:")
    for item in sorted(all_items):
        print(f"  - {item}")
    
    # 分类项目
    ai_dirs = []
    non_ai_items = []
    
    for item in all_items:
        item_path = os.path.join(projects_dir, item)
        if os.path.isdir(item_path):
            if item in ai_related_dirs:
                ai_dirs.append(item)
            else:
                non_ai_items.append(item)
        elif os.path.isfile(item_path):
            if item not in allowed_files:
                non_ai_items.append(item)
    
    print(f"\nAI Agent相关目录 ({len(ai_dirs)}):")
    for dir_name in sorted(ai_dirs):
        print(f"  ✅ {dir_name}")
    
    print(f"\n需要删除的非AI相关项目 ({len(non_ai_items)}):")
    for item in sorted(non_ai_items):
        item_path = os.path.join(projects_dir, item)
        if os.path.isdir(item_path):
            print(f"  🗂️  {item} (目录)")
        else:
            print(f"  📄 {item} (文件)")
    
    # 删除非AI相关项目
    if non_ai_items:
        print(f"\n开始清理 {len(non_ai_items)} 个非AI相关项目...")
        
        for item in non_ai_items:
            item_path = os.path.join(projects_dir, item)
            try:
                if os.path.isdir(item_path):
                    shutil.rmtree(item_path)
                    print(f"  ✅ 已删除目录: {item}")
                else:
                    os.remove(item_path)
                    print(f"  ✅ 已删除文件: {item}")
            except Exception as e:
                print(f"  ❌ 删除失败 {item}: {e}")
    
    # 检查缺失的AI目录
    missing_dirs = [d for d in ai_related_dirs if d not in ai_dirs]
    if missing_dirs:
        print(f"\n缺失的AI Agent目录 ({len(missing_dirs)}):")
        for dir_name in missing_dirs:
            print(f"  ❌ {dir_name}")
    
    print(f"\n✅ 清理完成! projects目录现在只包含AI Agent相关内容。")
    
    # 最终检查
    final_items = os.listdir(projects_dir)
    print(f"\n最终目录内容 ({len(final_items)}):")
    for item in sorted(final_items):
        print(f"  - {item}")

if __name__ == "__main__":
    main()
