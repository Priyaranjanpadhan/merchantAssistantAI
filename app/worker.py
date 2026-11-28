import json
from redis import Redis

from app.agent import build_support_agent
from app.config import settings

def get_redis_conn() -> Redis:
    return Redis(host=settings.redis_host, port=settings.redis_port)

# maybe you think why can't we just write get_redis_conn in parameter(), but that would trigger function call as soon as python reaches there.
# Python would try to connect to Redis at the moment worker.py is imported defeating out entire lazy initialization goal. 
# Using =None + if ... is not None else ... delays creating Redis/Gemini until the function is actually called. 
def process_tickets(ticket_id: str, merchant_id: str, issue_text: str, agent=None, redis_conn=None):
    # printing so that we can see whose ticket was going on.
    print(f"Processing ticket {ticket_id} for {merchant_id}.....")

    # If a test passed a fake agent, use it: otherwise BUILD the real agent!
    support_agent = agent if agent is not None else build_support_agent()

    # If a test passed fakeredis, use it; otherwise CONNECT to a real redis.
    redis_client = redis_conn if redis_conn is not None else get_redis_conn

    # creating the initial state so that we can send it to support_agent as TicketState
    initial_state = {
        "ticket_id": ticket_id, 
        "merchant_id" : merchant_id, 
        "issue_text": issue_text
    }

    # Invoke the LangGraph multi-agent workflow.
    result = support_agent.invoke(initial_state)

    # save result into redis as a json style not the dictionary.
    # we saved it, so that we can use this to display in the main terminal, when the main terminal asks for this key, is it ready, if it is ready we will send it and if not we will make them wait.
    # we are putting a 1-hour safety expiration, if the client didn't fetch during that time, we will delete the data so memory leak can't happen.
    result["status"] = "completed" # Mark status as completed and save in Redis
    redis_client.set(f"result:{ticket_id}", json.dumps(result), ex=settings.result_ttl_seconds)

    print(f"Ticket {ticket_id} resolved under category: {result['category']}")
    return result