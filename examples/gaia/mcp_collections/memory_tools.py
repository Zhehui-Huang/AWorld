"""
Memory Management MCP Tools

Provides MCP tools for agents to save and manage their task memories.
These tools allow agents to explicitly control when and how they save memories.
"""

import os
from typing import Optional
from pydantic import Field

from aworld.logs.util import Color
from examples.gaia.mcp_collections.base import ActionArguments, ActionCollection, ActionResponse
from examples.gaia.agent_collections.shared_memory import get_agent_memory


class MemoryToolsCollection(ActionCollection):
    """MCP tools for agent memory management."""

    def __init__(self, arguments: ActionArguments) -> None:
        super().__init__(arguments)
        self.memory = get_agent_memory()

    def mcp_save_task_memory(
        self,
        agent_id: str = Field(description="Unique ID of the agent instance (required)"),
        agent_type: str = Field(description="Type of agent (search_agent, pdf_agent, image_agent, orchestrator_agent)"),
        task_description: str = Field(description="Description of the completed task"),
        success: bool = Field(description="Whether the task was completed successfully"),
        artifacts: list[dict] = Field(
            default=[], 
            description="List of concrete resources used or created (dicts with keys like 'type', 'name', 'path', 'url')."
        ),
        reflection: dict = Field(
            default={}, 
            description="Agent self-reflection with 'what_worked' (list), 'what_failed' (list), 'lessons_learned' (string)."
        ),
    ) -> ActionResponse:
        """
        Save a detailed task memory with artifacts and reflection for future use.

        Args:
            agent_id: Agent instance identifier.
            agent_type: The type of agent.
            task_description: Description of the task.
            success: Task completion status.
            artifacts: List of relevant files, URLs, or data.
            reflection: Object with 'what_worked', 'what_failed', 'lessons_learned'.

        Returns:
            ActionResponse confirming if memory was saved.
        """
        valid_types = ["search_agent", "pdf_agent", "image_agent", "orchestrator_agent"]
        if agent_type not in valid_types:
            return ActionResponse(
                success=False,
                message=f"Invalid agent_type '{agent_type}'. Must be one of: {valid_types}",
                metadata={"error": "invalid_agent_type"}
            )
        try:
            self.memory.save_task_memory(
                agent_id=agent_id,
                agent_type=agent_type,
                task_description=task_description,
                success=success,
                artifacts=artifacts,
                reflection=reflection,
            )
            self._color_log(
                f"💾 Saved memory for {agent_id} ({agent_type}): {len(artifacts)} artifacts, reflection: {bool(reflection)}",
                Color.cyan, "debug"
            )
            return ActionResponse(
                success=True,
                message=f"{'Success:' if success else 'Fail:'} Memory saved for agent {agent_id} ({agent_type}).",
                metadata={
                    "agent_type": agent_type,
                    "agent_id": agent_id,
                    "success": success,
                    "memory_saved": True,
                }
            )
        except Exception as e:
            error_msg = f"Failed to save memory: {e}"
            self.logger.error(error_msg)
            return ActionResponse(
                success=False,
                message=error_msg,
                metadata={"error": str(e)}
            )

    def mcp_get_memory_stats(
        self,
        agent_id: str = Field(description="Unique ID of the agent instance to get statistics for"),
    ) -> ActionResponse:
        """
        Get statistics about saved memories for a specific agent instance.

        Args:
            agent_id: Agent instance identifier.

        Returns:
            ActionResponse with memory statistics.
        """
        try:
            stats = self.memory.get_memory_stats(agent_id)
            message = (
                f"Memory Statistics for agent {agent_id}:\n"
                f"- Total memories: {stats['total_memories']}\n"
                f"- Successful tasks: {stats['successful_tasks']}\n"
                f"- Failed tasks: {stats['failed_tasks']}\n"
                f"- Success rate: {stats['success_rate']:.1%}\n"
            )
            return ActionResponse(success=True, message=message, metadata=stats)
        except Exception as e:
            error_msg = f"Failed to get memory stats: {e}"
            self.logger.error(error_msg)
            return ActionResponse(
                success=False, message=error_msg, metadata={"error": str(e)}
            )


if __name__ == "__main__":
    from dotenv import load_dotenv
    load_dotenv()

    args = ActionArguments(
        name="memory_tools",
        transport="stdio",
        workspace=os.getenv("AWORLD_WORKSPACE", "~"),
    )

    service = MemoryToolsCollection(args)
    service.run()

