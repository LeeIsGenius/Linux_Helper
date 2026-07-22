#!/usr/bin/env python3
import os
import sys
import time
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
    temperature=0.2
)

class AgentState(TypedDict):
    raw_error: str
    analysis: str
    solution: str


# ==========================================
# Graph Nodes
# ==========================================
def analyze_error_node(state: AgentState) -> AgentState:
    """Node 1: 에러 요약 및 원인 분석"""
    print(f"{YELLOW}⚡ [LangGraph: Node 1] 에러 원인 분석 중...{RESET}")
    sys.stdout.flush()

    prompt = f"""
당신은 리눅스 및 파이썬 개발 환경을 보좌하는 전문 개발 도우미 AI입니다.
다음 터미널 로그의 발생 원인을 분석하세요.

[에러 로그]
{state['raw_error']}

[작성 양식]
1. 🚨 **오류 요약**: (한 줄로 간결하게 요약)
2. 💡 **원인 분석**: (명령어 오타, 권한 문제, 경로 부재, 파이썬 예외 등 핵심 원인 설명)
"""
    messages = [
        SystemMessage(content="당신은 리눅스/파이썬 에러 분석 전문가입니다."),
        HumanMessage(content=prompt)
    ]
    response = llm.invoke(messages)
    state['analysis'] = response.content.strip()
    return state


def generate_solution_node(state: AgentState) -> AgentState:
    """Node 2: 해결 명령어 제시"""
    print(f"{YELLOW}⚡ [LangGraph: Node 2] 해결 명령어 생성 중...{RESET}")
    sys.stdout.flush()

    prompt = f"""
다음 에러 분석 결과를 바탕으로 개발자가 터미널에서 즉시 실행하여 해결할 수 있는 추천 CLI 명령어와 조치 가이드를 작성하세요.

[에러 분석 결과]
{state['analysis']}

[원본 에러 로그]
{state['raw_error']}

[작성 양식]
3. 🛠️ **해결 명령 및 조치 가이드**: (개발자가 터미널에서 즉시 실행할 수 있는 명령어 및 적용 방법)
"""
    messages = [
        SystemMessage(content="당신은 구체적이고 실용적인 리눅스 해결 명령어를 제공하는 AI 부관입니다."),
        HumanMessage(content=prompt)
    ]
    response = llm.invoke(messages)
    state['solution'] = response.content.strip()
    return state


# ==========================================
# Build LangGraph Workflow
# ==========================================
workflow = StateGraph(AgentState)

workflow.add_node("analyzer", analyze_error_node)
workflow.add_node("planner", generate_solution_node)

workflow.set_entry_point("analyzer")
workflow.add_edge("analyzer", "planner")
workflow.add_edge("planner", END)

app = workflow.compile()


# ==========================================
# Main Execution
# ==========================================
def main():
    print(f"{GREEN}=========================================={RESET}")
    print(f"{GREEN}   🛡️  Linux Helper v2.0 (LangGraph)      {RESET}")
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
                    print(f"{BOLD}📊 [AI Terminal Agent - LangGraph Workflow Start]{RESET}")
                    
                    initial_state = {"raw_error": log_data, "analysis": "", "solution": ""}
                    result = app.invoke(initial_state)

                    print(f"\n{result['analysis']}")
                    print(f"\n{result['solution']}")
                    print(f"{CYAN}{'='*50}{RESET}\n")
                    sys.stdout.flush()
        except Exception as e:
            pass
        
        time.sleep(0.5)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print(f"\n{RED}[!] AI 에러 모니터링 서비스가 종료되었습니다.{RESET}")
        sys.exit(0)