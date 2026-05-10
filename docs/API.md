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
| POST | `/symptom-checker/assess` | 선택한 부위, 증상, 강도, 컨텍스트 기반 질환 후보 조회 |
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

이 기능은 1차 API 골격이 구현된 상태입니다. 응답은 진단이나 처방이 아니라 `가능성 있는 질환 후보`와 `참고 정보`로 표현합니다.

endpoint는 다음과 같습니다.

| Method | Endpoint | 설명 |
| --- | --- | --- |
| GET | `/symptom-checker/body-regions` | 인체 UI의 큰 부위 목록 조회 |
| GET | `/symptom-checker/contexts` | 증상 평가에 사용할 컨텍스트 선택지 조회 |
| GET | `/symptom-checker/body-regions/{region_id}/symptoms` | 특정 큰 부위의 세부 부위와 증상 선택지 조회 |
| POST | `/symptom-checker/assess` | 선택한 부위, 증상, 강도, 컨텍스트 기반 질환 후보 조회 |

평가 요청 예시는 다음과 같습니다.

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

응답 예시는 다음과 같습니다.

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
