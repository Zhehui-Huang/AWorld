"""
Dynamic Multi-Agent Workflow Example - Version 2 (Hierarchical Orchestration)

This example demonstrates Version 2 of the orchestration framework with support for:
- Multi-level hierarchical orchestration
- Recursive orchestrator agents
- Automatic sub-orchestrator creation for complex multi-agent sub-tasks
- Parallel execution of independent sub-orchestrators
- Dynamic agent coordination at multiple levels

Example Task:
"A paper about AI regulation that was originally submitted to arXiv.org in June 2022 shows
a figure with three axes, where each axis has a label word at both ends. Which of these words
is used to describe a type of society in a Physics and Society article submitted to arXiv.org
on August 11, 2016?"

Architecture (Version 2 - Hierarchical):
    Main Orchestrator (Level 0)
        │
        ├─> Sub-Orchestrator 1 (Level 1) - Phase 1: Extract axis labels from June 2022 paper
        │   ├─> Search Agent (find and download paper)
        │   ├─> PDF Agent (extract figures)
        │   └─> Image Agent (analyze figure, extract labels)
        │
        └─> Sub-Orchestrator 2 (Level 1) - Phase 2: Find society word in August 2016 paper
            ├─> Search Agent (find specific paper by date)
            └─> PDF Agent (search for label words in context)

Key Improvements Over V1:
1. **Hierarchical Decomposition**: Complex tasks automatically decompose into sub-orchestrators
2. **Reduced Cognitive Load**: Each orchestrator manages fewer agents at its level
3. **Better Parallelism**: Independent sub-orchestrators can run in parallel
4. **Recursive Orchestration**: Unlimited nesting depth for complex workflows
5. **Improved Modularity**: Each orchestrator focuses on its specific sub-task
6. **Error Isolation**: Failures in one sub-orchestrator don't affect others

Workflow:
1. Main Orchestrator analyzes the task
2. Identifies two major phases requiring multiple agents each
3. Creates Sub-Orchestrator 1 for Phase 1 (multi-agent coordination)
4. Sub-Orchestrator 1 internally manages: search → pdf → image agents
5. Main Orchestrator receives axis labels
6. Creates Sub-Orchestrator 2 for Phase 2
7. Sub-Orchestrator 2 internally manages: search → pdf agents
8. Main Orchestrator synthesizes final answer
"""

import json
import os
import sys
import uuid
from pathlib import Path
from typing import Any, Dict

from dotenv import load_dotenv

from aworld.agents.llm_agent import Agent
from aworld.config.conf import AgentConfig, TaskConfig
from aworld.core.task import Task
from aworld.runner import Runners
from examples.gaia.agent_collections.prompt import system_prompt


def load_mcp_config_v2() -> Dict[str, Any]:
    """Load MCP configuration V2 that includes orchestrator_agent."""
    try:
        mcp_path = Path(__file__).parent / "mcp.json"
        with open(mcp_path, mode="r", encoding="utf-8") as f:
            mcp_config = json.loads(f.read())
            available_servers = list(mcp_config.get("mcpServers", {}).keys())
            print(f"✅ Loaded MCP V2 servers: {available_servers}")
            return mcp_config
    except Exception as e:
        print(f"❌ Error loading mcp_v2.json: {e}")
        return {}


def create_main_orchestrator_v2(mcp_config: Dict[str, Any]) -> Agent:
    """Create main orchestrator agent V2 with access to sub-orchestrators."""

    # Load LLM configuration from environment variables
    llm_provider = os.getenv("LLM_PROVIDER", "openai")
    llm_model_name = os.getenv("LLM_MODEL_NAME", "gpt-4o")
    llm_base_url = os.getenv("LLM_BASE_URL")
    llm_api_key = os.getenv("LLM_API_KEY")
    llm_temperature = float(os.getenv("LLM_TEMPERATURE", "0.0"))

    # Create agent configuration
    agent_config = AgentConfig(
        llm_provider=llm_provider,
        llm_model_name=llm_model_name,
        llm_base_url=llm_base_url,
        llm_api_key=llm_api_key,
        llm_temperature=llm_temperature,
    )

    # Get available MCP servers (including orchestrator_agent for recursion)
    available_servers = list(mcp_config.get("mcpServers", {}).keys())

    # Create main agent with V2 MCP tools (includes orchestrator_agent)
    agent = Agent(
        conf=agent_config,
        name="main_orchestrator_v2",
        agent_id=f"main_orchestrator_v2_{uuid.uuid4().hex[:8]}",
        system_prompt=system_prompt,
        mcp_config=mcp_config,
        mcp_servers=available_servers,
    )

    print(f"✅ Created main orchestrator V2 with access to: {available_servers}")

    return agent


