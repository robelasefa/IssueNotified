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

#   # Send a message to the user with the list of inline buttons.
#   bot.send_message(user_id, 'Which repository do you want to untrack?', reply_markup=InlineKeyboardMarkup(inline_buttons))

