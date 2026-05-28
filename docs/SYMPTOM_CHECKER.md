# Symptom Checker Design

## 2026-05-21 Body-map based Candidate Generation Gap

현재 인체 UI 흐름은 외부 증상체커의 `INFO -> SYMPTOMS -> CONDITIONS -> DETAILS -> TREATMENT` 흐름을 참고하지만, 후보 생성기는 아직 MVP seed 단계입니다.

### 외부 증상체커 공개 흐름에서 가져올 수 있는 근거

참고한 외부 증상체커의 공개 흐름에서 확인되는 기준은 다음과 같습니다.

- 해당 증상체커는 age/sex 같은 기본 정보를 받고, body map 기반으로 증상을 선택한 뒤 가능한 condition 또는 issue를 보여주는 흐름입니다.
- 앱 설명은 “불편한 신체 부위를 선택하고 증상을 고른 뒤 potential conditions or issues를 본다”는 제품 기준을 제시합니다.
- 공개 페이지는 “body location으로 증상을 선택할 수 있고 여러 증상을 빠르게 선택할 수 있다”는 방향을 제시합니다.
- 해당 서비스는 이 도구가 medical advice, diagnosis, treatment의 대체물이 아니며, 응급 상황에서는 doctor 또는 911에 연락하라고 명시합니다.

따라서 우리 기능은 외부 증상체커의 UI 흐름을 참고하되, 다음 범위로 제한합니다.

```text
허용: body location + symptoms + basic profile 기반 참고 후보군 표시
허용: 추가 확인 질문으로 후보군을 좁히기
허용: reviewed source/card 기반 설명
금지: 확정 진단, 처방, 치료 지시, RAG/LLM 기반 새 판단 생성
```

확인된 기준선:

- active condition seed rule: 60개
- DDXPlus approved condition mapping: 6개
- DDXPlus frequency baseline: candidate ranking tie-break 보조 전용
- RAG: 이미 생성된 후보/red flag 설명 전용

따라서 현재 빈번한 `후보 없음`은 프론트 UI 문제가 아니라 `symptom/context -> condition candidate` 지식베이스와 scoring schema가 좁기 때문입니다.

다음 개선 방향:

1. UI의 `맥락` 입력을 `동반 증상`, `증상 특징`, `생활/상황 요인`, `위험 확인 항목`으로 분리합니다.
2. `/assess`는 빠른 후보 생성만 수행하고, RAG 설명은 `/explain` 또는 후보 상세 단계로 분리합니다.
3. 기존 `required_symptoms` rule은 유지하되, 신규 rule schema는 `required_all`, `required_any`, `supporting`, `less_likely`, `red_flag_exclusions`, `age_sex_applicability`, `score_weights`, `review_status`를 포함하도록 확장합니다.
4. 후보가 없을 때 빈 배열만 반환하지 않고 `possible_candidates`와 `missing_evidence_questions`를 반환합니다.
5. DDXPlus와 RAG는 판단을 새로 만들지 않습니다. DDXPlus는 reviewed candidate ranking 보강, RAG는 reviewed explanation card 조회에만 사용합니다.

### Candidate coverage report

인체 UI 흐름처럼 `부위 -> 세부 부위 -> 증상 -> 후보/추가 질문 JSON`이 안정적으로 나오려면 active rule coverage를 수치로 관리해야 합니다.

리포트 생성:

```powershell
cd health-navigator-backend
.\.venv\Scripts\python.exe tools\build_symptom_checker_candidate_coverage.py
```

출력:

```text
app/data/processed/symptom_checker_candidate_coverage_report.json
```

현재 1차 기준선:

```json
{
  "active_condition_rule_count": 60,
  "region_count": 12,
  "symptom_option_count": 71,
  "single_symptom_candidate_option_count": 40,
  "uncovered_symptom_option_count": 0,
  "safety_review_symptom_option_count": 7,
  "single_symptom_candidate_option_ratio": 0.5634,
  "uncovered_symptom_option_ratio": 0.0,
  "safety_review_symptom_option_ratio": 0.0986
}
```

이 리포트는 다음을 함께 제공합니다.

- 부위별 active candidate 수
- 증상별 단일 선택 후보 연결 여부
- 일부 근거만 맞는 `possible_candidates` 후보 연결 여부
- 독립 후보로 바로 연결하지 않고 안전 확인 또는 후속 질문으로 분리한 `safety_review_symptom_codes`
- DDXPlus condition/evidence needs-review 우선순위
- RAG/LLM이 판단값을 만들지 않는 safety policy

후보 확장 작업은 이 리포트의 `region_coverage`, `ddxplus_condition_review_queue`, `ddxplus_evidence_review_queue`를 기준으로 batch 단위로 진행합니다. `needs_review` DDXPlus 항목은 리포트와 검수 큐에만 쓰며, active service rule로 바로 올리지 않습니다.

DDXPlus 후보 확장 초안 생성:

```powershell
cd health-navigator-backend
.\.venv\Scripts\python.exe tools\draft_ddxplus_candidate_expansion.py
```

출력:

```text
app/data/review/ddxplus_candidate_expansion_draft.json
```

이 파일은 active service 입력이 아니라 검수용 초안입니다. 각 draft에는 다음 추천 상태가 붙습니다.

| status | 의미 |
| --- | --- |
| `candidate_rule_batch_candidate` | 현재 symptom/context mapping이 비교적 작고 명확해 1차 rule 검수 batch 후보로 볼 수 있음 |
| `needs_symptom_option_review` | 흔한 후보군이지만 내부 증상/context 선택지 추가 또는 DDXPlus evidence 검토가 먼저 필요함 |
| `hold_for_clinical_scope_review` | 만성/고위험/범위가 넓은 질환이라 단순 참고 후보로 바로 올리기 어려움 |
| `hold_for_scope_review` | 안정적인 body region mapping이 부족함 |
| `hold_for_evidence_mapping` | 현재 증상 evidence가 내부 code로 직접 매핑되지 않음 |
| `hold_for_mapping_cleanup` | evidence mapping이 넓어 active rule에 바로 쓰기 어려움 |

현재 첫 batch 후보:

```text
candidate_rule_batch_candidate:
- Bronchospasm / acute asthma exacerbation
- Bronchiolitis

needs_symptom_option_review:
- Acute laryngitis
- Cluster headache
- Acute rhinosinusitis
- Chronic rhinosinusitis
- Pneumonia
```

이 문서는 인체 기반 UI에서 선택한 부위, 증상, 강도, 생활 컨텍스트를 바탕으로 `가능성 있는 질환 후보`와 `참고 정보`를 반환하는 백엔드 기능 초안을 정리합니다.

이 기능은 의료 진단이나 처방을 제공하지 않습니다. 응답 문구는 항상 참고용 정보로 제한하고, 위험 신호가 감지되면 질환 후보보다 의료기관 방문 안내를 우선합니다.

## 1차 목표

- Flutter가 인체 UI에서 큰 부위와 세부 부위 또는 증상을 선택할 수 있도록 백엔드 기준 코드를 제공한다.
- 비로그인 사용자는 성별과 생년월일을 직접 입력하고, 로그인 사용자는 저장된 사용자 정보로 해당 단계를 건너뛴다.
- 사용자가 선택한 증상, 강도, 기간, 생활 컨텍스트를 구조화된 요청으로 받는다.
- 요청값과 매칭되는 질환 후보를 참고 정보 형태로 반환한다.
- 데이터셋이 확정되지 않아도 나중에 DB 또는 외부 데이터셋으로 교체 가능한 구조를 먼저 잡는다.

## 제외 범위

- 확정적 진단, 처방, 치료 지시.
- 응급 질환을 배제한다는 표현.
- LLM이 직접 의료 판단을 내리는 구조.
- 데이터셋 라이선스 확인 전 대량 콘텐츠 저장 또는 재배포.
- Flutter 화면 구현.

## 사용자 입력 모델

1차 입력은 선택형 중심으로 둡니다.

- 큰 부위: 1차 확정 범주 `head_face`, `eye`, `ear_nose_throat`, `neck_shoulder`, `chest`, `abdomen`, `pelvis_urinary`, `back_waist`, `arm_hand`, `leg_foot`, `skin`, `general`
- 세부 부위: 예시 `temple`, `forehead`, `eye_area`, `lower_abdomen`
- 증상: 예시 `pain`, `numbness`, `swelling`, `fever`, `dizziness`, `nausea`, `rash`
- 강도: 1에서 10 사이 숫자
- 기간: 시간 또는 일 단위
- 양상: 갑작스러움, 반복 여부, 악화 여부
- 생활 컨텍스트와 양상: 기본 후보 점수 보강에는 `alcohol_yesterday`, `sleep_deprivation`, `overeating`, `recent_exercise`, `stress`, `sudden_onset`, `worsening`, `after_injury`를 사용한다. v2 위험 신호 판단에는 별도 세부 컨텍스트를 추가로 사용한다.

입력 흐름은 다음 순서로 둡니다.

1. 성별과 생년월일 확인
   - 비로그인 사용자는 `POST /symptom-checker/assess` 요청에 `gender`, `birth_date`를 포함합니다.
   - 로그인 사용자는 `POST /symptom-checker/assess/me`를 사용하며, 백엔드가 토큰의 사용자 정보에서 `gender`, `birth_date`를 채웁니다.
2. 큰 부위 선택
3. 세부 부위 선택
4. 증상과 강도 선택
5. 생활 컨텍스트와 증상 양상 선택
6. 참고용 질환 후보와 위험 신호 반환

자연어 입력은 2차 확장으로 둡니다. 자연어를 받더라도 LLM은 진단자가 아니라 입력 구조화 보조 역할로 제한합니다.

## LLM/RAG 부착 위치

LLM과 RAG는 의료 판단을 새로 만드는 계층이 아니라, 입력 정리와 설명 생성을 돕는 보조 계층으로 둡니다.

중요한 기준:

- rule 자체가 의학적 근거의 원천이 아니다.
- active rule은 공식/공공/전문기관 evidence를 사람이 검수해 내부 입력 조건으로 번역한 실행 조건이다.
- RAG는 런타임에서 새 판단을 만드는 도구가 아니라, evidence-reviewed rule 결과를 공식 출처 claim과 mapping limit 안에서 설명하는 도구다.

전체 흐름:

```text
설계/검수 단계
  공식/공공/전문기관 evidence
  -> source_claim 추출
  -> 사람이 검수
  -> 내부 symptom/context code로 mapping
  -> mapping_limit 기록
  -> evidence-reviewed rule 생성

런타임 단계
  사용자 입력
  -> 입력 검증
  -> LLM 자유 입력 구조화, 선택 기능
  -> evidence-reviewed rule engine
  -> DDXPlus/model candidate ranking 보조
  -> red flag rule 판단
  -> 내부 설명 카드/RAG 조회
  -> LLM 사용자용 설명 생성
  -> API 응답
```

LLM 사용 위치:

| 위치 | 역할 | 제한 |
| --- | --- | --- |
| 평가 전 | 자유 입력을 내부 `symptom_code`/`context_code` 후보로 구조화 | 후보만 반환하며, rule engine 검증 전에는 판단에 쓰지 않습니다. |
| 평가 전 | 기존 follow-up question id 추천 | 질문 문장을 새로 만들기보다 `REGION_FOLLOW_UP_QUESTIONS`의 id를 추천합니다. |
| 응답 직전 | rule/model/RAG 결과를 사용자용 문장으로 변환 | 질환 후보, red flag, confidence를 새로 만들거나 변경하지 않습니다. |

LLM 출력 제한:

- `condition_code`, red flag code, confidence를 새로 생성하면 무시합니다.
- 진단, 확정, 처방, 복용 지시 표현을 생성하지 않습니다.
- red flag가 있는 경우 긴급성은 rule 결과의 `suggested_action`만 풀어 씁니다.

RAG는 외부 웹 검색이 아니라 내부 검수 설명 카드 검색으로 시작합니다.

예상 카드 위치:

```text
health-navigator-backend/app/data/explanation_cards/
  conditions.json
  red_flags.json
  source_refs.json
```

설명 카드 필드:

| 필드 | 의미 |
| --- | --- |
| `card_id` | 카드 고유 ID. 예: `red_flag.chest_pain_with_shortness_of_breath.v1` |
| `card_type` | `red_flag_explanation`, `condition_explanation`, `source_ref` 중 하나 |
| `red_flag_code` | red flag 설명 카드가 연결되는 내부 rule code. condition 카드에서는 `null` |
| `condition_code` | 내부 후보 질환 코드. red flag 카드에서는 `null` |
| `triggered_by` | 이 카드가 설명할 수 있는 symptom/context code 목록. 실제 응답의 `triggered_by`와 교차 확인하는 검색 키 |
| `matched_reasons` | condition 후보 카드에서 설명에 사용할 수 있는 매칭 이유 label 후보 |
| `mapped_rule_condition` | 공식 출처의 위험 신호를 내부 rule 조건으로 번역한 문장 |
| `summary_ko` | 사용자에게 보여줄 한국어 요약 |
| `rationale_ko` | 왜 후보로 표시됐는지 설명 |
| `red_flag_notes_ko` | 검수된 위험 신호 안내 |
| `official_source_refs` | 검수된 출처 ID 목록 |
| `source_claim` | 공식 출처가 실제로 말하는 신호 범위. 내부 rule을 정당화하기 위해 과장하지 않음 |
| `mapping_limit` | 내부 rule로 번역할 때 잃는 정보와 한계. 예: 활력징후, 검사, 진찰 소견 미반영 |
| `source_usage_policy` | `approved`, `restricted/reference_only` 같은 사용 정책 |
| `must_not_claim` | LLM/템플릿이 말하면 안 되는 표현. 예: 확정 진단, 처방, 위험도 단정 |
| `review_status` | `draft`, `reviewed`, `needs_update`, `rejected` 중 하나 |
| `last_reviewed_at` | 마지막 검수 기준일 |

카드 예시:

