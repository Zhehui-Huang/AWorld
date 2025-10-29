"""
Dynamic Multi-Agent Workflow Example

This example demonstrates how a main agent can dynamically use specialized sub-agents 
(Search Agent and PDF Agent) to complete complex tasks that require multiple capabilities.

Example Task:
"Find a paper on arXiv from August 2020 about attention mechanisms in transformers, 
download the file, and extract and summarize it using 1000 words."

Architecture:
    Main Agent (Orchestrator)
        ├─> Search Agent (for finding and downloading papers)
        │   ├─> LLM Instance
        │   ├─> Memory Module
        │   └─> MCP Tools (search, download)
        │
        └─> PDF Agent (for extracting and analyzing papers)
            ├─> LLM Instance
            ├─> Memory Module
            └─> MCP Tools (pdf extraction)

Workflow:
1. Main Agent receives complex task
2. Main Agent delegates search task to Search Agent
3. Search Agent finds paper on arXiv and downloads it
4. Main Agent receives download location
5. Main Agent delegates PDF analysis to PDF Agent
6. PDF Agent extracts and summarizes content
7. Main Agent returns final result to user
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
from aworld.logs.util import Color, logger
from aworld.runner import Runners
from examples.gaia.agent_collections.prompt import system_prompt


def load_mcp_config() -> Dict[str, Any]:
    """Load MCP configuration that includes both search_agent and pdf_agent."""
    try:
        mcp_path = Path(__file__).parent.parent / "mcp.json"
        with open(mcp_path, mode="r", encoding="utf-8") as f:
            mcp_config = json.loads(f.read())
            print(f"✅ Loaded MCP servers: {list(mcp_config.get('mcpServers', {}).keys())}")
            return mcp_config
    except Exception as e:
        print(f"❌ Error loading mcp.json: {e}")
        return {}


def create_main_agent(mcp_config: Dict[str, Any]) -> Agent:
    """Create main orchestrator agent with access to both sub-agents."""
    
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
    

    # Get available MCP servers
    available_servers = list(mcp_config.get("mcpServers", {}).keys())
    
    # Create main agent with MCP tools for both sub-agents
    agent = Agent(
        conf=agent_config,
        name="main_orchestrator_agent",
        agent_id=f"main_agent_{uuid.uuid4().hex[:8]}",
        system_prompt=system_prompt,
        mcp_config=mcp_config,
        mcp_servers=available_servers,
    )
    
    print(f"✅ Created main orchestrator agent with access to: {available_servers}")
    
    return agent


def example_1_arxiv_paper_search_and_summarize():
    """
    Example 1: Complete workflow - Find arXiv paper, download, and summarize
    
    This demonstrates the full pipeline:
    1. Main agent receives complex task
    2. Main agent delegates to search agent (find and download paper)
    3. Main agent delegates to PDF agent (extract and summarize)
    4. Main agent returns comprehensive result
    """
    print("\n" + "=" * 100)
    print("Example 1: Find arXiv Paper, Download, Extract, and Summarize")
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
    
    # Load MCP configuration
    mcp_config = load_mcp_config()
    if not mcp_config:
        print("❌ Failed to load MCP configuration")
        return
    
    # Create main orchestrator agent
    print("\n🤖 Creating main orchestrator agent...")
    main_agent = create_main_agent(mcp_config)
    
    # Define complex task
    task_prompt = """Find two papers on arXiv that were published before August 2020 about attention mechanisms in transformers.  
Then, extract the content from the PDFs and provide a comprehensive summary of approximately 100 words that covers:
The main research question and motivation
"""
    # task_prompt = """A paper about AI regulation that was originally submitted to arXiv.org in June 2022 shows a figure with three axes, where each axis has a label word at both ends. Which of these words is used to describe a type of society in a Physics and Society article submitted to arXiv.org on August 11, 2016?
    # """
    
    print("\n📋 Task:")
    print(task_prompt)
    print("\n🚀 Executing workflow...\n")
    
    # Create and run task
    task = Task(
        id=str(uuid.uuid4().hex),
        input=task_prompt,
        agent=main_agent,
        conf=TaskConfig(max_steps=30),  # More steps for complex workflow
    )
    
    # Execute task
    result_map = Runners.sync_run_task(task=task)
    task_response = result_map.get(task.id) if result_map else None
    
    # Display results
    print("\n" + "=" * 100)
    print("📊 Results")
    print("=" * 100)
    
    if task_response and task_response.answer:
        print("\n✅ Task completed successfully!\n")
        print(task_response.answer)
    else:
        print("\n⚠️ Task completed but no answer was generated")
        if task_response:
            print(f"Status: {task_response}")
    
    print("\n" + "=" * 100)

def main():
    """Main entry point - run examples."""
    print("""
╔════════════════════════════════════════════════════════════════════════════╗
║                                                                            ║
║           Dynamic Multi-Agent Workflow Examples                           ║
║                                                                            ║
║  Demonstrates how a main agent orchestrates specialized sub-agents        ║
║  (Search Agent and PDF Agent) to complete complex tasks                   ║
║                                                                            ║
╚════════════════════════════════════════════════════════════════════════════╝
""")
    
    examples = {
        "1": ("Find arXiv Paper and Summarize (Full Workflow)", example_1_arxiv_paper_search_and_summarize),
    }
    
    print("Available Examples:")
    for key, (description, _) in examples.items():
        print(f"  {key}. {description}")
    print("  q. Quit")
    
    while True:
        print("\n" + "-" * 80)
        choice = input("\nSelect an example (1-4) or 'q' to quit: ").strip().lower()
        
        if choice == 'q':
            print("\n👋 Goodbye!")
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
            print("❌ Invalid choice. Please select 1-4 or 'q'")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n👋 Goodbye!")
        sys.exit(0)

