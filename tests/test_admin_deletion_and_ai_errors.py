import pytest
import os
import json
import config

TEST_DB = "test_admin_del.db"
TEST_CHROMA = "./test_chroma_admin_del"

@pytest.fixture
def client(monkeypatch):
    monkeypatch.setattr(config, "DATABASE", TEST_DB)
    monkeypatch.setattr(config, "CHROMA_PATH", TEST_CHROMA)
    monkeypatch.setattr(config, "OPENAI_API_KEY", "")
    monkeypatch.setattr(config, "ADMIN_KEY", "campus_admin_secret_2026")

    import database
    monkeypatch.setattr(database, "DATABASE", TEST_DB)

    import rag_service
    test_rag = rag_service.RAGService(chroma_path=TEST_CHROMA, in_memory=True)
    monkeypatch.setattr(rag_service, "rag_service_instance", test_rag)

    import app
    monkeypatch.setattr(app, "rag_service_instance", test_rag)

    if os.path.exists(TEST_DB):
        try:
            os.remove(TEST_DB)
        except Exception:
            pass

    database.init_db()
    app.app.config['TESTING'] = True

    with app.app.test_client() as client:
        yield client

    if os.path.exists(TEST_DB):
        try:
            os.remove(TEST_DB)
        except Exception:
            pass


# =====================================================================
# TASK 2 TESTS: Admin Verification & Item Deletion Security
# =====================================================================

def test_admin_verify_endpoint_success(client):
    res = client.post('/api/admin/verify', json={"admin_key": "campus_admin_secret_2026"})
    assert res.status_code == 200
    data = res.get_json()
    assert data["success"] is True
    assert "verified" in data["message"].lower()


def test_admin_verify_endpoint_invalid_key(client):
    res = client.post('/api/admin/verify', json={"admin_key": "wrong_key_attempt"})
    assert res.status_code == 401
    data = res.get_json()
    assert data["success"] is False
    assert "invalid" in data["message"].lower()


def test_unauthenticated_visitor_cannot_delete_item(client):
    # Create item
    res = client.post('/api/items', json={
        "type": "lost",
        "item_name": "Leather Jacket",
        "student_name": "Student A",
        "registration_number": "REG1",
        "contact_number": "111",
        "contact_email": "a@col.edu"
    })
    item_id = res.get_json()["id"]

    # Attempt deletion without any admin header
    del_res = client.delete(f'/api/items/{item_id}')
    assert del_res.status_code == 403
    data = del_res.get_json()
    assert data["success"] is False
    assert "Unauthorized" in data["message"]

    # Verify item is still in database
    items = client.get('/api/items').get_json()
    assert any(it["id"] == item_id for it in items)


def test_ordinary_student_with_fake_isadmin_cannot_delete_item(client):
    # Create item
    res = client.post('/api/items', json={
        "type": "found",
        "item_name": "Scientific Calculator",
        "student_name": "Student B",
        "registration_number": "REG2",
        "contact_number": "222",
        "contact_email": "b@col.edu"
    })
    item_id = res.get_json()["id"]

    # Attempt deletion trying to spoof isAdmin in query or headers or wrong key
    del_res = client.delete(
        f'/api/items/{item_id}?isAdmin=true',
        headers={"X-Admin-Key": "student_trying_to_bypass"},
        json={"isAdmin": True}
    )
    assert del_res.status_code == 403
    data = del_res.get_json()
    assert data["success"] is False


