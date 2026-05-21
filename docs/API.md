# API

이 문서는 Health Navigator-Management 백엔드의 주요 API와 응답 구조를 정리합니다.

## API 문서

FastAPI 서버 실행 후 Swagger UI에서 전체 API 문서를 확인할 수 있습니다.

```text
http://localhost:8000/docs
```

## API 개요

| Method | Endpoint | 설명 |
| --- | --- | --- |
| GET | `/` | 서버 상태 확인 |
| POST | `/auth/signup` | 회원가입 |
| POST | `/auth/login` | 로그인 및 JWT 발급 |
| GET | `/auth/me` | 현재 사용자 조회 |
| POST | `/health-check/ocr` | 건강검진표 OCR 및 파싱 |
| POST | `/health-check/results` | 로그인 사용자 기준 OCR 결과 저장 |
| PATCH | `/health-check/results/{result_id}` | 저장된 OCR 결과 수정 및 재판정 |
| GET | `/symptom-checker/body-regions` | 인체 UI의 큰 부위 목록 조회 |
| GET | `/symptom-checker/contexts` | 증상 평가에 사용할 컨텍스트 선택지 조회 |
| GET | `/symptom-checker/body-regions/{region_id}/symptoms` | 특정 큰 부위의 세부 부위와 증상 선택지 조회 |
| GET | `/symptom-checker/body-regions/{region_id}/context-guide` | 부위별 context chip, 선택 서술형 입력 예시, 후속 질문 후보 조회 |
| POST | `/symptom-checker/structure` | LLM/BERT/alias dictionary가 만든 서술형 입력 구조화 후보를 whitelist로 검증 |
| POST | `/symptom-checker/structure/medical-bert` | 로컬 의료 BERT 기반 서술형 입력 구조화 후보 추출. 모델 미설정/비활성화 시 manual fallback |
| POST | `/symptom-checker/assessment-draft` | 서술형 입력 구조화 결과를 `/assess` 요청 초안으로 변환 |
| POST | `/symptom-checker/assessment-draft/medical-bert` | 로컬 의료 BERT 후보를 `/assess` 요청 초안으로 병합 |
| POST | `/symptom-checker/explain` | 기존 증상 평가 결과에 검수된 설명 카드와 안전 metadata를 추가 |
| POST | `/symptom-checker/assess` | 비로그인 사용자의 성별, 생년월일, 선택한 부위, 증상, 강도, 컨텍스트 기반 질환 후보 조회. `include_explanation=true`이면 RAG 설명 카드도 함께 반환 |
| POST | `/symptom-checker/assess/me` | 로그인 사용자 정보와 선택한 부위, 증상, 강도, 컨텍스트 기반 질환 후보 조회. `include_explanation=true`이면 RAG 설명 카드도 함께 반환 |
| GET | `/drugs` | 의약품 목록 조회 |
| GET | `/drugs/autocomplete` | 의약품 검색 자동완성 |
| GET | `/drugs/search` | 의약품 검색 |
| GET | `/drugs/{item_seq}` | 의약품 상세 조회 |
| POST | `/drugs/check-interaction` | 직접 선택한 약물 간 병용금기 검사 |
| POST | `/drugs/check-duplicate` | 직접 선택한 약물 간 중복 복용 검사 |
| GET | `/drugs/my-medications` | 내 복용약 목록 조회 |
| POST | `/drugs/my-medications` | 내 복용약 등록 |
| DELETE | `/drugs/my-medications/{medication_id}` | 내 복용약 삭제 |
| POST | `/drugs/my-medications/check-interaction` | 내 복용약 기준 병용금기 검사 |
| POST | `/drugs/my-medications/check-duplicate` | 내 복용약 기준 중복 복용 검사 |

## 인체 기반 증상 탐색 API 초안

이 기능은 1차 API 골격과 v2 위험 신호 규칙이 구현된 상태입니다. 응답은 진단이나 처방이 아니라 `가능성 있는 질환 후보`, `참고 정보`, `위험 신호`로 표현합니다.

