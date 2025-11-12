"""
Memory Management MCP Tools

Provides MCP tools for agents to save and manage their task memories.
These tools allow agents to explicitly control when and how they save memories.
"""

import os
from typing import Optional
from pydantic import Field

from examples.gaia.mcp_collections.base import ActionArguments, ActionCollection, ActionResponse
from examples.gaia.agent_collections.shared_memory import get_agent_memory


class MemoryToolsCollection(ActionCollection):
    """MCP tools for agent memory management."""

    def __init__(self, arguments: ActionArguments) -> None:
        super().__init__(arguments)
        self.memory = get_agent_memory()

    def mcp_save_task_memory(
        self,
        agent_type: str = Field(
            description="Type of agent (search_agent, pdf_agent, image_agent, orchestrator_agent)"
        ),
        task_description: str = Field(description="Description of the task that was completed"),
        success: bool = Field(description="Whether the task was completed successfully"),
        summary: str = Field(
            description="Summary of how the task was completed (if success) or why it failed (if failure)"
        ),
        agent_id: Optional[str] = Field(
            default=None, description="Optional agent ID for tracking"
        ),
    ) -> ActionResponse:
        """
        Save a task memory for future reference.
        
        Call this tool before returning results to save what you learned from this task.
        
        For successful tasks:
        - Summarize the key steps taken to complete the task
        - Highlight what worked well
        - Include specific tool calls or approaches that were effective
        
        For failed tasks:
        - Explain what went wrong
        - Describe what was attempted
        - Suggest what should be done differently next time
        
        Args:
            agent_type: Type of agent (must be one of: search_agent, pdf_agent, image_agent, orchestrator_agent)
            task_description: Description of the task
            success: True if task succeeded, False if failed
            summary: Detailed summary of outcome
            agent_id: Optional agent identifier
            
        Returns:
            ActionResponse confirming memory was saved
        """
        # Validate agent_type
        valid_types = ["search_agent", "pdf_agent", "image_agent", "orchestrator_agent"]
        if agent_type not in valid_types:
            return ActionResponse(
                success=False,
                message=f"Invalid agent_type '{agent_type}'. Must be one of: {valid_types}",
                metadata={"error": "invalid_agent_type"}
            )
        
        try:
            # Save the memory
            self.memory.save_task_memory(
                agent_type=agent_type,
                task_description=task_description,
                success=success,
                summary=summary,
                metadata={"agent_id": agent_id} if agent_id else {}
            )
            
            status_emoji = "✅" if success else "❌"
            message = f"{status_emoji} Memory saved for {agent_type}: {task_description[:50]}..."
            
            self._color_log(f"💾 Saved task memory for {agent_type}", self.logger.color_cyan, "debug")
            
            return ActionResponse(
                success=True,
                message=message,
                metadata={
                    "agent_type": agent_type,
                    "success": success,
                    "memory_saved": True
                }
            )
            
        except Exception as e:
            error_msg = f"Failed to save memory: {str(e)}"
            self.logger.error(error_msg)
            return ActionResponse(
                success=False,
                message=error_msg,
                metadata={"error": str(e)}
            )

    def mcp_get_memory_stats(
        self,
        agent_type: str = Field(
            description="Type of agent to get statistics for"
        ),
    ) -> ActionResponse:
        """
        Get statistics about saved memories for an agent type.
        
        Args:
            agent_type: Type of agent
            
        Returns:
            ActionResponse with memory statistics
        """
        try:
            stats = self.memory.get_memory_stats(agent_type)
            
            message = f"""Memory Statistics for {agent_type}:
- Total memories: {stats['total_memories']}
- Successful tasks: {stats['successful_tasks']}
- Failed tasks: {stats['failed_tasks']}
- Success rate: {stats['success_rate']:.1%}
"""
            
            return ActionResponse(
                success=True,
                message=message,
                metadata=stats
            )
            
        except Exception as e:
            error_msg = f"Failed to get memory stats: {str(e)}"
            self.logger.error(error_msg)
            return ActionResponse(
                success=False,
                message=error_msg,
                metadata={"error": str(e)}
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

