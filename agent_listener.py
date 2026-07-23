#!/usr/bin/env python3
import os
import sys
import time
import re
import shutil
import json
import subprocess
import urllib.request
from typing import TypedDict
from langgraph.graph import StateGraph, END

# ==========================================
# Configuration (Ollama & FIFO)
# ==========================================
OLLAMA_URL = "http://127.0.0.1:11434/api/generate"
MODEL_NAME = "gemma3:4b"
FIFO_PATH = "/tmp/agent_fifo"
MAX_RETRY_COUNT = 3  # 자가 피드백 루프 최대 재시도 횟수

# Terminal ANSI Color Codes
GREEN = "\033[92m"
YELLOW = "\033[93m"
CYAN = "\033[96m"
RED = "\033[91m"
RESET = "\033[0m"
BOLD = "\033[1m"


# ==========================================
# Direct Ollama HTTP Call
# ==========================================
def call_ollama(prompt: str, system_prompt: str = "") -> str:
    """urllib 기반 통신 - timeout 파라미터를 제거하여 추론 완료 시까지 무제한 대기"""
    full_prompt = f"{system_prompt}\n\n{prompt}" if system_prompt else prompt
    payload = {
        "model": MODEL_NAME,
        "prompt": full_prompt,
        "stream": False,
        "options": {"temperature": 0.0}
    }
    data = json.dumps(payload).encode('utf-8')
    req = urllib.request.Request(
        OLLAMA_URL,
        data=data,
        headers={'Content-Type': 'application/json'}
    )
    try:
        # timeout 매개변수를 완전히 제거하여 무제한 응답 대기
        with urllib.request.urlopen(req) as response:
            result = json.loads(response.read().decode('utf-8'))
            return result.get("response", "").strip()
    except Exception as e:
        print(f"{RED}❌ Ollama API 호출 실패: {e}{RESET}")
        return ""


# ==========================================
# State Definition
# ==========================================
class AgentState(TypedDict):
    raw_error: str
    target_file: str
    analysis: str
    fixed_code: str
    cli_solution: str
    backup_status: str
    apply_status: str
    test_returncode: int
    test_stdout: str
    test_stderr: str
    retry_count: int


# ==========================================
# Graph Nodes
# ==========================================
def parse_and_backup_node(state: AgentState) -> AgentState:
    """Node 1: Traceback에서 파일 경로 추출 및 백업"""
    print(f"\n{YELLOW}⚡ [Node 1] 에러 파일 추적 및 백업 중...{RESET}")
    sys.stdout.flush()

    matches = re.findall(r'File "([^"]+\.py)"', state['raw_error'])
    if matches:
        raw_path = matches[-1].strip()
        file_path = os.path.abspath(raw_path)
        state['target_file'] = file_path
        
        if os.path.exists(file_path):
            backup_path = f"{file_path}.bak"
            try:
                shutil.copyfile(file_path, backup_path)
                state['backup_status'] = f"✅ 백업 완료 ({os.path.basename(backup_path)})"
            except Exception as e:
                state['backup_status'] = f"❌ 백업 실패 ({e})"
        else:
            state['backup_status'] = f"⚠️ 파일 찾을 수 없음 ({file_path})"
    else:
        state['target_file'] = "N/A"
        state['backup_status'] = "ℹ️ CLI 단일 명령어 실행건"

    return state


def analyze_error_node(state: AgentState) -> AgentState:
    """Node 2: 에러 로그 분석"""
    print(f"{YELLOW}⚡ [Node 2] 에러 원인 정밀 분석 중...{RESET}")
    sys.stdout.flush()

    sys_prompt = "당신은 리눅스/파이썬 에러 분석 전문가입니다."
    prompt = (
        "다음 파이썬/리눅스 에러 로그의 원인을 한글로 간결히 정리하세요.\n\n"
        f"[에러 로그]\n{state['raw_error']}\n\n"
        "[작성 양식]\n"
        "1. 🚨 **오류 요약**: (한 줄 요약)\n"
        "2. 💡 **원인 분석**: (원인 설명)"
    )
    state['analysis'] = call_ollama(prompt, sys_prompt)
    return state


