#!/usr/bin/env python3
import os
import sys
import time
import re
import shutil
from typing import TypedDict
from langchain_ollama import ChatOllama
from langchain_core.messages import HumanMessage, SystemMessage
from langgraph.graph import StateGraph, END

# ==========================================
# Configuration (Ollama & FIFO)
# ==========================================
OLLAMA_URL = "http://127.0.0.1:11434"
MODEL_NAME = "llama3:latest"
FIFO_PATH = "/tmp/agent_fifo"

# Terminal ANSI Color Codes
GREEN = "\033[92m"
YELLOW = "\033[93m"
CYAN = "\033[96m"
RED = "\033[91m"
RESET = "\033[0m"
BOLD = "\033[1m"

# ==========================================
# LLM & LangGraph State Setup
# ==========================================
llm = ChatOllama(
    base_url=OLLAMA_URL,
    model=MODEL_NAME,
    temperature=0.0
)

class AgentState(TypedDict):
    raw_error: str
    target_file: str
    analysis: str
    fixed_code: str
    cli_solution: str
    backup_status: str
    apply_status: str


# ==========================================
# Graph Nodes
# ==========================================
def parse_and_backup_node(state: AgentState) -> AgentState:
    """Node 1: Traceback에서 파이썬 파일 경로 정밀 추출"""
    print(f"\n{YELLOW}⚡ [LangGraph: Node 1] 에러 파일 추적 중...{RESET}")
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
    """Node 2: 에러 원인 분석"""
    print(f"{YELLOW}⚡ [LangGraph: Node 2] 에러 원인 분석 중...{RESET}")
    sys.stdout.flush()

    prompt = (
        "다음 파이썬/리눅스 에러 로그의 원인을 한글로 간결히 정리하세요.\n\n"
        f"[에러 로그]\n{state['raw_error']}\n\n"
        "[작성 양식]\n"
        "1. 🚨 **오류 요약**: (한 줄 요약)\n"
        "2. 💡 **원인 분석**: (원인 설명)"
    )
    messages = [
        SystemMessage(content="당신은 리눅스/파이썬 에러 분석 전문가입니다."),
        HumanMessage(content=prompt)
    ]
    response = llm.invoke(messages)
    state['analysis'] = response.content.strip()
    return state


def code_patcher_node(state: AgentState) -> AgentState:
    """Node 3-A: 파이썬 소스코드 자동 패치 및 강제적용 중"""
    print(f"{YELLOW}⚡ [LangGraph: Node 3-A] 연쇄 버그 포함 전면 정밀 패치 중...{RESET}")
    sys.stdout.flush()

    target_file = state['target_file']
    target_code = ""

    if target_file != "N/A" and os.path.exists(target_file):
        try:
            with open(target_file, 'r', encoding='utf-8') as f:
                target_code = f.read()
        except Exception as e:
            print(f"{RED}[!] 파일 읽기 에러: {e}{RESET}")

    prompt = (
        "너는 파이썬 소스코드의 모든 버그를 한 번에 완벽 치료하는 수석 개발 에이전트다.\n"
        "제시된 에러 로그뿐만 아니라 원본 코드 전체를 정밀 분석하여, 향후 발생할 수 있는 모든 연쇄 버그(KeyError, ZeroDivisionError, TypeError 등)를 방어 조건문이나 try-except로 미리 완전 치유한 '전체 코드'를 작성하라.\n\n"
        "[절대 수칙]\n"
        "1. 눈앞에 터진 에러만 고치지 말고, 코드 아래쪽에 잠복해 있는 0 나누기나 타입 오류까지 선제적으로 완전히 고쳐라.\n"
        "2. 설명, 인사말, 주석, 마크다운(```)을 절대 포함하지 마라. 오직 즉시 실행 가능한 파이썬 소스코드 전체만 출력하라.\n\n"
        f"[발생한 에러 로그]\n{state['raw_error']}\n\n"
        f"[원본 소스코드]\n{target_code}"
    )
    messages = [
        SystemMessage(content="You are an automated Python full-code patcher. Fix the reported error AND all latent errors in the entire script. Output ONLY executable Python code."),
        HumanMessage(content=prompt)
    ]
    response = llm.invoke(messages)
    raw_text = response.content.strip()

    # 정규식으로 순수 코드만 적출
    code_match = re.search(r'```(?:python)?\s*\n(.*?)\n```', raw_text, re.DOTALL)
    if code_match:
        clean_code = code_match.group(1).strip()
    else:
        clean_code = re.sub(r'^(Here is|This is|Below is|Note:).*$', '', raw_text, flags=re.MULTILINE).strip()

    state['fixed_code'] = clean_code

    if target_file != "N/A" and os.path.exists(target_file) and clean_code:
        try:
            with open(target_file, 'w', encoding='utf-8') as f:
                f.write(clean_code + "\n")
            state['apply_status'] = f"🚀 원본 파일({os.path.basename(target_file)}) 정밀 완전 패치 완료!"
        except Exception as e:
            state['apply_status'] = f"❌ 적용 실패 ({e})"
    else:
        state['apply_status'] = f"⚠️ 적용 스킵 (target_file={target_file})"

    return state


