#!/bin/sh
# 新克隆机器执行一次：启用入库的 git 钩子（pre-commit 会在每次提交时自动运行 docs-check）
set -e
cd "$(git rev-parse --show-toplevel)"
git config core.hooksPath scripts/githooks
echo "core.hooksPath = $(git config core.hooksPath)（pre-commit 钩子已启用）"
