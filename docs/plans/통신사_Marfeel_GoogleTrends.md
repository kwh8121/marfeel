# 인수인계 r9 — §5.5④ 개정 초안: 추천 점수 3단계 우선순위

*   기준 문서: `2026-10-12-wire-desk-poc-handoff-v2-r8.md` (file_id: 0d467666-c8f9-43aa-a627-bd5a96f3dcbc)
    
*   위치: r8의 §5.5는 "처리 로직" 전체(⓪~⑩)이며, 점수 산정은 **§5.5④**(r8 497~516행)에 있다. 이 초안은 §5.5 번호를 바꾸지 않고 **§5.5④에 "④-2 관심도 가산" 소절을 추가**하는 개정안이다.
    
*   상태: 초안 r9.1 (승인 전). 상한값·게이트 값은 출발값이며 측정 후 확정한다.
    
*   참조 문서: `marfeel-data-scope.md` §8 (2026-10-22 실측), `2026-10-22-wire-desk-marfeel-collect-plan.md`
    

### r9.1 변경 요약 (검증 결과 반영)

| # | 변경 | 이유 |
| --- | --- | --- |
| C-1 | boost 범위를 1.00~1.55에서 **1.00~1.45**로 정정. Trends 상한 출발값을 0.15에서 **0.10**으로 낮춤 | 기존 식의 실제 최대값은 1.475였다(1.55는 계산 오류). Trends 접근 방식이 확인되지 않음 |
| C-2 | 신규 worker 레인 `interest`를 삭제하고 **jobs 레인 하위 작업**으로 처리 | r8 원칙 "worker 1개 프로세스, 3개 레인"(238행)과 수집 계획(poller는 jobs 레인, worker 레인 3개 유지)이 충돌함 |
| C-3 | 6시간 창을 **30분 경계 정렬 스냅샷 12개 합산**으로 정의 | 수집은 5분마다 30분 창을 조회한다. 스냅샷을 그대로 더하면 같은 조회가 약 6배로 중복 계산됨 |
| C-4 | M에 **평균 보정**(축소 추정)과 **절대 트래픽 보정**을 추가하고, 백분위 기준 분포를 명시 | 기사 1건짜리 개체의 과대평가, 상위 200행으로 잘린 목록의 상향 편향, 새벽 시간대의 과도한 가산을 막기 위함 |
| C-5 | PoC의 M 입력을 `fixtures/marfeel/recordings`로 재사용 | 수집 계획의 녹화 JSONL과 중복되지 않게 함 |
| C-6 | Marfeel 호출 조건·세그먼트 분리 방식을 실측값으로 확정 | data-scope §8 실측 결과 |
| C-7 | 계약 검사 3건 추가, G7에 게이트 영향 건수 보고 추가 | 상한 위반·중복 집계·게이트 동작을 자동으로 확인하기 위함 |

* * *

## 0. 개정 전제와 범위 충돌 (승인 필요)

| # | r8 근거 | 충돌 내용 | r9 처리안 (권고) |
| --- | --- | --- | --- |
| S-1 | §4.2 범위 밖 (323행): "Google Trends 신호" | Trends는 PoC 범위 밖으로 명시돼 있음 | §4.2에서 "Google Trends 신호"를 "**Google Trends 실데이터 연동**"으로 좁히고, PoC에는 **가산 구조 + 픽스처 신호**만 포함 |
| S-2 | §4.2 (323·325행): 실제 Herb 호출·S1 Shadow 범위 밖 | PoC는 합성 픽스처 + 가상 Clock 재생이라 실시간 Marfeel·Trends 값과 시간축이 맞지 않음. 녹화본을 재사용해도 통신 픽스처와 시간축이 다르므로 개체가 겹치는 것은 우연일 뿐임 | PoC: M은 `fixtures/marfeel/recordings`(수집 계획 Task 7 녹화), T는 `fixtures/interest/trends/*.jsonl`(합성)로 구조·계약만 검증. **실효성 검증은 S1 Shadow 계획 문서로 이관** |
| S-3 | r8 전체 | Marfeel 신호에 대한 정의 없음 | 이 초안으로 신규 정의 |
| S-4 | r8 전체 | 경쟁사 감점 정의 없음 | 이번 개정에 넣지 않음. 수식에 `penalty` 자리(기본 1.0)만 둔다. Marfeel Reporting API로는 경쟁사 데이터를 받을 수 없으므로(data-scope §8) 정의한다면 RSS 방식 → 확인 필요 항목 |
| S-5 | §8 G7 ② (734행): `score / raw_score = 0.25 ± 1%` | 가산이 들어가면 이 판정식이 깨짐 | G7 ②는 **`decayed_score / raw_score`**로 판정식 변경 |
| S-6 (r9.1) | 238·313·413행: worker 1개 프로세스, 3개 레인 | r9 초판의 신규 `interest` 레인이 이 원칙과 충돌 | 레인을 추가하지 않는다. 수집과 개체값 계산은 jobs 레인 하위 작업(`MarfeelPoller` 재사용 + `TrendsPoller` 신규)으로 처리 |

