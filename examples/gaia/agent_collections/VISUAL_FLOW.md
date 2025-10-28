# Visual Flow Diagrams - Multi-Agent Orchestration

This document provides ASCII-based visual diagrams to help understand the multi-agent system.

## 1. System Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                            USER                                 │
│                                                                 │
│  Task: "Find arXiv paper, download, summarize in 1000 words"  │
└────────────────────────────┬────────────────────────────────────┘
                             │
                             │ Complex Task
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│                  MAIN ORCHESTRATOR AGENT                        │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │ • Task Analysis & Decomposition                          │  │
│  │ • Sub-Agent Selection                                    │  │
│  │ • Result Synthesis                                       │  │
│  │                                                           │  │
│  │ Available Tools:                                         │  │
│  │   - search_agent.mcp_create_search_agent()             │  │
│  │   - search_agent.mcp_use_existing_search_agent()       │  │
│  │   - pdf_agent.mcp_create_pdf_agent()                   │  │
│  │   - pdf_agent.mcp_use_existing_pdf_agent()             │  │
│  └──────────────────────────────────────────────────────────┘  │
└───────────┬────────────────────────────────┬────────────────────┘
            │                                │
            │ Delegate                       │ Delegate
            │ Search Tasks                   │ PDF Tasks
            ▼                                ▼
┌────────────────────────┐       ┌────────────────────────────┐
│  SEARCH AGENT SERVICE  │       │    PDF AGENT SERVICE       │
│  ┌──────────────────┐  │       │  ┌──────────────────────┐  │
│  │ Agent Registry   │  │       │  │ Agent Registry       │  │
│  │ ├─ agent_1      │  │       │  │ ├─ agent_1          │  │
│  │ ├─ agent_2      │  │       │  │ ├─ agent_2          │  │
│  │ └─ ...          │  │       │  │ └─ ...              │  │
│  └──────────────────┘  │       │  └──────────────────────┘  │
│                        │       │                            │
│  Each Agent Has:       │       │  Each Agent Has:           │
│  • Own LLM            │       │  • Own LLM                │
│  • Own Memory         │       │  • Own Memory             │
│  • MCP Tools:         │       │  • MCP Tools:             │
│    - search           │       │    - pdf extract          │
│    - download         │       │    - OCR support          │
└────────────────────────┘       └────────────────────────────┘
```

---

## 2. Task Flow: Sequential Steps

```
┌─────────────┐
│   START     │
│   USER      │
│   TASK      │
└──────┬──────┘
       │
       │ "Find paper, download, summarize"
       ▼
┌─────────────────────────────────────────┐
│  STEP 1: Main Agent Analyzes Task      │
│                                         │
│  Reasoning:                             │
│  "This needs:                          │
│   1. Web search + download             │
│   2. PDF extraction + summary"         │
└──────┬──────────────────────────────────┘
       │
       │ Decide: Use search_agent
       ▼
┌─────────────────────────────────────────┐
│  STEP 2: Delegate to Search Agent      │
│                                         │
│  Tool Call:                            │
│  search_agent.mcp_create_search_agent( │
│    task="Find and download paper..."   │
│  )                                      │
└──────┬──────────────────────────────────┘
       │
       │ Search Agent works autonomously
       ▼
┌─────────────────────────────────────────┐
│  STEP 3: Search Agent Executes         │
│                                         │
│  Actions:                              │
│  1. Think: "Need to search arXiv"     │
│  2. Act: search.mcp_search_google()    │
│  3. Observe: Found papers              │
│  4. Think: "Download first result"     │
│  5. Act: download.mcp_download_file()  │
│  6. Observe: Download complete         │
│  7. Return: file_path                  │
└──────┬──────────────────────────────────┘
       │
       │ Return: {file_path: "paper.pdf"}
       ▼
┌─────────────────────────────────────────┐
│  STEP 4: Main Agent Receives Result    │
│                                         │
│  Reasoning:                             │
│  "Got the PDF file. Now need to        │
│   extract and summarize."              │
└──────┬──────────────────────────────────┘
       │
       │ Decide: Use pdf_agent
       ▼
