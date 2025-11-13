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
        summary: str = Field(
            description="High-level summary of the outcome"
        ),
        detailed_steps: list[str] = Field(
            default=[],
            description="List of specific actions taken (e.g., ['Searched for papers on topic X', 'Downloaded paper1.pdf from URL1', 'Extracted text from page 5'])"
        ),
        artifacts: list[dict] = Field(
            default=[],
            description=(
                "List of concrete resources used or created. Each artifact should be a dict with keys like 'type', 'name', 'path', 'url'. "
                "Examples: "
                "[{'type': 'pdf', 'name': 'research_paper.pdf', 'path': '/workspace/research_paper.pdf'}, "
                "{'type': 'url', 'name': 'Nature Article 2023', 'url': 'https://nature.com/article123'}, "
                "{'type': 'image', 'name': 'figure_3.png', 'path': '/workspace/figure_3.png'}]"
            )
        ),
        key_findings: dict = Field(
            default={},
            description=(
                "Dictionary of specific data extracted or discovered. "
                "Example: {'author': 'John Doe', 'publication_year': 2023, 'main_result': '95% accuracy', 'dataset_used': 'ImageNet'}"
            )
        ),
        failure_details: dict = Field(
            default={},
            description=(
                "If task failed, provide specific details. "
                "Example: {'error_type': 'file_not_found', 'attempted_files': ['paper1.pdf', 'paper2.pdf'], "
                "'attempted_urls': ['url1', 'url2'], 'reason': 'All download links were broken'}"
            )
        ),
        trajectory: list[dict] = Field(
            default=[],
            description=(
                "Full sequence of agent interactions/actions with timestamps. Each step should include the action taken, tool used, input/output. "
                "Example: [{'step': 1, 'action': 'search', 'tool': 'google_search', 'input': 'quantum computing papers', "
                "'output': 'Found 10 results', 'timestamp': '2025-11-12T10:30:00'}, "
                "{'step': 2, 'action': 'download', 'tool': 'file_downloader', 'input': 'https://arxiv.org/paper.pdf', "
                "'output': 'Downloaded to /workspace/paper.pdf', 'timestamp': '2025-11-12T10:31:15'}]"
            )
        ),
        reflection: dict = Field(
            default={},
            description=(
                "Agent's self-reflection and learning from this task. Include what worked, what failed, and what to do differently. "
                "Required keys: 'what_worked' (list), 'what_failed' (list), 'would_do_again' (list), 'would_avoid' (list), 'lessons_learned' (string). "
                "Example: {"
                "'what_worked': ['Using arxiv.org for open access papers', 'Downloading PDFs directly instead of scraping'], "
                "'what_failed': ['Generic search terms returned irrelevant results', 'Institutional access without credentials'], "
                "'would_do_again': ['Start with arxiv.org for academic papers', 'Verify file integrity after download', 'Use specific search terms with author names'], "
                "'would_avoid': ['Trying paywalled journals first', 'Using broad search queries', 'Downloading from unverified sources'], "
                "'lessons_learned': 'Always prioritize open-access sources (arxiv, PMC) before attempting paywalled journals. Use specific search terms including publication year and author names for better results.'"
                "}"
            )
        ),
    ) -> ActionResponse:
        """
        Save a detailed task memory for future reference with trajectory and reflection.
        
        **IMPORTANT: Save DETAILED, CONCRETE information, not abstract summaries!**
        **NEW: Include trajectory (what you did step-by-step) and reflection (what you learned)**

        For successful tasks:
        - detailed_steps: List every specific action taken
        - artifacts: Include ALL files, URLs, images, PDFs used or created with their full paths/URLs
        - key_findings: Record specific data extracted (authors, dates, results, file sizes, dimensions, etc.)
        - trajectory: Record each tool call with input/output
        - reflection: Reflect on what worked, what didn't, what to do again, what to avoid
        - summary: Brief high-level summary

        Example for search agent that found 5 papers:
        ```
        detailed_steps: [
            "Searched Google for 'machine learning papers 2023'",
            "Found 5 relevant papers",
            "Downloaded paper 'Attention Is All You Need' from https://arxiv.org/abs/1706.03762",
        ]
        artifacts: [
            {"type": "url", "name": "Attention Is All You Need", "url": "https://arxiv.org/abs/1706.03762"},
            {"type": "pdf", "name": "attention_paper.pdf", "path": "/workspace/attention_paper.pdf"},
        ]
        key_findings: {
            "total_papers_found": 5,
            "paper_1_title": "Attention Is All You Need"
        }
        trajectory: [
            {"step": 1, "action": "search", "tool": "google_search", "input": "machine learning papers 2023", 
             "output": "Found 10 results", "timestamp": "2025-11-12T10:30:00"},
            {"step": 2, "action": "download", "tool": "file_downloader", "input": "https://arxiv.org/...", 
             "output": "Downloaded successfully", "timestamp": "2025-11-12T10:31:00"}
        ]
        reflection: {
            "what_worked": ["Using arxiv.org for open access", "Specific search terms with year"],
            "what_failed": ["Generic search queries", "Paywalled journals"],
            "would_do_again": ["Start with arxiv.org", "Include publication year in search"],
            "would_avoid": ["Broad search terms", "Trying paywalled sources first"],
            "lessons_learned": "Always prioritize open-access sources and use specific search terms"
        }
        ```

        For failed tasks:
        - detailed_steps: List everything attempted before failure
        - failure_details: Specific error types, files/URLs that failed
        - trajectory: Full sequence showing where it went wrong
        - reflection: What you learned from the failure, what to avoid next time

        Args:
            agent_id: Unique identifier for the agent instance (required)
            agent_type: The type of agent
            task_description: Brief description of the overall task
            success: True if completed successfully, False if failed
            summary: High-level summary
            detailed_steps: List of specific actions taken
            artifacts: List of concrete resources (files, URLs, etc.) with full details
            key_findings: Specific data extracted or discovered
            failure_details: If failed, specific details about what went wrong
            trajectory: Full sequence of agent interactions with timestamps
            reflection: Agent's learning - what worked, what failed, what to do/avoid next time
            
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
            # Save the memory with detailed information, trajectory, and reflection
            self.memory.save_task_memory(
                agent_id=agent_id,
                agent_type=agent_type,
                task_description=task_description,
                success=success,
                summary=summary,
                detailed_steps=detailed_steps,
                artifacts=artifacts,
                key_findings=key_findings,
                failure_details=failure_details,
                trajectory=trajectory,
                reflection=reflection,
                metadata={}
            )
            
            status_flag = "Success:" if success else "Fail:"
            artifacts_count = len(artifacts)
            steps_count = len(detailed_steps)
            trajectory_count = len(trajectory)
            has_reflection = bool(reflection)
            message = (
                f"{status_flag} Memory saved for agent {agent_id} ({agent_type}). "
                f"Recorded {steps_count} steps, {artifacts_count} artifacts, "
                f"{trajectory_count} trajectory items, reflection: {has_reflection}."
            )
            
            self._color_log(
                f"💾 Saved detailed task memory for agent {agent_id} ({agent_type}): "
                f"{steps_count} steps, {artifacts_count} artifacts, {trajectory_count} trajectory, "
                f"reflection: {has_reflection}",
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
                    "steps_count": steps_count,
                    "artifacts_count": artifacts_count,
                    "trajectory_count": trajectory_count,
                    "has_reflection": has_reflection
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

