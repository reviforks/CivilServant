import reddit.connection
import reddit.queries
import os
import praw
from mock import Mock, patch
import simplejson as json
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
import glob, datetime
from app.models import Base, PrawKey
from utils.common import DbEngine

TEST_DIR = os.path.dirname(os.path.realpath(__file__))

os.environ['CS_ENV'] ="test"

## SET UP THE DATABASE ENGINE
## TODO: IN FUTURE, SET UP A TEST-WIDE DB SESSION
TEST_DIR = os.path.dirname(os.path.realpath(__file__))
ENV = os.environ['CS_ENV'] ="test"

db_session = DbEngine(os.path.join(TEST_DIR, "../", "config") + "/{env}.json".format(env=ENV)).new_session()

def clear_praw_keys():
    db_session.query(PrawKey).delete()
    db_session.commit()

def setup_function(function):
    clear_praw_keys()

def teardown_function(function):
    clear_praw_keys()

### TEST THE MOCK SETUP AND  MAKE SURE IT WORKS
@patch('praw.reddit.Reddit', autospec=True)
@patch('praw.models.helpers.SubredditHelper', autospec=True)
@patch('praw.models.reddit.subreddit.Subreddit', autospec=True)
def test_mock_setup(mock_subreddit, mock_subreddithelper, mock_reddit):
    #mock_subreddit.display_name = "science"

    with open("{script_dir}/fixture_data/subreddit_posts_0.json".format(script_dir=TEST_DIR)) as f:
        mock_subreddit.new.return_value = json.loads(f.read())['data']['children']

    r = mock_reddit.return_value
    r.subreddit = mock_subreddithelper.return_value # set dynamic attributes initialized in __init__ explictly
    r.subreddit.return_value = mock_subreddit

    patch('praw.')

    ## NOW START THE TEST
    sub = r.subreddit("science")
    assert(len(mock_subreddit.new.return_value) == 100)
    #assert sub.display_name == "science"
    assert len(sub.new(limit=100)) == 100


### TEST THE MOCK SETUP WITH AN ACTUAL QUERY
### IN A WAY THAT BYPASSES THE FUNCTIONALITY
### OF THE app.reddit.Connect CLASS
@patch('praw.reddit.Reddit', autospec=True)
@patch('praw.models.helpers.SubredditHelper', autospec=True)
@patch('praw.models.Subreddit', autospec=True)    
def test_get_new_as_dict(mock_subreddit, mock_subreddithelper, mock_reddit):
    r = mock_reddit.return_value
    #mock_subreddit.display_name = "science"
    with open("{script_dir}/fixture_data/subreddit_posts_0.json".format(script_dir=TEST_DIR)) as f:
        mock_subreddit.new.return_value = json.loads(f.read())['data']['children']
    
    r.subreddit = mock_subreddithelper.return_value
    r.subreddit.return_value = mock_subreddit    
    patch('praw.')

    ## NOW START THE TEST
    d = reddit.queries.get_new_as_dict(r, "subreddit", 100)
    assert len(d) == 100

### TEST THE SYSTEM THAT STORES ACCESS KEYS
### IN THE DATABASE 
#@patch('praw.reddit.Reddit', autospec=True)
@patch('reddit.connection.praw.Reddit', autoSpec=True)
def test_connect_to_reddit_with_auth(mock_reddit):
    
    assert db_session.query(PrawKey).count() == 0
    
    reddit.connection.ENV= "test"    
    conn = reddit.connection.Connect()

    conn.connect()
    db_session.commit() ## update the objects
    assert db_session.query(PrawKey).count() == 1
    praw_key = db_session.query(PrawKey).first()
    assert praw_key.id.find("Main") >= 0
    conn.connect()
    db_session.commit() ## update the objects
    assert db_session.query(PrawKey).count() == 1

    conn.connect(controller = "FrontPageController")
    db_session.commit() ## update the objects
    assert db_session.query(PrawKey).count() == 2