# Telegram Claude Bot

通过 Telegram 与 Claude Code CLI 进行对话的机器人。

## 📋 项目概述

这是一个将 Claude Code CLI 封装为 Telegram Bot 的中间层服务，允许用户通过 Telegram 消息界面与 Claude 进行对话，支持上下文保持。

### 核心特性

- ✅ **Claude Code 集成** - 调用本地 `claude` CLI 命令
- ✅ **智能上下文管理** - 借鉴 Claude Code 终端的分层存储策略
- ✅ **自动压缩** - 对话过长时自动总结，保留关键信息
- ✅ **用户认证** - 仅允许指定用户 ID 访问
- ✅ **长消息分割** - 自动处理超过 4096 字符的消息
- ✅ **错误处理** - 完善的异常捕获和用户提示
- ✅ **数据持久化** - 对话历史保存到 JSON 文件

---

## 📁 文件结构

```
telegram-claude-bot/
├── bot.py              # 主程序
├── requirements.txt    # Python 依赖
├── start.sh           # 启动脚本
├── README.md          # 本文档
└── data/              # 数据目录（自动创建）
    └── conversation.json  # 对话历史
```

---

## ⚙️ 配置说明

### 必需配置

在 `bot.py` 中修改以下配置：

```python
# Telegram Bot Token（从 @BotFather 获取）
BOT_TOKEN = "你的Bot Token"

# 允许使用的 Telegram 用户 ID
ALLOWED_USER_ID = 123456789
```

### 可选配置

```python
# 会话历史保留条数（默认 20）
MAX_HISTORY = 20

# 上下文窗口大小（默认 10 条）
CONTEXT_WINDOW = 10

# Claude CLI 超时时间（默认 120 秒）
TIMEOUT = 120
```

---

## 🚀 使用方法

### 1. 安装依赖

```bash
cd ~/telegram-claude-bot

# 创建虚拟环境
python3 -m venv venv
source venv/bin/activate

# 安装依赖
pip install -r requirements.txt
```

### 2. 启动 Bot

```bash
# 前台运行（可查看日志）
./start.sh

# 后台运行
nohup ./start.sh > bot.log 2>&1 &

# 或直接运行
source venv/bin/activate
python3 bot.py
```

### 3. 停止 Bot

```bash
# 查找进程
ps aux | grep "python3 bot.py"

# 停止进程
kill <PID>
```

---

## 🤖 Bot 命令

| 命令 | 说明 |
|------|------|
| `/start` | 显示帮助信息 |
| `/clear` | 清除对话历史 |
| `/context` | 查看当前上下文状态 |
| `/stats` | 查看会话统计信息 |

---

## 🔧 技术实现

### 核心模块

#### 1. 上下文管理（借鉴 Claude Code 终端）

**设计原则**：
- **分层存储**：近期详细 + 远期摘要
- **智能压缩**：超过阈值时自动总结
- **关键信息保留**：重要决策始终可见

**数据结构**：

```json
{
  "messages": [...],           // 近期完整消息
  "summary": "...",            // 历史摘要
  "key_decisions": [...],      // 关键决策
  "last_compressed_at": "..."  // 上次压缩时间
}
```

**压缩策略**：

```
┌─────────────────────────────────────────────────────┐
│                    对话历史                          │
├─────────────────────────────────────────────────────┤
│  旧消息（超过阈值）          │  新消息（保留）      │
│  ↓                           │                     │
│  提取关键决策                │  完整保留            │
│  ↓                           │                     │
│  生成摘要（调用 Claude）     │                     │
│  ↓                           │                     │
│  丢弃原始消息                │                     │
├─────────────────────────────────────────────────────┤
│  最终结构：摘要 + 关键决策 + 近期消息               │
└─────────────────────────────────────────────────────┘
```

**上下文构建**：

```python
def get_context_prompt() -> str:
    """
    构建带上下文的 prompt

    结构：
    1. 历史摘要（如果有）
    2. 关键决策（如果有）
    3. 近期对话（完整保留）
    """
```

**配置参数**：

```python
CONTEXT_CONFIG = {
    "recent_window": 10,      # 近期窗口：保留完整消息数
    "compress_threshold": 15, # 压缩阈值：超过此数量触发总结
    "max_history": 50,        # 最大历史记录数
    "summary_max_tokens": 500 # 摘要最大长度
}
```

#### 2. 消息管理

```python
def load_conversation() -> dict:
    """从 JSON 文件加载会话历史"""

def save_conversation(conv: dict):
    """保存会话历史到 JSON 文件"""

def add_message(role: str, content: str):
    """添加消息到历史，自动触发压缩"""
```

#### 2. Claude CLI 调用

