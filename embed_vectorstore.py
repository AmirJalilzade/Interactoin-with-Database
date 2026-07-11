# embed_and_store.py

import json
import logging
import pickle
from pathlib import Path
from typing import List, Dict, Any

from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
    before_sleep_log,
)
from pymilvus import MilvusClient, DataType
from pymilvus.model.sparse import BM25EmbeddingFunction
from hazm import word_tokenize  # Added Hazm for Persian tokenization

from config.settings import settings
from embedding import EmbeddingService

# ============================================================
# LOGGING
# ============================================================

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)

# ============================================================
# CONFIGURATION
# ============================================================

MILVUS_COLLECTION_NAME = "column_info_bgem3"
COLUMNS_DESC_PATH      = Path("columns_with_desc.json")
BM25_MODEL_PATH        = Path("bm25_model.pkl")

# We use 40 for Embedding to avoid VRAM spikes, and 500 for Milvus insert batching.
EMBEDDING_BATCH_SIZE   = 40
INSERT_BATCH_SIZE      = 500

# ============================================================
# MILVUS CLIENT
# ============================================================

def _make_client() -> MilvusClient:
    uri = f"http://{settings.MILVUS_HOST}:{settings.MILVUS_PORT}"
    client = MilvusClient(uri=uri)
    logger.info("MilvusClient connected → %s", uri)
    return client

# ============================================================
# COLLECTION MANAGEMENT
# ============================================================

def _build_schema(client: MilvusClient, dim: int):
    schema = client.create_schema(auto_id=True, enable_dynamic_field=False)
    schema.add_field("id",            DataType.INT64,               is_primary=True)
    schema.add_field("vector",        DataType.FLOAT_VECTOR,        dim=dim)
    schema.add_field("sparse_vector", DataType.SPARSE_FLOAT_VECTOR)
    schema.add_field("table_name",    DataType.VARCHAR,             max_length=256)
    schema.add_field("column_name",   DataType.VARCHAR,             max_length=256)
    schema.add_field("chunk_text",    DataType.VARCHAR,             max_length=8192)
    schema.add_field("metadata_json", DataType.JSON)
    return schema

def _build_index_params(client: MilvusClient):
    idx = client.prepare_index_params()
    idx.add_index(
        field_name  = "vector",
        index_type  = "IVF_FLAT",
        metric_type = "COSINE",
        params      = {"nlist": 128},
    )
    idx.add_index(
        field_name  = "sparse_vector",
        index_type  = "SPARSE_INVERTED_INDEX",
        metric_type = "IP",
        params      = {"drop_ratio_build": 0.0},
    )
    return idx

def recreate_collection(client: MilvusClient, dim: int) -> None:
    """Always drops the existing collection and creates a fresh one."""
    if client.has_collection(MILVUS_COLLECTION_NAME):
        client.drop_collection(MILVUS_COLLECTION_NAME)
        logger.warning("Dropped existing collection '%s' for a fresh start.", MILVUS_COLLECTION_NAME)

    client.create_collection(
        collection_name = MILVUS_COLLECTION_NAME,
        schema          = _build_schema(client, dim),
        index_params    = _build_index_params(client),
    )
    logger.info("Collection '%s' created (dim=%d).", MILVUS_COLLECTION_NAME, dim)
    
    client.load_collection(MILVUS_COLLECTION_NAME)

# ============================================================
# BM25 — ALWAYS FIT NEW
# ============================================================

def fit_and_save_bm25(corpus_texts: List[str]) -> BM25EmbeddingFunction:
    """
    Always fits a new model using Hazm tokenization for Persian
    and overwrites the existing .pkl file.
    """
    logger.info("Fitting new BM25 model (Persian tokenization via Hazm)...")
    bm25_ef = BM25EmbeddingFunction(analyzer=word_tokenize)
    bm25_ef.fit(corpus_texts)
    
    with open(BM25_MODEL_PATH, "wb") as fh:
        pickle.dump(bm25_ef, fh)
    logger.info("BM25 model fitted and saved → %s", BM25_MODEL_PATH)
    
    return bm25_ef

# ============================================================
# SPARSE VECTOR HELPER
# ============================================================

def _sparse_row_to_dict(sparse_matrix, row_idx: int) -> Dict[int, float]:
    csr         = sparse_matrix.tocsr()
    row_start   = int(csr.indptr[row_idx])
    row_end     = int(csr.indptr[row_idx + 1])
    col_indices = csr.indices[row_start:row_end]
    values      = csr.data[row_start:row_end]
    return {int(c): float(v) for c, v in zip(col_indices, values)}

# ============================================================
# CHUNK TEXT BUILDER
# ============================================================

def build_chunk_text(col: dict) -> str:
    lines = [
        f"Table: {col.get('table', 'Unknown')}",
        f"Column: {col.get('column', 'Unknown')}",
        f"Data Type: {col.get('type', 'Unknown')}",
        f"Nullable: {col.get('nullable', 'Unknown')}",
        f"Description: {col.get('description', '').strip()}"
    ]
    
    if "stats" in col and col["stats"]:
        lines.append(f"Statistics: {json.dumps(col['stats'], ensure_ascii=False)}")
        
    if "top_values" in col and col["top_values"]:
        lines.append(f"Top Values: {json.dumps(col['top_values'], ensure_ascii=False)}")
        
    return "\n".join(lines)

