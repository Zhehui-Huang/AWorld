"""
PDF Agent MCP Server

This module provides MCP server functionality for processing PDF documents and images.
It supports PDF content extraction, text analysis, image processing, and returns LLM-friendly formatted results.

Key features:
- Extract text content from PDF documents
- Extract images and media from PDFs
- Support for OCR when needed (documents and standalone images)
- AI-powered image analysis using vision models
- Image metadata extraction
- Format output for LLM consumption
- Save extracted content to files

Main functions:
- mcp_create_pdf_agent: Create PDF agent
- mcp_use_existing_pdf_agent: Use existing PDF agent

Image tools available:
- mcp_extract_text_ocr: Extract text from images using OCR
- mcp_get_image_metadata: Extract technical metadata from images
"""

import json
import os
import traceback
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional, List, override

from dotenv import load_dotenv
from pydantic import BaseModel, Field
from pydantic.fields import FieldInfo

from aworld.agents.llm_agent import Agent
from aworld.config.conf import AgentConfig, TaskConfig
from aworld.core.common import ActionResult, Observation
from aworld.core.event.base import Message
from aworld.core.context.base import Context
from aworld.core.task import Task
from aworld.logs.util import Color, logger
from aworld.memory.models import MemoryHumanMessage, MessageMetadata
from aworld.runner import Runners
from examples.gaia.agent_collections.pdf_agent.prompt import system_prompt
from examples.gaia.mcp_collections.base import ActionArguments, ActionCollection, ActionResponse
from examples.gaia.agent_collections.shared_memory import get_agent_memory


