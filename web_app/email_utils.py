from flask_mail import Message
from flask import current_app
from config import MAIL_USERNAME
from app import mail

def send_email(to, subject, body):
    msg = Message(subject, sender=MAIL_USERNAME, recipients=[to])
    msg.body = body
    mail.send(msg)