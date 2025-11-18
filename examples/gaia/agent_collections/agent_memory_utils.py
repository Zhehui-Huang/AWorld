"""
Agent Memory Utilities

Shared utilities for extracting conversation history, analyzing it with LLM,
and saving task memory with artifacts and experience summary.

This module provides:
- Conversation history extraction from agent memory
- LLM-based analysis to extract artifacts and experience summary
- Memory saving with structured data
"""

import json
import os
import traceback
from typing import Any, Dict, List, Optional, Tuple

from aworld.agents.llm_agent import Agent
from aworld.config.conf import AgentConfig
from aworld.models.llm import call_llm_model, get_llm_model
from aworld.logs.util import logger
from aworld.agents.llm_json_dataset_logger import log_separate_llm_call


def extract_conversation_history(agent: Agent, task_id: str) -> str:
    """Extract conversation history from the agent's memory, with full content (not truncated).
    
    Args:
        agent: The agent instance that executed the task
        task_id: The task ID to filter messages
        
    Returns:
        Formatted conversation history as a string
    """
    try:
        # Get the agent's memory/conversation history
        if hasattr(agent, 'memory') and agent.memory:
            # Get all messages for this task and agent
            filters = {
                "agent_id": agent.id(),
                "task_id": task_id
            }
            messages = agent.memory.get_all(filters=filters)
            
            if messages:
                conversation = []
                for msg in messages:
                    role = msg.role if hasattr(msg, 'role') else 'unknown'
                    content = msg.content if hasattr(msg, 'content') else ''
                    
                    has_tool_calls = hasattr(msg, 'tool_calls') and msg.tool_calls
                    has_content = bool(content)
                    
                    # Always keep standard conversation roles (system, user, assistant, tool)
                    # even if content is empty, since they might have tool calls or are part of the conversation flow
                    # For other roles, only keep if they have content or tool calls
                    standard_roles = ['system', 'user', 'assistant', 'tool']
                    should_include = role in standard_roles or has_content or has_tool_calls
                    
                    if should_include:
                        # Add role header
                        conversation.append(f"[{role}]")
                        
                        # Add content first if present (reasoning before action)
                        if has_content:
                            conversation.append(content)
                        
                        # Then show tool calls (actions taken based on reasoning)
                        if has_tool_calls:
                            for tool_call in msg.tool_calls:
                                try:
                                    # Handle nested structure: tool_call.function.name and tool_call.function.arguments
                                    if hasattr(tool_call, 'function') and tool_call.function:
                                        tool_name = tool_call.function.get('name') if isinstance(tool_call.function, dict) else getattr(tool_call.function, 'name', None)
                                        tool_args = tool_call.function.get('arguments') if isinstance(tool_call.function, dict) else getattr(tool_call.function, 'arguments', '')
                                    # Handle flat structure: tool_call.function_name and tool_call.function_arguments
                                    elif hasattr(tool_call, 'function_name'):
                                        tool_name = tool_call.function_name
                                        tool_args = tool_call.function_arguments if hasattr(tool_call, 'function_arguments') else ''
                                    else:
                                        continue
                                    
                                    if tool_name:
                                        conversation.append(f"  Tool call: {tool_name}")
                                        if tool_args:
                                            # Do not truncate tool_args
                                            conversation.append(f"  Arguments: {tool_args}")
                                except Exception as e:
                                    logger.debug(f"Error processing tool call: {e}")
                                    continue
                
                return "\n".join(conversation)
        
        return "No conversation history available"
    except Exception as e:
        logger.warning(f"Error extracting conversation history: {e}")
        logger.debug(traceback.format_exc())
        return "Error extracting conversation history"


