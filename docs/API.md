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
| GET | `/drugs` | 의약품 목록 조회 |
| GET | `/drugs/search` | 의약품 검색 |
| GET | `/drugs/{item_seq}` | 의약품 상세 조회 |
| POST | `/drugs/check-interaction` | 직접 선택한 약물 간 병용금기 검사 |
| POST | `/drugs/check-duplicate` | 직접 선택한 약물 간 중복 복용 검사 |
| GET | `/drugs/my-medications` | 내 복용약 목록 조회 |
| POST | `/drugs/my-medications` | 내 복용약 등록 |
| DELETE | `/drugs/my-medications/{medication_id}` | 내 복용약 삭제 |
| POST | `/drugs/my-medications/check-interaction` | 내 복용약 기준 병용금기 검사 |
| POST | `/drugs/my-medications/check-duplicate` | 내 복용약 기준 중복 복용 검사 |

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
