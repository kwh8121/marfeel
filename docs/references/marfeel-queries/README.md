# Marfeel 수집 쿼리

Reporting API(`POST https://api.newsroom.bi/api/dashboard/query`) 요청 본문 3종이다. 지표·차원 이름은 모두 이 계정에서 값이 나오는 것만 사용한다. 근거는 [수집 가능 데이터 범위](../marfeel-data-scope.md).

- 검증일: 2026-10-22. 세 파일 모두 HTTP 200으로 호출을 확인했다(대상: Korea Times, site 9291).
- 인증·호출 방법: [Marfeel API 레퍼런스](../Marfeel%20API-reference.md). 토큰은 파일에 넣지 않는다.

| 파일 | 목적 | 차원 | 정렬 | 지표 수 |
| --- | --- | --- | --- | --- |
| `01-editorial-performance.json` | 편집 성과 | `section`, `author` | `pageViewsTotal` | 11 |
| `02-acquisition.json` | 유입·광고 | `source`, `country` | `uniqueUsers` | 7 |
| `03-google-search-discover-news.json` | Google 검색·Discover·News | `publishDate`, `author` | `searchImpressions` | 10 |

## 사용 시 주의

- 기간은 모두 `last30days` 프리셋이다. 바꾸려면 `dates`를 `{"last":{"number":7,"dimension":"day"}}` 또는 `{"range":{"start":"YYYY-MM-DD","end":"YYYY-MM-DD"}}`로 교체한다.
- 호출 한도는 계정당 분당 1회이며 응답당 최대 500행이다. 세 쿼리를 이어서 호출할 때는 사이에 65초 이상 둔다. `limit`은 100이고, 더 필요하면 `from`으로 페이지를 넘긴다.
- `granularity`를 `none`으로 두어도 응답의 `granularity`는 `daily`로 표시된다. 응답 `actualData.data`는 일별 시계열이므로 기간 전체 값은 지표의 `total`을 쓴다. 중복 제거 지표(`uniqueUsers`)를 일별 값의 합으로 대체하지 않는다.
- 03번의 Search·Discover·News 지표는 `medium` 같은 방문자 차원과 섞으면 0이 되므로 방문자 차원을 추가하지 않는다. 기사 차원(`publishDate`, `author`, `section`)만 쓴다.
- 02번의 `country` 대신 `deviceType`을 쓰면 기기별 유입을 볼 수 있다. 차원은 2개 이하로 유지한다.
- 시간 지표는 초 단위, CTR은 % 단위로 추정한다(값의 크기 기준, 공식 문서에 명시 없음).
- `pageViewsPerArticle`·`uniqueUsersPerArticle`의 분모는 `newArticles`가 아니다. `newArticles`는 기간 중 신규 발행 수이고, 기사당 지표는 기간 중 조회된 기사(오래된 기사 포함) 수 기준으로 보인다(2026-10-22 01번 쿼리 결과로 확인: `southkorea`/`Yonhap`은 `newArticles` 330, 분모 약 5,337). 그래서 `PV ÷ newArticles`로 재계산하면 값이 다르다. 홈(`MAIN`)처럼 URL이 하나뿐인 그룹은 분모가 1이라 기사당 값이 합계와 같다. 분모가 정수가 아닌 그룹이 많아 일별 값의 평균일 수 있으나 정확한 정의는 확인하지 못했다.
- `author`에는 기자 이름 외에 매체 URL(`https://www.koreatimes.co.kr`)과 `KTimes` 같은 값이 섞여 있다.
