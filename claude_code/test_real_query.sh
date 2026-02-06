#!/bin/bash
# Test script to send a real query and check logs

echo "🧪 Testing Real Query with Source Attribution"
echo "=============================================="
echo ""

# Test query
QUERY="How do I upload photos?"
SESSION_ID="test_session_$(date +%s)"

echo "📝 Sending query: $QUERY"
echo "🆔 Session ID: $SESSION_ID"
echo ""

# Send request to test agent (shows all debug info)
curl -X POST "http://localhost:8000/api/agent/test/" \
  -H "Content-Type: application/json" \
  -d "{
    \"message\": \"$QUERY\",
    \"session_id\": \"$SESSION_ID\",
    \"user_info\": {\"email\": \"test@example.com\"}
  }" | python3 -m json.tool

echo ""
echo "=============================================="
echo "✅ Check the response above for:"
echo "   - 'sources' array (should have entries)"
echo "   - 'confidence' score"
echo "   - 'debug_metrics' for detailed info"