운영 점수 기본값 원칙 (r6의 "언어권 정규화는 평가 비교값만" 방식과 같음): **PoC에서** `interest.enabled` **기본값은 false**. 평가 스크립트가 on/off 비교값을 산출한다.

* * *

## ④-1 기본 점수·감쇠 (r8 유지, 명칭만 정리)

```
raw_score      = 3 × agency_count + 1 × Σ_agency min(editions_per_agency, 3)
                 + 2 × min(growth_1h, 5) + w_u × urgency_bonus        (최대 67, r5)
decayed_score  = raw_score × 0.5 ^ ((Clock.now − last_item_at) / half_life)   (r6·r7)
```

*   r8의 `score`를 `decayed_score`로 이름을 바꾼다. `last_item_at` 규칙(499~501행)은 변경 없음.
    

## ④-2 관심도 가산 (r9 신규)

### (1) 우선순위 원칙

우선순위는 **각 신호가 최종 점수를 최대 얼마나 움직일 수 있는가**로 정의한다.
| 순위 | 신호 | 역할 | 최대 영향 (출발값) |
| --- | --- | --- | --- |
| 1 | 통신사 (`decayed_score`) | 점수의 바탕 | 100% |
| 2 | Marfeel `M` (0~1) | KT 독자 관심 보정 | +40% |
| 3 | Google Trends `T` (0~1) | 외부 검색 관심 보정 | +10% (M = 0일 때), M = 1이면 +5%로 축소 |

*   의도 (r9.1 명시): KT가 이미 다룬 주제(M 높음)가 신규 주제(M = 0, T만 있음)보다 크게 가산된다. 후속 보도와 KT 고정 관심 분야를 우선한다는 Marfeel의 역할과 맞추기 위한 것이다. 완전히 새로운 대형 속보는 통신사 점수(여러 통신사 동시 긴급 보도)가 잡는다.
    

### (2) 점수식

```
T_applied = T × (1 − 0.5 × M)                       # 관심 중복 계산 방지
boost     = 1 + cap_m × M + cap_t × T_applied        # 출발값 cap_m 0.40, cap_t 0.10
score     = decayed_score × boost × penalty          # penalty 기본 1.0 (S-4)

boost_max = 1 + cap_m + cap_t × (1 − 0.5)            # M = T = 1일 때
```

| cap_m / cap_t | M=0, T=1 | M=1, T=0 | M=1, T=1 (최대) |
| --- | --- | --- | --- |
| 0.40 / 0.10 (**출발값**) | 1.10 | 1.40 | **1.45** |
| 0.40 / 0.15 (r9 초판) | 1.15 | 1.40 | 1.475 (초판의 1.55는 오류) |
| 0.30 / 0.10 | 1.10 | 1.30 | 1.35 |
| 0.50 / 0.20 | 1.20 | 1.50 | 1.60 |

