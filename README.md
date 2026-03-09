# Lab Memory

연구실 위클리 레포트(PPT)와 논문(PDF)에서 실험 기록과 연구 지식을 검색하는 로컬 RAG 시스템.

## 요구사항

- Python >= 3.11
- 디스크 ~2GB (임베딩 모델 `intfloat/multilingual-e5-large` 자동 다운로드)

## 설치

```bash
pip install -e .
```

## 빠른 시작

```bash
# 1. 워크스페이스 초기화
lab-memory init ~/my-lab

# 2. 원본 PPT/PDF 연결
ln -s /path/to/weekly-reports ~/my-lab/data/raw/weekly
ln -s /path/to/papers ~/my-lab/data/raw/papers

# 3. 추출 + 인덱싱 (한 번에)
lab-memory --home ~/my-lab ingest ~/my-lab/data/raw/

# 4. 검색
lab-memory --home ~/my-lab search "ALE 실험 조건"
```

## 복수 워크스페이스

프로젝트별로 독립된 RAG를 운영할 수 있다.

```bash
# 프로젝트 A
lab-memory init ~/lab-a
lab-memory --home ~/lab-a ingest ~/lab-a/data/raw/

# 프로젝트 B
lab-memory init ~/lab-b
lab-memory --home ~/lab-b ingest ~/lab-b/data/raw/

# 환경변수로도 지정 가능
export LAB_MEMORY_HOME=~/lab-a
lab-memory search "query"
```

`--home` 미지정 시 `LAB_MEMORY_HOME` 환경변수 → 패키지 설치 디렉토리 순으로 fallback한다.

## 사용법

### 추출

```bash
lab-memory --home ~/my-lab extract ~/my-lab/data/raw/

# 특정 경로 제외
lab-memory --home ~/my-lab extract ~/my-lab/data/raw/ -x "backup" -x "old"
```

### 인덱싱

```bash
lab-memory --home ~/my-lab index
```

### 검색

```bash
# 기본 검색
lab-memory --home ~/my-lab search "tolerance mechanism"

# 옵션
lab-memory --home ~/my-lab search "adaptive evolution" --top-k 5 --date-from 2023-01-01 --type pptx

# Claude API로 답변 합성 (ANTHROPIC_API_KEY 환경변수 필요, 선택사항)
lab-memory --home ~/my-lab search "ALE 프로토콜" --synthesize
```

### 통계

```bash
lab-memory --home ~/my-lab stats
```

### MCP 서버 (Claude Code 연동)

Claude Code에서 lab-memory를 MCP 도구로 사용할 수 있다. 별도 API 키 없이 Claude 구독만으로 동작한다.

프로젝트 `.mcp.json` 설정 예시:

```json
{
  "mcpServers": {
    "lab-memory": {
      "command": "lab-memory",
      "args": ["serve"],
      "env": {
        "LAB_MEMORY_HOME": "/absolute/path/to/workspace"
      }
    }
  }
}
```

제공 도구:
- `search_lab_notes` — 키워드/의미 기반 검색
- `get_slide` — 특정 슬라이드 원문 조회
- `summarize_topic` — 주제별 소스 수집 (Claude Code가 종합)
- `list_reports` — 레포트 목록 조회
- `get_report_summary` — 개별 레포트 슬라이드 구성 확인

수동 실행:
```bash
LAB_MEMORY_HOME=~/my-lab lab-memory serve
```

## 디렉토리 구조

```
my-lab/                             # --home으로 지정하는 워크스페이스
├── configs/settings.yaml           # 임베딩 모델, 청킹 파라미터, 검색 설정
└── data/
    ├── raw/                        # 원본 PPT/PDF (심볼릭 링크 권장)
    ├── extracted/                  # 추출된 JSON (자동 생성)
    └── chroma_db/                  # 벡터 DB (자동 생성)

lab-memory/                         # 패키지 (pip install)
├── pyproject.toml
├── lab_memory/
│   ├── extract/                    # PPT/PDF → JSON 추출
│   ├── index/                      # 청킹 + 임베딩 + ChromaDB 저장
│   ├── query/                      # 검색 + 답변 합성
│   ├── mcp_server.py               # MCP 서버
│   └── cli.py                      # CLI 엔트리포인트
└── configs/settings.yaml           # 기본 설정 (init 시 워크스페이스로 복사)
```

## 기술 스택

| 컴포넌트 | 라이브러리 |
|----------|-----------|
| PPT 파싱 | python-pptx 1.0.2 |
| PDF 파싱 | PyMuPDF 1.25.3 |
| 임베딩 | sentence-transformers 3.4.1 + multilingual-e5-large |
| 벡터 DB | chromadb 0.6.3 |
| MCP | mcp[cli] 1.8.0 |
| LLM 합성 | anthropic 0.49.0 (CLI --synthesize 전용, 선택사항) |
| CLI | click 8.1.8 |

## 설정

`configs/settings.yaml`에서 조정 가능:

- `embedding.model_name` — 임베딩 모델 (기본: multilingual-e5-large)
- `chunking.min_chunk_length` — 슬라이드 병합 기준 (기본: 100자)
- `chunking.max_chunk_tokens` — PDF 청크 최대 토큰 (기본: 512)
- `search.default_top_k` — 기본 검색 결과 수 (기본: 10)
- `search.score_threshold` — 최소 유사도 점수 (기본: 0.3)
