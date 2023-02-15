from supabase import create_client, Client

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, ParseMode, utils

import os
import json
import logging

url: str = os.environ.get("SUPABASE_URL")
key: str = os.environ.get("SUPABASE_KEY")
channel_id: str = os.environ.get("TELEGRAM_CHANNEL")
supabase: Client = create_client(url, key)


def can_join_ride(tickets, ride_data, user_id):
  valid_tickets = [
    ticket for ticket in tickets
    if not ticket["invalidated"] and ticket["rider"] == user_id
  ]
  if len(valid_tickets) != 0:
    return False, "You are already in this ride"
  return True, ""


def can_leave_ride(tickets, ride_data, user_id):
  valid_tickets = [
    ticket for ticket in tickets
    if not ticket["invalidated"] and ticket["rider"] == user_id
  ]
  if len(valid_tickets) == 0:
    return False, "You cannot leave if you are not a rider"

  return True, ""


class Ride:

  def __init__(self, bot):
    self.is_loaded_ride = False
    self.bot = bot
    self.ride_id = ""
    self.ride_data = {}
    self.tickets = []

  def load(self, ride_id):
    self.ride_id = ride_id
    ride_data = supabase.table("rides").select("*").eq("id", ride_id).execute()
    self.ride_data = ride_data.data[0]

    existing_tickets = supabase.table("tickets").select("*").eq(
      "ride", self.ride_id).execute()
    self.tickets = existing_tickets.data
    self.is_loaded_ride = True
    return self

  def generate_ride_message(self):
    if not self.is_loaded_ride:
      logging.error("Ride is not loaded")
      return False, "Unknown error has occurred"

    created_by = self.ride_data["created_by"]
    pickup = self.ride_data["pickup"]
    destination = self.ride_data["destination"]
    time = self.ride_data["time"]

    usernames = [user["rider_username"] for user in self.get_valid_tickets()]
    seats_remaining = self.get_seats_remaining()
    username_list = [f"@{username}" for username in usernames]
    username_text = "\n".join(username_list)

    message = f"created by: {created_by} \nPickup: {pickup} \nDestination: {destination} \nTime: {time} \nSeats remaining: {seats_remaining} \nRiders:\n{username_text}"

    reply_markup = self.generate_ride_reply_markup()

    return message, reply_markup

  def generate_ride_reply_markup(self):
    if self.ride_data["cancelled"]:
      return None

    join_callback = self.get_join_callback()
    leave_callback = self.get_leave_callback()
    seats_remaining = self.get_seats_remaining()

    keyboard = [[]]

    if seats_remaining != 0:
      keyboard[0].append(
        InlineKeyboardButton("Join", callback_data=join_callback))

    keyboard[0].append(
      InlineKeyboardButton("Leave", callback_data=leave_callback))

    reply_markup = InlineKeyboardMarkup(keyboard)

    return reply_markup

  def join_ride(self,
                user_id,
                username,
                send_notification=True) -> (bool, str):
    if not self.is_loaded_ride:
      logging.error("Ride is not loaded")
      return False, "Unknown error has occurred"

    joinable, error_text = can_join_ride(self.tickets, self.ride_data, user_id)

    if not joinable:
      return False, error_text

    new_ticket = supabase.table("tickets").insert({
      "rider": user_id,
      "ride": self.ride_id,
      "rider_username": username
    }).execute().data[0]

    self.tickets.append(new_ticket)

    message, reply_markup = self.generate_ride_message()
    if send_notification:
      self.send_to_ride_creator(f"@{username} wants to join your ride")
    self.edit_posted_message(text=message, reply_markup=reply_markup)

    logging.info(f"Rider {username} joined ride {self.ride_id}")

    return True, ""

  def leave_ride(self, user_id, username):
    if not self.is_loaded_ride:
      logging.error("Ride is not loaded")
      return False, "Unknown error has occurred"

    joinable, error_text = can_leave_ride(self.tickets, self.ride_data,
                                          user_id)

    if not joinable:
      return False, error_text

    self.invalidate_tickets(user_id)

    message, reply_markup = self.generate_ride_message()
    self.send_to_ride_creator(f"@{username} has left your ride")
    self.edit_posted_message(text=message, reply_markup=reply_markup)

    logging.info(f"Rider {username} left ride {self.ride_id}")

    return True, ""

  def cancel_ride(self):
    if (self.ride_data["cancelled"]):
      logging.error("Trying to cancel a cancelled ride")
      return False
    supabase.table("rides").update({
      "cancelled": "true"
    }).eq("id", self.ride_id).execute()

    self.ride_data["cancelled"] = "true"

    message, reply_markup = self.generate_ride_message()

    final_message = f"*Cancelled*\n{message}"

    self.edit_posted_message(text=final_message,
                             reply_markup=None,
                             parse_mode=ParseMode.MARKDOWN_V2)
    return True

  def message_all_riders(self, exclude_creator=False, *args, **kwargs):
    valid_tickets = self.get_valid_tickets()
    sent_tickets = []
    rejected_tickets = []
    for ticket in valid_tickets:
      if (exclude_creator
          and ticket["rider"] == self.ride_data["created_by_id"]):
        continue
      id = ticket["rider"]
      username = ticket["rider_username"]
      try:
        self.bot.send_message(chat_id=id, *args, **kwargs)
        sent_tickets.append(ticket)
      except:
        logging.info(f"Attempt to send message to {username} has failed")
        rejected_tickets.append(ticket)
    return sent_tickets, rejected_tickets

  def ride_created_successfully(self):

    cancel_callback_id = self.get_cancel_callback()

    keyboard = [[
      InlineKeyboardButton("Cancel ride", callback_data=cancel_callback_id)
    ]]

    reply_markup = InlineKeyboardMarkup(keyboard)
    ride_url = self.generate_join_ride_url()

    self.send_to_ride_creator(
      f"Okay\! Your ride has been sent in the group\! You will receive notification when someone wants to join\.\nOr you can share this link \n`{ride_url}`",
      reply_markup=reply_markup,
      parse_mode=ParseMode.MARKDOWN_V2)

    return True

  def send_to_ride_creator(self, *args, **kwargs) -> bool:
    if not self.is_loaded_ride:
      logging.error("Ride is not loaded")
      return False

    ride_creator_id = self.ride_data["created_by_id"]
    self.bot.send_message(ride_creator_id, *args, **kwargs)

    return True

  def edit_posted_message(self, *args, **kwargs):
    if not self.is_loaded_ride:
      logging.error("Ride is not loaded")
      return False
    posted_message_id = self.ride_data["posted_message_id"]
    self.bot.edit_message_text(*args,
                               chat_id=channel_id,
                               message_id=posted_message_id,
                               **kwargs)
    return True

  def get_valid_tickets(self):
    return [ticket for ticket in self.tickets if not ticket["invalidated"]]

  def get_seats_remaining(self):
    valid_tickets = self.get_valid_tickets()
    return self.ride_data["seats"] - len(valid_tickets)

  def get_join_callback(self):
    if self.ride_data["join_callback"] != None:
      return self.ride_data["join_callback"]
    join_row = supabase.table("callbacks").insert({
      "type":
      "join",
      "data":
      json.dumps({"ride_id": self.ride_id})
    }).execute().data[0]

    supabase.table("rides").update({
      "join_callback": join_row["id"]
    }).eq("id", self.ride_id).execute()

    self.ride_data["join_callback"] = join_row["id"]
    return join_row["id"]

  def get_leave_callback(self):
    if self.ride_data["leave_callback"] != None:
      return self.ride_data["leave_callback"]
    leave_row = supabase.table("callbacks").insert({
      "type":
      "leave",
      "data":
      json.dumps({"ride_id": self.ride_id})
    }).execute().data[0]

    supabase.table("rides").update({
      "leave_callback": leave_row["id"]
    }).eq("id", self.ride_id).execute()

    self.ride_data["leave_callback"] = leave_row["id"]

    return leave_row["id"]

  def get_cancel_callback(self):
    if self.ride_data["cancel_callback"] != None:
      return self.ride_data["cancel_callback"]
    cancel_row = supabase.table("callbacks").insert({
      "type":
      "cancel",
      "data":
      json.dumps({"ride_id": self.ride_id})
    }).execute().data[0]

    supabase.table("rides").update({
      "cancel_callback": cancel_row["id"]
    }).eq("id", self.ride_id).execute()

    self.ride_data["cancel_callback"] = cancel_row["id"]
    return cancel_row["id"]

  def invalidate_tickets(self, user_id):
    new_tickets = []
    for ticket in self.tickets:
      if ticket["invalidated"]:
        new_tickets.append(ticket)
        continue

      if ticket["rider"] != user_id:
        new_tickets.append(ticket)
        continue

      modified_ticket = supabase.table("tickets").update({
        "invalidated": "true"
      }).eq("id", ticket["id"]).execute().data[0]

      new_tickets.append(modified_ticket)

    self.tickets = new_tickets

  def publish_to_group(self):
    if self.ride_data["posted_message_id"] != None:
      return logging.error("Attempted to post a ride twice")

    message, reply_markup = self.generate_ride_message()
    message = self.bot.send_message(chat_id=channel_id,
                                    text=message,
                                    reply_markup=reply_markup)

    ride = supabase.table("rides").update({
      "posted_message_id":
      message.message_id
    }).eq("id", self.ride_id).execute().data[0]

    self.ride_data = ride

  def generate_join_ride_url(self):
    join_callback = self.get_join_callback()

    join_url = utils.helpers.create_deep_linked_url(self.bot.username,
                                                    join_callback)
    return join_url

  @staticmethod
  def create(seats, created_by, pickup, destination, time, created_by_id):
    row_data = {
      "seats": seats,
      "created_by": created_by,
      "pickup": pickup,
      "destination": destination,
      "time": time,
      "created_by_id": created_by_id
    }
    ride = supabase.table("rides").insert(row_data).execute().data[0]
    return ride["id"]
