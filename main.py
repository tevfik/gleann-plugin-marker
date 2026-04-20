"""gleann-plugin-marker — High-accuracy document extraction using marker-pdf.

A gleann plugin that converts documents (PDF, DOCX, images, etc.) to
structured graph nodes and markdown using the marker-pdf library.

Endpoints:
    GET  /health  → Plugin health and backend availability
    POST /convert → Upload a file, get back nodes + edges + markdown
"""

import argparse
import json
import logging
import os
import sys
import tempfile
from pathlib import Path

from fastapi import FastAPI, File, UploadFile
from fastapi.responses import JSONResponse

import marker_backend
import section_parser

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

PLUGIN_NAME = "gleann-plugin-marker"
PLUGIN_URL = "http://localhost:8766"
CAPABILITIES = ["document-extraction"]
SUPPORTED_EXTENSIONS = [
    ".pdf", ".docx", ".doc",
    ".xlsx", ".xls", ".pptx", ".ppt",
    ".epub", ".html", ".htm",
    ".png", ".jpg", ".jpeg", ".tiff", ".bmp",
]

# ---------------------------------------------------------------------------
# Globals
# ---------------------------------------------------------------------------

USE_LLM = os.environ.get("MARKER_LLM", "").lower() in ("1", "true", "yes")
OLLAMA_MODEL = os.environ.get("MARKER_OLLAMA_MODEL", None)

app = FastAPI(title=PLUGIN_NAME)
logger = logging.getLogger(PLUGIN_NAME)

# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@app.get("/health")
async def health():
    """Return plugin status, capabilities, and backend availability."""
    return {
        "status": "ok",
        "plugin": PLUGIN_NAME,
        "capabilities": CAPABILITIES,
        "backends": {
            "marker": marker_backend.is_available(),
            "use_llm": USE_LLM,
        },
    }


@app.post("/convert")
async def convert(file: UploadFile = File(...)):
    """Convert an uploaded file to graph nodes + edges + markdown."""
    ext = Path(file.filename).suffix.lower() if file.filename else ""

    if ext not in SUPPORTED_EXTENSIONS:
        return JSONResponse(
            status_code=400,
            content={
                "error": f"Unsupported file type: {ext}",
                "supported": SUPPORTED_EXTENSIONS,
            },
        )

    if not marker_backend.is_available():
        return JSONResponse(
            status_code=503,
            content={
                "error": "marker-pdf is not installed. Run: pip install marker-pdf[full]",
            },
        )

    # Save to temp file for marker processing
    suffix = ext or ".bin"
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        content = await file.read()
        tmp.write(content)
        tmp_path = tmp.name

    backend_used = "marker"
    try:
        result = marker_backend.convert_document(
            file_path=tmp_path,
            use_llm=USE_LLM,
            ollama_model=OLLAMA_MODEL,
        )
        markdown = result["markdown"]
    except Exception as e:
        logger.error("Marker conversion failed: %s", e)
        return JSONResponse(
            status_code=500,
            content={"error": f"Conversion failed: {e}"},
        )
    finally:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass

    # Parse markdown into graph nodes + edges
    nodes, edges = section_parser.parse_document(
        markdown, file.filename or "document"
    )

    return {
        "nodes": nodes,
        "edges": edges,
        "markdown": markdown,
        "backend": backend_used,
    }


# ---------------------------------------------------------------------------
# Plugin installation
# ---------------------------------------------------------------------------


def install_plugin():
    """Register this plugin in ~/.gleann/plugins.json."""
    plugins_dir = Path.home() / ".gleann"
    plugins_dir.mkdir(parents=True, exist_ok=True)
    plugins_file = plugins_dir / "plugins.json"

    plugins = []
    if plugins_file.exists():
        try:
            plugins = json.loads(plugins_file.read_text())
        except (json.JSONDecodeError, OSError):
            plugins = []

    # Remove existing entry for this plugin
    plugins = [p for p in plugins if p.get("name") != PLUGIN_NAME]

    plugins.append({
        "name": PLUGIN_NAME,
        "url": PLUGIN_URL,
        "command": [sys.executable, str(Path(__file__).resolve()), "--serve"],
        "capabilities": CAPABILITIES,
        "extensions": SUPPORTED_EXTENSIONS,
        "timeout": 120,
    })

    plugins_file.write_text(json.dumps(plugins, indent=2))
    logger.info("Installed %s → %s", PLUGIN_NAME, plugins_file)
    print(f"✓ Installed {PLUGIN_NAME} → {plugins_file}")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def main():
    parser = argparse.ArgumentParser(description=PLUGIN_NAME)
    parser.add_argument("--install", action="store_true",
                        help="Register plugin in ~/.gleann/plugins.json")
    parser.add_argument("--serve", action="store_true",
                        help="Start the HTTP server")
    parser.add_argument("--port", type=int, default=8766,
                        help="Server port (default: 8766)")
    parser.add_argument("--use-llm", action="store_true",
                        help="Enable LLM post-processing for higher accuracy")
    parser.add_argument("--ollama-model", type=str, default=None,
                        help="Ollama model for LLM mode (e.g. gemma2)")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(name)s] %(levelname)s %(message)s",
    )

    if args.use_llm:
        global USE_LLM
        USE_LLM = True
    if args.ollama_model:
        global OLLAMA_MODEL
        OLLAMA_MODEL = args.ollama_model

    if args.install:
        install_plugin()
        return

    if args.serve:
        global PLUGIN_URL
        PLUGIN_URL = f"http://localhost:{args.port}"
        import uvicorn
        uvicorn.run(app, host="0.0.0.0", port=args.port)
        return

    parser.print_help()


if __name__ == "__main__":
    main()
