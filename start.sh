#!/bin/bash
# 启动 Telegram Claude Bot

cd "$(dirname "$0")"

# 创建虚拟环境（如果不存在）
if [ ! -d "venv" ]; then
    echo "📦 创建虚拟环境..."
    python3 -m venv venv
fi

# 激活虚拟环境
source venv/bin/activate

# 安装依赖（如果需要）
if ! python3 -c "import telegram" 2>/dev/null; then
    echo "📦 安装依赖..."
    pip install -r requirements.txt
fi

# 启动 Bot
echo "🤖 启动 Bot..."
python3 bot.py
