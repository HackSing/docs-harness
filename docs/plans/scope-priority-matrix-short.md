# Scope Priority Matrix (v1.8.1)

**目的**: 明确 RepoWiki 知识卡 scope 字段的优先级规则与兼容策略  
**版本**: v1.8.1 (吸收 Kimi 审查意见后简化)  
**最后更新**: 2026-08-09  

---

## 一、Scope 值定义表

| Scope 值 | 匹配强度 | 行为 | 使用场景 | 推荐度 |
|---------|---------|------|---------|-------|
| `exact:*` | 🔴 强制加载 | 仅当任务模块精确匹配时必送 | 核心架构/必须知道的知识 | ✅ **推荐用于关键卡** |
| `module/*` | 🟡 精确匹配 | fnmatch 精确路径匹配 | 特定模块相关卡 | ✅ **推荐** |
| `*` | 🟠 fnmatch | Shell 通配符模糊匹配 | 通用技术知识 (如"日志系统") | ⚠️ 谨慎使用 |
| `**` | 🔵 候选池≤3张 | 进入排序候选池，取 top 3 | 无法确定范围的外部依赖卡 | ⚠️ **已废弃，需替换** |

---

## 二、优先级顺序

```python
# 处理顺序 (从高到低):
1. exact:* → 强制加载 (不经过排序)
2. module/* → 精确匹配后加载
3. * → fnmatch 匹配后限制最多 2 张
4. ** → 进入候选池 + 语义排序 → 最多 3 张
```

**冲突解决规则**:
- 如果同一张卡同时有多个 scope → 按最高优先级处理
- 如果任务同时命中多个 scope → 合并去重后返回

---

## 三、兼容性映射 (历史包袱)

### v1.7.x 遗留的 `**` 如何处理？

```python
# 在 resolve_repowiki_knowledge() 中自动映射:
if card["scope"] == ["**"]:
    # 1. 进入候选池而非强制加载
    wildcard_candidates.append(card)
    
    # 2. 通过相关性排序过滤
    ranked = rank_by_minimal_relevance(wildcard_candidates, task_intent)[:3]
    
    # 3. 最终只保留前 3 高分的卡
    selected.extend(ranked)
```

**效果**: 
- ❌ ZBuddy 任务中 19 张 `**` 卡不会全部召回
- ✅ 只有相关性评分前 3 的会进入上下文
- ✅ 给后续清理工作留出时间窗口

---

## 四、迁移路线图

### 短期 (v1.8.1 - 立即生效)
```yaml
目标：控制现有 19 张 **卡的影响

行动:
├── ✅ 实施智能过滤机制 (v1.8.1 Phase 1)
├── ✅ **卡进入候选池，最多保留 3 张
└── ⏳ 开始人工排查每张 ** 卡的真实适用范围
```

### 中期 (v1.8.2 - 1 个月内)
```yaml
目标：逐步替换 ** 为具体 scope

行动:
├── 前端样式卡 → scope: ["module/frontend/styles"]
├── Electron 架构卡 → scope: ["module/electron/architecture"]
├── Fyne 托盘库 → scope: ["external_dependency/fyne"]
└── Go WebSockets → scope: ["external_dependency/go-websocket"]
```

### 长期 (v1.9.0 - 半年后)
```yaml
目标：完全废弃 ** 符号

行动:
├── Qoder Prompt 禁用生成 **
├── Review 机制拒绝含 ** 的新卡
└── 剩余 ** 卡批量迁移完成
```

---

## 五、常见问题 (FAQ)

**Q1: 为什么还要保留 `**` 而不直接删除？**
A: 向后兼容考虑。现有 19 张卡用了 `**`,突然删除会导致这些卡片完全失效。采用"候选池 + 排序"的过渡方案更稳妥。

**Q2: exact:*和 module/*的区别是什么？**
A: 
- `exact:*` = 必须是这个模块才送 (严格匹配)
- `module/*` = 用 fnmatch 模式可以部分匹配 (宽松一点)

**Q3: 什么时候应该用 `*`？**
A: 当你确实是通用知识但又能限定大致范围时，比如"日志系统"可以用 `src/**` 或 `docs/**`。

**Q4: Qoder 生成的新卡会自动填什么？**
A: v1.8.1 需要修改 Qoder 的 system prompt，禁止随意用 `**`，改为根据内容推断具体 scope。

---

## 六、实施检查清单

- [ ] ✅ harness.py L2400-2450: 添加 scope 类型识别逻辑
- [ ] ✅ 实现 minimal relevance ranking 算法
- [ ] ✅ 设置 TOP_K=3, MIN_SCORE=3.0 阈值
- [ ] ⏳ 编写 cleanup 脚本替换现有 `**` 卡
- [ ] ⏳ 更新 Qoder 的 Prompt 禁止生成 `**`
- [ ] ⏳ 建立月度 Review 机制监控 `**` 卡片数量 (<5% 目标)

---

**审批状态**: ✅ 已确认 (v1.8.1 方案一部分)  
**负责人**: @product-team  
**关联文档**: [v1.8.1 PRD](./repowiki-retrieval-delivery-system-v1.8.1-plan.md)
