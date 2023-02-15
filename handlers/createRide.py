from telegram.ext import CallbackContext, CommandHandler, ConversationHandler, MessageHandler, Filters
from telegram import Update, ParseMode

import logging
import os

from supabase import create_client, Client

import handlers.decorators
from classes.Ride import Ride

url: str = os.environ.get("SUPABASE_URL")
key: str = os.environ.get("SUPABASE_KEY")
channel_id: str = os.environ.get("TELEGRAM_CHANNEL")
supabase: Client = create_client(url, key)

create_ride_copy = """
*Creating ride*
To create a ride, first key in your pick up location

_E\.g\., Bedok MRT taxi stand_
"""


@handlers.decorators.save_user
def initialize_ride(update: Update, context: CallbackContext) -> None:
  update.message.reply_text(create_ride_copy, parse_mode=ParseMode.MARKDOWN_V2)
  logging.info(update.message.chat.username)

  context.user_data["created_by"] = update.message.chat.username
  context.user_data["created_by_id"] = update.message.chat.id

  return "awaiting from"


def receive_from(update: Update, context: CallbackContext) -> None:
  update.message.reply_text("Where will you be going?")
  context.user_data["pickup"] = update.message.text
  return "awaiting destination"


def receive_destination(update: Update, context: CallbackContext) -> None:
  update.message.reply_text("When?")
  context.user_data["destination"] = update.message.text
  return "awaiting time"


def receive_time(update: Update, context: CallbackContext) -> None:
  update.message.reply_text("How many seats are left in the ride?")
  context.user_data["time"] = update.message.text
  return "awaiting seats"


def receive_seat(update: Update, context: CallbackContext) -> None:

  context.user_data["seats"] = int(update.message.text) + 1
  user_id = update.effective_user["id"]
  username = update.effective_user["username"]

  ride_id = Ride.create(context.user_data["seats"],
                        context.user_data["created_by"],
                        context.user_data["pickup"],
                        context.user_data["destination"],
                        context.user_data["time"],
                        context.user_data["created_by_id"])

  ride = Ride(context.bot).load(ride_id)
  ride.publish_to_group()
  ride.join_ride(user_id, username, False)
  ride.ride_created_successfully()

  return ConversationHandler.END


def seat_error(update: Update, context: CallbackContext) -> None:
  update.message.reply_text("Please send a number between 1 and 7 inclusive")


create_ride_handler = ConversationHandler(
  [CommandHandler("create", initialize_ride)], {
    "awaiting from": [MessageHandler(Filters.text, receive_from)],
    "awaiting destination":
    [MessageHandler(Filters.text, receive_destination)],
    "awaiting time": [MessageHandler(Filters.text, receive_time)],
    "awaiting seats": [
      MessageHandler(Filters.regex("^([1-7])$"), receive_seat),
      MessageHandler(~Filters.regex("^([1-7])$"), seat_error)
    ],
  }, [])
