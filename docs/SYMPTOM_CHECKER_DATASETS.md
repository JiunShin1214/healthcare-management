# Symptom Checker Dataset Review

이 문서는 인체 UI 기반 증상 탐색 기능에 사용할 수 있는 데이터셋과 외부 API 후보를 정리합니다.

검토 기준일은 2026-05-10입니다. 라이선스와 API 정책은 바뀔 수 있으므로 실제 도입 전 다시 확인해야 합니다.

## 결론

1차 MVP는 외부 대량 데이터셋을 바로 적재하지 않고, 현재 백엔드의 rule-based seed를 `health-navigator-backend/app/data/symptom_checker_conditions.json` 파일로 분리해 로드합니다.

그 이유는 다음과 같습니다.

- 신뢰할 수 있는 공공/공식 출처는 건강정보 콘텐츠 중심이고, 증상에서 질환 후보로 바로 연결되는 구조화 데이터가 부족합니다.
- 증상-질환 매핑 CSV류 데이터는 Kaggle 등에 있으나 출처와 임상 검증 수준이 불명확하거나 synthetic 데이터가 많습니다.
- 상용 증상 체커 API는 기능적으로 가장 가깝지만 계약, 비용, 운영 의존성이 생깁니다.
- 질병관리청 국가건강정보포털은 한국어 콘텐츠 측면에서는 매력적이나, 이용허락범위에 상업적 이용금지와 변경금지가 포함되어 있어 가공 저장형 핵심 데이터셋으로 쓰기 어렵습니다.

따라서 단계는 다음처럼 둡니다.

```text
1차: 직접 정의한 rule-based seed 확장
2차: 공식 출처의 질환 설명과 참고 링크 연결
3차: 라이선스가 명확한 매핑 데이터셋 또는 상용 API 검토
```

## 후보 요약

| 후보 | 유형 | 장점 | 주요 제약 | 1차 도입 판단 |
| --- | --- | --- | --- | --- |
| 질병관리청 국가건강정보포털 | 한국어 공식 건강정보 API | 한국어, 공공기관 출처, 무료 | 상업적 이용금지/변경금지 조건, 콘텐츠 가공 저장 주의 | 참고 링크/설명 출처 후보 |
| MedlinePlus XML/Web Service | 영어/스페인어 건강 주제 XML/API | 무료, 등록/라이선스 불필요, XML 제공, 공신력 높음 | 한국어 없음, 증상-질환 추론 엔진 아님 | 질환 설명/외부 링크 후보 |
| MedlinePlus Connect | 코드 기반 건강정보 연결 API | ICD 등 코드 기반 연결 가능, JSON/XML 지원 | 증상 입력에서 질환 후보를 직접 반환하지 않음 | 나중에 질환 코드가 생긴 뒤 연결 |
| Human Phenotype Ontology | 표현형/질환 어노테이션 | 구조화된 phenotype-disease annotation, 재사용성 높음 | 희귀질환/표현형 중심, 일반 사용자 증상 용어 매핑 필요 | 장기 후보 |
| CDC Open Data | 공개 보건 데이터/API | 공공 보건 데이터 풍부, Socrata API | 증상-질환 매핑보다는 통계/감시 데이터 중심 | 직접 매핑용으로는 낮음 |
| Infermedica API | 상용 증상 분석/triage API | 증상 체커 기능에 가장 가까움, 다국어 지원 | 상용 계약/비용/외부 의존성 | MVP 이후 검토 |
| Kaggle SympScan | CSV 증상-질환 매핑 | CC0 표기, 빠른 실험 가능 | 출처/의학 검증 확인 필요, 약/식단 권고 데이터는 사용 주의 | 내부 실험 후보 |
| Kaggle Symptoms to diseases | CSV/NLP 매핑 | ODbL/DbCL 계열 표기, 구조화 데이터 | 출처/검증 확인 필요, 라이선스 세부 의무 확인 필요 | 내부 실험 후보 |

## 공식/공공 출처

### 질병관리청 국가건강정보포털

공공데이터포털의 `질병관리청_국가건강정보포털` API는 무료이고 XML/LINK 형태로 제공됩니다. 다만 이용허락범위가 공공누리 제4유형으로 표시되어 있으며, 출처표시와 함께 상업적 이용금지, 변경금지 조건이 포함됩니다.

국가건강정보포털 OpenAPI 신청 화면의 콘텐츠 사용 동의서도 콘텐츠 일부/전부 변경 금지, 직접적 영리 목적 사용 제한, 출처 명시, 변경사항 반영 의무 등을 안내합니다.

판단:

- 한국어 질환 설명과 참고 링크 출처로는 유용합니다.
- 증상-질환 매핑 데이터를 가공 저장하는 핵심 데이터셋으로 쓰기 전에는 사용 범위를 별도 확인해야 합니다.
- 서비스 응답에는 질병관리청 콘텐츠를 그대로 복제하기보다 링크와 출처를 연결하는 방식이 안전합니다.

출처:

- https://www.data.go.kr/data/15087442/openapi.do
- https://health.kdca.go.kr/healthinfo/biz/health/portalUseGuidance/openApiReqst/openApiReqstRegist.do

### MedlinePlus XML Files

MedlinePlus는 건강 주제 XML 파일을 제공하며, 영어와 스페인어 health topic 데이터를 포함합니다. XML 파일에는 health topic title, URL, language, vocabulary, summary, group membership, related topics, related content 등이 들어갑니다.