LLM 답변 생성 전 단계의 1차 시연/검증 기준은 `docs/SYMPTOM_CHECKER_FIRST_PASS_DEMO.md`를 따릅니다.

endpoint는 다음과 같습니다.

| Method | Endpoint | 설명 |
| --- | --- | --- |
| GET | `/symptom-checker/body-regions` | 인체 UI의 큰 부위 목록 조회 |
| GET | `/symptom-checker/contexts` | 증상 평가에 사용할 컨텍스트 선택지 조회 |
| GET | `/symptom-checker/body-regions/{region_id}/symptoms` | 특정 큰 부위의 세부 부위와 증상 선택지 조회 |
| POST | `/symptom-checker/structure` | LLM/BERT/alias dictionary가 만든 서술형 입력 구조화 후보를 whitelist로 검증 |
| POST | `/symptom-checker/structure/medical-bert` | 로컬 의료 BERT 기반 서술형 입력 구조화 후보 추출. 모델 미설정/비활성화 시 manual fallback |
| POST | `/symptom-checker/assessment-draft` | 구조화 후보를 선택형 평가 요청 초안으로 변환 |
| POST | `/symptom-checker/assessment-draft/medical-bert` | 로컬 의료 BERT 후보를 선택형 평가 요청 초안으로 병합 |
| POST | `/symptom-checker/explain` | `/assess` 또는 `/assess/me` 결과를 바꾸지 않고 검수된 설명 카드만 추가 |
| POST | `/symptom-checker/assess` | 비로그인 사용자의 성별, 생년월일, 선택한 부위, 증상, 강도, 컨텍스트 기반 질환 후보 조회. `include_explanation=true`이면 RAG 설명 카드도 함께 반환 |
| POST | `/symptom-checker/assess/me` | 로그인 사용자 정보와 선택한 부위, 증상, 강도, 컨텍스트 기반 질환 후보 조회. `include_explanation=true`이면 RAG 설명 카드도 함께 반환 |

`/symptom-checker/structure`는 외부 모델을 직접 호출하지 않습니다. 모델이나 alias dictionary가 만든 `body_region`, `symptom_candidates`, `context_candidates` 후보를 내부 whitelist로 검증하고, `condition_candidates`, `red_flags`, `confidence`, `severity`, `diagnosis`, `treatment` 같은 판단 필드는 무시합니다. 실제 판단은 `/assess`의 rule engine에서만 수행합니다.

`free_text`만 들어온 경우에도 관리 중인 선택지 이름과 alias hint를 이용해 후보 code를 추출할 수 있습니다. 이 추출은 최종 판단이 아니라 후보 검증 보조이며, code 공백은 whitelist 검증 전에 정리합니다. alias matching은 짧은 한국어 단어가 문장 경계에서 우연히 붙는 오탐을 줄이도록 보수적으로 처리합니다. 예를 들어 `흉통`, `숨참`, `피 섞인 가래` 같은 표현은 내부 후보 code로만 정규화되며, red flag나 질환 후보 판단은 `/assess`에서만 수행됩니다.

응답에는 거절된 후보의 이유를 담는 `rejection_reasons`와, 모델/provider가 보냈지만 판단에 쓰지 않은 `ignored_judgment_fields`가 포함됩니다. 예를 들어 알 수 없는 부위는 `unknown_body_region`, 해당 부위에 허용되지 않는 증상은 `unknown_or_not_allowed_for_body_region`, 알 수 없는 context는 `unknown_context`로 표시합니다.

예시 응답:

```json
{
  "source": "llm",
  "body_region": "chest",
  "symptom_candidates": ["pain"],
  "context_candidates": ["chest_pressure", "cold_sweat"],
  "rejected": {
    "body_region": null,
    "symptom_candidates": ["dryness"],
    "context_candidates": ["made_up_context"]
  },
  "rejection_reasons": {
    "body_region": null,
    "symptom_candidates": {
      "dryness": "unknown_or_not_allowed_for_body_region"
    },
    "context_candidates": {
      "made_up_context": "unknown_context"
    }
  },
  "ignored_judgment_fields": [
    "condition_candidates",
    "red_flags",
    "confidence",
    "severity",
    "diagnosis",
    "treatment"
  ],
  "judgment_fields_ignored": true,
  "final_judgment_performed": false
}
```