def test_authorized_admin_can_delete_item(client):
    # 1. Create lost item
    res_lost = client.post('/api/items', json={
        "type": "lost",
        "item_name": "AirPods Pro",
        "student_name": "Student C",
        "registration_number": "REG3",
        "contact_number": "333",
        "contact_email": "c@col.edu"
    })
    lost_id = res_lost.get_json()["id"]

    # 2. Create matching found item
    res_found = client.post('/api/items', json={
        "type": "found",
        "item_name": "AirPods Pro Case",
        "student_name": "Student D",
        "registration_number": "REG4",
        "contact_number": "444",
        "contact_email": "d@col.edu"
    })
    found_id = res_found.get_json()["id"]

    # Verify candidate matches exist
    matches_before = client.get('/api/matches').get_json()
    assert len(matches_before) >= 1

    # 3. Authorized Admin deletes the found item
    del_res = client.delete(
        f'/api/items/{found_id}',
        headers={"X-Admin-Key": "campus_admin_secret_2026"}
    )
    assert del_res.status_code == 200
    data = del_res.get_json()
    assert data["success"] is True
    assert "deleted successfully" in data["message"]

    # 4. Verify found item is gone from database
    items_after = client.get('/api/items').get_json()
    assert not any(it["id"] == found_id for it in items_after)
    # The lost item must NOT have been deleted
    assert any(it["id"] == lost_id for it in items_after)

    # 5. Verify referencing matches were also cleaned up
    matches_after = client.get('/api/matches').get_json()
    assert not any(m["found_id"] == found_id for m in matches_after)


def test_delete_nonexistent_item_returns_404(client):
    del_res = client.delete(
        '/api/items/99999',
        headers={"X-Admin-Key": "campus_admin_secret_2026"}
    )
    assert del_res.status_code == 404
    data = del_res.get_json()
    assert data["success"] is False
    assert "not found" in data["message"].lower()


def test_delete_invalid_item_id_returns_400(client):
    del_res = client.delete(
        '/api/items/invalid-id-text',
        headers={"X-Admin-Key": "campus_admin_secret_2026"}
    )
    assert del_res.status_code == 400
    data = del_res.get_json()
    assert data["success"] is False
    assert "Invalid item ID" in data["message"]

    del_res_negative = client.delete(
        '/api/items/-10',
        headers={"X-Admin-Key": "campus_admin_secret_2026"}
    )
    assert del_res_negative.status_code == 400


def test_deletion_does_not_affect_unrelated_items(client):
    # Create three items
    id1 = client.post('/api/items', json={
        "type": "lost", "item_name": "Item 1", "student_name": "S1",
        "registration_number": "R1", "contact_number": "1", "contact_email": "1@c.edu"
    }).get_json()["id"]

    id2 = client.post('/api/items', json={
        "type": "lost", "item_name": "Item 2", "student_name": "S2",
        "registration_number": "R2", "contact_number": "2", "contact_email": "2@c.edu"
    }).get_json()["id"]

    id3 = client.post('/api/items', json={
        "type": "lost", "item_name": "Item 3", "student_name": "S3",
        "registration_number": "R3", "contact_number": "3", "contact_email": "3@c.edu"
    }).get_json()["id"]

    # Delete only item 2
    del_res = client.delete(f'/api/items/{id2}', headers={"X-Admin-Key": "campus_admin_secret_2026"})
    assert del_res.status_code == 200

    remaining = client.get('/api/items').get_json()
    remaining_ids = [it["id"] for it in remaining]
    assert id1 in remaining_ids
    assert id3 in remaining_ids
    assert id2 not in remaining_ids


# =====================================================================
# TASK 1 TESTS: AI Search Error Handling & JSON Consistency
# =====================================================================

def test_ai_search_invalid_json_body_returns_400_json(client):
    res = client.post('/api/ai/search', data="not json", content_type="text/plain")
    assert res.status_code == 400
    data = res.get_json()
    assert isinstance(data, dict)
    assert "Expected JSON" in data["message"] or "Invalid" in data["message"]


def test_ai_search_query_too_long_returns_400_json(client):
    long_query = "x" * 501
    res = client.post('/api/ai/search', json={"query": long_query})
    assert res.status_code == 400
    data = res.get_json()
    assert "exceeds maximum allowed length" in data["message"]


