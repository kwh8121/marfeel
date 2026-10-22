# Marfeel Reporting API — 수집 가능 데이터 범위

- 확인일: 2026-10-21
- 대상: Korea Times (site id 9291, 시간대 Asia/Seoul, 통화 USD), `.env`의 API 전용 계정(role `Engineering`)
- 근거: 실제 API 호출 결과 + 공식 문서. 인증·요청 명세는 [Marfeel API-reference.md](Marfeel%20API-reference.md)를 따른다.
- 비밀값(이메일·비밀번호·토큰)은 이 문서에 기록하지 않는다.

## 1. 요약

- 로그인(`POST /api/user/signin`)과 조회(`POST /api/dashboard/query`)가 모두 HTTP 200으로 성공했다.
- 호출 한도는 계정당 분당 1회, 응답당 최대 500행이다. 모든 탐색은 호출 사이에 65초를 두고 수행했다. 60초 안의 두 번째 호출은 실측에서 HTTP 429였다(8절).
- 기사별 실시간 조회(1·5분 단위)와 국내·해외 분리가 가능하다. 경쟁사(koreaherald.com) 데이터는 이 API로 조회되지 않는다(8절).
- 이 계정에서 값이 있는 지표는 확인된 범위로 `uniqueUsers`, `pageViewsTotal`, `newArticles`, `discoverClicks`, `discoverImpressions`, `searchPosition`, `adsPerPage`, `socialPosts`에 6절에서 확인한 `totalDuration`, `averageRFV`, `adsImpressions`, `searchImpressions`, `searchClicks` 5개, 그리고 앱 카탈로그에서 확인한 15개를 더한 28개다. 수익 계열(`revenueTotal`, `CPM`, `RPM`, `ARPU`, `revenueTotalPerArticle`)과 모니터링 계열은 이름은 유효하지만 값이 0이다.
- `uniqueSessions`, `pageViewsPerSession`, `sessionsPerUser`, `uniqueRegisteredUsers`는 `rawData` 권한이 없어 조회할 수 없다(4절).
- Engagement·광고·미디어 계열의 나머지 후보는 권한 문제가 아니라 시도한 이름이 틀려 무시된 것으로 보이며, 실제 API 이름은 Explore에서 확인해야 한다.
- 확인된 그룹화 차원은 `url`, `title`, `section`, `visitorFrequency`, `folder`, `host`, `uri`, `pageTechnology`, `country`, `sentiment`, `source`, `customerLoyalty`(값이 `0` 하나뿐)이다. 6절에서 `deviceType`, `medium`, `author`, `contentByAge`, `publishDate`도 확인했다. 도시(`city`)는 Enterprise 전용이다. 브라우저·OS 등 나머지 방문자 세부 차원은 이름을 확인하지 못했다(5절). `groupBy`는 잘못된 이름도 200으로 받으므로 라벨 해석에 주의한다.
- `socialPosts`를 제외한 Social 후보는 `amplify metrics` 권한이 없어 조회할 수 없었다.

## 2. 확인된 지표 (최근 7일 기준)

| API 이름 | 값 | 판정 |
| --- | --- | --- |
| `uniqueUsers` | 729,019 | 사용 가능 |
| `pageViewsTotal` | 1,119,300 | 사용 가능 |
| `newArticles` | 746 | 사용 가능 |
| `discoverClicks` | 216,277 | 사용 가능 (Google Discover) |
| `discoverImpressions` | 7,899,349 | 사용 가능 (Google Discover) |
| `searchPosition` | 7.14 | 사용 가능 (Search Console 평균 순위) |
| `adsPerPage` | 1.189 | 사용 가능 (페이지당 광고 수) |
| `socialPosts` | 325 | 사용 가능 (소셜 게시물 수) |
| `revenueTotal` | 0 | 이름은 유효, 데이터 없음 |
| `affiliationClicks` / `affiliationRevenue` / `affiliationOrders` / `affiliationCommission` | 0 | 이름은 유효, 데이터 없음 |
| `productViews` / `totalItemsPurchased` | 0 | 이름은 유효, 데이터 없음 |

