# Context Debug API Reference

**Added:** January 30, 2026
**Endpoint:** `/api/agent/test`
**Purpose:** Debug and monitor conversation context management for the RAG agent

---

## Overview

The `context_debug` field provides complete visibility into how the agent manages conversation context, what information is passed to the LLM, and what related documents are available for follow-up questions.

---

## API Response Structure

### New Field Added to TestAgentResponse

```typescript
interface TestAgentResponse {
  // ... existing fields ...

  // 🆕 NEW: Context debugging information
  context_debug: {
    conversation_context: string;
    message_count: number;
    has_summary: boolean;
    context_length: number;
    recent_sources_used: string[];
    available_related_documents: string[];
  };
}
```

---

## Field Descriptions

### `conversation_context` (string)
**What it is:** The exact formatted text passed to the LLM for context

**Contains:**
- Rolling summary (if exists)
- Recent messages (last 5-8 messages)
- KB source attribution for each assistant response

**Example:**
```
=== CONVERSATION SUMMARY ===
Overview: User asking about photo uploads
Current Topic: image requirements
State: active
Key Facts: 5MB limit, 4th screen

=== RECENT MESSAGES ===
USER: how do I upload photos?
ASSISTANT: To upload photos, follow these steps: 1) Select listing...
   📚 Sources: Upload Photos Guide (confidence: 0.92)
   📌 Related: Photo Resizing Guide, Image Quality Tips

USER: what about resizing?
```

**Why it's useful:**
- See exactly what context the LLM has access to
- Verify that conversation history is being maintained
- Check if KB source information is being included
- Debug why the agent might be missing information

---

### `message_count` (number)
**What it is:** Total number of messages in conversation history

**Range:** 0 - unlimited (typically capped at last 8 messages + summary)

**Examples:**
- `0` = New conversation, no history
- `5` = 3 exchanges (user + assistant messages)
- `10` = 5 exchanges

**Why it's useful:**
- Monitor memory window size
- Verify messages are being stored
- Debug if context window is getting too large

---

### `has_summary` (boolean)
**What it is:** Whether a rolling summary exists for this conversation

**Values:**
- `true` = Summary generated (usually after 5+ messages)
- `false` = No summary yet (early in conversation)

**Why it's useful:**
- Verify summarization is working
- Check if long conversations are being compressed
- Debug memory management

---

### `context_length` (number)
**What it is:** Character count of the full conversation context

**Typical Ranges:**
- `0-500` chars = Short context (1-2 messages)
- `500-2000` chars = Medium context (3-5 messages)
- `2000-8000` chars = Large context (5+ messages with KB content)
- `>8000` chars = Very large context (may need summarization)

**Why it's useful:**
- Monitor token usage (rough estimate: chars/4 = tokens)
- Identify when summarization should trigger
- Debug performance issues with large contexts

---

### `recent_sources_used` (string[])
**What it is:** List of KB article titles used in recent responses

**Limit:** Last 5 unique sources (duplicates removed)

**Example:**
```json
[
  "Upload Photos Guide",
  "Photo Resizing Guide",
  "Create Listing Guide"
]
```

**Why it's useful:**
- Show user what KB articles were referenced
- Verify KB search is working
- Track which documentation is being used most
- Debug if wrong sources are being retrieved

---

### `available_related_documents` (string[])
**What it is:** Related documents available for follow-up questions

**Limit:** Last 10 unique related docs (duplicates removed)

**Source:** Extracted from `related_documents` metadata of KB entries

**Example:**
```json
[
  "Photo Resizing Guide",
  "Image Quality Best Practices",
  "Video Upload Guide",
  "File Size Limits"
]
```

**Why it's useful:**
- **Follow-up Detection:** Agent checks if user's next query matches any of these
- **Topic Suggestions:** Show these to user as "Related Topics"
- **Navigation:** Help users discover related content
- **Debug:** Verify related documents are being tracked

---

## Frontend Implementation Guide

### 1. Basic Display

```typescript
// Display context stats
const ContextStats = ({ contextDebug }) => (
  <div className="context-stats">
    <div>Messages: {contextDebug.message_count}</div>
    <div>Context Size: {contextDebug.context_length} chars</div>
    <div>Has Summary: {contextDebug.has_summary ? '✅' : '❌'}</div>
    <div>Sources Used: {contextDebug.recent_sources_used.length}</div>
  </div>
);
```

### 2. Full Context Viewer (Debug Panel)

```typescript
// Expandable debug panel
const ContextDebugPanel = ({ contextDebug }) => {
  const [expanded, setExpanded] = useState(false);

  return (
    <div className="debug-panel">
      <button onClick={() => setExpanded(!expanded)}>
        {expanded ? 'Hide' : 'Show'} Context
      </button>

      {expanded && (
        <pre className="context-view">
          {contextDebug.conversation_context}
        </pre>
      )}
    </div>
  );
};
```

