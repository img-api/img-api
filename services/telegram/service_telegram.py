import datetime
import hashlib
import json
import os
import threading

import requests

from config_telegram import imgapi_config, telegram_config
from telegram import (Bot, InlineKeyboardButton, InlineKeyboardMarkup,
                      ReplyKeyboardMarkup, ReplyKeyboardRemove, Update)
from telegram.ext import (Application, CallbackContext, CommandHandler,
                          ContextTypes, MessageHandler, filters)

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

        dev_id = self.props.get('dev_id', None)
        if (dev_id and dev_id in url) or 'TEST' in url:
            api_url = self.props.get('dev_api') + url
        else:
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


async def alarm(context: ContextTypes.DEFAULT_TYPE) -> None:
    """Send the alarm message."""
    job = context.job
    await context.bot.send_message(job.chat_id, text=f"Beep! {job.data} seconds are over!")


def remove_job_if_exists(name: str, context: ContextTypes.DEFAULT_TYPE) -> bool:
    """Remove job with given name. Returns whether job was removed."""
    current_jobs = context.job_queue.get_jobs_by_name(name)
    if not current_jobs:
        return False
    for job in current_jobs:
        job.schedule_removal()
    return True


async def set_timer(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Add a job to the queue."""
    chat_id = update.effective_message.chat_id
    try:
        # args[0] should contain the time for the timer in seconds
        due = float(context.args[0])
        if due < 0:
            await update.effective_message.reply_text("Sorry we can not go back to future!")
            return

        job_removed = remove_job_if_exists(str(chat_id), context)
        context.job_queue.run_once(alarm, due, chat_id=chat_id, name=str(chat_id), data=due)

        text = "Timer successfully set!"
        if job_removed:
            text += " Old one was removed."
        await update.effective_message.reply_text(text)

    except (IndexError, ValueError):
        await update.effective_message.reply_text("Usage: /set <seconds>")


async def unset(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Remove the job if the user changed their mind."""
    chat_id = update.message.chat_id
    job_removed = remove_job_if_exists(str(chat_id), context)
    text = "Timer successfully cancelled!" if job_removed else "You have no active timer."
    await update.message.reply_text(text)


async def timer(update: Update, context: ContextTypes.DEFAULT_TYPE):
    api_callback_for_bots(context.bot, update.effective_chat.id)


async def coms_send_notification(context, update, text):
    try:
        if isinstance(update, Update):
            chat_id = update.effective_chat.id

        if not chat_id:
            print(" Could not send message to None ")
            return

        await context.bot.send_message(chat_id=chat_id, text=text, parse_mode='HTML')
    except Exception as err:
        print(str(err))
        return

async def who_am_i(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """ Sends a request back to our server """

    result = imgapi.api_call("/telegram/who/" + str(update.effective_chat.id))
    user = result['user']

    hello = f"You are {user['first_name']} {user['last_name']} AKA {user['username']}\n"
    hello += f"What would you like to know?"

    await update.message.reply_text(hello)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Send a message when the command /start is issued."""
    global imgapi

    payload = ' '.join(context.args)
    try:
        if payload:
            result = imgapi.api_call("/telegram/register/" + payload + "/" + str(update.effective_chat.id))
            user = result['user']

            hello = f"Welcome! Hello {user['first_name']}\n"
            hello += f"You can now chat with us.\n"
            hello += f"Is there anything you would like to know?"

            print(hello)
            await coms_send_notification(context, update, hello)
            return
    except Exception as e:
        print(" CRASHED " + str(e))
        await coms_send_notification(
            context, update, '\n\nHi, Welcome to <i>HEADINGTOMARS.com</i> \n'
            'There was a problem talking to server about your registration, please try again later\n')
        return

    await coms_send_notification(
        context, update, '\n\nHi, Welcome to <i>HEADINGTOMARS.com</i> \n'
        'Type /help to get more help and a commands list!\n')


async def help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Send a message when the command /help is issued."""
    my_help = '\n\n<b>Help!</b>\n'
    my_help += "/report Your portfolio overview if registered\n"
    my_help += "/me Who are you ?\n"
    await coms_send_notification(context, update, my_help)


async def echo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Echo the user message."""
    await update.message.reply_text(update.message.text)


async def error(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Log Errors caused by Updates."""
    print(str(context.error))
    if not update:
        print(" ERROR ")
        return

    await coms_send_notification(context, update, "Error " + str(context.error))
    return


async def report(update: Update, context: ContextTypes.DEFAULT_TYPE):
    tmp = " <b>Report</b><pre>\n"
    tmp += "---------------------------------------------\n"
    tmp += "Chat ID <i>" + str(update.effective_chat.id) + "</i>"
    tmp += "</pre>\n"
    await coms_send_notification(context, update, tmp)
    return


def process_channel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.link == 'https://t.me/tothemoonstock':
        tmp = " Main channel message, hello world "
        return tmp

    tmp = "Hi, This is the bot for <i>HEADINGTOMARS.com</i> Where you will get news and stock market predictions.<br> If you added our bot by mistake, please just remove it from this channel."
    return tmp


async def text_event(update: Update, context: ContextTypes.DEFAULT_TYPE):

    if update.effective_chat.id < 0:
        msg = process_channel(update, context)
        if msg: await coms_send_notification(context, update, msg)
        return msg

    user = update.message.from_user
    print(update.effective_chat.title, f"{user.id}:: {update.message.text}")

    chat_id = update.effective_chat.id

    thinking_message = await context.bot.send_message(chat_id, "Thinking...")

    data = {
        'chat_id': chat_id,
        'message_id': thinking_message.message_id,
        'text': str(update.message.text),
    }

    result = imgapi.api_call("/telegram/chat/" + str(chat_id), data)

    if 'reply' in result:
        if 'message_id' in result:
            await context.bot.delete_message(chat_id, result['message_id'])

        await context.bot.send_message(chat_id, result['reply'])

    return None


def create_custom_context(bot: Bot) -> CallbackContext:
    # Create a mock update object or other parameters if needed
    context = CallbackContext(application=bot)
    return context


async def main_channel(context: ContextTypes.DEFAULT_TYPE) -> None:
    """Send the alarm message."""
    global imgapi
    data = context.job.data

    chat_id = data['tel_cfg']['main_channel_id']
    #await context.bot.send_message(chat_id, text=f"Beep! {data['name']} !")


async def chat_polling(context: ContextTypes.DEFAULT_TYPE) -> None:
    """Process all the messages."""
    global imgapi

    try:
        result = imgapi.api_call("/telegram/polling?telegram=1&TEST")
        if 'messages' not in result:
            return

        for msg in result['messages']:
            if not 'reply' in msg:
                continue

            chat_id = msg['chat_id']
            if 'message_id' in msg:
                await context.bot.delete_message(chat_id, msg['message_id'])

            await context.bot.send_message(chat_id, msg['reply'])
    except Exception as e:
        print(str(e))


def telegram_launch(cfg):
    if not cfg.get("token"):
        print("Token not found")
        return

    application = Application.builder().token(cfg["token"]).build()

    # Command handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help))
    application.add_handler(CommandHandler("report", report))
    application.add_handler(CommandHandler("set", set_timer))
    application.add_handler(CommandHandler("me", who_am_i))

    application.add_handler(CommandHandler("unset", unset))

    # Message handlers
    application.add_handler(MessageHandler(filters.TEXT, text_event))
    application.add_error_handler(error)

    # Create context to pull main channel from website / api
    context = create_custom_context(application)

    data = {'name': 'MAIN CHANNEL', 'tel_cfg': telegram_config, 'api_cfg': imgapi_config}
    context.job_queue.run_repeating(main_channel, 10.0, 1, name=str("Main Channel"), data=data)
    context.job_queue.run_repeating(chat_polling, 10.0, 5, name=str("Chat Polling"), data=data)

    # Start the bot
    application.run_polling()


############################# MAIN #############################

imgapi = ImgAPI()
imgapi.setup(imgapi_config)
telegram_launch(telegram_config)
