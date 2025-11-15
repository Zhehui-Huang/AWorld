import os
import time
import traceback
from typing import Literal

from dotenv import load_dotenv
from pydantic import Field
from pydantic.fields import FieldInfo

from aworld.config.conf import AgentConfig
from aworld.logs.util import Color
from aworld.models.llm import call_llm_model, get_llm_model
from examples.gaia.mcp_collections.base import ActionArguments, ActionCollection, ActionResponse


class ThinkCollection(ActionCollection):
    """MCP service for complex problem reasoning using powerful reasoning models.

    Supports advanced reasoning for:
    - Mathematical problems and proofs
    - Code contest and programming challenges
    - Logic puzzles and riddles
    - Competition-level STEM problems
    - Multi-step analytical reasoning
    """

    def __init__(self, arguments: ActionArguments) -> None:
        super().__init__(arguments)

        # Initialize reasoning model configuration
        self._llm_config = AgentConfig(
            llm_provider="openai",
            llm_model_name=os.getenv("THINK_LLM_MODEL_NAME"),
            llm_api_key=os.getenv("THINK_LLM_API_KEY"),
            llm_base_url=os.getenv("THINK_LLM_BASE_URL"),
        )

        self._color_log("Intelligence Reasoning Service initialized", Color.green, "debug")
        self._color_log(f"Using model: {self._llm_config.llm_model_name}", Color.blue, "debug")

    def _prepare_reasoning_prompt(self, question: str, original_task: str = "") -> str:
        """Prepare the reasoning prompt with question and optional context.

        Args:
            question: The main question for reasoning
            original_task: Optional original task description for context

        Returns:
            Formatted prompt string
        """
        if original_task:
            return f"Original Task: {original_task}\n\nQuestion: {question}"
        return f"Question: {question}"

    def _call_reasoning_model(self, prompt: str) -> str:
        """Call the reasoning model with the prepared prompt.

        Args:
            prompt: The formatted prompt for reasoning

        Returns:
            Reasoning result from the model

        Raises:
            Exception: If model call fails
        """
        response = call_llm_model(
            llm_model=get_llm_model(conf=self._llm_config),
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are an expert at solving complex problems including math, "
                        "code contests, riddles, and puzzles. "
                        "Provide detailed step-by-step reasoning and a clear final answer."
                    ),
                },
                {"role": "user", "content": prompt},
            ]
        )

        return response.content

    def mcp_complex_problem_reasoning(
        self,
        question: str = Field(
            description="The input question for complex problem reasoning, such as math and code contest problems"
        ),
        original_task: str = Field(default="", description="The original task description."),
        reasoning_style: Literal["detailed", "concise", "step-by-step"] = Field(
            default="detailed",
            description="Style of reasoning output: detailed analysis, concise summary, or step-by-step breakdown",
        ),
    ) -> ActionResponse:
        """This tool provides comprehensive reasoning capabilities for:
        - Mathematical problems and proofs
        - Programming and algorithm challenges
        - Logic puzzles, brain teasers, and fun riddles
        - Competition-level STEM problems
        - Multi-step analytical reasoning tasks

        Weakness:
        - Inability to process media types: image, audio, or video
        - Require precise description of problem context and settings

        Args:
            question: The input question requiring complex reasoning
            original_task: Optional original task description for additional context
            reasoning_style: Style of reasoning output format

        Returns:
            ActionResponse with reasoning result and processing metadata
        """
        try:
            # Handle FieldInfo objects
            if isinstance(question, FieldInfo):
                question = question.default
            if isinstance(original_task, FieldInfo):
                original_task = original_task.default
            if isinstance(reasoning_style, FieldInfo):
                reasoning_style = reasoning_style.default

            # Validate input
            if not question or not question.strip():
                raise ValueError("Question is required for complex problem reasoning")

            self._color_log(f"Processing reasoning request: {question[:100]}...", Color.cyan)

            start_time = time.time()

            # Prepare the reasoning prompt
            prompt = self._prepare_reasoning_prompt(question, original_task)

            # Enhance prompt based on reasoning style
            if reasoning_style == "step-by-step":
                prompt += "\n\nPlease provide a clear step-by-step breakdown of your reasoning process."
            elif reasoning_style == "concise":
                prompt += "\n\nPlease provide a concise but complete reasoning and final answer."
            elif reasoning_style == "detailed":
                prompt += "\n\nPlease provide detailed analysis with comprehensive reasoning."

            # Call the reasoning model
            reasoning_result = self._call_reasoning_model(prompt)

            processing_time = time.time() - start_time

            self._color_log(
                f"Successfully completed reasoning ({len(reasoning_result)} characters, {processing_time:.2f}s)",
                Color.green,
            )

            return ActionResponse(success=True, message=reasoning_result, metadata={})

        except ValueError as e:
            self.logger.error(f"Invalid input: {str(e)}")
            return ActionResponse(
                success=False,
                message=f"Invalid input: {str(e)}",
                metadata={"error_type": "invalid_input", "error_message": str(e)},
            )
        except Exception as e:
            self.logger.error(f"Reasoning failed: {str(e)}: {traceback.format_exc()}")
            return ActionResponse(
                success=False,
                message=f"Reasoning failed: {str(e)}",
                metadata={"error_type": "reasoning_error", "error_message": str(e)},
            )

# Example usage and entry point
if __name__ == "__main__":
    load_dotenv()

    # Default arguments for testing
    args = ActionArguments(
        name="intelligence_reasoning_service",
        transport="stdio",
        workspace=os.getenv("AWORLD_WORKSPACE", "~"),
    )

    # Initialize and run the intelligence reasoning service
    try:
        service = ThinkCollection(args)
        service.run()
    except Exception as e:
        print(f"An error occurred: {e}: {traceback.format_exc()}")
