# Automating Email Processing and Sentiment Analysis with RabbitMQ, Ollama, and Gmail API  

## 1. Introduction  
In the era of rapid digital communication, the volume of emails received daily has become overwhelming. Important messages often get lost in the clutter, and manually sorting through emails is both time-consuming and inefficient. Additionally, understanding the tone and sentiment of emails (especially sarcasm and negativity) is crucial for effective communication and decision-making.

I embarked on this project to create a fully automated pipeline that not only fetches emails but also analyzes their sentiment and reacts to negative or sarcastic messages in real time. The goal was to combine the power of machine learning, natural language processing (NLP), and message queueing to handle complex email processing tasks with minimal human intervention.

### 1.1. Objective and Scope

The primary objective of this project was to build a system capable of:
- Automating email retrieval from a target inbox using `Gmail API`
- Cleaning and formatting email content using `Ollama` (`Llama3 model`)
- Performing sentiment analysis to identify positive, negative, and sarcastic emails
- Leveraging `RabbitMQ` as a message broker to handle asynchronous communication
- Sending real-time alerts for negative or sarcastic emails using `SMTP`

### 1.2. Scope
- The system is designed to handle high volumes of emails without performance degradation.
- Sarcasm detection is handled solely through prompt engineering for `Llama3`, without fine-tuning.
- The system is designed to be scalable and adaptable for other `NLP` tasks.

### 1.3. Methodology
The project was implemented using a structured methodology:

- Design and Planning
   - Defined project scope and objectives.
   - Evaluated potential tools and technologies (e.g., `Ollama`, `RabbitMQ`, `Gmail API`).
   - Designed the overall architecture, including component communication via `RabbitMQ`.
- Implementation
   - Set up the development environment using Docker.
   - Developed three key components:
      - `RPC Server` – For email fetching and processing.
      - `RPC Client` – For content cleaning and sentiment analysis.
      - `Worker` – For sending alerts via `SMTP`.
   - Configured `OAuth 2.0` for `Gmail API` authentication.
   - Defined `Llama3` prompt for cleaning and sentiment analysis.
- Testing and Debugging
   - Sent multiple test emails covering different scenarios (positive, negative, and sarcastic).
   - Evaluated system response time and accuracy.
- Deployment
   - Deployed the solution using `Docker`.
   - Ensured `RabbitMQ` handled asynchronous processing without bottlenecks.
- Monitoring and Optimization
   - Added logging and monitoring for performance tracking.

### 1.4. Challenges
- OAuth 2.0 Complexity: Setting up `Gmail API` `OAuth` authentication required detailed configuration and token handling.
- Concurrency Handling: `RabbitMQ` message processing required careful configuration to avoid race conditions.
- SMTP Authentication: `Gmail` `SMTP` authentication required creating an app password due to Google’s security policies.

## 2. Architecture Overview  
The architecture consists of three main components:  

- **RPC Server** – Fetches the latest unread email from `Gmail` using the `Gmail API`  
- **RPC Client** – Sends the email content to `Ollama` for cleaning and sentiment analysis  
- **Worker** – Handles negative sentiment emails and sends alerts via `SMTP`
- Communication between services is managed using `RabbitMQ` queues.  

### 2.1. RabbitMQ and RPC Integration  
`RabbitMQ` serves as the central messaging broker, enabling communication between the components.  

- The **RPC (Remote Procedure Call)** mechanism allows the `RPC Client` to request and receive email data from the `RPC Server` through `RabbitMQ` queues.  
- `RabbitMQ` ensures asynchronous communication and reliable message delivery, making the system more scalable and fault-tolerant.  
- This architecture allows multiple services to work together seamlessly without direct dependencies, increasing overall system flexibility. 

## 3. Setting Up the Environment  

### 3.1. Setting Up RabbitMQ with Docker  
Start `RabbitMQ` using the official `Docker` image:  

```bash
docker run -d --hostname rabbitmq --name RabbitMQ -p 15672:15672 rabbitmq:4.0.7-management
```

At this point, you can access the **RabbitMQ Management UI** by opening your browser and going to:  

👉 `http://localhost:15672`  

The default username and password are `guest/guest`.  

![RabbitMQ Web UI](./images/RabbitMQ_WebUI.png)  

### 3.2. Setting Up Ollama (Llama3)  
Install `Ollama` and pull the `Llama3` model:  

```bash
# Install Ollama
docker run -d --name ollama -p 11434:11434 ollama/ollama

# Pull the Llama3 model in Ollama Docker container
docker exec -it ollama ollama pull llama3
```

To verify that `Ollama` is running, you can test the installation with the following command in `Ollama` `Docker` container:  

```bash
docker exec -it ollama ollama list
```

![Ollama](./images/Ollama.png)

### 3.3. Get Google API Credentials  
To access **Gmail**, you need to create **Google API** credentials:  

1. Go to the **Google Cloud Console**.  
2. From the left-hand menu, navigate to **APIs & Services** → **Library**.  
3. Enable the **Gmail API**.  
4. From the left-hand menu, navigate to **APIs & Services** → **Credentials**.  
5. Click on **Create Credentials** and select **OAuth Client ID**.  
    - Set the **Application type** to **Desktop App**.  
    - Download the `credentials.json` file.  
    - Save the file as `credentials.json` in your working directory.  
6. From the **Credentials** tab, click on the client name you just created to open the details.  
7. Go to the **OAuth Consent Screen** → **Audience** → **Test Users** → **Add Users** and add your email address.  

