# Search Agent MCP Server - Quick Start Guide

Get started with the Search Agent MCP Server in 5 minutes!

## Prerequisites

1. **Python 3.8+** installed
2. **Environment variables** configured
3. **AWorld framework** installed

## Step 1: Configure Environment

Create a `.env` file in your project root:

```bash
# LLM Configuration (Required)
LLM_PROVIDER=openai
LLM_MODEL_NAME=gpt-4o
LLM_API_KEY=your-openai-api-key
LLM_BASE_URL=https://api.openai.com/v1

# Google Search (Required for search functionality)
GOOGLE_API_KEY=your-google-api-key
GOOGLE_CSE_ID=your-custom-search-engine-id

# Workspace (Optional)
AWORLD_WORKSPACE=/path/to/your/workspace
```

### Getting API Keys

**OpenAI API Key:**
1. Go to https://platform.openai.com/api-keys
2. Create new API key
3. Copy and paste into `.env`

**Google Custom Search:**
1. Enable Custom Search API: https://console.cloud.google.com/
2. Create Search Engine: https://programmablesearchengine.google.com/
3. Get API key and CSE ID

## Step 2: Test the Installation

Run a simple test to verify everything works:

```bash
python -m examples.gaia.agent_collections.search_agent.example_usage
```

This will run Example 5 (Direct Usage) which doesn't require MCP protocol setup.

## Step 3: Use in Your Code

### Option A: Via MCP Protocol (Recommended)

```python
from aworld.agents.llm_agent import Agent
from aworld.config.conf import AgentConfig
from aworld.core.task import Task
from aworld.runner import Runners
import json

# Load MCP config
with open("examples/gaia/mcp.json", "r") as f:
    mcp_config = json.load(f)

# Create main agent
agent_config = AgentConfig(
    llm_provider="openai",
    llm_model_name="gpt-4o",
    llm_api_key="your-api-key",
)

main_agent = Agent(
    conf=agent_config,
    name="main_agent",
    system_prompt="You are a helpful assistant.",
    mcp_config=mcp_config,
    mcp_servers=["search_agent"],  # Enable search agent server
)

# Create a task that delegates to search agent
task = Task(
    input="""
    Use the search agent to find recent AI papers.
    Call search_agent.mcp_create_search_agent with task_prompt:
    "Find AI papers from arXiv submitted in 2023"
    """,
    agent=main_agent,
)

# Execute
result = Runners.sync_run_task(task=task)
print(result[task.id].answer)
```

### Option B: Direct Usage (For Testing)

```python
from examples.gaia.agent_collections.search_agent.search_agent import (
    SearchAgentCollection,
    ActionArguments,
)

# Create service
args = ActionArguments(
    name="search_agent",
    transport="stdio",
    workspace="/path/to/workspace",
    unittest=True,
)

service = SearchAgentCollection(args)

# Create and execute search agent
result = service.mcp_create_search_agent(
    task_prompt="Find papers about quantum computing",
    name="quantum_researcher",
    description="Agent for quantum computing research",
    max_steps=10,
)

if result.success:
    print(f"Agent ID: {result.metadata['agent_id']}")
    print(f"Answer: {result.metadata['answer']}")
```

## Step 4: Common Usage Patterns

### Pattern 1: Create Search Agent

```python
result = service.mcp_create_search_agent(
    task_prompt="Find the top 5 AI conferences in 2024",
    name="conference_finder",
    description="Agent specialized in finding academic conferences",
    max_steps=15,
)

agent_id = result.metadata['agent_id']
answer = result.metadata['answer']
```

### Pattern 2: Reuse Existing Agent

```python
# First call creates and registers the agent
result1 = service.mcp_create_search_agent(
    task_prompt="Find AI papers",
    name="ai_researcher",
)

# Later calls can reuse the same agent
result2 = service.mcp_use_existing_search_agent(
    agent_id=result1.metadata['agent_id'],
    task_prompt="Now find quantum computing papers",
)
```

### Pattern 3: Check Capabilities

```python
result = service.mcp_get_search_agent_capabilities()
print(result.message)  # Formatted capabilities
print(f"Registered agents: {result.metadata['agent_count']}")
```

