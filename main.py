from fastapi import FastAPI, HTTPException, Body
from typing import Annotated
from uuid import uuid4
from pydantic import BaseModel
from redis import Redis
from rq import Queue
from worker import process_tickets
import json
import os

app = FastAPI(title="MerchantAssist AI Backend", version="1.0.0")

# Reads REDIS_HOST from Docker environment, or falls back to localhost
redis_host = os.getenv("REDIS_HOST", "localhost")
redis_conn = Redis(host=redis_host, port=6379)

# Create a queue named support_tickets
ticket_queue = Queue("support_tickets", connection=redis_conn)

# Let's say a merchant is making a request saying hey, payment provider(let's say Razorpay) a payment of 500rs got stuck. Please help. 
# When they hit submit, razorpay frontend sends a POST request to FastAPI backend. The payload includes their unique merchant_id and their issue_text. 
class TicketRequest(BaseModel):
    merchant_id: str
    issue_text: str

@app.post("/api/tickets")
async def generate_ticket(
        ticket: Annotated[
            TicketRequest,
            Body(
                examples={
                    "billing_stuck":{
                        "summary": "1. Billing: Stuck ₹500 Payment",
                        "value": {
                            "merchant_id": "gyana",
                            "issue_text": "My customer paid 500rs, money was deducted, but it never reached my account."
                        }
                    },
                    "billing_wrong_person":{
                        "summary": "2. Billing: Sent to wrong person",
                        "value": {
                            "merchant_id": "razor_merchant",
                            "issue_text": "Your payment server is down and returning a 500 error."
                        }
                    },
                    "tech_server_down":{
                        "summary": "3. Technical: Payment server 500 error",
                        "value": {
                            "merchant_id": "razor_merchant",
                            "issue_text": "Your payment server is down and returning a 500 error."
                        }
                    },
                    "tech_webhook_fail": {
                        "summary": "4. Technical: API key / Webhook Failing",
                        "value": {
                            "merchant_id": "razor_merchant",
                            "issue_text": "My API key is failing and my webhook URL is not receiving events."
                        }
                    }
                }
            )
        ]
    ):
    # Generate a fresh ID every time a request hits this endpoint.
    unique_id = str(uuid4())

    # enqueue function to the queue
    ticket_queue.enqueue(process_tickets, unique_id, ticket.merchant_id, ticket.issue_text)
    return {"ticket_id": unique_id, "status": "queued", "merchant": ticket.merchant_id}

@app.get("/api/tickets/{ticket_id}")
async def get_ticket_status(ticket_id: str):
    key = f"result:{ticket_id}" # you might think that why result: is used but when we used multiple things in redis and maybe other thing has same keyid, so to know which database it belongs to we use this column method so we know which key it is.
    # ask redis if a finished result exists for this ticket_id
    saved_data = redis_conn.get(key)

    # If saved data is none, the worker is still processing it
    if saved_data is None:
        return {"ticket_id" : ticket_id, "status": "processing"}

    # if it exists, convert the JSON string into a python dictionary and return it
    result_dict = json.loads(saved_data)

    # Delete from Redis RAM now that we have retrieved it!
    redis_conn.delete(key)
    return{
        "ticket_id": ticket_id,
        "status": "completed",
        "merchant_id": result_dict["merchant_id"],
        "category": result_dict["category"],
        "issue_text": result_dict["issue_text"],
        "resolution": result_dict["resolution"]
    }
