from fastapi import FastAPI
from uuid import uuid4
from pydantic import BaseModel
from redis import Redis
from rq import Queue
from worker import process_tickets

app = FastAPI()

# Connect to local redis running on port 6379
redis_conn = Redis(host="localhost", port=6379)

# Create a queue named support_tickets
ticket_queue = Queue("support_tickets", connection=redis_conn)

@app.get("/")
def base():
    return {"name": "priyaranjan"}

# Let's say a merchant is making a request saying hey, payment provider(let's say Razorpay) a payment of 500rs got stuck. Please help. 
# When they hit submit, razorpay frontend sends a POST request to FastAPI backend. The payload includes their unique merchant_id and their issue_text. 
class TicketRequest(BaseModel):
    merchant_id: str
    issue_text: str

@app.post("/api/tickets")
async def generate_ticket(ticket: TicketRequest):
    # Generate a fresh ID every time a request hits this endpoint.
    unique_id = str(uuid4())

    # enqueue function to the queue
    job = ticket_queue.enqueue(process_tickets, unique_id, ticket.merchant_id, ticket.issue_text)
    return {"ticket_id": unique_id, "status": "queued", "merchant": ticket.merchant_id}

