# Marfeel Reporting API — 수집 가능 데이터 범위

- 확인일: 2026-10-21
- 대상: Korea Times (site id 9291, 시간대 Asia/Seoul, 통화 USD), `.env`의 API 전용 계정(role `Engineering`)
- 근거: 실제 API 호출 결과 + 공식 문서. 인증·요청 명세는 [Marfeel API-reference.md](Marfeel%20API-reference.md)를 따른다.
- 비밀값(이메일·비밀번호·토큰)은 이 문서에 기록하지 않는다.

## 1. 요약

- 로그인(`POST /api/user/signin`)과 조회(`POST /api/dashboard/query`)가 모두 HTTP 200으로 성공했다.
- 호출 한도는 계정당 분당 1회, 응답당 최대 500행이다. 모든 탐색은 호출 사이에 65초를 두고 수행했다.
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

- 개발 가이드가 `source`, `section`, `mediumInternal`, `userType`, `publishDate` 필터를 사용한다고 안내한다. 이번에 필터 값은 실측하지 않았다.

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
