#!/usr/bin/env bash
# P2 端到端联调脚本（需后端已启动：docker compose up 或 uvicorn）
set -euo pipefail

API="${API_URL:-http://localhost:8000/api/v1}"
USER="${ADMIN_USER:-admin}"
PASS="${ADMIN_PASS:-admin123}"

echo "==> 登录"
TOKEN=$(curl -sf -X POST "$API/auth/login" \
  -H "Content-Type: application/json" \
  -d "{\"username\":\"$USER\",\"password\":\"$PASS\"}" | python3 -c "import sys,json; print(json.load(sys.stdin)['data']['access_token'])")
AUTH="Authorization: Bearer $TOKEN"
echo "OK token=${TOKEN:0:20}..."

echo "==> 创建知识库"
KB_ID=$(curl -sf -X POST "$API/kb" -H "$AUTH" -H "Content-Type: application/json" \
  -d '{"name":"E2E知识库","description":"联调"}' | python3 -c "import sys,json; print(json.load(sys.stdin)['data']['id'])")
echo "KB=$KB_ID"

echo "==> 创建 RAG 流程"
GRAPH='{"nodes":[{"id":"input_1","type":"TextInput","data":{"input_key":"query"}},{"id":"search_1","type":"KnowledgeSearch","data":{"top_k":3}},{"id":"prompt_1","type":"PromptTemplate","data":{"template":"资料：{{检索结果}}\n问题：{{用户提问}}"}},{"id":"output_1","type":"TextOutput","data":{}}],"edges":[{"source":"input_1","target":"search_1","targetHandle":"query"},{"source":"input_1","target":"prompt_1","targetHandle":"query"},{"source":"search_1","target":"prompt_1","targetHandle":"hits"},{"source":"prompt_1","target":"output_1","targetHandle":"input"}]}'
FLOW_ID=$(curl -sf -X POST "$API/flows" -H "$AUTH" -H "Content-Type: application/json" \
  -d "{\"name\":\"E2E流程\",\"graph_json\":$GRAPH}" | python3 -c "import sys,json; print(json.load(sys.stdin)['data']['id'])")
echo "FLOW=$FLOW_ID"

echo "==> 发布流程"
curl -sf -X POST "$API/flows/$FLOW_ID/publish" -H "$AUTH" > /dev/null

echo "==> 创建智能体"
AGENT_ID=$(curl -sf -X POST "$API/agents" -H "$AUTH" -H "Content-Type: application/json" \
  -d "{\"name\":\"E2E助手\",\"kb_ids\":[\"$KB_ID\"],\"published_flow_id\":\"$FLOW_ID\"}" \
  | python3 -c "import sys,json; print(json.load(sys.stdin)['data']['id'])")
echo "AGENT=$AGENT_ID"

echo "==> 流程调试运行"
curl -sf -X POST "$API/flows/$FLOW_ID/run" -H "$AUTH" -H "Content-Type: application/json" \
  -d '{"inputs":{"query":"测试问题"}}' | python3 -m json.tool | head -30

echo "==> 智能体对话"
curl -sf -X POST "$API/agents/$AGENT_ID/chat" -H "$AUTH" -H "Content-Type: application/json" \
  -d '{"query":"你好"}' | python3 -m json.tool | head -30

echo "==> P2 联调完成"
