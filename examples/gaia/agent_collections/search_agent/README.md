# Search Agent MCP Server

A modular Search Agent MCP Server that implements a **dynamic multi-layer agent architecture**. This server enables the creation and management of specialized search agents that can autonomously handle search-related tasks with their own LLM, memory, and MCP tools.

## Architecture Overview

### Traditional Two-Layer System
```
Main Agent
    ├── MCP Tool 1
    ├── MCP Tool 2
    ├── MCP Tool 3
    └── ... (dozens of tools)
```

### New Dynamic Multi-Layer System
```
Main Agent
    ├── Sub-Main Agent (for specific goals)
    │   ├── Sub-Sub-Main Agent (for nested reasoning)
    │   └── Search Agent (for search tasks)
    │       ├── LLM Instance
    │       ├── Memory Module
    │       └── MCP Tools
    │           ├── search (Google Custom Search)
    │           └── download (File retrieval)
    └── Other Agents/Tools
```

## Key Features

### 1. **Independent Agent Instances**
Each Search Agent has:
- **Unique ID**: For tracking and reuse
- **Custom Name & Description**: For identification
- **Dedicated LLM**: Configurable provider and model
- **Memory Module**: Maintains context across tasks
- **Specialized MCP Tools**: Only search and download tools

### 2. **Autonomous Task Execution**
Search agents follow a **think-act-observe** loop:
1. **Think**: Analyze the task and plan steps
2. **Act**: Execute MCP tool calls (search, download)
3. **Observe**: Evaluate results and decide next actions
4. **Return**: Provide final results to parent agent

### 3. **Agent Registry**
Centralized management of created agents:
- Register new agents
- Retrieve existing agents by ID
- List all registered agents
- Reuse agents across multiple tasks

### 4. **Dynamic Delegation**
Parent agents can:
- Create new search agents on-demand
- Delegate search tasks to existing agents
- Receive structured results
- Continue with their own reasoning

## MCP Server API

### 1. `mcp_create_search_agent`

Create a new search agent and execute a task.

**Parameters:**
- `task_prompt` (str, required): The task or query to process
- `name` (str, optional): Name for the agent (default: "search_agent")
- `description` (str, optional): Agent description
- `max_steps` (int, optional): Maximum execution steps (default: 12)

**LLM Configuration (from environment variables):**
- `LLM_PROVIDER` (default: "openai")
- `LLM_MODEL_NAME` (default: "gpt-4o")
- `LLM_BASE_URL` (optional)
- `LLM_API_KEY` (required)
- `LLM_TEMPERATURE` (default: "0.0")

**Returns:**
```json
{
  "success": true,
  "message": "# Search Agent Execution Results...",
  "metadata": {
    "agent_id": "search_agent_abc12345",
    "agent_name": "search_agent",
    "description": "Search agent specialized in web search",
    "answer": "Result from the agent",
    "task_prompt": "Find...",
    "created_at": "2025-10-27 10:30:45",
    "llm_provider": "openai",
    "llm_model_name": "gpt-4o",
    "mcp_servers": ["search", "download"]
  }
}
```

**Example Usage:**
```python
# From main agent or parent agent
# LLM configuration is loaded from environment variables
result = mcp_create_search_agent(
    task_prompt="Find the latest AI regulation papers from arXiv in June 2022",
    name="arxiv_search_agent",
    description="Agent specialized in searching arXiv papers",
    max_steps=15
)

agent_id = result.metadata["agent_id"]
answer = result.metadata["answer"]
```

### 2. `mcp_use_existing_search_agent`

Reuse an existing search agent for a new task.

**Parameters:**
- `agent_id` (str, required): ID of existing search agent
- `task_prompt` (str, required): The task or query to process
- `max_steps` (int, optional): Maximum execution steps (default: 12)

**Returns:**
Similar to `mcp_create_search_agent` but without creation details.

**Example Usage:**
```python
# Reuse previously created agent
result = mcp_use_existing_search_agent(
    agent_id="search_agent_abc12345",
    task_prompt="Now search for climate change papers"
)

answer = result.metadata["answer"]
```

### 3. `mcp_get_search_agent_capabilities`

Get information about the search agent service.

**Parameters:** None

**Returns:**
Service capabilities, registered agents, and configuration details.

**Example Usage:**
```python
result = mcp_get_search_agent_capabilities()
print(result.message)  # Formatted capabilities
print(result.metadata["registered_agents"])  # List of agents
```

## Workflow Example

### Scenario: Multi-Step Research Task

