"""
Example usage of PDF Agent MCP Server

This script demonstrates how to use the PDF agent for document and image processing tasks.

Features demonstrated:
- PDF text extraction
- PDF image extraction
- OCR for scanned documents
- Image text extraction using OCR
- AI-powered image analysis using vision models
- Image metadata extraction
- Combining PDF and image processing
"""

import os
from dotenv import load_dotenv
from examples.gaia.agent_collections.pdf_agent.pdf_agent import PDFAgentCollection
from examples.gaia.mcp_collections.base import ActionArguments


def example_1_create_pdf_agent():
    """Example 1: Create a new PDF agent and process a document."""
    print("\n" + "=" * 80)
    print("Example 1: Create PDF agent and extract content from a PDF document")
    print("=" * 80)

    # Initialize the PDF agent service
    args = ActionArguments(
        name="pdf_agent_service",
        transport="stdio",
        workspace=os.getenv("AWORLD_WORKSPACE", "~"),
    )

    service = PDFAgentCollection(args)

    # Create agent and execute task
    task_prompt = """
    Extract all the text content from the PDF file located at '/path/to/document.pdf'.
    What is the title of the document?
    """

    result = service.mcp_create_pdf_agent(
        task_prompt=task_prompt,
        name="pdf_extractor",
        description="Agent for extracting and analyzing PDF content",
        max_steps=10,
    )

    print("\n--- Result ---")
    print(f"Success: {result.success}")
    print(f"Message:\n{result.message}")
    print(f"\nMetadata: {result.metadata}")


def example_2_extract_with_images():
    """Example 2: Extract content including images from a PDF."""
    print("\n" + "=" * 80)
    print("Example 2: Extract PDF content with images")
    print("=" * 80)

    args = ActionArguments(
        name="pdf_agent_service",
        transport="stdio",
        workspace=os.getenv("AWORLD_WORKSPACE", "~"),
    )

    service = PDFAgentCollection(args)

    task_prompt = """
    Process the PDF file at '/path/to/report.pdf'.
    Extract both text and images. The document contains several charts and diagrams.
    Summarize the key findings from page 5.
    """

    result = service.mcp_create_pdf_agent(
        task_prompt=task_prompt,
        name="pdf_analyzer",
        description="Agent for analyzing PDF reports with images",
        max_steps=15,
    )

    print("\n--- Result ---")
    print(f"Success: {result.success}")
    print(f"Message:\n{result.message}")


def example_3_specific_pages():
    """Example 3: Extract content from specific pages only."""
    print("\n" + "=" * 80)
    print("Example 3: Extract content from specific PDF pages")
    print("=" * 80)

    args = ActionArguments(
        name="pdf_agent_service",
        transport="stdio",
        workspace=os.getenv("AWORLD_WORKSPACE", "~"),
    )

    service = PDFAgentCollection(args)

    task_prompt = """
    Extract content from pages 10-15 of the PDF file at '/path/to/large_document.pdf'.
    What are the main topics discussed in these pages?
    """

    result = service.mcp_create_pdf_agent(
        task_prompt=task_prompt,
        name="pdf_page_extractor",
        description="Agent for extracting specific pages from PDFs",
        max_steps=10,
    )

    print("\n--- Result ---")
    print(f"Success: {result.success}")
    print(f"Message:\n{result.message}")


def example_4_ocr_processing():
    """Example 4: Process a scanned PDF with OCR."""
    print("\n" + "=" * 80)
    print("Example 4: Process scanned PDF with OCR")
    print("=" * 80)

    args = ActionArguments(
        name="pdf_agent_service",
        transport="stdio",
        workspace=os.getenv("AWORLD_WORKSPACE", "~"),
    )

    service = PDFAgentCollection(args)

    task_prompt = """
    Process the scanned PDF at '/path/to/scanned_document.pdf'.
    The document is a scanned image, so use OCR to extract the text.
    What is the date mentioned in the document?
    """

    result = service.mcp_create_pdf_agent(
        task_prompt=task_prompt,
        name="pdf_ocr_processor",
        description="Agent for processing scanned PDFs with OCR",
        max_steps=12,
    )

    print("\n--- Result ---")
    print(f"Success: {result.success}")
    print(f"Message:\n{result.message}")


