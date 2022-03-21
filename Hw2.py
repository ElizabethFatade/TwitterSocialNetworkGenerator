#!/usr/bin/env python
# coding: utf-8

# In[37]:


import twitter
import matplotlib.pyplot as plt
import networkx as nx
import io, json
from matplotlib.pyplot import figure

"""TwitterCookbook contains functions I used from the 
Mining the Social Web, 3rd Edition - Chapter 9: Twitter Cookbook"""
from TwitterCookbook import oauth_login, get_friends_followers_ids, get_user_profile, save_json, load_json


# In[82]:


twitter_api = oauth_login() #Twitter API
print("Twitter api " + str(twitter_api))

f = open("output.txt", "w")


# In[69]:


# My own function to get the user's name and ID

def get_user(username): 
    user = twitter_api.users.show(screen_name=username)
    return user["name"], user["id"]

# Sample Usage

name, bid = get_user('edmundyu1001') #Part 1
print("Name of User: {0}\n Twitter ID of user is: {1}".format(name, str(bid)))


# In[70]:


# My own function to get list of ids of freinds and followers

def get_friends_and_follorwers(username):
    friends = twitter_api.friends.ids(screen_name=username, count=1000)
    followers = twitter_api.followers.ids(screen_name=username, count=1000)
    
    return friends['ids'], followers['ids']
    
# Sample Usage

friends_ids, followers_ids = get_friends_and_follorwers('edmundyu1001') #Part 2
print("Number of friends: {0}\n Number of followers: {1}".format(len(friends_ids), len(followers_ids)))


# In[72]:


#Get reciprocal friends
reciprocal_friends = set(friends_ids) & set(followers_ids) # Part 3 
print("Number of Reciprocal friends: " + str(len(reciprocal_friends)))


# In[75]:


# Select 5 most popular friends

user_profiles = get_user_profile(twitter_api, user_ids=list(reciprocal_friends)) # Part 4
sorted_user_profiles = sorted(user_profiles, key=lambda x: user_profiles[x]['followers_count'], reverse=True)
print("Their 5 most popular twitter friend ID's:", sorted_user_profiles[:5])


# In[7]:


# Using a crawler use a BFS to get top 5 reciprocal friends 
# Get the user
# Get the reciprocal friends
# For each of their reciprocal friends do the same thing 

# I created this function to get the top 5 reciprocated friends for each user and sort them
def get_top_five_sorted(friends_id_list, followers_id_list):
    reciprocal_friends_ids = list(set(friends_id_list) & set(followers_id_list)) #get the reciproal friend id's
    
    #for each id get the user profiles
    user_profiles = get_user_profile(twitter_api, user_ids=list(reciprocal_friends_ids))
    
    #sort the profiles in descending order of follower count
    sorted_user_profiles = sorted(user_profiles, key=lambda x: user_profiles[x]['followers_count'], reverse=True)
    
    #get the top 5 ids with highest folllowers count
    list_of_ids = []
    if len(sorted_user_profiles) <= 5:
        i = 0
        while i < len(sorted_user_profiles):
            list_of_ids.append(user_profiles[sorted_user_profiles[i]]['id'])
            i += 1
    else:
        for i in range(5):
            list_of_ids.append(user_profiles[sorted_user_profiles[i]]['id'])
    
    #return list of ids
    return list_of_ids


# In[8]:


#This is professor Edmund Yu's crawler function
#I modified it to crawl reciprocal friends and to a depth of 3
#Part 6
def crawl_followers(twitter_api, screen_name, limit=5000, depth=3):
    # Resolve the ID for screen_name and start working with IDs for consistency
    # in storage
    seed_id = str(twitter_api.users.show(screen_name=screen_name)['id'])
    next_queue_friends, next_queue_followers = get_friends_followers_ids(twitter_api, user_id=seed_id,
    friends_limit=limit, followers_limit=limit) #changed to get the friends and followers queue
    
    next_queue = get_top_five_sorted(next_queue_friends, next_queue_followers)
    
    d = 1
    data = {}
    while d < depth:
        print(d)
        d += 1
        (queue, next_queue) = (next_queue, [])
        for fid in queue:
            friends_ids, follower_ids = get_friends_followers_ids(twitter_api, user_id=fid,
            friends_limit=limit,
            followers_limit=limit)
            
            reciprocal_friends = get_top_five_sorted(friends_ids, follower_ids) 
            
            data[fid] = reciprocal_friends
                    
            next_queue += reciprocal_friends 
            
    return data

print("Crawling...\n")
results = crawl_followers(twitter_api, 'edmundyu1001')


# In[8]:


#Twitter Cookbook function to save results to JSON file

def save_json(filename, data):
    with open('{0}.json'.format(filename),
              'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False)

print("Output saved to results.json file")
save_json('results', results) #results are stored in results.json file


# In[88]:


#Twitter Cookbook function to get data from JSON file
def load_json(filename):
    with open('{0}.json'.format(filename), 
              'r', encoding='utf-8') as f:
        return json.load(f)

results = load_json('results') #load JSON data

#Create graph
G = nx.Graph()

G.add_node(bid) #add root node - i.e main twitter user from part 1
keys = results.keys()

#Add edges to graph for each user and their reciprocal friends
for user in results.keys():
    G.add_edge(bid, user)
    for friend in results[user]:
        G.add_edge(user, friend)
        
G.edges(data=True)


# In[91]:


#Drawing the graph Part 6
nx.draw(G, with_labels=True)
#figure(figsize=(20, 20), dpi=100)

print("Social network graph has been saved to graph.png file!")
plt.savefig("graph.png")


# In[83]:


diameter = nx.diameter(G, e=None)
output1 = "The diameter of {0}'s Twitter Social Network is {1}\n".format(name, str(diameter))
f.write(output1)
print(output1)

average_distance = nx.average_shortest_path_length(G, weight=None)
output2 = "The average distance of {0}'s Twitter Social Network is {1}".format(name, str(average_distance))
f.write(output2)
print(output2)


# In[84]:


f.close()


# In[ ]:




