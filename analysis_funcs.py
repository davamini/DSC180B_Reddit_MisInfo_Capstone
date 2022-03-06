import praw
import os
import pandas as pd
import json
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import datetime
import time
from collections import defaultdict
import gensim
from gensim.utils import simple_preprocess
import nltk
from nltk.corpus import stopwords
import gensim.corpora as corpora
import pyLDAvis.gensim_models as gensimvis
import pickle 
import pyLDAvis
import hvplot.networkx as hvnx
import networkx as nx
import holoviews as hv
from pyvis.network import Network


USERS_TO_ANALYZE = 5
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

def generate_figures():
    """
    Generates figures. Returns a dictionary that has the number of misinfo
    posters per subreddit
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
    
    curr_fig.savefig(os.path.join("outputs", "# of MisInfo Posters per Subreddit.png"), bbox_inches='tight')
    output_topic_model_interactive_graph(subreddit_of_comments_per_user)
    
    return subreddits_most_common
    
def expand_subreddit_analysis(subreddits_most_common):
    """
    Increases the the scope of the misinformation network
    through adding more subreddits to the google sheet list of
    subreddits to analyze if misinfo-posters are seen interacting
    with them.
    """
    
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


def output_topic_model_interactive_graph(subreddit_of_comments_per_user):
    """
    Outputs Topic Model and interactive graph into output folder
    """
    stop_words = stopwords.words('english')
    stop_words.extend(['from', 'subject', 're', 'edu', 'use'])

    def words_from_sentence(sents):
        for sent in sents:
            yield(gensim.utils.simple_preprocess(str(sent), deacc=True))
            
    def take_out_stopwords(texts):
        return [[word for word in simple_preprocess(str(words)) 
                if word not in stop_words] for words in texts]

    data = sumbission_data_df['Title'].values.tolist()
    data_words = list(words_from_sentence(data))
    data_words = take_out_stopwords(data_words)
    
    id_2_word = corpora.Dictionary(data_words)
    words = data_words
    text_collection = [id_2_word.doc2bow(word) for word in words]
    topics = 5
    curr_lda = gensim.models.LdaMulticore(corpus=text_collection,
                                        id2word=id_2_word,
                                        num_topics=topics)
    
    LDAvis_data_path = os.path.join("outputs", 'outputs'+str(topics))
    
    LDAvis_started = gensimvis.prepare(curr_lda, text_collection, id_2_word)
    with open(LDAvis_data_path, 'wb') as f:
        pickle.dump(LDAvis_started, f)
    with open(LDAvis_data_path, 'rb') as f:
        LDAvis_started = pickle.load(f)
        
    pyLDAvis.save_html(LDAvis_started, os.path.join("outputs", "model_output.html"))
    print("Created model_output.html")
    ### Starting graph creation
    
   

    edge_lst = []
    edges_dict = defaultdict(set)
    for user, subreddits in subreddit_of_comments_per_user.items():
        for subreddit1 in subreddits:
            for subreddit2 in subreddits:
                if subreddit1 == subreddit2:
                    continue
                else:
                    edges_dict[subreddit1].add(subreddit2)

    popularity_dict = defaultdict(int)
    for subreddit1, subreddits in edges_dict.items():
        popularity_dict[subreddit1] = len(subreddits)
        
    top_mis_info_subreddits = pd.Series(popularity_dict).sort_values(ascending=False).iloc[:50].index

    for subreddit in top_mis_info_subreddits:
        for curr_subreddit in edges_dict[subreddit]:
            if curr_subreddit in top_mis_info_subreddits:
                edge_lst.append((subreddit, curr_subreddit))
                
    G = nx.petersen_graph()
    G.add_edges_from(edge_lst) 
    
    N = Network(directed=False)
    N.repulsion(node_distance=100)
    for n, attrs in G.nodes.data():
        N.add_node(n)
    for e in G.edges.data():
        N.add_edge(e[0], e[1], width=.0001)

    for i in N.edges.copy():
        if isinstance(i['from'], int):
            N.edges.remove(i)
        
    for i in N.node_map.copy():
        if isinstance(i, int):
            del N.node_map[i]
            
    for i in N.nodes.copy():
        if isinstance(i['label'], int):
            N.nodes.remove(i)

    N.width = '1000px'
    N.height = '1000px'
    N.write_html('outputs/subreddit_graph.html', notebook=False)

