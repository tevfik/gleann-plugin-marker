"""Marker backend for gleann-plugin-marker.

Provides high-accuracy document-to-markdown conversion using marker-pdf.
Falls back gracefully if marker is not installed.

Control via environment variable:
    MARKER_LLM=true       → enable LLM post-processing for max accuracy
    MARKER_LLM=false      → disable LLM mode (default)
    MARKER_OLLAMA_MODEL=x → use Ollama model x for LLM mode
"""

import os
import re
import logging
from typing import Optional

logger = logging.getLogger("gleann-plugin-marker.backend")

_converter = None
_marker_available = None


def is_available() -> bool:
    """Check if marker-pdf is installed."""
    global _marker_available

    if _marker_available is None:
        try:
            import marker  # noqa: F401
            _marker_available = True
        except ImportError:
            _marker_available = False

    return _marker_available


def _get_converter(use_llm: bool = False, ollama_model: Optional[str] = None):
    """Lazy-initialize the PdfConverter (first call takes ~3-5s for model loading)."""
    global _converter
    if _converter is not None:
        return _converter

    from marker.converters.pdf import PdfConverter
    from marker.models import create_model_dict
    from marker.config.parser import ConfigParser

    config = {"output_format": "markdown"}

    if use_llm:
        config["use_llm"] = True
        if ollama_model:
            config["llm_service"] = "marker.services.ollama.OllamaService"
            config["ollama_model"] = ollama_model

    config_parser = ConfigParser(config)

    logger.info("Initializing marker PdfConverter (first-time model load)...")
    _converter = PdfConverter(
        config=config_parser.generate_config_dict(),
        artifact_dict=create_model_dict(),
        processor_list=config_parser.get_processors(),
        renderer=config_parser.get_renderer(),
        llm_service=config_parser.get_llm_service() if use_llm else None,
    )
    logger.info("Marker PdfConverter ready.")
    return _converter


def linkify_urls(markdown: str) -> str:
    """Convert bare URL patterns in text to proper markdown links.

    Handles:
      - http:// and https:// URLs
      - www. prefixed URLs (adds https://)
      - Skips URLs already inside markdown links [text](url)
    """
    # Convert www. URLs not already in a markdown link
    markdown = re.sub(
        r'(?<!\(|/)(?<!/)(www\.[a-zA-Z0-9._/~:?#\[\]@!$&\'()*+,;=-]+[a-zA-Z0-9/])',
        lambda m: f'[{m.group(1)}](https://{m.group(1)})',
        markdown,
    )

    # Convert bare http(s):// URLs not already inside markdown link syntax
    markdown = re.sub(
        r'(?<!\]\()(?<!\()(https?://[a-zA-Z0-9._/~:?#\[\]@!$&\'()*+,;=-]+[a-zA-Z0-9/])',
        lambda m: f'[{m.group(1)}]({m.group(1)})',
        markdown,
    )

    return markdown


def convert_document(
    file_path: str,
    use_llm: bool = False,
    ollama_model: Optional[str] = None,
    linkify: bool = True,
) -> dict:
    """Convert a document using marker-pdf.

    Args:
        file_path: Path to the file.
        use_llm: Enable LLM post-processing for highest accuracy.
        ollama_model: Ollama model name for LLM mode (e.g. "gemma2").
        linkify: Whether to convert bare URLs to markdown links.

    Returns:
        Dict with keys:
          - markdown: The markdown content.
          - page_count: Number of pages (if available).
          - metadata: Marker metadata dict.

    Raises:
        Exception: If conversion fails (caller should handle gracefully).
    """
    from marker.output import text_from_rendered

    converter = _get_converter(use_llm=use_llm, ollama_model=ollama_model)
    rendered = converter(file_path)
    text, metadata, images = text_from_rendered(rendered)

    if linkify:
        text = linkify_urls(text)

    page_count = None
    if isinstance(metadata, dict):
        page_stats = metadata.get("page_stats", [])
        if page_stats:
            page_count = len(page_stats)

    return {
        "markdown": text,
        "page_count": page_count,
        "metadata": metadata if isinstance(metadata, dict) else {},
    }
