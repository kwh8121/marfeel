# goatway 기사 원장 가이드

goatway 최신 기사 API를 처음부터 끝까지 받아 쌓은 기사 원장의 사용법이다. 설계 배경은 [수집 계획](../jobs/2026-11-06-goatway-ledger-collection-plan.md)을 본다.

## 구성

- 스크립트: `scripts/goatway_ledger.py` (표준 라이브러리만 사용, 인증 없음)
- 저장소(git 제외): `data/ledger/`
  - `raw/{run_id}/` 페이지 원본 gzip (기자 이메일은 원본에만 있고 원장에는 넣지 않는다)
  - `ledger.sqlite` 표: runs, pages, articles, article_versions, checks
  - `exports/articles_YYYYMMDD.csv`, `backup/ledger_YYYYMMDD.sqlite`
- API: `GET https://goatway.koreatimes.co.kr/api/home/article/latest?page={n}&size=10` (size는 무시되고 10건 고정)

## 명령

| 명령 | 용도 |
|---|---|
| `find-start` | 시작일의 마지막 페이지를 이분 탐색으로 찾는다 |
| `collect [--resume]` | 전체 수집. 중단되면 `--resume`으로 이어 받는다 |
| `retry-failed` | 실패 페이지만 다시 받는다 |
| `incremental` | 새로 올라온 기사만 받는다(일 1회 용도) |
| `check` | V1~V4 점검을 하고 checks 표에 기록한다 |
| `export` | CSV 내보내기와 SQLite 백업 |

## 주요 열 (articles)

`article_id`(기본키), `herb_article_id`, `pub_dt`(+09:00), `pc_title`, `lead`, `reporter_name`, `main_section_en`, `canonical_url`(도메인 없는 경로), `is_yonhap`, `slug_date`, `amp_match_key`(Search Console의 `/amp/...` 경로와 맞추는 키).

## 첫 전체 수집 결과 (2026-11-10)

- run_id `20261110T0856`: 4,665페이지 성공, 실패 0, 기사 46,643건, 2025-02-21 ~ 2026-11-10, Yonhap 15,746건. 소요 약 7시간
- V1 PASS(실패 0). V2 연속성 어긋남 5건: 인접 페이지 경계의 시각이 1~70분 어긋난 정도라 수집 중 기사 순서가 바뀐 것으로 보이며 누락 증거는 없다(원인 미확인)
- V3 `pub_dt` 날짜와 `slug_date`가 다른 기사 85건(0.2%). 자정 근처 시간대가 아니라 시간대 문제는 아니다(원인 미확인)
- V4 일별 건수 0건인 날 없음. 중앙값 82건, 중앙값 절반 미만인 날은 106일이고 확인한 60일 중 55일이 토·일이다
- V5 무작위 3건을 실제 페이지와 대조해 제목·발행 시각이 일치했다(웹 메타는 UTC, 원장은 KST)

## 주의

- 시각 열은 KST다. 웹 페이지 메타의 발행 시각은 UTC다.
- 같은 기사가 수정되면 `article_versions`에 이전 제목·리드가 남는다.
- V6(GA4 대조)은 아직 하지 않았다.

## 자동 수집과 PC 꺼짐 대비 (2026-11-10 등록)

개인 PC(WSL)라 절전·종료 중에는 cron이 돌지 않고, 놓친 실행을 나중에 대신 돌려 주지도 않는다. 그래서 "하루 한 번 정시"가 아니라 "여러 번, 켜질 때마다 따라잡기"로 구성했다. 모든 수집은 락과 건너뛰기로 중복 실행이 안전하다.

| 대상 | 일정 | 따라잡는 방식 |
|---|---|---|
| goatway 증분 | 매시 15분 + 부팅 4분 뒤 | 페이지 0부터 받다가 기존 기사로만 된 페이지에 닿으면 멈춘다. 며칠 꺼져 있어도 켜진 뒤 첫 실행이 빠진 기사를 채운다 |
| Search Console | 09:30·13:30·18:30·22:30 + 부팅 3분 뒤 | 가장 오래된 받은 날부터 훑어 빠진 날을 채운다. 최근 7일 빈 응답은 저장하지 않고 다시 받는다 |
| 상태 점검 | 매일 10:05 | `scripts/collect_health.py`가 Search Console 빠진 날과 원장 최신성을 `data/collect_health.log`에 기록한다 |

한계
- goatway 증분은 한 번에 200페이지(약 2,000건, 대략 3주치)까지 거슬러 간다. 그보다 오래 꺼져 있으면 경고를 남기고 종료 코드 1로 끝나므로 `collect`로 전체를 다시 받는다.
- Search Console은 보존이 16개월이라 오래된 날부터 사라진다. 몇 주 꺼져 있는 것은 괜찮지만 몇 달이면 앞쪽을 잃는다.
- 꺼진 동안 쌓인 구간은 켜진 뒤에 받으므로, 그 사이 수정·삭제된 기사의 중간 상태는 남지 않는다.
- 로그: `data/ledger/incremental.log`, `data/searchconsole/collect.log`, `data/collect_health.log`. 직접 확인은 `python3 scripts/collect_health.py`.
- Windows가 절전이면 WSL도 멈춘다. 확실히 하려면 작업 스케줄러에서 깨우기 설정을 하거나 상시 켜진 서버로 옮긴다(미적용).