┌─────────────────────────────────────────┐
│  STEP 5: Delegate to PDF Agent         │
│                                         │
│  Tool Call:                            │
│  pdf_agent.mcp_create_pdf_agent(       │
│    task="Extract and summarize..."     │
│  )                                      │
└──────┬──────────────────────────────────┘
       │
       │ PDF Agent works autonomously
       ▼
┌─────────────────────────────────────────┐
│  STEP 6: PDF Agent Executes            │
│                                         │
│  Actions:                              │
│  1. Think: "Need to extract content"   │
│  2. Act: pdf.mcp_extract_content()     │
│  3. Observe: Content extracted         │
│  4. Think: "Create 1000-word summary"  │
│  5. Analyze: Read and process content  │
│  6. Return: summary                    │
└──────┬──────────────────────────────────┘
       │
       │ Return: {summary: "..."}
       ▼
┌─────────────────────────────────────────┐
│  STEP 7: Main Agent Synthesizes        │
│                                         │
│  Combines:                             │
│  • Paper details (from search agent)   │
│  • Summary (from PDF agent)            │
│  • Additional context                  │
└──────┬──────────────────────────────────┘
       │
       │ Final Answer
       ▼
┌─────────────┐
│   END       │
│   USER      │
│   RESULT    │
└─────────────┘
```

---

## 3. Agent Communication Flow

```
Main Agent                 Search Agent               PDF Agent
    │                          │                         │
    │                          │                         │
    ├── Create Agent ─────────>│                         │
    │   task_prompt            │                         │
    │                          │                         │
    │                     ┌────┴─────┐                  │
    │                     │ Reasoning │                  │
    │                     │   Loop    │                  │
    │                     └────┬─────┘                  │
    │                          │                         │
    │<── Return Results ───────┤                         │
    │   {file_path: "..."}     │                         │
    │                          │                         │
    │                          │                         │
    ├── Create Agent ─────────────────────────────────>│
    │   task_prompt                                      │
    │   file_path                                        │
    │                                                    │
    │                                              ┌─────┴──────┐
    │                                              │  Reasoning  │
    │                                              │    Loop     │
    │                                              └─────┬──────┘
    │                                                    │
    │<── Return Results ─────────────────────────────────┤
    │   {summary: "..."}                                 │
    │                                                    │
    ▼                                                    │
Synthesize                                              │
and Return                                              │
```

---

## 4. Agent Registry Pattern

```
┌─────────────────────────────────────────────────────────┐
│              SEARCH AGENT SERVICE                       │
│                                                         │
│  ┌───────────────────────────────────────────────────┐ │
│  │          Agent Registry                           │ │
│  │                                                   │ │
│  │  search_agent_abc123:                            │ │
│  │    ├─ name: "arxiv_search_agent"                │ │
│  │    ├─ created_at: "2024-01-15 10:30"            │ │
│  │    ├─ llm_provider: "openai"                    │ │
│  │    ├─ llm_model: "gpt-4o"                       │ │
│  │    └─ agent_instance: <Agent Object>            │ │
│  │                                                   │ │
│  │  search_agent_def456:                            │ │
│  │    ├─ name: "paper_finder"                      │ │
│  │    ├─ created_at: "2024-01-15 10:35"            │ │
│  │    └─ agent_instance: <Agent Object>            │ │
│  │                                                   │ │
│  └───────────────────────────────────────────────────┘ │
│                                                         │
│  Operations:                                            │
│  • create_agent() → Returns agent_id                   │
│  • get_agent(agent_id) → Returns agent instance       │
│  • list_agents() → Returns all agent metadata         │
│  • exists(agent_id) → Check if agent exists           │
└─────────────────────────────────────────────────────────┘

