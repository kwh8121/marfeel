# goatway 기사 원장 수집 계획과 저장 방법

- 상태: 구현됨(2026-11-10), 전체 수집 진행 중 · 작성 2026-11-06
- 목적: [발제 문서 r3](../plans/데이터%20기반%20발제%20에이전트%20—%20관심을%20끄는%20발제의%20필요·충분조건_r3.md) 4.0절의 기사 원장을 만든다. URL 개편 이후 KT 전체 기사의 ID, 발행 시각, 제목, 리드, 섹션, 기자, 정규 URL을 한 표로 모은다. 이 표가 GA4 PV·Marfeel 유입 경로를 결합하는 기준 키가 된다.
- 비목표: 본문 전체, 태그, 조회수 수집. 개편 전 기사의 구 URL(`/pages/article.asp/{ID}`) 대응

## 1. 대상 API (2026-11-06 실측)

`GET https://goatway.koreatimes.co.kr/api/home/article/latest?page={n}&size=10`

| 항목 | 내용 |
| --- | --- |
| 인증 | 없음 |
| 수집 주기 | 제한 없음(2026-11-06 사용자 확인) |
| 응답 | `{result, statusCode, data: {page, contents[]}}`. 정렬은 발행 시각 내림차순 |
| 페이지 크기 | `size`는 무시되고 항상 10건 |
| 범위 | 총 397,925건, 2007-03까지. 1,000페이지 미만에서는 `totalElements`가 10,000으로 표시된다(표시상 상한) |
| 응답 시간 | 앞쪽 페이지 0.05~0.5초, 깊은 페이지 4~5초 |
| 기사 필드 | `articleId`(UUID), `herbArticleId`, `pubDt`(초 단위), `pcTitle`·`mobileTitle`·`seoTitle`, `lead`(약 720~1,100자), `reporterName`·`reporterEmail`, `mainSectionId`·`mainSectionNameEn`·`sectionBreadcrumb`, `slugUrl`·`canonicalUrl`, `articleReadTime`, `thumbnail`, `articleRelationList` |
| 쓰지 않는 필드 | `type`, `status`(2026-11-06 사용자 결정) |
| 오래된 기사 | 2017년 무렵부터 `reporterName`·`reporterEmail`이 없고, 2007년 무렵은 `thumbnail`도 없다 |

## 2. 수집 범위

- **시작일은 2025-03-01**로 잡는다. URL 개편 전환일이 "2025-04 전후(GA4 차트 판독)"로만 알려져 있어 여유를 둔다. 정확한 전환일이 확정되면 분석할 때 잘라낸다. 추가 비용은 약 260페이지다(하루 약 86건 기준, 추정).
- **전환일은 goatway로 알 수 없다.** 과거 기사도 모두 슬러그 URL로 이관돼 나온다. GA4에서 일별 `pagePath` 중 `/pages/article.asp` 비중이 떨어지는 날을 1회 조회하거나, 개발팀에 확인한다.
- **마지막 페이지**: 2025-03-01에 해당하는 페이지 번호를 이분 탐색으로 찾는다. 호출은 10회 안팎이고, 예상은 약 5,500페이지다(추정). 여기에 50페이지를 더 받아 경계를 넘긴다.

## 3. 수집 방법

### 3.1 순서와 정합성

- **0페이지에서 깊은 페이지로 순서대로 받는다.**
  - 목록이 최신순이라 수집 중 새 기사가 올라오면 기존 기사가 뒤로 밀린다.
  - 얕은 쪽에서 깊은 쪽으로 받으면 밀린 기사가 다음 페이지에 한 번 더 나온다. 중복은 생기지만 누락은 없다.
  - 반대 순서로 받으면 이미 받은 페이지로 밀려 들어간 기사를 놓친다.
- **중복 제거**: `articleId`로 한다.
- **마무리 재수집**: 전체 수집이 끝나면 0페이지부터 이미 가진 `articleId`가 연속 10건 나올 때까지 다시 받아, 수집 중 새로 발행된 기사를 채운다.
- **연속성 검사**: 페이지 n의 마지막 `pubDt`가 페이지 n+1의 첫 `pubDt`보다 늦거나 같아야 한다. 어긋나면 `checks`에 기록하고 그 앞뒤 페이지를 다시 받는다. 기사 삭제로 목록이 앞으로 당겨지면 누락이 생길 수 있기 때문이다.

### 3.2 호출

