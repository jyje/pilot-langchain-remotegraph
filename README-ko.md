<div align="center">

# jyje/pilot-langchain-remotegraph

LangGraph의 `RemoteGraph`를 self-hosted, LangGraph Platform API 호환 백엔드 3종에 대해 `remotegraph` CLI 하나로 검증하는 파일럿.

[English](README.md) / [한국어](README-ko.md)

</div>

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
src/remotegraph/      # CLI (typer): cli.py, config.py, host.py, agent.py, backends/
agents/                # researcher/coder/reviewer (배포됨) + supervisor (RemoteGraph 호출자)
docker/aegra/          # Dockerfile + docker-compose.yml + aegra.json
docker/open-langgraph/ # Dockerfile + docker-compose.yml + open_langgraph.json
vendor/                # git submodule: jyje/open-langgraph-platform fork
langgraph.json         # langgraph-platform (dev) 백엔드가 사용하는 설정
```
