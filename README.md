# Lab Memory

연구실 위클리 레포트(PPT)와 논문(PDF)을 로컬에서 검색할 수 있는 RAG(Retrieval-Augmented Generation) 시스템.

"3년 전 발표에서 ALE 실험 조건이 뭐였지?" 같은 질문에, 수백 개 파일을 직접 뒤지지 않고 자연어로 답을 찾을 수 있다.

## 어떻게 동작하는가

```
PPT/PDF 원본  →  텍스트 추출(JSON)  →  임베딩 + ChromaDB 저장  →  자연어 검색
```

1. **추출**: PPT 슬라이드와 PDF 페이지에서 텍스트, 표, 발표 노트를 JSON으로 변환
2. **인덱싱**: 다국어 임베딩 모델(`multilingual-e5-large`)로 벡터화하여 ChromaDB에 저장
3. **검색**: 한국어/영어 질의를 벡터 유사도로 매칭하여 관련 슬라이드/페이지 반환

## 요구사항

- **Python** >= 3.11
- **디스크** ~2GB (임베딩 모델이 첫 실행 시 자동 다운로드됨)
- **API 키**: 기본 사용에는 불필요. CLI의 `--synthesize` 옵션을 쓸 때만 `ANTHROPIC_API_KEY` 필요

## 설치

```bash
git clone https://github.com/gyuminlee-repo/lab-memory.git
cd lab-memory
pip install -e .
```

설치가 끝나면 `lab-memory` 명령어를 터미널에서 바로 쓸 수 있다.

## 빠른 시작

### 1단계: 워크스페이스 만들기

워크스페이스는 데이터와 설정을 담는 폴더다. 원하는 위치에 초기화한다.

```bash
lab-memory init ~/my-lab
```

아래 구조가 자동 생성된다:

```
~/my-lab/
├── configs/settings.yaml    # 검색/임베딩 설정
└── data/
    ├── raw/                 # ← 여기에 PPT/PDF를 넣는다
    ├── extracted/           # 추출된 JSON (자동 생성)
    └── chroma_db/           # 벡터 DB (자동 생성)
```

### 2단계: PPT/PDF 파일 넣기

`data/raw/`에 파일을 복사하거나 심볼릭 링크를 건다.

```bash
# 방법 1: 심볼릭 링크 (원본을 복사하지 않아 디스크 절약)
ln -s /path/to/weekly-reports ~/my-lab/data/raw/weekly
ln -s /path/to/papers ~/my-lab/data/raw/papers

# 방법 2: 직접 복사
cp -r /path/to/files ~/my-lab/data/raw/
```

하위 폴더 구조는 자유롭게 정리해도 된다. 재귀적으로 모든 `.pptx`/`.pdf` 파일을 찾는다.

### 3단계: 추출 + 인덱싱

```bash
lab-memory --home ~/my-lab ingest ~/my-lab/data/raw/
```

이 명령 하나로 추출과 인덱싱이 순차 실행된다. PPT 추출은 멀티프로세싱으로 병렬 처리되며, 임베딩 모델은 첫 실행 시 자동 다운로드(~1.3GB)된다.

> 파일이 많으면 시간이 걸릴 수 있다. 400개 PPT 기준 약 10~15분 소요.

### 4단계: 검색

```bash
lab-memory --home ~/my-lab search "ALE 실험 조건"
```

유사도 점수와 함께 관련 슬라이드/페이지가 출력된다.

```
### [1] 2024-03-15 - weekly_0315.pptx (slide 5) (score: 0.82)
# ALE Experiment Setup
Flask volume: 100mL, Temperature: 37°C, ...

---

### [2] 2023-11-20 - weekly_1120.pptx (slide 3) (score: 0.76)
...
```

## 검색 옵션

```bash
# 상위 5개만 반환
lab-memory --home ~/my-lab search "tolerance mechanism" --top-k 5

# 날짜 범위 필터
lab-memory --home ~/my-lab search "growth rate" --date-from 2023-01-01 --date-to 2024-06-30

# PPT만 검색
lab-memory --home ~/my-lab search "protocol" --type pptx

# Claude API로 답변 합성 (ANTHROPIC_API_KEY 환경변수 필요)
lab-memory --home ~/my-lab search "적응 진화 프로토콜 요약" --synthesize
```

`--synthesize`는 검색된 소스를 Claude API에 보내 자연어 답변을 생성한다. 이 기능만 API 키가 필요하며, 없으면 검색 결과가 그대로 출력된다.

## 기타 명령어

```bash
# 추출만 (인덱싱 없이)
lab-memory --home ~/my-lab extract ~/my-lab/data/raw/

# 인덱싱만 (이미 추출된 JSON이 있을 때)
lab-memory --home ~/my-lab index

# 인덱스 통계 확인
lab-memory --home ~/my-lab stats

# 특정 폴더 제외하고 추출
lab-memory --home ~/my-lab extract ~/my-lab/data/raw/ -x "backup" -x "old"
```

## 멀티 워크스페이스

단일 MCP 서버에서 여러 주제별 워크스페이스를 관리할 수 있다. 임베딩 모델(~1.3GB)을 한 번만 로드하므로 메모리 효율적이다.

### CLI로 워크스페이스 관리

