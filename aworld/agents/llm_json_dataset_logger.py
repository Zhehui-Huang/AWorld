import os
import json
import hashlib
from pathlib import Path
from datetime import datetime
from typing import Optional, Dict, Set, Tuple


def log_separate_llm_call(
    messages: list[dict],
    agent_type: str,
    agent_id: str,
    llm_purpose: str = "separate_llm"
):
    """
    Log a separate LLM call (not from the main agent) in Qwen3 format.
    Creates a file named: logs/trajectories/{agent_type}_{agent_id}_{llm_purpose}.jsonl
    
    Args:
        messages: List of message dicts with role/content
        agent_type: Type of agent (e.g., "file_agent")
        agent_id: Unique agent ID
        llm_purpose: Purpose of this LLM call (e.g., "summarization", "image_analysis")
    """
    try:
        # Create file path based on agent_type, agent_id, and purpose
        trajectories_dir = Path("logs/trajectories")
        trajectories_dir.mkdir(parents=True, exist_ok=True)
        file_path = trajectories_dir / f"{agent_type}_{agent_id}_{llm_purpose}.jsonl"
        
        # Convert to Qwen3 format
        qwen_messages = []
        for message in messages:
            role = message.get("role", "user")
            qwen_msg = {"role": role}
            content = message.get("content", "")
            if isinstance(content, str):
                qwen_msg["content"] = content
            elif isinstance(content, list):
                qwen_msg["content"] = str(content)
            else:
                qwen_msg["content"] = str(content) if content else ""
            
            # Always include system messages (even if empty), skip empty non-system messages
            if role == "system" or qwen_msg["content"]:
                qwen_messages.append(qwen_msg)
        
        # Build Qwen3 record
        record = {"messages": qwen_messages}
        
        # Append to file
        with open(file_path, "a", encoding="utf-8") as f:
            json.dump(record, f, ensure_ascii=False)
            f.write("\n")
    except Exception as e:
        print(f"Error logging separate LLM call: {e}")


