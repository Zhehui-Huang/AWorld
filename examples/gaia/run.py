import argparse
import json
import logging
import os
import re
import traceback
from typing import Any, Dict, List
from pathlib import Path

from dotenv import load_dotenv

from aworld.agents.llm_agent import Agent
from aworld.config.conf import AgentConfig, TaskConfig
from aworld.core.task import Task
from aworld.core.agent.swarm import Swarm
from aworld.runner import Runners
from examples.gaia.prompt import system_prompt
from examples.gaia.agent_collections.search_agent.prompt import (
    system_prompt as search_system_prompt,
)
from examples.gaia.utils import (
    add_file_path,
    load_dataset_meta,
    question_scorer,
    report_results,
)

# Constants
RESULTS_FILENAME = "/results.json"
ANSWER_REGEX = r"<answer>(.*?)</answer>"
DEFAULT_WORKSPACE = "~"


def parse_arguments() -> argparse.Namespace:
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(description="Run GAIA benchmark with multi-agent system")
    parser.add_argument(
        "--start",
        type=int,
        default=0,
        help="Start index of the dataset",
    )
    parser.add_argument(
        "--end",
        type=int,
        default=20,
        help="End index of the dataset",
    )
    parser.add_argument(
        "--q",
        type=str,
        help="Question task_id, e.g., 0-0-0-0-0. Overrides --start and --end if provided.",
    )
    parser.add_argument(
        "--skip",
        action="store_true",
        help="Skip questions that have been processed before.",
    )
    parser.add_argument(
        "--split",
        type=str,
        default="validation",
        help="Dataset split: 'validation' or 'test'",
    )
    parser.add_argument(
        "--blacklist_file_path",
        type=str,
        nargs="?",
        help="Path to blacklist file containing task_ids to skip",
    )
    return parser.parse_args()


def get_workspace_path() -> str:
    """Get the workspace path from environment or default."""
    return os.getenv("AWORLD_WORKSPACE", DEFAULT_WORKSPACE)


def ensure_workspace_exists() -> None:
    """Create workspace directory if it doesn't exist."""
    workspace_path = get_workspace_path()
    os.makedirs(workspace_path, exist_ok=True)


def setup_logging(args: argparse.Namespace) -> None:
    """Configure logging to file."""
    logger = logging.getLogger()
    logger.setLevel(logging.INFO)

    log_filename = f"/entry_agent_{args.q}.log" if args.q else f"/entry_agent_{args.start}_{args.end}.log"
    log_path = get_workspace_path() + log_filename
    
    file_handler = logging.FileHandler(log_path, mode="a", encoding="utf-8")
    file_handler.setLevel(logging.INFO)
    
    formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
    file_handler.setFormatter(formatter)
    
    logger.addHandler(file_handler)


def create_agent_config() -> AgentConfig:
    """Create agent configuration from environment variables."""
    return AgentConfig(
        llm_provider=os.getenv("LLM_PROVIDER", "openai"),
        llm_model_name=os.getenv("LLM_MODEL_NAME", "gpt-4o"),
        llm_base_url=os.getenv("LLM_BASE_URL"),
        llm_api_key=os.getenv("LLM_API_KEY"),
        llm_temperature=os.getenv("LLM_TEMPERATURE", 0.0),
    )


def load_search_agent_mcp_config() -> tuple[Dict[str, Any], List[str]]:
    """Load MCP configuration for the search agent wrapper only."""
    config_path = Path(__file__).parent / "agent_collections" / "search_agent" / "mcp.json"
    try:
        with open(config_path, mode="r", encoding="utf-8") as f:
            mcp_config = json.load(f)
            servers = list(mcp_config.get("mcpServers", {}).keys())
            logging.info(f"🔧 SearchAgent MCP servers: {servers}")
            return mcp_config, servers
    except json.JSONDecodeError as e:
        logging.error(f"Error loading search_agent mcp.json: {e}")
        return {}, []
    except FileNotFoundError:
        logging.warning("search_agent mcp.json not found; continuing without MCP servers")
        return {}, []


