# Symptom Checker RAG Integration Design

작성일: 2026-05-28

## 목적

인체 UI 기반 질병 검색 기능의 성능을 높이기 위해 Medical RAG를 활용한다.

1차 목표는 기존 rule 기반 후보를 유지하면서, Medical RAG가 찾은 관련 질환을 별도 보조 후보로 노출하는 것이다. RAG 후보는 메인 후보 랭킹을 바로 바꾸지 않는다. 품질 검증 후 2차에서 rule/RAG 통합 랭킹을 검토한다.

## 현재 흐름 요약

### 증상체커 평가

`/symptom-checker/assess`와 `/symptom-checker/assess/me`는 `assess_symptoms()`를 호출한다.

- 선택 증상, context chip, free text alias 후보를 합친다.
- red flag는 `_detect_red_flags()`에서 rule 기반으로 만든다.
- 메인 후보는 `_match_condition_candidates()`에서 rule 기반으로 만든다.
- 보조 possible candidate는 `_find_possible_condition_candidates()`에서 rule evidence 부족 항목으로 만든다.
- 현재 metadata는 `rag_usage: explanation_only_not_judgment`, `judgment_mutation_allowed_by_rag: false`로 고정되어 있다.

### 기존 증상체커 RAG

증상체커 내부의 RAG는 Medical RAG가 아니다.

- `build_explanation_rag_context()`는 검수된 explanation card JSON을 고른다.
- sentence-transformers vector store는 explanation card 정렬 보조에만 쓰인다.
- `attach_explanation_to_assessment()`는 rule 결과를 바꾸지 않고 설명 카드만 붙인다.

### Gemini 설명

Gemini는 두 흐름에서 쓰인다.

- `/api/gemini/explain-symptoms`: 백엔드가 이미 만든 후보를 사용자 친화 문장으로 다시 쓴다.
- `/symptom-checker/explain/gemini` 또는 `include_gemini_explanation=true`: 검수된 explanation card context를 요약한다.

Gemini prompt는 새 질환, 증상, 근거를 만들지 말라고 제한한다. 따라서 Gemini는 후보 생성기가 아니라 설명 생성기다.

### Medical RAG

`/medical-rag/*`는 새로 추가된 공용 기능이다.

- `retrieve_documents()`는 OpenAI embedding으로 ChromaDB의 의료 문서를 검색한다.
- `/medical-rag/search`는 문서 chunk만 반환한다.
- `/medical-rag/answer`, `/medical-rag/card`, `/medical-rag/health-check-card`는 OpenAI chat completion으로 문장 또는 카드 JSON을 만든다.
- OCR 이후 카드에도 사용할 공용 API이므로 증상체커 전용 변경을 넣으면 안 된다.

## 충돌 위험

### 1. RAG라는 이름의 의미 충돌

현재 코드에는 두 종류의 RAG가 있다.

- Symptom explanation RAG: 검수된 내부 explanation card 기반
- Medical RAG: KDCA, NHS, Mayo Clinic 기반 ChromaDB 검색

둘 다 `rag`라는 용어를 쓰지만 목적과 신뢰 경계가 다르다. 응답 필드와 metadata에서 이를 분리해야 한다.

권장 명명:

- 기존 설명 카드: `explanations`, `explanation_safety`, `generated_summary_ko`
- Medical RAG 보조 후보: `rag_related_conditions` 또는 `medical_rag_related_conditions`
- Medical RAG metadata: `medical_rag_metadata`

### 2. Gemini와 OpenAI 생성문 혼합

Gemini는 기존 rule 후보/검수 카드 요약에 사용된다.
Medical RAG의 `/answer`, `/card`는 OpenAI가 생성한 문장이다.

두 provider의 생성문을 같은 `generated_summary_ko` 필드에 섞으면 프론트와 안전 검증이 어느 모델의 결과인지 구분하기 어렵다.

1차에서는 증상체커 RAG 보조 후보 생성에 Medical RAG의 `retrieve_documents()`만 사용하고, OpenAI chat completion 기반 `/medical-rag/card` 결과는 증상체커 후보 목록에 직접 섞지 않는다.

### 3. 공용 Medical RAG API 변경 위험

Medical RAG는 OCR 이후에도 사용할 기능이다.

따라서 증상체커 전용 필드나 rule 후보 구조를 `/medical-rag/*` response에 추가하지 않는다. 증상체커는 별도 adapter/service에서 Medical RAG를 읽고 필요한 형태로 변환한다.

### 4. 후보 생성 책임 경계

RAG 문서 topic과 LLM `possible_related_topics`는 질병 후보처럼 보일 수 있다.

하지만 현재 Medical RAG 문서는 distance를 반환하지 않고, topic aggregate score도 없다. 1차에서는 다음 원칙을 둔다.

- `possible_related_topics`는 후보 랭킹 근거로 사용하지 않는다.
- `sources.topic`, `sources.title`, `source`, 검색 순서는 보조 후보 설명에만 사용한다.
- red flag는 기존 rule이 우선한다.
- rule 후보 confidence는 RAG가 바꾸지 않는다.

## 1차 통합 방향

### 범위

1차는 보조 후보 표시까지다.

