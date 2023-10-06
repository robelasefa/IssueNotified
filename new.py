from telegram import InlineKeyboardButton
import sensitives

def get_issue_details(repo_owner, repo_name, issue_number):
    """Get the details of the given issue."""
    back_button = InlineKeyboardButton(f"{sensitives.BACK_ARROW_EMOJI}Back", callback_data="back")
    repo_url = "https://api.github.com/repos/{}/{}/issues/{}".format(
            repo_owner, repo_name, issue_number)