# Claude Code 설치 작업 계약·현재 상태

> 프로젝트: `/home/kwh8121/projects/marfeel` · 작업 ID: `local-claude-install-2026-10-21` · 기준일: 2026-10-21 · CLI: Claude Code 2.1.306

## 작업 계약

| 항목 | 내용 |
| --- | --- |
| 목표 | marfeel 프로젝트에 Claude Code 지침·설정·검증·기록 흐름 적용 |
| 범위 | `CLAUDE.md`, `.claude/settings.json`, `docs/` 기본 폴더와 Claude 설치 문서 |
| 비목표 | 사용자 설정·인증·Codex 설정·선택 확장·개인 프로젝트 설정 |
| 완료 조건 | 지침·설정 준비, 도입 연결, 문서 배치, 파일 검사, 새 세션 적용·동작 검증, 검토·인계 |
| 검증 방법 | 문서·설정 검사(앱 테스트 N/A). 명령은 [검증 가이드](../guides/verification.md) 참조 |
| 시작 상태 | 브랜치 없음(커밋 전), 공용 파일 전부 미추적, `.git` 없음 |
| 이슈·PR | 지정 Issue·PR·CI 없음. 로컬 작업 ID로 추적 |

## 문제 기록

### P1. 작업 폴더가 Git 저장소가 아님 (해결됨)

| 항목 | 내용 |
| --- | --- |
| 발견 | 2026-10-21 17:0x KST, S0 |
| 증상 | `git rev-parse --show-toplevel`이 `not a git repository`로 실패. 상위 경로에도 `.git` 없음 |
| 확인 | 원격 `https://github.com/kwh8121/marfeel.git`는 접근 가능하나 브랜치·커밋이 없는 빈 저장소(`git ls-remote` 종료 코드 0, 출력 없음). 복구할 이력 없음 |
| 조치 | 사용자 승인 후 `git init -b main`, `origin`을 위 URL로 연결. push·fetch는 하지 않음 |
| 영향 | 가이드 3.2절의 `git init` 금지에 대한 예외를 사용자가 승인함 |

## 단계별 상태

| 단계 | 결과 | 이번 동작 | 확인 시각 | 근거·입력 식별 | 다음 재시도 |
| --- | --- | --- | --- | --- | --- |
| S0 사전 조건 | PASS | CHECK | 2026-10-21 17:04 KST | CLI 2.1.306, `claude auth status` 종료 코드 0, JSON 파서 PASS, 루트 쓰기 가능(ext4 rw), P1 해소 후 Git 상태 조회 성공 | 없음 |
| S1 지침 준비 | PASS | APPLY | 2026-10-21 | `CLAUDE.md` 갱신(`/init` 개선 1~3 반영: 표준 머리말, 검증 가이드 연결, 프로젝트 사실 2줄). SHA-256 `5809a836…778052`(최초 `496edcad…25fc4d`). README 읽기 지시 유지, `@AGENTS.md` 미사용 | 없음 |
| S2 프로젝트 설정 | PASS | APPLY | 2026-10-21 17:04 KST | 신규 `.claude/settings.json` SHA-256 `6f0bfdb7…388804`, `permissions.defaultMode = default` | 없음 |
| S3 파일 검사 | FAIL | RETRY | 2026-10-21 | Claude 범위 파일은 통과. Codex 문서 부재로 링크 검사 실패(아래 미해결) | Codex 문서 배치 후 재실행 |
| S4 세션 적용 | NOT RUN | WAIT | 해당 없음 | 새 대화형 `claude` 세션이 필요하며 이 세션에서 수행 불가 | 사용자가 새 세션에서 6절 수행 |
| S5 로컬 동작 | NOT RUN | WAIT | 해당 없음 | S4 선행 | S4 통과 후 |

보조 근거: `claude doctor` — `No installation issues found` (세션 검증을 대신하지 않음).

## 생성·수정 경로

- 신규: `CLAUDE.md`, `.claude/settings.json`, `docs/plans/`, `docs/jobs/`, `docs/guides/`, `docs/references/`, `docs/images/`, `docs/README.md`, `docs/guides/verification.md`, `docs/jobs/claude-install-state.md`, `docs/jobs/2026-10-21.md`, `.git/`
- 수정: `README.md` 4절 연결표(Claude 행과 검증 실행 디렉터리). Codex 내용은 보존
- 수정: `CLAUDE.md` — 머리말·검증 가이드 연결·프로젝트 사실 추가. 변경 전 내용은 가이드 4.1절 코드 블록과 동일하며 이 기록의 최초 해시로 식별
- 백업: 기존 `CLAUDE.md`·`.claude/`가 없어 백업 대상 없음
- 보존 확인: `AGENTS.md`·`.codex/`는 이 폴더에 없으며 변경하지 않음

## 사용자 영역 영향

- 사용자 `~/.claude/CLAUDE.md`와 사용자 hooks·plugins가 이 프로젝트 세션에도 적용됨. 변경하지 않음.
- 새 세션 신뢰 결정은 `~/.claude.json`에 저장될 수 있음(프로젝트 산출물 아님).

## 미해결

- S4·S5: 새 대화형 세션 검증 미실행.
- S3: `README-Codex.md`, `docs/jobs/codex-install-state.md`가 이 폴더에 없어 `README.md`·`INSTALL.md`·`INSTALL_CODEX.md`의 링크 검사 실패. Codex 범위이므로 이번 설치에서 만들지 않음.
- 결정(2026-10-21): Codex 설치는 보류. S3의 Codex 링크 8건은 보류 사유와 함께 남기며 통과로 표시하지 않음.
- 결정(2026-10-21): `.env`(64B)와 `.opencode/`는 내용을 열지 않고 `.gitignore`로 커밋 대상에서 제외함.
- 첫 커밋·push는 실행하지 않음.
