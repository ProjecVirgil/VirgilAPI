"""
    Main file for the API
"""
import datetime
import json
import secrets
import os
from typing import List
import functools

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from pymongo import MongoClient
from fastapi.responses import JSONResponse

# Take the url for connection to MongoDB
urlMongo = os.getenv('MONGO_URL')

# Init the client of Mongo
client = MongoClient(urlMongo)

db = client.virgilUsers
users_collection = db.users
users_collection.create_index("userId", unique=True)
calendar_collection = db.calendarEvent

app = FastAPI()

# Take the base of setting
@functools.lru_cache(maxsize=None)
def get_cached_setting():
    """
    Get all settings from database and cache it in memory

    Returns:
        json: The default settings
    """
    with open('setting.json', 'r',encoding='utf-8') as file:
        return json.load(file)

# Modifica la chiamata nel codice originale
setting = get_cached_setting()

# User Model
class User(BaseModel):
    """
    User model used in this API

    Args:
        BaseModel (Class): The base model
    """
    userId: str
    setting: dict

# Event Model
class Event(BaseModel):
    """
    Event model used in this API

    Args:
        BaseModel (Class): The base model
    """
    date: str
    events: dict


# ---------- USER FUNCTION ----------

@app.get('/api/setting/{id_user}/', response_model=User)
def get_user_settings(id_user: str):
    """
    A function to bring the user's setting through the generated key to Virgilio.    

     Raises:
        HTTPException: Error
    Returns:
        JsonResponse: the result of request
    """
    result = users_collection.find_one({"userId": str(id_user)}, {"_id": 0, "userId": 0})
    if result is None:
        raise HTTPException(status_code=404, detail="User not found")
    user_dict = dict(result)
    return JSONResponse(content=user_dict, status_code=200)

def check_email_pass(list_of_events):
    """
    A function that checks whether a list contains an email and password or not

    Args:
        list (list): An list of data

    Returns:
        bool: False or None
    """
    for i in list_of_events:
        if i == "":
            return False

@app.post('/api/setting/modify/{id_user}/', response_model=User)
def new_setting(id_user: str, new_setting: dict):
    """
    This function updates all the setting of Virgil specifying the key of the user and
    sends a payload in json and skips the empty values.
    
    Returns:
        dict: Json format file       
    """
    updates = {f"setting.{key}": value for key, value in new_setting.items() if value != ""}
    query = {"userId": str(id_user)}
    value = {"$set": updates}
    users_collection.update_many(query, value)
    return get_user_settings(id_user)


# ---- CALENDAR ----
@app.put('/api/createUser', response_model=User, status_code=201)
def create_user():
    """
    This function creates a new user which is entered into the database by the 
    simple random key generated randomly and the setting base    

    Returns:
        dict: The dict with the user id and the settings
    """

    key = secrets.token_hex(16)
    users_collection.insert_one({
        "userId": key,
        "setting": setting
    })

    return {"userId": key, "setting": setting}

# ---------- CALENDAR FUNCTION ----------

@app.get('/api/calendar/{id_user}/', response_model=dict)
def get_events(id_user: str):
    """
    Get all the events from a user by the id

    Args:
        id (str): The id of user

    Raises:
        HTTPException: _description_

    Returns:
        list: List of events from the user
    """
    result = calendar_collection.find_one({"userId": str(id_user)},{"_id":0,"userId":0})
    if result is None:
        raise HTTPException(status_code=404, detail="User not found")
    return result

@app.put('/api/calendar/createUser/{id_user}/', status_code=201)
def create_user_calendar(id_user: str):
    """
    Create the profile in the db for manage the events of a user

    Args:
        id (str): id of user

    Returns:
        id_user: the id of user
    """
    calendar_collection.insert_one({"userId": id_user}) # Prepare the user for give event
    return id_user

@app.put('/api/calendar/createEvent/{id_user}/{date}/', status_code=201)
def create_event(id_user: str, date: str, events: List[str]):
    # Cambiato events: Event a events: List[str]
    """
    Create an event to save it into the database

    Args:
        id (str): The id of user
        date (str): the date of events
        events (List[str]): the description of events

    Returns:
        dict: The final result of modify
    """

    result = calendar_collection.find_one({"userId": id_user}, {date: 1})
    query = {"userId": id_user}
    if result is None or date not in result:
        # Utilizziamo direttamente il payload JSON per l'aggiornamento
        value = {"$set": {date: events}}
        result = calendar_collection.update_one(query, value)
    else:
        # Utilizziamo direttamente il payload JSON per l'aggiornamento
        value = {"$addToSet": {date: {"$each": events}}}
        result = calendar_collection.update_many(query, value)  # Aggiungi evento
    return value


def get_formatted_date():
    """
    Get today's format date

    Returns:
        str: The date formatted
    """
    today = datetime.datetime.today()
    yesterday = today.date() + datetime.timedelta(days=-1)
    yesterday = yesterday.strftime("%d-%m-%Y")
    yesterday = yesterday.split("-")
    yesterday[1] = int(yesterday[1])
    yesterday[1] = str(yesterday[1])
    yesterday[0] = int(yesterday[0])
    yesterday[0] = str(yesterday[0])
    yesterday = "-".join(yesterday)

    return yesterday

@app.put('/api/calendar/deleteEvent/{id_user}/', status_code=201)
def delete_event(id_user: str):
    """
    Delete all old events from the day and update the collection

    Args:
        id (str): id of user

    Returns:
        dict:Element deleted
    """
    yesterday = get_formatted_date()
    result = calendar_collection.find_one({"userId": id_user})
    query = {"userId": id_user}
    if result is None or yesterday not in result:
        return {"Delete": "No events yesterday"}, 202
    value = {"$unset": {yesterday: 1}}
    result = calendar_collection.update_one(query, value) # Add event
    return value
