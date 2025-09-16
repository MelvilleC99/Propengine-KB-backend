#!/bin/bash
# Google App Engine deployment script (No Docker required!)

set -e

echo "🚀 PropertyEngine Knowledge Base - App Engine Deployment"
echo "========================================================"

# Configuration
PROJECT_ID="propengine-472312"
SERVICE_NAME="propengine-kb-backend"

# Colors for output
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
NC='\033[0m'

print_status() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

# Set the project
print_status "Setting project to $PROJECT_ID..."
gcloud config set project $PROJECT_ID

# Enable App Engine API
print_status "Enabling App Engine API..."
gcloud services enable appengine.googleapis.com

# Create App Engine app (if it doesn't exist)
print_status "Creating App Engine application..."
gcloud app create --region=us-central || print_warning "App Engine app may already exist"

# Deploy to App Engine
print_status "Deploying to App Engine..."
gcloud app deploy app.yaml --version=v1 --promote

# Get the service URL
SERVICE_URL=$(gcloud app browse --no-launch-browser)

print_success "Deployment completed successfully!"
echo ""
echo "🌐 Service URL: $SERVICE_URL"
echo ""
echo "📋 Available endpoints:"
echo "   • Health check: $SERVICE_URL/api/chat/health"
echo "   • API docs: $SERVICE_URL/docs"
echo "   • Chat API: $SERVICE_URL/api/chat/"
echo "   • Admin API: $SERVICE_URL/api/admin/"
echo ""
echo "🔧 To update the deployment:"
echo "   ./deploy-appengine.sh"
echo ""
echo "📊 To view logs:"
echo "   gcloud app logs tail -s default"
echo ""
echo "🛠️  To manage the service:"
echo "   gcloud app versions list"
