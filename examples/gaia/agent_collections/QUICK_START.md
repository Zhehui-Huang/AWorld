# Quick Start Guide - Multi-Agent Orchestration

Get started with multi-agent workflows in 5 minutes!

## Prerequisites

### 1. Install Dependencies

```bash
# From project root
pip install -r aworld/requirements.txt
```

### 2. Get API Keys

You'll need:

1. **OpenAI API Key** (or other LLM provider)
   - Get from: https://platform.openai.com/api-keys
   
2. **Google Custom Search API Key**
   - Get from: https://developers.google.com/custom-search/v1/introduction
   
3. **Google Custom Search Engine ID**
   - Create at: https://programmablesearchengine.google.com/

### 3. Configure Environment

Create `.env` file in project root:

```bash
# LLM Configuration
LLM_PROVIDER=openai
LLM_MODEL_NAME=gpt-4o
LLM_API_KEY=sk-your-openai-key-here
LLM_BASE_URL=https://api.openai.com/v1  # optional

# Search Configuration
GOOGLE_API_KEY=your-google-api-key-here
GOOGLE_CSE_ID=your-custom-search-engine-id-here

# Workspace
AWORLD_WORKSPACE=/path/to/your/workspace
```

**Alternative LLM Providers:**

For other providers (Anthropic, Azure, etc.):

```bash
# Anthropic Claude
LLM_PROVIDER=anthropic
LLM_MODEL_NAME=claude-3-5-sonnet-20241022
LLM_API_KEY=your-anthropic-key

# Azure OpenAI
LLM_PROVIDER=azure
LLM_MODEL_NAME=gpt-4
LLM_API_KEY=your-azure-key
LLM_BASE_URL=https://your-resource.openai.azure.com/
```

## Run Your First Example

### Option 1: Interactive Menu

```bash
# From project root
cd /path/to/AWorld
python -m examples.gaia.agent_collections.example_usage
```

You'll see:
```
╔════════════════════════════════════════════════════════════════════════════╗
║                                                                            ║
║           Dynamic Multi-Agent Workflow Examples                           ║
║                                                                            ║
╚════════════════════════════════════════════════════════════════════════════╝

Available Examples:
  1. Find arXiv Paper and Summarize (Full Workflow)
  2. Multi-Paper Analysis and Comparison
  3. Check Sub-Agent Capabilities
  4. Custom Workflow Template
  q. Quit

Select an example (1-4) or 'q' to quit:
```

**Recommended first example:** Choose `1`

### Option 2: Python Script

Create `test_workflow.py`:

```python
from dotenv import load_dotenv
from examples.gaia.agent_collections.example_usage import example_1_arxiv_paper_search_and_summarize

# Load environment variables
load_dotenv()

# Run the example
example_1_arxiv_paper_search_and_summarize()
```

Run it:
```bash
python test_workflow.py
```

## What Happens?

When you run Example 1, you'll see:

### 1. Initialization
```
✅ Loaded MCP servers: ['search_agent', 'pdf_agent']
🤖 Creating main orchestrator agent...
✅ Created main orchestrator agent with access to: ['search_agent', 'pdf_agent']
```

### 2. Task Execution
```
📋 Task:
Find a paper on arXiv from August 2020 about attention mechanisms...

🚀 Executing workflow...
```

### 3. Agent Delegation (Behind the Scenes)

The main agent will:

**Step 1:** Delegate to Search Agent
```
Main Agent: "I need to find a paper from arXiv. I'll use the search agent."
Tool Call: search_agent.mcp_create_search_agent(
    task_prompt="Find paper on arXiv from August 2020 about attention mechanisms"
)

Search Agent: 
  - Searches arXiv: "site:arxiv.org attention mechanisms August 2020"
  - Finds relevant paper
  - Downloads PDF file
  - Returns: file path
```

