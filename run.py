import praw
import os
import pandas as pd
import json
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import datetime
import time
import sys


SCOPE = [
    # Used to send and retrieve data to and from Google Sheets
    "https://spreadsheets.google.com/feeds",
    'https://www.googleapis.com/auth/spreadsheets',
    "https://www.googleapis.com/auth/drive.file",
    "https://www.googleapis.com/auth/drive",
]

try:
    creds = ServiceAccountCredentials.from_json_keyfile_name(os.path.join("config", "google_sheets_creds.json"), SCOPE)

    client = gspread.authorize(creds)


    subreddits_worksheet = client.open("database").worksheet('subreddits')

    submission_data_worksheet = client.open("database").worksheet('submission_data')

    subreddits_df = pd.DataFrame(subreddits_worksheet.get_all_records()) # Subreddits to analyze

    subreddits_data_df = pd.DataFrame(submission_data_worksheet.get_all_records()) # Actual subreddit data

    append_location = subreddits_data_df.shape[0] + 2
    top_posts_range = "year"
    submissions_already_aquired = set()

    try:
        submissions_already_aquired = set(subreddits_data_df["ID"].tolist())
        if len(pd.to_datetime(subreddits_data_df["Date Created"]).dt.year.unique()) > 1:
            top_posts_range = "month"
    except KeyError as e:
        print(f"No data detected in {submission_data_worksheet.title} worksheet")
        
    conf_path = os.path.join('config', 'conf.json')
    with open(conf_path, "r") as conf_file:
        config_data = json.loads(conf_file.read())

    reddit = praw.Reddit(
        # Creating Reddit object
        client_id=config_data["client_id"],
        client_secret=config_data["client_secret"],
        user_agent="DSC180B capstone project",
    )

    iffy_data = pd.read_csv(os.path.join("data", "iffy+ 2021-03 - EmbedIffy+.tsv"), sep="\t")

    mis_info_domains = set(iffy_data["Domain"])

except FileNotFoundError as e:
    print(f"Error: {e}\nNot a problem if 'test' parameter was specified\nContinuing...")


SUBMISSION_LIMIT = 1000
SLEEP_TIME = 0.005

# python run.py test
if __name__=="__main__":
    
    if sys.argv[1] == "test":
        """
        Produces a small output based on test data
        """
        gsheet_submission_data = pd.read_csv(os.path.join("data", "test_sample.csv"))
        
        mis_info_posts = gsheet_submission_data.loc[gsheet_submission_data["Is Misinformation"] == "Detected"].reset_index(drop=True)

        curr_fig = mis_info_posts["Subreddit"].value_counts(
        ).plot(kind="barh", 
            ylabel="# of Misinformation Links Detected", 
            xlabel="Subreddit", 
            title="# of Misinformation URLs found per Subreddit").get_figure()

        curr_fig.savefig(os.path.join("outputs", "# of Misinformation URLs found per Subreddit"), bbox_inches='tight')
        print(f"Wrote '# of Misinformation URLs found per Subreddit.png' to outputs/")
        
        sys.exit(0)
        
    # Gets subreddit submission data based on parameters in a google sheet
    # Detects misinformation based on iffy.news
    # Uploads data to a google sheet database
    reddit_data = []
    topics = subreddits_df.columns
    for topic in topics:
        current_subreddits = subreddits_df.loc[subreddits_df[topic] != ""][topic].str.replace('r/', '')
        for subreddit in current_subreddits:
            try:
                #Iterates through submissions based on upvotes in descending order
                for index, submission in enumerate(reddit.subreddit(subreddit).top(time_filter = top_posts_range, limit=SUBMISSION_LIMIT)):
                    print_str = f"Getting data from last {SUBMISSION_LIMIT} submissions from subreddit: r/{subreddit} (Sorting=top ({top_posts_range})); Progress: {round((index/SUBMISSION_LIMIT)*100, 2)}%"
                    print(print_str, end="\r")
                    
                    curr_id = submission.id
                    
                    # Makes sure that the submission was not already uploaded to google sheets
                    if curr_id in submissions_already_aquired:
                        submissions_already_aquired
                        continue
                    
                    # Specifies Author and Domain fields
                    try:
                        author = submission.author.name
                    except AttributeError:
                        author = "None"
                    if submission.is_self or (submission.domain == 'i.redd.it' or submission.domain == 'v.redd.it' or 'reddit' in submission.domain or 'imgur' in submission.domain or "youtu" in submission.domain):
                        url = "None"
                    else:
                        url = submission.domain
                        
                    # Detects misinformation domains
                    is_mis_info = "Undetected"
                    if submission.domain in mis_info_domains:
                        print("\nMISINFO DETECTED:", subreddit.upper(), submission.domain, "\n")
                        is_mis_info = "Detected"
                        
                    # Builds table that will be uploaded to google sheets
                    reddit_data.append((topic,
                                        subreddit, 
                                        submission.title,
                                        author, 
                                        submission.selftext, 
                                        url, 
                                        str(datetime.datetime.fromtimestamp(submission.created)),
                                        submission.downs,
                                        submission.ups,
                                        submission.upvote_ratio,
                                        curr_id,
                                        is_mis_info
                                        ))
                    
                    time.sleep(SLEEP_TIME)
            except Exception as e:
                print(e)
                continue
            
            print()  
            #os.system('cls' if os.name == 'nt' else 'clear')
    
    cols = ["Topic", "Subreddit", "Title", "Author", "Text", "URL Domain", "Date Created", "Downvotes", "Upvotes", "Upvote Ratio", "ID", "Is Misinformation"]
    reddit_data_df = pd.DataFrame(reddit_data, columns=cols)
    
    # Uploads to google sheets and dedcides whether to append the data or not
    if append_location > 2:
        print(f"\nStarting update at line: A{append_location}")
        submission_data_worksheet.update(f"A{append_location}",  reddit_data_df.values.tolist(), value_input_option='USER_ENTERED')
    else:
        submission_data_worksheet.update([reddit_data_df.columns.values.tolist()] + reddit_data_df.values.tolist(), value_input_option='USER_ENTERED')