*   **순위 역전 한계**: 출발값 기준 boost 최대값은 1.45다. 같은 목록 안에서 `decayed_score` 차이가 45% 이상인 두 사안의 순위는 관심도 신호로 바뀌지 않는다. 예: 30점 사안이 넘을 수 있는 것은 43.5점 미만 사안까지다.
    
*   가산은 `korea_related` 판정과 목록 배정(한국 관련 1~10 / 국제 11~20)에 영향을 주지 않는다. 목록 분리(r8)는 그대로다.
    

### (3) 후보 게이트

*   목록별로 `decayed_score` 상위 **40건**(설정값 `gate_top_n`) 안의 사안에만 boost를 적용한다. 나머지는 boost = 1.
    
*   목적: 통신사 보도가 약한 사안이 관심도만으로 추천에 진입하는 것을 막는다(1순위 보장).
    
*   게이트 밖 사안은 상위 10건에 오를 수 없다. boost가 1 이상인 사안이 이미 40건 위에 있기 때문이다.
    
*   (r9.1) 게이트가 실제로 순위를 바꾸는 경우는 게이트 밖 1위 사안의 `decayed_score`가 목록 10위의 약 69%(1/1.45)를 넘을 때뿐이다. PoC 픽스처는 라벨 사안 규모가 작아서 목록당 40건 게이트가 거의 작동하지 않을 수 있다 [VERIFY]. 그래서 G7 ⑥에 "게이트로 인해 상위 10건 구성이 바뀐 건수"를 보고하도록 한다.
    

### (4) 신호 정의

**M — Marfeel (KT 발행 기사 반응의 개체 단위 이전)**

0.  **수집 (r9.1, 실측 반영)**: 수집 계획의 `MarfeelPoller`를 그대로 쓴다. 5분 주기(+60초 오프셋), `realtime`·30분 창, `groupBy: [url, title]`, PV 내림차순, `limit` 200(최대 500)이다. 세그먼트는 그룹화가 아니라 `country` 필터 2회 호출로 나눈다: 국내 = `eq 1835841`, 해외 = `neq 1835841`. 호출 한도는 분당 1회이고 계정 전체가 공유하므로 호출 간격을 65초 이상 둔다.
    
1.  KT 발행 기사(`kt_articles`)에서 개체를 추출한다. 결정적 사전 매칭을 쓴다(`interest_entities.yaml`, `korea_terms.yaml`과 같은 매칭 규칙: 영문은 단어 경계·대소문자 무시, 국문은 부분 문자열). LLM 추출은 PoC에 넣지 않는다(r8 원칙 28과 동일).
    *   (r9.1) **PoC는 제목만** 쓴다. Marfeel 수집값은 `url`·`title`뿐이다. 첫 문단은 출처(KT RSS 또는 CMS)가 확정된 뒤 추가한다 [VERIFY].
        
    *   해외 세그먼트 행에 제목이 없으면 URL로 `kt_articles`(또는 국내 세그먼트의 제목)와 연결한다.
        
2.  **6시간 창 집계 (r9.1)**: 최근 6시간 안에서 30분 경계(:00, :30 KST, 오프셋 허용)에 끝나는 `ok` 스냅샷 12개만 URL별로 더한다. 5분 주기 스냅샷을 모두 더하지 않는다(창이 겹쳐 약 6배 중복).
    *   경계 스냅샷이 실패(`rate_limited` 등)했으면 ±5분 안의 `ok` 스냅샷으로 대체하고 `substituted` 건수를 기록한다. 대체할 스냅샷도 없으면 그 칸은 비워 두고 `missing_slots`를 기록한다.
        
    *   대안(S1 비교값): 30분 창 + 지수 가중(EMA, 반감기 2시간). 360분 창을 직접 조회하는 방식은 실측 범위(180분) 밖이라 쓰지 않는다 [VERIFY].
        
