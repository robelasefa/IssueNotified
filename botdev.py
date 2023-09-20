from collections import Counter
from pathlib import Path
from datetime import datetime
import time
import json
import sqlite3

class BotDeveloper:
    """A sample BotDeveloper class."""
    def __init__(self, updater):
        self.updater = updater
        self.successful_issues = 0
        self.invalid_inputs = 0
        self.active_users = []
        self.repo_owners = []
        self.user_feedbacks = []
        self.timePath = Path('last_notification_time.txt')
        self.conn = sqlite3.connect("users.db")
        self.cur = self.conn.cursor()

    def _read_last_notification_time(self):
        if self.timePath.exists():
            self.last_time = int(self.timePath.read_text().strip())
        else:
            self.last_time = 0
        return self.last_time
    
    def _write_last_notification_time(self, timestamp):
        self.timePath.write_text(str(timestamp))

    def _parse_timestamp(self, timestamp):
        self.formatted_time = datetime.fromtimestamp(timestamp).strftime("%b %d, %Y %H:%M")
        return self.formatted_time

    def _orgranize_bot_info(self, last_time, users):
        """"""
        self.counted_users = Counter(self.active_users)
        self.counted_owners = Counter(self.repo_owners)
        self.top_5_users = self.counted_users.most_common(5)
        self.top_5_owners = self.counted_owners.most_common(5)

        BOT_EMOJI = '\U0001F916'
        msgTitle = f"\t{BOT_EMOJI} Here is the Bot Usage Report since {last_time}:\n\n"
        msgA = f"Number of bot users:\t\t{users}\n"
        msgB = f"Number of successful issues:\t\t{self.successful_issues}\n"
        msgC = f"Number of invalid inputs:\t\t{self.invalid_inputs}\n"

        if len(self.top_5_users) >= 5:
            msgD = "Top 5 most active bot users:\n"
            for user in self.top_5_users:
                msgD += "  Name: {}\t\tUsage: {}\n".format(user[0], user[1])
        else:
            msgD = '---\n'
        if len(self.top_5_owners) >= 5:
            msgE = "Top 5 most popular repository owners:\n"
            for owner in self.top_5_owners:
                msgE += "  Name: {}\t\tAsked: {}\n".format(owner[0], owner[1])
        else:
            msgE = '---\n'
        if self.user_feedbacks:
            msgF = f"You have {len(self.user_feedbacks)} new user feedbacks:"  # This last message has not \n.
            for feedback in self.user_feedbacks:
                if type(feedback) is set:
                    feedback = dict(enumerate(feedback))  # Convert the set object to a dictionary object
                    # with integer keys, assuming that there has been some error regarding the name of the user .            
                for userName, feedbackMsg in feedback.items():
                    msgF += f"{userName}: \n\t'{feedbackMsg}'"
        else:
            msgF = '---'
        
        composedMessage = msgTitle + msgA + msgB + msgC + msgD + msgE + msgF
        return composedMessage
        
    def notify_developer(self, developer_id):
        ONE_HOUR = 3600
        TWELVE_HOURS = 12 * ONE_HOUR
        with open("user_data.json", "r") as file:
            userData = json.load(file)
            users = len(userData)
        last_time = self._read_last_notification_time()
        composedMessage = self._orgranize_bot_info(self._parse_timestamp(last_time), users)
        current_time = int(time.time())

        if current_time - last_time >= TWELVE_HOURS:  # Notify once per 12 hour
            devMsg = composedMessage
            self._write_last_notification_time(current_time)
        else:
            # Do some math to calculate the time until the next report is available
            time_diff = TWELVE_HOURS - (current_time - last_time)
            hours_left =  time_diff // ONE_HOUR
            minutes_left = (time_diff % ONE_HOUR) // 60
            HI_EMOJI = "\U0001F44B"
            untimedMessage = f"""{HI_EMOJI} Hi Coder!
             \nIt looks like you've requested a report less than 12 hours ago. \
Please come back in {hours_left} hours {minutes_left} minutes to check for a new report."""
            devMsg = untimedMessage

        self.updater.bot.send_message(chat_id=developer_id, text=devMsg)
        self.user_feedbacks.clear()  # Clear the list after submitting the new feedback

    def new_features(self, InfoMsg):
        """Notify users about the improvement made to the bot."""
        with open("user_data.json", "r") as file:
            userData = json.load(file)

        for user in userData:
           self.updater.bot.send_message(chat_id=user["user_id"], text=InfoMsg)
    
    # def database(self):
        #         # Update the database to indicate that the message has been sent to all users
        # self.cur.execute("UPDATE users SET message_sent = 1 WHERE message_sent = 0")

        # # Insert the user IDs into the database(if it doesn't exists already)
        # for user in user_data:
        #     self.cur.execute("INSERT OR IGNORE INTO users (user_id) VALUES (?)", (user["user_id"],))

        # # Get all users who have not yet received the message
        # self.cur.execute("SELECT user_id FROM messages WHERE message_sent = 0")
        # users = self.cur.fetchall()

        # # Loop through the users and send the message
        # 

        # # Commit the changes
        # self.conn.commit()

    #     self._create_table()

    # def _create_table(self):
    #     """Create a database table to record user ID and message sent status."""
    #     # Create the database table if it doesn't exist
    #     self.cur.execute("""CREATE TABLE IF NOT EXISTS messages (
    #         user_id INT,
    #         message_sent INT DEFAULT 0);""")

    