MedlinePlus는 XML 데이터를 다운로드해 사용할 수 있다고 안내하며, 사용할 경우 정보 출처가 MedlinePlus.gov임을 표시하라고 요구합니다.

판단:

- 무료/공식/구조화 측면에서 좋은 후보입니다.
- 다만 증상 입력을 받아 질환 후보를 계산하는 데이터셋은 아닙니다.
- 질환 후보가 정해진 뒤 설명, 관련 링크, 외부 참고자료를 붙이는 용도에 적합합니다.

출처:

- https://medlineplus.gov/xml.html
- https://medlineplus.gov/about/developers/webservices/
- https://medlineplus.gov/about/using/usingcontent

### MedlinePlus Connect

MedlinePlus Connect는 diagnosis/problem code, drug code, lab test code, procedure code를 기반으로 관련 건강정보를 연결하는 서비스입니다. 출력은 XML, JSON, JSONP를 지원합니다.

판단:

- 현재처럼 증상만 있는 단계에서는 직접 쓰기 어렵습니다.
- 나중에 질환 후보에 ICD 같은 코드가 붙으면 참고 정보 연결용으로 가치가 있습니다.

출처:

- https://medlineplus.gov/medlineplus-connect/web-service

### Human Phenotype Ontology

HPO는 human phenotypic abnormalities를 구조화한 표준 vocabulary와 disease-phenotype annotation을 제공합니다. `phenotype.hpoa`는 disease name, HPO term, evidence, onset, frequency, sex 등 필드를 포함합니다.

판단:

- 구조화 정도는 매우 좋습니다.
- 일반 사용자가 고르는 “두통, 복통, 기침” 같은 UX 증상 코드와 HPO 표현형 용어를 매핑하는 중간 계층이 필요합니다.
- 희귀질환/유전질환 쪽이 강하므로 일반 MVP 데이터셋으로 바로 쓰기보다는 장기 확장 후보입니다.

출처:

- https://obophenotype.github.io/human-phenotype-ontology/annotations/phenotype_hpoa/
- https://bioportal.bioontology.org/ontologies/HP

### CDC Open Data

CDC는 Data.CDC.gov, Chronic Disease Indicators, NCHS, NNDSS 등 다양한 데이터셋과 Socrata API를 제공합니다.

판단:

- 보건 통계, 감시, 공중보건 데이터에는 강합니다.
- 사용자 증상에서 질환 후보를 직접 계산하는 데이터셋으로는 적합도가 낮습니다.
- 특정 질환 설명이나 유행성 질환 참고자료로는 나중에 연결할 수 있습니다.

출처:

- https://open.cdc.gov/data.html
- https://open.cdc.gov/apis.html

## 상용 API 후보

### Infermedica

Infermedica는 증상, 위험요인, 인구통계 정보를 받아 probable conditions, triage level, specialist recommendation 등을 제공하는 API/엔진을 설명합니다. 제품 설명상 증상 체커 목적에는 가장 가깝습니다.

판단:

- 기능 적합도는 높습니다.
- 다만 MVP 단계에서는 비용, 계약, 외부 의존성, 개인정보/의료정보 처리 검토가 필요합니다.
- 나중에 프로젝트가 실제 서비스화 단계로 가면 build-vs-buy 후보로 검토합니다.

출처:

- https://infermedica.com/product/symptom-checker
- https://developer.infermedica.com/docs/faq

## Kaggle/공개 CSV 후보

Kaggle의 증상-질환 데이터셋은 빠르게 실험하기 좋지만, 출처와 임상 검증 수준을 반드시 분리해서 봐야 합니다.

### SympScan

SympScan은 200개 이상 증상과 100개 이상 질환을 매핑한다고 설명하며, Kaggle 페이지상 라이선스는 CC0 Public Domain으로 표시됩니다.

판단:

- 내부 실험과 매핑 구조 검증에는 유용할 수 있습니다.
- 약물, 식단, 운동 권고 같은 후속 조치 데이터는 의료 조언처럼 보일 수 있으므로 MVP에서는 사용하지 않습니다.
- 실제 서비스 데이터로 쓰기 전에는 원 출처와 의학 검증 가능성을 확인해야 합니다.

출처:

- https://www.kaggle.com/datasets/behzadhassan/sympscan-symptomps-to-disease

### Symptoms to diseases

이 데이터셋은 713개 질환과 377개 binary symptom column, NLP용 symptom text 데이터를 제공한다고 설명합니다. Kaggle 페이지상 라이선스는 Database: Open Database, Contents: Database Contents로 표시됩니다.

판단:

- 증상-질환 매핑 구조 실험에 적합합니다.
- ODbL/DbCL 계열은 attribution/share-alike 등 세부 의무가 있을 수 있으므로 실제 도입 전 라이선스 전문을 확인해야 합니다.
- 한국어 용어 매핑과 질환명 표준화가 필요합니다.

출처:

- https://www.kaggle.com/datasets/abhishekgodara/symptoms-to-diseases

## 데이터 도입 기준

실제 도입 전에는 후보마다 아래 체크리스트를 통과해야 합니다.

