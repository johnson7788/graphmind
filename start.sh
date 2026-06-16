#!/usr/bin/env bash
# ──────────────────────────────────────────────────────────
#  GraphMind — 一键启动前后端
#  用法: ./start.sh
#  按 Ctrl+C 停止所有服务
# ──────────────────────────────────────────────────────────

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
BACKEND_DIR="$SCRIPT_DIR/backend"
FRONTEND_DIR="$SCRIPT_DIR/frontend"

# 子进程 PID 列表，用于统一清理
PIDS=()

cleanup() {
    echo ""
    echo "⏹  正在停止所有服务..."
    for pid in "${PIDS[@]}"; do
        if kill -0 "$pid" 2>/dev/null; then
            kill "$pid" 2>/dev/null
            wait "$pid" 2>/dev/null
        fi
    done
    echo "✅ 所有服务已停止"
    exit 0
}

trap cleanup SIGINT SIGTERM

# ── 检查依赖 ──────────────────────────────────────────────
echo "🔍 检查环境..."

if ! command -v uv &>/dev/null; then
    echo "❌ 未找到 uv，请先安装: https://docs.astral.sh/uv/"
    exit 1
fi

if ! command -v node &>/dev/null; then
    echo "❌ 未找到 node，请先安装 Node.js"
    exit 1
fi

# ── 安装依赖（如果需要）──────────────────────────────────
if [ ! -d "$BACKEND_DIR/.venv" ]; then
    echo "📦 安装后端依赖..."
    (cd "$BACKEND_DIR" && uv sync --quiet)
fi

if [ ! -d "$FRONTEND_DIR/node_modules" ]; then
    echo "📦 安装前端依赖..."
    (cd "$FRONTEND_DIR" && npm install --silent)
fi

# ── 启动后端 ──────────────────────────────────────────────
echo "🚀 启动后端 (port 8777)..."
(cd "$BACKEND_DIR" && uv run python -m uvicorn app.main:app --port 8777 2>&1 | sed 's/^/[backend]  /') &
PIDS+=($!)

# ── 启动前端 ──────────────────────────────────────────────
echo "🚀 启动前端 (port 5777)..."
(cd "$FRONTEND_DIR" && npm run dev 2>&1 | sed 's/^/[frontend] /') &
PIDS+=($!)

# ── 健康检查 ──────────────────────────────────────────────
wait_for_service() {
    local name="$1" url="$2" pid="$3" max_wait=15
    for i in $(seq 1 $max_wait); do
        if ! kill -0 "$pid" 2>/dev/null; then
            echo "❌ $name 启动失败，进程已退出"
            return 1
        fi
        if curl -sf "$url" &>/dev/null; then
            echo "✅ $name 已就绪"
            return 0
        fi
        sleep 1
    done
    echo "⚠️  $name 启动超时（${max_wait}s），请检查日志"
    return 1
}

wait_for_service "后端" "http://localhost:8777/api/health" "${PIDS[0]}"
wait_for_service "前端" "http://localhost:5777"        "${PIDS[1]}"

# ── 打印信息 ──────────────────────────────────────────────
echo ""
echo "═══════════════════════════════════════════════"
echo "  🧠 GraphMind 已启动"
echo ""
echo "  前端:  http://localhost:5777"
echo "  后端:  http://localhost:8777"
echo "  API文档: http://localhost:8777/docs"
echo ""
echo "  按 Ctrl+C 停止所有服务"
echo "═══════════════════════════════════════════════"
echo ""

# ── 等待所有子进程 ────────────────────────────────────────
wait
