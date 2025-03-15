import re
import os
import base64
import json
from googleapiclient.discovery import build
from google.oauth2.credentials import Credentials
from dotenv import load_dotenv
import pika

# Load environment variables from .env file
load_dotenv()

CREDENTIALS_FILE = os.getenv('CREDENTIALS_FILE')
TOKEN_FILE = os.getenv('TOKEN_FILE')
TARGET_EMAIL = os.getenv('TARGET_EMAIL')

SCOPES = [
    'https://www.googleapis.com/auth/gmail.readonly',
    'https://www.googleapis.com/auth/gmail.modify'
]

def get_gmail_service():
    """
    Authenticate and return a Gmail service instance.
    
    If the token file exists, it will use the existing credentials.
    If not, it will prompt for login and create a new token file.
    
    Returns:
        service (googleapiclient.discovery.Resource): Authenticated Gmail service object
    """
    creds = None
    if os.path.exists(TOKEN_FILE):
        creds = Credentials.from_authorized_user_file(TOKEN_FILE, SCOPES)
    else:
        from google_auth_oauthlib.flow import InstalledAppFlow
        flow = InstalledAppFlow.from_client_secrets_file(CREDENTIALS_FILE, SCOPES)
        creds = flow.run_local_server(port=0)
        with open(TOKEN_FILE, 'w') as token:
            token.write(creds.to_json())

    return build('gmail', 'v1', credentials=creds)

def get_latest_unread_email():
    """
    Fetch the latest unread email from the target inbox.

    Returns:
        dict: A dictionary containing 'sender' and 'body' keys.
              If no new email is found, returns {'sender': None, 'body': None}.
    """
    service = get_gmail_service()
    if not service:
        return {"sender": None, "body": None}

    print("INFO: Checking for new unread emails...")

    try:
        # Search for unread emails in the inbox that are not from no-reply addresses
        results = service.users().messages().list(
            userId='me',
            labelIds=['INBOX'],
            q=f'is:unread to:{TARGET_EMAIL} -from:no-reply@accounts.google.com',
            maxResults=1
        ).execute()

        messages = results.get('messages', [])
        if not messages:
            return {"sender": None, "body": None}

        message_id = messages[0]['id']

        # Get the email content using the message ID
        msg = service.users().messages().get(userId='me', id=message_id).execute()
        payload = msg['payload']

        # Extract the sender's email address from the headers
        headers = payload.get('headers', [])
        sender = next((header['value'] for header in headers if header['name'] == 'From'), None)

        # Extract the email body
        body = ""
        if 'parts' in payload:
            for part in payload['parts']:
                if part['mimeType'] == 'text/plain':
                    body = base64.urlsafe_b64decode(part['body']['data']).decode("utf-8", "ignore")
                    break
        elif 'body' in payload:
            body = base64.urlsafe_b64decode(payload['body']['data']).decode("utf-8", "ignore")

        # Handle encoding issues
        try:
            sender = sender.encode('utf-8').decode('utf-8', 'ignore') if sender else None
            body = body.encode('utf-8').decode('utf-8', 'ignore') if body else None

            if sender:
                match = re.search(r'<(.+?)>', sender)
                if match:
                    sender = match.group(1)

        except Exception as e:
            print(f"ERROR: Encoding error: {e}")

        # Mark the email as read
        service.users().messages().modify(
            userId='me',
            id=message_id,
            body={'removeLabelIds': ['UNREAD']}
        ).execute()

        if sender and body:            
            print(sender, body)
            return {"sender": sender, "body": body}
        else:
            print(sender, body)
            return {"sender": None, "body": None}

    except Exception as e:
        print(f"ERROR: Error while reading email: {e}")
        return {"sender": None, "body": None}

def on_request(ch, method, props, body):
    """
    Handle incoming RabbitMQ requests and process them.
    
    Args:
        ch: RabbitMQ channel
        method: RabbitMQ method
        props: RabbitMQ properties
        body: Message body
    """
    print("INFO: Processing new email request...")
    email = get_latest_unread_email()

    # Respond with the email content if available, otherwise notify no new messages
    response = json.dumps(email, ensure_ascii=False).encode('utf-8') if email["sender"] and email["body"] else b"No new messages"

    # Publish response back to the client
    ch.basic_publish(
        exchange='',
        routing_key=props.reply_to,
        properties=pika.BasicProperties(correlation_id=props.correlation_id),
        body=response
    )
    # Acknowledge the message
    ch.basic_ack(delivery_tag=method.delivery_tag)

# Establish connection with RabbitMQ server
connection = pika.BlockingConnection(pika.ConnectionParameters('localhost'))
channel = connection.channel()

# Declare the RPC queue
channel.queue_declare(queue='rpc_queue_v5', durable=True)

# Start consuming messages from the queue
channel.basic_consume(queue='rpc_queue_v5', on_message_callback=on_request)

print("INFO: Listening for requests...")
channel.start_consuming()