`/symptom-checker/assessment-draft`는 `/structure`와 같은 후보 검증을 거친 뒤, 사용자가 `/assess` 또는 `/assess/me`로 넘길 수 있는 선택형 입력 초안을 만듭니다. 이 endpoint도 최종 판단을 수행하지 않으며, `red_flags`, `candidates`, `confidence`, `severity`, `suggested_action`을 생성하지 않습니다. `ready_for_assessment`가 `false`이면 `missing_required_fields`를 보고 사용자가 부위 또는 증상을 추가 선택해야 합니다.

예시 요청:

```json
{
  "free_text": "가슴이 꽉 누르는 느낌이고 왼쪽 팔까지 저려요. 숨도 좀 차요.",
  "body_part": "center_chest",
  "default_severity": 7,
  "default_duration_hours": 2
}
```

예시 응답:

```json
{
  "source": "manual",
  "body_region": "chest",
  "body_part": "center_chest",
  "symptoms": [
    {
      "code": "numbness",
      "severity": 7,
      "duration_hours": 2
    },
    {
      "code": "shortness_of_breath",
      "severity": 7,
      "duration_hours": 2
    }
  ],
  "contexts": {
    "radiating_left_arm_or_jaw_or_back": true,
    "chest_pressure": true
  },
  "additional_context": {
    "recent_medications": [],
    "recent_conditions": [],
    "lab_values": [],
    "free_text": "가슴이 꽉 누르는 느낌이고 왼쪽 팔까지 저려요. 숨도 좀 차요."
  },
  "ready_for_assessment": true,
  "missing_required_fields": [],
  "judgment_fields_ignored": true,
  "final_judgment_performed": false
}
```

`/symptom-checker/assess?include_explanation=true`와 `/symptom-checker/assess/me?include_explanation=true`는 평가 결과에 검수된 내부 RAG 설명 카드를 바로 붙여 반환합니다. RAG 설명은 이미 생성된 `red_flags`, `candidates`, `confidence`, `severity`, `suggested_action`을 만들거나 바꾸지 않습니다. 응답에는 `explanations`, `explanation_safety`, `generated_summary_ko`, `provider_metadata`가 추가됩니다.

`/symptom-checker/explain`은 별도 설명 조회가 필요할 때 사용하는 endpoint입니다. 기본 API 경로에서는 외부 LLM/provider를 호출하지 않습니다. `/assess` 또는 `/assess/me`가 만든 평가 결과를 입력으로 받아 검수된 내부 설명 카드와 안전한 기본 요약을 붙이며, `red_flags`, `candidates`, `confidence`, `severity`, `suggested_action`을 생성하거나 수정하지 않습니다. 내부 구현에는 provider adapter가 사용할 RAG context builder, 최소 provider payload/prompt builder, 안전 필터가 준비되어 있으며, 향후 provider 출력은 금지 표현 검사 후 최대 700자의 `generated_summary_ko`에만 실릴 수 있습니다.

평가 요청 예시는 다음과 같습니다.

```json
{
  "gender": "female",
  "birth_date": "2000-01-01",
  "body_region": "head_face",
  "body_part": "temple",
  "symptoms": [
    {
      "code": "pain",
      "severity": 7,
      "duration_hours": 12
    }
  ],
  "contexts": {
    "alcohol_yesterday": true,
    "sleep_deprivation": true,
    "overeating": false,
    "stress": true
  }
}
```

