# Multi-Agent Orchestration Architecture

This document describes the architecture and design patterns used in the multi-agent orchestration system.

## Table of Contents

1. [System Overview](#system-overview)
2. [Architecture Layers](#architecture-layers)
3. [Component Interactions](#component-interactions)
4. [Data Flow](#data-flow)
5. [Design Patterns](#design-patterns)
6. [Execution Model](#execution-model)

---

## System Overview

The multi-agent orchestration system implements a **hierarchical agent architecture** where a main orchestrator agent delegates specialized tasks to sub-agents, each with their own LLM, memory, and tools.

### High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                          User / Client                          │
└──────────────────────────────┬──────────────────────────────────┘
                               │
                               │ Complex Task
                               │
┌──────────────────────────────▼──────────────────────────────────┐
│                     Main Orchestrator Agent                     │
│  ┌────────────────────────────────────────────────────────┐    │
│  │ - Task Analysis & Decomposition                        │    │
│  │ - Sub-Agent Selection & Delegation                     │    │
│  │ - Result Aggregation & Synthesis                       │    │
│  │ - LLM: GPT-4 / Claude / etc.                          │    │
│  │ - Memory: Task history, agent interactions            │    │
│  │ - Tools: search_agent, pdf_agent                      │    │
│  └────────────────────────────────────────────────────────┘    │
└────────────┬────────────────────────────────┬──────────────────┘
             │                                │
             │ Delegate                       │ Delegate
             │ Search Tasks                   │ PDF Tasks
             │                                │
┌────────────▼──────────────┐    ┌───────────▼─────────────────┐
│   Search Agent Service    │    │    PDF Agent Service        │
│  ┌──────────────────────┐ │    │  ┌───────────────────────┐ │
│  │ Agent Registry       │ │    │  │ Agent Registry        │ │
│  │ ├─ search_agent_1   │ │    │  │ ├─ pdf_agent_1       │ │
│  │ ├─ search_agent_2   │ │    │  │ ├─ pdf_agent_2       │ │
│  │ └─ ...              │ │    │  │ └─ ...               │ │
│  └──────────────────────┘ │    │  └───────────────────────┘ │
│                            │    │                             │
│  Each Agent Instance:      │    │  Each Agent Instance:       │
│  - Own LLM                 │    │  - Own LLM                  │
│  - Own Memory              │    │  - Own Memory               │
│  - Specialized Tools       │    │  - Specialized Tools        │
└────────────┬───────────────┘    └─────────────┬───────────────┘
             │                                   │
             │ Tool Calls                        │ Tool Calls
             │                                   │
┌────────────▼───────────────┐    ┌─────────────▼───────────────┐
│   MCP Tools (Search)       │    │   MCP Tools (PDF)           │
│  ┌──────────────────────┐  │    │  ┌───────────────────────┐ │
│  │ - Google Search      │  │    │  │ - PDF Extraction      │ │
│  │ - File Download      │  │    │  │ - Image Extraction    │ │
│  │ - Result Formatting  │  │    │  │ - OCR Processing      │ │
│  └──────────────────────┘  │    │  └───────────────────────┘ │
└────────────────────────────┘    └─────────────────────────────┘
```

---

## Architecture Layers

### Layer 0: User Interface Layer

**Purpose:** Entry point for user tasks and requests

**Components:**
- `example_usage.py`: Example workflows and interactive interface
- CLI or API endpoints (future extension)

**Responsibilities:**
- Receive user tasks
- Display results
- Handle user interactions

### Layer 1: Main Orchestrator Layer

**Purpose:** High-level task coordination and delegation

**Components:**
- Main Agent (Orchestrator)
- Task decomposition logic
- Result synthesis logic

**Responsibilities:**
- Analyze complex tasks
- Determine which sub-agents are needed
- Delegate subtasks to specialized agents
- Aggregate and synthesize results
- Provide final answer to user

**Key Characteristics:**
- Access to multiple sub-agent MCP servers
- Higher-level reasoning and planning
- No direct access to low-level tools (delegates to sub-agents)

### Layer 2: Sub-Agent Service Layer

**Purpose:** Provide specialized agent services with lifecycle management

**Components:**
- `SearchAgentCollection`: Search agent service
- `PDFAgentCollection`: PDF agent service
- `AgentRegistry`: Per-service agent instance management

**Responsibilities:**
- Create new agent instances
- Manage agent lifecycle (create, retrieve, reuse)
- Execute delegated tasks
- Return structured results
- Maintain agent metadata

**Key Characteristics:**
- MCP server implementation (ActionCollection)
- Agent registry for instance management
- Independent per-service configuration

### Layer 3: Agent Execution Layer

**Purpose:** Execute agent reasoning and tool usage

**Components:**
- `Agent`: Core agent implementation from AWorld framework
- `Task`: Task definition and configuration
- `Runners`: Task execution orchestration
- Agent memory and context

**Responsibilities:**
- Execute think-act-observe loop
- Manage LLM interactions
- Handle memory and context
- Execute tool calls
- Return execution results

**Key Characteristics:**
- Autonomous reasoning
- Independent LLM instance per agent
- Memory isolation between agents

### Layer 4: MCP Tools Layer

**Purpose:** Provide low-level capabilities through MCP protocol

**Components:**
- Search tools (Google Custom Search)
- Download tools (HTTP file retrieval)
- PDF extraction tools (Marker-based processing)

**Responsibilities:**
- Execute specific operations (search, download, extract)
- Format results for LLM consumption
- Handle errors and edge cases
- Validate inputs and outputs

---

## Component Interactions

### 1. Agent Creation Flow

```
Main Agent
    │
    ├─> MCP Call: search_agent.mcp_create_search_agent(...)
    │
    └─> Search Agent Service (SearchAgentCollection)
        │
        ├─> 1. Generate unique agent_id
        │
        ├─> 2. Load LLM configuration from environment
        │
        ├─> 3. Create AgentConfig
        │
        ├─> 4. Load MCP tools configuration
        │
        ├─> 5. Create Agent instance with:
        │      - agent_id
        │      - system_prompt
        │      - mcp_config (search, download tools)
        │      - mcp_servers list
        │
        ├─> 6. Register agent in AgentRegistry
        │
        ├─> 7. Create Task with agent
        │
        ├─> 8. Execute: Runners.sync_run_task(task)
        │      │
        │      └─> Agent reasoning loop:
        │          - Think: Analyze task
        │          - Act: Call MCP tools
        │          - Observe: Process results
        │          - Repeat until complete
        │
        └─> 9. Return ActionResponse with:
               - success status
               - agent_id
               - task results
               - metadata
```

### 2. Task Delegation Flow

```
User Task: "Find arXiv paper from Aug 2020, download, summarize in 1000 words"
    │
    ├─> Main Agent receives task
    │
    ├─> Main Agent reasoning:
    │   "This requires:
    │    1. Web search + download (search_agent)
    │    2. PDF extraction + summarization (pdf_agent)"
    │
    ├─> Step 1: Delegate to Search Agent
    │   │
    │   ├─> Tool Call: search_agent.mcp_create_search_agent(
    │   │       task_prompt="Find and download arXiv paper..."
    │   │   )
    │   │
    │   ├─> Search Agent Instance Created
    │   │   │
    │   │   ├─> Think: "Need to search arXiv for papers from Aug 2020"
    │   │   ├─> Act: search.mcp_search_google(query="site:arxiv.org...")
    │   │   ├─> Observe: Found paper URLs
    │   │   ├─> Think: "Found relevant paper, need to download"
    │   │   ├─> Act: download.mcp_download_file(url="...", output="paper.pdf")
    │   │   ├─> Observe: Download successful
    │   │   └─> Return: {file_path: "paper.pdf", metadata: {...}}
    │   │
    │   └─> Main Agent receives: file_path
    │
    ├─> Step 2: Delegate to PDF Agent
    │   │
    │   ├─> Tool Call: pdf_agent.mcp_create_pdf_agent(
    │   │       task_prompt="Extract and summarize paper.pdf in 1000 words..."
    │   │   )
    │   │
    │   ├─> PDF Agent Instance Created
    │   │   │
    │   │   ├─> Think: "Need to extract content from PDF"
    │   │   ├─> Act: pdf.mcp_extract_document_content(file_path="paper.pdf")
    │   │   ├─> Observe: Content extracted successfully
    │   │   ├─> Think: "Need to create 1000-word summary"
    │   │   ├─> Analyze: Process content, identify key points
    │   │   └─> Return: {summary: "...", word_count: 1000, metadata: {...}}
    │   │
    │   └─> Main Agent receives: summary
    │
    ├─> Step 3: Synthesize Results
    │   │
    │   └─> Main Agent combines:
    │       - Paper title and source (from search agent)
    │       - Summary and key findings (from PDF agent)
    │       - Additional context and insights
    │
    └─> Return: Final comprehensive answer to user
```

### 3. Agent Reuse Flow

```
First Task:
Main Agent → search_agent.mcp_create_search_agent(...)
         └─> Returns: agent_id = "search_agent_abc123"

Second Task (related):
Main Agent → search_agent.mcp_use_existing_search_agent(
                agent_id="search_agent_abc123",
                task_prompt="New related task"
             )
         └─> Reuses existing agent with:
             - Same LLM configuration
             - Previous memory/context
             - Established tool connections
```

---

## Data Flow

### Request Flow

```
User Input
    │
    │ 1. Complex task string
    │
    ▼
Main Agent
    │
    │ 2. Task analysis & decomposition
    │
    ├─────────────────┬─────────────────┐
    │                 │                 │
    ▼                 ▼                 ▼
Search Agent    PDF Agent       [Other Agents]
    │                 │                 │
    │ 3. Subtask      │ 3. Subtask      │ 3. Subtask
    │ execution       │ execution       │ execution
    │                 │                 │
    ▼                 ▼                 ▼
MCP Tools       MCP Tools       MCP Tools
    │                 │                 │
    │ 4. Low-level    │ 4. Low-level    │ 4. Low-level
    │ operations      │ operations      │ operations
    │                 │                 │
    └─────────────────┴─────────────────┘
                      │
                      │ 5. Results aggregation
                      │
                      ▼
                Main Agent
                      │
                      │ 6. Result synthesis
                      │
                      ▼
                 User Output
```

### Data Structures

#### ActionArguments (Input to Agent Services)
```python
{
    "name": "search_agent_service",
    "transport": "stdio",
    "workspace": "/path/to/workspace",
    "unittest": false
}
```

#### ActionResponse (Output from Agent Services)
```python
{
    "success": true,
    "message": "# Search Agent Execution Results\n...",
    "metadata": {
        "agent_id": "search_agent_abc123",
        "agent_name": "arxiv_search_agent",
        "description": "Agent for searching arXiv",
        "answer": "Downloaded paper.pdf successfully",
        "task_prompt": "Find and download...",
        "created_at": "2024-01-15 10:30:00",
        "llm_provider": "openai",
        "llm_model_name": "gpt-4o",
        "mcp_servers": ["search", "download"]
    }
}
```

#### Agent Metadata
```python
{
    "agent_id": "search_agent_abc123",
    "name": "arxiv_search_agent",
    "description": "Specialized agent for searching arXiv",
    "created_at": "2024-01-15 10:30:00",
    "llm_provider": "openai",
    "llm_model_name": "gpt-4o",
    "mcp_servers": ["search", "download"]
}
```

---

## Design Patterns

### 1. Registry Pattern

**Purpose:** Manage multiple agent instances with unique identifiers

**Implementation:**
```python
class AgentRegistry:
    def __init__(self):
        self._agents: Dict[str, Agent] = {}
        self._metadata: Dict[str, AgentMetadata] = {}
    
    def register(self, agent, metadata):
        self._agents[metadata.agent_id] = agent
        self._metadata[metadata.agent_id] = metadata
    
    def get_agent(self, agent_id):
        return self._agents.get(agent_id)
```

**Benefits:**
- Track multiple agent instances
- Enable agent reuse
- Maintain agent metadata
- Support concurrent agents

### 2. Delegation Pattern

**Purpose:** Distribute work to specialized components

**Implementation:**
```python
# Main agent delegates to sub-agents
result = search_agent.mcp_create_search_agent(
    task_prompt="specialized search task"
)

# Sub-agent executes autonomously
# Main agent receives results
```

**Benefits:**
- Separation of concerns
- Specialized expertise per agent
- Parallel capability (future)
- Modular architecture

### 3. Factory Pattern

**Purpose:** Create agent instances with consistent configuration

**Implementation:**
```python
def _create_agent_instance(self, name, description):
    agent_id = f"agent_{uuid.uuid4().hex[:8]}"
    agent_config = AgentConfig(...)
    agent = Agent(
        conf=agent_config,
        name=name,
        agent_id=agent_id,
        system_prompt=system_prompt,
        mcp_config=self.mcp_config,
        mcp_servers=available_servers,
    )
    metadata = AgentMetadata(...)
    self.agent_registry.register(agent, metadata)
    return agent, metadata
```

**Benefits:**
- Consistent agent creation
- Centralized configuration
- Easy to modify/extend
- Proper initialization

### 4. Service Pattern

**Purpose:** Encapsulate agent services as MCP servers

**Implementation:**
```python
class SearchAgentCollection(ActionCollection):
    def __init__(self, arguments):
        super().__init__(arguments)
        self.agent_registry = AgentRegistry()
        self.mcp_config = self._load_mcp_config()
    
    def mcp_create_search_agent(self, ...):
        # Service method
        pass
```

**Benefits:**
- Standardized interface (MCP)
- Service discovery
- Independent deployment
- Protocol compliance

### 5. Think-Act-Observe Pattern

**Purpose:** Agent reasoning loop

**Implementation:**
```
Loop until task complete:
    Think:  Analyze current state, plan next action
    Act:    Execute tool call
    Observe: Process results, update context
```

**Benefits:**
- Autonomous agent behavior
- Adaptive reasoning
- Error recovery
- Goal-oriented execution

---

## Execution Model

### Synchronous Execution

Currently, the system uses synchronous execution:

```
Main Agent
    ├─> Delegates to Search Agent (waits)
    │   └─> Returns result
    ├─> Delegates to PDF Agent (waits)
    │   └─> Returns result
    └─> Synthesizes and returns
```

**Characteristics:**
- Sequential task execution
- Blocking calls
- Simple error handling
- Predictable execution order

### Asynchronous Execution (Future)

For improved performance:

```
Main Agent
    ├─> Delegates to Search Agent 1 (non-blocking)
    ├─> Delegates to Search Agent 2 (non-blocking)
    └─> Waits for all results
        └─> Synthesizes and returns
```

**Benefits:**
- Parallel task execution
- Reduced latency
- Better resource utilization
- Improved throughput

### Agent Lifecycle

```
1. Creation
   ├─> Generate unique ID
   ├─> Initialize LLM connection
   ├─> Load system prompt
   ├─> Connect MCP tools
   └─> Register in registry

2. Execution
   ├─> Receive task
   ├─> Execute reasoning loop
   ├─> Call tools as needed
   └─> Return results

3. Reuse (Optional)
   ├─> Retrieve from registry
   ├─> Maintain existing state
   ├─> Execute new task
   └─> Return results

4. Cleanup (Implicit)
   └─> Garbage collected when no longer referenced
```

### Memory Management

Each agent has isolated memory:

```
Agent 1 Memory:
├─> Task history
├─> Tool call history
├─> Results cache
└─> Context window

Agent 2 Memory:
├─> Task history (separate)
├─> Tool call history (separate)
├─> Results cache (separate)
└─> Context window (separate)
```

**Benefits:**
- No cross-agent contamination
- Independent context management
- Parallel-safe execution
- Clear ownership

---

## Configuration Management

### Environment-Based Configuration

```
Environment Variables
    │
    ├─> Main Agent Config
    │   ├─> LLM_PROVIDER
    │   ├─> LLM_MODEL_NAME
    │   ├─> LLM_API_KEY
    │   └─> AWORLD_WORKSPACE
    │
    └─> Sub-Agent Config (inherited)
        ├─> LLM_PROVIDER
        ├─> LLM_MODEL_NAME
        ├─> LLM_API_KEY
        ├─> AWORLD_WORKSPACE
        └─> Service-specific keys
            ├─> GOOGLE_API_KEY
            └─> GOOGLE_CSE_ID
```

### MCP Configuration Hierarchy

```
Project Level (mcp.json)
├─> Defines available sub-agent services
└─> {
      "mcpServers": {
        "search_agent": {...},
        "pdf_agent": {...}
      }
    }

Service Level (search_agent/mcp.json)
├─> Defines available tools for that service
└─> {
      "mcpServers": {
        "search": {...},
        "download": {...}
      }
    }
```

---

## Error Handling

### Multi-Level Error Handling

```
Layer 1: Main Agent
├─> Try-catch around sub-agent calls
├─> Handle ActionResponse.success = false
└─> Provide fallback or retry logic

Layer 2: Sub-Agent Service
├─> Try-catch around agent creation/execution
├─> Return structured error in ActionResponse
└─> Log detailed error information

Layer 3: Agent Execution
├─> Handle tool call failures
├─> Retry with different parameters
└─> Return error status to service

Layer 4: MCP Tools
├─> Validate inputs
├─> Handle API errors
└─> Return structured error responses
```

### Error Flow Example

```
Main Agent calls search_agent
    │
    └─> search_agent.mcp_create_search_agent(...)
        │
        ├─> Error: Google API quota exceeded
        │
        └─> Return: ActionResponse(
                success=false,
                message="Google API quota exceeded",
                metadata={"error_type": "quota_exceeded"}
            )
    │
    └─> Main Agent receives error response
        │
        ├─> Decision: Try alternative approach
        │
        └─> Continue with available information
            or report error to user
```

---

## Scalability Considerations

### Horizontal Scaling

Each sub-agent service can be:
- Deployed independently
- Scaled based on demand
- Load balanced across instances
- Monitored separately

### Vertical Scaling

Adjust per-agent resources:
- Use different LLM models (smaller/larger)
- Adjust context window size
- Modify max_steps limits
- Control concurrency

### Performance Optimization

1. **Agent Reuse:**
   - Reuse agents for related tasks
   - Maintain context across calls
   - Reduce initialization overhead

2. **Caching:**
   - Cache search results
   - Cache extracted PDF content
   - Cache LLM responses

3. **Parallel Execution:**
   - Execute independent subtasks in parallel
   - Use async/await patterns
   - Implement result streaming

4. **Resource Management:**
   - Connection pooling for MCP tools
   - Lazy initialization of agents
   - Cleanup unused agents

---

## Security Considerations

### 1. API Key Management
- Environment variable based
- No hardcoded credentials
- Per-service isolation

### 2. File System Access
- Workspace sandboxing
- Path validation
- Permission checks

### 3. Network Access
- URL validation
- Download size limits
- Timeout enforcement

### 4. Agent Isolation
- Memory isolation
- Separate LLM instances
- Independent configurations

---

## Future Enhancements

### 1. Parallel Agent Execution
- Execute independent subtasks concurrently
- Async/await implementation
- Result aggregation

### 2. Agent Collaboration
- Agents communicate directly
- Shared context between related agents
- Collaborative problem solving

### 3. Dynamic Agent Discovery
- Registry service for agent capabilities
- Runtime agent loading
- Plugin architecture

### 4. Monitoring and Observability
- Agent performance metrics
- Task execution traces
- Cost tracking per agent

### 5. Advanced Orchestration
- Conditional execution flows
- Loop and iteration support
- Error recovery strategies

---

## Summary

The multi-agent orchestration architecture provides:

✅ **Modularity:** Clear separation between main agent and sub-agents  
✅ **Scalability:** Independent scaling of services  
✅ **Maintainability:** Focused, single-responsibility components  
✅ **Extensibility:** Easy to add new agent types  
✅ **Reusability:** Agents can be reused across tasks  
✅ **Isolation:** Independent memory and context per agent  

This architecture enables building complex AI workflows by composing specialized agents, each optimized for specific tasks, while maintaining clean abstractions and clear responsibilities.

