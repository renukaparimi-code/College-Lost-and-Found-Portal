# 🏛️ College Lost and Found Portal (GenAI & RAG Powered)

An intelligent, full-stack campus lost and found platform that reunites students with missing belongings using **Natural Language RAG (Retrieval-Augmented Generation)**, **ChromaDB Vector Embeddings**, and **OpenAI Large Language Models**.

Built on Python Flask, SQLite, ChromaDB, and modern responsive vanilla JavaScript.

---

## 🌟 Main Objective & Key Features

Help college students find lost belongings by describing items in simple, everyday natural language (e.g., *"I lost my dark-colored purse near the library yesterday"* or *"Found a blue water bottle in the classroom"*). The AI searches actual database records and identifies possible matches even when the student's wording differs from stored records.

1. **AI-Powered Natural Search Interface**:
   * Prominent natural language search box with clear button, loading indicator, and responsive layout for mobile and desktop.
   * Search scope filters: All Items, Looking for Found Items (I lost something), Looking for Lost Reports (I found something).
2. **Complete RAG Pipeline (Retrieval-Augmented Generation)**:
   * Uses an embedding model and **ChromaDB** vector database to convert descriptions and queries into high-dimensional vector representations.
   * Authoritative item records are retrieved directly from the SQLite database before generating responses, preventing hallucinated records.
   * Auto-synchronizes with the database whenever items are added, updated, or marked resolved.
3. **OpenAI LLM Integration**:
   * Uses official OpenAI API (`OPENAI_API_KEY`, defaulting to `gpt-4o-mini`).
   * **Truthful Status Handling**: If no API key is configured, the system displays a clear setup message rather than pretending the AI is working. Semantic vector search continues to operate using database records.
   * API keys are kept securely on the backend in environment variables and never exposed to frontend code or committed to Git.
4. **Context-Based Grounded AI Responses**:
   * Passes the student's query and verified database records to the LLM.
   * Generates a concise, factual summary explaining possible matches using **only** retrieved records.
   * Explicitly labels results as *possible matches*, never claiming confirmed ownership.
   * Prompt injection defense: treats all item descriptions and queries as untrusted data.
5. **Student Privacy Protection**:
   * Student contact numbers, emails, and registration numbers are strictly redacted from public item listings and vector embeddings (`"Verification Required"` / `"Protected"`).
   * Private details are only accessible to authorized campus staff with `X-Admin-Key`.
6. **Preserved Working Features**:
   * Reporting lost and found items, browsing feeds, automated candidate matching, and ownership verification claims remain fully intact.

---

## 🏗️ Architecture & Data Flow

```text
       Student Natural Language Query
   "I lost my dark-colored purse near the library"
                      │
                      ▼
         [ Embedding Generation ]
       (ChromaDB Vector Embeddings)
                      │
                      ▼
         [ Semantic Vector Search ]
      (Cosine Similarity across ChromaDB)
                      │
                      ▼
      [ Database Record Verification ]
      (Fetch Authoritative SQLite Records)
                      │
                      ▼
        [ Grounded Prompt Assembly ]
    (Query + Factual Context + Anti-Injection)
                      │
                      ▼
           [ OpenAI LLM Synthesis ]
          (Grounded Rationale Summary)
                      │
                      ▼
       [ Displayed UI Result Cards ]
 (AI Match Analysis + DB Details + Similarity %)
```

---

## 💻 Prerequisites & Setup (Windows PowerShell)

* **Operating System**: Windows 10/11
* **Python**: Python 3.10+ (Tested on Python 3.11)
* **Shell**: Windows PowerShell

### 1. Clone or Open Project Directory
```powershell
cd c:\Users\dabba\OneDrive\Desktop\College-Lost-and-Found-Portal-main
```

### 2. Create Virtual Environment
Using `uv` (recommended):
```powershell
uv venv .venv
```
Or using standard `python`:
```powershell
python -m venv .venv
```

### 3. Activate Virtual Environment
```powershell
.\.venv\Scripts\Activate.ps1
```
> *Note on Execution Policy*: If PowerShell blocks script activation (`running scripts is disabled`), run:
> ```powershell
> Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
> .\.venv\Scripts\Activate.ps1
> ```

### 4. Install Dependencies
```powershell
uv pip install -r requirements.txt
```
Or with standard pip:
```powershell
python -m pip install -r requirements.txt
```

### 5. Configure Environment Variables
Copy `.env.example` to `.env`:
```powershell
Copy-Item .env.example .env
```

Edit `.env` to configure your settings:
```ini
# Vector Database (ChromaDB)
CHROMA_PATH=chroma_data
CHROMA_COLLECTION=items_rag

# OpenAI LLM Integration
# Set your OpenAI API key here. NEVER commit this file with your real key!
OPENAI_API_KEY=your_actual_openai_api_key_here
OPENAI_MODEL=gpt-4o-mini
OPENAI_TIMEOUT=10

# SQLite Database Location
DATABASE_PATH=lost_found.db

# Admin Authorization Key for Claim Reviews and Item Status Changes
ADMIN_KEY=campus_admin_secret_2026
```

