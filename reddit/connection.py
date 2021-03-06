import praw
from praw.handlers import MultiprocessHandler
import pickle
import os, inspect
from app.models import PrawKey
import simplejson as json
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.models import Base
import sqlalchemy
from utils.common import DbEngine
from reddit.praw_patch import PrawPatch

ENV =  os.environ['CS_ENV']

class Connect:

  # this initializer accepts a database session
  # and if it doesn't exist, initializes one
  # this may become a pattern that we should break out
  # into its own class eventually
  def __init__(self, db_session = None, base_dir="", env=None):
    praw_patch = PrawPatch()
    if praw_patch.required:
      praw_patch.ensure_applied()

    self.base_dir = base_dir
    if(env):
      self.env = env
    else:
      self.env = ENV
    ## LOAD DATABASE OBJECT

    if db_session is None:
      ### LOAD SQLALCHEMY SESSION
      self.db_session = DbEngine(os.path.join(self.base_dir, "config","{env}.json".format(env=self.env))).new_session()
    else:
      self.db_session = db_session
    
  def connect(self, controller="Main"):
    r = None #Praw Connection Object
    handler = MultiprocessHandler()

    # Check the Database for a Stored Praw Key
    db_praw_id = PrawKey.get_praw_id(self.env, controller)
    pk = self.db_session.query(PrawKey).filter_by(id=db_praw_id).first()
    r = praw.Reddit(user_agent="Test version of CivilServant by u/natematias", handler=handler)
    
    access_information = {}
    
    if(pk is None):
      with open(os.path.join(self.base_dir, "config","access_information_{environment}.pickle".format(environment=self.env)), "rb") as fp:
          access_information = pickle.load(fp)
    else:
      access_information['access_token'] = pk.access_token
      access_information['refresh_token'] = pk.refresh_token
      access_information['scope'] = json.loads(pk.scope)
    
    r.set_access_credentials(**access_information)

    new_access_information = {}
    update_praw_key = False

    # SAVE OR UPDATE THE ACCESS TOKEN IF NECESSARY
    if(pk is None):
      pk = PrawKey(id=db_praw_id,
                   access_token = r.access_token,
                   refresh_token = r.refresh_token,
                   scope = json.dumps(list(r._authentication)),
                   authorized_username = r.user.json_dict['name'],
                   authorized_user_id = r.user.json_dict['id'])
      self.db_session.add(pk)

    elif(access_information['access_token'] != r.access_token or
       access_information['refresh_token'] != r.refresh_token):
       pk.access_token = r.access_token
       pk.refresh_token = r.refresh_token
       pk.scope = json.dumps(list(r._authentication))
      
    self.db_session.commit()
    return r
