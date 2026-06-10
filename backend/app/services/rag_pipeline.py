"""
KisanMitra AI — RAG Pipeline & Knowledge Base Manager
====================================================
Handles document ingestion, embedding, and retrieval for the
agricultural knowledge base using ChromaDB and sentence-transformers.

Architecture:
1. Load markdown documents from knowledge_base/
2. Split into 512-token chunks with 50-token overlap
3. Embed with sentence-transformers (all-MiniLM-L6-v2)
4. Store in ChromaDB persistent collection
5. Retrieve top-k relevant chunks for any query
"""
import os
import re
import glob
from typing import List, Optional, Dict, Any

try:
    from langchain_text_splitters import RecursiveCharacterTextSplitter
    from langchain_chroma import Chroma
    from langchain_huggingface import HuggingFaceEmbeddings
    LANGCHAIN_AVAILABLE = True
except ImportError:
    try:
        # Fallback to older langchain-community paths
        from langchain.text_splitter import RecursiveCharacterTextSplitter
        from langchain_community.vectorstores import Chroma
        from langchain_community.embeddings import HuggingFaceEmbeddings
        LANGCHAIN_AVAILABLE = True
    except ImportError:
        LANGCHAIN_AVAILABLE = False
        print("⚠️ LangChain not installed. RAG pipeline will use fallback mode.")


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
_BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
KB_DIR = os.path.join(_BACKEND_DIR, "knowledge_base")
CHROMA_DIR = os.path.join(_BACKEND_DIR, "chroma_db")
EMBEDDING_MODEL = "sentence-transformers/all-MiniLM-L6-v2"

# Chunking config
CHUNK_SIZE = 512
CHUNK_OVERLAP = 50


