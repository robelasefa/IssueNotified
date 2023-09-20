from telegram import InlineKeyboardButton, InlineKeyboardMarkup
userDataPath = None
updater = None
import json
import re

def prompt_repo_to_untrack(update, context):
    """Prompts the user to select a repository to cease tracking."""
    CROSS_MARK_EMOJI = chr(0x274C)
    user_id = update.message.from_user.id

    with userDataPath.open(mode='r') as file:
        userData = json.load(file)
        repoDictList = next((user['data'] for user in userData if user['user_id'] == user_id), None)

        if repoDictList is not None:
            repoList = [repo for repoDict in repoDictList for repo in repoDict.values()]
            untracking_inline_keyboard = []  # Create a list of inline buttons, one button for each repository in the user's tracking list.
            
            for repo in repoList:
                untracking_inline_keyboard.append([InlineKeyboardButton(text=repo, callback_data='untrack_repo:' + repo)])
            untracking_inline_keyboard.append([InlineKeyboardButton(text=f'{CROSS_MARK_EMOJI} Remove all', callback_data='untrack_all_repo')])

            # Send a message to the user with the list of inline buttons.
            update.message.reply_text(text='Which repository do you want to untrack?', reply_markup=InlineKeyboardMarkup(untracking_inline_keyboard))
        else:
            update.message.reply_text("You have no repositories to stop receiving notifications from.")



def untrack(update, context):
    """Remove the repository the user wants to cease tracking."""
    user_id = update.callback_query.from_user.id
    repo_name = update.callback_query.data.split(':')[1]  # Get the repository name from the callback data.

    with userDataPath.open(mode='r+') as file:
        userData = json.load(file)
        repoDictList = [user['data'] for user in userData if user['user_id'] == user_id]

        for Dict in repoDictList:
            if repo_name in Dict.values():
                repoDict = Dict
                break
        repoDictList.remove(repoDict)
        
        if not repoDictList:  # Verify whether the user has any repositories for tracking future issues, and if not, delete the user's information from the database.
            for user in userData:
                if user['user_id'] == user_id:
                    userData.remove(user)

        file.seek(0)  # Move the file pointer to the beginning of the file
        json.dump(userData, file, indent=4)  # Write the updated data back to the file
        file.truncate()  # Truncate any remaining content in the file

    # Send a message to the user confirming that the repository has been removed from their tracking list.
    updater.bot.send_message(chat_id=user_id, text='The repository {} has been removed from your tracking list.'.format(repo_name))

def untrack_all(update, context):
    """Delete all repositories from tracking list."""
    user_id = update.callback_query.from_user.id
    with userDataPath.open(mode='r+') as file:
        userData = json.load(file)

        for user in userData: # Remove user from the database, since they have no any remaining repository to keep notifying them. 
            if user['user_id'] == user_id:
                userData.remove(user)

        file.seek(0)  # Move the file pointer to the beginning of the file
        json.dump(userData, file, indent=4)  # Write the updated data back to the file
        file.truncate()  # Truncate any remaining content in the file

    updater.bot.send_message(chat_id=user_id, text="All clear! You have now untracked all of your repositories." )

# disp.add_handler(CallbackQueryHandler(untrack, pattern='untrack'))

# def confirm_untrack(update, context):
#     """Handler function for confirmationnof untracking."""
#     user_id = update.effective_user.id
#     repo = context.user_data['repo']

#     update.message.reply_text("Are you sure you want to untrack {}".format(repo))
