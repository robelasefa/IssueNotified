import logging
import warnings

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.constants import ParseMode
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
from ai import ai_client
from database import db

logger = logging.getLogger(__name__)

GET_MESSAGE, CONFIRM = range(2)
_CB_CONFIRM = "broadcast|confirm"
_CB_CANCEL = "broadcast|cancel"
_CB_AI_POLISH = "broadcast|ai_polish"


def _confirm_keyboard(include_ai: bool = False) -> InlineKeyboardMarkup:
    rows = []
    if include_ai:
        rows.append(
            [InlineKeyboardButton("✨ Polish with AI", callback_data=_CB_AI_POLISH)]
        )
    rows.append(
        [
            InlineKeyboardButton("✅ Confirm & Send", callback_data=_CB_CONFIRM),
            InlineKeyboardButton("❌ Cancel", callback_data=_CB_CANCEL),
        ]
    )
    return InlineKeyboardMarkup(rows)


async def broadcast_command(update: Update, _: ContextTypes.DEFAULT_TYPE) -> int:
    if update.effective_user.id != config.ADMIN_USER_ID:
        return ConversationHandler.END

    await update.message.reply_text(
        "📢 *Admin Broadcast*\n\n"
        "Send the message you want to broadcast to all users.\n"
        "You can use Markdown formatting.\n\n"
        "Type /cancel to abort.",
        parse_mode=ParseMode.MARKDOWN,
    )
    return GET_MESSAGE


async def handle_broadcast_message(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> int:
    context.user_data["broadcast_message"] = update.message.text

    await update.message.reply_text(
        "📝 *Preview of your message:*", parse_mode=ParseMode.MARKDOWN
    )

    try:
        await update.message.reply_text(
            update.message.text, parse_mode=ParseMode.MARKDOWN
        )
    except Exception as e:
        await update.message.reply_text(
            f"❌ *Formatting Error*\n\nInvalid Markdown: `{e}`\n\nFix it and resend, or type /cancel.",
            parse_mode=ParseMode.MARKDOWN,
        )
        return GET_MESSAGE

    await update.message.reply_text(
        "⚠️ *Send this to ALL users?*",
        reply_markup=_confirm_keyboard(include_ai=bool(config.GEMINI_API_KEY)),
        parse_mode=ParseMode.MARKDOWN,
    )
    return CONFIRM


async def handle_broadcast_callback(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> int:
    query = update.callback_query
    await query.answer()

    if query.data == _CB_CANCEL:
        await query.edit_message_text("❌ Broadcast cancelled.")
        context.user_data.pop("broadcast_message", None)
        return ConversationHandler.END

    message = context.user_data.get("broadcast_message")
    if not message:
        await query.edit_message_text("❌ Error: No message found.")
        return ConversationHandler.END

    if query.data == _CB_AI_POLISH:
        await query.edit_message_text(
            "✨ *Polishing with AI...*", parse_mode=ParseMode.MARKDOWN
        )
        try:
            polished = await ai_client.polish_broadcast(message, context.bot.username)
        except Exception as e:
            logger.error("Error polishing broadcast: %s", e)
            polished = None

        if polished:
            context.user_data["broadcast_message"] = polished
            await query.edit_message_text(
                "✨ *AI Polished Preview:*", parse_mode=ParseMode.MARKDOWN
            )
            try:
                await query.message.reply_text(polished, parse_mode=ParseMode.HTML)
            except Exception:
                await query.message.reply_text(polished)
        else:
            await query.message.reply_text(
                "❌ AI polishing failed. You can still send the original."
            )

        await query.message.reply_text(
            "⚠️ *Send this to ALL users?*",
            reply_markup=_confirm_keyboard(),
            parse_mode=ParseMode.MARKDOWN,
        )
        return CONFIRM

    # _CB_CONFIRM
    await query.edit_message_text("🚀 *Broadcasting...*", parse_mode=ParseMode.MARKDOWN)

    user_ids = db.get_all_user_ids()
    success = failed = 0
    for uid in user_ids:
        try:
            await context.bot.send_message(
                chat_id=uid, text=message, parse_mode=ParseMode.HTML
            )
            success += 1
        except Exception as e:
            logger.error("Failed to send broadcast to %s: %s", uid, e)
            failed += 1

    await query.edit_message_text(
        f"✅ *Broadcast Complete*\n\n"
        f"• Total: {len(user_ids)}\n"
        f"• Sent: {success}\n"
        f"• Failed: {failed}",
        parse_mode=ParseMode.MARKDOWN,
    )
    context.user_data.pop("broadcast_message", None)
    return ConversationHandler.END


async def cancel_broadcast(update: Update, _: ContextTypes.DEFAULT_TYPE) -> int:
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
