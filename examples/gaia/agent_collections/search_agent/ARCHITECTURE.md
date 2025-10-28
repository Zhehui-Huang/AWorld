# Search Agent MCP Server - Architecture Documentation

## Overview

The Search Agent MCP Server implements a **dynamic multi-layer agent architecture** that enables modular, scalable, and maintainable AI agent systems. This document details the architecture, design patterns, and implementation strategies.

## Table of Contents

1. [Architecture Layers](#architecture-layers)
2. [Component Design](#component-design)
3. [Data Flow](#data-flow)
4. [Design Patterns](#design-patterns)
5. [Integration Points](#integration-points)
6. [Scalability Considerations](#scalability-considerations)

---

## Architecture Layers

### Layer 0: MCP Protocol Layer

**Purpose:** Provides standardized communication between agents and tools.

**Components:**
- `ActionCollection`: Base class for MCP server implementations
- `ActionArguments`: Configuration for MCP servers
- `ActionResponse`: Standardized response format

**Responsibilities:**
- Protocol compliance
- Message serialization/deserialization
- Transport management (stdio, SSE)

### Layer 1: Search Agent Service Layer

**Purpose:** Manages search agent lifecycle and orchestration.

**Components:**
- `SearchAgentCollection`: Main MCP server implementation
- `AgentRegistry`: Manages agent instances
- `SearchAgentMetadata`: Agent metadata storage

**Responsibilities:**
- Agent creation and registration
- Agent retrieval and reuse
- Service capabilities reporting
- Configuration management

### Layer 2: Agent Execution Layer

**Purpose:** Executes agent reasoning and tool usage.

**Components:**
- `Agent`: Core agent implementation from AWorld framework
- `Task`: Task definition and configuration
- `Runners`: Task execution orchestration

**Responsibilities:**
- LLM interaction
- Memory management
- Tool calling (think-act-observe loop)
- Result aggregation

### Layer 3: MCP Tools Layer

**Purpose:** Provides specialized capabilities to agents.

**Components:**
- `SearchCollection`: Google Custom Search integration
- `DownloadCollection`: File download capabilities

**Responsibilities:**
- External API integration
- Data retrieval and formatting
- Error handling and validation

---

## Component Design

### SearchAgentCollection

```python
class SearchAgentCollection(ActionCollection):
    """
    Main MCP server for search agent management.
    
    Attributes:
        agent_registry: Registry of created agents
        mcp_config: Configuration for agent MCP tools
    
    Methods:
        mcp_create_search_agent: Create and execute new agent
        mcp_use_existing_search_agent: Reuse existing agent
        mcp_get_search_agent_capabilities: Get service info
    """
```

**Design Decisions:**
- **Singleton Registry:** Each service instance maintains its own registry
- **Lazy Loading:** MCP config loaded on initialization
- **Environment Fallback:** Uses env vars for missing config

### AgentRegistry

```python
class AgentRegistry:
    """
    In-memory registry for agent instances.
    
    Attributes:
        _agents: Dict[agent_id -> Agent]
        _metadata: Dict[agent_id -> SearchAgentMetadata]
    
    Methods:
        register: Add new agent
        get_agent: Retrieve agent by ID
        get_metadata: Get agent metadata
        list_agents: List all agents
        exists: Check agent existence
    """
```

**Design Decisions:**
- **In-Memory Storage:** Fast access, suitable for single-process
- **Dual Storage:** Separate agent instances and metadata
- **Simple Interface:** CRUD operations only

**Future Enhancements:**
- Persistent storage (Redis, PostgreSQL)
- Distributed registry (across processes)
- TTL and cleanup policies

### SearchAgentMetadata

```python
class SearchAgentMetadata(BaseModel):
    """
    Immutable metadata for search agents.
    
    Fields:
        agent_id: Unique identifier
        name: Human-readable name
        description: Agent purpose
        created_at: Creation timestamp
        llm_provider: LLM service provider
        llm_model_name: Model identifier
        mcp_servers: Available tools
    """
```

**Design Decisions:**
- **Pydantic Model:** Type safety and validation
- **Immutable:** Metadata doesn't change after creation
- **Comprehensive:** All info needed for agent management

---

## Data Flow

### 1. Agent Creation Flow

```
User/Main Agent
    │
    ├─> Call: mcp_create_search_agent(task_prompt="...")
    │
    ├─> SearchAgentCollection
    │   │
    │   ├─> Generate unique agent_id
    │   │
    │   ├─> Load MCP config (search, download tools)
    │   │
    │   ├─> Create AgentConfig (LLM settings)
    │   │
    │   ├─> Initialize Agent instance
    │   │   │
    │   │   ├─> Agent gets LLM client
    │   │   ├─> Agent gets Memory module
    │   │   └─> Agent loads MCP tools
    │   │
    │   ├─> Create SearchAgentMetadata
    │   │
    │   ├─> Register in AgentRegistry
    │   │
    │   ├─> Create Task with agent and task_prompt
    │   │
    │   └─> Execute: Runners.sync_run_task(task)
    │       │
    │       ├─> Agent reasoning loop
    │       │   │
    │       │   ├─> Think: Analyze task
    │       │   ├─> Act: Call MCP tools
    │       │   │   ├─> search.mcp_search_google(...)
    │       │   │   └─> download.mcp_download_file(...)
    │       │   ├─> Observe: Process results
    │       │   └─> Repeat or Finish
    │       │
    │       └─> Return TaskResponse with answer
    │
    └─> Return ActionResponse with results and metadata
```

### 2. Agent Reuse Flow

```
User/Main Agent
    │
    ├─> Call: mcp_use_existing_search_agent(agent_id="...", task_prompt="...")
    │
    ├─> SearchAgentCollection
    │   │
    │   ├─> Check: agent_registry.exists(agent_id)
    │   │
    │   ├─> Retrieve: agent = agent_registry.get_agent(agent_id)
    │   │
    │   ├─> Create new Task with existing agent
    │   │
    │   └─> Execute: Runners.sync_run_task(task)
    │       │
    │       └─> Agent reuses existing:
    │           - LLM configuration
    │           - Memory (previous context)
    │           - MCP tool connections
    │
    └─> Return ActionResponse with results
```

### 3. Multi-Layer Delegation Flow

```
Main Agent
    │
    ├─> Receives complex task: "Research and summarize AI papers"
    │
    ├─> Decision: This requires search capability
    │
    ├─> Delegates to Search Agent Server
    │   │
    │   ├─> mcp_create_search_agent(
    │   │       task_prompt="Find AI papers from 2022"
    │   │   )
    │   │
    │   ├─> Search Agent autonomously:
    │   │   ├─> Plans search strategy
    │   │   ├─> Executes searches
    │   │   ├─> Downloads relevant papers
    │   │   └─> Returns structured results
    │   │
    │   └─> Returns: List of papers with URLs and summaries
    │
    ├─> Main Agent processes results
    │
    ├─> Main Agent may delegate to Analysis Agent
    │   └─> (Similar pattern for analysis tasks)
    │
    └─> Main Agent returns final answer to user
```

---

## Design Patterns

### 1. **Registry Pattern**

**Purpose:** Manage multiple agent instances with unique identifiers.

**Implementation:**
```python
class AgentRegistry:
    def __init__(self):
        self._agents = {}
        self._metadata = {}
    
    def register(self, agent, metadata):
        self._agents[metadata.agent_id] = agent
        self._metadata[metadata.agent_id] = metadata
```

**Benefits:**
- Centralized agent management
- Easy lookup by ID
- Prevents duplicate agents

### 2. **Factory Pattern**

**Purpose:** Create agent instances with consistent configuration.

**Implementation:**
```python
def _create_agent_instance(self, name, description, llm_provider, ...):
    agent_id = f"search_agent_{uuid.uuid4().hex[:8]}"
    
    agent_config = AgentConfig(
        llm_provider=llm_provider,
        llm_model_name=llm_model_name,
        ...
    )
    
    agent = Agent(conf=agent_config, name=name, ...)
    metadata = SearchAgentMetadata(agent_id=agent_id, ...)
    
    self.agent_registry.register(agent, metadata)
    return agent, metadata
```

**Benefits:**
- Consistent agent creation
- Encapsulated configuration logic
- Easy to extend with new agent types

### 3. **Strategy Pattern**

**Purpose:** Different execution strategies for agents.

**Implementation:**
- Create new agent: `mcp_create_search_agent`
- Reuse existing agent: `mcp_use_existing_search_agent`

**Benefits:**
- Flexible execution models
- Easy to add new strategies
- Clear separation of concerns

### 4. **Delegation Pattern**

**Purpose:** Delegate specialized tasks to sub-agents.

**Implementation:**
```python
# Main agent delegates to search agent
main_agent -> search_agent.mcp_create_search_agent(task_prompt)

# Search agent uses its tools
search_agent -> mcp_search_google(query)
search_agent -> mcp_download_file(url)
```

**Benefits:**
- Modular task decomposition
- Specialized agent responsibilities
- Hierarchical problem solving

---

## Integration Points

### 1. **AWorld Framework Integration**

**Components Used:**
- `Agent`: Core agent class
- `AgentConfig`: Agent configuration
- `Task` / `TaskConfig`: Task definition
- `Runners`: Task execution
- `MemoryFactory`: Memory management

**Integration Pattern:**
```python
from aworld.agents.llm_agent import Agent
from aworld.config.conf import AgentConfig, TaskConfig
from aworld.core.task import Task
from aworld.runner import Runners

agent = Agent(conf=agent_config, ...)
task = Task(input=task_prompt, agent=agent, conf=task_config)
result = Runners.sync_run_task(task=task)
```

### 2. **MCP Protocol Integration**

**Base Classes:**
- `ActionCollection`: MCP server base
- `ActionArguments`: Configuration
- `ActionResponse`: Response format

**Integration Pattern:**
```python
from examples.gaia.mcp_collections.base import (
    ActionCollection, ActionArguments, ActionResponse
)

class SearchAgentCollection(ActionCollection):
    def __init__(self, arguments: ActionArguments):
        super().__init__(arguments)
    
    def mcp_method(self, ...) -> ActionResponse:
        return ActionResponse(success=True, message="...", metadata={})
```

### 3. **Environment Configuration**

**Environment Variables:**
- `LLM_PROVIDER`, `LLM_MODEL_NAME`, `LLM_API_KEY`, `LLM_BASE_URL`
- `GOOGLE_API_KEY`, `GOOGLE_CSE_ID`
- `AWORLD_WORKSPACE`

**Configuration Loading:**
```python
llm_provider = llm_provider or os.getenv("LLM_PROVIDER", "openai")
```

---

## Scalability Considerations

### Current Implementation

**Strengths:**
- ✅ In-memory registry for fast access
- ✅ Synchronous execution for simplicity
- ✅ Single-process architecture

**Limitations:**
- ⚠️ No persistence (agents lost on restart)
- ⚠️ No distributed support
- ⚠️ Limited concurrent execution

### Future Scalability Enhancements

#### 1. **Persistent Agent Storage**

```python
class PersistentAgentRegistry:
    def __init__(self, db_url):
        self.db = Database(db_url)  # PostgreSQL, Redis, etc.
    
    def register(self, agent, metadata):
        # Serialize agent state
        agent_state = agent.to_dict()
        self.db.save(metadata.agent_id, agent_state, metadata)
    
    def get_agent(self, agent_id):
        # Deserialize and reconstruct agent
        agent_state, metadata = self.db.load(agent_id)
        return Agent.from_dict(agent_state)
```

#### 2. **Distributed Agent Registry**

```python
class DistributedAgentRegistry:
    def __init__(self, redis_url):
        self.redis = Redis(redis_url)
    
    def register(self, agent, metadata):
        # Store in Redis for cross-process access
        key = f"agent:{metadata.agent_id}"
        self.redis.set(key, pickle.dumps((agent, metadata)))
    
    def get_agent(self, agent_id):
        key = f"agent:{agent_id}"
        return pickle.loads(self.redis.get(key))
```

#### 3. **Async Execution**

```python
async def mcp_create_search_agent_async(self, task_prompt, ...):
    """Async version for concurrent agent execution."""
    agent, metadata = self._create_agent_instance(...)
    
    task = Task(...)
    result_map = await Runners.run_task(task=task)
    
    return ActionResponse(...)
```

#### 4. **Agent Pool Management**

```python
class AgentPool:
    def __init__(self, max_agents=10):
        self.max_agents = max_agents
        self.active_agents = 0
    
    async def acquire_agent(self):
        """Get available agent or wait."""
        while self.active_agents >= self.max_agents:
            await asyncio.sleep(0.1)
        self.active_agents += 1
        return self._create_agent()
    
    def release_agent(self, agent):
        """Return agent to pool."""
        self.active_agents -= 1
```

#### 5. **Load Balancing**

```python
class LoadBalancedAgentService:
    def __init__(self, instances):
        self.instances = instances  # Multiple service instances
    
    def get_instance(self):
        """Select least-loaded instance."""
        return min(self.instances, key=lambda x: x.active_tasks)
```

---

## Best Practices

### 1. **Agent Creation**

✅ **DO:**
- Generate unique agent IDs
- Set descriptive names and descriptions
- Use appropriate LLM settings for the task
- Register agents immediately after creation

❌ **DON'T:**
- Reuse agent IDs
- Create agents without purpose
- Ignore configuration errors
- Forget to clean up unused agents

### 2. **Task Delegation**

✅ **DO:**
- Delegate clearly defined subtasks
- Provide sufficient context in task_prompt
- Set appropriate max_steps
- Handle agent responses properly

❌ **DON'T:**
- Delegate vague or complex tasks
- Assume agents will always succeed
- Ignore error responses
- Create unnecessary agent hierarchies

### 3. **Error Handling**

✅ **DO:**
- Catch and log all exceptions
- Return informative error messages
- Include error details in metadata
- Provide recovery suggestions

❌ **DON'T:**
- Silently fail
- Return generic error messages
- Expose sensitive information
- Leave agents in invalid states

### 4. **Resource Management**

✅ **DO:**
- Monitor agent count
- Clean up completed agents
- Set reasonable timeouts
- Track resource usage

❌ **DON'T:**
- Create unlimited agents
- Keep all agents indefinitely
- Ignore memory leaks
- Exceed API quotas

---

## Testing Strategy

### Unit Tests

```python
def test_agent_registry():
    registry = AgentRegistry()
    agent, metadata = create_test_agent()
    
    registry.register(agent, metadata)
    assert registry.exists(metadata.agent_id)
    assert registry.get_agent(metadata.agent_id) == agent

def test_agent_creation():
    service = SearchAgentCollection(test_args)
    result = service.mcp_create_search_agent(task_prompt="test")
    
    assert result.success
    assert "agent_id" in result.metadata
```

### Integration Tests

```python
def test_end_to_end_search():
    # Create main agent
    main_agent = create_main_agent()
    
    # Delegate to search agent
    result = main_agent.call_mcp_tool(
        "search_agent.mcp_create_search_agent",
        task_prompt="Find AI papers"
    )
    
    assert result.success
    assert result.metadata["answer"] is not None
```

### Performance Tests

```python
def test_concurrent_agents():
    service = SearchAgentCollection(test_args)
    
    # Create multiple agents concurrently
    tasks = [
        service.mcp_create_search_agent(task_prompt=f"Task {i}")
        for i in range(10)
    ]
    
    results = asyncio.gather(*tasks)
    assert all(r.success for r in results)
```

---

## Conclusion

The Search Agent MCP Server architecture provides a foundation for building sophisticated multi-layer agent systems. Key design principles include:

- **Modularity**: Clear separation of concerns
- **Scalability**: Extensible design patterns
- **Maintainability**: Clean code structure
- **Flexibility**: Configurable components

Future enhancements will focus on persistence, distribution, and advanced orchestration patterns to support production-scale deployments.

