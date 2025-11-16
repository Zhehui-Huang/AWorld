"""
Agent Memory Utilities

Shared utilities for extracting conversation history, analyzing it with LLM,
and saving task memory with artifacts and reflection.

This module provides:
- Conversation history extraction from agent memory
- LLM-based analysis to extract artifacts and reflection
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
                    
                    # Extract tool calls if present
                    if hasattr(msg, 'tool_calls') and msg.tool_calls:
                        for tool_call in msg.tool_calls:
                            if hasattr(tool_call, 'function_name'):
                                tool_name = tool_call.function_name
                                tool_args = tool_call.function_arguments if hasattr(tool_call, 'function_arguments') else ''
                                conversation.append(f"[{role}] Tool call: {tool_name}")
                                if tool_args:
                                    # Do not truncate tool_args
                                    conversation.append(f"  Arguments: {tool_args}")
                    
                    # Add content if present, do not truncate
                    if content:
                        conversation.append(f"[{role}] {content}")
                
                return "\n".join(conversation)
        
        return "No conversation history available"
    except Exception as e:
        logger.warning(f"Error extracting conversation history: {e}")
        logger.debug(traceback.format_exc())
        return "Error extracting conversation history"


def extract_artifacts_and_reflection(
    agent: Agent,
    task_id: str,
    task_prompt: str,
    answer: Optional[str],
    agent_type: str = "agent"
) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    """Extract artifacts and reflection from task execution by analyzing conversation history.
    
    Args:
        agent: The agent instance that executed the task
        task_id: The task ID to filter messages
        task_prompt: The original task prompt
        answer: The final answer
        agent_type: Type of agent (for logging context)
        
    Returns:
        Tuple of (artifacts, reflection)
    """
    artifacts = []
    reflection = {
        "what_worked": [],
        "what_failed": [],
        "lessons_learned": ""
    }
    
    try:
        # Get conversation history
        conversation_history = extract_conversation_history(agent, task_id)
        
        # Create prompt for LLM to analyze the conversation
        analysis_prompt = f"""Analyze the following task execution conversation and extract key information.

Task: {task_prompt}

Final Answer: {answer if answer else "No answer generated"}

Conversation History:
{conversation_history}

Extract the following information in JSON format:

1. artifacts: List of concrete resources used or created (files, URLs, images, datasets, etc.)
   Each artifact should be a dict with keys like 'type', 'name', 'path', 'url'
   Example: {{"type": "pdf", "name": "paper.pdf", "path": "/workspace/paper.pdf", "url": "https://arxiv.org/..."}}

2. reflection: Agent self-reflection with:
   - what_worked: List of strategies/approaches that were successful
   - what_failed: List of strategies/approaches that failed
   - lessons_learned: String summarizing key insights and learnings

Return ONLY valid JSON with this structure:
{{
    "artifacts": [...],
    "reflection": {{
        "what_worked": [...],
        "what_failed": [...],
        "lessons_learned": "..."
    }}
}}"""

        # Call LLM to analyze
        llm_provider = os.getenv("LLM_PROVIDER", "openai")
        llm_model_name = os.getenv("LLM_MODEL_NAME", "gpt-4o")
        llm_base_url = os.getenv("LLM_BASE_URL")
        llm_api_key = os.getenv("LLM_API_KEY")
        
        llm_config = AgentConfig(
            llm_provider=llm_provider,
            llm_model_name=llm_model_name,
            llm_base_url=llm_base_url,
            llm_api_key=llm_api_key,
        )
        
        response = call_llm_model(
            llm_model=get_llm_model(conf=llm_config),
            messages=[{"role": "user", "content": analysis_prompt}],
            temperature=0.7
        )
        
        # Parse LLM response
        if response and response.content:
            try:
                analysis = json.loads(response.content)
                artifacts = analysis.get("artifacts", [])
                reflection = analysis.get("reflection", reflection)
            except json.JSONDecodeError as e:
                logger.warning(f"Failed to parse LLM response as JSON: {e}")
        
    except Exception as e:
        logger.warning(f"Error in LLM-based extraction for {agent_type}: {e}")
        logger.debug(traceback.format_exc())
        # Fallback to basic reflection
        if answer:
            reflection["what_worked"].append("Successfully completed the task")
            reflection["lessons_learned"] = "Task completed successfully"
        else:
            reflection["what_failed"].append("Failed to generate answer")
            reflection["lessons_learned"] = "Need to improve task approach"
    
    return artifacts, reflection


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
    """Extract artifacts/reflection and save task memory.
    
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
        # Extract artifacts and reflection
        artifacts, reflection = extract_artifacts_and_reflection(
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
            reflection=reflection
        )
        
        if logger_func:
            logger_func("💾 Task memory saved successfully", "debug")
    except Exception as e:
        error_msg = f"Failed to save task memory: {e}"
        if logger_func:
            logger_func(error_msg, "warning")
        else:
            logger.warning(error_msg)

