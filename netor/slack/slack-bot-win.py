#!/usr/bin/python
# -*- coding: iso-8859-15 -*-

import time
import re
from slackclient import SlackClient
import socket
import ipaddress
import subprocess
import configparser
import slacklogging
import sys


config = configparser.ConfigParser(interpolation=configparser.ExtendedInterpolation())
netor_config_path_name = "../netor.config"
config.read(netor_config_path_name)

bot_oauth_token = config['Slack']['bot_win_oauth']

# instantiate Slack client
slack_client = SlackClient(bot_oauth_token)
# starterbot's user ID in Slack: value is assigned after the bot starts up
starterbot_id = None

# constants
_RTM_READ_DELAY = 1  # 1 second delay between reading from RTM
_EXAMPLE_COMMAND = "do"
_MENTION_REGEX = "^<@(|[WU].+?)>(.*)"
_NETOR_HOME_DIRECTORY = "/home/adrian/netor-master/"
_PLAYBOOK_FULL_PATH_NAME = _NETOR_HOME_DIRECTORY + "netor/ansible/playbooks/"

# variables in files
_AUTHORIZATION_FILE = 'authorizations/auth-bot-win.txt'


def parse_bot_commands(slack_events):
    """
        Parses a list of events coming from the Slack RTM API to find bot commands.
        If a bot command is found, this function returns a tuple of command and channel.
        If its not found, then this function returns None, None.
    """
    for event in slack_events:
        if event["type"] == "message" and "subtype" not in event:
            user_id, message = parse_direct_mention(event["text"])
            if user_id == starterbot_id:
                return message, event["channel"], str(event["user"])
    return None, None, None


def parse_direct_mention(message_text):
    """
        Finds a direct mention (a mention that is at the beginning) in message text
        and returns the user ID which was mentioned. If there is no direct mention, returns None
    """
    matches = re.search(_MENTION_REGEX, message_text)
    # the first group contains the username, the second group contains the remaining message
    return (matches.group(1), matches.group(2).strip()) if matches else (None, None)


def verify_source(source):
    with open(_NETOR_HOME_DIRECTORY + "netor/ansible/hosts", "r") as file:
        source += " "
        for line in file:
            if source in line:
                ansible_host = re.search("(.*) ansible_host", line)
                return ansible_host[1]
    return False


def fix_hostname(host):
    if "http" in host:
        host = re.search("\|(.*)>", host)
        return host[1]


def verify_host(host):
    try:
        ipaddress.ip_address(host)
    except ValueError:
        try:
            host = socket.gethostbyname(fix_hostname(host))
        except socket.error:
            return False
        except TypeError:
            return False
        else:
            return host
    else:
        return host


def send_msg(channel_sm, response_sm):
    # Sends the response back to the channel
    try:
        slack_client.api_call("chat.postMessage", channel=channel_sm, text=response_sm)
    except Exception:
        slacklogging.log_msg(bot_log_file, __file__, "Cannot send message to Slack.")
        slacklogging.log_msg(bot_log_file, __file__, Exception)
    slacklogging.log_msg(bot_log_file, __file__, "Chat Command: " + response_sm + " - On Channel: " + channel_sm)


def ansible_cmd(playbook, channel_hd, **kwargs):
    p_book = _PLAYBOOK_FULL_PATH_NAME + playbook
    cmd = "ansible-playbook " + p_book + " --extra-vars \""
    for key, value in kwargs.items():
        cmd += key + "=" + value + " "
    cmd += "\" -vvvv"

    send_msg(channel_hd, "```Comando en ejecuci�n```")
    slacklogging.log_msg(bot_log_file, __file__, "Ansible command: " + cmd)
    subprocess.Popen(cmd, shell=True)


def win_ping(command_hd, channel_hd):
    command_hd_splited = command_hd.split()
    source = verify_source(command_hd_splited[1])
    destination = verify_host(command_hd_splited[2])

    if len(command_hd_splited) < 3:
        send_msg(channel_hd, "`Sintaxis incorrecta.`")

    if not source:
        send_msg(channel_hd, "`El servidor \"{}\" no est� en mi inventario de equipos`".format(command_hd_splited[1]))
        return

    if not destination:
        send_msg(channel_hd, "`El destino \"{}\" es inv�lido`".format(command_hd_splited[2]))
        return

    ansible_cmd("win-os-ping-msg-slack.yml", channel_hd, cmd="ping", source=source, destination=destination)


def list_inventory(channel_hd):
    text = ""
    with open(_NETOR_HOME_DIRECTORY + "netor/ansible/hosts", "r") as file:
        for line in file:
            match = re.search("(.*) ansible_host=([^\s]+)", line)
            if match:
                text += match[1] + " \t" + match[2] + "\n"
    send_msg(channel_hd, text)


def authorized_user(slack_userid):
    file = open(_AUTHORIZATION_FILE, 'r')
    authorized_user_ids = file.read()
    file.close()
    if slack_userid in authorized_user_ids:
        return True
    else:
        return False


def handle_command(command_hd, channel_hd):
    """
        Executes bot command if the command is known
    """

    slacklogging.log_msg(bot_log_file, __file__, "Chat Command: " + command_hd + " - On Channel: " + channel_hd)

    if command_hd.startswith("help"):
        response = "```Esta es la lista de commandos que puedes ejecutar:\n" \
                   "- @Bot-Win listar inventario \n" \
                   "- @Bot-Win win-ping _direccion_ip_origen_ _direccion_ip_destino_```"
        send_msg(channel_hd, response)

    elif command_hd.startswith("win-ping"):
        win_ping(command_hd, channel_hd)

    elif command_hd.startswith("listar inventario"):
        list_inventory(channel_hd)

    else:
        response = "`No conozco ese comando. Intenta con *\"@Bot-Win help\"* para ver la lista de comandos.`"
        send_msg(channel_hd, response)


if __name__ == "__main__":

    config = configparser.ConfigParser(interpolation=configparser.ExtendedInterpolation())
    config.read((_NETOR_HOME_DIRECTORY + "netor/netor.config"))
    bot_log_file = config['Slack']['bot_win_log_file']

    sys.stdout = open(bot_log_file, 'a+')

    if slack_client.rtm_connect(with_team_state=False):
        print("Starter Bot connected and running!")
        # Read bot's user ID by calling Web API method `auth.test`
        starterbot_id = slack_client.api_call("auth.test")["user_id"]
        while True:
            try:
                command, channel, userid = parse_bot_commands(slack_client.rtm_read())
            except Exception:
                slacklogging.log_msg(bot_log_file, __file__, "Cannot send message to Slack.")
                slacklogging.log_msg(bot_log_file, __file__, Exception)
            else:
                if command:
                    print("UserID= " + userid)
                    print("Command= " + str(command))
                    print("Channel= " + str(channel))
                    if authorized_user(userid):
                        print("Comando Autorizado")
                        handle_command(command, channel)
                    else:
                        print("Comando Denegado")
                        send_msg(channel, "`Usuario \"{}\" no autorizado a ejecutar el comando`".format(userid))

            time.sleep(_RTM_READ_DELAY)
    else:
        print("Connection failed. Exception traceback printed above.")
