import os
import json
from pathlib import Path
from datetime import datetime

class LLMJsonDatasetLogger:
    """
    Logs structured LLM conversations (role/content pairs) to a JSONL file.
    Each line can directly serve as fine-tuning data.
    """

    def __init__(self, file_path: str = "logs/llm_messages.jsonl"):
        self.file_path = Path(file_path)
        self.file_path.parent.mkdir(parents=True, exist_ok=True)

    def log_conversation(self, messages: list[dict]):
        """
        Write one conversation (list of role/content messages) as one JSON line.
        Example messages:
        [
          {"role": "user", "content": "Hello"},
          {"role": "assistant", "content": "Hi there!", "tool_calls": [...]},
          {"role": "tool", "content": "...", "tool_call_id": "..."}
        ]
        """
        try:
            # Add token count to each message
            messages_with_tokens = []
            total_tokens = 0
            for message in messages:
                message_copy = message.copy()
                # Simple token estimation (rough approximation: 1 token ≈ 4 characters)
                content = message.get("content", "")
                if isinstance(content, str):
                    token_count = len(content) // 4
                else:
                    token_count = 0
                message_copy["token_count"] = token_count
                total_tokens += token_count
                messages_with_tokens.append(message_copy)
            
            record = {
                "timestamp": datetime.utcnow().isoformat(),
                "messages": messages_with_tokens,
                "total_tokens": total_tokens
            }
            with open(self.file_path, "a", encoding="utf-8") as f:
                json.dump(record, f, ensure_ascii=False)
                f.write("\n")
        except Exception as e:
            print(f"Error logging conversation: {e}")