class LLMJsonDatasetLogger:
    """
    Logs structured LLM conversations (role/content pairs) to agent-specific JSONL files.
    Each agent gets its own trajectory file to avoid redundancy and maintain clean datasets.
    
    Features:
    - Agent-specific trajectory files
    - Conversation deduplication
    - Hierarchical agent tracking
    - Metadata preservation
    """

    def __init__(
        self, 
        file_path: str = "logs/llm_messages.jsonl",
        agent_id: Optional[str] = None,
        agent_name: Optional[str] = None,
        agent_type: Optional[str] = None,
        parent_agent_id: Optional[str] = None,
        orchestration_level: int = 0
    ):
        """
        Initialize logger with agent context.
        
        Args:
            file_path: Legacy path for backward compatibility (used if agent_id not provided)
            agent_id: Unique identifier for the agent
            agent_name: Human-readable name of the agent
            agent_type: Type of agent (main, orchestrator, search_agent, file_agent, etc.)
            parent_agent_id: ID of parent agent in hierarchy (if any)
            orchestration_level: Level in orchestration hierarchy (0 = main agent)
        """
        self._agent_id = agent_id
        self._agent_name = agent_name
        self._agent_type = agent_type
        self._parent_agent_id = parent_agent_id
        self._orchestration_level = orchestration_level
        self._base_file_path = file_path
        
        # Track current session and task for unique trajectory logging
        self._session_id: Optional[str] = None
        self._task_id: Optional[str] = None
        
        # Determine and set file path
        self._update_file_path()
        
        # Track logged conversations to avoid duplicates (per agent instance)
        self._logged_conversations: Set[str] = set()
        
        # Track conversation threads (to only keep final/longest version)
        # Key: thread_id (based on first message), Value: (message_count, conversation_hash)
        self._conversation_threads: Dict[str, Tuple[int, str]] = {}
        
        self._load_logged_conversation_ids_for_agent()
        
        # Conversation counter for this specific agent instance
        self._conversation_count = 0
    
    @property
    def agent_id(self) -> Optional[str]:
        return self._agent_id
    
    @agent_id.setter
    def agent_id(self, value: Optional[str]):
        self._agent_id = value
    
    @property
    def agent_name(self) -> Optional[str]:
        return self._agent_name
    
    @agent_name.setter
    def agent_name(self, value: Optional[str]):
        self._agent_name = value
    
    @property
    def agent_type(self) -> Optional[str]:
        return self._agent_type
    
    @agent_type.setter
    def agent_type(self, value: Optional[str]):
        """Update agent type and recalculate file path."""
        self._agent_type = value
        self._update_file_path()
    
    @property
    def parent_agent_id(self) -> Optional[str]:
        return self._parent_agent_id
    
    @parent_agent_id.setter
    def parent_agent_id(self, value: Optional[str]):
        self._parent_agent_id = value
    
    @property
    def orchestration_level(self) -> int:
        return self._orchestration_level
    
    @orchestration_level.setter
    def orchestration_level(self, value: int):
        self._orchestration_level = value
    
    @property
    def session_id(self) -> Optional[str]:
        return self._session_id
    
    @session_id.setter
    def session_id(self, value: Optional[str]):
        self._session_id = value
    
    @property
    def task_id(self) -> Optional[str]:
        return self._task_id
    
    @task_id.setter
    def task_id(self, value: Optional[str]):
        self._task_id = value
    
    def _update_file_path(self):
        """Update file path based on current agent_type."""
        # Determine file path based on agent type (one file per agent type)
        if self._agent_type:
            # Create agent-type-specific trajectory file
            trajectories_dir = Path("logs/trajectories")
            trajectories_dir.mkdir(parents=True, exist_ok=True)
            # Use agent_type for filename (e.g., "search_agent.jsonl", "file_agent.jsonl")
            self.file_path = trajectories_dir / f"{self._agent_type}.jsonl"
        elif self._agent_id:
            # Fallback to agent_id if no type specified
            trajectories_dir = Path("logs/trajectories")
            trajectories_dir.mkdir(parents=True, exist_ok=True)
            self.file_path = trajectories_dir / f"{self._agent_id}.jsonl"
        else:
            # Fallback to legacy behavior
            self.file_path = Path(self._base_file_path)
            self.file_path.parent.mkdir(parents=True, exist_ok=True)

    def _load_logged_conversation_ids_for_agent(self):
        """Load existing conversation IDs for this specific agent instance to avoid duplicates."""
        if not hasattr(self, 'file_path') or not self.file_path.exists() or not self._agent_id:
            return
            
        try:
            with open(self.file_path, "r", encoding="utf-8") as f:
                for line in f:
                    if line.strip():
                        record = json.loads(line)
                        # Check if this record is for our agent instance and same task
                        record_agent_id = record.get("_agent_id") or record.get("agent_id")
                        record_task_id = record.get("_task_id")
                        
                        # Match by agent_id and task_id if both are set
                        if record_agent_id == self._agent_id and (not self._task_id or record_task_id == self._task_id):
                            # Rebuild thread tracking
                            messages = record.get("messages", [])
                            if messages:
                                conv_hash = self._compute_conversation_hash(messages)
                                thread_id = self._compute_thread_id(messages)
                                msg_count = len(messages)
                                
                                # Keep track of the longest conversation per thread
                                if thread_id not in self._conversation_threads or msg_count > self._conversation_threads[thread_id][0]:
                                    self._conversation_threads[thread_id] = (msg_count, conv_hash)
                                    self._logged_conversations.add(conv_hash)
        except Exception as e:
            print(f"Warning: Could not load existing conversation IDs: {e}")

    def _compute_conversation_hash(self, messages: list[dict]) -> str:
        """
        Compute a unique hash for a conversation to detect duplicates.
        Uses message content, roles, and tool calls.
        """
        # Create a canonical representation of the conversation
        canonical = []
        for msg in messages:
            msg_repr = {
                "role": msg.get("role", ""),
                "content": str(msg.get("content", ""))[:1000],  # First 1000 chars
            }
            # Include tool call info if present
            if "tool_calls" in msg:
                tool_calls = msg["tool_calls"]
                if isinstance(tool_calls, list):
                    msg_repr["tool_calls"] = [
                        {
                            "name": tc.get("function", {}).get("name", "") if isinstance(tc, dict) else "",
                            "args": str(tc.get("function", {}).get("arguments", ""))[:200] if isinstance(tc, dict) else ""
                        }
                        for tc in tool_calls
                    ]
            canonical.append(msg_repr)
        
        # Generate hash
        canonical_str = json.dumps(canonical, sort_keys=True, ensure_ascii=False)
        return hashlib.sha256(canonical_str.encode()).hexdigest()[:16]
    
    def _compute_thread_id(self, messages: list[dict] = None) -> str:
        """
        Compute a thread ID based on agent_type, agent_id, session_id, and task_id.
        Each unique combination gets its own thread to prevent overwriting trajectories
        when agents are reused across different tasks.
        
        Args:
            messages: Not used, kept for API compatibility
        """
        # Use agent_type, agent_id, session_id, and task_id as the thread identifier
        # This ensures each task gets its own trajectory even when reusing the same agent
        agent_type = self._agent_type or "unknown"
        agent_id = self._agent_id or "unknown"
        session_id = self._session_id or "no_session"
        task_id = self._task_id or "no_task"
        thread_key = f"{agent_type}_{agent_id}_{session_id}_{task_id}"
        return hashlib.sha256(thread_key.encode()).hexdigest()[:16]

    def log_conversation(
        self, 
        messages: list[dict],
        task_id: Optional[str] = None,
        metadata: Optional[Dict] = None
    ):
        """
        Write one conversation in Qwen3-compatible format.
        Only logs the final/longest version of multi-turn conversations.
        
        Args:
            messages: List of message dicts with role/content
            task_id: Optional task identifier
            metadata: Additional metadata to include
            
        Qwen3 format:
        {
          "messages": [
            {"role": "system", "content": "..."},
            {"role": "user", "content": "..."},
            {"role": "assistant", "content": "...", "tool_calls": [...]}
          ]
        }
        """
        if not messages:
            return
        
        # Skip if agent_id is not set (shouldn't happen but defensive)
        if not self._agent_id:
            return
            
        try:
            # Generate conversation hash and thread ID
            conversation_hash = self._compute_conversation_hash(messages)
            thread_id = self._compute_thread_id()
            
            # Skip if this exact conversation was already logged
            if conversation_hash in self._logged_conversations:
                return
            
            # Check if this is part of an existing conversation thread
            needs_rewrite = False
            if thread_id in self._conversation_threads:
                prev_msg_count, prev_hash = self._conversation_threads[thread_id]
                
                # If this is a shorter or equal length conversation, skip it (it's intermediate)
                if len(messages) <= prev_msg_count:
                    return
                
                # This is a longer conversation - it's the continuation
                # Remove the previous shorter version from logged set
                self._logged_conversations.discard(prev_hash)
                needs_rewrite = True
            
            # Update thread tracking with this (longer) conversation
            self._conversation_threads[thread_id] = (len(messages), conversation_hash)
            self._logged_conversations.add(conversation_hash)
            self._conversation_count += 1
            
            # Convert to Qwen3 format - preserve important fields
            qwen_messages = []
            for message in messages:
                role = message.get("role", "user")
                
                # Handle content
                content = message.get("content", "")
                if isinstance(content, str):
                    content_str = content
                elif isinstance(content, list):
                    # For multimodal content, convert to string
                    content_str = str(content)
                else:
                    content_str = str(content) if content else ""
                
                # Build message dict
                qwen_msg = {"role": role, "content": content_str}
                
                # Include tool_calls if present (for assistant messages)
                if "tool_calls" in message and message["tool_calls"]:
                    tool_calls = message["tool_calls"]
                    # Serialize tool_calls to proper format
                    if isinstance(tool_calls, list):
                        serialized_calls = []
                        for tc in tool_calls:
                            if hasattr(tc, 'to_dict'):
                                serialized_calls.append(tc.to_dict())
                            elif isinstance(tc, dict):
                                serialized_calls.append(tc)
                            else:
                                serialized_calls.append(str(tc))
                        qwen_msg["tool_calls"] = serialized_calls
                    else:
                        qwen_msg["tool_calls"] = str(tool_calls)
                
                # Include tool_call_id if present (for tool messages)
                if "tool_call_id" in message and message["tool_call_id"]:
                    qwen_msg["tool_call_id"] = message["tool_call_id"]
                
                # Always include system messages, even if empty (important for training)
                # For other roles, skip if content is empty AND no tool_calls
                if role == "system" or content_str or qwen_msg.get("tool_calls"):
                    qwen_messages.append(qwen_msg)
            
            # Skip if no valid messages
            if not qwen_messages:
                return
            
            # Build Qwen3 record with agent tracking info
            # The _agent_id, _session_id, _task_id fields are for internal tracking only, can be ignored during training
            record = {
                "messages": qwen_messages,
                "_agent_id": self._agent_id,  # Internal tracking field
                "_session_id": self._session_id,  # Track which session this belongs to
                "_task_id": self._task_id  # Track which task this belongs to
            }
            
            # For multi-turn conversations, we need to rewrite the file
            # to replace shorter versions with this longer one
            if needs_rewrite:
                self._rewrite_file_replacing_thread(record)
            else:
                # New conversation, just append
                with open(self.file_path, "a", encoding="utf-8") as f:
                    json.dump(record, f, ensure_ascii=False)
                    f.write("\n")
                
        except Exception as e:
            print(f"Error logging conversation for agent {self._agent_id}: {e}")
    
    def _rewrite_file_replacing_thread(self, new_record: dict):
        """
        Rewrite the trajectory file, replacing older version of this agent's conversation with new one.
        
        Args:
            new_record: The new (longer) conversation record to replace the old one
        """
        if not self.file_path.exists():
            # File doesn't exist yet, just write
            with open(self.file_path, "a", encoding="utf-8") as f:
                json.dump(new_record, f, ensure_ascii=False)
                f.write("\n")
            return
        
        # Read all existing records
        existing_records = []
        replaced = False
        
        try:
            with open(self.file_path, "r", encoding="utf-8") as f:
                for line in f:
                    if line.strip():
                        try:
                            record = json.loads(line)
                            
                            # Check if this record is from the same agent instance and task
                            # (by comparing _agent_id, _session_id, and _task_id)
                            record_agent_id = record.get("_agent_id")
                            record_session_id = record.get("_session_id")
                            record_task_id = record.get("_task_id")
                            
                            # Match if agent_id matches AND (no task tracking OR task/session match)
                            is_same_instance = (
                                record_agent_id == self._agent_id and
                                (not self._task_id or (record_session_id == self._session_id and record_task_id == self._task_id))
                            )
                            
                            if is_same_instance and not replaced:
                                # Replace with new record (only replace first occurrence)
                                existing_records.append(new_record)
                                replaced = True
                            else:
                                # Keep existing record
                                existing_records.append(record)
                        except json.JSONDecodeError:
                            # Skip malformed lines
                            continue
            
            # If we didn't replace (shouldn't happen), append
            if not replaced:
                existing_records.append(new_record)
            
            # Rewrite file atomically (write to temp file first)
            temp_path = self.file_path.with_suffix('.tmp')
            with open(temp_path, "w", encoding="utf-8") as f:
                for record in existing_records:
                    json.dump(record, f, ensure_ascii=False)
                    f.write("\n")
            
            # Replace original with temp file
            temp_path.replace(self.file_path)
                    
        except Exception as e:
            # If rewrite fails, just append
            print(f"Warning: Could not rewrite file, appending instead: {e}")
            try:
                with open(self.file_path, "a", encoding="utf-8") as f:
                    json.dump(new_record, f, ensure_ascii=False)
                    f.write("\n")
            except Exception as append_error:
                print(f"Error: Could not append to file either: {append_error}")