- 동시성은 1로 하고 순차 호출한다. 호출 사이 간격은 0.3초다. 제한은 없지만 깊은 페이지의 응답이 4~5초라 서버 부하를 피한다.
- 예상 소요 시간은 약 2~4시간이다(추정).
- 클라이언트 이름은 일반 이름을 쓴다(예: `kt-ledger-collector/0.1`). 개인 정보를 넣지 않는다.
- **재시도**: 200이 아니거나 30초 안에 응답이 없거나 `result`가 `success`가 아니면 재시도한다. 간격을 2초, 5초, 15초로 늘려 3회까지 한다. 그래도 실패하면 `pages`에 실패로 기록하고 다음 페이지로 간다.
- **이어받기**: `pages` 표에서 해당 `run_id`로 완료된 페이지를 건너뛴다. 중단된 지점부터 다시 시작할 수 있다. 기존 `scripts/marfeel_collect.py`의 상태 파일 방식과 같은 원리다.
- **실패 페이지 재처리**: 전체 수집이 끝나면 실패 페이지만 다시 받는다.

## 4. 저장 방법

세 층으로 저장한다. 표준 라이브러리만 쓴다. SQLite는 3.45가 있고, DuckDB·pyarrow는 설치돼 있지 않아 쓰지 않는다. `.gitignore`가 `data/` 전체를 제외하므로 수집물은 git에 올라가지 않는다.

### 4.1 위치

```
data/ledger/
├── raw/{run_id}/page_00000.json.gz   # 원본. 수정하지 않는다
├── ledger.sqlite                      # 원장 DB
├── exports/articles_YYYYMMDD.csv      # 분석용 스냅샷
└── backup/ledger_YYYYMMDD.sqlite      # 전체 수집 후 백업
```

`run_id`는 수집 시작 시각(KST)이다. 예: `20261106T1730`.

### 4.2 원본 층

- 페이지 응답 본문을 그대로 gzip으로 저장한다. 파싱을 바꿔도 다시 호출하지 않고 원본에서 원장을 다시 만들 수 있다.
- 임시 파일에 쓴 뒤 이름을 바꿔 저장한다. 중단돼도 반쯤 쓰인 파일이 남지 않는다.
- 예상 크기는 페이지당 약 22KB × 약 5,500페이지 ≈ 120MB이고, 압축하면 약 25MB다(추정).

### 4.3 원장 층 (SQLite)

| 표 | 내용 | 키 |
| --- | --- | --- |
| `runs` | 실행 기록: 시작·종료 시각, 방식(`full`/`incremental`), 대상 시작일, 성공·실패 페이지 수, 메모 | `run_id` |
| `pages` | 페이지 기록: 받은 시각, HTTP 상태, 응답 시간(ms), 시도 횟수, 건수, 첫·마지막 `pubDt`, 원본 경로, sha256, 성공 여부 | (`run_id`, `page`) |
| `articles` | 기사 1행(중복 제거 결과) | `article_id` |
| `article_versions` | 제목·리드·정규 URL이 바뀐 이력 | (`article_id`, `content_hash`) |
| `checks` | 검사 결과: 연속성 어긋남, 일별 건수 이상, 실패 페이지, 시간대 불일치 | 자동 번호 |

**`articles` 열**

| 구분 | 열 |
| --- | --- |
| 원본 | `article_id`, `herb_article_id`, `pub_dt_raw`, `pc_title`, `mobile_title`, `seo_title`, `lead`, `reporter_name`, `main_section_id`, `main_section_en`, `section_breadcrumb`, `canonical_url`, `slug_url`, `read_time`, `thumbnail` |
| 파생 | `pub_dt`(ISO 8601, `+09:00`), `is_yonhap`(`reporter_name` = `Yonhap`이면 1), `slug_date`(경로의 `YYYYMMDD`), `amp_match_key`(`/amp` + `canonical_url` 앞부분 100자. GA4 AMP 경로 결합용) |
| 관리 | `first_seen_run`, `last_seen_run`, `first_seen_at`, `last_seen_at`, `content_hash`(제목 3종 + 리드 + 정규 URL의 sha256) |

- 색인: `pub_dt`, `canonical_url`, `herb_article_id`, `amp_match_key`
- **기자 이메일(`reporterEmail`)은 원장에 넣지 않는다.** 분석에 필요 없는 개인 정보라 원본 파일에만 남는다.
- 타입은 TEXT·INTEGER·REAL만 쓰고 SQLite 전용 기능은 쓰지 않는다. Wire Desk가 쓰는 Postgres로 옮길 수 있게 하기 위해서다.

