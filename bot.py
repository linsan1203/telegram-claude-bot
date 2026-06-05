#!/usr/bin/env python3
"""
Telegram Bot for Claude Code CLI
通过 Telegram 与 Claude Code 进行对话

上下文管理策略（借鉴 Claude Code 终端）：
- 分层存储：近期详细 + 远期摘要
- 智能压缩：超过阈值时自动总结
- 关键信息保留：重要决策始终可见
"""

import subprocess
import asyncio
import json
import os
from pathlib import Path
from datetime import datetime
from telegram import Update
from telegram.ext import Application, MessageHandler, CommandHandler, filters, ContextTypes

# ============ 配置 ============
BOT_TOKEN = "8703978277:AAEUTrYqz-Vys22i-c8chGbovNSM-WaIhLE"
ALLOWED_USER_ID = 2020648226  # 只允许这个用户使用

# 上下文管理配置
CONTEXT_CONFIG = {
    "recent_window": 8,       # 近期窗口：保留完整消息数（减少以加快速度）
    "compress_threshold": 12, # 压缩阈值：超过此数量触发总结
    "max_history": 30,        # 最大历史记录数
    "summary_max_tokens": 300 # 摘要最大长度
}

# 超时和重试配置
CLAUDE_CONFIG = {
    "timeout": 180,           # 超时时间：180 秒（原 120 秒）
    "max_retries": 2,         # 最大重试次数
    "retry_delay": 5,         # 重试间隔（秒）
    "context_max_chars": 2000 # 上下文最大字符数（避免太长）
}

# 会话数据存储路径
DATA_DIR = Path(__file__).parent / "data"
DATA_DIR.mkdir(exist_ok=True)
CONVERSATION_FILE = DATA_DIR / "conversation.json"

# 文件上传目录
UPLOAD_DIR = DATA_DIR / "uploads"
UPLOAD_DIR.mkdir(exist_ok=True)

# 流式响应配置
STREAM_CONFIG = {
    "update_interval": 1.5,    # 更新间隔（秒）- Telegram 有频率限制
    "min_change_len": 50,      # 最小变化长度才触发更新
}