**Step 2:** Delegate to PDF Agent
```
Main Agent: "Now I have the PDF. I'll use the PDF agent to extract and summarize."
Tool Call: pdf_agent.mcp_create_pdf_agent(
    task_prompt="Extract content from [file_path] and create 1000-word summary"
)

PDF Agent:
  - Extracts text from PDF
  - Analyzes content
  - Generates structured summary
  - Returns: summary text
```

**Step 3:** Synthesis
```
Main Agent: "I have results from both agents. Let me synthesize the final answer."
Returns: Comprehensive summary with paper details, findings, and insights
```

### 4. Results
```
📊 Results
═══════════════════════════════════════════════════════════════════

✅ Task completed successfully!

[Detailed summary of the paper, approximately 1000 words, covering:]
- Paper title and authors
- Research question and motivation
- Proposed attention mechanism
- Key findings and results
- Significance and contributions
```

## Understanding the Output

### Successful Execution

You'll see these indicators:
- ✅ Green checkmarks for successful steps
- 🤖 Agent creation messages
- 🚀 Task execution status
- 📊 Final results

### Error Messages

If something goes wrong:
- ❌ Red X with error description
- Suggested fixes
- Missing configuration details

Common errors:
```
❌ Missing required environment variables: ['LLM_API_KEY']
→ Solution: Set LLM_API_KEY in .env file

❌ Failed to load MCP configuration
→ Solution: Ensure mcp.json exists in correct location

❌ Agent creation failed
→ Solution: Check API key and model name
```

## Next Steps

### 1. Try Other Examples

```bash
# Example 2: Compare multiple papers
python -m examples.gaia.agent_collections.example_usage
# Select: 2

# Example 3: Check agent capabilities
python -m examples.gaia.agent_collections.example_usage
# Select: 3
```

### 2. Modify Example 4 (Custom Workflow)

Edit `example_usage.py`, find `example_4_custom_workflow()`, and modify:

```python
task_prompt = """Find the latest quantum computing paper from arXiv,
download it, and extract the main algorithms described."""
```

### 3. Create Your Own Workflow

```python
import os
from pathlib import Path
from dotenv import load_dotenv
from aworld.agents.llm_agent import Agent
from aworld.config.conf import AgentConfig, TaskConfig
from aworld.core.task import Task
from aworld.runner import Runners
import json
import uuid

# Load environment
load_dotenv()

# Load MCP config
mcp_path = Path("examples/gaia/mcp.json")
with open(mcp_path) as f:
    mcp_config = json.load(f)

# Create agent config
agent_config = AgentConfig(
    llm_provider=os.getenv("LLM_PROVIDER", "openai"),
    llm_model_name=os.getenv("LLM_MODEL_NAME", "gpt-4o"),
    llm_api_key=os.getenv("LLM_API_KEY"),
)

# Create main agent
system_prompt = """You are an orchestrator agent with access to:
- search_agent (for web search and file download)
- pdf_agent (for PDF extraction and analysis)

Delegate tasks to specialized agents as needed."""

main_agent = Agent(
    conf=agent_config,
    name="my_orchestrator",
    agent_id=f"agent_{uuid.uuid4().hex[:8]}",
    system_prompt=system_prompt,
    mcp_config=mcp_config,
    mcp_servers=["search_agent", "pdf_agent"],
)

# Define your task
my_task = Task(
    id=uuid.uuid4().hex,
    input="Your task description here...",
    agent=main_agent,
    conf=TaskConfig(max_steps=30),
)

# Run it
results = Runners.sync_run_task(task=my_task)
print(results[my_task.id].answer)
```

## Tips for Success

### 1. Be Specific in Task Descriptions

**Good:**
```
"Find a paper on arXiv from August 2020 about attention mechanisms in transformers, 
download it, and provide a 1000-word summary covering the main contributions."
```

**Bad:**
```
"Find and summarize a paper about AI."
```

### 2. Set Appropriate `max_steps`

- Simple tasks: 10-15 steps
- Complex tasks with one agent: 20-30 steps
- Multi-agent workflows: 30-50 steps

