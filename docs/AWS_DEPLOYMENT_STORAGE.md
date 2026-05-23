# AWS Deployment Storage Plan

이 문서는 Health Navigator-Management를 AWS에 올릴 때 운영 API, EC2 배포 파일, RDS/S3/EBS 적재 대상을 분리하기 위한 기준이다.

## 1. 운영 API 선별

### Public production API

운영 서비스에서 기본 노출할 API다.

| Domain | Method | Path | Purpose |
| --- | --- | --- | --- |
| Auth | POST | `/auth/signup` | 회원가입 |
| Auth | POST | `/auth/login` | 로그인/JWT 발급 |
| Auth | GET | `/auth/me` | 현재 사용자 조회 |
| Health check | POST | `/health-check/ocr` | 건강검진표 OCR/파싱 |
| Health check | POST | `/health-check/results` | 건강검진 결과 저장 |
| Health check | PATCH | `/health-check/results/{result_id}` | 건강검진 결과 수정/재판정 |
| Drugs | GET | `/drugs/search` | 의약품 검색 |
| Drugs | GET | `/drugs/autocomplete` | 의약품 자동완성 |
| Drugs | GET | `/drugs/{item_seq}` | 의약품 상세 조회 |
| Drugs | POST | `/drugs/check-interaction` | 직접 병용금기 검사 |
| Drugs | POST | `/drugs/check-duplicate` | 직접 중복복용 검사 |
| Drugs | GET | `/drugs/my-medications` | 내 복용약 조회 |
| Drugs | POST | `/drugs/my-medications` | 내 복용약 추가 |
| Drugs | DELETE | `/drugs/my-medications/{medication_id}` | 내 복용약 삭제 |
| Drugs | POST | `/drugs/my-medications/check-interaction` | 내 복용약 기준 병용금기 검사 |
| Drugs | POST | `/drugs/my-medications/check-duplicate` | 내 복용약 기준 중복복용 검사 |
| Symptom checker | GET | `/symptom-checker/anatomy-areas` | 인체 UI 선택 트리 |
| Symptom checker | GET | `/symptom-checker/body-regions/{region_id}/symptoms` | 부위별 증상 선택지 |
| Symptom checker | GET | `/symptom-checker/body-regions/{region_id}/context-guide` | 부위별 문맥/질문 선택지 |
| Symptom checker | POST | `/symptom-checker/assess` | 증상 기반 후보 생성 |
| Symptom checker | POST | `/symptom-checker/assess/me` | 로그인 사용자 기준 후보 생성 |
| Gemini | POST | `/api/gemini/explain-symptoms` | 백엔드 candidates JSON 기반 사용자 설명문 생성 |

### Internal or development-only API

아래 API는 운영 public surface에서 제외한다. 필요하면 `ENABLE_DEV_ENDPOINTS=true` 같은 feature flag 또는 내부 보안 그룹/VPN 뒤에서만 노출한다.

| Method | Path | Reason |
| --- | --- | --- |
| GET | `/symptom-checker/body-regions` | UI는 `/anatomy-areas` 중심으로 충분함 |
| GET | `/symptom-checker/contexts` | 디버그/개발용 전체 context 조회 |
| POST | `/symptom-checker/structure` | 구조화 실험용 |
| POST | `/symptom-checker/structure/medical-bert` | 로컬 BERT 실험용, 운영 미사용 |
| POST | `/symptom-checker/assessment-draft` | draft 변환 실험용 |
| POST | `/symptom-checker/assessment-draft/medical-bert` | 로컬 BERT 실험용, 운영 미사용 |
| POST | `/symptom-checker/explain` | 기존 RAG 카드 설명 실험/검수용 |
| POST | `/symptom-checker/explain/gemini` | 이전 설명 생성 경로, 새 `/api/gemini/explain-symptoms`로 대체 |
| GET | `/demo/symptom-checker-flow` | 로컬 데모 HTML, 운영 서버 노출 금지 |
| GET | `/docs`, `/redoc`, `/openapi.json` | 운영 public에서는 비활성화 또는 관리자 IP 제한 권장 |

## 2. AWS 적재 기준

### GitHub

GitHub에는 코드와 작은 runtime seed만 둔다.

Keep in Git:

```text
health-navigator-backend/app/
health-navigator-backend/requirements.txt
README.md
docs/
health-navigator-backend/app/data/symptom_checker_conditions.json
health-navigator-backend/app/data/explanation_cards/conditions.json
health-navigator-backend/app/data/explanation_cards/source_refs.json
health-navigator-backend/app/data/processed/ddxplus_frequency_baseline.json
```

Do not keep in Git:

```text
.env
health-navigator-backend/secrets/
*.parquet
*.pt
*.pth
*.safetensors
.model-cache/
health-navigator-backend/app/data/raw/
health-navigator-backend/app/data/processed/*
health-navigator-backend/app/data/review/
health-navigator-backend/tests/
health-navigator-backend/tools/
```

예외: `app/data/processed/ddxplus_frequency_baseline.json`은 runtime tie-break seed라 Git에 남긴다.

### EC2 + EBS

EC2/EBS는 애플리케이션 실행에 필요한 최소 파일만 둔다.

Keep on EC2:

```text
/opt/health-navigator/app/health-navigator-backend/app
/opt/health-navigator/app/health-navigator-backend/requirements.txt
/opt/health-navigator/app/health-navigator-backend/.venv
/etc/systemd/system/health-navigator.service
/etc/nginx/sites-available/health-navigator
/var/log/health-navigator/
```

