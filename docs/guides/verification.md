# 검증 가이드

> 수정일: 2026-10-21 · 실행 위치: 프로젝트 루트 `/home/kwh8121/projects/marfeel` · 이 프로젝트는 문서·설정 프로젝트이며 앱 빌드·앱 테스트는 해당 없음

## Claude Code

### 문서 단독 검사

프로젝트 루트에서 [설치 가이드 5절](../../INSTALL_CLAUDE.md#5-파일-검증-명령과-성공-기준)의 문서 검사(상대 링크·코드 블록·줄 끝 공백)를 실행한다. 기대 결과는 종료 코드 0이다.

### 전체 검사(설정 포함)

같은 절의 전체 검사 블록을 실행한다. `CLAUDE.md`, `.claude/settings.json`, `permissions.defaultMode = default`, 진입 지침의 README 읽기 지시를 함께 검사한다. 기대 결과는 `PASS: project files, JSON values, Markdown checks`와 종료 코드 0이다.

이어서 다음을 실행한다.

```bash
claude doctor
git diff --check
git diff --cached --check
git status --short
```

`claude doctor`는 설정 진단 보조 근거이며 세션 검증을 대신하지 않는다.

### 새 세션 검증

프로젝트 루트에서 덮어쓰기 옵션 없이 새 대화형 `claude` 세션을 시작해 [설치 가이드 6절](../../INSTALL_CLAUDE.md#6-새-claude-code-세션에서-적용-검증)의 항목을 확인한다. 항목은 시작 화면, `/memory`, `/context`, `/status`, `/permissions`, 작은 로컬 작업이다.

### 복구

앱 배포는 해당 없음. 프로젝트 파일 복구는 [설치 가이드 7.2절](../../INSTALL_CLAUDE.md#72-되돌리기)과 [설치 기록](../jobs/claude-install-state.md)의 생성·수정 경로를 따른다.
