import OAuth2Util
import praw
import pylast
import os
import time
import pickle

STATE_DATA = "botStateData.pkl"
SUBREDDIT = "TeacupsAndTurntables"
USER_NAME = ""
USER_AGENT = "AdminUtil"
OAUTH_CONF_FILE = "./config/oauth.ini"

class Bot:
    upcoming_submissions = [] #TODO: remove album after it is posted
    archived_submissions = []
    
    ERROR_AUTH = "Error: You do not have the correct permissions for this command!"
    ERROR_INVALID = "Error: Invalid Number of Arguments"
    ERROR_ALBUM_INVALID = "Error: Too Few Arguments to add Album"
    
    def __init__(self, user_agent, user_name):
        self.user_name = user_name
        self.reddit = praw.Reddit(user_agent)
        self.parser = Parser()
        print("authenticating")
        self.oauth = OAuth2Util.OAuth2Util(self.reddit, configfile=OAUTH_CONF_FILE)
        print("authentication complete")
        self.oauth.refresh(force=True)
        if os.path.isfile(STATE_DATA):
            self.load_data()
        else:
            self.data = Data()
        self._retrieve_moderators()
    
    def save_data(self):
        with open(STATE_DATA, 'wb') as output_file:
            pickle.dump(self.data, output_file, pickle.HIGHEST_PROTOCOL)
    
    def load_data(self):
        with open(STATE_DATA, 'rb') as input_file:
            self.data = pickle.load(input_file)

    #TODO: test this
    def _retrieve_moderators(self):
        user_list = self.data.get_user_names()
        state_mod_list = self.data.get_user_names_by_auth(User.AUTH_ADMIN)
        mod_list = self.reddit.get_subreddit(SUBREDDIT).get_moderators()

        for mod in mod_list:
            print("Processing mod: " + mod.name)
            if mod.name not in user_list:
                self.data.add_user(mod.name, User.AUTH_ADMIN)
            elif mod.name not in state_modS_list:
                self.data.elevate_user(mod, User.AUTH_ADMIN)

        #for a user who is not a moderator on the subreddit,
        #but was a part of the state saved moderator list
        #we need to remove them from the set of moderators
        for user in user_list:
            print("Processing user:" + user.user_name)
            if user.user_name not in mod_list and user.user_name in state_mod_list:
                self.data.elevate_user(user.user_name, User.AUTH_DEFAULT)

    
    def check_messages(self):
        messages = self.reddit.get_unread(limit=None)
        for msg in reversed(list(messages)):
            response = self._parse_command(msg)
            print(response)
            msg.reply(response)
            msg.mark_as_read()
    
    def check_events(self): #TODO: fix to where it doesn't post every 15 minutes
        if time.strftime("%A") == self.data.post_day:
            self._post_album()
    
    def _authenticate_user(self, name, level):
        if level == 'Mod':
            mod_list = self.reddit.get_subreddit(SUBREDDIT).get_moderators()
            for mod in mod_list:
                if name == mod:
                    return True
            return False
        elif level == 'User':
            for user in self.data.user_list:
                if user.name == name:
                    return True
            return False
        else:
            return False
    
    def _post_album_to_reddit(self, album):
        post_body = self._generate_post_body(album)
        print(post_body)
        self.reddit.submit(SUBREDDIT, "Week "+ str(self.data.week) + ": " + album.artist + " = " + album.album_title, text=str(post_body), send_replies=False)
    
    def _generate_post_body(self, album):
        #post_body = "This Weeks Album Has Been Picked By /u/" #TODO: get user who submitted album
        post_body += "\n\n## ["+ album.artist +" - "+ album.album_title + "]("+album.link1+")\n\n### Details and Synopsis\n\n"
        post_body += "Release Detail | Value\n---|---:\n**Year** | " +  album.year +"\n**Length** | " + album.length + "\n**Label** | " +  album.label +"\n**Genre** | " + album.genre
        post_body += "\n\n&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;\n\n"
        post_body += album.description + "\n\n### Links\n\n*" + "[" + album.link1 + "](" + album.link1 + ")"
        if album.link2 != "NULL":
            post_body += "\n*" + "[" + album.link2 + "](" + album.link2 + ")"
        if album.link3 != "NULL":
            post_body += "\n*" + "[" + album.link3 + "](" + album.link3 + ")"
        post_body += "\n\n### Selection Reason\n\n" + album.selection_reason
        post_body += "\n\n### Analysis Questions\n\n" + album.analysis_questions

        return post_body
    
    def _post_album(self):
        if len(Bot.upcoming_submissions) > 0:
            album = Bot.upcoming_submissions[0]
            self._post_album_to_reddit(album)
            self.data.week += 1
        else:
            print("No albums submitted.")
    
    def _parse_command(self, msg):
        cmd = msg.subject
        args = msg.body
        success = True
        args = args.split(';')
        if cmd == "ADD-USER":
            if len(args) == 1:
                print("Add User: " + args[0])
                if self._authenticate_user(msg.author.name, 'Mod'):
                    success = self._add_user(args[0])
                else:
                    success = Bot.ERROR_AUTH
            else:
                success = Bot.ERROR_INVALID
        elif cmd == "GET-USERS":
            if len(args) == 1 and args[0] == '?':
                if self._authenticate_user(msg.author.name, 'User'):
                    success = str(self._get_user_list())
                else:
                    success = Bot.ERROR_AUTH
            else:
                success = Bot.ERROR_INVALID
        elif cmd == "ADD-ALBUM":
            if len(args) >= 10:
                if self._authenticate_user(msg.author.name, 'User'):
                    success = self._add_album(msg.author.name, args)
                else:
                    success = Bot.ERROR_AUTH
            else:
                success = Bot.ERROR_ALBUM_INVALID
        elif cmd == "POST-ALBUM":
            if len(args) == 1:
                if self._authenticate_user(msg.author.name, 'Mod'):
                    success = self._add_event(msg.author.name, args[0])
                else:
                    success = Bot.ERROR_AUTH
            else:
                success = Bot.ERROR_INVALID
        else:
            success = "Error: Invalid Command: " + cmd

        if success:
            return "Your Command has been processed."
        else:
            return success
    
    def _add_user(self, user_name):
        for user in self.data.user_list:
            if user.name == user_name:
                return "Error: User Already Added!"
        self.data.user_list.append(User(user_name))
        return True
    
    def _add_event(self, user_name, post_day):
        self.data.post_day = post_day
        return True
    
    def _add_album(self, user_name, args):
        #TODO: verify no one has added album
        for user in self.data.user_list:
            print(user.name + user_name)
            if user.name == user_name:
                return user.add_submission(args)
        return "Error: User Name Not Recognised!"
    
    def _get_user_list(self):
        if len(self.data.user_list) != 0:
            return self.data.user_list
        else:
            return "Error: No Users Added!"