Remove from EC2 if present:

```text
/opt/health-navigator/app/health-navigator-backend/tests
/opt/health-navigator/app/health-navigator-backend/tools
/opt/health-navigator/app/health-navigator-backend/app/data/raw
/opt/health-navigator/app/health-navigator-backend/app/data/review
/opt/health-navigator/app/health-navigator-backend/app/data/*.parquet
/opt/health-navigator/app/health-navigator-backend/app/data/processed/*
/opt/health-navigator/app/.model-cache
/opt/health-navigator/models/kmbert
*.pt
*.pth
*.safetensors
```

If a local model is reintroduced later, model weights go to S3 or a dedicated EBS path, not Git. The service must download/sync the selected version during deployment.

### RDS MySQL

RDS stores relational service data.

Store in RDS:

```text
users
health_check_results
user_medications
drug_items
drug_details
easy_drugs
dur_interactions
dur_duplicates
```

The parquet files are import sources only. They should be stored in S3 as archive/import input and loaded into RDS tables before production.

### S3

S3 stores large objects, raw data, backups, and model artifacts.

Recommended bucket layout:

```text
s3://health-navigator-prod-artifacts/
  raw/ddxplus/
    release_train_patients
    release_test_patients
    release_validate_patients
    release_evidences.json
  drug-source/
    permit_detail.parquet
    dur_taboo.parquet
    permit_list.parquet
    dur_prdlst.parquet
    easy_drug.parquet
    dur_duplicate.parquet
  model-artifacts/
    kmbert-structure/
    sentence-transformers/
  ocr-uploads/
    yyyy/mm/dd/
  backups/
    rds-export/
```

S3 lifecycle:

- `ocr-uploads/`: 30-90일 보관 후 Glacier 또는 삭제 정책 검토
- `raw/`, `drug-source/`: Standard 또는 Standard-IA
- `model-artifacts/`: Standard-IA, 버전 태그 필수
- `backups/`: AWS Backup/RDS snapshot 정책과 중복되지 않게 retention 정의

## 3. 현재 로컬 기준 큰 파일

운영 EC2/Git에서 제외할 대표 파일이다.

| File or directory | Size | Destination |
| --- | ---: | --- |
| `app/data/raw/release_train_patients` | ~640 MB | S3 `raw/ddxplus/` |
| `app/data/raw/release_test_patients` | ~84 MB | S3 `raw/ddxplus/` |
| `app/data/raw/release_validate_patients` | ~83 MB | S3 `raw/ddxplus/` |
| `app/data/permit_detail.parquet` | ~13 MB | S3 `drug-source/`, imported to RDS |
| `app/data/dur_taboo.parquet` | ~10.7 MB | S3 `drug-source/`, imported to RDS |
| `.model-cache/kmbert-structure/checkpoint-1/optimizer.pt` | ~753 MB | S3 `model-artifacts/` or delete if unused |
| `.model-cache/kmbert-structure/model.safetensors` | ~377 MB | S3 `model-artifacts/` or delete if unused |
| `.model-cache/experiments/kmbert-body-region/model.safetensors` | ~376 MB | S3 `model-artifacts/` or delete if unused |
| sentence-transformers cache | ~449 MB | S3/cache only if runtime needs it |

Current production direction uses rule-based candidates and Vertex AI Gemini explanations, so local BERT/model cache is not required on EC2.

## 4. EC2 audit commands

Run these on EC2 after SSH login. Do not print `.env` or credential contents.

```bash
pwd
hostname
df -h
free -h
systemctl status health-navigator --no-pager
systemctl cat health-navigator
ps aux | grep -E 'uvicorn|gunicorn|python' | grep -v grep
sudo du -h -d 2 /opt/health-navigator 2>/dev/null | sort -h | tail -50
sudo find /opt/health-navigator -type f \
  \( -name '*.parquet' -o -name '*.pt' -o -name '*.pth' -o -name '*.safetensors' -o -name '*.json' \) \
  -printf '%s %p\n' 2>/dev/null | sort -nr | head -80
sudo find /opt/health-navigator -type d \
  \( -name '.model-cache' -o -name 'raw' -o -name 'processed' -o -name 'review' -o -name 'tests' -o -name 'tools' -o -name 'secrets' \) \
  -print 2>/dev/null
curl -s http://127.0.0.1:8000/ || true
curl -s http://127.0.0.1:8000/openapi.json | python3 -m json.tool | grep -E '"/(auth|health-check|drugs|symptom-checker|api/gemini)'
```

If the app is under a different path, replace `/opt/health-navigator`.

## 5. Cleanup sequence

Do not delete files before S3/RDS migration is confirmed.

1. EC2 inventory
2. Snapshot or AMI backup
3. Upload raw/parquet/model artifacts to S3
4. Verify drug parquet data is imported into RDS
5. Remove EC2-only large artifacts
6. Disable development-only endpoints
7. Restart service
8. Verify production endpoints

## 6. Deployment checklist

```text
[ ] GitHub branch contains latest application code
[ ] EC2 pulls only production code
[ ] `.env` exists only on server, not Git
[ ] Google service account JSON is not in app repository path if possible
[ ] RDS connection uses environment variables
[ ] Drug tables loaded into RDS
[ ] Raw/parquet/model artifacts uploaded to S3
[ ] EC2 has no raw datasets, model checkpoints, or parquet source files
[ ] Public API exposes only production endpoints
[ ] `/docs` and `/demo/*` are disabled or access-limited in production
```