> **Note on OpenAI API Key**: If left empty, the portal operates in graceful offline mode: semantic vector search retrieves matching database items, and the UI displays a clear setup banner explaining how to configure your key.

---

## ▶️ Running the Application

Start the Flask server:
```powershell
.\.venv\Scripts\python app.py
```

Open your browser and navigate to:
```
http://127.0.0.1:5000/
```

---

## 🔍 Testing the AI-Powered Search

Try entering these sample natural language queries in the search box:

1. **Semantic Conceptual Matching**:
   * Query: `I lost my dark-colored purse near the library yesterday`
   * *Match*: Retrieves database records describing a **"Black leather wallet"** found at the library.
2. **Category & Location Proximity**:
   * Query: `I found a blue water bottle in the classroom`
   * *Match*: Retrieves records for a **"Milton Insulated Bottle"** or **"Blue Flask"**.
3. **Synonym Matching**:
   * Query: `Looking for my wireless earphones misplaced in cafeteria`
   * *Match*: Retrieves records for **"Bluetooth Earbuds"** or **"AirPods"** found near the canteen.
4. **Empty / Non-Existent Item**:
   * Query: `Lost a purple hoverboard in space`
   * *Response*: Clearly states that no matching items were found in the database.

---

## 🧪 Running Automated Tests

Run the full pytest suite (21 automated unit and integration tests):
```powershell
.\.venv\Scripts\python -m pytest tests/ -v
```

### Test Coverage Summary:
* `tests/test_rag_search.py` (7 tests):
  * Semantic vector matching (*dark purse* $\leftrightarrow$ *black wallet*).
  * Ranking relevant items above unrelated items.
  * Ensuring zero results when items do not match.
  * Empty search input validation.
  * Clear setup notice when `OPENAI_API_KEY` is unconfigured.
  * Exclusion of resolved items from vector search.
  * Prompt injection resistance and secret protection.
* `tests/test_api.py` (7 tests):
  * Static file serving and index route.
  * Form field validation and item creation.
  * Automated opposite-type matching (*lost* vs *found*).
  * Exclusion of lost-vs-lost matching.
  * Item resolution workflow with `PATCH /api/items/<id>/status`.
  * Claims submission and admin inspection with `ADMIN_KEY`.
* `tests/test_matching.py` (5 tests):
  * Text normalization and synonym expansion.
  * Privacy filtering in semantic item representations.
  * Attribute scoring (color, brand, location).
  * Grounded deterministic explanation fallback.
* `tests/test_privacy.py` (2 tests):
  * Student contact redaction on public endpoints.
  * Accurate dashboard database counts.
* `tests/test_admin_deletion_and_ai_errors.py` (18 tests):
  * Admin key verification (`POST /api/admin/verify`).
  * Rejection of unauthenticated visitors attempting deletion (`403 Forbidden`).
  * Prevention of student authorization bypasses (e.g. `isAdmin=true` spoofing).
  * Authorized item deletion and cascading cleanup of matches, claims, and ChromaDB vector embeddings.
  * 404 responses for nonexistent item deletions and 400 for invalid/negative IDs.
  * Verification that deleting an item does not affect unrelated records.
  * Mocked OpenAI success, timeout (`APITimeoutError`), rate limit (`RateLimitError`), and authentication error handling.
  * Safe 500 error handling returning predictable JSON for server exceptions.
* `tests/test_storage_and_render_config.py` (9 tests):
  * `DATA_DIR` persistent disk resolution for SQLite and ChromaDB (`/var/data`).
  * Explicit `DATABASE_PATH` and `CHROMA_PATH` environment overrides.
  * Resilient `RAGService` startup and graceful fallback on read-only filesystems.
  * Preventing ChromaDB from downloading ONNX models (`embedding_function=None`).
  * Safe item creation (HTTP 201) when vector store synchronization fails.
  * Seamless fallback to SQLite hybrid search when vector search encounters errors.
  * Graceful handling when `LLM_PROVIDER="none"`.
  * Production dependency verification (`gunicorn` in `requirements.txt`).
  * Prevention of exposed secrets in `.env.example`.

Total: **48 automated tests** covering security, API reliability, RAG retrieval, storage configuration, and AI matching.

---

## 📡 REST API Reference

