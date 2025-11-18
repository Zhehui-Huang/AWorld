"""
Trajectory Analyzer - Utilities for analyzing and consolidating agent trajectories

This module provides tools to:
1. Load and analyze individual agent trajectory files
2. Build hierarchical agent execution trees
3. Consolidate trajectories for training/analysis
4. Generate statistics and visualizations
"""

import json
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from collections import defaultdict
from datetime import datetime


class TrajectoryAnalyzer:
    """Analyze and consolidate agent trajectory files."""
    
    def __init__(self, trajectories_dir: str = "logs/trajectories"):
        """
        Initialize the analyzer.
        
        Args:
            trajectories_dir: Directory containing agent trajectory files
        """
        self.trajectories_dir = Path(trajectories_dir)
        # trajectories organized by agent_id
        self.trajectories: Dict[str, List[dict]] = {}
        # agent_metadata by agent_id
        self.agent_metadata: Dict[str, dict] = {}
        # hierarchy: parent_id -> [child_ids]
        self.hierarchy: Dict[str, List[str]] = defaultdict(list)
        # type_trajectories: agent_type -> [all conversations]
        self.type_trajectories: Dict[str, List[dict]] = defaultdict(list)
        
    def load_all_trajectories(self) -> None:
        """Load all trajectory files from the directory."""
        if not self.trajectories_dir.exists():
            print(f"Trajectories directory not found: {self.trajectories_dir}")
            return
            
        for traj_file in self.trajectories_dir.glob("*.jsonl"):
            agent_type = traj_file.stem
            conversations = self._load_trajectory_file(traj_file)
            self.type_trajectories[agent_type] = conversations
            
            # Group conversations by agent_id
            for conv in conversations:
                agent_id = conv.get("agent_id")
                if not agent_id:
                    continue
                    
                if agent_id not in self.trajectories:
                    self.trajectories[agent_id] = []
                self.trajectories[agent_id].append(conv)
                
                # Extract metadata (update if needed)
                if agent_id not in self.agent_metadata:
                    self.agent_metadata[agent_id] = {
                        "agent_name": conv.get("agent_name"),
                        "agent_type": conv.get("agent_type"),
                        "parent_agent_id": conv.get("parent_agent_id"),
                        "orchestration_level": conv.get("orchestration_level", 0),
                    }
            
            # Update conversation counts
            for agent_id in self.trajectories:
                self.agent_metadata[agent_id]["conversation_count"] = len(self.trajectories[agent_id])
                
                # Build hierarchy
                parent_id = self.agent_metadata[agent_id].get("parent_agent_id")
                if parent_id and agent_id not in self.hierarchy[parent_id]:
                    self.hierarchy[parent_id].append(agent_id)
    
    def _load_trajectory_file(self, file_path: Path) -> List[dict]:
        """Load conversations from a single trajectory file."""
        conversations = []
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                for line in f:
                    if line.strip():
                        conversations.append(json.loads(line))
        except Exception as e:
            print(f"Error loading {file_path}: {e}")
        return conversations
    
    def print_summary(self) -> None:
        """Print a summary of all loaded trajectories."""
        print("\n" + "=" * 80)
        print("TRAJECTORY SUMMARY")
        print("=" * 80)
        
        print(f"\nTotal Agent Instances: {len(self.trajectories)}")
        print(f"Agent Types (Files): {len(self.type_trajectories)}")
        print(f"Trajectories Directory: {self.trajectories_dir.absolute()}")
        
        # Show files and their sizes
        print("\nMain Trajectory Files (Agent Conversations):")
        main_files = []
        separate_llm_files = []
        
        for agent_type, conversations in sorted(self.type_trajectories.items()):
            if "_" in agent_type and any(purpose in agent_type for purpose in ["summarization", "condensation", "image_analysis", "memory_analysis"]):
                # This is a separate LLM file
                separate_llm_files.append((agent_type, conversations))
            else:
                # Main agent conversation file
                main_files.append((agent_type, conversations))
        
        for agent_type, conversations in main_files:
            unique_agents = len(set(c.get("agent_id") for c in conversations if c.get("agent_id")))
            if unique_agents > 0:
                print(f"  {agent_type}.jsonl: {len(conversations)} conversations from {unique_agents} agents")
            else:
                print(f"  {agent_type}.jsonl: {len(conversations)} conversations")
        
        if separate_llm_files:
            print("\nSeparate LLM Call Files:")
            for agent_type, conversations in separate_llm_files:
                print(f"  {agent_type}.jsonl: {len(conversations)} calls")
        
        # Group by agent type
        by_type = defaultdict(list)
        for agent_id, metadata in self.agent_metadata.items():
            agent_type = metadata.get("agent_type", "unknown")
            by_type[agent_type].append(agent_id)
        
        print("\nAgent Instances by Type:")
        for agent_type, agent_ids in sorted(by_type.items()):
            print(f"  {agent_type}: {len(agent_ids)} instances")
        
        # Calculate total statistics
        total_conversations = sum(len(convs) for convs in self.trajectories.values())
        total_tokens = 0
        total_messages = 0
        
        for conversations in self.trajectories.values():
            for conv in conversations:
                total_tokens += conv.get("total_tokens", 0)
                total_messages += conv.get("message_count", 0)
        
        print(f"\nTotal Conversations: {total_conversations}")
        print(f"Total Messages: {total_messages}")
        print(f"Total Tokens (estimated): {total_tokens:,}")
        
    def print_agent_details(self, agent_id: Optional[str] = None) -> None:
        """
        Print detailed information about a specific agent or all agents.
        
        Args:
            agent_id: Specific agent ID, or None to show all agents
        """
        print("\n" + "=" * 80)
        print("AGENT DETAILS")
        print("=" * 80)
        
        agent_ids = [agent_id] if agent_id else sorted(self.trajectories.keys())
        
        for aid in agent_ids:
            if aid not in self.trajectories:
                print(f"\n❌ Agent '{aid}' not found")
                continue
                
            metadata = self.agent_metadata.get(aid, {})
            conversations = self.trajectories[aid]
            
            print(f"\n{'─' * 80}")
            print(f"Agent ID: {aid}")
            print(f"Name: {metadata.get('agent_name', 'N/A')}")
            print(f"Type: {metadata.get('agent_type', 'N/A')}")
            print(f"Orchestration Level: {metadata.get('orchestration_level', 0)}")
            print(f"Parent Agent: {metadata.get('parent_agent_id', 'None (root)')}")
            
            # Child agents
            children = self.hierarchy.get(aid, [])
            if children:
                print(f"Child Agents: {len(children)}")
                for child_id in children:
                    child_meta = self.agent_metadata.get(child_id, {})
                    print(f"  - {child_id} ({child_meta.get('agent_type', 'unknown')})")
            
            # Conversation statistics
            print(f"\nConversations: {len(conversations)}")
            for i, conv in enumerate(conversations, 1):
                timestamp = conv.get("timestamp", "N/A")
                tokens = conv.get("total_tokens", 0)
                msg_count = conv.get("message_count", 0)
                conv_num = conv.get("conversation_number", i)
                print(f"  [{conv_num}] {timestamp[:19]} - {msg_count} messages, ~{tokens} tokens")
            
            # Token statistics
            total_tokens = sum(conv.get("total_tokens", 0) for conv in conversations)
            total_messages = sum(conv.get("message_count", 0) for conv in conversations)
            print(f"\nTotal: {total_messages} messages, ~{total_tokens:,} tokens")
    
    def print_hierarchy_tree(self, root_id: Optional[str] = None, indent: int = 0) -> None:
        """
        Print the agent hierarchy as a tree.
        
        Args:
            root_id: Root agent ID to start from, or None to show all roots
            indent: Current indentation level (for recursion)
        """
        if indent == 0:
            print("\n" + "=" * 80)
            print("AGENT HIERARCHY")
            print("=" * 80 + "\n")
        
        # Find root agents (those without parents)
        if root_id is None:
            root_agents = [
                aid for aid, meta in self.agent_metadata.items()
                if not meta.get("parent_agent_id")
            ]
            for root in sorted(root_agents):
                self.print_hierarchy_tree(root, 0)
            return
        
        # Print current agent
        metadata = self.agent_metadata.get(root_id, {})
        conversations = self.trajectories.get(root_id, [])
        
        prefix = "  " * indent + ("└─ " if indent > 0 else "")
        agent_name = metadata.get("agent_name", "unknown")
        agent_type = metadata.get("agent_type", "unknown")
        conv_count = len(conversations)
        
        print(f"{prefix}{root_id}")
        print(f"{' ' * len(prefix)}  ├─ Type: {agent_type}")
        print(f"{' ' * len(prefix)}  ├─ Name: {agent_name}")
        print(f"{' ' * len(prefix)}  └─ Conversations: {conv_count}")
        print()
        
        # Recursively print children
        children = self.hierarchy.get(root_id, [])
        for child_id in sorted(children):
            self.print_hierarchy_tree(child_id, indent + 1)
    
    def export_consolidated_dataset(self, output_file: str = "consolidated_trajectories.jsonl") -> None:
        """
        Export all trajectories as a consolidated JSONL file for training.
        
        Args:
            output_file: Output file path
        """
        output_path = Path(output_file)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        total_records = 0
        with open(output_path, "w", encoding="utf-8") as f:
            for agent_id, conversations in sorted(self.trajectories.items()):
                for conv in conversations:
                    # Write each conversation as a separate line
                    json.dump(conv, f, ensure_ascii=False)
                    f.write("\n")
                    total_records += 1
        
        print(f"\n✅ Exported {total_records} conversation records to {output_path}")
        print(f"   From {len(self.trajectories)} agent instances ({len(self.type_trajectories)} types)")
    
    def export_training_format(
        self, 
        output_file: str = "training_data.jsonl",
        format_type: str = "openai",
        agent_type_filter: Optional[str] = None
    ) -> None:
        """
        Export trajectories in a format suitable for fine-tuning.
        
        Args:
            output_file: Output file path
            format_type: Format type ("openai" for OpenAI fine-tuning)
            agent_type_filter: Only export this agent type (e.g., "search_agent"), None for all
        """
        output_path = Path(output_file)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        total_records = 0
        with open(output_path, "w", encoding="utf-8") as f:
            for agent_id, conversations in sorted(self.trajectories.items()):
                metadata = self.agent_metadata.get(agent_id, {})
                
                # Filter by agent type if specified
                if agent_type_filter and metadata.get("agent_type") != agent_type_filter:
                    continue
                
                for conv in conversations:
                    if format_type == "openai":
                        # OpenAI fine-tuning format
                        record = {
                            "messages": conv.get("messages", []),
                            "metadata": {
                                "agent_id": agent_id,
                                "agent_type": metadata.get("agent_type"),
                                "agent_name": metadata.get("agent_name"),
                                "conversation_id": conv.get("conversation_id"),
                                "timestamp": conv.get("timestamp"),
                            }
                        }
                    else:
                        # Keep original format
                        record = conv
                    
                    json.dump(record, f, ensure_ascii=False)
                    f.write("\n")
                    total_records += 1
        
        filter_msg = f" (filtered to {agent_type_filter})" if agent_type_filter else ""
        print(f"\n✅ Exported {total_records} training records to {output_path}{filter_msg}")
        print(f"   Format: {format_type}")


