# app/main/views.py

import requests
from flask import Flask, request
from flask import json
from app.linebot import linebot
from .. import csrf
LINE_API = 'https://api.line.me/v2/bot/message/reply'
CHANNEL_ID = '1567298753'
CHANNEL_SERECT = '45cdc818a4bf88dacbd4ff1ecea0c8c4'
MID = 'U1844ae791846a4f3a85f923543941b9b'
AUTHORIZATION = 'Bearer BDl3jAjUip3Y2j9tReJOodSDIdV7TxXVeGnAUnuzoviwQg5WwDipTFFxH+5dZuUKgUEa1ZEx/usWKxR8unDZZIbyl1IToO4HmkgvdzWLdNK39xwTpPV+1fwJ3qo2Zv6MLi6cChgO1ZIeF2BbpMwXDAdB04t89/1O/w1cDnyilFU='
headers = {
    'Content-Type': 'application/json; charset=UTF-8',
    'Authorization': AUTHORIZATION,
    'X-Line-ChannelID': CHANNEL_ID,
    'X-Line-ChannelSecret': CHANNEL_SERECT,
    'X-Line-Trusted-User-With-ACL': MID
    }

# *****************************************************************************************
# Create POST http://127.0.0.1:5000/api/v1.0/print
# *****************************************************************************************
@csrf.exempt
@linebot.route("/api", methods=['POST'])
def postMethod():  
    json_line = request.get_json()
    #print(json_line)
    json_line = json.dumps(json_line)
    decoded = json.loads(json_line)
    replytoken = decoded['events'][0]['replyToken']
    user = decoded['events'][0]['source']['userId']
    text = decoded['events'][0]['message']['text']
    #print("replaytoken : ",replytoken)
    #print("user : ",user)
    #print("content : ",text)
    if text == "hi":
        sendText(replytoken,user,"Hi dear, nice to meet you. command : product or story")
    elif text == 'product':
        sendproduct(replytoken,user)
    elif text == 'story':
        sendstory(replytoken,user)
    else:
        sendText(replytoken,user,"You could input 'hi' to me.")
    #sendText(replytoken,user,text)

    return ''

def sendstory(replytoken, user):

    data = json.dumps({
        "replyToken" : replytoken,
        "messages":[
                    {
                        "type":"text",
                        "text":"https://bytaiwan.me: Best product url"
                    },
                    {
                        "type": "image",
                        "originalContentUrl": "https://bytaiwan.me/static/story/images/23dc32acf023bbe35e27fd4c417ecda6.jpg",
                        "previewImageUrl": "https://bytaiwan.me/static/story/images/23dc32acf023bbe35e27fd4c417ecda6.jpg"
                    }
            ]

    })
    r = requests.post(LINE_API, headers=headers, data=data)  

def sendproduct(replytoken, user):

    data = json.dumps({
        "replyToken" : replytoken,
        "messages":[
                    {
                        "type":"text",
                        "text":"https://bytaiwan.me: Best product url"
                    },
                    {
                        "type": "image",
                        "originalContentUrl": "https://bytaiwan.me/static/story/images/23dc32acf023bbe35e27fd4c417ecda6.jpg",
                        "previewImageUrl": "https://bytaiwan.me/static/story/images/23dc32acf023bbe35e27fd4c417ecda6.jpg"
                    }
            ]

    })
    r = requests.post(LINE_API, headers=headers, data=data)   

def sendText(replytoken, user, text):

    data = json.dumps({
        "replyToken" : replytoken,
        "messages":[
                {
                "type":"text",
                "text":"https://bytaiwan.me: " + text
                }
            ]

    })
    r = requests.post(LINE_API, headers=headers, data=data)

# *****************************************************************************************
# Read GET http://127.0.0.1:5000/api/v1.0/print
# *****************************************************************************************
@linebot.route("/api", methods=['GET'])
def getMethod():  
    return json.dumps({"status": 200, "comment": "[ Get Method ] Hello World"})

# *****************************************************************************************
# Update PUT http://127.0.0.1:5000/api/v1.0/print
# *****************************************************************************************
@linebot.route("/api", methods=['PUT'])
def putMethod():  
    return json.dumps({"status": 200, "comment": "[ PUT Method ] Hello World"})

# *****************************************************************************************
# Delete DELETE http://127.0.0.1:5000/api/v1.0/print
# *****************************************************************************************
@linebot.route("/api", methods=['DELETE'])
def deleteMethod():  
    return json.dumps({"status": 200, "comment": "[ DELETE Method ] Hello World"})
    