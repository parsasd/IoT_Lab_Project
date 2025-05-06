from flask_mail import Message
from flask import current_app

def send_email(to, subject, body):
    """
    Send an email using the Flask-Mail extension that's been
    registered on the current_app.
    """
    # Grab the Mail instance from Flask's extensions registry
    mail = current_app.extensions.get('mail')
    if mail is None:
        raise RuntimeError("Flask-Mail not initialized")

    msg = Message(subject,
                  sender=current_app.config['MAIL_USERNAME'],
                  recipients=[to])
    msg.body = body
    mail.send(msg)