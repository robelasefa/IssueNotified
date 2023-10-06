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
import datetime
import re
import threading
import logging
from telegram.ext import Updater, CommandHandler, MessageHandler, ConversationHandler, CallbackQueryHandler, Filters
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
import telegram.error

# Enable logging
logging.basicConfig(filename='botmain.log', format='%(asctime)s:%(name)s:%(levelname)s:  %(message)s', level=logging.DEBUG)
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

class BotException(Exception):
    """A bot exception class to indicate error when something went wrong."""
    pass

def notify_new_features(update_message):
    """Check for bot new features and send messages only once."""
    is_sent = True
    if is_sent:
        dev.new_features(update_message)
        is_sent = False

def load_data(filename, mode='r'):
    """Load the file in the specified filepath and return it."""
    with filename.open(mode) as file:
        return json.load(file)
    
def save_data(filename, data, indent=4, mode='w'):
    """Write the updated data back to the file."""
    with filename.open(mode) as file:
        json.dump(data, file, indent=indent)

def old_issue(issue_id):
    """Delete the reported or old issue."""
    oldIssue = load_data(oldIssuePath)
    oldIssue.append(issue_id)
    save_data(oldIssuePath, oldIssue, indent=2)

def checked_issue(issue_id):
    """Verify that the issue has not already been reported."""
    oldIssue = load_data(oldIssuePath)
    if not issue_id in oldIssue:
        return True
    return False

def remove_repo(user_id, repoDict):
    """Delete the invalid repository."""
    userData = load_data(userDataPath)
    for user in userData:
        if user['user_id'] == user_id:
            user['data'].remove(repoDict)
            if not user['data']:   # Verify whether the user has any repositories for tracking future issues
                userData.remove(user)

    save_data(userDataPath, userData)

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
                issue_tags = issue['issue']['labels']
                issue_description = issue['issue']['body']
                issue_assignee = issue['issue']['assignees'][0]['login'] if issue['issue']['assignees'] else None
                issue_created_at = issue['created_at']
                
                release_time = datetime.datetime.strptime(issue_created_at, "%Y-%m-%dT%H:%M:%SZ")
                now = datetime.datetime.now()  # Get the current time
                time_difference = now - release_time  # Calculate the time difference between the issue creation time and the current time
                
                if time_difference.days > 0:  # If the time difference is greater than 1 day, format the time difference as a string
                    if time_difference == 1:
                        time_difference_string = f"a day ago"
                    else:
                        time_difference_string = f"{time_difference.days} days ago"
                else:
                    time_difference_string = ""

                release_time_string = release_time.strftime('%Y-%m-%d %H:%M %p')
                if time_difference_string:
                    release_time_message = f"\nTime released: {release_time_string} ({time_difference_string})\n"
                else:
                   release_time_message = f"\nTime released: {release_time_string}\n"

                issue_tags_strings = []
                for issue_tag in issue_tags:
                    issue_tags_strings.append(issue_tag['name'])
                
                try:
                    if checked_issue(issue_id):
                        issue_url_button = InlineKeyboardButton(text='View Issue', url=issue_url)  # Define an InlineKeyboardButton object for the button
                        reply_markup = InlineKeyboardMarkup([[issue_url_button]])  # Create an InlineKeyboardMarkup object for the issue url

                        BELL_EMOJI = '\U0001F514'
                        issue_str = f"{BELL_EMOJI}New issue on {repo_name.capitalize()} \
                                    \n-------------------------------------- \
                                    \n\n{issue_title}\n"
                        if issue_tags:
                            issue_str += f"\nTags: {', '.join(issue_tags_strings)}\n"
                            
                        if issue_description:
                            issue_str += f"\nDescription:\n{issue_description}\n"

                        if issue_assignee:
                            issue_str += f"\nAssignee: {issue_assignee}\n"

                        issue_str += release_time_message

                        old_issue(issue_id)
                        dev.repo_owners.append(repo_owner)
                        return issue_str, reply_markup
                    else:
                        raise BotException("This issue isn't new.")
                except BotException:
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
    user_id = update.effective_user.id
    user_input = update.message.text
    pattern = r'^[a-zA-Z0-9_-]+,\s[a-zA-Z0-9_-]+$'

    if user_id in sensitives.DEVELOPERS.values() and update.message.text == sensitives.COMMUNICATION_CODE:
        dev.send_botInfo_to_dev(user_id)
    else:
        if re.match(pattern, user_input):
            repo_owner, repo_name = user_input.split(", ")
            userData = load_data(userDataPath)

            if not userData or user_id not in [user["user_id"] for user in userData]:
                add_user(user_id, repo_name, repo_owner, userData)
                dev.active_users.append(update.effective_user.first_name)
            else:
                add_repo(user_id, repo_name, repo_owner, userData)
                dev.active_users.append(update.effective_user.first_name)

            save_data(userDataPath, userData)
            msg = "Your repo has been saved!"
        else:
            msg = "Something went wrong. Please try again."
        update.message.reply_text(msg)
    return ConversationHandler.END

def get_current_repos(user_id):
    """Retrieve the user's repositories from the database."""
    userData = load_data(userDataPath)    
    repoDictList = next((user['data'] for user in userData if user['user_id'] == user_id), None)
    if repoDictList is not None:
        return [repo for repoDict in repoDictList for repo in repoDict.values()]
    return None

def get_inline_keyboard(repos):
    """Create the inline keyboard markup with user's repositories and send it to the user."""
    CROSS_MARK_EMOJI = chr(0x274C)
    repo_buttons = []
    for repo in repos:
        repo_button = InlineKeyboardButton(text=repo, callback_data=repo)
        repo_buttons.append([repo_button])

    cancel_button = InlineKeyboardButton(text='Cancel', callback_data='cancel')
    remove_all_button = InlineKeyboardButton(text=f'{CROSS_MARK_EMOJI} Remove all', callback_data='remove_all')
    repo_buttons.append([cancel_button, remove_all_button])
    
    keyboard = InlineKeyboardMarkup(repo_buttons)
    return keyboard
    
