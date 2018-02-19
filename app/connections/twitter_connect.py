import simplejson as json
import os, sys, glob, random, datetime, time, inspect, csv
from collections import defaultdict
import twitter
import app.cs_logger
from retrying import retry


ENV =  os.environ['CS_ENV']
BASE_DIR = os.path.join(os.path.dirname(os.path.abspath(inspect.getfile(inspect.currentframe()))), "../..")


## LOAD CONFIG TO GET TOKEN INFO (copied from below, sigh)
config_path = os.path.join(BASE_DIR, "config", "twitter_configuration_" + ENV + ".json")
with open(config_path, "r") as config:
	config = json.loads(config.read())

if(config['key_path'][0] == "/"):
	token_path = config['key_path']
else:
	token_path = os.path.join(BASE_DIR, config['key_path'])

## HOW MANY TIMES TO RETRY?
## WE SHOULD RETRY FOR AS MANY TIMES AS THERE ARE KEYS
RETRY_LIMIT = len(glob.glob(os.path.join(token_path, "*.json")))

def rate_limit_retry(func):

    def retry_if_api_limit_error(exception):
        #print("rate_limit_retry: {0}".format(str(exception)))
        #print(exception)
        if(len(exception.args)>0 and len(exception.args[0])>0 and "code" in exception.args[0][0] and exception.args[0][0]['code'] == 88):
            return True
        #print("rate_limit_retry: Raising Exception")
        raise exception

    # this code wraps the function in a retry block
    @retry(retry_on_exception=retry_if_api_limit_error, stop_max_attempt_number=RETRY_LIMIT)
    def func_wrapper(self,*args, **kwargs):
        #print("Before (Class {0}, Method {1})".format(self.__class__.__name__,  sys._getframe().f_code.co_name))
        self.try_counter += 1
        result = None
        #try a new key only if it's the second attempt or later
        if(self.try_counter >= 2):
            self.log.info("Twitter: rate limit calling TwitterConnect.api.{0} on ID {1}.".format(set(args).pop().__name__, self.token['user_id']))
            ## reset time to be the appropriate reset time
            ## by setting it to the earliest possible reset time
            ## TODO: Make this more efficient by observing the specific
            max_rate_limit = None
            max_rate_limit_keys = []
            for method, ratelist in self.api.rate_limit.resources.items():
                for rl in list(ratelist.items()):
                    url = rl[0]
                    ratelimit = rl[1]
                    ##  TODO: THIS SHOULD BE THE LATEST RATE LIMIT FOR THIS KEY
                    if('reset' in ratelimit.keys() and (max_rate_limit is None or ratelimit['reset'] > max_rate_limit)):
                        max_rate_limit_keys = [method, url]
                        max_rate_limit = ratelimit['reset']
            self.token['next_available'] = datetime.datetime.fromtimestamp(max_rate_limit)
            self.token['available'] = False
            self.log.info("Twitter: Token for ID {0} next available at {1}. Selecting a new token...".format(self.token['user_id'], self.token['next_available']))

            token = self.select_available_token()
            previous_token_user = self.token['user_id']
            if(self.apply_token(token)):
                self.log.info("Twitter API connection verified under ID {0}. Previously {1}.".format(self.token['user_id'], previous_token_user))

        result = func(self,*args, **kwargs)
        ## if the above line fails, the counter will iterate
        ## without being reset, since the line below would never run
        ## if the above line succeeds, reset the counter and continue
        self.try_counter = 0
        return result

    return func_wrapper

#def rate_limit_dict():
#  return {
#      "token":None,
#      "method": None,
#      "limit_per_window": None,
#      "remaining": None,
#      "url": None
#  }

