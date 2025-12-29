# Phase 13 Copilot Intelligence MVP - GitHub Issues Checklist

## Component: Vector Database & Indexing Infrastructure

### Issue P13-1: Implement Vector Database Setup and Schema
**Labels:** `component:database`, `phase:13`, `priority:high`
**Description:**
- Set up vector database infrastructure:
  - Option: Postgres with pgvector extension (preferred for production)
  - Option: SQLite with FAISS for development/testing
- Create database schema for vector storage:
  - `copilot_documents` table:
    - `id` (PK, auto-increment)
    - `tenant_id` (string, indexed, for isolation)
    - `source_type` (enum: POLICY_DOC | RESOLVED_EXCEPTION | AUDIT_EVENT | TOOL_REGISTRY | PLAYBOOK)
    - `source_id` (string, indexed, references original document)
    - `domain` (string, nullable, indexed)
    - `chunk_id` (string, for document chunking)
    - `content` (text, the document text)
    - `embedding` (vector, dimension based on model)
    - `metadata_json` (jsonb, title, snippet, url, etc.)
    - `created_at` (timestamp)
    - `version` (string, for document versioning)
- Create SQLAlchemy models for vector storage
- Create Alembic migration for vector tables
- Reference: docs/phase13-copilot-intelligence-mvp.md Section 4.2

**Dependencies:** None (foundational)

**Acceptance Criteria:**
- [ ] Vector database configured (pgvector or FAISS)
- [ ] copilot_documents table created with migration
- [ ] SQLAlchemy models implemented
- [ ] All required fields present
- [ ] Indexes created on tenant_id, source_type, source_id, domain
- [ ] Vector index configured for similarity search
- [ ] Migration tested and reversible
- [ ] Unit tests for vector storage models

---

### Issue P13-2: Implement Embedding Service
**Labels:** `component:embedding`, `phase:13`, `priority:high`
**Description:**
- Create EmbeddingService class:
  - Generate embeddings for text content using LLM API (OpenAI, Anthropic, etc.)
  - Support configurable embedding model
  - Batch embedding generation for efficiency
  - Handle embedding dimension configuration
- Support multiple embedding providers (OpenAI, local models, etc.)
- Cache embeddings to avoid regenerating for unchanged content
- Add retry logic and error handling for API failures
- Reference: docs/phase13-copilot-intelligence-mvp.md Section 4.2

**Dependencies:** None (can use external embedding API)

**Acceptance Criteria:**
- [ ] EmbeddingService implemented
- [ ] Embedding generation functional
- [ ] Batch embedding generation supported
- [ ] Configurable embedding model/provider
- [ ] Embedding caching implemented
- [ ] Error handling and retries functional
- [ ] Unit tests for embedding generation
- [ ] Integration tests with embedding provider

---

### Issue P13-3: Implement Document Chunking Service
**Labels:** `component:indexing`, `phase:13`, `priority:high`
**Description:**
- Create DocumentChunkingService class:
  - Split documents into semantic chunks (sentence/paragraph boundaries)
  - Preserve context (overlap between chunks)
  - Support different chunking strategies (fixed size, semantic, etc.)
  - Generate chunk metadata (chunk_id, position, parent_document_id)
- Handle different document types:
  - Policy documents (structured text)
  - Exception records (structured JSON → text)
  - Audit events (structured JSON → text)
- Preserve source attribution in chunks
- Reference: docs/phase13-copilot-intelligence-mvp.md Section 4.2

**Dependencies:** None

**Acceptance Criteria:**
- [ ] DocumentChunkingService implemented
- [ ] Semantic chunking functional
- [ ] Context overlap preserved
- [ ] Multiple chunking strategies supported
- [ ] Chunk metadata generation functional
- [ ] Source attribution preserved
- [ ] Unit tests for chunking logic
- [ ] Integration tests with different document types

---

## Component: RAG Indexing Pipeline

### Issue P13-4: Implement Policy Documents Indexer
**Labels:** `component:indexing`, `phase:13`, `priority:high`
**Description:**
- Create PolicyDocsIndexer class:
  - Extract policy documents from Domain Packs and Tenant Packs
  - Index SOPs, policy packs, playbook documentation
  - Track document versions and updates
  - Support incremental indexing (only changed documents)
- Background job integration:
  - Index on pack import/activation
  - Re-index on pack updates
- Tenant and domain isolation:
  - Tag documents with tenant_id and domain
  - Only retrieve within same tenant/domain scope
- Reference: docs/phase13-copilot-intelligence-mvp.md Section 4.1, 4.2

**Dependencies:** P13-1, P13-2, P13-3, P12-6, P12-7