- 값 0은 "해당 데이터를 수집하지 않는 사이트"일 가능성이 높다. 기능이 꺼져 있는지는 확인하지 못했다.
- `uniqueUsers`의 `total`은 중복 제거 값이다. 일별 값을 합산해 대체하지 않는다.
- 지원 집계 단위는 응답의 `availableGranularities` 기준 `hourly`, `daily`, `weekly`였다.

## 3. 사이트 플래그 (로그인 응답의 Site)

| 플래그 | 값 |
| --- | --- |
| `hasRevenue` | 1 |
| `hasRecirculation` | 1 |
| `hasEntities` | 30 |
| `hasCategories` | 0 |
| `hasCdp` | 0 |
| `hasDynamicPaywall` | 1 |
| `hasFlowcards` | 1 |

`hasRevenue`가 1인데 `revenueTotal`이 0이므로, 수익 데이터가 실제로 들어오는지는 운영 측에 확인이 필요하다.

## 4. 탐색 방법과 미확정 범위

### 탐색 방법

| 관찰 | 해석 |
| --- | --- |
| 존재하지 않는 지표만 보냄 → HTTP 204(빈 본문) | 오류 메시지로 유효한 이름을 알려주지 않는다 |
| 유효·무효 지표를 섞어 보냄 → HTTP 200, 유효한 지표만 반환 | 후보 이름을 한 요청에 여러 개 보내 유효한 것만 걸러낼 수 있다 |
| 권한 없는 지표가 하나라도 포함 → HTTP 403 | 해당 요청 전체가 거부된다. 메시지로 권한 종류를 구분할 수 있다 |

### 403 메시지

- `You do not have access to rawData`: 지표 후보 54개 묶음(3개 청크)에서 발생.
- `You do not have access to amplify metrics`: Social 후보 묶음에서 발생.

### 미확정

- `rawData` 오류가 났던 후보 54개를 이분 탐색(29회 요청)으로 좁혔다.
  - 권한이 필요해 막힌 지표(HTTP 403): `uniqueSessions`, `pageViewsPerSession`, `sessionsPerUser`, `uniqueRegisteredUsers`
  - `rawData` 제한은 요금제 문제로 보인다. Marfeel Explore에서 Unique Sessions(지표)와 City(차원)에 "Enterprise" 표시가 붙어 있고, 클릭하면 "Upgrade your Marfeel plan" 안내가 뜬다(2026-10-21, 사용자 확인). 이 계정에서는 Enterprise 항목을 쓸 수 없다.
  - 허용되는 지표: 위 2절의 `adsPerPage`, `socialPosts`가 새로 확인됐다.
  - 나머지 후보는 모두 무시(HTTP 204)되었다. 즉 읽기 시간·RFV·스크롤·광고 노출·CPM·미디어 계열은 권한 문제가 아니라 **내가 시도한 이름이 틀렸을 가능성이 크다**. 실제 API 이름은 Marfeel Explore의 "Get JSON API"로 확인해야 한다.
- `socialPosts`는 허용됐지만 나머지 Social 후보(좋아요, 댓글 등)는 별도 묶음에서 `amplify metrics` 권한 오류가 났다. 이분 탐색 대상이 아니었으므로 Social 계열의 허용 범위는 미확정이다.
- 페이지 속도(`lcp` 등), 재순환(`eligible` 등), Health Score, 전환 후보 이름은 200 응답에서 반환되지 않았다. 이름이 틀렸거나 이 계정에서 제공되지 않는 것으로 보이며 어느 쪽인지는 구분하지 못했다.
- 아래 이름은 추측이 틀려 무시된 것으로 보이며, 실제 API 이름은 Marfeel Explore의 "Get JSON API"로 확인해야 한다: `pageViews`, `sessions`, `searchImpressions`, `searchClicks`, `adImpressions` 등.
- 과거 데이터 보존 기간, 날짜 경계·시간대 처리는 문서에 없다.

## 5. 확인된 그룹화 차원 (`groupBy`)

