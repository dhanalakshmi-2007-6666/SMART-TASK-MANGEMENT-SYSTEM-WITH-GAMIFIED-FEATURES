from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify
import re
import sqlite3
import smtplib
from email.message import EmailMessage
import random
from datetime import datetime, timedelta
from datetime import date
import joblib
from pywebpush import webpush
import json
import threading
import time
import os
from werkzeug.utils import secure_filename
from ollama_ai import ask_ai
sqlite3.register_adapter(datetime, lambda val: val.isoformat())
sqlite3.register_converter("DATETIME", lambda b: datetime.fromisoformat(b.decode()))
try:
    ML_MODEL = joblib.load("delay_predictor.pkl")
    print("ML model loaded")
except:
    ML_MODEL = None
    print("ML model not found")
app = Flask(__name__)
subscriptions = []
app.secret_key = "my_super_secret_key_123"
UPLOAD_FOLDER = os.path.join(app.root_path, 'static', 'uploads')
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
def init_db():
    con = sqlite3.connect("task.db")
    cur = con.cursor()
    cur.execute('''CREATE TABLE IF NOT EXISTS users_main(
                    email TEXT PRIMARY KEY,
                    password TEXT,
                    otp TEXT,
                    otpex DATETIME,
                    name TEXT,
                    mobile TEXT,
                    gender TEXT,
                    coins INTEGER DEFAULT 0
                )''')
    cur.execute('''CREATE TABLE IF NOT EXISTS adds__task(
                id integer primary key autoincrement,
                email text,
                taskname TEXT,
                des TEXT,
                from_date DATE,
                to_date DATE,
                filename TEXT,
                filetype TEXT,
                status TEXT DEFAULT 'pending',
                completed_date DATE,
                earned_coins INTEGER DEFAULT 0
                )''')
    cur.execute('''
    CREATE TABLE IF NOT EXISTS dailys_task(
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    email TEXT,
    taskname TEXT,
    description TEXT,
    task_time TEXT
    )
    ''')
    cur.execute('''
    CREATE TABLE IF NOT EXISTS coin_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    email TEXT,
    task_name TEXT,
    coins INTEGER,
    earned_date DATE
    )
    ''')
    cur.execute('''
    CREATE TABLE IF NOT EXISTS gift_requests (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    email TEXT,
    name TEXT,
    phone TEXT,
    address TEXT,
    coins INTEGER,
    request_date DATE,
    status TEXT DEFAULT 'pending'
    )
    ''')
    cur.execute('''
    CREATE TABLE IF NOT EXISTS chat_history(
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    email TEXT,
    user_msg TEXT,
    bot_reply TEXT,
    time DATETIME
    )
    ''')
    cur.execute('''
    CREATE TABLE IF NOT EXISTS user_energy(
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    email TEXT,
    energy TEXT,
    date DATE
    )
    ''')

    con.commit()
    con.close()
def analyze_user(email):
    con = sqlite3.connect("task.db")
    cur = con.cursor()

    cur.execute("""
        SELECT taskname, from_date, to_date, completed_date
        FROM adds__task
        WHERE email=? AND status='completed'
        ORDER BY completed_date DESC
        LIMIT 20
    """, (email,))
    tasks = cur.fetchall()
    con.close()

    if not tasks:
        return "User has not completed enough tasks yet."

    total_days = 0
    for t in tasks:
        start = datetime.strptime(t[1], "%Y-%m-%d")
        end = datetime.strptime(t[3], "%Y-%m-%d")
        total_days += (end - start).days

    avg_days = total_days / len(tasks)

    return f"""
    User recently completed {len(tasks)} tasks.
    Average completion time: {avg_days:.1f} days.
    """
@app.route("/",methods=["GET","POST"])
def index():
    return render_template("login.html")
