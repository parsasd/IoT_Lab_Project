
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from getpass import getpass


def send_email(to, subject, body):
    # Configuration (Modify these values)
    SMTP_SERVER = "smtp.sharif.edu"
    PORT = 587                    
    SENDER_EMAIL = "sepehr.mizanian@sharif.edu"
    RECEIVER_EMAIL = to

    # Get password securely
    password = "123456aA@#$%^&*"

    msg = MIMEMultipart()
    msg['From'] = SENDER_EMAIL
    msg['To'] = RECEIVER_EMAIL
    msg['Subject'] = subject
    msg.attach(MIMEText(body, 'plain'))

    try:
        with smtplib.SMTP(SMTP_SERVER, PORT) as server:
            server.starttls()
            server.login(SENDER_EMAIL, password)
            server.sendmail(SENDER_EMAIL, RECEIVER_EMAIL, msg.as_string())
        print("✓ Email sent successfully using app password!")
    except Exception as e:
        print(f"× Error: {str(e)}")