def example_5_reuse_existing_agent():
    """Example 5: Create an agent and reuse it for multiple tasks."""
    print("\n" + "=" * 80)
    print("Example 5: Reuse existing PDF agent")
    print("=" * 80)

    args = ActionArguments(
        name="pdf_agent_service",
        transport="stdio",
        workspace=os.getenv("AWORLD_WORKSPACE", "~"),
    )

    service = PDFAgentCollection(args)

    # First task - create agent
    task_1 = "Extract the table of contents from '/path/to/document.pdf'"

    result_1 = service.mcp_create_pdf_agent(
        task_prompt=task_1,
        name="persistent_pdf_agent",
        description="Agent for multiple PDF processing tasks",
        max_steps=10,
    )

    print("\n--- First Task Result ---")
    print(f"Success: {result_1.success}")
    print(f"Agent ID: {result_1.metadata.get('agent_id')}")

    # Get agent ID for reuse
    agent_id = result_1.metadata.get("agent_id")

    if agent_id:
        # Second task - reuse the same agent
        task_2 = "Now extract the references section from the same document."

        result_2 = service.mcp_use_existing_pdf_agent(
            agent_id=agent_id,
            task_prompt=task_2,
            max_steps=10,
        )

        print("\n--- Second Task Result (Reusing Agent) ---")
        print(f"Success: {result_2.success}")
        print(f"Message:\n{result_2.message}")


def example_6_get_capabilities():
    """Example 6: Get PDF agent service capabilities."""
    print("\n" + "=" * 80)
    print("Example 6: Get PDF Agent Service Capabilities")
    print("=" * 80)

    args = ActionArguments(
        name="pdf_agent_service",
        transport="stdio",
        workspace=os.getenv("AWORLD_WORKSPACE", "~"),
    )

    service = PDFAgentCollection(args)

    result = service.mcp_get_pdf_agent_capabilities()

    print("\n--- Service Capabilities ---")
    print(f"Success: {result.success}")
    print(f"Message:\n{result.message}")
    print(f"\nMetadata: {result.metadata}")


def example_7_complex_analysis():
    """Example 7: Complex document analysis task."""
    print("\n" + "=" * 80)
    print("Example 7: Complex PDF analysis")
    print("=" * 80)

    args = ActionArguments(
        name="pdf_agent_service",
        transport="stdio",
        workspace=os.getenv("AWORLD_WORKSPACE", "~"),
    )

    service = PDFAgentCollection(args)

    task_prompt = """
    Analyze the research paper at '/path/to/research_paper.pdf'.
    
    1. Extract the abstract
    2. Identify the main research questions
    3. List all the figures and their captions
    4. Extract the conclusions
    5. What is the publication year?
    
    Format your answer as a structured summary.
    """

    result = service.mcp_create_pdf_agent(
        task_prompt=task_prompt,
        name="research_paper_analyzer",
        description="Agent for comprehensive research paper analysis",
        max_steps=20,
    )

    print("\n--- Result ---")
    print(f"Success: {result.success}")
    print(f"Message:\n{result.message}")


def example_8_image_ocr():
    """Example 8: Extract text from an image using OCR."""
    print("\n" + "=" * 80)
    print("Example 8: Extract text from image using OCR")
    print("=" * 80)

    args = ActionArguments(
        name="pdf_agent_service",
        transport="stdio",
        workspace=os.getenv("AWORLD_WORKSPACE", "~"),
    )

    service = PDFAgentCollection(args)

    task_prompt = """
    Extract all text from the image located at '/path/to/image.png' using OCR.
    The image contains a document or text. What does it say?
    """

    result = service.mcp_create_pdf_agent(
        task_prompt=task_prompt,
        name="image_ocr_agent",
        description="Agent for extracting text from images",
        max_steps=8,
    )

    print("\n--- Result ---")
    print(f"Success: {result.success}")
    print(f"Message:\n{result.message}")


def example_9_image_ai_analysis():
    """Example 9: Analyze image content using AI vision models."""
    print("\n" + "=" * 80)
    print("Example 9: Analyze image with AI vision")
    print("=" * 80)

    args = ActionArguments(
        name="pdf_agent_service",
        transport="stdio",
        workspace=os.getenv("AWORLD_WORKSPACE", "~"),
    )

    service = PDFAgentCollection(args)

    task_prompt = """
    Analyze the image at '/path/to/chart.jpg'.
    This is a chart or graph. Describe what the chart shows, including:
    - Type of chart (bar, line, pie, etc.)
    - What data is being displayed
    - Any trends or patterns visible
    - Key insights from the visualization
    """

    result = service.mcp_create_pdf_agent(
        task_prompt=task_prompt,
        name="image_analyzer_agent",
        description="Agent for analyzing images with AI vision",
        max_steps=10,
    )

    print("\n--- Result ---")
    print(f"Success: {result.success}")
    print(f"Message:\n{result.message}")