@app.route("/create",methods=["GET","POST"])
def create():
    if request.method == "POST":
        try:
            name = request.form['name']
            gender = request.form['gender'].lower()
            email= request.form['email']
            password = request.form['confirmpassword']
            mobile= request.form['mobile']
            if len(password) < 10 or not re.search("[A-Z]", password) or not re.search("[a-z]", password) or not re.search("[!@#$%^&*(),.?]", password):
                flash("Password must have 10+ chars, uppercase, lowercase, and special char.", "danger")
                return redirect(url_for("create"))

            con = sqlite3.connect("task.db")
            cur = con.cursor()
            cur.execute('INSERT INTO users_main(email, password, otp, otpex, name, mobile, gender) VALUES (?, ?, ?, ?, ?, ?, ?)',
                        (email, password, '', '', name, mobile,gender))
            con.commit()
            con.close()
            flash("Account created successfully!", "success")
            return redirect(url_for("login"))
        except Exception as e:
            print(e)
            flash("Error creating account. Email might already exist.", "danger")
            return redirect(url_for("create"))
    return render_template("create.html")
# @app.route("/welcome")
# def welcome():
#     if 'email' not in session:
#         return redirect(url_for("login"))

#     email = session['email']
#     today = datetime.now().date()

#     con = sqlite3.connect("task.db")
#     cur = con.cursor()
#     cur.execute("SELECT COUNT(*) FROM adds__task WHERE email=?", (email,))
#     total_tasks = cur.fetchone()[0]
#     cur.execute("""
#         SELECT COUNT(*) FROM adds__task
#         WHERE email=? AND DATE(to_date) < ?
#     """, (email, today))
#     completed = cur.fetchone()[0]
#     cur.execute("""
#         SELECT COUNT(*) FROM adds__task
#         WHERE email=? AND DATE(to_date) >= ?
#     """, (email, today))
#     pending = cur.fetchone()[0]
#     cur.execute("""
#         SELECT COUNT(*) FROM adds__task
#         WHERE email=? AND DATE(to_date) < ?
#     """, (email, today))
#     overdue = cur.fetchone()[0]
#     cur.execute("""
#         SELECT taskname
#         FROM dailys_task
#         WHERE email=? AND task_date=?
#     """, (email, today))
#     today_tasks = cur.fetchall()

#     con.close()

#     return render_template(
#         "welcome.html",
#         name=session['name'],
#         total_tasks=total_tasks,
#         completed=completed,
#         pending=pending,
#         overdue=overdue,
#         today_tasks=today_tasks
#     )
@app.route("/welcome")
def welcome():
    if 'email' not in session:
        return redirect(url_for("login"))

    email = session['email']
    today = datetime.now().date()

    con = sqlite3.connect("task.db")
    cur = con.cursor()

    # Total
    cur.execute("SELECT COUNT(*) FROM adds__task WHERE email=?", (email,))
    total_tasks = cur.fetchone()[0]

    # Completed
    cur.execute("SELECT COUNT(*) FROM adds__task WHERE email=? AND status='completed'", (email,))
    completed = cur.fetchone()[0]

    # Pending
    cur.execute("""SELECT COUNT(*) FROM adds__task
                   WHERE email=? AND status='pending' AND DATE(to_date)>=?""",
                (email, today))
    pending = cur.fetchone()[0]

    # Overdue
    cur.execute("""SELECT COUNT(*) FROM adds__task
                   WHERE email=? AND status='pending' AND DATE(to_date)<?""",
                (email, today))
    overdue = cur.fetchone()[0]

    # Today daily tasks
    cur.execute("SELECT * FROM dailys_task WHERE email=?", (session['email'],))
    today_tasks = cur.fetchall()

    con.close()
    overloaded, hours, limit = cognitive_load_check(email)
    warning = None
    if overloaded:
        warning = f"You have heavy workload today ({hours} hrs). We recommend moving 1 task to tomorrow."

    return render_template(
        "welcome.html",
        name=session['name'],
        total_tasks=total_tasks,
        completed=completed,
        pending=pending,
        overdue=overdue,
        today_tasks=today_tasks,
        warning=warning
    )

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form['email']
        password = request.form['password'] 

        con = sqlite3.connect("task.db")
        cur = con.cursor()
        cur.execute("SELECT * FROM users_main WHERE email=? AND password=?", (email, password))
        row = cur.fetchone()
        con.close()

        if row:
            session['email'] = row[0]
            session['name'] = row[4]
            return redirect(url_for("energy_check"))
        else:
            flash("Invalid username or password.", "danger")

    return render_template("login.html")
