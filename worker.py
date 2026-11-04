from agent import support_agent
import json
from redis import Redis

redis_conn = Redis(host="localhost", port=6379)

def process_tickets(ticket_id: str, merchant_id: str, issue_text: str):
    # printing so that we can see whose ticket was going on.
    print(f"Processing ticket {ticket_id} for {merchant_id}.....")

    # creating the initial state so that we can send it to support_agent as TicketState
    initial_state = {"ticket_id": ticket_id, "merchant_id" : merchant_id, "issue_text": issue_text}

    result = support_agent.invoke(initial_state)

    # save result into redis as a json style not the dictionary.
    # we saved it, so that we can use this to display in the main terminal, when the main terminal asks for this key, is it ready, if it is ready we will send it and if not we will make them wait.
    # we are putting a 1-hour safety expiration, if the client didn't fetch during that time, we will delete the data so memory leak can't happen.
    redis_conn.set(f"result:{ticket_id}", json.dumps(result), ex=3600)

    # print(f"Ticket {ticket_id} resolved under category: {result['category']}")

    return result