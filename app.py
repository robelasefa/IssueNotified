"""
IssueNotified is a Telegram bot that will assist programmers by notifying them of
any modifications or changes to issues in open source projects on GitHub.

Copyright (c) 2023, Miki Asefa.

"""

import sensitives
from botdev import BotDeveloper
import requests
from pathlib import Path
import json
import re
import threading
import logging
from telegram.ext import Updater, CommandHandler, MessageHandler, ConversationHandler, CallbackQueryHandler, Filters
from telegram import InlineKeyboardButton, InlineKeyboardMarkup

# Enable logging
logging.basicConfig(level=logging.INFO, format='%(levelname)s - %(name)s - %(message)s')
logger = logging.getLogger(__name__)

TELEGRAM_TOKEN = sensitives.TELEGRAM_TOKEN
GITHUB_TOKEN = sensitives.GITHUB_TOKEN

updater = Updater(TELEGRAM_TOKEN, use_context=True)
disp = updater.dispatcher

dev = BotDeveloper(updater)

# Set up the file paths that the bot uses on local storage
userDataPath = Path("user_data.json")
oldIssuePath = Path("old_issue.json")

if not userDataPath.exists():
    with open(userDataPath, "w") as file:
        json.dump([], file, indent=4)
if not oldIssuePath.exists():
    with open(oldIssuePath, "w") as file:
        json.dump([], file, indent=2)

def start(update, context):
    """Send an introductory message when the user issues the /start command."""
    user = update.message.from_user.first_name
    WAVING_HAND_EMOJI = '\U0001F44B'
    PARTY_POPPER_EMOJI = '\U0001F389'
    welcome_msg =  f"""
{WAVING_HAND_EMOJI}Hi {user}! Welcome to IssueNotified bot! {PARTY_POPPER_EMOJI}
\n\nWe are excited to have you join us on this journey with IssueNotified bot, your personal assistant for GitHub repositories.
With our stunning and timely notifications, you'll always be the first to know about any new issues.
Just type /track and let us take care of the rest."""
    update.message.reply_text(welcome_msg)

class botExceptions(Exception):
    """A bot exception class to indicate error when something went wrong."""
    pass

def notify_new_features(update_message):
    """Check for bot new features and send messages only once."""
    is_sent = True
    if is_sent:
        dev.new_features(update_message)
        is_sent = False

def old_issue(issue_id):
    """Delete the reported or old issue."""
    with oldIssuePath.open(mode='r') as file:
        oldIssue = json.load(file)
        oldIssue.append(issue_id)

    with open(oldIssuePath, "w") as file:
        json.dump(oldIssue, file, indent=2)

def checked_issue(issue_id):
    """Verify that the issue has not already been reported."""
    with oldIssuePath.open(mode='r') as file:
        oldIssue = json.load(file)
        if not issue_id in oldIssue:
            return True
        return False

def remove_repo(user_id, repoDict):
    """Delete the invalid repository."""
    with userDataPath.open(mode='r+') as file:
        userData = json.load(file)
        for user in userData:
            if user['user_id'] == user_id:
                user['data'].remove(repoDict)
                if not user['data']:   # Verify whether the user has any repositories for tracking future issues
                    userData.remove(user)
        file.seek(0)
        json.dump(userData, file, indent=4)  # Write the updated data back to the file
        file.truncate() 

def get_issues(repo_owner, repo_name):
    """Gets the list of issues in the specified repository."""
    repo_url = "https://api.github.com/repos/{}/{}/issues/events".format(
            repo_owner, repo_name)
    headers = {"Authorization": "bearer {}".format(GITHUB_TOKEN)}
    response = requests.get(repo_url, headers=headers)

    if response.status_code == 200:
        if response is None:
            return None   # The repo entered by the user cannot be located
        else:
            issues = json.loads(response.content)
            for issue in issues:
                issue_title = issue['issue']['title']
                issue_url = issue['issue']['html_url']
                issue_id = issue['id']
                try:
                    if checked_issue(issue_id):
                        issue_url_button = InlineKeyboardButton(text='View Issue', url=issue_url)  # Define an InlineKeyboardButton object for the button
                        reply_markup = InlineKeyboardMarkup([[issue_url_button]])  # Create an InlineKeyboardMarkup object for the issue url

                        BELL_EMOJI = '\U0001F514'
                        issue_str = f"{BELL_EMOJI}New issue on {repo_name.capitalize()} \
                                    \n-------------------------------------- \
                                    \n\n{issue_title}"
                        old_issue(issue_id)
                        dev.repo_owners.append(repo_owner)
                        return issue_str, reply_markup
                    else:
                        raise botExceptions("This issue isn't new.")
                except botExceptions:
                    pass

