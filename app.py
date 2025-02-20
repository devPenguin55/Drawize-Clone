from flask import Flask, render_template, session, redirect, request, send_file
from flask_socketio import SocketIO, emit
import random as r
import math
import os


app = Flask(__name__)
app.secret_key = os.urandom(32)  # clears all sessions

socketio = SocketIO(app, cors_allowed_origins='*')

rooms = {} # server side storage of the inner working of the rooms
countdownPIDs = {}  # server side storage of time counting down processes
BYPASS_AUTH = False # enable this to join rooms and games without having created them (for debugging features)

if BYPASS_AUTH:
    rooms = {'NEEHOMA': {'owner': 'aarav', 'roundPointsUpdates':[], 'nextRoom': None, 'users': [], 'started': False, 'order': ['aarav', 'adsdfsdfsdfsdfsdfsdfsdfsdf', 'ad'], 'advanceRound': {'aarav': False, 'adsdfsdfsdfsdfsdfsdfsdfsdf': False, 'ad':False}, 'word': 'apple',
    'timeLeft': 90, 'stopTimeCountdown': {'aarav': False, 'adsdfsdfsdfsdfsdfsdfsdfsdf': False, 'ad':False}, 'usersWhoGuessedWordTime': {}, 'points': {'aarav': 0, 'adsdfsdfsdfsdfsdfsdfsdfsdf': 0, 'ad':0}, 'allowPointUpdate': False}}


with open('logs\\log.txt', "w+") as f:
    f.seek(0)
    f.truncate(0)
    f.seek(0)


def log(msg):
    with open('logs\\log.txt', "a") as f:
        f.write(msg+'\n')


def plainTextPage(text: str, link, linkText):
    return '''
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>lidi</title>
        <style>
            body {
                font-family: Arial, sans-serif;
                background-color: #f4f4f4;
                margin: 0;
                padding: 0;
                display: flex;
                justify-content: center;
                align-items: center;
                height: 100vh;
            }
            .container {
                text-align: center;
            }
            h1 {
                color: #333;
                font-size: 36px;
                margin-bottom: 20px;
            }
            p {
                color: #666;
                font-size: 18px;
            }
        </style>
        <style>
            .link {
                color: #93a782; /* Link color */
                text-decoration:none; /* Underline to mimic link */
                cursor: pointer; /* Change cursor to pointer on hover */
                font-size: 20px;
                margin-top: 40px;
            }
        </style>
    </head>
    <body>
        <div class="container">
            <h1>''' + text + '''</h1>
            <div class="link" onclick="window.location.href=\''''+link+'''\'">'''+linkText+'''</div>
        </div>
    </body>
    </html>
    '''


def removeUserFromRoom(username, room):
    if username in rooms[room]['users']:
        rooms[room]['users'].remove(username)


def getThreeWordsForSelection():  # 3-4 secs latency
    # url = "https://pictionary-charades-word-generator.p.rapidapi.com/pictionary"
    # words = []
    # for difficulty in r.sample(['easy', 'medium', 'hard'], 3):
    #     querystring = {"difficulty":difficulty}

    #     headers = {
    #         "x-rapidapi-key": "8531fa116cmsh0e92361f6545a6cp14ac80jsnb94c6ef1912f",
    #         "x-rapidapi-host": "pictionary-charades-word-generator.p.rapidapi.com"
    #     }

    #     response = requests.get(url, headers=headers, params=querystring)
    #     print(response.json())
    #     words.append(response.json()['word'])
    testWords = [
        "strawberry",
        "eclipse",
        "chandelier",
        "ketchup",
        "toothpaste",
        "rainbow",
        "beehive",
        "lemon",
        "wreath",
        "waffles",
        "bubble",
        "whistle",
        "snowball",
        "bouquet",
        "headphones",
        "fireworks",
        "igloo",
        "lawnmower",
        "summer",
        "whisk",
        "cupcake",
        "bruise",
        "fog",
        "crust",
        "battery"
    ]

    words = r.sample(testWords, 3)
    return words