@app.route("/logout")
def logout():
    session.clear()
    flash("You have been logged out successfully.", "green")
    return render_template("login.html")
@app.route("/forgot_reset", methods=["POST", "GET"])
def forgot_reset():
    if request.method == "POST":
        email = request.form["email"]
        con = sqlite3.connect("task.db")
        cur = con.cursor()
        cur.execute("SELECT email FROM users_main WHERE email=?", (email,))
        user = cur.fetchone()

        if not user:
            flash("Email not found!", "danger")
            return redirect(url_for("forgot_reset"))

        otp = str(random.randint(100000, 999999))
        expiry = datetime.now() + timedelta(minutes=5)

        cur.execute("UPDATE users_main SET otp=?, otpex=? WHERE email=?", (otp, expiry, email))
        con.commit()
        con.close()

        if send_email(email, "Password Reset OTP", f"Your OTP is {otp}. Valid for 5 minutes."):
            session["reset_email"] = email
            flash("OTP sent successfully! Check your email.", "info")
            return redirect(url_for("verify_otp"))
        else:
            flash("Failed to send email.", "danger")
            return redirect(url_for("forgot_reset"))
    return render_template("forgot_reset.html")

@app.route("/verify_otp", methods=["GET", "POST"])
def verify_otp():
    if "reset_email" not in session:
        flash("Session expired. Please try again.", "danger")
        return redirect(url_for("forgot_reset"))

    if request.method == "POST":
        email = session["reset_email"]
        otp_entered = request.form["otp"]

        con = sqlite3.connect("task.db")
        cur = con.cursor()
        cur.execute("SELECT otp, otpex FROM users_main WHERE email=?", (email,))
        data = cur.fetchone()
        con.close()

        if not data:
            flash("Invalid request.", "danger")
            return redirect(url_for("forgot_reset"))

        stored_otp, otp_expiry = data

        # Convert string datetime → datetime object
        otp_expiry = datetime.fromisoformat(otp_expiry)

        if stored_otp == otp_entered and datetime.now() <= otp_expiry:
            flash("OTP verified successfully!", "success")
            return redirect(url_for("reset_password"))
        else:
            flash("Invalid or expired OTP.", "danger")
            return redirect(url_for("verify_otp"))

    return render_template("verify_otp.html")

@app.route("/reset_password", methods=["POST", "GET"])
def reset_password():
    if request.method == "POST":
        email = session.get("reset_email")
        new_password = request.form["new_password"]

        if len(new_password) < 10:
            flash("Password must be at least 10 characters long.", "danger")
            return redirect(url_for("reset_password"))

        con = sqlite3.connect("task.db")
        cur = con.cursor()
        cur.execute("UPDATE users_main SET password=?, otp='', otpex='' WHERE email=?", (new_password, email))
        con.commit()
        con.close()

        session.pop("reset_email", None)
        flash("Password reset successful! Please log in.", "success")
        return redirect(url_for("index"))
    return render_template("reset_password.html")
def send_email(to_email, subject, body):
    msg = EmailMessage()
    msg.set_content(body)
    msg['Subject'] = subject
    msg['From'] = "dhanalakshmib772@gmail.com"
    msg['To'] = to_email

    try:
        server = smtplib.SMTP_SSL('smtp.gmail.com', 465)
        server.login("dhanalakshmib772@gmail.com", "nfujxqwazwliawuf")  # App password
        server.send_message(msg)
        server.quit()
        return True
    except Exception as e:
        print("Email sending failed:", e)
        return False
