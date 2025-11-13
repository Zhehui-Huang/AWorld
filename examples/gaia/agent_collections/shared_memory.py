"""
Shared Memory System for Agent Collections

This module provides a memory system for agents to save and retrieve past task experiences.
Each agent instance has its own isolated memory space, ensuring privacy and independence.

Key features:
- Memory storage with concrete information (files, URLs)
- Reflection and learning (what worked, what failed, lessons learned)
- Each agent instance has separate memory (no sharing, even between agents of same type)
- Retrieval of relevant past experiences based on task similarity using semantic embeddings
- Success/failure tracking with artifacts and reflection
- Semantic similarity-based retrieval with recency weighting
- Integration with AWorld's embedding providers (OpenAI, Ollama, etc.)

Memory Entry Structure:
- task_description: Task description
- success: Whether the task succeeded or failed
- artifacts: List of concrete resources (files, URLs, images) with full details
  Example: [{"type": "pdf", "name": "paper.pdf", "path": "/workspace/paper.pdf", "url": "https://..."}]
- reflection: Agent's self-assessment and learning
  Example: {
      "what_worked": ["Using specific search terms", "Downloading from arxiv.org"],
      "what_failed": ["Generic queries", "Paywalled journals"],
      "lessons_learned": "Prioritize open-access sources for better success rate"
  }
"""

import hashlib
import json
import os
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from aworld.core.memory import EmbeddingsConfig
from aworld.logs.util import logger
from aworld.memory.embeddings.base import EmbeddingFactory, Embeddings


