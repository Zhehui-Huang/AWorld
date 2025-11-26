"""
WebShaper Dataset Batch Processing

Processes all tasks from Alibaba-NLP/WebShaper dataset:
- Runs each task through the agent system
- Compares predicted answers with ground truth
- Organizes results into success/fail folders with trajectories and metadata
"""

import json
import logging
import os
import re
import shutil
import sys
import time
import uuid
from pathlib import Path
from typing import Any, Dict, Optional

from dotenv import load_dotenv
from datasets import load_dataset
from openai import OpenAI
from pydantic import BaseModel

from aworld.agents.llm_agent import Agent
from aworld.config.conf import AgentConfig, TaskConfig
from aworld.core.task import Task
from aworld.runner import Runners
from examples.gaia.agent_collections.prompt import system_prompt

# Constants
WORKSPACE_PATH = "/home/ethan/repo/AWorld/tmp"
LOGS_PATH = "/home/ethan/repo/AWorld/examples/gaia/agent_collections/logs"
OUTPUT_BASE_PATH = "/home/ethan/repo/AWorld/z_full_traj"


# Pydantic model for structured output
class AnswerComparison(BaseModel):
    is_correct: bool


def setup_logging() -> None:
    """Configure logging."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )


def clean_directory(dir_path: str) -> None:
    """Clean a directory by removing all its contents."""
    path = Path(dir_path)
    try:
        if path.exists() and path.is_dir():
            shutil.rmtree(path)
            logging.info(f"Cleaned directory: {path}")
        path.mkdir(parents=True, exist_ok=True)
    except Exception as e:
        logging.error(f"Failed to clean directory {dir_path}: {e}", exc_info=True)
        # Try to at least create the directory if it doesn't exist
        try:
            path.mkdir(parents=True, exist_ok=True)
        except Exception as mkdir_error:
            logging.error(f"Failed to create directory {dir_path}: {mkdir_error}")


def extract_answer_from_tags(text: str) -> str:
    """Extract answer from <answer>FORMATTED_ANSWER</answer> tags."""
    if not text:
        return ""
    
    # Try to find answer in tags
    pattern = r'<answer>(.*?)</answer>'
    matches = re.findall(pattern, text, re.DOTALL | re.IGNORECASE)
    
    if matches:
        # Get the last match (in case there are multiple)
        return matches[-1].strip()
    
    # If no tags found, return the original text
    return text.strip()


def compare_answers_with_llm(predicted: str, ground_truth: str, llm_client: OpenAI) -> bool:
    """
    Compare predicted answer with ground truth using LLM with structured output.
    Returns is_correct (bool)
    """
    prompt = f"""Compare these two answers and determine if they are semantically equivalent.

Ground Truth Answer: {ground_truth}
Predicted Answer: {predicted}