def prompt_repo_to_track(update, context):
    """Ask the user to provide the name and owner of the repository that they want to be tracked."""
    update.message.reply_text(
        "Enter the owner and name of the repository you want to track. \
         \neg. Expensify, App"
            )
    return 1  # This returns the track() function

def add_user(user_id, repo_name, repo_owner, userData):
    new_user = {
            "user_id": user_id,
            "data": [{repo_owner: repo_name}]
        }
    userData.append(new_user)
    
def add_repo(user_id, repo_name, repo_owner, userData):
    """Add a repository to an existing user's tracked repositories."""
    new_repo = {repo_owner: repo_name}
    for user in userData:
        if user["user_id"] == user_id and new_repo not in user["data"]:
            user["data"].append(new_repo)

def track_repo(update, context):
    """Add the repository that the user wants to be notified about the latest issues."""
    user_id = update.message.from_user.id
    user_input = update.message.text
    pattern = r'^[a-zA-Z0-9_-]+,\s[a-zA-Z0-9_-]+$'

    if user_id in sensitives.DEVELOPERS.values() and update.message.text == sensitives.COMMUNICATION_CODE:
        dev.send_botInfo_to_dev(user_id)
    else:
        if re.match(pattern, user_input):
            repo_owner, repo_name = user_input.split(", ")
            with userDataPath.open(mode='r+') as file:
                userData = json.load(file)
                if not userData or user_id not in [user["user_id"] for user in userData]:
                    add_user(user_id, repo_name, repo_owner, userData)
                    dev.active_users.append(update.message.from_user.first_name)
                else:
                    add_repo(user_id, repo_name, repo_owner, userData)
                    dev.active_users.append(update.message.from_user.first_name)

                # Write the updated data back to the file
                file.seek(0)
                json.dump(userData, file, indent=4)
                file.truncate()
            msg = "Your repo has been saved!"
        else:
            msg = "Something went wrong. Please try again."
    
        update.message.reply_text(msg)
    return ConversationHandler.END

def get_current_repos(user_id):
    """Retrieve the user's repositories from the database."""
    with userDataPath.open(mode='r') as file:
        userData = json.load(file)    
        repoDictList = next((user['data'] for user in userData if user['user_id'] == user_id), None)
        if repoDictList is not None:
            return [repo for repoDict in repoDictList for repo in repoDict.values()]
        return None

def send_inline_keyboard(user_id, repos):
    """Create the inline keyboard markup with user's repositories and send it to the user."""
    CROSS_MARK_EMOJI = chr(0x274C)
    repo_buttons = [InlineKeyboardButton(text=repo, callback_data=repo) for repo in repos]
    repo_buttons.append(InlineKeyboardButton(text=f'{CROSS_MARK_EMOJI} Remove all', callback_data='remove_all'))
    keyboard = InlineKeyboardMarkup([repo_buttons])
    
    updater.bot.send_message(chat_id=user_id, text='Which repository do you want to untrack?', reply_markup=keyboard)
   
def prompt_repo_to_untrack(update, context):
    """Prompts user to select a repository to cease tracking."""
    user_id = update.message.from_user.id
    repos = get_current_repos(user_id)
    if repos:
        send_inline_keyboard(user_id, repos)
    else:
        update.message.reply_text('You have no repositories to stop receiving notifications from.')

def untrack_repo(user_id, repo):
    """Remove the specified repository from the user's list in the database."""
    with userDataPath.open(mode='r+') as file:
        userData = json.load(file)
        repoDictList = [user['data'] for user in userData if user['user_id'] == user_id]
        
        # Remove the specified repository from the user's tracking list.
        for Dict in repoDictList:
            if repo in Dict.values():
                repoDict = Dict
                break
        repoDictList.remove(repoDict)
        # Verify whether the user has any repositories for tracking future issues.
        for user in userData:
            if user['user_id'] == user_id:
                userData.remove(user)

        # Write the updated data back to the file.
        file.seek(0)
        json.dump(userData, file, indent=4)
        file.truncate()

def untrack_all_repos(user_id):
    """Delete all repositories from tracking list."""
    with userDataPath.open(mode='r+') as file:
        userData = json.load(file)

        # Remove the user's information from the database.
        for user in userData:
            if user['user_id'] == user_id:
                userData.remove(user)
                
        # Write the updated data back to the file.
        file.seek(0)
        json.dump(userData, file, indent=4)
        file.truncate()

def untrack_buttons_callback(update, context):
    query = update.callback_query
    user_id = query.from_user.id
    if query.data == "remove_all":
        untrack_all_repos(user_id)
        query.edit_message_reply_markup(reply_markup=InlineKeyboardMarkup([]))
        updater.bot.send_message(chat_id=user_id, text="All clear! You have now untracked all of your repositories.")
    else:
        untrack_repo(user_id, query.data)
        query.edit_message_reply_markup(reply_markup=InlineKeyboardMarkup([]))
        updater.bot.send_message(chat_id=user_id, text=f'The repository {query.data} has been removed from your tracking list.')

