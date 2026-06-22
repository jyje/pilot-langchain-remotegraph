# remotegraph: 멀티 백엔드 RemoteGraph 파일럿 + CLI

## Context

`pilot-langchain-remotegraph`는 LangGraph의 `RemoteGraph` 클라이언트(원격에 호스팅된 그래프를 로컬 그래프처럼 호출하는 기능)가 LangGraph Platform 호환 REST API를 구현하는 다양한 self-host 백엔드에서도 동작하는지 검증하는 파일럿이다. 후보 백엔드 3개(aegra, LangGraph Platform self-hosted, open-langgraph-platform)를 조사했고, 각각 Docker로 띄워 테스트할 수 있는 옵션으로 다룬다. 이를 관리/실행하기 위한 `remotegraph` CLI(typer + ruff + ty, Python 3.14, uv 패키징)를 만든다. 데모용 에이전트는 Researcher / Coder / Reviewer 3개 + 이들을 RemoteGraph로 호출하는 Supervisor 1개로 구성한다. 에이전트 LLM 호출은 OpenAI 호환 클라이언트로 구성하고 모델명은 하드코딩하지 않는다. 에이전트의 툴은 일반 LangChain `@tool` 함수로 구현한다 (MCP는 이 파일럿의 비즈니스 로직과 무관하므로 사용하지 않음 — 개발 중 정확한 레퍼런스 확인을 위해 LangChain 공식 문서 MCP 서버(`docs.langchain.com/mcp`)는 별도로 Claude Code 개발 도구로만 등록).

