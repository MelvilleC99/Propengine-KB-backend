#!/bin/bash
# Google Cloud Platform deployment script for PropertyEngine Knowledge Base Backend

set -e  # Exit on any error

echo "🚀 PropertyEngine Knowledge Base - Google Cloud Deployment"
echo "=========================================================="

# Configuration
PROJECT_ID="propengine-472312"  # Update this with your GCP project ID
SERVICE_NAME="propengine-kb-backend"
REGION="us-central1"
IMAGE_NAME="gcr.io/$PROJECT_ID/$SERVICE_NAME"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Function to print colored output
print_status() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Check if gcloud is installed
if ! command -v gcloud &> /dev/null; then
    print_error "Google Cloud CLI is not installed. Please install it first:"
    echo "https://cloud.google.com/sdk/docs/install"
    exit 1
fi

# Check if user is authenticated
if ! gcloud auth list --filter=status:ACTIVE --format="value(account)" | grep -q .; then
    print_warning "You are not authenticated with Google Cloud. Please run:"
    echo "gcloud auth login"
    exit 1
fi

# Set the project
print_status "Setting project to $PROJECT_ID..."
gcloud config set project $PROJECT_ID

# Enable required APIs
print_status "Enabling required Google Cloud APIs..."
gcloud services enable cloudbuild.googleapis.com
gcloud services enable run.googleapis.com
gcloud services enable containerregistry.googleapis.com
gcloud services enable secretmanager.googleapis.com

# Check if secrets exist, create if they don't
print_status "Setting up secrets in Secret Manager..."

# Function to create secret if it doesn't exist
create_secret_if_not_exists() {
    local secret_name=$1
    local secret_value=$2
    
    if ! gcloud secrets describe $secret_name &> /dev/null; then
        print_status "Creating secret: $secret_name"
        echo "$secret_value" | gcloud secrets create $secret_name --data-file=-
    else
        print_status "Secret $secret_name already exists"
    fi
}

# Check if .env file exists
if [ -f .env ]; then
    print_status "Reading secrets from .env file..."
    
    # Extract secrets from .env file
    ASTRADB_TOKEN=$(grep "ASTRADB_APPLICATION_TOKEN=" .env | cut -d'=' -f2- | tr -d '"')
    OPENAI_KEY=$(grep "OPENAI_API_KEY=" .env | cut -d'=' -f2- | tr -d '"')
    FIREBASE_PROJECT=$(grep "FIREBASE_PROJECT_ID=" .env | cut -d'=' -f2- | tr -d '"')
    FIREBASE_EMAIL=$(grep "FIREBASE_CLIENT_EMAIL=" .env | cut -d'=' -f2- | tr -d '"')
    FIREBASE_KEY=$(grep "FIREBASE_PRIVATE_KEY=" .env | cut -d'=' -f2- | tr -d '"')
    
    # Create secrets
    create_secret_if_not_exists "ASTRADB_TOKEN" "$ASTRADB_TOKEN"
    create_secret_if_not_exists "OPENAI_API_KEY" "$OPENAI_KEY"
    create_secret_if_not_exists "FIREBASE_PROJECT_ID" "$FIREBASE_PROJECT"
    create_secret_if_not_exists "FIREBASE_CLIENT_EMAIL" "$FIREBASE_EMAIL"
    create_secret_if_not_exists "FIREBASE_PRIVATE_KEY" "$FIREBASE_KEY"
else
    print_warning ".env file not found. Please create secrets manually:"
    echo "gcloud secrets create ASTRADB_TOKEN --data-file=-"
    echo "gcloud secrets create OPENAI_API_KEY --data-file=-"
    echo "gcloud secrets create FIREBASE_PROJECT_ID --data-file=-"
    echo "gcloud secrets create FIREBASE_CLIENT_EMAIL --data-file=-"
    echo "gcloud secrets create FIREBASE_PRIVATE_KEY --data-file=-"
fi

# Build and push the Docker image
print_status "Building Docker image..."
docker build -t $IMAGE_NAME:latest .

print_status "Pushing image to Container Registry..."
docker push $IMAGE_NAME:latest

# Deploy to Cloud Run
print_status "Deploying to Cloud Run..."
gcloud run deploy $SERVICE_NAME \
    --image $IMAGE_NAME:latest \
    --region $REGION \
    --platform managed \
    --allow-unauthenticated \
    --port 8080 \
    --memory 2Gi \
    --cpu 2 \
    --min-instances 0 \
    --max-instances 10 \
    --concurrency 100 \
    --timeout 300 \
    --set-env-vars "API_HOST=0.0.0.0,API_PORT=8080,DEBUG=false,LOG_LEVEL=INFO" \
    --set-secrets "ASTRADB_APPLICATION_TOKEN=ASTRADB_TOKEN:latest,OPENAI_API_KEY=OPENAI_API_KEY:latest,FIREBASE_PROJECT_ID=FIREBASE_PROJECT_ID:latest,FIREBASE_CLIENT_EMAIL=FIREBASE_CLIENT_EMAIL:latest,FIREBASE_PRIVATE_KEY=FIREBASE_PRIVATE_KEY:latest"

# Get the service URL
SERVICE_URL=$(gcloud run services describe $SERVICE_NAME --region=$REGION --format="value(status.url)")

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
echo "   ./deploy-gcp.sh"
echo ""
echo "📊 To view logs:"
echo "   gcloud run services logs read $SERVICE_NAME --region=$REGION"
echo ""
echo "🛠️  To manage the service:"
echo "   gcloud run services describe $SERVICE_NAME --region=$REGION"