- 기존 `/medical-rag/*` API는 변경하지 않는다.
- 기존 rule 후보는 메인 후보로 유지한다.
- 증상체커 응답에 선택 플래그로 Medical RAG 보조 후보를 붙인다.
- 기본 `/assess` 응답은 OpenAI/Chroma 호출 없이 현재처럼 빠르게 유지한다.

권장 호출 방식:

```text
POST /symptom-checker/assess?include_rag_candidates=true
POST /symptom-checker/assess/me?include_rag_candidates=true
```

### 응답 구조 초안

```json
{
  "candidates": [],
  "possible_candidates": [],
  "rag_related_conditions": [
    {
      "condition_name": "Sore throat",
      "display_name": "Sore throat",
      "source": "NHS",
      "category": "질병",
      "topic": "Sore throat",
      "title": "Sore throat",
      "url": "https://www.nhs.uk/conditions/sore-throat/",
      "matched_basis": "medical_rag_retrieval",
      "rank": 1,
      "used_for_main_ranking": false,
      "disclaimer": "검색된 의료 문서 기반 참고 후보이며 확정 진단이 아닙니다."
    }
  ],
  "medical_rag_metadata": {
    "enabled": true,
    "used": true,
    "fallback_reason": null,
    "query": "...",
    "top_k": 5,
    "source_policy": "kdca_nhs_mayo_retrieval_only",
    "used_for_main_ranking": false
  }
}
```

### Query 생성

Medical RAG 검색 query는 rule 결과와 사용자 입력을 합쳐 만든다.

포함 후보:

- body region/body part 이름
- 선택 증상 이름
- 선택 context 이름
- free text
- red flag message
- 메인 rule candidate 이름과 matched reasons

주의:

- 사용자의 자가 추측 질환명은 query에 포함할 수는 있지만, RAG 후보 확정 근거로 단독 사용하지 않는다.
- 개인정보, 주민번호, 이름 등은 query에 넣지 않는다.

### 실패 처리

Medical RAG는 보조 기능이므로 실패해도 `/assess` 전체가 실패하면 안 된다.

권장 fallback:

```json
{
  "rag_related_conditions": [],
  "medical_rag_metadata": {
    "enabled": true,
    "used": false,
    "fallback_reason": "medical_rag_error",
    "used_for_main_ranking": false
  }
}
```

## 2차 통합 방향

1차 운영/검증 후 다음 조건이 충족되면 rule/RAG 통합 랭킹을 검토한다.

- retrieval distance 또는 score를 응답/내부 metadata로 확보
- topic별 aggregate score 계산
- rule 후보와 RAG topic의 canonical condition mapping 확보
- red flag 오탐/누락 검토
- 부위별 UI spec 질문이 code화되어 evidence 밀도가 올라간 상태

2차에서도 red flag와 응급 안내는 rule 우선이다.

## UI Spec 반영 방향

`docs/SYMPTOM_CHECKER_*_UI_SPEC.md` 문서들은 질문과 evidence code를 부위별로 정리한다.

현재 코드 반영 위치:

- context code: `CONTEXT_OPTIONS`
- 부위별 chip: `REGION_CONTEXT_CHIPS`, `BODY_PART_CONTEXT_CHIP_CODES`
- 후속 질문: `REGION_FOLLOW_UP_QUESTIONS`, `BODY_PART_FOLLOW_UP_QUESTIONS`
- rule 후보: `CONDITION_RULES`, `SPEC_CONDITION_RULES`, `SPEC_RULE_UPDATES`
- 응답 schema: `FollowUpQuestionResponse`

반영 순서:

1. UI spec의 context code 후보를 `CONTEXT_OPTIONS`에 추가한다.
2. 질문을 body part별 `BODY_PART_FOLLOW_UP_QUESTIONS`에 넣는다.
3. 안전 확인 질문은 `red_flag` purpose로 분리한다.
4. evidence 조합이 충분한 질환은 rule 후보에 추가한다.
5. evidence가 부족한 질환은 possible candidate로 남긴다.
6. Medical RAG 보조 후보는 이 질문 답변을 query 품질 향상에 사용한다.

## 다음 구현 체크리스트

1. 증상체커 schema에 `rag_related_conditions`, `medical_rag_metadata` 선택 필드 추가
2. `include_rag_candidates` query flag 추가
3. `build_medical_rag_query_from_assessment()` adapter 추가
4. Medical RAG `retrieve_documents()`만 호출하는 보조 후보 변환 함수 추가
5. 실패해도 assessment를 반환하는 fallback 처리
6. 단위 테스트: RAG 성공, RAG 실패, flag false, Gemini explanation 동시 요청 경계
7. 이후 UI spec context/question 반영

## 열린 질문

- RAG 보조 후보의 display name을 `topic`, `title`, LLM 번역 중 무엇으로 할지 결정해야 한다.
- Chroma 검색 distance를 Medical RAG 내부에서 받을지 여부를 결정해야 한다.
- 증상체커 query용 `top_k` 기본값을 정해야 한다.
- `include_gemini_explanation=true`와 `include_rag_candidates=true`가 동시에 들어온 경우 응답 필드 조합 정책을 테스트로 고정해야 한다.
