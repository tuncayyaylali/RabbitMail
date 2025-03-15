import pika
import smtplib
from email.mime.text import MIMEText
import os
from dotenv import load_dotenv
from datetime import datetime
import json
import time

# Load environment variables from .env file
load_dotenv()

SMTP_SERVER = os.getenv('SMTP_SERVER')
SMTP_PORT = int(os.getenv('SMTP_PORT'))
EMAIL_ADDRESS = os.getenv('EMAIL_ADDRESS')
EMAIL_PASSWORD = os.getenv('EMAIL_PASSWORD')
ALERT_RECIPIENT = os.getenv('ALERT_RECIPIENT')

def format_email(sender, body):
    """
    Format the email content into an HTML structure.

    Args:
        sender (str): Email sender's address
        body (str): Email body content

    Returns:
        str: Formatted HTML content for the email
    """
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    html = f"""
    <html>
        <body>
            <h2>Negative Email Alert</h2>
            <p><strong>From:</strong> {sender}</p>
            <p><strong>Time:</strong> {timestamp}</p>
            <hr>
            <p>{body}</p>
        </body>
    </html>
    """
    return html

def send_email_alert(sender, body):
    """
    Send an email alert using SMTP.

    Args:
        sender (str): Email sender's address
        body (str): Email body content
    """
    try:
        # Create the email message
        msg = MIMEText(format_email(sender, body), 'html')
        msg["From"] = EMAIL_ADDRESS
        msg["To"] = ALERT_RECIPIENT
        msg["Subject"] = "Negative Email Alert"

        # Connect to SMTP server and send the email
        with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as server:
            server.starttls()
            server.login(EMAIL_ADDRESS, EMAIL_PASSWORD)
            server.sendmail(EMAIL_ADDRESS, ALERT_RECIPIENT, msg.as_string())

        print(f"INFO: Email alert sent to {ALERT_RECIPIENT}")

    except Exception as e:
        print(f"ERROR: Failed to send email: {e}")

def on_message(ch, method, properties, body):
    """
    Handle incoming messages from RabbitMQ.

    Args:
        ch: RabbitMQ channel
        method: RabbitMQ method
        properties: RabbitMQ properties
        body: Message body (JSON format)
    """
    try:
        # Decode and parse the JSON message
        message = json.loads(body.decode())
        sender = message.get("sender")
        body = message.get("body")

        if sender and body:
            print(f"INFO: New message received from: {sender}")
            # Send email alert
            send_email_alert(sender, body)
            # Acknowledge the message
            ch.basic_ack(delivery_tag=method.delivery_tag)
            print("INFO: Email successfully processed and removed from queue.")
        else:
            print("ERROR: Invalid message format. Missing sender or body.")
            # Reject the message and do not requeue
            ch.basic_nack(delivery_tag=method.delivery_tag, requeue=False)

    except json.JSONDecodeError as e:
        print(f"ERROR: JSON format error: {e}")
        # Reject the message and do not requeue
        ch.basic_nack(delivery_tag=method.delivery_tag, requeue=False)

    except Exception as e:
        print(f"ERROR: Message processing error: {e}")
        # Reject the message and requeue it for another attempt
        ch.basic_nack(delivery_tag=method.delivery_tag, requeue=True)

def connect_to_rabbitmq():
    """
    Connect to RabbitMQ and listen for messages.
    """
    while True:
        try:
            print("INFO: Connecting to RabbitMQ...")
            # Connect to RabbitMQ server
            connection = pika.BlockingConnection(pika.ConnectionParameters('localhost'))
            channel = connection.channel()

            # Declare the queue (durable to survive broker restarts)
            channel.queue_declare(queue='email_alerts_v5', durable=True)

            # Start consuming messages from the queue
            channel.basic_consume(queue='email_alerts_v5', on_message_callback=on_message)
            print("INFO: Listening for incoming messages...")
            channel.start_consuming()

        except KeyboardInterrupt:
            print("INFO: Program stopped manually.")
            connection.close()
            break

        except Exception as e:
            print(f"ERROR: RabbitMQ connection error: {e}")
            # Wait for 5 seconds before retrying connection
            time.sleep(5)

if __name__ == "__main__":
    connect_to_rabbitmq()
