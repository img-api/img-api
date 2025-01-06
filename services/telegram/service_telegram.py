import datetime
import hashlib
import json
import os

import requests

from config_telegram import imgapi_config, telegram_config
from telegram import (InlineKeyboardButton, InlineKeyboardMarkup,
                      ReplyKeyboardMarkup, ReplyKeyboardRemove, Update)
from telegram.ext import (Application, CommandHandler, ContextTypes,
                          MessageHandler, filters)

telegram_bot = None


class ImgAPI():
    user = None
    token = None
    _instance = None

    def __new__(cls):
        # Singleton
        if cls._instance is None:
            print("================================")
            print(" IMGAPI Start v0.1pa")
            print("================================")
            cls._instance = super(ImgAPI, cls).__new__(cls)

        return cls._instance

    def get_api_url(self, url):
        api_url = self.api_entry + url
        if not self.token:
            return api_url

        if url.find("?") == -1:
            api_url += "?"
        else:
            api_url += "&"

        api_url += "key=" + self.token
        print(api_url)

        return api_url

    def setup(self, props={}):
        self.props = props

        if 'api' in props:
            self.api_entry = props['api']

        if 'token' in props:
            self.token = props['token']

    def api_call(self, url, data=None):
        api_url = self.get_api_url(url)
        try:
            if data:
                r = requests.post(api_url, json=data)
            else:
                r = requests.get(api_url)

        except requests.exceptions.RequestException as e:
            print(" Failed on request ")
            raise e

        return r.json()


async def coms_send_notification(chat_id, text):
    global telegram_bot
    try:
        await telegram_bot.send_message(chat_id=chat_id, text=text, parse_mode='HTML')
    except Exception as err:
        print(str(err))
        return


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Send a message when the command /start is issued."""
    global imgapi

    payload = ' '.join(context.args)
    try:
        if payload:
            result = imgapi.api_call("/telegram/register/" + payload + "/" + str(update.effective_chat.id))
            user = result['user']

            hello = f"Welcome! Hello {user['first_name']}"

            print(hello)
            await coms_send_notification(update.effective_chat.id, hello)
            return
    except Exception as e:
        print(" CRASHED " + str(e))
        await coms_send_notification(
            update.effective_chat.id, '\n\nHi, Welcome to <i>HEADINGTOMARS.com</i> \n'
            'There was a problem talking to server about your registration, please try again later\n')
        return

    await coms_send_notification(
        update.effective_chat.id, '\n\nHi, Welcome to <i>HEADINGTOMARS.com</i> \n'
        'Type /help to get more help and a commands list!\n')


async def help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Send a message when the command /help is issued."""
    await coms_send_notification(update.effective_chat.id, '\n\n<b>Help!</b>\n' + "/report <b>1</b> Send report \n")


async def echo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Echo the user message."""
    await update.message.reply_text(update.message.text)


async def error(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Log Errors caused by Updates."""
    print(str(context.error))
    if not update:
        print(" ERROR ")
        return

    await coms_send_notification(update.effective_chat.id, "Error " + str(context.error))
    return


async def report(update: Update, context: ContextTypes.DEFAULT_TYPE):
    tmp = " <b>Report</b><pre>\n"
    tmp += "---------------------------------------------\n"
    tmp += "Chat ID <i>" + str(update.effective_chat.id) + "</i>"
    tmp += "</pre>\n"
    await coms_send_notification(update.effective_chat.id, tmp)
    return


async def text_event(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.message.from_user
    print(update.effective_chat.title, f"{user.id}:: {update.message.text}")

    return None


def telegram_init(cfg):
    global telegram_bot

    if not cfg.get("token"):
        print("Token not found")
        return

    application = Application.builder().token(cfg["token"]).build()
    telegram_bot = application.bot

    # Command handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help))
    application.add_handler(CommandHandler("report", report))

    # Message handlers
    application.add_handler(MessageHandler(filters.TEXT, text_event))
    application.add_error_handler(error)

    # Start the bot
    application.run_polling()


############################# MAIN #############################

imgapi = ImgAPI()
imgapi.setup(imgapi_config)
telegram_init(telegram_config)