class AgentMemory:
    """Memory system for agents to store and retrieve task experiences with semantic search."""

    def __init__(
        self,
        memory_dir: Optional[str] = None,
        embeddings_config: Optional[EmbeddingsConfig] = None,
        use_embeddings: bool = True
    ):
        """Initialize the agent memory system.
        
        Args:
            memory_dir: Directory to store memory files. Defaults to workspace/agent_memories
            embeddings_config: Configuration for embedding provider. If None, uses environment variables.
            use_embeddings: Whether to use semantic embeddings for similarity. Falls back to keyword matching if False.
        """
        if memory_dir is None:
            # Default to workspace directory
            workspace = os.getenv("AWORLD_WORKSPACE", os.path.expanduser("~"))
            memory_dir = os.path.join(workspace, "agent_memories")
        
        self.memory_dir = Path(memory_dir)
        self.memory_dir.mkdir(parents=True, exist_ok=True)
        self.use_embeddings = use_embeddings
        self.embedder: Optional[Embeddings] = None
        
        # Initialize embedder if requested
        if self.use_embeddings:
            self._init_embedder(embeddings_config)
    
    def _init_embedder(self, embeddings_config: Optional[EmbeddingsConfig] = None) -> None:
        """Initialize the embedding model.
        
        Args:
            embeddings_config: Custom embedding configuration. If None, uses environment variables.
        """
        try:
            if embeddings_config is None:
                # Build configuration from environment variables
                embeddings_config = EmbeddingsConfig(
                    provider=os.getenv("EMBEDDING_PROVIDER", "openai"),
                    api_key=os.getenv("EMBEDDING_API_KEY") or os.getenv("OPENAI_API_KEY"),
                    model_name=os.getenv("EMBEDDING_MODEL_NAME", "text-embedding-3-small"),
                    base_url=os.getenv("EMBEDDING_BASE_URL", "https://api.openai.com/v1"),
                    dimensions=int(os.getenv("EMBEDDING_MODEL_DIMENSIONS", "512")),
                    timeout=int(os.getenv("EMBEDDING_TIMEOUT", "60"))
                )
            
            self.embedder = EmbeddingFactory.get_embedder(embeddings_config)
            logger.info(f"✅ Initialized embedder: {embeddings_config.provider}/{embeddings_config.model_name}")
            
        except Exception as e:
            logger.warning(f"⚠️ Failed to initialize embedder, falling back to keyword matching: {e}")
            self.embedder = None
            self.use_embeddings = False
    
    def _get_memory_file(self, agent_id: str) -> Path:
        """Get the memory file path for a specific agent instance.
        
        Args:
            agent_id: Unique ID of the agent instance
        
        Returns:
            Path to the memory file
        """
        return self.memory_dir / f"{agent_id}_memory.json"
    
    def _load_memories(self, agent_id: str) -> List[Dict[str, Any]]:
        """Load memories for a specific agent instance.
        
        Args:
            agent_id: Unique ID of the agent instance
        
        Returns:
            List of memory entries
        """
        memory_file = self._get_memory_file(agent_id)
        
        if not memory_file.exists():
            return []
        
        try:
            with open(memory_file, 'r', encoding='utf-8') as f:
                memories = json.load(f)
                logger.debug(f"Loaded {len(memories)} memories for agent {agent_id}")
                return memories
        except (json.JSONDecodeError, IOError) as e:
            logger.error(f"Failed to load memories for agent {agent_id}: {e}")
            return []
    
    def _save_memories(self, agent_id: str, memories: List[Dict[str, Any]]) -> None:
        """Save memories for a specific agent instance.
        
        Args:
            agent_id: Unique ID of the agent instance
            memories: List of memory entries to save
        """
        memory_file = self._get_memory_file(agent_id)
        
        try:
            with open(memory_file, 'w', encoding='utf-8') as f:
                json.dump(memories, f, indent=2, ensure_ascii=False)
            logger.debug(f"Saved {len(memories)} memories for agent {agent_id}")
        except IOError as e:
            logger.error(f"Failed to save memories for agent {agent_id}: {e}")
    
    def _calculate_relevance_score(self, query: str, memory_task: str) -> float:
        """
        Calculate semantic relevance score between query and memory task.

        Uses the framework's embedding system for semantic similarity.
        Falls back to keyword/Jaccard similarity if embeddings are not available.

        Args:
            query: Current task query
            memory_task: Past task description

        Returns:
            Relevance score (0.0 to 1.0)
        """
        # Use semantic embeddings if available
        if self.use_embeddings and self.embedder is not None:
            try:
                return self._semantic_similarity(query, memory_task)
            except Exception as e:
                logger.warning(f"⚠️ Semantic similarity failed, falling back to keyword matching: {e}")
                return self._keyword_similarity(query, memory_task)
        
        # Fall back to keyword similarity
        return self._keyword_similarity(query, memory_task)
    
    def _semantic_similarity(self, query: str, memory_task: str) -> float:
        """
        Calculate semantic similarity using embeddings.
        
        Args:
            query: Current task query
            memory_task: Past task description
            
        Returns:
            Similarity score (0.0 to 1.0)
        """
        try:
            import numpy as np
            
            # Get embeddings for both texts
            query_embedding = self.embedder.embed_query(query)
            memory_embedding = self.embedder.embed_query(memory_task)
            
            # Convert to numpy arrays
            query_vec = np.array(query_embedding)
            memory_vec = np.array(memory_embedding)
            
            # Calculate cosine similarity
            dot_product = float(np.dot(query_vec, memory_vec))
            query_norm = float(np.linalg.norm(query_vec))
            memory_norm = float(np.linalg.norm(memory_vec))
            
            if query_norm == 0 or memory_norm == 0:
                return 0.0
            
            cosine_similarity = dot_product / (query_norm * memory_norm)
            
            # Normalize to [0, 1] range (cosine similarity is in [-1, 1])
            normalized_score = max(0.0, min(1.0, (cosine_similarity + 1.0) / 2.0))
            
            return normalized_score
            
        except ImportError:
            logger.warning("NumPy not available, falling back to keyword similarity")
            return self._keyword_similarity(query, memory_task)
    
    def _keyword_similarity(self, query: str, memory_task: str) -> float:
        """
        Calculate keyword-based similarity using Jaccard index.
        
        Args:
            query: Current task query
            memory_task: Past task description
            
        Returns:
            Similarity score (0.0 to 1.0)
        """
        query_lower = query.lower()
        memory_lower = memory_task.lower()
        
        query_words = set(query_lower.split())
        memory_words = set(memory_lower.split())
        
        if not query_words or not memory_words:
            return 0.0
        
        intersection = query_words.intersection(memory_words)
        union = query_words.union(memory_words)
        
        return len(intersection) / len(union) if union else 0.0
    
    def save_task_memory(
        self,
        agent_id: str,
        agent_type: str,
        task_description: str,
        success: bool,
        artifacts: Optional[List[Dict[str, Any]]] = None,
        reflection: Optional[Dict[str, Any]] = None
    ) -> None:
        """Save a task memory entry for a specific agent instance.
        
        Args:
            agent_id: Unique ID of the agent instance
            agent_type: Type of agent (e.g., 'search_agent', 'pdf_agent')
            task_description: Description of the task that was attempted
            success: Whether the task succeeded or failed
            artifacts: List of concrete resources used/created (files, URLs, etc.)
                      Example: [{"type": "pdf", "name": "Research Paper", "path": "paper.pdf", "url": "https://..."}]
            reflection: Agent's learning and self-assessment
                       Example: {
                           "what_worked": ["Using specific search terms", "Downloading PDFs directly"],
                           "what_failed": ["Generic search queries", "Accessing paywalled content"],
                           "lessons_learned": "Always check if paper is open-access before attempting download"
                       }
        """
        memories = self._load_memories(agent_id)
        
        # Create memory entry
        memory_entry = {
            "id": hashlib.md5(
                f"{agent_id}_{task_description}_{datetime.now().isoformat()}".encode()
            ).hexdigest()[:12],
            "agent_id": agent_id,
            "agent_type": agent_type,
            "task_description": task_description,
            "success": success,
            "artifacts": artifacts or [],
            "reflection": reflection or {},
            "timestamp": datetime.now().isoformat()
        }
        
        # Add to memories
        memories.append(memory_entry)
        
        # Keep only last 100 memories per agent instance (configurable)
        max_memories = 100
        if len(memories) > max_memories:
            logger.info(f"Pruning old memories for agent {agent_id}, keeping last {max_memories}")
            memories = memories[-max_memories:]
        
        # Save to disk
        self._save_memories(agent_id, memories)
        
        # Log the save
        status = "✓ SUCCESS" if success else "✗ FAILURE"
        artifacts_count = len(artifacts) if artifacts else 0
        has_reflection = bool(reflection)
        logger.info(
            f"💾 [{status}] Saved memory for agent {agent_id} ({agent_type}): "
            f"{task_description[:60]}... ({artifacts_count} artifacts, "
            f"reflection: {has_reflection})"
        )
    
    def retrieve_relevant_memories(
        self,
        agent_id: str,
        task_description: str,
        max_results: int = 5,
        min_relevance: float = 0.1
    ) -> List[Dict[str, Any]]:
        """Retrieve relevant past memories for a specific agent instance.
        
        Uses semantic similarity (if embeddings are available) or keyword matching
        to find the most relevant past experiences. Results are ranked by a combination
        of relevance and recency.
        
        Args:
            agent_id: Unique ID of the agent instance
            task_description: Current task description
            max_results: Maximum number of memories to return
            min_relevance: Minimum relevance score threshold (0.0 to 1.0)
        
        Returns:
            List of relevant memory entries, sorted by relevance and recency
        """
        memories = self._load_memories(agent_id)
        
        if not memories:
            logger.debug(f"No memories found for agent {agent_id}")
            return []
        
        # Calculate relevance scores
        scored_memories = []
        for memory in memories:
            try:
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
                    
                    # Weighted combination: 70% relevance, 30% recency
                    final_score = relevance_score * 0.7 + recency_bonus * 0.3
                    
                    scored_memories.append({
                        "memory": memory,
                        "relevance_score": relevance_score,
                        "recency_bonus": recency_bonus,
                        "final_score": final_score
                    })
            except Exception as e:
                logger.warning(f"Error scoring memory {memory.get('id', 'unknown')}: {e}")
                continue
        
        # Sort by final score (descending)
        scored_memories.sort(key=lambda x: x["final_score"], reverse=True)
        
        # Log retrieval results
        if scored_memories:
            top_score = scored_memories[0]["final_score"]
            logger.debug(
                f"Retrieved {min(len(scored_memories), max_results)}/{len(memories)} "
                f"memories for agent {agent_id} (top score: {top_score:.3f})"
            )
        
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
            
            # Add artifacts if available
            artifacts = memory.get('artifacts', [])
            if artifacts:
                formatted += f"   Artifacts Used ({len(artifacts)}):\n"
                for artifact in artifacts[:10]:  # Limit to first 10 to avoid overwhelming the prompt
                    artifact_type = artifact.get('type', 'unknown')
                    artifact_name = artifact.get('name', 'unnamed')
                    if artifact_type == 'url':
                        formatted += f"      - {artifact_name}: {artifact.get('url', 'N/A')}\n"
                    elif artifact_type in ['pdf', 'file', 'image']:
                        formatted += f"      - {artifact_name} ({artifact_type}): {artifact.get('path', 'N/A')}\n"
                    else:
                        formatted += f"      - {artifact_name} ({artifact_type})\n"
                if len(artifacts) > 10:
                    formatted += f"      ... and {len(artifacts) - 10} more artifacts\n"
            
            # Add reflection - This is crucial for learning
            reflection = memory.get('reflection', {})
            if reflection:
                formatted += f"   Agent Reflection:\n"
                
                what_worked = reflection.get('what_worked', [])
                if what_worked:
                    formatted += f"      ✓ What Worked:\n"
                    for item in what_worked[:5]:
                        formatted += f"         - {item}\n"
                
                what_failed = reflection.get('what_failed', [])
                if what_failed:
                    formatted += f"      ✗ What Failed:\n"
                    for item in what_failed[:5]:
                        formatted += f"         - {item}\n"
                
                lessons_learned = reflection.get('lessons_learned', '')
                if lessons_learned:
                    formatted += f"      💡 Lesson: {lessons_learned}\n"
            
            formatted += f"   Date: {memory['timestamp'][:10]}\n\n"
        
        formatted += "Use these past experiences to inform your approach:\n"
        formatted += "- Learn from what worked and what failed\n"
        formatted += "- Apply the lessons learned\n"
        formatted += "- Utilize successful artifacts and approaches\n"
        formatted += "=== END OF PAST EXPERIENCES ===\n"
        
        return formatted
    
    def get_memory_stats(self, agent_id: str) -> Dict[str, Any]:
        """Get statistics about memories for a specific agent instance.
        
        Args:
            agent_id: Unique ID of the agent instance
        
        Returns:
            Dictionary with memory statistics
        """
        memories = self._load_memories(agent_id)
        
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
_global_memory: Optional[AgentMemory] = None


def get_agent_memory(
    memory_dir: Optional[str] = None,
    embeddings_config: Optional[EmbeddingsConfig] = None,
    use_embeddings: bool = True,
    reset: bool = False
) -> AgentMemory:
    """Get the global shared agent memory instance.
    
    This function returns a singleton instance of AgentMemory. By default, it uses
    environment variables to configure the embedding provider.
    
    Args:
        memory_dir: Directory to store memory files. Only used on first initialization.
        embeddings_config: Custom embedding configuration. Only used on first initialization.
        use_embeddings: Whether to use semantic embeddings. Only used on first initialization.
        reset: If True, forces recreation of the global instance with new settings.
    
    Returns:
        AgentMemory instance
    """
    global _global_memory
    if _global_memory is None or reset:
        _global_memory = AgentMemory(
            memory_dir=memory_dir,
            embeddings_config=embeddings_config,
            use_embeddings=use_embeddings
        )
    return _global_memory

