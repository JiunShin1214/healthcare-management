import json
from pathlib import Path
from typing import Any

from app.core.config import (
    BACKEND_DIR,
    MEDICAL_RAG_CHAT_MODEL,
    MEDICAL_RAG_CHROMA_PATH,
    MEDICAL_RAG_COLLECTION_NAME,
    MEDICAL_RAG_EMBEDDING_MODEL,
    MEDICAL_RAG_ENABLED,
    MEDICAL_RAG_OPENAI_API_KEY,
)


_openai_client = None
_chroma_collection = None


KOREAN_RETRIEVAL_KEYWORD_EXPANSIONS: dict[str, list[str]] = {
    "목": ["throat", "neck"],
    "목이": ["throat"],
    "인후": ["throat", "pharyngitis"],
    "열": ["fever"],
    "미열": ["low grade fever", "fever"],
    "기침": ["cough"],
    "가래": ["phlegm", "sputum"],
    "콧물": ["runny nose"],
    "코막힘": ["nasal congestion"],
    "소변": ["urination", "urinary"],
    "배뇨": ["urination"],
    "따갑": ["painful urination", "burning"],
    "화장실": ["frequent urination"],
    "자주": ["frequent"],
    "아랫배": ["lower abdomen", "suprapubic"],
    "손": ["hand"],
    "손등": ["back of hand", "hand skin"],
    "발": ["foot"],
    "발등": ["top of foot", "foot skin"],
    "피부": ["skin"],
    "발진": ["rash"],
    "물집": ["blister"],
    "상처": ["wound", "skin injury"],
    "긁": ["scratch", "skin wound"],
    "빨갛": ["redness", "red skin"],
    "붉": ["redness", "red skin"],
    "붓": ["swelling", "swollen"],
    "부어": ["swelling", "swollen"],
    "뜨거": ["warm skin"],
    "열감": ["warm skin"],
    "아파": ["pain"],
    "통증": ["pain"],
    "가렵": ["itching"],
    "번지": ["spreading"],
    "악화": ["worsening"],
    "감기": ["common cold", "upper respiratory infection"],
    "인후염": ["pharyngitis", "sore throat"],
    "요로감염": ["urinary tract infection", "UTI"],
    "방광염": ["cystitis"],
    "봉와직염": ["cellulitis"],
    "연조직염": ["cellulitis", "skin infection"],
}

KOREAN_RETRIEVAL_PHRASE_EXPANSIONS: tuple[tuple[tuple[str, ...], list[str]], ...] = (
    (("소변", "따갑"), ["urinary tract infection", "UTI", "cystitis", "painful urination"]),
    (("소변", "자주"), ["urinary tract infection", "UTI", "frequent urination"]),
    (("화장실", "자주"), ["urinary tract infection", "UTI", "frequent urination"]),
    (("목", "열"), ["common cold", "upper respiratory infection", "pharyngitis", "influenza"]),
    (("인후", "열"), ["pharyngitis", "tonsillitis", "upper respiratory infection"]),
    (("빨갛", "붓", "뜨거"), ["cellulitis", "skin infection", "red swollen warm skin"]),
    (("상처", "붓"), ["cellulitis", "skin infection", "wound infection"]),
    (("물집", "붓"), ["cellulitis", "skin infection", "blister infection"]),
    (("발진", "가렵"), ["eczema", "contact dermatitis", "hives", "itchy rash"]),
)


def _default_chroma_path() -> Path:
    project_root_path = BACKEND_DIR.parent / "chroma_db"
    if project_root_path.exists():
        return project_root_path
    return BACKEND_DIR / "app" / "data" / "processed" / "medical_chroma_db"


def get_chroma_path() -> Path:
    if MEDICAL_RAG_CHROMA_PATH:
        return Path(MEDICAL_RAG_CHROMA_PATH).expanduser()
    return _default_chroma_path()


def _get_openai_client():
    global _openai_client
    if _openai_client is not None:
        return _openai_client
    if not MEDICAL_RAG_OPENAI_API_KEY:
        raise RuntimeError("OPENAI_API_KEY가 설정되지 않았습니다.")
    try:
        from openai import OpenAI
    except ImportError as exc:
        raise RuntimeError("openai 패키지가 설치되어 있지 않습니다.") from exc
    _openai_client = OpenAI(api_key=MEDICAL_RAG_OPENAI_API_KEY)
    return _openai_client


