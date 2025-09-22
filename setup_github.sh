#!/bin/bash

# Linux内核研究项目GitHub仓库设置快速启动脚本
# 使用方法: ./setup_github.sh YOUR_GITHUB_USERNAME

set -e

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# 检查参数
if [ $# -eq 0 ]; then
    echo -e "${RED}错误: 请提供GitHub用户名${NC}"
    echo "使用方法: $0 YOUR_GITHUB_USERNAME"
    exit 1
fi

GITHUB_USERNAME=$1
REPO_NAME="linux-kernel-research"
REPO_URL="https://github.com/$GITHUB_USERNAME/$REPO_NAME.git"

echo -e "${BLUE}🚀 开始设置Linux内核研究项目GitHub仓库...${NC}"
echo -e "${YELLOW}GitHub用户名: $GITHUB_USERNAME${NC}"
echo -e "${YELLOW}仓库名称: $REPO_NAME${NC}"
echo ""

# 检查git状态
if [ ! -d ".git" ]; then
    echo -e "${RED}错误: 当前目录不是git仓库${NC}"
    exit 1
fi

# 检查远程仓库是否已存在
if git remote get-url origin >/dev/null 2>&1; then
    echo -e "${YELLOW}⚠️  远程仓库已存在，正在更新...${NC}"
    git remote set-url origin $REPO_URL
else
    echo -e "${GREEN}➕ 添加远程仓库...${NC}"
    git remote add origin $REPO_URL
fi

echo -e "${GREEN}✅ 远程仓库设置完成${NC}"
echo ""

# 显示下一步操作说明
echo -e "${BLUE}📋 下一步操作:${NC}"
echo "1. 访问 https://github.com/new 创建新仓库"
echo "   - Repository name: $REPO_NAME"
echo "   - Description: Linux内核深度研究项目 - 涵盖内存管理、进程调度、网络子系统、文件系统、设备驱动等核心技术"
echo "   - 选择 Public 或 Private"
echo "   - 不要勾选 'Initialize this repository with' 选项"
echo ""
echo "2. 创建仓库后，运行以下命令推送代码:"
echo -e "${GREEN}   git push -u origin master${NC}"
echo ""
echo "3. 可选 - 启用 GitHub Pages (如果需要展示网站):"
echo "   - 进入仓库 Settings > Pages"
echo "   - Source: Deploy from a branch"
echo "   - Branch: master, Folder: / (root)"
echo ""
echo -e "${BLUE}🌐 如果启用Pages，网站地址将是: https://$GITHUB_USERNAME.github.io/$REPO_NAME/${NC}"
echo ""
echo -e "${YELLOW}⚠️  重要提醒: 本项目包含内核级代码，仅用于学习和研究目的${NC}"
echo -e "${YELLOW}   请在虚拟机或测试环境中运行，不要在生产环境中使用${NC}"
echo ""

# 询问是否现在推送
read -p "是否现在推送代码到GitHub? (y/N): " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    echo -e "${GREEN}🚀 正在推送代码...${NC}"

    # 检查当前分支名
    CURRENT_BRANCH=$(git branch --show-current)
    if [ "$CURRENT_BRANCH" = "main" ]; then
        git push -u origin main
    else
        git push -u origin master
    fi

    echo -e "${GREEN}✅ 代码推送完成！${NC}"
    echo ""
    echo -e "${BLUE}🎉 恭喜！你的Linux内核研究项目已经成功推送到GitHub！${NC}"
    echo -e "${BLUE}� 现在你可以开始深入研究Linux内核的奥秘了！${NC}"
    echo ""
    echo -e "${GREEN}📚 建议下一步:${NC}"
    echo "   1. 阅读各个研究领域的README.md文档"
    echo "   2. 在虚拟机中编译和测试内核模块"
    echo "   3. 使用提供的调试和分析工具"
    echo "   4. 参与项目讨论和贡献代码"
else
    echo -e "${YELLOW}好的，你可以稍后手动推送代码${NC}"
fi

echo ""
echo -e "${GREEN}✨ Linux内核研究项目设置完成！${NC}"