def extract_artifacts_and_experience_summary(
    agent: Agent,
    task_id: str,
    task_prompt: str,
    answer: Optional[str],
    agent_type: str = "agent"
) -> Tuple[List[Dict[str, Any]], str]:
    """Extract artifacts and experience summary from task execution by analyzing conversation history.
    
    Args:
        agent: The agent instance that executed the task
        task_id: The task ID to filter messages
        task_prompt: The original task prompt
        answer: The final answer
        agent_type: Type of agent (for logging context)
        
    Returns:
        Tuple of (artifacts, experience_summary)
    """
    artifacts = []
    experience_summary = ""
    
    try:
        # Get conversation history
        conversation_history = extract_conversation_history(agent, task_id)
        
        # Create system and user prompts for LLM to analyze the conversation
        system_prompt = """You are an expert at analyzing AI agent task execution conversations. Your role is to extract structured information about artifacts (files, URLs, resources) used or created during task execution, and summarize key insights and learnings from the agent's experience."""
        
        user_prompt = f"""Analyze the following task execution conversation and extract key information.

Task: {task_prompt}

Final Answer: {answer if answer else "No answer generated"}

Conversation History:
{conversation_history}

Extract the following information in JSON format:

1. artifacts: List of concrete resources used or created (files, URLs, images, datasets, etc.)
   Each artifact should be a dictionary with the following keys: 'type', 'name', 'path', and 'url'. The file name is typically different from the file path. If the file title is unavailable, use the file path as the name; otherwise, use the file title as the name.
   Example: {{"type": "pdf", "name": "[FILE_NAME]", "path": "[FILE_PATH]", "url": "[FILE_URL]"}}

2. experience_summary: String summarizing key insights and learnings.

Return ONLY valid JSON with this structure:
{{
    "artifacts": [...],
    "experience_summary": "..."
}}"""

        # Call LLM to analyze
        llm_provider = os.getenv("LLM_PROVIDER", "openai")
        llm_model_name = os.getenv("LLM_MODEL_NAME", "gpt-4o")
        llm_base_url = os.getenv("LLM_BASE_URL")
        llm_api_key = os.getenv("LLM_API_KEY")
        llm_temperature = float(os.getenv("LLM_TEMPERATURE", "0.7"))
        
        llm_config = AgentConfig(
            llm_provider=llm_provider,
            llm_model_name=llm_model_name,
            llm_base_url=llm_base_url,
            llm_api_key=llm_api_key,
        )
        
        response = call_llm_model(
            llm_model=get_llm_model(conf=llm_config),
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            temperature=llm_temperature
        )
        
        # Log this separate LLM call with response (including system prompt)
        analysis_messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
            {"role": "assistant", "content": response.content if response else ""}
        ]
        log_separate_llm_call(
            messages=analysis_messages,
            agent_type=agent_type,
            agent_id=agent.id() if hasattr(agent, 'id') else "unknown",
            llm_purpose="memory_analysis"
        )
        
        # Parse LLM response
        if response and response.content:
            try:
                analysis = json.loads(response.content)
                artifacts = analysis.get("artifacts", [])
                experience_summary = analysis.get("experience_summary", experience_summary)
            except json.JSONDecodeError as e:
                logger.warning(f"Failed to parse LLM response as JSON: {e}")
        
    except Exception as e:
        logger.warning(f"Error in LLM-based extraction for {agent_type}: {e}")
        logger.debug(traceback.format_exc())
        # Fallback to basic experience summary
        if answer:
            experience_summary = "Successfully completed the task"
        else:
            experience_summary = "Failed to generate answer"
    
    return artifacts, experience_summary


def save_task_memory_with_analysis(
    memory,
    agent: Agent,
    task_id: str,
    agent_id: str,
    agent_type: str,
    task_prompt: str,
    answer: Optional[str],
    logger_func: Optional[callable] = None
) -> None:
    """Extract artifacts/experience summary and save task memory.
    
    Args:
        memory: The memory instance to save to
        agent: The agent that executed the task
        task_id: The task ID
        agent_id: The agent's unique ID
        agent_type: Type of agent (e.g., 'search_agent', 'orchestrator_agent')
        task_prompt: The original task prompt
        answer: The final answer
        logger_func: Optional logging function for success/error messages
    """
    try:
        # Extract artifacts and experience summary
        artifacts, experience_summary = extract_artifacts_and_experience_summary(
            agent=agent,
            task_id=task_id,
            task_prompt=task_prompt,
            answer=answer,
            agent_type=agent_type
        )
        
        # Save to memory
        memory.save_task_memory(
            agent_id=agent_id,
            agent_type=agent_type,
            task_description=task_prompt,
            success=bool(answer),
            artifacts=artifacts,
            experience_summary=experience_summary
        )
        
        if logger_func:
            logger_func("💾 Task memory saved successfully", "debug")
    except Exception as e:
        error_msg = f"Failed to save task memory: {e}"
        if logger_func:
            logger_func(error_msg, "warning")
        else:
            logger.warning(error_msg)