```python
def call_claude(prompt: str, use_context: bool = True) -> str:
    """
    调用 Claude Code CLI

    参数:
        prompt: 用户输入的消息
        use_context: 是否包含上下文历史

    返回:
        Claude 的回复文本

    实现:
        - 构建带上下文的完整 prompt
        - 使用 subprocess 调用 claude -p "prompt" --output-format text
        - 处理超时和错误
    """
```

#### 3. Telegram Handlers

```python
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    处理用户消息

    流程:
        1. 验证用户身份
        2. 发送"思考中"提示
        3. 保存用户消息到历史
        4. 调用 Claude CLI
        5. 保存 Claude 回复到历史
        6. 发送回复（自动分割长消息）
    """
```

### 数据格式

**conversation.json**

```json
{
  "messages": [
    {
      "role": "user",
      "content": "你好"
    },
    {
      "role": "assistant",
      "content": "你好！有什么我可以帮你的吗？"
    }
  ]
}
```

### 上下文传递机制

```
用户消息: "写一个排序算法"
         ↓
构建 prompt:
  "Previous conversation:
   Human: 什么是算法？
   Assistant: 算法是解决问题的步骤...
   Current question: 写一个排序算法"
         ↓
调用: claude -p "完整prompt" --output-format text
         ↓
返回结果给用户
```

---

## 🛡️ 安全特性

### 用户认证

```python
async def check_auth(update: Update) -> bool:
    """验证用户 ID 是否在白名单"""
    user_id = update.effective_user.id
    if user_id != ALLOWED_USER_ID:
        await update.message.reply_text("⛔ 未授权访问")
        return False
    return True
```

### 输入验证

- 只处理文本消息
- 超时保护（120 秒）
- 错误捕获和提示

---

## 📈 扩展指南

### 1. 添加新命令

```python
async def new_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """新命令处理函数"""
    if not await check_auth(update):
        return

    # 逻辑处理
    await update.message.reply_text("回复内容")

# 注册命令
app.add_handler(CommandHandler("new", new_command))
```

### 2. 支持多用户

```python
# 修改配置
ALLOWED_USER_IDS = [123456, 789012]

# 修改认证逻辑
async def check_auth(update: Update) -> bool:
    user_id = update.effective_user.id
    if user_id not in ALLOWED_USER_IDS:
        await update.message.reply_text("⛔ 未授权访问")
        return False
    return True

# 为每个用户维护独立会话
def get_user_conversation_file(user_id: int) -> Path:
    return DATA_DIR / f"conversation_{user_id}.json"
```

### 3. 添加文件处理

```python
async def handle_document(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """处理文档消息"""
    if not await check_auth(update):
        return

    file = await update.message.document.get_file()
    file_path = await file.download_to_drive()

    # 调用 Claude 分析文件
    response = call_claude(f"分析这个文件: {file_path}")
    await update.message.reply_text(response)

# 注册处理器
app.add_handler(MessageHandler(filters.Document.ALL, handle_document))
```

### 4. 添加图片处理

```python
async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """处理图片消息"""
    if not await check_auth(update):
        return

    photo = update.message.photo[-1]  # 获取最高分辨率
    file = await photo.get_file()
    file_path = await file.download_to_drive()

    # 调用 Claude 分析图片
    response = call_claude(f"描述这张图片: {file_path}")
    await update.message.reply_text(response)
```

### 5. 集成 Claude Vision API

```python
import base64

def call_claude_with_image(image_path: str, prompt: str) -> str:
    """使用 Claude Vision API 分析图片"""
    with open(image_path, "rb") as f:
        image_data = base64.standard_b64encode(f.read()).decode("utf-8")

    # 需要使用 Anthropic API 而非 CLI
    # 这里需要修改为 API 调用方式
    pass
```

### 6. 添加速率限制

```python
from collections import defaultdict
import time

# 用户请求记录
user_requests = defaultdict(list)
RATE_LIMIT = 10  # 每分钟最大请求数

async def check_rate_limit(user_id: int) -> bool:
    """检查是否超过速率限制"""
    now = time.time()
    user_requests[user_id] = [
        t for t in user_requests[user_id] if now - t < 60
    ]

    if len(user_requests[user_id]) >= RATE_LIMIT:
        return False

    user_requests[user_id].append(now)
    return True
```

---

## 🧠 上下文管理详解

### 为什么需要智能压缩？

**问题**：
- 简单的 FIFO 策略（保留最近 N 条）会丢失重要上下文
- 长对话中，早期的关键决策可能被遗忘
- 每次都传入完整历史会浪费 token

**借鉴 Claude Code 终端的解决方案**：

