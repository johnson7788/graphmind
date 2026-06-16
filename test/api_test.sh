#!/usr/bin/env bash
# ──────────────────────────────────────────────────────────
#  GraphRAG 后端 API 集成测试
#  用法: ./test/api_test.sh [文件路径]
#  前提: 后端已启动 (http://localhost:8777)
# ──────────────────────────────────────────────────────────

set -e

BASE="http://localhost:8777/api"
TEST_FILE="${1:-}"

# 如果没有指定文件，创建一个测试文件
if [ -z "$TEST_FILE" ]; then
    TEST_FILE="/tmp/graphrag_test_sample.txt"
    cat > "$TEST_FILE" <<'EOF'
人工智能（Artificial Intelligence，简称AI）是计算机科学的一个分支，致力于创建能够模拟人类智能的系统。

机器学习是人工智能的核心领域之一，它使计算机能够从数据中学习并改进性能，而无需显式编程。深度学习是机器学习的一个子领域，使用多层神经网络来处理复杂的模式识别任务。

自然语言处理（NLP）是人工智能的另一个重要领域，它研究如何让计算机理解和生成人类语言。大语言模型（如GPT、Claude、通义千问）是NLP领域的重大突破，它们通过在海量文本上训练，获得了强大的语言理解和生成能力。

知识图谱是一种结构化的知识表示方法，它用图的形式来描述实体之间的关系。GraphRAG是一种结合了知识图谱和检索增强生成（RAG）的技术，它通过构建知识图谱来增强大语言模型的问答能力。
EOF
    echo "📝 已创建测试文件: $TEST_FILE"
fi

echo "═══════════════════════════════════════════"
echo "  GraphRAG API 集成测试"
echo "  后端: $BASE"
echo "  文件: $TEST_FILE"
echo "═══════════════════════════════════════════"
echo ""

# ── Step 1: 检查后端健康状态 ──
echo "🔍 Step 1: 健康检查..."
HEALTH=$(curl -s "$BASE/health")
echo "   $HEALTH"
echo ""

# ── Step 2: 检查配置状态 ──
echo "🔍 Step 2: 配置状态..."
CONFIG=$(curl -s "$BASE/config/status")
echo "   $CONFIG"
echo ""

# ── Step 3: 创建数据集 ──
DATASET_NAME="test_$(date +%Y%m%d_%H%M%S)"
echo "📦 Step 3: 创建数据集 '$DATASET_NAME'..."
CREATE_RESP=$(curl -s -X POST "$BASE/datasets" \
    -H "Content-Type: application/json" \
    -d "{\"name\": \"$DATASET_NAME\"}")
echo "   $CREATE_RESP"
DATASET_ID=$(echo "$CREATE_RESP" | python3 -c "import sys,json; print(json.load(sys.stdin)['id'])")
echo "   Dataset ID: $DATASET_ID"
echo ""

# ── Step 4: 上传文件 ──
echo "📤 Step 4: 上传文件..."
UPLOAD_RESP=$(curl -s -X POST "$BASE/datasets/$DATASET_ID/documents" \
    -F "files=@$TEST_FILE")
echo "   $UPLOAD_RESP"
echo ""

# ── Step 5: 列出文件 ──
echo "📋 Step 5: 列出已上传文件..."
DOCS_RESP=$(curl -s "$BASE/datasets/$DATASET_ID/documents")
echo "   $DOCS_RESP"
echo ""

# ── Step 6: 启动索引 ──
echo "🚀 Step 6: 启动索引..."
INDEX_RESP=$(curl -s -X POST "$BASE/datasets/$DATASET_ID/index" \
    -H "Content-Type: application/json" \
    -d '{"entity_types": ["人物", "技术", "概念", "组织"], "entity_type_mode": "manual"}')
echo "   $INDEX_RESP"
echo ""

# ── Step 7: 轮询索引状态 (最多等待 10 分钟) ──
echo "⏳ Step 7: 轮询索引状态..."
MAX_WAIT=600
ELAPSED=0
LAST_STATUS=""
while [ $ELAPSED -lt $MAX_WAIT ]; do
    STATUS_RESP=$(curl -s "$BASE/datasets/$DATASET_ID/index/status")
    STATUS=$(echo "$STATUS_RESP" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('status','unknown'))" 2>/dev/null || echo "parse_error")
    STEP=$(echo "$STATUS_RESP" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('step',''))" 2>/dev/null || echo "")
    MSG=$(echo "$STATUS_RESP" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('message',''))" 2>/dev/null || echo "")
    PROGRESS=$(echo "$STATUS_RESP" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('progress',0))" 2>/dev/null || echo "0")

    if [ "$STATUS" != "$LAST_STATUS" ] || [ $((ELAPSED % 30)) -eq 0 ]; then
        echo "   [$ELAPSED s] status=$STATUS step=$STEP progress=$PROGRESS msg=$MSG"
        LAST_STATUS="$STATUS"
    fi

    if [ "$STATUS" = "completed" ]; then
        echo ""
        echo "✅ 索引完成！"
        break
    elif [ "$STATUS" = "failed" ]; then
        ERROR=$(echo "$STATUS_RESP" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('error','')[:500])" 2>/dev/null || echo "")
        echo ""
        echo "❌ 索引失败: $ERROR"
        break
    fi

    sleep 3
    ELAPSED=$((ELAPSED + 3))
done

if [ $ELAPSED -ge $MAX_WAIT ]; then
    echo "⏰ 超时（${MAX_WAIT}秒）"
fi

echo ""

# ── Step 8: 检查结果 ──
echo "📊 Step 8: 图谱统计..."
STATS_RESP=$(curl -s "$BASE/datasets/$DATASET_ID/graph/stats" 2>/dev/null)
echo "   $STATS_RESP"
echo ""

# ── Step 9: 清理 ──
read -p "🗑️  是否删除测试数据集? [y/N] " -n 1 -r
echo ""
if [[ $REPLY =~ ^[Yy]$ ]]; then
    curl -s -X DELETE "$BASE/datasets/$DATASET_ID" > /dev/null
    echo "   已删除"
fi

echo ""
echo "═══════════════════════════════════════════"
echo "  测试完成"
echo "═══════════════════════════════════════════"
