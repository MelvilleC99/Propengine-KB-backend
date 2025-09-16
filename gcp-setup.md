# Google Cloud Platform Deployment Guide

This guide will help you deploy your PropertyEngine Knowledge Base backend to Google Cloud Platform using Cloud Run.

## Prerequisites

1. **Google Cloud Account**: You need a GCP account with billing enabled
2. **Google Cloud CLI**: Install the [Google Cloud CLI](https://cloud.google.com/sdk/docs/install)
3. **Docker**: Install [Docker](https://docs.docker.com/get-docker/) for building container images
4. **Project Setup**: Your GCP project should be `propengine-12655` (update in `deploy-gcp.sh` if different)

## Quick Start

### 1. Authenticate with Google Cloud

```bash
gcloud auth login
gcloud config set project propengine-12655
```

### 2. Run the Deployment Script

```bash
./deploy-gcp.sh
```

This script will:
- Enable required GCP APIs
- Create secrets in Secret Manager from your `.env` file
- Build and push a Docker image
- Deploy to Cloud Run with proper configuration

## Manual Deployment Steps

If you prefer to run the steps manually:

### 1. Enable Required APIs

```bash
gcloud services enable cloudbuild.googleapis.com
gcloud services enable run.googleapis.com
gcloud services enable containerregistry.googleapis.com
gcloud services enable secretmanager.googleapis.com
```

### 2. Create Secrets

```bash
# Create secrets from your .env file values
gcloud secrets create ASTRADB_TOKEN --data-file=- <<< "your_astra_token"
gcloud secrets create OPENAI_API_KEY --data-file=- <<< "your_openai_key"
gcloud secrets create FIREBASE_PROJECT_ID --data-file=- <<< "propengine-12655"
gcloud secrets create FIREBASE_CLIENT_EMAIL --data-file=- <<< "your_firebase_email"
gcloud secrets create FIREBASE_PRIVATE_KEY --data-file=- <<< "your_firebase_private_key"
```

### 3. Build and Push Docker Image

```bash
docker build -t gcr.io/propengine-12655/propengine-kb-backend:latest .
docker push gcr.io/propengine-12655/propengine-kb-backend:latest
```

### 4. Deploy to Cloud Run

```bash
gcloud run deploy propengine-kb-backend \
    --image gcr.io/propengine-12655/propengine-kb-backend:latest \
    --region us-central1 \
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
```

## Configuration Details

### Cloud Run Settings

- **Memory**: 2GB (adjustable based on your needs)
- **CPU**: 2 vCPUs
- **Min Instances**: 0 (cost optimization)
- **Max Instances**: 10 (scalability)
- **Concurrency**: 100 requests per instance
- **Timeout**: 300 seconds

### Environment Variables

The deployment sets these environment variables:
- `API_HOST=0.0.0.0`
- `API_PORT=8080`
- `DEBUG=false`
- `LOG_LEVEL=INFO`

### Secrets Management

Sensitive data is stored in Google Secret Manager:
- `ASTRADB_TOKEN`: Your AstraDB application token
- `OPENAI_API_KEY`: Your OpenAI API key
- `FIREBASE_PROJECT_ID`: Your Firebase project ID
- `FIREBASE_CLIENT_EMAIL`: Your Firebase service account email
- `FIREBASE_PRIVATE_KEY`: Your Firebase private key

## Monitoring and Management

### View Logs

```bash
gcloud run services logs read propengine-kb-backend --region=us-central1
```

### Check Service Status

```bash
gcloud run services describe propengine-kb-backend --region=us-central1
```

### Update Deployment

To update your deployment, simply run the deployment script again:

```bash
./deploy-gcp.sh
```

## Cost Optimization

- **Min Instances**: Set to 0 to avoid costs when not in use
- **CPU Allocation**: Only allocate CPU during request processing
- **Memory**: Start with 2GB, adjust based on actual usage
- **Region**: Choose the region closest to your users

## Security Considerations

1. **Secrets**: All sensitive data is stored in Secret Manager
2. **HTTPS**: Cloud Run automatically provides HTTPS
3. **Authentication**: Currently set to allow unauthenticated access (update if needed)
4. **CORS**: Update CORS settings in `main.py` for production

## Troubleshooting

### Common Issues

1. **Authentication Errors**: Make sure you're logged in with `gcloud auth login`
2. **Permission Errors**: Ensure your account has the necessary IAM roles
3. **Build Failures**: Check that Docker is running and you have internet access
4. **Secret Errors**: Verify secrets exist in Secret Manager

### Debug Commands

```bash
# Check authentication
gcloud auth list

# Check project
gcloud config get-value project

# Check secrets
gcloud secrets list

# Check Cloud Run services
gcloud run services list --region=us-central1
```

## Next Steps

1. **Custom Domain**: Set up a custom domain for your API
2. **SSL Certificate**: Configure SSL for your custom domain
3. **Monitoring**: Set up Cloud Monitoring and alerting
4. **CI/CD**: Set up automated deployments with Cloud Build
5. **Scaling**: Monitor usage and adjust resource allocation

## Support

For issues with this deployment:
1. Check the Cloud Run logs
2. Verify your secrets are correctly set
3. Ensure all required APIs are enabled
4. Check your GCP billing and quotas