def setup_agents(agent_config: AgentConfig) -> Swarm:
    """Set up the main agent and sub-agents as a swarm, without direct MCP usage.

    Creates a search sub-agent wrapper and a super entry agent that delegates to it,
    and returns a Swarm that registers the search agent so handoffs can find it.

    Returns:
        Swarm containing the entry agent and registered search sub-agent
    """
    # Create search sub-agent wrapper (no direct MCP configuration here)
    mcp_config, mcp_servers = load_search_agent_mcp_config()

    search_agent = Agent(
        conf=agent_config,
        name="search_agent",
        agent_id="search_agent",
        system_prompt=search_system_prompt,
        mcp_config=mcp_config,
        mcp_servers=mcp_servers,
    )

    # Create main agent that delegates to the search agent
    entry_agent = Agent(
        conf=agent_config,
        name="entry_agent",
        agent_id="entry_agent",
        system_prompt=system_prompt,
        agent_names=[search_agent.id()],
    )

    # Build a swarm with entry agent, and register search_agent so runner can handoff
    swarm = Swarm(entry_agent, register_agents=[search_agent])
    return swarm


def load_results() -> List[Dict[str, Any]]:
    """Load existing results from checkpoint file."""
    results_path = get_workspace_path() + RESULTS_FILENAME
    if os.path.exists(results_path):
        with open(results_path, "r", encoding="utf-8") as f:
            return json.load(f)
    return []


def load_blacklist(blacklist_path: str | None) -> set[str]:
    """Load blacklisted task IDs from file.
    
    Args:
        blacklist_path: Path to blacklist file, or None
        
    Returns:
        Set of blacklisted task IDs
    """
    if blacklist_path and os.path.exists(blacklist_path):
        with open(blacklist_path, "r", encoding="utf-8") as f:
            return set(f.read().splitlines())
    return set()


def save_results(results: List[Dict[str, Any]]) -> None:
    """Save results to checkpoint file."""
    results_path = get_workspace_path() + RESULTS_FILENAME
    with open(results_path, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=4, ensure_ascii=False)


def should_skip_question(dataset_record: Dict[str, Any], results: List[Dict[str, Any]], 
                         blacklist: set[str], args: argparse.Namespace) -> bool:
    """Determine if a question should be skipped based on various conditions.
    
    Args:
        dataset_record: The dataset record to check
        results: List of existing results
        blacklist: Set of blacklisted task IDs
        args: Command line arguments
        
    Returns:
        True if the question should be skipped, False otherwise
    """
    task_id = dataset_record["task_id"]
    
    # Skip if in blacklist
    if task_id in blacklist:
        return True
    
    # Find existing result for this task
    existing_result = next((r for r in results if r["task_id"] == task_id), None)
    
    if not existing_result:
        return False
    
    # Skip if already answered correctly
    if existing_result.get("is_correct"):
        return True
    
    # Skip if already attempted a level 3 question incorrectly (too hard)
    if not existing_result.get("is_correct") and dataset_record.get("Level") == 3:
        return True
    
    # Skip if --skip flag is set and question was already processed
    if args.skip:
        return True
    
    return False


def get_dataset_slice(full_dataset: List[Dict[str, Any]], args: argparse.Namespace) -> List[Dict[str, Any]]:
    """Get the slice of dataset to process based on arguments.
    
    Args:
        full_dataset: The full dataset
        args: Command line arguments
        
    Returns:
        Slice of dataset to process
    """
    if args.q is not None:
        # Process specific task ID
        return [record for record in full_dataset if record["task_id"] == args.q]
    else:
        # Process range
        return full_dataset[args.start:args.end]


def extract_answer_from_response(response_text: str) -> str | None:
    """Extract answer from agent response.
    
    Args:
        response_text: The full response text from the agent
        
    Returns:
        Extracted answer or None if not found
    """
    match = re.search(ANSWER_REGEX, response_text)
    return match.group(1) if match else None


