# Database Layer

This folder contains all database-related configuration and management for the PropertyEngine Knowledge Base backend.

## Files Overview

### `firebase_config.py`
**Purpose**: Firebase Admin SDK initialization and configuration
- Sets up Firebase Admin SDK using environment variables
- Provides global Firestore client instance
- Handles credential management and error fallback
- Used by all Firebase-dependent services

**Key Features**:
- Auto-detects existing Firebase app instances
- Loads credentials from `.env` file
- Graceful error handling with fallback options
- Singleton pattern for global access

**Environment Variables Required**:
```bash
FIREBASE_PROJECT_ID=your-project-id
FIREBASE_CLIENT_EMAIL=your-service-account@project.iam.gserviceaccount.com
FIREBASE_PRIVATE_KEY="-----BEGIN PRIVATE KEY-----\n..."
```

### `firebase_session.py`
**Purpose**: Firebase-based session persistence and message logging
- Manages user sessions in Firestore
- Stores all chat messages with metadata
- Handles session expiration and cleanup
- Provides conversation history retrieval

**Key Methods**:
- `create_session()` - Creates new user session with metadata
- `get_session()` - Retrieves session with expiration check
- `add_message()` - Logs user/assistant messages with timestamps
- `get_recent_messages()` - Gets conversation history for context
- `update_session_summary()` - Updates conversation summaries

**Firestore Collections**:

#### `kb_sessions`
```json
{
  "session_id": "uuid-string",
  "user_email": "user@company.com",
  "user_name": "John Doe",
  "company": "Company Name",
  "division": "Sales",
  "created_at": "timestamp",
  "last_activity": "timestamp",
  "message_count": 15,
  "status": "active",
  "conversation_summary": "User asking about property definitions",
  "total_queries": 8,
  "escalations": 0,
  "avg_confidence": 0.85
}
```

#### `kb_messages`
```json
{
  "session_id": "uuid-string",
  "role": "user|assistant",
  "content": "Message content",
  "timestamp": "timestamp",
  "metadata": {
    "confidence": 0.85,
    "query_type": "definition",
    "sources_count": 3,
    "user_email": "user@company.com"
  }
}
```

### `connection.py`
**Purpose**: AstraDB connection management for vector search
- Manages connection to DataStax AstraDB
- Provides vector database operations
- Handles authentication and session management
- Used for document similarity search

## Data Flow

```
User Request → Session Manager → Firebase Session Manager → Firestore
                     ↓
Agent Processing → Message Logging → Firebase Session Manager → Firestore
                     ↓
Vector Search → AstraDB Connection → DataStax AstraDB
```

## Configuration

### Firebase Setup
1. Create service account in Firebase Console
2. Download credentials or set environment variables
3. Ensure Firestore is enabled in your Firebase project
4. Configure security rules for collections

### AstraDB Setup
1. Create AstraDB instance in DataStax Console
2. Generate application token
3. Configure connection parameters in environment

## Error Handling

The database layer implements graceful degradation:
- Firebase failures fall back to in-memory storage
- Connection errors are logged but don't crash the system
- Session timeouts are handled automatically
- Expired data is cleaned up periodically

## Monitoring

Key metrics to monitor:
- Active session count
- Message throughput
- Firebase connection health
- AstraDB query performance
- Session expiration rates

## Security

- All Firebase operations use Admin SDK
- Environment variables for sensitive credentials
- Session data includes user context for personalization
- Message metadata for audit trails
- Rate limiting integration for abuse prevention