1. **分层存储**
   - 近期消息：完整保留，确保连贯性
   - 远期消息：压缩成摘要，保留关键信息

2. **智能压缩**
   - 使用 Claude 自身来总结对话
   - 提取关键决策，始终保留在上下文中

3. **动态调整**
   - 根据对话长度自动触发压缩
   - 保留最重要的信息

### 压缩流程示例

```
用户消息 1: "我们要用 Python 开发"
用户消息 2: "选择 Flask 框架"
用户消息 3-15: 各种讨论...
用户消息 16: "添加用户认证"  ← 超过阈值，触发压缩

压缩过程：
1. 提取关键决策：
   - "使用 Python + Flask"
   - "需要用户认证"

2. 生成摘要：
   "讨论了项目架构，决定使用 Python + Flask，
    需要实现用户认证功能..."

3. 最终上下文：
   [摘要] + [关键决策] + [消息 6-16]
```

### 手动查看上下文

使用 `/context` 命令可以查看：
- 📝 历史摘要
- 🎯 关键决策
- 💬 近期对话

使用 `/stats` 命令可以查看：
- 消息数量
- 压缩状态
- 配置参数

---

## 🐛 故障排除

### 常见问题

#### 1. Bot 无响应

**症状**: 发送消息后没有回复

**可能原因**:
- Bot 进程未运行
- Token 错误
- 用户 ID 未授权

**解决方案**:
```bash
# 检查进程
ps aux | grep "python3 bot.py"

# 查看日志
tail -f bot.log

# 验证 Token
curl "https://api.telegram.org/bot<TOKEN>/getMe"
```

#### 2. Claude 命令未找到

**症状**: 错误提示 "未找到 claude 命令"

**解决方案**:
```bash
# 检查 claude 是否安装
which claude

# 如果未安装，参考 Claude Code 安装文档
```

#### 3. 对话历史丢失

**症状**: Bot 重启后忘记之前的对话

**可能原因**:
- `data/conversation.json` 文件被删除
- 文件权限问题

**解决方案**:
```bash
# 检查文件是否存在
ls -la data/

# 检查权限
chmod 644 data/conversation.json
```

#### 4. 消息发送失败

**症状**: 错误提示 "Message is too long"

**说明**: Telegram 消息长度限制 4096 字符，Bot 会自动分割，如果仍有问题：

```python
# 在 handle_message 中添加日志
print(f"Response length: {len(response)}")
```

---

## 📊 性能优化

### 1. 异步调用 Claude

当前使用同步 `subprocess.run()`，会阻塞主线程。可以改为异步：

```python
import asyncio

async def call_claude_async(prompt: str, use_context: bool = True) -> str:
    """异步调用 Claude CLI"""
    cmd = ["claude", "-p", prompt, "--output-format", "text"]

    process = await asyncio.create_subprocess_exec(
        *cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE
    )

    stdout, stderr = await process.communicate()

    if process.returncode != 0:
        return f"❌ Claude 错误:\n{stderr.decode()}"

    return stdout.decode().strip()
```

### 2. 缓存机制

```python
from functools import lru_cache

@lru_cache(maxsize=100)
def cached_claude_call(prompt: str) -> str:
    """缓存相同请求的结果"""
    return call_claude(prompt, use_context=False)
```

### 3. 数据库存储

对于大规模使用，建议用 SQLite 或 PostgreSQL：

```python
import sqlite3

def init_db():
    conn = sqlite3.connect('conversations.db')
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            role TEXT,
            content TEXT,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    conn.commit()
    return conn
```

---

## 🔄 版本历史

### v1.0.0 (2026-06-03)
- ✅ 基础对话功能
- ✅ 上下文保持
- ✅ 用户认证
- ✅ 命令支持（/start, /clear, /context）

---

## 📝 开发计划

### 短期
- [ ] 添加 /help 命令显示详细帮助
- [ ] 支持回复特定消息
- [ ] 添加消息队列避免并发问题

### 中期
- [ ] 支持文件上传和分析
- [ ] 支持图片识别（Claude Vision）
- [ ] 多用户支持

### 长期
- [ ] Web 管理界面
- [ ] 对话导出功能
- [ ] 集成更多 Claude 功能

---

## 🤝 贡献指南

1. Fork 项目
2. 创建功能分支
3. 提交更改
4. 推送到分支
5. 创建 Pull Request

---

## 📄 许可证

MIT License

---

## 🙏 致谢

- [python-telegram-bot](https://github.com/python-telegram-bot/python-telegram-bot)
- [Claude Code](https://docs.anthropic.com/claude-code)

---

## 📞 支持

遇到问题？查看：
1. 本文档的"故障排除"章节
2. GitHub Issues
3. 相关项目的官方文档