def _get_collection():
    global _chroma_collection
    if _chroma_collection is not None:
        return _chroma_collection
    if not MEDICAL_RAG_ENABLED:
        raise RuntimeError("MEDICAL_RAG_ENABLED가 false입니다.")
    try:
        import chromadb
    except ImportError as exc:
        raise RuntimeError("chromadb 패키지가 설치되어 있지 않습니다.") from exc
    chroma_path = get_chroma_path()
    if not chroma_path.exists():
        raise RuntimeError(f"ChromaDB 경로를 찾을 수 없습니다: {chroma_path}")
    chroma_client = chromadb.PersistentClient(path=str(chroma_path))
    _chroma_collection = chroma_client.get_collection(name=MEDICAL_RAG_COLLECTION_NAME)
    return _chroma_collection


def create_embedding(text: str) -> list[float]:
    response = _get_openai_client().embeddings.create(
        model=MEDICAL_RAG_EMBEDDING_MODEL,
        input=text,
    )
    return response.data[0].embedding


def _build_retrieval_query(query: str) -> str:
    expansions: list[str] = []
    phrase_expansions: list[str] = []
    lowered_query = query.lower()
    for korean_keyword, english_terms in KOREAN_RETRIEVAL_KEYWORD_EXPANSIONS.items():
        if korean_keyword in query:
            expansions.extend(english_terms)
    for required_terms, english_terms in KOREAN_RETRIEVAL_PHRASE_EXPANSIONS:
        if all(term in query for term in required_terms):
            phrase_expansions.extend(english_terms)
    if any(term in lowered_query for term in ("cellulitis", "urinary tract infection", "cystitis", "pharyngitis")):
        return query
    if phrase_expansions:
        unique_phrase_expansions = list(dict.fromkeys(phrase_expansions))
        return f"{'; '.join(unique_phrase_expansions)}\n\nOriginal Korean question: {query}"
    unique_expansions = list(dict.fromkeys(expansions))
    if not unique_expansions:
        return query
    return f"{'; '.join(unique_expansions)}\n\nOriginal Korean question: {query}"


def medical_rag_health() -> dict[str, Any]:
    result = {
        "enabled": MEDICAL_RAG_ENABLED,
        "configured": False,
        "collection_name": MEDICAL_RAG_COLLECTION_NAME,
        "chroma_path": str(get_chroma_path()),
        "document_count": None,
        "error": None,
    }
    if not MEDICAL_RAG_ENABLED:
        result["error"] = "MEDICAL_RAG_ENABLED가 false입니다."
        return result
    if not MEDICAL_RAG_OPENAI_API_KEY:
        result["error"] = "OPENAI_API_KEY가 설정되지 않았습니다."
        return result
    try:
        collection = _get_collection()
        result["document_count"] = collection.count()
        result["configured"] = True
    except Exception as exc:
        result["error"] = str(exc)
    return result


def emergency_check(user_text: str) -> dict[str, Any]:
    emergency_keywords = [
        "흉통",
        "가슴 통증",
        "가슴이 답답",
        "호흡곤란",
        "숨이 차",
        "식은땀",
        "왼팔 통증",
        "턱 통증",
        "한쪽 마비",
        "말이 어눌",
        "의식 저하",
        "극심한 두통",
        "혈변",
        "검은변",
    ]
    matched_keywords = [keyword for keyword in emergency_keywords if keyword in user_text]
    if matched_keywords:
        return {
            "risk_level": "주의",
            "matched_keywords": matched_keywords,
            "message": "응급 또는 빠른 진료가 필요한 증상이 포함될 수 있습니다.",
        }
    return {
        "risk_level": "일반",
        "matched_keywords": [],
        "message": "명확한 응급 키워드는 확인되지 않았습니다.",
    }


