"""
Simplified Multi-Agent Workflow Test

Test Question:
"On 16 August 1986, the opening match of a team that won 10 consecutive DDR-Oberliga 
titles between 1978 and 1988 took place at a sports complex with multiple facilities 
in Berlin. How many spectators attended this match?"
"""

import json
import logging
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

# Constants
WORKSPACE_PATH = "/home/ethan/repo/AWorld/tmp"


def setup_logging() -> None:
    """Configure logging."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )


def load_mcp_config() -> Dict[str, Any]:
    """Load MCP configuration."""
    mcp_path = Path(__file__).parent / "mcp.json"
    with open(mcp_path, "r", encoding="utf-8") as f:
        mcp_config = json.load(f)
        servers = list(mcp_config.get("mcpServers", {}).keys())
        print(f"✅ Loaded MCP servers: {servers}")
        return mcp_config


def create_agent(mcp_config: Dict[str, Any]) -> Agent:
    """Create main orchestrator agent."""
    agent_config = AgentConfig(
        llm_provider=os.getenv("LLM_PROVIDER", "openai"),
        llm_model_name=os.getenv("LLM_MODEL_NAME", "gpt-4o"),
        llm_base_url=os.getenv("LLM_BASE_URL"),
        llm_api_key=os.getenv("LLM_API_KEY"),
        llm_temperature=float(os.getenv("LLM_TEMPERATURE", "0.0")),
    )

    available_servers = list(mcp_config.get("mcpServers", {}).keys())

    agent = Agent(
        conf=agent_config,
        name="main_orchestrator",
        agent_id=f"orchestrator_{uuid.uuid4().hex[:8]}",
        system_prompt=system_prompt,
        mcp_config=mcp_config,
        mcp_servers=available_servers,
    )
    
    if hasattr(agent, 'llm_json_dataset_logger'):
        agent.llm_json_dataset_logger.agent_type = "main_agent"

    print(f"✅ Created orchestrator with: {available_servers}")
    return agent


def main():
    """Main test function."""
    print("\n" + "=" * 80)
    print("Multi-Agent Orchestration Test")
    print("=" * 80)

    # Setup
    setup_logging()
    load_dotenv()

    # Check environment variables
    required_vars = ["LLM_API_KEY", "GOOGLE_API_KEY", "GOOGLE_CSE_ID"]
    missing_vars = [var for var in required_vars if not os.getenv(var)]
    if missing_vars:
        print(f"❌ Missing environment variables: {missing_vars}")
        return

    # Setup workspace
    os.makedirs(WORKSPACE_PATH, exist_ok=True)
    os.environ["AWORLD_WORKSPACE"] = WORKSPACE_PATH
    print(f"📁 Workspace: {WORKSPACE_PATH}")

    # Load MCP configuration
    mcp_config = load_mcp_config()
    if not mcp_config:
        print("❌ Failed to load MCP configuration")
        return

    # Create agent
    print("\n🎭 Creating orchestrator agent...")
    agent = create_agent(mcp_config)

    # Task question
    # task_prompt = """What is the date of death of the performer of song Velvet Goldmine (Song)?"""
    task_prompt = """On 16 August 1986, the opening match of a team that won 10 consecutive DDR-Oberliga titles between 1978 and 1988 took place at a sports complex with multiple facilities in Berlin. How many spectators attended this match?
    """

    # Generate task ID
    task_id = uuid.uuid4().hex
    print(f"📝 Task ID: {task_id}")
    print(f"\n📋 Question:\n{task_prompt}")
    print("\n🚀 Executing task...\n")

    try:
        # Create and run task
        task = Task(
            id=task_id,
            input=task_prompt,
            agent=agent,
            conf=TaskConfig(max_steps=50),
        )

        # Execute
        result_map = Runners.sync_run_task(task=task)
        task_response = result_map.get(task.id) if result_map else None

        # Results
        print("\n" + "=" * 80)
        print("📊 Results")
        print("=" * 80)

        if task_response and task_response.answer:
            print("\n✅ Task completed!\n")
            print("🎯 Answer:")
            print(task_response.answer)
            logging.info(f"Task completed: {task_response.answer}")
        else:
            print("\n⚠️ No answer generated")
            if task_response:
                print(f"Status: {task_response}")

        print("\n" + "=" * 80)

    except Exception as e:
        print(f"\n❌ Error: {e}")
        logging.error(f"Task error: {e}", exc_info=True)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n👋 Goodbye!")
        sys.exit(0)
