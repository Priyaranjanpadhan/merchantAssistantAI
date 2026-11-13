# MerchantAssist AI — Asynchronous Multi-Agent Support Triage Engine

![Python](https://img.shields.io/badge/Python-3.12+-3776AB?style=flat&logo=python&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-009688?style=flat&logo=fastapi&logoColor=white)
![Redis](https://img.shields.io/badge/Redis_Queue_(RQ)-DC382D?style=flat&logo=redis&logoColor=white)
![LangGraph](https://img.shields.io/badge/LangGraph-Multi--Agent-1C3C3C?style=flat)
![Google Gemini](https://img.shields.io/badge/Google_Gemini-3.8_Flash-4285F4?style=flat&logo=google&logoColor=white)
![Docker](https://img.shields.io/badge/Docker_Compose-2496ED?style=flat&logo=docker&logoColor=white)
![GitHub Actions](https://img.shields.io/badge/CI%2FCD-GitHub_Actions-2088FF?style=flat&logo=github-actions&logoColor=white)
![AWS EC2](https://img.shields.io/badge/AWS-EC2-FF9900?style=flat&logo=amazon-aws&logoColor=white)

An event-driven, asynchronous AI backend that triages, routes, and resolves merchant support tickets using **FastAPI**, **Redis & Python RQ**, **LangGraph**, and **Google Gemini**, containerized with **Docker Compose** and continuously deployed to **AWS EC2** via **GitHub Actions**.

> **Project Status (Foundational v1.0 — Active Development):**  
> This repository represents the **foundational asynchronous core** of the system, built to demonstrate non-blocking LLM ingestion, message queuing, multi-agent routing, and automated cloud CI/CD. It is an evolving architecture upcoming iterations will integrate **Retrieval-Augmented Generation (RAG)** over live merchant policy knowledge bases and expand into a broader **multi-system distributed architecture**.

---

## 1. The Engineering Problem & Solution

### The Problem: Synchronous LLM Bottlenecks
In payment gateways and merchant platforms (e.g., Razorpay, Stripe), thousands of merchants submit support tickets simultaneously regarding stuck settlements, failed webhooks, or 500 server errors. Calling an LLM directly inside a synchronous HTTP `POST` request blocks the web server thread for **5 to 15 seconds** per ticket, quickly exhausting worker threads and causing cascading timeouts under load.

### The Solution: Decoupled Producer–Consumer Architecture
**MerchantAssist AI** decouples ticket ingestion from AI inference:
1. **Non-Blocking Ingestion:** FastAPI validates the incoming merchant payload, assigns a unique `ticket_id` (UUID4), enqueues the job into **Redis**, and returns `"status": "queued"` without waiting for LLM processing.
2. **Background Multi-Agent Execution:** An isolated **Python RQ Worker** pulls jobs from Redis and executes a **LangGraph `StateGraph`** workflow. A Router Agent classifies the issue (`BILLING` vs. `TECHNICAL`) and routes it via conditional edges to a specialized domain sub-agent.
3. **Ephemeral State & Polling:** Completed resolutions are serialized into Redis under a namespaced key (`result:{ticket_id}`) with automatic TTL expiration and delete-on-read memory cleanup.

---

## 2. System Architecture & Data Flow

```text
[Client / Merchant System (client_test.py or Swagger UI)]
   │
   ├──► 1. POST /api/tickets (merchant_id, issue_text)
   │         │
   │         ▼
   │    [FastAPI Web Server (main.py)]
   │      • Validates payload via Pydantic (TicketRequest)
   │      • Generates UUID4 ticket_id
   │      • Enqueues job into Redis Queue ("support_tickets")
   │      • Instantly returns {"ticket_id": "...", "status": "queued"}
   │
   │    =======================================================================
   │    ASYNC BACKGROUND PIPELINE (Decoupled from HTTP Thread)
   │
   │    [Redis Broker (Port 6379)] ──► [RQ Worker (worker.py)]
   │                                      │
   │                                      ▼ Invokes LangGraph (agent.py)
   │                             ┌────────────────────────┐
   │                             │      router_node       │
   │                             │ (Classifies Issue Type)│
   │                             └───────────┬────────────┘
   │                                         │ Conditional Edge (router_decision)
   │                            ┌────────────┴────────────┐
   │                            ▼                         ▼
   │                 ┌────────────────────┐    ┌────────────────────┐
   │                 │    billing_node    │    │     tech_node      │
   │                 │ (Settlement/Refund │    │ (500 Errors/API Key│
   │                 │   Policy Engine)   │    │  & Webhook Policy) │
   │                 └──────────┬─────────┘    └──────────┬─────────┘
   │                            └────────────┬────────────┘
   │                                         ▼
   │                   Writes JSON to Redis (`result:{ticket_id}`, ex=3600)
   │    =======================================================================
   │
   └──► 2. GET /api/tickets/{ticket_id} (Automated Short Polling)
             │
             ├──► While Worker is Running: Returns {"status": "processing"}
             └──► When Worker Completes:   Fetches JSON, deletes key from Redis RAM,
                                           and returns {"status": "completed", ...}
```

---

## 3. Key Engineering Highlights

* **Stateful Multi Agent Routing (`LangGraph`):** Uses a strictly typed `TicketState` (`TypedDict`) shared across graph nodes (`START` $\rightarrow$ `router_node` $\rightarrow$ `billing_node` | `tech_node` $\rightarrow$ `END`).
* **Production LLM Resilience (`.with_fallbacks()`):** Configured with a primary Gemini model (15s timeout, 1 retry) and a backup model. If the primary model request fails, LangChain can try the configured fallback model.
* **In Memory Lifecycle & RAM Protection:**
  * **Key Namespacing:** Separates finished ticket payloads (`result:{ticket_id}`) from internal RQ queue registries (`rq:queue:support_tickets`).
  * **Delete on Read + TTL Backup:** Immediately deletes resolved tickets from Redis RAM (`redis_conn.delete()`) upon client retrieval, backed by a 1 hour TTL (`ex=3600`) so abandoned tickets never cause Out Of Memory(OOM) leaks.
* **Single Image Multi Container Orchestration:** Both the FastAPI web server (`merchantassistai_api`) and the background worker (`merchantassistai_worker`) are built from a single layer-cached `Dockerfile` and orchestrated alongside `redis:7-alpine` via `docker-compose.yml`.
* **Automated CI/CD Pipeline (`GitHub Actions` $\rightarrow$ `AWS EC2`):**
  * **Continuous Integration (CI):** Spins up an Ubuntu runner on every push to `main`, builds the Docker images, boots the multi-container stack, and runs a live health check (`curl -f http://localhost:8000/docs`).
  * **Continuous Deployment (CD):** If and only if CI passes (`needs: build-and-test`), SSHes into the production AWS EC2 instance, pulls the latest commit, injects production secrets, rebuilds containers in detached mode, and prunes dangling images.

---

## 4. Accessing the FastAPI Interface (`/docs`)

FastAPI automatically generates an interactive **OpenAPI (Swagger UI)** dashboard where you can inspect the request/response schemas and trigger the asynchronous pipeline directly from your browser:

### Live AWS Cloud Deployment
Navigate to the deployed EC2 instance IP on port `8000` with `/docs` appended:
```text
http://<AWS_EC2_PUBLIC_IP>:8000/docs
```


### Local Development
When running locally via Docker Compose or Uvicorn, open:
```text
http://localhost:8000/docs
```

### How to Test via Swagger UI
1. Expand **`POST /api/tickets`**, click **Try it out**, enter a `merchant_id` and `issue_text`, and click **Execute**.
2. Copy the returned `ticket_id` UUID from the response body.
3. Expand **`GET /api/tickets/{ticket_id}`**, paste the `ticket_id`, and click **Execute** to retrieve the categorized AI resolution once the background worker finishes processing.

---

## 5. Repository Structure

```text
merchantAssistantAI/
├── .github/
│   └── workflows/
│       └── deploy.yml       # GitHub Actions CI/CD pipeline (Build, Health Check & AWS EC2 Deploy)
├── agent.py                 # LangGraph StateGraph, TicketState schema, Router & Sub-Agent nodes
├── worker.py                # Python RQ background consumer & Redis result serialization
├── main.py                  # FastAPI application (POST ingestion & GET polling endpoints)
├── client_test.py           # Automated client polling simulation script
├── Dockerfile               # Python 3.12-slim image with Docker layer caching
├── docker-compose.yml       # Orchestrates redis, api, and worker containers
├── requirements.txt         # Locked Python dependencies
├── .dockerignore            # Excludes local .venv, .env, and cache from Docker build context
└── .gitignore               # Protects secrets (.env) and local artifacts from Git tracking
```

---

## 6. Running the Project Locally

### Option A: Run with Docker Compose (Recommended)

1. **Clone the repository:**
   ```bash
   git clone https://github.com/Priyaranjanpadhan/merchantAssistantAI.git
   cd merchantAssistantAI
   ```
2. **Create your `.env` file:**
   ```bash
   echo "GEMINI_API_KEY=your_google_gemini_api_key" > .env
   ```
3. **Build and start all 3 containers (`redis`, `api`, `worker`):**
   ```bash
   docker compose up --build
   ```
4. **Access the API:**
   * Interactive Swagger UI: `http://localhost:8000/docs`
   * Or run the automated polling script in a separate terminal:
     ```bash
     python3 client_test.py
     ```

### Option B: Run Manually with Python Virtual Environment

1. **Start Redis via Docker:**
   ```bash
   docker run -d --name merchant-redis -p 6379:6379 redis:7-alpine
   ```
2. **Create and activate a virtual environment:**
   ```bash
   python3 -m venv .venv
   source .venv/bin/activate
   pip install -r requirements.txt
   ```
3. **Start the FastAPI Server (Terminal 1):**
   ```bash
   uvicorn main:app --reload
   ```
4. **Start the RQ Background Worker (Terminal 2):**
   ```bash
   # On Linux:
   rq worker support_tickets

   # On macOS (avoids Objective-C fork() safety crashes):
   rq worker -w rq.SimpleWorker support_tickets
   ```
5. **Run the Automated Polling Client (Terminal 3):**
   ```bash
   python3 client_test.py
   ```

---

## 7. CI/CD & AWS EC2 Deployment Setup

The `.github/workflows/deploy.yml` pipeline deploys pushes to `main` onto an **AWS EC2 Ubuntu** instance in two stages:

1. **Continuous integration:** GitHub Actions builds the Docker Compose services, starts them, and checks that the FastAPI documentation endpoint responds successfully.
2. **Continuous deployment:** Only after the CI job succeeds, GitHub Actions connects to EC2 over SSH, pulls the latest `main` branch, writes the production Gemini key to `.env`, rebuilds the containers, and starts them in detached mode.

### EC2 prerequisites

The EC2 instance must have the following installed and configured:

* Ubuntu with the `ubuntu` SSH user
* Git
* Docker Engine
* Docker Compose plugin (`docker compose`)
* An AWS Security Group rule allowing inbound TCP traffic on port `8000`

To configure deployment on your own fork, add the following Repository Secrets under **GitHub Settings $\rightarrow$ Secrets and variables $\rightarrow$ Actions**:

| Secret Name | Description |
| :--- | :--- |
| `EC2_HOST` | Public IPv4 address of the target AWS EC2 instance |
| `EC2_SSH_KEY` | Full contents of the `.pem` private key for the `ubuntu` user |
| `GEMINI_API_KEY` | Production Google Gemini API key injected into `.env` on EC2 |

Never commit `.env`, API keys, `.pem` files, or SSH private keys to the repository.

### Deployment troubleshooting

* **`Error: missing server host`:** Check that the secret is named exactly `EC2_HOST` and contains the EC2 public IPv4 address or public DNS name.
* **`ssh: no key found` or `unable to authenticate`:** Replace `EC2_SSH_KEY` with the complete contents of the EC2 private `.pem` file. Do not use the `.pub` file. The key must include its `BEGIN` and `END` lines.
* **`Permission denied (publickey)`:** Confirm that the key belongs to the EC2 instance, the SSH username is `ubuntu`, and the instance security group allows inbound TCP port `22` from GitHub Actions.
* **`docker: command not found`:** Install Docker Engine and the Docker Compose plugin on the EC2 instance, then verify them with `docker --version` and `docker compose version`.
* **Containers start but the API is unreachable:** Confirm that port `8000` is allowed by the EC2 Security Group and check the server logs with:

  ```bash
  sudo docker compose ps
  sudo docker compose logs --tail=100 api worker
  ```

* **The worker cannot process tickets:** Confirm that the Redis, API, and worker services are all running and that the API and worker use `REDIS_HOST=redis` inside Docker Compose.
* **Gemini requests fail:** Confirm that `GEMINI_API_KEY` is present in the EC2 `.env` file and that the key is active. Never print the key in logs or commit it to Git.