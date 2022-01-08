from re import sub
import praw
import os
import pandas as pd
import json
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import datetime
import time
import sys

# popular, rising popularity (year), covid related, politics, news

SCOPE = [
    # Used to send and retrieve data to and from Google Sheets
    "https://spreadsheets.google.com/feeds",
    'https://www.googleapis.com/auth/spreadsheets',
    "https://www.googleapis.com/auth/drive.file",
    "https://www.googleapis.com/auth/drive",
]

creds = ServiceAccountCredentials.from_json_keyfile_name(os.path.join("config", "google_sheets_creds.json"), SCOPE)

client = gspread.authorize(creds)


subreddits_worksheet = client.open("database").worksheet('subreddits')

submission_data_worksheet = client.open("database").worksheet('submission_data')

subreddits_df = pd.DataFrame(subreddits_worksheet.get_all_records())



conf_path = os.path.join('config', 'conf.json')
with open(conf_path, "r") as conf_file:
    config_data = json.loads(conf_file.read())

reddit = praw.Reddit(
    # Creating Reddit object
    client_id=config_data["client_id"],
    client_secret=config_data["client_secret"],
    user_agent="DSC180B capstone project",
)


SUBMISSION_LIMIT = 100
SLEEP_TIME = .3

if __name__=="__main__":
    reddit_data = []
    topics = subreddits_df.columns
    for topic in topics:
        current_subreddits = subreddits_df[topic].str.replace('r/', '')
        for subreddit in current_subreddits:
            for index, submission in enumerate(reddit.subreddit(subreddit).hot(limit=SUBMISSION_LIMIT)):
                print_str = f"Getting data for subreddit: r/{subreddit}; Progress: {round((index/SUBMISSION_LIMIT)*100, 3)}%"
                print(print_str, end="\r")
                reddit_data.append((subreddit, 
                                    submission.title,
                                    submission.author.name, 
                                    submission.selftext, 
                                    submission.url, 
                                    str(datetime.datetime.fromtimestamp(submission.created)),
                                    submission.downs,
                                    submission.ups,
                                    submission.upvote_ratio
                                    ))
                
                time.sleep(SLEEP_TIME)
                
    reddit_data_df = pd.DataFrame(reddit_data, columns=["Subreddit", "Title", "Author", "Text", "URL", "Date Created", "Upvotes", "Downvotes", "Upvote Ratio"])
    
    
    submission_data_worksheet.update([reddit_data_df.columns.values.tolist()] + reddit_data_df.values.tolist())
