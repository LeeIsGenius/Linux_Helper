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
    temperature=0.1
)

class AgentState(TypedDict):
    raw_error: str
    target_file: str
    analysis: str
    fixed_code: str
    backup_status: str
    apply_status: str


# ==========================================
# Graph Nodes
# ==========================================
def parse_and_backup_node(state: AgentState) -> AgentState:
    """Node 1: Traceback에서 대상 파일 추출 및 .bak 백업 생성"""
    print(f"\n{YELLOW}⚡ [LangGraph: Node 1] 에러 파일 추적 및 백업 생성 중...{RESET}")
    sys.stdout.flush()

    match = re.search(r'File "([^"]+)"', state['raw_error'])
    if match:
        file_path = match.group(1)
        state['target_file'] = file_path
        
        if os.path.exists(file_path):
            backup_path = f"{file_path}.bak"
            try:
                shutil.copyfile(file_path, backup_path)
                state['backup_status'] = f"✅ 백업 완료 ({os.path.basename(backup_path)})"
            except Exception as e:
                state['backup_status'] = f"❌ 백업 실패 ({e})"
        else:
            state['backup_status'] = "⚠️ 파일 경로 부재"
    else:
        state['target_file'] = "N/A"
        state['backup_status'] = "ℹ️ CLI 단일 명령어 실행건"

    return state


def analyze_error_node(state: AgentState) -> AgentState:
    """Node 2: 에러 요약 및 원인 분석"""
    print(f"{YELLOW}⚡ [LangGraph: Node 2] 에러 원인 분석 중...{RESET}")
    sys.stdout.flush()

    prompt = f"""
다음 파이썬/리눅스 에러 로그의 원인을 한글로 간결히 정리하세요.

[에러 로그]
{state['raw_error']}

[작성 양식]
1. 🚨 **오류 요약**: (한 줄 요약)
2. 💡 **원인 분석**: (원인 설명)
"""
    messages = [
        SystemMessage(content="당신은 리눅스/파이썬 에러 분석 전문가입니다."),
        HumanMessage(content=prompt)
    ]
    response = llm.invoke(messages)
    state['analysis'] = response.content.strip()
    return state


def code_patcher_node(state: AgentState) -> AgentState:
    """Node 3: 강제 패치 코드 생성 및 원본 파일 수정 적용"""
    print(f"{YELLOW}⚡ [LangGraph: Node 3] 코드 패치 및 파일 수정 적용 중...{RESET}")
    sys.stdout.flush()

    target_code = ""
    if state['target_file'] != "N/A" and os.path.exists(state['target_file']):
        try:
            with open(state['target_file'], 'r') as f:
                target_code = f.read()
        except Exception:
            target_code = ""

    prompt = f"""
너는 파이썬 버그 수정 자동화 도구이다.
아래 에러와 원본 코드를 분석하여, 에러가 나지 않고 정상 실행되는 수정된 파이썬 코드 '전체'를 작성하라.
설명, 인사말, 마크다운 주석을 절대 포함하지 마라. 오직 실행 가능한 파이썬 소스코드만 출력하라.

[에러 분석]
{state['analysis']}

[원본 코드]
{target_code}
"""
    messages = [
        SystemMessage(content="You are an automated Python code patcher. Output ONLY the corrected executable Python source code without any markdown or conversational response."),
        HumanMessage(content=prompt)
    ]
    response = llm.invoke(messages)
    clean_code = response.content.strip()

    # 마크다운 백틱 및 설명 문구 강제 정제
    clean_code = re.sub(r'^```python\n?', '', clean_code)
    clean_code = re.sub(r'^```\n?', '', clean_code)
    clean_code = re.sub(r'\n?```$', '', clean_code).strip()

    state['fixed_code'] = clean_code

    # 원본 파일에 실제 패치 코드 덮어쓰기
    if state['target_file'] != "N/A" and os.path.exists(state['target_file']) and clean_code:
        try:
            with open(state['target_file'], 'w') as f:
                f.write(clean_code + "\n")
            state['apply_status'] = f"🚀 원본 파일({os.path.basename(state['target_file'])}) 수정 적용 완료!"
        except Exception as e:
            state['apply_status'] = f"❌ 파일 수정 적용 실패 ({e})"
    else:
        state['apply_status'] = "ℹ️ 수정 적용 불가"

    return state


# ==========================================
# Build LangGraph Workflow
# ==========================================
workflow = StateGraph(AgentState)

workflow.add_node("backup_parser", parse_and_backup_node)
workflow.add_node("analyzer", analyze_error_node)
workflow.add_node("patcher", code_patcher_node)

workflow.set_entry_point("backup_parser")
workflow.add_edge("backup_parser", "analyzer")
workflow.add_edge("analyzer", "patcher")
workflow.add_edge("patcher", END)

app = workflow.compile()


# ==========================================
# Main Execution
# ==========================================
def main():
    print(f"{GREEN}=========================================={RESET}")
    print(f"{GREEN}   🛡️  Linux Helper v2.1 (Full Auto-Patcher) {RESET}")
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
                    print(f"{BOLD}📊 [AI Terminal Agent - Auto-Fix & Patch Workflow]{RESET}")
                    
                    initial_state = {
                        "raw_error": log_data,
                        "target_file": "",
                        "analysis": "",
                        "fixed_code": "",
                        "backup_status": "",
                        "apply_status": ""
                    }
                    result = app.invoke(initial_state)

                    print(f"\n📁 **대상 파일**: {result['target_file']}")
                    print(f"🔒 **백업 상태**: {result['backup_status']}")
                    print(f"🛠️ **적용 상태**: {result['apply_status']}\n")
                    print(f"{result['analysis']}")
                    print(f"\n🛠️ **적용된 수정 코드**:\n```python\n{result['fixed_code']}\n```")
                    print(f"{CYAN}{'='*50}{RESET}\n")
                    sys.stdout.flush()
        except Exception:
            pass
        
        time.sleep(0.5)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print(f"\n{RED}[!] AI 에러 모니터링 서비스가 종료되었습니다.{RESET}")
        sys.exit(0)