3.  개체별 **보정 평균 조회**를 세그먼트별로 계산한다. 총조회수는 쓰지 않는다(기사 수 편향).
    
    ```
    adj_mean(e) = (Σ PV(e의 기사) + k × μ_seg) / (n(e) + k)     # k = 2 (출발값)
    μ_seg       = 같은 창·세그먼트의 기사당 평균 PV
    ```
    
    *   목적: 기사 1건짜리 개체의 과대평가와, 상위 200행만 수집해 생기는 상향 편향을 줄인다. 수집 계획 T0-3에서 200위 PV가 1위의 1% 이상이면 `limit` 500으로 올린다.
        
4.  범용 개체(최근 7일 KT 기사 중 20% 이상에 등장, 설정값)는 가중치를 0.2로 낮춘다(예: US, Korea).
    
5.  사안 개체(대표 판 제목 + 첫 문단, 같은 사전)와 겹치는 개체 값 중 최대값을 사안 값으로 한다.
    
6.  **정규화 (r9.1 명시)**: 같은 창·세그먼트에서 `adj_mean × 가중치 > 0`인 **개체 값 분포** 안의 백분위로 0~1 정규화한다. 개체가 5개 미만이면 그 세그먼트의 값은 0으로 둔다.
    
7.  **절대 트래픽 보정 (r9.1)**: 조회가 적은 시간대에 상위 개체가 1.0을 받는 것을 막는다.
    
    ```
    M_seg = 백분위 × min(1, 현재 창 세그먼트 총 PV / 최근 7일 같은 시간대 총 PV 중앙값)
    ```
    
    *   7일 기준값이 없는 기간(PoC, S1 초기)에는 보정계수를 1로 둔다.
        
8.  `M = w_o × M_overseas + w_d × M_domestic`. 출발값은 5:5다. S1에서 실제 트래픽 비중(실측 30분 기준 국내 약 1/3, 해외 약 2/3)을 비교값으로 둔다.
    

**T — Google Trends**

1.  (r9.1) 수집 후보는 **Trending Now RSS(급상승)**다. 공식 Trends API(2025년 7월 알파)는 일·주·월·연 단위 관심도만 제공하므로 2시간 유효시간의 급상승 신호로는 맞지 않는다. 이용 약관과 응답 형식은 확인이 필요하다 [VERIFY].
    
2.  지역: 국내 = KR. 해외는 US 하나로 고정하지 않고, Marfeel 해외 세그먼트의 국가별 PV 상위 국가(`groupBy: country`)의 비중으로 가중한다. "글로벌" 지역은 제공되지 않을 수 있다 [VERIFY].
    
3.  사안 개체와 일치하는 검색어의 급상승 강도를 지역별 백분위로 0~1 정규화한다. 트래픽 값이 구간(예: "1000+")으로만 제공되면 동점은 평균 순위로 처리한다.
    
4.  국문 급상승 검색어를 매칭할 수 있도록 `interest_entities.yaml`에 개체별 국문 별칭을 둔다.
    
5.  `T = 0.5 × T_overseas + 0.5 × T_domestic`
    

**공통**

*   개체 매칭이 없으면 값은 0이다(감점 아님).
    
*   유효시간: M 30분, T 2시간(Clock 기준). 지나면 0이 되므로, 신호 장애 시 boost = 1이 되어 r8 점수와 같아진다.
    
*   (r9.1) M 유효시간 30분은 수집 계획의 장애 알림 기준(3주기 연속 실패 = 15분)보다 길다. 따라서 알림이 먼저 나가고, 실패가 6주기 이상 계속되면 신호가 0이 된다.
    

### (5) 처리 위치와 저장 (r9.1 수정)

*   **신규 worker 레인 없음 (S-6).** jobs 레인 하위 작업으로 처리한다.
    *   `MarfeelPoller`(수집 계획 그대로): 스냅샷과 URL별 행을 저장한다.
        
    *   `InterestJob`(신규, 5분 주기, Marfeel 수집 직후): 30분 경계 집계 → 개체별 보정 평균 → 세그먼트별 정규화를 거쳐 **개체 단위 값**을 `interest_signals`에 저장한다(`entity`, `segment`, `source`, `value`, `computed_at`, `expires_at`, `missing_slots`).
        
    *   `TrendsPoller`(신규, 주기는 약관 확인 후 결정): T 원천값을 저장한다.
        