**저장 규칙**

- 페이지 하나의 처리(원본 저장 → `pages` 기록 → `articles` 갱신)를 한 트랜잭션으로 묶는다.
- 같은 `article_id`가 다시 나오면 덮어쓰지 않는다. `last_seen_*`만 갱신한다.
- `content_hash`가 다르면 `articles`를 최신 값으로 바꾸고 `article_versions`에 이전 값을 한 행 남긴다. 지금 API에는 슬러그 수정 이력이 없지만, 증분 수집을 이어 가면 앞으로의 이력은 쌓인다.
- `pub_dt`의 시간대는 KST로 가정하고 `+09:00`을 붙인다. 가정은 5절 검증에서 확인한다.

**크기**: 기사 약 5만 5천 건 × 약 1.5KB ≈ 80MB(추정)

### 4.4 내보내기와 백업

- 전체 수집과 검증이 끝나면 `articles`를 CSV로 내보낸다(`exports/articles_YYYYMMDD.csv`, UTF-8). 분석 결과에는 어느 날짜의 원장을 썼는지 적는다.
- 전체 수집 후 SQLite 백업 기능(`Connection.backup`)으로 `backup/`에 복사한다. `data/`가 git 밖이라 원장의 사본은 이것뿐이다.

### 4.5 이후 같은 DB에 넣을 표 (참고)

| 표 | 내용 | 결합 키 |
| --- | --- | --- |
| `ga4_article_pv` | 기사별 72시간 PV·활성 사용자, 국가 × 언어 행 | `article_id` |
| `bot_rows` | 72시간 창별 사이트 전체 봇 의심 행 목록 | 창 시작·종료 시각, 국가, 언어 |
| `marfeel_article_source` | 기사별 유입 경로 구성 (Marfeel 보존 기간 확인 후) | `article_id` |

## 5. 검증

| # | 검사 | 방법 | 통과 기준 |
| --- | --- | --- | --- |
| V1 | 실패 페이지 | `pages`에서 성공 아닌 페이지 수 | 재처리 후 0건 |
| V2 | 연속성 | 인접 페이지 `pubDt` 순서 | 어긋남 0건(재수집 후) |
| V3 | 시간대 | `pub_dt` 날짜와 `slug_date` 비교. 자정 근처 기사 중심 | 불일치는 모두 설명돼야 한다(예: 발행 직전 슬러그 생성) |
| V4 | 일별 건수 | 하루 건수 분포 | 0건인 날, 평균의 절반 미만인 날은 원인을 기록한다 |
| V5 | 표본 대조 | 3건을 실제 기사 페이지와 비교(제목, 발행 시각, 정규 URL) | 3건 일치 |
| V6 | GA4 대조 | 한 달을 골라 GA4 기사 경로 목록과 원장 대조 | 누락률과 AMP·슬러그 결합률을 기록한다. 기준값은 결과를 보고 정한다 |

## 6. 완료 기준

- 2025-03-01부터 수집 종료 시점까지 V1·V2 통과
- V3~V5 결과가 `checks`와 작업일지에 기록됨
- V6 누락률·결합률이 기록됨
- CSV 내보내기와 백업 완료

## 7. 운영 단계의 증분 수집

- 매일 1회 0페이지부터 받고, 이미 가진 `articleId`가 연속 10건 나오면 멈춘다. 하루 수십 건, 호출 10회 안팎이다.
- 방식은 `incremental`로 `runs`에 기록한다. 저장 규칙은 전체 수집과 같다.
- 증분 수집이 쌓이면 `article_versions`에 제목·슬러그 변경 이력이 생긴다.

## 8. 구현 산출물 (예정)

- 스크립트: `scripts/goatway_ledger.py`(가칭). 하위 명령 `find-start`(이분 탐색), `collect`(전체·이어받기), `retry-failed`, `incremental`, `check`, `export`
- 가이드: `docs/guides/goatway-ledger.md`. 실행 방법, 검증 명령, 복구 방법
- 기록: 실행 결과는 해당 날짜 작업일지에 남긴다

## 9. 미해결

- URL 개편 정확한 전환일(GA4 `pagePath` 일별 조회 또는 개발팀 확인)
- V6 누락률·결합률의 통과 기준(대조 결과를 보고 정함)