```python
# Main Agent receives a complex query
user_query = "Research the top 3 AI safety papers from 2022 and summarize their key findings"

# Step 1: Main Agent creates a Search Agent
search_result = mcp_create_search_agent(
    task_prompt="Find top 3 AI safety papers from 2022 with download links",
    name="ai_safety_researcher",
    description="Agent specialized in AI safety research"
)

agent_id = search_result.metadata["agent_id"]
papers = search_result.metadata["answer"]

# Step 2: Main Agent processes the results
# (Could create another agent for summarization)
summary_agent = create_summary_agent(
    task_prompt=f"Summarize these papers: {papers}"
)

# Step 3: Main Agent returns final result to user
return final_summary
```

## Configuration

### Environment Variables

Create a `.env` file or set these variables:

```bash
# LLM Configuration
LLM_PROVIDER=openai
LLM_MODEL_NAME=gpt-4o
LLM_BASE_URL=https://api.openai.com/v1
LLM_API_KEY=your-api-key

# Search Configuration
GOOGLE_API_KEY=your-google-api-key
GOOGLE_CSE_ID=your-cse-id

# Workspace
AWORLD_WORKSPACE=/path/to/workspace
```

### MCP Configuration

The search agent automatically loads its MCP configuration from `mcp.json`:

```json
{
  "mcpServers": {
    "search": {
      "command": "python",
      "args": ["-m", "examples.gaia.agent_collections.search_agent.mcp_tools.search"],
      "env": {
        "GOOGLE_API_KEY": "${GOOGLE_API_KEY}",
        "GOOGLE_CSE_ID": "${GOOGLE_CSE_ID}"
      }
    },
    "download": {
      "command": "python",
      "args": ["-m", "examples.gaia.agent_collections.search_agent.mcp_tools.download"]
    }
  }
}
```

## Benefits of Multi-Layer Architecture

### 1. **Modularity**
- Each agent has clear responsibilities
- Easy to add new specialized agents
- Clean separation of concerns

### 2. **Scalability**
- Parent agents don't need to know all tools
- New tools can be added to sub-agents without affecting parents
- Hierarchical task decomposition

### 3. **Flexibility**
- Dynamic agent creation based on task needs
- Reusable agents for similar tasks
- Configurable per-agent settings

### 4. **Maintainability**
- Isolated agent logic
- Easier debugging and testing
- Clear data flow between layers

## Advanced Usage

### Creating Custom Agent Hierarchies

```python
# Main Agent
main_agent = Agent(...)

# Main agent detects complex task
if requires_search(task):
    # Create specialized search agent
    search_agent = mcp_create_search_agent(
        task_prompt=extract_search_query(task)
    )
    search_results = search_agent.metadata["answer"]
    
if requires_analysis(task):
    # Create analysis agent
    analysis_agent = create_analysis_agent(
        data=search_results
    )
    analysis = analysis_agent.execute()

# Combine results
final_result = combine(search_results, analysis)
```

### Recursive Agent Creation

```python
# Parent agent can create child agents
# Child agents can create grandchild agents
# And so on...

main_agent
  └─> sub_main_agent (for complex reasoning)
      ├─> search_agent (for information retrieval)
      └─> analysis_agent (for data processing)
          └─> visualization_agent (for presenting results)
```

## Testing

Run the search agent standalone:

```bash
python -m examples.gaia.agent_collections.search_agent.search_agent_run \
  --prompt "Find AI papers from 2022" \
  --max-steps 15
```

Or test the MCP server:

```bash
python -m examples.gaia.agent_collections.search_agent.search_agent
```

## Troubleshooting

### Common Issues

1. **Agent Not Found**
   - Check if agent_id is correct
   - Use `mcp_get_search_agent_capabilities` to list agents

2. **LLM Configuration Error**
   - Verify environment variables
   - Check API keys are valid

3. **MCP Tools Not Loading**
   - Ensure `mcp.json` exists in correct location
   - Verify tool paths are correct

4. **Task Timeout**
   - Increase `max_steps` parameter
   - Simplify the task prompt

## Future Enhancements

- [ ] Persistent agent storage (database)
- [ ] Agent collaboration patterns
- [ ] Advanced memory management
- [ ] Cost tracking per agent
- [ ] Agent performance metrics
- [ ] Multi-agent orchestration patterns

## Contributing

When extending the search agent:

1. Keep agent logic focused on search/retrieval
2. Add new tools to `mcp_tools/` directory
3. Update `mcp.json` with new tool configurations
4. Document new capabilities in this README

## License

See main project LICENSE file.

