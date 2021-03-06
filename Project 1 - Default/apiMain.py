# NAME: Marek Sautter
# PROF: Kenytt Avery
# CLSS: CPSC 476
# DATE: 26 September
# PROJ: 1 - Flask Forum API

# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
import json, sqlite3, sys
from flask import Flask, jsonify, request, make_response
from flask.cli import AppGroup
from flask_basicauth import BasicAuth
from datetime import datetime

app = Flask(__name__)
app.config['JSON_SORT_KEYS'] = False
basic_auth = BasicAuth(app)
databaseName = 'database.db'

# < HELPER FUNCTIONS --------------------------------------------------
@app.cli.command('init_db')
def init_db():                
    # ALTERED CODE BASED ON FLASK DOC : http://flask.pocoo.org/docs/0.12/tutorial/dbinit/           
    try:
        conn = sqlite3.connect(databaseName)
        with app.open_resource('init.sql', mode='r') as f:
            conn.cursor().executescript(f.read())
        conn.commit()
        print("Database file created as {}".format(str(databaseName)))
    except:
        print("Failed to create {}".format(str(databaseName)))
        sys.exit()
app.cli.add_command(init_db)

def connectDB(dbName):  
    # Connects to database and returns the connection, if database is offline, program exits
    try:
        conn = sqlite3.connect(dbName)
        print("SUCCESS: CONNECTED TO {}".format(str(dbName)))
        return conn
    except:
        print("ERROR: {} OFFLINE".format(str(dbName)))
        sys.exit()

def checkUser(cur, user_name, pass_word):
    # Simple log in check for the authorization username and password
    if user_name == '' or pass_word == '':
        return False
    cur.execute("SELECT * FROM Users WHERE username='{}'".format(str(user_name)))
    user = cur.fetchone()
    if user == None:
        return False
    elif user[0] == str(user_name) and user[1] == str(pass_word):
        return True
    return False

def fixDate(my_date):   
    # Reads the raw string date, creates date object, and returns correct format
    new_date = datetime.strptime(my_date,'%Y-%m-%d %H:%M:%S.%f')
    return new_date.strftime('%a, %d %b %Y %H:%M:%S GMT')

def compareDates(prevDate, nextDate):
    # Finds the most recent date, used for finding most recent date out of posts
    prevDate = datetime.strptime(str(prevDate),'%Y-%m-%d %H:%M:%S.%f')
    nextDate = datetime.strptime(str(nextDate),'%Y-%m-%d %H:%M:%S.%f')
    if prevDate <= nextDate:
        return nextDate
    return prevDate 

# HELPER FUNCTIONS />---------------------------------------------------
       
@app.route('/forums', methods=['GET'])
def get_forums():
    conn = connectDB(databaseName)
    cur = conn.cursor()
    responseJSON = []
    cur.execute("SELECT * FROM forums")
    forumsSQL = cur.fetchall()
    if forumsSQL == []:
        # Returns an empty array if no forums have been created
        conn.close()
        return make_response(jsonify(forumsSQL), 200)
    for forum in forumsSQL:
        responseJSON.append({'id': forum[0], 'name': forum[1], 'creator': forum[2]}) 
    conn.close()   
    return make_response(jsonify(responseJSON), 200)
    
@app.route('/forums', methods=['POST'])
# @basic_auth.required 
def add_forum():
    auth = request.authorization
    conn = connectDB(databaseName)
    cur = conn.cursor()
    login = checkUser(cur, auth.username.lower(), auth.password)
    if login:
        requestJSON = request.get_json(force=True)
        cur.execute("SELECT * FROM forums WHERE forum_title='{}'".format(str(requestJSON['name'])))
        forumsSQL = cur.fetchall()
        if forumsSQL != []:
            conn.close()
            return make_response("FORUM ALREADY EXISTS", 409)
        cur.execute("INSERT INTO forums(forum_title,creator) VALUES (?,?)",(str(requestJSON['name']), str(auth.username)))
        conn.commit()
        cur.execute("SELECT * FROM forums WHERE forum_title='{}'".format(str(requestJSON['name'])))
        newForum = cur.fetchone()
        conn.close()
        # Location header field set to /forums/<forum_id> for new id
        return make_response("SUCCESS: FORUM CREATED", 201, {"location" : '/forums/' + str(newForum[0])})
    conn.close()
    return make_response("ERROR: Unsuccessful Login / Unauthorized", 401)

