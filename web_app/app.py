from flask import Flask, render_template, redirect, url_for, request, flash
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from flask_mail import Mail
from flask_apscheduler import APScheduler
from werkzeug.security import generate_password_hash, check_password_hash
import random, string, requests, time
import os, sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from config import *
from models import db, User, Alert
from email_utils import send_email

app = Flask(__name__)
app.config.from_object("config")
db.init_app(app)
mail = Mail(app)

login_manager = LoginManager(app)
login_manager.login_view = 'login'

scheduler = APScheduler()
scheduler.init_app(app)
scheduler.start()

@login_manager.user_loader
def load_user(uid):
    return User.query.get(int(uid))

@app.before_first_request
def create_tables():
    db.create_all()

@app.route('/register', methods=['GET','POST'])
def register():
    if request.method=='POST':
        email = request.form['email']
        pwd   = generate_password_hash(request.form['password'])
        code  = ''.join(random.choices(string.digits, k=6))
        u = User(email=email, password=pwd, confirm_code=code)
        db.session.add(u); db.session.commit()
        send_email(email, "Your confirmation code", f"Code: {code}")
        flash("Confirmation code sent to your email")
        return redirect(url_for('confirm', email=email))
    return render_template('register.html')

@app.route('/confirm', methods=['GET','POST'])
def confirm():
    email = request.args.get('email')
    u = User.query.filter_by(email=email).first_or_404()
    if request.method=='POST':
        if request.form['code']==u.confirm_code:
            u.confirmed=True; db.session.commit()
            flash("Email confirmed. Please log in.")
            return redirect(url_for('login'))
        else:
            flash("Wrong code.")
    return render_template('confirm.html', email=email)

@app.route('/login', methods=['GET','POST'])
def login():
    if request.method=='POST':
        u = User.query.filter_by(email=request.form['email']).first()
        if u and check_password_hash(u.password, request.form['password']) and u.confirmed:
            login_user(u)
            return redirect(url_for('dashboard'))
        flash("Invalid credentials or email not confirmed.")
    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))

@app.route('/dashboard')
@login_required
def dashboard():
    alerts = Alert.query.filter_by(user_id=current_user.id).all()
    return render_template('dashboard.html', alerts=alerts)

@app.route('/alert/new', methods=['GET','POST'])
@login_required
def new_alert():
    if request.method=='POST':
        a = Alert(
            user_id=current_user.id,
            coin=request.form['coin'],
            threshold=float(request.form['threshold']),
            direction=request.form['direction']
        )
        db.session.add(a); db.session.commit()
        flash("Alert created.")
        return redirect(url_for('dashboard'))
    return render_template('alert_form.html', coins=COIN_LIST)

# scheduled job: runs every minute
@scheduler.task('interval', id='check_alerts', seconds=60, misfire_grace_time=30)
def check_alerts():
    alerts = Alert.query.filter_by(sent=False).all()
    if not alerts: return
    # fetch all current prices in one go
    res = requests.get(
        "https://api.coingecko.com/api/v3/simple/price",
        params={"ids": ",".join(COIN_LIST), "vs_currencies": VS_CURRENCY}
    ).json()
    ts = time.strftime("%Y-%m-%d %H:%M:%S")
    for a in alerts:
        price = res[a.coin][VS_CURRENCY]
        if (a.direction=="above" and price>a.threshold) or (a.direction=="below" and price<a.threshold):
            send_email(current_app.config['MAIL_USERNAME'], 
                       f"Alert: {a.coin} {a.direction} {a.threshold}", 
                       f"At {ts}, {a.coin} price is {price}")
            a.sent = True
    db.session.commit()

if __name__=='__main__':
    app.run(debug=True)