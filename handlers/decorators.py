from supabase import create_client, Client
from telegram.ext import CallbackContext
from telegram import Update

from functools import lru_cache

import os
import logging

url: str = os.environ.get("SUPABASE_URL")
key: str = os.environ.get("SUPABASE_KEY")
supabase: Client = create_client(url, key)


def save_user(function):

  def wrapper(update: Update, context: CallbackContext):
    user_id = update.effective_user["id"]
    logging.info(f"Checking user availability: {user_id}")
    hasUser = get_user_data(user_id)

    if len(hasUser) == 0:
      logging.info(f"Saving user: {user_id}")
      chat_data = update.effective_user
      get_user_data.cache_clear()
      supabase.table("users").insert({
        "id": chat_data["id"],
        "first_name": chat_data["first_name"],
        "username": chat_data["username"],
        "last_name": chat_data["last_name"]
      }).execute()
    return function(update, context)

  return wrapper


@lru_cache(maxsize=32)
def get_user_data(user_id):
  logging.info(f"Fetching user {user_id}")
  return supabase.table("users").select("*").eq("id",
                                                str(user_id)).execute().data