def calculatePointsForRoom(room):
    if not rooms[room]['allowPointUpdate']:
        return

    log(f'Calculating points for room {room}, previous points: {rooms[room]['points']}')

    currentArtist = rooms[room]['order'][math.floor(session['round']-1)]

    normalizedGuessScoresDict = {}
    for user_ in rooms[room]['usersWhoGuessedWordTime']:
        normalizedGuessScoresDict[user_] = 30 * \
            (rooms[room]['usersWhoGuessedWordTime'][user_]/90)
    expectedGuessesMade = len(rooms[room]['users']) - 1
    actualGuessesMade = len(normalizedGuessScoresDict)


    if normalizedGuessScoresDict:
        maxPointsOfUsers = max(normalizedGuessScoresDict.values())
        summedGuessScores = sum(normalizedGuessScoresDict.values())
    else:
        maxPointsOfUsers = 30/expectedGuessesMade
        summedGuessScores = 0
        for user_ in rooms[room]['users']:
            if user_ != currentArtist:
                normalizedGuessScoresDict[user_] = 0

    if not maxPointsOfUsers:
        maxPointsOfUsers = 30/expectedGuessesMade
    artistScore = summedGuessScores - maxPointsOfUsers * (expectedGuessesMade - actualGuessesMade)

    for user in rooms[room]['users']:
        if user == currentArtist:
            rooms[room]['points'][currentArtist] += round(artistScore)
        else:
            if normalizedGuessScoresDict.get(user, 0):
                rooms[room]['points'][user] += round(normalizedGuessScoresDict.get(user, 0) * 0.6)
            else:
                rooms[room]['points'][user] += round(-30/expectedGuessesMade)
    rooms[room]['allowPointUpdate'] = False
    log(f'    -> Finished calculating points for room {room}, new points: {rooms[room]['points']}')
    

def getNewRoomCode():
    def generateRandomRoomCode():
        chars = 'QWERTYUIOPASDFGHJKLZXCVBNM'
        code = ''
        for _ in range(6):
            code += r.choice(chars)
        return code

    roomCode = generateRandomRoomCode()
    while roomCode in rooms.keys():
        roomCode = generateRandomRoomCode()
    return roomCode

# routes


@app.route('/')
def homePage():
    if session.get('room'):
        sessionRoom = session['room']
        if (sessionRoom in rooms) and (session['username'] in rooms[sessionRoom]['users']):
            if rooms[sessionRoom]['started']:
                return redirect('/gameWait')
            else:
                return redirect(f'/room')

    session['username'] = None
    session['inRoom'] = False
    session['room'] = ''
    session['round'] = None
    return send_file("home.html")


@app.route("/getValidRoomCode")
def getValidRoomCode():
    return getNewRoomCode()

# @app.route('/drawing')
# def drawing():
#     return render_template("drawing.html", word='word', username='aarav', room='NEEHOMA')
# @app.route('/guessing')
# def guessing():
#     return render_template("guessing.html", username='aarav', artist='hesdfsdfsdfsdfsdfsfsdfsdfsd', room='NEEHOMA')


@app.route("/processJoinRoom", methods=['POST'])
def processJoinRoom():
    if session.get('room'):
        sessionRoom = session['room']
        if (sessionRoom in rooms) and (session['username'] in rooms[sessionRoom]['users']):
            if rooms[sessionRoom]['started']:
                return redirect('/gameWait')
            else:
                return redirect(f'/room')

    session['username'] = None
    session['inRoom'] = False
    session['room'] = ''
    session['round'] = None
    room = request.form['joinRoomName']
    username = request.form['username'].strip()

    if room in rooms:
        if username in rooms[room]['users']:
            return plainTextPage('Username already in room', '/', 'Try another?')
        if rooms[room]['started']:
            return plainTextPage('Game has already started', '/', 'Try another?')

        session['username'] = username
        session['inRoom'] = True
        session['room'] = room
        rooms[room]['points'][username] = 0
        rooms[room]['users'].append(username)
        return redirect(f'/room')
    else:
        return plainTextPage('Room does not exist', '/', 'Try another?')