### 응답 해석 주의

- 지표와 달리 `groupBy`는 잘못된 이름도 HTTP 200으로 받는다. 응답의 `items[].type`은 요청한 이름이 순서대로 붙을 뿐이며 유효성을 뜻하지 않는다.
- 유효한 차원의 값이 앞 칸부터 채워지고 무효한 이름은 값이 `null`이다. 그래서 유효한 차원이 뒤에 있으면 값이 앞 이름으로 당겨져 라벨이 어긋난다.
  - 예: `["country","trafficSource","sentiment","pageTechnology"]`를 보내자 `trafficSource` 칸에 sentiment 값(`no sentiment`)이, `sentiment` 칸에 pageTechnology 값(`Web`)이 들어왔다. `trafficSource`는 무효로 판단했다.
- 따라서 차원은 **단독 또는 확인된 것끼리만** 그룹화하고, 새 이름은 한 번에 하나씩 값을 확인한다.

### 확인된 차원

| 이름 | 예시 값 | 근거 |
| --- | --- | --- |
| `url` | `https://www.koreatimes.co.kr/...` | 값 확인 |
| `title` | 기사 제목 | 값 확인 |
| `section` | `business`, `entertainment`, `southkorea` | 값 확인 (id는 숫자) |
| `visitorFrequency` | `New` | 값 확인 |
| `folder` | `/business/` | 값 확인 |
| `host` | `www.koreatimes.co.kr` | 값 확인 |
| `uri` | `/business/companies/...` | 값 확인 |
| `pageTechnology` | `Web`, `AMP` | 값 확인 |
| `country` | `United States`, `Singapore`, `South Korea` | 값 확인 |
| `sentiment` | `no sentiment` | 값 확인 |
| `source` | `Google`(333,726), `dark social`(134,302), `Google Discover`(74,324) | 단독 조회로 확인. 유입 소스 차원 역할 |
| `customerLoyalty` | `0` 한 그룹(729,019, 전체 순방문자) | 단독 조회로 이름은 확인. 모든 사용자가 `0`이라 분석 가치는 없음(이커머스 미사용으로 추정) |

### 유효하지만 미확정

| 이름 | 내용 |
| --- | --- |
| `brand`, `product`, `sku` | 이전 묶음 결과상 유효하지 않은 것으로 보이나 단독 조회는 하지 않았다 |
| `tag`, `topic` | 서버가 "Cannot combine tag and topic groupby in the same query"(HTTP 400)로 응답하여 이름은 유효. 같은 쿼리에서 함께 쓸 수 없다 |

### 권한 제한

- `mediumInternal`, `userType`, `visitorLoyalty`, `consentChoice`, `os`, `browser`, `browserVersion`, `trafficTerm`, `trafficContent`, `city` 묶음과 `region`, `subregion`, `continent`, `networkDomain`, `visibility`, `contentType`, `publishDate`, `articlePublishDate`, `authors`, `author` 묶음은 각각 HTTP 403 `You do not have access to rawData`였다. 각 묶음에 `rawData` 권한이 필요한 차원이 최소 1개 있으며 어느 것인지는 가려내지 못했다.
- 디바이스·방문자 유형·브라우저·도시 같은 방문자 세부 차원은 이 권한 뒤에 있을 가능성이 높다.

### 무효로 보이는 이름

`originalUrl`, `rfvRecency`, `rfvFrequency`, `rfvVolume`, `adType`, `mediaTitle`, `mediaProvider`, `hasMedia`, `hasAudio`, `hasVideo`, `isLive`, `searchType`(이 묶음은 HTTP 204), `searchKeyword`, `isSyndicated`, `deviceCategory`, `device`, `userJourney`, `trafficCampaign`, `trafficMedium`, `trafficSource`. 이름이 틀린 것이지 기능이 없다는 뜻은 아니다. 일부는 위 `rawData` 묶음과 이름 형태가 다를 수 있어 Explore에서 확인한다.

### 필터

