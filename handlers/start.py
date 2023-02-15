from telegram.ext import CallbackContext, CommandHandler, Filters
from telegram import Update

from supabase import create_client, Client

import os
import json

import handlers.decorators
from classes.Ride import Ride

url: str = os.environ.get("SUPABASE_URL")
key: str = os.environ.get("SUPABASE_KEY")
channel_id: str = os.environ.get("TELEGRAM_CHANNEL")
supabase: Client = create_client(url, key)

initial_message = """Welcome to the Gatheride Bot! \nThis is a service that links you with other students to share cabs / carpool to school and home. We advise you to meet up at MRT locations / central malls to school. @erictisme

To create a ride, use the command /create"""


@handlers.decorators.save_user
def start(update: Update, context: CallbackContext):
  update.message.reply_text(initial_message)


def start_with_callbacks(update: Update, context: CallbackContext):
  user_id = str(update.effective_user["id"])
  username = update.effective_user["username"]
  callback_data = supabase.table("callbacks").select("*").eq(
    "id", context.args[0]).execute().data[0]
  data = json.loads(callback_data["data"])

  ride_id = str(data["ride_id"])
  ride = Ride(context.bot).load(ride_id)

  joined, error_text = ride.join_ride(user_id, username)

  if not joined:
    return update.message.reply_text(f"Error: {error_text}")

  update.message.reply_text("You have joined the ride")


start_handler_with_callbacks = CommandHandler(
  "start", start_with_callbacks,
  Filters.regex(
    r"[0-9a-fA-F]{8}\b-[0-9a-fA-F]{4}\b-[0-9a-fA-F]{4}\b-[0-9a-fA-F]{4}\b-[0-9a-fA-F]{12}"
  ))
start_handler = CommandHandler("start", start)
