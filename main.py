import datetime
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import json
import secrets
from pymongo import MongoClient
import os
from fastapi.responses import JSONResponse
from typing import List 
import functools




# Take the url for connection to MongoDB
urlMongo = os.getenv('MONGO_URL')

# Init the client of Mongo
client = MongoClient(urlMongo)

db = client.virgilUsers
usersCollection = db.users
usersCollection.create_index("userId", unique=True)
calendarCollection = db.calendarEvent

app = FastAPI()



# Take the base of setting
@functools.lru_cache(maxsize=None)
def get_cached_setting():
    with open('setting.json', 'r') as f:
        return json.load(f)

# Modifica la chiamata nel codice originale
setting = get_cached_setting()

# User Model
class User(BaseModel):
    userId: str
    setting: dict

# Event Model
class Event(BaseModel):
    date: str
    events: dict


# ---------- USER FUNCTION ----------

@app.get('/api/setting/{id}/', response_model=User)
def get_user(id: str):
    """
    A function to bring the user's setting through the generated key to Virgilio.    
    
     Raises:
        HTTPException: _description_
    Returns:
        _type_: _description_
    """
    result = usersCollection.find_one({"userId": str(id)}, {"_id": 0, "userId": 0})
    if result is None:
        raise HTTPException(status_code=404, detail="User not found")
    user_dict = dict(result)
    return JSONResponse(content=user_dict, status_code=200)
def checkEmailPass(list):
    for i in list:
        if i == "":
            return False

@app.post('/api/setting/modify/{id}/', response_model=User)
def new_setting(id: str, newSetting: dict):
    """
    This function updates all the setting of Virgil specifying the key of the user and
    sends a payload in json and skips the empty values.
    
    Returns:
        _type_: _description_       
    """
    
    updates = {f"setting.{key}": value for key, value in newSetting.items() if value != ""}
    query = {"userId": str(id)}
    value = {"$set": updates}
    usersCollection.update_many(query, value)
    return get_user(id)



# ---- CALENDAR ----
@app.put('/api/createUser', response_model=User, status_code=201)
def create_user():
    """
    This function creates a new user which is entered into the database by the simple random key generated randomly and the setting base    
    

    Returns:
        _type_: _description_
    """

    key = secrets.token_hex(16)
    usersCollection.insert_one({
        "userId": key,
        "setting": setting
    })
    
    return {"userId": key, "setting": setting}

# ---------- CALENDAR FUNCTION ----------

@app.get('/api/calendar/{id}/', response_model=dict)
def get_events(id: str):
    """_summary_

    Args:
        id (str): _description_

    Raises:
        HTTPException: _description_

    Returns:
        _type_: _description_
    """
    result = calendarCollection.find_one({"userId": str(id)},{"_id":0,"userId":0})
    if result is None:
        raise HTTPException(status_code=404, detail="User not found")
    return result

@app.put('/api/calendar/createUser/{id}/', status_code=201)
def create_user_calendar(id: str):
    """_summary_

    Args:
        id (str): _description_

    Returns:
        _type_: _description_
    """
    calendarCollection.insert_one({"userId": id}) # Prepare the user for give event
    return id

@app.put('/api/calendar/createEvent/{id}/{date}/', status_code=201)
def create_event(id: str, date: str, events: List[str]):  # Cambiato events: Event a events: List[str]
    """_summary_

    Args:
        id (str): _description_
        date (str): _description_
        events (List[str]): _description_

    Returns:
        _type_: _description_
    """
    
    result = calendarCollection.find_one({"userId": id}, {date: 1}) 
    query = {"userId": id}
    if result is None or date not in result:
        value = {"$set": {date: events}}  # Utilizziamo direttamente il payload JSON per l'aggiornamento
        result = calendarCollection.update_one(query, value)
    else:
        value = {"$addToSet": {date: {"$each": events}}}  # Utilizziamo direttamente il payload JSON per l'aggiornamento
        result = calendarCollection.update_many(query, value)  # Aggiungi evento
    return value


def getFormatDate():
    """_summary_

    Returns:
        _type_: _description_
    """
    today = datetime.datetime.today()
    yesterday = today.date() + datetime.timedelta(days=-1)
    yesterday = yesterday.strftime("%d-%m-%Y")
    yesterday = yesterday.split("-")
    yesterday[1] = yesterday[1].replace("0", "")
    if("0" == yesterday[0][0]):
        yesterday[0] = yesterday[0].lstrip('0')
    yesterday = "-".join(yesterday)
    
    return yesterday

@app.put('/api/calendar/deleteEvent/{id}/', status_code=201)
def delete_event(id: str):
    """_summary_

    Args:
        id (str): _description_

    Returns:
        _type_: _description_
    """
    yesterday = getFormatDate()
    result = calendarCollection.find_one({"userId": id}) 
    query = {"userId": id}
    if result is None or yesterday not in result:
        return {"Delete": "No events yesterday"}, 202
    else:
        value = {"$unset": {yesterday: 1}}
        result = calendarCollection.update_one(query, value) # Add event
    return value

