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
"""

import json
import os
import traceback
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional

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
from examples.gaia.agent_collections.shared_memory import get_agent_memory


class OrchestratorMetadata(BaseModel):
    """Metadata for an orchestrator agent instance."""

    agent_id: str
    name: str
    description: str
    orchestration_level: int


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
    - Create orchestrator agents with access to all available MCP tools
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

    def _create_agent_instance(
        self,
        name: str,
        description: str,
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

        # Use base MCP config with all agents
        mcp_config = self.base_mcp_config
        mcp_servers = list(mcp_config.get("mcpServers", {}).keys())

        # Update orchestration level in environment for sub-orchestrators
        new_level = self.orchestration_level + 1
        if "orchestrator_agent" in mcp_config.get("mcpServers", {}):
            # Update orchestration level for recursive orchestrators
            env_config = mcp_config["mcpServers"]["orchestrator_agent"].get("env", {})
            env_config["ORCHESTRATION_LEVEL"] = str(new_level)
            mcp_config["mcpServers"]["orchestrator_agent"]["env"] = env_config

        # Create orchestrator agent with MCP tools
        agent = Agent(
            conf=agent_config,
            name=name,
            agent_id=agent_id,
            system_prompt=system_prompt,
            mcp_config=mcp_config,
            mcp_servers=mcp_servers,
        )

        # Create metadata
        metadata = OrchestratorMetadata(
            agent_id=agent_id,
            name=name,
            description=description,
            orchestration_level=new_level,
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
    ) -> ActionResponse:
        """
        Create a new orchestrator agent and execute the given task.

        This orchestrator can coordinate multiple specialized agents and even create
        sub-orchestrators for complex workflows requiring nested coordination.

        Key Features:
        1. Recursive orchestration (can create sub-orchestrators)
        2. Parallel and sequential execution patterns
        3. Context and memory preservation across agent calls
        4. Hierarchical task decomposition

        Args:
            task_prompt: The task to orchestrate (provide complete context)
            name: Name for the orchestrator
            description: Description of orchestrator's purpose

        Returns:
            ActionResponse with execution results and orchestrator metadata
        """
        # Handle FieldInfo objects
        if isinstance(task_prompt, FieldInfo):
            task_prompt = task_prompt.default
        if isinstance(name, FieldInfo):
            name = name.default
        if isinstance(description, FieldInfo):
            description = description.default

        # Load max_steps from environment
        max_steps = int(os.getenv("ORCHESTRATOR_MAX_STEPS", "50"))

        try:
            indent = "  " * self.orchestration_level
            self._color_log(
                f"{indent}🎭 Creating orchestrator (level {self.orchestration_level + 1}): {name}", Color.cyan
            )

            # Create orchestrator instance
            agent, metadata = self._create_agent_instance(
                name=name,
                description=description,
            )

            self._color_log(f"{indent}✅ Orchestrator created with ID: {metadata.agent_id}", Color.green)

            # Retrieve relevant memories from past tasks
            memory = get_agent_memory()
            relevant_memories = memory.retrieve_relevant_memories(
                agent_id=metadata.agent_id,
                task_description=task_prompt,
                max_results=3
            )
            
            if relevant_memories:
                self._color_log(
                    f"{indent}🧠 Retrieved {len(relevant_memories)} relevant past experiences",
                    Color.blue
                )
            
            # Add agent ID to task prompt
            task_prompt_with_id = f"[Agent ID: {metadata.agent_id}]\n\n{task_prompt}"
            
            # Enhance task prompt with past experiences
            enhanced_task_prompt = task_prompt_with_id
            if relevant_memories:
                memory_context = memory.format_memories_for_prompt(relevant_memories)
                enhanced_task_prompt = f"{task_prompt_with_id}\n\n{memory_context}"

            # Execute task with the orchestrator
            self._color_log(f"{indent}🚀 Orchestrating task: {task_prompt[:100]}...", Color.cyan)

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
                self._color_log(f"{indent}✅ Orchestration completed successfully", Color.green)
            else:
                answer = None
                self._color_log(f"{indent}⚠️ Orchestration completed with no answer", Color.yellow)

            # Format response
            formatted_message = answer

            return ActionResponse(
                success=True,
                message=formatted_message,
                metadata={
                    "agent_id": metadata.agent_id,
                    "agent_name": metadata.name,
                    "description": metadata.description,
                    "orchestration_level": metadata.orchestration_level,
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
    ) -> ActionResponse:
        """
        Use an existing orchestrator agent to execute a task.

        This method reuses a previously created orchestrator, maintaining its
        configuration, available agents, and state across multiple tasks.

        Args:
            agent_id: ID of the existing orchestrator
            task_prompt: The task to orchestrate

        Returns:
            ActionResponse with execution results and orchestrator metadata
        """
        # Handle FieldInfo objects
        if isinstance(agent_id, FieldInfo):
            agent_id = agent_id.default
        if isinstance(task_prompt, FieldInfo):
            task_prompt = task_prompt.default

        # Load max_steps from environment
        max_steps = int(os.getenv("ORCHESTRATOR_MAX_STEPS", "50"))

        try:
            # Check if orchestrator exists
            if not self.agent_registry.exists(agent_id):
                available_orchestrators = [m.agent_id for m in self.agent_registry.list_agents()]
                return ActionResponse(
                    success=False,
                    message=f"Orchestrator ID '{agent_id}' not found. Available: {available_orchestrators}",
                    metadata={"error_type": "orchestrator_not_found", "available_orchestrators": available_orchestrators},
                )

            # Get existing orchestrator
            agent = self.agent_registry.get_agent(agent_id)
            metadata = self.agent_registry.get_metadata(agent_id)
            
            if not agent or not metadata:
                return ActionResponse(
                    success=False,
                    message=f"Orchestrator ID '{agent_id}' exists in registry but agent or metadata is None",
                    metadata={"error_type": "orchestrator_data_corrupted"},
                )

            indent = "  " * self.orchestration_level
            self._color_log(f"{indent}🔄 Using existing orchestrator: {metadata.name} ({agent_id})", Color.cyan)

            # Retrieve relevant memories from past tasks
            memory = get_agent_memory()
            relevant_memories = memory.retrieve_relevant_memories(
                agent_id=metadata.agent_id,
                task_description=task_prompt,
                max_results=3
            )
            
            if relevant_memories:
                self._color_log(
                    f"{indent}🧠 Retrieved {len(relevant_memories)} relevant past experiences",
                    Color.blue
                )
            
            # Add agent ID to task prompt
            task_prompt_with_id = f"[Agent ID: {metadata.agent_id}]\n\n{task_prompt}"
            
            # Enhance task prompt with past experiences
            enhanced_task_prompt = task_prompt_with_id
            if relevant_memories:
                memory_context = memory.format_memories_for_prompt(relevant_memories)
                enhanced_task_prompt = f"{task_prompt_with_id}\n\n{memory_context}"

            # Execute task
            self._color_log(f"{indent}🚀 Orchestrating task: {task_prompt[:100]}...", Color.cyan)

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
                self._color_log(f"{indent}✅ Orchestration completed successfully", Color.green)
            else:
                answer = None
                self._color_log(f"{indent}⚠️ Orchestration completed with no answer", Color.yellow)

            # Format response
            formatted_message = answer

            return ActionResponse(
                success=True,
                message=formatted_message,
                metadata={
                    "agent_id": metadata.agent_id,
                    "agent_name": metadata.name,
                    "description": metadata.description,
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

