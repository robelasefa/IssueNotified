"""
Broadcast command callback handlers (admin only).
"""

import logging
import warnings

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import (
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    ConversationHandler,
    MessageHandler,
    filters,
)
from telegram.warnings import PTBUserWarning

import config
from database import db

logger = logging.getLogger(__name__)

GET_MESSAGE, CONFIRM = range(2)
_CB_CONFIRM = "broadcast|confirm"
_CB_CANCEL = "broadcast|cancel"


async def broadcast_command(update: Update, _: ContextTypes.DEFAULT_TYPE):
    """Start the broadcast conversation."""
    user_id = update.effective_user.id

    if user_id != config.ADMIN_USER_ID:
        return ConversationHandler.END

    await update.message.reply_text(
        "📢 *Admin Broadcast*\n\n"
        "Please send the message you want to broadcast to all users.\n"
        "You can use Markdown formatting.\n\n"
        "Type /cancel to abort.",
        parse_mode="Markdown",
    )
    return GET_MESSAGE


async def handle_broadcast_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Store the message and ask for confirmation."""
    context.user_data["broadcast_message"] = update.message.text

    keyboard = [
        [
            InlineKeyboardButton("✅ Confirm & Send", callback_data=_CB_CONFIRM),
            InlineKeyboardButton("❌ Cancel", callback_data=_CB_CANCEL),
        ]
    ]

    await update.message.reply_text(
        "📝 *Preview of your message:*", parse_mode="Markdown"
    )

    try:
        # Send the actual message as it will appear to users
        await update.message.reply_text(
            update.message.text,
            parse_mode="Markdown",  # Default to Markdown (V1)
        )
    except Exception as e:
        await update.message.reply_text(
            f"❌ *Formatting Error*\n\n"
            f"Your message contains invalid Markdown: `{e}`\n\n"
            "Please fix it and send the message again, or type /cancel.",
            parse_mode="Markdown",
        )
        return GET_MESSAGE

    keyboard = [
        [
            InlineKeyboardButton("✅ Confirm & Send", callback_data=_CB_CONFIRM),
            InlineKeyboardButton("❌ Cancel", callback_data=_CB_CANCEL),
        ]
    ]

    await update.message.reply_text(
        "⚠️ *Are you sure you want to send this to ALL users?*",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="Markdown",
    )
    return CONFIRM
    return CONFIRM


async def handle_broadcast_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Execute the broadcast or cancel."""
    query = update.callback_query
    await query.answer()

    if query.data == _CB_CANCEL:
        await query.edit_message_text("❌ Broadcast cancelled.")
        return ConversationHandler.END

    message = context.user_data.get("broadcast_message")
    if not message:
        await query.edit_message_text("❌ Error: No message found.")
        return ConversationHandler.END

    await query.edit_message_text("🚀 *Broadcasting message...*", parse_mode="Markdown")

    user_ids = db.get_all_user_ids()
    total = len(user_ids)
    success = 0
    failed = 0

    for uid in user_ids:
        try:
            await context.bot.send_message(
                chat_id=uid,
                text=message,
                parse_mode="Markdown",
            )
            success += 1
        except Exception as e:
            logger.error(f"Failed to send broadcast to {uid}: {e}")
            failed += 1

    await query.edit_message_text(
        "✅ *Broadcast Complete*\n\n"
        f"📊 *Results:*\n"
        f"• Total users: {total}\n"
        f"• Successfully sent: {success}\n"
        f"• Failed: {failed}",
        parse_mode="Markdown",
    )

    context.user_data.pop("broadcast_message", None)
    return ConversationHandler.END


async def cancel_broadcast(update: Update, _: ContextTypes.DEFAULT_TYPE):
    """Cancel the broadcast conversation."""
    await update.message.reply_text("❌ Broadcast aborted.")
    return ConversationHandler.END


warnings.filterwarnings(
    action="ignore", message=r".*CallbackQueryHandler.*", category=PTBUserWarning
)
broadcast_conv_handler = ConversationHandler(
    entry_points=[CommandHandler("broadcast", broadcast_command)],
    states={
        GET_MESSAGE: [
            MessageHandler(filters.TEXT & ~filters.COMMAND, handle_broadcast_message)
        ],
        CONFIRM: [
            CallbackQueryHandler(handle_broadcast_callback, pattern=r"^broadcast\|")
        ],
    },
    fallbacks=[CommandHandler("cancel", cancel_broadcast)],
)