def retrieve_documents(
    query: str,
    top_k: int = 5,
    source: str | None = None,
    category: str | None = None,
) -> list[dict[str, Any]]:
    retrieval_query = _build_retrieval_query(query)
    query_embedding = create_embedding(retrieval_query)
    collection = _get_collection()
    fetch_count = max(top_k * 3, top_k)
    if source or category:
        fetch_count = min(max(top_k * 4, 10), 40)

    results = collection.query(
        query_embeddings=[query_embedding],
        n_results=fetch_count,
    )

    documents: list[dict[str, Any]] = []
    if not results["ids"] or not results["ids"][0]:
        return documents

    for i, doc_id in enumerate(results["ids"][0]):
        metadata = results["metadatas"][0][i] or {}
        if source and metadata.get("source") != source:
            continue
        if category and metadata.get("category") != category:
            continue
        distance = None
        if results.get("distances") and results["distances"][0]:
            distance = results["distances"][0][i]
        if distance is not None and distance > 1.3:
            continue
        documents.append({
            "id": doc_id,
            "content": results["documents"][0][i],
            "category": metadata.get("category", ""),
            "topic": metadata.get("topic", ""),
            "title": metadata.get("title", ""),
            "source": metadata.get("source", ""),
            "url": metadata.get("url", ""),
            "trust_tier": metadata.get("trust_tier", ""),
            "distance": distance,
        })
        if len(documents) >= top_k:
            break
    return documents


def build_prompt(question: str, retrieved_docs: list[dict[str, Any]], emergency_result: dict[str, Any]) -> str:
    context_text = ""
    for idx, doc in enumerate(retrieved_docs, start=1):
        context_text += f"""
[근거 {idx}]
제목: {doc.get("title", "")}
출처: {doc.get("source", "")}
URL: {doc.get("url", "")}
분류: {doc.get("category", "")}
주제: {doc.get("topic", "")}
내용: {doc.get("content", "")}
"""
    if not context_text.strip():
        context_text = "검색된 근거 문서가 없습니다."

    return f"""
당신은 의약품 및 건강 정보를 설명하는 보조 AI입니다.

반드시 지켜야 할 규칙:
1. 의학적 진단을 확정하지 마세요.
2. 검색된 근거 문서를 우선 사용하세요.
3. 근거에 없는 내용을 확정적으로 말하지 마세요.
4. 위험 신호가 있으면 병원 또는 응급실 상담을 권고하세요.
5. 사용자가 이해하기 쉬운 한국어로 답변하세요.
6. 약물, 증상, 건강검진 수치에 대해 과도하게 단정하지 마세요.
7. 답변 마지막에 참고한 출처를 정리하세요.

[사용자 질문]
{question}

[응급 키워드 검사 결과]
위험도: {emergency_result.get("risk_level")}
탐지 키워드: {emergency_result.get("matched_keywords")}
메시지: {emergency_result.get("message")}

[검색된 근거 문서]
{context_text}

[답변 형식]
1. 요약
2. 관련 가능성
3. 주의해야 할 점
4. 병원 또는 전문가 상담이 필요한 경우
5. 참고 근거
"""


def generate_rag_answer(
    question: str,
    top_k: int = 5,
    source: str | None = None,
    category: str | None = None,
) -> dict[str, Any]:
    emergency_result = emergency_check(question)
    retrieved_docs = retrieve_documents(query=question, top_k=top_k, source=source, category=category)
    prompt = build_prompt(question, retrieved_docs, emergency_result)

    response = _get_openai_client().chat.completions.create(
        model=MEDICAL_RAG_CHAT_MODEL,
        messages=[
            {
                "role": "system",
                "content": "너는 의료 정보를 신중하고 안전하게 설명하는 AI 보조자다.",
            },
            {"role": "user", "content": prompt},
        ],
        temperature=0.2,
    )

    return {
        "question": question,
        "answer": response.choices[0].message.content,
        "risk_level": emergency_result["risk_level"],
        "emergency_keywords": emergency_result["matched_keywords"],
        "emergency_message": emergency_result["message"],
        "sources": [
            {
                "title": doc.get("title", ""),
                "source": doc.get("source", ""),
                "url": doc.get("url", ""),
                "category": doc.get("category", ""),
                "topic": doc.get("topic", ""),
            }
            for doc in retrieved_docs
        ],
    }


