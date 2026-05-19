import logging

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import CallbackQueryHandler, ContextTypes

from database import db

logger = logging.getLogger(__name__)

_CONFIRM_YES = "stop|confirm"
_CONFIRM_NO = "stop|cancel"


async def stop_command(update: Update, _: ContextTypes.DEFAULT_TYPE) -> None:
    keyboard = [
        [
            InlineKeyboardButton("✅ Yes, delete my data", callback_data=_CONFIRM_YES),
            InlineKeyboardButton("❌ Cancel", callback_data=_CONFIRM_NO),
        ]
    ]
    await update.message.reply_text(
        "⚠️ *Are you sure?*\n\n"
        "This will remove your account and untrack all repositories. "
        "This action cannot be undone.",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="Markdown",
    )


async def handle_stop_callback(update: Update, _: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()

    if query.data == _CONFIRM_YES:
        user_id = update.effective_user.id
        db.delete_user(user_id)
        logger.info("User %s deleted their account.", user_id)
        await query.edit_message_text(
            "✅ Your data has been deleted. Goodbye!\n\n"
            "You can always start fresh with /start."
        )
    else:
        await query.edit_message_text("Deletion cancelled. You're still registered.")


stop_callback_handler = CallbackQueryHandler(handle_stop_callback, pattern=r"^stop\|")
