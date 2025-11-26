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
import logging
import os
import shutil
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

# Constants
WORKSPACE_PATH = "/home/ethan/repo/AWorld/tmp"
LOGS_PATH = "/home/ethan/repo/AWorld/examples/gaia/agent_collections/logs"
FULL_ARTIFACTS_PATH = "/home/ethan/repo/AWorld/full_artifacts"
ALL_TRAJS_PATH = "/home/ethan/repo/AWorld/full_trajs"


def setup_logging() -> None:
    """Configure logging."""
    logger = logging.getLogger()
    logger.setLevel(logging.INFO)
    
    # Console handler
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)


def ensure_directories_exist() -> None:
    """Create necessary directories if they don't exist."""
    os.makedirs(WORKSPACE_PATH, exist_ok=True)
    os.makedirs(LOGS_PATH, exist_ok=True)
    os.makedirs(FULL_ARTIFACTS_PATH, exist_ok=True)
    os.makedirs(ALL_TRAJS_PATH, exist_ok=True)


def move_artifacts_for_task(task_id: str) -> None:
    """Move all files from workspace to full_artifacts/{task_id}/.
    
    Args:
        task_id: The task identifier
    """
    try:
        # Create task-specific artifact directory
        task_artifact_dir = os.path.join(FULL_ARTIFACTS_PATH, task_id)
        os.makedirs(task_artifact_dir, exist_ok=True)
        
        # Move all files from workspace to task artifact directory
        if os.path.exists(WORKSPACE_PATH):
            for item in os.listdir(WORKSPACE_PATH):
                source_path = os.path.join(WORKSPACE_PATH, item)
                dest_path = os.path.join(task_artifact_dir, item)
                
                try:
                    if os.path.isfile(source_path):
                        shutil.move(source_path, dest_path)
                        logging.info(f"Moved artifact: {item} -> {task_artifact_dir}")
                    elif os.path.isdir(source_path):
                        # Move directory
                        if os.path.exists(dest_path):
                            shutil.rmtree(dest_path)
                        shutil.move(source_path, dest_path)
                        logging.info(f"Moved artifact directory: {item} -> {task_artifact_dir}")
                except Exception as e:
                    logging.warning(f"Failed to move {item}: {e}")
        
        logging.info(f"✅ Artifacts moved to: {task_artifact_dir}")
    except Exception as e:
        logging.error(f"Error moving artifacts for task {task_id}: {e}")


def move_trajectories_for_task(task_id: str) -> None:
    """
    Copy everything from the LOGS_PATH folder—including all subfolders like 'trajectories' and all files such as .log files—
    into a new subfolder named after task_id inside ALL_TRAJS_PATH, preserving full folder structure.
    The original LOGS_PATH folder and its content will NOT be deleted or removed.
    
    Args:
        task_id: The task identifier
    """
    try:
        # The root for this task's trajectories/logs
        dest_root = os.path.join(ALL_TRAJS_PATH, task_id)
        os.makedirs(dest_root, exist_ok=True)

        if os.path.exists(LOGS_PATH):
            # Walk through every file and directory in LOGS_PATH
            for root, dirs, files in os.walk(LOGS_PATH):
                # rel_path is "" for the root itself, or e.g., "trajectories" etc.
                rel_path = os.path.relpath(root, LOGS_PATH)
                dest_dir = os.path.join(dest_root, rel_path) if rel_path and rel_path != "." else dest_root
                os.makedirs(dest_dir, exist_ok=True)
                # Copy all files in the current directory
                for f in files:
                    src_file = os.path.join(root, f)
                    dest_file = os.path.join(dest_dir, f)
                    try:
                        shutil.copy2(src_file, dest_file)
                        logging.info(f"Copied log file: {src_file} -> {dest_file}")
                    except Exception as e:
                        logging.warning(f"Failed to copy {src_file}: {e}")

        logging.info(f"✅ All logs and trajectories copied and structure preserved at: {dest_root}")
    except Exception as e:
        logging.error(f"Error copying trajectories for task {task_id}: {e}")


