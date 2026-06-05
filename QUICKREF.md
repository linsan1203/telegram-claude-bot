# Telegram Claude Bot - 快速参考

## 🚀 启动/停止

```bash
# 启动
cd ~/telegram-claude-bot
./start.sh

# 后台启动
nohup ./start.sh > bot.log 2>&1 &

# 停止
pkill -f "python3 bot.py"

# 查看状态
ps aux | grep "python3 bot.py"
```

## 🤖 Bot 命令

| 命令 | 功能 |
|------|------|
| `/start` | 显示帮助 |
| `/clear` | 清除对话历史 |
| `/context` | 查看当前上下文 |
| `/stats` | 查看会话统计 |

## 🧠 上下文管理

### 配置参数

```python
CONTEXT_CONFIG = {
    "recent_window": 10,      # 保留完整消息数
    "compress_threshold": 15, # 触发压缩阈值
    "max_history": 50,        # 最大历史数
}
```

### 压缩策略

```
消息数量 < 15  →  完整保留
消息数量 > 15  →  自动压缩
                 ├─ 提取关键决策
                 ├─ 生成摘要（调用 Claude）
                 └─ 保留：摘要 + 关键决策 + 最近 10 条
```

### 数据结构

```json
{
  "messages": ["近期消息"],
  "summary": "历史摘要",
  "key_decisions": ["关键决策"],
  "last_compressed_at": "时间戳"
}
```

## 📁 文件说明

```
telegram-claude-bot/
├── bot.py              # 主程序
├── requirements.txt    # 依赖
├── start.sh           # 启动脚本
├── README.md          # 详细文档
├── QUICKREF.md        # 本文件（快速参考）
└── data/
    └── conversation.json  # 对话数据
```

## 🔧 常见操作

### 查看日志

```bash
tail -f bot.log
```

### 清除对话历史

在 Telegram 中发送 `/clear`

### 修改配置

编辑 `bot.py` 中的 `CONTEXT_CONFIG`

### 更新依赖

```bash
cd ~/telegram-claude-bot
source venv/bin/activate
pip install -r requirements.txt
```

## 🐛 快速排错

**Bot 无响应**：
```bash
ps aux | grep "python3 bot.py"
tail -f bot.log
```

**Claude 命令未找到**：
```bash
which claude
```

**对话历史丢失**：
```bash
ls -la data/conversation.json
```

## 📊 监控

```bash
# 查看进程
ps aux | grep bot.py

# 查看资源占用
top -p $(pgrep -f "python3 bot.py")

# 查看对话数据
cat data/conversation.json | jq .
```

---

💡 **提示**：详细文档请查看 `README.md`