@app.route("/addtask", methods=["GET", "POST"])
def addtask():
    if 'email' not in session:
        return redirect(url_for("login"))

    if request.method == 'POST':
        taskname = request.form["tn"]
        desc = request.form["des"]
        fdate = request.form["fdate"]
        tdate = request.form["tdate"]
        email = session['email']
        hours = request.form["hours"]
        # 🔮 ML Delay Prediction BEFORE saving task
        try:
            model = joblib.load("delay_predictor.pkl")

            duration = (datetime.strptime(tdate, "%Y-%m-%d") -
                        datetime.strptime(fdate, "%Y-%m-%d")).days
            # 🔮 Calculate task duration
            duration = (datetime.strptime(tdate, "%Y-%m-%d") -
            datetime.strptime(fdate, "%Y-%m-%d")).days
            if ML_MODEL:
                prediction = ML_MODEL.predict([[duration, 0]])
                if prediction[0] == 1:
                    flash("⚠️ You usually delay tasks like this. Consider reducing duration.", "warning")

        except Exception as e:
            print("ML prediction error:", e)

        # 📁 File upload handling
        file = request.files.get('myfile')
        filename = None
        filetype = None

        if file and file.filename:
            filename = secure_filename(file.filename)
            filetype = file.content_type
            file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))

        # 💾 Save task into DB
        con = sqlite3.connect("task.db")
        cur = con.cursor()
        cur.execute("""
            INSERT INTO adds__task
            (email, taskname, des, from_date, to_date,est_hours,filename, filetype)
            VALUES (?, ?, ?, ?, ?, ?, ?,?)
        """, (email, taskname, desc, fdate, tdate,hours,filename, filetype))

        con.commit()
        con.close()

        # 📧 Send confirmation email
        subject = "Task Added Successfully"
        body = f"""
        Hi {session['name']},

        Your task has been added successfully.

        Task Name : {taskname}
        From Date : {fdate}
        To Date   : {tdate}
        """

        send_email(email, subject, body)

        flash("Task added successfully", "success")
        return redirect(url_for("welcome"))

    return render_template("addtask.html")

@app.route("/mytask")
def mytask():
    if 'email' not in session:
        return redirect(url_for("login"))

    energy = session.get('energy')

    con = sqlite3.connect("task.db")
    cur = con.cursor()

    if energy == "Low":
        cur.execute("""
            SELECT * FROM adds__task
            WHERE email=? AND status='pending'
            ORDER BY to_date ASC
            LIMIT 3
        """, (session['email'],))
    elif energy == "Medium":
        cur.execute("""
            SELECT * FROM adds__task
            WHERE email=? AND status='pending'
            ORDER BY to_date ASC
            LIMIT 6
        """, (session['email'],))
    else:
        cur.execute("""
            SELECT * FROM adds__task
            WHERE email=? AND status='pending'
            ORDER BY to_date ASC
        """, (session['email'],))

    tasks = cur.fetchall()
    cur.execute("SELECT * FROM dailys_task WHERE email=?", (session['email'],))
    daily_tasks = cur.fetchall()

    con.close()

    today = date.today().strftime("%Y-%m-%d")

    return render_template("mytask.html",
                           tasks=tasks,
                           daily_tasks=daily_tasks,
                           today=today,
                           energy=energy)
@app.route("/back")
def back():
    if 'email' not in session:
        return redirect(url_for("login"))
    return redirect(url_for("welcome"))
@app.route("/delete_task/<int:task_id>")
def delete_task(task_id):
    if 'email' not in session:
        return redirect(url_for("login"))
    con = sqlite3.connect("task.db")
    cur = con.cursor()
    cur.execute(
        "SELECT filename FROM adds__task WHERE id=? AND email=?",
        (task_id, session['email'])
    )
    row = cur.fetchone()
    if row and row[0]:
        file_path = os.path.join(app.config['UPLOAD_FOLDER'], row[0])
        if os.path.exists(file_path):
            os.remove(file_path)
    cur.execute(
        "DELETE FROM adds__task WHERE id=? AND email=?",
        (task_id, session['email'])
    )

    con.commit()
    con.close()

    flash("Task deleted successfully 🗑️", "success")
    return redirect(url_for("mytask"))
