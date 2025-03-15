import os
import json
import requests
from dotenv import load_dotenv
import pika
import uuid
import time

# Load environment variables from .env file
load_dotenv()

LLAMA_URL = "http://localhost:11434/api/generate"

class GmailRpcClient:
    """
    A RabbitMQ RPC Client for fetching emails from Gmail.
    
    This class connects to RabbitMQ, sends a request to get the latest unread email, 
    and waits for a response with the email content.
    """
    def __init__(self):
        print("INFO: Connecting to RabbitMQ...")
        self.connection = pika.BlockingConnection(pika.ConnectionParameters('localhost'))
        self.channel = self.connection.channel()

        # Create a unique callback queue for receiving responses
        result = self.channel.queue_declare(queue='', exclusive=True)
        self.callback_queue = result.method.queue

        # Listen for responses on the callback queue
        self.channel.basic_consume(
            queue=self.callback_queue,
            on_message_callback=self.on_response,
            auto_ack=True
        )

        self.response = None
        self.corr_id = None

        print("INFO: RabbitMQ connection established.")

    def on_response(self, ch, method, props, body):
        """
        Handle the response from RabbitMQ.

        Args:
            ch: RabbitMQ channel
            method: RabbitMQ method
            props: RabbitMQ properties
            body: Message body
        """
        if self.corr_id == props.correlation_id:
            self.response = body.decode()

    def call(self):
        """
        Send a request to RabbitMQ to get the latest unread email.

        Returns:
            str: Email content or "No new messages" if no new email is found.
        """
        self.response = None
        self.corr_id = str(uuid.uuid4())

        # Send a message to RabbitMQ
        self.channel.basic_publish(
            exchange='',
            routing_key='rpc_queue_v5',  
            properties=pika.BasicProperties(
                reply_to=self.callback_queue,
                correlation_id=self.corr_id,
            ),
            body=''
        )

        # Wait for response from RabbitMQ
        while self.response is None:
            self.connection.process_data_events(time_limit=None)

        return self.response

# Function to clean up the message using Llama3
def clean_with_llama(content):
    """
    Clean up the email content using Llama3.

    Args:
        content (str): Raw email content

    Returns:
        dict: Cleaned email content with 'sender' and 'body'
    """
    print(f"INFO: Sending the following message to Llama3:\n{content}")

    try:
        content = content.encode('utf-8', 'ignore').decode('utf-8')

        response = requests.post(
            LLAMA_URL,
            json={
                "model": "llama3",
                "prompt": (
                    "Clean: Format the following message in a clean and structured way. "
                    "Remove unnecessary signatures, special characters, and extra spaces. "
                    "Respond strictly in the following JSON format:\n"
                    "{ \"sender\": \"<Sender>\", \"body\": \"<Cleaned Content>\" }\n\n"
                    "Message:\n"
                    f"{content}"
                ),
                "stream": False
            }
        )

        result = response.json().get("response", "").strip()
        print(f"INFO: Llama3 response:\n{result}")

        # Parse the response from Llama3
        clean_message = parse_llama_response(result)
        if clean_message:
            print(f"INFO: Cleaned message: {clean_message}")
            return clean_message
        else:
            print("ERROR: Invalid response from Llama3 or missing format.")
            return None

    except Exception as e:
        print(f"ERROR: Llama3 cleaning error: {e}")
        return None

# Function to analyze sentiment using Llama3
def analyze_sentiment_with_llama(content):
    """
    Analyze the sentiment of the email using Llama3.

    Args:
        content (str): Email body content

    Returns:
        str: "positive", "negative", or "neutral"
    """
    print(f"INFO: Sending the following message to Llama3 for sentiment analysis:\n{content}")

    try:
        response = requests.post(
            LLAMA_URL,
            json={
                "model": "llama3",
                "prompt": (
                    "Analyze the sentiment of this message. If the message contains sarcasm, irony, or mockery, "
                    "consider it as negative. Respond strictly in the following JSON format. Do not provide any explanations:\n"
                    "{ \"sentiment\": \"positive\" | \"negative\" | \"neutral\", \"sarcasm\": true | false }\n\n"
                    f"Message:\n{content}"
                ),
                "stream": False
            }
        )

        result = response.json().get("response", "").strip()
        print(f"INFO: Sentiment analysis response from Llama3:\n{result}")

        # Parse JSON response
        sentiment_data = json.loads(result.replace("'", "\""))
        sentiment = sentiment_data.get("sentiment", "").lower()
        sarcasm = sentiment_data.get("sarcasm", False)

        if sarcasm:
            sentiment = "negative"

        return sentiment

    except Exception as e:
        print(f"ERROR: Sentiment analysis error: {e}")
        return None


def parse_llama_response(result):
    """
    Parse the JSON response from Llama3.

    Args:
        result (str): Raw JSON string from Llama3

    Returns:
        dict: Parsed JSON object containing 'sender' and 'body'
    """
    try:
        if "{" in result and "}" in result:
            json_part = result[result.index("{"):result.rindex("}") + 1]
            json_part = json_part.replace("'", "\"")
            json_part = json_part.replace("\n", " ").replace("\r", " ").replace("\t", " ")

            message = json.loads(json_part, strict=False)
            if isinstance(message, dict) and 'sender' in message and 'body' in message:
                return message
            else:
                raise ValueError("Invalid JSON format")
        else:
            raise ValueError("No valid JSON found in the response")

    except Exception as e:
        print(f"ERROR: JSON parsing error: {e}")
        return None


# Send message to RabbitMQ
def send_to_rabbitmq(message):
    """
    Send the processed message to RabbitMQ.

    Args:
        message (dict): Cleaned and processed email content
    """
    connection = pika.BlockingConnection(pika.ConnectionParameters('localhost'))
    channel = connection.channel()

    channel.queue_declare(queue='email_alerts_v5', durable=True)

    channel.basic_publish(
        exchange='',
        routing_key='email_alerts_v5',
        body=json.dumps(message)
    )

    connection.close()

if __name__ == "__main__":
    rpc_client = GmailRpcClient()

    while True:
        # Get new email
        email_content = rpc_client.call()

        if email_content != "No new messages":
            # Clean the email content
            message = clean_with_llama(email_content)
            if message and message.get("sender") and message.get("body"):
                # Perform sentiment analysis
                sentiment = analyze_sentiment_with_llama(message.get("body"))

                if sentiment:
                    print(f"INFO: Sentiment: {sentiment}")

                    if sentiment == "negative":
                        send_to_rabbitmq(message)
                        print("INFO: Negative message sent to RabbitMQ.")
                    else:
                        print(f"INFO: Message sentiment '{sentiment}', not processed.")
                else:
                    print("ERROR: Sentiment not determined.")

        time.sleep(10)