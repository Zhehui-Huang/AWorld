# Agent Collections - Multi-Agent Orchestration Examples

This directory demonstrates **dynamic multi-agent orchestration** using the AWorld framework. It showcases how a main agent can delegate complex tasks to specialized sub-agents, each with their own LLM, memory, and tools.

## Architecture Overview

### Traditional Approach (Flat)
```
Main Agent
├── Tool 1
├── Tool 2
├── Tool 3
├── ...
└── Tool N (dozens of tools)
```
**Problems:**
- Agent must reason about many tools simultaneously
- Increased cognitive load and token usage
- Difficult to maintain and scale
- No specialization or context isolation

### Multi-Agent Approach (Hierarchical)
```
Main Agent (Orchestrator)
├─> Search Agent (Specialized Sub-Agent)
│   ├── LLM Instance
│   ├── Memory Module
│   └── MCP Tools
│       ├── Google Search
│       └── File Download
│
└─> PDF Agent (Specialized Sub-Agent)
    ├── LLM Instance
    ├── Memory Module
    └── MCP Tools
        └── PDF Extraction
```
**Benefits:**
- Clear separation of concerns
- Each agent specializes in specific domain
- Reduced cognitive load per agent
- Easier to maintain and extend
- Agent reusability across tasks
- Independent memory and context

## Quick Start

### Prerequisites

1. **Install Dependencies**
```bash
pip install -r aworld/requirements.txt
```

2. **Set Environment Variables**

Create a `.env` file in the project root:
```bash
# LLM Configuration (Main Agent)
LLM_PROVIDER=openai
LLM_MODEL_NAME=gpt-4o
LLM_API_KEY=your_openai_api_key
LLM_BASE_URL=https://api.openai.com/v1  # optional

# Search Configuration (for Search Agent)
GOOGLE_API_KEY=your_google_api_key
GOOGLE_CSE_ID=your_custom_search_engine_id

# Workspace (where files are downloaded/saved)
AWORLD_WORKSPACE=/path/to/your/workspace
```

### Run Examples

From the project root directory:

```bash
# Interactive menu with all examples
python -m examples.gaia.agent_collections.example_usage

# Or run specific example directly
python -m examples.gaia.agent_collections.example_usage
```

## Available Sub-Agents

### 1. Search Agent

**Purpose:** Find information on the web and download files

**Capabilities:**
- Web search using Google Custom Search API
- Filter and rank search results
- Download files from URLs
- Return structured, LLM-friendly results

**MCP Tools:**
- `mcp_create_search_agent`: Create new search agent instance
- `mcp_use_existing_search_agent`: Reuse existing search agent by ID
- `mcp_get_search_agent_capabilities`: Query agent capabilities

**Use Cases:**
- Finding papers on arXiv
- Downloading research documents
- Web research and fact-checking
- Gathering resources from specific sources

**Location:** `search_agent/`

### 2. PDF Agent

**Purpose:** Extract and analyze content from PDF documents

**Capabilities:**
- Extract text from PDF documents
- Extract images and media
- OCR support for scanned documents
- Format content for LLM analysis
- Handle multi-page documents

**MCP Tools:**
- `mcp_create_pdf_agent`: Create new PDF agent instance
- `mcp_use_existing_pdf_agent`: Reuse existing PDF agent by ID
- `mcp_get_pdf_agent_capabilities`: Query agent capabilities

**Use Cases:**
- Summarizing research papers
- Extracting specific information from documents
- Analyzing document structure
- Comparing multiple documents

**Location:** `pdf_agent/`

## Example Workflows

### Example 1: Find and Summarize arXiv Paper

**Task:** Find a paper on arXiv from August 2020 about attention mechanisms, download it, and provide a 1000-word summary.

