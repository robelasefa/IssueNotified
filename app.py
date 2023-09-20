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

# Check for bot new features and send messages only once
is_sent = True
if is_sent:
    dev.new_features(sensitives.MESSAGE1)
    is_sent = False

class botExceptions(Exception):
    """A bot exception class to indicate error when something went wrong."""
    pass

def start(update, context):
    """Send an introductory message when the user issues the /start command."""
    user = update.message.from_user.first_name
    WAVING_HAND_EMOJI = '\U0001F44B'
    PARTY_POPPER_EMOJI = '\U0001F389'
    welcome_msg =  f"""{WAVING_HAND_EMOJI}Hi {user}! Welcome to IssueNotified bot! {PARTY_POPPER_EMOJI}
    \n\nWe are excited to have you join us on this journey with IssueNotified bot, your personal assistant for GitHub repositories.
With our stunning and timely notifications, you'll always be the first to know about any new issues.
Just type /track and let us take care of the rest."""
    update.message.reply_text(welcome_msg)

def oldIssue(issue_id):
    """Delete the reported or old issue."""
    with oldIssuePath.open(mode='r') as file:
        oldIssue = json.load(file)
        oldIssue.append(issue_id)

    with open(oldIssuePath, "w") as file:
        json.dump(oldIssue, file, indent=2)

def checkedIssue(issue_id):
    """Verify that the issue has not already been reported."""
    with oldIssuePath.open(mode='r') as file:
        oldIssue = json.load(file)
        if not issue_id in oldIssue:
            return True
        return False

def add_repo(user_id, new_repo, userData):
    """Add a repository to an existing user's tracked repositories."""
    for user in userData:
        if user["user_id"] == user_id and not new_repo in user["data"]:
            user["data"].append(new_repo)

def remove_repo(user_id, repoDict):
    """Delete the invalid repository."""
    with userDataPath.open(mode='r+') as file:
        userData = json.load(file)
        for user in userData:
            if user['user_id'] == user_id:
                user['data'].remove(repoDict)
                if not user['data']:   # Verify whether the user has any repositories for tracking future issues
                    userData.remove(user)
        file.seek(0)  # Move the file pointer to the beginning of the file
        json.dump(userData, file, indent=4)  # Write the updated data back to the file
        file.truncate()  # Truncate any remaining content in the file
        

def get_issues(repo_owner, repo_name):
    """Gets the list of issues in the specified repository."""
    repo_url = "https://api.github.com/repos/{}/{}/issues/events".format(
            repo_owner, repo_name)
    headers = {"Authorization": "bearer {}".format(GITHUB_TOKEN)}
    response = requests.get(repo_url, headers=headers)

    if response.status_code == 200:
        canBeChecked = True
    else:
        canBeChecked = False  # Connection error
        
    if canBeChecked:
        if response is None:
            return None   # The repo entered by the user cannot be located
        else:
            issues = json.loads(response.content)
            for issue in issues:
                issue_title = issue['issue']['title']
                issue_url = issue['issue']['html_url']
                issue_id = issue['id']
                try:
                    if checkedIssue(issue_id):
                        issue_url_button = InlineKeyboardButton(text='View Issue', url=issue_url)  # Define an InlineKeyboardButton object for the button
                        reply_markup_1 = InlineKeyboardMarkup([[issue_url_button]])  # Create an InlineKeyboardMarkup object for the issue url

                        BELL_EMOJI = '\U0001F514'
                        issue_str = f"{BELL_EMOJI}New issue on {repo_name.capitalize()} \
                                    \n-------------------------------------- \
                                    \n\n{issue_title}"
                        oldIssue(issue_id)
                        dev.successful_issues += 1
                        dev.repo_owners.append(repo_owner)
                        return issue_str, reply_markup_1
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

