# gleann-plugin-marker

High-accuracy document extraction plugin for [gleann](https://github.com/tevfik/gleann) using [marker-pdf](https://github.com/VikParuchuri/marker).

```
┌──────────────┐       POST /convert        ┌────────────────────┐
│              │  ───────────────────────►   │                    │
│    gleann    │                             │  gleann-plugin-    │
│              │  ◄───────────────────────   │  marker            │
│              │   { nodes, edges, markdown} │                    │
└──────────────┘                             └────────┬───────────┘
                                                      │
                                             ┌────────▼───────────┐
                                             │   marker-pdf       │
                                             │   (surya OCR +     │
                                             │    texify + LLM)   │
                                             └────────────────────┘
```

## Supported Formats

| Format | Extensions | Backend |
|--------|-----------|---------|
| PDF | `.pdf` | marker-pdf (surya OCR) |
| Word | `.docx`, `.doc` | marker-pdf |
| Excel | `.xlsx`, `.xls` | marker-pdf |
| PowerPoint | `.pptx`, `.ppt` | marker-pdf |
| EPUB | `.epub` | marker-pdf |
| HTML | `.html`, `.htm` | marker-pdf |
| Images (OCR) | `.png`, `.jpg`, `.jpeg`, `.tiff`, `.bmp` | marker-pdf (surya OCR) |

## Accuracy

marker-pdf achieves **95.67% heuristic accuracy** vs docling's **86.71%** ([benchmark source](https://github.com/VikParuchuri/marker)).

With LLM post-processing enabled (`--use-llm`), accuracy improves further at the cost of latency.

## Installation

### Prerequisites

- Python 3.10+
- PyTorch (CPU or CUDA)

### Quick Start

```bash
# Clone
git clone https://github.com/tevfik/gleann-plugin-marker.git
cd gleann-plugin-marker

# Install dependencies
pip install -r requirements.txt

# Register with gleann
python main.py --install

# Start server
python main.py --serve
```

### With LLM Mode (Higher Accuracy)

```bash
# Using Ollama
python main.py --serve --use-llm --ollama-model gemma2

# Using environment variables
MARKER_LLM=true MARKER_OLLAMA_MODEL=gemma2 python main.py --serve
```

### Virtual Environment (Recommended)

```bash
python -m venv venv
source venv/bin/activate   # Linux/macOS
pip install -r requirements.txt
```

## Usage

### CLI

```bash
python main.py --help

# Register plugin
python main.py --install

# Start server (default port 8766)
python main.py --serve

# Custom port
python main.py --serve --port 9000

# With LLM post-processing
python main.py --serve --use-llm --ollama-model gemma2
```

### API

```bash
# Health check
curl http://localhost:8766/health

# Convert a PDF
curl -X POST http://localhost:8766/convert \
  -F "file=@document.pdf"

# Convert an image (OCR)
curl -X POST http://localhost:8766/convert \
  -F "file=@scan.png"
```

### Response Format

```json
{
  "nodes": [
    {"id": "doc_document_pdf", "type": "Document", "properties": {"title": "document.pdf"}},
    {"id": "sec_introduction", "type": "Section", "properties": {"title": "Introduction", "level": 1}}
  ],
  "edges": [
    {"source": "doc_document_pdf", "target": "sec_introduction", "type": "HAS_SECTION"}
  ],
  "markdown": "# Introduction\n\nContent here...",
  "backend": "marker"
}
```

## Configuration

| Environment Variable | Default | Description |
|---------------------|---------|-------------|
| `MARKER_LLM` | `false` | Enable LLM post-processing |
| `MARKER_OLLAMA_MODEL` | `None` | Ollama model for LLM mode |

## Development

```bash
# Install dev dependencies
pip install -r requirements-dev.txt

# Run tests
pytest -v

# Run tests with coverage
pytest --cov=. --cov-report=term-missing
```

## Architecture

The plugin follows gleann's plugin protocol:

1. **`GET /health`** — Returns plugin status, capabilities, and backend availability
2. **`POST /convert`** — Accepts multipart file upload, converts via marker-pdf, parses markdown into graph nodes/edges via `section_parser.py`

### Files

| File | Purpose |
|------|---------|
| `main.py` | FastAPI server, CLI, plugin registration |
| `marker_backend.py` | marker-pdf wrapper (lazy model init, LLM config, URL linkification) |
| `section_parser.py` | Markdown → graph nodes + edges (shared with gleann-plugin-docs) |
| `conftest.py` | Pytest fixtures |
| `test_main.py` | Endpoint + backend tests |

## License

GPL-3.0 (marker-pdf dependency is GPL-3.0 licensed)