class TwitterConnect():
    def __init__(self, log=None):
        BASE_DIR = os.path.join(os.path.dirname(os.path.abspath(inspect.getfile(inspect.currentframe()))), "../..")
        self.try_counter = 0

        self.api = None

        ## LOAD LOGGER
        if(log):
            self.log = log
        else:
            self.log = app.cs_logger.get_logger(ENV, BASE_DIR)
        
        #self.rate_limit_resources = defaultdict(rate_limit_dict)
        ### LOAD API RESOURCE LIMIT INFORMATION
        #with open(os.path.join(BASE_DIR, "config", "twitter_rate_limit_resources.csv"), "r") as f:
        #    reader = csv.DictReader(f)
        #    for row in reader:
        #        if("method" in row.keys() and row["method"]!=''):
        #            for key in row:
        #                self.rate_limit_resources[row['method']][key] = row[key]
        #self.log.info("TwitterConnect loaded {0} rate limit resource mappings: {1}.".format(
        #    len(self.rate_limit_resources), 
        #    ", ".join(list(self.rate_limit_resources.keys()))))

        ## LOAD INFORMATION ABOUT KEYS (relative or absolute path)
        config_path = os.path.join(BASE_DIR, "config", "twitter_configuration_" + ENV + ".json")
        with open(config_path, "r") as config:
            self.config = json.loads(config.read())

        if(self.config['key_path'][0] == "/"):
            self.log.info("TwitterConnect is loading from an absolute configuration path specified in {0}".format(config_path))
            token_path = self.config['key_path']
        else:
            token_path = os.path.join(BASE_DIR, self.config['key_path'])
            self.log.info("TwitterConnect is loading from a relative configuration path specified in {0}. Loading tokens from {1}".format(config_path, token_path))


        self.tokens = {}
        for filename in sorted(glob.glob(os.path.join(token_path, "*.json"))):
            with open(filename, "r") as f:
                token = json.loads(f.read())
                token["valid"] = True
                token["available"] = True
                token["next_available"] = None
                token["resources"] = {}
            self.tokens[token['user_id']] = token

        ## LOAD BASE CONFIGURATION INFORMATION
        twitter_config_path = os.path.join(BASE_DIR, "config", "twitter_auth_" + ENV + ".json")
        with open(twitter_config_path, 'r') as t_config:
            twitter_config = json.loads(t_config.read())
        self.consumer_key = twitter_config["consumer_key"]
        self.consumer_secret = twitter_config["consumer_secret"]

        token = self.select_available_token()
        if(self.apply_token(token)):
            self.log.info("Twitter API connection verified under ID {0}".format(self.token['user_id']))

    ## This method takes a token and tries to adjust the API to query using the token
    def apply_token(self, token):
        if(self.api is None):
            self.api = twitter.Api(consumer_key = self.consumer_key,
                                   consumer_secret = self.consumer_secret,
                                   access_token_key = token['oauth_token'],
                                   access_token_secret = token['oauth_token_secret'])
        else:
            self.api.SetCredentials(consumer_key = self.consumer_key,
                                    consumer_secret = self.consumer_secret,
                                    access_token_key = token['oauth_token'],
                                    access_token_secret = token['oauth_token_secret'])
        try:
            verification = self.api.VerifyCredentials()
            self.api.InitializeRateLimit()            
        except twitter.error.TwitterError as e:
            self.log.error("Twitter: Failed to connect to API with User ID {0}. Remove from token set. Error: {1}.".format(token['user_id'], str(e)))
            token['valid'] = False
            self.token = None
            return False
        self.token = token
        return True

    ## This method will select from available tokens
    ## or if no tokens are available, wait until the next token 
    ## becomes available, based on information from the Twitter API
    ## then return that token
    def select_available_token(self):
        available_tokens = [token for token in self.tokens.values() if (token['available'] and token['valid'])]
        ## we take the first one rather than a random sample
        ## to make testing more reliable
        available_token = None
        if(len(available_tokens)>0):
            available_token = available_tokens[0]

        if(available_token is None):
            available_tokens = sorted(list(self.tokens.values()), key=lambda x: x['next_available'])
            for token in available_tokens:
                seconds_until_available = (token['next_available'] - datetime.datetime.now()).total_seconds() + 1
                if(seconds_until_available <= 0):
                    token['available'] = True

            try:
                available_token = available_tokens[0]
            except:
                self.log.error("Twitter: failed to find any valid tokens. Ending process.")
                sys.exit("Twitter: failed to find any valid tokens. Ending process")

            seconds_until_available = (available_token['next_available'] - datetime.datetime.now()).total_seconds() + 1
            if(seconds_until_available>0):
                self.log.info("Twitter: Next available token ({0}): {1} seconds. Waiting...".format(available_token['user_id'], seconds_until_available))
                time.sleep(seconds_until_available)
        return available_token

    ## TO USE RATE LIMIT MULTIPLEXING, CALL THE BELOW METHOD AS FOLLOWS
    ## x = TwitterConnect()
    ## x.query(x.api.GetFriends, "user")
    @rate_limit_retry
    def query(self, method, *args, **kwargs):
        method_name = method.__name__
        #print("Running {0}".format(method_name))
        #try:
        #    rate_limit_resource = self.rate_limit_resources[method_name]
        #except KeyError:
        #    # log the error and continue having the error bubble through
        #    self.log.error("Missing a method name ({0}) from config/twitter_rate_limit_resources.csv".format(method_name))
        #    raise

        result = method(*args, **kwargs)

        #current_rate_limit = self.api.rate_limit.resources[rate_limit_resource['family']][rate_limit_resource['url']]
        #self.rate_limit_resources[method_name]['token'] = self.token['user_id']
        #self.rate_limit_resources[method_name]['remaining'] = current_rate_limit['remaining']
        #self.rate_limit_resources[method_name]['reset'] = current_rate_limit['reset']

        # UPDATE TOKEN AND TOKEN LIST
        ## (IN FUTURE THIS WILL BE MULTIPLE TOKENS IN A DB)
        #self.token['resources'][method_name] = self.rate_limit_resources[method_name]
        #self.tokens[self.token['user_id']] = self.token

        return result
