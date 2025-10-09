import asyncio
import logging
import json
import os
import re
import time

import traceback
from pathlib import Path
from typing import Union

from playwright.async_api import async_playwright
from pydantic import BaseModel, Field
from browser_use import Agent, AgentHistoryList, BrowserProfile, BrowserSession
from browser_use.llm import ChatOpenAI
from dotenv import load_dotenv
from mcp.server import FastMCP
from mcp.types import TextContent
from mcp.server.fastmcp import Context

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)

workspace = "/home/ethan/repo/AWorld/tmp/browser"
logs_path = workspace + "/logs"
logs_path.mkdir(parents=True, exist_ok=True)
trace_log_dir = str(logs_path) + "/browser_log"

extended_browser_system_prompt = """
# 效率指南
0. 如果有下载选项，尽可能**下载**！下载根目录必须在在~/wokspace目录下面，可以根据场景适当的创建文件夹来存放下载的文件，同时，在结果中报告要包含存放文件的完整路径。
1. 使用包含任务关键词的特定搜索查询
2. 避免被无关信息分散注意力
3. 如果被付费墙阻挡，尝试使用archive.org或类似替代方案
4. 清晰简洁地记录每个重要发现
5. 以最少的浏览步骤精确提取必要信息。
6. ***重要****如果操作浏览器过程中出现需要人工干预的过程，比如：登录、验证码输入、输入密码、支付等操作，就不能继续往下操作，需要返回习惯人工干预的提示信息从而等待人工干预之后继续操作(但需要保持当前操作浏览器窗口)
样例：
1、遇到登录页面
    返回：当前操作需要用户进行登录，请你在页面上进行相关登录操作，之后继续执行
2、遇到输入验证码页面
    返回：当前操作需要用户进行输入验证码，请你在页面上进行输入验证码，之后继续执行
3、遇到输入密码页面
    返回：当前操作需要用户进行输入密码，请你在页面上进行输入密码操作，之后继续执行
4、遇到支付页面
    返回：当前操作需要用户进行支付，请你在页面上进行相关支付操作，之后继续执行
"""

# Initialize LLM configuration
llm_config = ChatOpenAI(
    model=os.getenv("LLM_MODEL_NAME"),
    api_key=os.getenv("LLM_API_KEY"),
    base_url=os.getenv("LLM_BASE_URL"),
    temperature=1.0,
)

browser_profile = BrowserProfile(
    cookies_file=os.getenv("COOKIES_FILE_PATH"),
    downloads_dir=workspace,
    downloads_path=workspace,
    save_recording_path=workspace,
    save_downloads_path=workspace,
    chromium_sandbox=False,
    headless=False,
    keep_alive=True,
)

from base import ActionResponse


class BrowserMetadata(BaseModel):
    """Metadata for browser automation results."""

    task: str
    execution_successful: bool
    steps_taken: int | None = None
    downloaded_files: list[str] = Field(default_factory=list)
    visited_urls: list[str] = Field(default_factory=list)
    execution_time: float | None = None
    error_type: str | None = None
    trace_log_path: str | None = None


browser_session = BrowserSession(
    browser_profile=browser_profile
)

mcp = FastMCP("browser-server")


async def show_vnc_window(
    ctx: Context,
):
    """Show the VNC window"""
    await ctx.report_progress(
        progress=0.0,
        total=1.0,
        message="tool_call_card_novnc_window",
    )


def _extract_visited_urls(extracted_content: list[str]) -> list[str]:
    """Inner method to extract URLs from content using regex.

    Args:
        content_list: List of content strings to search for URLs

    Returns:
        List of unique URLs found in the content
    """
    url_pattern = r'https?://[^\s<>"\[\]{}|\\^`]+'
    visited_urls = set()

    for content in extracted_content:
        if content and isinstance(content, str):
            urls = re.findall(url_pattern, content)
            visited_urls.update(urls)

    return list(visited_urls)


def _format_extracted_content(extracted_content: list[str]) -> str:
    """Format extracted content to be LLM-friendly.

    Args:
        extracted_content: List of extracted content strings from browser execution

    Returns:
        Formatted string suitable for LLM consumption
    """
    if not extracted_content:
        return "No content extracted from browser execution."

    # Handle list of strings
    if len(extracted_content) == 1:
        # Single item - return it directly with formatting
        return f"**Extracted Content:**\n{extracted_content[0]}"
    else:
        # Multiple items - format as numbered list
        formatted_parts = ["**Extracted Content:**"]
        for i, content in enumerate(extracted_content, 1):
            if content.strip():  # Only include non-empty content
                formatted_parts.append(f"{i}. {content}")

        return (
            "\n".join(formatted_parts)
            if len(formatted_parts) > 1
            else "No meaningful content extracted from browser execution."
        )