- 개발 가이드가 `source`, `section`, `mediumInternal`, `userType`, `publishDate` 필터를 사용한다고 안내한다.
- `country`, `source` 필터는 8절에서 실측했다. 필터 값은 응답 `items`의 `value`가 아니라 `id`를 쓴다(`country`는 GeoNames ID).

## 6. Marfeel Explore에서 확인한 화면 이름과 API 필드 (2026-10-22, 사용자 제공)

Explore 화면에서 쿼리를 만들고 "Get JSON API"로 복사한 본문 기준이다. 이 표는 Explore가 생성한 이름이며, 이 계정의 API 호출로 허용 여부를 확인한 결과는 아래 "이 계정 검증 결과"에 적었다.

### 이 계정 검증 결과 (2026-10-22, 최근 7일 기준)

대응표의 지표·차원 중 `uniqueSessions`, `city`처럼 Explore에서 Enterprise 표시가 붙은 항목은 제외하고 나머지를 API로 호출했다. 모두 HTTP 200이었고 권한 오류(403)는 없었다.

| 지표 | 값 | 비고 |
| --- | --- | --- |
| `totalDuration` | 112,979,191.87 | 총 읽기 시간 |
| `averageRFV` | 11.65 | |
| `adsImpressions` | 1,327,229 | |
| `searchImpressions` | 4,598,743 | `section`(기사 차원) 기준 조회 |
| `searchClicks` | 59,442 | `section`(기사 차원) 기준 조회 |
| `CPM` | 0 | 이름은 유효, 수익 데이터 없음 (`revenueTotal`도 0) |

| 차원 | 값 예시 |
| --- | --- |
| `deviceType` | `desktop`, `mobile`, `tablet` |
| `medium` | `search`, `social`, `direct` |
| `author` | `Yonhap`, `The Korea Times` 등 (id는 숫자) |
| `contentByAge` | `Evergreen`, `New`, `Not editorial` |
| `publishDate` | `2026-10-16T00:00:00` 등. 발행일 정보가 없는 기사는 `1970-01-01`, 값 `-` |

| 화면 이름 | API 필드 | 종류 |
| --- | --- | --- |
| Unique users | `uniqueUsers` | 지표 |
| Pageviews total | `pageViewsTotal` | 지표 |
| Total reading duration | `totalDuration` | 지표 |
| Average RFV | `averageRFV` | 지표 |
| Ad Impressions | `adsImpressions` | 지표 |
| CPM | `CPM` | 지표 |
| Total Ads Revenue | `revenueTotal` | 지표 |
| Google Search Impressions | `searchImpressions` | 지표 |
| Google Search Clicks | `searchClicks` | 지표 |
| Device category | `deviceType` | 차원 |
| Traffic medium | `medium` | 차원 |
| Author | `author` | 차원 |
| Content Type | `contentByAge` | 차원 (값: New / Evergreen / Not editorial, 기사 나이 기준) |
| Article publish date | `publishDate` | 차원 |

화면 이름을 camelCase로 바꾼 추측이 자주 틀린 이유다(예: `totalReadingDuration`→실제 `totalDuration`, `adImpressions`→실제 `adsImpressions`, `deviceCategory`→실제 `deviceType`, `trafficMedium`→실제 `medium`).

### 앱 카탈로그 지표 27개 검증 결과 (2026-10-22, 최근 7일, `section` 기준)

사용자가 Marfeel 앱의 지표 카탈로그에서 찾은 ID(지표 41개, 차원 8개) 중 아직 검증하지 않은 지표 27개를 API로 호출했다. 차원 8개(`deviceType`, `medium`, `source`, `author`, `section`, `contentByAge`, `publishDate`, `country`)는 앞서 모두 검증했다. 27개 모두 HTTP 200이었고 권한 오류는 없었다.

**값이 나오는 지표 (15개)**