@app.route('/forums/<int:forum_id>', methods=['GET'])
def get_threads(forum_id):
    conn = connectDB(databaseName)
    cur = conn.cursor()
    responseJSON = []
    cur.execute("SELECT * FROM threads WHERE forum_id={}".format(str(forum_id)))
    threadsSQL = cur.fetchall()
    if threadsSQL == []:
        return make_response("NOT FOUND", 404)

    # I know this is probably a dumb way to get the most recent date but I'm not a
    # Database genius so I'm just gonna stick with my poorly optimized nested for loop
    for thread in threadsSQL:
        cur.execute("SELECT * FROM posts WHERE thread_id='{}'".format(str(thread[1])))
        postList = cur.fetchall()
        if postList == []:
            responseJSON.append({'id': thread[1], 'title': thread[2], 'creator': thread[4], 'timestamp': fixDate(str(thread[5]))})
        else:
            newestDate = "2000-01-01 01:00:00.000000"
            for post in postList:
                newestDate = compareDates(newestDate, str(post[5]))
            responseJSON.append({'id': thread[1], 'title': thread[2], 'creator': thread[4], 'timestamp': fixDate(str(newestDate))})
    conn.close()
    # Threads are listed in reverse chronological order (by date? or by id? I'm gonna go with date)  ¯\_(ツ)_/¯
    responseJSON = sorted(responseJSON, key=lambda k: k['timestamp'], reverse=True) 
    return make_response(jsonify(responseJSON), 200)

@app.route('/forums/<int:forum_id>', methods=['POST'])
# @basic_auth.required 
def add_thread(forum_id):
    auth = request.authorization
    requestJSON = request.get_json(force=True)
    currentTime = str(datetime.now())
    conn = connectDB(databaseName)
    cur = conn.cursor()
    login = checkUser(cur, auth.username.lower(), auth.password)
    if login:
        cur.execute("SELECT * FROM forums WHERE forum_id={}".format(str(forum_id)))
        forumsSQL = cur.fetchall()
        if forumsSQL == []:
            conn.close()
            return make_response("NOT FOUND", 404)
        cur.execute("INSERT INTO threads(forum_id, creator, thread_title, thread_text, thread_time) VALUES (?,?,?,?,?)",(forum_id, str(auth.username), requestJSON['title'], requestJSON['text'], currentTime))
        conn.commit()
        cur.execute("SELECT * FROM threads WHERE thread_title='{}'".format(str(requestJSON['title'])))
        newThread = cur.fetchone()
        conn.close()
        return make_response("SUCCESS: THREAD CREATED", 201, {"location" : '/forums/{}/{}'.format(str(newThread[0]), str(newThread[1]))})
    conn.close()
    return make_response("ERROR: Unsuccessful Login / Unauthorized", 401)

