TELEGRAM_TOKEN = '6685183482:AAH6q7gWdUm5ZYYAbhoqDh0tqHIXcrjGSPw'
BOT_NAME = 'IssueNotified'
GITHUB_TOKEN = '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'
DEVELOPERS = {"DEVELOPER_ROBEL_ID": 5347094985, "DEVELOPER_BEFEKADU_ID": 6167688485}
COMMUNICATION_CODE = 'The king is back!'

# EMOJIS
HUNDRED_POINTS = "\U0001F4AF"
CHECK_MARK_EMOJI = chr(0x2705)
CROSS_MARK_EMOJI = chr(0x274C)
HI_EMOJI = "\U0001F44B"
"👋"	"\U0001F44B"
"🐛"	"\U0001F41B"
"🤯"	"\U0001F92F"
"🔧"	"\U0001F527"
"🚀"	"\U0001F680"
"📄"	"\U0001F4C4"
"🤖"	"\U0001F916"
"👍"	"\U0001F44D"
"💬"	"\U0001F4AC"
"🙏"	"\U0001F64F"

# Update messages to send to users
MESSAGE1 = f"""
\U0001F44B Hi everyone,

We're so sorry for the bugs in our bot lately. We know they've been frustrating \U0001F92F, and we appreciate your patience as we worked to fix them.

We're happy to announce that we've made some improvements and bug fixes, and our bot is now running smoothly again \U0001F680! You can now receive timely updates on your favorite repositories with ease!

Thank you for choosing our bot \U0001F916 . We're always looking for ways to improve, so please don't hesitate to share any feedback or questions in the comments section \U0001F4AC.
""" 

# 🎉: U+1F389
# 🚀: U+1F680
# 📧: U+1F4E7
# ⏰: U+23F0
# ✨: U+2728
# 😊: U+1F60A
# 🙏: U+1F64F

MESSAGE2 = f"""
Here is a revised version of the message with emojis:

🎉🚀 IssueNotified Bot Update! 🚀🎉

Hi everyone,

We are excited to announce some improvements to our IssueNotified bot!

Untracking repositories is now easier than ever! 🎉

Now, you can simply click on an inline button to untrack a repository, instead of having to manually enter the name and owner of the repository.

We have also fixed some bugs and added some new features:

Receive notifications about new issues via email! 📧
Configure the bot to send you notifications at specific times of the day. ⏰
More bug fixes and improvements! ✨
We hope you enjoy the new features and improvements to the IssueNotified bot! Please let us know if you have any feedback or suggestions. 😊

Thank you for using IssueNotified! 🙏"""


# ✨: U+2728
# 🌟: U+1F31F
# 🌠: U+1F320
# 🎇: U+1F387
# 🎆: U+1F386
# 🧨: U+1F9E8
# 💥: U+1F4A5
# 💫: U+1F4AB


# import logging

# def error_handler(update, context):
#   """Handles errors that occur during the bot's runtime.

#   Args:
#     update: The Telegram update.
#     context: The Telegram context.
#   """

#   logging.error(context.error)

#   # Send a notification message to the bot's developer about the error.
#   bot.send_message(YOUR_DEVELOPER_ID, 'An error occurred in the IssueNotified bot: {}'.format(context.error))

# updater.dispatcher.add_error_handler(error_handler)