def track(update, context):
    """Add the repository that the user wants to be notified about the latest issues."""
    global repo_owner, repo_name

    user_input = update.message.text
    user_id = update.message.from_user.id

    if user_id in sensitives.DEVELOPERS.values() and update.message.text == sensitives.COMMUNICATION_CODE:
        dev.notify_dev(user_id)
    else:
        pattern = r'^[a-zA-Z0-9_-]+,\s[a-zA-Z0-9_-]+$'
        if re.match(pattern, user_input):
            repo_owner, repo_name = user_input.split(", ")
            msg = f"Your repo has been saved!"
            is_passed = True
        else:
            msg = "Something went wrong. Please try again."
            is_passed = False
        
        if is_passed:
            new_user = {
                    "user_id": user_id,
                    "data": [{repo_owner: repo_name}]
                                }
            new_repo = {repo_owner: repo_name}

            with userDataPath.open(mode='r+') as file:
                userData = json.load(file)
                if not userData or not user_id in [user["user_id"] for user in userData]:
                    dev.active_users.append(update.message.from_user.first_name)
                    userData.append(new_user)
                else:
                    add_repo(user_id, new_repo, userData)
                    dev.active_users.append(update.message.from_user.first_name)
                file.seek(0)  # Move the file pointer to the beginning of the file
                json.dump(userData, file)  # Write the updated data back to the file
                file.truncate()  # Truncate any remaining content in the file
        update.message.reply_text(msg)
    return ConversationHandler.END

def prompt_repo_to_untrack(update, context):
    """Ask the user to provide the name and owner of the repository that they don't want to be tracked."""
    CROSS_MARK_EMOJI = chr(0x274C)
    untrack_all_button = InlineKeyboardButton(text=f'{CROSS_MARK_EMOJI} Remove all', callback_data='untrack_all_callback_data')
    reply_markup_2 = InlineKeyboardMarkup([[untrack_all_button]])

    prompt_repo_msg = "Enter the name and owner of the repository you want to terminate watching."
    update.message.reply_text(text=prompt_repo_msg, reply_markup=reply_markup_2)

    return 3 # This returns the untrack() function

def untrack(update, context):
    """Remomve the repository the user wants to cease tracking."""
    untrack_repo = update.message.text
    user_id = update.message.from_user.id

    with userDataPath.open(mode='r+') as file:
        userData = json.load(file)
        userRepos = [user['data'] for user in userData if user['user_id'] == user_id]

        pattern = r'^[a-zA-Z0-9_-]+,\s[a-zA-Z0-9_-]+$'
        
        if re.match(pattern, untrack_repo):
            repo_owner, repo_name = untrack_repo.split(", ")
            repoDict = {repo_owner: repo_name}

            if user_id not in [user["user_id"] for user in userData]:  # Check if the user is using the bot 
                msg = f"You have no repositories to stop receiving notifications from."
            elif repoDict not in userRepos:   # Check if the repository to be removed exists
                msg = f"I couldn't find a repository named '{repo_name}' that you've tracked before."
            else:
                userRepos.remove(repoDict)
                # Verify whether the user has any repositories for tracking future issues, and if not,
                #  delete the user's information from the database.
                if not userRepos:
                    for user in userData:
                        if user['user_id'] == user_id:
                            userData.remove(user)
                msg = f"Your repository has been removed from tracking."   
        else:
            msg = "Please be sure to use this format: <owner_name>, <repository_name>."
        file.seek(0)  # Move the file pointer to the beginning of the file
        json.dump(userData, file, indent=4)  # Write the updated data back to the file
        file.truncate()  # Truncate any remaining content in the file

    update.message.reply_text(msg)
    return ConversationHandler.END

def untrack_all(update, context):
    """Delete all repositories from tracking list."""
    # Get the chat ID of the user who clicked the inline button
    user_id = update.callback_query.from_user.id
    with userDataPath.open(mode='r+') as file:
        userData = json.load(file)
        if user_id not in [user["user_id"] for user in userData]:  # Check if the user is using the bot 
            deleteMsg = f"You have no repositories to stop receiving notifications from."
        else:
            for user in userData: # Remove user from the database
                if user['user_id'] == user_id:
                    userData.remove(user)
            deleteMsg = "All clear! You have now untracked all of your repositories."    
        file.seek(0)  # Move the file pointer to the beginning of the file
        json.dump(userData, file, indent=4)  # Write the updated data back to the file
        file.truncate()  # Truncate any remaining content in the file

    updater.bot.send_message(chat_id=user_id, text=deleteMsg)