class Data:
    def __init__(self):
        self.week = 0
        self.user_list = []
        self.post_day = ""

    def get_user_names(self):
        users = []
        for user in self.user_list:
            users.append(user.name)
        return users

    def get_user_names_by_auth(self, auth):
        users = []
        for user in self.user_list:
            if user.auth_level == auth:
                users.append(user.name)
        return users

    def add_user(self, name, auth):
        self.user_list.append(User(name, auth))

class User:
    AUTH_DEFAULT = 0
    AUTH_ADMIN = 1

    def __init__(self, name, auth_level):
        self.name = name
        self.auth_level = auth_level #TODO: update _add_user to this
        
class Submission:
    def __init__(self, args, user):
        ar = Album_Retriever()
        self.album_details = ar.get_album_details(args[0], args[1])
        ar = None
        self.description = args[2]
        self.selection_reason = args[3]
        self.notes = args[4]
        self.analysis_questions = args[5]
        self.links = args[6]
        self.submitter = user

class Album:
    def __init__(self):
        self.title = ""
        self.artist = ""
        self.year_published = ""
        self.label = ""
        self.genres = []
        self.tracklist = []

    def print_album_details(self):
        print("title: " + self.title)
        print("artist: " + self.artist)
        if self.year_published:
            print("year_published: " + self.year_published)
        if self.label:
            print("label: " + self.label)
        if self.genres:
            print("genres: " + str(self.genres))
        if self.tracklist:
            print("tracklist: " + str(self.tracklist))

