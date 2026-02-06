#!/bin/bash

echo "=================================="
echo "Backend Deployment Troubleshooting"
echo "=================================="
echo ""

# Check if deployment succeeded
echo "1. Checking Cloud Run service status..."
gcloud run services describe knowledge-base-backend \
  --region us-central1 \
  --format="value(status.url)" 2>/dev/null

if [ $? -eq 0 ]; then
    SERVICE_URL=$(gcloud run services describe knowledge-base-backend \
      --region us-central1 \
      --format="value(status.url)")
    echo "✅ Service URL: $SERVICE_URL"
    echo ""
else
    echo "❌ Service not found or deployment failed"
    echo ""
    exit 1
fi

# Test health endpoint
echo "2. Testing health endpoint..."
HEALTH_RESPONSE=$(curl -s -w "\n%{http_code}" "$SERVICE_URL/api/chat/health")
HTTP_CODE=$(echo "$HEALTH_RESPONSE" | tail -n1)
RESPONSE_BODY=$(echo "$HEALTH_RESPONSE" | head -n-1)

if [ "$HTTP_CODE" = "200" ]; then
    echo "✅ Health check passed: $RESPONSE_BODY"
else
    echo "❌ Health check failed (HTTP $HTTP_CODE)"
    echo "Response: $RESPONSE_BODY"
fi
echo ""

# Test agent endpoint
echo "3. Testing agent endpoint..."
TEST_RESPONSE=$(curl -s -X POST "$SERVICE_URL/api/agent/test" \
  -H "Content-Type: application/json" \
  -d '{
    "message": "test query",
    "session_id": "troubleshoot_test"
  }')

if echo "$TEST_RESPONSE" | grep -q "response"; then
    echo "✅ Agent endpoint working"
    echo "Response preview: $(echo $TEST_RESPONSE | head -c 100)..."
else
    echo "❌ Agent endpoint not working"
    echo "Response: $TEST_RESPONSE"
fi
echo ""

# Check recent logs for errors
echo "4. Checking recent logs for errors..."
gcloud run services logs read knowledge-base-backend \
  --region us-central1 \
  --limit 20 \
  --format="table(timestamp,severity,textPayload)" 2>/dev/null | grep -E "ERROR|WARNING" | tail -5

echo ""
echo "5. CORS Configuration Check..."
echo "Your backend needs to allow requests from your frontend domain."
echo ""
echo "Current CORS settings should include:"
echo "  - Your frontend URL (e.g., https://your-frontend.vercel.app)"
echo "  - http://localhost:3000 (for local development)"
echo ""

# Get service URL for frontend configuration
echo "=================================="
echo "Frontend Configuration Needed:"
echo "=================================="
echo ""
echo "Add this to your frontend .env.production:"
echo ""
echo "NEXT_PUBLIC_BACKEND_URL=$SERVICE_URL"
echo ""
echo "Or if using different variable name:"
echo "REACT_APP_API_URL=$SERVICE_URL"
echo "VITE_API_URL=$SERVICE_URL"
echo ""
