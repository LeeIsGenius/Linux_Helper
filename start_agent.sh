#!/usr/bin/env bash

SESSION_NAME="ai_agent"
FIFO_PATH="/tmp/agent_fifo"

# 1. 기존 파이프 및 tmux 세션 초기화
rm -f "$FIFO_PATH"
mkfifo "$FIFO_PATH"
tmux kill-session -t "$SESSION_NAME" 2>/dev/null

# 2. tmux 세션 생성 및 분할
tmux new-session -d -s "$SESSION_NAME" -n "Dashboard"
tmux split-window -h -t "$SESSION_NAME:0"

# 3. [우측 Pane 1] AI 에러 분석 리스너 구동
tmux send-keys -t "$SESSION_NAME:0.1" "source .venv/bin/activate 2>/dev/null || true" C-m
tmux send-keys -t "$SESSION_NAME:0.1" "clear" C-m
tmux send-keys -t "$SESSION_NAME:0.1" "python3 agent_listener.py" C-m

# 4. [좌측 Pane 0] 완전 자동화 세팅 (Bash + Python 자동 캡처)
# 4-1) 파이썬 실행 시 stderr 자동 전달 래퍼
tmux send-keys -t "$SESSION_NAME:0.0" 'python3() { command python3 "$@" 2> >(tee /tmp/agent_fifo >&2); }' C-m

# 4-2) 일반 Bash 명령어 실행 후 에러(종료코드 != 0) 발생 시 자동으로 파이프로 전달하는 로직
tmux send-keys -t "$SESSION_NAME:0.0" 'exec 3>&1 4>&2' C-m
tmux send-keys -t "$SESSION_NAME:0.0" 'trap "echo \"\$(history 1 | sed \"s/^[ ]*[0-9]*[ ]*//\")\" > /tmp/agent_fifo" ERR' C-m

tmux send-keys -t "$SESSION_NAME:0.0" "clear" C-m
tmux send-keys -t "$SESSION_NAME:0.0" "echo '====================================='" C-m
tmux send-keys -t "$SESSION_NAME:0.0" "echo '💻 Developer Workspace Ready (.venv)'" C-m
tmux send-keys -t "$SESSION_NAME:0.0" "echo '====================================='" C-m

# 5. 좌측 포커스 및 세션 연결
tmux select-pane -t "$SESSION_NAME:0.0"
tmux attach-session -t "$SESSION_NAME"