# ============ 会话管理 ============
def load_conversation() -> dict:
    """
    加载会话历史

    数据结构：
    {
        "messages": [...],           # 完整消息历史
        "summary": "...",            # 历史摘要（当消息被压缩时）
        "key_decisions": [...],      # 关键决策列表
        "last_compressed_at": 123456 # 上次压缩时间
    }
    """
    if CONVERSATION_FILE.exists():
        with open(CONVERSATION_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            # 确保所有字段存在
            if "summary" not in data:
                data["summary"] = ""
            if "key_decisions" not in data:
                data["key_decisions"] = []
            if "last_compressed_at" not in data:
                data["last_compressed_at"] = 0
            return data
    return {
        "messages": [],
        "summary": "",
        "key_decisions": [],
        "last_compressed_at": 0
    }

def save_conversation(conv: dict):
    """保存会话历史"""
    with open(CONVERSATION_FILE, "w", encoding="utf-8") as f:
        json.dump(conv, f, ensure_ascii=False, indent=2)

def add_message(role: str, content: str):
    """
    添加消息到历史

    流程：
    1. 添加新消息
    2. 检查是否需要压缩
    3. 如果需要，触发智能压缩
    """
    conv = load_conversation()

    # 添加时间戳
    message = {
        "role": role,
        "content": content,
        "timestamp": datetime.now().isoformat()
    }

    conv["messages"].append(message)

    # 检查是否需要压缩
    if len(conv["messages"]) > CONTEXT_CONFIG["compress_threshold"]:
        conv = compress_conversation(conv)

    save_conversation(conv)

def extract_key_decisions(messages: list) -> list:
    """
    从消息中提取关键决策

    关键决策包括：
    - 用户明确的要求或偏好
    - 重要的技术选择
    - 需要后续跟进的事项
    """
    decisions = []

    for msg in messages:
        content = msg["content"].lower()

        # 检测关键决策模式
        decision_patterns = [
            "我决定", "我们选择", "确认使用", "采用方案",
            "记住", "重要", "下次", "以后",
            "decision", "choose", "use", "important"
        ]

        if any(pattern in content for pattern in decision_patterns):
            decisions.append({
                "content": msg["content"][:200],  # 限制长度
                "role": msg["role"],
                "timestamp": msg.get("timestamp", "")
            })

    return decisions[-5:]  # 只保留最近 5 个关键决策

def compress_conversation(conv: dict) -> dict:
    """
    智能压缩对话历史

    策略：
    1. 提取关键决策
    2. 让 Claude 总结旧消息
    3. 保留：摘要 + 关键决策 + 近期消息
    """
    messages = conv["messages"]

    if len(messages) <= CONTEXT_CONFIG["compress_threshold"]:
        return conv

    # 分割：旧消息（需要总结）和新消息（保留）
    split_point = len(messages) - CONTEXT_CONFIG["recent_window"]
    old_messages = messages[:split_point]
    new_messages = messages[split_point:]

    # 提取关键决策
    key_decisions = extract_key_decisions(old_messages)

    # 生成摘要
    summary = generate_summary(old_messages, conv.get("summary", ""))

    # 更新结构
    conv["messages"] = new_messages
    conv["summary"] = summary
    conv["key_decisions"] = key_decisions
    conv["last_compressed_at"] = datetime.now().isoformat()

    print(f"📦 压缩完成: {len(old_messages)} 条消息 → 摘要 + {len(new_messages)} 条保留")

    return conv

def generate_summary(old_messages: list, existing_summary: str) -> str:
    """
    生成对话摘要

    使用 Claude 来总结对话，保留关键信息
    """
    # 构建总结请求
    messages_text = "\n".join([
        f"{msg['role']}: {msg['content'][:200]}"
        for msg in old_messages[-20:]  # 只取最近 20 条旧消息
    ])

    summary_prompt = f"""请用中文总结以下对话的要点，保留关键信息和决策，限制在 300 字内。

{f"已有摘要：{existing_summary}" if existing_summary else ""}

对话内容：
{messages_text}

请总结："""

    try:
        cmd = ["claude", "-p", summary_prompt, "--output-format", "text", "--dangerously-skip-permissions"]
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=30,
            cwd=str(Path.home())
        )

        if result.returncode == 0:
            return result.stdout.strip()
    except Exception as e:
        print(f"⚠️ 生成摘要失败: {e}")

    # 如果失败，使用简单截断
    return existing_summary + "\n" + "\n".join([
        f"- {msg['role']}: {msg['content'][:100]}"
        for msg in old_messages[-5:]
    ])

def get_context_prompt() -> str:
    """
    构建带上下文的 prompt（优化版）

    优化策略：
    1. 控制总长度，避免 token 浪费
    2. 优先保留关键决策
    3. 截断过长的消息
    """
    conv = load_conversation()

    if not conv["messages"] and not conv["summary"]:
        return ""

    context_parts = []
    total_chars = 0
    max_chars = CLAUDE_CONFIG["context_max_chars"]

    # 1. 关键决策（优先级最高）
    if conv["key_decisions"]:
        decisions_text = "\n".join([
            f"- {d['content'][:100]}"
            for d in conv["key_decisions"][-3:]  # 只保留最近 3 个
        ])
        decisions_section = f"[关键决策]\n{decisions_text}"
        if total_chars + len(decisions_section) < max_chars:
            context_parts.append(decisions_section)
            total_chars += len(decisions_section)

    # 2. 历史摘要（如果有）
    if conv["summary"]:
        summary_section = f"[历史摘要]\n{conv['summary'][:300]}"
        if total_chars + len(summary_section) < max_chars:
            context_parts.append(summary_section)
            total_chars += len(summary_section)

    # 3. 近期对话（截断过长消息）
    if conv["messages"]:
        recent_messages = conv["messages"][-CONTEXT_CONFIG["recent_window"]:]
        recent_lines = []
        for msg in recent_messages:
            content = msg['content']
            # 截断过长消息
            if len(content) > 200:
                content = content[:200] + "..."
            recent_lines.append(f"{msg['role']}: {content}")

        recent_text = "\n".join(recent_lines)
        recent_section = f"[近期对话]\n{recent_text}"

        if total_chars + len(recent_section) < max_chars:
            context_parts.append(recent_section)

    return "\n\n".join(context_parts)

