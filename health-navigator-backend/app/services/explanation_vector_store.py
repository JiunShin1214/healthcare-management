import json
import sqlite3
from math import sqrt
from pathlib import Path


DATA_DIR = Path(__file__).resolve().parents[1] / "data"
DEFAULT_STORE_PATH = DATA_DIR / "processed" / "explanation_vector_store.sqlite"


def search_explanation_documents(
    target_codes: list[str],
    target_type: str | None = None,
    query_embedding: list[float] | None = None,
    store_path: Path = DEFAULT_STORE_PATH,
    limit: int = 6,
) -> list[dict]:
    if not store_path.exists():
        return []

    clauses = ["review_status = 'reviewed'"]
    params: list[str | int] = []
    if target_codes:
        placeholders = ", ".join("?" for _ in target_codes)
        clauses.append(f"target_code IN ({placeholders})")
        params.extend(target_codes)
    if target_type:
        clauses.append("target_type = ?")
        params.append(target_type)

    query = f"""
        SELECT card_id, target_type, target_code, text, metadata_json, embedding_json
        FROM explanation_documents
        WHERE {' AND '.join(clauses)}
        ORDER BY
            CASE
                WHEN source_usage_policy = 'approved' THEN 0
                ELSE 1
            END,
            card_id
    """
    with sqlite3.connect(store_path) as conn:
        rows = conn.execute(query, params).fetchall()

    documents = [
        {
            "card_id": card_id,
            "target_type": row_target_type,
            "target_code": target_code,
            "text": text,
            "metadata": json.loads(metadata_json),
            "score": _cosine_similarity(query_embedding, json.loads(embedding_json))
            if query_embedding is not None and embedding_json
            else None,
        }
        for card_id, row_target_type, target_code, text, metadata_json, embedding_json in rows
    ]
    if query_embedding is not None:
        documents.sort(key=lambda item: (-(item["score"] or 0), item["card_id"]))
    return documents[:limit]


def _cosine_similarity(left: list[float], right: list[float]) -> float:
    numerator = sum(a * b for a, b in zip(left, right))
    left_norm = sqrt(sum(a * a for a in left))
    right_norm = sqrt(sum(b * b for b in right))
    return numerator / (left_norm * right_norm) if left_norm and right_norm else 0.0