## V6 GA4 대조 결과 (2026-11-10)

속성 `340662437`의 날짜별 기사 경로(URL에 `/YYYYMMDD/`가 든 경로)를 원장과 대조했다. 8일 표본: 2025-04-15, 08-20, 12-10, 2026-03-18, 06-10, 09-15, 10-20, 11-04.

- 원장 → GA4: 그날 발행된 원장 기사의 약 97~100%가 GA4에 나타난다(예: 11-04 125/125, 10-20 113/116). 원장에 실재하지 않는 기사를 넣은 흔적은 없다.
- GA4 → 원장: GA4에 잡힌 기사 경로 중 원장 URL과 맞지 않는 것이 PV 기준 약 7~32%(길이 잘림 보정 후 7~22%)다.
- 원인 두 가지를 확인했다.
  1. GA4 `pagePath`가 약 100자에서 잘린다. 원장 URL과 앞부분(90자 이상)이 같으면 같은 기사로 본다.
  2. 속보·외신 기사는 발행 뒤 제목이 바뀌어 슬러그가 달라진다. 예: GA4 `.../seoul-to-pull-some-embassy-staff-from-kyiv-...` ↔ 원장 `.../seoul-to-pull-half-of-embassy-staff-from-kyiv-...`, GA4 `democrats-capture-us-congress-...` ↔ 원장 `democrats-seize-us-congress-...`. 원장은 마지막으로 본 URL만 갖고, 이전 슬러그는 수집을 시작한 뒤의 변경만 `article_versions`에 남는다(현재 5건).
- 그러므로 PV·검색 데이터를 원장과 URL로 붙이면 이전 슬러그로 들어온 몫이 빠진다. 같은 날짜·섹션 안에서 제목 단어 겹침으로 맞추는 보정이 필요하다(미구현). 원장에 아예 없는 기사인지는 이 방법으로 구별하지 못했다.
- 한계: 8일만 봤고 일별 추이 전체나 PV 합계 대조는 하지 않았다.

## 슬러그 변경 보정 매칭 (2026-11-11)

`scripts/slug_match.py`가 GA4·Search Console의 기사 경로를 원장 기사에 연결해 `ledger.sqlite`의 `url_aliases` 표(alias_url, article_id, canonical_url, method, score)에 기록한다. 원장의 다른 표는 건드리지 않는다.

| method | 규칙 | 신뢰도 |
|---|---|---|
| exact | 정규화한 경로(`/amp` 접두·쿼리·끝 슬래시 제거)가 원장 URL과 같다 | 확정 |
| prefix | GA4 절단(약 100자, 또는 `…`로 끝남)이라 원장 URL 앞부분과 같다. 같은 날짜 안에서 후보가 1개일 때만 | 높음 |
| slug | 섹션만 다르고 슬러그가 같다 | 높음 |
| fuzzy | 같은 URL 날짜 안에서 슬러그 단어 자카드 ≥ 0.6이고 2등과 0.1 이상 차이 | 중간(표본 약 95%) |
| canonical | `--live`: 옛 URL을 열어 `<link rel="canonical">`이 가리키는 현재 URL을 원장과 맞춘다 | 확정. fuzzy를 덮어쓴다 |
| gone | `--live`: canonical이 섹션 페이지다. 기사가 내려갔거나 열리지 않는다 | 원장에 없는 것으로 본다 |
| none | 위에 해당 없음 | - |

사용: `python3 scripts/slug_match.py ga4 --days 2026-11-04 --live 80` (매칭 실패·fuzzy 경로 중 PV 상위 80개를 실제 페이지로 확인, 호출 간 0.3초). `--dry-run`이면 기록하지 않는다. `sample`로 기록된 매칭 표본을 사람이 본다.

실측(GA4 2일, PV 기준)
- 2026-11-04: exact 83.7%, prefix 5.5%, fuzzy 2.7%, canonical 7.5%, gone 0.5%, 미매칭 0%
- 2026-10-20: exact 69.7%, prefix 9.4%, canonical 18.2%, gone 2.5%, 미매칭 0%
- 보정 전 원장 불일치 14~22%가 거의 전부 연결된다. 제목이 크게 바뀌어(예: `appeals-court-upholds-yoons-...` → `yoon-loses-appeal-...`) 단어 겹침으로는 못 맞추던 것을 canonical이 해결한다.
- fuzzy 정확도: 표본 25건 중 live로 확인된 19건에서 18건 일치, 1건 불일치(원장에 슬러그 끝에 `-1`이 붙은 거의 같은 제목의 다른 기사). 확인되지 않은 6건은 내려갔거나 열리지 않았다.