def build_card_prompt(question: str, retrieved_docs: list[dict[str, Any]], emergency_result: dict[str, Any]) -> str:
    context_text = ""
    for idx, doc in enumerate(retrieved_docs, start=1):
        context_text += f"""
[근거 {idx}]
제목: {doc.get("title", "")}
출처: {doc.get("source", "")}
URL: {doc.get("url", "")}
분류: {doc.get("category", "")}
주제: {doc.get("topic", "")}
내용: {doc.get("content", "")}
"""
    if not context_text.strip():
        context_text = "검색된 근거 문서가 없습니다."

    return f"""
당신은 의료 정보를 카드 UI에 맞게 구조화하는 보조 AI입니다.

반드시 지켜야 할 규칙:
1. 의학적 진단을 확정하지 마세요.
2. 사용자의 상태를 특정 질병이라고 단정하지 마세요.
3. 검색된 근거 문서를 우선 사용하세요.
4. 근거에 없는 의학 정보를 새로 만들지 마세요.
5. 위험 신호가 있으면 recommended_next_steps에 의료기관 또는 응급 상담 권고를 포함하세요.
6. 모든 문장은 사용자가 이해하기 쉬운 한국어로 작성하세요.
7. JSON 객체만 출력하세요. markdown, 설명문, 코드블록은 출력하지 마세요.
8. possible_related_topics에는 사용자 질문의 증상, 부위, 기간, 맥락과 직접 관련 있는 질병명 또는 건강 주제만 넣으세요.
9. 검색된 근거 문서의 제목/주제가 사용자 질문과 직접 관련이 낮으면 possible_related_topics에 넣지 마세요.
10. possible_related_topics에는 단순 증상명만 단독으로 넣지 말고, 가능하면 질병명 또는 임상적으로 의미 있는 건강 주제로 작성하세요.
11. possible_related_topics는 2-5개로 제한하고, 관련성이 높은 순서로 작성하세요.
12. 검색 문서에 있더라도 사용자 질문에 없는 핵심 증상이나 부위를 전제로 하는 주제는 제외하세요. 예를 들어 목 통증과 미열만 말한 질문에는 입안 궤양, 잇몸/치아 통증, 피부 증상, 해외여행 감염병처럼 별도 단서가 필요한 주제를 넣지 마세요.
13. possible_related_topics를 만들 때는 검색 문서 제목을 그대로 베끼지 말고, 사용자 질문과 근거 문서가 함께 지지하는 주제만 남기세요.
14. Cellulitis는 한국어로 "봉와직염" 또는 "연조직염"으로 표현하세요. "세포염"이라고 번역하지 마세요.

[사용자 질문]
{question}

[응급 키워드 검사 결과]
위험도: {emergency_result.get("risk_level")}
탐지 키워드: {emergency_result.get("matched_keywords")}
메시지: {emergency_result.get("message")}

[검색된 근거 문서]
{context_text}

[출력 JSON 스키마]
{{
  "card_title": "string",
  "card_subtitle": "string",
  "summary": "string",
  "possible_related_topics": ["string"],
  "key_points": ["string"],
  "red_flags": ["string"],
  "recommended_next_steps": ["string"],
  "self_care_notes": ["string"],
  "sections": [
    {{
      "title": "string",
      "items": ["string"]
    }}
  ]
}}
"""


def _json_object_from_response(text: str | None) -> dict[str, Any]:
    if not text:
        return {}
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        start = text.find("{")
        end = text.rfind("}")
        if start >= 0 and end > start:
            return json.loads(text[start:end + 1])
        raise


def _list_of_strings(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item).strip() for item in value if str(item).strip()]


