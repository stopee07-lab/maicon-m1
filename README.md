# MAICON M1 실행 안내

M1에서 채점하는 `target`, `search_sectors`, `base`를 Claude로 추출하고 검증합니다. 공식 리허설에서 명령을 읽어 결과만 확인하거나, 같은 결과를 리허설 채점 서버에 제출할 수 있습니다. Python 3.9 이상과 표준 라이브러리로 실행합니다.

기체에서 발급 키로 예시 명령을 해석해 세 필드가 기대값과 일치했습니다. 팀 테스트 서버에서 준비완료 접수도 확인했습니다. 공식 리허설에서 실제 명령을 제출하고 채점받는 단계는 아직 검증 전입니다.

Git 번들을 받았다면 파일이 있는 폴더에서 아래처럼 복제합니다.

```sh
git clone -b m1-report-only MAICON_M1.bundle maicon-m1-share
cd maicon-m1-share
```

## 1. 실행 환경 확인

복제한 폴더의 PowerShell에서 아래 명령을 실행합니다. `py`로 설치한 경우 `python` 자리에 `py`를 쓰면 됩니다.

```powershell
$m1Python = 'python'
& $m1Python -B -m unittest -v test_m1
```

실기체에서 시험할 때는 운영진이 허용한 시간에 이 폴더를 옮긴 뒤 JupyterLab 터미널에서 폴더를 엽니다. `python3 --version`으로 버전을 확인하고 `python3 -B -m unittest -v test_m1`을 실행합니다. 아래 PowerShell 명령에서 `& $m1Python`을 `python3`으로 바꾸면 됩니다.

## 2. 발급 키 인증과 모델 선택

```powershell
& $m1Python m1.py models
```

`ANTHROPIC_API_KEY (숨김 입력)`이 나오면 운영진이 발급한 원본 키를 입력합니다. 이미 현재 프로세스에 `ANTHROPIC_API_KEY`가 있으면 그 값을 씁니다. 키를 프로그램 인수로 넘기거나 코드와 로그에 넣지 마세요. `models`는 모델 목록 조회만 하고, 실제 문장 해석은 다음 명령에서 한 번 호출합니다.

출력된 목록에서 운영진이 허용하고 [구조화 출력](https://platform.claude.com/docs/en/build-with-claude/structured-outputs)을 지원하는 모델 ID를 확인합니다. 아래 `claude-MODEL-ID` 자리에 실제 ID를 넣습니다. `ANTHROPIC_MODEL` 환경 변수로도 지정할 수 있습니다.

## 3. 예시 문장 해석

```powershell
& $m1Python m1.py interpret --order example_order.json --camp BLUE --model claude-MODEL-ID
```

`example_order.json`은 명령 응답과 형태가 같은 연습 파일입니다. BLUE 기준 기대값은 `RED_RADAR`, `["CM", "R-S1"]`, `RED_SUPPLY_DEPOT`입니다. 정상 처리 시 표준 출력에는 보고 JSON이 나오고, 표준 오류에는 Claude 응답 시간과 요청 ID가 표시됩니다. 응답에서 빠진 시설, 중복·빈 섹터, 미등록 코드가 있으면 오류를 반환합니다.

## 4. 공식 리허설에서 접수 확인

포털에서 **테스트 대시보드 → 팀 테스트 준비 → 이 임무로 준비**를 선택합니다. 안내 자료 28쪽의 포털은 `http://192.168.110.50:8000/test/`이고, 30쪽의 팀 테스트 API는 `http://192.168.110.50:8100/api/report`입니다. 아래 명령에는 경로를 제외한 8100 주소를 넣습니다. [임무교육자료](https://maicon.kr/wp-content/kossa/2026MAICON/guide%28mission%29_2026MAICON.pdf#page=28)

M1만 시험할 때는 기체 터미널에서 이 폴더의 `m1.py`를 실행합니다. 이 파일은 HTTP 요청으로 명령을 받고 보고합니다. 포털의 **시작**은 기체에도 시작 신호를 보냅니다. 이전 시험에서 기체가 잠깐 움직였으므로, 시작 전에 다른 주행 노드가 실행 중인지 확인하고 바퀴가 움직여도 위험하지 않도록 기체를 고정합니다.

```powershell
& $m1Python m1.py ready --game-url http://192.168.110.50:8100
```

포털에서 준비완료가 **받음**으로 바뀌면 **시작**을 누릅니다. 진행 단계에서 아래 명령을 실행하면 진영과 명령을 팀 테스트 API에서 읽습니다. `MAICON_MISSION_CODE`는 화면에 표시되지 않게 입력받습니다. 서버 주소는 `MAICON_GAME_URL`로도 지정할 수 있습니다.

```powershell
& $m1Python m1.py rehearsal --game-url http://192.168.110.50:8100 --model claude-MODEL-ID
```

결과가 예상과 일치하면 끝에 `--submit`을 붙여 실행합니다. 그때 받은 명령을 다시 해석해 리허설 서버에 한 번 제출합니다. `accepted: true`와 `received`가 검증되면 포털의 **M1 정답 비교**까지 확인합니다. 접수 여부와 정답률은 각각 기록합니다.

## 팀 코드에 합치는 방법

`m1.py`를 팀 프로젝트에 가져온 뒤 경기 서버의 명령 응답, 우리 진영(`BLUE` 또는 `RED`), 승인된 모델 ID를 전달합니다. 반환된 세 필드를 기존 팀 코드의 M1 제출 함수에 넘길 수 있습니다.

```python
import os

from m1 import Claude, order_text

def build_m1_report(order_response, own_camp):
    claude = Claude(os.environ["ANTHROPIC_API_KEY"])
    model = os.environ["ANTHROPIC_MODEL"]
    return claude.interpret(model, own_camp, order_text(order_response))
```

명령 수신, Claude 호출, 결과 검증이 실패하면 `M1Error`가 발생합니다. 이 호출은 네트워크 응답을 기다리므로 팀 프로그램의 주행 제어와 별도 작업에서 실행합니다. 팀 테스트 전용 `Rehearsal` 클래스는 `8100` 포트로 제한돼 있습니다.

## 실패가 나면

| 표시 | 확인할 곳 |
|---|---|
| Claude `401` | 발급 키가 정확한지, 만료 또는 재발급됐는지 |
| Claude `403` 또는 `404` | 해당 키로 모델에 접근할 수 있는지, 모델 ID가 정확한지 |
| Claude `400` | 모델이 구조화 출력을 지원하는지, 호출 한도에 도달했는지 |
| Claude `429` | 할당량 또는 호출 제한 |
| 리허설 `409` | 팀 편성과 `running` 단계 |
| 리허설 `422` | 현장 통신 규약의 보고 필드와 배포 코드의 형식 |
| 보고 검증 실패 | 불명확한 시설·거점 또는 비어 있거나 중복된 섹터 |

시험 기록에는 코드 버전, 사용한 모델 ID, 우리 진영, 예시 또는 리허설 구분, 응답 시간, 접수 여부와 포털의 항목별 정답 여부를 남깁니다. [Claude API 오류 문서](https://platform.claude.com/docs/en/api/errors)
