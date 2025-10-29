"""
Example Usage of Image Agent MCP Server

This script demonstrates how to use the Image Agent MCP Server
to create dynamic multi-layer agent architectures for image processing.
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


def example_1_create_image_agent():
    """Example 1: Create a new image agent and execute a task."""
    print("\n" + "=" * 80)
    print("Example 1: Creating a New Image Agent")
    print("=" * 80)

    # Load the main agent's MCP configuration
    mcp_config_path = Path(__file__).parent.parent.parent.parent / "gaia" / "mcp.json"
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
        system_prompt="You are a helpful assistant that can delegate image processing tasks to specialized agents.",
        mcp_config=mcp_config,
        mcp_servers=["image_agent"],
    )

    # Task that requires image processing
    task_prompt = """
    I need to extract text from an image document and analyze its content.
    Use the image agent to process the image.
    
    Call image_agent.mcp_create_image_agent with:
    - task_prompt: "Extract text from document.png and provide AI analysis of the content"
    - name: "document_analyzer"
    - description: "Agent specialized in document image processing"
    """

    task = Task(
        id="example_1",
        input=task_prompt,
        agent=main_agent,
        conf=TaskConfig(max_steps=5),
    )

    print("\n🚀 Executing task with main agent...")
    result_map = Runners.sync_run_task(task=task)
    result = result_map.get(task.id)

    if result and result.answer:
        print("\n✅ Task completed!")
        print(f"\nAnswer:\n{result.answer}")
    else:
        print("\n⚠️ Task completed but no answer was generated")


def example_2_reuse_image_agent():
    """Example 2: Reuse an existing image agent for multiple tasks."""
    print("\n" + "=" * 80)
    print("Example 2: Reusing an Existing Image Agent")
    print("=" * 80)

    # This example requires an agent_id from example_1
    # In practice, you would store the agent_id from the first call
    agent_id = "image_agent_abc12345"  # Replace with actual agent_id

    print(f"\n🔄 Attempting to reuse agent: {agent_id}")
    print("Note: This will fail if the agent doesn't exist.")
    print("Run example_1 first to create an agent, then use its ID here.")


def example_3_hierarchical_agents():
    """Example 3: Create a hierarchical agent structure."""
    print("\n" + "=" * 80)
    print("Example 3: Hierarchical Agent Structure")
    print("=" * 80)

    print("\nArchitecture:")
    print("Main Agent")
    print("  └─> Document Processor (Sub-Main Agent)")
    print("      ├─> Image Agent (for OCR and analysis)")
    print("      └─> Summary Agent (for consolidating results)")

    # This demonstrates the concept
    # In practice, you would implement this with actual agent delegation

    workflow_description = """
    1. Main Agent receives: "Process and analyze 3 document images"
    
    2. Main Agent creates Document Processor:
       - Specialized in coordinating image processing tasks
       - Has access to both image and summary agents
    
    3. Document Processor creates Image Agent:
       - Task: "Extract text and analyze content from document1.png, document2.png, document3.png"
       - Agent autonomously processes each image
    
    4. Document Processor creates Summary Agent:
       - Task: "Summarize findings from all documents"
       - Agent consolidates and summarizes
    
    5. Results flow back up:
       Summary Agent -> Document Processor -> Main Agent -> User
    """

    print(workflow_description)


def example_4_capabilities_check():
    """Example 4: Check image agent service capabilities."""
    print("\n" + "=" * 80)
    print("Example 4: Checking Service Capabilities")
    print("=" * 80)

    # Load MCP configuration
    mcp_config_path = Path(__file__).parent.parent.parent.parent / "gaia" / "mcp.json"
    with open(mcp_config_path, "r") as f:
        mcp_config = json.load(f)

    # Create agent
    agent_config = AgentConfig(
        llm_provider=os.getenv("LLM_PROVIDER", "openai"),
        llm_model_name=os.getenv("LLM_MODEL_NAME", "gpt-4o"),
        llm_base_url=os.getenv("LLM_BASE_URL"),
        llm_api_key=os.getenv("LLM_API_KEY"),
    )

    agent = Agent(
        conf=agent_config,
        name="capability_checker",
        system_prompt="Get capabilities of the image agent service.",
        mcp_config=mcp_config,
        mcp_servers=["image_agent"],
    )

    task_prompt = "Call image_agent.mcp_get_image_agent_capabilities to see what this service can do."

    task = Task(
        id="example_4",
        input=task_prompt,
        agent=agent,
        conf=TaskConfig(max_steps=2),
    )

    print("\n🔍 Checking capabilities...")
    result_map = Runners.sync_run_task(task=task)
    result = result_map.get(task.id)

    if result and result.answer:
        print("\n✅ Capabilities retrieved!")
        print(f"\n{result.answer}")


def example_5_direct_usage():
    """Example 5: Direct usage of ImageAgentCollection (without MCP)."""
    print("\n" + "=" * 80)
    print("Example 5: Direct Usage (Without MCP Protocol)")
    print("=" * 80)

    from examples.gaia.agent_collections.image_agent.image_agent import (
        ImageAgentCollection,
        ActionArguments,
    )

    # Create image agent collection directly
    args = ActionArguments(
        name="image_agent_direct",
        transport="stdio",
        workspace=os.getenv("AWORLD_WORKSPACE", "~"),
        unittest=True,  # Don't actually run MCP server
    )

    image_service = ImageAgentCollection(args)

    # Create and execute image agent
    # Note: LLM configuration is loaded from environment variables
    print("\n🤖 Creating image agent...")
    result = image_service.mcp_create_image_agent(
        task_prompt="Extract text from receipt.png and analyze what items were purchased",
        name="receipt_analyzer",
        description="Agent specialized in receipt image processing",
        max_steps=10,
    )

    if result.success:
        print("\n✅ Image agent created and executed!")
        print(f"\nAgent ID: {result.metadata['agent_id']}")
        print(f"Agent Name: {result.metadata['agent_name']}")
        print(f"\nAnswer: {result.metadata.get('answer', 'No answer')}")

        # Check capabilities
        print("\n📊 Checking capabilities...")
        caps_result = image_service.mcp_get_image_agent_capabilities()
        print(f"\nRegistered Agents: {caps_result.metadata['agent_count']}")
    else:
        print(f"\n❌ Failed: {result.message}")


def main():
    """Run all examples."""
    load_dotenv()

    print("\n" + "=" * 80)
    print("Image Agent MCP Server - Example Usage")
    print("=" * 80)

    # Check environment
    required_vars = ["LLM_PROVIDER", "LLM_MODEL_NAME", "LLM_API_KEY"]
    missing_vars = [var for var in required_vars if not os.getenv(var)]

    if missing_vars:
        print(f"\n⚠️ Warning: Missing environment variables: {missing_vars}")
        print("Some examples may fail. Please configure your .env file.")

    print("\nAvailable Examples:")
    print("1. Create a new image agent")
    print("2. Reuse an existing image agent")
    print("3. Hierarchical agent structure (concept)")
    print("4. Check service capabilities")
    print("5. Direct usage (without MCP protocol)")

    # Run examples
    try:
        # Example 5 is the most self-contained and doesn't require MCP setup
        example_5_direct_usage()

        # Uncomment to run other examples
        # example_4_capabilities_check()
        # example_3_hierarchical_agents()
        # example_1_create_image_agent()
        # example_2_reuse_image_agent()

    except KeyboardInterrupt:
        print("\n\n👋 Interrupted by user")
    except Exception as e:
        print(f"\n\n❌ Error: {e}")
        import traceback

        traceback.print_exc()


if __name__ == "__main__":
    main()