**Acceptance Criteria:**
- [ ] PolicyDocsIndexer implemented
- [ ] Policy documents extracted from packs
- [ ] Indexing functional on pack import/activation
- [ ] Incremental indexing supported
- [ ] Version tracking functional
- [ ] Tenant/domain isolation enforced
- [ ] Background job integration working
- [ ] Unit tests for indexing logic
- [ ] Integration tests with pack imports

---

### Issue P13-5: Implement Resolved Exceptions Indexer
**Labels:** `component:indexing`, `phase:13`, `priority:high`
**Description:**
- Create ResolvedExceptionsIndexer class:
  - Extract resolved exceptions from database
  - Index final state, resolution notes, outcomes
  - Index exception metadata (severity, domain, type, classification)
- Background job integration:
  - Daily/hourly batch indexing of new resolved exceptions
  - Support incremental updates
- Tenant isolation:
  - Only index exceptions within tenant scope
  - Prevent cross-tenant retrieval
- Reference: docs/phase13-copilot-intelligence-mvp.md Section 4.1, 4.2

**Dependencies:** P13-1, P13-2, P13-3

**Acceptance Criteria:**
- [ ] ResolvedExceptionsIndexer implemented
- [ ] Resolved exceptions extracted from database
- [ ] Batch indexing functional (daily/hourly)
- [ ] Incremental indexing supported
- [ ] Exception metadata indexed
- [ ] Tenant isolation enforced
- [ ] Background job integration working
- [ ] Unit tests for indexing logic
- [ ] Integration tests with exception data

---

### Issue P13-6: Implement Audit Events Indexer
**Labels:** `component:indexing`, `phase:13`, `priority:medium`
**Description:**
- Create AuditEventsIndexer class:
  - Extract audit events from audit log
  - Index event descriptions, reasons for changes, decision explanations
  - Index audit metadata (timestamp, actor, action type)
- Background job integration:
  - Periodic indexing of recent audit events
  - Support incremental updates
- Tenant isolation enforced
- Reference: docs/phase13-copilot-intelligence-mvp.md Section 4.1, 4.2

**Dependencies:** P13-1, P13-2, P13-3

**Acceptance Criteria:**
- [ ] AuditEventsIndexer implemented
- [ ] Audit events extracted from audit log
- [ ] Periodic indexing functional
- [ ] Incremental indexing supported
- [ ] Audit metadata indexed
- [ ] Tenant isolation enforced
- [ ] Background job integration working
- [ ] Unit tests for indexing logic
- [ ] Integration tests with audit events

---

### Issue P13-7: Implement Tool Registry Indexer
**Labels:** `component:indexing`, `phase:13`, `priority:medium`
**Description:**
- Create ToolRegistryIndexer class:
  - Extract tool capabilities from Tool Registry
  - Index tool descriptions, parameters, capabilities (NOT secrets)
  - Support tool versioning
- Background job integration:
  - Index on tool registration/update
- Tenant and domain scoping:
  - Tools may be tenant-specific or domain-specific
- Reference: docs/phase13-copilot-intelligence-mvp.md Section 4.1, 4.2

**Dependencies:** P13-1, P13-2, P13-3

**Acceptance Criteria:**
- [ ] ToolRegistryIndexer implemented
- [ ] Tool capabilities extracted (no secrets)
- [ ] Indexing functional on tool registration/update
- [ ] Tool versioning supported
- [ ] Tenant/domain scoping enforced
- [ ] Background job integration working
- [ ] Unit tests for indexing logic
- [ ] Integration tests with tool registry

---

### Issue P13-8: Implement Index Rebuild Service
**Labels:** `component:indexing`, `phase:13`, `priority:high`
**Description:**
- Create IndexRebuildService class:
  - Support full rebuild of all indices
  - Support tenant-scoped rebuild
  - Support source-type-scoped rebuild (e.g., rebuild only policy docs)
  - Progress tracking and reporting
- Admin API endpoint:
  - `POST /copilot/index/rebuild` - Trigger rebuild (admin only)
- Background job execution:
  - Long-running rebuild jobs
  - Progress updates
- Reference: docs/phase13-copilot-intelligence-mvp.md Section 5

**Dependencies:** P13-4, P13-5, P13-6, P13-7

**Acceptance Criteria:**
- [ ] IndexRebuildService implemented
- [ ] Full rebuild functional
- [ ] Tenant-scoped rebuild functional
- [ ] Source-type-scoped rebuild functional
- [ ] Progress tracking functional
- [ ] Admin API endpoint working
- [ ] Background job execution working
- [ ] Unit tests for rebuild service
- [ ] Integration tests for rebuild operations

---

## Component: Copilot Query & Intent Detection