@app.route("/processCreateRoom", methods=['POST'])
def processCreateRoom():
    if session.get('room'):
        sessionRoom = session['room']
        if (sessionRoom in rooms) and (session['username'] in rooms[sessionRoom]['users']):
            if rooms[sessionRoom]['started']:
                return redirect('/gameWait')
            else:
                return redirect(f'/room')
    session['username'] = None
    session['inRoom'] = False
    session['room'] = ''
    session['round'] = None
    room = request.form['createRoomName']
    username = request.form['username'].strip()

    if room not in rooms:
        session['username'] = username
        session['inRoom'] = True
        session['room'] = room
        rooms[room] = {'owner': username, 'roundPointsUpdates':[], 'nextRoom': None, 'users': [username], 'started': False, 'order': None, 'advanceRound': {}, 'stopTimeCountdown': {}, 'usersWhoGuessedWord': [], 'usersWhoGuessedWordTime': {}, 'points': {username: 0}, 'allowPointUpdate':False}
        return redirect(f'/room')
    else:
        return plainTextPage('Room already exists', '/', 'Try another?')


@app.route("/room")
def lobbyForRoom():
    # ! delete this:
    if not session.get('username'):
        if BYPASS_AUTH:
            if 'aarav' not in rooms['NEEHOMA']['users']:
                session['username'] = 'aarav'
            elif 'adsdfsdfsdfsdfsdfsdfsdfsdf' not in rooms['NEEHOMA']['users']:
                session['username'] = 'adsdfsdfsdfsdfsdfsdfsdfsdf'
            else:
                session['username'] = 'ad'
            rooms['NEEHOMA']['users'].append(session['username'])
            session['inRoom'] = True
            session['room'] = 'NEEHOMA'
            session['round'] = None
        else: 
            return plainTextPage('You are not in a room', '/', 'Join one?')

        

        

    room = session['room']
    if room not in rooms.keys():
        return plainTextPage("Room doesn't exist", '/', 'Make one?')
    elif not room:
        return plainTextPage("Link invalid", '/', 'Try again?')
    elif not session.get('inRoom'):
        return plainTextPage("You are not in the room yet", '/', 'Enter it?')
    elif rooms[room]['started']:
        return redirect('/gameWait')

    username = session.get('username')
    roomOwner = rooms[room]['owner']
    return render_template('lobby.html', room=room, roomOwner=roomOwner, users=rooms[room]['users'], userIsOwner=(username == roomOwner), username=username)


