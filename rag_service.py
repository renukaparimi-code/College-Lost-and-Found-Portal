import os
import re
import numpy as np
import chromadb
from chromadb.config import Settings
from sklearn.feature_extraction.text import HashingVectorizer
import config
from ai_matcher import HybridAIMatcher, normalize_text, expand_synonyms

class RAGService:
    """
    Retrieval-Augmented Generation (RAG) vector service.
    Indexes lost and found items in ChromaDB using vector embeddings,
    synchronizes with SQLite records, and executes semantic retrieval.
    """

    def __init__(self, chroma_path: str = None, collection_name: str = None, in_memory: bool = False):
        self.chroma_path = chroma_path or config.CHROMA_PATH
        self.collection_name = collection_name or config.CHROMA_COLLECTION
        self.in_memory = in_memory
        self.matcher = HybridAIMatcher()
        self.vectorizer = HashingVectorizer(n_features=384, norm='l2', alternate_sign=False)
        self.client = None
        self._collection = None
        # In test environments with in_memory=True, initialize immediately
        if self.in_memory or self.chroma_path == ":memory:":
            self._init_chroma()

    @property
    def collection(self):
        """Lazy loads Chroma collection inside the active worker process to prevent Gunicorn fork deadlocks."""
        if self._collection is None:
            self._init_chroma()
        return self._collection

    @collection.setter
    def collection(self, val):
        self._collection = val

    def embed_text(self, text: str) -> list:
        """Generates a fast normalized 384-dimensional semantic embedding with domain expansion."""
        expanded = expand_synonyms(text or "")
        matrix = self.vectorizer.transform([expanded]).toarray().astype(np.float32)
        return matrix[0].tolist()

    def embed_batch(self, texts: list) -> list:
        """Generates embeddings for a batch of text documents."""
        expanded = [expand_synonyms(t or "") for t in texts]
        matrix = self.vectorizer.transform(expanded).toarray().astype(np.float32)
        return matrix.tolist()

    def _init_chroma(self):
        """Initializes ChromaDB client and collection with safe error handling."""
        settings = Settings(anonymized_telemetry=False)
        if self.in_memory or self.chroma_path == ":memory:":
            self.client = chromadb.EphemeralClient(settings=settings)
        else:
            try:
                os.makedirs(self.chroma_path, exist_ok=True)
                persistent_settings = Settings(anonymized_telemetry=False, is_persistent=True)
                self.client = chromadb.PersistentClient(path=self.chroma_path, settings=persistent_settings)
            except (OSError, Exception) as e:
                # E.g. Errno 30 Read-only file system or permission error
                print(f"Warning: Chroma storage path '{self.chroma_path}' not accessible ({e}). Using in-memory client.")
                self.in_memory = True
                self.client = chromadb.EphemeralClient(settings=settings)

        try:
            # Explicitly pass embedding_function=None to prevent ChromaDB from attempting
            # to download the ~80MB ONNX all-MiniLM-L6-v2 model over the network.
            self.collection = self.client.get_or_create_collection(
                name=self.collection_name,
                metadata={"hnsw:space": "cosine"},
                embedding_function=None
            )
        except Exception as e:
            print(f"Warning: Chroma collection initialization error: {e}")
            self.collection = None

    def build_item_document(self, item: dict) -> str:
        """
        Builds a privacy-safe, high-information semantic document for embedding.
        NEVER includes student names, registration numbers, or contact details.
        """
        parts = []
        item_name = item.get("item_name") or item.get("name") or "Unknown Item"
        parts.append(f"Item: {item_name}")

        category = item.get("category")
        if category and str(category).lower() != "other":
            parts.append(f"Category: {category}")

        item_type = item.get("type")
        if item_type:
            parts.append(f"Type: {item_type}")

        color = item.get("color")
        if color:
            parts.append(f"Color: {color}")

        brand = item.get("brand")
        if brand:
            parts.append(f"Brand: {brand}")

        distinctive = item.get("distinctive_features")
        if distinctive:
            parts.append(f"Features: {distinctive}")

        location = item.get("location")
        if location:
            parts.append(f"Location: {location}")

        desc = item.get("description")
        if desc:
            parts.append(f"Description: {desc}")

        item_date = item.get("item_date") or item.get("reported_at")
        if item_date:
            parts.append(f"Date: {str(item_date)[:10]}")

        status = item.get("status")
        if status:
            parts.append(f"Status: {status}")

        return " | ".join(parts)

    def sync_item(self, item: dict):
        """Adds or updates a single item in the ChromaDB vector collection."""
        if not item or "id" not in item or self.collection is None:
            return

        try:
            item_id = str(item["id"])
            doc = self.build_item_document(item)
            metadata = {
                "id": int(item["id"]),
                "type": str(item.get("type", "lost")).lower(),
                "status": str(item.get("status", "active")).lower(),
                "category": str(item.get("category") or "Other"),
                "location": str(item.get("location") or "")
            }
            emb = self.embed_text(doc)

            self.collection.upsert(
                ids=[item_id],
                documents=[doc],
                metadatas=[metadata],
                embeddings=[emb]
            )
        except Exception as e:
            print(f"Notice: Vector store sync deferred: {e}")

    def delete_item(self, item_id: int):
        """Removes an item from the vector store."""
        if self.collection is None:
            return
        try:
            self.collection.delete(ids=[str(item_id)])
        except Exception:
            pass

    def sync_all_from_db(self, db_conn):
        """Synchronizes all active records from SQLite into ChromaDB."""
        if self.collection is None or db_conn is None:
            return 0
        try:
            cursor = db_conn.cursor()
            cursor.execute("SELECT * FROM items")
            rows = cursor.fetchall()

            if not rows:
                return 0

            ids = []
            docs = []
            metadatas = []

            for row in rows:
                item = dict(row)
                item_id = str(item["id"])
                ids.append(item_id)
                docs.append(self.build_item_document(item))
                metadatas.append({
                    "id": int(item["id"]),
                    "type": str(item.get("type", "lost")).lower(),
                    "status": str(item.get("status", "active")).lower(),
                    "category": str(item.get("category") or "Other"),
                    "location": str(item.get("location") or "")
                })

            if ids:
                embs = self.embed_batch(docs)
                self.collection.upsert(
                    ids=ids,
                    documents=docs,
                    metadatas=metadatas,
                    embeddings=embs
                )
            return len(ids)
        except Exception as e:
            print(f"Notice: Vector store batch sync deferred: {e}")
            return 0

    def parse_intent(self, query: str) -> str:
        """
        Infers whether the student is looking for a 'lost' item or reporting a 'found' item.
        - If query indicates student lost an item -> search among 'found' items.
        - If query indicates student found an item -> search among 'lost' items.
        - Otherwise returns 'all'.
        """
        q = query.lower()
        # "I lost...", "lost my...", "looking for my...", "missing..."
        lost_patterns = [
            r"\bi\s+lost\b", r"\blost\s+my\b", r"\blooking\s+for\s+my\b",
            r"\bmy\s+.*\s+is\s+lost\b", r"\bmisplaced\b", r"\bleft\s+behind\b",
            r"\bwhere\s+is\s+my\b"
        ]
        # "I found...", "found a...", "picked up..."
        found_patterns = [
            r"\bi\s+found\b", r"\bfound\s+a\b", r"\bfound\s+an\b",
            r"\bpicked\s+up\b", r"\bsomeone\s+left\b"
        ]

        for p in lost_patterns:
            if re.search(p, q):
                return "found"  # Student lost something, search FOUND items!

        for p in found_patterns:
            if re.search(p, q):
                return "lost"   # Student found something, search LOST reports!

        return "all"

    def _fallback_sqlite_search(self, query: str, target_type: str, top_k: int, db_conn) -> list:
        """
        Fallback search executing hybrid semantic matching directly against SQLite database records.
        Guarantees student search never breaks if vector database is unavailable or degraded.
        """
        if not db_conn:
            return []
        try:
            cursor = db_conn.cursor()
            if target_type:
                cursor.execute("SELECT * FROM items WHERE status = 'active' AND type = ?", (target_type,))
                rows = cursor.fetchall()
            else:
                rows = []

            if not rows:
                cursor.execute("SELECT * FROM items WHERE status = 'active'")
                rows = cursor.fetchall()

            if not rows:
                return []

            query_item = {
                'item_name': query,
                'description': query,
                'location': query
            }

            ranked = []
            for row in rows:
                item = dict(row)
                score_data = self.matcher.score_pair(query_item, item)
                score = score_data['similarity_score']
                if score >= config.SIMILARITY_THRESHOLD:
                    ranked.append({
                        "id": item["id"],
                        "type": item["type"],
                        "item_name": item["item_name"],
                        "category": item.get("category") or "Other",
                        "description": item.get("description") or "",
                        "color": item.get("color") or "",
                        "brand": item.get("brand") or "",
                        "distinctive_features": item.get("distinctive_features") or "",
                        "location": item.get("location") or "Not specified",
                        "item_date": item.get("item_date") or (item.get("reported_at", "")[:10] if item.get("reported_at") else "Not specified"),
                        "status": item.get("status") or "active",
                        "reported_at": item.get("reported_at", ""),
                        "similarity_score": score,
                        "confidence": score_data.get('confidence', 'Possible match'),
                        "evidence": score_data.get('evidence', [])
                    })

            ranked.sort(key=lambda x: x["similarity_score"], reverse=True)
            return ranked[:top_k]
        except Exception as e:
            print(f"Notice: SQLite fallback search error: {e}")
            return []

    def search(self, query: str, scope: str = "all", top_k: int = 5, db_conn = None) -> list:
        """
        Executes semantic vector search against ChromaDB and verifies against SQLite database.
        Returns candidate items ranked by calibrated similarity score.
        """
        if not query or not query.strip():
            return []

        cleaned_query = query.strip()

        # Determine target item type
        target_type = None
        if scope in ("lost", "found"):
            target_type = scope
        else:
            inferred = self.parse_intent(cleaned_query)
            if inferred in ("lost", "found"):
                target_type = inferred

        # If ChromaDB collection is not available, immediately use robust SQLite hybrid search
        if self.collection is None:
            return self._fallback_sqlite_search(cleaned_query, target_type, top_k, db_conn)

        # Attempt vector search via ChromaDB
        results = None
        try:
            # If ChromaDB is empty and DB connection is provided, auto-sync
            if self.collection.count() == 0 and db_conn:
                self.sync_all_from_db(db_conn)

            col_count = self.collection.count()
            if col_count > 0:
                q_emb = self.embed_text(cleaned_query)
                where_filter = {"status": "active"}
                if target_type:
                    where_filter = {
                        "$and": [
                            {"status": "active"},
                            {"type": target_type}
                        ]
                    }

                n_results = min(top_k * 3, max(1, col_count))

                if target_type and scope != "all":
                    try:
                        results = self.collection.query(
                            query_embeddings=[q_emb],
                            n_results=n_results,
                            where=where_filter
                        )
                    except Exception:
                        results = None
                elif target_type and scope == "all":
                    try:
                        results = self.collection.query(
                            query_embeddings=[q_emb],
                            n_results=n_results,
                            where=where_filter
                        )
                    except Exception:
                        results = None

                    if not results or not results.get("ids") or not results["ids"][0]:
                        try:
                            results = self.collection.query(
                                query_embeddings=[q_emb],
                                n_results=n_results,
                                where={"status": "active"}
                            )
                        except Exception:
                            results = None
                else:
                    try:
                        results = self.collection.query(
                            query_embeddings=[q_emb],
                            n_results=n_results,
                            where={"status": "active"}
                        )
                    except Exception:
                        results = None

                if not results or not results.get("ids") or not results["ids"][0]:
                    try:
                        results = self.collection.query(
                            query_embeddings=[q_emb],
                            n_results=n_results
                        )
                    except Exception:
                        results = None
        except Exception as e:
            print(f"Notice: ChromaDB search failed, activating SQLite fallback: {e}")
            results = None

        if not results or not results.get("ids") or not results["ids"][0]:
            # Graceful fallback to SQLite hybrid matching
            return self._fallback_sqlite_search(cleaned_query, target_type, top_k, db_conn)

        retrieved_ids = []
        retrieved_distances = {}
        try:
            if results and isinstance(results, dict) and results.get("ids") and len(results["ids"]) > 0:
                id_list = results["ids"][0] or []
                dist_list = (results.get("distances") or [[]])[0] if results.get("distances") else []
                for idx, id_str in enumerate(id_list):
                    try:
                        item_id = int(id_str)
                        retrieved_ids.append(item_id)
                        if idx < len(dist_list) and dist_list[idx] is not None:
                            dist = float(dist_list[idx])
                            # In ChromaDB cosine space: distance in [0, 2], similarity = 1 - (dist / 2)
                            similarity = max(0.0, min(1.0, 1.0 - (dist / 2.0)))
                        else:
                            similarity = 0.5
                        retrieved_distances[item_id] = similarity
                    except (ValueError, TypeError):
                        continue
        except Exception as e:
            print(f"Notice: Result distance parsing exception: {e}")

        if not retrieved_ids or not db_conn:
            return self._fallback_sqlite_search(cleaned_query, target_type, top_k, db_conn)

        # Retrieve authoritative SQLite database records
        try:
            cursor = db_conn.cursor()
            placeholders = ",".join("?" for _ in retrieved_ids)
            cursor.execute(f"SELECT * FROM items WHERE id IN ({placeholders}) AND status = 'active'", retrieved_ids)
            db_items = [dict(row) for row in cursor.fetchall()]
        except Exception as e:
            print(f"Notice: Authoritative record retrieval error: {e}")
            return self._fallback_sqlite_search(cleaned_query, target_type, top_k, db_conn)

        if not db_items:
            return self._fallback_sqlite_search(cleaned_query, target_type, top_k, db_conn)

        ranked_results = []
        for item in db_items:
            item_id = item["id"]
            vector_sim = retrieved_distances.get(item_id, 0.5)

            # Attribute verification & evidence generation using HybridAIMatcher
            # Create a mock query item for attribute comparison
            query_doc = {"item_name": cleaned_query, "description": cleaned_query, "location": cleaned_query}
            attr_eval = self.matcher.evaluate_structured_attributes(query_doc, item)

            evidence = list(attr_eval["evidence"])
            
            # Check location proximity from text query
            item_loc = normalize_text(item.get("location") or "")
            if item_loc and item_loc in normalize_text(cleaned_query):
                evidence.append(f"Location match: {item.get('location')}")

            # Check category match
            item_cat = normalize_text(item.get("category") or "")
            if item_cat and item_cat != "other" and item_cat in normalize_text(cleaned_query):
                evidence.append(f"Category: {item.get('category')}")

            # Combined score: vector similarity + attribute boost
            combined_score = vector_sim + attr_eval["boost"]
            calibrated_score = round(max(0.05, min(0.96, combined_score)), 3)

            # Confidence label
            if calibrated_score >= config.STRONG_MATCH_THRESHOLD:
                confidence = "Strong potential match"
            elif calibrated_score >= config.POSSIBLE_MATCH_THRESHOLD:
                confidence = "Possible match"
            else:
                confidence = "Low similarity"

            if not evidence and calibrated_score >= config.SIMILARITY_THRESHOLD:
                evidence.append("Semantic similarity between search query and item description")

            item_result = {
                "id": item["id"],
                "type": item["type"],
                "item_name": item["item_name"],
                "category": item.get("category") or "Other",
                "description": item.get("description") or "",
                "color": item.get("color") or "",
                "brand": item.get("brand") or "",
                "distinctive_features": item.get("distinctive_features") or "",
                "location": item.get("location") or "Not specified",
                "item_date": item.get("item_date") or item.get("reported_at", "")[:10],
                "status": item.get("status") or "active",
                "reported_at": item.get("reported_at", ""),
                "similarity_score": calibrated_score,
                "confidence": confidence,
                "evidence": evidence
            }
            ranked_results.append(item_result)

        # Sort by similarity_score descending
        ranked_results.sort(key=lambda x: x["similarity_score"], reverse=True)
        return ranked_results[:top_k]

# Global singleton
rag_service_instance = RAGService()
