"""
Search Agent MCP Server

This module provides MCP server functionality for performing file finding and downloading using various search engines.
It supports structured queries and returns LLM-friendly formatted search results.

Key features:
- Perform file finding and downloading using Google Custom Search API
- Filter and format search results for LLM consumption
- Validate and process search queries with metadata tracking
- download files

Main functions:
- mcp_create_search_agent: Create search agent
- mcp_use_existing_search_agent: Use existing search agent
"""

import json
import os
import traceback
import uuid
from pathlib import Path
from typing import Any, Dict, Optional

from dotenv import load_dotenv
from pydantic import BaseModel, Field
from pydantic.fields import FieldInfo

from aworld.agents.llm_agent import Agent
from aworld.config.conf import AgentConfig, TaskConfig
from aworld.core.task import Task
from aworld.logs.util import Color, logger
from aworld.runner import Runners
from examples.gaia.agent_collections.search_agent.prompt import system_prompt
from examples.gaia.mcp_collections.base import ActionArguments, ActionCollection, ActionResponse
from examples.gaia.agent_collections.shared_memory import get_agent_memory
from examples.gaia.agent_collections.agent_memory_utils import save_task_memory_with_analysis


class SearchAgentMetadata(BaseModel):
    """Metadata for a search agent instance."""

    agent_id: str
    name: str
    description: str
    mcp_servers: list[str]


class AgentRegistry:
    """Registry to manage created search agent instances."""

    def __init__(self):
        self._agents: Dict[str, Agent] = {}
        self._metadata: Dict[str, SearchAgentMetadata] = {}

    def register(self, agent: Agent, metadata: SearchAgentMetadata) -> None:
        """Register a new agent instance."""
        self._agents[metadata.agent_id] = agent
        self._metadata[metadata.agent_id] = metadata

    def get_agent(self, agent_id: str) -> Optional[Agent]:
        """Get an agent by ID."""
        return self._agents.get(agent_id)

    def get_metadata(self, agent_id: str) -> Optional[SearchAgentMetadata]:
        """Get agent metadata by ID."""
        return self._metadata.get(agent_id)

    def list_agents(self) -> list[SearchAgentMetadata]:
        """List all registered agents."""
        return list(self._metadata.values())

    def exists(self, agent_id: str) -> bool:
        """Check if an agent exists."""
        return agent_id in self._agents


