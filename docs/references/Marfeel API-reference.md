# Marfeel API 인증·연동 — 개발 에이전트 레퍼런스

## 1. 범위와 핵심 요약

Marfeel API는 Bearer 토큰 인증을 사용한다. API 전용 계정의 이메일·비밀번호로 로그인 요청을 보내 토큰을 발급받고, 이후 API 요청의 `Authorization` 헤더에 포함한다. 토큰은 생성 후 **최대 14일** 동안 유효하며, 만료 후 새로 발급해야 한다. [1]
이 노트는 앞서 작성한 인증 레퍼런스를 보존하고, 관련 Reporting API 개발 가이드를 직접 확인해 조회 명세와 운영 제한을 보완했다. 공식 문서의 명세와 일반적인 구현 권고를 구분한다. 코드의 자격 증명·토큰은 모두 자리표시자다.

## 2. 계정 사전 설정

| 항목 | 공식 문서의 요구·안내 사항 |
| --- | --- |
| API 권한 | 사용자 계정에 **API role**이 활성화되어 있어야 한다. |
| 이메일 | Analytics 요금제에 따른 요청 한도 관리를 위해 공용 이메일 계정 사용을 권고한다. |
| SSO 강제 조직 | API 인증용 비밀번호를 별도로 설정해야 한다. Compass 로그인 화면의 **Forgot your password** 기능을 사용한다. |
| SSO 강제 시 Admin 계정 | API 접근에 사용할 수 없다. API role을 가진 별도 전용 사용자를 생성해야 한다. |

위 계정 요건은 API 연동 전에 확인한다. [1]

## 3. 토큰 발급

| 항목 | 값 |
| --- | --- |
| 메서드 | `POST` |
| URL | `https://api.newsroom.bi/api/user/signin` |
| Content-Type | `application/json` |
| 요청 본문 | `email`, `password` |
| 응답에서 사용할 필드 | `token` |

이메일·비밀번호를 JSON 본문으로 전송하는 로그인 방식으로 토큰을 발급한다. [1]

```bash
curl --request POST \
  'https://api.newsroom.bi/api/user/signin' \
  --header 'Content-Type: application/json' \
  --data-raw '{
    "email": "compass.api@youraccount.com",
    "password": "REPLACE_WITH_API_PASSWORD"
  }'
```

원문의 응답에는 사용자 정보와 `token` 필드가 포함된다. 아래는 필요한 필드만 발췌한 예시다. [1]

```json
{
  "token": "REPLACE_WITH_ISSUED_TOKEN"
}
```

**구현 권고**

*   HTTP 요청 성공 여부와 응답 JSON 파싱 성공 여부를 확인한다.
    
*   `token`이 비어 있지 않은 문자열인지 확인한다.
    
*   로그인 응답 전체를 로그에 남기지 않는다.
    
*   다른 사용자 정보 필드에 불필요하게 의존하지 않는다.
    

## 4. API 요청 인증

보호된 API 요청에 다음 헤더를 전달한다. [1]

```http
Authorization: Bearer REPLACE_WITH_ISSUED_TOKEN
```

Reporting API 엔드포인트는 다음과 같다. [1]

```text
POST https://api.newsroom.bi/api/dashboard/query
```

인증 가이드에는 조회 요청 본문·응답 스키마가 없다. 실제 조회 구현에는 아래 관련 문서의 **Reporting API developer guide**를 함께 사용한다.

## 5. 토큰 수명과 갱신

*   토큰 유효기간은 생성 후 **최대 14일**이다.
    
*   유효한 토큰은 요청마다 재발급하지 않고 재사용할 수 있다.
    
*   유효기간이 지난 뒤에는 새 토큰을 생성해야 한다. [1]
    

인증 가이드에는 별도 refresh-token 엔드포인트나 refresh-token 흐름이 제시되어 있지 않다. 문서에 명시된 발급 경로는 `POST /api/user/signin`이다.
**구현 권고**

*   토큰과 발급 시각을 함께 관리한다.
    
*   ‘최대 14일’을 정확히 14일간의 유효성 보장으로 해석하지 않는다.
    
*   재발급 로직을 하나의 함수나 모듈로 분리한다.
    
*   동시 요청 시 토큰 재발급이 중복 실행되지 않도록 제어한다.
    
*   재인증 후 재시도 횟수를 제한해 무한 반복을 방지한다.
    
*   토큰 내부 구조를 추정해 만료 시각을 확정하지 않는다.
    