def code_patcher_node(state: AgentState) -> AgentState:
    """Node 3-A: 파이썬 전체 코드 자동 패치 생성 (피드백 반영)"""
    current_retry = state.get('retry_count', 0)
    if current_retry > 0:
        print(f"{YELLOW}⚡ [Node 3-A] 🔄 자가 피드백 패치 재시도 중... ({current_retry}/{MAX_RETRY_COUNT}){RESET}")
    else:
        print(f"{YELLOW}⚡ [Node 3-A] 최초 정밀 패치 코드 생성 중...{RESET}")
    sys.stdout.flush()

    target_file = state['target_file']
    target_code = ""

    if target_file != "N/A" and os.path.exists(target_file):
        try:
            with open(target_file, 'r', encoding='utf-8') as f:
                target_code = f.read()
        except Exception as e:
            print(f"{RED}[!] 원본 파일 읽기 에러: {e}{RESET}")

    sys_prompt = "You are an automated Python full-code patcher. Fix all reported and latent errors. Output ONLY executable Python code."
    prompt = (
        "너는 파이썬 소스코드의 모든 버그를 완벽히 치료하는 수석 개발 에이전트다.\n"
        "제시된 에러 로그뿐만 아니라 원본 코드 전체를 정밀 분석하여, 잠복해 있는 연쇄 버그(KeyError, ZeroDivisionError, NameError 등)를 미리 완전히 치유한 '전체 코드'를 작성하라.\n\n"
        "[절대 수칙]\n"
        "1. 눈앞의 에러뿐 아니라 코드 내 미선언 변수, 타입 오류, 0 나누기 등을 선제적으로 완전 치유하라.\n"
        "2. 설명, 인사말, 주석, 마크다운(```)을 절대 포함하지 마라. 오직 즉시 실행 가능한 파이썬 소스코드 전체만 출력하라.\n\n"
        f"[발생한 에러 로그]\n{state['raw_error']}\n\n"
        f"[원본 소스코드]\n{target_code}"
    )
    
    raw_text = call_ollama(prompt, sys_prompt)

    # 순수 코드만 정밀 적출
    code_match = re.search(r'```(?:python)?\s*\n(.*?)\n```', raw_text, re.DOTALL)
    if code_match:
        clean_code = code_match.group(1).strip()
    else:
        clean_code = re.sub(r'^(Here is|This is|Below is|Note:).*$', '', raw_text, flags=re.MULTILINE).strip()

    state['fixed_code'] = clean_code
    return state


def test_execution_node(state: AgentState) -> AgentState:
    """Node 3-A-2: 수정된 코드를 임시 환경에서 직접 실행하여 자가 검증"""
    print(f"{YELLOW}🧪 [Node 3-A-2] 샌드박스 백그라운드 구동 테스트(Dry-run) 진행 중...{RESET}")
    sys.stdout.flush()

    target_file = state['target_file']
    temp_file = f"{target_file}.agent_tmp"

    # 임시 검증 파일 작성
    try:
        with open(temp_file, 'w', encoding='utf-8') as f:
            f.write(state['fixed_code'])
    except Exception as e:
        state['test_returncode'] = -1
        state['test_stderr'] = f"임시 파일 작성 실패: {e}"
        return state

    # 현재 Python 인터프리터로 직접 실행 테스트
    try:
        res = subprocess.run(
            [sys.executable, temp_file],
            capture_output=True,
            text=True,
            timeout=10  # 무한루프 방지용 10초 타임아웃
        )
        
        state['test_returncode'] = res.returncode
        state['test_stdout'] = res.stdout
        state['test_stderr'] = res.stderr

        if res.returncode == 0:
            print(f"{GREEN}✅ [Self-Test] 자가 구동 테스트 성공! (Return Code: 0){RESET}")
        else:
            print(f"{RED}⚠️ [Self-Test] 자가 구동 테스트 실패! (Return Code: {res.returncode}){RESET}")
            # 다음 피드백 루프를 위해 에러 로그를 새로 터진 stderr로 교체
            state['raw_error'] = res.stderr.strip()
            state['retry_count'] = state.get('retry_count', 0) + 1

    except subprocess.TimeoutExpired:
        state['test_returncode'] = -1
        state['test_stderr'] = "TimeoutExpired: 패치 코드가 10초 내에 종료되지 않았습니다 (무한 루프 감지)."
        state['raw_error'] = state['test_stderr']
        state['retry_count'] = state.get('retry_count', 0) + 1
    finally:
        if os.path.exists(temp_file):
            os.remove(temp_file)

    return state


