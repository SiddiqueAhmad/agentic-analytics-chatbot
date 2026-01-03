from typing import List, Optional

import uvicorn
from annotated_types import Annotated
from fastapi import FastAPI, HTTPException
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_google_genai import ChatGoogleGenerativeAI
from langgraph.checkpoint.redis import RedisSaver
from langgraph.graph import StateGraph
from langgraph.graph.message import add_messages
from langgraph.prebuilt import ToolNode, tools_condition
from pydantic import BaseModel
from redis import Redis
from typing_extensions import TypedDict

from config import settings
from system_prompt import SYSTEM_PROMPT
from tools import execute_order_query, validate_order_query, verify_identity

redis_client = Redis.from_url(settings.redis_url)

llm = ChatGoogleGenerativeAI(
    model="gemini-2.0-flash-exp", temperature=0, api_key=settings.google_api_key
)


# 1. State
class AgentState(TypedDict):
    messages: Annotated[list, add_messages]
    customer_id: Optional[str]


# 2. Setup Agent
tools = [verify_identity, validate_order_query, execute_order_query]
llm_with_tools = llm.bind_tools(tools)


def assistant_node(state: AgentState):
    messages = state["messages"]

    # Prepend System Prompt if not present
    # (Note: It's safer to check if the *first* message is SystemMessage)
    if not messages or not isinstance(messages[0], SystemMessage):
        messages = [SystemMessage(content=SYSTEM_PROMPT)] + messages

    response = llm_with_tools.invoke(messages)
    return {"messages": [response]}


# 3. Build Graph
workflow = StateGraph(AgentState)

workflow.add_node("agent", assistant_node)
workflow.add_node("tools", ToolNode(tools))

workflow.set_entry_point("agent")

workflow.add_conditional_edges(
    "agent",
    tools_condition,
)

workflow.add_edge("tools", "agent")

checkpointer = RedisSaver(redis_client=redis_client)

checkpointer.create_indexes()
checkpointer.setup()

app_graph = workflow.compile(checkpointer=checkpointer)

app = FastAPI(title="LangGraph Analytics Bot")


class ChatRequest(BaseModel):
    message: str
    thread_id: str  # Unique ID for the user session (e.g., "user-123")


class ChatResponse(BaseModel):
    response: str
    tool_calls: List[str] = []  # Optional: return what tools were used


@app.post("/chat", response_model=ChatResponse)
async def chat_endpoint(request: ChatRequest):
    """
    Main chat endpoint.
    Pass 'thread_id' to maintain conversation history.
    """
    config = {"configurable": {"thread_id": request.thread_id}}

    # Prepare input
    inputs = {"messages": [HumanMessage(content=request.message)]}

    final_response_text = ""
    tool_names = []

    try:
        # We use invoke() instead of stream() for a simple Request/Response API
        # If you want streaming (Server Sent Events), that requires a different setup.
        result = app_graph.invoke(inputs, config=config)

        # Extract the last message (the bot's final answer)
        last_message = result["messages"][-1]
        final_response_text = last_message.content

        # Optional: Inspect history to see which tools were called in this turn
        # This logic iterates backwards to find tool calls from the most recent run
        for msg in reversed(result["messages"]):
            if hasattr(msg, "tool_calls") and msg.tool_calls:
                for tool in msg.tool_calls:
                    tool_names.append(tool["name"])
            # Stop if we hit the user's input (don't scan whole history)
            if isinstance(msg, HumanMessage):
                break

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    return ChatResponse(
        response=final_response_text,
        tool_calls=list(set(tool_names)),  # Remove duplicates
    )


if __name__ == "__main__":
    uvicorn.run("server:app", host="0.0.0.0", port=8000, reload=True)