*   모든 시각은 `Clock`을 거친다(r8 원칙 6). 재생 모드에서 실제 Marfeel 주소로 호출하면 기동이 실패해야 한다(수집 계획 Task 6 규칙 유지).
    
*   외부 호출 제한·백오프: Marfeel은 수집 계획 설정(`min_call_interval_seconds: 65`, 429가 나면 그 주기를 건너뜀)을 따른다. Trends는 약관을 확인한 뒤 정한다.
    
*   계산 시점: **사안–개체 매칭과 boost는 api가 스냅샷 생성 시** 계산한다(r7 `compute_at: query` 유지). analyze 레인은 boost를 저장하지 않는다.
    
*   `rec_snapshots.rows`(r8 440행)에 `decayed_score`, `m`, `t`, `t_applied`, `boost`, `gated`(bool)를 추가한다. `score`는 최종값이다.
    

### (6) 화면 표시 (`추천` 응답, r8 552행 보강)

*   각 행에 최종 점수와 기여 배지를 표시한다. 예: `독자↑ +28%`, `검색↑ +6%`
    
*   신호가 만료됐으면 표 하단에 "관심도 신호 없음(통신사 점수만 반영)"을 표시한다.
    
*   `사안 {id}` 상세의 점수 구성(r8 581행)에 M·T 매칭 개체와 그 값을 추가한다. `missing_slots`가 있으면 "독자 신호 일부 누락(n/12)"을 표시한다.
    

* * *

## 부록 G 추가분 (설정 골격, r9.1)

```yaml
scoring:
  interest:                      # r9.1
    enabled: false               # PoC 기본 off, 평가 스크립트에서 비교
    caps: { marfeel: 0.40, trends: 0.10 }   # boost 최대 1.45
    trends_overlap_factor: 0.5   # T_applied = T × (1 − 0.5 × M)
    gate_top_n: 40               # 목록별, decayed_score 기준
    segments: { overseas: 0.5, domestic: 0.5 }
    window: { mode: aligned_30m, slots: 12, substitute_tolerance_minutes: 5 }
    mean_shrinkage_k: 2
    min_entities_for_percentile: 5
    traffic_floor: { enabled: true, baseline_days: 7 }   # 기준값 없으면 계수 1
    generic_entity: { doc_ratio: 0.20, weight: 0.2, lookback_days: 7 }
    ttl_minutes: { marfeel: 30, trends: 120 }
    entity_text: title           # PoC. 첫 문단 출처 확정 후 title_lead
    trends_regions: { domestic: KR, overseas: marfeel_country_share }   # 확인 필요
    entities_file: interest_entities.yaml
    source_lane: jobs            # 신규 worker 레인 없음 (S-6)
  penalty:
    enabled: false               # 경쟁사 감점 미정의 (S-4)
```

```yaml
# eval/config.yaml 추가
compare:
  interest: [off, marfeel_only, marfeel_trends]       # S0 / S1 / S2
  interest_caps:
    marfeel: [0.30, 0.40, 0.50]
    trends: [0.10, 0.15, 0.20]
  interest_segments: [[0.5, 0.5], [0.67, 0.33]]       # 해외, 국내 (S1)
  interest_window: [aligned_30m, ema_2h]              # S1
```

* * *

## §8 G7 연계 변경

*   G7 ②: 판정식을 `decayed_score / raw_score = 0.25 ± 1%`로 변경한다(S-5).
    
*   G7 ⑥ 비교값에 S0/S1/S2와 상한 조합별 상위 목록 변화를 추가한다. 보고만 하며 기준값은 없다. 합성 신호이므로 "(잠정)"으로 표기한다.
    
*   (r9.1) G7 ⑥ 보고 항목에 "게이트로 인해 상위 10건 구성이 바뀐 건수(목록별)"를 추가한다.
    
