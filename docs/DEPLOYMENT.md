# Deployment

이 문서는 Health Navigator-Management 백엔드의 서버 운영 환경을 정리합니다.

## 현재 운영 환경

현재 프로젝트는 AWS EC2 인스턴스를 생성하고, 탄력적 IP를 연결하여 서버 IP가 고정되도록 구성했습니다.

로컬에서는 MobaXterm을 사용해 Ubuntu 서버에 SSH private key 방식으로 접속하도록 설정했습니다.

## 구성 범위

- AWS EC2 인스턴스 생성
- Elastic IP를 통한 고정 IP 구성
- Ubuntu 서버 접속 환경 구성
- SSH private key 기반 인증
- MobaXterm을 통한 원격 접속
- systemd 서비스 등록을 통한 서버 프로세스 관리
- 테스트 시점에만 인스턴스 실행
- 사용하지 않을 때는 비용 관리를 위해 인스턴스 중지

## systemd 기반 실행

systemd 기반 실행 설정을 적용하여 터미널 연결이 끊겨도 서버 프로세스가 유지되고, 인스턴스가 실행된 상태에서는 백엔드 서버가 서비스로 관리되도록 구성했습니다.

즉, MobaXterm 연결을 종료하더라도 인스턴스가 실행 중이면 서버 프로세스가 systemd 서비스로 관리되는 구조입니다.

서버 실행은 `health-navigator-backend` 디렉터리를 기준으로 수행합니다.

## 인스턴스 사양

현재 인스턴스 타입은 `t3.medium` 수준으로 사용 중입니다.

향후 OCR 결과 저장, 건강검진 이력 관리, ML/XAI 분석, LLM 기반 증상 입력 보조 등 기능이 추가되면 처리량과 메모리 사용량이 증가할 수 있으므로 상위 사양으로 조정할 가능성이 있습니다.

## ML/BERT 모델 운영 원칙

KM-BERT 같은 로컬 모델을 붙일 경우에도 로컬 PC와 AWS EC2에서 같은 절차로 재현 가능해야 합니다.

- 모델 weight는 Git 저장소에 커밋하지 않습니다.
- 모델 다운로드/cache 위치는 실제 연결 전 별도 승인 후 정합니다. 현재 후보는 로컬 `C:/tmp/health-navigator-models/kmbert`, AWS EC2 `/opt/health-navigator/models/kmbert`입니다.
- cache 위치는 저장소 밖 경로 또는 명시적으로 Git 추적에서 제외된 경로를 사용합니다.
- AWS에서는 MobaXterm으로 접속한 뒤 서버 내부 경로에 모델을 준비하되, private key, `.env`, credential 파일은 Codex가 읽거나 수정하지 않습니다.
- `torch`, `transformers` 같은 무거운 의존성은 실제 KM-BERT 연결 승인 전 `requirements.txt`에 추가하지 않습니다. 실제 연결 단계에서는 별도 ML requirements 파일보다 기본 `requirements.txt`에 추가해 AWS에서 `git pull` 후 같은 설치 절차를 쓰는 방향을 우선합니다.
- Git으로 받는 것은 adapter 코드, 설정, 설치 목록입니다. 모델 weight는 용량과 라이선스/재배포 이슈 때문에 Git에 넣지 않고, 서버에서 한 번 내려받거나 지정 cache 경로에 배치합니다.
- 모델 출처는 공식 KU-RIAS artifact를 우선합니다. Hugging Face 변환본은 편의 reference로만 보고, 기본 배포 의존성으로 삼지 않습니다.
- EC2 CPU/RAM 기준 추론 시간이 `/symptom-checker/structure` 시연 흐름에 충분한지 확인한 뒤 사용자-facing 흐름에 연결합니다.
- provider가 꺼져 있거나 모델 파일이 없거나 timeout이 발생하면 기존 선택형 입력과 rule-based `/assess` 흐름으로 fallback합니다.

현재 상태에서는 KM-BERT 실제 연결을 구현하지 않았고, 모델도 다운로드하지 않습니다. 사전 결정은 `docs/SYMPTOM_CHECKER_DATASETS.md`의 `KM-BERT pre-connection policy`를 기준으로 하며, 실제 연결 시점에 모델 파일 배치, 의존성 설치, runtime 측정을 진행합니다.

## 비용 및 운영 조건

현재는 캡스톤 프로젝트 조직 환경에서 AWS 리소스를 사용하고 있습니다. 프로젝트 종료 이후에는 운영 비용과 계정 환경에 따라 배포 방식 또는 지속 운영 여부를 재검토해야 합니다.

## 추가 정리 필요 항목

- systemd 서비스 파일 문서화
- 서버 실행 명령 문서화
- 환경 변수 분리
- 운영 환경과 개발 환경 설정 분리
- 배포 절차 문서화
- 인스턴스 재시작 후 서버 상태 확인 절차 정리
- KM-BERT 실제 연결 시 EC2 모델 cache 경로와 의존성 설치 절차 문서화
