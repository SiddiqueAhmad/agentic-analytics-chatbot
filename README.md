# Agentic Analytics Chatbot 🤖

A conversational analytics assistant built with **LangGraph**, **FastAPI**, and **Gemini 2.0**.

This bot uses an **agentic workflow** to securely verify user identity, validate natural language queries, and execute analytics queries against a data source (CubeJS mock). It features persistent memory using **Redis** to remember users across conversation turns.

## 🚀 Key Features

* **Agentic Workflow:** Uses a ReAct loop (Reason + Act) to decide when to call tools.
* **State Persistence:** Redis-backed memory ensures the bot remembers context (like your user ID) across different HTTP requests.
* **Tool Use:**
    * `verify_identity`: Checks email/phone before allowing access.
    * `validate_order_query`: Ensures generated queries are valid before execution.
    * `execute_order_query`: Fetches actual data securely.
* **FastAPI Integration:** Serves the agent as a production-ready REST API.

## 🛠️ Architecture

The flow follows a **Cyclic Graph**:
1.  **Agent Node:** Receives user input -> Decides next step.
2.  **Tool Node:** Executes Python functions (Verify, Validate, Execute).
3.  **Redis Checkpointer:** Saves the state after every step.

## 📋 Prerequisites

* Python 3.11+
* [uv](https://github.com/astral-sh/uv) (Recommended for package management)
* [Docker](https://www.docker.com/) (Required for Redis Stack)

## ⚡ Quick Start

### 1. Clone & Setup
```bash
git clone https://github.com/SiddiqueAhmad/agentic-analytics-chatbot.git
cd agentic-analytics-chatbot
```

### 2. Configure Environment
Create a `.env` file in the root directory:
```bash
# .env
GOOGLE_API_KEY="your_gemini_api_key_here"
REDIS_URL="redis://localhost:6379"
```

### 3. Install Dependencies
Using `uv` (fastest):
```bash
uv sync
```
*Or using pip:*
```bash
pip install -r pyproject.toml
```

### 4. Start Infrastructure
Start **Redis Stack** (Required for LangGraph memory indices):
```bash
docker run -d -p 6379:6379 redis/redis-stack-server:latest
```

### 5. Run the Server
```bash
uv run server.py
# Server will start at [http://0.0.0.0:8000](http://0.0.0.0:8000)
```

---

## 🧪 Usage Examples

You can test the API using `curl`. Note that we use the same `thread_id` to maintain conversation history.

### Step 1: Verification (Turn 1)
User tries to ask a question without being logged in.

```bash
curl -X POST "http://localhost:8000/chat" \
     -H "Content-Type: application/json" \
     -d '{
           "message": "Hi, I need help with my order.", 
           "thread_id": "session_1"
         }'
```
**Bot Response:** *"I need to verify your identity. Please provide your email."*

### Step 2: Provide Credentials (Turn 2)
User provides email. Bot calls `verify_identity` tool.

```bash
curl -X POST "http://localhost:8000/chat" \
     -H "Content-Type: application/json" \
     -d '{
           "message": "It is bob@example.com", 
           "thread_id": "session_1"
         }'
```
**Bot Response:** *"Thanks Bob! You are verified. How can I help?"*

### Step 3: Analytics Query (Turn 3)
User asks for data. Bot remembers the verified ID, generates a query, validates it, and executes it.

```bash
curl -X POST "http://localhost:8000/chat" \
     -H "Content-Type: application/json" \
     -d '{
           "message": "What is my order total?", 
           "thread_id": "session_1"
         }'
```
**Bot Response:** *"Your order total is $100.00"*

---

## 💻 Frontend

The project includes a **Streamlit** frontend designed to demonstrate the agent's capabilities visually. It connects to the backend via Server-Sent Events (SSE) to show real-time "thinking" status updates.

To run the UI:
```bash
uv run streamlit run frontend.py
```
Visit **http://localhost:8501** in your browser to start chatting.

---

## 📂 Project Structure

```text
agentic-analytics-chatbot/
├── server.py           # Main FastAPI entry point & Graph definition
├── frontend.py         # Streamlit UI
├── tools.py            # Tool definitions (Verify, Validate, Execute)
├── system_prompt.py    # LLM Instructions & Guardrails
├── pyproject.toml      # Project dependencies
├── .env                # Secrets (Gitignored)
├── .gitignore          # Git ignore rules
└── README.md           # This file
```