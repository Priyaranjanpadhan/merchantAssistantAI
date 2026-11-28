from dotenv import load_dotenv
from langchain.chat_models import init_chat_model
from typing import TypedDict
from langgraph.graph import StateGraph, START, END

from app.config import settings

class TicketState(TypedDict):
    ticket_id : str
    merchant_id : str
    issue_text : str
    category : str
    resolution : str

def extract_text(response) -> str:
    """Handles both Gemini block-list reponses and plain string responses."""
    content = response.content
    # response.content looks like [{"type": "text", "text": "  BILLING \n"}]
    if isinstance(content, list): # checks: "Is content a python list?" -> True
        return content[0]["text"].strip() #grabs the first dictionary, ["text"] pulls out the string
    return str(content).strip() # If isinstance is False, then it would just return instead of crashing because None[0](will crash)

def get_default_llm():
    load_dotenv()
    # it's not needed as we already have the load_dotenv, init_chat_model can fetch from the .env file/
    # os.environ["GOOGLE_API_KEY"] = os.getenv("GEMINI_API_KEY")

    # as the error is 503, it's temporary and not a bug in code so need to fix it gracefully.
    # In production backend engineering, the graceful way to handle 503/504 errors on a flagship LLM is MODEL FALLBACK(.with_fallbacks())
    primary_model = init_chat_model(
        settings.primary_model,
        timeout=settings.llm_timeout,
        max_retries = settings.llm_max_retries
    )
    backup_model = init_chat_model(
        settings.backup_model,
        timeout=settings.llm_timeout,
        max_retries=settings.llm_max_retries
    )
    return primary_model.with_fallbacks([backup_model])

# conditional edge logic: either biiling_node or tech_node
def router_decision(state: TicketState):
    if "BILLING" in state["category"].upper():
        return "billing_node"
    else:
        return "tech_node"

def build_support_agent(llm=None): # In python writing, llm=None in a function definition makes llm as an optional parameter. If caller passes something that will be llm if not no parameter.
    """Factory that builds and compiles the LangGraph agent with an injected LLM."""
    model = llm if llm is not None else get_default_llm() # in testing, caller gave us a fakemodel just to test, then that fakeLLM will be used in test, but caller doesn't gave us anything then it's the default gemini llm.

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
        # print(response)
        # write the result into the 'category' slot of ticketState.
        return {"category": extract_text(response)}

    # now we need to change the resolution node, for resolution node, we need to have two resoltion one is BILLING and another one is TECHNICAL. so according to that we will change it.
    def billing_node(state: TicketState):
        issue = state["issue_text"]
        merchant = state["merchant_id"]
        prompt = (
            f"You are a professional billing support agent assisting merchant '{merchant}'"
            f"Follow these policies to answer their issue:\n"
            f"1. If money was deducted but didn't reach the receiver: Explain that we must wait 3 business days for bank settlement. If it still hasn't arrived after 3 days, we will process a full refund.\n"
            f"2. If money was sent to the wrong person/account: Politely explain that completed transfers can't be reversed by us, and advise them to contact the recipient directly.\n"
            f"Merchant Issue: {issue}\n"
            f"Write a short, polite response directly to {merchant}.\n"
        )
        response = model.invoke(prompt)
        # print(response)
        return {"resolution": extract_text(response)}

    def tech_node(state: TicketState):
        issue = state["issue_text"]
        merchant = state["merchant_id"]
        prompt = (
            f"You are a professional technical support agent assisting merchant '{merchant}'\n"
            f"Follow these policies to answer their issue:\n"
            f"1. If the payment server is down/500 error: Explain to the merchant to check our status page and implement an automatic retry after 5 minutes.\n"
            f"2. If their API key or webhook is failing: Explain to the merchant to verify their API secret key in the developer dashboard and check that their webhook URL is publicly accessible.\n"
            f"Merchant Issue: {issue}\n"
            f"Write a short, polite response directly to {merchant}.\n"
        )
        response = model.invoke(prompt)
        # print(response)
        return {"resolution": extract_text(response)}

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
    return builder.compile()

if __name__ == "__main__":
    agent = build_support_agent()
    test_ticket = {
        "ticket_id": "test-101",
        "merchant_id": "gyana",
        "issue_text": "payment server is down."
    }
    result = agent.invoke(test_ticket)
    print("CATEGORY: ", result["category"])
    print("RESOLUTION: ", result["resolution"])