**Workflow:**
```
1. Main Agent receives task
2. Main Agent → Search Agent: "Find and download arXiv paper from Aug 2020 about attention mechanisms"
   └─> Search Agent searches arXiv
   └─> Search Agent downloads PDF
   └─> Returns: file path
3. Main Agent → PDF Agent: "Extract and summarize in 1000 words: [file_path]"
   └─> PDF Agent extracts content
   └─> PDF Agent generates summary
   └─> Returns: summary text
4. Main Agent synthesizes results
5. Returns final answer to user
```

**Code:**
```python
from examples.gaia.agent_collections.example_usage import example_1_arxiv_paper_search_and_summarize

example_1_arxiv_paper_search_and_summarize()
```

### Example 2: Multi-Paper Comparative Analysis

**Task:** Find two papers about different attention mechanisms, download both, and provide a comparative analysis.

**Workflow:**
```
1. Main Agent receives task
2. Main Agent → Search Agent: "Find first paper on self-attention"
   └─> Returns: paper1.pdf
3. Main Agent → Search Agent (reuse): "Find second paper on cross-attention"
   └─> Returns: paper2.pdf
4. Main Agent → PDF Agent: "Extract content from paper1.pdf"
   └─> Returns: content1
5. Main Agent → PDF Agent (reuse): "Extract content from paper2.pdf"
   └─> Returns: content2
6. Main Agent analyzes and compares both
7. Returns comparative analysis
```

**Code:**
```python
from examples.gaia.agent_collections.example_usage import example_2_multi_paper_analysis

example_2_multi_paper_analysis()
```

### Example 3: Check Capabilities

**Task:** Query available sub-agents and their capabilities.

**Code:**
```python
from examples.gaia.agent_collections.example_usage import example_3_check_capabilities

example_3_check_capabilities()
```

## How It Works

### 1. Main Agent Creation

The main agent is created with access to both sub-agent MCP servers:

```python
# Load MCP config with both search_agent and pdf_agent
mcp_config = load_mcp_config()  # from mcp.json

# Create main agent with access to sub-agents
main_agent = Agent(
    conf=agent_config,
    name="main_orchestrator_agent",
    system_prompt=orchestrator_prompt,  # Includes sub-agent usage instructions
    mcp_config=mcp_config,
    mcp_servers=["search_agent", "pdf_agent"],
)
```

### 2. Task Delegation

The main agent decides which sub-agent to use and delegates tasks:

```python
# Main agent's reasoning process:
# "I need to search for a paper -> use search_agent"
# Tool call: search_agent.mcp_create_search_agent(
#     task_prompt="Find paper on arXiv about attention mechanisms from Aug 2020"
# )

# "Now I need to analyze the PDF -> use pdf_agent"
# Tool call: pdf_agent.mcp_create_pdf_agent(
#     task_prompt="Extract and summarize [file_path] in 1000 words"
# )
```

### 3. Sub-Agent Execution

Each sub-agent runs independently with its own reasoning loop:

```python
# Inside Search Agent:
# 1. Think: "I need to search arXiv for papers from Aug 2020"
# 2. Act: search.mcp_search_google(query="site:arxiv.org attention mechanisms Aug 2020")
# 3. Observe: Got results with paper URLs
# 4. Think: "Found relevant paper, need to download it"
# 5. Act: download.mcp_download_file(url="https://arxiv.org/pdf/...")
# 6. Observe: File downloaded successfully
# 7. Return: Results with file path

# Inside PDF Agent:
# 1. Think: "I need to extract content from this PDF"
# 2. Act: pdf.mcp_extract_document_content(file_path="...")
# 3. Observe: Content extracted successfully
# 4. Think: "Now I need to create a 1000-word summary"
# 5. Analyze content and create summary
# 6. Return: Summary text
```

### 4. Result Synthesis

The main agent receives results from sub-agents and synthesizes the final answer.

## Configuration Files

### `mcp.json` (Project Level)

Located at `examples/gaia/mcp.json`, this file defines which MCP servers the main agent can access:

```json
{
  "mcpServers": {
    "search_agent": {
      "command": "python",
      "args": ["-m", "examples.gaia.agent_collections.search_agent.search_agent"],
      "env": {
        "GOOGLE_API_KEY": "${GOOGLE_API_KEY}",
        "GOOGLE_CSE_ID": "${GOOGLE_CSE_ID}",
        "LLM_PROVIDER": "${LLM_PROVIDER}",
        "LLM_MODEL_NAME": "${LLM_MODEL_NAME}",
        "LLM_API_KEY": "${LLM_API_KEY}",
        "AWORLD_WORKSPACE": "${AWORLD_WORKSPACE}"
      }
    },
    "pdf_agent": {
      "command": "python",
      "args": ["-m", "examples.gaia.agent_collections.pdf_agent.pdf_agent"],
      "env": {
        "LLM_PROVIDER": "${LLM_PROVIDER}",
        "LLM_MODEL_NAME": "${LLM_MODEL_NAME}",
        "LLM_API_KEY": "${LLM_API_KEY}",
        "AWORLD_WORKSPACE": "${AWORLD_WORKSPACE}"
      }
    }
  }
}
```

### Sub-Agent MCP Configs

Each sub-agent has its own `mcp.json` defining the low-level tools it can use:

- `search_agent/mcp.json`: Defines `search` and `download` tools
- `pdf_agent/mcp.json`: Defines `pdf` extraction tools

## Directory Structure

```
agent_collections/
├── README.md                          # This file
├── example_usage.py                   # Main examples and workflows
│
├── search_agent/                      # Search Agent implementation
│   ├── search_agent.py               # Agent server implementation
│   ├── prompt.py                     # Agent system prompt
│   ├── mcp.json                      # Low-level MCP tools config
│   ├── mcp_tools/                    # Tool implementations
│   │   ├── search.py                 # Google search tool
│   │   └── download.py               # File download tool
│   ├── README.md                     # Search agent documentation
│   ├── QUICK_START.md               # Quick start guide
│   ├── ARCHITECTURE.md              # Architecture details
│   └── example_usage.py             # Standalone examples
│
└── pdf_agent/                        # PDF Agent implementation
    ├── pdf_agent.py                 # Agent server implementation
    ├── prompt.py                    # Agent system prompt
    ├── mcp.json                     # Low-level MCP tools config
    ├── mcp_tools/                   # Tool implementations
    │   └── pdf.py                   # PDF extraction tool
    ├── README.md                    # PDF agent documentation
    ├── QUICK_START.md              # Quick start guide
    └── example_usage.py            # Standalone examples
```

## Key Concepts

### 1. Agent Registry

Each sub-agent maintains a registry of created agent instances:

```python
# Create new agent
response = search_agent.mcp_create_search_agent(task_prompt="...")
agent_id = response.metadata["agent_id"]

# Reuse existing agent (maintains memory and context)
response = search_agent.mcp_use_existing_search_agent(
    agent_id=agent_id,
    task_prompt="new task for same agent"
)
```

### 2. Autonomous Execution

Sub-agents execute tasks autonomously:
- They have their own reasoning loop (think-act-observe)
- They decide which tools to use and when
- They manage their own memory and context
- They return results to the parent agent

### 3. Dynamic Delegation

The main agent dynamically decides:
- Which sub-agent to use based on task requirements
- When to create new agents vs. reuse existing ones
- How to synthesize results from multiple agents
- What information to pass between agents

### 4. Separation of Concerns

Each agent focuses on its specialty:
- **Main Agent**: Task orchestration, delegation, result synthesis
- **Search Agent**: Web search, resource discovery, file download
- **PDF Agent**: Document extraction, content analysis, summarization

## Advanced Usage

### Creating Custom Sub-Agents

To add a new specialized agent:

1. Create agent directory: `my_agent/`
2. Implement agent server: `my_agent.py`
3. Define agent prompt: `prompt.py`
4. Create MCP tools config: `mcp.json`
5. Implement tools: `mcp_tools/`
6. Update project-level `mcp.json` to include new agent
7. Update main agent's system prompt with new agent capabilities

### Agent Reusability

Agents can be reused across multiple tasks to maintain context:

```python
# First task - create agent
response1 = search_agent.mcp_create_search_agent(
    task_prompt="Find papers about transformers"
)
agent_id = response1.metadata["agent_id"]

# Second task - reuse same agent (remembers previous context)
response2 = search_agent.mcp_use_existing_search_agent(
    agent_id=agent_id,
    task_prompt="Now find papers about attention mechanisms"
)
```

### Error Handling

The framework includes robust error handling:
- Agent creation failures return detailed error messages
- Tool execution failures are logged and reported
- Missing dependencies are detected and reported
- Configuration errors are caught early

## Troubleshooting

### Common Issues

1. **Missing API Keys**
   - Error: "Missing required environment variables"
   - Solution: Set all required variables in `.env` file

2. **MCP Configuration Not Found**
   - Error: "Failed to load MCP configuration"
   - Solution: Ensure `mcp.json` exists in correct location

3. **Import Errors**
   - Error: "ModuleNotFoundError"
   - Solution: Run from project root, ensure all dependencies installed

4. **Agent Creation Fails**
   - Error: "Failed to create agent"
   - Solution: Check LLM credentials, ensure model name is correct

5. **File Download Fails**
   - Error: "Failed to download file"
   - Solution: Check network connection, URL validity, workspace permissions

### Debug Mode

Enable detailed logging:

```python
import logging
logging.basicConfig(level=logging.DEBUG)
```

## Performance Considerations

### Token Usage

Multi-agent architectures can use more tokens due to:
- Multiple LLM calls (one per agent)
- Inter-agent communication overhead
- Result serialization and deserialization

**Optimization strategies:**
- Reuse agents when possible (maintains context)
- Set appropriate `max_steps` limits
- Use smaller models for sub-agents if accuracy permits
- Cache common results

### Execution Time

Multi-agent workflows are slower than single-agent due to:
- Sequential delegation (main → sub-agent → main)
- Multiple reasoning loops
- Tool execution overhead

**Optimization strategies:**
- Use parallel execution when tasks are independent
- Optimize sub-agent prompts for efficiency
- Set reasonable timeouts

## Best Practices

1. **Clear Task Definitions**
   - Provide specific, actionable instructions to sub-agents
   - Include expected output format in task prompts

2. **Appropriate Agent Selection**
   - Use search agent for information retrieval
   - Use PDF agent for document analysis
   - Don't mix concerns within a single sub-agent

3. **Error Recovery**
   - Handle sub-agent failures gracefully
   - Provide fallback strategies
   - Log errors for debugging

4. **Resource Management**
   - Clean up downloaded files when no longer needed
   - Monitor workspace disk usage
   - Set reasonable file size limits

5. **Security**
   - Validate file paths before operations
   - Sanitize URLs before downloading
   - Use secure API key management

## Future Extensions

Potential additional sub-agents:

- **Data Analysis Agent**: Process CSV/Excel files, run statistical analysis
- **Code Agent**: Read, analyze, and execute code
- **Image Agent**: Process and analyze images
- **Translation Agent**: Translate between languages
- **Summarization Agent**: Specialized long-form summarization
- **Verification Agent**: Fact-check and verify information

## Resources

- **AWorld Framework**: Main repository documentation
- **MCP Protocol**: [Model Context Protocol specification](https://modelcontextprotocol.io/)
- **Agent Architectures**: See individual agent README files
- **Examples**: See `example_usage.py` for working code

## Support

For issues or questions:
1. Check individual agent README files
2. Review example code in `example_usage.py`
3. Check logs in workspace directory
4. Open an issue in the main repository

## License

See project root LICENSE file.