### Issue P13-9: Implement Intent Detection Router
**Labels:** `component:copilot`, `phase:13`, `priority:high`
**Description:**
- Create IntentDetectionRouter class:
  - Detect user intent from query:
    - `SUMMARY` - Summarize today's exceptions
    - `EXPLAIN` - Explain why exception was classified
    - `FIND_SIMILAR` - Find similar exceptions
    - `RECOMMEND_PLAYBOOK` - Recommend playbook
    - `DRAFT_RESPONSE` - Draft operator response
    - `GENERAL_QUERY` - General knowledge query
  - Use LLM for intent classification
  - Extract query parameters (exception_id, filters, etc.)
  - Return structured intent with parameters
- Support intent confidence scoring
- Reference: docs/phase13-copilot-intelligence-mvp.md Section 3, 4.3

**Dependencies:** None (can use LLM API)

**Acceptance Criteria:**
- [ ] IntentDetectionRouter implemented
- [ ] All intent types detected correctly
- [ ] Query parameters extracted
- [ ] Intent confidence scoring functional
- [ ] Unit tests for intent detection
- [ ] Integration tests with sample queries

---

### Issue P13-10: Implement Retrieval Service
**Labels:** `component:copilot`, `phase:13`, `priority:high`
**Description:**
- Create RetrievalService class:
  - Perform semantic similarity search in vector database
  - Support hybrid search (semantic + keyword filtering)
  - Retrieve top N relevant documents based on query embedding
  - Filter by tenant_id (mandatory isolation)
  - Filter by domain (optional)
  - Filter by source_type (optional)
- Return retrieved documents with:
  - Relevance score
  - Source metadata (title, snippet, url)
  - Content snippet
- Support re-ranking of results (optional enhancement)
- Reference: docs/phase13-copilot-intelligence-mvp.md Section 4.3

**Dependencies:** P13-1, P13-2

**Acceptance Criteria:**
- [ ] RetrievalService implemented
- [ ] Semantic similarity search functional
- [ ] Hybrid search supported
- [ ] Top N retrieval functional
- [ ] Tenant isolation enforced
- [ ] Domain/source_type filtering functional
- [ ] Relevance scores returned
- [ ] Source metadata included
- [ ] Unit tests for retrieval logic
- [ ] Integration tests with vector database

---

### Issue P13-11: Implement Similar Exceptions Finder
**Labels:** `component:copilot`, `phase:13`, `priority:high`
**Description:**
- Create SimilarExceptionsFinder class:
  - Find exceptions similar to a given exception_id
  - Use exception embedding for similarity search
  - Return top N similar exceptions with:
    - Similarity score
    - Exception details
    - Resolution outcome
    - Recommended next steps/playbook (if available)
- Tenant isolation enforced (only find within same tenant)
- Support similarity threshold filtering
- Reference: docs/phase13-copilot-intelligence-mvp.md Section 3, 5

**Dependencies:** P13-10, P13-5

**Acceptance Criteria:**
- [ ] SimilarExceptionsFinder implemented
- [ ] Similar exceptions found by exception_id
- [ ] Top N results returned with scores
- [ ] Resolution outcomes included
- [ ] Tenant isolation enforced
- [ ] Similarity threshold filtering supported
- [ ] Unit tests for similarity search
- [ ] Integration tests with exception data

---

## Component: Copilot Response Generation

### Issue P13-12: Implement Copilot Response Generator
**Labels:** `component:copilot`, `phase:13`, `priority:high`
**Description:**
- Create CopilotResponseGenerator class:
  - Generate structured responses based on intent and retrieved evidence
  - Assemble prompt with:
    - User query
    - Retrieved evidence (citations)
    - Context (exception details, tenant policy, etc.)
    - Instructions for structured output
  - Call LLM API to generate response
  - Parse structured response schema:
    ```json
    {
      "answer": "...",
      "bullets": ["..."],
      "citations": [...],
      "recommended_playbook": {...},
      "safety": {...}
    }
    ```
- Handle different intents with appropriate response templates
- Validate response schema
- Reference: docs/phase13-copilot-intelligence-mvp.md Section 4.3, 6

**Dependencies:** P13-9, P13-10

**Acceptance Criteria:**
- [ ] CopilotResponseGenerator implemented
- [ ] Prompt assembly functional with evidence
- [ ] LLM API integration working
- [ ] Structured response parsing functional
- [ ] Response schema validation working
- [ ] Intent-specific templates functional
- [ ] Unit tests for response generation
- [ ] Integration tests with different intents

---

### Issue P13-13: Implement Playbook Recommender
**Labels:** `component:copilot`, `phase:13`, `priority:high`
**Description:**
- Create PlaybookRecommender class:
  - Match exception characteristics to playbooks
  - Calculate playbook match confidence score
  - Extract playbook steps and descriptions
  - Explain match logic (why this playbook was recommended)
- Support playbook recommendation in response:
  - Playbook ID
  - Confidence score
  - Step-by-step guidance
- Reference: docs/phase13-copilot-intelligence-mvp.md Section 3, 6

**Dependencies:** P13-12, P12-6, P12-7