def cli_advisor_node(state: AgentState) -> AgentState:
    """Node 3-B: CLI 해결 명령어 제시"""
    print(f"{YELLOW}⚡ [LangGraph: Node 3-B] 리눅스 CLI 해결 명령어 생성 중...{RESET}")
    sys.stdout.flush()

    prompt = (
        "리눅스 CLI 터미널 에러를 해결할 한 줄 Bash 명령어를 작성하세요.\n\n"
        f"[에러 로그]\n{state['raw_error']}\n\n"
        "[작성 양식]\n"
        "🛠️ **추천 해결 명령어**: (실행할 Bash 명령어)\n"
        "📌 **실행 가이드**: (한 줄 가이드)"
    )
    messages = [
        SystemMessage(content="당신은 리눅스 에러 해결 부관입니다."),
        HumanMessage(content=prompt)
    ]
    response = llm.invoke(messages)
    state['cli_solution'] = response.content.strip()
    return state


def route_error_type(state: AgentState) -> str:
    if state['target_file'] != "N/A":
        return "patcher"
    else:
        return "cli_advisor"


# ==========================================
# Graph Workflow
# ==========================================
workflow = StateGraph(AgentState)

workflow.add_node("backup_parser", parse_and_backup_node)
workflow.add_node("analyzer", analyze_error_node)
workflow.add_node("patcher", code_patcher_node)
workflow.add_node("cli_advisor", cli_advisor_node)

workflow.set_entry_point("backup_parser")
workflow.add_edge("backup_parser", "analyzer")

workflow.add_conditional_edges(
    "analyzer",
    route_error_type,
    {
        "patcher": "patcher",
        "cli_advisor": "cli_advisor"
    }
)

workflow.add_edge("patcher", END)
workflow.add_edge("cli_advisor", END)

app = workflow.compile()


def main():
    print(f"{GREEN}=========================================={RESET}")
    print(f"{GREEN}   🛡️  Linux Helper v2.6 (Strict Code Extractor) {RESET}")
    print(f"{GREEN}   Monitoring Pipe: {FIFO_PATH}{RESET}")
    print(f"{GREEN}   Model: {MODEL_NAME}{RESET}")
    print(f"{GREEN}=========================================={RESET}\n")
    sys.stdout.flush()

    if not os.path.exists(FIFO_PATH):
        os.mkfifo(FIFO_PATH)

    while True:
        try:
            fifo_fd = os.open(FIFO_PATH, os.O_RDONLY | os.O_NONBLOCK)
            with os.fdopen(fifo_fd, 'r') as fifo:
                log_data = fifo.read().strip()
                if log_data:
                    print(f"\n{CYAN}{'='*50}{RESET}")
                    print(f"{BOLD}📊 [AI Terminal Agent - Workflow v2.6]{RESET}")
                    
                    initial_state = {
                        "raw_error": log_data,
                        "target_file": "",
                        "analysis": "",
                        "fixed_code": "",
                        "cli_solution": "",
                        "backup_status": "",
                        "apply_status": ""
                    }
                    result = app.invoke(initial_state)

                    print(f"\n📁 **대상 파일**: {result['target_file']}")
                    print(f"{result['analysis']}\n")
                    
                    if result['target_file'] != 'N/A':
                        print(f"🔒 **백업 상태**: {result['backup_status']}")
                        print(f"🛠️ **적용 상태**: {result['apply_status']}")
                        print(f"\n🛠️ **적용된 수정 코드**:\n```python\n{result['fixed_code']}\n```")
                    else:
                        print(f"{result['cli_solution']}")
                        
                    print(f"{CYAN}{'='*50}{RESET}\n")
                    sys.stdout.flush()
        except Exception:
            pass
        
        time.sleep(0.5)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print(f"\n{RED}[!] 모니터링 서비스 종료.{RESET}")
        sys.exit(0)