Consider:
- Different phrasings of the same answer should be considered equivalent
- Minor formatting differences should be ignored
- Numerical answers should match in value
- Dates should match in meaning even if formatted differently"""

    try:
        response = llm_client.beta.chat.completions.parse(
            model="gpt-5-nano-2025-08-07",
            messages=[
                {"role": "system", "content": "You are an expert at comparing answers for semantic equivalence."},
                {"role": "user", "content": prompt}
            ],
            response_format=AnswerComparison
        )
        
        result = response.choices[0].message.parsed
        return result.is_correct
        
    except Exception as e:
        logging.error(f"LLM comparison error: {e}")
        # Fallback to simple string comparison
        return predicted.strip().lower() == ground_truth.strip().lower()


def save_task_results(
    task_id: str,
    question: str,
    ground_truth: str,
    predicted_answer: str,
    extracted_answer: str,
    is_success: bool,
    formalization: list = None,
    urls: list = None
) -> None:
    """Save task results to appropriate success/fail folder."""
    # Determine output folder
    status_folder = "success" if is_success else "fail"
    task_output_dir = Path(OUTPUT_BASE_PATH) / status_folder / task_id
    task_output_dir.mkdir(parents=True, exist_ok=True)
    
    # Copy trajectories from logs folder
    logs_path = Path(LOGS_PATH)
    traj_copied = False
    if logs_path.exists() and logs_path.is_dir():
        # Check if directory has any content
        try:
            contents = list(logs_path.iterdir())
            if contents:
                traj_dest = task_output_dir / "traj"
                if traj_dest.exists():
                    shutil.rmtree(traj_dest)
                shutil.copytree(logs_path, traj_dest)
                print(f"  📋 Copied {len(contents)} items from trajectories to {traj_dest}")
                traj_copied = True
            else:
                logging.warning(f"Logs directory exists but is empty: {logs_path}")
                print(f"  ⚠️ Warning: Logs directory is empty")
        except Exception as e:
            logging.error(f"Failed to copy trajectories from {logs_path}: {e}", exc_info=True)
            print(f"  ❌ Error copying trajectories: {e}")
    else:
        logging.warning(f"Logs directory does not exist: {logs_path}")
        print(f"  ⚠️ Warning: Logs directory not found")
    
    # Copy middle files from tmp folder
    tmp_copied = False
    tmp_path = Path(WORKSPACE_PATH)
    if tmp_path.exists() and tmp_path.is_dir():
        try:
            contents = list(tmp_path.iterdir())
            if contents:
                middle_files_dest = task_output_dir / "middle_files"
                if middle_files_dest.exists():
                    shutil.rmtree(middle_files_dest)
                shutil.copytree(tmp_path, middle_files_dest)
                print(f"  📁 Copied {len(contents)} items from workspace to {middle_files_dest}")
                tmp_copied = True
            else:
                logging.warning(f"Workspace directory exists but is empty: {tmp_path}")
                print(f"  ⚠️ Warning: Workspace directory is empty")
        except Exception as e:
            logging.error(f"Failed to copy workspace files from {tmp_path}: {e}", exc_info=True)
            print(f"  ❌ Error copying workspace files: {e}")
    else:
        logging.warning(f"Workspace directory does not exist: {tmp_path}")
        print(f"  ⚠️ Warning: Workspace directory not found")
    
    # Save task info with copy status
    task_info = {
        "task_id": task_id,
        "question": question,
        "ground_truth_answer": ground_truth,
        "predicted_answer_raw": predicted_answer,
        "predicted_answer_extracted": extracted_answer,
        "is_correct": is_success,
        "formalization": formalization,
        "reference_urls": urls,
        "metadata": {
            "trajectories_copied": traj_copied,
            "workspace_files_copied": tmp_copied
        }
    }
    
    info_file = task_output_dir / "task_info.json"
    try:
        with open(info_file, "w", encoding="utf-8") as f:
            json.dump(task_info, f, indent=2, ensure_ascii=False)
        print(f"  💾 Saved task info to {info_file}")
    except Exception as e:
        logging.error(f"Failed to save task info: {e}", exc_info=True)
        print(f"  ❌ Error saving task info: {e}")


def cleanup_workspace() -> None:
    """Clean up logs and tmp directories."""
    print("  🧹 Cleaning workspace...")
    try:
        clean_directory(LOGS_PATH)
        print(f"    ✓ Cleaned logs directory")
    except Exception as e:
        logging.error(f"Failed to clean logs directory: {e}", exc_info=True)
        print(f"    ✗ Failed to clean logs: {e}")
    
    try:
        clean_directory(WORKSPACE_PATH)
        print(f"    ✓ Cleaned workspace directory")
    except Exception as e:
        logging.error(f"Failed to clean workspace directory: {e}", exc_info=True)
        print(f"    ✗ Failed to clean workspace: {e}")


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


def process_single_task(
    agent: Agent,
    llm_client: OpenAI,
    task_id: str,
    question: str,
    ground_truth: str,
    formalization: list = None,
    urls: list = None,
    task_index: int = 0,
    total_tasks: int = 0
) -> bool:
    """Process a single task and return whether it succeeded."""
    print("\n" + "=" * 80)
    print(f"📋 Task {task_index}/{total_tasks}")
    print("=" * 80)
    print(f"🆔 Task ID: {task_id}")
    print(f"❓ Question: {question[:200]}{'...' if len(question) > 200 else ''}")
    print(f"🎯 Ground Truth: {ground_truth}")
    print("\n🚀 Executing task...\n")

    try:
        # Create and run task
        task = Task(
            id=task_id,
            input=question,
            agent=agent,
            conf=TaskConfig(max_steps=50),
        )

        # Execute
        result_map = Runners.sync_run_task(task=task)
        task_response = result_map.get(task.id) if result_map else None

        # Get predicted answer
        predicted_answer_raw = ""
        if task_response and task_response.answer:
            predicted_answer_raw = task_response.answer
            print(f"\n✅ Task completed!")
            print(f"🤖 Raw Response: {predicted_answer_raw[:200]}{'...' if len(predicted_answer_raw) > 200 else ''}")
        else:
            print("\n⚠️ No answer generated")
            predicted_answer_raw = "NO_ANSWER"

        # Extract answer from tags
        extracted_answer = extract_answer_from_tags(predicted_answer_raw)
        print(f"📝 Extracted Answer: {extracted_answer}")

        # Compare with ground truth using LLM
        print(f"\n🔍 Comparing with ground truth using LLM...")
        is_correct = compare_answers_with_llm(
            extracted_answer, ground_truth, llm_client
        )
        
        status = "✅ CORRECT" if is_correct else "❌ INCORRECT"
        print(f"\n{status}")
        print(f"  Ground Truth: {ground_truth}")
        print(f"  Extracted:    {extracted_answer}")

        # Wait briefly to ensure all logs/files are flushed to disk
        print(f"\n💾 Saving results...")
        print(f"  ⏳ Waiting for file system to flush...")
        time.sleep(2)  # Give time for logs and files to be written
        
        save_task_results(
            task_id=task_id,
            question=question,
            ground_truth=ground_truth,
            predicted_answer=predicted_answer_raw,
            extracted_answer=extracted_answer,
            is_success=is_correct,
            formalization=formalization,
            urls=urls
        )

        # Cleanup workspace for next task
        cleanup_workspace()

        return is_correct

    except Exception as e:
        print(f"\n❌ Error processing task: {e}")
        logging.error(f"Task error: {e}", exc_info=True)
        
        # Wait briefly to capture any partial logs/files before saving
        print(f"  ⏳ Waiting to capture partial results...")
        time.sleep(2)
        
        # Still save the failed result
        save_task_results(
            task_id=task_id,
            question=question,
            ground_truth=ground_truth,
            predicted_answer=f"ERROR: {str(e)}",
            extracted_answer="",
            is_success=False,
            formalization=formalization,
            urls=urls
        )
        
        # Cleanup workspace
        cleanup_workspace()
        
        return False


def main():
    """Main batch processing function."""
    print("\n" + "=" * 80)
    print("WebShaper Dataset Batch Processing")
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
    os.makedirs(OUTPUT_BASE_PATH, exist_ok=True)
    os.environ["AWORLD_WORKSPACE"] = WORKSPACE_PATH
    print(f"📁 Workspace: {WORKSPACE_PATH}")
    print(f"📁 Output: {OUTPUT_BASE_PATH}")

    # Load MCP configuration
    mcp_config = load_mcp_config()
    if not mcp_config:
        print("❌ Failed to load MCP configuration")
        return

    # Load WebShaper dataset
    print("\n📦 Loading WebShaper dataset...")
    try:
        dataset = load_dataset("Alibaba-NLP/WebShaper", split="main")
        print(f"✅ Loaded {len(dataset)} tasks from WebShaper dataset")
    except Exception as e:
        print(f"❌ Failed to load dataset: {e}")
        return

    # Create agent once (reuse for all tasks)
    print("\n🎭 Creating orchestrator agent...")
    agent = create_agent(mcp_config)

    # Create OpenAI client for answer comparison
    print("🤖 Creating LLM client for answer comparison...")
    llm_client = OpenAI(
        api_key=os.getenv("LLM_API_KEY"),
        base_url=os.getenv("LLM_BASE_URL")
    )

    # Process all tasks
    total_tasks = len(dataset)
    success_count = 0
    fail_count = 0

    for idx, item in enumerate(dataset, start=1):
        task_id = item["id"]
        if task_id != "d00abb6d-8650-4f0b-9792-a205d6795e56":
            continue
        question = item["question"]
        ground_truth = item["answer"]
        formalization = item.get("formalization", [])
        urls = item.get("urls", [])

        is_success = process_single_task(
            agent=agent,
            llm_client=llm_client,
            task_id=task_id,
            question=question,
            ground_truth=ground_truth,
            formalization=formalization,
            urls=urls,
            task_index=idx,
            total_tasks=total_tasks
        )

        if is_success:
            success_count += 1
        else:
            fail_count += 1

        print(f"\n📊 Progress: {idx}/{total_tasks} | ✅ Success: {success_count} | ❌ Failed: {fail_count}")
        time.sleep(2)  # Give time for logs and files to be written

    # Final summary
    print("\n" + "=" * 80)
    print("🎉 Batch Processing Complete!")
    print("=" * 80)
    print(f"Total Tasks:    {total_tasks}")
    print(f"✅ Successful:  {success_count} ({success_count/total_tasks*100:.1f}%)")
    print(f"❌ Failed:      {fail_count} ({fail_count/total_tasks*100:.1f}%)")
    print(f"\n📁 Results saved to: {OUTPUT_BASE_PATH}")
    print("=" * 80)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n👋 Goodbye!")
        sys.exit(0)