| 지표 | 값 | 비고 |
| --- | --- | --- |
| `pageViewsPerArticle` | 13.21 | 기사당 페이지뷰 |
| `uniqueUsersPerArticle` | 8.59 | 기사당 순방문자 |
| `pageViewsPerUser` | 1.54 | |
| `averageDurationPerUser` | 153.73 | 단위는 초로 추정(`totalDuration`÷`uniqueUsers`와 일치) |
| `averageDurationPerPage` | 99.92 | 위와 같음 |
| `totalEngagementTime` | 32,314,407.02 | |
| `averageEngagementTimePerUser` | 43.97 | |
| `averageEngagementTimePerPage` | 28.58 | |
| `averageScroll` | 28.53 | |
| `cumulativeRFV` | 13,169,219.81 | |
| `searchCTR` | 1.31 | 단위는 %로 추정 |
| `discoverCTR` | 2.73 | 단위는 %로 추정 |
| `googleNewsImpressions` | 88,377 | |
| `googleNewsClicks` | 1,839 | |
| `googleNewsCTR` | 2.08 | 단위는 %로 추정 |

`pageViewsPerArticle`·`uniqueUsersPerArticle`의 분모는 `newArticles`(신규 발행 수)가 아니라 기간 중 조회된 기사 수로 보인다. 자세한 근거는 [수집 쿼리 README](marfeel-queries/README.md)의 사용 시 주의를 참고한다.

**이름은 유효하나 값이 0인 지표 (12개)**: `revenueTotalPerArticle`, `RPM`, `ARPU`(수익 데이터 없음, `revenueTotal`·`CPM`과 같은 원인으로 보임), `googleNewsPosition`, `discoverMonitoring::visibility`, `discoverMonitoring::timeOnFeed`, `discoverMonitoring::articleCount`, `socialMonitoring::interactions`, `socialMonitoring::posts`, `socialMonitoring::shares`, `socialMonitoring::comments`, `socialMonitoring::reactions`.

- Discover Monitoring과 Social Monitoring 지표는 ID에 `접두어::이름` 형식이 붙는다. 값이 0인 것은 해당 모니터링 기능이 이 사이트에 활성화되어 있지 않기 때문일 수 있으나 확인하지 못했다. 앞서 확인한 `socialPosts`(325)와 `socialMonitoring::posts`(0)는 서로 다른 지표다.
- 41개 중 `New original articles`, `Unique sessions`, `City`는 Enterprise 전용이라 제외되었다.

### 요청 설계 권고

사용자가 조립한 단일 쿼리(차원 8개 × 지표 41개)를 한 번에 호출하는 것은 권장하지 않는다. 차원이 겹쳐 그룹이 잘게 쪼개지고(추정), Search·Discover·News 지표는 방문자 차원과 섞이면 0이 되기 때문이다. 목적별로 나눈다.

| 목적 | 차원 | 지표 |
| --- | --- | --- |
| 편집 성과 | `section`, `author` | 기사당 지표, 체류·참여 지표 |
| 유입 | `source`, `country`, `deviceType` | 사용자 지표, 광고 지표 |
| Google | `publishDate`, `author` | Search·Discover·News 지표 |

### Explore가 보여준 요청 형식

- `dates`에 프리셋을 쓸 수 있다: `{"period":"preset","preset":"last30days"}`.
- `granularity`에 `"none"`을 쓸 수 있고, `"discardOld":"false"` 필드가 있다.
- 인증 헤더와 엔드포인트는 이미 확인된 `Authorization: Bearer {token}`, `POST https://api.newsroom.bi/api/dashboard/query`를 따른다.

### 쿼리 설계상 주의 (사용자 관찰, 추정 포함)