위험 신호 판단이 필요한 경우에는 `/symptom-checker/contexts`와 부위별 `/context-guide`에서 내려주는 세부 컨텍스트를 함께 전송합니다. 1차 UI는 조건부 질문 엔진 대신 `/context-guide`의 `context_chips`를 부위별 chip/checkbox로 노출하고, 선택 서술형 입력은 보조 입력으로 둡니다. 예를 들어 가슴 통증과 호흡곤란에 압박감이나 방사통 맥락이 함께 있으면 `red_flags`가 우선 반환될 수 있습니다.

`context_chips`는 전체 context 중 해당 부위에서 우선 노출할 항목입니다. 각 chip은 내부 context 원본 정보와 함께 UI 표시 그룹, 표시 순서, 선정 이유, 근거 기준을 포함합니다.

```json
{
  "region_id": "chest",
  "context_chips": [
    {
      "code": "chest_pressure",
      "name": "가슴 압박감",
      "category": "red_flag_detail",
      "description": "가슴이 눌리거나 조이는 느낌인지",
      "usage": ["red_flag", "explanation_context"],
      "rule_strength": "strong",
      "display_group": "safety",
      "display_priority": 1,
      "selection_rationale": "가슴 통증 red flag 설명에 직접 연결되는 압박감 맥락입니다.",
      "evidence_basis": "reviewed_red_flag_rule_supporting_context"
    }
  ]
}
```

```json
{
  "gender": "female",
  "birth_date": "2000-01-01",
  "body_region": "chest",
  "symptoms": [
    {
      "code": "pain",
      "severity": 8,
      "duration_hours": 1
    },
    {
      "code": "shortness_of_breath",
      "severity": 7,
      "duration_hours": 1
    }
  ],
  "contexts": {
    "chest_pressure": true,
    "radiating_left_arm_or_jaw_or_back": true
  }
}
```

로그인 사용자는 `/symptom-checker/assess/me`를 호출하며, 요청 본문에 `gender`, `birth_date`를 넣지 않습니다. 백엔드는 JWT 토큰으로 현재 사용자를 확인한 뒤 저장된 `gender`, `birth_date`를 평가에 사용합니다.

응답 예시는 다음과 같습니다.

```json
{
  "disclaimer": "이 결과는 진단이 아닌 참고용 정보입니다.",
  "profile": {
    "gender": "female",
    "birth_date": "2000-01-01",
    "source": "request",
    "age": 26
  },
  "input_analysis": {
    "body_region": "head_face",
    "body_part": "temple",
    "selected_symptom_codes": ["pain"],
    "selected_context_codes": ["alcohol_yesterday", "sleep_deprivation", "stress"],
    "free_text": "잠을 못 자고 관자놀이가 욱신거려요.",
    "free_text_symptom_candidates": [],
    "free_text_context_candidates": [],
    "merged_symptom_codes": ["pain"],
    "merged_context_codes": ["alcohol_yesterday", "sleep_deprivation", "stress"],
    "free_text_used_for_candidate_matching": false
  },
  "candidate_generation": {
    "mode": "reviewed_rule_based_candidate_ranking",
    "source_layers": [
      "manual_seed_rules",
      "approved_ddxplus_frequency_tie_break",
      "reviewed_explanation_cards_available_via_explain"
    ],
    "ddxplus_usage": "approved_frequency_tie_break_only",
    "rag_usage": "explanation_only_not_judgment",
    "explain_endpoint": "/symptom-checker/explain",
    "judgment_mutation_allowed_by_rag": false
  },
  "red_flags": [],
  "candidates": [
    {
      "condition_code": "tension_headache",
      "condition_name": "긴장성 두통",
      "confidence": "medium",
      "matched_reasons": [
        "관자놀이 통증",
        "수면 부족",
        "스트레스"
      ],
      "suggested_action": "증상이 지속되거나 악화되면 의료기관 상담을 권장합니다."
    }
  ],
  "possible_candidates": [],
  "missing_evidence_questions": []
}
```

