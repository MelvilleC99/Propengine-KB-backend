#!/bin/bash

# Setup Google Cloud Secrets for Knowledge Base Backend
# This script creates all necessary secrets in Google Secret Manager

set -e  # Exit on error

echo "=========================================="
echo "Setting up Google Cloud Secrets"
echo "=========================================="
echo ""

# Check if .env file exists
if [ ! -f .env ]; then
    echo "❌ Error: .env file not found!"
    exit 1
fi

# Load environment variables from .env
source .env

echo "📦 Creating secrets in Google Secret Manager..."
echo ""

# Function to create or update a secret
create_secret() {
    local secret_name=$1
    local secret_value=$2
    
    if [ -z "$secret_value" ]; then
        echo "⚠️  Skipping $secret_name (empty value)"
        return
    fi
    
    # Check if secret exists
    if gcloud secrets describe "$secret_name" >/dev/null 2>&1; then
        echo "🔄 Updating existing secret: $secret_name"
        echo -n "$secret_value" | gcloud secrets versions add "$secret_name" --data-file=-
    else
        echo "✨ Creating new secret: $secret_name"
        echo -n "$secret_value" | gcloud secrets create "$secret_name" --data-file=-
    fi
}

# Create all secrets
echo "Creating Firebase secrets..."
create_secret "FIREBASE_PROJECT_ID" "$FIREBASE_PROJECT_ID"
create_secret "FIREBASE_CLIENT_EMAIL" "$FIREBASE_CLIENT_EMAIL"
create_secret "FIREBASE_PRIVATE_KEY" "$FIREBASE_PRIVATE_KEY"

echo ""
echo "Creating AstraDB secrets..."
create_secret "ASTRADB_APPLICATION_TOKEN" "$ASTRADB_APPLICATION_TOKEN"
create_secret "ASTRADB_DATABASE_ID" "$ASTRADB_DATABASE_ID"
create_secret "ASTRADB_API_ENDPOINT" "$ASTRADB_API_ENDPOINT"
create_secret "ASTRADB_KEYSPACE" "$ASTRADB_KEYSPACE"

echo ""
echo "Creating OpenAI/Azure secrets..."
create_secret "AZURE_OPENAI_API_KEY" "$AZURE_OPENAI_API_KEY"
create_secret "AZURE_OPENAI_BASE_URL" "$AZURE_OPENAI_BASE_URL"
create_secret "OPENAI_API_KEY" "$OPENAI_API_KEY"
create_secret "OPENAI_BASE_URL" "$OPENAI_BASE_URL"

echo ""
echo "Creating Freshdesk secrets..."
create_secret "FRESHDESK_API_KEY" "$FRESHDESK_API_KEY"
create_secret "FRESHDESK_DOMAIN" "$FRESHDESK_DOMAIN"

echo ""
echo "Creating Redis secrets..."
create_secret "REDIS_HOST" "$REDIS_HOST"
create_secret "REDIS_PORT" "$REDIS_PORT"
create_secret "REDIS_PASSWORD" "$REDIS_PASSWORD"

echo ""
echo "=========================================="
echo "✅ All secrets created successfully!"
echo "=========================================="
echo ""
echo "Next steps:"
echo "1. Deploy to Cloud Run with: ./deploy_with_secrets.sh"
echo "2. Or use the manual command shown in deploy_with_secrets.sh"
echo ""