def delete_expired_tasks():
    today = datetime.now().date()

    con = sqlite3.connect("task.db")
    cur = con.cursor()
    cur.execute("""
        SELECT id, filename FROM adds__task
        WHERE DATE(to_date) < ?
    """, (today,))

    expired_tasks = cur.fetchall()
    for task_id, filename in expired_tasks:
        if filename:
            file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            if os.path.exists(file_path):
                os.remove(file_path)
    cur.execute("""
        DELETE FROM adds__task
        WHERE DATE(to_date) < ?
    """, (today,))

    con.commit()
    con.close()
@app.route("/add_daily_task", methods=["GET", "POST"])
def add_daily_task():
    if 'email' not in session:
        return redirect(url_for("login"))

    if request.method == "POST":
        taskname = request.form["taskname"]
        description = request.form["description"]
        task_time = request.form["task_time"]
        email = session['email']

        con = sqlite3.connect("task.db")
        cur = con.cursor()
        cur.execute("""
            INSERT INTO dailys_task (email, taskname, description, task_time)
            VALUES (?,?,?,?)
        """, (email, taskname, description, task_time))

        con.commit()
        con.close()

        flash("Reminder task added ⏰", "success")
        return redirect(url_for("mytask"))

    return render_template("dailytask.html")
@app.route("/delete_daily_task/<int:task_id>")
def delete_daily_task(task_id):
    if 'email' not in session:
        return redirect(url_for("login"))

    con = sqlite3.connect("task.db")
    cur = con.cursor()

    cur.execute("""
        DELETE FROM dailys_task
        WHERE id=? AND email=?
    """, (task_id, session['email']))

    con.commit()
    con.close()

    flash("Daily task deleted ", "success")
    return redirect(url_for("mytask"))
def send_deadline_reminders():
    tomorrow = (datetime.now() + timedelta(days=1)).date()

    con = sqlite3.connect("task.db")
    cur = con.cursor()

    cur.execute("""
    SELECT email, taskname, to_date
    FROM adds__task
    WHERE DATE(to_date)=? AND status='pending'
""", (tomorrow,))

    tasks = cur.fetchall()
    con.close()

    for email, taskname, to_date in tasks:
        subject = " Task Deadline Tomorrow"
        body = f"""
        Hi,

        Reminder!!

        Your task deadline is TOMORROW.

        Task Name : {taskname}
        Deadline  : {to_date}

        Please complete it on time
        """

        send_email(email, subject, body)
@app.route("/complete_task/<int:task_id>")
def complete_task(task_id):
    if 'email' not in session:
        return redirect(url_for("login"))

    today = datetime.now().date()

    con = sqlite3.connect("task.db")
    cur = con.cursor()
    cur.execute("""
        SELECT taskname, to_date, status
        FROM adds__task
        WHERE id=? AND email=?
    """, (task_id, session['email']))
    task = cur.fetchone()

    if not task or task[2] == 'completed':
        con.close()
        return redirect(url_for("mytask"))

    taskname, to_date, _ = task
    to_date = datetime.strptime(to_date, "%Y-%m-%d").date()
    if today < to_date:
        coins = 50
    elif today == to_date:
        coins = 20
    else:
        coins = 0

    cur.execute("""
        UPDATE adds__task
        SET status='completed', completed_date=?, earned_coins=?
        WHERE id=? AND email=?
    """, (today, coins, task_id, session['email']))

    cur.execute("""
        UPDATE users_main
        SET coins = coins + ?
        WHERE email=?
    """, (coins, session['email']))
    if coins > 0:
        cur.execute("""
            INSERT INTO coin_history (email, task_name, coins, earned_date)
            VALUES (?,?,?,?)
        """, (session['email'], taskname, coins, today))

    con.commit()
    subject = "🎉 Task Completed Successfully"
    body = f"""
    Hi {session['name']},

    Great job! 🎯

    You have successfully completed your task.

    Task Name : {taskname}
    Completed On : {today}
    Coins Earned : {coins} 🪙

    Keep going! 💪
    """

    send_email(session['email'], subject, body)

    con.close()

    flash(f"Task completed 🎉 You earned {coins} coins", "success")
    return redirect(url_for("mytask"))
