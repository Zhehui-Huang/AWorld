import multiprocessing as mp
mp.set_start_method("spawn", force=True)

import asyncio
import json
import os
import re
import tempfile
import time
import traceback
from collections import defaultdict
from pathlib import Path
from typing import Any, Literal, Optional  # Added Optional

from dotenv import load_dotenv
from marker.converters.pdf import PdfConverter
from marker.models import create_model_dict
from marker.output import text_from_rendered
from marker.settings import settings
from pydantic import BaseModel, Field
from pydantic.fields import FieldInfo

import tiktoken
from PyPDF2 import PdfReader, PdfWriter

from aworld.logs.util import Color
from aworld.core.llm_provider import get_llm_provider
from examples.gaia.mcp_collections.base import ActionArguments, ActionCollection, ActionResponse


class DocumentMetadata(BaseModel):
    """Metadata extracted from document processing."""

    file_name: str = Field(description="Original file name")
    file_size: int = Field(description="File size in bytes")
    file_type: str = Field(description="Document file type/extension")
    absolute_path: str = Field(description="Absolute path to the document file")
    page_count: int | None = Field(default=None, description="Number of pages in document")
    # processing_time: float = Field(description="Time taken to process the document in seconds", deprecated=True, exclude=True)
    extracted_images: list[str] = Field(default_factory=list, description="Paths to extracted image files")
    extracted_media: list[dict[str, str]] = Field(default_factory=list, description="list of extracted media files with type and path")
    output_format: str = Field(description="Format of the extracted content")
    llm_enhanced: bool = Field(default=False, description="Whether LLM enhancement was used", exclude=True)
    ocr_applied: bool = Field(default=False, description="Whether OCR was applied", exclude=True)
    extracted_text_file_path: str | None = Field(default=None, description="Absolute path to the extracted text file (if applicable)")
    total_page_num: int | None = Field(default=None, description="Total number of pages of the document")


