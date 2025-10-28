# Troubleshooting Guide - Multi-Agent Orchestration

This guide helps you diagnose and resolve common issues when working with the multi-agent orchestration system.

## Table of Contents

1. [Setup Issues](#setup-issues)
2. [Configuration Issues](#configuration-issues)
3. [Runtime Issues](#runtime-issues)
4. [Agent Issues](#agent-issues)
5. [Tool Issues](#tool-issues)
6. [Performance Issues](#performance-issues)
7. [Debug Techniques](#debug-techniques)

---

## Setup Issues

### Issue: Module Import Errors

**Symptom:**
```
ModuleNotFoundError: No module named 'aworld'
```

**Causes:**
- Not running from project root
- Dependencies not installed
- Python path not configured

**Solutions:**

1. **Run from project root:**
```bash
cd /path/to/AWorld
python -m examples.gaia.agent_collections.example_usage
```

2. **Install dependencies:**
```bash
pip install -r aworld/requirements.txt
```

3. **Install in development mode:**
```bash
pip install -e .
```

4. **Check Python path:**
```python
import sys
print(sys.path)
# Should include project root
```

---

### Issue: Missing Dependencies

**Symptom:**
```
ImportError: cannot import name 'FastMCP' from 'mcp.server'
```

**Causes:**
- MCP package not installed
- Wrong package version
- Virtual environment not activated

**Solutions:**

1. **Install MCP:**
```bash
pip install mcp
```

2. **Update all dependencies:**
```bash
pip install --upgrade -r aworld/requirements.txt
```

3. **Check installed packages:**
```bash
pip list | grep mcp
```

4. **Create new virtual environment if needed:**
```bash
python -m venv venv
source venv/bin/activate  # Linux/Mac
# or
venv\Scripts\activate  # Windows
pip install -r aworld/requirements.txt
```

---

## Configuration Issues

### Issue: Missing Environment Variables

**Symptom:**
```
❌ Missing required environment variables: ['LLM_API_KEY', 'GOOGLE_API_KEY']
```

**Causes:**
- `.env` file not created
- `.env` file in wrong location
- Environment variables not exported

**Solutions:**

1. **Create `.env` file in project root:**
```bash
touch .env
```

2. **Add required variables:**
```bash
# LLM Configuration
LLM_PROVIDER=openai
LLM_MODEL_NAME=gpt-4o
LLM_API_KEY=sk-your-key-here
LLM_BASE_URL=https://api.openai.com/v1

# Search Configuration
GOOGLE_API_KEY=your-google-key
GOOGLE_CSE_ID=your-cse-id

# Workspace
AWORLD_WORKSPACE=/path/to/workspace
```

3. **Verify `.env` is loaded:**
```python
from dotenv import load_dotenv
import os

load_dotenv()
print(os.getenv('LLM_API_KEY'))  # Should not be None
```

4. **Alternative: Export directly:**
```bash
export LLM_API_KEY=your-key
export GOOGLE_API_KEY=your-key
```

---

### Issue: Invalid API Keys

**Symptom:**
```
Error: Invalid API key provided
```
or
```
401 Unauthorized
```

**Causes:**
- Incorrect API key
- Expired API key
- Wrong API provider

**Solutions:**

1. **Verify OpenAI API key:**
```bash
curl https://api.openai.com/v1/models \
  -H "Authorization: Bearer $LLM_API_KEY"
```

2. **Verify Google API key:**
```bash
curl "https://www.googleapis.com/customsearch/v1?key=$GOOGLE_API_KEY&cx=$GOOGLE_CSE_ID&q=test"
```

3. **Check key format:**
- OpenAI: Starts with `sk-`
- Google: 39 characters, alphanumeric

4. **Regenerate keys if needed:**
- OpenAI: https://platform.openai.com/api-keys
- Google: https://console.cloud.google.com/apis/credentials

---

### Issue: MCP Configuration Not Found

**Symptom:**
```
❌ Failed to load MCP configuration
Error loading mcp.json: [Errno 2] No such file or directory
```

**Causes:**
- `mcp.json` file missing
- File in wrong location
- Incorrect file path

**Solutions:**

1. **Check file exists:**
```bash
ls examples/gaia/mcp.json
ls examples/gaia/agent_collections/search_agent/mcp.json
ls examples/gaia/agent_collections/pdf_agent/mcp.json
```

2. **Verify file contents:**
```bash
cat examples/gaia/mcp.json
# Should show valid JSON with mcpServers
```

3. **Check file permissions:**
```bash
ls -l examples/gaia/mcp.json
# Should be readable
```

4. **Recreate if missing:**
```json
{
  "mcpServers": {
    "search_agent": {
      "command": "python",
      "args": ["-m", "examples.gaia.agent_collections.search_agent.search_agent"],
      "env": {...}
    },
    "pdf_agent": {
      "command": "python",
      "args": ["-m", "examples.gaia.agent_collections.pdf_agent.pdf_agent"],
      "env": {...}
    }
  }
}
```

---

## Runtime Issues

### Issue: Agent Creation Fails

**Symptom:**
```
❌ Failed to create and execute search agent
Error: Agent creation failed
```

**Causes:**
- Invalid LLM configuration
- Network connectivity issues
- Insufficient permissions

**Solutions:**

1. **Check LLM configuration:**
```python
import os
print(f"Provider: {os.getenv('LLM_PROVIDER')}")
print(f"Model: {os.getenv('LLM_MODEL_NAME')}")
print(f"API Key: {os.getenv('LLM_API_KEY')[:10]}...")  # First 10 chars
```

2. **Test LLM connection:**
```python
from openai import OpenAI
client = OpenAI(api_key=os.getenv('LLM_API_KEY'))
response = client.chat.completions.create(
    model=os.getenv('LLM_MODEL_NAME'),
    messages=[{"role": "user", "content": "test"}]
)
print("LLM connection successful")
```

3. **Check network:**
```bash
ping api.openai.com
```

4. **Check logs:**
```bash
tail -f logs/AWorld-*.log
```

---

### Issue: Task Execution Times Out

**Symptom:**
```
⚠️ Task completed but no answer was generated
```
or agent stops responding

**Causes:**
- `max_steps` too low
- Task too complex
- Infinite reasoning loop

**Solutions:**

1. **Increase max_steps:**
```python
task = Task(
    id=uuid.uuid4().hex,
    input=task_prompt,
    agent=main_agent,
    conf=TaskConfig(max_steps=50),  # Increase from default
)
```

2. **Simplify task:**
```python
# Instead of:
"Find 5 papers, download all, compare them, and write detailed analysis"

# Try:
"Find 1 paper about attention mechanisms from arXiv 2020 and download it"
```

3. **Add explicit instructions:**
```python
task_prompt = """Find a paper on arXiv from 2020 about attention.
Steps to follow:
1. Search for papers
2. Select the first relevant result
3. Download the PDF
4. Return the file path
Do not spend more than 3 steps on searching."""
```

4. **Check if agent is making progress:**
```bash
# Watch logs in real-time
tail -f logs/Trace-*.log
```

---

### Issue: No Results from Search

**Symptom:**
```
Search completed but found no results
```

**Causes:**
- Search query too specific
- API quota exceeded
- Network issues
- Incorrect search parameters

**Solutions:**

1. **Broaden search query:**
```python
# Instead of:
"site:arxiv.org exact paper title from August 15, 2020"

# Try:
"site:arxiv.org attention mechanisms 2020"
```

2. **Check Google CSE quota:**
- Go to: https://console.cloud.google.com/apis/api/customsearch.googleapis.com
- Check quota usage (100 queries/day for free tier)

3. **Test search manually:**
```bash
curl "https://www.googleapis.com/customsearch/v1?key=$GOOGLE_API_KEY&cx=$GOOGLE_CSE_ID&q=test"
```

4. **Check CSE configuration:**
- Go to: https://programmablesearchengine.google.com/
- Ensure "Search the entire web" is enabled
- Verify CSE ID matches `GOOGLE_CSE_ID`

---

### Issue: File Download Fails

**Symptom:**
```
Failed to download file from URL
```
or
```
404 Not Found
```

**Causes:**
- Invalid URL
- File not accessible
- Network issues
- Workspace permissions

**Solutions:**

1. **Verify URL manually:**
```bash
curl -I https://arxiv.org/pdf/2004.12345
# Should return 200 OK
```

2. **Check workspace permissions:**
```bash
ls -ld $AWORLD_WORKSPACE
# Should be writable
```

3. **Test download manually:**
```bash
cd $AWORLD_WORKSPACE
wget https://arxiv.org/pdf/2004.12345.pdf
```

4. **Check disk space:**
```bash
df -h $AWORLD_WORKSPACE
```

---

### Issue: PDF Extraction Fails

**Symptom:**
```
Failed to extract content from PDF
```
or
```
Error: PDF is corrupted or protected
```

**Causes:**
- Corrupted PDF file
- Password-protected PDF
- Scanned document (needs OCR)
- Missing dependencies

**Solutions:**

1. **Verify PDF is valid:**
```bash
file paper.pdf
# Should show: PDF document
```

2. **Try to open PDF:**
```bash
# Linux
xdg-open paper.pdf

# Mac
open paper.pdf
```

3. **Check if scanned (use OCR):**
```python
# Use force_ocr parameter
pdf_agent.mcp_create_pdf_agent(
    task_prompt="Extract content from scanned.pdf with force_ocr=True"
)
```

4. **Install OCR dependencies:**
```bash
# Linux
apt-get install tesseract-ocr

# Mac
brew install tesseract
```

5. **Check PDF is not protected:**
```bash
pdfinfo paper.pdf | grep Encrypted
# Should show: Encrypted: no
```

---

## Agent Issues

### Issue: Agent Not Using Correct Tools

**Symptom:**
Agent tries to use tools it doesn't have access to, or doesn't use available tools

**Causes:**
- System prompt not clear
- Tool descriptions unclear
- Agent confused about capabilities

**Solutions:**

1. **Check agent's system prompt:**
```python
# Verify prompt includes tool descriptions
print(agent.system_prompt)
```

2. **Make instructions more explicit:**
```python
task_prompt = """You MUST use the search_agent.mcp_create_search_agent tool 
to find and download the paper. Do NOT try to search directly."""
```

3. **Check available tools:**
```python
# Query agent capabilities
main_agent.mcp_get_search_agent_capabilities()
main_agent.mcp_get_pdf_agent_capabilities()
```

4. **Verify MCP servers loaded:**
```python
print(agent.mcp_servers)
# Should show: ['search_agent', 'pdf_agent']
```

---

### Issue: Sub-Agent Returns Incomplete Results

**Symptom:**
Sub-agent completes but doesn't return expected information

**Causes:**
- Task prompt not specific enough
- Sub-agent's max_steps too low
- Sub-agent misunderstood task

**Solutions:**

1. **Be more specific in delegation:**
```python
# Instead of:
"Find a paper"

# Use:
"Find a paper on arXiv from August 2020 about attention mechanisms. 
Download the PDF file and return the complete file path in your answer."
```

2. **Increase sub-agent max_steps:**
```python
search_agent.mcp_create_search_agent(
    task_prompt="...",
    max_steps=20  # Increase from default 12
)
```

3. **Check sub-agent's response:**
```python
response = search_agent.mcp_create_search_agent(...)
print(response.metadata)  # Check what was returned
print(response.message)   # Check detailed message
```

---

### Issue: Agent Memory Not Persisting

**Symptom:**
Reused agent doesn't remember previous tasks

**Causes:**
- Creating new agent instead of reusing
- Agent ID not stored correctly
- Agent registry not working

**Solutions:**

1. **Store agent ID properly:**
```python
# First task - create agent
response1 = search_agent.mcp_create_search_agent(...)
agent_id = response1.metadata["agent_id"]
print(f"Created agent: {agent_id}")  # Save this!

# Second task - reuse agent
response2 = search_agent.mcp_use_existing_search_agent(
    agent_id=agent_id,  # Use saved ID
    task_prompt="..."
)
```

2. **Verify agent exists:**
```python
# Check if agent_id is valid
if not agent_registry.exists(agent_id):
    print(f"Agent {agent_id} not found")
```

3. **List registered agents:**
```python
agents = agent_registry.list_agents()
for agent in agents:
    print(f"{agent.agent_id}: {agent.name}")
```

---

## Tool Issues

### Issue: Google Search API Quota Exceeded

**Symptom:**
```
Error: API quota exceeded
```
or
```
429 Too Many Requests
```

**Causes:**
- Free tier limit reached (100 queries/day)
- Too many search requests

**Solutions:**

1. **Check quota usage:**
- Go to: https://console.cloud.google.com/apis/api/customsearch.googleapis.com/quotas

2. **Reduce number of searches:**
```python
# Use fewer, more targeted searches
# Cache search results
# Combine multiple queries
```

3. **Upgrade to paid tier:**
- Google Custom Search: $5 per 1000 queries

4. **Wait for quota reset:**
- Free quota resets daily at midnight Pacific Time

---

### Issue: Downloaded File Not Found

**Symptom:**
```
FileNotFoundError: File not found: /path/to/file.pdf
```

**Causes:**
- Download failed silently
- File saved to different location
- Incorrect file path

**Solutions:**

1. **List workspace files:**
```bash
ls -la $AWORLD_WORKSPACE
```

2. **Check download location:**
```python
print(f"Workspace: {os.getenv('AWORLD_WORKSPACE')}")
```

3. **Use absolute paths:**
```python
from pathlib import Path
workspace = Path(os.getenv('AWORLD_WORKSPACE')).expanduser()
file_path = workspace / "paper.pdf"
print(f"Looking for: {file_path}")
```

4. **Check download response:**
```python
response = download.mcp_download_file(url="...", output_file_path="paper.pdf")
print(response.metadata)  # Should include actual file path
```

---

## Performance Issues

### Issue: Slow Execution

**Symptom:**
Tasks take very long to complete

**Causes:**
- Large context window
- Too many reasoning steps
- Slow LLM model
- Network latency

**Solutions:**

1. **Use faster model:**
```bash
# Instead of:
LLM_MODEL_NAME=gpt-4o

# Try:
LLM_MODEL_NAME=gpt-4o-mini  # Faster, cheaper
```

2. **Reduce max_steps:**
```python
TaskConfig(max_steps=15)  # Instead of 50
```

3. **Cache results:**
```python
# Reuse agents to maintain context
# Cache common searches
```

4. **Optimize prompts:**
```python
# Be more direct and specific
# Reduce unnecessary verbosity
```

---

### Issue: High Token Usage

**Symptom:**
Unexpected high API costs

**Causes:**
- Large system prompts
- Too many LLM calls
- Inefficient reasoning loops

**Solutions:**

1. **Monitor token usage:**
```python
# Enable token counting
# Check LLM API dashboard
```

2. **Optimize system prompts:**
```python
# Remove unnecessary examples
# Use concise language
# Focus on essential instructions
```

3. **Reuse agents:**
```python
# Instead of creating new agents for each task
# Reuse existing agents to maintain context
```

4. **Use smaller models for sub-agents:**
```bash
# Sub-agents can use cheaper models
LLM_MODEL_NAME=gpt-4o-mini
```

---

## Debug Techniques

### 1. Enable Debug Logging

```python
import logging

# Set logging level
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
```

### 2. Inspect Agent State

```python
# Check agent configuration
print(f"Agent ID: {agent.agent_id}")
print(f"Agent Name: {agent.name}")
print(f"System Prompt: {agent.system_prompt[:100]}...")
print(f"MCP Servers: {agent.mcp_servers}")

# Check task configuration
print(f"Task ID: {task.id}")
print(f"Max Steps: {task.conf.max_steps}")
```

### 3. Monitor Logs in Real-Time

```bash
# Terminal 1: Watch application logs
tail -f logs/AWorld-*.log

# Terminal 2: Watch trace logs
tail -f logs/Trace-*.log

# Terminal 3: Run your script
python -m examples.gaia.agent_collections.example_usage
```

### 4. Use Breakpoints

```python
# Add breakpoint before agent call
import pdb; pdb.set_trace()

# Or use debugger in IDE
breakpoint()
```

### 5. Test Components Individually

```python
# Test LLM connection
from openai import OpenAI
client = OpenAI(api_key=os.getenv('LLM_API_KEY'))
response = client.chat.completions.create(
    model="gpt-4o",
    messages=[{"role": "user", "content": "test"}]
)
print(response.choices[0].message.content)

# Test search
from examples.gaia.agent_collections.search_agent.mcp_tools.search import SearchCollection
search = SearchCollection(...)
result = search.mcp_search_google(query="test")
print(result)

# Test PDF extraction
from examples.gaia.agent_collections.pdf_agent.mcp_tools.pdf import PDFCollection
pdf = PDFCollection(...)
result = pdf.mcp_extract_document_content(file_path="test.pdf")
print(result)
```

### 6. Validate Configuration

```python
def validate_config():
    """Validate all configuration before running."""
    required_vars = [
        'LLM_API_KEY',
        'LLM_PROVIDER',
        'LLM_MODEL_NAME',
        'GOOGLE_API_KEY',
        'GOOGLE_CSE_ID',
        'AWORLD_WORKSPACE'
    ]
    
    missing = []
    for var in required_vars:
        if not os.getenv(var):
            missing.append(var)
    
    if missing:
        raise ValueError(f"Missing required environment variables: {missing}")
    
    # Check workspace exists
    workspace = Path(os.getenv('AWORLD_WORKSPACE'))
    if not workspace.exists():
        raise ValueError(f"Workspace does not exist: {workspace}")
    
    print("✅ Configuration valid")

validate_config()
```

### 7. Simplified Test Case

```python
def test_basic_workflow():
    """Minimal test case to isolate issues."""
    from dotenv import load_dotenv
    load_dotenv()
    
    # Test 1: Load config
    print("Test 1: Loading MCP config...")
    mcp_config = load_mcp_config()
    assert mcp_config, "MCP config failed to load"
    print("✅ MCP config loaded")
    
    # Test 2: Create agent
    print("Test 2: Creating main agent...")
    main_agent = create_main_agent(mcp_config)
    assert main_agent, "Main agent creation failed"
    print("✅ Main agent created")
    
    # Test 3: Simple task
    print("Test 3: Running simple task...")
    task = Task(
        id=uuid.uuid4().hex,
        input="Check search agent capabilities",
        agent=main_agent,
        conf=TaskConfig(max_steps=5)
    )
    results = Runners.sync_run_task(task=task)
    assert results, "Task execution failed"
    print("✅ Task completed")
    
    print("\n✅ All tests passed!")

test_basic_workflow()
```

---

## Getting Help

If you're still stuck after trying these solutions:

### 1. Check Documentation
- Main README: `agent_collections/README.md`
- Architecture: `agent_collections/ARCHITECTURE.md`
- Quick Start: `agent_collections/QUICK_START.md`

### 2. Review Examples
- Example workflows: `example_usage.py`
- Agent-specific examples: `{agent}/example_usage.py`

### 3. Check Logs
```bash
# Application logs
cat logs/AWorld-*.log

# Trace logs (detailed execution)
cat logs/Trace-*.log

# Search for errors
grep -i error logs/*.log
```

### 4. Create Minimal Reproducible Example

```python
"""
Minimal example that reproduces the issue.
Include:
- Exact error message
- Configuration used
- Steps to reproduce
"""
```

### 5. Report Issue

Include:
- Error message and stack trace
- Configuration (without API keys)
- Steps to reproduce
- Environment details (OS, Python version)
- Logs (relevant sections)

---

## Common Error Messages and Solutions

| Error Message | Cause | Solution |
|--------------|-------|----------|
| `ModuleNotFoundError: No module named 'aworld'` | Wrong directory or dependencies missing | Run from project root, install dependencies |
| `Missing required environment variables` | `.env` not configured | Create `.env` with required variables |
| `401 Unauthorized` | Invalid API key | Verify and update API keys |
| `429 Too Many Requests` | API quota exceeded | Wait or upgrade quota |
| `FileNotFoundError` | File not found | Check file path and workspace |
| `Failed to load MCP configuration` | `mcp.json` missing | Verify file exists and is valid JSON |
| `Agent creation failed` | LLM connection issue | Check API key and network |
| `PDF extraction failed` | Corrupted or protected PDF | Verify PDF, try OCR |
| `Task completed but no answer` | Task timeout or max_steps reached | Increase max_steps or simplify task |

---

## Prevention Best Practices

1. **Always validate configuration first:**
   ```python
   validate_config()
   ```

2. **Use try-catch blocks:**
   ```python
   try:
       result = agent.execute(task)
   except Exception as e:
       logger.error(f"Error: {e}")
       # Handle gracefully
   ```

3. **Start with simple tasks:**
   - Test each component individually
   - Gradually increase complexity

4. **Monitor resources:**
   - Check API quotas regularly
   - Monitor disk space
   - Track token usage

5. **Keep logs:**
   - Don't delete logs immediately
   - Review logs after each run
   - Archive important logs

6. **Use version control:**
   - Track configuration changes
   - Document what works
   - Revert if needed

---

This troubleshooting guide should help you resolve most common issues. Remember: start simple, test incrementally, and check logs frequently!

