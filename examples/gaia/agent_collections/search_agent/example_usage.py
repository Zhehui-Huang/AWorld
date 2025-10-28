"""
Example Usage of Search Agent MCP Server

This script demonstrates how to use the Search Agent MCP Server
to create dynamic multi-layer agent architectures.
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


def example_1_create_search_agent():
    """Example 1: Create a new search agent and execute a task."""
    print("\n" + "=" * 80)
    print("Example 1: Creating a New Search Agent")
    print("=" * 80)

    # Load the main agent's MCP configuration
    mcp_config_path = Path(__file__).parent.parent.parent.parent / "gaia" / "mcp.json"
    with open(mcp_config_path, "r") as f:
        mcp_config = json.load(f)

    # Create main agent with search_agent MCP server
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
        system_prompt="You are a helpful assistant that can delegate search tasks to specialized agents.",
        mcp_config=mcp_config,
        mcp_servers=["search_agent"],
    )

    # Task that requires search
    task_prompt = """
    I need to find information about AI regulation papers from June 2022.
    Use the search agent to find relevant papers.
    
    Call search_agent.mcp_create_search_agent with:
    - task_prompt: "Find AI regulation papers from arXiv submitted in June 2022"
    - name: "arxiv_researcher"
    - description: "Agent specialized in finding arXiv papers"
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


def example_2_reuse_search_agent():
    """Example 2: Reuse an existing search agent for multiple tasks."""
    print("\n" + "=" * 80)
    print("Example 2: Reusing an Existing Search Agent")
    print("=" * 80)

    # This example requires an agent_id from example_1
    # In practice, you would store the agent_id from the first call
    agent_id = "search_agent_abc12345"  # Replace with actual agent_id

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
    print("  └─> Research Coordinator (Sub-Main Agent)")
    print("      ├─> Search Agent (for finding papers)")
    print("      └─> Analysis Agent (for summarizing)")

    # This demonstrates the concept
    # In practice, you would implement this with actual agent delegation

    workflow_description = """
    1. Main Agent receives: "Research top 3 AI safety papers from 2022"
    
    2. Main Agent creates Research Coordinator:
       - Specialized in coordinating research tasks
       - Has access to both search and analysis agents
    
    3. Research Coordinator creates Search Agent:
       - Task: "Find top 3 AI safety papers from 2022"
       - Agent autonomously searches and retrieves papers
    
    4. Research Coordinator creates Analysis Agent:
       - Task: "Summarize findings from these papers"
       - Agent processes and summarizes
    
    5. Results flow back up:
       Analysis Agent -> Research Coordinator -> Main Agent -> User
    """

    print(workflow_description)


def example_4_capabilities_check():
    """Example 4: Check search agent service capabilities."""
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
        system_prompt="Get capabilities of the search agent service.",
        mcp_config=mcp_config,
        mcp_servers=["search_agent"],
    )

    task_prompt = "Call search_agent.mcp_get_search_agent_capabilities to see what this service can do."

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
    """Example 5: Direct usage of SearchAgentCollection (without MCP)."""
    print("\n" + "=" * 80)
    print("Example 5: Direct Usage (Without MCP Protocol)")
    print("=" * 80)

    from examples.gaia.agent_collections.search_agent.search_agent import (
        SearchAgentCollection,
        ActionArguments,
    )

    # Create search agent collection directly
    args = ActionArguments(
        name="search_agent_direct",
        transport="stdio",
        workspace=os.getenv("AWORLD_WORKSPACE", "~"),
        unittest=True,  # Don't actually run MCP server
    )

    search_service = SearchAgentCollection(args)

    # Create and execute search agent
    # Note: LLM configuration is loaded from environment variables
    print("\n🤖 Creating search agent...")
    result = search_service.mcp_create_search_agent(
        task_prompt="Find a paper about quantum computing breakthroughs in 2023 and download",
        name="quantum_researcher",
        description="Agent specialized in quantum computing research",
        max_steps=10,
    )

    if result.success:
        print("\n✅ Search agent created and executed!")
        print(f"\nAgent ID: {result.metadata['agent_id']}")
        print(f"Agent Name: {result.metadata['agent_name']}")
        print(f"\nAnswer: {result.metadata.get('answer', 'No answer')}")

        # Check capabilities
        print("\n📊 Checking capabilities...")
        caps_result = search_service.mcp_get_search_agent_capabilities()
        print(f"\nRegistered Agents: {caps_result.metadata['agent_count']}")
    else:
        print(f"\n❌ Failed: {result.message}")


def main():
    """Run all examples."""
    load_dotenv()

    print("\n" + "=" * 80)
    print("Search Agent MCP Server - Example Usage")
    print("=" * 80)

    # Check environment
    required_vars = ["LLM_PROVIDER", "LLM_MODEL_NAME", "LLM_API_KEY"]
    missing_vars = [var for var in required_vars if not os.getenv(var)]

    if missing_vars:
        print(f"\n⚠️ Warning: Missing environment variables: {missing_vars}")
        print("Some examples may fail. Please configure your .env file.")

    print("\nAvailable Examples:")
    print("1. Create a new search agent")
    print("2. Reuse an existing search agent")
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
        # example_1_create_search_agent()
        # example_2_reuse_search_agent()

    except KeyboardInterrupt:
        print("\n\n👋 Interrupted by user")
    except Exception as e:
        print(f"\n\n❌ Error: {e}")
        import traceback

        traceback.print_exc()


if __name__ == "__main__":
    main()

