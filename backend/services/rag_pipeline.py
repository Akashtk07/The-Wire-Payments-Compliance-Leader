"""
RAG (Retrieval-Augmented Generation) Pipeline.

Handles document ingestion (PDF, PPTX, DOCX, XML/TXT), chunking, embedding
via sentence-transformers, and storage in ChromaDB. Supports querying with
LLM-synthesised answers.

Singleton instance `rag_pipeline` is exported at module bottom.
"""

from __future__ import annotations

import os
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import structlog

from config import settings
from services.llm_router import llm_router

log = structlog.get_logger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

CHUNK_TOKENS = 512
OVERLAP_TOKENS = 64
EMBED_MODEL_NAME = "all-MiniLM-L6-v2"
COLLECTION_NAME = "compliance_docs"

# ---------------------------------------------------------------------------
# Lazy singletons for heavy dependencies
# ---------------------------------------------------------------------------

_embed_model = None
_chroma_client = None
_collection = None


def _get_embed_model():
    global _embed_model
    if _embed_model is None:
        try:
            from sentence_transformers import SentenceTransformer  # type: ignore
            _embed_model = SentenceTransformer(EMBED_MODEL_NAME)
            log.info("embed_model_loaded", model=EMBED_MODEL_NAME)
        except ImportError as exc:
            raise RuntimeError(
                "sentence-transformers is not installed. "
                "Run: pip install --prefer-binary -r requirements.txt\n"
                f"Original error: {exc}"
            ) from exc
    return _embed_model


def _get_collection():
    global _chroma_client, _collection
    if _collection is None:
        try:
            import chromadb  # type: ignore
            _chroma_client = chromadb.PersistentClient(path=settings.CHROMA_PERSIST_DIR)
            _collection = _chroma_client.get_or_create_collection(
                name=COLLECTION_NAME,
                metadata={"hnsw:space": "cosine"},
            )
            log.info("chromadb_collection_ready", collection=COLLECTION_NAME)
        except ImportError as exc:
            raise RuntimeError(
                "chromadb is not installed or failed to load its native library. "
                "Run: pip install 'chromadb>=0.6.0'\n"
                f"Original error: {exc}"
            ) from exc
        except Exception as exc:
            raise RuntimeError(
                f"ChromaDB failed to initialize at path '{settings.CHROMA_PERSIST_DIR}': {exc}"
            ) from exc
    return _collection


# ---------------------------------------------------------------------------
# Text extraction helpers
# ---------------------------------------------------------------------------


def _extract_text_pdf(file_path: str) -> List[Tuple[str, int]]:
    """Extract (text, page_num) pairs from a PDF using PyMuPDF."""
    import fitz  # PyMuPDF  # type: ignore
    doc = fitz.open(file_path)
    pages: List[Tuple[str, int]] = []
    for page_num, page in enumerate(doc, start=1):
        text = page.get_text()
        if text.strip():
            pages.append((text, page_num))
    doc.close()
    return pages


def _extract_text_pptx(file_path: str) -> List[Tuple[str, int]]:
    """Extract (text, slide_num) pairs from a PowerPoint file."""
    from pptx import Presentation  # type: ignore
    prs = Presentation(file_path)
    slides: List[Tuple[str, int]] = []
    for idx, slide in enumerate(prs.slides, start=1):
        parts: List[str] = []
        for shape in slide.shapes:
            if shape.has_text_frame:
                for para in shape.text_frame.paragraphs:
                    line = " ".join(run.text for run in para.runs).strip()
                    if line:
                        parts.append(line)
        if parts:
            slides.append(("\n".join(parts), idx))
    return slides


def _extract_text_docx(file_path: str) -> List[Tuple[str, int]]:
    """Extract text from a DOCX file (single 'page' grouping)."""
    from docx import Document  # type: ignore
    doc = Document(file_path)
    paragraphs = [p.text for p in doc.paragraphs if p.text.strip()]
    return [("\n".join(paragraphs), 1)]


def _extract_text_plain(file_path: str) -> List[Tuple[str, int]]:
    """Read plain text / XML file as-is."""
    with open(file_path, "r", encoding="utf-8", errors="replace") as fh:
        return [(fh.read(), 1)]


def _extract_text(file_path: str) -> List[Tuple[str, int]]:
    """Dispatch to the correct extractor based on file extension."""
    ext = Path(file_path).suffix.lower()
    if ext == ".pdf":
        return _extract_text_pdf(file_path)
    elif ext == ".pptx":
        return _extract_text_pptx(file_path)
    elif ext in (".docx",):
        return _extract_text_docx(file_path)
    else:  # .xml, .txt, and fallback
        return _extract_text_plain(file_path)