def test_ai_search_returns_consistent_json_structure(client):
    res = client.post('/api/ai/search', json={"query": "water bottle", "scope": "all"})
    assert res.status_code == 200
    data = res.get_json()
    assert "query" in data
    assert "scope" in data
    assert "api_key_configured" in data
    assert "llm_response" in data
    assert "disclaimer" in data
    assert "results" in data
    assert isinstance(data["results"], list)


def test_global_error_handlers_return_consistent_json(client):
    # Nonexistent endpoint must return 404 JSON, not HTML
    res_404 = client.get('/api/nonexistent/endpoint/12345')
    assert res_404.status_code == 404
    assert res_404.is_json
    data_404 = res_404.get_json()
    assert data_404["success"] is False
    assert "not found" in data_404["message"].lower()

    # Method not allowed must return 405 JSON, not HTML
    res_405 = client.delete('/api/dashboard/stats')
    assert res_405.status_code == 405
    assert res_405.is_json
    data_405 = res_405.get_json()
    assert data_405["success"] is False


def test_ai_search_with_mocked_openai_success(client, monkeypatch):
    from unittest.mock import MagicMock
    import app
    import llm_service

    # Create an item in db first
    client.post('/api/items', json={
        "type": "found",
        "item_name": "Milton Water Bottle",
        "student_name": "Alice",
        "registration_number": "R1",
        "contact_number": "111",
        "contact_email": "a@col.edu"
    })

    mock_client = MagicMock()
    mock_choice = MagicMock()
    mock_choice.message.content = "A blue Milton water bottle matching your query was found in the library."
    mock_response = MagicMock(choices=[mock_choice])
    mock_client.chat.completions.create.return_value = mock_response

    test_llm = llm_service.OpenAIRAGService()
    monkeypatch.setattr(test_llm, "api_key", "sk-mock-valid-key-for-test")
    monkeypatch.setattr(test_llm, "_get_openai_client", lambda: mock_client)
    monkeypatch.setattr(app, "llm_service_instance", test_llm)

    res = client.post('/api/ai/search', json={"query": "water bottle", "scope": "all"})
    assert res.status_code == 200
    data = res.get_json()
    assert data["api_key_configured"] is True
    assert data["status"] == "success"
    assert "Milton water bottle" in data["llm_response"]
    assert len(data["results"]) >= 1


def test_ai_search_with_mocked_openai_timeout(client, monkeypatch):
    from unittest.mock import MagicMock
    from openai import APITimeoutError
    import app
    import llm_service

    client.post('/api/items', json={
        "type": "found",
        "item_name": "Milton Water Bottle",
        "student_name": "Alice",
        "registration_number": "R1",
        "contact_number": "111",
        "contact_email": "a@col.edu"
    })

    mock_client = MagicMock()
    mock_client.chat.completions.create.side_effect = APITimeoutError(request=MagicMock())

    test_llm = llm_service.OpenAIRAGService()
    monkeypatch.setattr(test_llm, "api_key", "sk-mock-valid-key-for-test")
    monkeypatch.setattr(test_llm, "_get_openai_client", lambda: mock_client)
    monkeypatch.setattr(app, "llm_service_instance", test_llm)

    res = client.post('/api/ai/search', json={"query": "water bottle"})
    assert res.status_code == 200
    data = res.get_json()
    assert data["status"] == "timeout_error"
    assert "timed out" in data["llm_response"].lower()
    assert len(data["results"]) >= 1


def test_ai_search_with_mocked_openai_rate_limit(client, monkeypatch):
    from unittest.mock import MagicMock
    from openai import RateLimitError
    import app
    import llm_service

    client.post('/api/items', json={
        "type": "found",
        "item_name": "Milton Water Bottle",
        "student_name": "Alice",
        "registration_number": "R1",
        "contact_number": "111",
        "contact_email": "a@col.edu"
    })

    mock_client = MagicMock()
    mock_client.chat.completions.create.side_effect = RateLimitError(
        message="Rate limit reached", response=MagicMock(status_code=429), body=None
    )

    test_llm = llm_service.OpenAIRAGService()
    monkeypatch.setattr(test_llm, "api_key", "sk-mock-valid-key-for-test")
    monkeypatch.setattr(test_llm, "_get_openai_client", lambda: mock_client)
    monkeypatch.setattr(app, "llm_service_instance", test_llm)

    res = client.post('/api/ai/search', json={"query": "water bottle"})
    assert res.status_code == 200
    data = res.get_json()
    assert data["status"] == "rate_limited"
    assert "rate limit" in data["llm_response"].lower()
    assert len(data["results"]) >= 1


