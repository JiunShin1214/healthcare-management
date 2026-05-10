# Symptom Checker Design

이 문서는 인체 기반 UI에서 선택한 부위, 증상, 강도, 생활 컨텍스트를 바탕으로 `가능성 있는 질환 후보`와 `참고 정보`를 반환하는 백엔드 기능 초안을 정리합니다.

이 기능은 의료 진단이나 처방을 제공하지 않습니다. 응답 문구는 항상 참고용 정보로 제한하고, 위험 신호가 감지되면 질환 후보보다 의료기관 방문 안내를 우선합니다.

## 1차 목표

- Flutter가 인체 UI에서 큰 부위와 세부 부위 또는 증상을 선택할 수 있도록 백엔드 기준 코드를 제공한다.
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
- 생활 컨텍스트와 양상: 1차 MVP에서는 `alcohol_yesterday`, `sleep_deprivation`, `overeating`, `recent_exercise`, `stress`, `sudden_onset`, `worsening`, `after_injury`를 사용한다.

자연어 입력은 2차 확장으로 둡니다. 자연어를 받더라도 LLM은 진단자가 아니라 입력 구조화 보조 역할로 제한합니다.

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

1차 MVP 컨텍스트는 다음 8개로 둡니다.

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

### 질환 후보 평가

```http
POST /symptom-checker/assess
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
    "alcohol_yesterday": true,
    "sleep_deprivation": true,
    "overeating": false,
    "stress": true
  }
}
```

응답 예시:

```json
{
  "disclaimer": "이 결과는 진단이 아닌 참고용 정보입니다.",
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
  ]
}
```

## 백엔드 구조 후보

기존 프로젝트 구조를 따릅니다.

- `app/routers/symptom_checker.py`: endpoint 정의
- `app/schemas/symptom_checker.py`: 요청/응답 Pydantic 스키마
- `app/services/symptom_checker_service.py`: 위험 신호 감지, 후보 점수 계산, 응답 구성
- `app/models/symptom_checker.py`: DB 전환 시 사용할 SQLAlchemy 모델

1차 구현은 API 계약과 서비스 책임을 먼저 고정하고, DB 테이블 없이 서비스 내부의 구조화된 seed 데이터로 시작합니다. 실제 데이터는 데이터셋이 확정되면 DB 테이블 또는 import 데이터로 옮길 수 있게 유지합니다.

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

## DB 모델 후보

- `body_regions`: 큰 부위 코드, 이름, 정렬 순서, 활성 여부
- `body_parts`: 세부 부위 코드, 큰 부위 FK, 이름, 정렬 순서
- `symptoms`: 증상 코드, 이름, 강도/기간 입력 지원 여부
- `conditions`: 질환 후보 코드, 이름, 설명, 참고 출처
- `condition_rules`: 부위, 세부 부위, 증상, 컨텍스트 조합과 질환 후보의 가중치
- `red_flag_rules`: 즉시 진료 권고가 필요한 위험 신호 규칙

## 위험 신호 우선순위

아래 항목은 질환 후보 점수보다 우선해서 별도 경고로 반환합니다.

- 흉통과 호흡곤란
- 의식 저하 또는 혼란
- 갑작스러운 극심한 두통
- 편측 마비, 말 어눌함, 시야 이상
- 심한 복통과 지속 구토
- 고열과 목 경직
- 외상 후 심한 통증 또는 감각 이상

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

## 구현 전 결정할 것

- 큰 부위 범주는 1차에서 12개로 고정한다.
- 세부 부위 선택을 필수로 할지 선택으로 둘지.
- 증상은 단일 선택인지 복수 선택인지.
- 생활 컨텍스트는 1차 MVP에 포함하되, 질환 후보를 단독 생성하지 않고 증상 후보 점수 보강과 위험 신호 판단에만 사용한다.
- DB 테이블은 1차 구현에서 만들지 않고, 구조화된 seed 기반 API 골격을 먼저 사용한다.
- 질환 후보 점수는 `low`, `medium`, `high` 같은 등급으로 줄지, 숫자 점수도 함께 줄지.