**Acceptance Criteria:**
- [ ] PlaybookRecommender implemented
- [ ] Playbook matching functional
- [ ] Confidence scoring functional
- [ ] Match logic explanation generated
- [ ] Step-by-step guidance extracted
- [ ] Unit tests for playbook recommendation
- [ ] Integration tests with playbooks

---

## Component: Conversation Memory

### Issue P13-14: Implement Conversation Session Storage
**Labels:** `component:database`, `phase:13`, `priority:high`
**Description:**
- Create database schema for conversation sessions:
  - `copilot_sessions` table:
    - `id` (PK, UUID)
    - `tenant_id` (string, indexed)
    - `user_id` (string, indexed)
    - `created_at` (timestamp)
    - `last_activity_at` (timestamp)
    - `context_json` (jsonb, session context/metadata)
  - `copilot_messages` table:
    - `id` (PK, auto-increment)
    - `session_id` (FK to copilot_sessions)
    - `role` (enum: USER | ASSISTANT | SYSTEM)
    - `content` (text)
    - `metadata_json` (jsonb, citations, playbook recommendations, etc.)
    - `created_at` (timestamp)
- Create SQLAlchemy models
- Create Alembic migration
- Tenant and user isolation enforced
- Reference: docs/phase13-copilot-intelligence-mvp.md Section 3, 5

**Dependencies:** None (foundational)

**Acceptance Criteria:**
- [ ] copilot_sessions table created with migration
- [ ] copilot_messages table created with migration
- [ ] SQLAlchemy models implemented
- [ ] Tenant/user isolation enforced
- [ ] Indexes created appropriately
- [ ] Migration tested and reversible
- [ ] Unit tests for session models

---

### Issue P13-15: Implement Conversation Memory Service
**Labels:** `component:copilot`, `phase:13`, `priority:high`
**Description:**
- Create ConversationMemoryService class:
  - Create new conversation session
  - Store messages in session
  - Retrieve conversation history (last N messages)
  - Load session context for response generation
  - Update session last_activity_at
  - Support session cleanup (TTL-based)
- Tenant and user scoping:
  - Only retrieve sessions for same tenant + user
  - Prevent cross-tenant/user access
- Reference: docs/phase13-copilot-intelligence-mvp.md Section 3

**Dependencies:** P13-14

**Acceptance Criteria:**
- [ ] ConversationMemoryService implemented
- [ ] Session creation functional
- [ ] Message storage functional
- [ ] Conversation history retrieval functional
- [ ] Session context loading functional
- [ ] Tenant/user isolation enforced
- [ ] Session cleanup functional
- [ ] Unit tests for memory service
- [ ] Integration tests with database

---

## Component: Safety & RBAC

### Issue P13-16: Implement Copilot Safety Constraints
**Labels:** `component:safety`, `phase:13`, `priority:high`
**Description:**
- Create CopilotSafetyService class:
  - Enforce "read-only by default" mode
  - Validate that no actions are suggested without approval
  - Check tenant policy for allowed actions
  - Block CRITICAL severity actions unless explicitly permitted
- Safety validation in response:
  - Set `safety.mode` to "READ_ONLY"
  - Set `safety.actions_allowed` based on tenant policy
  - Reject response if unsafe actions detected
- Integration with tenant policy packs
- Reference: docs/phase13-copilot-intelligence-mvp.md Section 8

**Dependencies:** P13-12, P12-7

**Acceptance Criteria:**
- [ ] CopilotSafetyService implemented
- [ ] Read-only mode enforced by default
- [ ] Action suggestion validation functional
- [ ] Tenant policy integration working
- [ ] CRITICAL severity blocking functional
- [ ] Safety metadata in response functional
- [ ] Unit tests for safety constraints
- [ ] Integration tests with tenant policies

---