```json
{
  "card_id": "red_flag.chest_pain_with_shortness_of_breath.v1",
  "card_type": "red_flag_explanation",
  "red_flag_code": "chest_pain_with_shortness_of_breath",
  "condition_code": null,
  "triggered_by": ["pain", "shortness_of_breath"],
  "matched_reasons": [],
  "mapped_rule_condition": "chest region pain symptom + shortness_of_breath symptom",
  "summary_ko": "가슴 통증과 숨참이 함께 선택되어 빠른 평가가 필요한 위험 신호일 수 있습니다.",
  "rationale_ko": "공식 자료에서는 흉부 불편감과 숨참을 심장 관련 warning sign으로 다룹니다. 이 결과는 특정 질환을 진단하지 않고, 선택된 신호 조합을 바탕으로 빠른 상담이 필요할 수 있음을 안내합니다.",
  "red_flag_notes_ko": "심한 증상, 지속되는 증상, 의식 변화, 식은땀, 방사통이 동반되면 응급 상담이 더 중요할 수 있습니다.",
  "official_source_refs": ["cdc.heart_attack.symptoms", "aha.heart_attack.warning_signs"],
  "source_claim": "CDC/AHA는 흉부 불편감, 숨참, 식은땀, 팔/턱/등 통증 등을 heart attack warning sign으로 제시한다.",
  "mapping_limit": "활력징후, 심전도, 혈액검사, 진찰 소견을 반영하지 않으므로 심근경색이나 다른 질환을 확정하지 않는다.",
  "source_usage_policy": "approved",
  "must_not_claim": ["심근경색입니다", "확정 진단", "약을 복용하세요", "괜찮습니다"],
  "review_status": "reviewed",
  "last_reviewed_at": "2026-05-15"
}
```

검색 방식:

1. `/symptom-checker/assess`가 rule engine으로 `red_flags[]`와 `candidates[]`를 만든다.
2. `red_flag_code` 또는 `condition_code`로 1차 exact lookup을 수행한다.
3. 같은 code에 카드가 여러 개 있으면 `triggered_by`와 `matched_reasons` 교집합이 큰 카드를 우선한다.
4. 그래도 동률이면 `review_status: "reviewed"`와 최신 `last_reviewed_at`을 우선한다.
5. red flag 설명은 `display_priority`가 낮은 순서로 먼저 붙이고, condition 설명은 `/assess`가 만든 candidate 순서를 따른다.
6. 같은 `target_type`과 `target_code`에 대한 설명 카드는 한 번만 선택해 중복 표시를 막는다.
7. 벡터 검색은 카드가 많아져 exact lookup만으로 설명 선택이 어려울 때 보조로 검토한다.

정확성 기준:

- 정확성은 “질환 진단 정확도”가 아니라 “공식 출처가 말한 위험 신호를 내부 rule 조건과 한계 안에서 정확히 설명하는가”로 본다.
- 카드가 내부 rule 조건보다 넓은 의학적 판단을 주장하면 안 된다.
- `source_claim`은 공식 출처의 신호 범위를 요약하고, `mapped_rule_condition`은 서비스가 실제로 사용하는 조건만 적는다.
- `mapping_limit`이 비어 있으면 reviewed 상태로 올리지 않는다.

RAG source policy:

| policy | 허용 출처 예 | 허용 용도 | 금지 용도 |
| --- | --- | --- | --- |
| `approved` | KDCA, CDC, NIH/NHLBI/NEI/NINDS, NICE, NHS, WHO, AHA, AAO EyeWiki, NCBI Bookshelf, PubMed guideline, 사람이 검수한 DDXPlus/HPO 매핑 | red flag 설명 카드 근거, active rule 근거, candidate scoring 보강 근거, 사용자 설명 출처 | 출처 원문을 무단 복제하거나, 내부 rule 조건보다 넓은 진단/처방 주장 생성 |
| `restricted/reference_only` | MedlinePlus, MedlinePlus Medical Encyclopedia, 사용 범위가 제한된 공식 건강정보 링크 | 후보 설명 링크, 출처 메타데이터, 사용자용 참고 설명 보조 | red flag 활성화 근거, confidence 상승, candidate 생성 근거, 외부 본문 크롤링/임베딩 |
| `dataset_supported` | 사전 protocol로 승인된 DDXPlus/HPO/Disease Ontology/Symptom Ontology 매핑 | candidate ranking 보조, `dataset_support` metadata, 검수된 candidate scoring 보강 | red flag 생성, red flag severity, 응급 안내 문구, 단독 high confidence 승격 |
| `internal_reviewed` | 사람이 작성/검수한 내부 설명 카드와 rule mapping record | RAG 설명 카드, `mapped_rule_condition`, `mapping_limit`, `must_not_claim` 관리 | 공식 출처 없이 새 의학 판단 생성 |
| `rejected` | 블로그, 커뮤니티, 광고성 문서, 출처 불명확 자료, 뉴스 단독 근거, 오래되었거나 철회/폐기된 자료 | 사용하지 않음 | 모든 판단/설명/검색/학습 용도 |

테스트 가능한 정책 조건:

- `source_usage_policy`가 `approved`가 아닌 red flag 설명 카드는 `review_status: "reviewed"`가 될 수 없다.
- `restricted/reference_only` 출처만 가진 카드는 `red_flag_code`를 가질 수 없고, `condition_explanation` 또는 `source_ref` 카드로만 둔다.
- `restricted/reference_only` 출처만 가진 카드는 `confidence`, `severity`, `suggested_action`을 생성하거나 바꾸는 입력으로 쓰지 않는다.
- `dataset_supported`는 `candidate_ranking_only: true`일 때만 자동 응답 metadata로 노출한다.
- `rejected` 출처가 하나라도 `official_source_refs`에 들어간 카드는 검색 대상에서 제외한다.
- `review_status`가 `draft` 또는 `needs_update`인 카드는 운영 응답에 자동 사용하지 않는다.
- 카드의 `must_not_claim` 표현이 생성 결과에 포함되면 설명 생성은 실패로 처리하고 fallback 문구를 사용한다.
- source card에 원문 전문을 저장하지 않고, `source`, `title`, `url`, `accessed_at`, `usage_policy`, `claim_summary` 같은 메타데이터와 짧은 검수 요약만 저장한다.

설명 카드 파일 구조:

| 파일 | 역할 | 운영 규칙 |
| --- | --- | --- |
| `app/data/explanation_cards/red_flags.json` | active red flag rule을 사용자 설명으로 풀어 쓰는 reviewed card seed | `card_type: "red_flag_explanation"`만 둔다. 모든 카드는 `red_flag_code`와 `approved` source ref를 가져야 하며, `restricted/reference_only` 출처만으로는 운영 응답에 쓰지 않는다. |
| `app/data/explanation_cards/conditions.json` | `/assess`가 이미 만든 condition candidate를 참고 후보 설명으로 풀어 쓰는 reviewed card seed | `card_type: "condition_explanation"`만 둔다. `red_flag_code`는 `null`이어야 하며, MedlinePlus 같은 `restricted/reference_only` 출처는 후보 설명 링크/메타데이터로만 허용한다. confidence, severity, suggested_action을 바꾸지 않는다. |
| `app/data/explanation_cards/source_refs.json` | 설명 카드가 참조하는 출처 metadata registry | `source_id`, `source`, `title`, `url`, `usage_policy`, `accessed_at`, `claim_summary`만 저장한다. 원문 전문을 저장하지 않고, `rejected` 출처는 운영 카드에서 참조할 수 없다. |

파일 간 연결 규칙:

- `red_flags.json`과 `conditions.json`의 모든 `official_source_refs` 값은 `source_refs.json`의 `source_id`에 존재해야 한다.
- `review_status`가 `reviewed`가 아닌 카드는 `/symptom-checker/explain` 운영 응답에 자동 사용하지 않는다.
- `must_not_claim`은 카드별 금지 표현 목록이며, 생성 또는 보조 설명 문구가 이 표현과 충돌하면 fallback 설명을 사용한다.
- 설명 카드 파일은 판단 데이터가 아니라 설명 데이터다. 새 card를 추가해도 `/assess`의 red flag, candidate, confidence, severity, suggested_action 생성 규칙은 변하지 않는다.
- 운영 고도화 방식, 즉 `/symptom-checker/explain`이 `assessment_id`를 조회할지 signed payload를 검증할지는 현재 결정하지 않는다. 지금은 시연과 단위 테스트가 쉬운 assessment payload 직접 전달 방식을 유지한다.

현재 red flag 설명 카드 seed:

| card_id | 연결 rule | 주요 공식 출처 |
| --- | --- | --- |
| `red_flag.chest_pain_with_shortness_of_breath.v1` | `chest_pain_with_shortness_of_breath` | CDC, AHA |
| `red_flag.shortness_of_breath_with_hemoptysis_or_pleuritic_pain.v1` | `shortness_of_breath_with_hemoptysis_or_pleuritic_pain` | NHLBI |
| `red_flag.chest_pain_with_acs_supporting_context.v1` | `chest_pain_with_acs_supporting_context` | CDC, AHA, NHS |
| `red_flag.chest_pain_at_rest.v1` | `chest_pain_at_rest` | CDC, AHA, NHS |
| `red_flag.airway_swelling_with_breathing_symptom.v1` | `airway_swelling_with_breathing_symptom` | CDC, NHS |
| `red_flag.progressive_weakness_with_bulbar_or_walking_difficulty.v1` | `progressive_weakness_with_bulbar_or_walking_difficulty` | WHO |
| `red_flag.sudden_one_sided_numbness_or_weakness.v1` | `sudden_one_sided_numbness_or_weakness` | CDC |
| `red_flag.thunderclap_headache.v1` | `thunderclap_headache` | NICE, CDC |
| `red_flag.headache_with_neurologic_deficit.v1` | `headache_with_neurologic_deficit` | NICE, CDC |
| `red_flag.sudden_vision_loss.v1` | `sudden_vision_loss` | NHS, CDC |
| `red_flag.curtain_or_shadow_over_vision.v1` | `curtain_or_shadow_over_vision` | NEI, AAO EyeWiki |
| `red_flag.severe_eye_pain_with_vision_change.v1` | `severe_eye_pain_with_vision_change` | NHS |
| `red_flag.new_flashes_or_floaters_with_vision_change.v1` | `new_flashes_or_floaters_with_vision_change` | NEI, AAO EyeWiki |
| `red_flag.fever_with_neck_stiffness.v1` | `fever_with_neck_stiffness` | NHS |
| `red_flag.abdominal_pain_with_bloody_stool_or_vomit.v1` | `abdominal_pain_with_bloody_stool_or_vomit` | Mayo Clinic |
| `red_flag.injury_with_numb_or_discolored_extremity.v1` | `injury_with_numb_or_discolored_extremity` | Mayo Clinic |
| `red_flag.head_injury_with_neurologic_danger_sign.v1` | `head_injury_with_neurologic_danger_sign` | CDC, NHS |
| `red_flag.injury_with_deformity_or_unusable_limb.v1` | `injury_with_deformity_or_unusable_limb` | Mayo Clinic |

현재 active red flag 18개는 모두 reviewed 설명 카드 seed를 가집니다. 새 active red flag를 추가하면 `/symptom-checker/explain` coverage 테스트에 해당 카드도 추가해야 합니다.

MedlinePlus 사용 제한:

- MedlinePlus는 후보 설명 링크와 참고 메타데이터로만 사용한다.
- MedlinePlus Medical Encyclopedia 본문은 RAG chunk, embedding, 모델 학습, 자동 수집 대상에서 제외한다.
- MedlinePlus 링크가 붙은 condition card라도 `source_usage_policy`는 `restricted/reference_only`로 두며, 단독으로 `high` confidence를 만들지 않는다.
- MedlinePlus 내용과 공식기관 red flag 근거가 같은 증상을 언급하더라도, active red flag 근거는 CDC/NICE/NHS/NIH/AHA/WHO 같은 approved source에서 따로 확인한다.

RAG 금지 범위:

- MedlinePlus 또는 외부 웹 본문 자동 크롤링/임베딩
- 검색 결과로 red flag 생성
- 검색 결과로 confidence 상승
- 검수되지 않은 source card 사용

RAG/LLM 안전 테스트 설계:

| 테스트 | 입력 예 | 기대 결과 |
| --- | --- | --- |
| RAG card가 새 red flag를 추가하지 못함 | `rule_result.red_flags: []`, 검색 카드에 `red_flag_code: "thunderclap_headache"` 포함 | 최종 `red_flags`는 빈 배열 유지 |
| RAG card가 candidate confidence를 올리지 못함 | `candidate.confidence: "low"`, approved 설명 카드 존재 | 최종 confidence는 `low` 유지 |
| RAG card가 red flag severity를 바꾸지 못함 | rule 결과 `severity: "urgent"`, 카드 문구가 강한 위험 신호를 설명 | 최종 severity는 `urgent` 유지 |
| RAG card가 suggested_action을 바꾸지 못함 | rule 결과 `suggested_action` 존재, 카드에 다른 행동 문구 존재 | 최종 `suggested_action`은 rule 결과 그대로 유지 |
| restricted/reference_only 카드는 red flag 설명 카드로 사용되지 않음 | `source_usage_policy: "restricted/reference_only"`만 가진 `red_flag_explanation` 카드 | 운영 검색 대상 제외 또는 validation 실패 |
| rejected source가 포함된 카드는 검색되지 않음 | `official_source_refs`에 rejected source 포함 | 카드 전체 검색 제외 |
| `must_not_claim` 표현이 나오면 fallback | LLM 출력에 “심근경색입니다”, “약을 복용하세요”, “괜찮습니다” 포함 | 안전 fallback 문구 사용 |
| draft/needs_update 카드는 운영 응답에 자동 사용되지 않음 | `review_status: "draft"` 또는 `"needs_update"` | 운영 검색 대상 제외 |

테스트 구현 방식:

1. 실제 LLM 호출 없이 순수 함수 단위 테스트를 먼저 만든다.
2. 예상 함수는 `select_explanation_cards(rule_result, cards)`와 `build_safe_explanation(rule_result, cards, generated_text)`처럼 판단값과 설명값을 분리한다.
3. 단위 테스트는 `red_flags`, `candidates[].confidence`, `red_flags[].severity`, `red_flags[].suggested_action`이 입력 rule 결과와 동일한지 확인한다.
4. `/symptom-checker/explain` endpoint가 생긴 뒤에만 API 단위 테스트를 추가한다.
5. Swagger 수동 검증은 로컬 서버 `http://127.0.0.1:8000/docs`에서 endpoint가 생긴 뒤 수행한다.
6. 전체 테스트는 큰 기능 묶음 완료 시점에만 검토하고, 평소에는 관련 선별 테스트를 우선한다.

### 모델 계층 결정

LLM과 의료 NLP 모델은 같은 역할이 아닙니다. 이 프로젝트에서는 두 계층을 분리합니다.