def prompt_repo_to_untrack(update, context):
    """Prompts user to select a repository to cease tracking."""
    user_id = update.effective_user.id
    repos = get_current_repos(user_id)
    if repos:
        keyboard = get_inline_keyboard(repos)
        update.message.reply_text(text='Which repository do you want to untrack?', reply_markup=keyboard)
    else:
        update.message.reply_text('You have no repositories to stop receiving notifications from.')

def untrack_repo(user_id, repo):
    """Remove the specified repository from the user's list in the database."""
    userData = load_data(userDataPath)
    for user in userData:
        if user['user_id'] == user_id:
            for Dict in user['data']:  # Remove the specified repository from the user's tracking list.
                if repo in Dict.values():
                    repoDict = Dict
                    user['data'].remove(repoDict)
                    break         
            if not user['data']:  # Verify whether the user has any repositories for tracking future issues.
                userData.remove(user)

    save_data(userDataPath, userData)

def untrack_all_repos(user_id):
    """Delete all repositories from tracking list."""
    userData = load_data(userDataPath)

    # Remove the user's information from the database.
    for user in userData:
        if user['user_id'] == user_id:
            userData.remove(user)
            
    save_data(userDataPath, userData)

def untrack_buttons_callback(update, context):
    query = update.callback_query
    user_id = update.effective_user.id
    
    all_repo_removed_msg = "All clear! You have now untracked all of your repositories."
    operation_cancelled_msg = 'Cancelled'

    if query.data == "cancel":
        query.edit_message_text(text=operation_cancelled_msg, reply_markup=None)
    elif query.data == "remove_all":
        untrack_all_repos(user_id)
        query.edit_message_text(text=all_repo_removed_msg, reply_markup=None)
    else:
        untrack_repo(user_id, query.data)
        repos = get_current_repos(user_id)
        repo_removed_msg = f'The repository {query.data} has been removed from your tracking list.'
        if repos:
            keyboard = get_inline_keyboard(get_current_repos(user_id))
            query.edit_message_text(text='Which repository do you want to untrack?', reply_markup=keyboard)
            updater.bot.send_message(chat_id=user_id, text=repo_removed_msg)
        else:
            query.edit_message_text(text=repo_removed_msg, reply_markup=None)    

def list_repos(update, context):
    """Show the repositories the user has subscribed to."""
    user_id = update.effective_user.id
    userData = load_data(userDataPath)

    if user_id not in [user["user_id"] for user in userData] or not [user['data'] for user in userData if user['user_id'] == user_id]:
        msg = "Your repository list is empty."

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
    username =  update.effective_user.username
    first_name = update.effective_user.first_name
    DEVELOPER_ID = sensitives.DEVELOPERS["DEVELOPER_ROBEL_ID"]

    name = username if username else first_name
    feedback = update.message.text

    update.message.reply_text("Thank you for taking time to share your thoughts with us!")
    dev.send_feedbacks_to_dev([name, feedback], DEVELOPER_ID)
    return ConversationHandler.END

def handle_error(update, context):
    """Handles errors that occur during the bot's runtime."""
    logger.error(context.error, exc_info=True)

    DEVELOPER_ID = sensitives.DEVELOPERS["DEVELOPER_ROBEL_ID"]

    # Send a notification message to the bot's developer about the error.
    updater.bot.send_message(chat_id=DEVELOPER_ID, text='An error occurred in the IssueNotified bot: \n{}'.format(context.error))

def send_notification():
    """Sends a notification to the user if there are any new issues in the repo."""
    userData = load_data(userDataPath)

    if userData:
        iterableData = [(owner, repo, user['user_id']) for user in userData for repoDict in user['data'] for owner, repo in repoDict.items()]
        for items in iterableData:
            new_issue, reply_markup = get_issues(items[0], items[1])
            try:
                if new_issue is None:
                    noRepoFound = f"There is no repository called '{items[1]}' under the ownership of '{items[0]}'."
                    updater.bot.send_message(chat_id=items[2], text=noRepoFound)
                    remove_repo(items[2], {items[0]: items[1]})
                    dev.invalid_inputs += 1
                else:
                    updater.bot.send_message(chat_id=items[2], text=new_issue, reply_markup=reply_markup, disable_web_page_preview=True, disable_notification=False)
            except telegram.error.BadRequest as e:  # Remove the user's information from the database.
                    if 'bot was blocked by the user' in str(e):
                        untrack_all_repos(items[2])
                        logger.info(f"User {items[2]} has blocked the bot.")
                    elif 'user is deactivated' in str(e):
                        untrack_all_repos(items[2])
                        logger.info(f"User {items[2]} has deleted their account.")
                    else:
                        untrack_all_repos(items[2])   
                        raise BotException("\n\tSomething went wrong with the user'S account.")  # The exceptions is not BadRequest, raise a general exception
            except BotException as e:
                 logger.info(f"Failure to deliver messages to user {items[2]}: {e}")
            
def cancel():
    """Conclude the conversation."""
    pass  # Do nothing

def main():
    # notify_new_features(sensitives.MESSAGE3)  # Send bot improvement messesages ONLY ONCE

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
    disp.add_error_handler(handle_error)

    timer = threading.Timer(15 * 60, send_notification)  # Notify users every 15 minutes
    timer.start()

    updater.start_polling()  # Run the bot
    updater.idle()

if __name__ == "__main__":
    main()