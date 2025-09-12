# PropEngine Support Agent Backend

## 🏗️ Architecture Overview

Clean, modular AI-powered support agent backend with intelligent query routing and vector search.

## 📁 Project Structure

```
Propengine-KB-backend/
├── main.py                      # FastAPI application entry point
├── requirements.txt             # Python dependencies
├── .env                        # Environment configuration
│
├── src/                        # Source code directory
│   ├── __init__.py
│   │
│   ├── config/                # Configuration management
│   │   ├── __init__.py
│   │   └── settings.py        # Environment settings
│   │
│   ├── agent/                 # Agent orchestration
│   │   ├── __init__.py
│   │   └── orchestrator.py    # Query routing and response generation
│   │
│   ├── query/                 # Query and search operations
│   │   ├── __init__.py
│   │   └── vector_search.py   # Vector search implementation
│   │
│   ├── prompts/               # System and user prompts
│   │   ├── __init__.py
│   │   └── system_prompts.py  # LLM prompt templates
│   │
│   ├── api/                   # API endpoints
│   │   ├── __init__.py
│   │   ├── chat_routes.py     # Chat endpoints
│   │   └── admin_routes.py    # Admin endpoints
│   │
│   ├── database/              # Database connections
│   │   ├── __init__.py
│   │   └── connection.py      # AstraDB connection management
│   │
│   └── memory/                # Session management
│       ├── __init__.py
│       └── session_manager.py # Conversation history
│
└── tests/                     # Unit tests
    ├── __init__.py
    ├── test_database.py       # Database connection tests
    ├── test_query.py          # Vector search tests
    └── test_api.py            # API endpoint tests
```

## 🔑 Key Components

### 1. **Configuration (`src/config/`)**
- Centralized environment variable management
- Settings validation with Pydantic

### 2. **Agent (`src/agent/`)**
- Query classification (greeting, definition, howto, error, workflow)
- Intelligent routing to appropriate collections
- Response generation with LLM

### 3. **Query (`src/query/`)**
- Vector search across AstraDB collections
- **IMPORTANT**: Handles different field names:
  - `definitions`, `errors`, `howto` collections use `page_content`
  - `workflow` collection uses `content` field in metadata
- Query cleaning and optimization

### 4. **Prompts (`src/prompts/`)**
- System prompts for consistent agent behavior
- Response generation templates
- Fallback prompts for no-result scenarios

### 5. **Database (`src/database/`)**
- AstraDB connection initialization
- Health checks for all collections
- Connection status monitoring

### 6. **Memory (`src/memory/`)**
- Session management with 2-hour expiration
- Conversation history tracking
- Metadata collection for analytics

### 7. **API (`src/api/`)**
- RESTful endpoints for chat and admin functions
- Health checks with detailed status
- Session management endpoints

## 🚀 Quick Start

### 1. Install Dependencies
```bash
cd /Users/melville/Documents/Propengine-KB-backend
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### 2. Configure Environment
Ensure `.env` file contains:
```env
# AstraDB
ASTRADB_APPLICATION_TOKEN=your_token
ASTRADB_API_ENDPOINT=your_endpoint
ASTRADB_KEYSPACE=default_keyspace

# Collections
ASTRADB_DEFINITIONS_COLLECTION=definitions_collection
ASTRADB_ERRORS_COLLECTION=errors_collection
ASTRADB_HOWTO_COLLECTION=howto_collection
ASTRADB_WORKFLOWS_COLLECTION=workflow

# OpenAI
OPENAI_API_KEY=your_key
OPENAI_MODEL=gpt-4o-mini
```

### 3. Run the Backend
```bash
python main.py
```

The server will start on `http://localhost:8000`

## 🧪 Testing

### Run All Tests
```bash
pytest tests/
```

### Run Specific Test Categories
```bash
# Database connection tests
pytest tests/test_database.py

# Query/search tests
pytest tests/test_query.py

# API endpoint tests
pytest tests/test_api.py
```

### Test Coverage
```bash
pytest --cov=src tests/
```

## 📊 API Endpoints

### Chat Endpoints
- `POST /api/chat/` - Main chat interface
- `GET /api/chat/health` - Health check with collection status
- `GET /api/chat/session/{id}` - Session information
- `GET /api/chat/history/{id}` - Chat history

### Admin Endpoints
- `GET /api/admin/stats` - Overall statistics
- `GET /api/admin/sessions` - Active sessions
- `GET /api/admin/messages` - Recent messages
- `POST /api/admin/escalate/{id}` - Escalate to human
- `DELETE /api/admin/sessions/{id}` - Delete session

## 🔍 Collection Field Mapping

**CRITICAL**: Different collections use different field structures:

| Collection | Field Name | Location |
|------------|------------|----------|
| definitions_collection | `page_content` | Document root |
| errors_collection | `page_content` | Document root |
| howto_collection | `page_content` | Document root |
| workflow | `content` | In metadata |

## 📝 Logging

The backend uses structured logging with detailed information:
- File location and line numbers
- Timestamp and log levels
- Collection-specific search results
- Error tracking with stack traces

Check logs in console output for:
- Connection status for each collection
- Query classification results
- Search operations and results
- Error details with context

## 🎯 Query Flow

1. **User Query** → Chat endpoint receives message
2. **Classification** → Query type determined (definition, error, etc.)
3. **Collection Selection** → Route to appropriate collection
4. **Query Cleaning** → Remove stop words, optimize for search
5. **Vector Search** → Search selected collection
6. **Content Extraction** → Handle different field formats
7. **Response Generation** → LLM generates response with context
8. **Session Update** → Store in conversation history

## ⚠️ Important Notes

1. **Field Name Handling**: The system automatically handles the difference between `page_content` and `content` fields
2. **Collection Indexing**: Current collections have indexing warnings but work correctly
3. **Session Expiration**: Sessions expire after 2 hours of inactivity
4. **Error Logging**: All errors are logged with full context for debugging

## 🔧 Troubleshooting

### Collection Connection Issues
- Check AstraDB credentials in `.env`
- Verify collection names match exactly
- Review health check endpoint for specific collection status

### Search Not Finding Results
- Verify data exists in collection (check AstraDB console)
- Check field mapping (page_content vs content)
- Review query classification in logs

### Session Issues
- Sessions expire after 2 hours
- Check session ID is being passed correctly
- Use admin endpoints to view active sessions

## 📈 Monitoring

Access the health endpoint for real-time status:
```bash
curl http://localhost:8000/api/chat/health
```

This returns:
- Overall system status
- Individual collection connection status
- Active session count
- Service availability

## 🚦 Status Indicators

- ✅ **Healthy**: All services connected
- ⚠️ **Degraded**: Some services unavailable
- ❌ **Unhealthy**: Critical services offline

## 📞 Support

For issues or questions:
1. Check logs for detailed error messages
2. Verify environment configuration
3. Run test suite to identify specific failures
4. Review collection field mappings
