# PDF Agent MCP Server

A comprehensive PDF document processing agent that can extract, analyze, and answer questions from PDF documents using the marker package for high-quality text extraction.

## Features

- **Text Extraction**: Extract text content from PDF documents with proper formatting
- **Image Extraction**: Extract images, charts, and diagrams from PDFs
- **OCR Support**: Process scanned PDFs using OCR for text recognition
- **Page-Specific Processing**: Extract content from specific pages or page ranges
- **Multiple Output Formats**: Support for markdown, JSON, and HTML output formats
- **Agent Persistence**: Create agents that can be reused across multiple tasks
- **LLM Integration**: Optimized for LLM consumption with structured output

## Architecture

The PDF Agent follows a multi-layer architecture:

```
┌─────────────────────────────────────────────┐
│         Parent/Coordinator Agent            │
│    (receives tasks from higher level)       │
└──────────────────┬──────────────────────────┘
                   │
                   │ delegates PDF tasks
                   ▼
┌─────────────────────────────────────────────┐
│          PDF Agent (this service)           │
│  - Independent LLM instance                 │
│  - Dedicated memory module                  │
│  - PDF-specific tools (MCP)                 │
└──────────────────┬──────────────────────────┘
                   │
                   │ uses MCP tools
                   ▼
┌─────────────────────────────────────────────┐
│       PDF Processing MCP Tools              │
│  - mcp_extract_document_content             │
│  - mcp_list_supported_formats               │
└─────────────────────────────────────────────┘
```

## Installation

### Prerequisites

```bash
# Install required packages
pip install marker-pdf pydantic python-dotenv

# For the parent framework
pip install -e .  # from the AWorld root directory
```

### Environment Variables

Create a `.env` file with the following variables:

```bash
# Required
LLM_API_KEY=your_api_key_here

# Optional (with defaults)
LLM_PROVIDER=openai  # default: openai
LLM_MODEL_NAME=gpt-4o  # default: gpt-4o
LLM_BASE_URL=  # optional, for custom endpoints
LLM_TEMPERATURE=0.0  # default: 0.0
AWORLD_WORKSPACE=~/workspace  # default: ~
```

## Usage

### 1. As a Standalone MCP Server

Run the PDF agent as a standalone MCP server:

```bash
python -m examples.gaia.agent_collections.pdf_agent.pdf_agent
```

### 2. Programmatic Usage

#### Create a PDF Agent

```python
from examples.gaia.agent_collections.pdf_agent.pdf_agent import PDFAgentCollection
from examples.gaia.mcp_collections.base import ActionArguments

# Initialize service
args = ActionArguments(
    name="pdf_agent_service",
    transport="stdio",
    workspace="~/workspace"
)

service = PDFAgentCollection(args)

# Create agent and execute task
result = service.mcp_create_pdf_agent(
    task_prompt="Extract the title and abstract from '/path/to/paper.pdf'",
    name="pdf_extractor",
    description="Agent for extracting PDF content",
    max_steps=10
)

print(f"Answer: {result.metadata['answer']}")
print(f"Agent ID: {result.metadata['agent_id']}")
```

#### Reuse Existing Agent

```python
# Reuse the agent for another task
result = service.mcp_use_existing_pdf_agent(
    agent_id="pdf_agent_abc123",
    task_prompt="What are the main conclusions in the same document?",
    max_steps=8
)

print(f"Answer: {result.metadata['answer']}")
```

### 3. Integration with Parent Agent

Configure the parent agent to use PDF agent via MCP:

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

Then the parent agent can delegate PDF tasks:

```python
# Parent agent calls:
result = pdf_agent.mcp_create_pdf_agent(
    task_prompt="Extract key information from the PDF report",
    name="report_processor",
    max_steps=15
)
```

## Available Tools

The PDF agent has access to the following MCP tools:

### 1. `mcp_extract_document_content`

Extract text and images from PDF documents.

**Parameters:**
- `file_path` (str): Path to the PDF file
- `output_format` (str): Output format - "markdown", "json", or "html" (default: "markdown")
- `extract_images` (bool): Whether to extract images (default: True)
- `save_extracted_text_to_file` (bool): Save extracted text to a file (default: False)
- `page_range` (str | None): Specific pages to process, e.g., "0,5-10,20" (default: None)
- `force_ocr` (bool): Force OCR processing for scanned documents (default: False)
- `format_lines` (bool): Reformat lines using OCR model (default: False)

**Example:**
```python
result = pdf_tool.mcp_extract_document_content(
    file_path="/path/to/document.pdf",
    output_format="markdown",
    extract_images=True,
    page_range="5-10"
)
```

### 2. `mcp_list_supported_formats`

List all supported document formats.

**Example:**
```python
result = pdf_tool.mcp_list_supported_formats()
```

## Agent Methods

### `mcp_create_pdf_agent`

Create a new PDF agent and execute a task.

**Parameters:**
- `task_prompt` (str): The task or query for the agent to process
- `name` (str): Name for the agent (default: "pdf_agent")
- `description` (str): Description of the agent's purpose (default: "PDF agent specialized in pdf processing")
- `max_steps` (int): Maximum execution steps (default: 12)

**Returns:** `ActionResponse` with execution results and agent metadata

### `mcp_use_existing_pdf_agent`