## 6. 개발 에이전트용 구현 흐름

다음은 공식 API 명세가 아닌 **구현 권고 흐름**이다.

```text
1. 보안 설정에서 API 전용 이메일·비밀번호를 읽는다.
2. 재사용 가능한 토큰이 있는지 확인한다.
3. 토큰이 없거나 갱신이 필요하면:
   POST /api/user/signin
   → 응답 검증
   → token 및 발급 시각 저장
4. API 요청에 Authorization: Bearer {token}을 추가한다.
5. 인증 오류가 발생하면:
   실제 오류 응답 명세에 따라 재인증 필요 여부를 판단한다.
   → 필요한 경우 제한적으로 토큰 재발급 및 재시도
6. 실패가 지속되면 오류를 호출자에게 전달한다.
```

## 7. 보안·운영 권고

다음은 공식 명세와 구분되는 일반적인 구현 권고다.

*   이메일·비밀번호·토큰을 소스 코드, 버전 관리 저장소, 노트에 저장하지 않는다.
    
*   환경변수나 시크릿 관리 시스템을 사용한다.
    
*   `Authorization` 헤더, 로그인 요청 본문, 토큰을 로그에서 마스킹한다.
    
*   인증 정보 처리는 가능한 한 신뢰할 수 있는 서버 환경에서 수행한다.
    
*   네트워크 타임아웃을 설정하고 재시도 횟수를 제한한다.
    
*   공용 API 계정을 사용하더라도 자격 증명의 접근 권한은 제한한다.
    

## 8. 관련 개발 가이드 확인으로 보완한 조회 명세

아래는 인증 가이드가 아닌 **Reporting API developer guide**를 직접 확인한 내용이다. 출처 URL은 10절에 수록했다.

### 요청 구성

`dates`, `filters`, `groupBy`, `metrics`, `order`는 필수 필드다. 빈 값을 허용하는 필드도 필드 자체를 생략해서는 안 된다. 특히 `metrics`에는 최소 1개의 지표가 필요하다.

```json
{
  "dates": {
    "last": {
      "number": 7,
      "dimension": "day"
    }
  },
  "filters": [],
  "groupBy": ["url"],
  "metrics": ["uniqueUsers"],
  "order": {
    "metric": "uniqueUsers",
    "sort": "DESC"
  },
  "granularity": "daily",
  "limit": 100,
  "from": 0
}
```

위 예시는 가이드의 필드 구성을 이용한 최근 7일 URL별 순방문자 조회 요청 본문이다. 전송 시 `Content-Type: application/json`과 Bearer 인증 헤더를 함께 설정한다.
| 항목 | 개발 가이드 내용 |
| --- | --- |
| 지표 | `metrics` 배열. 예: `uniqueUsers`, `pageViewsTotal`, `revenueTotal` |
| 그룹화 | `groupBy` 배열. 예: `url`, `visitorFrequency` |
| 상대 기간 | `dates.last.number`와 `dates.last.dimension` |
| 절대 기간 | `dates.range.start`와 `dates.range.end` |
| 시간 집계 단위 | `realtime`, `hourly`, `daily`, `weekly`, `monthly` |
| 정렬 | `order.metric`와 `order.sort`(`ASC` 또는 `DESC`) |
| 페이지네이션 | `limit`은 반환 행 수, `from`은 오프셋. 최대 500행 |

### 필터

필터 객체는 `filter`, `op`, `value`로 구성된다. `value`는 배열이다. 하나의 필터 안에서 여러 값은 OR로, 여러 필터 사이는 AND로 결합된다.
지원 연산자: `eq`(같음), `neq`(다름), `like`(포함), `nlike`(미포함), `gt`(초과), `lt`(미만).

### 응답 구조

복수 지표 요청 시 지표별 결과 객체의 배열을 반환한다. 문서 예시에는 `metric`, `total`, `granularity`, `availableGranularities`, `actualData`, `compareData`가 나온다. `actualData.values`에는 그룹별 키와 설명이, `actualData.data`에는 해당 키를 사용하는 시계열 데이터가 제시된다.
**구현 권고:** 응답의 동적 키를 하드코딩하지 말고 `values`와 `data` 사이의 매핑을 이용한다. 순방문자 등 중복 제거 지표의 전체 합계를 시간 버킷의 단순 합산으로 대체하지 않는다.

### 호출 제한과 오류