def _card_sections(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    sections = []
    for section in value:
        if not isinstance(section, dict):
            continue
        title = str(section.get("title", "")).strip()
        items = _list_of_strings(section.get("items", []))
        if title and items:
            sections.append({"title": title, "items": items})
    return sections


def _format_health_check_value(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, (str, int, float, bool)):
        return str(value)
    if isinstance(value, dict):
        parts = []
        for key, nested_value in value.items():
            formatted = _format_health_check_value(nested_value)
            if formatted:
                parts.append(f"{key}: {formatted}")
        return ", ".join(parts)
    if isinstance(value, list):
        return ", ".join(_format_health_check_value(item) for item in value if _format_health_check_value(item))
    return str(value)


def _extract_health_check_profile(parsed_result: dict[str, Any]) -> list[str]:
    profile_parts = []
    for key in ["gender", "sex", "age", "birth_date"]:
        value = parsed_result.get(key)
        if value not in (None, ""):
            profile_parts.append(f"{key}={value}")
    return profile_parts


def _summarize_health_check_result(parsed_result: dict[str, Any]) -> list[str]:
    ignored_keys = {
        "name",
        "rrn",
        "resident_registration_number",
        "birth_date",
        "gender",
        "sex",
        "age",
        "missing_fields",
        "parsing_status",
    }
    summary = []
    for key, value in parsed_result.items():
        if key in ignored_keys:
            continue
        formatted = _format_health_check_value(value)
        if formatted:
            summary.append(f"{key}: {formatted}")
    return summary[:30]


def build_health_check_rag_query(
    parsed_result: dict[str, Any],
    findings: list[dict[str, Any]] | None = None,
) -> str:
    findings = findings or []
    profile_parts = _extract_health_check_profile(parsed_result)
    result_parts = _summarize_health_check_result(parsed_result)

    finding_lines = []
    for finding in findings:
        label = finding.get("label") or finding.get("code") or "검진 항목"
        value = finding.get("value", "")
        status = finding.get("status", "")
        reason = finding.get("reason", "")
        line = f"{label}: {value}"
        if status:
            line += f" ({status})"
        if reason:
            line += f" - {reason}"
        finding_lines.append(line)

    query = "건강검진 결과를 참고용으로 설명해주세요. 확정 진단이나 처방은 하지 말고, 수치의 의미와 생활 관리, 병원 상담이 필요한 경우를 알려주세요."
    if profile_parts:
        query += "\n사용자 기본 정보: " + ", ".join(profile_parts)
    if finding_lines:
        query += "\nrule 기반 주요 소견: " + " / ".join(finding_lines)
    if result_parts:
        query += "\nOCR 파싱 수치: " + " / ".join(result_parts)
    return query


def generate_rag_card(
    question: str,
    top_k: int = 5,
    source: str | None = None,
    category: str | None = None,
) -> dict[str, Any]:
    emergency_result = emergency_check(question)
    retrieved_docs = retrieve_documents(query=question, top_k=top_k, source=source, category=category)
    prompt = build_card_prompt(question, retrieved_docs, emergency_result)

    response = _get_openai_client().chat.completions.create(
        model=MEDICAL_RAG_CHAT_MODEL,
        messages=[
            {
                "role": "system",
                "content": "너는 의료 정보를 안전한 참고 카드 JSON으로 구조화하는 AI 보조자다.",
            },
            {"role": "user", "content": prompt},
        ],
        temperature=0.1,
        response_format={"type": "json_object"},
    )
    payload = _json_object_from_response(response.choices[0].message.content)

    return {
        "question": question,
        "card_title": str(payload.get("card_title") or "건강 정보 참고 카드").strip(),
        "card_subtitle": str(payload.get("card_subtitle") or "검색된 의료 문서 기반 요약").strip(),
        "risk_level": emergency_result["risk_level"],
        "emergency_keywords": emergency_result["matched_keywords"],
        "summary": str(payload.get("summary") or "").strip(),
        "possible_related_topics": _list_of_strings(payload.get("possible_related_topics", [])),
        "key_points": _list_of_strings(payload.get("key_points", [])),
        "red_flags": _list_of_strings(payload.get("red_flags", [])),
        "recommended_next_steps": _list_of_strings(payload.get("recommended_next_steps", [])),
        "self_care_notes": _list_of_strings(payload.get("self_care_notes", [])),
        "sections": _card_sections(payload.get("sections", [])),
        "sources": [
            {
                "title": doc.get("title", ""),
                "source": doc.get("source", ""),
                "url": doc.get("url", ""),
                "category": doc.get("category", ""),
                "topic": doc.get("topic", ""),
            }
            for doc in retrieved_docs
        ],
        "disclaimer": "이 카드는 참고용 건강 정보이며 의학적 진단이나 처방을 대체하지 않습니다.",
    }


def generate_health_check_rag_card(
    parsed_result: dict[str, Any],
    findings: list[dict[str, Any]] | None = None,
    top_k: int = 5,
) -> dict[str, Any]:
    generated_query = build_health_check_rag_query(parsed_result=parsed_result, findings=findings)
    card = generate_rag_card(question=generated_query, top_k=top_k, category="검진수치")
    card["question"] = "건강검진 결과 참고 카드"
    card["generated_query"] = generated_query
    card["abnormal_findings"] = findings or []
    return card