def example_1_hierarchical_paper_analysis():
    """
    Example 1: Hierarchical Orchestration - AI Regulation Paper Analysis

    This demonstrates the full V2 hierarchical orchestration:
    1. Main orchestrator receives complex multi-phase task
    2. Creates sub-orchestrator for Phase 1 (find paper + extract figure + analyze labels)
    3. Sub-orchestrator 1 internally coordinates: search → pdf → image agents
    4. Main orchestrator receives extracted labels
    5. Creates sub-orchestrator for Phase 2 (find paper + search for society word)
    6. Sub-orchestrator 2 internally coordinates: search → pdf agents
    7. Main orchestrator synthesizes final answer

    This shows how V2 automatically handles multi-level orchestration.
    """
    print("\n" + "=" * 100)
    print("Example 1: Hierarchical Multi-Agent Orchestration (V2)")
    print("=" * 100)

    # Load environment variables
    load_dotenv()

    # Verify required environment variables
    required_vars = ["LLM_API_KEY", "GOOGLE_API_KEY", "GOOGLE_CSE_ID"]
    missing_vars = [var for var in required_vars if not os.getenv(var)]
    if missing_vars:
        print(f"❌ Missing required environment variables: {missing_vars}")
        print("Please set these variables in your .env file or environment")
        return

    # Set workspace
    workspace = os.getenv("AWORLD_WORKSPACE", str(Path.home()))
    print(f"📁 Workspace: {workspace}")

    # Load MCP V2 configuration
    mcp_config = load_mcp_config_v2()
    if not mcp_config:
        print("❌ Failed to load MCP V2 configuration")
        return

    # Create main orchestrator V2
    print("\n🎭 Creating main orchestrator V2 (with sub-orchestrator capability)...")
    main_agent = create_main_orchestrator_v2(mcp_config)

    # Define complex task that benefits from hierarchical orchestration
    task_prompt = """A paper about AI regulation that was originally submitted to arXiv.org in June 2022 shows a figure with three axes, where each axis has a label word at both ends. Which of these words is used to describe a type of society in a Physics and Society article submitted to arXiv.org on August 11, 2016?
"""

    image_path = str(Path(__file__).parent / "image_0.png")
    image_path_1 = str(Path(__file__).parent / "image_1.png")
    # image_path_2 = str(Path(__file__).parent / "image_2.png")

    # Task that requires image processing
    # task_prompt = f"""
    # Please analyze following two images one by one: {image_path}, {image_path_1}.
    # You need to create an image_agent first, and then keep using this image agent.
    # Please output their description.
    # """

    print("\n📋 Task:")
    print(task_prompt)
    print("\n🚀 Executing hierarchical orchestration workflow...\n")
    print("Expected behavior:")
    print("  → Main orchestrator analyzes task structure")
    print("  → Creates sub-orchestrator for Phase 1 (search + pdf + image)")
    print("  → Sub-orchestrator 1 coordinates multi-agent workflow internally")
    print("  → Main orchestrator receives axis labels")
    print("  → Creates sub-orchestrator for Phase 2 (search + pdf)")
    print("  → Sub-orchestrator 2 searches for society word")
    print("  → Main orchestrator synthesizes final answer\n")

    # Create and run task
    task = Task(
        id=str(uuid.uuid4().hex),
        input=task_prompt,
        agent=main_agent,
        conf=TaskConfig(max_steps=100),  # More steps for hierarchical coordination
    )

    # Execute task
    result_map = Runners.sync_run_task(task=task)
    task_response = result_map.get(task.id) if result_map else None

    # Display results
    print("\n" + "=" * 100)
    print("📊 Results - Hierarchical Orchestration V2")
    print("=" * 100)

    if task_response and task_response.answer:
        print("\n✅ Task completed successfully!\n")
        print("🎯 Final Answer:")
        print(task_response.answer)
    else:
        print("\n⚠️ Task completed but no answer was generated")
        if task_response:
            print(f"Status: {task_response}")

    print("\n" + "=" * 100)

def main():
    """Main entry point - run V2 orchestration examples."""
    print("""
╔════════════════════════════════════════════════════════════════════════════╗
║                                                                            ║
║         Hierarchical Multi-Agent Orchestration Examples (V2)              ║
║                                                                            ║
║  Demonstrates recursive orchestrators that create sub-orchestrators       ║
║  for complex multi-agent workflows with automatic task decomposition      ║
║                                                                            ║
║  Key Features:                                                            ║
║    • Multi-level hierarchical orchestration                               ║
║    • Recursive orchestrator agents                                        ║
║    • Automatic sub-orchestrator creation                                  ║
║    • Parallel execution of independent sub-orchestrators                  ║
║    • Smart decision-making (when to use sub-orchestrators)                ║
║                                                                            ║
╚════════════════════════════════════════════════════════════════════════════╝
""")

    examples = {
        "1": ("Hierarchical Multi-Agent Task (AI Regulation Paper)", example_1_hierarchical_paper_analysis),
        # "2": ("Parallel Sub-Orchestrators (Two Papers)", example_2_parallel_orchestrators),
        # "3": ("Direct Agent Management (Simple Task)", example_3_direct_vs_hierarchical),
    }

    print("Available Examples:")
    for key, (description, _) in examples.items():
        print(f"  {key}. {description}")
    print("  a. Run all examples")
    print("  q. Quit")

    while True:
        print("\n" + "-" * 80)
        choice = input("\nSelect an example (1-3, 'a' for all, 'q' to quit): ").strip().lower()

        if choice == 'q':
            print("\n👋 Goodbye!")
            break
        elif choice == 'a':
            print("\n🚀 Running all examples...\n")
            for _, example_func in examples.values():
                try:
                    example_func()
                except KeyboardInterrupt:
                    print("\n\n⚠️ Interrupted by user")
                    break
                except Exception as e:
                    print(f"\n❌ Error running example: {e}")
                    import traceback

                    traceback.print_exc()
            break
        elif choice in examples:
            _, example_func = examples[choice]
            try:
                example_func()
            except KeyboardInterrupt:
                print("\n\n⚠️ Interrupted by user")
                break
            except Exception as e:
                print(f"\n❌ Error running example: {e}")
                import traceback

                traceback.print_exc()
        else:
            print("❌ Invalid choice. Please select 1-3, 'a', or 'q'")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n👋 Goodbye!")
        sys.exit(0)

