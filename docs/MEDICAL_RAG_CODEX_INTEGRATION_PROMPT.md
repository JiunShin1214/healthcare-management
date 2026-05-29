# Medical RAG Codex Integration Prompt

아래 내용을 백엔드 개발자가 Codex에게 그대로 전달하면 됩니다.

```text
우리 FastAPI 백엔드에 선택형 Medical RAG 기능을 반영해줘.

중요 전제:
- 백엔드에서는 추가 크롤링, 추가 수집, CSV 재생성, 재임베딩을 하지 않는다.
- 런타임에서는 이미 생성된 ChromaDB 폴더만 읽는다.
- RAG는 확정 진단 기능이 아니다. 사용자에게 보여주는 결과는 참고용 건강 정보 카드다.
- 기존 증상체커나 건강검진 OCR 기능에 강결합하지 말고, 별도 /medical-rag 라우터로 분리한다.
- 기존 기능이 RAG를 안 쓰면 아무 영향이 없어야 한다.

전달받은 산출물:
- chroma_db/
- app/routers/medical_rag.py
- app/services/medical_rag_service.py
- app/schemas/medical_rag.py
- docs/MEDICAL_RAG_HANDOFF.md

이미 생성된 ChromaDB 정보:
- collection name: medical_docs
- embedding model: text-embedding-3-small
- embedding dimension: 1536
- document count: 13643
- sources: KDCA, NHS, Mayo Clinic

필요한 requirements:
- chromadb
- openai

환경 변수:
OPENAI_API_KEY=...
MEDICAL_RAG_ENABLED=true
MEDICAL_RAG_CHROMA_PATH=/absolute/path/to/chroma_db
MEDICAL_RAG_COLLECTION_NAME=medical_docs
MEDICAL_RAG_EMBEDDING_MODEL=text-embedding-3-small
MEDICAL_RAG_CHAT_MODEL=gpt-4o-mini

반영할 endpoint:
1. GET /medical-rag/health
   - RAG 설정 상태와 Chroma collection count 확인

2. POST /medical-rag/search
   - 입력: { "query": string, "top_k": number, "source"?: string, "category"?: string }
   - 출력: 검색된 문서 chunk 목록
   - 답변 생성 없이 검색 결과만 반환

3. POST /medical-rag/answer
   - 입력은 search와 동일
   - 출력: 자유 텍스트 answer, risk_level, emergency_keywords, sources

4. POST /medical-rag/card
   - 입력은 search와 동일
   - 출력: 프론트 카드 UI용 구조화 JSON
   - card_title, summary, key_points, red_flags, recommended_next_steps, self_care_notes, sections, sources, disclaimer 포함

5. POST /medical-rag/health-check-card
   - 선택 기능
   - 건강검진 OCR/파싱 JSON과 선택적 rule finding을 받아 RAG query를 내부 생성한 뒤 카드 응답 반환
   - 기존 health-check router에 직접 섞지 말고 필요할 때 호출 가능하게 둔다.

구현상 주의:
- OpenAI와 Chroma import는 lazy import로 유지한다. RAG 의존성이 미설치되어도 앱 전체 import가 바로 죽지 않게 한다.
- /medical-rag/health에서 설정 오류를 JSON으로 확인할 수 있게 한다.
- risk_level은 현재 사용자 query의 응급 키워드 포함 여부로만 판단한다.
- emergency_keywords는 검색 문서가 아니라 사용자 query에서 찾는다.
- sources는 retrieve_documents 결과 순서를 유지한다. 현재 유사도 distance는 응답하지 않는다.
- possible_related_topics는 LLM 생성값이므로 질병 후보 랭킹 근거로 쓰지 않는다.
- 질병 후보 랭킹에 가장 안정적인 값은 sources 배열 순서와 sources.topic이다. 다만 점수는 아직 없다.
- 증상체커 후보 생성/랭킹을 RAG가 바꾸면 안 된다. RAG는 설명 카드와 근거 보강 용도로만 사용한다.
- 건강검진 OCR도 RAG 단독 진단이 아니라 rule-based finding 이후 설명 카드 생성 용도로 사용한다.

검증:
- 서버 실행 후 GET /medical-rag/health 호출
- document_count가 13643 근처로 나오는지 확인
- POST /medical-rag/search 로 검색 결과 확인
- POST /medical-rag/card 로 구조화 카드 응답 확인
- OPENAI_API_KEY가 없을 때 /medical-rag/health가 error를 반환하는지 확인

예시 요청:
POST /medical-rag/card
{
  "query": "어제부터 목이 아프고 열이 조금 나요. 감기인지 걱정돼요.",
  "top_k": 5
}

예시 health-check 요청:
POST /medical-rag/health-check-card
{
  "parsed_result": {
    "gender": "male",
    "age": 42,
    "blood_pressure": {
      "systolic": 145,
      "diastolic": 92,
      "unit": "mmHg"
    },
    "fasting_glucose": {
      "value": 118,
      "unit": "mg/dL"
    }
  },
  "findings": [
    {
      "code": "blood_pressure",
      "label": "혈압",
      "value": "145/92 mmHg",
      "status": "주의",
      "reason": "수축기와 이완기 혈압이 기준보다 높게 확인되었습니다."
    }
  ],
  "top_k": 5
}
```

## 판단 기준

Codex가 구현 중 임의로 바꾸면 안 되는 기준입니다.

- RAG는 확정 진단을 생성하지 않는다.
- 백엔드는 크롤링/수집/색인을 수행하지 않는다.
- `chroma_db/`는 런타임 read-only 산출물이다.
- 증상체커와 건강검진 OCR은 RAG 없이도 계속 동작해야 한다.
- RAG 결과는 “후보 생성”이 아니라 “근거 설명”에 우선 사용한다.
