#!/bin/bash

# Deploy Knowledge Base Backend to Google Cloud Run with Secrets
# This script deploys the backend with all secrets from Google Secret Manager

set -e  # Exit on error

echo "=========================================="
echo "Deploying Knowledge Base Backend"
echo "=========================================="
echo ""

# Configuration
SERVICE_NAME="knowledge-base-backend"
REGION="us-central1"
PLATFORM="managed"

echo "📦 Service: $SERVICE_NAME"
echo "🌍 Region: $REGION"
echo ""

echo "🚀 Deploying to Cloud Run..."
echo ""

gcloud run deploy $SERVICE_NAME \
  --source . \
  --platform $PLATFORM \
  --region $REGION \
  --allow-unauthenticated \
  --port 8080 \
  --memory 2Gi \
  --cpu 2 \
  --timeout 300 \
  --min-instances 0 \
  --max-instances 10 \
  --set-env-vars="DEBUG=false,LOG_LEVEL=INFO,API_HOST=0.0.0.0,API_PORT=8080" \
  --set-env-vars="AZURE_OPENAI_EMBEDDING_MODEL=text-embedding-3-large,AZURE_OPENAI_CHAT_MODEL=gpt-4o-mini" \
  --set-env-vars="OPENAI_MODEL=gpt-4o-mini,EMBEDDING_MODEL=text-embedding-3-large" \
  --set-env-vars="ASTRADB_KB_ENTRIES_COLLECTION=kb_entries,ASTRADB_PROPERTY_ENGINE_COLLECTION=kb_entries,REDIS_DB=0" \
  --set-secrets="FIREBASE_PROJECT_ID=FIREBASE_PROJECT_ID:latest" \
  --set-secrets="FIREBASE_CLIENT_EMAIL=FIREBASE_CLIENT_EMAIL:latest" \
  --set-secrets="FIREBASE_PRIVATE_KEY=FIREBASE_PRIVATE_KEY:latest" \
  --set-secrets="ASTRADB_APPLICATION_TOKEN=ASTRADB_APPLICATION_TOKEN:latest" \
  --set-secrets="ASTRADB_DATABASE_ID=ASTRADB_DATABASE_ID:latest" \
  --set-secrets="ASTRADB_API_ENDPOINT=ASTRADB_API_ENDPOINT:latest" \
  --set-secrets="ASTRADB_KEYSPACE=ASTRADB_KEYSPACE:latest" \
  --set-secrets="AZURE_OPENAI_API_KEY=AZURE_OPENAI_API_KEY:latest" \
  --set-secrets="AZURE_OPENAI_BASE_URL=AZURE_OPENAI_BASE_URL:latest" \
  --set-secrets="OPENAI_API_KEY=OPENAI_API_KEY:latest" \
  --set-secrets="OPENAI_BASE_URL=OPENAI_BASE_URL:latest" \
  --set-secrets="FRESHDESK_API_KEY=FRESHDESK_API_KEY:latest" \
  --set-secrets="FRESHDESK_DOMAIN=FRESHDESK_DOMAIN:latest" \
  --set-secrets="FRESHDESK_RESPONDER_ID=FRESHDESK_RESPONDER_ID:latest" \
  --set-secrets="REDIS_HOST=REDIS_HOST:latest" \
  --set-secrets="REDIS_PORT=REDIS_PORT:latest" \
  --set-secrets="REDIS_PASSWORD=REDIS_PASSWORD:latest"

echo ""
echo "=========================================="
echo "✅ Deployment complete!"
echo "=========================================="
echo ""
echo "📋 Next steps:"
echo "1. Copy the Service URL from above"
echo "2. Add it to your frontend .env.production:"
echo "   NEXT_PUBLIC_BACKEND_URL=https://your-service-url"
echo "3. Test the backend: curl https://your-service-url/"
echo ""