| Method | Endpoint | Authorization | Description |
|---|---|---|---|
| `POST` | `/api/ai/search` | Public | **RAG Natural Language Search**: Vector search + OpenAI LLM synthesis |
| `GET` | `/api/items` | Public / Admin | List reported items (publicly redacted; `X-Admin-Key` reveals contacts) |
| `POST` | `/api/items` | Public | Report lost/found item; syncs with vector store & generates candidate matches |
| `DELETE` | `/api/items/<item_id>` | **Admin Only** | Deletes an item, cascades to matches & claims, and cleans up ChromaDB embeddings |
| `POST` | `/api/admin/verify` | Public (Key check) | Verifies administrator credentials using constant-time comparison |
| `PATCH` | `/api/items/<id>/status` | **Admin Only** | Update item status (`active`, `resolved`). Protected by `X-Admin-Key` |
| `GET` | `/api/matches` | Public | Retrieve candidate matches between lost and found items |
| `POST` | `/api/claims` | Public | Submit ownership verification claim with identifying marks |
| `GET` | `/api/claims` | **Admin Only** | Inspect submitted claims (Protected by `X-Admin-Key`) |
| `GET` | `/api/dashboard/stats` | Public | Real-time counts of lost, found, active, and resolved items |

---

## 🛡️ Admin Authorization & Item Deletion

1. **Staff Mode Access**: Campus administrators click the **Staff Login** button in the header and input their secret `ADMIN_KEY`.
2. **Server-Side Enforcement**: All state-changing admin actions (`DELETE /api/items/<id>`, `PATCH /api/items/<id>/status`, `GET /api/claims`) strictly enforce the `X-Admin-Key` header with constant-time `hmac.compare_digest` to prevent timing attacks.
3. **No Frontend Secrets**: The admin secret is never embedded in JavaScript or HTML.
4. **Relational & Vector Integrity**: Deleting an item removes the database record, referencing rows in `matches` and `claims`, and removes the item's embedding from ChromaDB.

---

## 🚀 Deployment on Render

The repository is fully configured for deployment as a **Web Service** on [Render](https://render.com):

### 1. Web Service Settings
* **Environment**: `Python 3`
* **Build Command**: `pip install -r requirements.txt`
* **Start Command**:
  ```bash
  gunicorn --workers 2 --timeout 120 --bind 0.0.0.0:$PORT app:app
  ```
  *(The `--timeout 120` prevents Gunicorn worker timeouts during cold starts and LLM completions).*

### 2. Render Persistent Disk (Data Persistence)
On cloud platforms like Render, application container instances have ephemeral storage by default (data resets on every new deploy or service restart). To permanently retain reported items and vector embeddings:

1. In the Render Dashboard, open your Web Service and navigate to **Disks**.
2. Click **Add a Disk**.
3. Set the following disk parameters:
   * **Name**: `portal-data`
   * **Mount Path**: `/var/data`
   * **Size**: `1 GB` (or as required)
4. Go to **Environment** settings and add the environment variable:
   * **`DATA_DIR`**: `/var/data`

When `DATA_DIR=/var/data` is configured, the application automatically places:
* **SQLite Database**: `/var/data/lost_found.db`
* **ChromaDB Vector Store**: `/var/data/chroma_data`

*(Note: If no persistent disk is mounted, the portal still operates reliably using ephemeral local storage in the service directory).*

### 3. Environment Variables (Render Dashboard)
Configure the following in your service's **Environment** tab:

| Variable | Recommended Production Value | Description |
|---|---|---|
| `DATA_DIR` | `/var/data` | Mount point for Render Persistent Disk |
| `OPENAI_API_KEY` | `sk-...` | Your OpenAI API key (kept confidential) |
| `OPENAI_MODEL` | `gpt-4o-mini` | Recommended OpenAI model |
| `OPENAI_TIMEOUT` | `10` | Timeout in seconds for OpenAI calls |
| `LLM_PROVIDER` | `openai` | LLM provider (`openai`, `gemini`, or `none`) |
| `ADMIN_KEY` | `your_secret_admin_password` | Authorization key for Staff Mode |
| `CHROMA_TELEMETRY` | `0` | Disables outbound telemetry to eliminate SSL timeouts |
| `FLASK_DEBUG` | `0` | Production mode (disabled debug) |

### 4. Zero External Embedding Downloads
ChromaDB is initialized with `embedding_function=None` and telemetry disabled, utilizing the built-in 384-dimensional domain vectorizer. It requires **zero external model downloads** (no 80MB ONNX downloads at runtime), eliminating container timeouts and SSL handshake issues.

---

## 🔒 Security & Privacy Guarantees

1. **No Hallucinated Items**: All search candidates originate directly from verified SQLite records (`lost_found.db`).
2. **Student Privacy**: Phone numbers, emails, and student registration IDs are excluded from vector embeddings and redacted from public API outputs.
3. **Anti-Prompt-Injection**: User queries and item descriptions are treated strictly as untrusted text within system prompts.
4. **No Premature Handover**: High match percentages are explicitly labeled as *potential matches*, directing students to submit verification claims for administrative approval.