@app.route('/gameWait')
def gameWait():
    # ! delete this:
    if not session.get('username'):
        if BYPASS_AUTH:
            if 'aarav' not in rooms['NEEHOMA']['users']:
                session['username'] = 'aarav'
            elif 'adsdfsdfsdfsdfsdfsdfsdfsdf' not in rooms['NEEHOMA']['users']:
                session['username'] = 'adsdfsdfsdfsdfsdfsdfsdfsdf'
            else:
                session['username'] = 'ad'
            rooms['NEEHOMA']['users'].append(session['username'])
            session['inRoom'] = True
            session['room'] = 'NEEHOMA'
            session['round'] = None
            rooms[session['room']]['started'] = True
        else: 
            return plainTextPage('You are not in a room', '/', 'Join one?')

        

    if session.get('inRoom'):
        if rooms[session['room']]['started']:
            room = session['room']
            username = session['username']
            rooms[room]['stopTimeCountdown'][username] = False

            if session['round'] == None:
                session['round'] = 1
            else:
                if rooms[room]['advanceRound'][username]:
                    rooms[room]['advanceRound'][username] = False
                    session['round'] += 0.5
            print(session)
            curRound = session['round']
            orderClients = rooms[room]['order']
            # round starts at 1 so add one to length to compensate
            if len(orderClients) + 1 == curRound:
                # rounds over
                return redirect('/gameOverFinalScreen')

            owner = rooms[room]['owner']
            currentArtist = orderClients[math.floor(curRound)-1]

            # a whole number of rounds = pick word + wait, otherwise draw + guess
            if curRound == math.floor(curRound):
                # select word or wait
                sortedUsers = sorted([[i, rooms[room]['points'][i]] for i in rooms[room]
                                     ['users']], key=lambda x: rooms[room]['points'][x[0]], reverse=True)
                if username == currentArtist:
                    # select word
                    word1, word2, word3 = getThreeWordsForSelection()
                    return render_template("gameWait.html", username=username, isArtist=True, users=sortedUsers, room=room, totalRounds=len(orderClients), curRound=int(curRound), word1=word1, word2=word2, word3=word3, artist=currentArtist)
                else:
                    # wait for artist to select word
                    return render_template("gameWait.html", username=username, isArtist=False, users=sortedUsers, room=room, totalRounds=len(orderClients), curRound=int(curRound), artist=currentArtist)
            else:
                word = rooms[room]['word']
                if username == currentArtist:
                    # draw word
                    return render_template("drawing.html", word=word, room=room, username=username)
                elif username in rooms[room]['usersWhoGuessedWord']:
                    # watch others guess the word
                    return render_template("guessingNoTyping.html", artist=currentArtist, room=room, username=username)
                else:
                    # guess the word
                    return render_template("guessing.html", artist=currentArtist, room=room, username=username)
        else:
            return plainTextPage('The game has not started yet', '/room', 'Return to room?')
    else:
        return plainTextPage('You are not in a room', '/', 'Join one?')


@app.route('/gameOverFinalScreen')
def gameOverFinalScreen():
    if session.get('inRoom'):
        if rooms[session['room']]['started']:
            room = session['room']
            username = session['username']
            rooms[room]['stopTimeCountdown'][username] = False
            curRound = session['round']
            if len(rooms[room]['order']) + 1 == curRound:
                sortedUsers = sorted([[i, rooms[room]['points'][i]] for i in rooms[room]
                                     ['users']], key=lambda x: rooms[room]['points'][x[0]], reverse=True)

                return render_template("gameOverScreen.html", room=room, username=username, leaderboard=sortedUsers)

            else:
                return plainTextPage('The game has not ended yet', '/gameWait', 'Return to game?')
        else:
            return plainTextPage('The game has not started yet', '/room', 'Return to room?')
    else:
        return plainTextPage('You are not in a room', '/', 'Join one?')


@app.route('/playAgainRoom')
def playAgainRoom():
    if session.get('username') and session.get('room') and session.get('inRoom'):
        room = session['room']
        if rooms[room]['started']:
            if session['round'] - 1 == len(rooms[room]['order']) and rooms[room].get('nextRoom'):
                rooms[room]['advanceRound'] = {}
                rooms[room]['stopTimeCountdown'][session['username']] = True
                rooms[room]['usersWhoGuessedWord'] = []
                rooms[room]['usersWhoGuessedWordTime'] = {}
                for process in list(countdownPIDs.keys()):
                    if countdownPIDs[process] == [room, session['username']]:
                        del countdownPIDs[process]

                removeUserFromRoom(session['username'], room)

                newRoom = rooms[room]['nextRoom']

                session['inRoom'] = True
                session['room'] = newRoom
                session['round'] = None

                if newRoom not in rooms:
                    rooms[newRoom] = {'owner': session['username'], 'roundPointsUpdates':[], 'nextRoom': None, 'users': [session['username']], 'started': False, 'order': None, 'advanceRound': {}, 'stopTimeCountdown': {}, 'usersWhoGuessedWord': [], 'usersWhoGuessedWordTime': {}, 'points': {session['username']: 0}, 'allowPointUpdate': False}
                else:
                    rooms[newRoom]['points'][session['username']] = 0
                    rooms[newRoom]['users'].append(session['username'])

                return redirect('/room')
            else:
                return redirect('/gameWait')
        else:
            return redirect('/gameWait')
    else:
        return plainTextPage('You are not in a room', '/', 'Join one?')


