from dotenv import load_dotenv
from langchain.chat_models import init_chat_model
from typing import TypedDict
import os
from langgraph.graph import StateGraph, START, END

load_dotenv()
os.environ["GOOGLE_API_KEY"] = os.getenv("GEMINI_API_KEY")

model = init_chat_model("google_genai:gemini-3.7-flash")

class TicketState(TypedDict):
    ticket_id : str
    merchant_id : str
    issue_text : str
    category : str
    resolution : str

# we need to complete the ticketstate for that we need node. we need to complete it because we need to 
# knkow which type of fix is required and what's the resolution. Previously we only have 3 things so from that 
# we have to extract category and resolution so for that we are using node and then we use these nodes in langgraph in START -> END
# fashion so that it will know how to proceed.

# we need a router node which will tell us the which type of category it is. A simple node.
def router_node(state: TicketState):
    # read the issue from the clipboard
    issue = state["issue_text"]

    # Create the prompt using an f-string.
    prompt = (
        f"You are a support router. Classify the merchant issue into strictly one word: BILLING or TECHNICAL.\n"
        f"Example 1: 'Check if my money got credited or not' -> BILLING\n"
        f"Example 2: 'Payment server is down or API error' -> TECHNICAL\n"
        f"Issue to classify: {issue}\n"
        f"Category:"
    )

    # we need to call gemini, model.invoke() is langchain function which will convert our entire prompt model query into a proper backend structure and 
    # make api call to gemini and also it will accept the gemini response and show it to us, that's why langchain is so helpful.
    response = model.invoke(prompt)

    # write the result into the 'category' slot of ticketState.
    return {"category": response.content.strip()}

# now we need to change the resolution node, for resolution node, we need to have two resoltion one is BILLING and another one is TECHNICAL. so according to that we will change it.
def billing_node(state: TicketState):
    issue = state["issue_text"]
    merchant = state["merchant_id"]

    prompt = (
        f"You are a professional billing support agent assisting merchant '{merchant}'"
        f"Follow these policies to answer their issue:\n"
        f"1. If money was deducted but didn't reach the receiver: Explain that we must wait 3 business days for bank settlement. If it still hasn't arrived after 3 days, we will process a full refund.\n"
        f"2. If money was sent to the wrong person/account: Politely explain that completed transfers can't be reversed by us, and advise them to contact the recipient directly."
        f"Merchant Issue: {issue}\n"
        f"Write a short, polite response directly to {merchant}.\n"
    )

    response = model.invoke(prompt)
    return{"resolution": response.content.strip()}

def tech_node(state: TicketState):
    issue = state["issue_text"]
    merchant = state["merchant_id"]

    prompt = (
        f"You are a professional technial support agent assiting merchant '{merchant}'\n"
        f"Follow these policies to answer their issue:\n"
        f"1. If the payment server is down/500 error: Explain to the merchant to check our status page and implement an automatic retry after 5 minutes.\n"
        f"2. If their API key or webhook is failing: Explain to the merchant to verify their API secret key in the develpper dashboard and check that their webhook URL is publicly accessible.\n"
        f"Merchant Issue: {issue}\n"
        f"Write a short, polite response directly to {merchant}.\n"
    )

    response = model.invoke(prompt)
    return{"resolution": response.content.strip()}

# conditional edge logic: either biiling_node or tech_node
def router_decision(state: TicketState):
    if "BILLING" in state["category"].upper():
        return "billing_node"
    else:
        return "tech_node"

# Initialize the graph with your State class
builder = StateGraph(TicketState)

# Registering the nodes in graph: builder.add_node("node_name", function_name)
builder.add_node("router_node", router_node)
builder.add_node("billing_node", billing_node)
builder.add_node("tech_node", tech_node)

# Connect START to the router.
builder.add_edge(START, "router_node")

# add the conditional edge after router_node
builder.add_conditional_edges("router_node", router_decision)

# connect the sub-agents to END so the workflow finishes.
builder.add_edge("billing_node", END)
builder.add_edge("tech_node", END)

# Compile the graph into an executable agent.
support_agent = builder.compile() # we can export this support_agent to other files.