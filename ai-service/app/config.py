import os
from pathlib import Path

DATA_DIR = Path(os.getenv('DATA_DIR', './var'))
DATA_DIR.mkdir(parents=True, exist_ok=True)
DATABASE_URL = os.getenv('DATABASE_URL', f'sqlite:///{DATA_DIR}/assessments.db')
CHECKPOINT_URL = os.getenv('CHECKPOINT_URL', '')
SERVICE_TOKEN = os.getenv('SERVICE_TOKEN', 'local-demo-internal-token')
LLM_MODE = os.getenv('LLM_MODE', 'mock')
LLM_BASE_URL = os.getenv('LLM_BASE_URL', 'http://localhost:8001/v1')
LLM_API_KEY = os.getenv('LLM_API_KEY', '')
LLM_MODEL = os.getenv('LLM_MODEL', 'your-model-name')
INPUT_USD_PER_MILLION = float(os.getenv('INPUT_USD_PER_MILLION', '0'))
OUTPUT_USD_PER_MILLION = float(os.getenv('OUTPUT_USD_PER_MILLION', '0'))
QDRANT_URL = os.getenv('QDRANT_URL', '')
RETRIEVAL_MODE = os.getenv('RETRIEVAL_MODE', 'local')
LEASE_SECONDS = int(os.getenv('LEASE_SECONDS', '300'))
CORS_ORIGINS = os.getenv('CORS_ORIGINS', '')   # comma-separated allowed origins
MAX_ATTEMPTS = 3
