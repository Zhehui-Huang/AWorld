"""
Search Agent MCP Server

This module provides MCP server functionality for performing web searches using various search engines.
It supports structured queries and returns LLM-friendly formatted search results.

Key features:
- Perform web searches using Google Custom Search API
- Filter and format search results for LLM consumption
- Validate and process search queries with metadata tracking
- download files

Main functions:
- mcp_create_search_agent: Create search agent
- mcp_use_existing_search_agent: Use existing search agent
- mcp_get_search_agent_capabilities: Returns information about search agent service capabilities
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
    """MCP service for web search agent that able to use various search engines and download needed files.

    Provides comprehensive web search capabilities including:
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
        description: str = Field(
            default="Search agent specialized in web search and file retrieval",
            description="Description of the search agent's purpose",
        ),
        max_steps: int = Field(default=12, description="Maximum steps for agent execution"),
    ) -> ActionResponse:
        """
        Create a new search agent and execute the given task.

        This method creates a search agent with:
        1. Unique agent ID
        2. Custom name and description
        3. Independent LLM instance (configured via environment variables)
        4. Dedicated memory module
        5. MCP tools (search and download)

        The agent will autonomously handle its thinking, planning, and tool calls
        to complete the task.

        Args:
            task_prompt: The task or query to process
            name: Name for the agent
            description: Description of agent's purpose
            max_steps: Maximum execution steps

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
        if isinstance(max_steps, FieldInfo):
            max_steps = max_steps.default

        try:
            self._color_log(f"🤖 Creating new search agent: {name}", Color.cyan)

            # Create agent instance (LLM config loaded from environment)
            agent, metadata = self._create_agent_instance(
                name=name,
                description=description,
            )

            self._color_log(f"✅ Agent created with ID: {metadata.agent_id}", Color.green)

            # Execute task with the agent
            self._color_log(f"🚀 Executing task: {task_prompt}", Color.cyan)

            task = Task(
                id=str(uuid.uuid4().hex),
                input=task_prompt,
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

            # Format response
            formatted_message = f"""# Search Agent Created Successfully

**Agent ID:** `{metadata.agent_id}`
**Agent Name:** `{metadata.name}`
**Description:** {metadata.description}

## Task Results
**Task:** {task_prompt}
**Answer:** {answer if answer else "No answer generated"}

---
*Agent ID `{metadata.agent_id}` is now registered and can be reused with `mcp_use_existing_search_agent`.*
"""

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
        max_steps: int = Field(default=12, description="Maximum steps for agent execution"),
    ) -> ActionResponse:
        """
        Use an existing search agent to execute a task.

        This method reuses a previously created search agent, maintaining its
        configuration, memory, and state across multiple tasks.

        Args:
            agent_id: ID of the existing search agent
            task_prompt: The task or query to process
            max_steps: Maximum execution steps

        Returns:
            ActionResponse with execution results and agent metadata
        """
        # Handle FieldInfo objects
        if isinstance(agent_id, FieldInfo):
            agent_id = agent_id.default
        if isinstance(task_prompt, FieldInfo):
            task_prompt = task_prompt.default
        if isinstance(max_steps, FieldInfo):
            max_steps = max_steps.default

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

            # Execute task with the agent
            self._color_log(f"🚀 Executing task: {task_prompt}", Color.cyan)

            task = Task(
                id=str(uuid.uuid4().hex),
                input=task_prompt,
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

            # Format response
            formatted_message = f"""# Use Existing Search Agent Successfully

**Agent ID:** `{metadata.agent_id}`
**Agent Name:** `{metadata.name}`
**Description:** {metadata.description}

## Task Results
**Task:** {task_prompt}
**Answer:** {answer if answer else "No answer generated"}
"""

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

    def mcp_get_search_agent_capabilities(self) -> ActionResponse:
        """Get information about search service agent capabilities and configuration.

        Returns:
            ActionResponse with search service capabilities and current configuration
        """
        # Get list of registered agents
        registered_agents = [
            {"agent_id": m.agent_id, "name": m.name, "description": m.description}
            for m in self.agent_registry.list_agents()
        ]

        capabilities = {
            "service_name": "Search Agent MCP Server",
            "version": "1.0.0",
            "description": "Dynamic multi-layer agent architecture for search and retrieval tasks",
            "features": [
                "Create independent search agents with dedicated LLM and memory",
                "Reuse existing agents across multiple tasks",
                "Autonomous task execution with think-act-observe loop",
                "Web search using Google Custom Search API",
                "File download from HTTP/HTTPS URLs",
                "LLM-optimized result formatting",
                "Agent registry for managing multiple agent instances",
            ],
            "mcp_tools": list(self.mcp_config.get("mcpServers", {}).keys()),
            "supported_operations": [
                "mcp_create_search_agent: Create and execute with new agent",
                "mcp_use_existing_search_agent: Execute with existing agent",
                "mcp_get_search_agent_capabilities: Get service information",
            ],
            "registered_agents": registered_agents,
            "agent_count": len(registered_agents),
            "configuration": {
                "workspace": str(self.workspace),
                "default_max_steps": 12,
                "default_temperature": 0.0,
            },
        }

        formatted_info = f"""# Search Agent MCP Server Capabilities

## Overview
**Service:** {capabilities["service_name"]}
**Version:** {capabilities["version"]}
**Description:** {capabilities["description"]}

## Features
{chr(10).join(f"- {feature}" for feature in capabilities["features"])}

## Available MCP Tools
{chr(10).join(f"- {tool}" for tool in capabilities["mcp_tools"])}

## Supported Operations
{chr(10).join(f"- {op}" for op in capabilities["supported_operations"])}

## Registered Agents
**Total Agents:** {capabilities["agent_count"]}
{chr(10).join(f"- **{agent['agent_id']}** ({agent['name']}): {agent['description']}" for agent in registered_agents) if registered_agents else "No agents registered yet."}

## Configuration
- **Workspace:** `{capabilities["configuration"]["workspace"]}`
- **Default Max Steps:** {capabilities["configuration"]["default_max_steps"]}
- **Default Temperature:** {capabilities["configuration"]["default_temperature"]}
"""

        return ActionResponse(success=True, message=formatted_info, metadata=capabilities)


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