- 무료 사용 가능 여부
- 회원가입/API 키 필요 여부
- 상업적 사용 가능 여부
- 수정/가공 가능 여부
- 저장 가능 여부
- 재배포 가능 여부
- 출처 표기 의무
- 한국어 지원 여부
- 증상-질환 매핑 구조 제공 여부
- 원 출처와 의학 검증 가능성
- 업데이트 주기
- 서비스 응답에 노출 가능한 문구 범위

## 추천 도입 전략

### Red flag 근거 정책

- 위험 신호 판단 근거는 공식기관, 공공 보건기관, 전문학회, 임상 가이드라인처럼 신뢰도와 책임 주체가 분명한 출처를 우선합니다.
- MedlinePlus와 MedlinePlus Medical Encyclopedia는 후보 설명 링크와 참고 메타데이터로는 사용할 수 있지만, red flag 활성화의 단독 근거로 쓰지 않습니다.
- 질병관리청 국가건강정보포털은 한국어 공식 출처로 유용하지만, 콘텐츠 전문을 복제하거나 가공 저장하지 않고 링크와 출처 중심으로 연결합니다.
- v2 위험 신호 규칙의 1차 근거 후보는 질병관리청, CDC, NICE, NHS, NEI, AAO EyeWiki, AHA, Mayo Clinic입니다.
- Kaggle, DDXPlus, HPO 같은 매핑/표현형 데이터는 후보 점수화 실험에는 쓸 수 있어도, 사용자가 보는 응급 위험 신호를 자동 생성하는 근거로는 쓰지 않습니다.

### Red flag 후보 근거 검토 큐

아래 항목은 DDXPlus 질환명을 그대로 서비스 rule로 옮긴 목록이 아니라, 사용자에게 실제로 받을 수 있는 입력 신호와 공식/공공 출처에서 반복 확인되는 위험 신호를 대조한 검토 큐입니다. 일부 항목은 2026-05-15 공식 근거 검토를 거쳐 제한적 active 조합으로 승격되었고, 나머지는 review-only 또는 비활성 설계 후보로 남아 있습니다.

상태 용어:

- `active 조합`: 현재 rule engine에서 특정 symptom/context 조합이 충족될 때만 red flag를 반환합니다.
- `review-only`: `CONTEXT_OPTIONS`에 있지만 `usage: ["explanation_context"]`로만 노출합니다. 일부 active 조합의 구성 요소가 될 수 있으나 단독 red flag는 만들 수 없습니다.
- `비활성 설계 후보`: 아직 `CONTEXT_OPTIONS`에 넣지 않은 설계 후보입니다. 공식 근거, 사용자 UX, 기존 code와의 중복 검토 전에는 API 입력이나 rule에 반영하지 않습니다.

| 후보군 | 입력 code 후보 | 근거 출처 후보 | 상태 |
| --- | --- | --- | --- |
| Severe allergic reaction/anaphylaxis | `known_allergen_exposure`, `facial_lip_tongue_throat_swelling`, `wheezing_or_stridor`, `severe_shortness_of_breath`, `difficulty_swallowing_or_drooling`, 전신 두드러기/어지러움 | CDC adverse reaction guidance, CDC anaphylaxis guidance, NHS anaphylaxis | `airway_swelling_with_breathing_symptom` 조합만 active. `known_allergen_exposure`, `facial_lip_tongue_throat_swelling`, `wheezing_or_stridor`, `difficulty_swallowing_or_drooling`은 review-only. `severe_shortness_of_breath`, 전신 두드러기/어지러움은 비활성 설계 후보 |
| Upper airway obstruction | `wheezing_or_stridor`, `severe_shortness_of_breath`, `difficulty_swallowing_or_drooling`, `voice_hoarseness`, 고열/심한 인후통 | NHS epiglottitis, NHS croup, Mayo Clinic epiglottitis | `wheezing_or_stridor`, `difficulty_swallowing_or_drooling`, `voice_hoarseness`는 review-only. `severe_shortness_of_breath`, 고열/심한 인후통 조합은 비활성 설계 후보. 단독 red flag 금지 |
| Acute coronary syndrome/chest pain | `chest_pressure`, `radiating_left_arm_or_jaw_or_back`, `cold_sweat`, `persistent_pain`, `rest_chest_pain`, `exertional_chest_pain_relieved_by_rest`, 호흡곤란 | CDC heart attack, American Heart Association heart attack, NHS heart attack | `chest_pain_with_shortness_of_breath`, `chest_pain_with_acs_supporting_context`, `chest_pain_at_rest` 조합만 active. `exertional_chest_pain_relieved_by_rest`는 review-only이며 단독 red flag 금지 |
| Pulmonary embolism/pneumothorax-like pleuritic danger | `severe_shortness_of_breath`, `pleuritic_chest_pain`, `hemoptysis`, 갑작스러운 시작, 실신/심한 어지러움 | NHLBI pulmonary embolism, American Heart Association pulmonary embolism | `shortness_of_breath_with_hemoptysis_or_pleuritic_pain` 조합만 active. `pleuritic_chest_pain`, `hemoptysis`는 review-only. `severe_shortness_of_breath`, 실신/심한 어지러움은 비활성 설계 후보 |
| Progressive neurologic weakness | `bilateral_limb_weakness`, `progressive_weakness`, `walking_difficulty_from_weakness`, `difficulty_swallowing_or_drooling`, 호흡곤란 | WHO Guillain-Barre syndrome, NINDS Guillain-Barre syndrome, CDC Guillain-Barre syndrome | `progressive_weakness_with_bulbar_or_walking_difficulty` 조합만 active |