# ============ Claude CLI 调用 ============
def call_claude(prompt: str, use_context: bool = True) -> str:
    """
    调用 Claude Code CLI（带重试机制）

    优化：
    1. 增加超时时间
    2. 自动重试
    3. 精简 prompt
    """
    for attempt in range(CLAUDE_CONFIG["max_retries"] + 1):
        try:
            # 构建完整 prompt（带上下文）
            if use_context:
                context = get_context_prompt()
                if context:
                    # 精简 prompt 结构
                    full_prompt = f"上下文：\n{context}\n\n问题：{prompt}"
                else:
                    full_prompt = prompt
            else:
                full_prompt = prompt

            # 调用 claude CLI (yolo 模式：跳过权限检查)
            cmd = ["claude", "-p", full_prompt, "--output-format", "text", "--dangerously-skip-permissions"]

            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=CLAUDE_CONFIG["timeout"],
                cwd=str(Path.home())
            )

            if result.returncode != 0:
                if attempt < CLAUDE_CONFIG["max_retries"]:
                    print(f"⚠️ Claude 调用失败，重试 {attempt + 1}/{CLAUDE_CONFIG['max_retries']}")
                    import time
                    time.sleep(CLAUDE_CONFIG["retry_delay"])
                    continue
                return f"❌ Claude 错误:\n{result.stderr}"

            return result.stdout.strip()

        except subprocess.TimeoutExpired:
            if attempt < CLAUDE_CONFIG["max_retries"]:
                print(f"⏰ 超时，重试 {attempt + 1}/{CLAUDE_CONFIG['max_retries']}")
                import time
                time.sleep(CLAUDE_CONFIG["retry_delay"])
                continue
            return "⏰ 请求超时，Claude 处理时间过长，请稍后重试"
        except FileNotFoundError:
            return "❌ 未找到 claude 命令，请确认已安装 Claude Code CLI"
        except Exception as e:
            if attempt < CLAUDE_CONFIG["max_retries"]:
                print(f"❌ 错误: {e}，重试 {attempt + 1}/{CLAUDE_CONFIG['max_retries']}")
                import time
                time.sleep(CLAUDE_CONFIG["retry_delay"])
                continue
            return f"❌ 错误: {str(e)}"

    return "❌ 多次重试后仍然失败"

async def call_claude_stream(prompt: str, use_context: bool = True, callback=None) -> str:
    """
    异步调用 Claude CLI（流式输出）

    优化：
    1. 实时读取输出
    2. 定期回调更新消息
    3. 更好的用户体验
    """
    # 构建完整 prompt（带上下文）
    if use_context:
        context = get_context_prompt()
        if context:
            full_prompt = f"上下文：\n{context}\n\n问题：{prompt}"
        else:
            full_prompt = prompt
    else:
        full_prompt = prompt

    # 调用 claude CLI (yolo 模式：跳过权限检查)
    cmd = ["claude", "-p", full_prompt, "--output-format", "text", "--dangerously-skip-permissions"]

    try:
        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=str(Path.home())
        )

        output_lines = []
        last_update = asyncio.get_event_loop().time()
        last_output = ""

        # 逐行读取输出
        while True:
            line = await asyncio.wait_for(
                process.stdout.readline(),
                timeout=CLAUDE_CONFIG["timeout"]
            )

            if not line:
                break

            decoded_line = line.decode("utf-8", errors="replace")
            output_lines.append(decoded_line)
            current_output = "".join(output_lines).strip()

            # 定期回调更新消息
            now = asyncio.get_event_loop().time()
            if callback and (now - last_update) >= STREAM_CONFIG["update_interval"]:
                if len(current_output) - len(last_output) >= STREAM_CONFIG["min_change_len"]:
                    try:
                        await callback(current_output + " ▌")
                        last_output = current_output
                        last_update = now
                    except Exception:
                        pass  # 忽略更新失败

        # 等待进程结束
        await process.wait()

        final_output = "".join(output_lines).strip()

        if process.returncode != 0:
            stderr = await process.stderr.read()
            return f"❌ Claude 错误:\n{stderr.decode('utf-8', errors='replace')}"

        return final_output

    except asyncio.TimeoutError:
        return "⏰ 请求超时，Claude 处理时间过长，请稍后重试"
    except FileNotFoundError:
        return "❌ 未找到 claude 命令，请确认已安装 Claude Code CLI"
    except Exception as e:
        return f"❌ 错误: {str(e)}"

def download_file(file_path: str, dest_path: Path) -> Path:
    """下载文件到指定目录"""
    dest_path.parent.mkdir(parents=True, exist_ok=True)
    return dest_path

