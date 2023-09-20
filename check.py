from telegram import InlineKeyboardButton, InlineKeyboardMarkup
userDataPath = None
import json

def prompt_repo_to_untrack(update, context):
    """Prompts the user to select a repository to cease tracking."""
    CROSS_MARK_EMOJI = chr(0x274C)
    user_id = update.message.from_user.id
    with userDataPath.open(mode='r') as file:
        userData = json.load(file)
        repoDictList = next((user['data'] for user in userData if user['user_id'] == user_id), None)

        if repoDictList is not None:
            untracking_inline_keyboard = []  # Create a list of inline buttons, one button for each repository in the user's tracking list.
            
            for repo in repoDictList:
                untracking_inline_keyboard.append([InlineKeyboardButton(text=repo, callback_data='untrack_repo:' + repo)])
            untrack_all_button = InlineKeyboardButton(text=f'{CROSS_MARK_EMOJI} Remove all', callback_data='untrack_all_repo')
            untracking_inline_keyboard.append([untrack_all_button])

            # Send a message to the user with the list of inline buttons.
            update.message.reply_text(text='Select the repository you want to cease tracking:', reply_markup=InlineKeyboardMarkup(untracking_inline_keyboard))
        else:
            update.message.reply_text("You have no repositories to stop receiving notifications from.")

    return 3 # This returns the untrack() function