Usage:
1. Create: agent_id = create_agent(...)
2. Reuse:  result = use_existing_agent(agent_id, new_task)
```

---

## 5. Think-Act-Observe Loop

```
┌────────────────────────────────────────────────────────┐
│              AGENT REASONING LOOP                      │
│                                                        │
│  ┌─────────────────────────────────────────────────┐  │
│  │                                                 │  │
│  │  ┌──────────┐                                  │  │
│  │  │  THINK   │  "What do I need to do next?"   │  │
│  │  │          │  "Which tool should I use?"      │  │
│  │  └────┬─────┘  "What parameters are needed?"   │  │
│  │       │                                         │  │
│  │       ▼                                         │  │
│  │  ┌──────────┐                                  │  │
│  │  │   ACT    │  Execute tool call               │  │
│  │  │          │  (search, download, extract)     │  │
│  │  └────┬─────┘                                  │  │
│  │       │                                         │  │
│  │       ▼                                         │  │
│  │  ┌──────────┐                                  │  │
│  │  │ OBSERVE  │  Process tool results            │  │
│  │  │          │  Update context                  │  │
│  │  └────┬─────┘  Check if task complete          │  │
│  │       │                                         │  │
│  │       │ Task Not Complete                      │  │
│  │       └──────────────┐                         │  │
│  │                      │                         │  │
│  └──────────────────────┘                         │  │
│                                                    │  │
│         Task Complete                              │  │
│              │                                     │  │
│              ▼                                     │  │
│         Return Result                              │  │
└────────────────────────────────────────────────────────┘

Example:
  Think: "Need to search for papers"
  Act:   search.mcp_search_google(query="...")
  Observe: "Found 5 results"
  
  Think: "First result looks good, need to download"
  Act:   download.mcp_download_file(url="...")
  Observe: "Download successful"
  
  Think: "Task complete"
  Return: "Paper downloaded to: path/to/file.pdf"
```

---

## 6. Multi-Agent Comparison

### Traditional Approach (Flat)
```
┌─────────────────────────────────────────┐
│          SINGLE AGENT                   │
│                                         │
│  Must reason about:                     │
│  ├─ Tool 1                             │
│  ├─ Tool 2                             │
│  ├─ Tool 3                             │
│  ├─ ...                                 │
│  └─ Tool 20                            │
│                                         │
│  Problems:                              │
│  • High cognitive load                  │
│  • Complex reasoning                    │
│  • Increased token usage                │
│  • Difficult to maintain                │
└─────────────────────────────────────────┘
```

### Multi-Agent Approach (Hierarchical)
```
┌─────────────────────────────────────────┐
│       MAIN AGENT (Orchestrator)         │
│                                         │
│  Simplified reasoning:                  │
│  ├─ Which sub-agent to use?            │
│  ├─ How to delegate task?              │
│  └─ How to synthesize results?         │
└──────────┬──────────────────────────────┘
           │
           ├──> Search Agent (Specialist)
           │    ├─ search tool
           │    └─ download tool
           │
           └──> PDF Agent (Specialist)
                ├─ extract tool
                └─ OCR tool

Benefits:
• Lower cognitive load per agent
• Specialized expertise
• Better scalability
• Easier to maintain
```

---

## 7. Data Flow Diagram

```
┌────────┐
│  USER  │
└───┬────┘
    │
    │ 1. Complex Task
    ▼
┌──────────────────────────────────────┐
│      Main Agent                      │
│  • Receives: Task string             │
│  • Analyzes: Requirements            │
│  • Decides: Agent selection          │
└───┬──────────────────────────────────┘
    │
    │ 2. Subtask + Parameters
    ▼
┌──────────────────────────────────────┐
│   Search Agent Service               │
│  • Creates: Agent instance           │
│  • Executes: Task                    │
│  • Returns: ActionResponse           │
└───┬──────────────────────────────────┘
    │
    │ 3. ActionResponse {success, message, metadata}
    ▼
┌──────────────────────────────────────┐
│      Main Agent                      │
│  • Receives: Search results          │
│  • Extracts: file_path               │
│  • Decides: Next step                │
└───┬──────────────────────────────────┘
    │
    │ 4. Subtask + file_path
    ▼
┌──────────────────────────────────────┐
│   PDF Agent Service                  │
│  • Creates: Agent instance           │
│  • Executes: Extraction + Summary    │
│  • Returns: ActionResponse           │
└───┬──────────────────────────────────┘
    │
    │ 5. ActionResponse {success, summary, metadata}
    ▼