흉통 후보 중 ACS 계열은 세 경로만 active로 둡니다. 첫째, `chest_pain_with_shortness_of_breath`는 기존처럼 가슴 통증과 호흡곤란 조합을 잡습니다. 둘째, `chest_pain_with_acs_supporting_context`는 가슴 통증과 `chest_pressure`, `radiating_left_arm_or_jaw_or_back`, `cold_sweat`, `persistent_pain` 중 2개 이상이 함께 있을 때만 활성화합니다. 단일 보조 context는 red flag를 만들지 않습니다. 셋째, `chest_pain_at_rest`는 가슴 통증과 `rest_chest_pain` 조합에서만 활성화합니다. `exertional_chest_pain_relieved_by_rest`는 angina 맥락으로 review-only 유지하며 단독 red flag를 만들지 않습니다. `worse_lying_down_better_sitting`은 공식 근거 확인 전까지 비활성 설계 후보로 둡니다. `hemoptysis`와 `pleuritic_chest_pain`은 `shortness_of_breath`와 조합될 때만 active red flag에 사용합니다.

검토 원칙:

- 이 표의 code는 DDXPlus coverage 개선만을 이유로 API에 추가하지 않습니다.
- 출처 확인 전에는 red flag rule, context chip, candidate boost로 사용하지 않습니다.
- active로 승격된 항목도 단독 context가 아니라 문서화된 symptom/context 조합에서만 사용합니다.
- DDXPlus coverage 개선을 목표로 code를 추가하지 않습니다.
- code 추가 여부는 사용자 UX, 안전 판단 필요성, 공식 근거, 기존 rule 중복 여부를 함께 보고 결정합니다.

2026-05-15 검토 결과:

- CDC anaphylaxis guidance와 NHS anaphylaxis는 wheeze/stridor/noisy breathing, breathing difficulty, swallowing difficulty, throat/tongue/lip swelling을 심한 알레르기 반응의 인식 신호로 제시한다.
- NHS epiglottitis와 Mayo Clinic epiglottitis는 stridor/high-pitched breathing, difficulty breathing, difficulty swallowing, drooling, hoarse voice를 upper-airway emergency 맥락으로 제시한다.
- NHS croup은 hoarse voice, difficulty breathing, high-pitched rasping sound when breathing in을 제시하고, drooling/swallowing difficulty가 있으면 즉시 도움을 요청할 신호로 제시한다.
- 따라서 `ear_nose_throat`에는 `wheezing_or_stridor`, `facial_lip_tongue_throat_swelling`, `known_allergen_exposure`, `difficulty_swallowing_or_drooling`, `voice_hoarseness`를 review-only chip으로 노출한다.
- `airway_swelling_with_breathing_symptom`은 active red flag 조합으로 승격한다.
- 활성 조건은 `facial_lip_tongue_throat_swelling`과 `wheezing_or_stridor` 또는 기존 `shortness_of_breath` 증상의 조합이다.
- `known_allergen_exposure`는 supporting context로만 기록하며, 단독 trigger 또는 필수 조건으로 사용하지 않는다.
- `difficulty_swallowing_or_drooling`와 `voice_hoarseness`도 supporting/review-only context 후보로 둔다. 공식 출처에서 upper-airway 맥락으로 확인되지만, 현재 구현에서는 단독 red flag 조건으로 사용하지 않는다. `difficulty_swallowing_or_drooling`은 별도 progressive weakness 조합에서는 구성 요소로 쓰인다.
- 개별 chip의 `usage: ["explanation_context"]`, `rule_strength: "review"`, `evidence_basis: red_flag_context_not_standalone`은 유지한다.
- 다음 active rule 검토 때도 단독 chip이 아니라 다중 시스템/호흡곤란/부종/삼킴 곤란/노출 시간 관계 같은 조합 조건만 검토한다.

검토 출처:

- CDC anaphylaxis guidance: https://www.cdc.gov/vaccines/covid-19/clinical-considerations/managing-anaphylaxis.html
- NHS anaphylaxis: https://www.nhs.uk/conditions/anaphylaxis/
- NHS epiglottitis: https://www.nhs.uk/conditions/epiglottitis/
- NHS croup: https://www.nhs.uk/conditions/croup/
- Mayo Clinic epiglottitis: https://www.mayoclinic.org/diseases-conditions/epiglottitis/symptoms-causes/syc-20372227

2026-05-15 흉통/폐색전 및 진행성 약화 검토 결과:

- NHLBI와 American Heart Association은 pulmonary embolism 증상으로 호흡곤란, 깊게 숨쉴 때 통증 또는 깊은 호흡/기침으로 악화되는 흉통, 피 섞인 기침/객혈, 어지러움/실신 등을 제시한다.
- 따라서 `pleuritic_chest_pain`을 review-only context로 추가하고, 기존 `hemoptysis`와 함께 chest safety 맥락으로 둔다.
- `shortness_of_breath_with_hemoptysis_or_pleuritic_pain`은 active red flag 조합으로 승격한다.
- 활성 조건은 기존 `shortness_of_breath` 증상과 `hemoptysis` 또는 `pleuritic_chest_pain` context의 조합이다. `hemoptysis` 또는 `pleuritic_chest_pain` 단독으로는 red flag를 만들지 않는다.
- CDC/AHA/NHS heart attack 자료는 chest discomfort, shortness of breath, cold sweat, jaw/neck/back/arm discomfort를 제시한다. 현재 구현은 `chest_pain_with_shortness_of_breath`, `chest_pain_with_acs_supporting_context`, `chest_pain_at_rest` 세 경로만 active로 둔다.
- WHO, NINDS, CDC 자료는 Guillain-Barre syndrome 관련 안전 맥락으로 진행하는 약화, 팔다리 약화, 삼킴/말하기/호흡 문제, 보행/균형 문제를 제시한다.
- 따라서 `bilateral_limb_weakness`, `walking_difficulty_from_weakness`, `progressive_weakness`를 review-only context로 추가한다.
- `progressive_weakness_with_bulbar_or_walking_difficulty`는 active red flag 조합으로 승격한다.
- 활성 조건은 `weakness` 증상, `progressive_weakness` context, 그리고 `bilateral_limb_weakness`, `walking_difficulty_from_weakness`, `difficulty_swallowing_or_drooling` 중 하나 이상의 조합이다. 진행성 약화 context 단독으로는 red flag를 만들지 않는다.
- 이 조합들은 질환명 후보가 아니라 위험 신호 조합이다.

현재 `docs/SYMPTOM_CHECKER.md`의 상태표와 맞춘 입력 code 상태:

| code | 현재 상태 |
| --- | --- |
| `wheezing_or_stridor` | review-only, `airway_swelling_with_breathing_symptom` 조합 구성 요소 |
| `known_allergen_exposure` | review-only, 설명/수집 전용 |
| `facial_lip_tongue_throat_swelling` | review-only, `airway_swelling_with_breathing_symptom` 조합 구성 요소 |
| `difficulty_swallowing_or_drooling` | review-only, `progressive_weakness_with_bulbar_or_walking_difficulty` 조합 구성 요소 |
| `voice_hoarseness` | review-only, 설명/수집 전용 |
| `hemoptysis` | review-only, `shortness_of_breath_with_hemoptysis_or_pleuritic_pain` 조합 구성 요소 |
| `pleuritic_chest_pain` | review-only, `shortness_of_breath_with_hemoptysis_or_pleuritic_pain` 조합 구성 요소 |
| `rest_chest_pain` | review-only, `chest_pain_at_rest` 조합 구성 요소 |
| `exertional_chest_pain_relieved_by_rest` | review-only, 설명/수집 전용 |
| `bilateral_limb_weakness` | review-only, `progressive_weakness_with_bulbar_or_walking_difficulty` 조합 구성 요소 |
| `walking_difficulty_from_weakness` | review-only, `progressive_weakness_with_bulbar_or_walking_difficulty` 조합 구성 요소 |
| `progressive_weakness` | review-only, `progressive_weakness_with_bulbar_or_walking_difficulty` 필수 context |

아직 `CONTEXT_OPTIONS`에 없는 code는 비활성 설계 후보이며, DDXPlus 성능이나 coverage만을 이유로 추가하지 않는다.

검토 출처:

- NHLBI pulmonary embolism: https://www.nhlbi.nih.gov/health/pulmonary-embolism
- American Heart Association pulmonary embolism: https://www.heart.org/en/health-topics/pulmonary-embolism
- CDC heart attack: https://www.cdc.gov/heart-disease/about/heart-attack.html
- WHO Guillain-Barre syndrome: https://www.who.int/news-room/fact-sheets/detail/guillain-barr%C3%A9-syndrome
- NINDS Guillain-Barre syndrome: https://www.ninds.nih.gov/health-information/disorders/guillain-barre-syndrome
- CDC Guillain-Barre syndrome: https://www.cdc.gov/campylobacter/signs-symptoms/guillain-barre-syndrome.html

### 1차 MVP

- 현재 코드의 `required_symptoms`, `optional_symptoms`, `boosting_contexts` 구조를 유지합니다.
- condition seed는 `app/data/symptom_checker_conditions.json`에서 관리하고, 서비스는 이 파일을 로드해 후보를 계산합니다.
- 각 부위별 질환 후보를 2~3개씩 직접 seed로 늘립니다.
- 후보 이름은 “질환 확정”이 아니라 “관련 증상군” 또는 “가능성 있는 질환 후보”로 표현합니다.

### 2차 콘텐츠 연결

- 질환 후보에 `reference_links` 필드를 추가합니다.
- 질병관리청 또는 MedlinePlus 링크를 연결합니다.
- 외부 콘텐츠 전문을 저장하거나 재가공하지 않고, 출처와 링크 중심으로 제공합니다.

### 3차 데이터셋 실험

- Kaggle CC0/ODbL 후보를 로컬 실험 데이터로만 사용합니다.
- 기존 증상 코드와 외부 symptom column 간 매핑 테이블을 만듭니다.
- 자동 결과를 서비스 응답에 바로 쓰지 않고, rule seed를 확장하는 참고자료로만 사용합니다.

### DDXPlus 로컬 준비

DDXPlus 원본 데이터는 사용자가 직접 내려받아 로컬에 추가합니다. 원본 파일은 Git에 넣지 않고, `.gitignore` 대상 로컬 데이터로 취급합니다.

현재 로컬 위치:

| 위치 | 용도 |
| --- | --- |
| `health-navigator-backend/app/data/raw/` | 사용자가 내려받은 DDXPlus 원본 파일 |
| `health-navigator-backend/app/data/processed/` | import 스크립트가 만든 중간 산출물 |
| `health-navigator-backend/app/data/review/` | 사람이 검수할 매핑표 |

