from vertexai import agent_engines
from google.adk.agents import Agent
import os
import vertexai
from agents.agent import root_agent
from dotenv import load_dotenv

# Read .env from agents folder
dotenv_path = os.path.join("agents", ".env")
if os.path.exists(dotenv_path):
    load_dotenv(dotenv_path, override=True)

PROJECT_ID = os.environ.get("GOOGLE_CLOUD_PROJECT")
BUCKET = os.environ.get("GCS_BUCKET")
LOCATION = os.environ.get("GOOGLE_CLOUD_LOCATION")
ENV = "prod"
stripe_secret_key = os.environ.get("STRIPE_SECRET_KEY")

ENDPOINT = f"{LOCATION}-aiplatform.googleapis.com"

print(f"Initializing Vertex AI with project={PROJECT_ID}, bucket={BUCKET}, endpoint={ENDPOINT}")
vertexai.init(
    project=PROJECT_ID,
    location=LOCATION,
    staging_bucket=f"gs://{BUCKET}",
    api_endpoint=ENDPOINT,
)

print("Creating AdkApp...")
app = agent_engines.AdkApp(
    agent=root_agent,
    app_name="shopping_squad",
    enable_tracing=True,
)
app.set_up()

print("Deploying agent to Agent Engine...")
remote_agent = agent_engines.create(
    app,
    display_name='Shopping Squad',
    requirements=[
        "google-adk==2.0.0a3",
        "stripe>=15.0.1",
        "python-dotenv>=1.2.2",
    ],
    extra_packages=["./agents"],
    env_vars={
        'GOOGLE_CLOUD_AGENT_ENGINE_ENABLE_TELEMETRY': 'true',
        'OTEL_INSTRUMENTATION_GENAI_CAPTURE_MESSAGE_CONTENT': 'true',
        'PROJECT_ID': PROJECT_ID,
        'STRIPE_SECRET_KEY': stripe_secret_key or '',
    },
)
print(f"Successfully deployed agent: {remote_agent.resource_name}")
