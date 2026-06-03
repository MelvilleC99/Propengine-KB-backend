# PropertyEngine AI Support Agent - Product Spec

## Vision

Build an AI-powered support agent for PropertyEngine (a real estate CRM platform) that can answer customer and internal support questions instantly using a managed knowledge base. When the agent can't answer, it seamlessly escalates to human support by creating a Freshdesk ticket with full conversation context.

The system has two parts: a **backend API** (the AI brain) and a **frontend admin panel** (for managing the knowledge base and testing the agent).

---

## Users

There are three types of users:

1. **Customers** - External PropertyEngine users who need help. They interact with the AI chat agent embedded in the PropertyEngine platform. They should never see internal/technical details.

2. **Support Agents** - Internal support staff who use the agent as a tool to quickly find answers when helping customers. They can see more detailed information than customers.

3. **Admins** - Internal team members who manage the knowledge base content, monitor agent performance, and review failed queries.

---

## Core Features

### 1. AI Chat Agent

The main feature. Users ask questions in natural language and get instant answers.

- Users type a question in a chat interface
- The agent searches the knowledge base for relevant articles
- If it finds a good match, it generates a natural-language answer from those articles
- The agent maintains conversation context across multiple messages (multi-turn chat)
- If the agent can't confidently answer, it tells the user and offers to escalate

**Key behaviors:**
- The agent should only answer from the knowledge base - never make things up
- If the answer requires multiple steps (like a 20-step workflow), the agent should ask clarifying questions first (e.g., "Which part are you struggling with?")
- Responses should be concise and friendly, not robotic
- The agent should handle greetings and off-topic messages gracefully

**Three agent modes:**
- **Customer Agent** - For external customers. Only shows articles tagged for customers. No technical details, no confidence scores. Clean, simple responses.
- **Support Agent** - For internal support staff. Shows articles tagged for internal use. More detailed responses.
- **Test Agent** - For admins to test. Shows everything: confidence scores, source articles, debug metrics, search details. Used to verify the KB is working correctly.

### 2. Escalation & Ticket Creation

When the agent can't answer a question:

- The chat interface shows an option: "Would you like to raise a support ticket?"
- If the user says yes:
  - A failure record is saved (capturing the question, the agent's response, confidence score)
  - A Freshdesk support ticket is created automatically with:
    - The user's question
    - The AI's attempted response
    - Full conversation history
    - User details (name, email, agency, office)
  - The user sees a confirmation with the ticket number
- If the user says no:
  - The failure is recorded as "declined" for analytics

**Ticket lifecycle:**
- When a Freshdesk agent resolves the ticket, the system is automatically notified via webhook
- The resolved ticket is marked in the system, and the resolution details (root cause, solution steps) are captured
- These resolved tickets feed back into knowledge base improvement - admins can see which questions keep failing and add new KB articles

### 3. Knowledge Base Management

Admins need a way to create, edit, and manage knowledge base articles.

**Article types:**
- **Definitions** - Short explanations of terms and concepts (e.g., "What is a mandate?")
- **Errors** - Known errors/issues with causes and solutions (e.g., "Listing not syncing to portal")
- **How-To Guides** - Step-by-step instructions (e.g., "How to create a listing")
- **Workflows** - Multi-step business processes (e.g., "End-to-end listing workflow")

**For each article, admins can set:**
- Title
- Content (rich text editor)
- Category (listings, contacts, leads, reports, etc.)
- User type visibility: "External" (customers only), "Internal" (support only), or "Both"
- Tags for better searchability
- Related documents (links to other KB articles)

**Article workflow:**
- Create/edit article in the admin panel
- Sync article to the vector database (this makes it searchable by the AI)
- Articles can be unsynced (removed from AI search) without deleting them
- Articles can be re-synced after edits to update the AI's knowledge

**Document upload:**
- Admins can upload existing documents (PDF, Word, text files)
- The system automatically extracts content, analyzes the structure, and creates a KB article
- Large documents are automatically split into searchable sections

### 4. Admin Dashboard

A dashboard for monitoring and managing the system:

- **KB Overview** - Total articles, articles by type, articles by category, sync status
- **Agent Performance** - Total queries, successful answers vs escalations, average confidence scores
- **Failed Queries** - List of questions the agent couldn't answer, sorted by frequency
- **Needs KB Entry** - Failed queries that should become new KB articles (prioritized list)
- **Recent Escalations** - Tickets created, their status (open/resolved), resolution details
- **Search Analytics** - Most common queries, most-used KB articles, least-used articles

### 5. Rate Limiting

To prevent abuse:
- Chat queries: 100 per day per user
- Ticket creation: 10 per day per user
- Returns a clear message when limits are exceeded

---

## User Flows

### Customer asks a question (happy path)
1. Customer opens the chat widget
2. Types: "How do I publish a listing to portals?"
3. Agent searches KB, finds the relevant how-to guide
4. Agent responds with a clear, step-by-step answer
5. Customer asks a follow-up: "What if it shows an error?"
6. Agent uses conversation context + searches again, finds the error article
7. Agent responds with troubleshooting steps

### Customer asks something not in KB (escalation)
1. Customer types: "How do I integrate with Xero?"
2. Agent searches KB, finds nothing relevant
3. Agent responds: "I don't have information about that yet. Would you like me to escalate this to our support team?"
4. Customer clicks "Yes, raise a ticket"
5. System creates a Freshdesk ticket with all context
6. Customer sees: "Ticket #1234 has been created. Our team will get back to you."

### Admin adds a new KB article
1. Admin opens the KB management panel
2. Clicks "New Article" and selects type "Error"
3. Fills in: title, error description, causes, solutions
4. Sets visibility to "Both" (customers and support)
5. Tags it: "listing, portal, sync, error"
6. Clicks "Save" - article is saved to the database
7. Clicks "Sync to AI" - article becomes searchable by the agent
8. Tests it using the Test Agent chat to verify it works

### Admin reviews failed queries
1. Admin opens the dashboard
2. Sees "Failed Queries" section showing: "How do I integrate with Xero?" (asked 5 times this week)
3. Clicks on it to see the conversation details
4. Decides to create a new KB article for this topic
5. Creates the article, syncs it
6. Future customers asking this question now get an answer

---

## Integrations

### Freshdesk
- **Ticket creation** - Automatically create support tickets when customers escalate
- **Webhook** - Receive notifications when tickets are resolved, capturing resolution details
- **Product mapping** - Tickets are tagged with the PropertyEngine product in Freshdesk

### PropertyEngine Platform
- The customer chat agent should be embeddable as a widget in the PropertyEngine web application
- User identity (name, email, agency, office) should be passed from PropertyEngine to the chat agent

---

## Future Enhancements (Planned)

These are features to build next:

1. **Streaming responses** - Show the AI response as it's being generated (like ChatGPT) instead of waiting for the full response. Improves perceived speed.

2. **Clarifying questions** - When a query is ambiguous or matches a large workflow, the agent should ask "Which part do you need help with?" before giving a full answer.

3. **Response feedback** - After each response, show thumbs up/down buttons. Use this feedback to improve article quality and identify gaps.

4. **Auto-suggest KB articles** - When resolved Freshdesk tickets come in, automatically suggest creating a KB article from the resolution.

5. **Multi-language support** - PropertyEngine operates in multiple regions. Support for Afrikaans and other languages.

6. **Bulk KB import** - Import existing support documentation (Freshdesk KB articles, Google Docs, Confluence) into the knowledge base in bulk.

7. **Analytics export** - Export agent performance reports for management review.

---

## Non-Functional Requirements

- **Response time** - Agent should respond within 5 seconds for a typical query
- **Availability** - The system should be available 24/7 (this is customer-facing)
- **Data privacy** - Customer conversations should not be used to train external AI models
- **Scalability** - Should handle up to 1000 queries per day without performance issues
- **Cost efficiency** - Minimize AI API costs per query (use smaller, cheaper models where possible)