| 계층 | 1차 후보 | 역할 | 금지 역할 |
| --- | --- | --- | --- |
| 규칙 엔진 | 내부 `RED_FLAG_METADATA`, `CONTEXT_OPTIONS`, condition seed | red flag, 후보 생성, confidence cap의 최종 판단 | 없음 |
| 한국어 구조화 보조 | 한국어 의료 BERT/NER 후보 또는 alias dictionary | 사용자 자유 입력에서 증상/컨텍스트 후보 추출, 표현 정규화 | red flag, severity, confidence, 질환 후보 생성 |
| LLM 구조화/설명 | OpenAI `gpt-5.4-mini` 사용 가능 여부를 우선 검토하고, 계정/비용/지원 상태에 따라 `gpt-5-mini` 계열로 fallback | 긴 자유 입력 요약, 내부 code 후보 정리, 설명 카드 문장화 | 진단, 처방, red flag 생성, confidence 상승 |
| RAG | 내부 검수 설명 카드, 공식 출처 링크/metadata | rule 결과를 설명할 근거 카드 조회 | 외부 웹 본문 자동 수집, 미검수 문서 기반 판단 |

모델 ID는 코드에 하드코딩하지 않고 환경 변수 또는 설정값으로 둡니다. 모델이 없거나 호출에 실패하면 `/symptom-checker/assess`의 기존 rule-based 응답으로 fallback합니다.

의료 BERT 계열은 의료 용어 표현을 더 잘 인식하기 위한 후보입니다. 하지만 학습된 의료 모델도 서비스의 red flag 기준, 국내 사용자 UX, 공식 근거 metadata, 단독 trigger 금지 정책을 자동으로 보장하지 않습니다. 따라서 의료 BERT는 `symptom_code`/`context_code` 후보 추출과 alias 정규화까지만 담당하고, 최종 판단은 항상 내부 whitelist와 rule engine이 수행합니다.

의료 NLP 후보 검토 기준:

| 후보 | 우선 사용 가능성 | 검토 이유 | 제한 |
| --- | --- | --- | --- |
| 한국어 의료 BERT/NER | 높음 | 한국어 사용자 서술형 입력에서 증상, 부위, 기간, 약물, 검사명 후보를 뽑는 데 적합 | 라이선스, 모델 크기, 추론 비용, 개인정보 처리 검토 필요 |
| BioBERT | 중간 | PubMed/PMC 기반 biomedical text mining 근거가 명확함 | 영어 biomedical 문헌 중심이라 한국어 사용자 입력에는 직접 적용하기 어려움 |
| PubMedBERT/ClinicalBERT 계열 | 보류 | biomedical/clinical domain language model 후보군 | 영어 임상/문헌 환경 중심이며 국내 사용자 문장 정규화에는 별도 검증 필요 |

### 의료 BERT/NER adapter 출력 스키마

의료 BERT/NER adapter는 최종 판단자가 아니라 자유 입력을 내부 code 후보로 정리하는 계층입니다. adapter 출력은 항상 후보이며, whitelist 검증 전에는 rule engine 입력으로 사용할 수 없습니다.

요청 예시:

```json
{
  "text": "어제부터 가슴이 답답하고 숨이 차요. 식은땀도 났습니다.",
  "locale": "ko-KR",
  "known_profile": {
    "gender": "female",
    "birth_date": "2000-01-01"
  }
}
```

adapter 원시 출력 예시:

```json
{
  "body_region_candidates": [
    {
      "code": "chest",
      "confidence": 0.82,
      "span": "가슴"
    }
  ],
  "symptom_code_candidates": [
    {
      "code": "pain",
      "confidence": 0.64,
      "span": "답답"
    },
    {
      "code": "shortness_of_breath",
      "confidence": 0.91,
      "span": "숨이 차요"
    }
  ],
  "context_code_candidates": [
    {
      "code": "chest_pressure",
      "confidence": 0.7,
      "span": "답답"
    },
    {
      "code": "cold_sweat",
      "confidence": 0.86,
      "span": "식은땀"
    }
  ],
  "unmapped_mentions": [
    {
      "text": "어제부터",
      "reason": "duration_candidate"
    }
  ],
  "model_metadata": {
    "provider": "local_korean_medical_ner",
    "model_id": "not_decided",
    "model_version": "not_decided"
  }
}
```

검증 후 내부 구조화 후보:

```json
{
  "body_region": "chest",
  "symptom_candidates": [
    {
      "code": "pain",
      "source": "bert_ner_candidate",
      "accepted": true
    },
    {
      "code": "shortness_of_breath",
      "source": "bert_ner_candidate",
      "accepted": true
    }
  ],
  "context_candidates": [
    {
      "code": "chest_pressure",
      "source": "bert_ner_candidate",
      "accepted": true
    },
    {
      "code": "cold_sweat",
      "source": "bert_ner_candidate",
      "accepted": true
    }
  ],
  "rejected_candidates": [
    {
      "code": "unknown_code",
      "reason": "not_in_service_whitelist"
    }
  ],
  "ignored_judgment_fields": ["condition_candidates", "red_flags", "confidence", "severity", "diagnosis", "treatment"]
}
```

adapter 제한:

- 출력 code는 `BODY_REGIONS`, 부위별 symptom 목록, `CONTEXT_OPTIONS` whitelist에 있어야 한다.
- adapter confidence는 후보 정렬과 검토 보조에만 사용하고 candidate confidence 또는 red flag severity로 전파하지 않는다.
- adapter가 `condition_candidates`, `red_flags`, `diagnosis`, `treatment`, `severity`, `confidence`를 보내면 validation layer가 무시한다.
- whitelist 밖 code는 `rejected_candidates`로 남기고 rule engine 입력에 넣지 않는다.
- review-only context는 그대로 review-only로 유지하며, adapter 출력만으로 active context나 red flag 용도로 승격하지 않는다.
- 모델 성능이나 benchmark 점수에 맞춰 내부 symptom/context 구조를 바꾸지 않는다.

참고 근거:

- OpenAI Models 문서: https://platform.openai.com/docs/models
- OpenAI Structured Outputs 문서: https://platform.openai.com/docs/guides/structured-outputs
- OpenAI Retrieval 문서: https://platform.openai.com/docs/guides/retrieval
- BioBERT 논문: https://pmc.ncbi.nlm.nih.gov/articles/PMC7703786/
- 한국어 의료 BERT 논문: https://pubmed.ncbi.nlm.nih.gov/35974113/

## 확정 작업 흐름

현재 증상 탐색 고도화는 아래 순서로 진행합니다. LLM/Qwen API는 지금 단계에서 제외하고, 사용자가 다시 지시할 때까지 구현하지 않습니다.

```text
1. 사용자가 부위, 세부 부위, 증상, 강도, 기간을 선택한다.
2. 사용자가 추가 컨텍스트를 직접 서술형으로 입력한다.
3. 의료 BERT가 서술형 입력에서 symptom/context 후보 code만 추출한다.
4. 후보 code는 내부 whitelist 검증을 통과해야 한다.
5. 사용자 선택값과 BERT 후보를 병합한다. 사용자 직접 선택값을 우선한다.
6. rule engine이 red_flags, candidates, confidence, severity, suggested_action을 만든다.
7. 평가 결과를 기준으로 무료 로컬 vector DB에서 설명 카드/근거를 검색한다.
8. RAG 검색 결과를 explanations, generated_summary_ko, source_refs에만 반영한다.
9. 기능 묶음이 완성된 뒤 선별 테스트와 Swagger 검증을 수행한다.
```

역할 분리:

| 구성요소 | 역할 | 금지 사항 |
| --- | --- | --- |
| 선택형 입력 | 사용자가 직접 고른 부위/증상/강도/기간/context | 없음 |
| 의료 BERT | 서술형 입력에서 내부 symptom/context 후보 code 추출 | 진단, 처방, red flag, condition candidate, confidence, severity 생성 금지 |
| whitelist 검증 | unknown code와 부위에 맞지 않는 symptom 제거 | 판단값 생성 금지 |
| rule engine | red flag와 참고 candidate 판단 | DDXPlus/BERT/RAG 성능에 맞춘 질환별 예외 추가 금지 |
| 무료 vector DB RAG | 이미 생성된 평가 결과를 설명할 카드/근거 검색 | red_flags, candidates, confidence, severity, suggested_action 변경 금지 |
| Qwen/LLM | 현재 단계 제외. 나중에 사용자가 다시 지시할 때만 검토 | 현재 구현 금지 |

## 의료 BERT 적용 계획

의료 BERT는 API가 아니라 무료 로컬 모델로 적용합니다. 적용 위치는 `/symptom-checker/structure`와 `/symptom-checker/assessment-draft`의 서술형 입력 구조화 단계입니다.

의료 BERT 입력:

```json
{
  "body_region": "chest",
  "selected_symptoms": ["pain"],
  "selected_contexts": ["chest_pressure"],
  "free_text": "숨도 차고 왼팔까지 저려요"
}
```

의료 BERT 출력 후보:

```json
{
  "symptom_candidates": ["shortness_of_breath", "numbness"],
  "context_candidates": ["radiating_left_arm_or_jaw_or_back"]
}
```

병합 원칙:

- 사용자가 직접 선택한 값이 BERT 후보보다 우선합니다.
- BERT 후보는 `validate_structured_input_candidates()`를 통과해야 합니다.
- 동일 code는 중복 제거합니다.
- body region에 허용되지 않는 symptom은 제외합니다.
- whitelist 밖 context는 제외합니다.
- BERT가 판단 필드(`condition_candidates`, `red_flags`, `confidence`, `severity`, `diagnosis`, `treatment`)를 만들거나 반환해도 사용하지 않습니다.

다운로드 시점:

- 현재 문서화된 흐름을 반영한 뒤, 의료 BERT adapter 구현 단계에서 다운로드합니다.
- 사용자가 직접 다운로드해야 하는 파일이나 사이트 로그인이 필요한 경우에만 사용자에게 요청합니다.
- 모델 weight는 Git에 커밋하지 않습니다.
- 기본 cache 후보는 `C:/tmp/health-navigator-models/kmbert`입니다.
- 필요한 의존성 후보는 `torch`, `transformers`입니다. 실제 `requirements.txt` 수정은 의료 BERT adapter 구현 시점에 진행합니다.

모델 후보 기준:

- 무료로 사용할 수 있어야 합니다.
- 한국어 의료/임상 텍스트 후보 추출에 쓸 수 있어야 합니다.
- 라이선스, 출처, 인용 정보를 문서에 남깁니다.
- 공식 KU-RIAS/KM-BERT 계열 artifact를 우선 검토합니다.
- 비공식 Hugging Face 변환본은 라이선스와 재배포 상태를 확인하기 전 기본 의존성으로 고정하지 않습니다.

## 무료 vector DB RAG 적용 계획

RAG는 무료 로컬 vector DB로 구현합니다. 유료 vector DB, 유료 hosted retrieval, 유료 embedding API는 사용하지 않습니다.

1차 구현 후보:

| 후보 | 판단 |
| --- | --- |
| SQLite + 로컬 embedding vector 저장 + cosine similarity 직접 계산 | 1차 선택. 무료, 로컬, 설치 부담이 작고 카드 수가 적은 현재 단계에 충분합니다. |
| Chroma local persistent | 2차 후보. metadata filtering은 좋지만 의존성이 늘어납니다. |
| FAISS local | 3차 후보. 빠르지만 Windows 설치 리스크가 있습니다. |

RAG 인덱싱 대상:

```text
app/data/explanation_cards/red_flags.json
app/data/explanation_cards/conditions.json
app/data/explanation_cards/source_refs.json
```

vector document 구성:

```text
card_type
target code(red_flag_code 또는 condition_code)
summary_ko
rationale_ko
mapping_limit
source claim 요약
review/source policy metadata
```

metadata:

```json
{
  "card_id": "red_flag.chest_pain_with_shortness_of_breath.v1",
  "target_type": "red_flag",
  "target_code": "chest_pain_with_shortness_of_breath",
  "review_status": "reviewed",
  "source_usage_policy": "approved"
}
```

embedding 모델:

- 무료 로컬 embedding 모델을 사용합니다.
- 1차 후보는 `sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2`입니다.
- cache 후보는 `C:/tmp/health-navigator-models/embeddings`입니다.
- 모델 weight는 Git에 커밋하지 않습니다.

RAG 검색 시점:

```text
/assess rule engine 결과
  -> body_region, symptoms, contexts, red_flags, candidates 기반 query 생성
  -> vector DB top-k 검색
  -> reviewed card/source만 explanations에 첨부
```

RAG 성공 기준:

- reviewed card만 검색 결과로 사용합니다.
- rejected source는 사용하지 않습니다.
- red flag 설명은 다른 red flag 설명으로 잘못 붙으면 안 됩니다.
- RAG는 `red_flags`, `candidates`, `confidence`, `severity`, `suggested_action`을 바꾸지 않습니다.

## 다음 TODO: 세부 부위별 입력 재설계와 서술형 구조화

기존 1차 완료 TODO는 LLM 이전 JSON 흐름, RAG fallback, KM-BERT 실행 계약을 검증하는 단계였다. 해당 단계는 완료된 기준선으로 두고, 다음 작업은 기능의 입력 품질을 다시 설계하는 것으로 전환한다.

이번 단계의 핵심은 두 가지다.

1. 큰 부위와 세부 부위별 증상, 질문, context를 일일이 다시 작성한다.
2. 서술형 입력을 사용자의 개인 상황 context로 구조화해 선택형 입력과 안전하게 병합한다.

질환 후보 도출은 `질문 1개 = 질환 1개` 방식으로 만들지 않는다. 증상 선택, 세부 질문 답변, 서술형 구조화 결과가 각각 내부 `symptom_code`/`context_code` evidence를 만들고, rule engine은 이 evidence 조합을 질환 후보별 조건과 점수로 평가한다. 단일 질문은 후보 점수를 올리는 근거일 뿐이며, 최종 응답은 여러 evidence를 종합한 `가능 질환 후보`, `근거`, `부족한 확인 질문`, `red_flags`로 반환한다.

질환 후보 수 확장, BERT 성능 개선, vector DB 검색 품질 개선은 이번 단계의 1차 목표가 아니다. 후보와 위험 신호는 계속 rule engine이 만들고, LLM/BERT/RAG는 입력 구조화 또는 설명 보조에만 사용한다.

### 입력 구조 재정의

입력은 다음 네 층으로 나눈다.

| 층 | 역할 | 예시 |
| --- | --- | --- |
| Anatomy | 큰 부위와 세부 부위 | `arm_hand`, `wrist` |
| Symptoms | 해당 세부 부위에서 흔한 직접 증상 | 통증, 붓기, 저림, 움직임 제한 |
| Guided Context | 세부 부위와 증상에 맞는 빠른 질문 | 외상 후 시작, 반복 사용, 손끝 색 변화 |
| Free Text Context | 사용자의 개인 설명 | 약 복용, 굴 섭취, 기저질환, 자기 추측 |

### Context taxonomy

context code는 한 덩어리로 다루지 않고 아래 범주로 재분류한다.

