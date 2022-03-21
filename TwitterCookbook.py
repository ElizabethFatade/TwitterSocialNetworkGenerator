#!/usr/bin/env python
# coding: utf-8

# In[18]:
"""
Mining the Social Web, 3rd Edition
Chapter 9: Twitter Cookbook
This Jupyter Notebook provides an interactive way to follow along with and explore the numbered examples from Mining the Social Web (3rd Edition). The intent behind this notebook is to reinforce the concepts from the sample code in a fun, convenient, and effective way. This notebook assumes that you are reading along with the book and have the context of the discussion as you work through these exercises.

In the somewhat unlikely event that you've somehow stumbled across this notebook outside of its context on GitHub, you can find the full source code repository here.

Copyright and Licensing
You are free to use or adapt this notebook for any purpose you'd like. However, please respect the Simplified BSD License that governs its use.

Notes
This notebook is still a work in progress and currently features 25 recipes. The example titles should be fairly self-explanatory, and the code is designed to be reused as you progress further in the notebook --- meaning that you should follow along and execute each cell along the way since later cells may depend on functions being defined from earlier cells. Consider this notebook draft material at this point.

Material copy and pasted from Mining the Social Web, 3rd Edition - Chapter 9: Twitter Cookbook
"""

import twitter
import networkx as nx
import json
import sys
import datetime
import time
from functools import partial
from sys import maxsize as maxint
from urllib.error import URLError
from http.client import BadStatusLine


# In[4]:


#Accessing Twitter's API for development purposes

def oauth_login():
    
    CONSUMER_KEY = 'xS2CqsJ1kB0mWLeg4qukZlDyQ'
    CONSUMER_SECRET = 'Fnsjgd65dIKZEhwS8qANbjjY3Woq9qkF1ACU5qMzEshn8SK8of'
    OAUTH_TOKEN = '1496910867119624194-pWvBAYbOukRdbtZekvNshXCGLqlcmF'
    OAUTH_TOKEN_SECRET = 'yiNobnvLL3c70yM1U7GThbvUevJT2wYuBNaXhvME3PSwe'

    auth = twitter.oauth.OAuth(OAUTH_TOKEN, OAUTH_TOKEN_SECRET,CONSUMER_KEY, CONSUMER_SECRET)
    #auth = twitter.oauth.OAuth(CONSUMER_KEY, CONSUMER_SECRET)

    twitter_api = twitter.Twitter(auth=auth)

    # Nothing to see by displaying twitter_api except that it's now a
    # defined variable

    return twitter_api


# In[5]:


#Discovering the trending topics

def twitter_trends(twitter_api, woe_id):
    # Prefix ID with the underscore for query string parameterization.
    # Without the underscore, the twitter package appends the ID value
    # to the URL itself as a special-case keyword argument.
    return twitter_api.trends.place(_id=woe_id)


# In[6]:


#Searching for tweets

def twitter_search(twitter_api, q, max_results=200, **kw):

    # See https://developer.twitter.com/en/docs/tweets/search/api-reference/get-search-tweets
    # and https://developer.twitter.com/en/docs/tweets/search/guides/standard-operators
    # for details on advanced search criteria that may be useful for 
    # keyword arguments
    
    # See https://dev.twitter.com/docs/api/1.1/get/search/tweets    
    search_results = twitter_api.search.tweets(q=q, count=100, **kw)
    
    statuses = search_results['statuses']
    
    # Iterate through batches of results by following the cursor until we
    # reach the desired number of results, keeping in mind that OAuth users
    # can "only" make 180 search queries per 15-minute interval. See
    # https://developer.twitter.com/en/docs/basics/rate-limits
    # for details. A reasonable number of results is ~1000, although
    # that number of results may not exist for all queries.
    
    # Enforce a reasonable limit
    max_results = min(1000, max_results)
    
    for _ in range(10): # 10*100 = 1000
        try:
            next_results = search_results['search_metadata']['next_results']
        except KeyError as e: # No more results when next_results doesn't exist
            break
            
        # Create a dictionary from next_results, which has the following form:
        # ?max_id=313519052523986943&q=NCAA&include_entities=1
        kwargs = dict([ kv.split('=') 
                        for kv in next_results[1:].split("&") ])
        
        search_results = twitter_api.search.tweets(**kwargs)
        statuses += search_results['statuses']
        
        if len(statuses) > max_results: 
            break
            
    return statuses