*   계약 검사:
    1.  `interest.enabled = true`이고 신호가 전부 만료된 상태에서, 스냅샷 순위가 off 상태와 같아야 한다.
        
    2.  (r9.1) `gated = false`인 행은 모두 `boost = 1`이어야 한다.
        
    3.  (r9.1) 모든 행에서 `score / (decayed_score × penalty) ≤ 1 + cap_m + 0.5 × cap_t`여야 한다.
        
    4.  (r9.1) 6시간 집계에 같은 30분 구간이 두 번 들어가지 않아야 한다. 겹치는 스냅샷을 넣은 픽스처로 확인한다.
        

## S1 Shadow 계획 문서로 이관 (r8 325행 기준)

*   실데이터 판정 지표: 추천 적중률(r8 정의), 기자 선정 사안의 상위 20건 포함률, 발행 초안의 해외·국내 조회
    
*   판정 원칙: S1이 S0보다 개선되지 않으면 Marfeel 상한을 낮춘다. S2가 S1보다 개선되지 않으면 Trends는 표시용 배지로만 남긴다.
    
*   (r9.1) S1 비교값: 세그먼트 가중 5:5 vs 6.7:3.3, 집계 방식 aligned_30m vs ema_2h, 절대 트래픽 보정 on/off
    

* * *

## 확인 필요 항목

1.  [결정] §4.2 범위 변경 승인: PoC에 가산 구조·픽스처 신호를 포함할지 (S-1·S-2)
    
2.  ~~[VERIFY] Marfeel API: 기사별·세그먼트별 조회, 갱신 주기, 호출 제한~~ → **확인됨**(data-scope §8: 기사별 실시간 가능, 국내·해외는 country 필터 2회 호출, 분당 1회·계정 공유). 남은 항목: 배치 위치·유입 경로 제공 여부 [VERIFY]
    
3.  [VERIFY] Google Trends: Trending Now RSS 이용 약관, 트래픽 구간 형식, 지역별 제공 범위, "글로벌" 지역 제공 여부
    
4.  [결정] 경쟁사 감점 도입 여부와 정의 (S-4)
    
5.  [결정] 출발값 승인: 상한 0.40·0.10(초판 0.15에서 하향), 게이트 40건, 축소 계수 k = 2
    
6.  개체 사전 `interest_entities.yaml` 초판 작성 주체·규모, 국문 별칭 포함 (T5 공수 영향)
    
7.  (r9.1) [VERIFY] `kt_articles` 첫 문단의 출처 (KT RSS 또는 CMS)
    
8.  (r9.1) [VERIFY] PoC 픽스처의 목록별 사안 수 (게이트 40건이 실제로 작동하는지)
    
9.  (r9.1) [VERIFY] 360분 realtime 창 직접 조회 가능 여부 (실측은 180분까지)
    
10.  (r9.1) [결정] 문서 간 표기 통일: Marfeel 역할 문서의 "최대 +50%"를 이 초안의 상한(+45%)에 맞춤
     

## 영향 문서 (후속 수정)

*   인수인계 r9: §4.1/§4.2, §5.4 `rec_snapshots`·신규 `interest_signals`, §5.5④, §8 G7, 부록 G, T 일정표(T5 또는 신규 태스크)
    
*   DB 설계안: `interest_signals` 테이블(개체 단위, `missing_slots` 포함), `rec_snapshots.rows` 필드
    
*   API 명세서: `/v1/render` 추천 응답 필드(배지, 신호 상태, 누락 표시)
    
*   화면 정의서: 추천 표 배지 열, 신호 없음 문구, 사안 상세 점수 구성
    
*   아키텍처 초안: (r9.1) `interest` 레인 삭제 → jobs 레인 하위 작업(`InterestJob`, `TrendsPoller`), 외부 연동 장애 시 동작
    
*   Marfeel 수집 계획(2026-10-22): `InterestJob`이 스냅샷을 읽는 조건(30분 경계 정렬) 추가, T0-3 결과를 `limit`에 반영
    
*   Marfeel 역할 정리 문서: 최대 가산 표기 +50% → +45%