# ---------------------------------------------------------------------------
# Chunking
# ---------------------------------------------------------------------------


def _chunk_text(
    text: str,
    page_num: int,
    chunk_tokens: int = CHUNK_TOKENS,
    overlap_tokens: int = OVERLAP_TOKENS,
) -> List[Dict[str, Any]]:
    """
    Naïve word-based chunking (approximates tokens as words).
    Returns list of {text, page_num, chunk_index} dicts.
    """
    words = text.split()
    chunks: List[Dict[str, Any]] = []
    step = chunk_tokens - overlap_tokens
    idx = 0
    chunk_index = 0
    while idx < len(words):
        chunk_words = words[idx : idx + chunk_tokens]
        chunks.append(
            {
                "text": " ".join(chunk_words),
                "page_num": page_num,
                "chunk_index": chunk_index,
            }
        )
        idx += step
        chunk_index += 1
    return chunks


# ---------------------------------------------------------------------------
# RAGPipeline
# ---------------------------------------------------------------------------


class RAGPipeline:
    """Multi-format document ingestor and RAG query engine."""

    # ------------------------------------------------------------------
    # Ingestion
    # ------------------------------------------------------------------

    async def ingest(
        self,
        file_path: str,
        filename: str,
        doc_id: str,
        guideline_version: str = "Unclassified",
        guideline_category: str = "Custom",
        tags: str = "",
    ) -> int:
        """
        Ingest a document into ChromaDB.
        Returns the number of chunks indexed.
        """
        log.info("rag_ingest_start", filename=filename, doc_id=doc_id)

        # Extract text
        pages = _extract_text(file_path)
        if not pages:
            log.warning("rag_ingest_empty", filename=filename)
            return 0

        # Chunk all pages
        all_chunks: List[Dict[str, Any]] = []
        for text, page_num in pages:
            chunks = _chunk_text(text, page_num)
            all_chunks.extend(chunks)

        if not all_chunks:
            return 0

        # Embed
        model = _get_embed_model()
        texts = [c["text"] for c in all_chunks]
        embeddings = model.encode(texts, show_progress_bar=False).tolist()

        # Store in ChromaDB
        collection = _get_collection()
        ids = [f"{doc_id}_chunk_{c['chunk_index']}_page_{c['page_num']}" for c in all_chunks]
        metadatas = [
            {
                "doc_id": doc_id,
                "filename": filename,
                "chunk_index": c["chunk_index"],
                "page_num": c["page_num"],
                "guideline_version": guideline_version,
                "guideline_category": guideline_category,
                "tags": tags,
            }
            for c in all_chunks
        ]

        # ChromaDB upsert in batches of 256 to avoid payload limits
        batch_size = 256
        for i in range(0, len(ids), batch_size):
            collection.upsert(
                ids=ids[i : i + batch_size],
                embeddings=embeddings[i : i + batch_size],
                documents=texts[i : i + batch_size],
                metadatas=metadatas[i : i + batch_size],
            )

        log.info("rag_ingest_complete", filename=filename, chunks=len(all_chunks))
        return len(all_chunks)

    # ------------------------------------------------------------------
    # Query
    # ------------------------------------------------------------------

    async def query(
        self,
        question: str,
        top_k: int = 5,
        version_filter: Optional[List[str]] = None,
    ) -> Tuple[str, List[Dict[str, Any]]]:
        """
        Embed question, retrieve top_k chunks (optionally filtered by guideline
        version), synthesise answer with LLM.
        Returns (answer_text, list_of_source_metadata_dicts).
        """
        model = _get_embed_model()
        question_embedding = model.encode([question], show_progress_bar=False).tolist()[0]

        collection = _get_collection()

        # Build optional version where-clause for ChromaDB
        query_kwargs: Dict[str, Any] = {
            "query_embeddings": [question_embedding],
            "n_results": min(top_k, collection.count() or 1),
            "include": ["documents", "metadatas", "distances"],
        }
        if version_filter and len(version_filter) > 0:
            if len(version_filter) == 1:
                query_kwargs["where"] = {"guideline_version": {"$eq": version_filter[0]}}
            else:
                query_kwargs["where"] = {
                    "guideline_version": {"$in": version_filter}
                }

        results = collection.query(**query_kwargs)

        docs: List[str] = results.get("documents", [[]])[0]
        metas: List[Dict[str, Any]] = results.get("metadatas", [[]])[0]

        if not docs:
            return (
                "No relevant documents found in the knowledge base. "
                "Please upload relevant compliance documents first.",
                [],
            )

        # Build context string
        context_parts = []
        for i, (doc_text, meta) in enumerate(zip(docs, metas), start=1):
            context_parts.append(
                f"[Source {i} — {meta.get('filename','unknown')}, "
                f"Page {meta.get('page_num','?')}, "
                f"Chunk {meta.get('chunk_index','?')}]\n{doc_text}"
            )
        context = "\n\n---\n\n".join(context_parts)

        answer = await llm_router.query(
            question, context=context, version_context=version_filter
        )

        return answer, metas

    # ------------------------------------------------------------------
    # Cross-version compare
    # ------------------------------------------------------------------

    async def query_cross_version(
        self,
        question: str,
        selected_versions: List[str],
        top_k: int = 4,
    ) -> Dict[str, Any]:
        """
        Run the same query across each selected version separately, then
        synthesise a combined answer that highlights differences.
        Returns per-version answers + unified comparison.
        """
        per_version: Dict[str, Any] = {}
        for version in selected_versions:
            answer, sources = await self.query(question, top_k=top_k, version_filter=[version])
            per_version[version] = {"answer": answer, "sources": sources}

        # Build a combined context for the comparison prompt
        comparison_ctx = "\n\n".join(
            f"=== {v} ===\n{data['answer']}" for v, data in per_version.items()
        )
        comparison_prompt = (
            f"Compare how the following guideline versions answer this question:\n"
            f"Question: {question}\n\n"
            f"{comparison_ctx}\n\n"
            f"Summarise the KEY DIFFERENCES between versions. "
            f"Use format: '⚠️ Changed in [VERSION]: ...' for each difference found."
        )
        unified_answer = await llm_router.query(comparison_prompt, context="", version_context=selected_versions)
        return {
            "per_version": per_version,
            "unified_comparison": unified_answer,
            "versions_compared": selected_versions,
        }

    # ------------------------------------------------------------------
    # List documents
    # ------------------------------------------------------------------

    async def list_documents(self) -> List[Dict[str, Any]]:
        """Return distinct documents currently indexed in ChromaDB."""
        collection = _get_collection()
        total = collection.count()
        if total == 0:
            return []

        # Fetch all metadata in batches
        all_meta = collection.get(include=["metadatas"])
        metadatas: List[Dict[str, Any]] = all_meta.get("metadatas") or []

        # Deduplicate by doc_id
        seen: Dict[str, Dict[str, Any]] = {}
        for meta in metadatas:
            doc_id = meta.get("doc_id", "unknown")
            if doc_id not in seen:
                seen[doc_id] = {
                    "doc_id": doc_id,
                    "filename": meta.get("filename", "unknown"),
                    "guideline_version": meta.get("guideline_version", "Unclassified"),
                    "guideline_category": meta.get("guideline_category", "Custom"),
                    "tags": meta.get("tags", ""),
                    "total_chunks": 0,
                }
            seen[doc_id]["total_chunks"] += 1

        return list(seen.values())

    async def list_versions(self) -> List[str]:
        """Return distinct guideline versions present in ChromaDB."""
        collection = _get_collection()
        if collection.count() == 0:
            return []
        all_meta = collection.get(include=["metadatas"])
        metas: List[Dict[str, Any]] = all_meta.get("metadatas") or []
        versions = {m.get("guideline_version", "Unclassified") for m in metas}
        return sorted(versions)

    # ------------------------------------------------------------------
    # Delete document
    # ------------------------------------------------------------------

    async def delete_document(self, doc_id: str) -> int:
        """
        Remove all chunks associated with *doc_id* from ChromaDB.
        Returns the number of chunks deleted.
        """
        collection = _get_collection()

        # Fetch all IDs for this doc_id
        existing = collection.get(where={"doc_id": doc_id}, include=["metadatas"])
        ids_to_delete = existing.get("ids") or []

        if ids_to_delete:
            collection.delete(ids=ids_to_delete)
            log.info("rag_document_deleted", doc_id=doc_id, chunks_removed=len(ids_to_delete))
        else:
            log.warning("rag_document_not_found", doc_id=doc_id)

        return len(ids_to_delete)


# Module-level singleton
rag_pipeline = RAGPipeline()