@app.route("/coins", methods=["GET", "POST"])
def coins():
    if "email" not in session:
        return redirect(url_for("login"))

    con = sqlite3.connect("task.db")
    cur = con.cursor()
    cur.execute("SELECT coins FROM users_main WHERE email=?", (session["email"],))
    total_coins = cur.fetchone()[0]

    if request.method == "POST":
        if total_coins >= 1000:
            name = request.form["name"]
            phone = request.form["phone"]
            address = request.form["address"]
            today = datetime.now().date()

            cur.execute("""
                INSERT INTO gift_requests
                (email, name, phone, address, coins, request_date)
                VALUES (?,?,?,?,?,?)
            """, (session["email"], name, phone, address, total_coins, today))

            con.commit()
            flash("🎁 Gift request submitted successfully!")
        else:
            flash("❌ You need at least 1000 coins")

    con.close()

    return render_template("coins.html", coins=total_coins)
@app.route("/leaderboard")
def leaderboard():
    if "email" not in session:
        return redirect(url_for("login"))

    con = sqlite3.connect("task.db")
    cur = con.cursor()

    cur.execute("""
        SELECT name, email, coins
        FROM users_main
        ORDER BY coins DESC
    """)
    leaderboard_data = cur.fetchall()

    con.close()

    return render_template(
        "leaderboard.html",
        leaderboard=leaderboard_data,
        current_email=session["email"]
    )
# @app.route('/chatbot', methods=['POST'])
# def ask_ai_route():
#     user_msg = request.json['message']

#     # You can add user analytics here later
#     reply = ask_ai(user_msg)

#     return jsonify({"reply": reply})
@app.route('/chatbot', methods=['POST'])
def ask_ai_route():
    if 'email' not in session:
        return jsonify({"reply": "Login required"})

    user_msg = request.json['message']

    try:
        reply = ask_ai(user_msg)
    except Exception as e:
        print("Ollama error:", e)
        reply = "AI not responding. Check Ollama."

    # Store chat history
    con = sqlite3.connect("task.db")
    cur = con.cursor()
    cur.execute("""
        INSERT INTO chat_history (email, user_msg, bot_reply, time)
        VALUES (?,?,?,?)
    """, (session['email'], user_msg, reply, datetime.now()))
    con.commit()
    con.close()

    return jsonify({"reply": reply})
@app.route("/energy-check")
def energy_check():
    if 'email' not in session:
        return redirect(url_for("login"))
    return render_template("energy.html")
@app.route("/set-energy", methods=["POST"])
def set_energy():
    if 'email' not in session:
        return redirect(url_for("login"))

    energy = request.form['energy']
    today = datetime.now().date()

    con = sqlite3.connect("task.db")
    cur = con.cursor()
    cur.execute("""
        INSERT INTO user_energy (email, energy, date)
        VALUES (?,?,?)
    """, (session['email'], energy, today))
    con.commit()
    con.close()

    session['energy'] = energy

    return redirect(url_for("welcome"))
@app.route("/alltasks")
def alltasks():
    if 'email' not in session:
        return redirect(url_for("login"))

    con = sqlite3.connect("task.db")
    cur = con.cursor()

    cur.execute("""
        SELECT * FROM adds__task
        WHERE email=?
        ORDER BY to_date ASC
    """, (session['email'],))

    tasks = cur.fetchall()

    cur.execute("""
        SELECT * FROM dailys_task
        WHERE email=?
        ORDER BY task_date ASC
    """, (session['email'],))

    daily_tasks = cur.fetchall()

    con.close()

    return render_template("alltasks.html",
                           tasks=tasks,
                           daily_tasks=daily_tasks)