### 3. Monitor Token Usage

Multi-agent systems use more tokens. To optimize:
- Use smaller models for sub-agents when possible
- Reuse agents to maintain context
- Be specific to reduce unnecessary reasoning

### 4. Check Workspace

Downloaded files are saved to `AWORLD_WORKSPACE`:
```bash
ls $AWORLD_WORKSPACE
# You should see downloaded PDFs
```

### 5. Review Logs

Logs are written to workspace and help debug issues:
```bash
tail -f $AWORLD_WORKSPACE/*.log
```

## Common Workflows

### 1. Research Paper Analysis

```python
task = "Find the top-cited paper on transformers from 2023, download it, " \
       "and extract the key innovations."
```

### 2. Comparative Analysis

```python
task = "Find two papers comparing CNNs vs Transformers for image classification, " \
       "download both, and summarize their findings."
```

### 3. Specific Paper Retrieval

```python
task = "Find the paper 'Attention Is All You Need' on arXiv, download it, " \
       "and extract all mathematical formulas."
```

### 4. Topic Survey

```python
task = "Find 3 recent papers on reinforcement learning from arXiv (2024), " \
       "download them, and create a comparative summary of their approaches."
```

## Troubleshooting

### Issue: "No results found"

**Cause:** Search query too specific or API limits
**Solution:** 
- Broaden search terms
- Check Google CSE quota
- Try different date ranges

### Issue: "Failed to download file"

**Cause:** Network issues, invalid URL, or file protection
**Solution:**
- Check internet connection
- Verify URL is accessible
- Try alternative paper source

### Issue: "PDF extraction failed"

**Cause:** Corrupted PDF, protected PDF, or scanned document
**Solution:**
- Try with `force_ocr=True` for scanned documents
- Ensure PDF is not password-protected
- Verify PDF is not corrupted

### Issue: "Agent timeout"

**Cause:** Task too complex or max_steps too low
**Solution:**
- Increase `max_steps`
- Break task into smaller subtasks
- Simplify task description

## Advanced Features

### 1. Agent Reuse

```python
# Create agent once
result1 = search_agent.mcp_create_search_agent(task_prompt="Find paper A")
agent_id = result1.metadata["agent_id"]

# Reuse for related task (maintains context)
result2 = search_agent.mcp_use_existing_search_agent(
    agent_id=agent_id,
    task_prompt="Find paper B by same author"
)
```

### 2. Custom Agent Configuration

```python
# Use different model for sub-agents
os.environ["LLM_MODEL_NAME"] = "gpt-3.5-turbo"  # Faster, cheaper

# Or use different provider
os.environ["LLM_PROVIDER"] = "anthropic"
os.environ["LLM_MODEL_NAME"] = "claude-3-5-sonnet-20241022"
```

### 3. Parallel Execution

For independent tasks, consider using parallel execution (advanced):
```python
# Coming soon: parallel agent execution for independent subtasks
```

## Getting Help

1. **Check Documentation:**
   - Main README: `agent_collections/README.md`
   - Search Agent: `search_agent/README.md`
   - PDF Agent: `pdf_agent/README.md`

2. **Review Examples:**
   - All examples: `example_usage.py`
   - Standalone agent examples: `{agent}/example_usage.py`

3. **Enable Debug Logging:**
   ```python
   import logging
   logging.basicConfig(level=logging.DEBUG)
   ```

4. **Check Logs:**
   ```bash
   # Main logs
   tail -f logs/AWorld-*.log
   
   # Trace logs
   tail -f logs/Trace-*.log
   ```

## What's Next?

Now that you've run your first multi-agent workflow:

1. ✅ Try all example workflows
2. ✅ Modify Example 4 with your own tasks
3. ✅ Read the full documentation in README.md
4. ✅ Explore individual agent capabilities
5. ✅ Create custom workflows for your use case

Happy orchestrating! 🚀