@app.route('/leaveRoom')
def leaveRoom():
    if session.get('username') and session.get('room') and session.get('inRoom'):
        room = session['room']
        if session['round'] - 1 == len(rooms[room]['order']):
            rooms[room]['advanceRound'] = {}
            rooms[room]['stopTimeCountdown'][session['username']] = True
            rooms[room]['usersWhoGuessedWord'] = []
            rooms[room]['usersWhoGuessedWordTime'] = {}
            for process in list(countdownPIDs.keys()):
                if countdownPIDs[process] == [room, session['username']]:
                    del countdownPIDs[process]

            removeUserFromRoom(session['username'], room)

            session['username'] = None
            session['inRoom'] = False
            session['room'] = ''
            session['round'] = None
            return redirect('/')
        else:
            return redirect('/gameWait')
    else:
        return plainTextPage('You are not in a room', '/', 'Join one?')

# drawing


@socketio.on('connect')
def handleConnect():
    print('User Connected')
    emit('giveNewClientImage', broadcast=True)


@socketio.on('fullImage')
def sendFullImage(image):
    print("Sending full image")
    emit('fullImage', image, broadcast=True)


@socketio.on('newPacket')
def sendPacket(packet):
    emit('guessingClientsNewPacket', packet, broadcast=True)

# lobby (rooms)


@socketio.on('lobbyConnect')
def handleLobbyConnect(data):
    emit('addUserToVisualLobbyList', data, broadcast=True)


@socketio.on('lobbyDisconnect')
def handleLobbyDisconnect(data):
    username, room = data['username'], data['room']
    removeUserFromRoom(username, room)
    if rooms[room]['owner'] == username:
        if rooms[room]['users']:
            rooms[room]['owner'] = r.choice(rooms[room]['users'])
            emit('changeRoomOwner', {
                 'room': room, 'newRoomOwner': rooms[room]['owner']}, broadcast=True)
    if not rooms[room]['users']:
        del rooms[room]

    session['username'] = None
    session['inRoom'] = False
    session['room'] = ''
    session['round'] = None

    emit('removeUserFromVisualLobbyList', data, broadcast=True)


@socketio.on('startGame')
def handleStartGame(data):
    room = data['room']
    rooms[room]['started'] = True
    rooms[room]['timeLeft'] = 90
    rooms[room]['order'] = r.sample(rooms[room]['users'], len(
        rooms[room]['users'])) + r.sample(rooms[room]['users'], len(rooms[room]['users']))
    emit('lobbyClientsSwitchToGameWait', room, broadcast=True)


@socketio.on('nextPhaseOfGame')
def handleNextPhaseOfGame(data):
    global countdownPIDs
    room = data['room']

    word = data['word']
    rooms[room]['word'] = word
    rooms[room]['timeLeft'] = 90
    rooms[room]['usersWhoGuessedWord'] = []
    rooms[room]['usersWhoGuessedWordTime'] = {}
    print(rooms[room])
    for user in rooms[room]['users']:
        rooms[room]['advanceRound'][user] = True
        rooms[room]['stopTimeCountdown'][user] = False

    for process in list(countdownPIDs.keys()):
        user_, room_ = countdownPIDs[process]
        if room_ == room:
            del countdownPIDs[process]

    emit('gameClientsSwitchToGameWait', room, broadcast=True)


