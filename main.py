import datetime
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import json
import secrets
from pymongo import MongoClient
import os
from fastapi.responses import JSONResponse
from typing import List 
# Take the url for connection to MongoDB
urlMongo = os.getenv('MONGO_URL')

# Init the client of Mongo
client = MongoClient(urlMongo)

db = client.virgilUsers
usersCollection = db.users
calendarCollection = db.calendarEvent
app = FastAPI()

# Take the base of setting
with open('setting.json', 'r') as f:
    setting = json.load(f)

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
    """
    key = secrets.token_hex(16)
    print(key)
    result = usersCollection.insert_one({
        "userId": key,
        "setting": setting
    })
    
    return {"userId": key, "setting": setting}

# ---------- CALENDAR FUNCTION ----------

@app.get('/api/calendar/{id}/', response_model=dict)
def get_events(id: str):
    """
    A function to bring the user's calendar through the generated key to Virgilio.    
    """
    result = calendarCollection.find_one({"userId": str(id)}, {"_id": 0, "userId": 0}) 
    if result is None:
        raise HTTPException(status_code=404, detail="User not found")
    return result

@app.put('/api/calendar/createUser/{id}/', status_code=201)
def create_user_calendar(id: str):
    calendarCollection.insert_one({"userId": id}) # Prepare the user for give event
    return id

@app.put('/api/calendar/createEvent/{id}/{date}/', status_code=201)
def create_event(id: str, date: str, events: List[str]):  # Cambiato events: Event a events: List[str]
    result = calendarCollection.find_one({"userId": id}, {date: 1}) 
    query = {"userId": id}
    if result is None or date not in result:
        value = {"$set": {date: events}}  # Utilizziamo direttamente il payload JSON per l'aggiornamento
        result = calendarCollection.update_one(query, value)
    else:
        value = {"$addToSet": {date: {"$each": events}}}  # Utilizziamo direttamente il payload JSON per l'aggiornamento
        result = calendarCollection.update_many(query, value)  # Aggiungi evento
    return value

@app.put('/api/calendar/deleteEvent/{id}/', status_code=201)
def delete_event(id: str):
    """
    A function to delete the old event automatically.    
    """
    
    today = datetime.datetime.today()
    yesterday = today.date() + datetime.timedelta(days=-1)
    yesterday = yesterday.strftime("%d-%m-%Y")
    yesterday = yesterday.split("-")
    yesterday[1] = yesterday[1].replace("0", "")
    yesterday = "-".join(yesterday)
    result = calendarCollection.find_one({"userId": id}) 
    print(yesterday)
    query = {"userId": id}
    if result is None or yesterday not in result:
        return {"Delete": "No events yesterday"}, 202
    else:
        value = {"$unset": {yesterday: 1}}
        result = calendarCollection.update_one(query, value) # Add event
    return value

