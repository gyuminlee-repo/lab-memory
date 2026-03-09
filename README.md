# Lab Memory

연구실 위클리 레포트(PPT)와 논문(PDF)에서 실험 기록과 연구 지식을 검색하는 로컬 RAG 시스템.

## 설치

```bash
cd lab-memory
pip install -e .
```

임베딩 모델(`intfloat/multilingual-e5-large`, ~1.3GB)은 첫 실행 시 자동 다운로드된다.

## 사용법

### 1. 데이터 준비

원본 PPT/PDF를 `data/raw/`에 심볼릭 링크 또는 복사:

```bash
ln -s /path/to/weekly-reports data/raw/weekly
ln -s /path/to/papers data/raw/papers
```

### 2. 추출 + 인덱싱

```bash
# 일괄 실행 (추출 → 청킹 → 임베딩 → ChromaDB 저장)
lab-memory ingest data/raw/

# 개별 실행도 가능
lab-memory extract data/raw/          # PPT/PDF → JSON
lab-memory index                       # JSON → ChromaDB
```

### 3. 검색

```bash
# 기본 검색
lab-memory search "ALE 실험 조건"

# 옵션
lab-memory search "tolerance mechanism" --top-k 5 --date-from 2023-01-01 --type pptx

# Claude API로 답변 합성 (ANTHROPIC_API_KEY 환경변수 필요)
lab-memory search "adaptive evolution 프로토콜" --synthesize
```

### 4. 인덱스 통계

```bash
lab-memory stats
```

### 5. MCP 서버 (Claude Code 연동)

프로젝트 루트의 `.mcp.json`에 등록되어 있어 Claude Code 세션에서 자동으로 사용 가능하다.

제공 도구:
- `search_lab_notes` — 키워드/의미 기반 검색
- `get_slide` — 특정 슬라이드 원문 조회
- `summarize_topic` — 주제별 종합 요약 (Claude API 사용)
- `list_reports` — 레포트 목록 조회
- `get_report_summary` — 개별 레포트 슬라이드 구성 확인

수동 실행:
```bash
lab-memory serve
```

## 디렉토리 구조

```
lab-memory/
├── pyproject.toml
├── configs/settings.yaml        # 임베딩 모델, 청킹 파라미터, 검색 설정
├── lab_memory/
│   ├── extract/                 # PPT/PDF → JSON 추출
│   │   ├── pptx_extractor.py   # python-pptx, multiprocessing 병렬
│   │   ├── pdf_extractor.py    # PyMuPDF
│   │   └── image_describer.py  # Phase 4 (미구현)
│   ├── index/                   # 청킹 + 임베딩 + 저장
│   │   ├── chunker.py          # 슬라이드 단위 / 토큰 기반 청킹
│   │   ├── embedder.py         # multilingual-e5-large
│   │   └── store.py            # ChromaDB
│   ├── query/                   # 검색 + 답변 합성
│   │   ├── retriever.py        # 벡터 검색 + 메타데이터 필터
│   │   └── synthesizer.py      # Claude API 답변 합성
│   ├── mcp_server.py           # MCP 서버 (5개 도구)
│   └── cli.py                  # CLI 엔트리포인트
└── data/
    ├── raw/                     # 원본 PPT/PDF (심볼릭 링크)
    ├── extracted/               # 추출된 JSON
    └── chroma_db/               # 벡터 DB
```

## 기술 스택

| 컴포넌트 | 라이브러리 |
|----------|-----------|
| PPT 파싱 | python-pptx 1.0.2 |
| PDF 파싱 | PyMuPDF 1.25.3 |
| 임베딩 | sentence-transformers 3.4.1 + multilingual-e5-large |
| 벡터 DB | chromadb 0.6.3 |
| MCP | mcp[cli] 1.8.0 |
| LLM 합성 | anthropic 0.49.0 |
| CLI | click 8.1.8 |

## 설정

`configs/settings.yaml`에서 조정 가능:

- `embedding.model_name` — 임베딩 모델 (기본: multilingual-e5-large)
- `chunking.min_chunk_length` — 슬라이드 병합 기준 (기본: 100자)
- `chunking.max_chunk_tokens` — PDF 청크 최대 토큰 (기본: 512)
- `search.default_top_k` — 기본 검색 결과 수 (기본: 10)
- `search.score_threshold` — 최소 유사도 점수 (기본: 0.3)