async def _create_browser_agent(task: str) -> Agent:
    """Create a browser agent instance with configured settings.

    Args:
        task: The task description for the browser agent

    Returns:
        Configured Agent instance
    """
    playwright = await async_playwright().start()
    ws_remote_url: str = f"ws://localhost:37367/default"
    browser = await playwright.chromium.connect(ws_endpoint=ws_remote_url)
    return Agent(
        task=task,
        llm=llm_config,
        extend_system_message=extended_browser_system_prompt,
        use_vision=True,
        enable_memory=False,
        browser=browser,
        #browser_profile=browser_profile,
        browser_session=browser_session,
        save_conversation_path=trace_log_dir + "/browser_log/trace.log",
    )


@mcp.tool(
    description="""
    Get information about browser automation capabilities and configuration.
    """
)
async def get_browser_capabilities() -> Union[str, TextContent]:
    """Get information about browser automation capabilities and configuration.

    Returns:
        ActionResponse with browser service capabilities and current configuration
    """
    capabilities = {
        "automation_features": [
            "Web scraping and content extraction",
            "Form submission and interaction",
            "File downloads and media handling",
            "LLM-enhanced browsing with vision",
            "Memory-enabled browsing sessions",
            "Robot detection and paywall handling",
        ],
        "supported_formats": ["markdown", "json", "text"],
        "configuration": {
            "llm_model": os.getenv("LLM_MODEL_NAME", "Not configured"),
            "downloads_directory": browser_profile.downloads_path,
            "cookies_enabled": bool(os.getenv("COOKIES_FILE_PATH")),
            "trace_logging": True,
            "vision_enabled": True,
            "headless": False,
        },
    }

    formatted_info = f"""# Browser Automation Service Capabilities

    ## Features
    {chr(10).join(f"- {feature}" for feature in capabilities["automation_features"])}

    ## Supported Output Formats
    {chr(10).join(f"- {fmt}" for fmt in capabilities["supported_formats"])}

    ## Current Configuration
    - **LLM Model:** {capabilities["configuration"]["llm_model"]}
    - **Downloads Directory:** {capabilities["configuration"]["downloads_directory"]}
    - **Cookies Enabled:** {capabilities["configuration"]["cookies_enabled"]}
    - **Vision Enabled:** {capabilities["configuration"]["vision_enabled"]}
    - **Memory Enabled:** {capabilities["configuration"]["memory_enabled"]}
    - **Trace Logging:** {capabilities["configuration"]["trace_logging"]}
    """

    action_response = ActionResponse(
        success=True, message=formatted_info, metadata=capabilities
    )
    return TextContent(
        type="text",
        text=json.dumps(action_response.model_dump()),  # Empty string instead of None
        **{"metadata": {}},  # Pass as additional fields
    )


