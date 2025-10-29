"""
Orchestrator Agent MCP Server

This module provides MCP server functionality for hierarchical multi-agent orchestration.
It supports recursive orchestration where orchestrators can create sub-orchestrators to manage
complex multi-agent workflows.

Key features:
- Create orchestrator agents that coordinate multiple specialized agents
- Support recursive orchestration (orchestrators creating orchestrators)
- Dynamically configure available agents for each orchestrator
- Manage agent lifecycle and state across nested orchestrations
- Enable parallel and sequential execution patterns

Main functions:
- mcp_create_orchestrator_agent: Create new orchestrator agent
- mcp_use_existing_orchestrator_agent: Reuse existing orchestrator
- mcp_get_orchestrator_capabilities: Get orchestrator service information
"""

import json
import os
import time
import traceback
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional

import requests
from dotenv import load_dotenv
from pydantic import BaseModel, Field
from pydantic.fields import FieldInfo

from aworld.agents.llm_agent import Agent
from aworld.config.conf import AgentConfig, TaskConfig
from aworld.core.task import Task
from aworld.logs.util import Color, logger
from aworld.runner import Runners
from examples.gaia.agent_collections.orchestrator_agent.prompt import system_prompt
from examples.gaia.mcp_collections.base import ActionArguments, ActionCollection, ActionResponse


class OrchestratorMetadata(BaseModel):
    """Metadata for an orchestrator agent instance."""

    agent_id: str
    name: str
    description: str
    created_at: str
    llm_provider: str
    llm_model_name: str
    available_agents: list[str]
    orchestration_level: int
    parent_orchestrator_id: Optional[str] = None


class AgentRegistry:
    """Registry to manage created orchestrator agent instances."""

    def __init__(self):
        self._agents: Dict[str, Agent] = {}
        self._metadata: Dict[str, OrchestratorMetadata] = {}

    def register(self, agent: Agent, metadata: OrchestratorMetadata) -> None:
        """Register a new agent instance."""
        self._agents[metadata.agent_id] = agent
        self._metadata[metadata.agent_id] = metadata

    def get_agent(self, agent_id: str) -> Optional[Agent]:
        """Get an agent by ID."""
        return self._agents.get(agent_id)

    def get_metadata(self, agent_id: str) -> Optional[OrchestratorMetadata]:
        """Get agent metadata by ID."""
        return self._metadata.get(agent_id)

    def list_agents(self) -> list[OrchestratorMetadata]:
        """List all registered agents."""
        return list(self._metadata.values())

    def exists(self, agent_id: str) -> bool:
        """Check if an agent exists."""
        return agent_id in self._agents


