"""
Simple example showing how to use the trajectory analyzer.

Trajectories are organized in Qwen3-compatible format:

Main agent conversations (by agent type):
- logs/trajectories/main_agent.jsonl
- logs/trajectories/search_agent.jsonl  
- logs/trajectories/file_agent.jsonl
- logs/trajectories/orchestrator_agent.jsonl

Separate LLM calls (by agent_type_agent_id_purpose):
- logs/trajectories/file_agent_{agent_id}_pdf_summarization.jsonl
- logs/trajectories/file_agent_{agent_id}_pdf_condensation.jsonl
- logs/trajectories/file_agent_image_analysis_image_analysis.jsonl
- logs/trajectories/{agent_type}_{agent_id}_memory_analysis.jsonl

Each file contains Qwen3 format:
{"messages": [{"role": "user", "content": "..."}, {"role": "assistant", "content": "..."}]}

Usage:
    python examples/gaia/agent_collections/example_trajectory_usage.py
"""

from trajectory_analyzer import TrajectoryAnalyzer

def main():
    # Create analyzer
    analyzer = TrajectoryAnalyzer("logs/trajectories")
    
    # Load all trajectories
    analyzer.load_all_trajectories()
    
    if not analyzer.trajectories:
        print("No trajectories found. Run your multi-agent workflow first.")
        return
    
    # Print summary (shows files per agent type)
    analyzer.print_summary()
    
    # Print hierarchy (shows relationships between agent instances)
    analyzer.print_hierarchy_tree()
    
    # Print details for all agent instances
    analyzer.print_agent_details()
    
    # Export consolidated dataset (all agents)
    analyzer.export_consolidated_dataset("consolidated_trajectories.jsonl")
    
    # Export in training format (all agents)
    analyzer.export_training_format("training_data_all.jsonl", format_type="openai")
    
    # Export only search agents for specialized training
    analyzer.export_training_format(
        "training_data_search.jsonl", 
        format_type="openai",
        agent_type_filter="Agent"  # Adjust based on actual agent type name
    )
    
    print("\n" + "=" * 80)
    print("Example commands:")
    print("  # View only search agents")
    print("  python trajectory_analyzer.py --filter-type Agent")
    print()
    print("  # Export only file agents")
    print("  python trajectory_analyzer.py --export-training file_agents.jsonl --filter-type file_agent")
    print("=" * 80)

if __name__ == "__main__":
    main()