def list_repos(update, context):
    """Show the repositories the user has subscribed to."""
    user_id = update.message.from_user.id
    with userDataPath.open(mode='r') as file:
        userData = json.load(file)
        if not user_id in [user["user_id"] for user in userData] or not [user['data'] for user in userData if user['user_id'] == user_id]:
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

def take_feedback(update, context):
    """"""
    update.message.reply_text("What steps can we take to enhance your interaction with our bot? \
Please share your thoughts on your stay on the bot.")
    return 2  # This returns the process_feedback() function

def process_feedback(update, context):
    """"""
    username =  update.message.from_user.username
    first_name = update.message.from_user.first_name

    name = username if username else first_name
    feedbackMsg = update.message.text
    dev.user_feedbacks.append({name, feedbackMsg})

    update.message.reply_text("Thank you for taking time to share your thoughts with us!")
    return ConversationHandler.END

def notify():
    """Sends a notification to the user if there are any new issues in the repo."""
    with userDataPath.open(mode='r') as file:
        userData = json.load(file)
        if userData:
            iterableData = [(owner, repo, user['user_id']) for user in userData for repoDict in user['data'] for owner, repo in repoDict.items()]
            for items in iterableData:
                new_issue, reply_markup_1 = get_issues(items[0], items[1])
                
                if new_issue is None:
                    noRepoFound = f"There is no repository called '{items[1]}' under the ownership of '{repo_owner}'."
                    updater.bot.send_message(chat_id=items[2], text=noRepoFound)
                    remove_repo(items[2], {items[0]: items[1]})
                    dev.invalid_inputs += 1
                else:
                    updater.bot.send_message(chat_id=items[2], text=new_issue, reply_markup=reply_markup_1, disable_web_page_preview=True)

timer = threading.Timer(15 * 60, notify)  # Notify users every 15 minutes
timer.start()

def error_handler(update, context):
    """Handles errors that occur during the bot's runtime."""
    logger.error(context.error)

    DEVELOPER_ID = sensitives.DEVELOPERS["DEVELOPER_ROBEL_ID"]

    # Send a notification message to the bot's developer about the error.
    updater.bot.send_message(chat_id=DEVELOPER_ID, text='An error occurred in the IssueNotified bot: {}'.format(context.error))

def cancel():
    """Conclude the conversation."""
    pass  # Do nothing

# This will manage the conversation to track new repository.
conv_handler1 = ConversationHandler(
    entry_points=[CommandHandler('track', prompt_repo_to_track)],
    states = {
        1: [MessageHandler(Filters.text, track)]
    },
    fallbacks=[CommandHandler('cancel', cancel)])

# This will manage the convesation to receive feedback from the user.
conv_handler2 = ConversationHandler(
    entry_points=[CommandHandler('feedback', take_feedback)],
    states = {
        2: [MessageHandler(Filters.text, process_feedback)]
    },
    fallbacks=[CommandHandler('cancel', cancel)])

# This will manage the conversation to track new repository.
conv_handler3 = ConversationHandler(
    entry_points=[CommandHandler('untrack', prompt_repo_to_untrack)],
    states = {
        3: [MessageHandler(Filters.text, untrack)]
    },
    fallbacks=[CommandHandler('cancel', cancel)])

# Command Handlers
disp.add_handler(CommandHandler("start", start))
disp.add_handler(CommandHandler("list", list_repos))

# Callback query handlers
disp.add_handler(CallbackQueryHandler(untrack_all, pattern='untrack_all_callback_data'))

# Conversational Handlers
disp.add_handler(conv_handler1)
disp.add_handler(conv_handler2)
disp.add_handler(conv_handler3)

# This handles the errors occured during the bot's runtime
disp.add_error_handler(error_handler)

updater.start_polling()
updater.idle()

