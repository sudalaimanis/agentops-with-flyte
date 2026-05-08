import argparse
import requests
from dotenv import load_dotenv

from langchain_core.tools import tool
from langchain_core.messages import ToolMessage
from langchain_google_genai import ChatGoogleGenerativeAI

from langgraph.graph import StateGraph, END

# -----------------------------
# LOAD ENV
# -----------------------------
load_dotenv()

# -----------------------------
# HELPER: Clean text output
# -----------------------------
def extract_text(content):
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return "\n".join(
            item.get("text", "")
            for item in content
            if isinstance(item, dict) and item.get("type") == "text"
        )
    return str(content)

# -----------------------------
# TOOL 
# -----------------------------
@tool("get_weather_forecast")
def get_weather_forecast(location: str = "Hyderabad", date: str = "today") -> str:
    """
    Fetch weather forecast (defaults to Hyderabad if missing)
    """

    response = requests.get(
        "https://api.open-meteo.com/v1/forecast",
        params={
            "latitude": 17.38,
            "longitude": 78.48,
            "hourly": "temperature_2m",
        },
    )

    data = response.json()
    temps = data["hourly"]["temperature_2m"][:5]

    return f"Temperatures in {location}: {temps}"

# -----------------------------
# MODEL
# -----------------------------
model = ChatGoogleGenerativeAI(
    model="gemini-2.5-flash",
    temperature=0.2,
).bind_tools([get_weather_forecast])

# -----------------------------
# NODES
# -----------------------------
def call_model(state):
    messages = state["messages"]
    response = model.invoke(messages)

    # DEBUG (optional)
    # print("TOOL CALLS:", response.tool_calls)

    return {"messages": messages + [response]}


def call_tool(state):
    last_message = state["messages"][-1]

    tool_call = last_message.tool_calls[0]
    result = get_weather_forecast.invoke(tool_call["args"])

    tool_message = ToolMessage(
        content=result,
        tool_call_id=tool_call["id"],
    )

    return {"messages": state["messages"] + [tool_message]}

# -----------------------------
# ROUTER
# -----------------------------
def should_continue(state):
    last_message = state["messages"][-1]

    if getattr(last_message, "tool_calls", None):
        return "tool"
    return END

# -----------------------------
# GRAPH
# -----------------------------
workflow = StateGraph(dict)

workflow.add_node("llm", call_model)
workflow.add_node("tool", call_tool)

workflow.set_entry_point("llm")

workflow.add_conditional_edges(
    "llm",
    should_continue,
    {
        "tool": "tool",
        END: END,
    },
)

workflow.add_edge("tool", "llm")

graph = workflow.compile()

# -----------------------------
# RUN AGENT
# -----------------------------
def run_agent(prompt: str):
    result = graph.invoke({
        "messages": [
            ("system", "You are a weather assistant. Always call the get_weather_forecast tool when asked about weather. Extract location from the user query."),
            ("user", prompt),
        ]
    })

    final_message = result["messages"][-1]
    return extract_text(final_message.content)

# -----------------------------
# CLI
# -----------------------------
def main():
    parser = argparse.ArgumentParser(description="Weather Agent (LangGraph)")
    parser.add_argument("--prompt", type=str, required=True)

    args = parser.parse_args()

    result = run_agent(args.prompt)

    print("\n--- FINAL ANSWER ---\n")
    print(result.strip())


if __name__ == "__main__":
    main()