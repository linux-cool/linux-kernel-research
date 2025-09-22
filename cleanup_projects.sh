#!/bin/bash

# 清理projects目录中的Linux内核相关内容

echo "开始清理projects目录中的Linux内核相关内容..."

# 要删除的目录和文件
ITEMS_TO_DELETE=(
    "projects/内核安全"
    "projects/内核性能"
    "projects/文件系统"
)

# 删除每个项目
for item in "${ITEMS_TO_DELETE[@]}"; do
    if [ -e "$item" ]; then
        echo "删除: $item"
        rm -rf "$item"
        if [ $? -eq 0 ]; then
            echo "✅ 成功删除: $item"
        else
            echo "❌ 删除失败: $item"
        fi
    else
        echo "⚠️  项目不存在: $item"
    fi
done

echo ""
echo "清理完成！现在检查projects目录内容："
echo "=================================="
ls -la projects/

echo ""
echo "AI Agent相关目录："
echo "=================="
find projects/ -maxdepth 1 -type d | grep -E "(AI|企业|多智能|安全|开发|性能|规划|记忆)" | sort

echo ""
echo "✅ 清理完成！projects目录现在只包含AI Agent相关内容。"
