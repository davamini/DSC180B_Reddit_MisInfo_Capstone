import praw
import os
import pandas as pd
import json

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
    print(reddit)