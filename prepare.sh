#!/usr/bin/env bash
# ──────────────────────────────────────────────────────────
#  GraphMind — 后端 Python + MinerU 环境准备
#  用法:
#    ./prepare.sh              # 安装依赖并预下载 MinerU 模型（默认，约几 GB）
#    ./prepare.sh --skip-models # 仅安装依赖，跳过模型预下载
#
#  为什么不用 `uv sync`：
#    raganything 依赖 lightrag-hku<1.5，与我们使用的 1.5.4 冲突，
#    uv 的整体解析会失败。因此这里用手工 `uv pip install` 分步安装，
#    并对 raganything 使用 --no-deps 绕过其过时的版本钉。
# ──────────────────────────────────────────────────────────

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
BACKEND_DIR="$SCRIPT_DIR/backend"
PY_VERSION="3.12"

DOWNLOAD_MODELS=true
for arg in "$@"; do
    case "$arg" in
        --skip-models) DOWNLOAD_MODELS=false ;;
        *) echo "未知参数: $arg"; exit 1 ;;
    esac
done

# ── 检查 uv ───────────────────────────────────────────────
if ! command -v uv &>/dev/null; then
    echo "❌ 未找到 uv，请先安装: https://docs.astral.sh/uv/"
    exit 1
fi

cd "$BACKEND_DIR"

# ── 创建虚拟环境 ──────────────────────────────────────────
if [ ! -d ".venv" ]; then
    echo "🐍 创建虚拟环境 (Python $PY_VERSION)..."
    uv venv --python "$PY_VERSION"
else
    echo "🐍 复用已存在的 .venv"
fi

# ── 安装依赖（分步，避免 raganything 的 lightrag<1.5 钉冲突）──
echo "📦 [1/4] 安装 LightRAG (含 API 依赖: fastapi/uvicorn 等)..."
uv pip install "lightrag-hku[api]==1.5.4"

echo "📦 [2/4] 安装 MinerU + ModelScope（体积较大，含 torch/transformers）..."
uv pip install "mineru[core]==3.4.0" modelscope

echo "📦 [3/4] 安装 RAG-Anything（--no-deps 绕过过时的 lightrag<1.5 钉）..."
uv pip install "raganything==1.3.1" --no-deps

echo "📦 [4/4] 安装后端其余依赖..."
uv pip install \
    "fastapi>=0.115" \
    "uvicorn[standard]>=0.30" \
    "python-multipart>=0.0.9" \
    "sse-starlette>=2.0" \
    "networkx>=3.0" \
    "pyyaml>=6.0"

# ── 准备 LLM 配置 ─────────────────────────────────────────
if [ ! -f "config.local.yaml" ] && [ -f "config.template.yaml" ]; then
    cp config.template.yaml config.local.yaml
    echo "📝 已从模板生成 config.local.yaml，请填入你的 API Key"
fi

# ── 验证导入 ──────────────────────────────────────────────
echo "🔎 验证环境..."
MINERU_MODEL_SOURCE=modelscope .venv/bin/python - <<'PY'
import lightrag, raganything, mineru, modelscope
from app.services import rag_engine  # noqa: F401
from mineru.utils.models_download_utils import resolve_model_source
print(f"  lightrag-hku : {lightrag.__version__ if hasattr(lightrag,'__version__') else 'ok'}")
print(f"  raganything  : ok")
print(f"  mineru       : {mineru.__version__ if hasattr(mineru,'__version__') else 'ok'}")
print(f"  modelscope   : {modelscope.__version__}")
print(f"  模型下载源   : {resolve_model_source()}")
print("  后端服务导入 : ok")
PY

# ── 可选：预下载 MinerU 模型 ──────────────────────────────
if [ "$DOWNLOAD_MODELS" = true ]; then
    echo "⬇️  预下载 MinerU 解析模型（ModelScope，约几 GB，请耐心等待）..."
    MINERU_MODEL_SOURCE=modelscope .venv/bin/python - <<'PY'
from mineru.utils.models_download_utils import auto_download_and_get_model_root_path
# VLM 模型（hybrid/vlm 后端使用）
auto_download_and_get_model_root_path("/", "vlm")
# pipeline 模型（布局/公式/OCR 等）
auto_download_and_get_model_root_path("models/README.md", "pipeline")
print("✅ MinerU 模型已就绪")
PY
fi

echo ""
echo "═══════════════════════════════════════════════"
echo "  ✅ 环境准备完成"
echo ""
echo "  下一步:"
echo "    1. 编辑 backend/config.local.yaml 填入 API Key（若尚未配置）"
echo "    2. 运行 ./start.sh 启动前后端"
if [ "$DOWNLOAD_MODELS" = false ]; then
    echo ""
    echo "  提示: 已跳过模型预下载，首次构建图谱会自动下载 MinerU 模型（几 GB，一次性）。"
fi
echo "═══════════════════════════════════════════════"