`input_analysis`는 사용자가 선택한 증상/맥락과 서술형 입력에서 추출된 후보를 분리해서 보여줍니다. `merged_symptom_codes`와 `merged_context_codes`가 실제 후보 생성에 들어간 값입니다. 서술형 입력이 후보 생성에 반영되면 `free_text_used_for_candidate_matching`이 `true`가 됩니다.

후보가 확정적으로 매칭되지 않았지만 일부 근거가 맞는 경우에는 `possible_candidates`와 `missing_evidence_questions`가 내려옵니다. 이 값은 상세 확인 단계처럼 추가 확인 질문을 만들기 위한 참고 목록이며, 질병 후보 확정 목록인 `candidates`와 분리해서 표시합니다.

예를 들어 눈 부위에서 사용자가 통증을 선택하고 서술형으로 "눈 위쪽이 가려워요"라고 쓰면, alias 구조화가 `itching`을 추출해 후보 생성에 병합할 수 있습니다.

```json
{
  "input_analysis": {
    "body_region": "eye",
    "body_part": "eyes",
    "selected_symptom_codes": ["pain"],
    "selected_context_codes": [],
    "free_text": "눈 위쪽이 가려워요.",
    "free_text_symptom_candidates": ["itching"],
    "free_text_context_candidates": [],
    "merged_symptom_codes": ["itching", "pain"],
    "merged_context_codes": [],
    "free_text_used_for_candidate_matching": true
  },
  "candidates": [
    {
      "condition_code": "conjunctivitis",
      "condition_name": "결막염 가능성"
    }
  ],
  "possible_candidates": [
    {
      "condition_code": "dry_eye",
      "condition_name": "안구건조증 가능성",
      "matched_evidence": ["pain"],
      "missing_required_symptoms": ["dryness"],
      "missing_evidence_questions": ["눈 건조감이(가) 있나요?"]
    }
  ]
}
```

위험 신호가 감지된 응답 예시는 다음과 같습니다. `reference_links`는 red flag 판단 근거로 검토한 공식/공공/전문기관 링크를 연결하며, 특정 진단명을 확정하지 않습니다.

```json
{
  "disclaimer": "이 결과는 진단이 아닌 참고용 정보입니다.",
  "profile": {
    "gender": "female",
    "birth_date": "2000-01-01",
    "source": "request"
  },
  "red_flags": [
    {
      "code": "chest_pain_with_shortness_of_breath",
      "severity": "emergency",
      "message": "가슴 통증과 호흡곤란이 함께 선택되었습니다.",
      "reason": "가슴 통증 또는 압박감과 숨참이 함께 있으면 빠른 평가가 필요한 위험 신호일 수 있습니다.",
      "triggered_by": [
        "pain",
        "shortness_of_breath",
        "chest_pressure",
        "radiating_left_arm_or_jaw_or_back"
      ],
      "suggested_action": "응급 신호일 수 있으므로 의료기관 또는 응급실에 빠르게 상담하는 것을 권장합니다.",
      "display_priority": 10,
      "rule_type": "red_flag",
      "evidence_level": "guideline_supported",
      "evidence_strength": "strong",
      "source_status": "approved",
      "review_status": "reviewed",
      "last_reviewed_at": "2026-05-11",
      "reference_links": [
        {
          "title": "급성 심근경색증",
          "url": "https://health.kdca.go.kr/healthinfo/biz/health/gnrlzHealthInfo/gnrlzHealthInfo/gnrlzHealthInfoView.do?cntnts_sn=6770",
          "source": "KDCA"
        }
      ]
    }
  ],
  "candidates": []
}
```

설명 카드 endpoint는 먼저 `/symptom-checker/assess` 또는 `/symptom-checker/assess/me`를 호출한 뒤, 그 응답 전체를 `assessment`에 넣어 호출합니다. Swagger에서는 `/assess` 응답을 복사해 아래 형태로 감싸면 됩니다.