@socketio.on('startTimeCountdown')
def handleStartTimeCountdownForClient(data):
    room = data['room']
    username = data['username']
    timeLeft = rooms[room]['timeLeft']
    if not countdownPIDs.keys():
        selfPID = 0
        countdownPIDs[selfPID] = [room, username]  # last one is active
    else:
        selfPID = list(countdownPIDs.keys())[-1] + 1
        countdownPIDs[selfPID] = [room, username]

    selfPIDContent = countdownPIDs[selfPID]

    for PID in list(countdownPIDs.keys()):
        if PID != selfPID:
            if PID in countdownPIDs:
                room_, username_ = countdownPIDs[PID]
                if room_ == room and username_ == username:
                    if selfPID > PID:
                        # delete the older process for being too old
                        print(f'\nDeleting other time countdown process | PID: {
                              PID}, data: {selfPIDContent}, selfPID: {selfPID}\n')
                        del countdownPIDs[PID]
            else:
                return

    print('\nStarting time countdown', data, timeLeft, 'secs left', '\n')

    minutes = timeLeft // 60
    secs = timeLeft % 60

    secs = f"{secs:02}"
    emit('updateTimeCountdown', {
         'room': room, 'username': username, 'timeLeft': f"{minutes}:{secs}"})

    while timeLeft > 0 and not rooms[room]['stopTimeCountdown'][username] and selfPID in countdownPIDs:
        socketio.sleep(1)
        timeLeft -= 1

        minutes = timeLeft // 60
        secs = timeLeft % 60

        secs = f"{secs:02}"
        emit('updateTimeCountdown', {
             'room': room, 'username': username, 'timeLeft': f"{minutes}:{secs}"})
        rooms[room]['timeLeft'] = timeLeft

    if selfPID in countdownPIDs:
        print(f'\nDeleting time countdown process | selfPID {selfPID}, data: {selfPIDContent}\n')
        del countdownPIDs[selfPID]
    else:
        print(f'\nTime countdown process deleted by other process | selfPID {selfPID}, data: {selfPIDContent}\n')
    if timeLeft <= 0:
        # if have gotten to this place, the round will end due to not all ppl guessing it
        print(f'\n\n\nTIME ELAPSED {rooms[room]['allowPointUpdate']}\n\n\n')
        if session['round'] not in rooms[room]['roundPointsUpdates']:
            for user in rooms[room]['users']:
                rooms[room]['advanceRound'][user] = True
                rooms[room]['stopTimeCountdown'][user] = False
            rooms[room]['allowPointUpdate'] = True
            calculatePointsForRoom(room)
            rooms[room]['allowPointUpdate'] = False
            rooms[room]['roundPointsUpdates'].append(session['round'])
            emit('endRound', {'room': room}, broadcast=True)
        else:
            rooms[room]['allowPointUpdate'] = False
        


@socketio.on('processGuess')
def processGuess(data):
    data['guess'] = ' '.join(
        [i for i in data['guess'].strip().lower().split(' ') if i])
    room, username, guess = data['room'], data['username'], data['guess']
    if guess == rooms[room]['word']:
        # user got the word right
        rooms[room]['usersWhoGuessedWord'].append(username)
        rooms[room]['usersWhoGuessedWordTime'][username] = rooms[room]['timeLeft']
        # -1 because the artist can't guess
        if len(rooms[room]['usersWhoGuessedWord']) == len(rooms[room]['users'])-1:
            # all users have answered it
            for user in rooms[room]['users']:
                rooms[room]['advanceRound'][user] = True
                rooms[room]['stopTimeCountdown'][user] = True

            rooms[room]['allowPointUpdate'] = True
            calculatePointsForRoom(room)
            rooms[room]['nextRoom'] = getNewRoomCode()
            for process in list(countdownPIDs.keys()):
                if countdownPIDs[process][0] == room:
                    del countdownPIDs[process]
            emit('endRound', {'room': room}, broadcast=True)
        else:
            emit('userGuessedWord', {'room': room,
                 'username': username}, broadcast=True)

    else:
        emit('animateNewGuess', data, broadcast=True)


if __name__ == '__main__':
    # socketio.run(app, host='0.0.0.0', port=8000, allow_unsafe_werkzeug=True, debug=False)
    socketio.run(app, host='192.168.0.87', port=5000, allow_unsafe_werkzeug=True, debug=False)