def cognitive_load_check(email):
    today = datetime.now().date()
    con = sqlite3.connect("task.db")
    cur = con.cursor()

    # Get today energy
    cur.execute("""
        SELECT energy FROM user_energy
        WHERE email=? AND date=?
    """, (email, today))
    row = cur.fetchone()
    energy = row[0] if row else "Medium"

    # Get today's tasks and hours
    cur.execute("""
        SELECT COUNT(*), SUM(est_hours)
        FROM adds__task
        WHERE email=? AND status='pending' AND DATE(to_date)=?
    """, (email, today))

    count, total_hours = cur.fetchone()
    total_hours = total_hours or 0

    con.close()

    # Threshold based on energy
    if energy == "Low":
        limit = 3
    elif energy == "Medium":
        limit = 6
    else:
        limit = 9

    overloaded = total_hours > limit

    return overloaded, total_hours, limit
@app.route("/suggest_shift")
def suggest_shift():
    if 'email' not in session:
        return redirect(url_for("login"))

    today = datetime.now().date()

    con = sqlite3.connect("task.db")
    cur = con.cursor()

    # Suggest the lowest priority (farthest deadline)
    cur.execute("""
        SELECT id, taskname, to_date
        FROM adds__task
        WHERE email=? AND status='pending' AND DATE(to_date)=?
        ORDER BY to_date DESC
        LIMIT 1
    """, (session['email'], today))

    task = cur.fetchone()
    con.close()

    return render_template("shift_task.html", task=task)
@app.route("/move_task/<int:task_id>")
def move_task(task_id):
    if 'email' not in session:
        return redirect(url_for("login"))

    tomorrow = datetime.now().date() + timedelta(days=1)

    con = sqlite3.connect("task.db")
    cur = con.cursor()
    cur.execute("""
        UPDATE adds__task
        SET to_date=?
        WHERE id=? AND email=?
    """, (tomorrow, task_id, session['email']))

    con.commit()
    con.close()

    flash("Task moved to tomorrow to reduce overload ✅", "success")
    return redirect(url_for("welcome"))
@app.route("/get_chat_history")
def get_chat_history():
    if 'email' not in session:
        return jsonify([])

    con = sqlite3.connect("task.db")
    cur = con.cursor()

    cur.execute("""
        SELECT user_msg, bot_reply
        FROM chat_history
        WHERE email=?
        ORDER BY time ASC
        LIMIT 50
    """, (session['email'],))

    rows = cur.fetchall()
    con.close()

    history = []
    for u, b in rows:
        history.append({"user": u, "bot": b})

    return jsonify(history)
@app.route("/subscribe", methods=["POST"])
def subscribe():
    sub = request.json
    subscriptions.append(sub)
    return '', 204
def send_notification(title, message):
    for sub in subscriptions:
        webpush(
            subscription_info=sub,
            data=json.dumps({"title": title, "body": message}),
            vapid_private_key="vr7XGM7EU1p8kbdAKHxPg-X2ZPidYhoLqq7ANqXJSA8",
            vapid_claims={"sub": "mailto:yourmail@gmail.com"}
        )
def reminder_checker():
    while True:
        now = datetime.now().strftime("%H:%M")
        con = sqlite3.connect("task.db")
        cur = con.cursor()
        cur.execute("SELECT taskname, task_time FROM dailys_task")
        tasks = cur.fetchall()
        con.close()

        for name, ttime in tasks:
            task_dt = datetime.strptime(ttime, "%H:%M") - timedelta(hours=1)
            if now == task_dt.strftime("%I:%M %p"):
                send_notification("Reminder", f"{name} in 1 hour!")

        time.sleep(60)

threading.Thread(target=reminder_checker).start()
if __name__ == '__main__':
    init_db()
    app.run(debug=True)