def list_repos(update, context):
    """Show the repositories the user has subscribed to."""
    user_id = update.message.from_user.id
    with userDataPath.open(mode='r') as file:
        userData = json.load(file)
        if user_id not in [user["user_id"] for user in userData] or not [user['data'] for user in userData if user['user_id'] == user_id]:
            msg = f"Your repository list is empty."
        else:
            msg = 'Owner\t\t\t\t\t\t\tRepository'
            repoDictList = next((user['data'] for user in userData if user['user_id'] == user_id), None)
            if repoDictList is not None:
                counter = 1
                for repoDict in repoDictList:
                    for owner, repo in repoDict.items():
                        msg += f"\n{counter}. {owner}\t\t\t\t\t\t\t{repo}"
                        counter += 1
            else:
                msg = "Something went wrong. Please try again."
        update.message.reply_text(msg)

def prompt_feedback(update, context):
    """Prompt user to enter their feedback."""
    update.message.reply_text("What steps can we take to enhance your interaction with our bot? \
Please share your thoughts on your stay on the bot.")
    return 2  # This returns the process_feedback() function

def process_feedback(update, context):
    """Retrieve the user's feedback and send it to bot dev."""
    username =  update.message.from_user.username
    first_name = update.message.from_user.first_name

    name = username if username else first_name
    feedback = update.message.text

    DEVELOPER_ID = sensitives.DEVELOPERS["DEVELOPER_ROBEL_ID"]
    dev.send_feedbacks_to_dev([name, feedback], DEVELOPER_ID)

    update.message.reply_text("Thank you for taking time to share your thoughts with us!")
    return ConversationHandler.END

def error_handler(update, context):
    """Handles errors that occur during the bot's runtime."""
    logger.error(context.error, exc_info=True)

    DEVELOPER_ID = sensitives.DEVELOPERS["DEVELOPER_ROBEL_ID"]

    # Send a notification message to the bot's developer about the error.
    updater.bot.send_message(chat_id=DEVELOPER_ID, text='An error occurred in the IssueNotified bot: {}'.format(context.error))

def send_notification():
    """Sends a notification to the user if there are any new issues in the repo."""
    with userDataPath.open(mode='r') as file:
        userData = json.load(file)
        if userData:
            iterableData = [(owner, repo, user['user_id']) for user in userData for repoDict in user['data'] for owner, repo in repoDict.items()]
            for items in iterableData:
                new_issue, reply_markup = get_issues(items[0], items[1])
                
                if new_issue is None:
                    noRepoFound = f"There is no repository called '{items[1]}' under the ownership of '{items[0]}'."
                    updater.bot.send_message(chat_id=items[2], text=noRepoFound)
                    remove_repo(items[2], {items[0]: items[1]})
                    dev.invalid_inputs += 1
                else:
                    updater.bot.send_message(chat_id=items[2], text=new_issue, reply_markup=reply_markup, disable_web_page_preview=True)

def cancel():
    """Conclude the conversation."""
    pass  # Do nothing

def main():
    # notify_new_features(sensitives.MESSAGE2)  # Send bot improvement messesages ONLY ONCE

    # This will manage the conversation to track new repository.
    conv_handler1 = ConversationHandler(
        entry_points=[CommandHandler('track', prompt_repo_to_track)],
        states = {
            1: [MessageHandler(Filters.text, track_repo)]
        },
        fallbacks=[CommandHandler('cancel', cancel)])

    # This will manage the convesation to receive feedback from the user.
    conv_handler2 = ConversationHandler(
        entry_points=[CommandHandler('feedback', prompt_feedback)],
        states = {
            2: [MessageHandler(Filters.text, process_feedback)]
        },
        fallbacks=[CommandHandler('cancel', cancel)])

    # Command Handlers
    disp.add_handler(CommandHandler("start", start))
    disp.add_handler(CommandHandler("list", list_repos))
    disp.add_handler(CommandHandler("untrack", prompt_repo_to_untrack))

    # Callback query handler
    disp.add_handler(CallbackQueryHandler(untrack_buttons_callback))

    # Conversational Handlers
    disp.add_handler(conv_handler1)
    disp.add_handler(conv_handler2)

    # Error Handler
    disp.add_error_handler(error_handler)

    timer = threading.Timer(15 * 60, send_notification)  # Notify users every 15 minutes
    timer.start()

    updater.start_polling()  # Run the bot
    updater.idle()

if __name__ == "__main__":
    main()