### Pattern 4: Multi-Layer Delegation

```python
# Main agent receives complex task
main_task = "Research AI safety and provide a comprehensive report"

# Main agent decides to delegate search to search agent
search_result = main_agent.call_tool(
    "search_agent.mcp_create_search_agent",
    task_prompt="Find top AI safety papers from 2023-2024"
)

# Main agent processes search results
papers = search_result.metadata['answer']

# Main agent might delegate analysis to another agent
analysis_result = main_agent.call_tool(
    "analysis_agent.analyze",
    data=papers
)

# Main agent synthesizes final report
final_report = main_agent.synthesize(search_result, analysis_result)
```

## Step 5: Troubleshooting

### Issue: "Agent ID not found"

**Solution:** Make sure you're using the correct agent_id from the creation response.

```python
# Save agent_id for later use
result = service.mcp_create_search_agent(...)
agent_id = result.metadata['agent_id']  # Save this!

# Use it later
result2 = service.mcp_use_existing_search_agent(agent_id=agent_id, ...)
```

### Issue: "LLM API key missing"

**Solution:** Check your `.env` file and environment variables.

```bash
# Verify environment variables are loaded
python -c "import os; from dotenv import load_dotenv; load_dotenv(); print(os.getenv('LLM_API_KEY'))"
```

### Issue: "Google Search API error"

**Solution:** Verify your Google API credentials.

```python
# Test Google API directly
from examples.gaia.agent_collections.search_agent.mcp_tools.search import SearchCollection

args = ActionArguments(name="test", workspace="~")
search = SearchCollection(args)
result = search.mcp_search_google(query="test", num_results=1)
print(result.success)
```

### Issue: "Task timeout"

**Solution:** Increase `max_steps` parameter.

```python
result = service.mcp_create_search_agent(
    task_prompt="Complex task...",
    max_steps=20,  # Increase from default 12
)
```

## Next Steps

### Learn More

- 📖 Read the [README.md](README.md) for detailed documentation
- 🏗️ Check [ARCHITECTURE.md](ARCHITECTURE.md) for design details
- 💡 See [example_usage.py](example_usage.py) for more examples

### Customize

1. **Modify System Prompt:** Edit `prompt.py` to change agent behavior
2. **Add New Tools:** Add new MCP servers to `mcp.json`
3. **Extend Agent Types:** Create new agent collections for other tasks

### Production Deployment

Before deploying to production:

1. ✅ Add persistent storage for agents
2. ✅ Implement rate limiting
3. ✅ Add monitoring and logging
4. ✅ Set up error alerting
5. ✅ Test with production data
6. ✅ Configure proper security

## Common Recipes

### Recipe 1: Research Assistant

```python
# Create a research assistant that can search and summarize
result = service.mcp_create_search_agent(
    task_prompt="Find and summarize the top 3 papers on transformers architecture",
    name="research_assistant",
    description="AI research assistant specializing in ML papers",
    max_steps=20,
)
```

### Recipe 2: News Aggregator

```python
# Create an agent that aggregates news
result = service.mcp_create_search_agent(
    task_prompt="Find the latest news about AI regulation in the EU",
    name="news_aggregator",
    description="Agent for aggregating and filtering news",
    max_steps=15,
)
```

### Recipe 3: Data Collector

```python
# Create an agent that collects and downloads data
result = service.mcp_create_search_agent(
    task_prompt="Find and download public datasets on climate change",
    name="data_collector",
    description="Agent for finding and downloading datasets",
    max_steps=25,
)
```

## Help & Support

### Getting Help

- 📝 Check existing documentation first
- 🐛 Report bugs via GitHub issues
- 💬 Ask questions in discussions
- 📧 Contact maintainers for support

### Contributing

Contributions are welcome! Please:

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests
5. Submit a pull request

## Additional Resources

- **AWorld Framework:** [Documentation](../../README.md)
- **MCP Protocol:** [Specification](https://modelcontextprotocol.io/)
- **Google Custom Search:** [API Docs](https://developers.google.com/custom-search/v1/introduction)

---

**Happy coding! 🚀**

If you found this helpful, consider starring the repository and sharing with others!

