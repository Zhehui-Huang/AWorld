import multiprocessing as mp
mp.set_start_method("spawn", force=True)

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

try:
    from pypdf import PdfReader, PdfWriter
except ImportError:
    try:
        from PyPDF2 import PdfReader, PdfWriter
    except ImportError:
        PdfReader = None
        PdfWriter = None

from aworld.logs.util import Color
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
        output_format: Literal["markdown", "json", "html"] = Field(default="markdown", description="Output format: 'markdown', 'json', or 'html'"),
        extract_images: bool = Field(default=True, description="Whether to extract and save images from the whole document"),
        save_extracted_text_to_file: bool = Field(default=False, description="Save extracted text to a local file"),  # New parameter
        use_llm: bool = Field(default=False, description="Use LLM for enhanced accuracy (requires additional setup)"),
        page_range: str | None = Field(default=None, description="Specific pages to process (e.g., '0,5-10,20')"),
        force_ocr: bool = Field(default=False, description="Force OCR processing on the entire document"),
        format_lines: bool = Field(default=False, description="Reformat lines using local OCR model for better quality"),
        return_extracted_text: bool = Field(default=True, description="Return the extracted text content in the response"),
        return_metadata: bool = Field(default=True, description="Return metadata in the response. If metadata has already included in the previous message, set this to False to avoid duplication.")
    ) -> ActionResponse:
        """Extract content from PDF documents using marker package.

        This tool provides comprehensive PDF document content extraction with support for:
        - PDF files
        - Text extraction with proper formatting
        - Image and media extraction
        - Metadata collection
        - LLM-optimized output formatting
        - Optional page range selection
        - OCR processing support

        Args:
            args: Document extraction arguments including file path and options

        Returns:
            ActionResponse with extracted content, metadata, and media file paths
        """
        try:
            if isinstance(file_path, FieldInfo):
                file_path = file_path.default
            if isinstance(output_format, FieldInfo):
                output_format = output_format.default
            if isinstance(extract_images, FieldInfo):
                extract_images = extract_images.default
            if isinstance(save_extracted_text_to_file, FieldInfo):  # Handle new parameter
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

            # Get page count from the original PDF
            total_pages = self._get_pdf_page_count(file_path)

            # Load marker models if needed
            self._load_marker_models()

            # Extract content using marker (with page range validation)
            extraction_result = self._extract_content_with_marker(file_path, page_range, force_ocr, total_pages)

            # Save extracted media if requested
            saved_media = []
            if extract_images and extraction_result["images"]:
                saved_media = self._save_extracted_media(extraction_result["images"], file_path.stem)

            # Format content for LLM consumption
            formatted_content = self._format_content_for_llm(extraction_result["content"], output_format, return_extracted_text)

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
                    # Optionally, you might want to reflect this failure in the response

            # Prepare metadata
            file_stats = file_path.stat()
            if return_metadata:
                document_metadata = DocumentMetadata(
                    file_name=file_path.name,
                    file_size=file_stats.st_size,
                    file_type=file_path.suffix.lower(),
                    absolute_path=str(file_path.absolute()),
                    page_count=extraction_result["metadata"].get("page_count", total_pages),
                    extracted_images=[media["path"] for media in saved_media if media["type"] == "image"],
                    extracted_media=saved_media,
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
                    # If images were requested to be extracted this call
                    extracted_images = [media["path"] for media in saved_media if media.get("type") == "image"]
                    response_metadata["extracted_images"] = extracted_images
                    # Save mapping for future reference, in case images are needed on subsequent runs with extract_images=False
                    if extracted_images:
                        self._extract_images_path_info = {img_path: img_path for img_path in extracted_images}
                else:
                    # extract_images=False: Provide last known images if available,
                    # only if saved_media contains such images (which may not happen every call).
                    if self._extract_images_path_info:
                        # Use paths from self._extract_images_path_info
                        response_metadata["extracted_images"] = list(self._extract_images_path_info.values())
                # if saved_media:
                #     response_metadata["extracted_media"] = saved_media

            self._color_log(
                f"Successfully extracted content from {file_path.name} "
                f"({len(formatted_content)} characters, {len(saved_media)} media files)",
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
        
        This tool is useful when you only need to know document properties (especially page count)
        before performing more expensive operations like content extraction.

        Args:
            file_path: Path to the PDF document file

        Returns:
            ActionResponse with document metadata including total_page_num
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
                f"Successfully retrieved metadata for {file_path.name} ({total_pages} pages)",
                Color.green,
            )

            metadata_summary = (
                f"Document Metadata:\n"
                f"- File: {document_metadata.file_name}\n"
                f"- Total Pages: {total_pages}\n"
                f"- File Size: {document_metadata.file_size:,} bytes\n"
                f"- Absolute Path: {document_metadata.absolute_path}"
            )

            return ActionResponse(
                success=True,
                message=metadata_summary,
                metadata={}
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

    def mcp_summarize_and_reset_memory(
        self,
        summary: str = Field(description="A comprehensive summary of all findings from the pages processed so far"),
        reason: str = Field(description="Reason for needing to continue processing more pages"),
        processed_page_range: str | None = Field(default=None, description="Page range of all processed pages so far (e.g., '0-2')")
    ) -> ActionResponse:
        """Summarize current findings and reset conversation memory.

        This tool should be called when:
        - Current pages don't contain enough information to answer the question
        - Need to continue processing more pages to find the answer
        - Want to avoid context overflow by summarizing progress so far

        After calling this tool:
        - All previous conversation history (except system prompt and initial task) will be cleared
        - The summary will be added as context for future processing
        - Agent can continue processing remaining pages with fresh context

        Args:
            summary: A comprehensive summary of findings from pages processed so far
            reason: Explanation of why more pages need to be processed
            processed_page_range: Page range of all processed pages so far (e.g., '0-2')
        Returns:
            ActionResponse confirming memory reset with summary
        """
        try:
            if isinstance(summary, FieldInfo):
                summary = summary.default
            if isinstance(reason, FieldInfo):
                reason = reason.default
            if isinstance(processed_page_range, FieldInfo):
                processed_page_range = processed_page_range.default

            self._color_log(f"📝 Summarizing and resetting memory", Color.cyan)
            self._color_log(f"Summary: {summary[:200]}...", Color.blue, "debug")
            self._color_log(f"Reason: {reason}", Color.blue, "debug")
            self._color_log(f"Processed Page Range: {processed_page_range}", Color.blue, "debug")

            # Format the summary message with explicit processed_page_range
            formatted_summary = f"""## Progress Summary
**Pages Processed So Far:** {processed_page_range if processed_page_range else "As documented above"}
**Findings:** {summary}
**Reason to Continue:** {reason}

Memory has been reset. You can now continue processing the remaining pages with fresh context.
The summary above captures all important findings from previously processed pages.
###"""

            return ActionResponse(
                success=True,
                message=formatted_summary,
                metadata={
                    "memory_reset": True,
                    # "summary": summary,
                    # "reason": reason,
                    "processed_page_range": processed_page_range,
                    "action": "summarize_and_reset"
                }
            )

        except Exception as e:
            self.logger.error(f"Failed to summarize and reset memory: {str(e)}: {traceback.format_exc()}")
            return ActionResponse(
                success=False,
                message=f"Failed to summarize and reset memory: {str(e)}",
                metadata={"error_type": "summarization_error"}
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