한계
- `gone`·미확인 경로가 진짜 원장 누락인지, 삭제된 기사인지 이 방법으로는 구별하지 못한다. 원장 기사 중 GA4에 보이지 않는 것은 약 0~3%다.
- 실제 페이지 조회는 사이트에 요청을 보내므로 상위 N개로 제한한다. Search Console 경로는 아직 적용하지 않았다.
- 슬러그가 바뀐 기사의 이전 URL은 앞으로 `article_versions`에도 쌓인다. 과거 이력은 복원할 수 없어 위 방법으로 매번 맞춘다.

### Search Console 적용 결과 (2026-11-11)

`python3 scripts/slug_match.py sc --live 1500`으로 Search Console 원본 4개 유형(2,000개 파일)의 기사 경로 159,857개를 원장에 맞췄다. `url_aliases`에 exact·pre_ledger를 뺀 결과를 기록한다. `--live`로 실제 페이지를 읽는 경로는 클릭·노출 상위 1,500개이며, `missing`·`gone` 분류(`method`)는 이 상위 경로에서만 나온다.

| 분류 | 클릭 | 노출 | 의미 |
|---|---|---|---|
| exact | 93.9% | 90.1% | 원장 URL과 그대로 일치 |
| prefix·slug·fuzzy | 0.8% | 0.8% | 절단·섹션 변경·슬러그 변경 |
| canonical | 3.0% | 2.4% | 옛 슬러그를 실제 페이지로 확인 |
| missing | 0.9% | 0.5% | 열리는 기사인데 원장에 없다(47개) |
| gone | 0.3% | 0.3% | canonical이 섹션 페이지(내려갔거나 열리지 않음) |
| pre_ledger | 1.1% | 6.1% | URL 날짜가 원장 시작(2025-02-21) 이전. 경로 수로는 102,716개 |
| none | 0.0% | 0.1% | 상위 1,500 밖이라 실제 페이지를 확인하지 않은 경로 2,249개 |

- Search Console 기사 클릭의 약 98%가 원장 기사에 연결된다(exact~canonical, 정확도는 fuzzy 표본 약 95%).
- `pre_ledger`는 2025-02-21 이전에 발행된 옛 기사로, 원장 범위 밖이다. 경로가 많지만 클릭은 1.1%다.
- **`missing`**: 원장 기간 안에 발행됐고 실제 페이지가 정상인데 원장에 없는 기사 47개. 클릭 비중은 0.9%지만 한 기사당 클릭이 평균보다 매우 크다(상위 경로만 확인했기 때문). 섹션은 entertainment 18, foreignaffairs 8, business 8, southkorea 5, economy 4. 예: 2026-03-02 `kim-soo-hyun-comeback-rumors-...`(그날 원장 기사 54건). 원인은 아직 모른다(최신 기사 API가 일부 기사를 내보내지 않을 가능성, 수집 시점의 일시 누락 등).
- 따라서 원장은 "그 기간의 모든 기사"가 아닐 수 있다. 발제 분석(G1~G6)에서 원장을 기준으로 삼기 전에 `missing` 규모를 상위 1,500 밖까지 확인해야 한다.

### 원장 누락 조사 (2026-11-11)

Search Console에서 찾은 `missing` 47개를 조사했다.

- 7개는 2025-02-21 기사로, 실제 발행 시각이 원장 시작(2025-02-21 16:48 KST)보다 앞선 경계 효과다. 진짜 누락이 아니다. 나머지 중 다른 슬러그·섹션으로 같은 이야기가 원장에 있는 것이 일부 있고, 약 40개는 원장에 같은 기사가 없다.
- 수집 방식 문제가 아니다. 현재 최신 기사 API(`/api/home/article/latest`)를 직접 탐색해도 이 기사들이 나오지 않는다(2026-03-02 14:00 기사, 2026-01-22 `kospi-tops-another-milestone` 등). 페이지 경계 건너뜀도 아니다(발행 시각 대조 시 40개 중 37개가 수집 페이지 내부, 3개만 경계).
- 유형(`type`)이 원인이 아니다. 원장에는 일반(G) 46,376, 사진(P) 253, 영상(V) 11, A 6, I 1, E 1이 들어 있다.
- 실제 기사 페이지는 정상으로 열리고 canonical이 자기 자신이다. 추정: 서버가 목록 API에서 일부 기사를 제외하거나(대체·교체된 연합 기사 등) 목록에서 내려갔지만 페이지는 남아 있다. 이 추정은 확인하지 않았다. 확인하려면 goatway 담당자에게 목록 API의 제외 규칙을 물어야 한다.
- 규모: GA4 3일(2026-03-18, 06-10, 11-04) PV 기준 `missing` 0~0.2%, `gone` 0.6~2.0%. Search Console 상위 1,500 경로에서는 클릭 0.9%. 발제 분석 입력으로는 영향이 작지만, 클릭이 많은 개별 기사가 빠질 수 있다.
- 대응: 원장 기준 분석에서 `url_aliases.method='missing'`을 별도로 보고, 필요하면 Search Console·GA4 쪽에서 직접 보충한다.
