# coding: utf-8
# Copyright (c) 2025 inclusionAI.
import os

from aworld.config.conf import ModelConfig
from aworld.core.task import Task
from aworld.runner import Runners
from examples.gaia.agent_collections.search_agent.agent import SearchAgent
from examples.gaia.agent_collections.search_agent.config import SearchAgentConfig
from examples.common.tools.common import Agents, Tools
from examples.common.tools.conf import SearchToolConfig

# os.environ["LLM_MODEL_NAME"] = "YOUR_LLM_MODEL_NAME"
# os.environ["LLM_BASE_URL"] = "YOUR_LLM_BASE_URL"
# os.environ["LLM_API_KEY"] = "YOUR_LLM_API_KEY"

if __name__ == '__main__':
    llm_config = ModelConfig(
        llm_provider=os.getenv("LLM_PROVIDER", "openai"),
        llm_model_name=os.getenv("LLM_MODEL_NAME"),
        llm_base_url=os.getenv("LLM_BASE_URL"),
        llm_api_key=os.getenv("LLM_API_KEY"),
        llm_temperature=os.getenv("LLM_TEMPERATURE", 0.0)
    )
    search_tool_config = SearchToolConfig(
        headless=False,
        use_async=False,
        custom_executor=True,
        llm_config=llm_config
    )

    agent_config = SearchAgentConfig(
        name=Agents.SEARCH.value,
        tool_calling_method="raw",
        llm_config=llm_config,
        max_actions_per_step=10,
        max_input_tokens=128000,
        working_dir="",
        # llm model not supported vision, need to set `False`
        # use_vision=False
    )

    task_config = {
        'max_steps': 100,
        'max_actions_per_step': 100,
        'resp_carry_context': True,
        'stream': False,
        'resp_carry_raw_llm_resp': False,
        'exit_on_failure': False
    }

    task = Task(
        input="""Find all papers about AI regulation that was originally submitted to arXiv.org in June 2022 and save that.""",
        agent=SearchAgent(conf=agent_config, name=Agents.SEARCH.value, tool_names=[Tools.SEARCH_API.name]),
        tools_conf={Tools.SEARCH_API.value: search_tool_config},
        conf=task_config
    )
    Runners.sync_run_task(task)
