import praw
import os
import pandas as pd
import json
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import datetime

SCOPE = [
    # Used to send and retrieve data to and from Google Sheets
    "https://spreadsheets.google.com/feeds",
    'https://www.googleapis.com/auth/spreadsheets',
    "https://www.googleapis.com/auth/drive.file",
    "https://www.googleapis.com/auth/drive",
]

creds = ServiceAccountCredentials.from_json_keyfile_name(os.path.join("config", "google_sheets_creds.json"), SCOPE)

client = gspread.authorize(creds)

worksheet = client.open("reddit_data").sheet1
         
conf_path = os.path.join('config', 'conf.json')
with open(conf_path, "r") as conf_file:
    config_data = json.loads(conf_file.read())

reddit = praw.Reddit(
    # Creating Reddit object
    client_id=config_data["client_id"],
    client_secret=config_data["client_secret"],
    user_agent="DSC180B capstone project",
)


if __name__=="__main__":
    reddit_data = []
    subreddit = "UCSD"
    for submission in reddit.subreddit(subreddit).hot(limit=10):
        reddit_data.append((subreddit, submission.title, submission.selftext, submission.url, str(datetime.datetime.fromtimestamp(submission.created))))
        
    reddit_data_df = pd.DataFrame(reddit_data, columns=["Subreddit", "Title", "Text", "URL", "Date Created"])
    
    
    worksheet.update([reddit_data_df.columns.values.tolist()] + reddit_data_df.values.tolist())
        
    print(pd.DataFrame(worksheet.get_all_records()))