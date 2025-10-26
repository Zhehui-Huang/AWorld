import argparse
import json
import logging
import os
import sys
import traceback
from pathlib import Path
from typing import Any, Dict, Iterable, Tuple

from dotenv import load_dotenv

from aworld.agents.llm_agent import Agent
from aworld.config.conf import AgentConfig, TaskConfig
from aworld.core.task import Task
from aworld.runner import Runners
from examples.gaia.agent_collections.search_agent.prompt import system_prompt


def setup_logging():
    logging_logger = logging.getLogger()
    logging_logger.setLevel(logging.INFO)

    log_file_name = f"/search_agent.log"
    file_handler = logging.FileHandler(
        os.getenv("AWORLD_WORKSPACE", "~") + log_file_name,
        mode="a",
        encoding="utf-8",
    )
    file_handler.setLevel(logging.INFO)

    formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
    file_handler.setFormatter(formatter)

    logging_logger.addHandler(file_handler)
    # Also log to stderr for visibility
    if not any(isinstance(h, logging.StreamHandler) for h in logging_logger.handlers):
        stream_handler = logging.StreamHandler(sys.stderr)
        stream_handler.setLevel(logging.INFO)
        stream_handler.setFormatter(formatter)
        logging_logger.addHandler(stream_handler)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the standalone search agent.")
    parser.add_argument(
        "--input-file",
        type=str,
        help="Path to JSONL file of tasks. Each line: {id?, query|string?}. If string, it's the query.",
    )
    parser.add_argument(
        "--stdin",
        action="store_true",
        help="Read JSONL tasks from stdin (one JSON object or plain text query per line).",
    )
    parser.add_argument(
        "--prompt",
        type=str,
        default="Find one AI regulation paper that was originally submitted to arXiv.org in June 2022 and download it",
        help="Single query to run (for quick testing).",
    )
    parser.add_argument(
        "--output-file",
        type=str,
        help="Write JSONL results to this file (defaults to stdout).",
    )
    parser.add_argument(
        "--max-steps",
        type=int,
        default=12,
        help="Max agent steps per task.",
    )
    return parser.parse_args()


def iter_tasks_from_input(args: argparse.Namespace) -> Iterable[Tuple[str, str]]:
    def parse_line(line: str, idx: int) -> Tuple[str, str] | None:
        line = line.strip()
        if not line:
            return None
        try:
            obj = json.loads(line)
            if isinstance(obj, dict):
                task_id = str(obj.get("id") or obj.get("task_id") or idx)
                query = obj.get("query") or obj.get("text") or obj.get("q") or obj.get("task")
                if isinstance(query, str) and query.strip():
                    return task_id, query.strip()
                # If the object itself is a single-key with string value
                if len(obj) == 1:
                    only_val = next(iter(obj.values()))
                    if isinstance(only_val, str) and only_val.strip():
                        return task_id, only_val.strip()
                return None
            if isinstance(obj, str):
                return str(idx), obj.strip()
        except Exception:
            # Treat as raw query string
            if line:
                return str(idx), line
        return None

    if args.prompt:
        yield ("single", args.prompt)
        return

    if args.input_file:
        with open(args.input_file, "r", encoding="utf-8") as f:
            for i, line in enumerate(f, start=1):
                parsed = parse_line(line, i)
                if parsed:
                    yield parsed
        return

    if args.stdin:
        for i, line in enumerate(sys.stdin, start=1):
            parsed = parse_line(line, i)
            if parsed:
                yield parsed
        return

    raise SystemExit("No input provided. Use --prompt, --input-file, or --stdin.")


if __name__ == "__main__":
    load_dotenv()
    setup_logging()
    args = parse_args()

    # Load MCP configuration
    available_servers: list[str] = []
    try:
        with open(Path(__file__).parent / "mcp.json", mode="r", encoding="utf-8") as f:
            mcp_config: Dict[str, Any] = json.loads(f.read())
            available_servers = list(mcp_config.get("mcpServers", {}).keys())
            logging.info(f"🔧 MCP Available Servers: {available_servers}")
    except json.JSONDecodeError as e:
        logging.error(f"Error loading mcp.json: {e}")
        mcp_config = {}
    except FileNotFoundError:
        logging.warning("mcp.json not found; continuing without MCP servers")
        mcp_config = {}

    # Build agent
    agent_config = AgentConfig(
        llm_provider=os.getenv("LLM_PROVIDER", "openai"),
        llm_model_name=os.getenv("LLM_MODEL_NAME", "gpt-4o"),
        llm_base_url=os.getenv("LLM_BASE_URL"),
        llm_api_key=os.getenv("LLM_API_KEY"),
        llm_temperature=float(os.getenv("LLM_TEMPERATURE", 0.0)),
    )
    search_agent = Agent(
        conf=agent_config,
        name="search_agent",
        system_prompt=system_prompt,
        mcp_config=mcp_config,
        mcp_servers=available_servers,
    )

    # Prepare output stream
    out_fp = None
    try:
        if args.output_file:
            out_fp = open(args.output_file, "w", encoding="utf-8")
        output_stream = out_fp if out_fp else sys.stdout

        # Process tasks
        for task_idx, (task_id, query) in enumerate(iter_tasks_from_input(args), start=1):
            try:
                logging.info(f"Start to process task: {task_id}")
                logging.info(f"Query: {query}")

                task = Task(id=str(task_id), input=query, agent=search_agent, conf=TaskConfig(max_steps=args.max_steps))
                result_map = Runners.sync_run_task(task=task)
                answer = result_map[task.id].answer if result_map and task.id in result_map else None

                record = {
                    "id": task_id,
                    "query": query,
                    "response": answer,
                    "success": bool(answer and str(answer).strip()),
                }

                output_stream.write(json.dumps(record, ensure_ascii=False) + "\n")
                output_stream.flush()
            except KeyboardInterrupt:
                raise
            except Exception:
                logging.error(f"Error processing task {task_id}: {traceback.format_exc()}")
                record = {
                    "id": task_id,
                    "query": query,
                    "response": None,
                    "success": False,
                    "error": "processing_failed",
                }
                output_stream.write(json.dumps(record, ensure_ascii=False) + "\n")
                output_stream.flush()
    except KeyboardInterrupt:
        pass
    finally:
        if out_fp:
            out_fp.close()