def test_ai_search_with_mocked_openai_auth_error(client, monkeypatch):
    from unittest.mock import MagicMock
    from openai import AuthenticationError
    import app
    import llm_service

    client.post('/api/items', json={
        "type": "found",
        "item_name": "Milton Water Bottle",
        "student_name": "Alice",
        "registration_number": "R1",
        "contact_number": "111",
        "contact_email": "a@col.edu"
    })

    mock_client = MagicMock()
    mock_client.chat.completions.create.side_effect = AuthenticationError(
        message="Invalid API Key", response=MagicMock(status_code=401), body=None
    )

    test_llm = llm_service.OpenAIRAGService()
    monkeypatch.setattr(test_llm, "api_key", "sk-mock-valid-key-for-test")
    monkeypatch.setattr(test_llm, "_get_openai_client", lambda: mock_client)
    monkeypatch.setattr(app, "llm_service_instance", test_llm)

    res = client.post('/api/ai/search', json={"query": "water bottle"})
    assert res.status_code == 200
    data = res.get_json()
    assert data["status"] == "auth_error"
    assert "invalid openai api key" in data["llm_response"].lower()
    assert len(data["results"]) >= 1


def test_ai_search_server_exception_returns_500_json(client, monkeypatch):
    import app

    def faulty_search(*args, **kwargs):
        raise RuntimeError("Simulated internal database crash")

    monkeypatch.setattr(app.rag_service_instance, "search", faulty_search)

    res = client.post('/api/ai/search', json={"query": "water bottle"})
    assert res.status_code == 500
    assert res.is_json
    data = res.get_json()
    assert data["success"] is False
    assert data["results"] == []


def test_delete_item_cleans_up_claims_and_chroma(client, monkeypatch):
    import app

    # Create an item
    res_item = client.post('/api/items', json={
        "type": "found",
        "item_name": "Calculator FX",
        "student_name": "Alice",
        "registration_number": "R1",
        "contact_number": "111",
        "contact_email": "a@col.edu"
    })
    item_id = res_item.get_json()["id"]

    # Create a claim
    res_claim = client.post('/api/claims', json={
        "item_id": item_id,
        "claimant_name": "Claimant Student",
        "claimant_contact": "555-1234",
        "claimant_email": "c@col.edu",
        "verification_details": "Silver battery cover"
    })
    assert res_claim.status_code == 201

    # Verify claim exists
    claims_before = client.get('/api/claims', headers={"X-Admin-Key": "campus_admin_secret_2026"}).get_json()
    assert any(c["item_id"] == item_id for c in claims_before)

    # Track chroma delete call
    deleted_chroma_ids = []
    original_delete = app.rag_service_instance.delete_item

    def tracking_delete(i_id):
        deleted_chroma_ids.append(i_id)
        original_delete(i_id)

    monkeypatch.setattr(app.rag_service_instance, "delete_item", tracking_delete)

    # Delete item as admin
    del_res = client.delete(f'/api/items/{item_id}', headers={"X-Admin-Key": "campus_admin_secret_2026"})
    assert del_res.status_code == 200

    # Verify claim is removed
    claims_after = client.get('/api/claims', headers={"X-Admin-Key": "campus_admin_secret_2026"}).get_json()
    assert not any(c["item_id"] == item_id for c in claims_after)

    # Verify chroma delete was called
    assert item_id in deleted_chroma_ids

