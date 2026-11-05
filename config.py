import os
from pathlib import Path
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / '.env')

# Database & Core Services
MONGO_URI = os.getenv('MONGO_URI', 'mongodb://localhost:27017')
MONGO_DB = os.getenv('MONGO_DB', 'fake_news_unlearning')
SECRET_KEY = os.getenv('SECRET_KEY', 'dev-secret-change-me')
ADMIN_USERNAME = os.getenv('ADMIN_USERNAME', 'admin')
ADMIN_PASSWORD = os.getenv('ADMIN_PASSWORD', 'admin123')
HOST = os.getenv('HOST', '0.0.0.0')
PORT = int(os.getenv('PORT', '8000'))
FLASK_PORT = int(os.getenv('FLASK_PORT', '5000'))

# Redis Cache Controller Configuration
REDIS_HOST = os.getenv('REDIS_HOST', 'localhost')
REDIS_PORT = int(os.getenv('REDIS_PORT', '6379'))
REDIS_DB = int(os.getenv('REDIS_DB', '0'))
REDIS_PASSWORD = os.getenv('REDIS_PASSWORD', None)
REDIS_CACHE_TTL = int(os.getenv('REDIS_CACHE_TTL', '86400'))  # 24 hours dynamic default

# Qdrant Vector DB Configuration
QDRANT_HOST = os.getenv('QDRANT_HOST', 'localhost')
QDRANT_PORT = int(os.getenv('QDRANT_PORT', '6333'))
QDRANT_COLLECTION = os.getenv('QDRANT_COLLECTION', 'official_indian_news_corpus')
QDRANT_PREFER_GRPC = os.getenv('QDRANT_PREFER_GRPC', 'false').lower() == 'true'

# Neo4j Chronological Graph Configuration
NEO4J_URI = os.getenv('NEO4J_URI', 'bolt://localhost:7687')
NEO4J_USER = os.getenv('NEO4J_USER', 'neo4j')
NEO4J_PASSWORD = os.getenv('NEO4J_PASSWORD', 'password')

# Machine Learning & LoRA SISA Configuration
MODEL_BACKEND = os.getenv('MODEL_BACKEND', 'hybrid_lora')  # 'hybrid_lora' or 'sisa'
DEBERTA_MODEL_NAME = os.getenv('DEBERTA_MODEL_NAME', 'microsoft/deberta-v3-base')
BGE_MODEL_NAME = os.getenv('BGE_MODEL_NAME', 'BAAI/bge-m3')
LORA_R = int(os.getenv('LORA_R', '8'))
LORA_ALPHA = int(os.getenv('LORA_ALPHA', '16'))
LORA_DROPOUT = float(os.getenv('LORA_DROPOUT', '0.05'))

# Thresholds & Sharding
FAKE_THRESHOLD_HIGH = float(os.getenv('FAKE_THRESHOLD_HIGH', '0.70'))
FAKE_THRESHOLD_LOW = float(os.getenv('FAKE_THRESHOLD_LOW', '0.30'))
SISA_SHARDS = int(os.getenv('SISA_SHARDS', '5'))
SISA_SLICES = int(os.getenv('SISA_SLICES', '5'))
RANDOM_STATE = int(os.getenv('RANDOM_STATE', '42'))

# Storage & Directory Layout
DATA_DIR = BASE_DIR / 'data'
PROCESSED_DIR = DATA_DIR / 'processed'
OFFICIAL_CORPUS_DIR = DATA_DIR / 'official_corpus'
QDRANT_STORAGE_DIR = DATA_DIR / 'qdrant_storage'
ARTIFACT_DIR = BASE_DIR / 'artifacts'
SISA_DIR = ARTIFACT_DIR / 'sisa'
SISA_ADAPTERS_DIR = BASE_DIR / 'sisa_adapters'
EVAL_DIR = ARTIFACT_DIR / 'evaluation'
LOG_DIR = BASE_DIR / 'logs'

for p in [PROCESSED_DIR, OFFICIAL_CORPUS_DIR, QDRANT_STORAGE_DIR, SISA_DIR, SISA_ADAPTERS_DIR, EVAL_DIR, LOG_DIR]:
    p.mkdir(parents=True, exist_ok=True)