### Issue P13-17: Implement Copilot RBAC
**Labels:** `component:rbac`, `phase:13`, `priority:high`
**Description:**
- Enforce RBAC for Copilot endpoints:
  - Tenant-scoped access (users can only access their tenant's copilot)
  - Role-based permissions:
    - OPERATOR: Can use copilot, view citations
    - SUPERVISOR: Can use copilot, view full context
    - ADMIN: Can rebuild indices, view debug info
  - User context extraction from authentication token
- Tenant isolation checks in all Copilot operations
- Reference: docs/phase13-copilot-intelligence-mvp.md Section 8

**Dependencies:** P13-9, P13-10, P13-11, P13-12

**Acceptance Criteria:**
- [ ] Tenant-scoped access enforced
- [ ] Role-based permissions enforced
- [ ] User context extraction functional
- [ ] Tenant isolation checks in all operations
- [ ] Unit tests for RBAC enforcement
- [ ] Integration tests with different roles

---

## Component: Backend APIs

### Issue P13-18: Implement Copilot Chat API
**Labels:** `component:api:copilot`, `phase:13`, `priority:high`
**Description:**
- Create `POST /copilot/chat` endpoint:
  - Accept query, session_id (optional), exception_id (optional)
  - Perform intent detection
  - Retrieve evidence
  - Generate structured response
  - Store message in session
  - Return structured response with citations
- Request schema:
  ```json
  {
    "query": "...",
    "session_id": "uuid (optional)",
    "exception_id": "EX-xxx (optional)",
    "context": {...}
  }
  ```
- Response schema matches Section 6 of spec
- Tenant context from authentication
- Reference: docs/phase13-copilot-intelligence-mvp.md Section 5

**Dependencies:** P13-9, P13-10, P13-12, P13-15, P13-16, P13-17

**Acceptance Criteria:**
- [ ] POST /copilot/chat endpoint working
- [ ] Intent detection integrated
- [ ] Evidence retrieval integrated
- [ ] Response generation integrated
- [ ] Session management integrated
- [ ] Structured response returned
- [ ] Tenant context enforced
- [ ] Unit tests for API endpoint
- [ ] Integration tests for full flow

---

### Issue P13-19: Implement Copilot Session Management API
**Labels:** `component:api:copilot`, `phase:13`, `priority:medium`
**Description:**
- Create session management endpoints:
  - `POST /copilot/sessions` - Create new session
  - `GET /copilot/sessions/{id}` - Get session with message history
  - `DELETE /copilot/sessions/{id}` - Delete session (optional)
- Tenant and user scoping enforced
- Return session metadata and message history
- Reference: docs/phase13-copilot-intelligence-mvp.md Section 5

**Dependencies:** P13-14, P13-15, P13-17

**Acceptance Criteria:**
- [ ] POST /copilot/sessions endpoint working
- [ ] GET /copilot/sessions/{id} endpoint working
- [ ] DELETE /copilot/sessions/{id} endpoint working (optional)
- [ ] Tenant/user scoping enforced
- [ ] Session history returned correctly
- [ ] Unit tests for session endpoints
- [ ] Integration tests with session lifecycle

---

### Issue P13-20: Implement Similar Exceptions API
**Labels:** `component:api:copilot`, `phase:13`, `priority:high`
**Description:**
- Create `GET /copilot/similar/{exception_id}` endpoint:
  - Find similar exceptions to given exception_id
  - Return top N similar with:
    - Similarity scores
    - Exception details
    - Resolution outcomes
    - Recommended playbooks
- Query parameters:
  - `limit` (default: 10)
  - `threshold` (minimum similarity score)
- Tenant isolation enforced
- Reference: docs/phase13-copilot-intelligence-mvp.md Section 5

**Dependencies:** P13-11, P13-17

**Acceptance Criteria:**
- [ ] GET /copilot/similar/{exception_id} endpoint working
- [ ] Similar exceptions returned with scores
- [ ] Resolution outcomes included
- [ ] Recommended playbooks included
- [ ] Query parameters supported
- [ ] Tenant isolation enforced
- [ ] Unit tests for similar exceptions endpoint
- [ ] Integration tests with exception data

---

### Issue P13-21: Implement Evidence Debug API
**Labels:** `component:api:copilot`, `phase:13`, `priority:low`
**Description:**
- Create `GET /copilot/evidence/{request_id}` endpoint:
  - Return retrieved evidence for a specific request
  - Include:
    - Retrieved documents
    - Relevance scores
    - Source metadata
  - Admin-only access
- Useful for debugging and explainability
- Reference: docs/phase13-copilot-intelligence-mvp.md Section 5

**Dependencies:** P13-10, P13-17

**Acceptance Criteria:**
- [ ] GET /copilot/evidence/{request_id} endpoint working
- [ ] Retrieved evidence returned
- [ ] Relevance scores included
- [ ] Source metadata included
- [ ] Admin-only access enforced
- [ ] Unit tests for evidence endpoint

---

## Component: UI - Copilot Chat Interface

### Issue P13-22: Implement Copilot Chat UI Component
**Labels:** `component:ui:copilot`, `phase:13`, `priority:high`
**Description:**
- Create Copilot chat interface at `/copilot` route:
  - Chat message list with user/assistant messages
  - Input field for queries
  - Send button
  - Loading states during response generation
  - Error handling and display
- Display structured response:
  - Answer text
  - Bullet points
  - Citations panel (expandable, shows source title, snippet, link)
  - Recommended playbook section (if present)
  - Safety indicators (read-only mode)
- Support conversation sessions:
  - New conversation button
  - Session history display
  - Continue existing session
- Use Material UI components (Chat, TextField, Button, Accordion for citations)
- Reference: docs/phase13-copilot-intelligence-mvp.md Section 7

**Dependencies:** P13-18, P13-19, P11-2, P11-3

**Acceptance Criteria:**
- [ ] Copilot chat page created at `/copilot` route
- [ ] Chat message list displays correctly
- [ ] Input field and send button functional
- [ ] Loading states handled
- [ ] Error states handled
- [ ] Structured response displayed
- [ ] Citations panel expandable
- [ ] Recommended playbook displayed
- [ ] Session management functional
- [ ] Unit tests for Copilot chat components

---

### Issue P13-23: Implement Explainability Panel in Exception Detail
**Labels:** `component:ui:copilot`, `phase:13`, `priority:high`
**Description:**
- Add "Explainability" tab to Exception Detail page:
  - Show classification reasoning (top features/rules)
  - Show model confidence scores
  - Display evidence retrieved (citations)
  - Show similar cases (with links)
  - Display recommended playbook with match logic
- Add "Ask Copilot about this exception" shortcut:
  - Opens Copilot chat with exception context pre-loaded
  - Query template: "Explain why this exception was classified as [classification]"
- Integrate with Copilot APIs
- Use existing Exception Detail page structure
- Reference: docs/phase13-copilot-intelligence-mvp.md Section 7

**Dependencies:** P13-22, P13-20, P4-15 (Exception Detail page)

**Acceptance Criteria:**
- [ ] Explainability tab added to Exception Detail page
- [ ] Classification reasoning displayed
- [ ] Model confidence scores displayed
- [ ] Evidence/citations displayed
- [ ] Similar cases displayed with links
- [ ] Recommended playbook displayed
- [ ] "Ask Copilot" shortcut functional
- [ ] Copilot opens with exception context
- [ ] Unit tests for Explainability panel

---

### Issue P13-24: Implement Copilot API Client Functions
**Labels:** `component:ui:api`, `phase:13`, `priority:high`
**Description:**
- Create API client functions in `ui/src/api/copilot.ts`:
  - `POST /copilot/chat` - Send chat query
  - `POST /copilot/sessions` - Create session
  - `GET /copilot/sessions/{id}` - Get session
  - `GET /copilot/similar/{exception_id}` - Get similar exceptions
  - `GET /copilot/evidence/{request_id}` - Get evidence (admin only)
  - `POST /copilot/index/rebuild` - Rebuild index (admin only)
- Ensure all functions include tenant context (header)
- Use existing HTTP client utility
- Add TypeScript types for all request/response models
- Central error handling (toast notifications)
- Reference: docs/phase13-copilot-intelligence-mvp.md Section 5

**Dependencies:** None (can use existing HTTP client)

**Acceptance Criteria:**
- [ ] Copilot API client file created in `ui/src/api/copilot.ts`
- [ ] All chat functions implemented
- [ ] All session functions implemented
- [ ] Similar exceptions function implemented
- [ ] Evidence function implemented (admin)
- [ ] Index rebuild function implemented (admin)
- [ ] Tenant context included in all requests
- [ ] TypeScript types defined for all models
- [ ] Central error handling functional
- [ ] Unit tests for API client functions

---

## Component: Playbook Workflow Viewer (Section 7A)

### Issue P13-25: Implement Playbook Graph Model Service
**Labels:** `component:playbook`, `phase:13`, `priority:high`
**Description:**
- Create PlaybookGraphService class:
  - Convert playbook JSON from packs to graph model:
    - Extract nodes (agent, decision, human, system steps)
    - Extract edges (transitions, conditions)
    - Generate graph structure:
      ```json
      {
        "playbook_id": "...",
        "name": "...",
        "nodes": [...],
        "edges": [...]
      }
      ```
  - Support graph model validation
  - Handle different playbook formats from domain/tenant packs
- Reference: docs/phase13-copilot-intelligence-mvp.md Section 7A.3

**Dependencies:** P12-6, P12-7

**Acceptance Criteria:**
- [ ] PlaybookGraphService implemented
- [ ] Playbook JSON → graph conversion functional
- [ ] Nodes extracted correctly
- [ ] Edges extracted correctly
- [ ] Graph model validation functional
- [ ] Multiple playbook formats supported
- [ ] Unit tests for graph conversion
- [ ] Integration tests with sample playbooks

---

### Issue P13-26: Implement Playbook Execution State Service
**Labels:** `component:playbook`, `phase:13`, `priority:high`
**Description:**
- Create PlaybookExecutionStateService class:
  - Map execution events to workflow step status
  - Track step execution state:
    - PENDING | IN_PROGRESS | COMPLETED | FAILED | SKIPPED
  - Extract execution metadata:
    - started_at, completed_at
    - actor (AI_AGENT | HUMAN | SYSTEM)
    - notes
  - Correlate agent actions and approvals to workflow steps
  - Generate execution overlay for workflow diagram
- Reference: docs/phase13-copilot-intelligence-mvp.md Section 7A.4

**Dependencies:** P13-25

**Acceptance Criteria:**
- [ ] PlaybookExecutionStateService implemented
- [ ] Execution events mapped to steps
- [ ] Step status tracking functional
- [ ] Execution metadata extracted
- [ ] Execution overlay generated
- [ ] Unit tests for execution state service
- [ ] Integration tests with execution events

---

### Issue P13-27: Implement Playbook Workflow Viewer API
**Labels:** `component:api:playbook`, `phase:13`, `priority:medium`
**Description:**
- Create optional lightweight APIs (if needed for UI decoupling):
  - `GET /playbooks/{playbook_id}/graph` - Get playbook graph
  - `GET /exceptions/{exception_id}/playbook-execution` - Get execution state
- APIs adapt existing pack + execution data (no new persistence)
- Return graph model + execution overlay
- Tenant isolation enforced
- Reference: docs/phase13-copilot-intelligence-mvp.md Section 7A.5

**Dependencies:** P13-25, P13-26, P13-17

**Acceptance Criteria:**
- [ ] GET /playbooks/{playbook_id}/graph endpoint working
- [ ] GET /exceptions/{exception_id}/playbook-execution endpoint working
- [ ] Graph model returned
- [ ] Execution overlay returned
- [ ] Tenant isolation enforced
- [ ] Unit tests for workflow APIs
- [ ] Integration tests with playbooks

---

### Issue P13-28: Implement Playbook Workflow Viewer UI
**Labels:** `component:ui:playbook`, `phase:13`, `priority:high`
**Description:**
- Add "Workflow" tab to Exception Detail page:
  - Display playbook workflow diagram using React Flow (or equivalent)
  - Show nodes with type icons:
    - Agent (🤖 Blue)
    - Human (👤 Purple)
    - Decision (🔀 Orange)
    - System (⚙️ Gray)
  - Show step status indicators:
    - Pending (hollow circle)
    - In Progress (pulsing)
    - Completed (green check)
    - Failed (red cross)
    - Skipped (dashed)
  - Highlight current step
  - Show step-by-step execution state
  - Read-only (no editing)
- Integrate with Copilot:
  - "View workflow" action in Copilot responses
  - "Highlight current step" shortcut
  - "Explain why this step is next" query
- Reference: docs/phase13-copilot-intelligence-mvp.md Section 7A.6, 7A.7, 7A.8

**Dependencies:** P13-27, P13-22, P4-15, P11-2

**Acceptance Criteria:**
- [ ] Workflow tab added to Exception Detail page
- [ ] Playbook workflow diagram rendered
- [ ] Node type icons displayed correctly
- [ ] Step status indicators displayed correctly
- [ ] Current step highlighted
- [ ] Execution state displayed
- [ ] Read-only enforced
- [ ] Copilot integration functional
- [ ] React Flow (or equivalent) integrated
- [ ] Unit tests for Workflow Viewer components

---

### Issue P13-29: Enhance Copilot with Workflow Queries
**Labels:** `component:copilot`, `phase:13`, `priority:medium`
**Description:**
- Extend Copilot to handle workflow-related queries:
  - "Show me the workflow for this exception"
  - "Which step is blocking resolution?"
  - "Why is human approval required here?"
  - "What happens if this step fails?"
- Copilot responses must:
  - Reference workflow step IDs
  - Cite playbook definition + execution state
  - Provide actionable guidance
  - Remain read-only
- Integrate with PlaybookGraphService and PlaybookExecutionStateService
- Reference: docs/phase13-copilot-intelligence-mvp.md Section 7A.8

**Dependencies:** P13-12, P13-25, P13-26

**Acceptance Criteria:**
- [ ] Copilot handles workflow queries
- [ ] Workflow step references included
- [ ] Playbook definition cited
- [ ] Execution state cited
- [ ] Read-only mode maintained
- [ ] Unit tests for workflow queries
- [ ] Integration tests with workflow context

---

## Component: Testing & Documentation

### Issue P13-30: Implement Phase 13 Integration Tests
**Labels:** `component:testing`, `phase:13`, `priority:high`
**Description:**
- Write integration tests for Phase 13 components:
  - Vector database indexing tests
  - Retrieval and similarity search tests
  - Intent detection and routing tests
  - Response generation tests
  - Session management tests
  - Tenant isolation tests for all operations
  - RBAC enforcement tests
  - Workflow viewer tests
  - End-to-end Copilot chat flow tests
- Test cross-tenant isolation (ensure no leakage)
- Test with multiple domains (Finance, Healthcare)
- Achieve >80% code coverage for Phase 13 code
- Reference: docs/phase13-copilot-intelligence-mvp.md Section 9

**Dependencies:** P13-1 through P13-29

**Acceptance Criteria:**
- [ ] Vector database integration tests passing
- [ ] Retrieval tests passing
- [ ] Intent detection tests passing
- [ ] Response generation tests passing
- [ ] Session management tests passing
- [ ] Tenant isolation tests passing
- [ ] RBAC tests passing
- [ ] Workflow viewer tests passing
- [ ] End-to-end tests passing
- [ ] Code coverage >80%

---

### Issue P13-31: Update Documentation for Phase 13
**Labels:** `component:documentation`, `phase:13`, `priority:high`
**Description:**
- Update docs/STATE_OF_THE_PLATFORM.md with Phase 13 capabilities
- Create or update docs/copilot-intelligence-guide.md:
  - Copilot usage guide
  - Intent types and query examples
  - Citation and evidence explanation
  - Workflow viewer guide
  - Safety and RBAC overview
- Document all new API endpoints
- Document all new UI screens
- Document indexing pipeline and maintenance
- Document vector database setup and configuration
- Reference: docs/phase13-copilot-intelligence-mvp.md Section 10

**Dependencies:** All P13 issues

**Acceptance Criteria:**
- [ ] STATE_OF_THE_PLATFORM.md updated
- [ ] copilot-intelligence-guide.md created/updated
- [ ] All new API endpoints documented
- [ ] All new UI screens documented
- [ ] Indexing pipeline documented
- [ ] Vector database setup documented

---

## Summary

**Total Issues:** 31
**High Priority:** 26
**Medium Priority:** 4
**Low Priority:** 1

**Components Covered:**
- Vector Database & Indexing Infrastructure (3 issues)
- RAG Indexing Pipeline (5 issues)
- Copilot Query & Intent Detection (3 issues)
- Copilot Response Generation (2 issues)
- Conversation Memory (2 issues)
- Safety & RBAC (2 issues)
- Backend APIs (4 issues)
- UI - Copilot Chat Interface (3 issues)
- Playbook Workflow Viewer (Section 7A) (5 issues)
- Testing & Documentation (2 issues)

**Implementation Order:**

### Foundation (Week 1)
1. P13-1: Vector Database Setup and Schema
2. P13-2: Embedding Service
3. P13-3: Document Chunking Service
4. P13-14: Conversation Session Storage

### Indexing Pipeline (Week 2)
5. P13-4: Policy Documents Indexer
6. P13-5: Resolved Exceptions Indexer
7. P13-6: Audit Events Indexer (optional)
8. P13-7: Tool Registry Indexer (optional)
9. P13-8: Index Rebuild Service

### Copilot Core (Week 3)
10. P13-9: Intent Detection Router
11. P13-10: Retrieval Service
12. P13-11: Similar Exceptions Finder
13. P13-12: Copilot Response Generator
14. P13-13: Playbook Recommender
15. P13-15: Conversation Memory Service
16. P13-16: Copilot Safety Constraints
17. P13-17: Copilot RBAC

### Backend APIs (Week 4)
18. P13-18: Copilot Chat API
19. P13-19: Copilot Session Management API
20. P13-20: Similar Exceptions API
21. P13-21: Evidence Debug API (optional)

### UI - Copilot Chat (Week 5)
22. P13-24: Copilot API Client Functions
23. P13-22: Copilot Chat UI Component
24. P13-23: Explainability Panel in Exception Detail

### Playbook Workflow Viewer (Week 6)
25. P13-25: Playbook Graph Model Service
26. P13-26: Playbook Execution State Service
27. P13-27: Playbook Workflow Viewer API (optional)
28. P13-28: Playbook Workflow Viewer UI
29. P13-29: Enhance Copilot with Workflow Queries

### Finalization (Week 7)
30. P13-30: Integration Tests
31. P13-31: Documentation

**Key Dependencies:**
- P13-1, P13-2, P13-3 must be completed before indexing pipeline
- P13-4 through P13-7 depend on P13-1, P13-2, P13-3
- P13-9, P13-10, P13-11 must be completed before response generation
- P13-12 depends on P13-9, P13-10
- P13-14 must be completed before P13-15
- P13-16, P13-17 depend on P13-12
- P13-18 depends on most Copilot core components
- UI issues depend on backend APIs being available
- P13-24 must be completed before P13-22, P13-23
- P13-25, P13-26 must be completed before P13-27, P13-28
- P13-28 depends on P13-27 (if APIs are created)
- All UI issues depend on Phase 11 shared components (P11-2, P11-3)

**Spec References:**
- docs/phase13-copilot-intelligence-mvp.md - Phase 13 Copilot Intelligence MVP specification
- docs/03-data-models-apis.md - Backend API schemas and data models
- docs/10-ui-guidelines.md - UI working principles and tech stack
- Phase 12 pack management (for accessing policy/playbook docs)
- Phase 11 shared UI components (DataTable, FilterBar, etc.)
- Phase 4 Exception Detail page (for Explainability tab integration)

