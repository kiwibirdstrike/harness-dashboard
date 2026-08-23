# Harness Dashboard

프로젝트 폴더를 작업공간 트리로 보고, 내가 등록한 AI Agent CLI를 폴더마다 배치해 해당 위치에서 터미널을 여는 데스크톱 앱입니다.

## 현재 지원 상태

- macOS Apple Silicon: 소스와 `.app` 실행 확인
- Windows x64: 실행 코드 포함, 실제 빌드 확인 전

## 소스로 실행

Python 3.10 이상과 Tkinter가 필요합니다. macOS에서는 [python.org](https://www.python.org/downloads/macos/) 설치본을 권장합니다.

```bash
python3 app.py
```

상단의 `Set Root`로 프로젝트의 상위 폴더를 지정한 뒤 오른쪽 Agent Dock의 카드를 클릭하거나 폴더 위로 드래그해 배치합니다. 선택한 작업 폴더는 `Open Folder`로 Finder/Explorer에서 열고, `Open Terminal`로 배치된 CLI를 실행합니다. 배치 정보는 선택한 프로젝트의 `.harness.json`에 바로 저장됩니다.

## Terminal Workspace

`Open Terminal`은 선택한 폴더의 Agent 하나만 엽니다. `Open Workspace`는 현재 프로젝트에 정상 배치된 Agent를 모두 하나의 tmux 세션으로 실행하고 iTerm2에서 균등한 `tiled` 배치로 보여줍니다. 기존 세션이 있으면 Agent를 중복 실행하지 않고 `Show Workspace`로 다시 연결합니다.

macOS 워크스페이스 기능에는 tmux가 필요하며 iTerm2 사용을 권장합니다. Harness는 두 프로그램을 자동 설치하지 않습니다. iTerm2가 없으면 기본 Terminal 앱으로 열립니다.

```bash
brew install tmux
```

`Stop Workspace`는 현재 프로젝트의 Harness tmux 세션과 그 안의 Agent를 모두 종료합니다. CLI가 종료된 pane은 오류 내용을 확인할 수 있도록 남아 있으며, pane을 닫으면 나머지가 다시 균등 배치됩니다.

## Agent 관리

`Manage` 또는 왼쪽 아래 설정 버튼에서 Agent를 직접 추가·수정·삭제할 수 있습니다.

- Name: Dock에 표시할 이름
- Launch command: 터미널에서 실행할 명령과 옵션
- Best for: 이 Agent가 잘하는 작업에 대한 짧은 설명
- Signature image: 선택 사항인 PNG 이미지
- Accent: Agent 카드 구분 색상

첫 실행 시 Codex, Claude, Antigravity의 구분 아이콘과 기본 설명이 함께 등록됩니다. Antigravity의 기본 실행 명령은 `agy`입니다. 기존 기본 Gemini Agent는 앱을 다시 열면 같은 배치와 아이콘을 유지한 채 Antigravity로 자동 변경됩니다. 목록은 컴퓨터 전체에서 공유되며 macOS는 `~/Library/Application Support/HarnessDashboard/agents.json`, Windows는 `%APPDATA%\HarnessDashboard\agents.json`에 저장됩니다. 삭제된 Agent가 프로젝트에 배치돼 있으면 해당 폴더에 `Missing agent`가 표시되며, 다른 Agent로 다시 배치할 때까지 실행되지 않습니다.

앱은 CLI 설치 여부나 구독 상태를 감지하지 않습니다. 등록한 실행 명령이 일반 터미널에서 먼저 동작하고 로그인이 완료돼 있어야 합니다.

## 개발 확인

```bash
python3 -m unittest tests.test_harness -v
python3 -m compileall -q app.py harness tests
```

## 앱 빌드

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements-build.txt
.venv/bin/python scripts/build.py
```

macOS에서는 `dist/HarnessDashboard.app`, Windows에서는 `dist/HarnessDashboard/` 폴더와 그 안의 `HarnessDashboard.exe`가 생성됩니다. PyInstaller는 교차 컴파일을 지원하지 않으므로 각 운영체제에서 따로 빌드합니다.

## 배포 참고

MVP 빌드는 코드 서명과 공증을 하지 않습니다. 신뢰하는 GitHub 저장소에서 받은 파일인지 확인한 뒤 운영체제의 보안 경고에서 직접 실행을 승인해야 합니다. 자동 업데이트와 설치 프로그램은 포함하지 않습니다.

- macOS: 앱을 한 번 연 뒤 `시스템 설정 > 개인정보 보호 및 보안 > 확인 없이 열기`를 선택합니다.
- Windows: SmartScreen 경고에서 `추가 정보 > 실행`을 선택합니다.

`v0.1.0` 같은 버전 태그를 GitHub에 푸시하면 macOS Apple Silicon과 Windows x64 빌드를 각각 만들고 같은 이름의 GitHub Release에 첨부합니다.