@mcp.tool(
    description="""
    Perform browser automation tasks using the browser-use package.

        This tool provides comprehensive browser automation capabilities including:
        - Web scraping and content extraction
        - Form submission and automated interactions
        - File downloads and media handling
        - LLM-enhanced browsing with memory and vision
        - Automatic handling of robot detection and paywalls
    """
)
async def browser_use(
    context: Context,
    task: str = Field(
        description="The task to perform using the browser automation agent"
    ),
    max_steps: int = Field(
        default=50, description="Maximum number of steps for browser execution"
    ),
    extract_format: str = Field(
        default="markdown",
        description="Format for extracted content: 'markdown', 'json', or 'text'",
    ),
) -> Union[str, TextContent]:
    try:
        logging.info(f"🎯 Starting browser task: {task}")

        # Create browser agent
        agent = await _create_browser_agent(task)

        start_time = time.time()

        await show_vnc_window(context)

        browser_execution: AgentHistoryList = await agent.run(max_steps=max_steps)

        execution_time = time.time() - start_time
        result_content = ""

        if browser_execution is not None and hasattr(browser_execution, 'history') and browser_execution.history is not None:
            latest_history = browser_execution.history[-1]
            if latest_history is not None and hasattr(latest_history, 'result') and latest_history.result is not None:
                first_result = latest_history.result[0]
                if first_result is not None and hasattr(first_result, 'extracted_content'):
                    result_content = first_result.extracted_content

        if result_content:
            return TextContent(
                type="text",
                text=result_content,  # Empty string instead of None
                **{"metadata": {}},  # Pass as additional fields
            )

        else:
            # Handle execution failure
            error_msg = "Browser execution failed or was not completed successfully"

            metadata = BrowserMetadata(
                task=task,
                execution_successful=False,
                execution_time=execution_time,
                error_type="execution_failure",
                trace_log_path=trace_log_dir + "/trace.log",
            )

            logging.info(f"❌ {error_msg}")

            action_response = ActionResponse(
                success=False, message=error_msg, metadata=metadata.model_dump()
            )
            return TextContent(
                type="text",
                text=json.dumps(
                    action_response.model_dump()
                ),  # Empty string instead of None
                **{"metadata": {}},  # Pass as additional fields
            )

        # if (
        #     browser_execution is not None
        #     and browser_execution.is_done()
        #     and browser_execution.is_successful()
        # ):
        #     # Extract and format content
        #     extracted_content = browser_execution.extracted_content()
        #     final_result = browser_execution.final_result()
        #
        #     # Format content based on requested format
        #     if extract_format.lower() == "json":
        #         formatted_content = json.dumps(
        #             {"summary": final_result, "extracted_data": extracted_content},
        #             indent=2,
        #         )
        #     elif extract_format.lower() == "text":
        #         formatted_content = (
        #             f"{final_result}\n\n{_format_extracted_content(extracted_content)}"
        #         )
        #     else:  # markdown (default)
        #         formatted_content = (
        #             f"## Browser Automation Result\n\n**Summary:** {final_result}\n\n"
        #             f"{_format_extracted_content(extracted_content)}"
        #         )
        #
        #     # Prepare metadata
        #     metadata = BrowserMetadata(
        #         task=task,
        #         execution_successful=True,
        #         steps_taken=(
        #             len(browser_execution.history)
        #             if hasattr(browser_execution, "history")
        #             else None
        #         ),
        #         downloaded_files=[],
        #         visited_urls=_extract_visited_urls(extracted_content),
        #         execution_time=execution_time,
        #         trace_log_path=trace_log_dir + "/browser_log/trace.log",
        #     )
        #
        #     logging.info(f"🗒️ Detail: {extracted_content}")
        #     logging.info(f"🌏 Result: {final_result}")
        #
        #     action_response = ActionResponse(
        #         success=True,
        #         message=formatted_content,
        #         metadata=metadata.model_dump(),
        #     )
        #     return TextContent(
        #         type="text",
        #         text=json.dumps(
        #             action_response.model_dump()
        #         ),  # Empty string instead of None
        #         **{"metadata": {}},  # Pass as additional fields
        #     )
        #
        # else:
        #     # Handle execution failure
        #     error_msg = "Browser execution failed or was not completed successfully"
        #
        #     metadata = BrowserMetadata(
        #         task=task,
        #         execution_successful=False,
        #         execution_time=execution_time,
        #         error_type="execution_failure",
        #         trace_log_path=trace_log_dir + "/browser_log/trace.log",
        #     )
        #
        #     logging.info(f"❌ {error_msg}")
        #
        #     action_response = ActionResponse(
        #         success=False, message=error_msg, metadata=metadata.model_dump()
        #     )
        #     return TextContent(
        #         type="text",
        #         text=json.dumps(
        #             action_response.model_dump()
        #         ),  # Empty string instead of None
        #         **{"metadata": {}},  # Pass as additional fields
        #     )

    except Exception as e:
        error_msg = f"Browser automation failed: {str(e)}"
        error_trace = traceback.format_exc()

        logging.info(f"Browser execution error: {error_trace}")

        metadata = BrowserMetadata(
            task=task,
            execution_successful=False,
            error_type="exception",
            trace_log_path=trace_log_dir + "/trace.log",
        )

        logging.info(f"❌ {error_msg}")
        action_response = ActionResponse(
            success=False,
            message=f"{error_msg}\n\nError details: {error_trace}",
            metadata=metadata.model_dump(),
        )
        return TextContent(
            type="text",
            text=json.dumps(
                action_response.model_dump()
            ),  # Empty string instead of None
            **{"metadata": {}},  # Pass as additional fields
        )


if __name__ == "__main__":
    load_dotenv(override=True)
    logging.info("Starting browser-server MCP server!")
    mcp.run(transport="stdio")