class DocumentExtractionCollection(ActionCollection):
    """MCP service for PDF document content extraction using marker package.

    Supports extraction from PDF files only.
    Provides LLM-friendly text output with structured metadata and media file handling.
    """

    def __init__(self, arguments: ActionArguments) -> None:
        super().__init__(arguments)
        self._models_loaded = False
        self._marker_models = None
        self._media_output_dir = self.workspace / "extracted_media"
        self._media_output_dir.mkdir(exist_ok=True)
        self._extracted_texts_dir = self.workspace / "extracted_texts"  # New directory for text files
        self._extracted_texts_dir.mkdir(exist_ok=True)

        self.supported_extensions = {".pdf"}

        # extract images path info
        self._extract_images_path_info = {}
        
        # Initialize tokenizer for token counting
        self._tokenizer = tiktoken.get_encoding("o200k_base")
        
        # Initialize LLM provider for summarization
        self._summarization_llm = None
        try:
            llm_provider = os.getenv("LLM_PROVIDER", "openai")
            llm_model_name = os.getenv("LLM_MODEL_NAME", "gpt-4o")
            llm_base_url = os.getenv("LLM_BASE_URL")
            llm_api_key = os.getenv("LLM_API_KEY")
            llm_temperature = float(os.getenv("LLM_TEMPERATURE", "1.0"))
            
            self._summarization_llm = get_llm_provider(
                provider=llm_provider,
                model_name=llm_model_name,
                base_url=llm_base_url,
                api_key=llm_api_key,
                temperature=llm_temperature
            )
            self._color_log("Summarization LLM initialized", Color.green, "debug")
        except Exception as e:
            self.logger.warning(f"Failed to initialize summarization LLM: {e}")
        
        # Load token limit for automatic summarization from environment
        self._token_limit = int(os.getenv("PDF_EXTRACTION_TOKEN_LIMIT", "3000"))
        self._color_log(f"Token limit for auto-summarization: {self._token_limit}", Color.blue, "debug")

        self._color_log("PDF Extraction Service initialized", Color.green, "debug")
        self._color_log(f"Media output directory: {self._media_output_dir}", Color.blue, "debug")

    def _load_marker_models(self) -> None:
        """Load marker models for document processing.

        Lazy loading to avoid unnecessary resource consumption.
        """
        if not self._models_loaded:
            try:
                self._color_log("Loading marker models...", Color.yellow)
                self._marker_models = create_model_dict()
                self._models_loaded = True
                self._color_log("Marker models loaded successfully", Color.green)
            except Exception as e:
                self.logger.error(f"Failed to load marker models: {str(e)}")
                raise
    
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
    
    def _create_summary_sync(self, content: str, page_range: str, task_description: str = None) -> str:
        """Synchronous wrapper for _create_summary_async.
        
        Args:
            content: The full content to summarize
            page_range: The page range this content covers
            task_description: Optional task/question context for focused summarization
            
        Returns:
            Summarized content
        """
        try:
            # Try to get the current event loop
            loop = asyncio.get_event_loop()
            if loop.is_running():
                # If loop is already running, create a new task
                # This shouldn't happen in normal MCP context but handle it
                import concurrent.futures
                with concurrent.futures.ThreadPoolExecutor() as executor:
                    future = executor.submit(
                        asyncio.run,
                        self._create_summary_async(content, page_range, task_description)
                    )
                    return future.result()
            else:
                # Use existing loop
                return loop.run_until_complete(self._create_summary_async(content, page_range, task_description))
        except RuntimeError:
            # No event loop exists, create one
            return asyncio.run(self._create_summary_async(content, page_range, task_description))
    
    async def _create_summary_async(self, content: str, page_range: str, task_description: str = None) -> str:
        """Create a task-aware summary of extracted content using LLM.
        
        Args:
            content: The full content to summarize
            page_range: The page range this content covers
            task_description: Optional task/question context for focused summarization
            
        Returns:
            Summarized content
        """
        token_count = self._count_tokens(content)
        
        if token_count <= 1000:
            # Content is short enough, return as-is with header
            return f"## Content from pages {page_range}:\n{content}\n"
        
        # Use LLM to create intelligent summary
        if self._summarization_llm:
            try:
                self._color_log(
                    f"🤖 Creating task-aware LLM summary for pages {page_range} ({token_count} tokens)...",
                    Color.cyan,
                    "debug"
                )
                
                # Build task-aware summarization prompt
                if task_description:
                    summarization_prompt = f"""You are helping to answer the following task/question:

**Task**: {task_description}

Summarize the following content from pages {page_range} of a PDF document, focusing on information relevant to the task above.

Requirements:
1. Preserve all facts, data, numbers, and details that might help answer the task
2. Highlight any information directly relevant to the task/question
3. Keep technical terms and specific information
4. Maintain logical structure and flow
5. Use clear, organized formatting with markdown
6. If no relevant information is found, explicitly state that

Content to summarize:
{content}

Provide a focused summary that preserves information relevant to the task:"""
                else:
                    summarization_prompt = f"""Summarize the following content from pages {page_range} of a PDF document.

Requirements:
1. Preserve all key facts, data, numbers, and important details
2. Maintain logical structure and flow
3. Keep technical terms and specific information
4. Be comprehensive but concise
5. Use clear, organized formatting with markdown

Content to summarize:
{content}

Provide a comprehensive summary that preserves all important information:"""

                messages = [
                    {"role": "system", "content": "You are helping to extract and summarize information from PDF documents."},
                    {"role": "user", "content": summarization_prompt}
                ]
                
                response = await self._summarization_llm.acompletion(messages)
                summary_text = response.content if hasattr(response, 'content') else str(response)
                
                self._color_log(
                    f"✅ Task-aware summary created ({self._count_tokens(summary_text)} tokens)",
                    Color.green,
                    "debug"
                )
                
                task_label = "task-aware " if task_description else ""
                return f"## Summary of pages {page_range} ({task_label}LLM summary from {token_count} tokens):\n{summary_text}\n"
                
            except Exception as e:
                self.logger.warning(f"LLM summarization failed, falling back to simple method: {e}")
        
        # Fallback: Simple summarization if LLM fails or not available
        char_limit = 2000  # Approximate character limit for ~500 tokens
        
        first_part = content[:char_limit]
        last_part = content[-char_limit:]
        
        # Find good break points (end of sentence or paragraph)
        first_break = first_part.rfind('\n\n')
        if first_break == -1:
            first_break = first_part.rfind('. ')
        if first_break != -1:
            first_part = first_part[:first_break + 1]
        
        last_break = last_part.find('\n\n')
        if last_break == -1:
            last_break = last_part.find('. ')
        if last_break != -1:
            last_part = last_part[last_break + 1:]
        
        summary = (
            f"## Summary of pages {page_range} ({token_count} tokens, auto-truncated):\n"
            f"{first_part}\n"
            f"[... middle content omitted for brevity ...]\n"
            f"{last_part}\n"
        )
        
        return summary

    def _get_pdf_page_count(self, file_path: Path) -> int | None:
        """Get the total number of pages in a PDF file using pypdf.

        Args:
            file_path: Path to the PDF file

        Returns:
            Number of pages in the PDF, or None if pypdf is not available or an error occurs
        """
        if PdfReader is None:
            return None

        try:
            reader = PdfReader(str(file_path))
            num_pages = len(reader.pages)
            return num_pages
        except Exception as e:
            self.logger.error(f"Failed to get page count using pypdf: {str(e)}")
            return None
    
    def _extract_pdf_outline(self, file_path: Path) -> list[dict[str, Any]]:
        """Extract outline (table of contents / bookmarks) from PDF.
        
        Args:
            file_path: Path to the PDF file
            
        Returns:
            List of outline items with title, page number, and level
        """
        if PdfReader is None:
            return []
        
        try:
            reader = PdfReader(str(file_path))
            outline_items = []
            
            def extract_outline_recursive(outline, level=0):
                """Recursively extract outline items."""
                if not outline:
                    return
                
                for item in outline:
                    if isinstance(item, list):
                        # Nested outline
                        extract_outline_recursive(item, level + 1)
                    else:
                        # Individual outline item
                        try:
                            title = item.title if hasattr(item, 'title') else str(item)
                            # Get page number (0-indexed)
                            page_num = reader.get_destination_page_number(item) if hasattr(item, 'page') else None
                            
                            if title and page_num is not None:
                                outline_items.append({
                                    "title": title,
                                    "page": page_num,
                                    "level": level
                                })
                        except Exception as e:
                            self.logger.debug(f"Failed to extract outline item: {e}")
                            continue
            
            # Extract outline
            if hasattr(reader, 'outline') and reader.outline:
                extract_outline_recursive(reader.outline)
            
            return outline_items
            
        except Exception as e:
            self.logger.warning(f"Failed to extract PDF outline: {str(e)}")
            return []

    def _extract_pages_to_temp_pdf(self, file_path: Path, pages: list[int]) -> Path | None:
        """Extract specific pages from a PDF to a temporary file using pypdf.

        Args:
            file_path: Path to the original PDF file
            pages: List of page numbers to extract (0-indexed, pre-validated)

        Returns:
            Path to the temporary PDF file, or None if pypdf is not available
        
        Note:
            Pages are assumed to be validated before calling this method.
        """
        if PdfReader is None or PdfWriter is None:
            self._color_log("pypdf/PyPDF2 not available, cannot filter pages", Color.yellow)
            return None

        try:
            reader = PdfReader(str(file_path))
            writer = PdfWriter()
            
            # Add requested pages (already validated)
            for page_num in pages:
                writer.add_page(reader.pages[page_num])
            
            # Create temporary file
            temp_fd, temp_path = tempfile.mkstemp(suffix=".pdf", prefix="filtered_")
            os.close(temp_fd)
            
            # Write filtered PDF
            with open(temp_path, "wb") as output_file:
                writer.write(output_file)
            
            self._color_log(f"Extracted {len(pages)} pages to temporary PDF", Color.blue)
            return Path(temp_path)
            
        except Exception as e:
            self.logger.error(f"Failed to extract pages using pypdf: {str(e)}")
            return None

    def _extract_content_with_marker(
        self, file_path: Path, page_range: str | None, force_ocr: bool = False, total_pages: int | None = None
    ) -> dict[str, Any]:
        """Extract content using marker package.

        Args:
            file_path: Path to the document file
            page_range: Specific pages to process (e.g., '0,5-10,20')
            force_ocr: Use OCR to extract text from images if available
            total_pages: Total number of pages in the PDF (for validation)

        Returns:
            Dictionary containing extracted content and metadata
        
        Raises:
            ValueError: If any requested page is out of range
        """
        start_time = time.time()
        temp_pdf_path = None

        try:
            # Handle page range using pypdf
            pages = None
            if page_range:
                # Parse page range string (e.g., "0,5-10,20")
                pages = []
                for part in page_range.split(","):
                    if "-" in part:
                        start, end = map(int, part.split("-"))
                        pages.extend(range(start, end + 1))
                    else:
                        pages.append(int(part))
                
                # Validate page range if total_pages is known
                if total_pages is not None and pages:
                    invalid_pages = [p for p in pages if p < 0 or p >= total_pages]
                    if invalid_pages:
                        raise ValueError(
                            f"Invalid page numbers {invalid_pages}. "
                            f"Document has {total_pages} pages (valid range: 0-{total_pages-1})"
                        )
                    self._color_log(
                        f"Page range validated: {len(pages)} pages within valid range (0-{total_pages-1})", 
                        Color.green, 
                        "debug"
                    )
                
                # Extract specific pages to a temporary PDF using pypdf
                temp_pdf_path = self._extract_pages_to_temp_pdf(file_path, pages)
                if temp_pdf_path:
                    file_path = temp_pdf_path
                    self._color_log(f"Processing {len(pages)} specific pages", Color.cyan)
                else:
                    self._color_log("Falling back to processing entire PDF (pypdf not available)", Color.yellow)
            
            # Initialize converter and process
            converter: PdfConverter = PdfConverter(artifact_dict=self._marker_models)
            rendered = converter(str(file_path))
            text, _, images = text_from_rendered(rendered)
            text = text.encode(settings.OUTPUT_ENCODING, errors="replace").decode(settings.OUTPUT_ENCODING)

            processing_time = time.time() - start_time
            return {
                "content": text,
                "images": images or {},
                "metadata": {},
                # "processing_time": processing_time,
            }
        
        finally:
            # Clean up temporary PDF file
            if temp_pdf_path and temp_pdf_path.exists():
                try:
                    os.unlink(temp_pdf_path)
                    self._color_log("Cleaned up temporary PDF", Color.blue, "debug")
                except Exception as e:
                    self.logger.warning(f"Failed to delete temporary PDF {temp_pdf_path}: {str(e)}")

    def _save_extracted_media(self, images: dict[str, Any], file_stem: str) -> list[dict[str, str]]:
        """Save extracted images and return their paths.

        Args:
            images: Dictionary of extracted images from marker
            file_stem: Base name for saving files

        Returns:
            list of dictionaries containing media type and file paths
        """
        saved_media = []

        for idx, (page_num, image_data) in enumerate(images.items()):
            try:
                # Extract page number from page_num if it contains additional info
                if isinstance(page_num, str) and "_page_" in page_num:
                    # Extract page number from strings like "_page_11_Picture_0.jpeg"
                    match = re.search(r'_page_(\d+)', page_num)
                    actual_page_num = match.group(1) if match else page_num
                else:
                    actual_page_num = int(time.time() * 1000) % 1000000
                
                # Generate unique filename
                image_filename = f"{file_stem}_page_{actual_page_num}_img_{idx}.png"
                image_path = self._media_output_dir / image_filename

                # Save image data
                if hasattr(image_data, "save"):
                    # PIL Image object
                    image_data.save(image_path)
                elif isinstance(image_data, bytes):
                    # Raw image bytes
                    with open(image_path, "wb") as f:
                        f.write(image_data)
                else:
                    # Handle other formats
                    self.logger.warning(f"Unknown image data type for page {actual_page_num}: {type(image_data)}")
                    continue

                saved_media.append(
                    {"type": "image", "path": str(image_path), "page": str(actual_page_num), "filename": image_filename}
                )

                self._color_log(f"Saved image: {image_filename}", Color.blue)

            except Exception as e:
                self.logger.error(f"Failed to save image from page {page_num}: {str(e)}")

        return saved_media

    def _format_content_for_llm(self, content: str, output_format: str, return_extracted_text: bool) -> str:
        """Format extracted content to be LLM-friendly.

        Args:
            content: Raw extracted content
            output_format: Desired output format

        Returns:
            Formatted content string
        """
        if not return_extracted_text:
            return ""

        if output_format.lower() == "markdown":
            # Content is already in markdown format from marker
            return content
        elif output_format.lower() == "json":
            # Structure content as JSON

            return json.dumps({"content": content, "format": "structured_text"}, indent=2)
        elif output_format.lower() == "html":
            # Convert markdown to HTML if needed
            try:
                import markdown
                return markdown.markdown(content)
            except ImportError:
                self.logger.warning("markdown package not available, returning raw content")
                return content
        else:
            return content

    def mcp_extract_document_content(
        self,
        file_path: str = Field(description="Path to the PDF document file to extract content from"),
        task_description: str = Field(default="", description="The task/question you're trying to answer using this PDF content. Used to create task-aware summaries when content exceeds token limits."),
        insight_page_range: str | None = Field(default=None, description="Optional page range hint where the answer might be located (e.g., '5-10'). If provided, this range will be processed first. If no answer is found, the entire document will be processed."),
        output_format: Literal["markdown", "json", "html"] = Field(default="markdown", description="Output format: 'markdown', 'json', or 'html'"),
        extract_images: bool = Field(default=True, description="Whether to extract and save images from the whole document"),
        save_extracted_text_to_file: bool = Field(default=False, description="Save extracted text to a local file"),
        use_llm: bool = Field(default=False, description="Use LLM for enhanced accuracy (requires additional setup)"),
        page_range: str | None = Field(default=None, description="Specific pages to process (e.g., '0,5-10,20'). Use this when you know exactly which pages to extract. Leave empty to process entire document."),
        force_ocr: bool = Field(default=False, description="Force OCR processing on the entire document"),
        format_lines: bool = Field(default=False, description="Reformat lines using local OCR model for better quality"),
        return_extracted_text: bool = Field(default=True, description="Return the extracted text content in the response"),
        return_metadata: bool = Field(default=True, description="Return metadata in the response. If metadata has already included in the previous message, set this to False to avoid duplication.")
    ) -> ActionResponse:
        """Extract content from PDF documents using marker package with automatic summarization.

        This tool provides comprehensive PDF document content extraction with support for:
        - PDF files
        - Text extraction with proper formatting
        - Image and media extraction
        - Metadata collection
        - LLM-optimized output formatting
        - Optional page range selection
        - OCR processing support
        - Automatic incremental processing with summarization for long content

        The tool processes pages incrementally and automatically summarizes content when
        it exceeds the token limit, preventing context overflow.

        Args:
            args: Document extraction arguments including file path and options

        Returns:
            ActionResponse with extracted content (potentially summarized), metadata, and media file paths
        """
        try:
            if isinstance(file_path, FieldInfo):
                file_path = file_path.default
            if isinstance(task_description, FieldInfo):
                task_description = task_description.default
            if isinstance(insight_page_range, FieldInfo):
                insight_page_range = insight_page_range.default
            if isinstance(output_format, FieldInfo):
                output_format = output_format.default
            if isinstance(extract_images, FieldInfo):
                extract_images = extract_images.default
            if isinstance(save_extracted_text_to_file, FieldInfo):
                save_extracted_text_to_file = save_extracted_text_to_file.default
            if isinstance(page_range, FieldInfo):
                page_range = page_range.default
            if isinstance(use_llm, FieldInfo):
                use_llm = use_llm.default
            if isinstance(force_ocr, FieldInfo):
                force_ocr = force_ocr.default
            if isinstance(format_lines, FieldInfo):
                format_lines = format_lines.default
            if isinstance(return_extracted_text, FieldInfo):
                return_extracted_text = return_extracted_text.default
            if isinstance(return_metadata, FieldInfo):
                return_metadata = return_metadata.default

            # Validate input file
            file_path: Path = self._validate_file_path(file_path)
            self._color_log(f"Processing document: {file_path.name}", Color.cyan)
            if task_description:
                self._color_log(f"Task: {task_description[:100]}...", Color.blue, "debug")

            # Get page count from the original PDF
            total_pages = self._get_pdf_page_count(file_path)

            # Determine which pages to process based on insight_page_range or page_range
            pages_to_process = []
            using_insight_range = False
            
            # Priority: insight_page_range > page_range > all pages
            if insight_page_range:
                # Process insight pages first
                self._color_log(f"📍 Processing insight page range first: {insight_page_range}", Color.yellow)
                for part in insight_page_range.split(","):
                    if "-" in part:
                        start, end = map(int, part.split("-"))
                        pages_to_process.extend(range(start, end + 1))
                    else:
                        pages_to_process.append(int(part))
                using_insight_range = True
            elif page_range:
                # Process specified pages
                for part in page_range.split(","):
                    if "-" in part:
                        start, end = map(int, part.split("-"))
                        pages_to_process.extend(range(start, end + 1))
                    else:
                        pages_to_process.append(int(part))
            else:
                # Process all pages if no range specified
                if total_pages is not None:
                    pages_to_process = list(range(total_pages))
                else:
                    raise ValueError("Cannot determine page range without total page count")
            
            # Validate pages
            if total_pages is not None:
                invalid_pages = [p for p in pages_to_process if p < 0 or p >= total_pages]
                if invalid_pages:
                    raise ValueError(
                        f"Invalid page numbers {invalid_pages}. "
                        f"Document has {total_pages} pages (valid range: 0-{total_pages-1})"
                    )

            self._color_log(f"Will process {len(pages_to_process)} pages incrementally", Color.cyan)

            # Load marker models if needed
            self._load_marker_models()

            # Process pages incrementally with automatic summarization
            summaries = []
            accumulated_content = ""
            accumulated_pages = []
            all_saved_media = []
            
            for page_num in pages_to_process:
                self._color_log(f"Processing page {page_num}...", Color.blue, "debug")
                
                # Extract this single page
                extraction_result = self._extract_content_with_marker(
                    file_path, str(page_num), force_ocr, total_pages
                )
                
                page_content = extraction_result["content"]
                
                # Save extracted media if requested (only once for all pages)
                if extract_images and extraction_result["images"] and not all_saved_media:
                    all_saved_media = self._save_extracted_media(extraction_result["images"], file_path.stem)
                
                # Accumulate content
                accumulated_content += f"\n## Page {page_num}\n{page_content}\n"
                accumulated_pages.append(page_num)
                
                # Check token count
                current_tokens = self._count_tokens(accumulated_content)
                self._color_log(
                    f"Accumulated {current_tokens} tokens from {len(accumulated_pages)} pages", 
                    Color.yellow, 
                    "debug"
                )
                
                # If exceeds limit, summarize and reset
                if current_tokens > self._token_limit:
                    page_range_str = f"{accumulated_pages[0]}-{accumulated_pages[-1]}" if len(accumulated_pages) > 1 else str(accumulated_pages[0])
                    summary = self._create_summary_sync(accumulated_content, page_range_str, task_description)
                    summaries.append(summary)
                    
                    self._color_log(
                        f"📝 Content exceeded {self._token_limit} tokens, created summary for pages {page_range_str}",
                        Color.cyan
                    )
                    
                    # Reset accumulation
                    accumulated_content = ""
                    accumulated_pages = []
            
            # Handle remaining accumulated content
            if accumulated_content:
                if accumulated_pages:
                    page_range_str = f"{accumulated_pages[0]}-{accumulated_pages[-1]}" if len(accumulated_pages) > 1 else str(accumulated_pages[0])
                    # If it's short enough, just add it directly; otherwise summarize
                    remaining_tokens = self._count_tokens(accumulated_content)
                    if remaining_tokens > self._token_limit:
                        summary = self._create_summary_sync(accumulated_content, page_range_str, task_description)
                        summaries.append(summary)
                    else:
                        summaries.append(f"## Content from pages {page_range_str}:\n{accumulated_content}")
            
            # Combine all summaries and content
            if summaries:
                final_content = "\n".join(summaries)
                
                # Add hint if this was an insight_page_range extraction
                if using_insight_range and total_pages is not None:
                    processed_pages = set(pages_to_process)
                    all_pages = set(range(total_pages))
                    remaining_pages = all_pages - processed_pages
                    if remaining_pages:
                        final_content += f"\n\n---\n**Note**: This extraction processed insight pages {insight_page_range} ({len(processed_pages)} pages). If the answer was not found, there are {len(remaining_pages)} remaining pages in the document that can be processed by calling this tool again without insight_page_range.\n---\n"
                
                self._color_log(
                    f"✅ Processed {len(pages_to_process)} pages with {len(summaries)} content sections",
                    Color.green
                )
            else:
                final_content = "No content extracted."
            
            # Format content for LLM consumption
            formatted_content = self._format_content_for_llm(final_content, output_format, return_extracted_text)

            # Save extracted text to file if requested
            saved_text_path_str: Optional[str] = None
            if save_extracted_text_to_file:
                text_file_name = f"{file_path.stem}_extracted_text.txt"
                saved_text_path = self._extracted_texts_dir / text_file_name
                try:
                    with open(saved_text_path, "w", encoding="utf-8") as f:
                        f.write(formatted_content)
                    saved_text_path_str = str(saved_text_path.absolute())
                    self._color_log(f"Saved extracted text to: {saved_text_path_str}", Color.blue)
                except Exception as e:
                    self.logger.error(f"Failed to save extracted text to {saved_text_path}: {str(e)}")

            # Prepare metadata
            file_stats = file_path.stat()
            if return_metadata:
                document_metadata = DocumentMetadata(
                    file_name=file_path.name,
                    file_size=file_stats.st_size,
                    file_type=file_path.suffix.lower(),
                    absolute_path=str(file_path.absolute()),
                    page_count=len(pages_to_process),
                    extracted_images=[media["path"] for media in all_saved_media if media["type"] == "image"],
                    extracted_media=all_saved_media,
                    output_format=output_format,
                    llm_enhanced=use_llm,
                    ocr_applied=force_ocr or format_lines,
                    extracted_text_file_path=saved_text_path_str,
                    total_page_num=total_pages,
                )
                response_metadata = document_metadata.model_dump()
            else:
                response_metadata = {}
                # Handle extracted images and media for non-metadata mode
                if extract_images:
                    extracted_images = [media["path"] for media in all_saved_media if media.get("type") == "image"]
                    response_metadata["extracted_images"] = extracted_images
                    if extracted_images:
                        self._extract_images_path_info = {img_path: img_path for img_path in extracted_images}
                else:
                    if self._extract_images_path_info:
                        response_metadata["extracted_images"] = list(self._extract_images_path_info.values())

            self._color_log(
                f"Successfully extracted content from {file_path.name} "
                f"({len(formatted_content)} characters, {len(all_saved_media)} media files)",
                Color.green,
            )

            return ActionResponse(success=True, message=formatted_content, metadata=response_metadata)

        except FileNotFoundError as e:
            self.logger.error(f"File not found: {str(e)}: {traceback.format_exc()}")
            return ActionResponse(
                success=False, message=f"File not found: {str(e)}", metadata={"error_type": "file_not_found"}
            )
        except ValueError as e:
            self.logger.error(f"Invalid input: {str(e)}: {traceback.format_exc()}")
            return ActionResponse(
                success=False,
                message=f"Invalid input: {str(e)}: {traceback.format_exc()}",
                metadata={"error_type": "invalid_input"},
            )
        except Exception as e:
            self.logger.error(f"Document extraction failed: {str(e)}: {traceback.format_exc()}")
            return ActionResponse(
                success=False,
                message=f"Document extraction failed: {str(e)}",
                metadata={"error_type": "extraction_error"},
            )

    def mcp_get_document_metadata(
        self,
        file_path: str = Field(description="Path to the PDF document file to get metadata from"),
    ) -> ActionResponse:
        """Get metadata from PDF document without extracting full content.

        This is a lightweight operation that quickly retrieves document information including:
        - File name and size
        - Total number of pages
        - File type and absolute path
        - Document outline/table of contents with page numbers (if available)
        
        The outline information is particularly useful for understanding document structure
        and deciding which pages to extract for specific tasks.

        Args:
            file_path: Path to the PDF document file

        Returns:
            ActionResponse with document metadata including total_page_num and outline
        """
        try:
            if isinstance(file_path, FieldInfo):
                file_path = file_path.default
            
            # Validate input file
            file_path: Path = self._validate_file_path(file_path)
            self._color_log(f"Getting metadata for: {file_path.name}", Color.cyan)

            # Get page count
            total_pages = self._get_pdf_page_count(file_path)
            
            if total_pages is None:
                return ActionResponse(
                    success=False,
                    message="Unable to read PDF metadata. pypdf/PyPDF2 library may not be available.",
                    metadata={"error_type": "library_unavailable"}
                )

            # Extract outline/table of contents
            outline = self._extract_pdf_outline(file_path)
            
            # Prepare metadata
            file_stats = file_path.stat()
            document_metadata = DocumentMetadata(
                file_name=file_path.name,
                file_size=file_stats.st_size,
                file_type=file_path.suffix.lower(),
                absolute_path=str(file_path.absolute()),
                page_count=total_pages,
                extracted_images=[],
                extracted_media=[],
                output_format="N/A",
                llm_enhanced=False,
                ocr_applied=False,
                extracted_text_file_path=None,
                total_page_num=total_pages,
            )

            self._color_log(
                f"Successfully retrieved metadata for {file_path.name} ({total_pages} pages, {len(outline)} outline items)",
                Color.green,
            )

            # Build metadata summary with outline
            metadata_summary = (
                f"Document Metadata:\n"
                f"- File: {document_metadata.file_name}\n"
                f"- Total Pages: {total_pages}\n"
                f"- File Size: {document_metadata.file_size:,} bytes\n"
                f"- Absolute Path: {document_metadata.absolute_path}\n"
            )
            
            # Add outline information if available
            if outline:
                metadata_summary += f"\nDocument Outline (Table of Contents):\n"
                for item in outline:
                    indent = "  " * item["level"]
                    metadata_summary += f"{indent}- {item['title']} (page {item['page']})\n"
                metadata_summary += "\n💡 Use this outline to determine which pages to extract for specific information."
            else:
                metadata_summary += "\n(No outline/table of contents found in this PDF)"

            return ActionResponse(
                success=True,
                message=metadata_summary,
                metadata={"outline": outline} if outline else {}
            )

        except FileNotFoundError as e:
            self.logger.error(f"File not found: {str(e)}")
            return ActionResponse(
                success=False,
                message=f"File not found: {str(e)}",
                metadata={"error_type": "file_not_found"}
            )
        except Exception as e:
            self.logger.error(f"Failed to get document metadata: {str(e)}: {traceback.format_exc()}")
            return ActionResponse(
                success=False,
                message=f"Failed to get document metadata: {str(e)}",
                metadata={"error_type": "metadata_error"}
            )


    def mcp_list_supported_formats(self) -> ActionResponse:
        """list all supported document formats for extraction.

        Returns:
            ActionResponse with list of supported file formats and their descriptions
        """
        supported_formats = {
            "PDF": "Portable Document Format files (.pdf)",
        }

        format_list = "\n".join(
            [f"**{format_name}**: {description}" for format_name, description in supported_formats.items()]
        )

        return ActionResponse(
            success=True,
            message=f"Supported document formats:\n\n{format_list}",
            metadata={"supported_formats": list(supported_formats.keys()), "total_formats": len(supported_formats)},
        )


# Example usage and entry point
if __name__ == "__main__":
    load_dotenv()

    # Default arguments for testing
    args = ActionArguments(
        name="document_extraction_service",
        transport="stdio",
        workspace=os.getenv("AWORLD_WORKSPACE", "~"),
    )

    # Initialize and run the document extraction service
    try:
        service = DocumentExtractionCollection(args)
        service.run()
    except Exception as e:
        print(f"An error occurred: {e}: {traceback.format_exc()}")