# In[8]:


#Collecting time-series data

def get_time_series_data(api_func, mongo_db_name, mongo_db_coll, 
                         secs_per_interval=60, max_intervals=15, **mongo_conn_kw):
    
    # Default settings of 15 intervals and 1 API call per interval ensure that 
    # you will not exceed the Twitter rate limit.
    
    interval = 0
    
    while True:
    
        # A timestamp of the form "2013-06-14 12:52:07"
        now = str(datetime.datetime.now()).split(".")[0]
    
        response = save_to_mongo(api_func(), mongo_db_name, mongo_db_coll + "-" + now, **mongo_conn_kw)
    
        print("Write {0} trends".format(len(response.inserted_ids)), file=sys.stderr)
        print("Zzz...", file=sys.stderr)
        sys.stderr.flush()
    
        time.sleep(secs_per_interval) # seconds
        interval += 1
        
        if interval >= 15:
            break


# In[9]:


# Extracting tweet entities

def extract_tweet_entities(statuses):
    
    # See https://developer.twitter.com/en/docs/tweets/data-dictionary/overview/entities-object
    # for more details on tweet entities

    if len(statuses) == 0:
        return [], [], [], [], []
    
    screen_names = [ user_mention['screen_name'] 
                         for status in statuses
                            for user_mention in status['entities']['user_mentions'] ]
    
    hashtags = [ hashtag['text'] 
                     for status in statuses 
                        for hashtag in status['entities']['hashtags'] ]

    urls = [ url['expanded_url'] 
                     for status in statuses 
                        for url in status['entities']['urls'] ]
               
    # In some circumstances (such as search results), the media entity
    # may not appear
    medias = []
    symbols = []
    for status in statuses:
        if 'media' in status['entities']:
            for media in status['entities']['media']:
                medias.append(media['url'])
        if 'symbol' in status['entities']:
            for symbol in status['entities']['symbol']:
                symbols.append(symbol)
    
    return screen_names, hashtags, urls, medias, symbols


# In[10]:


# Finding the most popular tweets in a collection of tweets

def find_popular_tweets(twitter_api, statuses, retweet_threshold=3):

    # You could also consider using the favorite_count parameter as part of 
    # this  heuristic, possibly using it to provide an additional boost to 
    # popular tweets in a ranked formulation
        
    return [ status
                for status in statuses 
                    if status['retweet_count'] > retweet_threshold ] 
    
# Making robust Twitter requests

def make_twitter_request(twitter_api_func, max_errors=10, *args, **kw): 
    
    # A nested helper function that handles common HTTPErrors. Return an updated
    # value for wait_period if the problem is a 500 level error. Block until the
    # rate limit is reset if it's a rate limiting issue (429 error). Returns None
    # for 401 and 404 errors, which requires special handling by the caller.
    def handle_twitter_http_error(e, wait_period=2, sleep_when_rate_limited=True):
    
        if wait_period > 3600: # Seconds
            print('Too many retries. Quitting.', file=sys.stderr)
            raise e
    
        # See https://developer.twitter.com/en/docs/basics/response-codes
        # for common codes
    
        if e.e.code == 401:
            print('Encountered 401 Error (Not Authorized)', file=sys.stderr)
            return None
        elif e.e.code == 404:
            print('Encountered 404 Error (Not Found)', file=sys.stderr)
            return None
        elif e.e.code == 429: 
            print('Encountered 429 Error (Rate Limit Exceeded)', file=sys.stderr)
            if sleep_when_rate_limited:
                print("Retrying in 15 minutes...ZzZ...", file=sys.stderr)
                sys.stderr.flush()
                time.sleep(60*15 + 5)
                print('...ZzZ...Awake now and trying again.', file=sys.stderr)
                return 2
            else:
                raise e # Caller must handle the rate limiting issue
        elif e.e.code in (500, 502, 503, 504):
            print('Encountered {0} Error. Retrying in {1} seconds'\
                  .format(e.e.code, wait_period), file=sys.stderr)
            time.sleep(wait_period)
            wait_period *= 1.5
            return wait_period
        else:
            raise e

    # End of nested helper function
    
    wait_period = 2 
    error_count = 0 

    while True:
        try:
            return twitter_api_func(*args, **kw)
        except twitter.api.TwitterHTTPError as e:
            error_count = 0 
            wait_period = handle_twitter_http_error(e, wait_period)
            if wait_period is None:
                return
        except URLError as e:
            error_count += 1
            time.sleep(wait_period)
            wait_period *= 1.5
            print("URLError encountered. Continuing.", file=sys.stderr)
            if error_count > max_errors:
                print("Too many consecutive errors...bailing out.", file=sys.stderr)
                raise
        except BadStatusLine as e:
            error_count += 1
            time.sleep(wait_period)
            wait_period *= 1.5
            print("BadStatusLine encountered. Continuing.", file=sys.stderr)
            if error_count > max_errors:
                print("Too many consecutive errors...bailing out.", file=sys.stderr)
                raise