- Google Search 지표(`searchImpressions`, `searchClicks`)는 방문자 차원 `medium`과 함께 쓰면 모든 그룹에서 0이 된다(2026-10-22 직접 확인, `search`·`social`·`direct`·`redirect`·`referral` 전부 0).
- 반면 `deviceType`과는 값이 나온다. 합계가 기사 차원(`section`) 조회와 같다(노출 4,598,743, 클릭 59,442). 이때 값 라벨은 `Desktop` / `Mobile` / `Tablet`으로, 방문자 쪽 `desktop` / `mobile` / `tablet`과 표기가 달라 Search Console 자체의 기기 구분으로 보인다. 방문자 지표(`uniqueUsers`)와 같은 쿼리에 넣어도 그룹 키가 달라 같은 기기로 합쳐 해석하면 안 된다.
- 다른 방문자 차원(`country`, `source` 등)과의 조합은 확인하지 않았다. Search Console 데이터는 기사·날짜 단위로 붙기 때문으로 추정하며, Search 지표는 `section`, `author`, `publishDate` 같은 기사 차원으로 별도 쿼리를 만든다.
- 차원 5개를 한 쿼리에 넣으면 조합 수가 크게 늘고 `limit`(최대 500)에서 잘린다. 목적별로 차원 1~2개씩 나눠 쿼리한다.

## 7. 공식 문서상 지표·차원 범주 (참고)

공식 사전에 나열된 범주다. 이 계정에서 사용 가능한지는 2~5절의 실측 결과가 우선한다. (6절은 Explore가 생성한 이름 목록이다.)

| 영역 | 지표 | 차원 |
| --- | --- | --- |
| General | 순방문자, 페이지뷰, 신규 기사, 세션 | Folder, Host, URL, URI, 페이지 기술 |
| Engagement | RFV, 읽기·참여 시간, 스크롤, PV/세션, 세션/사용자 | RFV recency·frequency·volume |
| Advertising | 광고 노출, CPM, 수익, ARPU, RPM | Ad type |
| Media | 재생, 노출, 재생 시간 | 제목, 제공자 |
| Google Search Console | 노출, 클릭, 순위, CTR, Discover | 검색 유형, 키워드 |
| Page Speed | LCP, CLS, FID, INP, TBT, TTFB | – |
| Recirculation | 노출·열림·전환율 | 모듈, 출발·도착 섹션 |
| Visitor / Geo | – | 국가, 기기, 유입 경로·매체, 로열티, OS, 브라우저, 도시 |
| Editorial | – | 저자, 섹션, 토픽, 발행일, 콘텐츠 유형 |

