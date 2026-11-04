import os
import sys
import pytest
from unittest.mock import patch, MagicMock

TEST_STORAGE_DB = "test_storage_render.db"
TEST_STORAGE_CHROMA = "./test_chroma_storage_render"

@pytest.fixture
def storage_client(monkeypatch):
    import config
    import database
    import rag_service
    import app

    monkeypatch.setattr(config, "DATABASE", TEST_STORAGE_DB)
    monkeypatch.setattr(database, "DATABASE", TEST_STORAGE_DB)
    monkeypatch.setattr(config, "CHROMA_PATH", TEST_STORAGE_CHROMA)
    monkeypatch.setattr(config, "OPENAI_API_KEY", "")
    monkeypatch.setattr(config, "ADMIN_KEY", "campus_admin_secret_2026")

    test_rag = rag_service.RAGService(chroma_path=TEST_STORAGE_CHROMA, in_memory=True)
    monkeypatch.setattr(rag_service, "rag_service_instance", test_rag)
    monkeypatch.setattr(app, "rag_service_instance", test_rag)

    if os.path.exists(TEST_STORAGE_DB):
        try:
            os.remove(TEST_STORAGE_DB)
        except Exception:
            pass

    database.init_db()
    app.app.config['TESTING'] = True

    with app.app.test_client() as client:
        yield client

    if os.path.exists(TEST_STORAGE_DB):
        try:
            os.remove(TEST_STORAGE_DB)
        except Exception:
            pass


def test_storage_paths_with_render_data_dir(monkeypatch):
    """Verifies DATA_DIR configures SQLite and Chroma paths for Render persistent disk."""
    import importlib
    monkeypatch.setenv("DATA_DIR", "/var/data")
    monkeypatch.delenv("DATABASE_PATH", raising=False)
    monkeypatch.delenv("CHROMA_PATH", raising=False)

    import config
    importlib.reload(config)

    expected_db = os.path.normpath("/var/data/lost_found.db")
    expected_chroma = os.path.normpath("/var/data/chroma_data")

    assert os.path.normpath(config.DATABASE) == expected_db
    assert os.path.normpath(config.CHROMA_PATH) == expected_chroma


def test_storage_paths_explicit_overrides(monkeypatch):
    """Verifies explicit DATABASE_PATH and CHROMA_PATH override DATA_DIR defaults."""
    import importlib
    monkeypatch.setenv("DATA_DIR", "/var/data")
    monkeypatch.setenv("DATABASE_PATH", "/var/custom/portal.sqlite")
    monkeypatch.setenv("CHROMA_PATH", "/var/custom/vectors")

    import config
    importlib.reload(config)

    assert config.DATABASE == "/var/custom/portal.sqlite"
    assert config.CHROMA_PATH == "/var/custom/vectors"


def test_rag_service_handles_readonly_filesystem():
    """Verifies RAGService does not crash on read-only filesystems (e.g. Vercel/Render)."""
    import rag_service

    with patch("os.makedirs", side_effect=OSError(30, "Read-only file system")):
        service = rag_service.RAGService(chroma_path="/var/task/read_only_chroma", in_memory=False)
        assert service.in_memory is True
        assert service.client is not None
        assert service.collection is not None


def test_chroma_collection_no_onnx_download():
    """Verifies collection is created with embedding_function=None to prevent ONNX model download."""
    import rag_service

    service = rag_service.RAGService(in_memory=True)
    assert service.collection._embedding_function is None


def test_item_creation_succeeds_even_when_vector_sync_fails(storage_client, monkeypatch):
    """Verifies item is saved in SQLite with HTTP 201 even if Chroma vector sync fails."""
    import app

    def failing_sync(item):
        raise RuntimeError("The read operation timed out in upsert (simulated)")

    monkeypatch.setattr(app.rag_service_instance, "sync_item", failing_sync)

    res = storage_client.post('/api/items', json={
        "type": "found",
        "item_name": "Hydro Flask Water Bottle",
        "category": "Bottle",
        "description": "Blue steel water bottle",
        "location": "Science Lab 3",
        "student_name": "Alex",
        "registration_number": "REG-8821",
        "contact_number": "9876543210",
        "contact_email": "alex@campus.edu"
    })

    assert res.status_code == 201
    data = res.get_json()
    assert "id" in data
    assert data["message"] == "Item added successfully"

    # Verify item is indeed in the SQLite database
    items_res = storage_client.get('/api/items')
    items = items_res.get_json()
    assert any(it["item_name"] == "Hydro Flask Water Bottle" for it in items)


def test_ai_search_graceful_fallback_on_chroma_error(storage_client, monkeypatch):
    """Verifies AI search falls back to SQLite hybrid search when Chroma query fails."""
    import app

    # Add an active item
    storage_client.post('/api/items', json={
        "type": "found",
        "item_name": "Silver Laptop Charger",
        "category": "Electronics",
        "description": "Dell 65W USB-C power adapter",
        "location": "Computer Lab",
        "student_name": "Sam",
        "registration_number": "REG-4433",
        "contact_number": "9876543211",
        "contact_email": "sam@campus.edu"
    })

    # Simulate ChromaDB query error
    def broken_chroma_query(*args, **kwargs):
        raise ConnectionError("_ssl.c:993: The handshake operation timed out in query")

    monkeypatch.setattr(app.rag_service_instance.collection, "query", broken_chroma_query)

    res = storage_client.post('/api/ai/search', json={"query": "lost dell laptop adapter"})
    assert res.status_code == 200
    data = res.get_json()
    assert len(data["results"]) >= 1
    assert data["results"][0]["item_name"] == "Silver Laptop Charger"


def test_llm_provider_none_handling(storage_client, monkeypatch):
    """Verifies that LLM_PROVIDER='none' turns off LLM explanations gracefully."""
    import config
    import llm_service
    import app

    monkeypatch.setattr(config, "LLM_PROVIDER", "none")
    test_llm = llm_service.OpenAIRAGService()
    test_llm.llm_provider = "none"
    test_llm.api_key = "sk-any-key"
    monkeypatch.setattr(app, "llm_service_instance", test_llm)

    assert test_llm.is_api_key_configured() is False

    res = storage_client.post('/api/ai/search', json={"query": "laptop"})
    assert res.status_code == 200
    data = res.get_json()
    assert data["api_key_configured"] is False
    assert data["status"] == "missing_api_key"


def test_requirements_contains_gunicorn():
    """Verifies requirements.txt specifies gunicorn for Render production deployment."""
    req_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "requirements.txt")
    with open(req_path, "r", encoding="utf-8") as f:
        content = f.read().lower()
    assert "gunicorn" in content


def test_env_example_has_no_secrets():
    """Verifies .env.example contains no real API keys or tokens."""
    env_example_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env.example")
    with open(env_example_path, "r", encoding="utf-8") as f:
        lines = f.readlines()

    for line in lines:
        line = line.strip()
        if line.startswith("OPENAI_API_KEY="):
            val = line.split("=", 1)[1].strip()
            assert val == "" or "your_" in val or "placeholder" in val
        if line.startswith("GEMINI_API_KEY="):
            val = line.split("=", 1)[1].strip()
            assert val == "" or "your_" in val or "placeholder" in val
