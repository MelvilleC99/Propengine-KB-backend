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

# Ensure the right account (gcloud sometimes reverts to a personal account between sessions,
# which fails the deploy with PERMISSION_DENIED). Override via DEPLOY_ACCOUNT env if needed.
DEPLOY_ACCOUNT="${DEPLOY_ACCOUNT:-Melville.Duplessis@Betterhome.co.za}"
gcloud config set account "$DEPLOY_ACCOUNT" >/dev/null 2>&1 || true

echo "📦 Service: $SERVICE_NAME"
echo "🌍 Region: $REGION"
echo ""

echo "🚀 Deploying to Cloud Run..."
echo ""

# ⚠️ TEMPORARY — TESTING/DEMO ONLY. Revert these THREE before production (in --set-env-vars below):
#   CUSTOMER_AGENT_PUBLIC=true → customer chat (chat/feedback/escalation) is OPEN, NO auth.
#                                Set false once the frontend sends Firebase tokens.
#   RATE_LIMIT_TIER=dev        → 10k/day = effectively no rate limit. Use 'production' for real limits.
#   CORS_ALLOWED_ORIGINS=*     → any origin allowed. Narrow to real domains for production.
#   (REQUIRE_AUTH=true stays — support/test/KB/admin remain locked; only the customer flow is opened.)
# NOTE: RESPONSE_USE_QWEN=true is NOT a revert-me flag — it makes answer generation use the
# self-hosted Qwen gateway (real token streaming; embeddings stay on OpenAI). It is intended to
# stay on. Requires the QWEN_API_KEY secret to exist in Secret Manager (see README/comment below).
gcloud run deploy $SERVICE_NAME \
  --source . \
  --platform $PLATFORM \
  --region $REGION \
  --allow-unauthenticated \
  --port 8080 \
  --memory 2Gi \
  --cpu 2 \
  --timeout 300 \
  --min-instances 1 \
  --max-instances 10 \
  --set-env-vars="DEBUG=false,LOG_LEVEL=INFO,API_HOST=0.0.0.0,API_PORT=8080,REQUIRE_AUTH=true,FRESHDESK_GROUP_ID=203000094600,CUSTOMER_AGENT_PUBLIC=true,CORS_ALLOWED_ORIGINS=*,RATE_LIMIT_TIER=dev" \
  --set-env-vars="AZURE_OPENAI_EMBEDDING_MODEL=text-embedding-3-small,AZURE_OPENAI_CHAT_MODEL=gpt-4o-mini" \
  --set-env-vars="OPENAI_MODEL=gpt-4o-mini,EMBEDDING_MODEL=text-embedding-3-small,RESPONSE_USE_QWEN=true" \
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
  --set-secrets="QWEN_API_KEY=QWEN_API_KEY:latest" \
  --set-secrets="FRESHDESK_API_KEY=FRESHDESK_API_KEY:latest" \
  --set-secrets="FRESHDESK_DOMAIN=FRESHDESK_DOMAIN:latest" \
  --set-secrets="FRESHDESK_RESPONDER_ID=FRESHDESK_RESPONDER_ID:latest" \
  --set-secrets="FRESHDESK_WEBHOOK_SECRET=FRESHDESK_WEBHOOK_SECRET:latest" \
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
