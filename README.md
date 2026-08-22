# Harness Dashboard

프로젝트 폴더를 작업공간 트리로 보고, 폴더마다 Codex·Claude·Gemini CLI를 배치해 해당 위치에서 터미널을 여는 데스크톱 앱입니다.

## 현재 지원 상태

- macOS Apple Silicon: 소스와 `.app` 실행 확인
- Windows x64: 실행 코드 포함, 실제 빌드 확인 전

## 소스로 실행

Python 3.10 이상과 Tkinter가 필요합니다. macOS에서는 [python.org](https://www.python.org/downloads/macos/) 설치본을 권장합니다.

```bash
python3 app.py
```

`Open Folder`로 프로젝트를 선택하고, 트리에서 폴더를 고른 뒤 Agent를 배치합니다. 배치 정보는 선택한 프로젝트의 `.harness.json`에 바로 저장됩니다.

## Agent CLI 준비

앱은 CLI를 설치하거나 로그인하지 않습니다. 사용할 명령이 터미널에서 먼저 실행돼야 합니다.

```bash
codex
claude
gemini
```

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