class PDFAgent(Agent):
    """Extended Agent with memory reset capability for PDF processing."""

    @override
    async def _add_tool_result_to_memory(self, tool_call_id: str, tool_result: ActionResult, context: Context):
        """Override to handle memory reset when summarization tool is called."""
        # Check if this is a memory reset signal
        should_reset = False
        summary_message = None
        
        if isinstance(tool_result, ActionResult) and tool_result.content:
            try:
                # Parse the JSON content from MCP tool result
                # The ActionResponse is serialized as JSON string wrapped in a list in tool_result.content
                content = tool_result.content
                
                # First, parse the outer JSON (which is a list)
                parsed_content = json.loads(content) if isinstance(content, str) else content
                
                # If it's a list, get the first element and parse it again
                if isinstance(parsed_content, list) and len(parsed_content) > 0:
                    response_data = json.loads(parsed_content[0]) if isinstance(parsed_content[0], str) else parsed_content[0]
                else:
                    response_data = parsed_content
                
                # Check if this is a memory reset action
                if isinstance(response_data, dict):
                    metadata = response_data.get("metadata", {})
                    if metadata.get("memory_reset") and metadata.get("action") == "summarize_and_reset":
                        should_reset = True
                        # Extract the summary message from the ActionResponse
                        summary_message = response_data.get("message", "")
                        self._color_log("🔄 Memory reset signal detected - clearing conversation history", Color.cyan)
                        self._color_log(f"📄 Summary length: {len(summary_message)} chars", Color.cyan, "debug")
            except (json.JSONDecodeError, TypeError, AttributeError) as e:
                # If parsing fails, this is not a memory reset action
                self._color_log(f"⚠️ Could not parse tool result as JSON: {e}", Color.yellow, "debug")
                pass
        
        # If memory reset is needed, perform special handling
        if should_reset:
            self._color_log(f"🔍 Tool call ID for reset: {tool_call_id}", Color.yellow, "debug")
            # Delete conversation history and add summary as user message
            await self._reset_conversation_memory(context, summary_message)
            # Don't add the tool result - we've already added the summary as user message
            return
        
        # Normal case: add tool result to memory
        await super()._add_tool_result_to_memory(tool_call_id, tool_result, context)

    @override
    async def async_messages_transform(
        self,
        image_urls: List[str] = None,
        observation: Observation = None,
        message: Message = None,
        **kwargs
    ) -> List[Dict[str, Any]]:
        """Override to log messages being sent to LLM."""
        messages = await super().async_messages_transform(
            image_urls=image_urls,
            observation=observation,
            message=message,
            **kwargs
        )

        self._color_log(f"🔍 Sending {len(messages)} messages to LLM:", Color.cyan, "debug")
        for idx, msg in enumerate(messages):
            role = msg.get("role", "unknown")
            preview = str(msg.get("content", ""))[:100] or "[no content]"
            tool_calls = msg.get("tool_calls", [])
            tool_call_id = msg.get("tool_call_id")

            info = []
            if tool_calls:
                info.append(f"tool_calls={len(tool_calls)}")
            if tool_call_id:
                info.append(f"tool_call_id={tool_call_id}")

            extra = f" ({', '.join(info)})" if info else ""
            self._color_log(f"  [{idx}] {role}{extra}: {preview}...", Color.cyan, "debug")

        return messages

    async def _reset_conversation_memory(self, context: Context, summary_message: str):
        """Clear conversation memory except system prompt and initial task, then merge summary with user prompt."""
        try:
            session_id = context.get_task().session_id
            task_id = context.get_task().id
            user_id = context.get_task().user_id
            
            # Debug: Check current memory state before deletion
            histories_before = self.memory.get_all(filters={
                "agent_id": self.id(),
                "session_id": session_id,
                "task_id": task_id
            })
            self._color_log(f"📊 Memory before reset: {len(histories_before)} items", Color.yellow, "debug")
            for idx, item in enumerate(histories_before):
                self._color_log(
                    f"  [{idx}] type={item.memory_type}, role={item.metadata.get('role', 'N/A')}, "
                    f"deleted={item.deleted}, content_len={len(str(item.content)) if item.content else 0}",
                    Color.yellow, "debug"
                )
            
            # Find the initial user prompt (init type with role=user)
            initial_user_prompt = None
            for item in histories_before:
                if (item.memory_type == "init" and 
                    item.metadata.get('role') == 'user' and 
                    not item.deleted):
                    initial_user_prompt = item
                    break
            
            if initial_user_prompt:
                # Merge the summary with the initial user prompt
                original_content = initial_user_prompt.content
                
                # Format the merged content
                merged_content = f"{original_content}\n\n{summary_message}"
                
                # Update the content
                initial_user_prompt.content = merged_content
                initial_user_prompt.updated_at = datetime.now().isoformat()
                
                # Save the updated memory item
                self.memory.update(initial_user_prompt)
                
                self._color_log(f"📝 Summary merged with initial user prompt", Color.blue)
                self._color_log(f"   Original length: {len(str(original_content))} chars", Color.blue, "debug")
                self._color_log(f"   Summary length: {len(summary_message)} chars", Color.blue, "debug")
                self._color_log(f"   New total length: {len(merged_content)} chars", Color.blue, "debug")
            else:
                self._color_log("⚠️ Could not find initial user prompt to merge with", Color.yellow)
            
            # Delete all "message" type memories (conversation history)
            # This preserves "init" type memories (system prompt and initial user prompt)
            self.memory.delete_items(
                message_types=["message"],
                session_id=session_id,
                task_id=task_id,
                filters={
                    "agent_id": self.id(),
                }
            )
            
            self._color_log("✅ Conversation memory cleared (kept system and user prompts)", Color.green)
            
            # Debug: Check memory state after deletion
            histories_after = self.memory.get_all(filters={
                "agent_id": self.id(),
                "session_id": session_id,
                "task_id": task_id
            })
            self._color_log(f"📊 Memory after reset: {len(histories_after)} items", Color.yellow, "debug")
            for idx, item in enumerate(histories_after):
                preview = str(item.content)[:100] if item.content else "[no content]"
                self._color_log(
                    f"  [{idx}] type={item.memory_type}, role={item.metadata.get('role', 'N/A')}, "
                    f"deleted={item.deleted}, content_preview={preview}...",
                    Color.yellow, "debug"
                )
            
        except Exception as e:
            self.logger.error(f"Failed to reset conversation memory: {str(e)}")
            self._color_log(f"❌ Memory reset failed: {str(e)}", Color.red)
    
    def _color_log(self, message: str, color: Color, level: str = "info"):
        """Helper method for colored logging."""
        if level == "debug":
            logger.debug(message, color=color)
        elif level == "warning":
            logger.warning(message, color=color)
        elif level == "error":
            logger.error(message, color=color)
        else:
            logger.info(message, color=color)


class PDFAgentMetadata(BaseModel):
    """Metadata for a PDF agent instance."""

    agent_id: str
    name: str
    description: str
    mcp_servers: list[str]


class AgentRegistry:
    """Registry to manage created PDF agent instances."""

    def __init__(self):
        self._agents: Dict[str, Agent] = {}
        self._metadata: Dict[str, PDFAgentMetadata] = {}

    def register(self, agent: Agent, metadata: PDFAgentMetadata) -> None:
        """Register a new agent instance."""
        self._agents[metadata.agent_id] = agent
        self._metadata[metadata.agent_id] = metadata

    def get_agent(self, agent_id: str) -> Optional[Agent]:
        """Get an agent by ID."""
        return self._agents.get(agent_id)

    def get_metadata(self, agent_id: str) -> Optional[PDFAgentMetadata]:
        """Get agent metadata by ID."""
        return self._metadata.get(agent_id)

    def list_agents(self) -> list[PDFAgentMetadata]:
        """List all registered agents."""
        return list(self._metadata.values())

    def exists(self, agent_id: str) -> bool:
        """Check if an agent exists."""
        return agent_id in self._agents


