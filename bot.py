"""Telegram bot for collecting and distributing media resources.

Features
--------
* Admins see a "收录资料" (Collect Resources) button via /start.
* Clicking the button puts the bot in collection mode for that admin.
* The admin forwards any number of messages (text, photos, videos, documents,
  media groups/albums) to the bot.
* Clicking "完成收录" finalises the collection:
  - All messages are copied to the main channel.
  - The province is extracted from a line that matches "现居：<province>" in any
    text or caption among the collected messages.
  - If a matching province channel is configured the messages are also copied
    there automatically.
"""

import logging
import os
import re
from typing import Optional

from dotenv import load_dotenv
from telegram import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    InputMediaDocument,
    InputMediaPhoto,
    InputMediaVideo,
    Message,
    Update,
)
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

import config as cfg

load_dotenv()

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# State constants
# ---------------------------------------------------------------------------
IDLE = "idle"
COLLECTING = "collecting"

# In-memory state per admin user
user_state: dict[int, str] = {}
user_messages: dict[int, list[Message]] = {}

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _is_admin(user_id: int) -> bool:
    return user_id in cfg.get_admin_ids()


def _collect_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [[InlineKeyboardButton("收录资料", callback_data="collect")]]
    )


def _done_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [[InlineKeyboardButton("完成收录", callback_data="done_collect")]]
    )


def extract_province(messages: list[Message]) -> Optional[str]:
    """Return the first matching Chinese province found in '现居：<province>' lines."""
    text_content = ""
    for msg in messages:
        if msg.text:
            text_content += msg.text + "\n"
        if msg.caption:
            text_content += msg.caption + "\n"

    match = re.search(r"现居[：:]\s*(.+)", text_content)
    if not match:
        return None

    location = match.group(1).strip()
    for province in cfg.PROVINCE_CHANNEL_ENV:
        if province in location:
            return province
    return None


# ---------------------------------------------------------------------------
# Command / callback handlers
# ---------------------------------------------------------------------------

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /start – show the collect button to admins."""
    if not update.effective_user or not update.message:
        return
    if not _is_admin(update.effective_user.id):
        await update.message.reply_text("您没有权限使用此机器人。")
        return
    await update.message.reply_text("请选择操作：", reply_markup=_collect_keyboard())


async def collect_button(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle the '收录资料' inline button."""
    query = update.callback_query
    if not query or not query.from_user:
        return
    if not _is_admin(query.from_user.id):
        await query.answer("您没有权限使用此功能。")
        return

    await query.answer()

    user_id = query.from_user.id
    user_state[user_id] = COLLECTING
    user_messages[user_id] = []

    await query.message.reply_text(
        "请转发一组资料到这里，完成后点击「完成收录」。",
        reply_markup=_done_keyboard(),
    )


async def done_collect_button(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    """Handle the '完成收录' inline button – process and forward messages."""
    query = update.callback_query
    if not query or not query.from_user:
        return
    if not _is_admin(query.from_user.id):
        await query.answer("您没有权限使用此功能。")
        return

    await query.answer()

    user_id = query.from_user.id

    if user_state.get(user_id) != COLLECTING:
        await query.message.reply_text("当前没有进行中的收录任务。")
        return

    messages = user_messages.get(user_id, [])
    if not messages:
        await query.message.reply_text("未收到任何资料，请先转发资料后再完成收录。")
        return

    # Reset state before processing so new messages are not captured
    user_state[user_id] = IDLE
    user_messages[user_id] = []

    await _process_collection(messages, query.message, context)


async def handle_message(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    """Collect messages forwarded by an admin while in COLLECTING state."""
    if not update.effective_user or not update.effective_message:
        return
    user_id = update.effective_user.id
    if not _is_admin(user_id):
        return
    if user_state.get(user_id) != COLLECTING:
        return

    user_messages.setdefault(user_id, []).append(update.effective_message)


# ---------------------------------------------------------------------------
# Core processing logic
# ---------------------------------------------------------------------------

async def _process_collection(
    messages: list[Message],
    reply_msg: Message,
    context: ContextTypes.DEFAULT_TYPE,
) -> None:
    """Copy collected messages to the main channel and an optional province channel."""
    main_channel = cfg.get_main_channel()
    province_channels = cfg.get_province_channels()

    province = extract_province(messages)

    # Build list of target channels (deduplicated, non-empty)
    target_channels: list[str] = []
    if main_channel:
        target_channels.append(main_channel)
    if province and province in province_channels:
        pch = province_channels[province]
        if pch and pch not in target_channels:
            target_channels.append(pch)

    if not target_channels:
        await reply_msg.reply_text("未配置目标频道，无法发送资料。")
        return

    # Separate media-group messages from single messages
    media_groups: dict[str, list[Message]] = {}
    single_messages: list[Message] = []

    for msg in messages:
        if msg.media_group_id:
            media_groups.setdefault(msg.media_group_id, []).append(msg)
        else:
            single_messages.append(msg)

    errors: list[str] = []

    for channel in target_channels:
        # Send albums as media groups
        for group_msgs in media_groups.values():
            try:
                media_input = []
                for i, msg in enumerate(group_msgs):
                    caption = msg.caption if i == 0 else None
                    caption_entities = msg.caption_entities if i == 0 else None
                    if msg.photo:
                        media_input.append(
                            InputMediaPhoto(
                                media=msg.photo[-1].file_id,
                                caption=caption,
                                caption_entities=caption_entities,
                            )
                        )
                    elif msg.video:
                        media_input.append(
                            InputMediaVideo(
                                media=msg.video.file_id,
                                caption=caption,
                                caption_entities=caption_entities,
                            )
                        )
                    elif msg.document:
                        media_input.append(
                            InputMediaDocument(
                                media=msg.document.file_id,
                                caption=caption,
                                caption_entities=caption_entities,
                            )
                        )
                if media_input:
                    await context.bot.send_media_group(
                        chat_id=channel, media=media_input
                    )
            except Exception as exc:
                logger.error("Error sending media group to %s: %s", channel, exc)
                errors.append(str(exc))

        # Copy single messages
        for msg in single_messages:
            try:
                await context.bot.copy_message(
                    chat_id=channel,
                    from_chat_id=msg.chat_id,
                    message_id=msg.message_id,
                )
            except Exception as exc:
                logger.error("Error copying message to %s: %s", channel, exc)
                errors.append(str(exc))

    # Build status reply
    parts = [f"✅ 收录完成！共处理 {len(messages)} 条消息。"]
    if main_channel:
        parts.append("📢 已发送到主频道")
    if province:
        parts.append(f"📍 识别地区：{province}")
        if province in province_channels:
            parts.append(f"✅ 已转发到{province}频道")
        else:
            parts.append(f"⚠️ 未配置{province}频道，已跳过地区转发")
    else:
        parts.append('⚠️ 未识别到地区信息（请在资料中包含"现居：省份"字段）')
    if errors:
        parts.append(f"⚠️ 发送过程中遇到 {len(errors)} 个错误，请检查日志")

    await reply_msg.reply_text("\n".join(parts))


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> None:
    token = cfg.get_bot_token()
    app = Application.builder().token(token).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(collect_button, pattern="^collect$"))
    app.add_handler(
        CallbackQueryHandler(done_collect_button, pattern="^done_collect$")
    )
    app.add_handler(
        MessageHandler(filters.ALL & ~filters.COMMAND, handle_message)
    )

    logger.info("Bot started. Press Ctrl-C to stop.")
    app.run_polling()


if __name__ == "__main__":
    main()