```json
{
  "assessment": {
    "disclaimer": "이 결과는 진단이 아닌 참고용 정보입니다.",
    "profile": {
      "gender": "female",
      "birth_date": "2000-01-01",
      "source": "request"
    },
    "red_flags": [
      {
        "code": "chest_pain_with_shortness_of_breath",
        "severity": "emergency",
        "message": "가슴 통증과 호흡곤란이 함께 선택되었습니다.",
        "reason": "가슴 통증이나 압박감과 호흡곤란이 함께 있으면 심장 관련 응급 신호일 수 있어 빠른 평가가 권장됩니다.",
        "triggered_by": ["pain", "shortness_of_breath"],
        "suggested_action": "응급 신호일 수 있으므로 의료기관 또는 응급실에 빠르게 상담하는 것을 권장합니다.",
        "display_priority": 10,
        "rule_type": "red_flag",
        "evidence_level": "guideline_supported",
        "evidence_strength": "strong",
        "source_status": "approved",
        "review_status": "reviewed",
        "last_reviewed_at": "2026-05-11",
        "reference_links": []
      }
    ],
    "candidates": []
  }
}
```

응답은 입력 `assessment`를 그대로 돌려주고, 설명 카드와 안전 metadata만 추가합니다. 설명 카드는 red flag와 일부 condition candidate에 붙을 수 있으며, condition 설명은 참고 후보의 내부 rule matching 이유만 설명하고 진단을 확정하지 않습니다.

```json
{
  "assessment": {
    "red_flags": [
      {
        "code": "chest_pain_with_shortness_of_breath",
        "severity": "emergency",
        "suggested_action": "응급 신호일 수 있으므로 의료기관 또는 응급실에 빠르게 상담하는 것을 권장합니다."
      }
    ],
    "candidates": []
  },
  "explanations": [
    {
      "target_type": "red_flag",
      "target_code": "chest_pain_with_shortness_of_breath",
      "card_id": "red_flag.chest_pain_with_shortness_of_breath.v1",
      "summary_ko": "가슴 통증과 숨참이 함께 선택되어 빠른 평가가 필요한 위험 신호일 수 있습니다.",
      "rationale_ko": "공식 자료에서는 흉부 불편감과 숨참을 심장 관련 warning sign으로 다룹니다. 이 결과는 특정 질환을 진단하지 않고, 선택된 신호 조합을 바탕으로 빠른 상담이 필요할 수 있음을 안내합니다.",
      "mapping_limit": "활력징후, 심전도, 혈액검사, 진찰 소견을 반영하지 않으므로 심근경색이나 다른 질환을 확정하지 않는다.",
      "source_refs": ["cdc.heart_attack.symptoms", "aha.heart_attack.warning_signs"]
    }
  ],
  "safety": {
    "judgment_mutation_allowed": false,
    "fallback_used": false,
    "blocked_claims": [],
    "missing_explanation_targets": []
  },
  "generated_summary_ko": "선택한 증상 조합에서 빠른 상담이 필요할 수 있는 위험 신호 설명을 정리했습니다. 이 내용은 특정 질환을 확정하지 않는 참고 정보입니다.",
  "provider_metadata": {
    "used": false,
    "fallback_reason": null,
    "name": "none",
    "model_id": "",
    "timeout_ms": 2000
  }
}
```

`red_flags` 항목의 검수 metadata 필드는 다음 의미를 가집니다.

| 필드 | 의미 |
| --- | --- |
| `rule_type` | 현재 응답 항목이 위험 신호 규칙인지 나타냅니다. v2 red flag는 `red_flag`입니다. |
| `evidence_level` | 규칙을 뒷받침하는 근거 성격입니다. 활성 red flag는 `guideline_supported`를 기본으로 합니다. |
| `evidence_strength` | 근거 강도입니다. 현재 활성 v2 red flag는 `strong`으로 관리합니다. |
| `source_status` | 판단 근거로 사용할 수 있는 출처인지 나타냅니다. 활성 red flag는 `approved` 출처만 사용합니다. |
| `review_status` | 사람이 검토한 규칙인지 나타냅니다. 응답으로 노출되는 v2 red flag는 `reviewed` 상태입니다. |
| `last_reviewed_at` | 마지막 검수 기준일입니다. |