# ---------------------------------------------------------------------------
# Knowledge Base Manager
# ---------------------------------------------------------------------------
class KnowledgeBaseManager:
    """Manages the agricultural knowledge base with vector search."""

    def __init__(self):
        self._vectorstore = None
        self._embeddings = None
        self._initialized = False

    @property
    def is_available(self) -> bool:
        return self._initialized and self._vectorstore is not None

    def initialize(self):
        """Load or create the vector store."""
        if not LANGCHAIN_AVAILABLE:
            print("⚠️ RAG not available — LangChain dependencies missing")
            return

        try:
            print("🧠 Initializing RAG knowledge base...")

            # Initialize embeddings
            self._embeddings = HuggingFaceEmbeddings(
                model_name=EMBEDDING_MODEL,
                model_kwargs={"device": "cpu"},
                encode_kwargs={"normalize_embeddings": True},
            )

            # Check if ChromaDB already has indexed data
            if os.path.exists(CHROMA_DIR) and os.listdir(CHROMA_DIR):
                print("📦 Loading existing ChromaDB index...")
                self._vectorstore = Chroma(
                    persist_directory=CHROMA_DIR,
                    embedding_function=self._embeddings,
                    collection_name="kisanmitra_kb",
                )
                count = self._vectorstore._collection.count()
                print(f"✅ Loaded {count} chunks from existing index")

                # Re-index if knowledge base has changed
                if self._needs_reindex():
                    print("🔄 Knowledge base changed — re-indexing...")
                    self._build_index()
            else:
                print("🔨 Building new ChromaDB index...")
                self._build_index()

            self._initialized = True
            print("✅ RAG knowledge base ready")

        except Exception as e:
            print(f"❌ RAG initialization failed: {e}")
            self._initialized = False

    def _needs_reindex(self) -> bool:
        """Check if the knowledge base files have changed since last index."""
        try:
            md_files = glob.glob(os.path.join(KB_DIR, "**", "*.md"), recursive=True)
            if not md_files:
                return False
            latest_file_time = max(os.path.getmtime(f) for f in md_files)

            # Compare with index creation time
            index_marker = os.path.join(CHROMA_DIR, ".index_timestamp")
            if os.path.exists(index_marker):
                index_time = os.path.getmtime(index_marker)
                return latest_file_time > index_time
            return True
        except Exception:
            return True

    def _build_index(self):
        """Load documents, chunk, embed, and store in ChromaDB."""
        if not os.path.exists(KB_DIR):
            print(f"⚠️ Knowledge base directory not found: {KB_DIR}")
            return

        # Load all markdown files
        md_files = glob.glob(os.path.join(KB_DIR, "**", "*.md"), recursive=True)
        if not md_files:
            print("⚠️ No markdown files found in knowledge base")
            return

        print(f"📄 Found {len(md_files)} knowledge base documents")

        # Load documents manually for better control
        documents = []
        for filepath in md_files:
            try:
                with open(filepath, "r", encoding="utf-8") as f:
                    content = f.read()

                # Extract category from path
                rel_path = os.path.relpath(filepath, KB_DIR)
                category = os.path.dirname(rel_path).replace(os.sep, "/")
                filename = os.path.basename(filepath)

                from langchain_core.documents import Document

                # Extract state/district from metadata header
                state, district = self._extract_location_metadata(content)

                doc = Document(
                    page_content=content,
                    metadata={
                        "source": filepath,
                        "category": category,
                        "filename": filename,
                        "state": state or "",
                        "district": district or "",
                    },
                )
                documents.append(doc)
                print(f"  📖 Loaded: {rel_path} [state={state or '-'}, district={district or '-'}]")
            except Exception as e:
                print(f"  ❌ Failed to load {filepath}: {e}")

        if not documents:
            print("⚠️ No documents loaded")
            return

        # Split into chunks
        text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=CHUNK_SIZE,
            chunk_overlap=CHUNK_OVERLAP,
            separators=["\n## ", "\n### ", "\n\n", "\n", ". ", " "],
            length_function=len,
        )
        chunks = text_splitter.split_documents(documents)
        print(f"✂️ Split into {len(chunks)} chunks")

        # Create ChromaDB vector store
        self._vectorstore = Chroma.from_documents(
            documents=chunks,
            embedding=self._embeddings,
            persist_directory=CHROMA_DIR,
            collection_name="kisanmitra_kb",
        )

        # Write timestamp marker
        index_marker = os.path.join(CHROMA_DIR, ".index_timestamp")
        os.makedirs(CHROMA_DIR, exist_ok=True)
        with open(index_marker, "w") as f:
            f.write(str(os.path.getmtime(md_files[-1])))

        print(f"✅ Indexed {len(chunks)} chunks into ChromaDB")

    def search(self, query: str, k: int = 4) -> List[Dict[str, Any]]:
        """
        Search the knowledge base for relevant information.

        Returns list of dicts with 'content', 'source', 'category', 'score'.
        """
        if not self.is_available:
            return []

        try:
            results = self._vectorstore.similarity_search_with_score(query, k=k)
            return [
                {
                    "content": doc.page_content,
                    "source": doc.metadata.get("filename", "unknown"),
                    "category": doc.metadata.get("category", "unknown"),
                    "score": float(score),
                }
                for doc, score in results
            ]
        except Exception as e:
            print(f"❌ RAG search error: {e}")
            return []

    def get_context_for_query(self, query: str, k: int = 3) -> str:
        """
        Get a formatted context string from the knowledge base for
        injection into the LLM prompt.
        """
        results = self.search(query, k=k)
        if not results:
            return ""

        context_parts = []
        for i, r in enumerate(results, 1):
            context_parts.append(
                f"[Source {i}: {r['source']} ({r['category']})]\n{r['content']}"
            )
        return "\n\n---\n\n".join(context_parts)

    def search_with_location(
        self,
        query: str,
        state: Optional[str] = None,
        district: Optional[str] = None,
        k: int = 4,
    ) -> List[Dict[str, Any]]:
        """
        Search with location-aware filtering.

        Priority:
        1. Documents matching user's district (if available)
        2. Documents matching user's state
        3. General documents (no location filter)

        Returns combined results, deduplicated, up to k items.
        """
        if not self.is_available:
            return []

        results = []
        seen_contents = set()

        try:
            # Tier 1: District-specific results
            if district:
                district_results = self._filtered_search(
                    query, {"district": district}, k=2
                )
                for r in district_results:
                    key = r["content"][:100]
                    if key not in seen_contents:
                        r["relevance"] = "district"
                        results.append(r)
                        seen_contents.add(key)

            # Tier 2: State-specific results
            if state and len(results) < k:
                state_results = self._filtered_search(
                    query, {"state": state}, k=k - len(results)
                )
                for r in state_results:
                    key = r["content"][:100]
                    if key not in seen_contents:
                        r["relevance"] = "state"
                        results.append(r)
                        seen_contents.add(key)

            # Tier 3: General results (fill remaining slots)
            if len(results) < k:
                general_results = self.search(query, k=k - len(results))
                for r in general_results:
                    key = r["content"][:100]
                    if key not in seen_contents:
                        r["relevance"] = "general"
                        results.append(r)
                        seen_contents.add(key)

        except Exception as e:
            print(f"❌ Location-aware search error: {e}")
            # Fallback to basic search
            return self.search(query, k=k)

        return results[:k]

    def _filtered_search(
        self, query: str, where_filter: Dict[str, str], k: int = 3
    ) -> List[Dict[str, Any]]:
        """Search ChromaDB with metadata filter."""
        if not self.is_available or k <= 0:
            return []

        try:
            results = self._vectorstore.similarity_search_with_score(
                query, k=k, filter=where_filter
            )
            return [
                {
                    "content": doc.page_content,
                    "source": doc.metadata.get("filename", "unknown"),
                    "category": doc.metadata.get("category", "unknown"),
                    "state": doc.metadata.get("state", ""),
                    "district": doc.metadata.get("district", ""),
                    "score": float(score),
                }
                for doc, score in results
            ]
        except Exception as e:
            # ChromaDB may return error if no docs match the filter
            return []

    def get_context_for_query_with_location(
        self,
        query: str,
        state: Optional[str] = None,
        district: Optional[str] = None,
        k: int = 3,
    ) -> str:
        """
        Get formatted context string with location-aware filtering.
        """
        results = self.search_with_location(query, state, district, k)
        if not results:
            return ""

        context_parts = []
        for i, r in enumerate(results, 1):
            loc_tag = ""
            if r.get("district"):
                loc_tag = f" | {r['district']}, {r.get('state', '')}"
            elif r.get("state"):
                loc_tag = f" | {r['state']}"
            context_parts.append(
                f"[Source {i}: {r['source']} ({r['category']}{loc_tag})]\n{r['content']}"
            )
        return "\n\n---\n\n".join(context_parts)

    @staticmethod
    def _extract_location_metadata(content: str) -> tuple:
        """
        Extract state and district from document content.
        Looks for YAML-style metadata headers like:
            state: UP
            district: Lucknow
        """
        state = None
        district = None

        # Check first 500 chars for metadata
        header = content[:500]

        state_match = re.search(r"^state:\s*(.+)$", header, re.MULTILINE | re.IGNORECASE)
        if state_match:
            state = state_match.group(1).strip()

        district_match = re.search(r"^district:\s*(.+)$", header, re.MULTILINE | re.IGNORECASE)
        if district_match:
            district = district_match.group(1).strip()

        # Also try extracting from directory path in the content
        # Documents from ingestion have paths like contingency/UP/lucknow.md
        path_match = re.search(r"(?:contingency|weather)/(\w{2})/", content[:200])
        if path_match and not state:
            state = path_match.group(1).upper()

        return state, district


# ---------------------------------------------------------------------------
# Singleton instance
# ---------------------------------------------------------------------------
_kb_manager = KnowledgeBaseManager()


def get_knowledge_base() -> KnowledgeBaseManager:
    """Get the knowledge base manager singleton."""
    if not _kb_manager._initialized:
        _kb_manager.initialize()
    return _kb_manager
