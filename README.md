# Lab Memory

연구실 PPT와 논문 PDF를 자연어로 검색하는 도구.

"3년 전 발표에서 ALE 실험 조건이 뭐였지?" — 수백 개 파일을 직접 열어보지 않고 답을 찾을 수 있다.

## 설치

```bash
git clone https://github.com/gyuminlee-repo/lab-memory.git
cd lab-memory
pip install -e .
```

> **pip 에러가 나면?**
> - `pip: command not found` → `sudo apt install -y python3-pip` 먼저 실행
> - `externally-managed-environment` → `pipx install -e .` 사용 (Ubuntu 24.04+)
> - Conda 사용자 → `conda activate base` 후 `pip install -e .`

설치가 끝나면 `lab-memory` 명령어를 바로 쓸 수 있다.

## 빠른 시작 (5분)

### 1. 워크스페이스 만들기

```bash
lab-memory init ~/my-lab
```

자동 생성되는 폴더 구조:

```
~/my-lab/
├── configs/settings.yaml    ← 설정 파일
└── data/
    ├── raw/                 ← 여기에 PPT/PDF를 넣는다
    ├── extracted/           ← (자동 생성)
    └── chroma_db/           ← (자동 생성)
```

### 2. PPT/PDF 넣기

`data/raw/`에 파일을 넣는다. 두 가지 방법이 있다:

```bash
# 심볼릭 링크 (원본을 복사하지 않아 디스크 절약, 권장)
ln -s /path/to/weekly-reports ~/my-lab/data/raw/weekly

# 또는 직접 복사
cp -r /path/to/files ~/my-lab/data/raw/
```

하위 폴더를 어떻게 구성하든 상관없다. 모든 `.pptx`/`.pdf` 파일을 재귀적으로 찾는다.

### 3. 인덱싱

```bash
lab-memory --home ~/my-lab ingest ~/my-lab/data/raw/
```

첫 실행 시 임베딩 모델(~1.3GB)이 자동 다운로드된다. 400개 PPT 기준 약 10~15분 소요.

### 4. 검색

```bash
lab-memory --home ~/my-lab search "ALE 실험 조건"
```

출력 예시:

```
### [1] 2024-03-15 - weekly_0315.pptx (slide 5) (score: 0.82)
# ALE Experiment Setup
Flask volume: 100mL, Temperature: 37°C, ...

---

### [2] 2023-11-20 - weekly_1120.pptx (slide 3) (score: 0.76)
...
```

## 파일을 추가했을 때

심볼릭 링크를 걸어두면 원본 폴더에 새 파일이 추가될 때 자동으로 보인다. 하지만 **검색에 반영하려면 `ingest`를 다시 실행**해야 한다. 이미 처리된 파일은 건너뛰고 새 파일만 인덱싱한다.

```bash
lab-memory --home ~/my-lab ingest ~/my-lab/data/raw/
```

## 검색 옵션

```bash
# 상위 5개만
lab-memory --home ~/my-lab search "tolerance" --top-k 5

# 날짜 범위
lab-memory --home ~/my-lab search "growth rate" --date-from 2023-01-01 --date-to 2024-06-30

# PPT만
lab-memory --home ~/my-lab search "protocol" --type pptx

# Claude API로 답변 합성 (ANTHROPIC_API_KEY 필요)
lab-memory --home ~/my-lab search "적응 진화 프로토콜" --synthesize
```

## 멀티 워크스페이스

주제별로 독립된 검색 공간을 만들 수 있다. MCP 서버 하나로 여러 워크스페이스를 관리하므로, 임베딩 모델(~1.3GB)을 중복 로드하지 않는다.

### 워크스페이스 추가하기

```bash
# 1. 등록 (폴더가 없으면 자동 생성)
lab-memory workspace add metabolic ~/metabolic-eng

# 2. 데이터 넣기
ln -s /path/to/metabolic-papers ~/metabolic-eng/data/raw/papers

# 3. 인덱싱
lab-memory --home ~/metabolic-eng ingest ~/metabolic-eng/data/raw/

# 4. 검색
lab-memory --home ~/metabolic-eng search "flux balance analysis"
```

