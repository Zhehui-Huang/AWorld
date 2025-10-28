# PDF Agent Quick Start Guide

Get started with the PDF Agent in 5 minutes!

## 1. Installation

```bash
# Install required dependencies
pip install marker-pdf pydantic python-dotenv

# Install AWorld framework (from project root)
pip install -e .
```

## 2. Environment Setup

Create a `.env` file in your project root:

```bash
# Required
LLM_API_KEY=your_openai_api_key_here

# Optional
LLM_PROVIDER=openai
LLM_MODEL_NAME=gpt-4o
LLM_TEMPERATURE=0.0
AWORLD_WORKSPACE=~/workspace
```

## 3. Basic Usage

### Option A: Standalone Script

```python
from dotenv import load_dotenv
from examples.gaia.agent_collections.pdf_agent.pdf_agent import PDFAgentCollection
from examples.gaia.mcp_collections.base import ActionArguments

# Load environment
load_dotenv()

# Initialize service
args = ActionArguments(
    name="pdf_agent_service",
    transport="stdio",
    workspace="~/workspace"
)

service = PDFAgentCollection(args)

# Create agent and process PDF
result = service.mcp_create_pdf_agent(
    task_prompt="Extract the title from '/path/to/document.pdf'",
    name="pdf_extractor",
    description="Extract PDF content",
    max_steps=10
)

print(f"Success: {result.success}")
print(f"Answer: {result.metadata.get('answer')}")
```

### Option B: Run as MCP Server

```bash
python -m examples.gaia.agent_collections.pdf_agent.pdf_agent
```

### Option C: Use Example Scripts

```bash
# Run the example usage script
python examples/gaia/agent_collections/pdf_agent/example_usage.py
```

## 4. Common Use Cases

### Extract Text from PDF

```python
task = "Extract all text content from '/workspace/report.pdf'"

result = service.mcp_create_pdf_agent(
    task_prompt=task,
    name="text_extractor",
    max_steps=8
)
```

### Extract Specific Pages

```python
task = "Extract content from pages 5-10 of '/workspace/document.pdf'"

result = service.mcp_create_pdf_agent(
    task_prompt=task,
    name="page_extractor",
    max_steps=10
)
```

### Process Scanned PDF with OCR

```python
task = """
Process the scanned document at '/workspace/scanned.pdf'.
Use OCR to extract text. What is the date mentioned?
"""

result = service.mcp_create_pdf_agent(
    task_prompt=task,
    name="ocr_processor",
    max_steps=12
)
```

### Extract Text and Images

```python
task = """
Extract both text and images from '/workspace/report.pdf'.
Describe the charts shown in the document.
"""

result = service.mcp_create_pdf_agent(
    task_prompt=task,
    name="image_extractor",
    max_steps=15
)
```

## 5. Reusing Agents

Create an agent once and reuse it for multiple tasks:

```python
# First task
result1 = service.mcp_create_pdf_agent(
    task_prompt="Extract table of contents from '/workspace/book.pdf'",
    name="book_analyzer",
    max_steps=10
)

agent_id = result1.metadata['agent_id']

# Second task - reuse the same agent
result2 = service.mcp_use_existing_pdf_agent(
    agent_id=agent_id,
    task_prompt="Now extract the references section",
    max_steps=8
)
```

## 6. Integration with Parent Agent

Add to your parent agent's `mcp.json`:

```json
{
  "mcpServers": {
    "pdf_agent": {
      "command": "python",
      "args": [
        "-m",
        "examples.gaia.agent_collections.pdf_agent.pdf_agent"
      ],
      "env": {},
      "client_session_timeout_seconds": 9999.0
    }
  }
}
```

Then your parent agent can call:

```python
# Parent agent automatically delegates PDF tasks
result = pdf_agent.mcp_create_pdf_agent(
    task_prompt="Extract key findings from the PDF",
    max_steps=12
)
```

## 7. Available Tools

The PDF agent uses these MCP tools:

- `pdf.mcp_extract_document_content()` - Extract text and images from PDFs
- `pdf.mcp_list_supported_formats()` - List supported document formats

## 8. Task Prompt Examples

### Simple Extraction
```python
"Extract all text from '/path/to/document.pdf'"
```

### Specific Information
```python
"What is the publication date in '/path/to/paper.pdf'?"
```

### Multi-Step Analysis
```python
"""
Analyze '/path/to/research.pdf':
1. Extract the abstract
2. List all figures
3. What are the conclusions?
"""
```

### With Special Requirements
```python
"""
Process '/path/to/scanned.pdf' using OCR.
Extract content from pages 10-20 only.
Save the extracted text to a file.
"""
```

## 9. Troubleshooting

### Issue: "File not found"
- Use absolute paths or paths relative to AWORLD_WORKSPACE
- Check file permissions

### Issue: Poor text quality
- Add "use OCR" or "force OCR" to your task prompt
- The agent will automatically use `force_ocr=True`

### Issue: Long processing time
- Specify page ranges in your prompt: "extract pages 5-10"
- Reduce `max_steps` for simpler tasks

### Issue: Out of memory
- Process large PDFs in smaller page ranges
- Ask agent to save extracted text to file

## 10. Next Steps

- Read the full [README.md](README.md) for detailed documentation
- Check [example_usage.py](example_usage.py) for more examples
- Explore the [MCP tools documentation](mcp_tools/pdf.py)
- See [ARCHITECTURE.md](../../search_agent/ARCHITECTURE.md) for system design (similar pattern)

## Tips for Best Results

1. **Be specific**: "Extract the title from page 1" is better than "extract something"
2. **Mention OCR**: For scanned docs, say "use OCR" in your prompt
3. **Specify pages**: For large PDFs, mention specific page ranges
4. **Request images**: Say "extract images" or "include charts" when needed
5. **Reuse agents**: For related tasks, reuse the same agent to maintain context

## Quick Reference

| Task Type | Recommended max_steps | Special Notes |
|-----------|----------------------|---------------|
| Simple text extraction | 8-10 | Standard PDFs |
| Scanned PDF (OCR) | 12-15 | Mention "OCR" in prompt |
| Large documents | 15-20 | Use page ranges |
| Multi-step analysis | 20-25 | Break into sub-tasks |

## Support

For issues or questions:
1. Check the full [README.md](README.md)
2. Review [example_usage.py](example_usage.py)
3. See the main AWorld documentation

Happy PDF processing! 📄✨