def update_results(results: List[Dict[str, Any]], new_result: Dict[str, Any]) -> None:
    """Update results list with new result, replacing existing if present.
    
    Args:
        results: List of results to update (modified in place)
        new_result: New result to add or update
    """
    task_id = new_result["task_id"]
    existing_index = next((i for i, r in enumerate(results) if r["task_id"] == task_id), None)
    
    if existing_index is not None:
        results[existing_index] = new_result
        logging.info(f"Updated existing record for task_id: {task_id}")
    else:
        results.append(new_result)
        logging.info(f"Added new record for task_id: {task_id}")


def process_question(dataset_record: Dict[str, Any], swarm: Swarm, 
                     gaia_dataset_path: str, split: str) -> Dict[str, Any]:
    """Process a single question from the dataset.
    
    Args:
        dataset_record: The dataset record to process
        swarm: The swarm containing the entry agent and registered sub-agents
        gaia_dataset_path: Path to the GAIA dataset
        split: Dataset split (validation/test)
        
    Returns:
        Result dictionary with answer and correctness
    """
    task_id = dataset_record["task_id"]
    
    logging.info(f"Start to process: {task_id}")
    logging.info(f"Question: {dataset_record['Question']}")
    logging.info(f"Level: {dataset_record['Level']}")
    logging.info(f"Tools: {dataset_record['Annotator Metadata']['Tools']}")
    
    # Prepare question with file paths
    question = add_file_path(dataset_record, file_path=gaia_dataset_path, split=split)["Question"]
    
    # Run using the swarm (ensures registered sub-agents are available for handoff)
    task = Task(input=question, swarm=swarm, conf=TaskConfig())
    result = Runners.sync_run_task(task=task)
    
    # Extract answer from response
    answer = extract_answer_from_response(result[task.id].answer)
    
    if answer:
        correct_answer = dataset_record["Final answer"]
        is_correct = question_scorer(answer, correct_answer)
        
        logging.info(f"Agent answer: {answer}")
        logging.info(f"Correct answer: {correct_answer}")
        logging.info(f"Result: {'Correct' if is_correct else 'Incorrect'}")
        
        return {
            "task_id": task_id,
            "level": dataset_record["Level"],
            "question": question,
            "answer": correct_answer,
            "response": answer,
            "is_correct": is_correct,
        }
    else:
        logging.warning(f"No answer extracted from response for task_id: {task_id}")
        return {
            "task_id": task_id,
            "level": dataset_record["Level"],
            "question": question,
            "answer": dataset_record["Final answer"],
            "response": "",
            "is_correct": False,
        }


if __name__ == "__main__":
    load_dotenv()
    args = parse_arguments()
    ensure_workspace_exists()
    setup_logging(args)

    gaia_dataset_path = os.getenv("GAIA_DATASET_PATH", "./gaia_dataset")
    full_dataset = load_dataset_meta(gaia_dataset_path, split=args.split)
    logging.info(f"Total questions: {len(full_dataset)}")

    # Setup agents via agent wrappers (no direct MCP usage)
    agent_config = create_agent_config()
    swarm = setup_agents(agent_config)

    # Load results and blacklist
    results = load_results()
    blacklist = load_blacklist(args.blacklist_file_path)

    try:
        # Get dataset slice to process
        dataset_slice = get_dataset_slice(full_dataset, args)
        logging.info(f"Processing {len(dataset_slice)} questions")

        # Process each question in the dataset slice
        for dataset_record in dataset_slice:
            # Skip if conditions are met (unless specific task_id requested)
            if not args.q and should_skip_question(dataset_record, results, blacklist, args):
                logging.info(f"Skipping task_id: {dataset_record['task_id']}")
                continue

            # Process the question
            try:
                new_result = process_question(dataset_record, swarm, gaia_dataset_path, args.split)
                update_results(results, new_result)
            except Exception as e:
                logging.error(f"Error processing {dataset_record['task_id']}: {str(e)}")
                logging.error(f"Full traceback: {traceback.format_exc()}")
                continue
                
    except KeyboardInterrupt:
        logging.info("Interrupted by user")
    finally:
        # Report and save results
        report_results(results)
        save_results(results)
