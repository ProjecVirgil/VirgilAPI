"""
    Main file for the API
"""
import datetime
import json
import os
import secrets
from typing import List
import functools
import re

from motor.motor_asyncio import AsyncIOMotorClient
from fastapi import FastAPI,HTTPException,Request
from pydantic import BaseModel
from fastapi.responses import JSONResponse
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware


# Take the url for connection to MongoDB
urlMongo = os.getenv('MONGO_URL')
urlMongo = "mongodb://mongo:FpziAXX6LxYZppYFZwVP@containers-us-west-101.railway.app:6626"
# Init the client of Mongo
client = AsyncIOMotorClient(urlMongo)

db = client.virgilUsers
users_collection = db.users
users_collection.create_index("userId", unique=True)
calendar_collection = db.calendarEvent
request_collection = db.user_request

limiter = Limiter(key_func=get_remote_address, default_limits=["5/minute"])
app = FastAPI()
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
app.add_middleware(SlowAPIMiddleware)



@app.get("/")
async def read_root():
    return {"message": "Server works"}

@app.get("/restricted")
async def read_restricted():
    return {"message": "Restricted"}

# ---------- UTILS FUNCTION ----------

async def validate_user(request:Request) -> bool:
    """
    This function is used in order to check if a user exists or not 
    and also to verify that it has access to this resource

    Args:
        request (Request): The request

    Returns:
        bool: True/False is valid or not
    """
    ip_request = request.client.host
    result_search = await request_collection.find_one({"ip": str(ip_request)},{"_id":0,"ip":0})  
      
    if result_search is None:
        await request_collection.insert_one(
            {
                "ip":str(ip_request),
                "count": 1
            }
        )
    else:
        if(result_search['count'] <= 5):
            query = {"ip": str(ip_request)}
            value = {"$set":  {
                    "ip":str(ip_request),
                    "count": result_search["count"] + 1
                }}
            
            await request_collection.update_one(
                query,
                value
            )
        else:
            return False
    return True
        
def sanitisation(text):
    """
    Sanitize a string by removing all special characters and spaces from it

    Args:
        text (_type_): The input for the sanitasion

    Returns:
        text: the text sanitazed
    """
    text = re.sub(r'[^a-zA-Z0-9#_!.+@]', '', text)
    if(len(text)> 100):
        text = text[:100]    
    return text

# Take the base of setting
@functools.lru_cache(maxsize=None)
def get_cached_setting():
    """
    Get all settings from database and cache it in memory

    Returns:
        json: The default settings
    """
    with open('setting_preset.json', 'r',encoding='utf-8') as file:
        return json.load(file)
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
# ---------- USER FUNCTION ----------

@app.get('/api/setting/{id_user}/', response_model=User)
async def get_user_settings(id_user: str):
    """
    A function to bring the user's setting through the generated key to Virgilio.    

     Raises:
        HTTPException: Error
    Returns:
        JsonResponse: the result of request
    """
    result = await users_collection.find_one({"userId": sanitisation(str(id_user))}, {"_id": 0, "userId": 0})
    if result is None:
        raise HTTPException(status_code=404, detail="User not found")
    user_dict = dict(result)
    return JSONResponse(content=user_dict, status_code=200)
    
@app.post('/api/setting/modify/{id_user}/', response_model=User)
async def new_setting(id_user: str, new_setting: dict):
    """
    This function updates all the setting of Virgil specifying the key of the user and
    sends a payload in json and skips the empty values.
    
    Returns:
        dict: Json format file       
    """
    id_user = sanitisation(id_user)
    updates = {f"setting.{key}": value for key, value in new_setting.items() if value != ""}
    query = {"userId": str(id_user)}
    value = {"$set": updates}
    await users_collection.update_many(query, value)
    return await get_user_settings(id_user)


@app.put('/api/createUser', response_model=User, status_code=201)
async def create_user(request: Request):
    """
    This function creates a new user which is entered into the database by the 
    simple random key generated randomly and the setting base    

    Returns:
        dict: The dict with the user id and the settings
    """
    
    if(await validate_user(request)):
        key = secrets.token_hex(16)
        await users_collection.insert_one({
            "userId": key,
            "setting": setting
        })
        return {"userId": key, "setting": setting}
    else:
        return {"Error":"Sorry, but you've run out of keys you can generate"}

# ---------- CALENDAR FUNCTION ----------

@app.get('/api/calendar/{id_user}/', response_model=dict)
async def get_events(id_user: str):
    """
    Get all the events from a user by the id

    Args:
        id (str): The id of user

    Raises:
        HTTPException: _description_

    Returns:
        list: List of events from the user
    """
    result = await calendar_collection.find_one({"userId": sanitisation(str(id_user))},{"_id":0,"userId":0})
    if result is None:
        raise HTTPException(status_code=404, detail="User not found")
    return result



@app.put('/api/calendar/createUser/{id_user}/', status_code=201)
async def create_user_calendar(id_user: str):
    """
    Create the profile in the db for manage the events of a user

    Args:
        id (str): id of user

    Returns:
        id_user: the id of user
    """
    await calendar_collection.insert_one({"userId": id_user}) # Prepare the user for give event
    return id_user


@app.put('/api/calendar/createEvent/{id_user}/{date}/', status_code=201)
async def create_event(id_user: str, date: str, events: List[str]):
    # Cambiato events: Event a events: List[str].
    """
    Create an event to save it into the database

    Args:
        id (str): The id of user
        date (str): the date of events
        events (List[str]): the description of events

    Returns:
        dict: The final result of modify
    """
    id_user = sanitisation(str(id_user))
    date = sanitisation(date)
    result = await calendar_collection.find_one({"userId": id_user}, {date: 1})
    query = {"userId": id_user}
    if result is None or date not in result:
        # Utilizziamo direttamente il payload JSON per l'aggiornamento
        value = {"$set": {date: events}}
        result = await calendar_collection.update_one(query, value)
    else:
        # Utilizziamo direttamente il payload JSON per l'aggiornamento
        value = {"$addToSet": {date: {"$each": events}}}
        result = await calendar_collection.update_many(query, value)  # Aggiungi evento
    return value

@app.put('/api/calendar/deleteEvent/{id_user}/', status_code=201)
async def delete_event(id_user: str):
    """
    Delete all old events from the day and update the collection.

    Args:
        id (str): id of user

    Returns:
        dict:Element deleted
    """
    yesterday = get_formatted_date()
    id_user = sanitisation(id_user)
    result = await calendar_collection.find_one({"userId": id_user})
    query = {"userId": id_user}
    if result is None or yesterday not in result:
        return {"Delete": "No events yesterday"}, 202
    value = {"$unset": {yesterday: 1}}
    result = await calendar_collection.update_one(query, value) # Add event
    return value
