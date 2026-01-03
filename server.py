from typing import Annotated, Any, Dict, List, Optional

import uvicorn
from fastapi import FastAPI, HTTPException
from langchain_core.messages import BaseMessage, HumanMessage, SystemMessage
from langchain_core.runnables import RunnableConfig

# --- LangChain / LangGraph Imports ---
from langchain_google_genai import ChatGoogleGenerativeAI
from langgraph.checkpoint.redis import RedisSaver
from langgraph.graph import StateGraph
from langgraph.graph.message import add_messages
from langgraph.prebuilt import ToolNode, tools_condition
from pydantic import BaseModel
from redis import Redis
from typing_extensions import TypedDict

# --- Local Imports ---
from config import settings
from system_prompt import SYSTEM_PROMPT
from tools import execute_order_query, validate_order_query, verify_identity

# 1. Setup Redis & LLM
# Note: 'conn' is the standard argument for RedisSaver
redis_client = Redis.from_url(settings.redis_url)
checkpointer = RedisSaver(redis_client=redis_client)

# Initialize Redis indices (Required for search/memory)
# Note: Ensure your Redis instance supports RediSearch (redis/redis-stack-server)
checkpointer.setup()

llm = ChatGoogleGenerativeAI(
    model="gemini-2.0-flash-exp", temperature=0, api_key=settings.google_api_key
)


# 2. State Definition
class AgentState(TypedDict):
    # FIX: Explicitly specify List[BaseMessage] for strict typing
    messages: Annotated[List[BaseMessage], add_messages]
    customer_id: Optional[str]


# 3. Setup Agent Nodes
tools = [verify_identity, validate_order_query, execute_order_query]
llm_with_tools = llm.bind_tools(tools)


# FIX: Add return type -> Dict[str, Any]
def assistant_node(state: AgentState) -> Dict[str, Any]:
    messages = state["messages"]

    # Prepend System Prompt if not present
    if not messages or not isinstance(messages[0], SystemMessage):
        messages = [SystemMessage(content=SYSTEM_PROMPT)] + messages

    response = llm_with_tools.invoke(messages)
    return {"messages": [response]}


# 4. Build Graph
workflow = StateGraph(AgentState)

workflow.add_node("agent", assistant_node)
workflow.add_node("tools", ToolNode(tools))

workflow.set_entry_point("agent")

workflow.add_conditional_edges("agent", tools_condition)
workflow.add_edge("tools", "agent")

app_graph = workflow.compile(checkpointer=checkpointer)

# 5. FastAPI App
app = FastAPI(title="LangGraph Analytics Bot")


class ChatRequest(BaseModel):
    message: str
    thread_id: str


class ChatResponse(BaseModel):
    response: str
    tool_calls: List[str] = []


# In server.py


@app.post("/chat", response_model=ChatResponse)
async def chat_endpoint(request: ChatRequest) -> ChatResponse:
    """
    Main chat endpoint.
    Pass 'thread_id' to maintain conversation history.
    """
    # FIX: Explicitly type hint 'config' as RunnableConfig
    config: RunnableConfig = {"configurable": {"thread_id": request.thread_id}}

    inputs = {"messages": [HumanMessage(content=request.message)]}

    final_response_text = ""
    tool_names: List[str] = []

    try:
        # invoke returns a dict-like state, but MyPy doesn't know the exact shape.
        result = app_graph.invoke(inputs, config=config)

        # Extract messages
        messages = result["messages"]
        last_message = messages[-1]

        # Ensure content is a string
        final_response_text = str(last_message.content)

        # Inspect history for tool calls
        for msg in reversed(messages):
            if hasattr(msg, "tool_calls") and msg.tool_calls:
                for tool_call in msg.tool_calls:
                    tool_names.append(tool_call["name"])

            if isinstance(msg, HumanMessage):
                break

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    return ChatResponse(
        response=final_response_text,
        tool_calls=list(set(tool_names)),
    )


if __name__ == "__main__":
    uvicorn.run("server:app", host="0.0.0.0", port=8000, reload=True)