| category | 예시 |
| --- | --- |
| `lifestyle` | 음주, 수면 부족, 스트레스, 과식 |
| `exposure` | 굴/조개/날음식, 감염자 접촉, 새 화장품, 알레르기 노출 |
| `injury_or_use` | 넘어짐, 부딪힘, 꺾임, 반복 사용, 무거운 물건 |
| `pattern` | 갑작스러운 시작, 점점 악화, 반복됨, 식후 악화 |
| `safety` | 호흡곤란, 의식 변화, 혈변, 시야 상실, 말단 색 변화 |
| `medication` | 최근 복용약, 평소 복용약, 약 복용 후 변화 |
| `medical_history` | 고혈압, 당뇨, 천식, 위염, 임신 가능성 |
| `time_course` | 어제부터, 3일째, 갑자기, 반복적으로 |

`음주`, `수면 부족`, `과한 운동` 같은 생활 context는 모든 부위에 공통 노출하지 않는다. 예를 들어 수면 부족은 두통이나 전신 피로에서는 의미가 있지만 손가락 통증에는 우선 노출하지 않는다.

### 질문 스키마 개편

질문은 region 공통 목록이 아니라 다음 조건으로 필터링한다.

- `applies_to_region`
- `applies_to_body_part`
- `applies_to_symptoms`
- `purpose`
- `maps_to_context`
- `suppress_when`
- `display_priority`

질문 목적은 `candidate_narrowing`, `red_flag_check`, `context_enrichment`, `free_text_prompt`로 분리한다.

각 질문은 화면 문구와 별도로 `maps_to_context` evidence code를 가져야 한다. 한 질문이 바로 특정 질환을 확정하지 않으며, 여러 질환 후보가 같은 evidence를 공유할 수 있다. 예를 들어 `무릎을 비튼 뒤 시작`, `무릎 잠김`, `계단/쪼그림 악화`, `붓기`가 함께 선택되면 반월상연골 손상 후보 점수가 올라가고, `뚝 소리`, `스포츠 방향 전환`, `빠른 붓기`, `불안정감`이 함께 있으면 인대 손상 후보 점수가 올라가는 식으로 처리한다.

### 세부 부위별 UI spec 진행 상태

세부 부위별 입력 재설계는 큰 부위 단위로 문서를 나누어 진행한다. 사용자가 "todo 이어서 진행" 또는 "다음 부위 진행"이라고 말하면 아래 상태를 기준으로 아직 완료되지 않은 큰 부위를 같은 형식으로 이어간다.

완료:

- `arm_hand`: `docs/SYMPTOM_CHECKER_ARM_HAND_UI_SPEC.md`
- `leg_foot`: `docs/SYMPTOM_CHECKER_LEG_FOOT_UI_SPEC.md`
- misc 묶음: `docs/SYMPTOM_CHECKER_MISC_BODY_UI_SPEC.md`
  - 목
  - 고관절
  - 직장/항문
  - 피부
  - 전신/일반

남은 큰 부위:

- `head_face`
- `eye`
- `ear_nose_throat`
- `chest`
- `abdomen`
- `pelvis_urinary`
- `back_waist`

권장 진행 순서:

1. `head_face`
2. `ear_nose_throat`
3. `eye`
4. `back_waist`
5. `chest`
6. `abdomen`
7. `pelvis_urinary`

각 세부 부위는 아래 형식으로 작성한다.

1. 가능 질환 후보
2. 가능 질환 후보별 evidence
3. 질문별 evidence 매핑
4. 사용자 화면 리스트
5. 구현 시 context code 후보

사용자에게 먼저 보여줄 화면 리스트는 항상 아래 파트로 나눈다.

1. 증상
2. 시작 계기
3. 시작 양상
4. 악화 양상
5. 안전 확인
6. 추가 설명

질환 후보는 너무 전문적인 질환만 나열하지 않는다. 사용자가 이해할 수 있는 대중적 이름도 함께 포함한다. 예: `신스플린트`, `하지정맥류`, `족저근막염`, `손목터널증후군`, `통풍성 관절염`. 다만 최종 응답 표현은 항상 "가능성" 또는 "위험 신호"로 제한한다.

참고로 기존 `arm_hand` 1차 파일럿 기준은 아래와 같다. 손목, 손, 손가락을 선택했을 때 같은 `pain`이라도 서로 다른 증상 목록, 질문, possible candidate 흐름이 나오게 하는 것이 목표였다.

| body_part | 증상 방향 | 질문 방향 |
| --- | --- | --- |
| `wrist` | 통증, 붓기, 저림, 움직임 제한, 힘 빠짐 | 넘어짐/부딪힘, 반복 사용, 변형, 손끝 저림 |
| `hand` | 통증, 붓기, 저림, 쥐는 힘 저하, 색 변화, 차가움 | 물건을 쥐기 어려움, 외상, 반복 사용, 손끝 색 변화 |
| `finger` | 통증, 붓기, 뻣뻣함, 저림, 열감, 상처/고름, 색 변화 | 꺾임/찔림, 빨갛게 붓고 열감, 고름, 손끝 색 변화 |
| `elbow` | 통증, 붓기, 움직임 제한, 저림 | 반복 사용, 부딪힘, 팔을 펴기 어려움 |
| `arm` | 통증, 저림, 힘 빠짐, 붓기 | 목/어깨에서 내려오는 증상, 외상, 진행하는 힘 빠짐 |

### 서술형 구조화 v2

서술형 입력은 "기타 증상"이 아니라 사용자의 개인 문맥 수집 레이어다. 사용자는 증상, 음식 섭취, 약 복용, 기저질환, 검사 수치, 자기 추측을 여러 문장으로 섞어 적을 수 있다.

구조화 결과는 진단이 아니라 내부 후보 code여야 한다.

```json
{
  "body_region_candidates": ["abdomen"],
  "body_part_candidates": ["whole_abdomen"],
  "symptom_candidates": ["pain", "diarrhea", "fever"],
  "context_candidates": ["raw_shellfish_exposure"],
  "medication_mentions": [],
  "medical_history_mentions": [],
  "time_expressions": ["since_last_night", "last_week"],
  "user_self_guess": ["norovirus"],
  "uncertain_phrases": []
}
```

사용자가 말한 질환명 추측은 `user_self_guess`로 분리하고 후보 생성 근거로 직접 쓰지 않는다. 예를 들어 "노로바이러스일 수도 있을 것 같다"는 문장은 `굴/조개/날음식 섭취`, `설사`, `복통`, `발열`, `기간` 같은 evidence만 판단에 반영한다.

### 새 작업 순서

1. 현재 큰 부위/세부 부위별 증상, 질문, context, 후보 중복률을 감사한다.
2. context code를 taxonomy 기준으로 재분류한다.
3. 질문 스키마에 적용 조건과 목적을 추가한다.
4. 질환 후보별 `required_all`, `required_any`, `supporting`, `less_likely`, `red_flag_exclusions`, `score_weights`를 정의한다.
5. 각 질문이 어떤 evidence code를 만들고 어떤 후보 점수에 기여하는지 문서화한다.
6. `arm_hand`와 `leg_foot` 세부 부위별 symptom profile과 질문을 먼저 구현한다.
7. 서술형 구조화 v2 스키마를 도입한다.
8. Gemini 구조화 provider는 내부 code 후보만 반환하도록 제한한다.
9. 손목/손/손가락, 발/발가락/무릎, 복부 음식 노출 예시를 포함한 golden set을 만든다.
10. 기존 pytest와 부위별 시나리오 테스트로 검증한다.

상세 계획은 `docs/SYMPTOM_CHECKER_NEXT_PASS_PLAN.md`를 기준 문서로 사용한다.

API 확장 순서:

1. 기존 `/symptom-checker/assess`는 rule/model 판단 응답으로 유지합니다.
2. `POST /symptom-checker/structure`로 자유 입력 구조화 endpoint를 별도 추가합니다.
3. `POST /symptom-checker/assessment-draft`로 구조화 후보를 평가 요청 초안으로 변환합니다.
4. `POST /symptom-checker/explain`으로 판단 결과 설명 endpoint를 별도 유지합니다.
5. `/symptom-checker/assess?include_explanation=true`와 `/symptom-checker/assess/me?include_explanation=true`에서 RAG 설명 통합 응답을 제공합니다.

`/symptom-checker/structure`의 1차 구현은 외부 LLM/BERT를 직접 호출하지 않습니다. LLM, 의료 BERT, alias dictionary가 만든 후보 code를 받아 내부 whitelist로 검증하고, 판단 필드는 무시하는 안전 계층입니다. 실제 질환 후보, red flag, confidence, severity는 이 endpoint에서 생성하지 않습니다.

`/symptom-checker/structure` 운영 방식:

- 현재 기본값은 검증 endpoint 유지입니다.
- 이 endpoint는 provider를 직접 호출하지 않고, 외부 LLM/BERT/alias dictionary가 만든 후보 payload를 받아 whitelist와 판단 필드 제거를 검증합니다.
- `free_text`만 들어온 경우에도 관리 중인 선택지 이름과 alias hint로 `body_region`, `symptom_candidates`, `context_candidates` 후보를 가볍게 추출합니다. 이 단계는 최종 판단이 아니라 whitelist 검증 전 후보 생성입니다.
- 후보 code 앞뒤 공백은 whitelist 검증 전에 정리합니다.
- alias matching은 짧은 한국어 단어가 문장 경계에서 붙어 생기는 오탐을 줄이도록 보수적으로 처리합니다.
- `흉통`, `숨참`, `피 섞인 가래`, `시야/시력 변화`처럼 시연에서 자주 쓸 수 있는 생활 표현은 내부 후보 code로만 정규화합니다. 이 정규화는 red flag나 질환 후보를 직접 만들지 않습니다.
- 응답에는 `rejection_reasons`를 포함해 unknown region, region에 맞지 않는 symptom, unknown context를 구분합니다.
- 응답에는 `ignored_judgment_fields`를 포함해 provider가 보냈지만 판단에 사용하지 않은 필드를 명시합니다.
- `/assess` 입력 검증 오류는 허용 세부 부위/증상 code 또는 context 조회 endpoint 힌트를 포함해 Swagger 수동 검증에서 바로 수정할 수 있게 합니다.
- 실제 provider adapter는 라이선스, 비용, 지연시간, 개인정보 처리, fallback, 키 관리 방식이 승인된 뒤 별도 단계로 붙입니다.
- provider adapter를 붙이더라도 adapter 출력은 `/structure` validation layer를 반드시 통과해야 합니다.
- provider 실패, timeout, quota 초과, 모델 미설정 시 기존 선택형 입력과 rule-based `/assess` 흐름으로 fallback합니다.
- 운영 설정은 코드 하드코딩이 아니라 환경 변수 또는 설정값으로 둡니다. 단, secret/key 파일은 읽거나 생성하거나 수정하지 않습니다.

provider adapter 도입 전 체크리스트:

- 모델/서비스 라이선스와 상업적 사용 가능 여부 확인
- 한국어 자유 입력에서 내부 code 후보만 반환하도록 출력 스키마 고정
- 개인정보/의료정보가 외부 provider로 나가는지 여부와 보관 정책 확인
- timeout, retry, fallback 정책 정의
- 비용과 호출량 제한 확인
- whitelist 밖 code와 판단 필드를 무시하는 단위 테스트 준비
- Swagger `http://127.0.0.1:8000/docs`에서 provider 없이 validation endpoint가 정상 동작하는지 확인

provider adapter 설정 원칙:

| 항목 | 원칙 |
| --- | --- |
| provider enable flag | 기본값은 off입니다. 명시적으로 켠 환경에서만 외부 provider를 호출합니다. |
| model id | 코드에 하드코딩하지 않고 환경 변수 또는 설정값으로 둡니다. |
| API key/secret | `.env`, secret, credential 파일은 Codex가 읽거나 생성/수정하지 않습니다. 키 관리 방식은 사용자 승인 후 별도 처리합니다. |
| timeout | 짧은 timeout을 둡니다. timeout 시 사용자 입력 선택값과 rule-based `/assess` 흐름으로 fallback합니다. |
| retry | 중복 비용과 지연을 막기 위해 1차 도입에서는 retry를 최소화하거나 비활성으로 둡니다. |
| max input length | `free_text` 길이 제한을 유지하고, 긴 문장은 provider에 보내기 전 잘라내거나 거부합니다. |
| output schema | provider 출력은 `body_region`, `symptom_candidates`, `context_candidates` 후보만 허용합니다. |
| candidate count limit | provider 후보는 symptom 최대 5개, context 최대 10개까지만 검증 대상으로 사용합니다. 초과분은 rule engine 입력에 넣지 않습니다. |
| forbidden output | `condition_candidates`, `red_flags`, `confidence`, `severity`, `diagnosis`, `treatment`는 받아도 `ignored_judgment_fields`로 기록하고 판단에는 쓰지 않습니다. |
| logging | 원문 자유 입력, 의료정보, provider raw response를 운영 로그에 그대로 남기지 않습니다. |
| fallback | provider 미설정, timeout, quota 초과, schema parse 실패, whitelist 전부 실패 시 기존 선택형 입력과 rule engine 결과만 사용합니다. |

현재 non-secret 설정값:

| 설정 | 기본값 | 용도 |
| --- | --- | --- |
| `SYMPTOM_STRUCTURE_PROVIDER_ENABLED` | `false` | 자유 입력 구조화 provider 사용 여부. 기본값은 provider 미사용입니다. |
| `SYMPTOM_STRUCTURE_PROVIDER_NAME` | `none` | 향후 provider adapter 선택용 이름입니다. 현재는 실제 provider 호출에 연결되어 있지 않습니다. |
| `SYMPTOM_STRUCTURE_MODEL_ID` | 빈 문자열 | 향후 모델 ID 설정값입니다. 코드에 모델 ID를 하드코딩하지 않기 위한 자리입니다. |
| `SYMPTOM_STRUCTURE_TIMEOUT_MS` | `2000` | 향후 provider 호출 timeout 설정값입니다. 정수가 아니면 기본값으로 fallback합니다. |
| `MEDICAL_BERT_STRUCTURE_ENABLED` | `false` | 로컬 의료 BERT 구조화 adapter 사용 여부입니다. |
| `MEDICAL_BERT_MODEL_DIR` | `C:/tmp/health-navigator-models/kmbert-structure` | fine-tuned 의료 BERT 구조화 모델 디렉터리입니다. |
| `MEDICAL_BERT_MODEL_ID` | 빈 문자열 | 의료 BERT 모델 식별자 또는 기록용 이름입니다. |
| `MEDICAL_BERT_SCORE_THRESHOLD` | `0.5` | 다중 라벨 분류 score threshold입니다. |