## 사용자 인증 응답 구조

회원가입 요청은 `UserCreate` 구조를 사용합니다.

```json
{
  "email": "user@example.com",
  "password": "string",
  "name": "string",
  "birth_date": "2000-01-01",
  "gender": "male"
}
```

회원가입은 기존 `email`, `name`, `password`에 `birth_date`, `gender`를 추가로 입력받습니다. `birth_date`는 `YYYY-MM-DD` 형식이고 오늘 이후 날짜는 허용하지 않습니다. `gender`는 `male` 또는 `female`만 허용합니다.

회원가입과 현재 사용자 조회 응답은 `UserResponse` 구조를 사용합니다.

```json
{
  "id": 0,
  "email": "user@example.com",
  "name": "string",
  "birth_date": "2000-01-01",
  "gender": "male",
  "created_at": "2026-05-10T00:00:00"
}
```

## 건강검진 OCR 응답 구조

`HealthCheckResponse`는 다음 구조로 반환됩니다.

```json
{
  "message": "string",
  "extracted_text": "string",
  "parsing_status": "string",
  "missing_fields": [],
  "data": {
    "name": "string",
    "rrn_masked": "string",
    "gender": "string",
    "birth_date": "string",
    "age": 0
  }
}
```

`data`에는 위 예시의 사용자 식별 관련 필드 외에도 키, 몸무게, BMI, 혈압, 혈당, 콜레스테롤, 간/신장 관련 수치와 각 항목별 판정 결과가 함께 포함됩니다.

현재 코드에서는 필수 수치 추출 여부에 따라 `parsing_status`에 다음 값 중 하나를 넣도록 구성되어 있습니다.

- `success`
- `partial_success`
- `needs_review`

## 건강검진 OCR 결과 저장

`/health-check/results`는 로그인한 사용자만 호출할 수 있으며, JWT 인증이 필요합니다. Flutter에서는 로그인 상태일 때 저장 버튼을 활성화할 수 있지만, 최종 저장 권한은 백엔드가 토큰으로 판단합니다.

요청 구조는 다음과 같습니다.

```json
{
  "extracted_text": "string",
  "parsing_status": "success",
  "missing_fields": [],
  "data": {}
}
```

`/health-check/ocr` 응답에서 `message`를 제외하고 `extracted_text`, `parsing_status`, `missing_fields`, `data`만 저장 API에 전송합니다.

응답 구조는 다음과 같습니다.

```json
{
  "id": 0,
  "user_id": 0,
  "extracted_text": "string",
  "parsing_status": "success",
  "missing_fields": [],
  "data": {},
  "original_data": {},
  "edited_data": null,
  "is_edited": false,
  "created_at": "2026-05-10T00:00:00"
}
```

저장 시 `original_data`와 `data`에는 최초 OCR 파싱 결과 전체가 함께 저장됩니다. 사용자가 결과를 수정하면 백엔드가 기존 `data`에 수정값을 반영하고 rule-based 판정을 다시 계산합니다.

수정 요청은 로그인한 사용자 본인의 결과에만 가능합니다.

```json
{
  "data": {
    "height_cm": 171.2,
    "weight_kg": 68.5,
    "systolic_bp": 120,
    "diastolic_bp": 80,
    "fasting_glucose": 95
  }
}
```

수정 API는 status 필드나 이름, 생년월일, 성별 같은 식별 정보를 직접 받지 않습니다. Flutter는 수정된 건강검진 수치 값만 보내고, 백엔드가 `data`, `edited_data`, `missing_fields`, `parsing_status`, `is_edited`를 갱신합니다.

수정 가능한 필드는 다음과 같습니다.

```text
height_cm, weight_kg, bmi, waist_cm,
systolic_bp, diastolic_bp,
hemoglobin, fasting_glucose,
total_cholesterol, hdl_cholesterol, triglycerides, ldl_cholesterol,
creatinine, egfr,
ast, alt, gamma_gtp
```