def apply_patch_node(state: AgentState) -> AgentState:
    """Node 4: 자가 검증을 통과한 완벽한 코드만 원본 파일에 반영"""
    print(f"{YELLOW}🚀 [Node 4] 검증 완비된 코드 원본 파일 최종 반영 중...{RESET}")
    sys.stdout.flush()

    target_file = state['target_file']
    clean_code = state['fixed_code']

    if target_file != "N/A" and os.path.exists(target_file) and clean_code:
        try:
            with open(target_file, 'w', encoding='utf-8') as f:
                f.write(clean_code + "\n")
            state['apply_status'] = f"🚀 원본 파일({os.path.basename(target_file)}) 자가 테스트 완치 후 정밀 반영 완료!"
        except Exception as e:
            state['apply_status'] = f"❌ 파일 저장 실패 ({e})"
    else:
        state['apply_status'] = f"⚠️ 적용 스킵 (target_file={target_file})"

    return state


def cli_advisor_node(state: AgentState) -> AgentState:
    """Node 3-B: CLI 해결 명령어 제시"""
    print(f"{YELLOW}⚡ [Node 3-B] 리눅스 CLI 해결 명령어 생성 중...{RESET}")
    sys.stdout.flush()

    sys_prompt = "당신은 리눅스 에러 해결 부관입니다."
    prompt = (
        "리눅스 CLI 터미널 에러를 해결할 한 줄 Bash 명령어를 작성하세요.\n\n"
        f"[에러 로그]\n{state['raw_error']}\n\n"
        "[작성 양식]\n"
        "🛠️ **추천 해결 명령어**: (실행할 Bash 명령어)\n"
        "📌 **실행 가이드**: (한 줄 가이드)"
    )
    state['cli_solution'] = call_ollama(prompt, sys_prompt)
    return state


# ==========================================
# Graph Routers (조건부 순환 제어)
# ==========================================
def route_error_type(state: AgentState) -> str:
    if state['target_file'] != "N/A":
        return "patcher"
    else:
        return "cli_advisor"


def route_test_validation(state: AgentState) -> str:
    """자가 구동 테스트 결과 및 피드백 루프 라우터"""
    if state.get('test_returncode') == 0:
        return "apply_patch"  # 검증 성공 시 최종 반영
    
    # 실패 시 최대 시도 횟수 확인 후 피드백 순환
    if state.get('retry_count', 0) <= MAX_RETRY_COUNT:
        print(f"{RED}🔄 자가 테스트에서 새로운 예외 감지! 재치료 루프 진입 (시도 횟수: {state.get('retry_count')}/{MAX_RETRY_COUNT}){RESET}")
        return "re_patch"
    else:
        print(f"{RED}❌ {MAX_RETRY_COUNT}회 재시도 후에도 자가 구동 검증 실패. 원본 파일 안전 보존.{RESET}")
        state['apply_status'] = f"❌ 자가 테스트 {MAX_RETRY_COUNT}회 실패로 원본 파일 안전 보존 (미적용)"
        return "failed_end"


# ==========================================
# Graph Workflow Construction
# ==========================================
workflow = StateGraph(AgentState)

