#!/bin/bash
# ==============================================================================
# reset.sh — 清空数据库 + 重启容器，开始新议题
#
# 用法:  ./reset.sh [新议题描述...]
#   例如: ./reset.sh "分析某 APT 组织最新活动趋势"
#   不传参数则只清空数据库，不修改 .env
# ==============================================================================
set -e

cd "$(dirname "$0")"

# --- 1. 停止并删除旧容器，抹掉数据库 ---
echo ""
echo "=== [1/3] 停止容器，清空数据库 ==="
docker compose down --remove-orphans 2>/dev/null || true
if [ -f data/nexus.db ]; then
    rm -v data/nexus.db
    echo "数据库已删除"
else
    echo "未找到数据库文件，跳过"
fi

# --- 2. 可选：写入新议题到 .env ---
if [ $# -gt 0 ]; then
    echo ""
    echo "=== [2/3] 更新议题 ==="
    NEW_TOPIC="$*"

    if grep -q '^TRACKING_TOPIC=' .env; then
        # 替换已有行
        sed -i "s|^TRACKING_TOPIC=.*|TRACKING_TOPIC=\"$NEW_TOPIC\"|" .env
    else
        # 没有则追加
        echo "TRACKING_TOPIC=\"$NEW_TOPIC\"" >> .env
    fi
    echo "议题已更新: $NEW_TOPIC"
fi

# --- 3. 重新构建并启动 ---
echo ""
echo "=== [3/3] 重新构建并启动 ==="
docker compose up -d --build

echo ""
echo "=== 完成 ==="
docker compose ps
