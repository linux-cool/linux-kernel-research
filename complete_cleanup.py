#!/usr/bin/env python3
"""
完整清理并确保只有AI Agent相关内容
"""

import os
import shutil

def main():
    print("完整清理projects目录...")
    
    # 应该存在的AI Agent目录
    ai_agent_dirs = [
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
    
    # 获取当前所有项目
    current_items = []
    if os.path.exists("projects"):
        current_items = os.listdir("projects")
    
    print(f"当前projects目录包含 {len(current_items)} 个项目:")
    for item in sorted(current_items):
        print(f"  - {item}")
    
    # 删除不应该存在的项目
    items_to_delete = []
    for item in current_items:
        if item not in ai_agent_dirs and item not in allowed_files:
            items_to_delete.append(item)
    
    if items_to_delete:
        print(f"\n需要删除的项目 ({len(items_to_delete)}):")
        for item in items_to_delete:
            print(f"  - {item}")
            
        print("\n开始删除...")
        for item in items_to_delete:
            item_path = os.path.join("projects", item)
            try:
                if os.path.isdir(item_path):
                    shutil.rmtree(item_path)
                    print(f"  ✅ 已删除目录: {item}")
                else:
                    os.remove(item_path)
                    print(f"  ✅ 已删除文件: {item}")
            except Exception as e:
                print(f"  ❌ 删除失败 {item}: {e}")
    
    # 检查缺失的AI Agent目录
    current_dirs = [item for item in os.listdir("projects") if os.path.isdir(os.path.join("projects", item))]
    missing_dirs = [d for d in ai_agent_dirs if d not in current_dirs]
    
    if missing_dirs:
        print(f"\n缺失的AI Agent目录 ({len(missing_dirs)}):")
        for dir_name in missing_dirs:
            print(f"  ❌ {dir_name}")
            # 创建缺失的目录
            try:
                os.makedirs(os.path.join("projects", dir_name), exist_ok=True)
                print(f"  ✅ 已创建目录: {dir_name}")
            except Exception as e:
                print(f"  ❌ 创建失败 {dir_name}: {e}")
    
    # 最终检查
    final_items = os.listdir("projects")
    ai_dirs = [item for item in final_items if item in ai_agent_dirs]
    
    print(f"\n✅ 清理完成!")
    print(f"AI Agent目录 ({len(ai_dirs)}/{len(ai_agent_dirs)}):")
    for dir_name in sorted(ai_dirs):
        print(f"  ✅ {dir_name}")
    
    # 检查是否还有非AI相关内容
    non_ai_items = [item for item in final_items if item not in ai_agent_dirs and item not in allowed_files]
    if non_ai_items:
        print(f"\n❌ 仍有非AI相关项目: {non_ai_items}")
    else:
        print(f"\n🎉 完美！projects目录现在只包含AI Agent相关内容！")

if __name__ == "__main__":
    main()