Use an existing PDF agent to execute a task.

**Parameters:**
- `agent_id` (str): ID of the existing PDF agent
- `task_prompt` (str): The task or query to process
- `max_steps` (int): Maximum execution steps (default: 12)

**Returns:** `ActionResponse` with execution results

### `mcp_get_pdf_agent_capabilities`

Get information about the PDF agent service capabilities.

**Returns:** `ActionResponse` with service capabilities and configuration

## Examples

### Example 1: Basic PDF Text Extraction

```python
task = "Extract all text from '/workspace/report.pdf' and summarize the key points"

result = service.mcp_create_pdf_agent(
    task_prompt=task,
    name="text_extractor",
    max_steps=10
)
```

### Example 2: Extract Specific Pages with Images

```python
task = """
Process pages 10-15 of '/workspace/research_paper.pdf'.
Extract both text and images. What charts are shown in these pages?
"""

result = service.mcp_create_pdf_agent(
    task_prompt=task,
    name="page_analyzer",
    max_steps=12
)
```

### Example 3: OCR Processing for Scanned Documents

```python
task = """
Process the scanned document at '/workspace/scanned.pdf'.
Use OCR to extract the text. What is the document date?
"""

result = service.mcp_create_pdf_agent(
    task_prompt=task,
    name="ocr_processor",
    max_steps=15
)
```

### Example 4: Multi-Task Processing with Agent Reuse

```python
# First task
result1 = service.mcp_create_pdf_agent(
    task_prompt="Extract the table of contents from '/workspace/book.pdf'",
    name="book_analyzer",
    max_steps=10
)

agent_id = result1.metadata['agent_id']

# Reuse for second task
result2 = service.mcp_use_existing_pdf_agent(
    agent_id=agent_id,
    task_prompt="Now extract the index from the same document",
    max_steps=8
)
```

## Configuration

### Agent Configuration

Agents are configured via environment variables:

- **LLM Provider**: Configurable via `LLM_PROVIDER` (openai, anthropic, etc.)
- **Model**: Configurable via `LLM_MODEL_NAME`
- **Temperature**: Configurable via `LLM_TEMPERATURE` (0.0 for deterministic)
- **Workspace**: Configurable via `AWORLD_WORKSPACE`

### MCP Tools Configuration

The MCP tools are configured in `mcp.json`:

```json
{
  "mcpServers": {
    "pdf": {
      "command": "python",
      "args": [
        "-m",
        "examples.gaia.agent_collections.pdf_agent.mcp_tools.pdf"
      ],
      "env": {},
      "client_session_timeout_seconds": 9999.0
    }
  }
}
```

## Workflow

The PDF agent follows this workflow:

1. **Plan**: Understand the task and identify which PDF documents need processing
2. **Extract**: Use `mcp_extract_document_content` to extract text and images
3. **Analyze**: Carefully read the extracted content
4. **Process**: Handle specific requirements (OCR, page ranges, images, etc.)
5. **Answer**: Provide accurate answers based on extracted content

## Output Format

The agent returns structured responses in `ActionResponse` format:

```python
{
    "success": True,
    "message": "Formatted result message",
    "metadata": {
        "agent_id": "pdf_agent_abc123",
        "agent_name": "pdf_extractor",
        "answer": "The extracted answer",
        "task_prompt": "Original task",
        "created_at": "2025-01-15 10:30:00",
        "llm_provider": "openai",
        "llm_model_name": "gpt-4o",
        "mcp_servers": ["pdf"]
    }
}
```

## Best Practices

1. **Use Page Ranges**: For large PDFs, specify page ranges to extract only relevant sections
2. **Enable OCR**: For scanned documents or poor-quality PDFs, use `force_ocr=True`
3. **Extract Images**: Enable image extraction when charts, diagrams, or visual information is important
4. **Save Long Text**: Use `save_extracted_text_to_file=True` for very long documents
5. **Reuse Agents**: For multiple related tasks, reuse the same agent to maintain context
6. **Appropriate Max Steps**: Set realistic `max_steps` based on task complexity

## Troubleshooting

### Common Issues

1. **"File not found" error**
   - Ensure the file path is absolute or relative to the workspace
   - Check file permissions

2. **Poor text extraction quality**
   - Try using `force_ocr=True` for scanned documents
   - Use `format_lines=True` to improve line formatting

3. **Agent timeout**
   - Increase `max_steps` for complex tasks
   - Process large PDFs in smaller page ranges

4. **Memory issues with large PDFs**
   - Extract specific page ranges instead of entire document
   - Use `save_extracted_text_to_file=True` to save content

## Dependencies

- `marker-pdf`: PDF content extraction with OCR support
- `pydantic`: Data validation and settings management
- `python-dotenv`: Environment variable management
- `aworld`: Parent framework for agent orchestration

## License

This project is part of the AWorld framework.

## Contributing

When contributing to the PDF agent:

1. Follow the existing code structure
2. Add tests for new features
3. Update documentation
4. Ensure compatibility with the MCP protocol
5. Test with various PDF types (text, scanned, mixed)

## Related Documentation

- [AWorld Framework](../../../../README.md)
- [Search Agent](../search_agent/README.md)
- [MCP Collections](../../../mcp_collections/README.md)
- [Marker PDF Documentation](https://github.com/VikParuchuri/marker)

