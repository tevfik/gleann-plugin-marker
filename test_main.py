"""Tests for gleann-plugin-marker."""

import json
from io import BytesIO
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest


# ---------------------------------------------------------------------------
# /health endpoint
# ---------------------------------------------------------------------------


def test_health(client):
    """GET /health returns plugin info and backend status."""
    resp = client.get("/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ok"
    assert data["plugin"] == "gleann-plugin-marker"
    assert "document-extraction" in data["capabilities"]
    assert "marker" in data["backends"]


# ---------------------------------------------------------------------------
# /convert endpoint — success paths
# ---------------------------------------------------------------------------


@patch("marker_backend.is_available", return_value=True)
@patch("marker_backend.convert_document")
def test_convert_pdf(mock_convert, mock_avail, client):
    """POST /convert with a PDF returns nodes, edges, markdown."""
    mock_convert.return_value = {
        "markdown": "# Title\n\nSome content",
        "page_count": 1,
        "metadata": {},
    }

    resp = client.post(
        "/convert",
        files={"file": ("test.pdf", BytesIO(b"%PDF-1.4 fake"), "application/pdf")},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "nodes" in data
    assert "edges" in data
    assert "markdown" in data
    assert data["backend"] == "marker"
    # Should have at least a document node and a section node
    assert len(data["nodes"]) >= 1


@patch("marker_backend.is_available", return_value=True)
@patch("marker_backend.convert_document")
def test_convert_docx(mock_convert, mock_avail, client):
    """POST /convert with a DOCX goes through marker backend."""
    mock_convert.return_value = {
        "markdown": "# Word Document\n\nParagraph text here.",
        "page_count": 2,
        "metadata": {},
    }

    resp = client.post(
        "/convert",
        files={"file": ("doc.docx", BytesIO(b"PK\x03\x04 fake"), "application/vnd.openxmlformats-officedocument.wordprocessingml.document")},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["backend"] == "marker"
    assert "Word Document" in data["markdown"]


@patch("marker_backend.is_available", return_value=True)
@patch("marker_backend.convert_document")
def test_convert_image(mock_convert, mock_avail, client):
    """POST /convert with a PNG image triggers OCR via marker."""
    mock_convert.return_value = {
        "markdown": "OCR extracted text from image.",
        "page_count": 1,
        "metadata": {},
    }

    resp = client.post(
        "/convert",
        files={"file": ("scan.png", BytesIO(b"\x89PNG fake"), "image/png")},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["backend"] == "marker"
    assert "OCR" in data["markdown"]


# ---------------------------------------------------------------------------
# /convert endpoint — error paths
# ---------------------------------------------------------------------------


def test_convert_unsupported_extension(client):
    """POST /convert with an unsupported extension returns 400."""
    resp = client.post(
        "/convert",
        files={"file": ("data.xyz", BytesIO(b"something"), "application/octet-stream")},
    )
    assert resp.status_code == 400
    data = resp.json()
    assert "error" in data
    assert "Unsupported" in data["error"]


def test_convert_no_file(client):
    """POST /convert without a file returns 422."""
    resp = client.post("/convert")
    assert resp.status_code == 422


@patch("marker_backend.is_available", return_value=False)
def test_convert_marker_not_installed(mock_avail, client):
    """POST /convert when marker is not installed returns 503."""
    resp = client.post(
        "/convert",
        files={"file": ("test.pdf", BytesIO(b"%PDF-1.4 fake"), "application/pdf")},
    )
    assert resp.status_code == 503
    data = resp.json()
    assert "not installed" in data["error"]


@patch("marker_backend.is_available", return_value=True)
@patch("marker_backend.convert_document", side_effect=RuntimeError("Model load failed"))
def test_convert_marker_failure(mock_convert, mock_avail, client):
    """POST /convert returns 500 when marker conversion fails."""
    resp = client.post(
        "/convert",
        files={"file": ("test.pdf", BytesIO(b"%PDF-1.4 fake"), "application/pdf")},
    )
    assert resp.status_code == 500
    data = resp.json()
    assert "Conversion failed" in data["error"]


# ---------------------------------------------------------------------------
# install_plugin
# ---------------------------------------------------------------------------


def test_install_plugin(tmp_path):
    """install_plugin() writes entry to plugins.json."""
    plugins_file = tmp_path / ".gleann" / "plugins.json"

    with patch("main.Path.home", return_value=tmp_path):
        from main import install_plugin
        install_plugin()

    assert plugins_file.exists()
    registry = json.loads(plugins_file.read_text())
    plugins = registry["plugins"]
    assert len(plugins) == 1
    assert plugins[0]["name"] == "gleann-plugin-marker"
    assert plugins[0]["capabilities"] == ["document-extraction"]
    assert plugins[0]["timeout"] == 120


def test_install_plugin_replaces_existing(tmp_path):
    """install_plugin() replaces an existing entry with the same name."""
    gleann_dir = tmp_path / ".gleann"
    gleann_dir.mkdir()
    plugins_file = gleann_dir / "plugins.json"

    existing = {"plugins": [
        {"name": "gleann-plugin-marker", "url": "http://old:1234"},
        {"name": "gleann-plugin-docs", "url": "http://localhost:8765"},
    ]}
    plugins_file.write_text(json.dumps(existing))

    with patch("main.Path.home", return_value=tmp_path):
        from main import install_plugin
        install_plugin()

    registry = json.loads(plugins_file.read_text())
    plugins = registry["plugins"]
    assert len(plugins) == 2
    marker = [p for p in plugins if p["name"] == "gleann-plugin-marker"][0]
    assert "serve" in str(marker["command"])
    docs = [p for p in plugins if p["name"] == "gleann-plugin-docs"]
    assert len(docs) == 1


# ---------------------------------------------------------------------------
# marker_backend unit tests
# ---------------------------------------------------------------------------


def test_marker_backend_is_available():
    """is_available() returns bool based on import availability."""
    import marker_backend as mb
    # Reset cached value
    mb._marker_available = None

    with patch.dict("sys.modules", {"marker": MagicMock()}):
        mb._marker_available = None
        assert mb.is_available() is True

    mb._marker_available = None
    with patch.dict("sys.modules", {"marker": None}):
        # Simulate ImportError
        mb._marker_available = False
        assert mb.is_available() is False


def test_linkify_urls():
    """linkify_urls converts bare URLs to markdown links."""
    from marker_backend import linkify_urls

    text = "Visit https://example.com/page for details."
    result = linkify_urls(text)
    assert "[https://example.com/page](https://example.com/page)" in result

    text2 = "See www.example.com/docs for more."
    result2 = linkify_urls(text2)
    assert "[www.example.com/docs](https://www.example.com/docs)" in result2