## 건강검진 파싱 대상

- 이름
- 주민등록번호 일부 (`앞 6자리-뒤 첫 번째 자리`)
- 생년월일
- 나이
- 성별
- 신장, 체중, BMI, 허리둘레
- 혈압
- 혈색소
- 공복혈당
- 총콜레스테롤, HDL, LDL, 중성지방
- 혈청 크레아티닌, e-GFR
- AST, ALT, 감마 GTP

## 의약품 응답 구조

### 자동완성 결과

의약품 자동완성은 `q`를 한 글자 이상 입력했을 때 후보 목록을 반환합니다. `limit`은 기본 10개이며 최대 20개로 제한합니다.

```text
GET /drugs/autocomplete?q=타이레&limit=10
```

응답 구조는 다음과 같습니다.

```json
[
  {
    "itemSeq": "string",
    "itemName": "string",
    "entpName": "string"
  }
]
```

### 검색 결과

의약품 검색과 목록 조회는 `DrugSearchResponse` 구조를 사용합니다.

```json
{
  "itemSeq": "string",
  "itemName": "string",
  "entpName": "string",
  "ingredientName": "string",
  "ingredientCount": "string",
  "productType": "string",
  "etcOtc": "string",
  "imageUrl": "string"
}
```

### 상세 조회

의약품 상세 조회는 `DrugDetailResponse` 구조를 사용합니다.

```json
{
  "itemSeq": "string",
  "itemName": "string",
  "itemEngName": "string",
  "entpName": "string",
  "ingredient": "string",
  "productType": "string",
  "etcOtc": "string",
  "imageUrl": "string",
  "chart": "string",
  "storage": "string",
  "effect": "string",
  "useMethod": "string",
  "warning": "string",
  "sideEffect": "string",
  "ediCode": "string",
  "atcCode": "string",
  "packUnit": "string",
  "cancelName": "string",
  "permitDate": "string",
  "hasMedicationInfo": true,
  "missingInfoFields": []
}
```

### 병용금기 검사

병용금기 검사는 `InteractionCheckResponse` 구조를 사용합니다.

```json
{
  "hasInteraction": true,
  "count": 0,
  "results": [
    {
      "source": "string",
      "type": "string",
      "drugASeq": "string",
      "drugAName": "string",
      "ingredientA": "string",
      "drugBSeq": "string",
      "drugBName": "string",
      "ingredientB": "string",
      "reason": "string"
    }
  ],
  "ingredientCodeCheckAvailable": true,
  "message": "string"
}
```

### 중복 복용 검사

중복 복용 검사는 `DuplicateCheckResponse` 구조를 사용합니다.

```json
{
  "hasDuplicate": true,
  "sameDrug": [],
  "ingredientCodeDuplicate": [],
  "atcDuplicate": [],
  "effectGroupDuplicate": [],
  "ingredientNameDuplicate": []
}
```

## Symptom Checker DDXPlus 보조 응답

`/symptom-checker/assess`와 `/symptom-checker/assess/me`의 `candidates[]` 항목은 DDXPlus approved frequency baseline이 있는 경우 `dataset_support`를 포함할 수 있습니다.

`dataset_support`는 후보 순위 보조 metadata입니다. red flag 생성, red flag severity, 응급 안내 문구에는 사용하지 않습니다. baseline 파일이 없거나 로드에 실패하면 이 필드는 `null`이거나 생략될 수 있으며, 기존 rule-only 후보 응답으로 동작합니다.

```json
{
  "condition_code": "arrhythmia_candidate",
  "confidence": "medium",
  "dataset_support": {
    "source": "DDXPlus",
    "baseline_type": "frequency",
    "support_level": "frequency_baseline",
    "candidate_ranking_only": true,
    "red_flag_usage": false,
    "requires_human_review_before_service_integration": true,
    "row_count": 21036,
    "prior_probability_within_approved_rows": 0.0842,
    "top_evidence_ids": ["E_155"]
  }
}
```