class PDFAgentCollection(ActionCollection):
    """MCP service for PDF processing agent that can extract and analyze PDF documents.

    Provides comprehensive PDF processing capabilities including:
    - create PDF agent
    - reuse existing PDF agent
    """

    def __init__(self, arguments: ActionArguments) -> None:
        super().__init__(arguments)
        # Initialize agent registry
        self.agent_registry = AgentRegistry()
        # Load MCP configuration for search tools
        self.mcp_config = self._load_mcp_config()
        # Log initialization status
        self._color_log("PDF agent service initialized", Color.green, "debug")

    def _load_mcp_config(self) -> Dict[str, Any]:
        """Load MCP configuration for PDF agent tools."""
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
    ) -> tuple[Agent, PDFAgentMetadata]:
        """Create a new PDF agent instance with its own configuration."""
        # Generate unique agent ID
        agent_id = f"pdf_agent_{uuid.uuid4().hex[:8]}"

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

        # Create agent with MCP tools using custom PDFAgent class
        agent = PDFAgent(
            conf=agent_config,
            name=name,
            agent_id=agent_id,
            system_prompt=system_prompt,
            mcp_config=self.mcp_config,
            mcp_servers=available_servers,
        )

        # Create metadata
        metadata = PDFAgentMetadata(
            agent_id=agent_id,
            name=name,
            description=description,
            mcp_servers=available_servers,
        )

        # Register agent
        self.agent_registry.register(agent, metadata)

        return agent, metadata

    def mcp_create_pdf_agent(
        self,
        task_prompt: str = Field(description="The task or query for the pdf agent to process"),
        name: str = Field(default="pdf_agent", description="Name for the pdf agent"),
        description: str = Field(
            default="PDF agent specialized in pdf processing",
            description="Description of the pdf agent's purpose",
        ),
        max_steps: int = Field(default=12, description="Maximum steps for agent execution"),
    ) -> ActionResponse:
        """
        Create a new pdf agent and execute the given task.

        This method creates a pdf agent with:
        1. Unique agent ID
        2. Custom name and description
        3. Independent LLM instance (configured via environment variables)
        4. Dedicated memory module
        5. MCP tools

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
            self._color_log(f"🤖 Creating new pdf agent: {name}", Color.cyan)

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
                enhanced_task_prompt = f"{task_prompt_with_id}\n\n{memory_context}"

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

            # Format response
            formatted_message = f"""**Answer:** {answer if answer else "No answer generated"}"""

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
            error_msg = f"Failed to create and execute PDF agent: {str(e)}"
            self.logger.error(f"PDF agent error: {traceback.format_exc()}")
            self._color_log(f"❌ {error_msg}", Color.red)

            return ActionResponse(
                success=False,
                message=error_msg,
                metadata={"error_type": "agent_creation_failed", "error_details": str(e)},
            )

    def mcp_use_existing_pdf_agent(
        self,
        agent_id: str = Field(description="The ID of an existing PDF agent to use"),
        task_prompt: str = Field(description="The task or query for the PDF agent to process"),
        max_steps: int = Field(default=12, description="Maximum steps for agent execution"),
    ) -> ActionResponse:
        """
        Use an existing PDF agent to execute a task.

        This method reuses a previously created PDF agent, maintaining its
        configuration, memory, and state across multiple tasks.

        Args:
            agent_id: ID of the existing PDF agent
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

            self._color_log(f"🔄 Using existing PDF agent: {metadata.name} ({agent_id})", Color.cyan)

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
                enhanced_task_prompt = f"{task_prompt_with_id}\n\n{memory_context}"

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

            # Format response
            formatted_message = f"""**Answer:** {answer if answer else "No answer generated"}"""

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
            self.logger.error(f"PDF agent error: {traceback.format_exc()}")
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
        name="pdf_agent_service",
        transport="stdio",
        workspace=os.getenv("AWORLD_WORKSPACE", "~"),
    )

    # Initialize and run the PDF service
    try:
        service = PDFAgentCollection(args)
        service.run()
    except Exception as e:
        print(f"An error occurred: {e}: {traceback.format_exc()}")
