# https://docs.python-telegram-bot.org/en/v13.14/
import os
import logging
from telegram.ext import Updater, CallbackContext, CommandHandler, Filters

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, utils
import handlers.createRide
import handlers.start
import handlers.debug
import handlers.inlineKeyboardCallback

TELEGRAM_SECRET = os.environ['TELEGRAM_TOKEN']
channel_id: str = os.environ.get("TELEGRAM_CHANNEL")

logging.basicConfig(
  format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
  level=logging.INFO)

eh = "check-this-out"


def sendSampleRide(update: Update, context: CallbackContext):
  keyboard = [
    [
      InlineKeyboardButton("Join",
                           url=utils.helpers.create_deep_linked_url(
                             context.bot.username, eh)),
    ],
  ]

  reply_markup = InlineKeyboardMarkup(keyboard)

  context.bot.sendMessage(
    channel_id,
    "(This will be posted in the group)\nWant to share a ride? \nTo: NTU\nFrom:Bedok\nSeat remaining: 2",
    reply_markup=reply_markup)


def joinRide(update: Update, context: CallbackContext):
  update.message.reply_text(
    "You have joined the ride, the ride creator has been notified")


sample_handler = CommandHandler("sample", sendSampleRide)

another_start_handler = CommandHandler("start", joinRide, Filters.regex(eh))


def main() -> None:
  updater = Updater(token=TELEGRAM_SECRET, use_context=True)
  dispatcher = updater.dispatcher
  dispatcher.add_handler(another_start_handler)
  dispatcher.add_handler(handlers.start.start_handler_with_callbacks)
  dispatcher.add_handler(handlers.start.start_handler)
  dispatcher.add_handler(sample_handler)
  dispatcher.add_handler(handlers.createRide.create_ride_handler)
  dispatcher.add_handler(
    handlers.inlineKeyboardCallback.inline_callback_handler)
  updater.start_polling()
  updater.idle()


if __name__ == '__main__':
  main()
