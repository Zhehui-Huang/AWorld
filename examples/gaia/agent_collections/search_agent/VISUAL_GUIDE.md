# Search Agent MCP Server - Visual Guide

Visual representations to help understand the architecture and workflows.

---

## Table of Contents

1. [System Architecture](#system-architecture)
2. [Agent Lifecycle](#agent-lifecycle)
3. [Data Flow](#data-flow)
4. [Multi-Layer Delegation](#multi-layer-delegation)
5. [Component Relationships](#component-relationships)

---

## System Architecture

### High-Level Overview

```
┌─────────────────────────────────────────────────────────────────────┐
│                          User / Main Agent                          │
└───────────────────────────────┬─────────────────────────────────────┘
                                │
                                │ MCP Protocol
                                │
┌───────────────────────────────▼─────────────────────────────────────┐
│                    Search Agent MCP Server                          │
│                                                                     │
│  ┌────────────────────────────────────────────────────────────┐   │
│  │          SearchAgentCollection                             │   │
│  │                                                            │   │
│  │  • mcp_create_search_agent()                              │   │
│  │  • mcp_use_existing_search_agent()                        │   │
│  │  • mcp_get_search_agent_capabilities()                    │   │
│  └────────────────────┬───────────────────────────────────────┘   │
│                       │                                            │
│  ┌────────────────────▼───────────────────────────────────────┐   │
│  │            AgentRegistry                                   │   │
│  │                                                            │   │
│  │  Agents:    {agent_id -> Agent}                           │   │
│  │  Metadata:  {agent_id -> SearchAgentMetadata}             │   │
│  └────────────────────┬───────────────────────────────────────┘   │
│                       │                                            │
└───────────────────────┼────────────────────────────────────────────┘
                        │
        ┌───────────────┴───────────────┐
        │                               │
        ▼                               ▼
┌───────────────┐           ┌───────────────────┐
│ Agent Instance│           │ Agent Instance    │
│ (ID: abc123)  │           │ (ID: def456)      │
├───────────────┤           ├───────────────────┤
│ • LLM Config  │           │ • LLM Config      │
│ • Memory      │           │ • Memory          │
│ • MCP Tools   │           │ • MCP Tools       │
│   - search    │           │   - search        │
│   - download  │           │   - download      │
└───────────────┘           └───────────────────┘
```

---

## Agent Lifecycle

### Creation Flow

```
START
  │
  ▼
┌────────────────────────────────────────┐
│ User calls mcp_create_search_agent     │
│ with task_prompt and configuration     │
└──────────────┬─────────────────────────┘
               │
               ▼
┌────────────────────────────────────────┐
│ SearchAgentCollection receives request │
└──────────────┬─────────────────────────┘
               │
               ▼
┌────────────────────────────────────────┐
│ Generate unique agent_id               │
│ (e.g., "search_agent_abc12345")        │
└──────────────┬─────────────────────────┘
               │
               ▼
┌────────────────────────────────────────┐
│ Load MCP Configuration                 │
│ - search tool                          │
│ - download tool                        │
└──────────────┬─────────────────────────┘
               │
               ▼
┌────────────────────────────────────────┐
│ Create AgentConfig                     │
│ - LLM provider                         │
│ - Model name                           │
│ - API credentials                      │
│ - Temperature                          │
└──────────────┬─────────────────────────┘
               │
               ▼
┌────────────────────────────────────────┐
│ Initialize Agent from AWorld           │
│ - Assign config                        │
│ - Initialize memory                    │
│ - Load MCP tools                       │
│ - Set system prompt                    │
└──────────────┬─────────────────────────┘
               │
               ▼
┌────────────────────────────────────────┐
│ Create SearchAgentMetadata             │
│ - Store agent_id, name, description    │
│ - Record creation timestamp            │
│ - Save configuration details           │
└──────────────┬─────────────────────────┘
               │
               ▼
┌────────────────────────────────────────┐
│ Register in AgentRegistry              │
│ - Store Agent instance                 │
│ - Store metadata                       │
└──────────────┬─────────────────────────┘
               │
               ▼
┌────────────────────────────────────────┐
│ Create Task                            │
│ - Assign agent                         │
│ - Set task_prompt as input             │
│ - Configure max_steps                  │
└──────────────┬─────────────────────────┘
               │
               ▼
┌────────────────────────────────────────┐
│ Execute with Runners.sync_run_task()   │
│ → See "Task Execution Flow" below      │
└──────────────┬─────────────────────────┘
               │
               ▼
┌────────────────────────────────────────┐
│ Collect results                        │
│ - Answer from agent                    │
│ - Execution metadata                   │
└──────────────┬─────────────────────────┘
               │
               ▼
┌────────────────────────────────────────┐
│ Return ActionResponse                  │
│ - success: true/false                  │
│ - message: formatted results           │
│ - metadata: agent info + answer        │
└──────────────┬─────────────────────────┘
               │
               ▼
             END
```

### Task Execution Flow (Think-Act-Observe Loop)

```
Agent Receives Task
       │
       ▼
┌─────────────────────┐
│   THINK Phase       │
│                     │
│ • Analyze task      │
│ • Plan approach     │
│ • Identify tools    │
└──────┬──────────────┘
       │
       ▼
┌─────────────────────┐
│   ACT Phase         │
│                     │
│ • Select tool       │
│ • Prepare args      │
│ • Execute call      │
│                     │
│   Examples:         │
│   • search_google() │
│   • download_file() │
└──────┬──────────────┘
       │
       ▼
┌─────────────────────┐
│   OBSERVE Phase     │
│                     │
│ • Process results   │
│ • Update memory     │
│ • Evaluate progress │
└──────┬──────────────┘
       │
       ▼
    Decision
       │
   ┌───┴───┐
   │       │
   ▼       ▼
 More    Done
 Steps     │
   │       │
   └───┬───┘
       │
       ▼
   Return Answer
```

---

## Data Flow

### Request/Response Flow

```
┌─────────────┐
│ Main Agent  │
└──────┬──────┘
       │
       │ (1) Request: Create search agent
       │     {task_prompt, name, config}
       │
       ▼
┌──────────────────────┐
│ SearchAgent Server   │
│                      │
│  (2) Create Agent    │
│  (3) Register Agent  │
│  (4) Execute Task    │
└──────┬───────────────┘
       │
       │ (5) Agent calls MCP tools
       │
       ▼
┌──────────────────────┐
│ MCP Tools            │
│                      │
│  • search            │◄──┐
│  • download          │   │
└──────┬───────────────┘   │
       │                   │
       │ (6) Tool results  │
       └───────────────────┘
       │
       ▼
┌──────────────────────┐
│ SearchAgent Server   │
│                      │
│  (7) Format response │
│  (8) Add metadata    │
└──────┬───────────────┘
       │
       │ (9) Response: {success, answer, metadata}
       │
       ▼
┌─────────────┐
│ Main Agent  │
└─────────────┘
```

### Data Structures

```
ActionResponse
├── success: bool
├── message: str (formatted for humans)
└── metadata: dict
    ├── agent_id: str
    ├── agent_name: str
    ├── description: str
    ├── answer: Any (actual result)
    ├── task_prompt: str
    ├── created_at: str
    ├── llm_provider: str
    ├── llm_model_name: str
    └── mcp_servers: list[str]
```

---

## Multi-Layer Delegation

### Traditional Flat Architecture

```
┌─────────────────────────────────────┐
│           Main Agent                │
│                                     │
│  Decision: Which tool to use?       │
│  • search_google                    │
│  • download_file                    │
│  • calculate                        │
│  • translate                        │
│  • summarize                        │
│  • ... (50+ tools)                  │
│                                     │
│  Problem: Too many choices!         │
└─────────────────────────────────────┘
```

### New Multi-Layer Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                        Main Agent                           │
│                                                             │
│  Decision: What type of task?                              │
│  • Search task → delegate to Search Agent                  │
│  • Analysis task → delegate to Analysis Agent              │
│  • Translation task → delegate to Translation Agent        │
│                                                             │
└─────────────┬───────────────────────────────────────────────┘
              │
              │ Delegate
              │
┌─────────────▼───────────────────────────────────────────────┐
│                    Search Agent Server                      │
│                                                             │
│  Decision: How to search?                                  │
│  • Use search_google for web search                        │
│  • Use download_file for documents                         │
│                                                             │
│  ┌─────────────────────────────────────────────────────┐   │
│  │ Search Agent Instance                               │   │
│  │                                                     │   │
│  │  Autonomous execution:                             │   │
│  │  1. Plan search strategy                           │   │
│  │  2. Execute searches                               │   │
│  │  3. Filter results                                 │   │
│  │  4. Download relevant docs                         │   │
│  │  5. Return structured data                         │   │
│  └─────────────────────────────────────────────────────┘   │
│                                                             │
└─────────────┬───────────────────────────────────────────────┘
              │
              │ Results
              │
┌─────────────▼───────────────────────────────────────────────┐
│                        Main Agent                           │
│                                                             │
│  Process results and continue...                           │
└─────────────────────────────────────────────────────────────┘
```

### Recursive Hierarchy Example

```
Level 0: Main Agent
   │
   ├── Task: "Comprehensive AI safety research"
   │
   └─> Creates: Research Coordinator (Sub-Main Agent)
           │
           ├── Subtask 1: "Find papers"
           │   └─> Creates: Search Agent
           │       └─> Uses: search, download tools
           │
           ├── Subtask 2: "Analyze papers"
           │   └─> Creates: Analysis Agent
           │       └─> Uses: summarize, extract tools
           │
           └── Subtask 3: "Visualize findings"
               └─> Creates: Visualization Agent
                   └─> Uses: chart, graph tools

Results flow back up:
Visualization Agent → Analysis Agent → Research Coordinator → Main Agent → User
```

---

## Component Relationships

### Class Diagram

```
┌─────────────────────────┐
│   ActionCollection      │
│   (Base Class)          │
└──────────┬──────────────┘
           │ inherits
           │
┌──────────▼──────────────┐
│ SearchAgentCollection   │
├─────────────────────────┤
│ + agent_registry        │───┐
│ + mcp_config            │   │
├─────────────────────────┤   │
│ + mcp_create_search..() │   │ has-a
│ + mcp_use_existing..()  │   │
│ + mcp_get_capabilities()│   │
└─────────────────────────┘   │
                              │
          ┌───────────────────┘
          │
          ▼
┌─────────────────────────┐
│   AgentRegistry         │
├─────────────────────────┤
│ - _agents: Dict         │───┐
│ - _metadata: Dict       │   │
├─────────────────────────┤   │
│ + register()            │   │ stores
│ + get_agent()           │   │
│ + get_metadata()        │   │
│ + list_agents()         │   │
│ + exists()              │   │
└─────────────────────────┘   │
                              │
          ┌───────────────────┴───────────────────┐
          │                                       │
          ▼                                       ▼
┌─────────────────────────┐         ┌─────────────────────────┐
│   Agent                 │         │ SearchAgentMetadata     │
│   (from AWorld)         │         ├─────────────────────────┤
├─────────────────────────┤         │ + agent_id              │
│ + conf: AgentConfig     │         │ + name                  │
│ + memory: Memory        │         │ + description           │
│ + tools: List[Tool]     │         │ + created_at            │
├─────────────────────────┤         │ + llm_provider          │
│ + async_policy()        │         │ + llm_model_name        │
│ + execute()             │         │ + mcp_servers           │
└─────────────────────────┘         └─────────────────────────┘
          │
          │ uses
          ▼
┌─────────────────────────┐
│   MCP Tools             │
├─────────────────────────┤
│ • search                │
│   - mcp_search_google() │
│                         │
│ • download              │
│   - mcp_download_file() │
└─────────────────────────┘
```

### Interaction Sequence

```
┌────────┐  ┌────────────┐  ┌─────────┐  ┌────────┐  ┌──────────┐
│  User  │  │Main Agent  │  │ Server  │  │Registry│  │  Agent   │
└───┬────┘  └─────┬──────┘  └────┬────┘  └───┬────┘  └────┬─────┘
    │             │               │           │            │
    │ Task        │               │           │            │
    ├────────────>│               │           │            │
    │             │               │           │            │
    │             │ create_agent  │           │            │
    │             ├──────────────>│           │            │
    │             │               │           │            │
    │             │               │ register  │            │
    │             │               ├──────────>│            │
    │             │               │           │            │
    │             │               │           │ new Agent  │
    │             │               │           ├───────────>│
    │             │               │           │            │
    │             │               │<──────────┤            │
    │             │               │  agent_id │            │
    │             │               │           │            │
    │             │               │ execute   │            │
    │             │               ├───────────┼───────────>│
    │             │               │           │            │
    │             │               │           │   [Agent reasoning loop]
    │             │               │           │   • Think
    │             │               │           │   • Act (call tools)
    │             │               │           │   • Observe
    │             │               │           │            │
    │             │               │<──────────┼────────────┤
    │             │               │  results  │            │
    │             │               │           │            │
    │             │<──────────────┤           │            │
    │             │  response     │           │            │
    │             │               │           │            │
    │<────────────┤               │           │            │
    │  answer     │               │           │            │
    │             │               │           │            │
```

---

## Configuration Hierarchy

```
┌─────────────────────────────────────────────────────────────┐
│                    Environment Variables                    │
│                                                             │
│  LLM_PROVIDER, LLM_MODEL_NAME, LLM_API_KEY,               │
│  GOOGLE_API_KEY, GOOGLE_CSE_ID, AWORLD_WORKSPACE          │
└──────────────────────┬──────────────────────────────────────┘
                       │
                       │ used by
                       │
┌──────────────────────▼──────────────────────────────────────┐
│              SearchAgentCollection                          │
│                                                             │
│  • Loads mcp.json (tool configuration)                     │
│  • Reads env vars for defaults                             │
└──────────────────────┬──────────────────────────────────────┘
                       │
                       │ creates
                       │
┌──────────────────────▼──────────────────────────────────────┐
│                   AgentConfig                               │
│                                                             │
│  • llm_provider (from env or param)                        │
│  • llm_model_name (from env or param)                      │
│  • llm_api_key (from env or param)                         │
│  • llm_temperature (from param)                            │
└──────────────────────┬──────────────────────────────────────┘
                       │
                       │ passed to
                       │
┌──────────────────────▼──────────────────────────────────────┐
│                      Agent                                  │
│                                                             │
│  • Uses AgentConfig for LLM                                │
│  • Uses mcp_config for tools                               │
│  • Uses system_prompt for behavior                         │
└─────────────────────────────────────────────────────────────┘
```

---

## Memory and State Management

```
┌─────────────────────────────────────────────────────────────┐
│                    Agent Instance                           │
│                                                             │
│  ┌───────────────────────────────────────────────────────┐ │
│  │  Memory Module (Persistent across tasks)             │ │
│  │                                                       │ │
│  │  • Conversation history                              │ │
│  │  • Tool call history                                 │ │
│  │  • Previous results                                  │ │
│  │  • Context from past tasks                          │ │
│  └───────────────────────────────────────────────────────┘ │
│                                                             │
│  ┌───────────────────────────────────────────────────────┐ │
│  │  Current Task State                                   │ │
│  │                                                       │ │
│  │  • Task input                                        │ │
│  │  • Current step                                      │ │
│  │  • Intermediate results                             │ │
│  │  • Tool call results                                │ │
│  └───────────────────────────────────────────────────────┘ │
│                                                             │
└─────────────────────────────────────────────────────────────┘

When reusing agent (mcp_use_existing_search_agent):
┌─────────────────────────────────────────────────────────────┐
│  Previous task memory IS preserved                          │
│  New task builds on previous context                        │
└─────────────────────────────────────────────────────────────┘
```

---

## Error Handling Flow

```
Any step in execution
       │
       │ Error occurs
       │
       ▼
┌─────────────────────┐
│ Exception caught    │
└──────┬──────────────┘
       │
       ▼
┌─────────────────────┐
│ Log error details   │
│ • Stack trace       │
│ • Error type        │
│ • Context           │
└──────┬──────────────┘
       │
       ▼
┌─────────────────────┐
│ Create error        │
│ ActionResponse      │
│                     │
│ • success: false    │
│ • message: error    │
│ • metadata: details │
└──────┬──────────────┘
       │
       ▼
┌─────────────────────┐
│ Return to caller    │
└─────────────────────┘
```

---

## Scaling Patterns

### Single Process (Current)

```
┌─────────────────────┐
│  Process            │
│                     │
│  ┌───────────────┐  │
│  │ Agent 1       │  │
│  ├───────────────┤  │
│  │ Agent 2       │  │
│  ├───────────────┤  │
│  │ Agent 3       │  │
│  └───────────────┘  │
│                     │
│  Registry: in-mem   │
└─────────────────────┘
```

### Multi-Process (Future)

```
┌─────────────┐  ┌─────────────┐  ┌─────────────┐
│  Process 1  │  │  Process 2  │  │  Process 3  │
│             │  │             │  │             │
│  Agent 1    │  │  Agent 4    │  │  Agent 7    │
│  Agent 2    │  │  Agent 5    │  │  Agent 8    │
│  Agent 3    │  │  Agent 6    │  │  Agent 9    │
└──────┬──────┘  └──────┬──────┘  └──────┬──────┘
       │                │                │
       └────────────────┼────────────────┘
                        │
                        ▼
           ┌────────────────────────┐
           │   Shared Registry      │
           │   (Redis / Database)   │
           └────────────────────────┘
```

---

## Summary Diagram

```
┌─────────────────────────────────────────────────────────────────────┐
│                      SEARCH AGENT MCP SERVER                        │
│                                                                     │
│  ┌───────────────────────────────────────────────────────────────┐ │
│  │                     PUBLIC API (MCP)                          │ │
│  │                                                               │ │
│  │  • mcp_create_search_agent()                                 │ │
│  │  • mcp_use_existing_search_agent()                           │ │
│  │  • mcp_get_search_agent_capabilities()                       │ │
│  └───────────────────────────────────────────────────────────────┘ │
│                                                                     │
│  ┌───────────────────────────────────────────────────────────────┐ │
│  │                   AGENT MANAGEMENT                            │ │
│  │                                                               │ │
│  │  Registry:    {agent_id → Agent}                             │ │
│  │  Metadata:    {agent_id → SearchAgentMetadata}               │ │
│  └───────────────────────────────────────────────────────────────┘ │
│                                                                     │
│  ┌───────────────────────────────────────────────────────────────┐ │
│  │                   AGENT INSTANCES                             │ │
│  │                                                               │ │
│  │  Each agent has:                                             │ │
│  │  • Unique ID                                                 │ │
│  │  • LLM configuration                                         │ │
│  │  • Memory module                                             │ │
│  │  • MCP tools (search, download)                              │ │
│  │  • Think-Act-Observe loop                                    │ │
│  └───────────────────────────────────────────────────────────────┘ │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
```

---

**This visual guide helps you understand:**
- ✅ System architecture and components
- ✅ Agent lifecycle from creation to execution
- ✅ Data flow through the system
- ✅ Multi-layer delegation patterns
- ✅ Component relationships
- ✅ Configuration hierarchy
- ✅ Error handling
- ✅ Scaling patterns

**Use this as a reference when:**
- 🏗️ Designing new features
- 🐛 Debugging issues
- 📚 Learning the system
- 💬 Explaining to others

