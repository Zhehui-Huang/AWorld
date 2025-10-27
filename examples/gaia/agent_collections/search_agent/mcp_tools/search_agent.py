"""
Search Agent MCP Server

This module provides MCP server functionality for performing web searches using an AI agent.
Unlike typical MCP tools that directly call APIs, this wraps a full agent that can reason,
plan, and use multiple tools to accomplish search tasks.

Key features:
- Agent-based search with reasoning and planning capabilities
- Supports complex multi-step search tasks
- Integrates with other MCP tools (search, download)
- Returns structured results with metadata

Main functions:
- mcp_search_agent: Executes a search task using the AI agent
- mcp_get_agent_capabilities: Returns information about agent capabilities
"""

import json
import os
import time
import traceback
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from pydantic import BaseModel, Field
from pydantic.fields import FieldInfo

from aworld.agents.llm_agent import Agent
from aworld.config.conf import AgentConfig, TaskConfig
from aworld.core.task import Task
from aworld.logs.util import Color
from aworld.runner import Runners
from examples.gaia.agent_collections.search_agent.prompt import system_prompt
from examples.gaia.mcp_collections.base import ActionArguments, ActionCollection, ActionResponse


class AgentSearchResult(BaseModel):
    """Result from agent-based search operation."""

    query: str
    answer: str | None
    success: bool
    steps_taken: int | None = None
    execution_time: float | None = None
    error_message: str | None = None


class AgentSearchMetadata(BaseModel):
    """Metadata for agent search operation."""

    agent_name: str
    max_steps: int
    llm_model: str
    llm_provider: str
    available_tools: list[str]
    execution_time: float | None = None
    steps_taken: int | None = None
    error_type: str | None = None


