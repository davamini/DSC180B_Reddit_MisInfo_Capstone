# DSC180B Subreddit Misinformation Capstone Project
Analyzing the spread of misinformation in the Reddit platform.<br>
Website URL: https://davamini.com/dsc180_project.github.io/index.html
<br>
### Build Instructions:
```sh
pip install pandas praw gspread oauth2client
```
> Must create conf.json and google_sheets_creds.json in the <b>config directory</b>.<br>
> * conf.json must contain values for client_secret, and client_id, which are aquired from Reddit after creating an application.<br>
> * google_sheets_creds.json is aquired from Google Cloud after enabling APIs for google sheets.<br>
#### Run either:
```sh
python run.py
```
#### Or:
```sh
python run.py test
```
