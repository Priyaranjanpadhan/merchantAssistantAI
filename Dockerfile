# 1. Downloads a clean, lightweight version of Linux pre-installed with Python3.12
FROM python:3.12-slim

# 2. Prevent Python from buffering stdout/stderr (so logs show up in real-time in Docker/AWS)
ENV PYTHONBUFFERED=1

# 3. Creates a folder named /app inside that Linux container and moves inside it(like running cd /app). 
WORKDIR /app

# 4. Copies only your requirements.txt file from your Mac into the container's /app folder.
COPY requirements.txt .

# 5. Runs pip install inside the Linux container to download all your Python libraries.
RUN pip install --no-cache-dir -r requirements.txt

# 6. Copies the rest of your project files (main.py, worker.py, agent.py) into /app.
# We copy requirements.txt first and code second to leverage Docker Layer Caching. 
# If you change a line of code in main.py tomorrow, Docker won't waste time re-installing all your pip packages
COPY . .

# 7. Tells Docker what command to run automatically the second the container boots up.
# By default, if a web server binds to 127.0.0.1(localhost), it only listens to traffic originating from inside itself.
# If device let's say visits 127.0.0.1:8000, it will move to mac's network and not container.
# By telling Uvicorn to host on 0.0.0.0, you tell the server: "Listen to all network interfaces". This allows from mac browser to cross the container boundary and reach FastAPI app.
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]