def cleanup_workspace() -> None:
    """Clean up workspace directory after moving files."""
    try:
        if os.path.exists(WORKSPACE_PATH):
            for item in os.listdir(WORKSPACE_PATH):
                item_path = os.path.join(WORKSPACE_PATH, item)
                try:
                    if os.path.isfile(item_path):
                        os.remove(item_path)
                    elif os.path.isdir(item_path):
                        shutil.rmtree(item_path)
                except Exception as e:
                    logging.warning(f"Failed to clean up {item}: {e}")
        logging.info("✅ Workspace cleaned up")
    except Exception as e:
        logging.error(f"Error cleaning up workspace: {e}")


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
    
    # Set agent type for trajectory logging
    if hasattr(agent, 'llm_json_dataset_logger'):
        agent.llm_json_dataset_logger.agent_type = "main_agent"

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

    # Setup logging
    setup_logging()

    # Load environment variables
    load_dotenv()

    # Verify required environment variables
    required_vars = ["LLM_API_KEY", "GOOGLE_API_KEY", "GOOGLE_CSE_ID"]
    missing_vars = [var for var in required_vars if not os.getenv(var)]
    if missing_vars:
        logging.error(f"❌ Missing required environment variables: {missing_vars}")
        print(f"❌ Missing required environment variables: {missing_vars}")
        print("Please set these variables in your .env file or environment")
        return

    # Ensure directories exist
    ensure_directories_exist()

    # Set workspace
    workspace = os.getenv("AWORLD_WORKSPACE", WORKSPACE_PATH)
    os.environ["AWORLD_WORKSPACE"] = workspace
    logging.info(f"📁 Workspace: {workspace}")
    print(f"📁 Workspace: {workspace}")

    # Load MCP V2 configuration
    # mcp_config = load_mcp_config_v2()
    # if not mcp_config:
    #     print("❌ Failed to load MCP V2 configuration")
    #     return

    # # Create main orchestrator V2
    # print("\n🎭 Creating main orchestrator V2 (with sub-orchestrator capability)...")
    # main_agent = create_main_orchestrator_v2(mcp_config)

    # # Define complex task that benefits from hierarchical orchestration
    # task_prompt = """A paper about AI regulation that was originally submitted to arXiv.org in June 2022 shows a figure with three axes, where each axis has a label word at both ends. Which of these words is used to describe a type of society in a Physics and Society article submitted to arXiv.org on August 11, 2016?"""
    # # task_prompt = """A paper about AI regulation that was originally submitted to arXiv.org in June 2022. Find and download that. Output the name of the paper."""
    # # task_prompt = """2207.01510.pdf has already be downloaded. Please find all words about a type of society or the ideology or principle behind it in the first 6 pages of 2207.01510.pdf and return them. Do not need to process any media, such as images."""
    # image_path = str(Path(__file__).parent / "image_0.png")
    # image_path_1 = str(Path(__file__).parent / "image_1.png")
    # # image_path_2 = str(Path(__file__).parent / "image_2.png")

    # # Task that requires image processing
    # # task_prompt = f"""
    # # Please analyze following two images one by one: {image_path}, {image_path_1}.
    # # You need to create a file_agent first, and then keep using this file agent.
    # # Please output their description.
    # # """

    # # Generate task ID
    task_id = str(uuid.uuid4().hex)
    logging.info(f"📝 Task ID: {task_id}")
    print(f"📝 Task ID: {task_id}")

    # print("\n📋 Task:")
    # print(task_prompt)
    # logging.info(f"Task: {task_prompt}")
    
    # print("\n🚀 Executing hierarchical orchestration workflow...\n")
    # print("Expected behavior:")
    # print("  → Main orchestrator analyzes task structure")
    # print("  → Creates sub-orchestrator for Phase 1 (search + pdf + image)")
    # print("  → Sub-orchestrator 1 coordinates multi-agent workflow internally")
    # print("  → Main orchestrator receives axis labels")
    # print("  → Creates sub-orchestrator for Phase 2 (search + pdf)")
    # print("  → Sub-orchestrator 2 searches for society word")
    # print("  → Main orchestrator synthesizes final answer\n")

    # try:
    #     # Create and run task
    #     task = Task(
    #         id=task_id,
    #         input=task_prompt,
    #         agent=main_agent,
    #         conf=TaskConfig(max_steps=100),  # More steps for hierarchical coordination
    #     )

    #     # Execute task
    #     result_map = Runners.sync_run_task(task=task)
    #     task_response = result_map.get(task.id) if result_map else None

    #     # Display results
    #     print("\n" + "=" * 100)
    #     print("📊 Results - Hierarchical Orchestration V2")
    #     print("=" * 100)

    #     if task_response and task_response.answer:
    #         print("\n✅ Task completed successfully!\n")
    #         print("🎯 Final Answer:")
    #         print(task_response.answer)
    #         logging.info(f"Task {task_id} completed successfully")
    #         logging.info(f"Answer: {task_response.answer}")
    #     else:
    #         print("\n⚠️ Task completed but no answer was generated")
    #         logging.warning(f"Task {task_id} completed but no answer was generated")
    #         if task_response:
    #             print(f"Status: {task_response}")
    #             logging.info(f"Status: {task_response}")

    #     print("\n" + "=" * 100)
        
    # except Exception as e:
    #     logging.error(f"Error executing task {task_id}: {e}")
    #     print(f"\n❌ Error executing task: {e}")
    #     import traceback
    #     logging.error(f"Full traceback: {traceback.format_exc()}")
        
    # finally:
    # Move artifacts and trajectories after task completion
    print("\n📦 Moving artifacts and trajectories...")
    logging.info(f"Moving artifacts and trajectories for task {task_id}")
    
    move_artifacts_for_task(task_id)
    move_trajectories_for_task(task_id)
    cleanup_workspace()
    
    print("✅ All files moved successfully!")
    logging.info(f"Task {task_id} cleanup completed")


if __name__ == "__main__":
    try:
        example_1_hierarchical_paper_analysis()
    except KeyboardInterrupt:
        print("\n\n👋 Goodbye!")
        sys.exit(0)
