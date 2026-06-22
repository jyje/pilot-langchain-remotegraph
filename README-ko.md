<div align="center">

# jyje/pilot-langchain-remotegraph

LangGraph의 `RemoteGraph`를 self-hosted, LangGraph Platform API 호환 백엔드 3종에 대해 `remotegraph` CLI 하나로 검증하는 파일럿.

[English](README.md) / [한국어](README-ko.md)

</div>

## Agent Protocol

`RemoteGraph`가 서로 다른 세 서버에 대해 동일하게 동작하는 건 우연이 아닙니다 — 셋 다 LangChain의 프레임워크 독립적인 스펙인 [**Agent Protocol**](https://github.com/langchain-ai/agent-protocol)(runs, threads, 장기 메모리 store, 스트리밍, 에이전트 introspection)을 구현하고 있습니다. **독립적인 Agent Protocol 구현체들이 공식 클라이언트와 실제로 상호운용되는지 확인하는 것이 이 파일럿의 핵심 목표**이며, 부수적인 구현 디테일이 아닙니다.

| 백엔드 | Agent Protocol과의 관계 | 출처 |
|---|---|---|
| LangGraph Platform self-hosted (`langgraph dev`) | 레퍼런스 구현체 — "LangGraph Platform implements a superset of this protocol" | [langchain-ai/agent-protocol](https://github.com/langchain-ai/agent-protocol) README |
| [`aegra`](https://github.com/aegra/aegra) | 커뮤니티 구현체, Agent Protocol 스펙에 맞춰 명시적으로 구축됨 | [aegra docs](https://docs.aegra.dev/) |
| [`open-langgraph-platform`](https://github.com/HyunjunJeon/open-langgraph-platform) | 커뮤니티 구현체 — "Agent Protocol server built on LangGraph" | 프로젝트 README |

## 개요

이 저장소는 한 가지 질문에 답하는 파일럿입니다: **`langgraph.pregel.remote.RemoteGraph`가 LangGraph Platform Cloud뿐 아니라, LangGraph Platform REST API(`/assistants`, `/threads`, `/runs`)를 구현한 어떤 서버에 대해서도 동일하게 동작할까?**

이 패턴을 보여주기 위한 예시 에이전트 4개:

| 에이전트 | 역할 |
|---|---|
| `researcher` | 웹 검색 (DuckDuckGo) |
| `coder` | Python 코드 작성·실행 (`run_python` 툴) |
| `reviewer` | `ruff`로 코드 린트 (`lint_python` 툴) |
| `supervisor` | 로컬에서 실행되며, 위 3개를 **`RemoteGraph`로 호출**해 research → code → review 파이프라인을 수행 |

`researcher`/`coder`/`reviewer`는 백엔드에 배포되지만, `supervisor`는 절대 배포되지 않습니다 — 실제 LangGraph Platform 배포를 호출할 때와 똑같이, 오직 네트워크를 통해서만 그들과 통신합니다.

## 백엔드

| 백엔드 | 실행 방식 | 포트 | 비고 |
|---|---|---|---|
| [`aegra`](https://github.com/aegra/aegra) | Docker (FastAPI + Postgres + Redis) | `2026` | OSS 대안 중 가장 성숙 |
| [`open-langgraph-platform`](https://github.com/HyunjunJeon/open-langgraph-platform) | Docker (FastAPI + Postgres + Redis), [jyje의 fork](https://github.com/jyje/open-langgraph-platform)를 git submodule로 vendoring하고 로컬 버그 수정 적용 — [Known upstream issues](#알려진-upstream-이슈) 참고 | `8001` | Pre-1.0, 단독 메인테이너 |
| LangGraph Platform self-hosted | `langgraph dev` (인메모리 서브프로세스, Docker **아님**) | `2024` | 실제 Docker 경로(`langgraph up`)는 Enterprise 라이선스 키가 필요해서, 이 파일럿은 동일한 REST API를 노출하는 무료 `langgraph dev` 서버를 대신 사용합니다 |

## 요구사항

- Python 3.14 ([`uv`](https://docs.astral.sh/uv/)가 인터프리터와 venv를 관리)
- Docker (이 파일럿은 [OrbStack](https://orbstack.dev/)으로 테스트됨)
- OpenAI 호환 LLM 엔드포인트. 기본값은 로컬 [LM Studio](https://lmstudio.ai/) 서버.

## 빠른 시작

```bash
uv sync
cp .env.sample .env   # OPENAI_BASE_URL / OPENAI_MODEL / OPENAI_API_KEY 조정
uv run remotegraph --help
```

백엔드를 기동하고, 3개 에이전트를 배포한 뒤 하나를 호출:

```bash
uv run remotegraph host up aegra
uv run remotegraph agent deploy aegra
uv run remotegraph agent call coder "What is 12 * 8?" --backend aegra
uv run remotegraph host down aegra
```

supervisor를 통해 research → code → review 전체 파이프라인 실행 (현재 떠 있는 백엔드를 가리키도록):

```bash
REMOTEGRAPH_BASE_URL=http://127.0.0.1:2026 uv run python -c "
from agents.supervisor.graph import graph
result = graph.invoke({'task': 'Write a one-line python function that returns the square of a number.'})
print(result['review'])
"
```

다른 백엔드를 테스트하려면 `aegra`를 `open-langgraph`(포트 `8001`) 또는 `langgraph-platform`(포트 `2024`, Docker 없이 `up`이 그냥 `langgraph dev`를 띄움)으로 바꾸세요.

### 분산 배포 (에이전트마다 별도 서버)

이 파일럿은 편의상 3개 에이전트를 모두 하나의 백엔드에 배포하지만, `agents/supervisor/graph.py`는 각 에이전트의 URL을 독립적으로 해석합니다 — 공유 `REMOTEGRAPH_BASE_URL` 대신 `RESEARCHER_URL`/`CODER_URL`/`REVIEWER_URL`을 설정하면 supervisor가 별도로 호스팅된 서버 3개(예: 에이전트마다 각자 호스트에 띄운 Aegra 인스턴스)를 가리키도록 할 수 있습니다:

```bash
export RESEARCHER_URL=http://research-agent.internal:8000
export CODER_URL=http://coder-agent.internal:8000
export REVIEWER_URL=http://reviewer-agent.internal:8000
```

에이전트별 환경변수는 항상 `REMOTEGRAPH_BASE_URL`보다 우선하며, `REMOTEGRAPH_BASE_URL`은 위의 단일 백엔드 사용 시 fallback으로 남습니다.

### 서브그래프 제어, 검증됨

`researcher`/`coder`/`reviewer`는 flat ReAct 에이전트라서, `RemoteGraph`가 실제로 원격 그래프 *내부*를 제어하는지(단순히 통째로 호출하는 게 아니라)는 증명할 수 없습니다. [`agents/subgraph_demo/`](agents/subgraph_demo/)는 실제 서브그래프 노드를 가진 작고 결정론적인(LLM 없는) 그래프 — `prepare -> inner (서브그래프: validate -> {transform -> format_text | reject}) -> finalize`, 분기 포함 — 로, [`notebooks/subgraph_verification.ipynb`](notebooks/subgraph_verification.ipynb)에서 실제 백엔드를 상대로 직접 확인했습니다. 확인된 사실:

- `stream_subgraphs=True`로 서브그래프 내부 노드의 업데이트가 별도로 네임스페이스된 이벤트(`updates|inner:<ns-id>`)로 노출됩니다 — *어느 분기*(`transform`/`format_text` 대 `reject`)를 탔는지까지 보입니다, `inner`의 집계 결과만 보이는 게 아닙니다.
- `interrupt_before=["inner"]`가 실제로 서브그래프 실행 *전*에 멈춥니다(`state.next == ("inner",)`, `state.values`도 아직 서브그래프의 영향을 받지 않은 상태) — 재개하면 서브그래프를 거쳐 정상적으로 끝까지 진행됩니다.
- 둘 다 raw `langgraph_sdk` 클라이언트뿐 아니라 `agents/supervisor/graph.py`가 실제로 쓰는 `RemoteGraph` 클래스를 통해서도 동일하게 동작합니다.

### 워크플로우 / 서브그래프-워크플로우 패턴, YAML로 정의

[`src/remotegraph/workflow.py`](src/remotegraph/workflow.py)는 그래프의 토폴로지를 명령형 `.add_node()`/`.add_edge()` 호출 대신 YAML(또는 JSON — PyYAML이 그대로 파싱)로 로드합니다:

- 노드의 `fn:`은 점(dot) 표기 `"package.module:attr"` import 경로(평범한 함수 노드);
- 노드의 `workflow:`는 다른 workflow 파일을 가리키며, 재귀적으로 로드되어 컴파일된 **서브그래프** 노드로 추가됩니다 — `agents/subgraph_demo`가 쓰는 것과 동일한 합성 방식;
- 엣지는 `[from, to]` 쌍(`__start__`/`__end__` 센티널 포함), 또는 `conditional:` 블록(`source`, 라우팅 `fn:`, `targets:` 매핑)으로 `add_conditional_edges`를 통해 컴파일됩니다.

`agents/subgraph_demo/workflow.yaml` + `inner_workflow.yaml`이 "서브그래프 워크플로우 패턴"의 정식 예시입니다 — `agents/subgraph_demo/graph.py`는 그냥 `graph = load_workflow(...)` 한 줄입니다. [`agents/workflows/research_pipeline.yaml`](agents/workflows/research_pipeline.yaml)은 "평범한 워크플로우 패턴" 예시입니다: `agents/supervisor/graph.py`의 `research -> code -> review` 토폴로지를 그 파일의 *기존* 노드 함수를 그대로 참조해서 재선언하고, `tests/test_workflow.py`가 둘이 구조적으로 동일한 그래프를 만드는지 검증합니다 — 이미 검증된 기존 supervisor 코드는 건드리지 않고 패턴을 증명합니다.

### 자율형 수퍼바이저 (deepagents), 평가됨

[`deepagents`](https://github.com/langchain-ai/deepagents) 기반의 자율형(LLM이 라우팅을 결정하는) 수퍼바이저가 위에서 검증한 것과 같은 서브그래프 레벨 제어를 얻는지 평가를 요청받았습니다 — 결론은 "아니다"이고, 이건 버그가 아니라 실제 메커니즘의 차이입니다:

- `deepagents.create_deep_agent`는 `task` *툴*을 통해 sub-agent에 위임합니다 — 런타임에 LLM이 내리는 결정이며, LangGraph의 구조적 서브그래프 합성이 아닙니다. `RemoteGraph` 입장에서 이 위임은 그냥 평범한 tool-call/tool-result 메시지일 뿐, 별도로 네임스페이스된 서브그래프 스트림 이벤트가 아닙니다. **`stream_subgraphs`/`interrupt_before`는 여기에 적용되지 않습니다.**
- 대신 유용한 다른 걸 얻습니다: `deepagents.middleware.subagents.CompiledSubAgent.runnable`은 `Runnable`을 만족하는 무엇이든 받고, `RemoteGraph`도 그중 하나입니다. [`agents/autonomous_supervisor/graph.py`](agents/autonomous_supervisor/graph.py)는 `researcher`/`coder`/`reviewer`를 **래퍼 툴/함수 코드 없이** `CompiledSubAgent`로 직접 등록하고, deep agent의 `task` 툴이 실제로 진짜 원격 서버로 위임합니다. [`notebooks/autonomous_supervisor.ipynb`](notebooks/autonomous_supervisor.ipynb)에서 end-to-end로 검증: 작업 하나를 주면 자율적으로 `coder`를 호출(자기 요청을 다듬어 두 번)한 뒤 `reviewer`를 호출하고, 결합된 결과를 반환했습니다.

## CLI 레퍼런스

```
remotegraph config show|init|set <key> <value>   # remotegraph.toml (active_backend, ...)
remotegraph host list|up|down|status|logs [backend]
remotegraph agent deploy|list [backend]
remotegraph agent call <name> "<message>" [--backend <backend>]
```

`backend`는 `aegra`, `open-langgraph`, `langgraph-platform` 중 하나입니다. 생략하면 설정된 `active_backend`를 사용합니다 (`remotegraph config set active_backend <name>`).

## 개발

```bash
uv run ruff format . && uv run ruff check .
uv run ty check
uv run pytest tests/             # 백엔드가 떠 있지 않으면 스모크 테스트는 자동으로 skip됩니다
```

## 알려진 upstream 이슈

`open-langgraph-platform`은 pre-1.0 상태라, 실제로 띄워보는 과정에서 진짜 버그들을 발견해 [jyje의 fork](https://github.com/jyje/open-langgraph-platform/tree/fix/immutable-index-now-predicate) 브랜치(서브모듈 `vendor/open-langgraph-platform`로 vendoring)에서 수정했습니다:

- 마이그레이션 3개가 `WHERE ... > NOW()` 조건으로 partial index를 생성하는데, Postgres는 IMMUTABLE이 아닌 함수를 인덱스 조건절에서 거부합니다 — 그래서 새 데이터베이스에서 `alembic upgrade head`가 무한 재시작했습니다.
- `AUTH_TYPE=noop`이 `is_authenticated=False`를 반환했는데, `get_current_user`는 인증되지 않은 요청을 모두 거부합니다 — 즉 noop 모드가 자신의 docstring("인증 없이 모든 요청 허용")과 달리 실제로는 접근을 전혀 허용하지 않았습니다.
- `pyproject.toml`은 `a2a-sdk`에 하한만 지정(`>=0.3.22`)되어 있어서, 일반 `pip install .`이 호환되지 않는 더 새로운 메이저 버전을 설치합니다. 이 저장소의 `docker/open-langgraph/Dockerfile`은 그들의 lockfile에 명시된 버전으로 고정합니다.
- `api/quotas.py`가 `from __future__ import annotations`와 함께, `User`는 `TYPE_CHECKING` 블록 안에서만 import하고 `"Request"`는 import 없이 문자열 어노테이션으로만 써놨습니다 — 정적 타입 체커에는 문제없지만, FastAPI/Pydantic은 OpenAPI 스키마를 만들 때 이 forward reference를 런타임에 실제로 해석해야 해서, `GET /openapi.json`(따라서 `/docs`도)이 매 요청마다 500을 던졌습니다. 둘 다 모듈 최상단에서 정상 import하도록 고쳤습니다.

별도로 (패치하지 않고 우회만 함): `POST /assistants/search`는 호출자의 identity로 필터링하는데, 서버가 자동으로 시드하는 기본 어시스턴트들은 `user_id="system"` 소유라서 — `remotegraph agent list --backend open-langgraph`는 에이전트들이 정상 동작함에도 빈 목록을 반환합니다. `remotegraph agent call`/`RemoteGraph`는 그래프 ID를 직접 넘기므로 영향받지 않습니다.

## 실험 결과

[`REPORT.md`](REPORT.md)에 3개 백엔드를 실제로 End-to-End 실행한 로그와 스크린샷이 있고, [`notebooks/`](notebooks/) 아래에 백엔드별로 재현 가능한 Jupyter 노트북이 있습니다.

## 프로젝트 구조

```
src/remotegraph/      # CLI (typer): cli.py, config.py, host.py, agent.py, backends/, workflow.py (YAML 로더)
agents/                # researcher/coder/reviewer (배포됨) + supervisor (RemoteGraph 호출자)
agents/subgraph_demo/  # 서브그래프 워크플로우 패턴 예시, workflow.yaml + inner_workflow.yaml로 정의
agents/autonomous_supervisor/ # deepagents 기반 수퍼바이저 (CompiledSubAgent(runnable=RemoteGraph(...)))
agents/workflows/      # 평범한 워크플로우 패턴 YAML 예시
docker/aegra/          # Dockerfile + docker-compose.yml + aegra.json
docker/open-langgraph/ # Dockerfile + docker-compose.yml + open_langgraph.json
vendor/                # git submodule: jyje/open-langgraph-platform fork
langgraph.json         # langgraph-platform (dev) 백엔드가 사용하는 설정
```
