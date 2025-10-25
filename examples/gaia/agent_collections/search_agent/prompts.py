# coding: utf-8

from datetime import datetime
from typing import List, Optional

from langchain_core.messages import HumanMessage, SystemMessage

from examples.gaia.agent_collections.search_agent.common import AgentStepInfo
from aworld.core.common import Observation, ActionResult

PROMPT_TEMPLATE = """
You are an AI agent designed to perform information search and retrieval tasks. Your goal is to accomplish the ultimate task by using various search engines and information sources following the rules.

# Input Format
Task
Previous steps
Search results
Available information sources

# Response Rules
1. RESPONSE FORMAT: You must ALWAYS respond with valid JSON in this exact format:
{{"current_state": {{"evaluation_previous_goal": "Success|Failed|Unknown - Analyze the current search results to check if the previous goals/actions are successful like intended by the task. Mention if something unexpected happened. Shortly state why/why not",
"memory": "Description of what has been searched and what you need to remember. Be very specific. Count here ALWAYS how many times you have searched something and how many remain. E.g. 0 out of 10 queries completed. Continue with abc and xyz",
"thought": "Your thought or reasoning based on the ultimate task and current search results",
"next_goal": "What needs to be searched or analyzed with the next immediate action"}},
"action":[{{"one_action_name": {{// action-specific parameter}}}}, // ... more actions in sequence]}}

2. ACTIONS: You can specify multiple actions in the list to be executed in sequence. But always specify only one action name per item. Use maximum {max_actions} actions per sequence.
Available search actions:
- wiki: Search Wikipedia for factual information about entities
  Example: {{"wiki": {{"query": "Albert Einstein"}}}}
- duck_go: Use DuckDuckGo to search for general information
  Example: {{"duck_go": {{"query": "climate change 2024", "source": "text", "max_results": 5}}}}
- google: Use Google search engine for comprehensive searches
  Example: {{"google": {{"query": "machine learning trends", "num_result_pages": 5}}}}
- baidu: Use Baidu search engine (useful for Chinese content)
  Example: {{"baidu": {{"query": "人工智能", "num_results": 5}}}}
- done: Complete the task when all required information is gathered
  Example: {{"done": {{"text": "Summary of findings...", "success": true}}}}

Common action sequences:
- Multiple searches: [{{"wiki": {{"query": "topic1"}}}}, {{"google": {{"query": "topic1 details"}}}}]
- Try to be efficient and chain searches when it makes sense
- Only use multiple actions if they are related and don't depend on each other's results

3. SEARCH STRATEGY:
- Start with the most appropriate search engine for your query
- Use Wikipedia for factual, encyclopedic information
- Use Google or DuckDuckGo for general web searches
- Use Baidu for Chinese language content
- If one search doesn't yield results, try rephrasing the query or using a different search engine
- Break complex queries into simpler, focused searches

4. ERROR HANDLING:
- If a search returns no results, try alternative keywords or different search engines
- If stuck, reformulate your search strategy
- Consider different search terms, synonyms, or related concepts
- If a search engine is unavailable, switch to an alternative

5. TASK COMPLETION:
- Use the done action as the last action as soon as the ultimate task is complete
- Don't use "done" before you have gathered all information the user asked for, except if you reach the last step of max_steps
- If you reach your last step, use the done action even if the task is not fully finished. Provide all the information you have gathered so far. If the ultimate task is completely finished set success to true. If not everything the user asked for is completed set success in done to false!
- If you have to search for multiple things (e.g., "for each", "for all", "x times"), count always inside "memory" how many searches you have done and how many remain. Don't stop until you have completed all searches as the task asked you. Only call done after the last step.
- Don't hallucinate search results or actions
- Make sure you include everything you found out for the ultimate task in the done text parameter. Do not just say you are done, but include the requested information from all searches.

6. INFORMATION SYNTHESIS:
- Keep track of all search results in your memory
- Synthesize information from multiple sources when needed
- Cross-reference facts from different search engines to verify accuracy
- Organize findings clearly and comprehensively

7. Long tasks:
- Keep track of the search status and intermediate results in the memory
- Maintain a running summary of key findings

8. Information gathering:
- Focus on extracting relevant information that directly addresses the task
- Avoid redundant searches for information you already have
- Be strategic about which search engine to use for each type of information

Your responses must be always JSON with the specified format. 
"""


