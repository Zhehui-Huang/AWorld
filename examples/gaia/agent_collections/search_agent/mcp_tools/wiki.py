"""
Wikipedia MCP Server

This module provides MCP server functionality for interacting with Wikipedia.
It supports searching Wikipedia, retrieving article content, and getting summaries.

Key features:
- Search Wikipedia for articles
- Retrieve full article content
- Get article summaries
- Fetch random articles
- Get article categories and links
- Access historical versions of articles

Main functions:
- mcp_search_wikipedia: Searches Wikipedia for articles matching a query
- mcp_get_article_content: Retrieves the full content of a Wikipedia article
- mcp_get_article_summary: Gets a summary of a Wikipedia article
- mcp_get_article_categories: Gets categories for a Wikipedia article
- mcp_get_article_links: Gets links from a Wikipedia article
- mcp_get_article_history: Gets historical version of a Wikipedia page closest to the specified date
"""

import asyncio
import calendar
import json
import os
import re
import traceback
from datetime import datetime

import requests
import tiktoken
import wikipedia
import wikipediaapi
from dotenv import load_dotenv
from pydantic import BaseModel, Field
from pydantic.fields import FieldInfo

from aworld.agents.llm_json_dataset_logger import log_separate_llm_call
from aworld.config.conf import AgentConfig
from aworld.logs.util import Color
from aworld.models.llm import get_llm_model
from examples.gaia.mcp_collections.base import ActionArguments, ActionCollection, ActionResponse


# System prompt for Wikipedia content summarization
wikipedia_summarization_system_prompt = """You are an expert at extracting and summarizing information from Wikipedia articles.

Your task is to create focused, task-aware summaries that preserve all relevant information needed to answer the given task or question.

Key principles:
1. **Task-Focused**: Only extract information directly relevant to the task/question
2. **Concise**: Provide brief descriptions without detailed explanations. State facts directly.
3. **Precise**: Keep technical terms, proper nouns, numbers, dates, and specific values exact
4. **Clear**: If no relevant information exists, simply state "No related information found."

Important:
- Do NOT include verbose explanations or background information unless directly relevant
- Focus on key facts, data, and numbers that help answer the task
- If the content is irrelevant to the task, respond with only: "No related information found."
"""


class WikipediaSearchResult(BaseModel):
    """Model representing a Wikipedia search result."""

    title: str
    snippet: str | None = None
    url: str | None = None


class WikipediaArticle(BaseModel):
    """Model representing a Wikipedia article."""

    title: str
    pageid: int | None = None
    url: str
    content: str
    summary: str
    images: list[str] | None = None
    categories: list[str] | None = None
    links: list[str] | None = None
    references: list[str] | None = None
    sections: list[dict[str, str]] | None = None
    # History-specific fields
    original_query: str | None = None
    requested_date: str | None = None
    actual_date: str | None = None
    is_exact_date: bool | None = None
    is_redirect: bool | None = None
    editor: str | None = None
    edit_comment: str | None = None


class WikipediaMetadata(BaseModel):
    """Metadata for Wikipedia operation results."""

    query: str
    language: str
    count: int
    operation_type: str
    error_type: str | None = None
    article_id: int | None = None
    is_redirect: bool | None = None
    requested_date: str | None = None
    actual_date: str | None = None


