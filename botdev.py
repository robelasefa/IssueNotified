from collections import Counter
from pathlib import Path
import datetime
import time
import json
import re
import logging

import telegram.error

class BotDeveloper:
    """A sample BotDeveloper class."""
    def __init__(self, updater):
        self.updater = updater
        self.invalid_inputs = 0
        self.active_users = []
        self.repo_owners = []
        self.timePath = Path('last_notification_time.txt')

        # Enable logging
        logging.basicConfig(
            filename='botdev.log', format='%(asctime)s:%(name)s:%(levelname)s:  %(message)s', level=logging.DEBUG
            )
        self.logger = logging.getLogger(__name__)

    def _read_last_notification_time(self):
        if self.timePath.exists():
            self.last_time = int(self.timePath.read_text().strip())
        else:
            self.last_time = 0
        return self.last_time
    
    def _write_last_notification_time(self, timestamp):
        self.timePath.write_text(str(timestamp))

    def _parse_timestamp(self, timestamp):
        self.formatted_time = datetime.datetime.fromtimestamp(timestamp).strftime("%b %d, %Y %H:%M")
        return self.formatted_time
    
    def _read_number_of_users(self):
        with open("user_data.json", "r") as file:
            userData = json.load(file)
            users = len(userData)
        return users
    
    def _read_number_of_issues(self):
        with open("old_issue.json", "r") as file:
            oldIssue = json.load(file)
            issues = len(oldIssue)
        return issues

    def _orgranize_bot_info(self, last_time, users, issues):
        """Organize the bot activity informations in a way to be sent to the developer."""
        self.counted_users = Counter(self.active_users)
        self.counted_owners = Counter(self.repo_owners)
        self.top_5_users = self.counted_users.most_common(5)
        self.top_5_owners = self.counted_owners.most_common(5)

        BOT_EMOJI = '\U0001F916'
        msgTitle = f"\t{BOT_EMOJI} Here is the Bot Usage Report since {last_time}:\n\n"
        msgA = f"Number of bot users:\t\t{users}\n"
        msgB = f"Number of successful issues:\t\t{issues}\n"
        msgC = f"Number of invalid inputs:\t\t{self.invalid_inputs}\n"

        if len(self.active_users) >= 5:
            msgD = "Top 5 most active bot users:\n"
            for user in self.top_5_users:
                msgD += "  Name: {}\t\tUsage: {}\n".format(user[0], user[1])
        else:
            msgD = '---\n'
        if len(self.repo_owners) >= 5:
            msgE = "Top 5 most popular repository owners:\n"
            for owner in self.top_5_owners:
                msgE += "  Name: {}\t\tAsked: {}\n".format(owner[0], owner[1])
        else:
            msgE = '---\n'

        composedMessage = msgTitle + msgA + msgB + msgC + msgD + msgE
        return composedMessage
        
    def send_botInfo_to_dev(self, developer_id):
        """Send a notification about the bot activity to the bot developer."""
        ONE_HOUR = 3600
        TWELVE_HOURS = 12 * ONE_HOUR
        current_time = int(time.time())
        last_time = self._read_last_notification_time()
        formatted_time = self._parse_timestamp(last_time)
        number_of_users = self._read_number_of_users()
        number_of_issues = self._read_number_of_issues()

        if current_time - last_time >= TWELVE_HOURS:
            composedMessage = self._orgranize_bot_info(formatted_time, number_of_users, number_of_issues)
            devMsg = composedMessage
            self._write_last_notification_time(current_time)
        else:
            # Do some math to calculate the time until the next report is available
            time_diff = TWELVE_HOURS - (current_time - last_time)
            hours_left =  time_diff // ONE_HOUR
            minutes_left = (time_diff % ONE_HOUR) // 60
            HI_EMOJI = "\U0001F44B"
            untimedRequest = f"""
{HI_EMOJI} Hi Coder!
             
It looks like you've requested a report less than 12 hours ago.
Please come back in {hours_left} hours and {minutes_left} minutes to check for a new report."""
            devMsg = untimedRequest

        self.updater.bot.send_message(chat_id=developer_id, text=devMsg)
    
    def send_feedbacks_to_dev(self, feedbackList, developer_id):
        """Send feedbacks from bot users to bot developer."""
        feedbackMsg = f"You have a new feedback from {feedbackList[0]}:"
        feedbackMsg += f"\n\n{feedbackList[1]}"
        
        self.updater.bot.send_message(chat_id=developer_id, text=feedbackMsg)

    def new_features(self, InfoMsg):
        """Notify users about the improvements made to the bot."""
        with open("user_data.json", "r+") as file:
            userData = json.load(file)

            for user in userData:
                try:
                    self.updater.bot.send_message(chat_id=user["user_id"], text=InfoMsg)
                except (telegram.error.BadRequest, Exception) as e:
                    if 'bot was blocked by the user' in str(e):
                        self.logger.info(f"User {user['user_id']} has blocked the bot.")
                    elif 'user is deactivated' in str(e):
                        self.logger.info(f"User {user['user_id']} has deleted their account.")
                    else:
                        self.logger.info(f"Unable to reach {user['user_id']} with bot update messages: {e}")
                    userData.remove(user)   # Remove the user's information from the database.

            file.seek(0)
            json.dump(userData, file, indent=4)
            file.truncate()