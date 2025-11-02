"""
Example Usage of Image Agent MCP Server

This script demonstrates how to use the Image Agent MCP Server
to create dynamic multi-layer agent architectures for image processing.

Tests included:
- Example 1: Basic usage patterns (create, reuse, hierarchical, capabilities, direct usage)

The script automatically tests all MCP tools available to the image agent:
1. mcp_get_image_metadata: Extract technical metadata (dimensions, format, size, etc.)
2. mcp_extract_text_ocr: Extract text from images using Tesseract OCR with preprocessing
3. mcp_analyze_image_ai: AI-powered image analysis using vision models
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
from examples.gaia.agent_collections.image_agent.prompt import system_prompt



def example_1_create_image_agent():
    """Example 1: Create a new image agent and execute a task."""
    print("\n" + "=" * 80)
    print("Example 1: Creating a New Image Agent")
    print("=" * 80)

    # Load the main agent's MCP configuration
    mcp_config_path = Path(__file__).parent / "mcp.json"
    with open(mcp_config_path, "r") as f:
        mcp_config = json.load(f)

    # Create main agent with image_agent MCP server
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
        mcp_servers=["image"],
    )

    # Get absolute path to image_0.png
    image_path = str(Path(__file__).parent / "image_0.png")
    
    # Task that requires image processing
    task_prompt = f"""
    I need to analyze the image at path: {image_path}
    Please extract all axis labels. The image contains three axes, and each axis has label words at both ends. I need you to identify and list all six labels (two labels per axis).
    """

    task = Task(
        id="example_1",
        input=task_prompt,
        agent=main_agent,
        conf=TaskConfig(max_steps=10),  # Allow more steps for multiple MCP tool calls
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
    print("Image Agent MCP Server - Comprehensive Testing with image_0.png")
    print("=" * 80)

    # Check environment
    required_vars = ["LLM_PROVIDER", "LLM_MODEL_NAME", "LLM_API_KEY"]
    missing_vars = [var for var in required_vars if not os.getenv(var)]

    if missing_vars:
        print(f"\n⚠️ Warning: Missing environment variables: {missing_vars}")
        print("Some examples may fail. Please configure your .env file.")

    # Check if image_0.png exists
    image_path = Path(__file__).parent / "image_0.png"
    if not image_path.exists():
        print(f"\n❌ Error: image_0.png not found at {image_path}")
        print("Please ensure image_0.png is in the same directory as this script.")
        return

    print(f"\n✅ Found image_0.png at: {image_path}")

    print("\nAvailable Examples:")
    print("1. Create a new image agent")

    # Run examples
    try:
        print("\n" + "=" * 80)
        print("Starting Comprehensive Tests")
        print("=" * 80)

        # Run Example 1: Create and test image agent with image_0.png
        example_1_create_image_agent()

    except KeyboardInterrupt:
        print("\n\n👋 Interrupted by user")
    except Exception as e:
        print(f"\n\n❌ Error: {e}")
        import traceback

        traceback.print_exc()


if __name__ == "__main__":
    main()
