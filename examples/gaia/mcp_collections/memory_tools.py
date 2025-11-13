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
        agent_id: str = Field(
            description="Unique ID of the agent instance (required)"
        ),
        agent_type: str = Field(
            description="Type of agent (search_agent, pdf_agent, image_agent, orchestrator_agent)"
        ),
        task_description: str = Field(description="Description of the task that was completed"),
        success: bool = Field(description="Whether the task was completed successfully"),
        artifacts: list[dict] = Field(
            default=[],
            description=(
                "List of concrete resources used or created. Each artifact should be a dict with keys like 'type', 'name', 'path', 'url'. "
                "Examples: "
                "[{'type': 'pdf', 'name': 'Nature Article 2023', 'path': 'research_paper.pdf', 'url': 'https://nature.com/article123'}, "
                "{'type': 'image', 'name': 'figure_3.png', 'path': figure_3.png'}]"
            )
        ),
        reflection: dict = Field(
            default={},
            description=(
                "Agent's self-reflection and learning from this task. "
                "Required keys: 'what_worked' (list), 'what_failed' (list), 'lessons_learned' (string). "
                "Example: {"
                "'what_worked': ['Using arxiv.org for open access papers', 'Downloading PDFs directly instead of scraping'], "
                "'what_failed': ['Generic search terms returned irrelevant results', 'Institutional access without credentials'], "
                "'lessons_learned': 'Always prioritize open-access sources (arxiv, PMC) before attempting paywalled journals. Use specific search terms including publication year and author names for better results.'"
                "}"
            )
        ),
    ) -> ActionResponse:
        """
        Save a task memory for future reference with artifacts and reflection.
        
        **IMPORTANT: Save DETAILED, CONCRETE information!**

        For all tasks:
        - artifacts: Include ALL files, URLs, images, PDFs used or created with their full paths/URLs
        - reflection: Reflect on what worked, what failed, and lessons learned

        Example for search agent that found a paper:
        ```
        artifacts: [
            {"type": "pdf", "name": "Attention Is All You Need", "path": "attention_paper.pdf", "url": "https://arxiv.org/pdf/1706.03762"},
        ]
        reflection: {
            "what_worked": ["Using arxiv.org for open access", "Specific search terms with year"],
            "what_failed": ["Generic search queries", "Paywalled journals"],
            "lessons_learned": "Always prioritize open-access sources and use specific search terms"
        }
        ```

        Args:
            agent_id: Unique identifier for the agent instance (required)
            agent_type: The type of agent
            task_description: Brief description of the overall task
            success: True if completed successfully, False if failed
            artifacts: List of concrete resources (files, URLs, etc.) with full details
            reflection: Agent's learning - what worked, what failed, lessons learned
            
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
            # Save the memory with artifacts and reflection
            self.memory.save_task_memory(
                agent_id=agent_id,
                agent_type=agent_type,
                task_description=task_description,
                success=success,
                artifacts=artifacts,
                reflection=reflection
            )
            
            status_flag = "Success:" if success else "Fail:"
            artifacts_count = len(artifacts)
            has_reflection = bool(reflection)
            message = (
                f"{status_flag} Memory saved for agent {agent_id} ({agent_type})."
            )
            
            self._color_log(
                f"💾 Saved task memory for agent {agent_id} ({agent_type}): "
                f"{artifacts_count} artifacts, reflection: {has_reflection}",
                Color.cyan, "debug"
            )
            
            return ActionResponse(
                success=True,
                message=message,
                metadata={
                    "agent_type": agent_type,
                    "agent_id": agent_id,
                    "success": success,
                    "memory_saved": True,
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
        agent_id: str = Field(
            description="Unique ID of the agent instance to get statistics for"
        ),
    ) -> ActionResponse:
        """
        Get statistics about saved memories for a specific agent instance.
        
        Args:
            agent_id: Unique ID of the agent instance
            
        Returns:
            ActionResponse with memory statistics
        """
        try:
            stats = self.memory.get_memory_stats(agent_id)
            
            message = f"""Memory Statistics for agent {agent_id}:
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

