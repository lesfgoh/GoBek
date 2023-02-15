from telegram.ext import CallbackContext, MessageHandler, Filters
from telegram import Update


def debug(update: Update, context: CallbackContext):
  print(update)


debug_handler = MessageHandler(Filters.all, debug)
