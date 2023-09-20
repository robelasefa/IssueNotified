        # self.conn = sqlite3.connect("users.db")
        # self.cur = self.conn.cursor()
 # def database(self):

    # # Insert the user IDs into the database(if it doesn't exists already)
    # for user in user_data:
    #     self.cur.execute("INSERT OR IGNORE INTO users (user_id) VALUES (?)", (user["user_id"],))

    # # Get all users who have not yet received the message
    # self.cur.execute("SELECT user_id FROM messages WHERE message_sent = 0")
    # users = self.cur.fetchall()

    # # Update the database to indicate that the message has been sent to all users
    # self.cur.execute("UPDATE users SET message_sent = 1 WHERE message_sent = 0")

    # # Commit the changes
    # self.conn.commit()

    #     self._create_table()

    # def _create_table(self):
    #     """Create a database table to record user ID and message sent status."""
    #     # Create the database table if it doesn't exist
    #     self.cur.execute("""CREATE TABLE IF NOT EXISTS messages (
    #         user_id INT,
            # message_sent INT DEFAULT 0);""")

# def prompt_repo_to_untrack(user_id):
#   """Prompts the user to select a repository to cease tracking.

#   Args:
#     user_id: The ID of the user.
#   """

#   # Get the list of repositories that the user is currently tracking.
#   user_data = load_user_data(user_id)
#   repositories = user_data['repositories']

#   # Create a list of inline buttons, one button for each repository in the user's tracking list.
#   inline_buttons = []
#   for repository in repositories:
#     inline_buttons.append([InlineKeyboardButton(repository, callback_data='untrack_repo:' + repository)])

#   # Send a message to the user with the list of inline buttons.
#   updater.bot.send_message(user_id, 'Select the repository you want to cease tracking:', reply_markup=InlineKeyboardMarkup(inline_buttons))

# def untrack(bot, update):
#   """Removes a repository from the user's tracking list.

#   Args:
#     bot: The Telegram bot.
# #     update: The Telegram update.
# #   """

# #   # Get the repository name from the callback data.
# #   repository_name = update.callback_query.data.split(':')[1]

# #   # Remove the repository from the user's tracking list.
# #   user_id = update.callback_query.from_user.id
# #   user_data = load_user_data(user_id)
# #   repositories = user_data['repositories']
# #   repositories.remove(repository_name)
# #   save_user_data(user_id, user_data)

# #   # Send a message to the user confirming that the repository has been removed from their tracking list.
# #   bot.send_message(user_id, 'The repository {} has been removed from your tracking list.'.format(repository_name))





# def untrack_repo_from_json(user_id, repository_name):
#   """Removes a repository from the user's tracking list in the JSON file.

#   Args:
#     user_id: The ID of the user.
#     repository_name: The name of the repository to untrack.
#   """

#   user_data = load_user_data(user_id)
#   repositories = user_data['repositories']
#   repositories.remove(repository_name)
#   save_user_data(user_id, user_data)

# def untrack_repo_callback(bot, update):
#   """Handles inline button clicks to untrack repositories.

#   Args:
#     bot: The Telegram bot.
#     update: The Telegram update.
#   """

#   repository_name = update.callback_query.data.split(':')[1]
#   untrack_repo_from_json(update.callback_query.from_user.id, repository_name)

#   # Send a confirmation message to the user.
#   bot.send_message(update.callback_query.from_user.id, 'The repository {} has been untracked.'.format(repository_name))

# def untrack_repos(bot, update):
#   """Sends a message to the user with a list of inline buttons to untrack repositories.

#   Args:
#     bot: The Telegram bot.
#     update: The Telegram update.
#   """

#   user_id = update.message.from_user.id
#   user_data = load_user_data(user_id)
#   repositories = user_data['repositories']

#   # Create a list of inline buttons, one button for each repository in the user's tracking list.
#   inline_buttons = []
#   for repository in repositories:
#     inline_buttons.append([InlineKeyboardButton(repository, callback_data='untrack_repo:' + repository)])

# #   # Send a message to the user with the list of inline buttons.
# #   bot.send_message(user_id, 'Which repository do you want to untrack?', reply_markup=InlineKeyboardMarkup(inline_buttons))



# #def delete_repo_callback(bot, update):
# #   """Handles inline button clicks to delete repositories.

# #   Args:
# #     bot: The Telegram bot.
# #     update: The Telegram update.
# #   """

# #   repository_name = update.callback_query.data.split(':')[1]
# #   delete_repo_from_json(update.callback_query.from_user.id, repository_name)

# #   # Send a confirmation message to the user.
# #   bot.send_message(update.callback_query.from_user.id, 'The repository {} has been deleted.'.format(repository_name))

# # def delete_repos(bot, update):
# #   """Sends a message to the user with a list of inline buttons to delete repositories.

# #   Args:
# #     bot: The Telegram bot.
# #     update: The Telegram update.
# #   """

# #   user_id = update.message.from_user.id
# #   user_data = load_user_data(user_id)
# #   repositories = user_data['repositories']

# #   # Create a list of inline buttons, one button for each repository in the user's tracking list.
# #   inline_buttons = []
# #   for repository in repositories:
# #     inline_buttons.append([InlineKeyboardButton(repository, callback_data='delete_repo:' + repository)])

# #   # Send a message to the user with the list of inline buttons.
# #   bot.send_message(user_id, 'Which repository do you want to delete?', reply_markup=InlineKeyboardMarkup(inline_buttons))



















# import sqlite3

# class User:
#   def __init__(self, user_id):
#     self.user_id = user_id
#     self.repositories = []

#   def add_repository(self, repository):
#     self.repositories.append(repository)

#   def remove_repository(self, repository):
#     self.repositories.remove(repository)

# def create_user_table():
#   """Creates the user table in the database."""

#   connection = sqlite3.connect('users.db')
#   cursor = connection.cursor()

#   cursor.execute('''CREATE TABLE IF NOT EXISTS users (
#     user_id INTEGER PRIMARY KEY,
#     repositories TEXT NOT NULL
#   )''')

#   connection.commit()
#   connection.close()

# def get_user(user_id):
#   """Returns the user object for the given user ID."""

#   connection = sqlite3.connect('users.db')
#   cursor = connection.cursor()

#   cursor.execute('SELECT repositories FROM users WHERE user_id = ?', (user_id,))
#   repositories = cursor.fetchone()[0]

#   connection.close()

#   user = User(user_id)
#   user.repositories = repositories.split(',')

#   return user

# def save_user(user):
#   """Saves the user object to the database."""

#   connection = sqlite3.connect('users.db')
#   cursor = connection.cursor()

#   repositories = ','.join(user.repositories)

#   cursor.execute('INSERT OR REPLACE INTO users (user_id, repositories) VALUES (?, ?)', (user.user_id, repositories))

#   connection.commit()
#   connection.close()



# def main():
#   """Starts the Telegram bot."""

#   updater = Updater(BOT_TOKEN)

#   # Register a message handler to handle all incoming messages
#   updater.dispatcher.add_handler(MessageHandler(Filters.all, send_notification))

#   # Start the bot
#   updater.start_polling()

#   # Keep the bot running until the user presses Ctrl+C
#   while True:
#     time.sleep(API_REQUEST_FREQUENCY)

#     # Get the latest issues for all of the monitored repositories
#     issues = []
#     for repository in GITHUB_REPOSITORIES:
#       latest_issues = get_latest_issues(repository)
#       issues.extend(latest_issues)

#     # Send notifications to all users about the latest issues
#     for issue in issues:
#       user = get_user(issue['assignees'][0]['id'])
#       send_notification(user, issue)
