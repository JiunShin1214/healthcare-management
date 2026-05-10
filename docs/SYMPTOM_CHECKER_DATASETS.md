# Symptom Checker Dataset Review

이 문서는 인체 UI 기반 증상 탐색 기능에 사용할 수 있는 데이터셋과 외부 API 후보를 정리합니다.

검토 기준일은 2026-05-10입니다. 라이선스와 API 정책은 바뀔 수 있으므로 실제 도입 전 다시 확인해야 합니다.

## 결론

1차 MVP는 외부 데이터셋을 바로 적재하지 않고, 현재 백엔드의 rule-based seed를 확장합니다.

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

### 1차 MVP

- 현재 코드의 `required_symptoms`, `optional_symptoms`, `boosting_contexts` 구조를 유지합니다.
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

### 4차 상용 엔진 검토

- Infermedica 같은 API는 실제 서비스화, 개인정보 처리, 비용, SLA가 논의될 때 검토합니다.
- MVP 백엔드는 상용 API 없이도 동작해야 합니다.