사용자가 원본을 추가할 때 함께 기록할 정보:

- 다운로드 URL 또는 배포 페이지
- 다운로드 날짜
- 데이터셋 버전 또는 커밋/릴리스 식별자
- 라이선스 표기
- 원본 파일명
- train/validate/test split 파일 구분

첫 산출물 후보:

| 파일 | 용도 |
| --- | --- |
| `pathology_candidates.csv` | DDXPlus `PATHOLOGY`를 내부 `condition_code` 후보로 정규화 |
| `evidence_candidates.csv` | DDXPlus `EVIDENCES`를 내부 `symptom_code` 또는 `context_code` 후보로 정규화 |
| `condition_evidence_frequency.csv` | train split 기준 질환별 evidence 빈도표 |
| `condition_prior_by_age_sex.csv` | age/sex별 질환 후보 prior 집계 |
| `ddxplus_mapping_review.csv` | 사람이 최종 검수할 매핑표 |

반영 원칙:

- `train`만 rule 후보 추출과 모델 학습에 사용합니다.
- `validate`는 오류 분석, 매핑 품질 검토, 사전 정의된 전역 파라미터 검토에만 사용합니다.
- `test`는 최종 평가 전용으로 두고 rule 생성, 매핑 수정, 파라미터 조정에는 쓰지 않습니다.
- `PATHOLOGY`와 `EVIDENCES` 매핑이 모두 `approved`인 항목만 candidate scoring 보강에 사용할 수 있습니다.
- DDXPlus는 candidate ranking 보강에만 사용하고 red flag 생성에는 사용하지 않습니다.

### DDXPlus 학습 계획

DDXPlus 기반 모델은 참고용 질환 후보의 순위 보강에만 사용합니다. 사용자가 보는 위험 신호, 응급 안내, red flag severity는 기존 rule engine이 담당하며 모델 출력으로 생성하거나 변경하지 않습니다.

학습 단계:

1. 원본 구조 확인
   - 사용자가 `raw/`에 추가한 파일명, 컬럼, split 구성을 확인합니다.
   - `PATHOLOGY`, `EVIDENCES`, `INITIAL_EVIDENCE`, `AGE`, `SEX`, `DIFFERENTIAL_DIAGNOSIS`에 해당하는 컬럼을 기록합니다.
2. 매핑 후보 생성
   - `PATHOLOGY`를 내부 `condition_code` 후보로 정규화합니다.
   - `EVIDENCES`를 내부 `symptom_code` 또는 `context_code` 후보로 정규화합니다.
   - 자동 매핑은 기본적으로 `needs_review`로 시작합니다.
3. 사람 검수
   - `ddxplus_mapping_review.csv`에서 `approved`인 매핑만 학습/평가에 사용합니다.
   - `needs_review`와 `rejected`는 candidate scoring 보강에 반영하지 않습니다.
4. 빈도표 baseline
   - 모델 없이 train split에서 condition별 evidence 빈도표를 만듭니다.
   - 이 baseline으로 rule seed 보강 후보와 평가 기준을 먼저 확인합니다.
5. 1차 모델
   - Logistic Regression multiclass classifier를 첫 모델로 사용합니다.
   - 입력 feature는 내부 symptom/context one-hot, age bucket, sex, initial evidence 후보를 사용합니다.
   - 출력은 내부 `condition_code`별 score 또는 probability입니다.
6. 후속 모델
   - baseline과 Logistic Regression이 안정된 뒤 LightGBM/XGBoost multiclass classifier 또는 ranker를 검토합니다.

서빙 구조:

```text
사용자 입력
  -> 내부 symptom/context 코드 검증
  -> rule-based candidate 생성
  -> DDXPlus 모델 candidate score 계산
  -> rule score와 model score 결합
  -> confidence cap 적용
  -> candidates 반환
```

초기 결합 방식은 rule score를 우선합니다. 아래 값은 구현 확정값이 아니라 사전 검토용 기본 후보이며, validate 점수에 맞춘 condition별 예외나 특수 가중치로 바꾸지 않습니다.

```text
final_score = rule_score * 0.85 + model_score * 0.15
```

모델이 없거나 로드에 실패하면 기존 rule-based candidate 응답으로 fallback합니다. 모델 결과는 후보 순위 보조 신호이며, 단독으로 `high` confidence를 만들 수 없습니다.

로컬 산출물 후보:

| 파일 | 용도 |
| --- | --- |
| `model.joblib` | candidate ranking 보강 모델 |
| `vectorizer.joblib` | 내부 symptom/context feature 변환기 |
| `label_encoder.joblib` | 내부 `condition_code` label encoder |
| `metrics.json` | validate/test 성능 지표 |
| `model_card.md` | 학습 데이터, split, 사용 제한, fallback 정책 기록 |

모델 산출물은 generated artifact로 취급하며, 사용자 승인 없이 Git에 넣지 않습니다.

평가 기준:

- top-1 accuracy
- top-3 accuracy
- top-5 accuracy
- macro F1
- condition별 성능 편차
- sex/age bucket별 성능 편차
- confidence calibration

서비스 반영 조건:

- test split을 학습이나 파라미터 조정에 쓰지 않았을 것
- 기존 manual seed보다 candidate ranking이 나빠지지 않을 것
- `manual_seed` 또는 검수되지 않은 DDXPlus 매핑만으로 `high` confidence를 만들지 않을 것
- red flag rule 생성이나 red flag severity 산정에 모델 출력을 쓰지 않을 것

### 4차 상용 엔진 검토

- Infermedica 같은 API는 실제 서비스화, 개인정보 처리, 비용, SLA가 논의될 때 검토합니다.
- MVP 백엔드는 상용 API 없이도 동작해야 합니다.

## DDXPlus 현재 반영 상태

현재 로컬 DDXPlus 원본은 `health-navigator-backend/app/data/raw/`에 두고 처리합니다.

생성된 중간 산출물은 다음과 같습니다.

| 파일 | 용도 |
| --- | --- |
| `app/data/review/ddxplus_condition_mapping_review.csv` | DDXPlus 질환명과 내부 `condition_code` 매핑 검토표 |
| `app/data/review/ddxplus_evidence_mapping_review.csv` | DDXPlus evidence와 내부 symptom/context 코드 매핑 검토표 |
| `app/data/processed/ddxplus_evidence_review_triage.json` | DDXPlus evidence를 검토 트랙별로 나눈 우선순위 목록 |
| `app/data/processed/ddxplus_dataset_summary.json` | 원본 split, 질환 수, evidence 수, 매핑 후보 집계 |
| `app/data/processed/ddxplus_mapping_protocol.json` | 목표, split 사용 정책, 매핑 승인/거절 기준, 과적합 방지 원칙 |
| `app/data/processed/ddxplus_approved_condition_mappings.json` | 명확한 alias 근거가 있는 condition 매핑 초안 |
| `app/data/processed/ddxplus_rejected_condition_mappings.json` | loose alias라서 protocol 기준으로 승인하지 않은 condition 매핑 초안 |
| `app/data/processed/ddxplus_needs_review_condition_mappings.json` | direct alias가 없어 사람이 검토해야 하는 condition 목록 |
| `app/data/processed/ddxplus_condition_review_triage.json` | needs review condition을 검토 트랙별로 나눈 우선순위 목록 |
| `app/data/processed/ddxplus_frequency_baseline.json` | approved condition 매핑만 사용한 train split 빈도 baseline |

현재 approved draft condition 매핑은 DDXPlus 질환명/ICD metadata가 내부 후보 범주와 직접 대응되는 6개만 포함합니다. `loose_alias`와 evidence keyword guess는 사람이 검토하기 전까지 approved 산출물에 넣지 않습니다.

현재 condition 매핑 상태:

- approved draft: 6개
- rejected draft: 4개
- needs review: 39개

현재 needs review triage:

- red flag policy review: 17개
- candidate scope review: 15개
- scope review: 7개

이 triage는 승인/거절 결정이 아닙니다. 성능을 보고 고른 것도 아니며, 사람이 protocol 기준으로 검토할 순서를 정하기 위한 보조 산출물입니다.

현재 evidence triage:

- value-coded evidence review: 15개
- antecedent context review: 112개
- context review: 14개
- current symptom review: 32개
- unmapped evidence review: 50개

evidence triage도 승인 결정이 아닙니다. keyword guess는 모두 `needs_review` 상태로 유지하며, value-coded evidence는 값 의미를 검토하기 전까지 approved mapping으로 올리지 않습니다.

명백한 false positive로 확인한 evidence keyword guess는 서비스 반영 대신 `unmapped_evidence_review`로 되돌립니다.

| evidence | 이전 오매핑 | 현재 상태 |
| --- | --- | --- |
| `E_194` high pitched sound when breathing in | `itching` | `unmapped_evidence_review` |
| `E_169` nose/back of throat itchy | `radiating_left_arm_or_jaw_or_back` | `unmapped_evidence_review` |

서비스 반영 범위:

- `dataset_support`는 후보 응답에 보조 metadata로만 노출합니다.
- DDXPlus baseline은 candidate ranking tie-break 보조에만 사용합니다.
- DDXPlus는 red flag 생성, red flag severity, 응급 안내 문구에 사용하지 않습니다.
- DDXPlus baseline만으로 candidate confidence를 `high`로 올리지 않습니다.
- baseline 파일이 없거나 깨져 있으면 기존 rule-only 후보 응답으로 fallback합니다.

DDXPlus frequency baseline 평가:

| split | evaluated rows | coverage | candidate set recall@5 | mean expected rank | MRR |
| --- | ---: | ---: | ---: | ---: | ---: |
| validate | 32,024 | 24.18% | 100.00% | 1.29 | 91.85% |

주의:

- 이 평가는 approved draft condition 6개에 한정됩니다.
- 전체 DDXPlus 49개 질환 기준 성능이 아닙니다.
- 현재 평가의 1차 목표는 단일 정답 top-1이 아니라 안전하고 설명 가능한 후보군 품질입니다.
- 평가 스크립트 기본값은 validate split만 사용합니다.
- test split은 `--include-test`를 명시했을 때만 평가하며, 최종 보고용으로만 사용합니다.
- condition별 성능만 보고 특정 condition을 제외하거나 포함하지 않습니다.
- `otitis_media`는 현재 평균 정답 순위가 3.55이므로 `needs_mapping_review`로 기록하지만, 이 지표만으로 임의 제외하지 않습니다.
- 현재 baseline은 모든 approved draft condition에 동일하게 후보 순위 tie-break와 `dataset_support` metadata로만 사용합니다.
- condition별 예외 처리는 validate 성능을 보고 사후 결정하지 않고, 사전에 문서화된 매핑/근거 기준이 있을 때만 검토합니다.