def example_10_pdf_with_image_analysis():
    """Example 10: Extract images from PDF and analyze them."""
    print("\n" + "=" * 80)
    print("Example 10: Extract PDF images and analyze with AI")
    print("=" * 80)

    args = ActionArguments(
        name="pdf_agent_service",
        transport="stdio",
        workspace=os.getenv("AWORLD_WORKSPACE", "~"),
    )

    service = PDFAgentCollection(args)

    task_prompt = """
    Process the PDF at '/path/to/report_with_charts.pdf'.
    
    1. Extract images from the PDF
    2. For each chart/diagram image extracted:
       - Analyze what the chart represents using AI vision
       - Extract any text labels using OCR if needed
    3. Summarize the key insights from all visualizations
    
    Focus on page 3-5 where the main charts are located.
    """

    result = service.mcp_create_pdf_agent(
        task_prompt=task_prompt,
        name="pdf_image_analyzer",
        description="Agent for extracting and analyzing images from PDFs",
        max_steps=25,
    )

    print("\n--- Result ---")
    print(f"Success: {result.success}")
    print(f"Message:\n{result.message}")


def example_11_image_metadata():
    """Example 11: Extract metadata from an image file."""
    print("\n" + "=" * 80)
    print("Example 11: Extract image metadata")
    print("=" * 80)

    args = ActionArguments(
        name="pdf_agent_service",
        transport="stdio",
        workspace=os.getenv("AWORLD_WORKSPACE", "~"),
    )

    service = PDFAgentCollection(args)

    task_prompt = """
    Get the technical metadata for the image at '/path/to/photo.jpg'.
    I need to know:
    - Image dimensions (width x height)
    - File format
    - File size
    - Color mode
    - Whether it has transparency
    """

    result = service.mcp_create_pdf_agent(
        task_prompt=task_prompt,
        name="image_metadata_agent",
        description="Agent for extracting image metadata",
        max_steps=6,
    )

    print("\n--- Result ---")
    print(f"Success: {result.success}")
    print(f"Message:\n{result.message}")


if __name__ == "__main__":
    # Load environment variables
    load_dotenv()

    # Check required environment variables
    required_vars = ["LLM_API_KEY"]
    missing_vars = [var for var in required_vars if not os.getenv(var)]

    if missing_vars:
        print(f"Error: Missing required environment variables: {', '.join(missing_vars)}")
        print("\nPlease set the following environment variables:")
        print("- LLM_API_KEY: Your LLM API key")
        print("- LLM_PROVIDER (optional, default: openai)")
        print("- LLM_MODEL_NAME (optional, default: gpt-4o)")
        print("- LLM_BASE_URL (optional)")
        print("- IMAGE_LLM_API_KEY (optional, for image analysis, falls back to LLM_API_KEY)")
        print("- IMAGE_LLM_MODEL_NAME (optional, for image analysis, default: gpt-4o)")
        print("- IMAGE_LLM_BASE_URL (optional, for image analysis, falls back to LLM_BASE_URL)")
        print("- AWORLD_WORKSPACE (optional, default: ~)")
        exit(1)

    print("\n" + "=" * 80)
    print("PDF Agent MCP Server - Example Usage")
    print("=" * 80)

    # Run examples
    try:
        # PDF Processing Examples
        # example_1_create_pdf_agent()
        # example_2_extract_with_images()
        # example_3_specific_pages()
        # example_4_ocr_processing()
        # example_5_reuse_existing_agent()
        example_6_get_capabilities()
        # example_7_complex_analysis()
        
        # Image Processing Examples (NEW)
        # example_8_image_ocr()              # Extract text from images
        # example_9_image_ai_analysis()      # AI-powered image analysis
        # example_10_pdf_with_image_analysis()  # Combined PDF + image analysis
        # example_11_image_metadata()        # Get image metadata

    except Exception as e:
        print(f"\nError running examples: {e}")
        import traceback

        traceback.print_exc()