# 노드 등록
workflow.add_node("backup_parser", parse_and_backup_node)
workflow.add_node("analyzer", analyze_error_node)
workflow.add_node("patcher", code_patcher_node)
workflow.add_node("tester", test_execution_node)
workflow.add_node("apply_patch", apply_patch_node)
workflow.add_node("cli_advisor", cli_advisor_node)

# 엣지 연결
workflow.set_entry_point("backup_parser")
workflow.add_edge("backup_parser", "analyzer")

# 1차 분기: 파이썬 파일 처리 vs CLI 처리
workflow.add_conditional_edges(
    "analyzer",
    route_error_type,
    {
        "patcher": "patcher",
        "cli_advisor": "cli_advisor"
    }
)

# 패치 후 자가 구동 테스트 진입
workflow.add_edge("patcher", "tester")

# 2차 분기 (자가 검증 피드백 루프)
workflow.add_conditional_edges(
    "tester",
    route_test_validation,
    {
        "apply_patch": "apply_patch",  # 성공 ➔ 원본 파일 반영
        "re_patch": "patcher",         # 실패 ➔ 새로운 에러 로그로 재치료(Loop)
        "failed_end": END              # 3회 초과 실패 ➔ 안전 중단
    }
)

workflow.add_edge("apply_patch", END)
workflow.add_edge("cli_advisor", END)

app = workflow.compile()


# ==========================================
# Main Monitoring Loop
# ==========================================
def main():
    print(f"{GREEN}=========================================={RESET}")
    print(f"{GREEN}   🛡️  Linux Helper v4.0 (Self-Correction Loop) {RESET}")
    print(f"{GREEN}   Monitoring Pipe: {FIFO_PATH}{RESET}")
    print(f"{GREEN}   Model: {MODEL_NAME}{RESET}")
    print(f"{GREEN}=========================================={RESET}\n")
    sys.stdout.flush()

    if not os.path.exists(FIFO_PATH):
        os.mkfifo(FIFO_PATH)

    print(f"{GREEN}[+] 자가 구동 검증 루프 포함 AI 모니터링 가동 완료!{RESET}\n")
    sys.stdout.flush()

    while True:
        try:
            fifo_fd = os.open(FIFO_PATH, os.O_RDONLY | os.O_NONBLOCK)
            with os.fdopen(fifo_fd, 'r') as fifo:
                log_data = fifo.read().strip()
                if log_data:
                    print(f"\n{CYAN}{'='*50}{RESET}")
                    print(f"{BOLD}📊 [AI Terminal Agent - Self-Correction Workflow v4.0]{RESET}")
                    
                    initial_state = {
                        "raw_error": log_data,
                        "target_file": "",
                        "analysis": "",
                        "fixed_code": "",
                        "cli_solution": "",
                        "backup_status": "",
                        "apply_status": "",
                        "test_returncode": -1,
                        "test_stdout": "",
                        "test_stderr": "",
                        "retry_count": 0
                    }
                    result = app.invoke(initial_state)

                    print(f"\n📁 **대상 파일**: {result['target_file']}")
                    print(f"{result['analysis']}\n")
                    
                    if result['target_file'] != 'N/A':
                        print(f"🔒 **백업 상태**: {result['backup_status']}")
                        print(f"🛠️ **적용 상태**: {result['apply_status']}")
                        if result.get('test_returncode') == 0:
                            print(f"🧪 **자가 검증 테스트**: ✅ 성공 (Exit Code 0)")
                            print(f"📄 **자가 검증 실행 출력**:\n{result.get('test_stdout', '').strip()}")
                        print(f"\n🛠️ **최종 반영된 완치 소스코드**:\n```python\n{result['fixed_code']}\n```")
                    else:
                        print(f"{result['cli_solution']}")
                        
                    print(f"{CYAN}{'='*50}{RESET}\n")
                    sys.stdout.flush()
        except Exception as e:
            pass
        
        time.sleep(0.5)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print(f"\n{RED}[!] 모니터링 서비스 종료.{RESET}")
        sys.exit(0)