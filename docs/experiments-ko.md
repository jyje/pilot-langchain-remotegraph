<div align="center">

# 프롬프트 시나리오 실증: 한국어

[English version](experiments-en.md) · [메인 README](../README-ko.md)

</div>

이 문서는 `RemoteGraph`가 실제로 다양한 프롬프트/시나리오에서 기대대로 동작하는지 **한국어 입력으로 직접 실증**한 결과입니다. 라이브 백엔드(`langgraph-platform`, `langgraph dev`)에 배포된 실제 에이전트(`coder`, `researcher`, `reviewer`, `subgraph_demo`)를 `RemoteGraph`/`langgraph_sdk` 클라이언트로 호출해 얻은 **실제 응답**을 그대로 인용했습니다. 재현용 스크립트는 [`scripts/run_experiments.py`](../scripts/run_experiments.py), 원본 캡처는 [`docs/experiments/raw/ko.json`](experiments/raw/ko.json)에 있습니다.

LLM은 로컬 LM Studio(`google/gemma-4-e4b`)를 사용했습니다 — 클라우드 API 키 없이도 전체 파이프라인이 동작함을 같이 보여줍니다.

## 1. 단일 호출 (Simple Q&A)

가장 기본적인 시나리오: 원격 그래프에 메시지 하나를 보내고 답을 받는다.

- 입력: `12 곱하기 8은 얼마야? 숫자로만 답해줘.`
- 응답: `96`

→ `RemoteGraph.invoke()`가 한국어 메시지를 그대로 전달하고, 원격 `coder` 에이전트가 정확히 답했다.

## 2. 멀티턴 스레드 상태 유지 (Thread persistence)

같은 `thread_id`로 두 번 호출해, 원격 서버가 대화 맥락을 실제로 기억하는지 확인.

- 1턴 입력: `내가 좋아하는 숫자는 7이야. 기억해줘.`
- 1턴 응답: `네, 알겠습니다. 좋아하시는 숫자가 7이라는 것을 기억하고 있겠습니다! 😊`
- 2턴 입력: `내가 좋아하는 숫자에 10을 더하면 얼마야?`
- 2턴 응답: `좋아하시는 숫자(7)에 10을 더하면 **17**입니다.`

→ `config={"configurable": {"thread_id": ...}}`만 넘기면, 클라이언트 쪽에서 별도 상태 관리 없이도 원격 서버가 스레드 단위로 대화를 이어간다.

## 3. 스트리밍 (Streaming)

`client.runs.stream(..., stream_mode="values")`로 중간 이벤트가 실제로 여러 번 오는지 확인.

- 입력: `1부터 5까지 세어줘.`
- 수신 이벤트 수: 3 (`metadata` → `values`(echo) → `values`(최종 답))
- 최종 답: `1, 2, 3, 4, 5입니다.`

→ 스트리밍 모드에서도 한국어 입력이 깨지지 않고 그대로 들어오고, 최종 답변 직전 단계(에코)도 별도 이벤트로 관찰된다.

## 4. 서브그래프 분기 제어 (Subgraph branch control)

`subgraph_demo` (`prepare → inner(subgraph: validate → {transform → format_text | reject}) → finalize`)에 입력을 다르게 주어 분기를 실제로 타게 함.

| 입력 | 탄 분기 | 최종 결과 |
|---|---|---|
| `안녕 리모트그래프` | `transform → format_text` | `[리모트그래프 안녕 [PREPARED]] [finalized]` |
| `""` (빈 문자열) | `reject` | `[rejected: empty input] [finalized]` |

→ LLM 없이 결정론적으로 동작하는 그래프라, `RemoteGraph`가 입력값에 따라 원격 서버 내부의 조건 분기를 실제로 통과시킨다는 걸 의심 없이 확인할 수 있다.

## 5. 에러/엣지 케이스 (존재하지 않는 어시스턴트 호출)

존재하지 않는 그래프 이름(`does-not-exist`)으로 호출했을 때, 클라이언트가 실패를 어떻게 전달하는지 확인.

```
UnprocessableEntityError: Invalid assistant: 'does-not-exist'. Must be either:
- A valid assistant UUID, or
- One of the registered graphs: researcher, coder, reviewer, subgraph_demo
```

→ 서버가 422를 반환하고, `langgraph_sdk`는 이를 구체적인 예외 타입(`UnprocessableEntityError`)과 사용 가능한 그래프 목록이 포함된 메시지로 그대로 전달한다. 잘못된 입력에 대해 조용히 실패하지 않는다.

## 6. 멀티에이전트 파이프라인 (research → code → review)

`agents/supervisor/graph.py`가 `researcher`/`coder`/`reviewer` 세 개의 **원격** 그래프를 `RemoteGraph`로 순서대로 호출하는 실제 파이프라인.

- 과제: `숫자를 입력받아 그 숫자의 제곱을 반환하는 한 줄짜리 파이썬 함수를 작성해줘.`
- `coder` 산출 코드: `square = lambda n: n ** 2`
- `reviewer` 평가 (요약): "기능적으로는 맞지만, `lambda`를 변수에 대입하는 것은 PEP 8(E731) 위반이며 `def`를 쓰는 게 더 읽기 좋다"

→ 슈퍼바이저는 세 에이전트의 그래프 구현을 전혀 import하지 않고, 오직 네트워크 너머의 `RemoteGraph`로만 통신했는데도 **실제로 의미 있는 코드 리뷰 피드백**(스타일 이슈 지적)이 파이프라인 끝까지 전달됐다.

## 요약

| 시나리오 | 확인된 것 |
|---|---|
| 단일 호출 | 기본 invoke가 한국어 입출력에서 정상 동작 |
| 멀티턴 | 서버 측 스레드 상태가 클라이언트 재시작 없이 유지됨 |
| 스트리밍 | 중간 이벤트가 순서대로, 한국어 그대로 도착 |
| 서브그래프 분기 | 입력에 따른 내부 조건 분기가 원격에서도 그대로 동작 |
| 에러 케이스 | 잘못된 호출이 명확한 타입의 예외로 전달됨 (조용한 실패 없음) |
| 멀티에이전트 파이프라인 | 세 개의 독립 원격 그래프를 엮어도 의미 있는 결과(코드 리뷰)가 나옴 |

같은 7개 시나리오를 영어로도 그대로 재현한 결과는 [English version](experiments-en.md)에 있습니다.
