#!/usr/bin/env bash

# 自动监控当前仓库是否有改动，有改动就自动提交并推送
# 使用方法：在项目根目录运行：
#   ./auto_commit.sh
# 建议在单独一个终端窗口里运行，想停掉时按 Ctrl+C。

set -euo pipefail

BRANCH="main"               # 如需其他分支可以改这里
INTERVAL=5                    # 检查间隔秒数

while true; do
  # 检查工作区是否有改动
  if git diff-index --quiet HEAD --; then
    sleep "${INTERVAL}"
    continue
  fi

  # 生成简单的自动提交信息
  MSG="Auto commit at $(date '+%Y-%m-%d %H:%M:%S')"

  echo "[auto-commit] 检测到改动，准备提交并推送：$MSG"

  git add -A || {
    echo "[auto-commit] git add 失败，稍后重试" >&2
    sleep "${INTERVAL}"
    continue
  }

  # 有可能没有实际内容（例如权限变化），commit 可能失败，忽略错误继续下一轮
  if git commit -m "$MSG"; then
    # 推送失败（网络、权限等）时，不退出循环，仅提示
    if ! git push origin "$BRANCH"; then
      echo "[auto-commit] git push 失败，请检查网络或凭据" >&2
    else
      echo "[auto-commit] 提交并推送成功"
    fi
  else
    echo "[auto-commit] 没有可提交的内容或提交失败" >&2
  fi

  sleep "${INTERVAL}"
done