class OrchestratorAgentCollection(ActionCollection):
    """MCP service for hierarchical orchestrator agent that coordinates multiple specialized agents.

    Provides recursive orchestration capabilities including:
    - Create orchestrator agents with configurable sub-agent access
    - Support nested orchestration (orchestrators creating orchestrators)
    - Manage complex multi-agent workflows
    - Enable parallel and sequential execution patterns
    """

    def __init__(self, arguments: ActionArguments) -> None:
        super().__init__(arguments)
        # Initialize agent registry
        self.agent_registry = AgentRegistry()
        # Load base MCP configuration for all available agents
        self.base_mcp_config = self._load_base_mcp_config()
        # Track orchestration level for debugging
        self.orchestration_level = int(os.getenv("ORCHESTRATION_LEVEL", "0"))
        # Log initialization status
        self._color_log(
            f"Orchestrator agent service initialized (level {self.orchestration_level})", Color.green, "debug"
        )

    def _load_base_mcp_config(self) -> Dict[str, Any]:
        """Load base MCP configuration with all available agents."""
        try:
            # Load the main MCP config that has all agent servers
            mcp_path = Path(__file__).parent.parent / "mcp_v2.json"
            if not mcp_path.exists():
                # Fallback to v1 config
                mcp_path = Path(__file__).parent.parent / "mcp.json"

            with open(mcp_path, mode="r", encoding="utf-8") as f:
                mcp_config = json.loads(f.read())
                available_servers = list(mcp_config.get("mcpServers", {}).keys())
                self._color_log(f"Loaded base MCP servers: {available_servers}", Color.blue, "debug")
                return mcp_config
        except Exception as e:
            self.logger.error(f"Error loading mcp config: {e}")
            return {}

    def _filter_mcp_config(self, available_agents: List[str]) -> Dict[str, Any]:
        """Filter MCP configuration to only include specified agents."""
        if not available_agents:
            return self.base_mcp_config

        filtered_config = {"mcpServers": {}}
        for agent_name in available_agents:
            if agent_name in self.base_mcp_config.get("mcpServers", {}):
                filtered_config["mcpServers"][agent_name] = self.base_mcp_config["mcpServers"][agent_name]
            else:
                self.logger.warning(f"Agent '{agent_name}' not found in base MCP config")

        return filtered_config

    def _create_agent_instance(
        self,
        name: str,
        description: str,
        available_agents: List[str],
        parent_orchestrator_id: Optional[str] = None,
    ) -> tuple[Agent, OrchestratorMetadata]:
        """Create a new orchestrator agent instance with its own configuration."""
        # Generate unique agent ID
        agent_id = f"orchestrator_{uuid.uuid4().hex[:8]}"

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

        # Filter MCP config to only include specified agents
        mcp_config = self._filter_mcp_config(available_agents)
        actual_available_agents = list(mcp_config.get("mcpServers", {}).keys())

        # Update orchestration level in environment for sub-orchestrators
        new_level = self.orchestration_level + 1
        if "orchestrator_agent" in mcp_config.get("mcpServers", {}):
            # Update orchestration level for recursive orchestrators
            env_config = mcp_config["mcpServers"]["orchestrator_agent"].get("env", {})
            env_config["ORCHESTRATION_LEVEL"] = str(new_level)
            mcp_config["mcpServers"]["orchestrator_agent"]["env"] = env_config

        # Create orchestrator agent with filtered MCP tools
        agent = Agent(
            conf=agent_config,
            name=name,
            agent_id=agent_id,
            system_prompt=system_prompt,
            mcp_config=mcp_config,
            mcp_servers=actual_available_agents,
        )

        # Create metadata
        metadata = OrchestratorMetadata(
            agent_id=agent_id,
            name=name,
            description=description,
            created_at=time.strftime("%Y-%m-%d %H:%M:%S"),
            llm_provider=llm_provider,
            llm_model_name=llm_model_name,
            available_agents=actual_available_agents,
            orchestration_level=new_level,
            parent_orchestrator_id=parent_orchestrator_id,
        )

        # Register agent
        self.agent_registry.register(agent, metadata)

        return agent, metadata

    def mcp_create_orchestrator_agent(
        self,
        task_prompt: str = Field(description="The task for the orchestrator to coordinate"),
        name: str = Field(default="orchestrator", description="Name for the orchestrator agent"),
        description: str = Field(
            default="Orchestrator agent for multi-agent coordination",
            description="Description of the orchestrator's purpose",
        ),
        available_agents: List[str] = Field(
            default=["search_agent", "pdf_agent", "image_agent", "orchestrator_agent"],
            description="List of agent types this orchestrator can use (e.g., ['search_agent', 'pdf_agent'])",
        ),
        max_steps: int = Field(default=50, description="Maximum steps for orchestrator execution"),
        parent_orchestrator_id: str = Field(
            default=None, description="ID of parent orchestrator (for tracking hierarchy)"
        ),
    ) -> ActionResponse:
        """
        Create a new orchestrator agent and execute the given task.

        This orchestrator can coordinate multiple specialized agents and even create
        sub-orchestrators for complex workflows requiring nested coordination.

        Key Features:
        1. Dynamic agent selection from available_agents list
        2. Recursive orchestration (can create sub-orchestrators)
        3. Parallel and sequential execution patterns
        4. Context and memory preservation across agent calls
        5. Hierarchical task decomposition

        LLM configuration is loaded from environment variables:
        - LLM_PROVIDER (default: "openai")
        - LLM_MODEL_NAME (default: "gpt-4o")
        - LLM_BASE_URL (optional)
        - LLM_API_KEY (required)
        - LLM_TEMPERATURE (default: "0.0")

        Args:
            task_prompt: The task to orchestrate (provide complete context)
            name: Name for the orchestrator
            description: Description of orchestrator's purpose
            available_agents: List of agent types this orchestrator can use
            max_steps: Maximum execution steps
            parent_orchestrator_id: ID of parent orchestrator (for tracking)

        Returns:
            ActionResponse with execution results and orchestrator metadata

        Example:
            ```
            orchestrator_agent.mcp_create_orchestrator_agent(
                task_prompt="Find paper X from 2022, extract figure with 3 axes, return axis labels",
                name="paper_analyzer",
                available_agents=["search_agent", "pdf_agent", "image_agent"],
                max_steps=20
            )
            ```
        """
        # Handle FieldInfo objects
        if isinstance(task_prompt, FieldInfo):
            task_prompt = task_prompt.default
        if isinstance(name, FieldInfo):
            name = name.default
        if isinstance(description, FieldInfo):
            description = description.default
        if isinstance(available_agents, FieldInfo):
            available_agents = available_agents.default
        if isinstance(max_steps, FieldInfo):
            max_steps = max_steps.default
        if isinstance(parent_orchestrator_id, FieldInfo):
            parent_orchestrator_id = parent_orchestrator_id.default

        try:
            indent = "  " * self.orchestration_level
            self._color_log(
                f"{indent}🎭 Creating orchestrator (level {self.orchestration_level + 1}): {name}", Color.cyan
            )
            self._color_log(f"{indent}   Available agents: {available_agents}", Color.blue, "debug")

            # Create orchestrator instance
            agent, metadata = self._create_agent_instance(
                name=name, description=description, available_agents=available_agents, parent_orchestrator_id=parent_orchestrator_id
            )

            self._color_log(f"{indent}✅ Orchestrator created with ID: {metadata.agent_id}", Color.green)

            # Execute task with the orchestrator
            self._color_log(f"{indent}🚀 Orchestrating task: {task_prompt[:100]}...", Color.cyan)

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
                self._color_log(f"{indent}✅ Orchestration completed successfully", Color.green)
            else:
                answer = None
                self._color_log(f"{indent}⚠️ Orchestration completed with no answer", Color.yellow)

            # Format response
            formatted_message = f"""# Orchestrator Agent Execution Results

**Orchestrator ID:** `{metadata.agent_id}`
**Name:** `{metadata.name}`
**Description:** {metadata.description}
**Orchestration Level:** {metadata.orchestration_level}
**Parent Orchestrator:** {metadata.parent_orchestrator_id or "None (Top Level)"}
**Created At:** {metadata.created_at}

## Configuration
- **LLM Provider:** {metadata.llm_provider}
- **LLM Model:** {metadata.llm_model_name}
- **Available Agents:** {', '.join(metadata.available_agents)}

## Task Results
**Task:** {task_prompt}

**Answer:** {answer if answer else "No answer generated"}

---
*Orchestrator ID `{metadata.agent_id}` is registered and can be reused with `mcp_use_existing_orchestrator_agent`.*
"""

            return ActionResponse(
                success=True,
                message=formatted_message,
                metadata={
                    "agent_id": metadata.agent_id,
                    "agent_name": metadata.name,
                    "description": metadata.description,
                    "answer": answer,
                    "task_prompt": task_prompt,
                    "created_at": metadata.created_at,
                    "llm_provider": metadata.llm_provider,
                    "llm_model_name": metadata.llm_model_name,
                    "available_agents": metadata.available_agents,
                    "orchestration_level": metadata.orchestration_level,
                    "parent_orchestrator_id": metadata.parent_orchestrator_id,
                },
            )

        except Exception as e:
            error_msg = f"Failed to create and execute orchestrator: {str(e)}"
            self.logger.error(f"Orchestrator error: {traceback.format_exc()}")
            self._color_log(f"❌ {error_msg}", Color.red)

            return ActionResponse(
                success=False,
                message=error_msg,
                metadata={"error_type": "orchestrator_creation_failed", "error_details": str(e)},
            )

    def mcp_use_existing_orchestrator_agent(
        self,
        agent_id: str = Field(description="The ID of an existing orchestrator to use"),
        task_prompt: str = Field(description="The task for the orchestrator to coordinate"),
        max_steps: int = Field(default=25, description="Maximum steps for execution"),
    ) -> ActionResponse:
        """
        Use an existing orchestrator agent to execute a task.

        This method reuses a previously created orchestrator, maintaining its
        configuration, available agents, and state across multiple tasks.

        Args:
            agent_id: ID of the existing orchestrator
            task_prompt: The task to orchestrate
            max_steps: Maximum execution steps

        Returns:
            ActionResponse with execution results and orchestrator metadata
        """
        # Handle FieldInfo objects
        if isinstance(agent_id, FieldInfo):
            agent_id = agent_id.default
        if isinstance(task_prompt, FieldInfo):
            task_prompt = task_prompt.default
        if isinstance(max_steps, FieldInfo):
            max_steps = max_steps.default

        try:
            # Check if orchestrator exists
            if not self.agent_registry.exists(agent_id):
                available_agents = [m.agent_id for m in self.agent_registry.list_agents()]
                return ActionResponse(
                    success=False,
                    message=f"Orchestrator ID '{agent_id}' not found. Available: {available_agents}",
                    metadata={"error_type": "orchestrator_not_found", "available_orchestrators": available_agents},
                )

            # Get existing orchestrator
            agent = self.agent_registry.get_agent(agent_id)
            metadata = self.agent_registry.get_metadata(agent_id)

            indent = "  " * self.orchestration_level
            self._color_log(f"{indent}🔄 Using existing orchestrator: {metadata.name} ({agent_id})", Color.cyan)

            # Execute task
            self._color_log(f"{indent}🚀 Orchestrating task: {task_prompt[:100]}...", Color.cyan)

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
                self._color_log(f"{indent}✅ Orchestration completed successfully", Color.green)
            else:
                answer = None
                self._color_log(f"{indent}⚠️ Orchestration completed with no answer", Color.yellow)

            # Format response
            formatted_message = f"""# Orchestrator Agent Execution Results

**Orchestrator ID:** `{metadata.agent_id}`
**Name:** `{metadata.name}`
**Description:** {metadata.description}
**Orchestration Level:** {metadata.orchestration_level}

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
                    "answer": answer,
                    "task_prompt": task_prompt,
                    "orchestration_level": metadata.orchestration_level,
                },
            )

        except Exception as e:
            error_msg = f"Failed to execute task with existing orchestrator: {str(e)}"
            self.logger.error(f"Orchestrator error: {traceback.format_exc()}")
            self._color_log(f"❌ {error_msg}", Color.red)

            return ActionResponse(
                success=False,
                message=error_msg,
                metadata={"error_type": "orchestrator_execution_failed", "error_details": str(e)},
            )

    def mcp_get_orchestrator_capabilities(self) -> ActionResponse:
        """Get information about orchestrator service capabilities and configuration.

        Returns:
            ActionResponse with orchestrator service capabilities and current configuration
        """
        # Get list of registered orchestrators
        registered_orchestrators = [
            {
                "agent_id": m.agent_id,
                "name": m.name,
                "description": m.description,
                "created_at": m.created_at,
                "orchestration_level": m.orchestration_level,
                "available_agents": m.available_agents,
            }
            for m in self.agent_registry.list_agents()
        ]

        capabilities = {
            "service_name": "Orchestrator Agent MCP Server",
            "version": "2.0.0",
            "description": "Hierarchical multi-agent orchestration with recursive orchestrator support",
            "features": [
                "Create orchestrator agents with configurable sub-agent access",
                "Recursive orchestration (orchestrators creating orchestrators)",
                "Support parallel and sequential execution patterns",
                "Dynamic agent selection and coordination",
                "Hierarchical task decomposition",
                "Context and memory preservation across nested orchestrations",
                "Agent registry for managing orchestrator instances",
                "Unlimited nesting depth for complex workflows",
            ],
            "available_agent_types": list(self.base_mcp_config.get("mcpServers", {}).keys()),
            "supported_operations": [
                "mcp_create_orchestrator_agent: Create and execute with new orchestrator",
                "mcp_use_existing_orchestrator_agent: Execute with existing orchestrator",
                "mcp_get_orchestrator_capabilities: Get service information",
            ],
            "registered_orchestrators": registered_orchestrators,
            "orchestrator_count": len(registered_orchestrators),
            "current_level": self.orchestration_level,
            "configuration": {
                "workspace": str(self.workspace),
                "default_max_steps": 25,
                "default_temperature": 0.0,
            },
        }

        formatted_info = f"""# Orchestrator Agent MCP Server Capabilities

## Overview
**Service:** {capabilities["service_name"]}
**Version:** {capabilities["version"]}
**Description:** {capabilities["description"]}
**Current Orchestration Level:** {capabilities["current_level"]}

## Features
{chr(10).join(f"- {feature}" for feature in capabilities["features"])}

## Available Agent Types
{chr(10).join(f"- {agent}" for agent in capabilities["available_agent_types"])}

## Supported Operations
{chr(10).join(f"- {op}" for op in capabilities["supported_operations"])}

## Registered Orchestrators
**Total Orchestrators:** {capabilities["orchestrator_count"]}
{chr(10).join(f"- **{orch['agent_id']}** ({orch['name']}) [Level {orch['orchestration_level']}]: {orch['description']}" for orch in registered_orchestrators) if registered_orchestrators else "No orchestrators registered yet."}

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
        name="orchestrator_agent_service",
        transport="stdio",
        workspace=os.getenv("AWORLD_WORKSPACE", "~"),
    )

    # Initialize and run the orchestrator service
    try:
        service = OrchestratorAgentCollection(args)
        service.run()
    except Exception as e:
        print(f"An error occurred: {e}: {traceback.format_exc()}")

