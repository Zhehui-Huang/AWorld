import json

def calculate_total_tokens(jsonl_file_path):
    """
    Calculate the total tokens from logs/llm_messages.jsonl file.
    
    Args:
        jsonl_file_path: Path to the JSONL file
        
    Returns:
        Total sum of all total_tokens values
    """
    total = 0
    line_count = 0
    
    try:
        with open(jsonl_file_path, 'r', encoding='utf-8') as f:
            print(f"\n{'='*80}")
            print(f"Processing file: {jsonl_file_path}")
            print(f"{'='*80}\n")
            
            for line in f:
                line = line.strip()
                if not line:
                    continue
                    
                try:
                    data = json.loads(line)
                    if 'total_tokens' in data:
                        line_count += 1
                        row_tokens = data['total_tokens']
                        total += row_tokens
                        
                        # Extract first 30 tokens of content from the first message with content
                        content_preview = ""
                        if 'messages' in data and isinstance(data['messages'], list):
                            for msg in data['messages']:
                                if isinstance(msg, dict) and 'content' in msg and msg['content']:
                                    content_str = str(msg['content'])
                                    # Get first 100 characters as approximation for 30 tokens
                                    content_preview = content_str[:100]
                                    if len(content_str) > 100:
                                        content_preview += "..."
                                    break
                        
                        # Print row information
                        print(f"Row {line_count}:")
                        print(f"  Content preview: {content_preview}")
                        print(f"  Row tokens: {row_tokens:,}")
                        print(f"  Running total: {total:,}")
                        print()
                        
                except json.JSONDecodeError as e:
                    print(f"Warning: Failed to parse line {line_count + 1}: {e}")
                    continue
        
        print(f"{'='*80}")
        print(f"Successfully processed {line_count} lines")
        print(f"Total tokens: {total:,}")
        print(f"{'='*80}")
        return total
        
    except FileNotFoundError:
        print(f"Error: File not found: {jsonl_file_path}")
        return None
    except Exception as e:
        print(f"Error: {e}")
        return None


if __name__ == "__main__":
    # Path to the JSONL file
    jsonl_file = "logs/llm_messages.jsonl"
    # jsonl_file = "logs/origin_llm_messages.jsonl"
    
    total_tokens = calculate_total_tokens(jsonl_file)
    
    if total_tokens is not None:
        print(f"\n{'='*50}")
        print(f"TOTAL TOKENS: {total_tokens:,}")
        print(f"{'='*50}")

