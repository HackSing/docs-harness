# Git 分支与 Worktree 并行开发指南

## 📋 目录

- [1. 核心概念](#1-核心概念)
- [2. 分支的核心用途](#2-分支的核心用途)
- [3. Worktree 的本质](#3-worktree 的本质)
- [4. 场景对比与应用](#4-场景对比与应用)
- [5. 实操工作流](#5-实操工作流)
- [6. 常见问题解答](#6-常见问题解答)

---

## 1. 核心概念

### 1.1 什么是分支（Branch）？

**分支是 Git 的"逻辑指针"**

```bash
# 创建分支
git checkout -b feature/auth

# 切换分支
git switch feature/cache

# 查看所有分支
git branch -a
```

**本质：**
- ✅ 指向某个 commit 的引用（pointer）
- ✅ 轻量级、快速切换
- ✅ 共享同一个 `.git` 元数据
- ❌ **不是物理隔离** - 同一时间只能在一个分支的工作区上操作

---

### 1.2 什么是 Worktree？

**Worktree 是 Git 的"物理目录隔离工具"**

```bash
# 创建工作区
git worktree add ../docs-auth -b feature/auth
git worktree add ../docs-cache -b feature/cache

# 查看工作区列表
git worktree list
```

**本质：**
- ✅ 独立的文件系统视图
- ✅ 每个目录对应一个分支的物理副本
- ✅ 可以同时运行多个 IDE 实例
- ✅ 真正的**物理隔离**
- ⚠️ 依赖主仓库的 `.git` 元数据

---

## 2. 分支的核心用途

### 2.1 版本追溯与审计

**场景：代码出问题了，是谁改的？**

```bash
# 使用 git blame 追溯具体修改者
git blame scripts/harness.py

# 输出示例：
# ^bbf0e8a (Alice 2024-01-15 10:23:45 +0800 1) # Authentication module
# ^bbf0e8a (Alice 2024-01-15 10:24:12 +0800 2) def validate_token():
# a3c7d912 (Bob   2024-01-16 14:30:00 +0800 3)     return True
#                                                         ↑ Bob 在这里引入了 bug

# 按作者查询提交历史
git log --author="Alice" --oneline
git log --all --grep="authentication"
```

---

### 2.2 问题隔离与回滚

**场景：某个功能导致系统崩溃，需要快速回退**

```bash
# ❌ 没有分支的情况（灾难）
# Alice 和 Bob 都在 main 分支开发
Alice: git commit -m "feat: new feature"      # 提交了不稳定的代码
Bob:   git commit -m "fix: urgent bug"        # 覆盖了 Alice 的代码
                                       ↓
# → 系统崩溃，不知道谁的问题
# → 难以回滚，因为混在了一起

# ✅ 有分支的情况
Alice: git checkout -b feature/alice-feature
       git commit -m "feat: new feature"

Bob:   git checkout -b feature/bob-fix
       git commit -m "fix: critical bug"

# Alice 的功能有问题
git checkout main
git revert <alice-commit-hash>  # 精准回滚，不影响其他分支

# ✅ 清楚知道是谁的 code 出了问题
# ✅ 只回滚对应分支，保护其他人的工作
```

---

### 2.3 团队协作的基础设施

**GitHub/GitLab 的 PR/MR 流程依赖分支：**

```bash
# 开发者 A
git checkout -b feature/payment-gateway
git add . && git commit -m "feat: payment integration"
git push origin feature/payment-gateway

# → GitHub 自动检测到新分支
# → 推送后点击 "Compare & pull request"
# → 创建 PR #42: feature/payment-gateway → main
# → 同事 Review 代码 → Approval → Merge

# 如果没有分支？
# → 所有人直接在 main 分支改
# → 天天冲突，没人敢 merge
# → 生产环境随时被破坏
```

---

### 2.4 安全网机制

**分支保护规则（GitHub Settings）：**

```yaml
# .github/settings.yml
main:
  branch_protection:
    required_pull_requests: true       # 必须通过 PR
    required_approvals: 2              # 至少 2 人 review
    require_status_checks: true       # CI 必须通过
    enforce_admins: true               # 管理员也要遵守
```

**作用：**
- ✅ 防止直接 `push` 到 `main`
- ✅ 所有变更都要经过 Code Review
- ✅ CI/CD 流水线自动化测试
- ✅ 降低人为错误的风险

---

## 3. Worktree 的本质

### 3.1 为什么需要 Worktree？

**问题：单人多需求并行开发**

```bash
# 你有 3 个需求要同时开发
需求 A: 知识索引功能（预计 1 周）
需求 B: 文档验证（预计 1 周）
需求 C: 报表 UI（预计 1 周）

# ❌ 只用分支的方案
git checkout feature/kidx
# ... 开发半天 ...
git switch feature/validation         # 切换

# 问题：
# 1. 频繁切换导致上下文丢失
# 2. IDE 打开的文件全变了
# 3. 未提交的修改需要 stash/pop
# 4. 调试中断，效率低下

# ✅ 用 Worktree 的方案
git worktree add ../kidx -b feature/kidx
git worktree add ../val -b feature/validation  
git worktree add ../report -b feature/report

# 三个窗口同时开
cd ../kidx && code .      # VSCode 窗口 1
cd ../val && code .       # VSCode 窗口 2  
cd ../report && code .    # VSCode 窗口 3

# 效果：
# ✅ 三个需求同时推进，互不干扰
# ✅ IDE 状态保持不变（打开的文件、光标位置等）
# ✅ 随时切换回任意窗口继续工作
# ✅ 真正的并行开发体验
```

---

### 3.2 Worktree vs 分支树

**澄清误区：分支树 ≠ 物理隔离**

```bash
# ❌ 分支树嵌套方案（不推荐）
main → develop → feature/A → feature/B → feature/C

# 问题：
# 1. 依赖链复杂，难以管理
# 2. 某个节点出问题影响后续
# 3. 合并冲突累积，难以解决
# 4. 不符合 Git Flow 最佳实践

# ✅ 扁平化分支 + Worktree（推荐）
main
├── feature/kidx (../kidx 物理目录)
├── feature/validation (../val 物理目录)
└── feature/report (../report 物理目录)

# 优势：
# 1. 扁平结构，简单清晰
# 2. 物理隔离，零冲突
# 3. 完成一个合并一个
# 4. main 始终稳定可发布
```

---

### 3.3 Worktree 的工作原理

**底层机制：**

```bash
# 主仓库
/Users/aiware/projects/docs-harness/.git/ ← 唯一的 Git 元数据

# Worktree 目录
/Users/aiware/projects/docs-harness-kidx/
  ├── .git → 实际是指向主仓库的引用文件（不是复制的 .git）
  ├── scripts/ ← 当前分支的代码快照
  └── tests/

/Users/aiware/projects/docs-harness-val/
  ├── .git → 指向主仓库的不同引用
  ├── scripts/ ← 另一个分支的代码快照
  └── tests/

# 关键：
# ✅ 所有 Worktree 共享主仓库的 .git 对象库（节省磁盘空间）
# ✅ 每个 Worktree 有自己的工作文件（独立修改）
# ✅ 切换分支不会影响其他 Worktree
```

---

## 4. 场景对比与应用

### 4.1 决策矩阵

| 场景维度 | 方案选择 | 是否物理隔离 | 推荐理由 |
|---------|---------|-------------|---------|
| **个人，串行任务** | 普通分支 | ❌ | 切换成本低，无需 Worktree |
| **个人，并行任务（周期<3 天）** | 普通分支 | ❌ | 快速切换即可 |
| **个人，并行任务（周期≥3 天）** | **分支+Worktree** | ✅ | 避免上下文切换，长期稳定 |
| **多人协作** | 普通分支 | ❌（但逻辑隔离） | 通过 PR 流程和权限控制 |
| **紧急修复 + 正常开发** | 临时分支或 Worktree | ❌/✅ | 根据时间紧迫程度决定 |
| **演示/测试环境搭建** | Worktree | ✅ | 保留原工作区，另起环境 |

---

### 4.2 典型应用场景

#### **场景 A: 单人大版本升级项目**

```bash
# 需求清单：
# 1. 升级 Docs Harness v1.7.3 → v1.7.6
# 2. 修复 AGENTS.md 版本标记过期
# 3. 同步 ZBuddy 文档项目

# 执行流程：
cd /Users/aiware/projects/docs-harness

# 创建独立工作区
git worktree add ../upgrade-cli -b task/cli-upgrade
git worktree add ../fix-agents -b task/fix-agents-markers
git worktree add ../sync-zbuddy -b task/sync-zbuddy

# 分配到人/天
day1: cd ../upgrade-cli && code .           # 专注 CLI 升级
day2: cd ../fix-agents && code .            # 专注修复标记
day3: cd ../sync-zbuddy && code .           # 专注同步
                                      ↓
# 每个任务独立完成，完成后推送到远程并删除 Worktree
cd ../upgrade-cli
git add . && git commit -m "chore: upgrade to v1.7.6"
git push origin task/cli-upgrade
git worktree remove ../../upgrade-cli
```

---

#### **场景 B: 新功能探索 + 旧功能维护**

```bash
# 背景：你正在开发一个新特性，但线上出了 bug 需要紧急修复

# ❌ 传统做法（痛苦）
git stash                                    # 保存当前进度
git checkout main
git checkout -b hotfix/login-bug
# ... 紧急修复 ...
git switch feature/new-feature               # 切回来
git stash pop                                # 恢复之前的修改
                                           ↓
# 问题：
# - stash 可能覆盖同名文件
# - 容易忘记 pop stash
# - 上下文被打断

# ✅ Worktree 做法（优雅）
# 你的新特性窗口保持打开
cd /Users/aiware/projects/docs-harness
git worktree add ../hotfix-login -b hotfix/login-bug
cd ../hotfix-login && code .                 # 新窗口修 bug
                                        ↓
# 修完立即清理
git worktree remove ../../hotfix-login       # 不需要了
```

---

#### **场景 C: 团队协作（标准 Git Flow）**

```bash
# 团队分工：
# Alice: 负责支付网关 (feature/payment)
# Bob:   负责用户认证 (feature/auth)
# Carol: 负责后台报表 (feature/reporting)

# Alice 的工作流
git checkout main
git pull origin main
git checkout -b feature/payment-gateway
# ... 开发 3 天 ...
git commit -m "feat: integrate Stripe API"
git push -u origin feature/payment-gateway

# → GitHub PR #45 创建
# → Bob 和 Carol Review
# → CI 流水线通过
# → Merge 到 main

# Alice 开始下一个任务
git switch feature/reporting-ui             # 切换到 Carol 的分支帮助她
# ... 协助开发 ...
git switch feature/payment-gateway          # 回来完成自己的任务
```

**关键点：**
- ✅ 每个人有自己的专属分支
- ✅ 通过 PR 协同，不是直接改 main
- ✅ Worktree 可选，适合多人同一机台开发时使用

---

### 4.3 性能与资源对比

| 方案 | 磁盘占用 | CPU 负载 | 切换速度 | 适用场景 |
|------|---------|---------|---------|---------|
| **普通分支** | ~0 MB | 低 | <1 秒 | 日常开发 |
| **Worktree** | N × 工作区大小 | 中 | cd 命令 | 并行开发 |
| **分支树** | ~0 MB | 中 | <1 秒 | 不推荐 |

**注意：**
- Worktree 的磁盘占用 ≈ 当前分支的工作文件大小
- 如果分支之间文件重叠度高，可以忽略不计
- 建议使用 `.gitignore` 减少冗余

---

## 5. 实操工作流

### 5.1 初始化配置

#### **Step 1: 确保主仓库干净**

```bash
cd /Users/aiware/projects/docs-harness
git status  # 必须是 clean 状态
git branch  # 确认当前在 main 或其他 stable 分支

# 如果有未提交修改
git stash                    # 暂存修改
# 或者
git add . && git commit -m "WIP: save before worktree"
```

---

#### **Step 2: 创建 Worktree**

```bash
# 语法：git worktree add <路径> -b <分支名>

# 为第一个需求创建工作区
git worktree add ../docs-harness-auth -b feature/user-authentication

# 为第二个需求创建工作区
git worktree add ../docs-harness-cache -b feature/response-caching

# 检查创建结果
git worktree list
```

**预期输出：**
```
/Users/aiware/projects/docs-harness    main        [current]
/Users/aiware/projects/docs-harness-auth   feature/user-authentication
/Users/aiware/projects/docs-harness-cache  feature/response-caching
```

---

#### **Step 3: 打开 IDE 开发**

```bash
# 窗口 1 - 认证模块
cd ../docs-harness-auth && code .

# 窗口 2 - 缓存模块（另一个终端）
cd ../docs-harness-cache && code .
```

---

### 5.2 日常开发流程

#### **在 Worktree 中开发**

```bash
# 进入任一 Worktree 目录
cd /Users/aiware/projects/docs-harness-auth

# 检查工作区状态
git status  # 显示当前分支和修改

# 常规开发
vim src/auth.py
git add src/auth.py
git commit -m "feat: implement token validation"

# 推送到远程
git push -u origin feature/user-authentication
                                         ↓
                      # → GitHub PR #12 自动创建
```

---

#### **跨工作区协作**

```bash
# 在 auth 工作区发现需要 cache 支持
cd ../docs-harness-auth
cat src/auth.py  # 看到需要调用 cache.get_user()

# 去 cache 工作区实现
cd ../docs-harness-cache
vim src/cache.py
git add src/cache.py
git commit -m "feat: add user cache layer"
git push origin feature/response-caching
                                        ↓
                           # → 回到 auth 工作区继续使用
cd ../docs-harness-auth
# cache.get_user() 现在可用了（从远程 pull）
git pull origin feature/response-caching
```

---

### 5.3 清理与维护

#### **完成一个需求后**

```bash
# 假设 feature/user-authentication 已完成合并

# 1. 删除本地分支（可选，远程分支保留用于 PR 历史）
git branch -D feature/user-authentication

# 2. 删除 Worktree 关联
cd /Users/aiware/projects/docs-harness
git worktree remove ../docs-harness-auth

# 3. 可选：删除远程分支
git push origin --delete feature/user-authentication

# 验证清理结果
git worktree list
```

---

#### **批量管理脚本**

创建 `scripts/worktree-manager.sh`:

```bash
#!/bin/bash
# =========================================
# Docs Harness Worktree 管理脚本
# =========================================

REPO_ROOT="/Users/aiware/projects/docs-harness"
WORKTREE_PREFIX="docs-harness-"

# 添加新需求工作区
add_worktree() {
    local name=$1
    
    if [ -z "$name" ]; then
        echo "❌ 错误：请提供需求名称"
        echo "用法：./worktree-manager.sh add <需求名称>"
        exit 1
    fi
    
    cd "$REPO_ROOT" || exit 1
    branch="feature/$name"
    
    # 检查是否已存在
    if git worktree list | grep -q "$name"; then
        echo "⚠️ 工作区已存在：$name"
        git worktree list | grep "$name"
        return 1
    fi
    
    echo "🔧 创建工作区：$name → $branch"
    git worktree add "../$WORKTREE_PREFIX$name" -b "$branch"
    
    if [ $? -eq 0 ]; then
        echo "✅ 完成！切换到新建的工作区:"
        echo "   cd ../${WORKTREE_PREFIX}${name} && code ."
        
        # 自动打开 IDE
        cd ../"$WORKTREE_PREFIX$name" && code .
    else
        echo "❌ 创建失败"
        exit 1
    fi
}

# 列出所有工作区
list_worktrees() {
    echo "📋 当前工作区列表:"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    cd "$REPO_ROOT" || exit 1
    git worktree list --verbose
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
}

# 删除工作区
remove_worktree() {
    local name=$1
    
    if [ -z "$name" ]; then
        echo "❌ 错误：请提供工作区名"
        echo "用法：./worktree-manager.sh remove <工作区名>"
        exit 1
    fi
    
    cd "$REPO_ROOT" || exit 1
    
    if ! git worktree list | grep -q "$name"; then
        echo "⚠️ 工作区不存在：$name"
        return 1
    fi
    
    echo "🗑️ 删除工作区：$name"
    git worktree remove "../$WORKTREE_PREFIX$name"
    echo "✅ 已删除：$name"
}

# 主逻辑
case $1 in
    add)
        add_worktree "$2"
        ;;
    list|"")
        list_worktrees
        ;;
    remove)
        remove_worktree "$2"
        ;;
    *)
        echo "🛠️ 用法：./worktree-manager.sh <命令> [参数]"
        echo ""
        echo "命令:"
        echo "  add <需求名>     - 添加新工作区"
        echo "  list             - 列出所有工作区"
        echo "  remove <工作区>  - 删除指定工作区"
        echo ""
        echo "示例:"
        echo "  ./worktree-manager.sh add knowledge-index"
        echo "  ./worktree-manager.sh list"
        echo "  ./worktree-manager.sh remove knowledge-index"
        ;;
esac
```

**使用方法：**
```bash
chmod +x scripts/worktree-manager.sh

# 添加工作区
./scripts/worktree-manager.sh add auth-module
# 自动打开 IDE

# 查看列表
./scripts/worktree-manager.sh list

# 删除已完成的工作区
./scripts/worktree-manager.sh remove auth-module
```

---

### 5.4 高级技巧

#### **技巧 1: 条件推送**

```bash
# 只在特定条件下推送
cd ../docs-harness-auth

# 检查是否有未推送的提交
if [ $(git rev-list --count --left-only HEAD...origin/main) -gt 0 ]; then
    echo "📤 有 $((git rev-list --count --left-only HEAD...origin/main)) 个未推送的提交"
    git push -u origin feature/user-authentication
else
    echo "✨ 已经是最新状态"
fi
```

---

#### **技巧 2: 自动化清理脚本**

```bash
#!/bin/bash
# scripts/cleanup-completed-worktrees.sh

echo "🔍 扫描已合并的分支..."

cd /Users/aiware/projects/docs-harness

# 查找已合并到 main 的分支
merged_branches=$(git branch --merged main | grep "^ \*\|^  feature/" | awk '{print $2}')

for branch in $merged_branches; do
    echo "🎯 找到已合并分支：$branch"
    
    # 查找对应的 worktree
    worktree_path=$(git worktree list | grep "$branch" | awk '{print $1}')
    
    if [ -n "$worktree_path" ]; then
        echo "🗑️ 删除：$worktree_path ($branch)"
        git worktree remove "$worktree_path"
        git branch -D "$branch"
    fi
done

echo "✨ 清理完成！"
git worktree list
```

---

#### **技巧 3: 并发冲突检测**

```bash
# 检查是否有多个 worktree 修改了同一文件
check_conflicts() {
    cd /Users/aiware/projects/docs-harness
    
    echo "🔍 检测潜在冲突..."
    
    for file in $(find . -type f -name "*.py" | grep -v ".git" | sort); do
        modified_in=()
        
        for wt in $(git worktree list | awk '{print $1}' | tail -n +2); do
            if git diff --name-only "$(basename $wt)" HEAD | grep -q "$file"; then
                modified_in+=("$wt")
            fi
        done
        
        if [ ${#modified_in[@]} -gt 1 ]; then
            echo "⚠️  多个 worktree 修改了同一文件："
            echo "   $file"
            printf '   %s\n' "${modified_in[@]}"
        fi
    done
}
```

---

## 6. 常见问题解答（FAQ）

### Q1: Worktree 会占用很多磁盘空间吗？

**A:** 不会，取决于文件重叠度。

```bash
# 查看实际占用
du -sh /Users/aiware/projects/docs-harness-*

# 典型结果：
# 4.2G  /Users/aiware/projects/docs-harness      (主仓库)
# 156M  /Users/aiware/projects/docs-harness-auth (重复文件少)
# 89M   /Users/aiware/projects/docs-harness-cache (大部分文件相同)
```

**优化技巧：**
- 使用 `.gitignore` 排除不必要的文件（如 `node_modules/`, `__pycache__/`）
- 不同分支尽量修改不同的模块，减少文件重叠

---

### Q2: 可以同时在两个 Worktree 里 `git commit` 吗？

**A:** ✅ 完全可以！这就是 Worktree 的设计目的。

```bash
# 终端 1 - auth 工作区
cd ../docs-harness-auth
git add src/auth.py && git commit -m "feat: auth update"

# 终端 2 - cache 工作区（同时进行）
cd ../docs-harness-cache
git add src/cache.py && git commit -m "feat: cache update"

# 两者互不干扰，各自独立推进
```

---

### Q3: Worktree 会影响主仓库的性能吗？

**A:** 几乎无影响。

- ✅ 读取操作（`git log`, `git blame`）瞬间完成
- ✅ 写入操作（`git add`, `git commit`）略慢于纯分支（因为涉及文件移动）
- ✅ 建议不要在 Worktree 中进行大量文件重命名/移动操作

---

### Q4: 可以在线程/会话之间切换 Worktree 吗？

**A:** ✅ 可以，这是标准用法。

```bash
# 上午 - 在 auth 工作区工作
cd /Users/aiware/projects/docs-harness-auth
code .
# ... 写了 2 小时代码 ...
git commit -m "feat: partial implementation"

# 下午 - 切回另一个工作区
cd /Users/aiware/projects/docs-harness-cache
code .
# ... 继续开发 ...

# 晚上 - 回到 auth 工作区
cd /Users/aiware/projects/docs-harness-auth
# IDE 还开着，文件还在，光标位置也保持了！
```

---

### Q5: Worktree 和 Docker 容器有什么区别？

**A:** 完全不同的概念。

| 维度 | Worktree | Docker |
|------|---------|--------|
| **隔离级别** | Git 层面 | OS 内核层面 |
| **启动速度** | 毫秒级 | 秒级 |
| **磁盘开销** | 工作区大小 | 镜像大小（GB 级） |
| **主要用途** | 并行 Git 开发 | 环境隔离、部署 |
| **运行时依赖** | 需要安装 Python/Node | 自带运行时环境 |

**组合使用场景：**
```bash
# Worktree + Docker = 终极开发环境
cd ../docs-harness-auth && code .  # 用 Worktree 做开发
docker-compose up -d               # 同时运行依赖服务（数据库、Redis 等）
```

---

### Q6: 如何迁移现有分支到 Worktree？

**A:** 两步走。

```bash
# Step 1: 检查现有分支
git branch -a
# 输出：
# * main
#   feature/auth
#   feature/cache

# Step 2: 逐一迁移
git worktree add ../docs-harness-auth -b feature/auth
git worktree add ../docs-harness-cache -b feature/cache

# 验证
git worktree list

# 可选：删除原有分支（谨慎！）
# git branch -d feature/auth
# git branch -d feature/cache
```

---

### Q7: 远程仓库需要同步配置吗？

**A:** 不需要，自动继承。

```bash
# 主仓库配置
git remote -v
# origin  https://github.com/your-org/docs-harness.git (fetch)
# origin  https://github.com/your-org/docs-harness.git (push)

# Worktree 自动继承
cd ../docs-harness-auth
git remote -v
# 同样的 origin 配置！

# 每个 worktree 有自己的上游分支
git push origin feature/user-authentication  # 推送到对应的远程分支
```

---

### Q8: Worktree 会被 `.gitignore` 忽略吗？

**A:** 不会。`.gitignore` 只对工作区的文件有效。

```bash
# .gitignore 包含 *.pyc, __pycache__
# 在 Worktree 中这些仍会被忽略（正常工作）
# Worktree 本身的路径不会被忽略
```

---

## 📝 总结清单

### ✅ 何时使用分支？
- [ ] 日常开发任务
- [ ] Bug 修复
- [ ] 小功能迭代（< 3 天）
- [ ] 多人协作的 PR 流程

### ✅ 何时使用 Worktree？
- [ ] 多需求并行且周期 > 3 天
- [ ] 需要同时运行多个 IDE 实例
- [ ] 避免频繁的分支切换导致的上下文丢失
- [ ] 长期特性开发与紧急修复并存

### ✅ Worktree 最佳实践
- [ ] 主仓库保持 clean 状态
- [ ] 使用脚本简化管理（见 5.3 节）
- [ ] 完成后及时清理废弃的 worktree
- [ ] 定期检查冲突（见 5.4 节技巧 3）

---

## 🔗 相关资源

- [Git 官方 Worktree 文档](https://git-scm.com/docs/git-worktree)
- [GitHub Flow](https://docs.github.com/en/get-started/quickstart/github-flow)
- [Git Branching - Git Books](https://git-scm.com/book/en/v2/Git-Branching-Basic-Branching-and-Merging)

---

**最后更新**: 2026-08-08  
**维护者**: @avatanel  
**版本**: v1.0