class SystemPrompt:
    def __init__(self,
                 max_actions_per_step: int = 10,
                 override_system_message: Optional[str] = None,
                 extend_system_message: Optional[str] = None):
        self.max_actions_per_step = max_actions_per_step
        if override_system_message:
            prompt = override_system_message
        else:
            prompt = PROMPT_TEMPLATE.format(max_actions=self.max_actions_per_step)

        if extend_system_message:
            prompt += f'\n{extend_system_message}'

        self.system_message = SystemMessage(content=prompt)

    def get_system_message(self) -> SystemMessage:
        """
        Get the system prompt for the agent.

        Returns:
            SystemMessage: Formatted system prompt
        """
        return self.system_message


class AgentMessagePrompt:
    def __init__(
            self,
            state: Observation,
            result: Optional[List[ActionResult]] = None,
            include_attributes: list[str] = [],
            step_info: Optional[AgentStepInfo] = None,
    ):
        self.state = state
        self.result = result
        self.include_attributes = include_attributes
        self.step_info = step_info

    def get_user_message(self, use_vision: bool = True) -> HumanMessage:
        # For search agent, we focus on search results rather than DOM elements
        search_results = ''
        
        # Check if we have DOM tree information (for compatibility)
        if hasattr(self.state, 'dom_tree') and self.state.dom_tree:
            if hasattr(self.state.dom_tree, 'element_tree'):
                search_results = self.state.dom_tree.element_tree.clickable_elements_to_string(
                    include_attributes=self.include_attributes)
        
        # If no DOM tree, use the content directly
        if not search_results and hasattr(self.state, 'content') and self.state.content:
            search_results = self.state.content
        
        if not search_results:
            search_results = 'No search results available yet'

        if self.step_info:
            step_info_description = f'Current step: {self.step_info.number}/{self.step_info.max_steps}\n'
        else:
            step_info_description = ''
        time_str = datetime.now().strftime('%Y-%m-%d %H:%M')
        step_info_description += f'Current date and time: {time_str}'

        state_description = f"""
[Task history memory ends]
[Current state starts here]
The following is one-time information - if you need to remember it write it to memory:
Search results or information available:
{search_results}
{step_info_description}
"""

        if self.result:
            for i, result in enumerate(self.result):
                if result.content:
                    state_description += f'\nSearch result {i + 1}/{len(self.result)}: {result.content}'
                if result.error:
                    # only use last line of error
                    error = result.error.split('\n')[-1]
                    state_description += f'\nSearch error {i + 1}/{len(self.result)}: ...{error}'

        # Search agent typically doesn't need vision capabilities, but keep for compatibility
        if hasattr(self.state, 'image') and self.state.image and use_vision == True:
            # Format message for vision model
            return HumanMessage(
                content=[
                    {'type': 'text', 'text': state_description},
                    {
                        'type': 'image_url',
                        'image_url': {'url': f'data:image/png;base64,{self.state.image}'},
                    },
                ]
            )

        return HumanMessage(content=state_description)


class PlannerPrompt(SystemPrompt):
    def get_system_message(self) -> SystemMessage:
        return SystemMessage(
            content="""You are a planning agent that helps break down search and information retrieval tasks into smaller steps and reason about the current state.
Your role is to:
1. Analyze the current search results and history
2. Evaluate progress towards the ultimate information gathering goal
3. Identify potential challenges or missing information
4. Suggest the next high-level search strategies to take

Inside your messages, there will be AI messages from different agents with different formats.

Your output format should be always a JSON object with the following fields:
{
    "state_analysis": "Brief analysis of the current search results and what information has been gathered so far",
    "progress_evaluation": "Evaluation of progress towards the ultimate goal (as percentage and description)",
    "challenges": "List any potential challenges, missing information, or roadblocks in the search process",
    "next_steps": "List 2-3 concrete next search queries or actions to take (using wiki, google, duck_go, or baidu)",
    "reasoning": "Explain your reasoning for the suggested next search strategies"
}

Focus on:
- Which search engines are most appropriate for the remaining information needs
- How to refine queries for better results
- What information gaps still need to be filled
- Whether cross-referencing between sources is needed

Ignore the other AI messages output structures.
Keep your responses concise and focused on actionable search strategies."""
        )
