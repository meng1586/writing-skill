#!/usr/bin/env bash
# study_daemon.sh — novel-study 采集预热
#
# 只做一件事：按 shelf.json 里在读的书，把下一批章节抓到本地缓存。
# 理解/拆解永远由 agent 做，这里不写笔记。
#
# 用法：
#   bash scripts/study_daemon.sh             # 抓取
#   bash scripts/study_daemon.sh --dry-run   # 只打印要做什么
#
# 环境变量：
#   NOVEL_STUDY_ROOT  项目根（默认从脚本位置推断）
#   NOVEL_STUDY_STATE 状态目录（默认 <项目>/.cache/novel-study/state）

set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SKILL_DIR="${NOVEL_STUDY_SKILL:-$(dirname "$SCRIPT_DIR")}"
# 运行副本模式下，跑前把工作区书架同步过来（工作区才是权威）
if [[ -n "${NOVEL_STUDY_SYNC_SHELF:-}" && -f "$NOVEL_STUDY_SYNC_SHELF" ]]; then
  mkdir -p "$SKILL_DIR/data"
  cp "$NOVEL_STUDY_SYNC_SHELF" "$SKILL_DIR/data/shelf.json"
fi
PROJECT_ROOT="${NOVEL_STUDY_ROOT:-$(dirname "$(dirname "$SKILL_DIR")")}"
STATE_DIR="${NOVEL_STUDY_STATE:-$PROJECT_ROOT/.cache/novel-study/state}"
SHELF="$SKILL_DIR/data/shelf.json"
FETCH="$SCRIPT_DIR/fetch.py"
CONFIG="$SKILL_DIR/config.json"

DRY_RUN=0
[[ "${1:-}" == "--dry-run" ]] && DRY_RUN=1

mkdir -p "$STATE_DIR"
LOG="$STATE_DIR/prefetch.log"
log() { printf '%s %s\n' "$(date '+%Y-%m-%d %H:%M:%S')" "$*" | tee -a "$LOG"; }

log "=== 预热开始 ${DRY_RUN:+dry-run} ==="

if [[ ! -f "$SHELF" ]]; then
  log "没有 shelf.json，跳过"
  exit 0
fi
if [[ ! -f "$FETCH" ]]; then
  log "fetch.py 不存在，跳过（采集层还没就绪）"
  exit 0
fi

# 每天最多抓的章数
DAILY=$(python3 - "$CONFIG" <<'PY'
import json,sys
try:
    c=json.load(open(sys.argv[1]))
    print(int(c.get("daily_chapters",3)))
except Exception:
    print(3)
PY
)
DAILY=${DAILY:-3}

# 输出 "key|source|book_id|from|to"
JOBS=$(python3 - "$SHELF" "$DAILY" "$PROJECT_ROOT" <<'PY'
import json, os, sys
shelf_path, daily, root = sys.argv[1], int(sys.argv[2]), sys.argv[3]
try:
    shelf = json.load(open(shelf_path))
except Exception:
    sys.exit(0)
for b in shelf.get("books", []):
    if b.get("status") not in ("reading", "unread"):
        continue
    done = int(b.get("chapters_done", 0) or 0)
    total = int(b.get("chapter_total", 0) or 0)
    start = done + 1
    end = start + daily - 1
    if total > 0:
        end = min(end, total)
    if end < start:
        continue
    print(f'{b.get("key")}|{b.get("source")}|{b.get("book_id")}|{start}|{end}')
PY
)

if [[ -z "$JOBS" ]]; then
  log "没有需要预热的书"
  exit 0
fi

while IFS='|' read -r key source book_id from to; do
  [[ -z "$key" ]] && continue
  log "《$key》第 $from-$to 章"
  if [[ $DRY_RUN -eq 1 ]]; then
    log "  [dry-run] python3 $FETCH book --source $source --book-id $book_id --from $from --to $to"
  else
    if python3 "$FETCH" book --source "$source" --book-id "$book_id" \
        --from "$from" --to "$to" --json >>"$LOG" 2>&1; then
      log "  ✅ 完成"
    else
      log "  ❌ 失败（详见上方输出）"
    fi
    # 礼貌限速
    sleep "$(python3 -c 'import random;print(round(random.uniform(1.0,2.0),1))')"
  fi
done <<< "$JOBS"

log "=== 预热结束 ==="