**추가 확인(구현 후반에 조사)**: 이 3개 백엔드가 같은 REST API 모양을 갖는 건 우연이 아니라, 셋 다 LangChain의 프레임워크 독립적 스펙인 [Agent Protocol](https://github.com/langchain-ai/agent-protocol)을 구현하기 때문이다 — LangGraph Platform은 이 프로토콜의 superset 레퍼런스 구현체, aegra와 open-langgraph-platform은 커뮤니티 구현체. 즉 이 파일럿은 "RemoteGraph가 LangGraph Platform류 서버에서 동작하는가"를 넘어 "독립적인 Agent Protocol 구현체들이 공식 클라이언트와 실제로 상호운용되는가"를 검증하는 것이 핵심 목표다. 자세한 내용은 README.md/REPORT.md의 "Agent Protocol" 섹션 참고.

## 리서치 요약 (의사결정에 반영된 내용)

| 백엔드 | API 호환성 | Docker 경로 | 특이사항 |
|---|---|---|---|
| **aegra** | `langgraph_sdk`/`RemoteGraph`와 호환되는 assistants/threads/runs API. `aegra.json`으로 그래프 등록. `aegra-cli` pip 패키지 존재 | Postgres+Redis+앱, `docker compose up`, 포트 2026 | ~989★, Apache-2.0, 가장 성숙 |
| **LangGraph Platform self-hosted** | 동일 REST API. `langgraph dev`(인메모리)는 라이선스 불필요 | `langgraph up`(Docker)은 **Enterprise 라이선스 키 필수** → 일반 파일럿에 비현실적 | → **`langgraph dev`를 이 백엔드의 실행 방식으로 채택** (Docker 대신 서브프로세스) |
| **open-langgraph-platform** | route 구조(`assistants.py`/`threads.py`/`runs.py`)가 RemoteGraph와 정합적이나 미검증. `open_langgraph.json`으로 그래프 등록 | Postgres+Redis+앱, `docker compose up`, MIT | ★19, 단독 메인테이너, 문서 한국어 위주 — PyPI 패키지 유무 미확인 → 구현 시 git submodule로 vendoring 필요 가능성 높음 |

사용자 결정: LangGraph Platform self-hosted는 **`langgraph dev` 대체 방식**으로 채택, 에이전트 구성은 **Researcher/Coder/Reviewer + Supervisor**로 확정, LLM은 **OpenAI 호환 구성(모델명 비고정)**으로 확정, 에이전트 툴은 **일반 LangChain `@tool` 함수**로 구현(MCP 불필요).

## 리포지토리 구조

```
pyproject.toml                  # uv_build, [project.scripts] remotegraph=remotegraph.cli:app
.env.example                    # OPENAI_API_KEY, OPENAI_MODEL, OPENAI_BASE_URL(optional), backend별 키
src/
  remotegraph/
    __init__.py
    cli.py                      # root Typer app: add_typer(config/host/agent)
    settings.py                 # pydantic-settings: .env + remotegraph.toml 로드
    config.py                   # `remotegraph config` 서브커맨드 (show/set/init)
    host.py                     # `remotegraph host` 서브커맨드 (up/down/status/logs)
    agent.py                    # `remotegraph agent` 서브커맨드 (deploy/list/call)
    backends/
      __init__.py
      base.py                   # Backend Protocol: name, compose_path|run_mode, config_filename, base_url, requires
      aegra.py
      open_langgraph.py
      langgraph_platform.py     # run_mode="subprocess" (langgraph dev)
agents/
  researcher/graph.py           # 웹 검색/조사 ReAct 에이전트 (@tool 함수)
  coder/graph.py                # 코드 작성·실행 에이전트 (@tool 함수)
  reviewer/graph.py             # 결과 검증/비평 에이전트 (@tool 함수)
  supervisor/graph.py           # RemoteGraph로 위 3개를 호출하는 오케스트레이터
  llm.py                        # OpenAI 호환 ChatOpenAI 팩토리 (모델명은 env)
docker/
  aegra/
    Dockerfile                 # aegra-cli pip 설치 + agents/ COPY + aegra.json
    docker-compose.yml          # postgres + redis + app
    aegra.json
  open-langgraph/
    docker-compose.yml          # vendor/open-langgraph-platform 빌드 컨텍스트 참조 (또는 PyPI 확인 후 단순화)
    open_langgraph.json
vendor/                         # git submodule (open-langgraph-platform 소스, 필요 시)
tests/
  test_cli.py
  test_backends.py
  test_smoke_remotegraph.py     # 3개 백엔드에 대해 RemoteGraph round-trip 테스트
README.md                       # centered-readme 스킬 적용
```

## 구현 단계

1. **프로젝트 스캐폴드** *(완료)*: `pyproject.toml`(Python ">=3.14", uv_build, `[project.scripts] remotegraph = "remotegraph.cli:app"`), `[tool.ruff]`(`select=["E","F","I","UP","B"]`, `target-version="py314"`), `[tool.ty]`(`environment.python-version="3.14"`, `src.include=["src","agents","tests"]`). `uv init`/`uv add`로 typer, pydantic-settings, langchain-openai, langgraph, langgraph-sdk 의존성 추가.

2. **CLI 스켈레톤**: `cli.py`에 루트 `Typer()` 생성 후 `config`/`host`/`agent` 서브 앱을 `add_typer`로 등록. `uv run remotegraph --help`로 동작 확인 가능하게.

3. **Backend 추상화**: `backends/base.py`에 공통 인터페이스 정의(`up()/down()/status()/base_url`). `aegra.py`, `open_langgraph.py`는 `docker compose -f docker/<name>/docker-compose.yml up -d` 래핑. `langgraph_platform.py`는 `langgraph dev --port ...`를 서브프로세스로 띄우고 PID/로그 관리(라이선스 키가 있으면 향후 `langgraph up`으로 전환 가능하도록 `requires_license` 플래그만 남겨둠).

4. **설정 관리**: `settings.py`(pydantic-settings)로 `.env` + 프로젝트 루트 `remotegraph.toml`(활성 백엔드, 포트, base_url) 로드. `remotegraph config show|set|init` 구현.

5. **에이전트 4종 구현**: `agents/llm.py`에 `get_chat_model()` 팩토리(환경변수 `OPENAI_API_KEY`/`OPENAI_MODEL`/`OPENAI_BASE_URL`로 `ChatOpenAI` 생성, 모델명 하드코딩 없음). `researcher`/`coder`/`reviewer`는 각 역할에 맞는 `@tool` 함수(예: 웹 검색, 코드 실행, 린트/검증)를 사용하는 ReAct 그래프, `supervisor`는 `langgraph.pregel.remote.RemoteGraph`로 위 3개의 배포된 엔드포인트를 호출하는 라우팅 그래프.

6. **백엔드별 등록 파일 생성**: `remotegraph agent deploy <backend>`가 `agents/*/graph.py`를 스캔해 `aegra.json`/`open_langgraph.json`을 생성(또는 동기화)하고 해당 backend의 `up()`을 호출.

7. **Docker 구성**:
   - `docker/aegra/Dockerfile`: `pip install aegra-cli`(또는 uv) 기반, `agents/`와 생성된 `aegra.json` COPY.
   - `docker/open-langgraph/`: 구현 착수 시 PyPI 패키지 존재 여부를 먼저 확인 — 있으면 aegra와 동일한 패턴, 없으면 `vendor/open-langgraph-platform`을 git submodule로 추가해 그들의 Dockerfile을 빌드 컨텍스트로 사용하고 `graphs/`를 우리 `agents/`로 바인드 마운트.
   - LangGraph Platform 백엔드는 Docker 미사용(서브프로세스 `langgraph dev`)이므로 별도 compose 없음.

8. **스모크 테스트**: `remotegraph agent call <name> "<message>" --backend <b>`로 수동 호출. `tests/test_smoke_remotegraph.py`는 각 백엔드를 띄우고 `RemoteGraph`로 supervisor→3개 에이전트 라운드트립을 검증(pytest marker로 backend별 분리, CI에서는 skip 가능하게).

9. **문서화**: `centered-readme` 스킬로 README 헤더 작성, 3개 백엔드 비교표·CLI 사용법·`.env.example` 안내 포함.

## 검증 방법

- `uv run remotegraph --help` 및 각 서브커맨드 `--help` 정상 출력 확인
- `uv run ruff check .`, `uv run ty check` 통과
- 백엔드별로: `remotegraph host up aegra` → `remotegraph agent deploy aegra` → `remotegraph agent call researcher "..."` → 정상 응답 확인 → `remotegraph host down aegra`
- 동일 절차를 `open-langgraph`, `langgraph-platform`(dev 모드)에 대해 반복
- `uv run pytest tests/test_smoke_remotegraph.py` 로 RemoteGraph 라운드트립 자동 검증