class WikipediaCollection(ActionCollection):
    """MCP service for Wikipedia information retrieval.

    Provides Wikipedia interaction capabilities including:
    - Article search
    - Content retrieval
    - Summary generation
    - Random article fetching
    - Category and link extraction
    - Historical version access
    - LLM-friendly result formatting
    """

    def __init__(self, arguments: ActionArguments) -> None:
        super().__init__(arguments)

        # Initialize configuration
        self.default_language = "en"
        self.max_search_results = 20
        self.max_random_articles = 10
        self.default_summary_sentences = 5

        wikipedia.set_lang(self.default_language)

        # Initialize tokenizer for token counting
        self._tokenizer = tiktoken.get_encoding("o200k_base")
        
        # Initialize LLM provider for summarization
        self._summarization_llm = None
        self._llm_temperature = float(os.getenv("LLM_TEMPERATURE", "1.0"))
        try:
            llm_config = AgentConfig(
                llm_provider=os.getenv("LLM_PROVIDER", "openai"),
                llm_model_name=os.getenv("LLM_MODEL_NAME", "gpt-4o"),
                llm_base_url=os.getenv("LLM_BASE_URL"),
                llm_api_key=os.getenv("LLM_API_KEY"),
                llm_temperature=self._llm_temperature
            )
            
            self._summarization_llm = get_llm_model(conf=llm_config)
            self._color_log("Summarization LLM initialized", Color.green, "debug")
        except Exception as e:
            self.logger.warning(f"Failed to initialize summarization LLM: {e}")
        
        # Load token limit for automatic summarization from environment
        self._token_limit = int(os.getenv("WIKIPEDIA_TOKEN_LIMIT", "500"))
        self._color_log(f"Token limit for auto-summarization: {self._token_limit}", Color.blue, "debug")

        self._color_log("Wikipedia service initialized", Color.green, "debug")

    def _extract_sections_recursive(self, sections_list) -> list[dict[str, str]]:
        """Recursively extract sections from wikipediaapi section structure.
        
        Args:
            sections_list: List of wikipediaapi Section objects
            
        Returns:
            List of dictionaries with 'title' and 'content' keys
        """
        result = []
        for section in sections_list:
            if section.text:  # Only include sections with text content
                result.append({
                    "title": section.title,
                    "content": section.text
                })
            # Recursively process subsections
            if section.sections:
                result.extend(self._extract_sections_recursive(section.sections))
        return result

    def _count_tokens(self, text: str) -> int:
        """Count the number of tokens in the given text.
        
        Args:
            text: The text to count tokens for
            
        Returns:
            Number of tokens, or character count / 4 as fallback
        """
        if self._tokenizer:
            try:
                return len(self._tokenizer.encode(text))
            except Exception as e:
                self.logger.warning(f"Token counting failed: {e}, using character approximation")
        
        # Fallback: approximate tokens as chars / 4
        return len(text) // 4
    
    def _create_summary_sync(self, previous_summary: str, new_content: str, section_range: str, task_description: str = None) -> str:
        """Synchronous wrapper for _create_summary_async.
        
        Args:
            previous_summary: Summary from previous sections (can be empty string)
            new_content: New content from current sections to summarize
            section_range: The section range this content covers
            task_description: Optional task/question context for focused summarization
            
        Returns:
            Summarized content
        """
        try:
            # Try to get the current event loop
            loop = asyncio.get_event_loop()
            if loop.is_running():
                # If loop is already running, we need to run in a separate thread
                # This shouldn't happen in normal MCP context but handle it gracefully
                import concurrent.futures
                with concurrent.futures.ThreadPoolExecutor() as executor:
                    future = executor.submit(
                        asyncio.run,
                        self._create_summary_async(previous_summary, new_content, section_range, task_description)
                    )
                    return future.result()
            else:
                # Use existing loop
                return loop.run_until_complete(self._create_summary_async(previous_summary, new_content, section_range, task_description))
        except RuntimeError:
            # No event loop exists, create one
            return asyncio.run(self._create_summary_async(previous_summary, new_content, section_range, task_description))
    
    async def _create_summary_async(self, previous_summary: str, new_content: str, section_range: str, task_description: str = None) -> str:
        """Create a task-aware summary of Wikipedia content using LLM.
        
        Args:
            previous_summary: Summary from previous sections (can be empty string)
            new_content: New content from current sections to summarize
            section_range: The section range this content covers
            task_description: Optional task/question context for focused summarization
            
        Returns:
            Summarized content combining previous summary with new content
        """
        if not self._summarization_llm:
            self.logger.warning("Summarization LLM not available, returning empty summary")
            return ""
        
        # Calculate token counts for logging
        prev_tokens = self._count_tokens(previous_summary) if previous_summary else 0
        new_tokens = self._count_tokens(new_content)
        total_tokens = prev_tokens + new_tokens
        
        try:
            self._color_log(
                f"🤖 Creating task-aware LLM summary for sections {section_range} (prev: {prev_tokens}, new: {new_tokens}, total: {total_tokens} tokens)...",
                Color.cyan,
                "debug"
            )
            
            # Build user prompt - restructured to cover previous summary first
            if task_description:
                if previous_summary:
                    user_prompt = f"""Task: {task_description}

You are continuing to process a Wikipedia article. Below is the summary of content from previous sections, followed by new content from sections {section_range}.

### Previous Summary ###
{previous_summary}

### New Content from sections {section_range} ###
{new_content}

### Instructions ###
1. Integrate the previous summary with any relevant information from the new content
2. Extract ONLY information directly relevant to the task
3. Be concise: provide brief descriptions without detailed explanations
4. Preserve exact numbers, dates, names, and technical terms
5. If the new content has no relevant information, keep only the previous summary
6. If nothing is relevant (including previous summary), respond with: "No related information found."
"""
                else:
                    user_prompt = f"""Task: {task_description}

Extract information from the following Wikipedia content that helps answer the task above.

### Content from sections {section_range} ###
{new_content}

### Instructions ###
1. Extract ONLY information directly relevant to the task
2. Be concise: provide brief descriptions without detailed explanations
3. Preserve exact numbers, dates, names, and technical terms
4. If no relevant information is found, respond with: "No related information found."
"""
            else:
                if previous_summary:
                    user_prompt = f"""You are continuing to process a Wikipedia article. Below is the summary of content from previous sections, followed by new content from sections {section_range}.

### Previous Summary ###
{previous_summary}

### New Content from sections {section_range} ###
{new_content}

### Instructions ###
1. Integrate the previous summary with key information from the new content
2. Be concise: provide brief descriptions without detailed explanations
3. Preserve exact numbers, dates, names, and technical terms
4. Remove redundant information"""
                else:
                    user_prompt = f"""Summarize the following content from sections {section_range} of a Wikipedia article.

### Content from sections {section_range} ###
{new_content}

### Instructions ###
1. Be concise: provide brief descriptions without detailed explanations
2. Preserve exact numbers, dates, names, and technical terms
3. Focus on key facts and important information
"""
            
            messages = [
                {"role": "system", "content": wikipedia_summarization_system_prompt},
                {"role": "user", "content": user_prompt}
            ]
            
            response = await self._summarization_llm.acompletion(messages, temperature=self._llm_temperature)
            summary_text = response.content if hasattr(response, 'content') else str(response)
            
            # Log this separate LLM call with response
            messages_with_response = messages + [{"role": "assistant", "content": summary_text}]
            # Extract agent_id from task_description if available (format: [Agent ID: xxx])
            agent_id = "unknown"
            if task_description:
                match = re.search(r'\[Agent ID: ([^\]]+)\]', task_description)
                if match:
                    agent_id = match.group(1)
            log_separate_llm_call(
                messages=messages_with_response,
                agent_type="search_agent",
                agent_id=agent_id,
                llm_purpose="wikipedia_summarization"
            )
            
            summary_token_count = self._count_tokens(summary_text)
            self._color_log(
                f"✅ Task-aware summary created ({summary_token_count} tokens, reduced from {total_tokens})",
                Color.green,
                "debug"
            )
            
            return summary_text

        except Exception as e:
            self.logger.warning(f"LLM summarization failed: {e}")
            return new_content if not previous_summary else previous_summary + "\n\n" + new_content
    
    async def _condense_summary_async(self, summary: str, task_description: str = None) -> str:
        """Condense a summary to make it more concise while preserving key information.
        
        Args:
            summary: The summary to condense
            task_description: Optional task/question context
            
        Returns:
            Condensed summary
        """
        if not self._summarization_llm:
            self.logger.warning("Summarization LLM not available, returning original summary")
            return summary
        
        token_count = self._count_tokens(summary)
        
        try:
            self._color_log(
                f"🔄 Condensing summary ({token_count} tokens)...",
                Color.magenta,
                "debug"
            )
            
            if task_description:
                user_prompt = f"""Task: {task_description}

The following summary has become too long. Condense it to as much as possible while keeping all critical information relevant to the task.

### Summary to condense ###
{summary}

### Instructions ###
1. Keep ALL key facts, numbers, and data relevant to the task
2. Remove redundant information and verbose explanations
3. Be concise: state facts directly without detailed explanations
4. Maintain exact numbers, dates, and technical terms"""
            else:
                user_prompt = f"""The following summary has become too long. Condense it to about half the length while preserving all critical information.

### Summary to condense ###
{summary}

### Instructions ###
1. Keep ALL key facts, numbers, and data
2. Remove redundant information and verbose explanations
3. Be concise: state facts directly without detailed explanations
4. Maintain exact numbers, dates, and technical terms"""
            
            messages = [
                {"role": "system", "content": wikipedia_summarization_system_prompt},
                {"role": "user", "content": user_prompt}
            ]
            
            response = await self._summarization_llm.acompletion(messages, temperature=self._llm_temperature)
            condensed_text = response.content if hasattr(response, 'content') else str(response)
            
            # Log this separate LLM call with response
            messages_with_response = messages + [{"role": "assistant", "content": condensed_text}]
            # Extract agent_id from task_description if available
            agent_id = "unknown"
            if task_description:
                match = re.search(r'\[Agent ID: ([^\]]+)\]', task_description)
                if match:
                    agent_id = match.group(1)
            log_separate_llm_call(
                messages=messages_with_response,
                agent_type="search_agent",
                agent_id=agent_id,
                llm_purpose="wikipedia_condensation"
            )
            
            condensed_token_count = self._count_tokens(condensed_text)
            self._color_log(
                f"✅ Summary condensed ({condensed_token_count} tokens, reduced from {token_count})",
                Color.green,
                "debug"
            )
            
            return condensed_text

        except Exception as e:
            self.logger.warning(f"Summary condensation failed: {e}")
            return summary
    
    def _condense_summary_sync(self, summary: str, task_description: str = None) -> str:
        """Synchronous wrapper for _condense_summary_async.
        
        Args:
            summary: The summary to condense
            task_description: Optional task/question context
            
        Returns:
            Condensed summary
        """
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                import concurrent.futures
                with concurrent.futures.ThreadPoolExecutor() as executor:
                    future = executor.submit(
                        asyncio.run,
                        self._condense_summary_async(summary, task_description)
                    )
                    return future.result()
            else:
                return loop.run_until_complete(self._condense_summary_async(summary, task_description))
        except RuntimeError:
            return asyncio.run(self._condense_summary_async(summary, task_description))

    def _format_search_results(self, results: list[WikipediaSearchResult], output_format: str = "markdown") -> str:
        """Format search results for LLM consumption.

        Args:
            results: List of search results
            output_format: Format type ('markdown', 'json', 'text')

        Returns:
            Formatted string suitable for LLM consumption
        """
        if output_format == "json":
            return json.dumps([result.model_dump() for result in results], indent=2)

        elif output_format == "text":
            if not results:
                return "No results found."

            output_parts = [f"Found {len(results)} results:"]

            for i, result in enumerate(results, 1):
                output_parts.append(f"{i}. {result.title}")
                if result.snippet:
                    output_parts.append(f"   {result.snippet}")
                if result.url:
                    output_parts.append(f"   URL: {result.url}")

            return "\n".join(output_parts)

        else:  # markdown (default)
            if not results:
                return "No Wikipedia search results found."

            output_parts = [f"# Wikipedia Search Results\n\nFound {len(results)} results:\n"]

            for i, result in enumerate(results, 1):
                output_parts.append(f"## {i}. [{result.title}]({result.url})")
                if result.snippet:
                    output_parts.append(f"{result.snippet}\n")

            return "\n".join(output_parts)

    def _format_article(
        self, article: WikipediaArticle, output_format: str = "markdown"
    ) -> str:
        """Format article for LLM consumption.

        Args:
            article: Wikipedia article
            output_format: Format type ('markdown', 'json', 'text')

        Returns:
            Formatted string suitable for LLM consumption
        """
        if output_format == "json":
            return json.dumps(article.model_dump(), indent=2)

        elif output_format == "text":
            output_parts = [f"Title: {article.title}"]

            if article.url:
                output_parts.append(f"URL: {article.url}")

            if article.summary:
                output_parts.append(f"\nSummary:\n{article.summary}")

            if article.content:
                output_parts.append(f"\nContent:\n{article.content}")

            if article.categories:
                output_parts.append(f"\nCategories: {', '.join(article.categories)}")

            if article.requested_date:
                output_parts.append("\nHistorical Version:")
                output_parts.append(f"Requested Date: {article.requested_date}")
                output_parts.append(f"Actual Date: {article.actual_date}")

            if article.links and len(article.links) > 0:
                output_parts.append(f"\nRelated Links: {', '.join(article.links[:10])}")
                if len(article.links) > 10:
                    output_parts.append(f"... and {len(article.links) - 10} more links")

            return "\n".join(output_parts)

        else:  # markdown (default)
            output_parts = [f"# {article.title}"]

            if article.url:
                output_parts.append(f"**Wikipedia:** [{article.title}]({article.url})")

            if article.summary:
                output_parts.append(f"\n## Summary\n{article.summary}")

            if article.content:
                output_parts.append(f"\n## Content\n{article.content}")

            if article.categories and len(article.categories) > 0:
                output_parts.append(f"\n## Categories\n{', '.join(article.categories)}")

            if article.links and len(article.links) > 0:
                output_parts.append("\n## Related Links\n")
                # Limit to first 20 links to avoid overwhelming output
                for i, link in enumerate(article.links[:20], 1):
                    output_parts.append(f"{i}. {link}")
                if len(article.links) > 20:
                    output_parts.append(f"\n... and {len(article.links) - 20} more links")

            if article.requested_date:
                output_parts.append("\n## Historical Version Information")
                output_parts.append(f"**Requested Date:** {article.requested_date}")
                output_parts.append(f"**Actual Date:** {article.actual_date}")
                if article.editor:
                    output_parts.append(f"**Editor:** {article.editor}")
                if article.edit_comment:
                    output_parts.append(f"**Edit Comment:** {article.edit_comment}")

            return "\n".join(output_parts)

    def mcp_search_wikipedia(
        self,
        query: str = Field(..., description="The search query string"),
        limit: int = Field(10, description="Maximum number of results to return"),
        language: str = Field("en", description="Language code for Wikipedia (e.g., 'en', 'es', 'fr')"),
        output_format: str = Field("markdown", description="Output format: 'markdown', 'json', or 'text'"),
    ) -> ActionResponse:
        """Search Wikipedia for articles matching the query.

        This tool provides Wikipedia search capabilities with:
        - Configurable result limits
        - Multi-language support
        - Result formatting
        - Error handling

        Args:
            query: Search query string
            limit: Maximum number of results to return
            language: Language code for Wikipedia
            output_format: Format for the response output

        Returns:
            ActionResponse with search results and metadata
        """
        try:
            # Handle FieldInfo objects
            if isinstance(query, FieldInfo):
                query = query.default
            if isinstance(limit, FieldInfo):
                limit = limit.default
            if isinstance(language, FieldInfo):
                language = language.default
            if isinstance(output_format, FieldInfo):
                output_format = output_format.default

            # Validate parameters
            if not query:
                return ActionResponse(
                    success=False,
                    message="Search query cannot be empty",
                    metadata=WikipediaMetadata(
                        query=query,
                        language=language,
                        count=0,
                        operation_type="search",
                        error_type="invalid_parameters",
                    ).model_dump(),
                )

            # Limit the number of results to prevent excessive API calls
            if limit > self.max_search_results:
                limit = self.max_search_results

            self._color_log(f"🔍 Searching Wikipedia for: {query} (language: {language})", Color.cyan)

            # Search Wikipedia
            search_results = wikipedia.search(query, results=limit)

            # Format results
            formatted_results = []
            for title in search_results:
                try:
                    # Get a summary to use as a snippet
                    summary = wikipedia.summary(title, sentences=1, auto_suggest=False)
                    # Create URL
                    url = f"https://{language}.wikipedia.org/wiki/{title.replace(' ', '_')}"

                    result = WikipediaSearchResult(title=title, snippet=summary, url=url)
                    formatted_results.append(result)
                except Exception as e:
                    self.logger.warning(f"Error getting details for '{title}': {str(e)}")
                    # Still include the result, but without a snippet
                    url = f"https://{language}.wikipedia.org/wiki/{title.replace(' ', '_')}"
                    result = WikipediaSearchResult(title=title, url=url)
                    formatted_results.append(result)

            # Format output for LLM
            formatted_output = self._format_search_results(formatted_results, output_format)

            # Create metadata
            metadata = WikipediaMetadata(
                query=query,
                language=language,
                count=len(formatted_results),
                operation_type="search",
            )

            self._color_log(f"✅ Found {len(formatted_results)} results for query: {query}", Color.green)

            return ActionResponse(
                success=True,
                message=formatted_output,
                metadata=metadata.model_dump(),
            )

        except Exception as e:
            error_msg = f"Failed to search Wikipedia: {str(e)}"
            self.logger.error(f"Wikipedia search error: {traceback.format_exc()}")

            return ActionResponse(
                success=False,
                message=error_msg,
                metadata=WikipediaMetadata(
                    query=query,
                    language=language,
                    count=0,
                    operation_type="search",
                    error_type="search_error",
                ).model_dump(),
            )

    def mcp_get_article_content(
        self,
        title: str = Field(..., description="Title of the Wikipedia article"),
        task_description: str = Field(default="", description="The task/question you're trying to answer using this Wikipedia content. Used to create task-aware summaries when content exceeds token limits."),
        auto_suggest: bool = Field(False, description="Whether to use Wikipedia's auto-suggest feature"),
        redirect: bool = Field(True, description="Whether to follow redirects"),
        language: str = Field("en", description="Language code for Wikipedia (e.g., 'en', 'es', 'fr')"),
        output_format: str = Field("markdown", description="Output format: 'markdown', 'json', or 'text'"),
    ) -> ActionResponse:
        """Retrieve the full content of a Wikipedia article with automatic summarization for long content.

        This tool provides Wikipedia article retrieval with:
        - Auto-suggestion support
        - Redirect handling
        - Multi-language support
        - LLM-optimized result formatting
        - Automatic task-aware summarization when content exceeds token limits (default: 3000 tokens)
        - Error handling

        Args:
            title: Title of the Wikipedia article
            task_description: Task/question context for focused summarization when content is too long
            auto_suggest: Whether to use Wikipedia's auto-suggest feature
            redirect: Whether to follow redirects
            language: Language code for Wikipedia
            output_format: Format for the response output

        Returns:
            ActionResponse with article content (automatically summarized if too long) and metadata
        """
        try:
            # Handle FieldInfo objects
            if isinstance(title, FieldInfo):
                title = title.default
            if isinstance(task_description, FieldInfo):
                task_description = task_description.default
            if isinstance(auto_suggest, FieldInfo):
                auto_suggest = auto_suggest.default
            if isinstance(redirect, FieldInfo):
                redirect = redirect.default
            if isinstance(language, FieldInfo):
                language = language.default
            if isinstance(output_format, FieldInfo):
                output_format = output_format.default

            # Validate parameters
            if not title:
                return ActionResponse(
                    success=False,
                    message="Article title cannot be empty",
                    metadata=WikipediaMetadata(
                        query=title,
                        language=language,
                        count=0,
                        operation_type="content_retrieval",
                        error_type="invalid_parameters",
                    ).model_dump(),
                )

            self._color_log(f"📖 Retrieving Wikipedia article: {title} (language: {language})", Color.cyan)
            if task_description:
                self._color_log(f"Task: {task_description[:100]}...", Color.blue, "debug")

            # Get the page using standard wikipedia library for basic info
            page = wikipedia.page(title, auto_suggest=auto_suggest, redirect=redirect)
            
            # Get the page using wikipediaapi for better section extraction
            wiki_api = wikipediaapi.Wikipedia(
                user_agent='AWorld-WikipediaAgent/1.0 (https://github.com/aiwaves-cn/agents)',
                language=language
            )
            page_api = wiki_api.page(page.title)  # Use the resolved title from wikipedia library
            
            # Extract sections using wikipediaapi
            sections = []
            if page_api.exists():
                sections = self._extract_sections_recursive(page_api.sections)

            # Create article object
            article = WikipediaArticle(
                title=page.title,
                pageid=page.pageid,
                url=page.url,
                content=page.content,
                summary=page.summary,
                images=page.images,
                categories=page.categories,
                links=page.links,
                references=page.references,
                sections=sections,
            )

            # Check if content needs rolling summarization
            if article.content:
                content_tokens = self._count_tokens(article.content)
                self._color_log(
                    f"Article content: {content_tokens} tokens",
                    Color.yellow,
                    "debug"
                )
                
                if content_tokens >= self._token_limit:
                    self._color_log(
                        f"📝 Content exceeds {self._token_limit} tokens, triggering rolling LLM summarization...",
                        Color.cyan
                    )
                    
                    # Process sections with rolling summarization
                    previous_summary = ""  # Rolling summary from previous sections
                    accumulated_new_content = ""  # New content not yet summarized
                    accumulated_sections = []  # Section indices in accumulated_new_content
                    
                    condensation_threshold = int(self._token_limit * 0.6)  # 60% of token limit
                    
                    # Process each section incrementally
                    for idx, section in enumerate(article.sections):
                        section_content = section.get("content", "")
                        if not section_content:
                            continue
                        
                        section_title = section.get("title", f"Section {idx}")
                        self._color_log(f"Processing section: {section_title}...", Color.blue, "debug")
                        
                        # Check if previous_summary needs condensation
                        if previous_summary:
                            summary_tokens = self._count_tokens(previous_summary)
                            if summary_tokens > condensation_threshold:
                                self._color_log(
                                    f"Previous summary has {summary_tokens} tokens (>{condensation_threshold}), condensing...",
                                    Color.yellow
                                )
                                previous_summary = self._condense_summary_sync(previous_summary, task_description)
                                condensed_tokens = self._count_tokens(previous_summary)
                                self._color_log(
                                    f"Summary condensed to {condensed_tokens} tokens",
                                    Color.green,
                                    "debug"
                                )
                        
                        # Accumulate new content
                        accumulated_new_content += f"\n\n## {section_title}\n{section_content}"
                        accumulated_sections.append(idx)
                        
                        # Calculate total tokens from both previous summary and accumulated new content
                        prev_summary_tokens = self._count_tokens(previous_summary) if previous_summary else 0
                        new_content_tokens = self._count_tokens(accumulated_new_content)
                        total_tokens = prev_summary_tokens + new_content_tokens
                        
                        self._color_log(
                            f"Total: {total_tokens} tokens (summary: {prev_summary_tokens}, new: {new_content_tokens})",
                            Color.yellow,
                            "debug"
                        )
                        
                        # If combined content exceeds limit, summarize
                        if total_tokens > self._token_limit:
                            # Create section range string
                            first_section = accumulated_sections[0] if accumulated_sections else idx
                            last_section = accumulated_sections[-1] if accumulated_sections else idx
                            section_range_str = f"{first_section}-{last_section}" if first_section != last_section else str(first_section)
                            
                            # Summarize with both previous summary and new content
                            previous_summary = self._create_summary_sync(previous_summary, accumulated_new_content, section_range_str, task_description)
                            
                            self._color_log(
                                f"📝 Content exceeded {self._token_limit} tokens, created rolling summary for sections {section_range_str}",
                                Color.cyan
                            )
                            
                            # Reset new content accumulation
                            accumulated_new_content = ""
                            accumulated_sections = []
                    
                    # Handle remaining content
                    if accumulated_new_content or previous_summary:
                        if accumulated_new_content:
                            # Create final summary from previous summary and remaining new content
                            first_section = accumulated_sections[0] if accumulated_sections else 0
                            last_section = accumulated_sections[-1] if accumulated_sections else (len(article.sections) - 1 if article.sections else 0)
                            section_range_str = f"{first_section}-{last_section}" if first_section != last_section else str(first_section)
                            
                            final_content = self._create_summary_sync(previous_summary, accumulated_new_content, section_range_str, task_description)
                        else:
                            # Only previous summary remains
                            final_content = previous_summary
                        
                        # Update article with summarized content
                        article.content = final_content
                        
                        self._color_log(
                            f"✅ Processed {len(article.sections)} sections with rolling summarization",
                            Color.green
                        )
                        self._color_log(
                            f"✅ Final content: {self._count_tokens(final_content)} tokens",
                            Color.green
                        )
                    else:
                        # No sections found, summarize entire content at once
                        self._color_log("No sections found, summarizing entire content", Color.yellow, "debug")
                        summarized_content = self._create_summary_sync("", article.content, "entire article", task_description)
                        article.content = summarized_content

            # Format output for LLM (content is automatically summarized if needed)
            formatted_output = self._format_article(article, output_format)

            # Create metadata
            metadata = WikipediaMetadata(
                query=title,
                language=language,
                count=1,
                operation_type="content_retrieval",
                article_id=page.pageid,
                is_redirect=page.title != title,
            )

            self._color_log(f"✅ Retrieved article: {page.title}", Color.green)

            return ActionResponse(
                success=True,
                message=formatted_output,
                metadata=metadata.model_dump(),
            )

        except Exception as e:
            error_msg = f"Failed to retrieve Wikipedia article: {str(e)}"
            self.logger.error(f"Wikipedia content retrieval error: {traceback.format_exc()}")

            return ActionResponse(
                success=False,
                message=error_msg,
                metadata=WikipediaMetadata(
                    query=title,
                    language=language,
                    count=0,
                    operation_type="content_retrieval",
                    error_type="content_retrieval_error",
                ).model_dump(),
            )

    def mcp_get_article_summary(
        self,
        title: str = Field(..., description="Title of the Wikipedia article"),
        sentences: int = Field(5, description="Number of sentences to return in the summary"),
        auto_suggest: bool = Field(False, description="Whether to use Wikipedia's auto-suggest feature"),
        redirect: bool = Field(True, description="Whether to follow redirects"),
        language: str = Field("en", description="Language code for Wikipedia (e.g., 'en', 'es', 'fr')"),
        output_format: str = Field("markdown", description="Output format: 'markdown', 'json', or 'text'"),
    ) -> ActionResponse:
        """Get a summary of a Wikipedia article.

        This tool provides Wikipedia article summary retrieval with:
        - Configurable summary length
        - Auto-suggestion support
        - Redirect handling
        - Multi-language support
        - LLM-optimized result formatting
        - Error handling

        Args:
            title: Title of the Wikipedia article
            sentences: Number of sentences to return in the summary
            auto_suggest: Whether to use Wikipedia's auto-suggest feature
            redirect: Whether to follow redirects
            language: Language code for Wikipedia
            output_format: Format for the response output

        Returns:
            ActionResponse with article summary and metadata
        """
        try:
            # Handle FieldInfo objects
            if isinstance(title, FieldInfo):
                title = title.default
            if isinstance(sentences, FieldInfo):
                sentences = sentences.default
            if isinstance(auto_suggest, FieldInfo):
                auto_suggest = auto_suggest.default
            if isinstance(redirect, FieldInfo):
                redirect = redirect.default
            if isinstance(language, FieldInfo):
                language = language.default
            if isinstance(output_format, FieldInfo):
                output_format = output_format.default

            # Validate parameters
            if not title:
                return ActionResponse(
                    success=False,
                    message="Article title cannot be empty",
                    metadata=WikipediaMetadata(
                        query=title,
                        language=language,
                        count=0,
                        operation_type="summary_retrieval",
                        error_type="invalid_parameters",
                    ).model_dump(),
                )

            self._color_log(f"📝 Retrieving summary for: {title} (language: {language})", Color.cyan)

            # Get the summary
            summary = wikipedia.summary(title, sentences=sentences, auto_suggest=auto_suggest, redirect=redirect)

            # Get the URL
            url = f"https://{language}.wikipedia.org/wiki/{title.replace(' ', '_')}"

            # Create article object with just the summary
            article = WikipediaArticle(
                title=title,
                url=url,
                content="",  # Empty content since we're just getting the summary
                summary=summary,
            )

            # Format output for LLM
            formatted_output = self._format_article(article, output_format)

            # Create metadata
            metadata = WikipediaMetadata(
                query=title,
                language=language,
                count=1,
                operation_type="summary_retrieval",
            )

            self._color_log(f"✅ Retrieved summary for: {title}", Color.green)

            return ActionResponse(
                success=True,
                message=formatted_output,
                metadata=metadata.model_dump(),
            )

        except Exception as e:
            error_msg = f"Failed to retrieve Wikipedia summary: {str(e)}"
            self.logger.error(f"Wikipedia summary retrieval error: {traceback.format_exc()}")

            return ActionResponse(
                success=False,
                message=error_msg,
                metadata=WikipediaMetadata(
                    query=title,
                    language=language,
                    count=0,
                    operation_type="summary_retrieval",
                    error_type="summary_retrieval_error",
                ).model_dump(),
            )

    def mcp_get_article_categories(
        self,
        title: str = Field(..., description="Title of the Wikipedia article"),
        language: str = Field("en", description="Language code for Wikipedia (e.g., 'en', 'es', 'fr')"),
        output_format: str = Field("markdown", description="Output format: 'markdown', 'json', or 'text'"),
    ) -> ActionResponse:
        """Get categories for a Wikipedia article.

        This tool provides Wikipedia article category retrieval with:
        - Multi-language support
        - LLM-optimized result formatting
        - Error handling

        Args:
            title: Title of the Wikipedia article
            language: Language code for Wikipedia
            output_format: Format for the response output

        Returns:
            ActionResponse with article categories and metadata
        """
        try:
            # Handle FieldInfo objects
            if isinstance(title, FieldInfo):
                title = title.default
            if isinstance(language, FieldInfo):
                language = language.default
            if isinstance(output_format, FieldInfo):
                output_format = output_format.default

            # Validate parameters
            if not title:
                return ActionResponse(
                    success=False,
                    message="Article title cannot be empty",
                    metadata=WikipediaMetadata(
                        query=title,
                        language=language,
                        count=0,
                        operation_type="categories_retrieval",
                        error_type="invalid_parameters",
                    ).model_dump(),
                )

            self._color_log(
                f"🏷️ Retrieving categories for Wikipedia article: {title} (language: {language})", Color.cyan
            )

            # Get the page
            page = wikipedia.page(title, auto_suggest=True, redirect=True)

            # Format output for LLM
            if output_format == "json":
                formatted_output = json.dumps(page.categories, indent=2)
            elif output_format == "text":
                formatted_output = f"Categories for {title}:\n" + "\n".join(f"- {cat}" for cat in page.categories)
            else:  # markdown
                formatted_output = f"# Categories for {title}\n\n" + "\n".join(f"- {cat}" for cat in page.categories)

            # Create metadata
            metadata = WikipediaMetadata(
                query=title,
                language=language,
                count=len(page.categories),
                operation_type="categories_retrieval",
                article_id=page.pageid,
            )

            self._color_log(f"✅ Retrieved {len(page.categories)} categories for: {title}", Color.green)

            return ActionResponse(
                success=True,
                message=formatted_output,
                metadata=metadata.model_dump(),
            )

        except Exception as e:
            error_msg = f"Failed to retrieve Wikipedia article categories: {str(e)}"
            self.logger.error(f"Wikipedia categories retrieval error: {traceback.format_exc()}")

            return ActionResponse(
                success=False,
                message=error_msg,
                metadata=WikipediaMetadata(
                    query=title,
                    language=language,
                    count=0,
                    operation_type="categories_retrieval",
                    error_type="categories_retrieval_error",
                ).model_dump(),
            )

    def mcp_get_article_links(
        self,
        title: str = Field(..., description="Title of the Wikipedia article"),
        language: str = Field("en", description="Language code for Wikipedia (e.g., 'en', 'es', 'fr')"),
        output_format: str = Field("markdown", description="Output format: 'markdown', 'json', or 'text'"),
    ) -> ActionResponse:
        """Get links from a Wikipedia article.

        This tool provides Wikipedia article link retrieval with:
        - Multi-language support
        - LLM-optimized result formatting
        - Error handling

        Args:
            title: Title of the Wikipedia article
            language: Language code for Wikipedia
            output_format: Format for the response output

        Returns:
            ActionResponse with article links and metadata
        """
        try:
            # Handle FieldInfo objects
            if isinstance(title, FieldInfo):
                title = title.default
            if isinstance(language, FieldInfo):
                language = language.default
            if isinstance(output_format, FieldInfo):
                output_format = output_format.default

            # Validate parameters
            if not title:
                return ActionResponse(
                    success=False,
                    message="Article title cannot be empty",
                    metadata=WikipediaMetadata(
                        query=title,
                        language=language,
                        count=0,
                        operation_type="links_retrieval",
                        error_type="invalid_parameters",
                    ).model_dump(),
                )

            self._color_log(f"🔗 Retrieving links from Wikipedia article: {title} (language: {language})", Color.cyan)

            # Get the page
            page = wikipedia.page(title, auto_suggest=True, redirect=True)

            # Format results
            formatted_results = []
            for link_title in page.links:
                try:
                    url = f"https://{language}.wikipedia.org/wiki/{link_title.replace(' ', '_')}"
                    result = WikipediaSearchResult(title=link_title, url=url)
                    formatted_results.append(result)
                except Exception as e:
                    self.logger.warning(f"Error formatting link '{link_title}': {str(e)}")

            # Format output for LLM
            if output_format == "json":
                formatted_output = json.dumps([result.model_dump() for result in formatted_results], indent=2)
            elif output_format == "text":
                formatted_output = f"Links from {title}:\n" + "\n".join(
                    f"- {result.title}" for result in formatted_results
                )

            else:  # markdown
                formatted_output = f"# Links from {title}\n\n"
                # Limit to first 50 links to avoid overwhelming output
                for i, result in enumerate(formatted_results[:50], 1):
                    formatted_output += f"{i}. [{result.title}]({result.url})\n"
                if len(formatted_results) > 50:
                    formatted_output += f"\n... and {len(formatted_results) - 50} more links"

            # Create metadata
            metadata = WikipediaMetadata(
                query=title,
                language=language,
                count=len(formatted_results),
                operation_type="links_retrieval",
                article_id=page.pageid,
            )

            self._color_log(f"✅ Retrieved {len(formatted_results)} links from: {title}", Color.green)

            return ActionResponse(
                success=True,
                message=formatted_output,
                metadata=metadata.model_dump(),
            )

        except Exception as e:
            error_msg = f"Failed to retrieve Wikipedia article links: {str(e)}"
            self.logger.error(f"Wikipedia links retrieval error: {traceback.format_exc()}")

            return ActionResponse(
                success=False,
                message=error_msg,
                metadata=WikipediaMetadata(
                    query=title,
                    language=language,
                    count=0,
                    operation_type="links_retrieval",
                    error_type="links_retrieval_error",
                ).model_dump(),
            )

    def mcp_get_article_history(
        self,
        title: str = Field(..., description="Title of the Wikipedia article"),
        date: str = Field(
            ...,
            description=("Target date in YYYY/MM/DD format. If day is omitted, last day of month will be used"),
        ),
        language: str = Field("en", description="Language code for Wikipedia (e.g., 'en', 'es', 'fr')"),
        auto_suggest: bool = Field(
            False,
            description="Whether to use Wikipedia's auto-suggest feature and handle redirects",
        ),
        output_format: str = Field("markdown", description="Output format: 'markdown', 'json', or 'text'"),
    ) -> ActionResponse:
        """Get historical version of a Wikipedia page closest to the specified date.

        This tool provides historical Wikipedia article retrieval with:
        - Date-based version lookup
        - Auto-suggestion support
        - Multi-language support
        - LLM-optimized result formatting
        - Error handling

        If exact date version is not available, returns the closest version before that date.
        Supports auto-suggestion and redirects to handle company name changes or variations.

        Args:
            title: The title of the Wikipedia page
            date: Target date in YYYY/MM/DD format
            language: Language code for Wikipedia
            auto_suggest: Whether to use Wikipedia's auto-suggest and handle redirects
            output_format: Format for the response output

        Returns:
            ActionResponse with historical article content and metadata
        """
        try:
            # Handle FieldInfo objects
            if isinstance(title, FieldInfo):
                title = title.default
            if isinstance(date, FieldInfo):
                date = date.default
            if isinstance(language, FieldInfo):
                language = language.default
            if isinstance(auto_suggest, FieldInfo):
                auto_suggest = auto_suggest.default
            if isinstance(output_format, FieldInfo):
                output_format = output_format.default

            # Validate parameters
            if not title:
                return ActionResponse(
                    success=False,
                    message="Article title cannot be empty",
                    metadata=WikipediaMetadata(
                        query=title,
                        language=language,
                        count=0,
                        operation_type="history_retrieval",
                        error_type="invalid_parameters",
                    ).model_dump(),
                )

            self._color_log(
                f"📅 Retrieving historical version of Wikipedia article: {title} for date: {date}", Color.cyan
            )

            # First try to find the correct page title using search and auto-suggest
            actual_title = title
            if auto_suggest:
                try:
                    # Search for the page and get the actual title
                    search_results = wikipedia.search(title, results=1)
                    if search_results:
                        # Get the page to handle redirects and get the canonical title
                        page = wikipedia.page(search_results[0], auto_suggest=True, redirect=True)
                        actual_title = page.title
                        self.logger.info(f"Found matching page: {actual_title} for query: {title}")
                except Exception as e:
                    self.logger.warning(f"Auto-suggest failed for {title}: {str(e)}")

            # Parse the date
            date_parts = date.split("/")
            year = int(date_parts[0])
            month = int(date_parts[1])
            day = int(date_parts[2]) if len(date_parts) > 2 else calendar.monthrange(year, month)[1]

            target_date = datetime(year, month, day)

            # Get page revisions
            params = {
                "action": "query",
                "prop": "revisions",
                "titles": actual_title,
                "rvprop": "ids|timestamp|user|comment|content",
                "rvlimit": 1,
                "rvdir": "older",
                "rvstart": target_date.isoformat(),
                "format": "json",
            }

            # Make API request
            API_URL = f"https://{language}.wikipedia.org/w/api.php"
            response = requests.get(API_URL, params=params, timeout=5)
            data = response.json()

            # Process response
            page = next(iter(data["query"]["pages"].values()))
            if "revisions" in page:
                revision = page["revisions"][0]
                actual_date = datetime.fromisoformat(revision["timestamp"].replace("Z", "+00:00"))

                # Create URL for this version
                page_id = page["pageid"]
                rev_id = revision["revid"]
                url = f"https://{language}.wikipedia.org/w/index.php?oldid={rev_id}"

                # Create article object
                article = WikipediaArticle(
                    title=actual_title,
                    pageid=page_id,
                    url=url,
                    content=revision["*"],
                    summary=f"Historical version from {actual_date.strftime('%Y/%m/%d')}",
                    images=[],  # Historical versions don't include images
                    categories=[],
                    links=[],
                    references=[],
                    sections=[],
                    original_query=title,
                    requested_date=target_date.strftime("%Y/%m/%d"),
                    actual_date=actual_date.strftime("%Y/%m/%d"),
                    is_exact_date=actual_date.date() == target_date.date(),
                    is_redirect=actual_title != title,
                    editor=revision["user"],
                    edit_comment=revision.get("comment", ""),
                )

                # Format output for LLM
                formatted_output = self._format_article(article, output_format)

                # Create metadata
                metadata = WikipediaMetadata(
                    query=title,
                    language=language,
                    count=1,
                    operation_type="history_retrieval",
                    article_id=page_id,
                    is_redirect=actual_title != title,
                    requested_date=target_date.strftime("%Y/%m/%d"),
                    actual_date=actual_date.strftime("%Y/%m/%d"),
                )

                self._color_log(f"✅ Retrieved historical version from {actual_date.strftime('%Y/%m/%d')}", Color.green)

                return ActionResponse(
                    success=True,
                    message=formatted_output,
                    metadata=metadata.model_dump(),
                )

            # No revision found
            error_msg = f"No revision found for {actual_title} (original query: {title}) before {date}"

            return ActionResponse(
                success=False,
                message=error_msg,
                metadata=WikipediaMetadata(
                    query=title,
                    language=language,
                    count=0,
                    operation_type="history_retrieval",
                    error_type="no_revision_found",
                    requested_date=target_date.strftime("%Y/%m/%d"),
                ).model_dump(),
            )

        except Exception as e:
            error_msg = f"Failed to retrieve Wikipedia article history: {str(e)}"
            self.logger.error(f"Wikipedia history retrieval error: {traceback.format_exc()}")

            return ActionResponse(
                success=False,
                message=error_msg,
                metadata=WikipediaMetadata(
                    query=title,
                    language=language,
                    count=0,
                    operation_type="history_retrieval",
                    error_type="history_retrieval_error",
                    requested_date=date,
                ).model_dump(),
            )


# Default arguments for testing
if __name__ == "__main__":
    load_dotenv()

    arguments = ActionArguments(
        name="wikipedia",
        transport="stdio",
        workspace=os.getenv("AWORLD_WORKSPACE", "~"),
    )

    try:
        service = WikipediaCollection(arguments)
        service.run()
    except Exception as e:
        print(f"An error occurred: {e}")
