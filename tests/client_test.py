# this file do the automated polling of the merchant request to the redis asking that is my request ready.

import time
import requests

BASE_URL = "http://127.0.0.1:8000/api/tickets"

payload = {
    "merchant_id": "gyana",
    "issue_text": "My customer paid 500rs, money was deducted, but it never reached my account."
}

print("1. Submitting ticket to FastAPI...")
post_response = requests.post(BASE_URL, json=payload).json()
ticket_id = post_response["ticket_id"]
print(f"-> Ticket Queued! ID: {ticket_id}\n")

# The System automatically polls the GET route every 3 seconds 
print("2. System is waiting for AI resolution...")
while True:
    get_response = requests.get(f"{BASE_URL}/{ticket_id}").json()

    if get_response["status"] == "completed":
        print("\n=== TICKET RESOLVED ====")
        print(f"category: {get_response['category']}")
        print(f"Merchant: {get_response['merchant_id']}")
        print(f"Resolution:\n{get_response['resolution']}")
        print("====================")
        break
    else:
        print("...Still processing in background worker, checking again in 3s.....")
        time.sleep(3)