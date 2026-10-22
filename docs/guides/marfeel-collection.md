# Marfeel 데이터 수집 스크립트

`scripts/marfeel_collect.py`가 토큰을 발급하고 [수집 쿼리](../references/marfeel-queries/README.md) 3종을 호출해 결과를 저장한다. Python 3 표준 라이브러리만 쓰며 Linux/WSL 기준이다(`fcntl` 사용).

## 준비

- 프로젝트 루트의 `.env`에 `MARFEEL_EMAIL`, `MARFEEL_SECRET`이 있어야 한다(`.gitignore`로 제외됨). 같은 이름의 환경변수가 있으면 환경변수가 우선한다.
- 계정은 API role이 활성화된 전용 사용자여야 한다. 근거: [API 레퍼런스](../references/Marfeel%20API-reference.md).

## 실행

실행 위치는 프로젝트 루트다.

| 목적 | 명령 |
| --- | --- |
| 토큰만 발급·확인 | `python3 scripts/marfeel_collect.py --auth-only` |
| 쿼리 3종 전부 수집 | `python3 scripts/marfeel_collect.py` |
| 쿼리 하나만 수집 | `python3 scripts/marfeel_collect.py docs/references/marfeel-queries/03-google-search-discover-news.json` |
| 여러 페이지 수집 | `python3 scripts/marfeel_collect.py --max-pages 3` |
| 출력 폴더 변경 | `python3 scripts/marfeel_collect.py --out <폴더>` |

3종을 전부 수집하면 호출 간격 때문에 약 3분 걸린다. 종료 코드는 성공 0, 하나라도 실패하면 1이다.

## 동작

| 항목 | 동작 |
| --- | --- |
| 토큰 | `POST /api/user/signin`으로 발급해 재사용한다. 최대 14일 유효하므로 13일이 지나면 재발급한다. 응답 전체는 로그에 남기지 않는다 |
| 토큰 저장 | `~/.cache/marfeel/state.json`(권한 600, 폴더 700). 저장소 안에는 두지 않는다 |
| 호출 한도 | 계정당 분당 1회. 호출 사이 65초를 둔다. 마지막 호출 시각을 파일에 저장해 실행이 달라도 간격을 지킨다 |
| 동시 실행 | 파일 잠금으로 직렬화한다. 다른 곳에서 돌고 있으면 끝날 때까지 기다린다 |
| 401 | 토큰을 재발급해 1회 재시도한다 |
| 429 | 최대 3회 재시도한다 |
| 403 | 재시도하지 않고 보고한다(`rawData`·`amplify` 권한은 요금제 제한) |
| 204 | 유효한 지표가 없거나 데이터가 없다는 뜻으로 실패 처리한다 |
| 쿼리 검사 | 필수 필드(`dates`, `filters`, `groupBy`, `metrics`, `order`), 빈 `metrics`, `limit` 500 초과를 호출 전에 거부한다 |

## 출력

`data/marfeel/YYYY-MM-DD/`(`.gitignore`로 제외됨)에 쿼리마다 두 파일을 쓴다.

| 파일 | 내용 |
| --- | --- |
| `<쿼리 이름>.json` | 요청 본문과 응답 원본. 시계열(`actualData.data`)과 `compareData`를 포함 |
| `<쿼리 이름>.csv` | 그룹(행)별 차원 값과 지표 합계(`total`). UTF-8 BOM(Excel 호환) |

CSV는 기간 전체의 합계다. 일별 값이 필요하면 JSON의 `actualData.data`를 쓴다. 중복 제거 지표(`uniqueUsers`)를 일별 값의 합으로 대체하지 않는다.

## 알려진 제약

- 인증 오류의 HTTP 상태 코드는 문서에 명시가 없다. 토큰 만료 시 401이 온다고 가정했고 다른 코드면 재인증하지 않고 실패로 보고한다.
- `--max-pages`를 늘리면 페이지마다 1분이 더 든다. 페이지 이어받기는 CSV와 JSON 모두에 합쳐 저장하지만 시계열 합치기는 하지 않고 페이지별 원본을 `pages`에 보존한다.
- 그룹 수가 `limit`(100)을 넘으면 상위 100개만 저장된다. 필요하면 쿼리 파일의 `limit`(최대 500)을 올리거나 `--max-pages`를 쓴다.
- 자동 스케줄링(cron 등)은 포함하지 않는다. 다른 작업이 같은 계정으로 호출하면 한도를 공유하므로 시간대를 조율한다.