class SearchAgentCollection(ActionCollection):
    """MCP service for agent-based web search operations.

    Provides comprehensive search capabilities through an AI agent that can:
    - Reason and plan multi-step search strategies
    - Use multiple tools (search APIs, download, etc.)
    - Verify information across sources
    - Handle complex queries requiring multiple searches
    - Format results appropriately
    """

    def __init__(self, arguments: ActionArguments) -> None:
        super().__init__(arguments)

        # Load environment variables
        load_dotenv()

        # Load MCP configuration for the agent
        self.mcp_config: dict[str, Any] = {}
        self.available_servers: list[str] = []
        
        try:
            mcp_config_path = Path(__file__).parent.parent / "mcp.json"
            with open(mcp_config_path, mode="r", encoding="utf-8") as f:
                self.mcp_config = json.loads(f.read())
                self.available_servers = list(self.mcp_config.get("mcpServers", {}).keys())
                self._color_log(f"🔧 Agent MCP Available Servers: {self.available_servers}", Color.blue, "debug")
        except json.JSONDecodeError as e:
            self._color_log(f"Error loading mcp.json: {e}", Color.red)
        except FileNotFoundError:
            self._color_log("mcp.json not found; agent will run without MCP tools", Color.yellow)

        # Store LLM configuration
        self.llm_provider = os.getenv("LLM_PROVIDER", "openai")
        self.llm_model_name = os.getenv("LLM_MODEL_NAME", "gpt-4o")
        self.llm_base_url = os.getenv("LLM_BASE_URL")
        self.llm_api_key = os.getenv("LLM_API_KEY")
        self.llm_temperature = float(os.getenv("LLM_TEMPERATURE", 0.0))

        # Log initialization status
        self._color_log("Search Agent service initialized", Color.green, "debug")

    def _create_agent(self) -> Agent:
        """Create a new agent instance for a search task.

        Returns:
            Configured Agent instance
        """
        agent_config = AgentConfig(
            llm_provider=self.llm_provider,
            llm_model_name=self.llm_model_name,
            llm_base_url=self.llm_base_url,
            llm_api_key=self.llm_api_key,
            llm_temperature=self.llm_temperature,
        )
        
        return Agent(
            conf=agent_config,
            name="search_agent",
            system_prompt=system_prompt,
            mcp_config=self.mcp_config,
            mcp_servers=self.available_servers,
        )

    def _format_agent_result(self, result: AgentSearchResult, output_format: str) -> str | dict:
        """Format agent result based on requested format.

        Args:
            result: Agent search result
            output_format: Desired output format

        Returns:
            Formatted result
        """
        if output_format.lower() == "json":
            return result.model_dump()
        elif output_format.lower() == "text":
            if result.success and result.answer:
                return f"Query: {result.query}\n\nAnswer: {result.answer}"
            else:
                error_msg = result.error_message or "No answer found"
                return f"Query: {result.query}\n\nStatus: Failed\nError: {error_msg}"
        else:  # markdown (default)
            if result.success and result.answer:
                formatted = [
                    f"# Search Agent Result",
                    f"",
                    f"**Query:** {result.query}",
                    f"",
                    f"**Answer:**",
                    f"{result.answer}",
                ]
                if result.steps_taken is not None:
                    formatted.append(f"")
                    formatted.append(f"**Steps Taken:** {result.steps_taken}")
                if result.execution_time is not None:
                    formatted.append(f"**Execution Time:** {result.execution_time:.2f}s")
                return "\n".join(formatted)
            else:
                error_msg = result.error_message or "No answer found"
                return f"# Search Agent Result\n\n**Query:** {result.query}\n\n**Status:** Failed\n\n**Error:** {error_msg}"

    def mcp_search_agent(
        self,
        query: str = Field(description="The search query or task for the agent to accomplish"),
        max_steps: int = Field(default=12, description="Maximum number of steps the agent can take (1-50, default: 12)"),
        output_format: str = Field(default="markdown", description="Output format: 'markdown', 'json', or 'text'"),
    ) -> ActionResponse:
        """Execute a search task using an AI agent.

        This tool provides agent-based search capabilities with:
        - Multi-step reasoning and planning
        - Integration with search APIs and download tools
        - Source verification and fact-checking
        - Complex query handling
        - Structured result formatting

        The agent can:
        - Break down complex queries into sub-tasks
        - Perform multiple searches with refined queries
        - Download and analyze documents
        - Verify information across multiple sources
        - Provide formatted, accurate answers

        Args:
            query: The search query or task description
            max_steps: Maximum steps for the agent (1-50)
            output_format: Format for the response

        Returns:
            ActionResponse with agent's answer and execution metadata
        """
        # Handle FieldInfo defaults
        if isinstance(query, FieldInfo):
            query = query.default
        if isinstance(max_steps, FieldInfo):
            max_steps = max_steps.default
        if isinstance(output_format, FieldInfo):
            output_format = output_format.default

        try:
            # Validate parameters
            if not query or not query.strip():
                return ActionResponse(
                    success=False,
                    message="Search query cannot be empty",
                    metadata={"error_type": "invalid_parameters"},
                )

            validated_query = query.strip()
            validated_max_steps = max(1, min(max_steps, 50))

            self._color_log(f"🤖 Starting search agent for: '{validated_query}'", Color.cyan)
            self._color_log(f"   Max steps: {validated_max_steps}", Color.cyan, "debug")

            # Create agent and task
            start_time = time.time()
            agent = self._create_agent()
            
            task = Task(
                id="search_agent_task",
                input=validated_query,
                agent=agent,
                conf=TaskConfig(max_steps=validated_max_steps)
            )

            # Run the agent
            result_map = Runners.sync_run_task(task=task)
            execution_time = time.time() - start_time

            # Extract result
            answer = None
            steps_taken = None
            if result_map and task.id in result_map:
                task_result = result_map[task.id]
                answer = task_result.answer if hasattr(task_result, 'answer') else None
                # Try to get steps taken from task result
                if hasattr(task_result, 'steps'):
                    steps_taken = len(task_result.steps)

            success = bool(answer and str(answer).strip())

            # Create result object
            agent_result = AgentSearchResult(
                query=validated_query,
                answer=answer,
                success=success,
                steps_taken=steps_taken,
                execution_time=execution_time,
            )

            # Format result
            formatted_content = self._format_agent_result(agent_result, output_format)

            # Prepare metadata
            metadata = AgentSearchMetadata(
                agent_name="search_agent",
                max_steps=validated_max_steps,
                llm_model=self.llm_model_name,
                llm_provider=self.llm_provider,
                available_tools=self.available_servers,
                execution_time=execution_time,
                steps_taken=steps_taken,
            )

            if success:
                self._color_log(f"✅ Agent completed task in {execution_time:.2f}s", Color.green)
            else:
                self._color_log(f"⚠️ Agent completed but no answer found in {execution_time:.2f}s", Color.yellow)

            return ActionResponse(
                success=success,
                message=formatted_content,
                metadata=metadata.model_dump()
            )

        except Exception as e:
            error_msg = f"Agent execution failed: {str(e)}"
            error_trace = traceback.format_exc()

            self.logger.error(f"Agent error: {error_trace}")
            self._color_log(f"❌ {error_msg}", Color.red)

            agent_result = AgentSearchResult(
                query=query,
                answer=None,
                success=False,
                error_message=str(e),
            )

            metadata = AgentSearchMetadata(
                agent_name="search_agent",
                max_steps=max_steps if not isinstance(max_steps, FieldInfo) else 12,
                llm_model=self.llm_model_name,
                llm_provider=self.llm_provider,
                available_tools=self.available_servers,
                error_type="execution_failed",
            )

            formatted_content = self._format_agent_result(agent_result, output_format if not isinstance(output_format, FieldInfo) else "markdown")

            return ActionResponse(
                success=False,
                message=formatted_content,
                metadata=metadata.model_dump()
            )

    def mcp_get_agent_capabilities(self) -> ActionResponse:
        """Get information about search agent capabilities and configuration.

        Returns:
            ActionResponse with agent capabilities and current configuration
        """
        capabilities = {
            "agent_type": "Search Agent",
            "description": "AI agent that can reason, plan, and execute multi-step search tasks",
            "supported_features": [
                "Multi-step reasoning and planning",
                "Web search with query refinement",
                "Document download and analysis",
                "Source verification and fact-checking",
                "Complex query decomposition",
                "Multiple output formats (markdown, json, text)",
                "Detailed execution metadata",
            ],
            "available_tools": self.available_servers,
            "supported_formats": ["markdown", "json", "text"],
            "configuration": {
                "llm_provider": self.llm_provider,
                "llm_model": self.llm_model_name,
                "default_max_steps": 12,
                "max_allowed_steps": 50,
                "temperature": self.llm_temperature,
                "mcp_tools_configured": bool(self.available_servers),
            },
            "capabilities": [
                "Can break down complex queries into sub-tasks",
                "Can perform multiple searches with refined queries",
                "Can download and analyze documents from URLs",
                "Can verify facts across multiple sources",
                "Can handle ambiguous or underspecified queries",
            ],
            "limitations": [
                f"Maximum {50} steps per task",
                "Depends on underlying tool availability (search API, download)",
                "Subject to LLM token limits and rate limits",
                "Requires valid API credentials for LLM and search services",
            ],
        }

        formatted_info = f"""# Search Agent Capabilities

## Agent Type
{capabilities["agent_type"]}

{capabilities["description"]}

## Features
{chr(10).join(f"- {feature}" for feature in capabilities["supported_features"])}

## Available Tools
{chr(10).join(f"- {tool}" for tool in capabilities["available_tools"]) if capabilities["available_tools"] else "- No MCP tools configured"}

## Agent Capabilities
{chr(10).join(f"- {cap}" for cap in capabilities["capabilities"])}

## Supported Output Formats
{chr(10).join(f"- {fmt}" for fmt in capabilities["supported_formats"])}

## Current Configuration
- **LLM Provider:** {capabilities["configuration"]["llm_provider"]}
- **LLM Model:** {capabilities["configuration"]["llm_model"]}
- **Default Max Steps:** {capabilities["configuration"]["default_max_steps"]}
- **Max Allowed Steps:** {capabilities["configuration"]["max_allowed_steps"]}
- **Temperature:** {capabilities["configuration"]["temperature"]}
- **MCP Tools Configured:** {capabilities["configuration"]["mcp_tools_configured"]}

## Limitations
{chr(10).join(f"- {limitation}" for limitation in capabilities["limitations"])}
"""

        return ActionResponse(
            success=True,
            message=formatted_info,
            metadata=capabilities
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

    # Initialize and run the search agent service
    try:
        service = SearchAgentCollection(args)
        service.run()
    except Exception as e:
        print(f"An error occurred: {e}: {traceback.format_exc()}")