def main():
    """Main function for command-line usage."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Analyze agent trajectory files")
    parser.add_argument(
        "--trajectories-dir",
        default="logs/trajectories",
        help="Directory containing trajectory files"
    )
    parser.add_argument(
        "--agent-id",
        help="Show details for a specific agent ID"
    )
    parser.add_argument(
        "--export",
        help="Export consolidated trajectories to file"
    )
    parser.add_argument(
        "--export-training",
        help="Export in training format (OpenAI fine-tuning)"
    )
    parser.add_argument(
        "--filter-type",
        help="Filter by agent type when exporting (e.g., search_agent, file_agent)"
    )
    
    args = parser.parse_args()
    
    # Initialize analyzer
    analyzer = TrajectoryAnalyzer(args.trajectories_dir)
    analyzer.load_all_trajectories()
    
    if not analyzer.trajectories:
        print(f"⚠️  No trajectories found in {args.trajectories_dir}")
        return
    
    # Print summary
    analyzer.print_summary()
    
    # Print hierarchy
    analyzer.print_hierarchy_tree()
    
    # Print agent details
    analyzer.print_agent_details(args.agent_id)
    
    # Export if requested
    if args.export:
        analyzer.export_consolidated_dataset(args.export)
    
    if args.export_training:
        analyzer.export_training_format(args.export_training, agent_type_filter=args.filter_type)


if __name__ == "__main__":
    main()