```bash
# 워크스페이스 등록 (디렉토리 없으면 자동 init)
lab-memory workspace add metabolic ~/metabolic-eng
lab-memory workspace add synbio ~/synthetic-bio

# 등록된 워크스페이스 목록
lab-memory workspace list

# 워크스페이스 제거 (파일은 삭제하지 않음)
lab-memory workspace remove synbio
```

각 워크스페이스에 독립적으로 데이터를 인덱싱한다:

```bash
lab-memory --home ~/metabolic-eng ingest ~/metabolic-eng/data/raw/
lab-memory --home ~/synthetic-bio ingest ~/synthetic-bio/data/raw/
```

### MCP에서 워크스페이스 전환

MCP 도구에 `workspace` 파라미터를 전달하면 해당 워크스페이스에서 검색한다:

```
search_lab_notes(query="ALE 실험", workspace="metabolic")
search_lab_notes(query="genetic circuit", workspace="synbio")
list_workspaces()  # 등록된 모든 워크스페이스와 청크 수 확인
```

`workspace`를 생략하면 `"default"` 워크스페이스를 사용한다 (하위 호환).

### 워크스페이스 설정 파일

`configs/workspaces.yaml`에 이름→경로 매핑이 저장된다:

```yaml
workspaces:
  default: "/mnt/d/_workspace/lab-memory"
  metabolic: "/home/user/metabolic-eng"
  synbio: "/home/user/synthetic-bio"
```

### 기존 방식 (--home)

기존의 `--home` 플래그도 그대로 사용 가능하다:

```bash
lab-memory --home ~/metabolic-eng search "flux balance analysis"
```

매번 `--home`을 쓰기 번거로우면 환경변수로 지정할 수 있다:

```bash
export LAB_MEMORY_HOME=~/metabolic-eng
lab-memory search "query"    # --home 없이 사용 가능
```

우선순위: `--home` 플래그 > `LAB_MEMORY_HOME` 환경변수 > 패키지 설치 디렉토리

## Claude Code 연동 (MCP 서버)

[Claude Code](https://docs.anthropic.com/en/docs/claude-code)에서 lab-memory를 MCP 도구로 연결하면, 대화 중에 "지난 실험에서 ALE 조건이 뭐였어?"라고 물어보면 자동으로 검색해준다. **별도 API 키 없이** Claude 구독만으로 동작한다.

### 설정 방법

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

> `LAB_MEMORY_HOME`은 **절대 경로**로 지정해야 한다. `~`는 사용할 수 없다.

### 제공 도구

| 도구 | 설명 |
|------|------|
| `search_lab_notes` | 키워드/의미 기반 검색. 한국어·영어 모두 가능. `workspace` 파라미터로 워크스페이스 지정 |
| `get_slide` | 특정 슬라이드 원문 전체 조회 |
| `summarize_topic` | 주제 관련 소스를 넓게 수집. Claude Code가 종합 요약 |
| `list_reports` | 인덱싱된 레포트 목록 조회 (날짜 필터 가능) |
| `get_report_summary` | 개별 레포트의 슬라이드 구성 확인 |
| `list_workspaces` | 등록된 워크스페이스 목록과 청크 수 조회 |

### 수동 실행 (디버깅용)

```bash
LAB_MEMORY_HOME=~/my-lab lab-memory serve
```

## 설정 커스터마이징

워크스페이스의 `configs/settings.yaml`에서 동작을 조정할 수 있다:

```yaml
embedding:
  model_name: "intfloat/multilingual-e5-large"  # 임베딩 모델
  batch_size: 64                                 # GPU 메모리에 맞게 조정

chunking:
  min_chunk_length: 100   # 이보다 짧은 슬라이드는 다음 슬라이드와 병합
  max_chunk_tokens: 512   # PDF 청크 최대 토큰 수
  overlap_tokens: 50      # PDF 청크 간 겹침 토큰 수

search:
  default_top_k: 10       # 기본 검색 결과 수
  score_threshold: 0.3    # 이 점수 미만은 결과에서 제외 (0~1, 높을수록 엄격)
```

## 기술 스택

| 컴포넌트 | 라이브러리 |
|----------|-----------|
| PPT 파싱 | python-pptx 1.0.2 |
| PDF 파싱 | PyMuPDF 1.25.3 |
| 임베딩 | sentence-transformers 3.4.1 + multilingual-e5-large |
| 벡터 DB | chromadb 0.6.3 |
| MCP | mcp[cli] 1.8.0 |
| LLM 합성 | anthropic 0.49.0 (CLI `--synthesize` 전용, 선택사항) |
| CLI | click 8.1.8 |

## 트러블슈팅

**Q: `lab-memory ingest` 실행 시 모델 다운로드가 안 된다**
프록시 환경에서 SSL 인증서 문제가 발생할 수 있다. `HF_HUB_DISABLE_SSL_VERIFY=1` 환경변수를 설정하면 우회 가능하다.

**Q: 검색 결과가 너무 적다**
`configs/settings.yaml`에서 `score_threshold`를 낮춰본다 (기본 0.3 → 0.1).

**Q: 메모리 부족 에러가 발생한다**
`embedding.batch_size`를 줄인다 (64 → 16). 임베딩 모델이 ~1.3GB 메모리를 사용한다.

**Q: 파일을 추가했는데 검색에 안 나온다**
`ingest`를 다시 실행해야 한다. 새 파일만 추출되고 기존 인덱스에 추가된다.
