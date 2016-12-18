from telegram import (ReplyKeyboardMarkup, ReplyKeyboardRemove)
from telegram.ext import (Updater, CommandHandler, MessageHandler, Filters, RegexHandler, ConversationHandler)
import telegram
import sys
import os
import inspect
message = sys.argv[1]
path = os.path.dirname(os.path.abspath(inspect.getfile(inspect.currentframe())))
path = os.path.join(path, '..', 'customs.env')
with open(path, 'r') as f:
    content = f.read().split("\n")
    content = [x for x in content if x.split("=")[0] == 'TELEGRAMBOTTOKEN']
    if content:
        TOKEN = content[0].split("=")[1]
bot = telegram.Bot(TOKEN)
updates = bot.getUpdates()
if updates:
    chat_id = updates[-1].message.chat_id
    bot.sendMessage(chat_id=chat_id, text=message)
