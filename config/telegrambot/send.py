#!/usr/bin/python
from telegram.ext import (
    Updater,
    CommandHandler,
    MessageHandler,
    Filters,
    RegexHandler,
    ConversationHandler
)
import telegram
import sys
import os
import inspect
dir = os.path.dirname(os.path.abspath(inspect.getfile(inspect.currentframe()))) # script directory
sys.path.append('/opt/odoo/admin/module_tools')
import odoo_config
conf = odoo_config.get_env()

def prefixed(message):
    with open('/etc/hostname', 'r') as f:
        hostname = f.read()
    return "\n".join([hostname, message])


message = sys.argv[1]
if message == '__setup__':
    token = sys.argv[2]
    channel_name = sys.argv[3].replace('@', '')   # remove leading @
    conf['TELEGRAMBOTTOKEN'] = sys.argv[2]
    bot = telegram.Bot(token)
    result = bot.sendMessage(chat_id='@{}'.format(channel_name), text='Setting up odoo channel')
    chat_id = result.chat.id
    conf["TELEGRAM_CHAT_ID"] = str(chat_id)
    conf.write()
else:
    TOKEN = conf['TELEGRAMBOTTOKEN']
    bot = telegram.Bot(TOKEN)
    updates = bot.getUpdates()
    try:
        conf['TELEGRAM_CHAT_ID']
    except:
        print "Please configure TELEGRAM_CHAT_ID by running the setup. Cannot send telegram messages now."
    else:
        chat_id = conf['TELEGRAM_CHAT_ID']
        bot.sendMessage(chat_id=chat_id, text=prefixed(message))