class SearchAgentCollection(ActionCollection):
    """MCP service for file finding and downloading agent that able to use various search engines and download needed files.

    Provides comprehensive file finding and downloading capabilities including:
    - create search agent
    - reuse existing search agent
    """

    def __init__(self, arguments: ActionArguments) -> None:
        super().__init__(arguments)
        # Initialize agent registry
        self.agent_registry = AgentRegistry()
        # Load MCP configuration for search tools
        self.mcp_config = self._load_mcp_config()
        # Log initialization status
        self._color_log("Search agent service initialized", Color.green, "debug")

    def _load_mcp_config(self) -> Dict[str, Any]:
        """Load MCP configuration for search agent tools."""
        try:
            mcp_path = Path(__file__).parent / "mcp.json"
            with open(mcp_path, mode="r", encoding="utf-8") as f:
                mcp_config = json.loads(f.read())
                available_servers = list(mcp_config.get("mcpServers", {}).keys())
                self._color_log(f"Loaded MCP servers: {available_servers}", Color.blue, "debug")
                return mcp_config
        except Exception as e:
            self.logger.error(f"Error loading mcp.json: {e}")
            return {}

    def _create_agent_instance(
        self,
        name: str,
        description: str,
        parent_agent_id: Optional[str] = None,
    ) -> tuple[Agent, SearchAgentMetadata]:
        """Create a new search agent instance with its own configuration."""
        # Generate unique agent ID
        agent_id = f"search_agent_{uuid.uuid4().hex[:8]}"

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
        available_servers = list(self.mcp_config.get("mcpServers", {}).keys())

        # Create agent with MCP tools
        agent = Agent(
            conf=agent_config,
            name=name,
            agent_id=agent_id,
            system_prompt=system_prompt,
            mcp_config=self.mcp_config,
            mcp_servers=available_servers,
        )
        
        # Update logger with parent information and correct agent type
        if hasattr(agent, 'llm_json_dataset_logger'):
            agent.llm_json_dataset_logger.agent_type = "search_agent"
            if parent_agent_id:
                agent.llm_json_dataset_logger.parent_agent_id = parent_agent_id

        # Create metadata
        metadata = SearchAgentMetadata(
            agent_id=agent_id,
            name=name,
            description=description,
            mcp_servers=available_servers,
        )

        # Register agent
        self.agent_registry.register(agent, metadata)

        return agent, metadata

    def mcp_create_search_agent(
        self,
        task_prompt: str = Field(description="The task or query for the search agent to process"),
        name: str = Field(default="search_agent", description="Name for the search agent"),
        description: str = Field(description="Description of the search agent's purpose"),
    ) -> ActionResponse:
        """
        Create a new search agent and execute the given task. 
        What search agents do:
            - Find files
            - Download files
        What search agents not do:
            - Process files
            - Analyze files
            - Extract information from files

        This method creates a search agent with:
        1. Unique agent ID
        2. Custom name and description
        3. Independent LLM instance
        4. Dedicated memory module
        5. MCP tools (search and download)

        Args:
            task_prompt: The task or query to process
            name: Name for the agent
            description: Description of agent's purpose

        Returns:
            ActionResponse with execution results and agent metadata
        """
        # Handle FieldInfo objects
        if isinstance(task_prompt, FieldInfo):
            task_prompt = task_prompt.default
        if isinstance(name, FieldInfo):
            name = name.default
        if isinstance(description, FieldInfo):
            description = description.default
        
        # Load max_steps from environment variable
        max_steps = int(os.getenv("SEARCH_AGENT_MAX_STEPS", "50"))

        try:
            self._color_log(f"🤖 Creating new search agent: {name}", Color.cyan)

            # Create agent instance (LLM config loaded from environment)
            agent, metadata = self._create_agent_instance(
                name=name,
                description=description,
            )

            self._color_log(f"✅ Agent created with ID: {metadata.agent_id}", Color.green)

            # Retrieve relevant memories from past tasks
            memory = get_agent_memory()
            relevant_memories = memory.retrieve_relevant_memories(
                agent_id=metadata.agent_id,
                task_description=task_prompt,
                max_results=3
            )
            
            if relevant_memories:
                self._color_log(
                    f"🧠 Retrieved {len(relevant_memories)} relevant past experiences",
                    Color.blue
                )
            
            # Add agent ID to task prompt
            task_prompt_with_id = f"[Agent ID: {metadata.agent_id}]\n\n{task_prompt}"
            
            # Enhance task prompt with past experiences
            enhanced_task_prompt = task_prompt_with_id
            if relevant_memories:
                memory_context = memory.format_memories_for_prompt(relevant_memories)
                enhanced_task_prompt = f"{task_prompt_with_id}\n\n##\nPrevious Experience:\n{memory_context}\n##"

            # Execute task with the agent
            self._color_log(f"🚀 Executing task: {task_prompt[:100]}...", Color.cyan)

            task = Task(
                id=str(uuid.uuid4().hex),
                input=enhanced_task_prompt,
                agent=agent,
                conf=TaskConfig(max_steps=max_steps),
            )

            result_map = Runners.sync_run_task(task=task)
            task_response = result_map.get(task.id) if result_map else None

            if task_response and task_response.answer:
                answer = task_response.answer
                self._color_log(f"✅ Task completed successfully", Color.green)
            else:
                answer = None
                self._color_log(f"⚠️ Task completed with no answer", Color.yellow)

            # Extract artifacts and experience summary, then save task memory
            save_task_memory_with_analysis(
                memory=memory,
                agent=agent,
                task_id=task.id,
                agent_id=metadata.agent_id,
                agent_type="search_agent",
                task_prompt=task_prompt,
                answer=answer,
                logger_func=lambda msg, level: self._color_log(msg, Color.blue, level)
            )

            # Format response
            formatted_message = answer

            return ActionResponse(
                success=True,
                message=formatted_message,
                metadata={
                    "agent_id": metadata.agent_id,
                    "agent_name": metadata.name,
                    "description": metadata.description,
                    "mcp_servers": metadata.mcp_servers,
                },
            )

        except Exception as e:
            error_msg = f"Failed to create and execute search agent: {str(e)}"
            self.logger.error(f"Search agent error: {traceback.format_exc()}")
            self._color_log(f"❌ {error_msg}", Color.red)

            return ActionResponse(
                success=False,
                message=error_msg,
                metadata={"error_type": "agent_creation_failed", "error_details": str(e)},
            )

    def mcp_use_existing_search_agent(
        self,
        agent_id: str = Field(description="The ID of an existing search agent to use"),
        task_prompt: str = Field(description="The task or query for the search agent to process"),
    ) -> ActionResponse:
        """
        Use an existing search agent to execute a task.

        This method reuses a previously created search agent, maintaining its configuration, memory, and state across multiple tasks.

        Args:
            agent_id: ID of the existing search agent
            task_prompt: The task or query to process

        Returns:
            ActionResponse with execution results and agent metadata
        """
        # Handle FieldInfo objects
        if isinstance(agent_id, FieldInfo):
            agent_id = agent_id.default
        if isinstance(task_prompt, FieldInfo):
            task_prompt = task_prompt.default
        
        # Load max_steps from environment variable
        max_steps = int(os.getenv("SEARCH_AGENT_MAX_STEPS", "50"))

        try:
            # Check if agent exists
            if not self.agent_registry.exists(agent_id):
                available_agents = [m.agent_id for m in self.agent_registry.list_agents()]
                return ActionResponse(
                    success=False,
                    message=f"Agent ID '{agent_id}' not found. Available agents: {available_agents}",
                    metadata={"error_type": "agent_not_found", "available_agents": available_agents},
                )

            # Get existing agent
            agent = self.agent_registry.get_agent(agent_id)
            metadata = self.agent_registry.get_metadata(agent_id)
            
            if not agent or not metadata:
                return ActionResponse(
                    success=False,
                    message=f"Agent ID '{agent_id}' exists in registry but agent or metadata is None",
                    metadata={"error_type": "agent_data_corrupted"},
                )

            self._color_log(f"🔄 Using existing search agent: {metadata.name} ({agent_id})", Color.cyan)

            # Retrieve relevant memories from past tasks
            memory = get_agent_memory()
            relevant_memories = memory.retrieve_relevant_memories(
                agent_id=metadata.agent_id,
                task_description=task_prompt,
                max_results=3
            )
            
            if relevant_memories:
                self._color_log(
                    f"🧠 Retrieved {len(relevant_memories)} relevant past experiences",
                    Color.blue
                )
            
            # Add agent ID to task prompt
            task_prompt_with_id = f"[Agent ID: {metadata.agent_id}]\n\n{task_prompt}"
            
            # Enhance task prompt with past experiences
            enhanced_task_prompt = task_prompt_with_id
            if relevant_memories:
                memory_context = memory.format_memories_for_prompt(relevant_memories)
                enhanced_task_prompt = f"{task_prompt_with_id}\n\n##\nPrevious Experience:\n{memory_context}\n##"

            # Execute task with the agent
            self._color_log(f"🚀 Executing task: {task_prompt[:100]}...", Color.cyan)

            task = Task(
                id=str(uuid.uuid4().hex),
                input=enhanced_task_prompt,
                agent=agent,
                conf=TaskConfig(max_steps=max_steps),
            )

            result_map = Runners.sync_run_task(task=task)
            task_response = result_map.get(task.id) if result_map else None

            if task_response and task_response.answer:
                answer = task_response.answer
                self._color_log(f"✅ Task completed successfully", Color.green)
            else:
                answer = None
                self._color_log(f"⚠️ Task completed with no answer", Color.yellow)

            # Extract artifacts and experience summary, then save task memory
            save_task_memory_with_analysis(
                memory=memory,
                agent=agent,
                task_id=task.id,
                agent_id=metadata.agent_id,
                agent_type="search_agent",
                task_prompt=task_prompt,
                answer=answer,
                logger_func=lambda msg, level: self._color_log(msg, Color.blue, level)
            )

            # Format response
            formatted_message = answer

            return ActionResponse(
                success=True,
                message=formatted_message,
                metadata={
                    "agent_id": metadata.agent_id,
                    "agent_name": metadata.name,
                    "description": metadata.description,
                    "mcp_servers": metadata.mcp_servers,
                },
            )

        except Exception as e:
            error_msg = f"Failed to execute task with existing agent: {str(e)}"
            self.logger.error(f"Search agent error: {traceback.format_exc()}")
            self._color_log(f"❌ {error_msg}", Color.red)

            return ActionResponse(
                success=False,
                message=error_msg,
                metadata={"error_type": "agent_execution_failed", "error_details": str(e)},
            )

# Example usage and entry point
if __name__ == "__main__":
    load_dotenv()

    # Default arguments for testing
    args = ActionArguments(
        name="search_agent_service",
        transport="stdio",
        workspace=os.getenv("AWORLD_WORKSPACE", "~"),
    )

    # Initialize and run the search service
    try:
        service = SearchAgentCollection(args)
        service.run()
    except Exception as e:
        print(f"An error occurred: {e}: {traceback.format_exc()}")