@app.route('/forums/<int:forum_id>/<int:thread_id>', methods=['GET'])
# @basic_auth.required 
def get_posts(forum_id, thread_id):
    conn = connectDB(databaseName)
    cur = conn.cursor()
    responseJSON = []

    # DUMB WAY OF CHECKING TO MAKE SURE THE THREAD/FORUM EXISTS BUT ¯\_(ツ)_/¯
    cur.execute("SELECT * FROM forums WHERE forum_id={}".format(str(forum_id)))
    forumsSQL = cur.fetchall()
    if forumsSQL == []:
        conn.close()
        return make_response("NOT FOUND", 404)
    cur.execute("SELECT * FROM threads WHERE thread_id={}".format(str(thread_id)))
    threadsSQL = cur.fetchone()
    if threadsSQL == None:
        conn.close()
        return make_response("NOT FOUND", 404)
    else:
        responseJSON.append({'author':threadsSQL[4], 'text': threadsSQL[3], 'timestamp': fixDate(threadsSQL[5])})
    cur.execute("SELECT * FROM posts WHERE forum_id={} AND thread_id={}".format(str(forum_id), str(thread_id)))
    postsSQL = cur.fetchall()
    if postsSQL == []:
        return make_response(jsonify(responseJSON), 200)
    for post in postsSQL:
        responseJSON.append({'author': post[3], 'text': post[4], 'timestamp': fixDate(post[5])})
    conn.close()
    return make_response(jsonify(responseJSON), 200)

@app.route('/forums/<int:forum_id>/<int:thread_id>', methods=['POST'])
# @basic_auth.required 
def add_post(forum_id, thread_id):
    conn = connectDB(databaseName)
    cur = conn.cursor()
    auth = request.authorization
    requestJSON = request.get_json(force=True)
    currentTime = str(datetime.now())
    login = checkUser(cur, auth.username.lower(), auth.password)
    if login:
        cur.execute("SELECT * FROM forums WHERE forum_id='{}'".format(str(forum_id)))
        forumsSQL = cur.fetchall()
        if forumsSQL == []:
            conn.close()
            return make_response("NOT FOUND", 404)
        cur.execute("SELECT * FROM threads WHERE thread_id='{}'".format(str(thread_id)))
        threadsSQL = cur.fetchall()
        if threadsSQL == []:
            conn.close()
            return make_response("NOT FOUND", 404)
        cur.execute("INSERT INTO posts(forum_id, thread_id, author, post_text, post_time) VALUES (?,?,?,?,?)",(forum_id, thread_id, str(auth.username), requestJSON['text'], currentTime))
        conn.commit()
        conn.close()
        return make_response("SUCCESS: POST CREATED", 201)
    conn.close()
    return make_response("ERROR: Unsuccessful Login / Unauthorized", 401)

@app.route('/users', methods=['POST'])
def add_user():
    requestJSON = request.json
    username = requestJSON['username'].lower()
    password = requestJSON['password']
    conn = connectDB(databaseName)
    cur = conn.cursor()
    cur.execute("SELECT * FROM users WHERE username='{}'".format(str(username)))
    user = cur.fetchone()
    if user != None:
        conn.close()
        return make_response("CONFLICT: USER EXISTS", 409)
    cur.execute("INSERT INTO users(username, password) VALUES (?,?)",(str(username), str(password)))
    conn.commit()
    conn.close()
    return make_response("SUCCESS: USER CREATED", 201)

@app.route('/users', methods=['PUT'])
# @basic_auth.required   
def change_password():
    auth = request.authorization
    requestJSON = request.json
    username = requestJSON['username'].lower()
    password = requestJSON['password']
    if username != auth.username.lower():
        return make_response("CONFLICT: USERNAME NOT EQUAL", 409)
    conn = connectDB(databaseName)
    cur = conn.cursor()
    login = checkUser(cur, auth.username.lower(), auth.password)
    if login:
        cur.execute("SELECT * FROM users WHERE username = '{}'".format(str(username)))
        user = cur.fetchall()
        if user == []:
            conn.close()
            return make_response("NOT FOUND", 404)
        cur.execute("UPDATE users SET password= '{}' WHERE username= '{}'".format(str(password), str(username)))
        conn.commit()
        conn.close()
        return make_response("SUCCESS: PASSWORD CHANGED", 200)
    conn.close()
    return make_response("ERROR: Unsuccessful Login / Unauthorized", 401)

if __name__ == '__main__':
    app.run(debug=True)

app.run()