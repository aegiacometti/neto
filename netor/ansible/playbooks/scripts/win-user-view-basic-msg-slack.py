import sys
import ast
from slackclient import SlackClient
import configparser

config = configparser.ConfigParser(interpolation=configparser.ExtendedInterpolation())
netor_config_path_name = "../../netor.config"
config.read(netor_config_path_name)
bot_ad_oauth_token = config['Slack']['bot_ad_oauth']

client = SlackClient(bot_ad_oauth_token)

s = sys.argv[1]

print("sys.argv= " + str(sys.argv))

try:
    d = ast.literal_eval(s)
except SyntaxError:
    t = "`El usuario \"{}\" no existe`".format(sys.argv[2])
else:

    if d['state'] == 'absent':
        t = "`El usuario \"{}\" no existe`".format(sys.argv[2])
    else:
        if 'name' in d:
            name = str(d['name'])
        else:
            name = str(d['fullname'])

        if 'account_disabled' in d:
            account_disabled = str(d['account_disabled'])
        else:
            account_disabled = str(d['enabled'])

        if d['state'] == 'present':
            t = "```userID: " + str(d['name']) + "\n"
            t += "*fullname:* " + name + "\n"
            t += "*account_disabled:* " + account_disabled + "\n"
            t += "*account_locked:* " + str(d['account_locked']) + "\n"
            t += "*password_expired:* " + str(d['password_expired']) + "```"

        else:
            t = "`El usuario \"{}\" no existe`".format(sys.argv[2])

print("Text= " + t)

client.api_call('chat.postMessage', channel='activedirectory', text=t)