### 관리 명령어

```bash
lab-memory workspace list              # 목록 보기
lab-memory workspace add synbio ~/dir  # 추가
lab-memory workspace remove synbio     # 제거 (파일은 삭제 안 함)
```

### `--home`을 매번 쓰기 귀찮다면

환경변수로 기본 워크스페이스를 지정할 수 있다:

```bash
export LAB_MEMORY_HOME=~/metabolic-eng
lab-memory search "query"    # --home 없이 사용
```

## Claude Code 연동 (MCP)

[Claude Code](https://docs.anthropic.com/en/docs/claude-code)에 연결하면, 대화 중에 "지난 실험에서 ALE 조건이 뭐였어?"라고 물으면 자동으로 검색해준다. API 키 없이 Claude 구독만으로 동작한다.

### 설정

프로젝트 루트에 `.mcp.json` 파일을 만든다:

```json
{
  "mcpServers": {
    "lab-memory": {
      "command": "lab-memory",
      "args": ["serve"],
      "env": {
        "LAB_MEMORY_HOME": "/home/user/my-lab"
      }
    }
  }
}
```

> `LAB_MEMORY_HOME`은 반드시 **절대 경로**로 지정한다. `~`는 사용할 수 없다.

### MCP 도구 목록

| 도구 | 설명 |
|------|------|
| `search_lab_notes` | 키워드/의미 검색 (한국어·영어). `workspace`로 워크스페이스 지정 가능 |
| `get_slide` | 특정 슬라이드 원문 조회 |
| `summarize_topic` | 주제 관련 소스를 넓게 수집 |
| `list_reports` | 인덱싱된 레포트 목록 (날짜 필터 가능) |
| `get_report_summary` | 레포트의 슬라이드 구성 확인 |
| `list_workspaces` | 등록된 워크스페이스 목록과 청크 수 |

멀티 워크스페이스를 사용할 때는 `workspace` 파라미터로 전환한다:

```
search_lab_notes(query="ALE 실험", workspace="metabolic")
list_workspaces()
```

생략하면 `"default"` 워크스페이스를 사용한다.

## 설정 커스터마이징

`configs/settings.yaml`에서 조정할 수 있다:

```yaml
embedding:
  model_name: "intfloat/multilingual-e5-large"  # 임베딩 모델
  batch_size: 64                                 # 메모리 부족 시 줄이기

chunking:
  min_chunk_length: 100   # 짧은 슬라이드는 다음과 병합
  max_chunk_tokens: 512   # PDF 청크 최대 토큰
  overlap_tokens: 50      # 청크 간 겹침

search:
  default_top_k: 10       # 기본 검색 결과 수
  score_threshold: 0.3    # 낮출수록 더 많은 결과 (0~1)
```

## 트러블슈팅

| 문제 | 해결 |
|------|------|
| 모델 다운로드 실패 | 프록시 환경이면 `HF_HUB_DISABLE_SSL_VERIFY=1` 설정 |
| 검색 결과가 너무 적다 | `score_threshold`를 낮춘다 (0.3 → 0.1) |
| 메모리 부족 | `batch_size`를 줄인다 (64 → 16) |
| 새 파일이 검색에 안 나온다 | `ingest`를 다시 실행한다 |
| `lab-memory: command not found` | `pip install -e .`를 다시 실행하거나, conda 환경이면 `conda activate base` 먼저 |

## 기술 스택

| 컴포넌트 | 라이브러리 |
|----------|-----------|
| PPT 파싱 | python-pptx 1.0.2 |
| PDF 파싱 | PyMuPDF 1.25.3 |
| 임베딩 | sentence-transformers 3.4.1 + multilingual-e5-large |
| 벡터 DB | chromadb 0.6.3 |
| MCP | mcp[cli] 1.8.0 |
| LLM 합성 | anthropic 0.49.0 (`--synthesize` 전용, 선택사항) |
| CLI | click 8.1.8 |
