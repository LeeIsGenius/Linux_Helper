#!/usr/bin/env python3
import os
import sys
import time
import urllib.request
import json

# ==========================================
# Configuration (Ollama & FIFO)
# ==========================================
OLLAMA_URL = "http://127.0.0.1:11434/api/generate"
MODEL_NAME = "llama3:latest"
FIFO_PATH = "/tmp/agent_fifo"

# Terminal ANSI Color Codes
GREEN = "\033[92m"
YELLOW = "\033[93m"
CYAN = "\033[96m"
RED = "\033[91m"
RESET = "\033[0m"
BOLD = "\033[1m"


def analyze_error(error_text: str):
    """수집된 에러 로그를 Ollama API로 전달하여 분석 리포트 출력"""
    prompt = f"""
당신은 리눅스 및 파이썬 개발 환경을 보좌하는 전문 개발 도우미 AI입니다.
다음 터미널 로그에서 발생한 에러 원인을 분석하고 해결 방법을 제시하세요.

[에러 로그]
{error_text}

[작성 양식]
1. 🚨 **오류 요약**: (한 줄로 간결하게 요약)
2. 💡 **원인 분석**: (명령어 오타, 권한 문제, 경로 부재, 파이썬 예외 등 핵심 원인 설명)
3. 🛠️ **해결 명령**: (개발자가 터미널에서 즉시 실행하여 해결할 수 있는 추천 CLI 명령어)
"""
    print(f"\n{YELLOW}⚡ [AI Agent 분석 진행 중... ({MODEL_NAME})]{RESET}")
    sys.stdout.flush()

    payload = {
        "model": MODEL_NAME,
        "prompt": prompt,
        "stream": False
    }
    data = json.dumps(payload).encode('utf-8')
    req = urllib.request.Request(
        OLLAMA_URL, 
        data=data, 
        headers={'Content-Type': 'application/json'}
    )

    try:
        with urllib.request.urlopen(req, timeout=120) as response:
            result = json.loads(response.read().decode('utf-8'))
            analysis = result.get("response", "")
            
            print(f"\n{CYAN}{'='*50}{RESET}")
            print(f"{BOLD}📊 [AI Terminal Agent Error Analysis Report]{RESET}")
            print(analysis.strip())
            print(f"{CYAN}{'='*50}{RESET}\n")
    except Exception as e:
        print(f"\n{RED}❌ Ollama API 호출 실패: {e}{RESET}")
        print("💡 'ollama serve' 서비스 가동 상태를 확인하세요.\n")
    
    sys.stdout.flush()


def main():
    print(f"{GREEN}=========================================={RESET}")
    print(f"{GREEN}   🛡️  Linux Helper - AI Error Monitor   {RESET}")
    print(f"{GREEN}   Monitoring Pipe: {FIFO_PATH}{RESET}")
    print(f"{GREEN}=========================================={RESET}\n")
    sys.stdout.flush()

    # FIFO 파이프 존재 확인 및 생성
    if not os.path.exists(FIFO_PATH):
        os.mkfifo(FIFO_PATH)

    # Non-blocking 방식을 이용한 무한 수신 루프
    while True:
        try:
            fifo_fd = os.open(FIFO_PATH, os.O_RDONLY | os.O_NONBLOCK)
            with os.fdopen(fifo_fd, 'r') as fifo:
                log_data = fifo.read().strip()
                if log_data:
                    analyze_error(log_data)
        except Exception:
            pass
        
        time.sleep(0.5)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print(f"\n{RED}[!] AI 에러 모니터링 서비스가 종료되었습니다.{RESET}")
        sys.exit(0)