### 3. Related Topics Display

```typescript
// Show related documents as clickable suggestions
const RelatedTopics = ({ contextDebug, onTopicClick }) => {
  if (contextDebug.available_related_documents.length === 0) {
    return null;
  }

  return (
    <div className="related-topics">
      <h4>Related Topics:</h4>
      <div className="topic-chips">
        {contextDebug.available_related_documents.map(doc => (
          <button
            key={doc}
            className="topic-chip"
            onClick={() => onTopicClick(doc)}
          >
            {doc}
          </button>
        ))}
      </div>
    </div>
  );
};
```

### 4. Source History Visualization

```typescript
// Show which KB articles were used
const SourceHistory = ({ contextDebug }) => (
  <div className="source-history">
    <h4>Recent KB Sources:</h4>
    <ul>
      {contextDebug.recent_sources_used.map(source => (
        <li key={source}>
          📄 {source}
        </li>
      ))}
    </ul>
  </div>
);
```

---

## Use Cases

### Use Case 1: Debug "Agent Doesn't Remember Previous Answer"

**Problem:** User complains agent forgot what they discussed

**Debug:**
```javascript
// Check if conversation context is empty
if (response.context_debug.message_count === 0) {
  console.error('❌ No conversation history!');
}

// Check if context contains the previous exchange
if (!response.context_debug.conversation_context.includes('previous topic')) {
  console.error('❌ Previous topic not in context!');
}
```

---

### Use Case 2: Monitor Memory Usage

**Goal:** Track context window size to optimize costs

```javascript
const analyzeContextSize = (contextDebug) => {
  const { context_length, message_count, has_summary } = contextDebug;
  const estimatedTokens = Math.ceil(context_length / 4);

  return {
    contextSize: context_length,
    estimatedTokens,
    messagesStored: message_count,
    isCompressed: has_summary,
    costEstimate: estimatedTokens * 0.0000015 // rough GPT-4 pricing
  };
};
```

---

### Use Case 3: Verify Follow-up Detection Works

**Goal:** Check if agent recognizes related documents for follow-ups

```javascript
// After user asks "What about resizing?"
const relatedDocs = response.context_debug.available_related_documents;

if (relatedDocs.includes('Photo Resizing Guide')) {
  console.log('✅ Agent should recognize this as follow-up!');
} else {
  console.warn('⚠️ Related doc not available for follow-up');
}
```

---

### Use Case 4: Show "You Might Also Like" Suggestions

**Goal:** Proactively suggest related topics to user

```javascript
// Display after each response
const SuggestionsWidget = ({ contextDebug }) => {
  const suggestions = contextDebug.available_related_documents.slice(0, 3);

  return (
    <div className="suggestions">
      <p>You might also be interested in:</p>
      {suggestions.map(doc => (
        <a key={doc} onClick={() => askAbout(doc)}>
          {doc} →
        </a>
      ))}
    </div>
  );
};
```

---

## Example API Response

```json
{
  "response": "To upload photos, follow these steps...",
  "session_id": "sess_abc123",
  "confidence": 0.92,
  "sources": [...],
  "debug_metrics": {...},

  "context_debug": {
    "conversation_context": "=== RECENT MESSAGES ===\nUSER: how do I upload photos?\nASSISTANT: To upload photos...\n   📚 Sources: Upload Photos Guide (confidence: 0.92)\n   📌 Related: Photo Resizing Guide, Image Quality Tips\n\nUSER: what about resizing?",
    "message_count": 4,
    "has_summary": false,
    "context_length": 487,
    "recent_sources_used": [
      "Upload Photos Guide"
    ],
    "available_related_documents": [
      "Photo Resizing Guide",
      "Image Quality Best Practices",
      "Video Upload Guide"
    ]
  }
}
```

---

## Integration Checklist

- [ ] Add `context_debug` field to frontend TypeScript types
- [ ] Create debug panel to view full conversation context
- [ ] Display context stats (message count, size, has summary)
- [ ] Show recent KB sources used
- [ ] Display related topics as clickable suggestions
- [ ] Add context size monitoring for cost tracking
- [ ] Log context issues for debugging (empty context, missing history)

---

## Notes

- **Performance:** Context string can be large (2-8KB). Consider lazy loading in debug panel.
- **Privacy:** `conversation_context` contains user messages. Don't log to analytics.
- **Cost Tracking:** Context length correlates to token usage. Monitor for cost optimization.
- **Follow-ups:** `available_related_documents` powers the smart follow-up detection system.

---

**For Questions or Issues:**
See `CHAT_SESSION_SUMMARY.md` for full system architecture