> **⚠️ Note:** If you don't add your email address in the Test Users section, you will get an authorization error.

### 3.4. Configuration
To configure the environment, create a .env file in the root directory and add the following settings:

```yaml
# OpenAI API Key (if using OpenAI for any task)
OPENAI_API_KEY=

# Gmail API Files (OAuth credentials)
CREDENTIALS_FILE=credentials.json    # Path to the OAuth credentials file  
TOKEN_FILE=token.json                # Path to the token file (generated after first login)  

# SMTP Configuration (for sending alerts via Gmail)
SMTP_SERVER=smtp.gmail.com           # SMTP server for Gmail  
SMTP_PORT=587                        # SMTP port for TLS  
EMAIL_ADDRESS=                       # Gmail address used for sending alerts  
EMAIL_PASSWORD=                      # App password or Gmail password  

# Target Email (where to read emails from)
TARGET_EMAIL=                        # Email address to monitor for incoming emails  

# Alert Recipient (where to send alerts)
ALERT_RECIPIENT=                     # Email address to receive alerts  
```

## 4. Create the RPC Server  
The `RPC server` will fetch emails using the `Gmail API` and push them to `RabbitMQ`.  

### 4.1. `rpc_server.py`  
Here’s the core logic for fetching emails and sending them to `RabbitMQ`:  

- Authenticate with the `Gmail API`  
- Fetch the latest unread email  
- Mark the email as read  
- Send the email content to `RabbitMQ`  

See the full email fetching and RabbitMQ logic in [`rpc_server.py`](./rpc_server.py).

## 5. Create the RPC Client  
The `RPC client` will process the fetched email by sending it to `Ollama` for cleaning and sentiment analysis.  

### 5.1. `rpc_client.py`  
Here’s the core logic for cleaning the email content, analyzing sentiment, and sending negative emails to `RabbitMQ`:  

- **Clean the email content using `Ollama`**  
   - Cleaning ensures that unnecessary signatures, formatting, and special characters are removed.  
   - Cleaned content helps improve the accuracy of sentiment analysis.  

- **Perform sentiment analysis using `Ollama`**  
   - Sentiment is classified as positive, negative, or neutral.  
   - If sarcasm is detected, the sentiment is set to negative.  

- **If the sentiment is negative, push the email to `RabbitMQ`**  
   - Only negative emails are forwarded to `RabbitMQ` for further processing.  

See the full email cleaning, sentiment analysis, and RabbitMQ handling logic in [`rpc_client.py`](./rpc_client.py)

## 6. Create the Worker  
The `Worker` will handle the email content and send alerts using `SMTP`.  

### 6.1. `rabbitmq_worker.py`  
Here’s the core logic for processing the email content and sending alerts:  

- **Receive email content from `RabbitMQ`**  
   - The worker listens to the `RabbitMQ` queue for incoming messages.  
   - If the message is properly formatted, it will extract the email content and sender.  

- **Format the email content**  
   - The email content is converted into an `HTML` format for better presentation.  
   - This makes the alert email visually more readable.  

- **Send an email alert using `SMTP`**  
   - The formatted email is sent using the `SMTP` server.  
   - If the `SMTP` connection fails, the worker will retry automatically.  

See the complete logic for processing email content and sending alerts in [`rabbitmq_worker.py`](./rabbitmq_worker.py)

## 7. Testing the Pipeline  
To test the pipeline, I first ran the following three files in separate terminals:

- `rpc_server.py` – To fetch and process emails from Gmail.
- `rpc_client.py` – To clean and analyze the sentiment of the emails.
- `rabbitmq_worker.py` – To send alerts for negative sentiment emails.

Once all three components were running, I sent four test emails to my `Gmail` account defined in `TARGET_EMAIL`:

- *"Sunumda her ne kadar beni hiç biriniz dinlememiş olsa da geldiğiniz için yine de teşekkür ederim."*  
   - This email was correctly identified as `sarcastic` marked as `negative` — An alert was sent to `ALERT_RECIPIENT`.  

- *"Sunuma iştirak ettiğiniz için hepinize teşekkür ederim."*  
   - This email was identified as `positive` — No alert was triggered.  

- *"Sunuma hiç kimse gelmedi. Çok sinirlendim."*  
   - This email was correctly identified as `negative` — An alert was sent to `ALERT_RECIPIENT`.  

- *"Tabii ki bu işin bu kadar karmaşık olacağını kim düşünebilirdi ki? Harika ilerliyoruz gerçekten, bravo bize!"*  
   - This email was correctly identified as `sarcastic` and marked as `negative` — An alert was sent to `ALERT_RECIPIENT`.  

## 8. Conclusion  
We’ve built a complete end-to-end solution to automate email processing using `Gmail API`, `Ollama`, `RabbitMQ`, and `SMTP`.  

### Key Achievements  
- The pipeline successfully handled real-world email processing scenarios, including sarcastic and negative sentiment analysis.  
- The system accurately distinguished between positive, negative, and sarcastic emails.  
- The use of `RabbitMQ's RPC mechanism` demonstrated how effective asynchronous communication can be in handling complex workflows.  

### Future Improvements  
- **Enhanced Llama Integration** – Improve sarcasm detection and multi-language support.  
- **Adaptive Learning** – Learn from feedback and adjust sentiment detection.  
- **Multi-Agent Architecture** – Allow parallel processing for more complex agent networks.  
- **Contextual Awareness** – Improve sentiment accuracy with conversation history.  

This solution serves as a foundational step toward building a fully autonomous `Agentic AI` system.
