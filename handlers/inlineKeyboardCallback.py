from telegram.ext import CallbackContext, CallbackQueryHandler
from telegram import Update
from supabase import create_client, Client

import handlers.decorators
import handlers.createRide
from classes.Ride import Ride

import os
import json

url: str = os.environ.get("SUPABASE_URL")
key: str = os.environ.get("SUPABASE_KEY")
supabase: Client = create_client(url, key)


@handlers.decorators.save_user
def handle_callback(update: Update, context: CallbackContext):
  query = update.callback_query
  user_id = str(update.effective_user["id"])
  username = update.effective_user["username"]

  callback_data = supabase.table("callbacks").select("*").eq(
    "id", query.data).execute().data[0]
  data = json.loads(callback_data["data"])

  if callback_data["type"] == "join":
    ride_id = str(data["ride_id"])
    ride = Ride(context.bot).load(ride_id)

    joined, error_text = ride.join_ride(user_id, username)

    if not joined:
      return query.answer(error_text)
    return query.answer(
      "You have joined successfully. The ride creator has been notified")

  if callback_data["type"] == "leave":
    ride_id = str(data["ride_id"])
    ride = Ride(context.bot).load(ride_id)

    joined, error_text = ride.leave_ride(user_id, username)

    if not joined:
      return query.answer(error_text)
    return query.answer("You have successfully left the ride")

  if callback_data["type"] == "cancel":
    data = json.loads(callback_data["data"])
    ride_id = str(data["ride_id"])
    ride = Ride(context.bot).load(ride_id)

    ride.cancel_ride()
    success, failed = ride.message_all_riders(
      text="Your ride has been cancelled by the ride creator.",
      exclude_creator=True)

    main_text = "Your ride has been cancelled. "

    if len(failed) > 0:
      failed_usernames = [ticket["rider_username"] for ticket in failed]
      username_list = [f"@{username}" for username in failed_usernames]
      username_text = "\n".join(username_list)
      main_text += f"The bot could not reach the following riders. We would greatly appreciate if you could inform them that the ride has been cancelled\n{username_text}"

    query.message.edit_text(main_text, reply_markup=None)

    query.answer()


inline_callback_handler = CallbackQueryHandler(handle_callback)
