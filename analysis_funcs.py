import praw
import os
import pandas as pd
import json
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import datetime
import time
from collections import defaultdict

USERS_TO_ANALYZE = 40
COMMENT_LIMIT = 500
SLEEP_TIME = 5

SCOPE = [
    # Used to send and retrieve data to and from Google Sheets
    "https://spreadsheets.google.com/feeds",
    'https://www.googleapis.com/auth/spreadsheets',
    "https://www.googleapis.com/auth/drive.file",
    "https://www.googleapis.com/auth/drive",
]

conf_path = os.path.join('config', 'conf.json')
with open(conf_path, "r") as conf_file:
    config_data = json.loads(conf_file.read())

reddit = praw.Reddit(
    # Creating Reddit object
    client_id=config_data["client_id"],
    client_secret=config_data["client_secret"],
    user_agent="DSC180B capstone project",
)

creds = ServiceAccountCredentials.from_json_keyfile_name(os.path.join("config", 
                                                                      "google_sheets_creds.json"
                                                                     ), SCOPE)

client = gspread.authorize(creds)
submission_data_worksheet = client.open("database").worksheet('submission_data')
sumbission_data_df  = pd.DataFrame(submission_data_worksheet.get_all_records())
mis_info_posts = sumbission_data_df.loc[sumbission_data_df["Is Misinformation"] == "Detected"].reset_index(drop=True)
all_subreddits = sumbission_data_df["Subreddit"].unique()

def expand_subreddit_analysis():
    """
    Increases the the scope of the misinformation network
    through adding more subreddits to the google sheet list of
    subreddits to analyze if misinfo-posters are seen interacting
    with them.
    """
    top_authors = mis_info_posts["Author"].value_counts().iloc[1:USERS_TO_ANALYZE+1]
    old_index = top_authors.index
    user_fake_names = {}
    new_index = []
    for index, user in enumerate(top_authors.index):
        # Using fake names for the anonimity
        user_fake_names[user] = f"user_{index}"
        new_index.append(f"user_{index}")

    top_authors.index = new_index
    curr_fig = top_authors.plot(kind="barh", 
                    title=f"Top {USERS_TO_ANALYZE} Users Posting Most Misinformation URLs",
                    xlabel="User",
                    ylabel="# of Misinformation URLs").get_figure()

    curr_fig.savefig(os.path.join("outputs", f"Top {USERS_TO_ANALYZE} Users Posting Most Misinformation URLs.png"), bbox_inches='tight')
    
    top_authors.index = old_index
    
    subreddit_of_comments_per_user = defaultdict(set)

    for user_name in top_authors.index:
        user = reddit.redditor(user_name)
        user_data = user._fetch_data()
        try:
            user_karma_total = user_data["data"]["total_karma"]
            user_comment_karma = user_data["data"]["comment_karma"]
        except KeyError as e:
            print(user_fake_names[user_name], e)
        #user_submissions = user.submissions()
        user_comments_itter = user.comments.hot(limit=COMMENT_LIMIT)
        
        try:
            for comment in user_comments_itter:
                subreddit_of_comment = comment.subreddit.display_name
                subreddit_of_comments_per_user[user_name].add(subreddit_of_comment)
        except Exception as e:
            print(user_fake_names[user_name], e)
        
        print(f"Got subreddits of last {COMMENT_LIMIT} comments from user: {user_fake_names[user_name]}")
        time.sleep(SLEEP_TIME)
        
    subreddits_most_common = defaultdict(int)
    for user, subreddits in subreddit_of_comments_per_user.items():
        for subreddit in subreddits:
            subreddits_most_common[subreddit] += 1
            
    curr_fig = pd.Series(subreddits_most_common).sort_values(ascending=False).iloc[:5].plot(kind="barh",
                                                                             title="# of MisInfo Posters per Subreddit",
                                                                             ylabel="# of MisInfo Posters",
                                                                             xlabel="Subreddit"
                                                                            ).get_figure()

    curr_fig.savefig(os.path.join("outputs", "# of MisInfo Posters per Subreddit"), bbox_inches='tight')
    
    curr_fig = pd.Series(subreddits_most_common).sort_values(ascending=False).iloc[:42].sort_values(ascending=True)
    curr_fig = pd.DataFrame(curr_fig).reset_index()
    curr_fig.columns = ["Subreddit", "# of MisInfo Posters"]
    user_data_worksheet = client.open("database").worksheet('user_data')
    attempts = 1
    updated = False
    while not updated:
        try:
            user_data_worksheet.update([curr_fig.columns.values.tolist()] + curr_fig.values.tolist(), value_input_option='USER_ENTERED')
            updated = True
            print(f"Updated user_data sheet\nAttempts: {attempts}")
        except Exception as e:
            print(f"{e}; Sleeping: {2**attempts} Seconds")
            time.sleep(2**attempts)
            attempts += 1
    
    return curr_fig.loc[curr_fig["Subreddit"].str.lower().isin([i.lower() for i in all_subreddits]) == False]