class Parser():
    #string literals
    CMD_GET_USERS = 0
    CMD_ADD_USER = 1
    CMD_GET_ALBUM = 2
    CMD_GET_ALBUM_LIST = 3
    CMD_GET_ARCHIVE_LIST = 4
    CMD_ADD_ALBUM = 5
    CMD_POST_ALBUM = 6

    def parse_args(self, cmd, args):
        if cmd == Parser.CMD_GET_USERS:
            return true
        elif cmd == Parser.CMD_ADD_USER:
            return true
        elif cmd == Parser.CMD_GET_ALBUM:
            return true
        elif cmd == Parser.CMD_GET_ALBUM_LIST:
            return true
        elif cmd == Parser.CMD_GET_ARCHIVE_LIST:
            return true
        elif cmd == Parser.CMD_ADD_ALBUM:
            return true
        elif cmd == Parser.CMD_POST_ALBUM:
            return true
        else:
            return false

class Album_Retriever:
    #string literals
    CONF_USERNAME = "username"
    CONF_PASSWORD = "password"
    CONF_API_KEY = "api_key"
    CONF_API_SECRET = "api_secret"
    CONF_TOKEN = "="
    def __init__(self):
        self.username = ""
        self.password_hash = ""
        self.api_key = ""
        self.api_secret = ""
        self._parse_config()
        self.network = pylast.LastFMNetwork(api_key = self.api_key, api_secret = self.api_secret, username = self.username, password_hash = self.password_hash)

    def _parse_config(self):
        pwd = os.path.dirname(os.path.realpath(__file__))
        conf = open(pwd + "/config/lastfm.ini", "r")
        for lines in conf:
            line = lines.split()
            if line[1] == Album_Retriever.CONF_TOKEN:
                if line[0] == Album_Retriever.CONF_USERNAME:
                    self.username = line[2]
                elif line[0] == Album_Retriever.CONF_PASSWORD:
                    self.password_hash = pylast.md5(line[2])
                elif line[0] == Album_Retriever.CONF_API_KEY:
                    self.api_key = line[2]
                elif line[0] == Album_Retriever.CONF_API_SECRET:
                    self.api_secret = line[2]
                else:
                    print "Unrecognized configuration option."
            else:
                print "Could not connect to last.fm"
        conf.close()

    def _parse_tags(self, toptags):
        tags = pylast.extract_items(toptags)
        genres = []
        for tag in tags:
            genres.append(tag.get_name())
        return genres

    def _parse_tracks(self, track_array):
        tracks = []
        for track in track_array:
            tracks.append(str(track))
        return tracks

    def get_album_details(self, artist, title):
        album = self.network.get_album(artist, title)
        album_details = Album()
        album_details.title = title
        album_details.artist = artist
        album_details.year_published = album.get_release_date()
        album_details.label = ""
        album_details.genres = self._parse_tags(album.get_artist().get_top_tags(limit=5))
        album_details.tracklist = self._parse_tracks(album.get_tracks())
        return album_details


##########MAIN###########
bot = Bot(USER_AGENT, USER_NAME)
#while True:
#    bot.check_messages()
#    bot.check_events()
#    bot.save_data()
#    time.sleep(900)
#ar = Album_Retriever()
#album_details = ar.get_album_details("Death Grips", "No Love Deep Web")
#album_details.print_album_details()
