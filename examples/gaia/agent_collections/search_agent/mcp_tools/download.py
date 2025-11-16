"""
Download MCP Server

This module provides MCP server functionality for downloading files from URLs.
It supports HTTP/HTTPS downloads and returns JSON formatted results.

Key features:
- Download files from HTTP/HTTPS URLs
- Always overwrites existing files
- Custom headers support for authentication
- JSON formatted output
- Comprehensive error handling and logging
- Path validation and directory creation

Main functions:
- mcp_download_file: Download files from URLs
"""

import json
import shutil
import traceback
from pathlib import Path
from urllib.parse import urlparse

import requests
from dotenv import load_dotenv
from pydantic import BaseModel, Field
from pydantic.fields import FieldInfo

from aworld.logs.util import Color
from examples.gaia.mcp_collections.base import ActionArguments, ActionCollection, ActionResponse


class DownloadResult(BaseModel):
    """Individual download operation result with structured data."""

    url: str
    file_path: str
    success: bool
    error_message: str | None = None


class DownloadMetadata(BaseModel):
    """Metadata for download operation results."""

    url: str
    output_path: str
    overwrite_enabled: bool
    error_type: str | None = None


class DownloadCollection(ActionCollection):
    """MCP service for file download operations.

    Provides secure file download capabilities including:
    - HTTP/HTTPS URL support
    - Always overwrites existing files
    - Path validation and directory creation
    - JSON formatted output
    - Error handling and logging
    """

    def __init__(self, arguments: ActionArguments) -> None:
        super().__init__(arguments)

        # Configuration
        self.timeout = 1000
        self.max_file_size = 1024 * 1024 * 1024  # 1GB limit
        self.supported_schemes = {"http", "https"}

        self.headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/91.0.4472.124 Safari/537.36"
            ),
            "Accept-Language": "en-US,en;q=0.9",
        }

        self._color_log("Download service initialized", Color.green, "debug")
        self._color_log(f"Workspace: {self.workspace}", Color.blue, "debug")

    def _validate_url(self, url: str) -> tuple[bool, str | None]:
        """Validate URL format and scheme.

        Args:
            url: URL to validate

        Returns:
            Tuple of (is_valid, error_message)
        """
        try:
            parsed = urlparse(url)

            if not parsed.scheme:
                return False, "URL must include a scheme (http:// or https://)"

            if parsed.scheme.lower() not in self.supported_schemes:
                return False, f"Unsupported URL scheme: {parsed.scheme}. Supported: {', '.join(self.supported_schemes)}"

            if not parsed.netloc:
                return False, "URL must include a valid domain"

            return True, None

        except Exception as e:
            return False, f"Invalid URL format: {str(e)}"

    def _resolve_output_path(self, output_path: str) -> Path:
        """Resolve and validate output file path.

        Args:
            output_path: Output file path (absolute or relative)

        Returns:
            Resolved Path object
        """
        path = Path(output_path).expanduser()

        if not path.is_absolute():
            path = self.workspace / path

        # Ensure parent directory exists
        path.parent.mkdir(parents=True, exist_ok=True)

        return path.resolve()

    async def _download_file_async(
        self, url: str, output_path: Path, headers: dict[str, str] | None
    ) -> DownloadResult:
        """Download file asynchronously with comprehensive error handling.

        Args:
            url: URL to download from
            output_path: Local path to save file
            headers: Optional custom headers

        Returns:
            DownloadResult with execution details
        """
        try:
            self._color_log(f"📥 Starting download: {url}", Color.cyan)

            with requests.get(url, stream=True, timeout=self.timeout, headers=headers) as response:
                response.raise_for_status()

                # Check content length if available
                content_length = response.headers.get("content-length")
                if content_length and int(content_length) > self.max_file_size:
                    raise ValueError(f"File too large: {content_length} bytes (max: {self.max_file_size})")

                # Download file
                with open(output_path, "wb") as f:
                    shutil.copyfileobj(response.raw, f)

                file_size = output_path.stat().st_size
                self._color_log(f"✅ Download completed: {file_size:,} bytes", Color.green)

                return DownloadResult(
                    url=url,
                    file_path=str(output_path),
                    success=True,
                )

        except requests.exceptions.Timeout:
            error_msg = f"Download timed out after {self.timeout} seconds"
            self._color_log(f"⏰ {error_msg}", Color.red)

            return DownloadResult(
                url=url,
                file_path=str(output_path),
                success=False,
                error_message=error_msg,
            )

        except requests.exceptions.RequestException as e:
            error_msg = f"Request failed: {str(e)}"
            self._color_log(f"❌ {error_msg}", Color.red)

            return DownloadResult(
                url=url,
                file_path=str(output_path),
                success=False,
                error_message=error_msg,
            )

        except Exception as e:
            error_msg = f"Unexpected error: {str(e)}"
            self._color_log(f"💥 {error_msg}", Color.red)

            return DownloadResult(
                url=url,
                file_path=str(output_path),
                success=False,
                error_message=error_msg,
            )

    async def mcp_download_file(
        self,
        url: str = Field(description="HTTP/HTTPS URL of the file to download"),
        output_file_path: str = Field(
            description="Local path where the file should be saved (absolute or relative to workspace)"
        ),
    ) -> ActionResponse:
        """Download a file from a URL.

        This tool provides secure file download capabilities with:
        - HTTP/HTTPS URL support
        - Path validation and directory creation
        - JSON formatted output

        Args:
            url: The HTTP/HTTPS URL of the file to download
            output_file_path: Local path to save the downloaded file

        Returns:
            ActionResponse with download results and metadata in JSON format
        """
        # Handle FieldInfo objects
        if isinstance(url, FieldInfo):
            url = url.default
        if isinstance(output_file_path, FieldInfo):
            output_file_path = output_file_path.default

        try:
            # Validate URL
            url_valid, url_error = self._validate_url(url)
            if not url_valid:
                return ActionResponse(
                    success=False,
                    message=f"Invalid URL: {url_error}",
                    metadata=DownloadMetadata(
                        url=url,
                        output_path=output_file_path,
                        overwrite_enabled=True,
                        error_type="invalid_url",
                    ).model_dump(),
                )

            # Resolve output path
            output_path = self._resolve_output_path(output_file_path)

            # Perform download (always overwrite)
            result = await self._download_file_async(url, output_path, self.headers)

            # Format output as JSON
            formatted_output = json.dumps(result.model_dump(), indent=2)

            # Create metadata
            metadata = DownloadMetadata(
                url=url,
                output_path=str(output_path),
                overwrite_enabled=True,
            )

            if not result.success:
                metadata.error_type = "download_failure"

            return ActionResponse(
                success=result.success,
                message=formatted_output,
                metadata=metadata.model_dump(),
            )

        except Exception as e:
            error_msg = f"Failed to download file: {str(e)}"
            self.logger.error(f"Download error: {traceback.format_exc()}")

            return ActionResponse(
                success=False,
                message=error_msg,
                metadata=DownloadMetadata(
                    url=url,
                    output_path=output_file_path,
                    overwrite_enabled=True,
                    error_type="internal_error",
                ).model_dump(),
            )


# Default arguments for testing
if __name__ == "__main__":
    import os

    load_dotenv()

    arguments = ActionArguments(
        name="download",
        transport="stdio",
        workspace=os.getenv("AWORLD_WORKSPACE", "~"),
    )
    try:
        service = DownloadCollection(arguments)
        service.run()
    except Exception as e:
        print(f"An error occurred: {e}: {traceback.format_exc()}")
