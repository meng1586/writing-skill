#!/usr/bin/env bash
# install_study_job.sh — 把 novel-study 的采集预热装成 launchd 定时任务（可选）
#
# 按工作区 AGENTS.md 的约定：launchd 读不到 macOS「桌面文件夹」（TCC），
# 所以运行副本、书架副本、抓取缓存都放 ~/Library/Application Support/novel-study/。
# 工作区里的 skills/novel-study/ 仍是源码与笔记的权威位置。
#
# 用法：
#   bash scripts/install_study_job.sh            # 安装（会先 dry-run 展示）
#   bash scripts/install_study_job.sh --yes      # 直接安装
#   bash scripts/install_study_job.sh --status   # 看状态
#   bash scripts/install_study_job.sh --uninstall
#
# 注意：launchd 只做「抓章节」，不写笔记、不改书架。

set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SKILL_DIR="$(dirname "$SCRIPT_DIR")"
PROJECT_ROOT="$(dirname "$(dirname "$SKILL_DIR")")"

APPLY_DIR="$HOME/Library/Application Support/novel-study"
LABEL="com.deepseek.novel-study-prefetch"
PLIST="$HOME/Library/LaunchAgents/$LABEL.plist"

cmd="${1:-}"

status() {
  echo "运行副本：$APPLY_DIR"
  [[ -d "$APPLY_DIR" ]] && ls -la "$APPLY_DIR" || echo "  (未安装)"
  echo "plist：$PLIST"
  if [[ -f "$PLIST" ]]; then
    launchctl print "gui/$(id -u)/$LABEL" 2>/dev/null | head -12 || echo "  (已登记但未加载)"
  else
    echo "  (未安装)"
  fi
}

uninstall() {
  launchctl bootout "gui/$(id -u)/$LABEL" 2>/dev/null || true
  rm -f "$PLIST"
  echo "已卸载 launchd 任务；运行副本保留在 $APPLY_DIR（可手动删除）"
}

install() {
  mkdir -p "$APPLY_DIR/scripts" "$APPLY_DIR/data" "$APPLY_DIR/state"
  cp "$SKILL_DIR/scripts/study_daemon.sh" "$APPLY_DIR/scripts/"
  cp "$SKILL_DIR/scripts/fetch.py"        "$APPLY_DIR/scripts/" 2>/dev/null || true
  cp "$SKILL_DIR/data/shelf.json"         "$APPLY_DIR/data/" 2>/dev/null || true
  chmod +x "$APPLY_DIR/scripts/study_daemon.sh"

  cat > "$PLIST" <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key><string>$LABEL</string>
  <key>ProgramArguments</key>
  <array>
    <string>/bin/bash</string>
    <string>$APPLY_DIR/scripts/study_daemon.sh</string>
  </array>
  <key>EnvironmentVariables</key>
  <dict>
    <key>NOVEL_STUDY_SKILL</key><string>$APPLY_DIR</string>
    <key>NOVEL_STUDY_ROOT</key><string>$APPLY_DIR</string>
    <key>NOVEL_STUDY_STATE</key><string>$APPLY_DIR/state</string>
    <key>NOVEL_STUDY_SYNC_SHELF</key><string>$SKILL_DIR/data/shelf.json</string>
  </dict>
  <key>StartCalendarInterval</key>
  <dict><key>Hour</key><integer>9</integer><key>Minute</key><integer>0</integer></dict>
  <key>RunAtLoad</key><false/>
  <key>StandardOutPath</key><string>$APPLY_DIR/state/launchd.out.log</string>
  <key>StandardErrorPath</key><string>$APPLY_DIR/state/launchd.err.log</string>
</dict>
</plist>
EOF

  echo "已写 plist：$PLIST"
  echo "运行副本：$APPLY_DIR"
  echo
  echo "下一步（需要你确认）："
  echo "  launchctl bootstrap gui/$(id -u) $PLIST"
  echo "  或：launchctl load -w $PLIST"
  echo "看日志：tail -f \"$APPLY_DIR/state/prefetch.log\""
}

case "$cmd" in
  --status) status ;;
  --uninstall) uninstall ;;
  --yes) install ;;
  *)
    echo "预览（加 --yes 才真正安装）："
    echo "  会复制 $SKILL_DIR/scripts/study_daemon.sh -> $APPLY_DIR/scripts/"
    echo "  会复制 $SKILL_DIR/scripts/fetch.py        -> $APPLY_DIR/scripts/（如存在）"
    echo "  会复制 $SKILL_DIR/data/shelf.json         -> $APPLY_DIR/data/"
    echo "  会写 $PLIST"
    echo "（这是预览，未写入。）" ;;
esac
