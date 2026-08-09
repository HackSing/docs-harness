# Token Budget Decision Tree (v1.8.1)

**目的**: 解释动态 Token 预算的计算逻辑与分层分配策略  
**版本**: v1.8.1 (Kimi Review Edition - 简化版)  
**最后更新**: 2026-08-09  

---

## 一、预算配置常数

```python
class TokenBudgetConfig:
    SIMPLE_TASK = 4096       # 单文件修改、问答类
    MODERATE_TASK = 8192     # 功能实现、跨文件修改 (默认值)
    COMPLEX_TASK = 12288     # 架构变更、多模块协作
    KNOWLEDGE_HEAVY = 16384  # 大量知识库阅读场景
```

---

## 二、决策树流程图

```
任务复杂度评估
    │
    ├── 简单任务 (单文件/问答)
    │   └── base = 4096 tokens
    │
    ├── 中等任务 (跨文件修改)
    │   └── base = 8192 tokens
    │
    └── 复杂任务 (架构变更/多模块)
        └── base = 12288 tokens
            │
            └── 全量指示词检测？
                ├── YES (包含 "full/complete/全部") → base *= 3 = 36864
                └── NO → base 不变
```

### 全量指示词检测规则

```python
full_task_keywords = ["full", "complete", "all", "全部", "全量", "整个项目"]

def is_full_task(task_text: str) -> bool:
    return any(keyword in task_text.lower() for keyword in full_task_keywords)
```

---

## 三、分层分配公式 (Kimi 建议)

```python
def allocate_budget(base: int) -> Dict[str, int]:
    """
    三层分配比例：40% / 40% / 20%
    
    但加上保护上限防止超额:
    - Layer 1 ≤ 4000 tokens (强制首层饱满)
    - Layer 3 ≥ 500 tokens (保底最小单位)
    """
    
    return {
        'layer1': min(base * 0.4, 4000),  # 最多 4k
        'layer2': base * 0.4,              # 无上限
        'layer3': max(base * 0.2, 500)     # 保底 500
    }
```

### 示例计算

| 任务类型 | base | layer1 | layer2 | layer3 | total |
|---------|------|--------|--------|--------|-------|
| Simple | 4096 | 1638 | 1638 | 819 | 4096 ✅ |
| Moderate | 8192 | **3276** | 3276 | 1638 | 8192 ✅ |
| Complex | 12288 | **4000** ⚠️ | 4915 | 2457 | 11372 |
| Knowledge-heavy + Full | 49152 | **4000** ⚠️ | 19660 | 9830 | 33490 |

⚠️ Layer 1 被限制为 4000，多余部分会溢出到 Layer 2

---

## 四、任务复杂度评分器

```python
def calculate_complexity(task: Task) -> float:
    """
    0-1 之间的复杂度评分
    
    评分因子:
    1. 涉及的文件修改数量 (每件 +0.1)
    2. 涉及的模块数量 (每个 +0.15)
    3. 是否需要架构决策 (+1.0)
    """
    
    score = 0.0
    
    # 因子 1: 文件修改数
    score += min(len(task.changes) * 0.1, 0.5)  # 最多贡献 0.5
    
    # 因子 2: 模块影响范围
    score += min(len(task.modules_affected) * 0.15, 0.5)  # 最多贡献 0.5
    
    # 因子 3: 架构决策需求
    if task.requires_architecture_decision():
        score += 1.0
    
    return min(score, 1.0)  # 封顶 1.0
```

### 复杂度分级映射

| 评分范围 | 等级 | base 值 |
|---------|------|--------|
| 0.0 - 0.3 | Simple | 4096 |
| 0.3 - 0.7 | Moderate | 8192 |
| 0.7 - 1.0 | Complex | 12288 |

---

## 五、完整计算流程

```python
async def compute_token_budget(task: Task) -> Tuple[Dict[str, int], Dict]:
    """
    返回:
      1. budget分配字典
      2. trace跟踪信息
    """
    
    # Step 1: 计算复杂度
    complexity = calculate_complexity(task)
    
    # Step 2: 判断是否全量任务
    is_full = any(kw in task.text.lower() for kw in FULL_KEYWORDS)
    
    # Step 3: 确定 base
    if complexity < 0.3:
        base = TokenBudgetConfig.SIMPLE_TASK
    elif complexity < 0.7:
        base = TokenBudgetConfig.MODERATE_TASK
    else:
        base = TokenBudgetConfig.COMPLEX_TASK
        if is_full:
            base *= 3
    
    # Step 4: 分层分配
    budget = allocate_budget(base)
    
    # Step 5: 构建 trace
    trace = {
        'complexity_score': complexity,
        'is_full_task': is_full,
        'base': base,
        'budget_distribution': budget,
        'layer_allocation_ratios': {'layer1': 0.4, 'layer2': 0.4, 'layer3': 0.2}
    }
    
    return budget, trace
```

---

## 六、监控指标 (NFR-03)

```yaml
必须记录的 metrics:
  - repowiki.token_budget_allocated: 分配的总预算
  - repowiki.layer1_tokens_used: Layer 1实际使用
  - repowiki.layer2_tokens_used: Layer 2实际使用  
  - repowiki.truncation_events: 发生截断的次数
  - repowiki.budget_efficiency: actual_tokens / allocated_budget

阈值告警:
  - LAYER1_OVERFLOW > 4000 次/月 → 调整 MIN_LAYER1 cap
  - TRUNCATION_RATE > 5% → 提升 base 值或增加 L1 limit
```

---

## 七、常见问题 (FAQ)

**Q1: 为什么 Layer 1 要限制在 4000？**
A: Kimi 的审查发现，核心知识必须在首层保证足够容量，否则会被 Layer 2/3 挤掉。4000 是经验值，能容纳约 5-6 张知识卡 + 少量代码示例。

**Q2: 如果任务特别复杂怎么办？**
A: base 可能高达 36864 (Complex*3),Layer 2/3 会自动扩大。但如果还是不够，会通过异步加载 + on-demand 机制补充。

**Q3: budget 计算误差大吗？**
A: 误差主要来自复杂度评分，当前方案是启发式的。未来可以通过历史数据训练更精准的模型。

**Q4: 能不能手动指定 budget？**
A: 可以在 task-package.json 中加 `token_budget_override` 字段，但需要有管理员权限。

---

## 八、实施检查清单

- [ ] ✅ harness.py: 添加 calculate_complexity() 函数
- [ ] ✅ 实现 allocate_budget() 分层分配逻辑
- [ ] ✅ 集成 to_full_task 检测逻辑
- [ ] ⏳ 添加 Metrics 埋点
- [ ] ⏳ 编写压力测试脚本 (模拟不同 budget 场景)
- [ ] ⏳ 监控 dashboard 接入

---

**审批状态**: ✅ 已确认 (v1.8.1 方案一部分)  
**负责人**: @product-team  
**关联文档**: [v1.8.1 PRD](./repowiki-retrieval-delivery-system-v1.8.1-plan.md), [Scope Priority Matrix](./scope-priority-matrix-short.md)