┌──────────────────────────────────────┐
│      Main Agent                      │
│  • Combines: All results             │
│  • Formats: Final answer             │
│  • Returns: Comprehensive result     │
└───┬──────────────────────────────────┘
    │
    │ 6. Final Answer
    ▼
┌────────┐
│  USER  │
└────────┘
```

---

## 8. Configuration Hierarchy

```
Environment Variables (.env)
    │
    ├─> LLM_PROVIDER=openai
    ├─> LLM_MODEL_NAME=gpt-4o
    ├─> LLM_API_KEY=sk-...
    ├─> GOOGLE_API_KEY=...
    ├─> GOOGLE_CSE_ID=...
    └─> AWORLD_WORKSPACE=/path/to/workspace
    │
    └──> Loaded by all agents
         │
         ▼
┌──────────────────────────────────────┐
│   Project MCP Config                 │
│   (examples/gaia/mcp.json)           │
│                                      │
│   Defines:                           │
│   • search_agent service             │
│   • pdf_agent service                │
│   • Environment variable mapping     │
└──────────────────────────────────────┘
         │
         ├─> Used by Main Agent
         │
         ▼
┌──────────────────────────────────────┐
│   Service MCP Config                 │
│   (search_agent/mcp.json)            │
│                                      │
│   Defines:                           │
│   • search tool                      │
│   • download tool                    │
│   • Tool configurations              │
└──────────────────────────────────────┘
         │
         └─> Used by Search Agent
```

---

## 9. Error Handling Flow

```
Main Agent
    │
    ├─> Calls: search_agent.mcp_create_search_agent(...)
    │
    ▼
Search Agent Service
    │
    ├─> Try: Create and execute agent
    │   │
    │   ├─> Success ────────────────────┐
    │   │                                │
    │   └─> Error                        │
    │       │                            │
    │       ├─> Catch exception          │
    │       ├─> Log error details        │
    │       └─> Return error response    │
    │           {                        │
    │             success: false,        │
    │             message: "Error...",   │
    │             metadata: {            │
    │               error_type: "...",   │
    │               error_details: "..." │
    │             }                      │
    │           }                        │
    │                                    │
    └────────────────────────────────────┘
                │
                ▼
Main Agent
    │
    ├─> Receives response
    ├─> Checks: response.success
    │
    ├─> If true: Process results
    │
    └─> If false: Handle error
        ├─> Option 1: Try alternative approach
        ├─> Option 2: Report error to user
        └─> Option 3: Retry with different params
```

---

## 10. Agent Lifecycle

```
Creation Phase
    │
    │ 1. Request: create_agent(task_prompt, name, ...)
    ▼
┌──────────────────────────────────────┐
│  Generate agent_id                   │
│  "search_agent_abc123"               │
└───┬──────────────────────────────────┘
    │
    │ 2. Load configuration
    ▼
┌──────────────────────────────────────┐
│  Initialize Agent                    │
│  • LLM connection                    │
│  • Memory module                     │
│  • MCP tools                         │
│  • System prompt                     │
└───┬──────────────────────────────────┘
    │
    │ 3. Register in registry
    ▼
┌──────────────────────────────────────┐
│  Agent Registry                      │
│  [agent_id] → Agent instance         │
└───┬──────────────────────────────────┘
    │
    │ 4. Execute task
    ▼
┌──────────────────────────────────────┐
│  Agent Reasoning Loop                │
│  (Think-Act-Observe)                 │
└───┬──────────────────────────────────┘
    │
    │ 5. Return results
    ▼
┌──────────────────────────────────────┐
│  ActionResponse                      │
│  {success, message, metadata}        │
└───┬──────────────────────────────────┘
    │
    ├─> Agent stays in registry (can be reused)
    │
    └─> Or garbage collected when not referenced
```

---

## Key Takeaways

1. **Hierarchy**: Main agent coordinates, sub-agents execute
2. **Autonomy**: Each agent has independent reasoning
3. **Specialization**: Each agent focuses on specific domain
4. **Isolation**: Separate LLM, memory, and tools per agent
5. **Reusability**: Agents can be reused across tasks
6. **Scalability**: Easy to add new specialized agents

---

This visual guide should help you understand how the multi-agent orchestration system works!