이 설정들은 secret이 아닙니다. API key, token, credential은 별도 승인 전 읽거나 생성하거나 수정하지 않습니다.

provider adapter 실패 유형과 처리:

| 실패 유형 | 처리 |
| --- | --- |
| provider disabled | provider를 호출하지 않고 `/structure` 검증 endpoint만 사용합니다. |
| missing provider name | `provider_fallback_reason: "provider_not_configured"`로 fallback합니다. |
| missing model id | `provider_fallback_reason: "model_not_configured"`로 fallback합니다. |
| missing key | provider를 호출하지 않고 fallback합니다. 실제 key 처리는 별도 승인 전 구현하지 않습니다. |
| timeout/network error | fallback하고, provider 결과 없이 선택형 입력만 사용합니다. |
| quota/rate limit | fallback하고, 재시도 폭주를 막습니다. |
| malformed JSON/schema mismatch | provider 결과 전체를 폐기하고 fallback합니다. |
| unknown code candidates | `/structure`의 `rejection_reasons`에 기록하고 rule engine 입력에서 제외합니다. |
| judgment fields present | `ignored_judgment_fields`에 기록하고 rule engine 판단에는 반영하지 않습니다. |

provider adapter 도입 시 최소 단위 테스트:

- provider가 꺼져 있으면 외부 호출 없이 fallback하는지 확인한다.
- provider가 timeout을 내면 fallback하는지 확인한다.
- provider가 invalid JSON을 반환하면 후보를 폐기하는지 확인한다.
- provider가 whitelist 밖 symptom/context code를 반환하면 `rejection_reasons`에 기록하고 제외하는지 확인한다.
- provider가 `red_flags`, `condition_candidates`, `confidence`, `severity`, `diagnosis`, `treatment`를 반환해도 `ignored_judgment_fields`로만 남고 판단에 쓰이지 않는지 확인한다.
- provider가 정상 후보를 반환하더라도 최종 red flag/candidate 판단은 `/assess` rule engine에서만 수행되는지 확인한다.
- provider가 과도한 후보를 반환하면 symptom 최대 5개, context 최대 10개까지만 검증 대상으로 쓰는지 확인한다.
- provider가 꺼져 있거나 실패해도 free text alias 후보가 있으면 manual validation 결과로 반환되는지 확인한다.

현재 코드 준비 상태:

- `StructuredInputProvider` protocol은 provider adapter가 구현해야 할 최소 인터페이스입니다.
- `structure_symptom_input_from_provider()`는 provider 결과를 직접 판단에 쓰지 않고, 항상 `SymptomStructureRequest`와 `structure_symptom_input()` validation layer를 거치게 합니다.
- `SYMPTOM_STRUCTURE_PROVIDER_ENABLED`가 `false`이면 provider 객체가 전달되어도 호출하지 않고 `provider_fallback_reason: "provider_disabled"`로 fallback합니다.
- provider name이 비어 있거나 `none`이면 provider 객체가 전달되어도 호출하지 않고 `provider_fallback_reason: "provider_not_configured"`로 fallback합니다.
- model id가 비어 있으면 provider 객체가 전달되어도 호출하지 않고 `provider_fallback_reason: "model_not_configured"`로 fallback합니다.
- `structure_symptom_input_from_provider()` 응답에는 `provider_name`과 `provider_model_id`를 포함해 어떤 non-secret 설정으로 adapter 경계가 평가되었는지 metadata로 남깁니다.
- `structure_symptom_input_from_provider()` 응답에는 `provider_timeout_ms`를 포함해 adapter가 사용할 timeout 설정값을 명시합니다.
- provider 운영 정보는 `provider_metadata`에도 묶어서 제공합니다. 구조는 `{used, fallback_reason, name, model_id, timeout_ms}`입니다. 이 metadata는 판단값이 아니며, red flag/candidate 생성에 쓰지 않습니다.
- `provider_metadata` 내부 구조는 `StructuredProviderMetadata` schema로 고정합니다. 기본값은 `{used: false, fallback_reason: null, name: "none", model_id: "", timeout_ms: 2000}`입니다.
- `fallback_reason`은 정해진 값만 허용합니다: `provider_disabled`, `provider_not_configured`, `model_not_configured`, `provider_timeout`, `provider_error`, `invalid_provider_payload`.
- 장기적으로 API에 provider 운영 정보를 노출해야 한다면 `provider_metadata`만 사용합니다. 현재 helper의 top-level `provider_used`, `provider_fallback_reason`, `provider_name`, `provider_model_id`, `provider_timeout_ms`는 내부 테스트/호환용 임시 필드이며 API 계약으로 고정하지 않습니다.
- provider가 없거나 timeout, 예외, 잘못된 payload를 반환하면 `provider_used: false`와 `provider_fallback_reason`을 내려주고 manual validation 결과로 fallback합니다.
- manual validation fallback에서도 free text alias 후보는 whitelist 검증을 거칩니다. 이 후보는 판단값이 아니며 `/assess` rule engine 입력으로 확정되기 전 단계입니다.
- 이 helper는 외부 provider를 호출하지 않는 단위 테스트용/adapter 연결 준비용 구조이며, 실제 provider 호출 구현은 아직 붙이지 않았습니다.

### `/symptom-checker/explain`

현재 상태: 최소 구현 완료. 기본 API 경로는 외부 LLM/provider 호출 없이 내부 검수 설명 카드 helper를 사용합니다. 내부 코드에는 provider adapter가 사용할 RAG context builder와 안전 필터가 준비되어 있습니다.
현재 설명 카드 seed는 active red flag 18개 전체와 condition seed 후보 60개 전체를 포함합니다. condition 카드는 기존 seed rule의 참고 후보 설명만 담당하며, confidence나 red flag 판단을 바꾸지 않습니다.

목적:

- `/symptom-checker/assess` 또는 `/symptom-checker/assess/me`가 이미 만든 판단 결과를 사용자용 설명으로 풀어쓴다.
- 이 endpoint는 새 red flag, 새 condition candidate, confidence, severity, suggested_action을 생성하거나 수정하지 않는다.
- 입력 판단값과 출력 판단값은 동일해야 하며, 추가되는 것은 설명과 출처/한계 문구뿐이다.
- 설명 카드가 없는 red flag 또는 condition target은 `safety.missing_explanation_targets`에 기록해 누락을 추적한다.
- `build_explanation_rag_context()`는 선택된 reviewed 설명 카드, source ref metadata, `must_not_claim`, provider 허용 출력 범위를 묶어 provider에 넘길 수 있는 내부 RAG context를 만든다.
- RAG context는 1차로 최대 6개 카드, 최대 8개 source ref, 카드별 주요 설명 필드 500자 이내로 제한한다.
- `build_explanation_provider_payload()`는 assessment 전체 원문이 아니라 profile/source, red flag 요약, candidate 요약, RAG context만 담는 최소 payload를 만든다.
- `build_explanation_provider_prompt()`는 payload와 안전 계약을 포함한 provider용 prompt를 만든다. prompt는 진단/확정/처방/복용 지시 금지와 판단 필드 변경 금지를 명시한다.
- 기본 `/explain` 응답은 외부 provider 없이 reviewed 설명 카드만으로 안전한 `generated_summary_ko`를 생성한다.
- `explain_symptom_assessment_from_provider()`는 provider 출력 텍스트를 `build_safe_explanation()` 안전 필터에 통과시킨다. 금지 표현이 있으면 `generated_summary_ko`를 비우고 fallback metadata를 남긴다.
- provider가 생성할 수 있는 것은 최대 700자의 사용자용 요약 텍스트뿐이며, `red_flags`, `candidates`, `confidence`, `severity`, `suggested_action`은 바꿀 수 없다.