출처: [Metrics and dimensions glossary](https://www.marfeel.com/docs/analytics/metrics-dimensions/metrics-dimensions-glossary), [Reporting API developer guide](https://www.marfeel.com/docs/analytics/api-docs/marfeel-reporting-api-developer-guide). 사전 페이지에는 API 필드명이 없으며, 범주별 상세 문서에 개별 정의가 있다.

## 8. 실시간 기사별 조회·국가 분리·호출 한도·경쟁사 (2026-10-22 실측)

해외 통신 기사 선별 파이프라인의 [VERIFY] 항목을 확인하려고 실측했다. 2026-10-22 10:59~11:17(KST)에 18회 호출했다. 17회는 65초 간격을 두었고, 1회는 한도 확인용으로 간격 없이 보냈다. 원본 응답은 `data/probes/out/`에 있으며 저장소에는 포함하지 않는다.

### 판정

| [VERIFY] 항목 | 판정 | 근거 |
| --- | --- | --- |
| 기사별 실시간 조회수 | **가능** | `granularity: realtime` + `groupBy: ["url"]`로 PV·UV를 기사별로 받는다 |
| 5분 주기 | **가능** | 5분·1분 단위를 모두 제공한다. 1분 단위로 보면 지연은 약 1분이다 |
| 국가별 분리 | **가능 (필터 방식)** | `country` 필터의 `eq`/`neq`에 GeoNames ID를 넣는다. 한국은 `1835841` |
| 호출 한도 | **분당 1회 (실측 확인)** | 60초 안의 두 번째 호출은 HTTP 429였다. 한도 헤더는 없다 |
| 유입 경로별 데이터 | **가능** | `source`는 실시간에서도 그룹화와 필터로 모두 동작한다 |
| 경쟁사 모니터링 | **API로 불가, 담당자 확인 필요** | 아래 "경쟁사 모니터링" 참고 |

### 실시간 조회

- 요청은 `"dates": {"last": {"number": 30, "dimension": "minute"}}`, `"granularity": "realtime"`으로 보낸다. 응답의 `granularity`는 `minutely_5`(기본)이고, `availableGranularities`는 `["minutely_1", "minutely_5"]`다.
- 30분을 요청하면 5분 구간 6개가 온다. `actualData.data[*].label`은 구간 시작 시각(KST, 예: `2026-10-22 10:55`)이다. 마지막 구간은 진행 중인 구간이다. 11:12:41 호출의 마지막 구간은 `11:10`이었다.
- 지연: 11:00:29에 `minutely_1`로 10분을 요청하니 마지막 구간이 `10:59`였다. 집계 지연은 약 1분 이내다.
- 갱신: 11:06:02에 같은 요청을 다시 보내니 구간 범위가 10:30~10:55에서 10:40~11:05로 밀렸다. 30분을 요청했는데 이때는 `10:40`부터 6개 구간이 왔다. 구간 경계는 정각 기준 5분 단위로 맞춰진다.
- 조회 가능한 기간:
  - 180분 요청은 `minutely_5`로 36개 구간(08:20~11:15)이 왔다. 이때 `availableGranularities`는 `["minutely_5", "hourly"]`다. 이 길이에서는 `minutely_1`이 빠진다.
  - `last 3 day`에 `minutely_5`를 요청하면 `hourly`로 바뀌어 응답한다. 이때 기간은 10-19 00:00~10-21 23:00이고 **오늘이 빠진다**. 오늘 데이터는 `minute` 단위 기간으로 받는다.
- 행 구성:
  - `url` 그룹에는 홈페이지(`https://www.koreatimes.co.kr`)가 1위로 섞인다. 기사만 쓰려면 경로로 걸러야 한다.
  - `pageViewsTotal`과 `uniqueUsers`를 함께 요청하면 지표마다 정렬된 결과 객체가 따로 온다.
- 응답은 1~3초 안에 왔다.

### 국가 분리

- 필터 값으로 국가명을 쓰면 안 된다. `{"filter":"country","op":"eq","value":["South Korea"]}`는 **HTTP 204**였다.
- 응답 `items`의 `id`(GeoNames ID)를 써야 한다.
  - `{"filter":"country","op":"eq","value":["1835841"]}`(국내)는 200이었다. 30분 PV 1,275, UV 597.
  - `{"filter":"country","op":"neq","value":["1835841"]}`(해외)는 200이었다. 30분 PV 2,670, UV 2,167.
  - 이 시간대 PV의 약 1/3이 국내, 2/3가 해외였다.
- 국내와 해외 상위 기사는 다르다. 국내 2위는 한국은행 금리 기사였고, 해외 2위는 K-pop 기사였다.
- `groupBy: ["url", "country"]`는 30분만으로도 500행 상한에 닿았다. 기사 319개 × 국가 48개였다. 국가 분리는 그룹화가 아니라 국내·해외 필터 2회로 한다.
- 주요 ID 예: South Korea `1835841`. 다른 국가 ID는 `groupBy: ["country"]` 응답의 `items[].id`에서 얻는다.

### 호출 한도

- 정상 호출 직후(같은 초) 두 번째 호출을 보내면 **HTTP 429**가 오고 본문은 `{"msg":"Exceeded rate limit"}`(29바이트)다.
- `Retry-After`, `X-RateLimit-*` 같은 한도 헤더는 200·429 응답 어디에도 없다. 남은 횟수를 알 수 없으므로 클라이언트가 직접 간격을 관리한다.
- 공식 가이드상 한도는 계정 전체가 공유한다. 요금표에는 Pro 기준 "1 request per minute included", 동시 요청 추가는 $599로 나온다. 더 높은 한도는 계정 관리자에게 문의한다.
- 5분 주기로 쓸 수 있는 호출은 최대 5회다. 같은 계정의 다른 작업(Explore 화면 사용 여부는 미확인, 정기 수집 스크립트)도 이 예산을 함께 쓴다.

### 유입 경로

- 실시간 30분 `groupBy: ["source"]` 상위는 `dark social` 909, `Google` 869, `direct` 610, `Google Discover` 459, `bookmark` 389 순이다.
- `{"filter":"source","op":"eq","value":["Google Discover"]}` + `groupBy: ["url"]`은 200으로 기사별 Discover 유입 PV를 준다. `source`는 `id`와 `value`가 같다.

### 경쟁사 모니터링 (koreaherald.com)

- API 실측 결과:
  - `groupBy: ["host"]`(7일)로 조회하면 `www.koreatimes.co.kr`과 PV 101의 관련 없는 호스트 하나만 나온다. 다른 매체 데이터는 없다.
  - `{"filter":"host","op":"like","value":["koreaherald"]}`는 200이었다. 하지만 합계(1,130,752)가 필터 없는 조회와 같았다. **필터가 조용히 무시된 것이다.** 필터가 틀려도 오류가 나지 않으므로, 필터를 쓸 때마다 합계가 줄었는지로 효과를 확인해야 한다.
  - `discoverMonitoring::visibility`, `discoverMonitoring::articleCount`, `socialMonitoring::posts`, `googleNewsPosition`은 `url` 그룹(7일)과 `host` 그룹(30일) 모두 **HTTP 204**였다.
- 공식 문서 (2026-10-22 조사):
  - 경쟁사 기능은 별도 제품 "Marfeel Monitoring"이다. Discover, Social, SERP 모니터링으로 구성된다. UI에서 host와 publisher 필터로 특정 경쟁사를 지정할 수 있다. 출처: [Marfeel Monitoring](https://www.marfeel.com/docs/monitoring/marfeel-monitoring-for-discover-and-social-trends), [Discover Monitoring](https://www.marfeel.com/docs/monitoring/discover-monitoring-doc/google-discover-monitoring-for-publishers)
  - 제공하는 값은 다음 두 가지뿐이고, 경쟁사의 페이지뷰는 주지 않는다. 출처: [Discover 가시성 점수](https://www.marfeel.com/docs/monitoring/discover-monitoring-doc/google-discover-monitoring-data-and-visibility-scores), [Social 지표](https://www.marfeel.com/docs/monitoring/social-monitoring-doc/social-monitoring-metrics-and-interaction-data)
    - Discover 피드를 수집해 계산한 가시성 점수. 조회수 대신 쓰는 근사 지표다.
    - 공개 소셜 게시물의 인터랙션
  - Reporting API 개발자 가이드에는 Monitoring 지표나 경쟁사를 지정하는 차원이 나오지 않는다. 요금표에도 Monitoring 가격이 없다.
- 결론: 이 계정의 Reporting API로는 경쟁사 데이터를 조회할 수 없다. 담당자에게 다음 두 가지를 확인한다.
  - Monitoring 제품을 계약했는지
  - 계약했다면 Monitoring UI의 쿼리를 API로 호출할 수 있는지. 브라우저 Network 패널의 요청으로 확인할 수 있다.
  - 확인 전까지 경쟁사 감점(`P_comp`)은 RSS 방식을 유지한다.

### 수집 서비스 설계에 넘길 제약

- 5분 주기 기본 호출은 국내 1회(`country eq 1835841`)와 해외 1회(`neq`)로 2회다. 남는 3회는 `source` 분리, 재시도, 다른 작업에 쓴다.
- 기사 수가 50~500개를 넘으면 `from`으로 페이지를 넘겨야 하고, 페이지마다 호출 1회를 쓴다.
- 기간은 `minute` 단위(예: 최근 30분)로 지정한다. `day` 단위는 오늘을 빼고 응답한다.
- 429가 오면 다음 분까지 기다린다. 헤더로 남은 횟수를 알 수 없어 호출 시각을 직접 기록한다. 기존 `scripts/marfeel_collect.py`의 상태 파일 방식이 이렇게 동작한다.
- 잘못된 지표, 차원, 필터 값은 오류 없이 무시되거나 204로 온다. 필터를 쓸 때는 합계 변화로 효과를 확인한다.
- 홈페이지 URL을 걸러야 한다.
