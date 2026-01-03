import json
import traceback
from contextlib import asynccontextmanager
from typing import Annotated, Any, Dict, List, Optional, cast

import uvicorn
from fastapi import FastAPI, HTTPException
from fastapi.responses import StreamingResponse
from langchain_core.messages import BaseMessage, HumanMessage, SystemMessage
from langchain_core.runnables import RunnableConfig

# --- LangChain / LangGraph Imports ---
from langchain_google_genai import ChatGoogleGenerativeAI

# --- FIX 1: Use ASYNC Redis Libraries ---
from langgraph.checkpoint.redis import AsyncRedisSaver
from langgraph.graph import StateGraph
from langgraph.graph.message import add_messages
from langgraph.prebuilt import ToolNode, tools_condition
from pydantic import BaseModel
from redis.asyncio import Redis as AsyncRedis  # Note the 'asyncio' import
from typing_extensions import TypedDict

# --- Local Imports ---
from config import settings
from system_prompt import SYSTEM_PROMPT
from tools import execute_order_query, validate_order_query, verify_identity

# --- 2. Global Setup ---
# We declare these globally but initialize them in the 'lifespan' (startup)
redis_client: AsyncRedis = None  # type: ignore
checkpointer: AsyncRedisSaver = None  # type: ignore
app_graph = None

# LLM setup (Async by default in LangChain)
llm = ChatGoogleGenerativeAI(
    model="gemini-2.0-flash-exp", temperature=0, api_key=settings.google_api_key
)


# --- 3. Graph Definition ---
class AgentState(TypedDict):
    messages: Annotated[List[BaseMessage], add_messages]
    customer_id: Optional[str]


tools = [verify_identity, validate_order_query, execute_order_query]
llm_with_tools = llm.bind_tools(tools)


# Note: We can keep this sync, LangGraph handles it.
# But for max performance, you could make it 'async def' too.
def assistant_node(state: AgentState) -> Dict[str, Any]:
    messages = state["messages"]
    if not messages or not isinstance(messages[0], SystemMessage):
        messages = [SystemMessage(content=SYSTEM_PROMPT)] + messages
    response = llm_with_tools.invoke(messages)
    return {"messages": [response]}


workflow = StateGraph(AgentState)
workflow.add_node("agent", assistant_node)
workflow.add_node("tools", ToolNode(tools))
workflow.set_entry_point("agent")
workflow.add_conditional_edges("agent", tools_condition)
workflow.add_edge("tools", "agent")


# --- 4. Application Lifecycle (Startup/Shutdown) ---
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: Connect to Redis Async
    global redis_client, checkpointer, app_graph

    redis_client = AsyncRedis.from_url(settings.redis_url)
    checkpointer = AsyncRedisSaver(redis_client=redis_client)

    # Create indices (Important for AsyncRedisSaver too)
    # We await it because we are in an async startup function
    await checkpointer.asetup()

    # Compile the graph with the ASYNC checkpointer
    app_graph = workflow.compile(checkpointer=checkpointer)

    yield

    # Shutdown: Close connections
    await redis_client.aclose()


# --- 5. FastAPI App ---
app = FastAPI(title="LangGraph Async Bot", lifespan=lifespan)


class ChatRequest(BaseModel):
    message: str
    thread_id: str


class ChatResponse(BaseModel):
    response: str
    tool_calls: List[str] = []


# --- Endpoint 1: Standard Chat (Now Async) ---
@app.post("/chat", response_model=ChatResponse)
async def chat_endpoint(request: ChatRequest) -> ChatResponse:
    if app_graph is None:
        raise HTTPException(status_code=500, detail="Graph not initialized")

    config: RunnableConfig = {"configurable": {"thread_id": request.thread_id}}
    inputs = cast(AgentState, {"messages": [HumanMessage(content=request.message)]})

    try:
        # FIX 2: Use 'ainvoke' (Async Invoke)
        # We must use ainvoke because our checkpointer is Async
        result = await app_graph.ainvoke(inputs, config=config)

        messages = result["messages"]
        last_message = messages[-1]

        tool_names = []
        for msg in reversed(messages):
            if hasattr(msg, "tool_calls") and msg.tool_calls:
                for tool in msg.tool_calls:
                    tool_names.append(tool["name"])
            if isinstance(msg, HumanMessage):
                break

        return ChatResponse(
            response=str(last_message.content),
            tool_calls=list(set(tool_names)),
        )

    except Exception as e:
        # Improved Error Logging
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


# --- Endpoint 2: Streaming Chat (SSE) ---
# --- Endpoint 2: Streaming Chat (SSE) ---
@app.post("/stream")
async def stream_chat(request: ChatRequest):
    if app_graph is None:
        raise HTTPException(status_code=500, detail="Graph not initialized")

    config: RunnableConfig = {"configurable": {"thread_id": request.thread_id}}
    inputs = cast(AgentState, {"messages": [HumanMessage(content=request.message)]})

    async def event_generator():
        try:
            async for event in app_graph.astream(inputs, config=config):
                for node_name, state_update in event.items():
                    if node_name == "agent":
                        last_msg = state_update["messages"][-1]

                        if last_msg.tool_calls:
                            # --- FIX: Calculate variable first to avoid quote collision ---
                            tool_name = last_msg.tool_calls[0]["name"]
                            payload = {
                                "type": "status",
                                "content": f"Calling {tool_name}...",
                            }
                            yield f"data: {json.dumps(payload)}\n\n"
                        else:
                            # Final result
                            payload = {"type": "result", "content": last_msg.content}
                            yield f"data: {json.dumps(payload)}\n\n"

                    elif node_name == "tools":
                        payload = {
                            "type": "status",
                            "content": "Tool execution finished.",
                        }
                        yield f"data: {json.dumps(payload)}\n\n"

            yield "data: [DONE]\n\n"

        except Exception as e:
            traceback.print_exc()
            error_msg = str(e) if str(e) else "Unknown Internal Error"
            payload = {"type": "error", "content": error_msg}
            yield f"data: {json.dumps(payload)}\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream")


if __name__ == "__main__":
    uvicorn.run("server:app", host="0.0.0.0", port=8000, reload=True)
