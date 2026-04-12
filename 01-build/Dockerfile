FROM python:3.13-slim

WORKDIR /app

# Copy requirements.txt
COPY requirements.txt .

# Install dependencies. We remove google-adk from requirements.txt dynamically
# to install it with --pre in the next step, avoiding failures if no stable version exists.
RUN grep -v "google-adk" requirements.txt > reqs.txt && pip install -r reqs.txt
RUN pip install google-adk --pre

# Copy the rest of the application
COPY . .

# Expose the port the app runs on
EXPOSE 8080

# Command to run the application
CMD ["uvicorn", "app_server:app", "--host", "0.0.0.0", "--port", "8080"]
