import json

import requests
import streamlit as st

# --- Page Config ---
st.set_page_config(page_title="Agentic Analytics Bot", page_icon="🤖")

st.title("🤖 Agentic Analytics Assistant")
st.caption("Powered by LangGraph, FastAPI, and Redis")

# --- Sidebar: Configuration ---
with st.sidebar:
    st.header("Configuration")
    thread_id = st.text_input(
        "Thread ID", value="demo_user_1", help="Unique session ID to maintain memory."
    )
    if st.button("Clear Chat History"):
        st.session_state.messages = []
        st.rerun()

API_URL = "http://localhost:8000/stream"

# --- Session State for Chat History ---
if "messages" not in st.session_state:
    st.session_state.messages = []

# --- Display Chat History ---
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

# --- Handle User Input ---
if prompt := st.chat_input("Ask about your orders..."):
    # 1. Display User Message
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    # 2. Display Assistant Response (Streaming)
    with st.chat_message("assistant"):
        message_placeholder = st.empty()
        status_placeholder = st.empty()
        full_response = ""

        try:
            # Connect to the SSE stream
            with requests.post(
                API_URL, json={"message": prompt, "thread_id": thread_id}, stream=True
            ) as response:
                # Check for HTTP errors (e.g., 500)
                if response.status_code != 200:
                    st.error(f"Error: {response.text}")
                else:
                    # Process the stream line by line
                    for line in response.iter_lines():
                        if line:
                            decoded_line = line.decode("utf-8")
                            if decoded_line.startswith("data: "):
                                json_str = decoded_line[6:]  # Strip "data: "

                                if json_str == "[DONE]":
                                    break

                                try:
                                    data = json.loads(json_str)
                                    event_type = data.get("type")
                                    content = data.get("content")

                                    # CASE A: Status Update (Tool Calls)
                                    if event_type == "status":
                                        with status_placeholder.status(
                                            "Thinking...", expanded=True
                                        ) as s:
                                            st.write(content)
                                            s.update(label=content, state="running")

                                    # CASE B: Final Result (The actual answer)
                                    elif event_type == "result":
                                        status_placeholder.empty()  # Remove status box
                                        full_response = content
                                        message_placeholder.markdown(
                                            full_response + "▌"
                                        )

                                    # CASE C: Error
                                    elif event_type == "error":
                                        st.error(content)

                                except json.JSONDecodeError:
                                    continue

                    # Final Polish: Remove cursor
                    message_placeholder.markdown(full_response)

                    # Add to history
                    st.session_state.messages.append(
                        {"role": "assistant", "content": full_response}
                    )

        except Exception as e:
            st.error(f"Connection Error: {e}")