목표와 과적합 방지 원칙:

- 목표는 단일 진단 top-1 최적화가 아니라 안전하고 설명 가능한 참고 후보군 제공입니다.
- red flag는 DDXPlus가 아니라 검토된 rule engine이 담당합니다.
- train은 baseline/모델 생성, validate는 오류 분석과 기준 검토, test는 최종 보고에만 사용합니다.
- validate/test 결과에 맞춰 특정 condition을 입맛대로 빼거나 넣지 않습니다.
- 증상, 컨텍스트, 후보, red flag 구조를 DDXPlus 점수에 맞춰 바꾸지 않습니다.
- 파라미터 조정은 사전에 정의한 전역 파라미터에 한해 임상/UX 근거가 있을 때만 허용합니다.
- train/validate/test 성능을 이유로 특정 질환별 예외, 특수 가중치, 후보 제외를 만들지 않습니다.
- 낮은 condition 성능은 제외 근거가 아니라 매핑/evidence 검토 필요 신호로만 사용합니다.
- 매핑 확장과 모델 반영은 `ddxplus_mapping_protocol.json`의 사전 기준을 따릅니다.

## DDXPlus 모델 학습 의미 정리

현재 구현한 것은 모델 학습이 아니라 frequency baseline입니다.

현재 baseline:

- train split에서 approved condition별 evidence 빈도를 집계합니다.
- 학습 파라미터가 없습니다.
- 최적화 과정이 없습니다.
- evidence 조합을 일반화하기보다, 자주 같이 나온 evidence를 점수화합니다.
- 서비스에서는 `dataset_support`와 후보 순위 tie-break 보조로만 씁니다.

나중에 말하는 모델 학습은 다릅니다.

모델 학습:

- train split으로 실제 분류 모델의 파라미터를 학습합니다.
- 입력 feature는 DDXPlus evidence, initial evidence, age bucket, sex, 내부 symptom/context 매핑 등을 사용합니다.
- 출력은 하나의 진단 확정이 아니라 내부 `condition_code`별 score/probability입니다.
- 모델 score는 candidate ranking 보강에만 쓰고, red flag나 처방/진단 표현에는 쓰지 않습니다.

첫 모델 후보는 Logistic Regression multiclass classifier입니다.

여기서 Logistic Regression은 이항분류만 뜻하지 않습니다. 사용할 방식은 다음 중 하나입니다.

- One-vs-Rest Logistic Regression: condition마다 yes/no 이항분류기를 하나씩 둡니다.
- Multinomial/Softmax Logistic Regression: 여러 condition class를 한 번에 분류합니다.

이 프로젝트에서 우선 검토할 방식은 `multinomial logistic regression`, 즉 softmax 기반 다중분류입니다. 이름은 Logistic Regression이지만 출력은 여러 condition 후보의 확률/점수입니다.

모델 학습 전제:

- approved condition mapping이 충분해야 합니다.
- approved evidence mapping이 충분해야 합니다.
- train/validate/test split 정책이 지켜져야 합니다.
- validate 성능을 보고 condition을 입맛대로 넣거나 빼지 않아야 합니다.
- test split은 최종 보고 전까지 사용하지 않아야 합니다.

서비스 연결 방식:

```text
사용자 입력
  -> 내부 symptom/context 코드 검증
  -> rule-based candidate 생성
  -> DDXPlus model score 계산
  -> rule score 우선 + model score 보조
  -> confidence cap 적용
  -> candidates 반환
```

모델 금지 역할:

- red flag 생성
- red flag severity 산정
- 응급 안내 문구 생성
- 진단 확정
- 처방 권고
- 단독 high confidence 승격

## 의료 NLP/BERT 검토 원칙

의료 BERT 계열 모델은 사용자의 자연어 입력을 더 잘 이해하기 위한 후보이지, 서비스 판단 기준을 대체하는 모델이 아닙니다.

이 프로젝트에서 허용하는 역할:

- 한국어 자유 입력에서 증상, 신체 부위, 기간, 강도, 약물, 검사명 후보 추출
- 사용자 표현을 내부 `symptom_code`/`context_code` alias 후보로 정규화
- LLM 호출 전후의 lightweight NER/normalization 보조

금지 역할:

- 질환 후보 직접 생성
- red flag 생성
- red flag severity 산정
- candidate confidence 생성 또는 상승
- 치료, 복용, 처방 지시 생성

우선 검토 순서:

1. alias dictionary와 rule-based normalization
2. 한국어 의료 BERT/NER 후보
3. OpenAI LLM structured output 기반 자유 입력 구조화
4. BioBERT/PubMedBERT/ClinicalBERT 계열의 영어 biomedical/clinical 비교 검토

의료 BERT 후보를 붙이더라도 출력은 항상 후보입니다. 내부 whitelist에 없는 code는 버리고, review-only context와 active context를 분리한 뒤, rule engine이 최종 판단합니다.

참고 근거:

- BioBERT 논문: https://pmc.ncbi.nlm.nih.gov/articles/PMC7703786/
- 한국어 의료 BERT 논문: https://pubmed.ncbi.nlm.nih.gov/35974113/
