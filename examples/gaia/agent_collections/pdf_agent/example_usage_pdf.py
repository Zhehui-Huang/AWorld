"""
Example Usage of PDF Agent MCP Server

This script demonstrates how to use the PDF Agent MCP Server
to create dynamic multi-layer agent architectures for PDF processing.

Tests included:
- Example 1: Basic PDF processing with text extraction
- Example 2: PDF processing with image extraction
- Example 3: Direct usage (without MCP protocol)
- Example 4: Check service capabilities

The script automatically tests all MCP tools available to the pdf agent:
1. mcp_extract_document_content: Extract text and images from PDF documents
2. mcp_extract_text_ocr: Extract text from images using OCR
3. mcp_get_image_metadata: Extract technical metadata from images
"""

import json
import os
import sys
from pathlib import Path

from dotenv import load_dotenv

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent.parent))

from aworld.agents.llm_agent import Agent
from aworld.config.conf import AgentConfig, TaskConfig
from aworld.core.task import Task
from aworld.runner import Runners
from examples.gaia.agent_collections.pdf_agent.prompt import system_prompt


def example_1_basic_pdf_processing():
    """Example 1: Create a new PDF agent and extract text from a PDF."""
    print("\n" + "=" * 80)
    print("Example 1: Basic PDF Processing - Text Extraction")
    print("=" * 80)

    # Load the main agent's MCP configuration
    mcp_config_path = Path(__file__).parent / "mcp.json"
    with open(mcp_config_path, "r") as f:
        mcp_config = json.load(f)

    # Create main agent with pdf_agent MCP server
    main_agent_config = AgentConfig(
        llm_provider=os.getenv("LLM_PROVIDER", "openai"),
        llm_model_name=os.getenv("LLM_MODEL_NAME", "gpt-4o"),
        llm_base_url=os.getenv("LLM_BASE_URL"),
        llm_api_key=os.getenv("LLM_API_KEY"),
        llm_temperature=0.0,
    )

    main_agent = Agent(
        conf=main_agent_config,
        name="main_agent",
        system_prompt=system_prompt,
        mcp_config=mcp_config,
        mcp_servers=["pdf", "image"],
    )

    # Get absolute path to the sample PDF
    pdf_path = str(Path(__file__).parent / "2207.01510.pdf")
    
    # Task that requires PDF processing
    task_prompt = f"""
    There is a section about pros and cons in {pdf_path}. Please extract the content of that section.
    """

    task = Task(
        id="example_1",
        input=task_prompt,
        agent=main_agent,
        conf=TaskConfig(max_steps=12),
    )

    print("\n🚀 Executing task with main agent...")
    result_map = Runners.sync_run_task(task=task)
    result = result_map.get(task.id)

    if result and result.answer:
        print("\n✅ Task completed!")
        print(f"\nAnswer:\n{result.answer}")
    else:
        print("\n⚠️ Task completed but no answer was generated")

def main():
    """Run all examples."""
    load_dotenv()

    print("\n" + "=" * 80)
    print("PDF Agent MCP Server - Example Usage")
    print("=" * 80)

    # Check environment
    required_vars = ["LLM_PROVIDER", "LLM_MODEL_NAME", "LLM_API_KEY"]
    missing_vars = [var for var in required_vars if not os.getenv(var)]

    if missing_vars:
        print(f"\n⚠️ Warning: Missing environment variables: {missing_vars}")
        print("Some examples may fail. Please configure your .env file.")

    # Check if sample PDF exists
    pdf_path = Path(__file__).parent / "2207.01510.pdf"
    if not pdf_path.exists():
        print(f"\n❌ Error: Sample PDF not found at {pdf_path}")
        print("Please ensure 2207.01510v1.pdf is in the same directory as this script.")
        return

    print(f"\n✅ Found sample PDF at: {pdf_path}")

    print("\nAvailable Examples:")
    print("1. Basic PDF processing - Text extraction")
    print("2. PDF processing with image extraction")
    print("3. Direct usage (without MCP protocol)")
    print("4. Check service capabilities")
    print("5. Page range extraction")

    # Run examples
    try:
        print("\n" + "=" * 80)
        print("Starting Examples")
        print("=" * 80)

        # Run Example 3: Direct usage (most self-contained)
        # example_3_direct_usage()

        # Uncomment to run other examples
        example_1_basic_pdf_processing()
        # example_2_pdf_with_images()
        # example_4_capabilities_check()
        # example_5_page_range_extraction()

    except KeyboardInterrupt:
        print("\n\n👋 Interrupted by user")
    except Exception as e:
        print(f"\n\n❌ Error: {e}")
        import traceback

        traceback.print_exc()


if __name__ == "__main__":
    main()

