"""
Shared Memory System for Agent Collections

This module provides a shared memory/database system for agents to save and retrieve
past task experiences. Agents of the same type (e.g., all search_agents) share memory,
allowing them to learn from past successes and failures.

Key features:
- Automatic memory saving after task completion
- Retrieval of relevant past experiences based on task similarity
- Separate memory spaces for different agent types
- Success/failure tracking with detailed summaries
- Keyword-based and recency-based retrieval
"""

import json
import os
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional
import hashlib


class AgentMemory:
    """Memory system for agents to store and retrieve task experiences."""

    def __init__(self, memory_dir: str = None):
        """Initialize the agent memory system.
        
        Args:
            memory_dir: Directory to store memory files. Defaults to workspace/agent_memories
        """
        if memory_dir is None:
            # Default to workspace directory
            workspace = os.getenv("AWORLD_WORKSPACE", os.path.expanduser("~"))
            memory_dir = os.path.join(workspace, "agent_memories")
        
        self.memory_dir = Path(memory_dir)
        self.memory_dir.mkdir(parents=True, exist_ok=True)
    
    def _get_memory_file(self, agent_type: str) -> Path:
        """Get the memory file path for a specific agent type.
        
        Args:
            agent_type: Type of agent (e.g., 'search_agent', 'pdf_agent')
        
        Returns:
            Path to the memory file
        """
        return self.memory_dir / f"{agent_type}_memory.json"
    
    def _load_memories(self, agent_type: str) -> List[Dict[str, Any]]:
        """Load memories for a specific agent type.
        
        Args:
            agent_type: Type of agent
        
        Returns:
            List of memory entries
        """
        memory_file = self._get_memory_file(agent_type)
        
        if not memory_file.exists():
            return []
        
        try:
            with open(memory_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError) as e:
            print(f"Warning: Could not load memories for {agent_type}: {e}")
            return []
    
    def _save_memories(self, agent_type: str, memories: List[Dict[str, Any]]) -> None:
        """Save memories for a specific agent type.
        
        Args:
            agent_type: Type of agent
            memories: List of memory entries to save
        """
        memory_file = self._get_memory_file(agent_type)
        
        try:
            with open(memory_file, 'w', encoding='utf-8') as f:
                json.dump(memories, f, indent=2, ensure_ascii=False)
        except IOError as e:
            print(f"Warning: Could not save memories for {agent_type}: {e}")
    
    def _calculate_relevance_score(self, query: str, memory_task: str) -> float:
        """Calculate relevance score between query and memory task.
        
        Simple keyword-based matching. Can be upgraded to semantic similarity later.
        
        Args:
            query: Current task query
            memory_task: Past task description
        
        Returns:
            Relevance score (0.0 to 1.0)
        """
        # Convert to lowercase for case-insensitive matching
        query_lower = query.lower()
        memory_lower = memory_task.lower()
        
        # Split into words
        query_words = set(query_lower.split())
        memory_words = set(memory_lower.split())
        
        # Calculate Jaccard similarity
        if not query_words or not memory_words:
            return 0.0
        
        intersection = query_words.intersection(memory_words)
        union = query_words.union(memory_words)
        
        return len(intersection) / len(union) if union else 0.0
    
    def save_task_memory(
        self,
        agent_type: str,
        task_description: str,
        success: bool,
        summary: str,
        metadata: Optional[Dict[str, Any]] = None
    ) -> None:
        """Save a task memory entry.
        
        Args:
            agent_type: Type of agent (e.g., 'search_agent', 'pdf_agent')
            task_description: Description of the task that was attempted
            success: Whether the task succeeded or failed
            summary: Summary of how it succeeded or why it failed
            metadata: Additional metadata (agent_id, execution_time, etc.)
        """
        memories = self._load_memories(agent_type)
        
        # Create memory entry
        memory_entry = {
            "id": hashlib.md5(
                f"{agent_type}_{task_description}_{datetime.now().isoformat()}".encode()
            ).hexdigest()[:12],
            "agent_type": agent_type,
            "task_description": task_description,
            "success": success,
            "summary": summary,
            "timestamp": datetime.now().isoformat(),
            "metadata": metadata or {}
        }
        
        # Add to memories
        memories.append(memory_entry)
        
        # Keep only last 100 memories per agent type (configurable)
        max_memories = 100
        if len(memories) > max_memories:
            memories = memories[-max_memories:]
        
        # Save to disk
        self._save_memories(agent_type, memories)
    
    def retrieve_relevant_memories(
        self,
        agent_type: str,
        task_description: str,
        max_results: int = 5,
        min_relevance: float = 0.1
    ) -> List[Dict[str, Any]]:
        """Retrieve relevant past memories for a task.
        
        Args:
            agent_type: Type of agent
            task_description: Current task description
            max_results: Maximum number of memories to return
            min_relevance: Minimum relevance score threshold
        
        Returns:
            List of relevant memory entries, sorted by relevance and recency
        """
        memories = self._load_memories(agent_type)
        
        if not memories:
            return []
        
        # Calculate relevance scores
        scored_memories = []
        for memory in memories:
            relevance_score = self._calculate_relevance_score(
                task_description,
                memory["task_description"]
            )
            
            if relevance_score >= min_relevance:
                # Add recency bonus (more recent = higher score)
                try:
                    timestamp = datetime.fromisoformat(memory["timestamp"])
                    days_old = (datetime.now() - timestamp).days
                    recency_bonus = 1.0 / (1.0 + days_old / 30.0)  # Decay over 30 days
                except (ValueError, KeyError):
                    recency_bonus = 0.0
                
                final_score = relevance_score * 0.7 + recency_bonus * 0.3
                
                scored_memories.append({
                    "memory": memory,
                    "relevance_score": relevance_score,
                    "recency_bonus": recency_bonus,
                    "final_score": final_score
                })
        
        # Sort by final score (descending)
        scored_memories.sort(key=lambda x: x["final_score"], reverse=True)
        
        # Return top results
        return [item["memory"] for item in scored_memories[:max_results]]
    
    def format_memories_for_prompt(self, memories: List[Dict[str, Any]]) -> str:
        """Format retrieved memories for inclusion in task prompt.
        
        Args:
            memories: List of memory entries
        
        Returns:
            Formatted string for prompt injection
        """
        if not memories:
            return ""
        
        formatted = "\n\n=== RELEVANT PAST EXPERIENCES ===\n"
        formatted += "You have access to the following past experiences from similar tasks:\n\n"
        
        for idx, memory in enumerate(memories, 1):
            status = "✓ SUCCESS" if memory["success"] else "✗ FAILURE"
            formatted += f"{idx}. [{status}] Task: {memory['task_description']}\n"
            formatted += f"   Summary: {memory['summary']}\n"
            formatted += f"   Date: {memory['timestamp'][:10]}\n\n"
        
        formatted += "Use these past experiences to inform your approach to the current task.\n"
        formatted += "=== END OF PAST EXPERIENCES ===\n"
        
        return formatted
    
    def get_memory_stats(self, agent_type: str) -> Dict[str, Any]:
        """Get statistics about memories for an agent type.
        
        Args:
            agent_type: Type of agent
        
        Returns:
            Dictionary with memory statistics
        """
        memories = self._load_memories(agent_type)
        
        if not memories:
            return {
                "total_memories": 0,
                "successful_tasks": 0,
                "failed_tasks": 0,
                "success_rate": 0.0
            }
        
        successful = sum(1 for m in memories if m["success"])
        failed = len(memories) - successful
        
        return {
            "total_memories": len(memories),
            "successful_tasks": successful,
            "failed_tasks": failed,
            "success_rate": successful / len(memories) if memories else 0.0,
            "oldest_memory": memories[0]["timestamp"] if memories else None,
            "newest_memory": memories[-1]["timestamp"] if memories else None
        }


# Global shared memory instance
_global_memory = None


def get_agent_memory() -> AgentMemory:
    """Get the global shared agent memory instance.
    
    Returns:
        AgentMemory instance
    """
    global _global_memory
    if _global_memory is None:
        _global_memory = AgentMemory()
    return _global_memory