# ============================================================
# EMBEDDING WITH RETRY
# ============================================================

@retry(
    stop         = stop_after_attempt(3),
    wait         = wait_exponential(multiplier=1, min=2, max=10),
    retry        = retry_if_exception_type(Exception),
    before_sleep = before_sleep_log(logger, logging.WARNING),
    reraise      = True,
)
def _embed_with_retry(embedder: EmbeddingService, texts: List[str]) -> List[List[float]]:
    raw = embedder.embed_documents(texts)
    return [[float(x) for x in vec] for vec in raw]

# ============================================================
# INGESTION
# ============================================================

def ingest_columns(columns_info: List[dict]) -> None:
    client = _make_client()
    embedder = EmbeddingService(
        base_url = settings.embedding_base_url,
        model    = settings.embedding_model,
    )

    # ── 1. Chunk texts ─────────────────────────────────────────────
    chunk_texts = [build_chunk_text(col) for col in columns_info]
    logger.info("Built %d chunk texts containing full column metadata.", len(chunk_texts))

    # ── 2. Dense embeddings (Batched) ──────────────────────────────
    dense_vectors = []
    logger.info("Generating dense embeddings via vLLM in batches of %d...", EMBEDDING_BATCH_SIZE)
    
    for i in range(0, len(chunk_texts), EMBEDDING_BATCH_SIZE):
        batch_texts = chunk_texts[i : i + EMBEDDING_BATCH_SIZE]
        batch_vectors = _embed_with_retry(embedder, batch_texts)
        dense_vectors.extend(batch_vectors)
        logger.info("  ✔ Embedded %d / %d chunks", min(i + EMBEDDING_BATCH_SIZE, len(chunk_texts)), len(chunk_texts))

    dim = len(dense_vectors[0])
    logger.info("Dense embeddings ready (%d vectors, dim=%d).", len(dense_vectors), dim)

    # ── 3. Sparse BM25 embeddings ──────────────────────────────────
    bm25_ef       = fit_and_save_bm25(chunk_texts)
    sparse_matrix = bm25_ef.encode_documents(chunk_texts)
    logger.info("Sparse vectors encoded successfully.")

    # ── 4. Collection (Always Recreated) ───────────────────────────
    recreate_collection(client, dim=dim)

    # ── 5. Insert in batches ───────────────────────────────────────
    total     = len(columns_info)
    n_batches = (total + INSERT_BATCH_SIZE - 1) // INSERT_BATCH_SIZE

    for batch_idx in range(n_batches):
        lo = batch_idx * INSERT_BATCH_SIZE
        hi = min(lo + INSERT_BATCH_SIZE, total)

        rows: List[Dict[str, Any]] = []
        for i in range(lo, hi):
            col = columns_info[i]
            rows.append({
                "vector":        dense_vectors[i],
                "sparse_vector": _sparse_row_to_dict(sparse_matrix, i),
                "table_name":    col["table"],
                "column_name":   col["column"],
                "chunk_text":    chunk_texts[i],
                "metadata_json": {
                    k: v for k, v in col.items()
                    if k not in ("table", "column")
                },
            })

        try:
            client.insert(collection_name=MILVUS_COLLECTION_NAME, data=rows)
            logger.info("Inserted batch %d/%d (rows %d–%d).", batch_idx + 1, n_batches, lo + 1, hi)
        except Exception as exc:
            logger.error("Insert failed for batch %d: %s", batch_idx + 1, exc)
            raise

    # ── 6. Flush ───────────────────────────────────────────────────
    client.flush(MILVUS_COLLECTION_NAME)
    stats = client.get_collection_stats(MILVUS_COLLECTION_NAME)
    logger.info("Flush complete. '%s' now holds %s entities.", MILVUS_COLLECTION_NAME, stats.get("row_count", "?"))

# ============================================================
# MAIN
# ============================================================

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Embed column descriptions and strictly overwrite them in Milvus.")
    parser.add_argument(
        "--input",
        default=str(COLUMNS_DESC_PATH),
        help=f"Path to input JSON  (default: {COLUMNS_DESC_PATH})",
    )
    args = parser.parse_args()

    input_path = Path(args.input)
    if not input_path.exists():
        logger.error("Input file not found: %s", input_path)
        raise SystemExit(1)

    logger.info("=" * 60)
    logger.info("Embedding & Ingestion Pipeline (OVERWRITE MODE)")
    logger.info("  Input:         %s", input_path)
    logger.info("  Collection:    %s", MILVUS_COLLECTION_NAME)
    logger.info("=" * 60)

    with open(input_path, "r", encoding="utf-8") as fh:
        columns_info = json.load(fh)
        
    ingest_columns(columns_info)
    
    logger.info("=" * 60)
    logger.info("Pipeline complete.")
    logger.info("=" * 60)