# ============ Telegram Handlers ============
async def check_auth(update: Update) -> bool:
    """检查是否是授权用户"""
    user_id = update.effective_user.id
    if user_id != ALLOWED_USER_ID:
        await update.message.reply_text("⛔ 未授权访问")
        return False
    return True

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """处理 /start 命令"""
    if not await check_auth(update):
        return

    welcome = """🤖 Claude Code Telegram Bot

我可以帮你：
• 回答问题
• 编写代码
• 分析文件
• 执行命令

直接发消息给我就行！

命令：
/start - 显示帮助
/clear - 清除对话历史
/context - 查看当前上下文
/stats - 查看会话统计"""

    await update.message.reply_text(welcome)

async def clear_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """清除对话历史"""
    if not await check_auth(update):
        return

    save_conversation({
        "messages": [],
        "summary": "",
        "key_decisions": [],
        "last_compressed_at": 0
    })
    await update.message.reply_text("✅ 对话历史已清除")

async def context_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """查看当前上下文"""
    if not await check_auth(update):
        return

    conv = load_conversation()

    text = "📊 当前上下文状态：\n\n"

    # 显示摘要
    if conv["summary"]:
        text += f"📝 历史摘要：\n{conv['summary'][:200]}...\n\n"

    # 显示关键决策
    if conv["key_decisions"]:
        text += "🎯 关键决策：\n"
        for d in conv["key_decisions"]:
            text += f"• {d['content'][:100]}\n"
        text += "\n"

    # 显示最近消息
    if conv["messages"]:
        text += f"💬 近期对话（最近 {len(conv['messages'])} 条）：\n"
        for msg in conv["messages"][-5:]:
            role = "👤" if msg["role"] == "user" else "🤖"
            content = msg["content"][:80] + "..." if len(msg["content"]) > 80 else msg["content"]
            text += f"{role} {content}\n"
    else:
        text += "📭 暂无近期对话"

    await update.message.reply_text(text)

async def stats_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """查看会话统计"""
    if not await check_auth(update):
        return

    conv = load_conversation()

    text = f"""📈 会话统计：

💬 近期消息数：{len(conv['messages'])}
📝 有历史摘要：{'是' if conv['summary'] else '否'}
🎯 关键决策数：{len(conv['key_decisions'])}
📦 上次压缩：{conv.get('last_compressed_at', '从未')}

⚙️ 配置：
• 近期窗口：{CONTEXT_CONFIG['recent_window']} 条
• 压缩阈值：{CONTEXT_CONFIG['compress_threshold']} 条
• 最大历史：{CONTEXT_CONFIG['max_history']} 条

⏱️ 超时配置：
• 超时时间：{CLAUDE_CONFIG['timeout']} 秒
• 最大重试：{CLAUDE_CONFIG['max_retries']} 次
• 上下文限制：{CLAUDE_CONFIG['context_max_chars']} 字符"""

    await update.message.reply_text(text)

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """处理普通消息（流式输出版）"""
    if not await check_auth(update):
        return

    user_message = update.message.text

    # 发送"正在思考"提示
    thinking_msg = await update.message.reply_text("绞尽脑汁全力输出中～")

    # 保存用户消息
    add_message("user", user_message)

    # 定义流式更新回调
    async def stream_callback(partial_output: str):
        try:
            # 截断过长的消息（Telegram 限制 4096）
            if len(partial_output) > 4000:
                partial_output = partial_output[:4000] + "..."
            await thinking_msg.edit_text(partial_output)
        except Exception:
            pass  # 忽略编辑失败（可能是内容没变化）

    # 调用 Claude（流式输出）
    response = await call_claude_stream(user_message, use_context=True, callback=stream_callback)

    # 保存 Claude 回复
    add_message("assistant", response)

    # 删除"正在思考"消息，发送最终回复
    try:
        await thinking_msg.delete()
    except Exception:
        pass  # 忽略删除失败

    # Telegram 消息长度限制 4096，需要分割
    if len(response) <= 4096:
        await update.message.reply_text(response)
    else:
        chunks = [response[i:i+4096] for i in range(0, len(response), 4096)]
        for chunk in chunks:
            await update.message.reply_text(chunk)