요청 예시:

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
  },
  "generated_text": null
}
```

응답 예시 일부:

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
      "rationale_ko": "공식 자료에서는 흉부 불편감과 숨참을 심장 관련 warning sign으로 다룹니다. 이 설명은 선택된 신호 조합을 근거로 빠른 상담 필요 가능성을 안내하며, 특정 질환을 확정하지 않습니다.",
      "mapping_limit": "활력징후, 심전도, 혈액검사, 진찰 소견은 반영하지 않았습니다.",
      "source_refs": [
        "cdc.heart_attack.symptoms",
        "aha.heart_attack.warning_signs"
      ]
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

요청 제한:

- 1차 시연 구현은 Swagger 검증과 UI 흐름 연결을 위해 assessment payload를 직접 받는다.
- 화면 구성은 다른 파트에서 담당하므로, 현재 백엔드 우선순위는 `/explain`의 설명 카드 seed와 안전 검증을 확장하는 것이다.
- 클라이언트가 임의로 만든 `red_flags`, `confidence`, `severity`를 신뢰하지 않는 운영 구조는 1차 UI 기능 완성 후 세부 조정 단계에서 다시 다룬다.
- 운영 고도화 단계에서는 `assessment_id` 기반 조회 또는 signed payload를 검토한다.
- 기본 구현은 reviewed 설명 카드 기반 요약을 생성한다. 선택 입력 `generated_text`는 금지 표현 검출과 fallback 확인 용도다. 문체, 출처 범위, 판단값을 바꾸는 옵션은 아직 지원하지 않는다.

응답 제한:

- `assessment.red_flags`, `assessment.candidates`, `confidence`, `severity`, `suggested_action`은 입력 assessment와 동일해야 한다.
- `explanations[]`는 `card_id`, `target_code`, 설명 문구, source ref id 목록, mapping limit만 추가한다.
- condition 설명 카드는 후보 질환을 확정하지 않고 내부 seed rule이 왜 참고 후보로 올렸는지만 설명한다.
- MedlinePlus 기반 condition 설명 카드는 `restricted/reference_only` 출처로만 다루며 red flag 활성화, confidence 상승, 응급 문구 생성에는 쓰지 않는다.
- 금지 표현이 생성되거나 `must_not_claim`과 충돌하면 `fallback_used: true`와 안전 fallback 설명을 반환한다.
- fallback 설명은 target type에 따라 다르게 둔다. red flag는 빠른 평가가 필요한 위험 신호 가능성을 안내하고, condition은 참고 후보 설명이 안전 안내로 대체되었음을 안내한다.

## API 초안

### 큰 부위 목록

```http
GET /symptom-checker/body-regions
```

응답 예시:

```json
[
  {
    "id": "head_face",
    "name": "머리/얼굴",
    "display_order": 1
  }
]
```

1차 큰 부위 범주는 다음 12개로 고정합니다.

| 코드 | 표시명 |
| --- | --- |
| `head_face` | 머리/얼굴 |
| `eye` | 눈 |
| `ear_nose_throat` | 귀/코/목 |
| `neck_shoulder` | 목/어깨 |
| `chest` | 가슴 |
| `abdomen` | 복부 |
| `pelvis_urinary` | 골반/비뇨/생식 |
| `back_waist` | 등/허리 |
| `arm_hand` | 팔/손 |
| `leg_foot` | 다리/발 |
| `skin` | 피부 |
| `general` | 전신 |

### 부위별 증상 목록

```http
GET /symptom-checker/body-regions/{region_id}/symptoms
```

응답 예시:

```json
{
  "region": {
    "id": "head_face",
    "name": "머리/얼굴"
  },
  "body_parts": [
    {
      "id": "temple",
      "name": "관자놀이"
    }
  ],
  "symptoms": [
    {
      "code": "pain",
      "name": "통증",
      "supports_severity": true,
      "supports_duration": true
    }
  ]
}
```

### 컨텍스트 선택지

```http
GET /symptom-checker/contexts
```

응답 예시:

```json
[
  {
    "code": "sleep_deprivation",
    "name": "수면 부족",
    "category": "lifestyle",
    "description": "평소보다 잠을 적게 잤거나 수면 질이 나빴는지"
  }
]
```

기본 컨텍스트는 다음 8개로 둡니다.

| 코드 | 표시명 | 분류 | 역할 |
| --- | --- | --- | --- |
| `alcohol_yesterday` | 전날 음주 | lifestyle | 두통, 메스꺼움 등에서 후보 점수 보강 |
| `sleep_deprivation` | 수면 부족 | lifestyle | 두통, 피로, 감기 관련 후보 점수 보강 |
| `overeating` | 과식 | lifestyle | 복부 통증, 메스꺼움 관련 후보 점수 보강 |
| `recent_exercise` | 최근 격한 운동 | lifestyle | 근육/관절 통증 후보 점수 보강 |
| `stress` | 스트레스 | lifestyle | 두통, 소화불량, 피로 후보 점수 보강 |
| `sudden_onset` | 갑작스러운 시작 | pattern | 심한 두통 등 위험 신호 판단에 사용 |
| `worsening` | 점점 악화 | pattern | 증상 악화 맥락을 후보 이유에 반영 |
| `after_injury` | 외상 후 발생 | pattern | 근육/관절/흉벽 통증 후보 점수 보강 |

v2 위험 신호 규칙은 넓은 증상 코드만으로 과도하게 활성화되지 않도록 세부 컨텍스트를 함께 사용합니다. 전체 목록은 `GET /symptom-checker/contexts`에서 내려주며, 부위별 질문은 `GET /symptom-checker/body-regions/{region_id}/context-guide`의 `maps_to_context`로 연결합니다.

| 예시 코드 | 용도 |
| --- | --- |
| `chest_pressure`, `radiating_left_arm_or_jaw_or_back`, `cold_sweat`, `persistent_pain` | 가슴 통증과 호흡곤란의 위험 맥락 보강 |
| `one_sided`, `speech_difficulty`, `vision_trouble`, `balance_trouble`, `face_droop` | 뇌졸중 의심 warning sign을 넓은 저림/힘 빠짐에서 좁히기 |
| `max_intensity_within_minutes`, `neurologic_deficit` | thunderclap headache 또는 두통 동반 신경학적 이상 확인 |
| `vision_loss`, `curtain_or_shadow_over_vision`, `new_flashes`, `new_floaters`, `halos_around_lights` | 눈/시야 변화 위험 신호 세분화 |
| `bloody_stool`, `bloody_vomit`, `black_stool` | 복통과 함께 빠른 평가가 필요할 수 있는 출혈 징후 확인 |
| `head_injury`, `repeated_vomiting`, `seizure`, `confusion`, `slurred_speech`, `unequal_pupils` | 머리 외상 후 위험 신호 확인 |
| `deformity`, `unable_to_use_joint_or_limb`, `unable_to_bear_weight`, `discolored_extremity`, `cold_extremity` | 외상 후 변형, 사용 불가, 색/온도 변화 확인 |

### 부위별 context chip

1차 UI는 복잡한 조건부 질문 엔진을 만들지 않고, 부위별 context chip/checkbox와 선택 서술형 입력을 사용합니다.

흐름:

1. 부위 선택
2. 세부 부위 선택
3. 증상 선택
4. 강도/기간 선택
5. 부위별 context chip 선택
6. 선택 서술형 입력
7. 평가

`GET /symptom-checker/body-regions/{region_id}/context-guide`는 기존 전체 `quick_contexts`와 별도로 `context_chips`를 반환합니다. UI는 `context_chips`를 우선 노출하고, 필요하면 전체 context 선택지를 확장 영역으로 둘 수 있습니다.

context chip 선정 원칙:

- `CONTEXT_OPTIONS`의 검수된 context code만 사용합니다.
- `red_flag` 용도 chip은 기존 approved/reviewed red flag rule 또는 그 보조 맥락과 연결되어야 합니다.
- `candidate_boost` 용도 chip은 후보 점수 보강용이며 red flag 활성화 근거로 쓰지 않습니다.
- `explanation_context` 용도 chip은 사용자 설명을 풍부하게 하기 위한 맥락이며 판단 근거와 분리합니다.
- 특정 부위에만 chip이 과도하게 몰리지 않도록 1차 노출 수를 제한합니다.
- chip의 `selection_rationale`과 `evidence_basis`로 왜 해당 부위에 노출되는지 추적합니다.

`context_chips` 예시:

```json
[
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
```

### 질환 후보 평가

### 서술형 구조화 후보 검증

```http
POST /symptom-checker/structure
```

이 endpoint는 모델 호출을 수행하지 않습니다. 외부 LLM, 의료 BERT/NER, alias dictionary가 만든 후보를 내부 whitelist로 거르고, 판단 필드는 무시합니다.

요청 예시:

```json
{
  "source": "llm",
  "free_text": "가슴이 답답하고 식은땀이 나요.",
  "body_region": "chest",
  "symptom_candidates": ["pain", "dryness"],
  "context_candidates": ["chest_pressure", "cold_sweat", "made_up_context"],
  "condition_candidates": ["myocardial_infarction"],
  "red_flags": ["chest_pain_with_acs_supporting_context"],
  "confidence": "high",
  "severity": "emergency",
  "diagnosis": "심근경색",
  "treatment": "약을 복용하세요"
}
```

응답 예시:

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

`condition_candidates`, `red_flags`, `confidence`, `severity`, `diagnosis`, `treatment`는 요청에 포함되어도 응답 판단에 쓰지 않습니다.
`rejection_reasons`는 후보가 왜 제외되었는지 설명하며, `ignored_judgment_fields`는 provider가 보냈지만 판단에 사용하지 않은 필드 목록입니다.

```http
POST /symptom-checker/assess
```

비로그인 사용자가 직접 입력한 성별과 생년월일로 평가합니다.

요청 예시:

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

로그인 사용자는 성별과 생년월일을 본문에 넣지 않고 아래 endpoint를 사용합니다.

```http
POST /symptom-checker/assess/me
Authorization: Bearer {access_token}
```

요청 예시:

```json
{
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
    "sleep_deprivation": true,
    "stress": true
  }
}
```

응답 예시:

```json
{
  "disclaimer": "이 결과는 진단이 아닌 참고용 정보입니다.",
  "profile": {
    "gender": "female",
    "birth_date": "2000-01-01",
    "source": "request"
  },
  "red_flags": [],
  "candidates": [
    {
      "condition_code": "tension_headache",
      "condition_name": "긴장성 두통",
      "confidence": "medium",
      "summary": "수면 부족, 스트레스, 머리 통증이 함께 있을 때 참고할 수 있는 두통 관련 후보입니다.",
      "matched_reasons": [
        "관자놀이 통증",
        "수면 부족",
        "스트레스"
      ],
      "suggested_action": "증상이 지속되거나 악화되면 의료기관 상담을 권장합니다.",
      "reference_links": [
        {
          "title": "Headache",
          "url": "https://medlineplus.gov/headache.html",
          "source": "MedlinePlus"
        }
      ]
    }
  ]
}
```

검증 규칙:

- 존재하지 않는 `body_region`은 `404`를 반환합니다.
- 비로그인 평가에서 `gender` 또는 `birth_date`가 없으면 `400`을 반환합니다.
- `birth_date`가 오늘 이후 날짜이면 `422`를 반환합니다.
- `body_part`가 선택된 큰 부위에 속하지 않으면 `400`을 반환합니다.
- 선택한 큰 부위에서 지원하지 않는 증상 코드는 `400`을 반환합니다.
- 지원하지 않는 컨텍스트 코드는 `400`을 반환합니다.
- 같은 증상 코드가 중복 전송되면 `400`을 반환합니다.

## 백엔드 구조 후보

기존 프로젝트 구조를 따릅니다.

- `app/routers/symptom_checker.py`: endpoint 정의
- `app/schemas/symptom_checker.py`: 요청/응답 Pydantic 스키마
- `app/services/symptom_checker_service.py`: 위험 신호 감지, 후보 점수 계산, 응답 구성
- `app/models/symptom_checker.py`: DB 전환 시 사용할 SQLAlchemy 모델

1차 구현은 API 계약과 서비스 책임을 먼저 고정하고, DB 테이블 없이 `app/data/symptom_checker_conditions.json` 데이터셋 파일을 로드해 동작합니다. 실제 데이터는 데이터셋이 확정되면 DB 테이블 또는 import 데이터로 옮길 수 있게 유지합니다.

## 질환 후보 룰 구조

컨텍스트는 단독으로 질환 후보를 만들지 않고, 증상 매칭을 보강하는 역할로 제한합니다.

```text
condition_rule
- region
- required_symptoms
- optional_symptoms
- boosting_contexts
- reasons
```

점수 계산은 1차 MVP에서 다음 기준을 사용합니다.

| 항목 | 점수 |
| --- | --- |
| 필수 증상 매칭 | +3 |
| 추가 증상 매칭 | +2 |
| 컨텍스트 매칭 | +1 |

필수 증상이 하나도 매칭되지 않으면 컨텍스트가 있어도 후보를 반환하지 않습니다. 예를 들어 `전날 음주`와 `수면 부족`이 선택되어도 두통이나 메스꺼움 같은 관련 증상이 없다면 `음주 후 두통` 후보는 생성하지 않습니다.

현재 seed는 `curated_reference`와 `manual_seed` 기반이므로 점수상 `high`에 해당하더라도 응답 confidence는 최대 `medium`으로 제한합니다. DDXPlus/HPO 같은 구조화 데이터와 검수 metadata가 붙은 뒤에만 `high` 승격을 검토합니다.

장기적으로는 각 condition rule 데이터에 `confidence_cap` 필드를 명시할 수 있습니다. 다만 현재 `app/data` seed 파일은 별도 데이터 정리 범위로 남겨두고, 이번 구현에서는 서비스 로직과 테스트로 동일 정책을 보장합니다.

## DB 모델 후보

- `body_regions`: 큰 부위 코드, 이름, 정렬 순서, 활성 여부
- `body_parts`: 세부 부위 코드, 큰 부위 FK, 이름, 정렬 순서
- `symptoms`: 증상 코드, 이름, 강도/기간 입력 지원 여부
- `conditions`: 질환 후보 코드, 이름, 설명, 참고 출처
- `condition_rules`: 부위, 세부 부위, 증상, 컨텍스트 조합과 질환 후보의 가중치
- `red_flag_rules`: 즉시 진료 권고가 필요한 위험 신호 규칙

## 위험 신호 우선순위

아래 active red flag rule은 질환 후보 점수보다 우선해서 별도 경고로 반환합니다.

활성 기준:

- 공식/공공/전문기관 자료에서 반복 확인되는 위험 신호 조합만 active rule로 둡니다.
- DDXPlus condition 또는 frequency baseline은 active red flag 근거로 쓰지 않습니다.
- 질환명을 맞히기보다 사용자가 고른 신호 조합이 빠른 평가가 필요한 위험 신호인지 판단합니다.
- 근거가 증상 목록을 제시하더라도, 서비스에서는 과도한 경고를 피하기 위해 단독 context trigger를 제한합니다.

| rule | 활성 조건 | 공식 근거 | 단독 trigger 금지/제한 |
| --- | --- | --- | --- |
| `chest_pain_with_shortness_of_breath` | `chest` 부위, `pain`, `shortness_of_breath` | CDC/AHA는 흉부 불편감과 숨참을 심장 관련 warning sign으로 제시 | 흉통 보조 context 단독으로는 이 rule을 만들지 않음 |
| `chest_pain_with_acs_supporting_context` | `chest` 부위, `pain`, `shortness_of_breath` 없음, `chest_pressure`/`radiating_left_arm_or_jaw_or_back`/`cold_sweat`/`persistent_pain` 중 2개 이상 | CDC/AHA/NHS는 지속/반복 흉부 불편감, 팔/턱/등 방사, 식은땀을 심장 관련 warning sign으로 제시 | 보조 context 1개만으로는 red flag 금지 |
| `chest_pain_at_rest` | `chest` 부위, `pain`, `rest_chest_pain` | AHA/CDC/NHS는 쉬어도 지속되거나 반복되는 흉부 불편감을 빠른 평가가 필요한 신호로 제시 | `rest_chest_pain` 단독으로는 red flag 금지 |
| `shortness_of_breath_with_hemoptysis_or_pleuritic_pain` | `chest` 부위, `shortness_of_breath`, `hemoptysis` 또는 `pleuritic_chest_pain` | NHLBI/AHA는 숨참, 깊게 숨쉴 때 통증, 객혈을 pulmonary embolism 관련 warning sign으로 제시 | `hemoptysis`, `pleuritic_chest_pain` 단독으로는 red flag 금지 |
| `airway_swelling_with_breathing_symptom` | 관련 부위, `facial_lip_tongue_throat_swelling`, `wheezing_or_stridor` 또는 `shortness_of_breath` | CDC/NHS/Mayo Clinic은 입술/혀/목 부종과 호흡/쌕쌕거림/기도 증상을 severe allergic reaction 또는 upper-airway danger sign으로 제시 | 부종/알레르기 노출/거친 숨소리 단독으로는 red flag 금지 |
| `progressive_weakness_with_bulbar_or_walking_difficulty` | `weakness`, `progressive_weakness`, `bilateral_limb_weakness`/`walking_difficulty_from_weakness`/`difficulty_swallowing_or_drooling` 중 1개 이상 | WHO/NINDS는 진행성 약화, 보행 어려움, 삼킴/호흡 문제를 Guillain-Barre 계열의 monitoring 필요 신호로 제시 | `progressive_weakness` 단독으로는 red flag 금지 |
| `fever_with_neck_stiffness` | `fever`, `neck_stiffness` | CDC/Mayo Clinic은 발열과 목 경직을 meningitis/meningococcal disease 주요 증상으로 제시 | 둘 중 하나만으로는 red flag 금지 |
| `sudden_one_sided_numbness_or_weakness` | `numbness`, `weakness`, `one_sided` | CDC는 갑작스러운 한쪽 얼굴/팔/다리 저림 또는 약화를 stroke sign으로 제시 | `numbness + weakness`만으로는 red flag 금지 |
| `thunderclap_headache` | `head_face` 부위, `pain`, `max_intensity_within_minutes`, `severity >= 9` 또는 `sudden_onset` | NICE는 수 분 안에 최고 강도에 도달하는 sudden severe headache를 subarachnoid haemorrhage red flag로 제시 | 두통 단독 또는 갑작스러운 시작 단독으로는 red flag 금지 |
| `headache_with_neurologic_deficit` | `head_face` 부위, `pain`, 신경학적 context 중 1개 이상 | NICE/CDC는 두통과 새 신경학적 이상, 말/시야/균형/혼란 신호를 위험 신호로 다룸 | 신경학적 context만으로는 이 rule을 만들지 않음 |
| `sudden_vision_loss` | `eye` 부위, `vision_loss` context | NHS/NEI는 갑작스러운 시력 저하/상실을 빠른 안과 평가 신호로 제시 | 일반 `vision_change` 단독으로는 red flag 금지 |
| `curtain_or_shadow_over_vision` | `eye` 부위, `curtain_or_shadow_over_vision` context | NHS/NEI/AAO EyeWiki는 커튼/그림자 같은 시야 가림을 retinal tear/detachment 관련 warning sign으로 제시 | 일반 `vision_change` 단독으로는 red flag 금지 |
| `severe_eye_pain_with_vision_change` | `eye` 부위, `pain`, `vision_change`, `severity >= 7` | NHS/AAO EyeWiki는 눈 통증과 시야 변화를 빠른 안과 평가가 필요한 신호로 다룸 | 눈 통증 또는 시야 변화 단독으로는 red flag 금지 |
| `new_flashes_or_floaters_with_vision_change` | `eye` 부위, `vision_change`, `new_flashes` 또는 `new_floaters` | NHS/NEI/AAO EyeWiki는 새 번쩍임/비문증과 시야 변화를 retinal tear/detachment 위험 신호로 제시 | 번쩍임/비문증 context만으로는 red flag 금지 |
| `abdominal_pain_with_bloody_stool_or_vomit` | `abdomen` 부위, `pain`, `bloody_stool`/`bloody_vomit`/`black_stool` 중 1개 이상 | Mayo Clinic은 복통과 토혈/혈변/검은 변을 빠른 평가가 필요한 gastrointestinal bleeding 신호로 제시 | 출혈 context만으로는 이 rule을 만들지 않음 |
| `injury_with_numb_or_discolored_extremity` | `after_injury`, `numbness`, `discolored_extremity` 또는 `cold_extremity` | Mayo Clinic first aid guidance는 외상 후 말단 변색/차가움/감각 이상, 혈류 문제 가능성을 평가 신호로 제시 | 외상 또는 저림 단독으로는 red flag 금지 |
| `head_injury_with_neurologic_danger_sign` | `head_injury`, 머리 외상 위험 context 중 1개 이상 | CDC HEADS UP은 머리 외상 후 반복 구토, 발작, 말 어눌함, 약화/저림 등을 concussion danger sign으로 제시 | `head_injury` 단독으로는 red flag 금지 |
| `injury_with_deformity_or_unusable_limb` | `after_injury`, `deformity`/`unable_to_use_joint_or_limb`/`unable_to_bear_weight` 중 1개 이상 | Mayo Clinic first aid guidance는 외상 후 변형, 관절/사지 사용 어려움을 빠른 평가 신호로 제시 | 통증 + 외상만으로는 red flag 금지 |

공식 근거 링크:

- CDC Heart Attack: https://www.cdc.gov/heart-disease/about/heart-attack.html
- AHA Heart Attack Warning Signs: https://www.heart.org/en/health-topics/heart-attack/warning-signs-of-a-heart-attack
- NHLBI Pulmonary Embolism: https://www.nhlbi.nih.gov/health/pulmonary-embolism
- NHS Anaphylaxis: https://www.nhs.uk/conditions/anaphylaxis/
- CDC Stroke Signs: https://www.cdc.gov/stroke/signs-symptoms/
- NICE Subarachnoid Haemorrhage: https://www.nice.org.uk/guidance/ng228/chapter/Recommendations
- NHS Floaters and Flashes: https://www.nhs.uk/symptoms/floaters-and-flashes-in-the-eyes/
- NEI Retinal Detachment: https://www.nei.nih.gov/eye-health-information/eye-conditions-and-diseases/retinal-detachment
- CDC Concussion Danger Signs: https://www.cdc.gov/heads-up/signs-symptoms/index.html
- WHO Guillain-Barre Syndrome: https://www.who.int/news-room/fact-sheets/detail/guillain-barr%C3%A9-syndrome
- NINDS Guillain-Barre Syndrome: https://www.ninds.nih.gov/health-information/disorders/guillain-barre-syndrome
- CDC Meningococcal Disease Symptoms: https://www.cdc.gov/meningococcal/symptoms/
- Mayo Clinic GI Bleeding: https://www.mayoclinic.org/diseases-conditions/gastrointestinal-bleeding/symptoms-causes/syc-20372729
- Mayo Clinic Fractures First Aid: https://www.mayoclinic.org/health/first-aid-fractures/FA00058

v2에서는 넓은 조합을 단독 위험 신호로 쓰지 않습니다. 예를 들어 `두근거림 + 호흡곤란`만으로는 red flag를 바로 활성화하지 않고, `vision_change` 단독, `after_injury + pain` 단독, `numbness + weakness` 단독도 세부 위험 컨텍스트 없이 응급 규칙으로 승격하지 않습니다.

### review-only context 역할 분리

`rule_strength: "review"` context는 공식 자료에서 의미가 확인됐더라도 현재 서비스에서는 `usage: ["explanation_context"]`로만 노출합니다. 일부는 active rule의 조합 조건에 쓰이지만, 단독으로 red flag를 만들 수 없습니다. 이 분리는 사용자가 이해할 수 있는 입력 신호를 수집하면서도, DDXPlus나 단일 단어에 맞춰 과도한 응급 경고를 만들지 않기 위한 안전 장치입니다.

| context | 현재 역할 | active 조합 사용 | 단독 red flag | 근거/제한 |
| --- | --- | --- | --- | --- |
| `wheezing_or_stridor` | airway breathing context | `airway_swelling_with_breathing_symptom`에서 부종과 조합 | 금지 | NHS/CDC/Mayo Clinic에서 airway/allergy 신호로 확인되지만 단독으로는 원인 범위가 넓음 |
| `known_allergen_exposure` | allergy exposure context | 현재 active 조건에는 직접 사용하지 않고 설명/수집 전용 | 금지 | 알레르기 시간적 맥락이지만 증상 조합 없이 응급 신호로 쓰지 않음 |
| `facial_lip_tongue_throat_swelling` | airway swelling context | `airway_swelling_with_breathing_symptom`에서 호흡 증상/context와 조합 | 금지 | 부종 자체는 중요하지만 호흡/기도 신호와 조합될 때만 active |
| `difficulty_swallowing_or_drooling` | upper-airway/bulbar context | `progressive_weakness_with_bulbar_or_walking_difficulty`에서 진행성 약화와 조합 | 금지 | airway와 neurologic 양쪽 맥락이 가능하므로 단독 판단 금지 |
| `voice_hoarseness` | upper-airway explanation context | 현재 active 조건에는 직접 사용하지 않음 | 금지 | upper-airway 후보 설명용. 호흡/부종 조합 없이 active 승격하지 않음 |
| `hemoptysis` | chest/respiratory danger context | `shortness_of_breath_with_hemoptysis_or_pleuritic_pain`에서 호흡곤란과 조합 | 금지 | NHLBI/AHA에서 PE 관련 신호로 확인되지만 단독 객혈만으로 현재 rule 생성 금지 |
| `pleuritic_chest_pain` | chest/respiratory danger context | `shortness_of_breath_with_hemoptysis_or_pleuritic_pain`에서 호흡곤란과 조합 | 금지 | 깊은 숨/기침 시 흉통은 원인 범위가 넓어 호흡곤란 조합에서만 active |
| `rest_chest_pain` | chest pain pattern context | `chest_pain_at_rest`에서 흉통 증상과 조합 | 금지 | 활동 여부 맥락이므로 `pain` 증상 없이 active 금지 |
| `exertional_chest_pain_relieved_by_rest` | angina-like explanation context | 현재 active 조건에는 직접 사용하지 않음 | 금지 | stable angina 맥락 수집용. 단독 응급 rule로 쓰지 않음 |
| `bilateral_limb_weakness` | progressive neurologic context | `progressive_weakness_with_bulbar_or_walking_difficulty`에서 약화+진행성 맥락과 조합 | 금지 | stroke one-sided rule과 분리. 진행성 약화 조합에서만 사용 |
| `walking_difficulty_from_weakness` | progressive neurologic context | `progressive_weakness_with_bulbar_or_walking_difficulty`에서 약화+진행성 맥락과 조합 | 금지 | 통증성 보행 어려움과 구분하기 위해 label에 “힘 빠짐”을 유지 |
| `progressive_weakness` | progressive neurologic pattern context | `progressive_weakness_with_bulbar_or_walking_difficulty`의 필수 context | 금지 | 진행성이라는 양상만으로는 active 금지, 구체적 약화 증상과 추가 맥락 필요 |

### context code 의미 점검

현재 충돌 가능성이 있는 코드는 아래 기준으로 구분합니다.

| code | 구분 기준 | 현재 판단 |
| --- | --- | --- |
| `shortness_of_breath` vs `wheezing_or_stridor` | `shortness_of_breath`는 사용자가 느끼는 숨참 증상이고, `wheezing_or_stridor`는 숨소리/기도 소리 맥락입니다. | 서로 대체하지 않음. airway rule에서는 부종과 함께 둘 중 하나를 호흡/기도 신호로 허용합니다. |
| `difficulty_swallowing_or_drooling` | upper-airway obstruction 맥락과 neurologic/bulbar weakness 맥락에 모두 걸칠 수 있습니다. | 단독 active 금지. airway 설명 chip과 progressive weakness 조합에서만 제한적으로 사용합니다. |
| `rest_chest_pain` vs `exertional_chest_pain_relieved_by_rest` | `rest_chest_pain`은 쉬고 있어도 나타나는 흉통, `exertional...`은 움직일 때 생기고 쉬면 완화되는 흉통입니다. | `rest_chest_pain`만 active 조합에 사용. `exertional...`은 stable-angina-like 설명/수집 전용입니다. |
| `hemoptysis` vs `bloody_vomit` | `hemoptysis`는 기침/가래의 피, `bloody_vomit`는 구토물의 피입니다. | 흉부/호흡기 rule과 복부/GI bleeding rule을 분리합니다. |
| `numbness + weakness + one_sided` vs `bilateral_limb_weakness` | 한쪽 증상은 stroke-like 신호, 양쪽/진행성 약화는 progressive neurologic weakness 신호입니다. | 같은 neurologic bucket으로 합치지 않음. active rule도 분리합니다. |
| `unable_to_bear_weight` vs `walking_difficulty_from_weakness` | 전자는 외상 후 체중 부하/관절 사용 문제, 후자는 힘 빠짐 때문에 걷기 어려움입니다. | injury rule과 progressive weakness rule을 분리합니다. |

### 흉통 red flag 정책

현재 active 흉통/흉부 red flag는 아래 조합으로 제한합니다.

활성 조건:

| rule | 활성 조건 | 단독 trigger 금지 |
| --- | --- | --- |
| `chest_pain_with_shortness_of_breath` | `chest` 부위, `pain` 증상, `shortness_of_breath` 증상 | `chest_pressure`, `radiating_left_arm_or_jaw_or_back`, `cold_sweat`, `persistent_pain`은 보조 맥락 |
| `chest_pain_with_acs_supporting_context` | `chest` 부위, `pain` 증상, `shortness_of_breath` 없음, `chest_pressure`, `radiating_left_arm_or_jaw_or_back`, `cold_sweat`, `persistent_pain` 중 2개 이상 | 보조 맥락 1개만으로는 red flag 금지 |
| `chest_pain_at_rest` | `chest` 부위, `pain` 증상, `rest_chest_pain` context | `rest_chest_pain` context 단독으로는 red flag 금지 |
| `shortness_of_breath_with_hemoptysis_or_pleuritic_pain` | `chest` 부위, `shortness_of_breath` 증상, `hemoptysis` 또는 `pleuritic_chest_pain` context | `hemoptysis`, `pleuritic_chest_pain` 단독으로는 red flag 금지 |

`exertional_chest_pain_relieved_by_rest`는 angina 맥락으로 review-only 유지하며, 단독 red flag를 만들지 않습니다.

이 결정을 유지하는 이유:

- broad safety rule과 공식 근거 기반 세부 조합을 함께 쓰되, 단독 context로 과도한 응급 경고가 생기지 않게 제한합니다.
- DDXPlus의 NSTEMI/STEMI, angina, PE, pneumothorax 계열을 그대로 따라 rule을 세분화하지 않습니다.
- 향후 세분화가 필요하면 CDC/NHS/AHA/NHLBI 같은 공식 근거와 사용자 입력 UX를 함께 검토한 뒤 active rule 후보로 올립니다.

흉통 관련 남은 검토 후보:

| 후보 code | 현재 상태 | 검토 방향 |
| --- | --- | --- |
| `exertional_chest_pain_relieved_by_rest` | review-only context | 안정형 협심증 맥락으로 수집하되 단독 red flag 금지 |
| `pleuritic_chest_pain` | review-only context, 일부 active 조합 | `shortness_of_breath`와 함께 있을 때 `shortness_of_breath_with_hemoptysis_or_pleuritic_pain` rule에 사용 |
| `worse_lying_down_better_sitting` | 비활성 | pericarditis/orthopnea 계열 신호로 공식 근거 확인 |
| `hemoptysis` | review-only context, 일부 active 조합 | `shortness_of_breath`와 함께 있을 때 `shortness_of_breath_with_hemoptysis_or_pleuritic_pain` rule에 사용 |

아래 rule 후보는 1차 구현에서 제외합니다.

| rule 후보 | 제외 사유 |
| --- | --- |
| `severe_abdominal_pain_with_persistent_vomiting` | 복통 강도, 지속 구토, 탈수 동반 여부에 따라 `urgent`와 `emergency` 승격 기준이 달라질 수 있어 제품 정책 확정 전까지 제외합니다. |
| `abdominal_pain_with_dehydration_or_distension` | 탈수, 쇼크 징후, 복부 팽만/압통을 어떤 컨텍스트 코드와 severity 기준으로 받을지 더 정해야 하므로 제외합니다. |
| `palpitation_with_syncope_or_chest_discomfort` | 심계항진 계열은 AF 의심 근거와 응급 red flag 근거를 분리해야 하며, 가슴 통증 rule과 중복될 수 있어 직접 응급 근거를 더 확인하기 전까지 제외합니다. |

### 입력 code 상태표

아래 코드는 DDXPlus coverage를 높이기 위한 항목이 아니라, 사용자가 실제로 이해하고 선택할 수 있는지와 공식 근거 기반 안전 판단에 필요한지 검토하기 위한 입력 신호입니다. 일부는 이미 `CONTEXT_OPTIONS`에 들어간 review-only context이고, 일부는 아직 비활성 설계 후보입니다.

| 분류 | code 후보 | 현재 상태 | 사용자 표시 후보 | 검토 이유 |
| --- | --- | --- | --- | --- |
| 호흡기/기도 | `wheezing_or_stridor` | review-only, 일부 active 조합 | 쌕쌕거림 또는 숨 들이쉴 때 거친 소리 | anaphylaxis, croup, epiglottitis 같은 airway 위험 후보에서 반복되는 신호 |
| 호흡기/기도 | `severe_shortness_of_breath` | 비활성 설계 후보 | 가만히 있어도 심한 숨참 | 흉통, 알레르기, 폐색전/기도 폐쇄 후보에서 공통 안전 신호 |
| 호흡기/기도 | `voice_hoarseness` | review-only | 갑작스러운 쉰 목소리 | upper airway obstruction 후보에서 삼킴/호흡 문제와 함께 검토 |
| 호흡기/기도 | `difficulty_swallowing_or_drooling` | review-only, 일부 active 조합 | 삼키기 어렵거나 침을 삼키기 힘듦 | epiglottitis/anaphylaxis 후보와 progressive neurologic weakness 후보에서 안전 맥락 검토 |
| 알레르기/부종 | `facial_lip_tongue_throat_swelling` | review-only, 일부 active 조합 | 얼굴/입술/혀/목 붓기 | severe allergic reaction 후보에서 airway 관련 부종 확인 |
| 알레르기/노출 | `known_allergen_exposure` | review-only | 알레르기 유발 음식/약/벌침/물질 노출 | 알레르기 반응 맥락을 사용자 입력으로 받을 수 있는지 검토 |
| 기침/가래 | `colored_or_increased_sputum` | 비활성 설계 후보 | 누렇거나 초록색 가래 또는 가래 증가 | pneumonia/COPD/bronchiectasis 후보의 설명 가능성 검토 |
| 기침/가래 | `hemoptysis` | review-only, 일부 active 조합 | 피 섞인 가래/객혈 | pulmonary embolism, bronchiectasis 등에서 urgent 신호 후보 |
| 기침/가래 | `coughing_fits` | 비활성 설계 후보 | 발작적으로 심한 기침 | whooping cough 등 특수 기침 후보 검토 |
| 기침/가래 | `post_tussive_vomiting` | 비활성 설계 후보 | 기침 뒤 구토 | 특수 기침 후보의 보조 맥락 |
| 흉통 양상 | `rest_chest_pain` | review-only, 일부 active 조합 | 쉬고 있어도 가슴 통증 | ACS/unstable angina 후보에서 기존 broad rule 세분화 여부 검토 |
| 흉통 양상 | `exertional_chest_pain_relieved_by_rest` | review-only | 움직이면 악화되고 쉬면 완화되는 가슴 통증 | angina 계열 후보 검토 |
| 흉통 양상 | `pleuritic_chest_pain` | review-only, 일부 active 조합 | 깊게 숨 쉬거나 기침할 때 심해지는 가슴 통증 | pulmonary embolism/pneumothorax/pericarditis 후보 검토 |
| 흉통 양상 | `worse_lying_down_better_sitting` | 비활성 설계 후보 | 누우면 악화되고 앉으면 완화되는 가슴 불편 | pericarditis/orthopnea 계열 후보 검토 |
| 신경계 | `double_vision` | 비활성 설계 후보 | 물체가 둘로 보임 | progressive neurologic weakness 후보 검토 |
| 신경계 | `ptosis_or_eye_facial_weakness` | 비활성 설계 후보 | 눈꺼풀 처짐 또는 얼굴/눈 근육 약화 | myasthenia/neurologic safety path 후보 검토 |
| 신경계 | `bilateral_limb_weakness` | review-only, 일부 active 조합 | 양쪽 팔다리 힘 빠짐 | stroke 한쪽 증상 rule과 분리할 신경계 후보 |
| 신경계 | `walking_difficulty_from_weakness` | review-only, 일부 active 조합 | 힘이 빠져 걷기 어려움 | Guillain-Barre-like progressive weakness 후보 |
| 신경계 | `progressive_weakness` | review-only, 일부 active 조합 | 점점 심해지는 힘 빠짐 | 단발성 저림/힘 빠짐과 구분할 안전 신호 |
| 두통/눈 | `one_sided_headache` | 비활성 설계 후보 | 한쪽으로 치우친 두통 | cluster headache/migraine 세분화 후보 |
| 두통/눈 | `eye_tearing_with_headache` | 비활성 설계 후보 | 두통과 함께 눈물이 남 | cluster headache 후보 검토 |

이 표에는 아직 비활성인 설계 후보와 2026-05-15 검토를 거쳐 review-only context 또는 제한적 active 조합으로 승격된 항목이 함께 있습니다. 새 항목을 추가하거나 단독 red flag로 승격하려면 아래 조건을 먼저 통과해야 합니다.

- 공식/공공/전문기관 출처로 신호 의미 확인
- 기존 active code와 중복/혼동 여부 검토
- 사용자가 이해할 수 있는 한국어 label 확정
- red flag, candidate boost, explanation context 중 용도 분리
- DDXPlus 성능 향상만을 이유로 추가하지 않는다는 검수 기록

## 현재 seed 후보 범위

1차 seed는 시연과 API 계약 안정화를 위한 참고 후보입니다. 후보 룰과 참고 링크는 `health-navigator-backend/app/data/symptom_checker_conditions.json`에서 관리합니다.

| 부위 | 후보 예시 |
| --- | --- |
| 머리/얼굴 | 긴장성 두통, 음주 후 두통 |
| 눈 | 눈 자극 또는 결막염 의심, 안구 건조 관련 증상 |
| 귀/코/목 | 상기도 감염 증상, 코 알레르기 유사 증상, 귀 압박감 관련 증상 |
| 목/어깨 | 목/어깨 근육 긴장, 어깨 과사용 관련 증상 |
| 가슴 | 흉벽 통증, 두근거림 관련 증상 |
| 복부 | 소화불량, 위장염 |
| 골반/비뇨/생식 | 요로 관련 증상, 골반/아랫배 불편 증상 |
| 등/허리 | 근육 긴장 또는 염좌, 좌골신경통 유사 증상 |
| 팔/손 | 팔/손 과사용 증상, 손목/손 과사용 관련 증상, 손/손가락 손상 관련 증상 |
| 다리/발 | 다리/발 근육 또는 관절 부담, 무릎 과사용 또는 손상 관련 증상, 발 불편 또는 손상 관련 증상 |
| 피부 | 피부염, 두드러기 유사 증상 |
| 전신 | 감기, 피로 관련 증상, 발열 관련 증상 |

후보 응답의 `reference_links`는 공식 건강정보 페이지를 연결하기 위한 필드입니다. 외부 콘텐츠 전문을 저장하거나 재가공하지 않고, 링크와 출처 중심으로 제공합니다.

현재 데이터셋은 MedlinePlus XML/Health Topics 사용 정책을 참고해 구성한 초기 seed입니다. MedlinePlus는 XML 파일을 다운로드해 사용할 수 있고, 사용 시 MedlinePlus.gov 출처 표시를 요구합니다. 다만 A.D.A.M. Medical Encyclopedia 등 일부 저작권 콘텐츠는 별도 제한이 있으므로, 서비스에는 전문을 복제하지 않고 링크와 출처 메타데이터만 연결합니다. MedlinePlus 링크는 후보 설명용 참고 링크로 관리하며, v2 위험 신호 판단의 단독 근거로 사용하지 않습니다.

v2 위험 신호의 참고 근거는 질병관리청, CDC, NICE, NHS, NEI, AAO EyeWiki, AHA, Mayo Clinic 같은 공식/공공/전문기관 출처 후보를 우선합니다. 응답은 특정 질환명을 확정하지 않고 "위험 신호"와 "빠른 진료 또는 응급 평가 필요 가능성"으로 표현합니다.

v2 위험 신호 응답에는 `rule_type`, `evidence_level`, `evidence_strength`, `source_status`, `review_status`, `last_reviewed_at` metadata를 포함합니다. 현재 활성 red flag는 `guideline_supported + approved + reviewed` 기준을 기본값으로 내려줍니다.

## 데이터셋 조사 기준

- 무료 사용 가능 여부
- 회원가입 또는 API 키 필요 여부
- 호출량 제한과 운영 안정성
- 상업적 사용 가능 여부
- 콘텐츠 변경, 가공, 저장 가능 여부
- 재배포 가능 여부
- 한국어 질병명과 증상명 지원 여부
- 증상에서 질환 후보로 연결되는 구조화 데이터 제공 여부
- 출처 신뢰도와 업데이트 주기

## 현재 확인한 후보 출처

- 질병관리청 국가건강정보포털 OpenAPI: 공공데이터포털 기준 무료이며 XML/LINK 형태로 제공됩니다. 다만 이용허락범위가 출처표시, 상업적 이용금지, 변경금지를 포함하므로 콘텐츠를 가공 저장하거나 서비스 핵심 데이터셋으로 쓰기 전에 사용 범위 확인이 필요합니다.
- 건강보험심사평가원 보건의료빅데이터개방시스템: 상병, 진료행위, 의약품 등 의료 데이터가 있으나 증상에서 질환 후보로 바로 매핑되는 데이터셋인지 별도 확인이 필요합니다.
- CDC 공개 데이터: 공개 데이터 포털은 있으나 한국어 증상-질환 매핑용으로 바로 쓰기 어렵고, 번역과 용어 표준화가 필요합니다.

데이터셋 후보와 도입 전략은 `docs/SYMPTOM_CHECKER_DATASETS.md`에 별도로 정리합니다.

## 남은 설계 결정

- 큰 부위 범주는 1차에서 12개로 고정되어 있으며, 새 부위 추가는 별도 UX/문서 검토 후 진행한다.
- 세부 부위 선택은 현재 API에서 선택 가능 구조로 두며, 필수 여부는 Flutter UX에서 최종 결정한다.
- 증상은 복수 선택 구조를 유지한다.
- 생활 컨텍스트는 질환 후보를 단독 생성하지 않고 증상 후보 점수 보강, 설명 맥락, 제한된 위험 신호 조합에만 사용한다.
- DB 테이블은 1차 구현에서 만들지 않고, 구조화된 seed 기반 API 골격을 먼저 사용한다. 장기적으로 seed/import 산출물 또는 DB 전환을 검토한다.
- 질환 후보 confidence는 `low`, `medium`, `high` 등급을 사용하되, 현재 curated/manual seed는 최대 `medium`으로 제한한다.
## 2026-05-14 review-only context exposure

- Added `wheezing_or_stridor`, `known_allergen_exposure`, `facial_lip_tongue_throat_swelling`, and `hemoptysis` to `CONTEXT_OPTIONS` as review-only `explanation_context` codes.
- Added chest `context_chips` for `wheezing_or_stridor` and `hemoptysis` with `evidence_basis: red_flag_context_not_standalone`.
- These codes do not activate red flags and do not change candidate scoring.

## 2026-05-15 official-source review for allergy/airway chips

- Reviewed official/public clinical sources only: CDC anaphylaxis guidance, NHS anaphylaxis, NHS epiglottitis, NHS croup, and Mayo Clinic epiglottitis.
- These sources repeatedly identify noisy breathing/wheeze/stridor, breathing difficulty, swallowing difficulty or drooling, hoarse voice, and lips/tongue/throat swelling as allergy or upper-airway safety signals.
- Added `ear_nose_throat` `context_chips` for `wheezing_or_stridor`, `facial_lip_tongue_throat_swelling`, `known_allergen_exposure`, `difficulty_swallowing_or_drooling`, and `voice_hoarseness`.
- These chips remain review-only with `usage: ["explanation_context"]` and `evidence_basis: red_flag_context_not_standalone`.
- Added one reviewed combination red flag: `airway_swelling_with_breathing_symptom`.
- This rule requires `facial_lip_tongue_throat_swelling` plus either `wheezing_or_stridor` or the existing `shortness_of_breath` symptom. `known_allergen_exposure` can be attached as supporting context but is not required and does not trigger the rule by itself.
- `difficulty_swallowing_or_drooling` and `voice_hoarseness` remain review-only context. They do not trigger emergency guidance by themselves.

Reference URLs:

- CDC: https://www.cdc.gov/vaccines/covid-19/clinical-considerations/managing-anaphylaxis.html
- NHS anaphylaxis: https://www.nhs.uk/conditions/anaphylaxis/
- NHS epiglottitis: https://www.nhs.uk/conditions/epiglottitis/
- NHS croup: https://www.nhs.uk/conditions/croup/
- Mayo Clinic epiglottitis: https://www.mayoclinic.org/diseases-conditions/epiglottitis/symptoms-causes/syc-20372227

## 2026-05-15 official-source review for chest/PE and progressive weakness

- Reviewed official/public clinical sources only: NHLBI pulmonary embolism, American Heart Association pulmonary embolism, CDC heart attack, WHO Guillain-Barre syndrome, NINDS Guillain-Barre syndrome, and CDC Guillain-Barre syndrome.
- Added one ACS-supporting chest red flag: `chest_pain_with_acs_supporting_context`.
- This rule requires the `pain` symptom in the `chest` region and at least two of `chest_pressure`, `radiating_left_arm_or_jaw_or_back`, `cold_sweat`, and `persistent_pain`. A single supporting context must not trigger emergency guidance.
- This rule is skipped when `shortness_of_breath` is already present, because `chest_pain_with_shortness_of_breath` covers that broader safety path.
- Added `rest_chest_pain` and `exertional_chest_pain_relieved_by_rest` as review-only context codes.
- Added one rest-chest-pain red flag: `chest_pain_at_rest`. This rule requires the `pain` symptom in the `chest` region plus `rest_chest_pain`.
- `exertional_chest_pain_relieved_by_rest` remains review-only and must not trigger emergency guidance by itself.
- Added `pleuritic_chest_pain`, `bilateral_limb_weakness`, `walking_difficulty_from_weakness`, and `progressive_weakness` as review-only `explanation_context` codes.
- Added one chest/respiratory combination red flag: `shortness_of_breath_with_hemoptysis_or_pleuritic_pain`.
- This rule requires the existing `shortness_of_breath` symptom plus `hemoptysis` or `pleuritic_chest_pain`. Either context alone must not trigger emergency guidance.
- Added one neurologic combination red flag: `progressive_weakness_with_bulbar_or_walking_difficulty`.
- This rule requires the `weakness` symptom plus `progressive_weakness` and at least one of `bilateral_limb_weakness`, `walking_difficulty_from_weakness`, or `difficulty_swallowing_or_drooling`.
- These rules are risk-signal combinations, not diagnosis or disease-name candidates.

Reference URLs:

- NHLBI pulmonary embolism: https://www.nhlbi.nih.gov/health/pulmonary-embolism
- American Heart Association pulmonary embolism: https://www.heart.org/en/health-topics/pulmonary-embolism
- CDC heart attack: https://www.cdc.gov/heart-disease/about/heart-attack.html
- WHO Guillain-Barre syndrome: https://www.who.int/news-room/fact-sheets/detail/guillain-barr%C3%A9-syndrome
- NINDS Guillain-Barre syndrome: https://www.ninds.nih.gov/health-information/disorders/guillain-barre-syndrome
- CDC Guillain-Barre syndrome: https://www.cdc.gov/campylobacter/signs-symptoms/guillain-barre-syndrome.html

## 2026-05-17 Zero-Cost Model Direction

- The project will not use paid OpenAI API calls for the current scope.
- `/symptom-checker/explain` remains card-based: it uses reviewed internal explanation cards and must not call an external LLM provider by default.
- OpenAI/GPT models are treated as deferred paid-provider options only. They are not part of the current zero-cost implementation path.
- KM-BERT is the primary medical BERT candidate for Korean free-text structure assistance under the current non-commercial research/demo scope.
- The current local prototype is a fine-tuned BERT structure classifier under `.model-cache/kmbert-structure`, trained to emit internal `BODY_REGION__*`, `SYMPTOM__*`, and `CONTEXT__*` labels.
- KM-BERT is limited to `/symptom-checker/structure` and `/symptom-checker/assessment-draft` candidate extraction before whitelist validation.
- KM-BERT must not create or mutate `red_flags`, `condition_candidates`, `confidence`, `severity`, `suggested_action`, diagnosis, or treatment text.
- The local model connection exists as an optional prototype path, but it remains disabled by default until runtime checks and extraction quality are acceptable for user-facing enablement.
- Model weights, raw medical text, and generated large artifacts must not be committed.

## 2026-05-20 Structure Performance Tuning

- Tuning 기준과 변경 기록은 `docs/SYMPTOM_CHECKER_TUNING_POLICY.md`를 따른다.
- 이번 단계는 LLM 출력 이전의 구조화 결과값 품질만 다룬다.
- alias 기반 구조화 성능은 train/validate만 사용해 평가했고, test split은 최종 보고 전까지 튜닝에 사용하지 않는다.
- 2026-05-20 alias 평가 결과: overall body_region accuracy `0.9338`, symptom micro F1 `0.8519`, context micro F1 `0.7500`.
- validate 결과: body_region accuracy `1.0000`, symptom micro F1 `0.9677`, context micro F1 `0.8750`.
- final holdout 확인 결과: test body_region accuracy `0.7143`, symptom micro F1 `0.5455`, context micro F1 `0.7600`.
- test 결과를 보고 추가 튜닝하지 않았다. 다음 성능 작업은 test 문장 맞춤이 아니라 독립 라벨 확대 또는 KM-BERT 구조화 모델 개선으로 진행한다.
- red flag rule, condition candidate rule, confidence, severity, suggested_action은 이 튜닝에서 변경하지 않았다.

