# 🐧 Linux Helper (리눅스 헬퍼)

> **리눅스 터미널 환경에서 발생하는 파이썬 및 CLI 실행 에러를 실시간으로 감지하고, 로컬 LLM(Ollama)이 원인 분석 및 해결 코드를 즉시 제안하는 AI 보조 도구입니다.**

---

## 📌 주요 특징 (Key Features)

* **비침습적 에러 포착**: 기존 파이썬 코드를 전혀 수정하지 않고도, 실행 시 발생하는 `Traceback` 및 표준 에러(`stderr`)를 실시간 포착합니다.
* **로컬 LLM 연동 (Ollama)**: 외부 API 키 비용이나 데이터 유출 걱정 없이, 로컬에서 구동되는 AI 모델이 에러를 분석합니다.
* **비동기 대시보드 모니터링**: `tmux` 멀티태스킹 환경을 활용하여, 개발 작업 영역과 AI 분석 대시보드가 실시간으로 분리되어 작동합니다.
* **다양한 터미널 지원**: 리눅스 콘솔(Konsole, GNOME Terminal 등) 및 VS Code 내장 터미널에서 모두 안정적으로 구동됩니다.

---

## ⚙️ 실행 환경 (Environment)

* **OS**: Linux (Debian, Ubuntu 등)
  > ⚠️ *윈도우 환경은 지원하지 않으며, 리눅스 CLI 개발 환경에 최적화되어 있습니다.*
* **필수 요구사항**:
  * `Python 3.x` (기본 내장 라이브러리만 사용하므로 `requirements.txt` 의존성 없음)
  * `Ollama` (로컬 AI 모델 구동)
  * `tmux` (터미널 화면 분할 및 세션 제어)

---

## 🔄 처리 과정 (Workflow)

1. **오류 발생**: 개발자가 파이썬 파일 또는 터미널 명령어를 실행하다 에러(`stderr`) 발생
2. **파이프 전달**: 쉘 래퍼(Shell Wrapper)가 에러 로그를 `/tmp/agent_fifo` 임시 파이프에 비동기로 작성
3. **실시간 분석**: 우측 대시보드의 `agent_listener.py`가 에러를 감지하여 Ollama 모델에 전달
4. **해결책 제시**: 에러의 근본 원인과 바로 적용 가능한 수정 코드를 실시간 보고서로 출력

---

## 🚀 시작하기 (Quick Start)

### 1. Repository 클론
```bash
git clone [https://github.com/LeeIsGenius/Linux_Helper.git](https://github.com/LeeIsGenius/Linux_Helper.git)
cd Linux_Helper

2. Ollama 모델 확인

ollama list

💡 참고: agent_listener.py 파일 12번째 줄의 MODEL_NAME 변수를 편집하여 원하시는 로컬 모델(예: gemma3:4b, llama3 등)로 변경할 수 있습니다.

3. 시동 스크립트 실행

chmod +x start_agent.sh
./start_agent.sh