async def handle_document(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """处理上传的文档"""
    if not await check_auth(update):
        return

    document = update.message.document
    file_name = document.file_name or "unknown_file"
    file_size = document.file_size

    # 检查文件大小（限制 20MB）
    if file_size > 20 * 1024 * 1024:
        await update.message.reply_text("❌ 文件太大，最大支持 20MB")
        return

    # 发送处理提示
    status_msg = await update.message.reply_text(f"📥 正在下载文件: {file_name}...")

    try:
        # 下载文件
        file = await document.get_file()
        file_path = UPLOAD_DIR / file_name
        await file.download_to_drive(file_path)

        await status_msg.edit_text(f"🔍 正在分析文件: {file_name}...")

        # 构建分析提示
        prompt = f"请分析这个文件的内容和结构：{file_path}"

        # 定义流式更新回调
        async def stream_callback(partial_output: str):
            try:
                display_text = f"🔍 分析 {file_name}：\n\n{partial_output}"
                if len(display_text) > 4000:
                    display_text = display_text[:4000] + "..."
                await status_msg.edit_text(display_text)
            except Exception:
                pass

        # 调用 Claude 分析
        response = await call_claude_stream(prompt, use_context=False, callback=stream_callback)

        # 删除状态消息，发送结果
        await status_msg.delete()

        # 发送分析结果
        result_text = f"📄 文件分析: {file_name}\n\n{response}"
        if len(result_text) <= 4096:
            await update.message.reply_text(result_text)
        else:
            await update.message.reply_text(f"📄 文件分析: {file_name}")
            chunks = [response[i:i+4096] for i in range(0, len(response), 4096)]
            for chunk in chunks:
                await update.message.reply_text(chunk)

    except Exception as e:
        await status_msg.edit_text(f"❌ 文件处理失败: {str(e)}")

async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """处理上传的图片"""
    if not await check_auth(update):
        return

    # 获取最高分辨率的图片
    photo = update.message.photo[-1]
    caption = update.message.caption or ""

    # 发送处理提示
    status_msg = await update.message.reply_text("🖼️ 正在下载图片...")

    try:
        # 下载图片
        file = await photo.get_file()
        file_path = UPLOAD_DIR / f"photo_{photo.file_unique_id}.jpg"
        await file.download_to_drive(file_path)

        await status_msg.edit_text("🔍 正在分析图片...")

        # 构建分析提示
        if caption:
            prompt = f"请分析这张图片：{file_path}\n\n用户说明：{caption}"
        else:
            prompt = f"请详细描述和分析这张图片的内容：{file_path}"

        # 定义流式更新回调
        async def stream_callback(partial_output: str):
            try:
                display_text = f"🖼️ 图片分析：\n\n{partial_output}"
                if len(display_text) > 4000:
                    display_text = display_text[:4000] + "..."
                await status_msg.edit_text(display_text)
            except Exception:
                pass

        # 调用 Claude 分析
        response = await call_claude_stream(prompt, use_context=False, callback=stream_callback)

        # 删除状态消息，发送结果
        await status_msg.delete()

        # 发送分析结果
        result_text = f"🖼️ 图片分析\n\n{response}"
        if len(result_text) <= 4096:
            await update.message.reply_text(result_text)
        else:
            await update.message.reply_text("🖼️ 图片分析")
            chunks = [response[i:i+4096] for i in range(0, len(response), 4096)]
            for chunk in chunks:
                await update.message.reply_text(chunk)

    except Exception as e:
        await status_msg.edit_text(f"❌ 图片处理失败: {str(e)}")

async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """处理错误"""
    print(f"Error: {context.error}")
    if update and update.message:
        await update.message.reply_text("❌ 发生错误，请稍后重试")

# ============ Main ============
def main():
    """启动 Bot"""
    print("🚀 启动 Telegram Claude Bot...")
    print(f"📁 数据目录: {DATA_DIR}")
    print(f"⚙️ 上下文配置: {CONTEXT_CONFIG}")

    # 创建 Application
    app = Application.builder().token(BOT_TOKEN).build()

    # 添加命令处理器
    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CommandHandler("clear", clear_command))
    app.add_handler(CommandHandler("context", context_command))
    app.add_handler(CommandHandler("stats", stats_command))

    # 添加消息处理器
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    app.add_handler(MessageHandler(filters.Document.ALL, handle_document))
    app.add_handler(MessageHandler(filters.PHOTO, handle_photo))

    # 添加错误处理器
    app.add_error_handler(error_handler)

    # 启动轮询
    print("✅ Bot 已启动，等待消息...")
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