개발 가이드는 **계정당 분당 1회 요청, 응답당 최대 500행**을 안내한다. 계정 내 모든 사용자와 자동화 작업이 할당량을 공유한다. HTTP 429 발생 시 대기 후 재시도하며, 더 높은 한도가 필요하면 계정 관리자(account manager)에게 문의하도록 안내한다.
**구현 권고:** API 전용 사용자를 생성해도 계정 전체 할당량이 분리된다고 가정하지 않는다. 계정 내 작업 간 호출 스케줄을 조율한다. 실제 계약·계정에 별도 한도가 적용되는지는 운영 전 확인한다.

### 복잡한 쿼리 작성

가이드는 Marfeel Explore에서 쿼리를 구성한 뒤 다음 방법으로 실제 요청을 복사하도록 안내한다.

1.  Explore의 **Get JSON API**에서 요청 본문 복사.
    
2.  브라우저 개발자 도구의 Network 패널에서 `/api/dashboard/query` 요청 본문 확인.
    

## 9. 추가 확인이 필요한 미명시 사항

다음은 확인한 문서만으로 확정할 수 없으므로 임의로 가정하지 않는다.

*   인증 관련 HTTP 상태 코드별 의미와 오류 응답 구조.
    
*   정확한 토큰 만료 시각 제공 여부, 조기 무효화·폐기 방식.
    
*   새 토큰 발급 시 기존 토큰의 유효성 유지 여부.
    
*   재시도 가능한 오류의 전체 목록, 권장 대기 시간 및 관련 응답 헤더.
    
*   날짜 경계의 포함 여부와 시간대 처리의 상세 정책.
    

## 10. 공식 문서 및 관련 주소

### [1] Marfeel API authentication with bearer tokens — 기준 문서

[https://www.marfeel.com/docs/analytics/api-docs/marfeel-api-authentication-with-bearer-tokens](https://www.marfeel.com/docs/analytics/api-docs/marfeel-api-authentication-with-bearer-tokens)
API role·SSO 계정 요건, 로그인 기반 토큰 발급, Authorization 헤더, 최대 14일의 토큰 수명을 설명한다. 본문 직접 확인.

### Marfeel Reporting API developer guide — 조회 구현의 핵심 문서

[https://www.marfeel.com/docs/analytics/api-docs/marfeel-reporting-api-developer-guide](https://www.marfeel.com/docs/analytics/api-docs/marfeel-reporting-api-developer-guide)
조회 요청 필수 필드, 지표·차원, 필터, 정렬, 날짜 범위, 시간 집계 단위, 페이지네이션, 응답 예시, 쿼리 추출 방법, 호출 제한과 오류 대응을 설명한다. 본문 직접 확인. 인증 구현 후 이어서 참조할 문서다.

### Metrics and dimensions glossary — 지표·차원 사전

[https://www.marfeel.com/docs/analytics/metrics-dimensions/metrics-dimensions-glossary](https://www.marfeel.com/docs/analytics/metrics-dimensions/metrics-dimensions-glossary)
Reporting API 개발 가이드가 사용 가능한 지표·차원 목록으로 연결하는 공식 문서다. `metrics`, `groupBy`, 필터 항목 선정 시 참조한다. 이번 작업에서는 링크를 개발 가이드에서 확인했으며 대상 문서 본문은 별도로 열람하지 않았다.

### Marfeel Explore — 쿼리 생성·요청 본문 추출 도구

[https://hub.marfeel.com/insights/explore](https://hub.marfeel.com/insights/explore)
개발 가이드가 안내하는 시각적 쿼리 구성 도구다. Get JSON API 또는 브라우저 Network 패널을 이용해 요청을 복사하는 데 사용한다. 이번 작업에서는 로그인 후 화면을 직접 확인하지 않았다.

### Marfeel Google Sheets Add-On setup and usage guide — 스프레드시트 연동 참고

[https://www.marfeel.com/docs/analytics/data-exports/marfeel-google-sheets-add-on-setup-and-usage-guide](https://www.marfeel.com/docs/analytics/data-exports/marfeel-google-sheets-add-on-setup-and-usage-guide)
Reporting API 개발 가이드가 Google Sheets 기반 연동 작업에 연결하는 공식 안내 문서다. 직접 API 클라이언트 외의 스프레드시트 연동 방식을 검토할 때 참고한다. 링크는 개발 가이드에서 확인했으며 대상 문서 본문은 별도로 열람하지 않았다.