#Getting all friends or followers for a user

def get_friends_followers_ids(twitter_api, screen_name=None, user_id=None, friends_limit=maxint, followers_limit=maxint):
    
    # Must have either screen_name or user_id (logical xor)
    assert (screen_name != None) != (user_id != None), "Must have screen_name or user_id, but not both"
    
    # See http://bit.ly/2GcjKJP and http://bit.ly/2rFz90N for details
    # on API parameters
    
    get_friends_ids = partial(make_twitter_request, twitter_api.friends.ids, 
                              count=5000)
    get_followers_ids = partial(make_twitter_request, twitter_api.followers.ids, 
                                count=5000)

    friends_ids, followers_ids = [], []
    
    for twitter_api_func, limit, ids, label in [
                    [get_friends_ids, friends_limit, friends_ids, "friends"], 
                    [get_followers_ids, followers_limit, followers_ids, "followers"]
                ]:
        
        if limit == 0: continue
        
        cursor = -1
        while cursor != 0:
        
            # Use make_twitter_request via the partially bound callable...
            if screen_name: 
                response = twitter_api_func(screen_name=screen_name, cursor=cursor)
            else: # user_id
                response = twitter_api_func(user_id=user_id, cursor=cursor)

            if response is not None:
                ids += response['ids']
                cursor = response['next_cursor']
        
            print('Fetched {0} total {1} ids for {2}'.format(len(ids),label,(user_id or screen_name)),file=sys.stderr)
        
            # XXX: You may want to store data during each iteration to provide an 
            # an additional layer of protection from exceptional circumstances
        
            if len(ids) >= limit or response is None:
                break

    # Do something useful with the IDs, like store them to disk...
    return friends_ids[:friends_limit], followers_ids[:followers_limit]


#Analyzing a user's friends and followers

def setwise_friends_followers_analysis(screen_name, friends_ids, followers_ids):
    
    friends_ids, followers_ids = set(friends_ids), set(followers_ids)
    
    print('{0} is following {1}'.format(screen_name, len(friends_ids)))

    print('{0} is being followed by {1}'.format(screen_name, len(followers_ids)))
    
    print('{0} of {1} are not following {2} back'.format(
            len(friends_ids.difference(followers_ids)), 
            len(friends_ids), screen_name))
    
    print('{0} of {1} are not being followed back by {2}'.format(
            len(followers_ids.difference(friends_ids)), 
            len(followers_ids), screen_name))
    
    print('{0} has {1} mutual friends'.format(
            screen_name, len(friends_ids.intersection(followers_ids))))


#Resolving user profile information

def get_user_profile(twitter_api, screen_names=None, user_ids=None):
   
    # Must have either screen_name or user_id (logical xor)
    assert (screen_names != None) != (user_ids != None), \
    "Must have screen_names or user_ids, but not both"
    
    items_to_info = {}

    items = screen_names or user_ids
    
    while len(items) > 0:

        # Process 100 items at a time per the API specifications for /users/lookup.
        # See http://bit.ly/2Gcjfzr for details.
        
        items_str = ','.join([str(item) for item in items[:100]])
        items = items[100:]

        if screen_names:
            response = make_twitter_request(twitter_api.users.lookup, 
                                            screen_name=items_str)
        else: # user_ids
            response = make_twitter_request(twitter_api.users.lookup, 
                                            user_id=items_str)
    
        for user_info in response:
            if screen_names:
                items_to_info[user_info['screen_name']] = user_info
            else: # user_ids
                items_to_info[user_info['id']] = user_info

    return items_to_info

# Saving and restoring JSON data with flat-text files

def save_json(filename, data):
    with open('{0}.json'.format(filename),
              'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False)


def load_json(filename):
    with open('{0}.json'.format(filename), 
              'r', encoding='utf-8') as f:
        return json.load(f)
