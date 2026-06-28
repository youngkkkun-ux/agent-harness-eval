# HermesEval 示例评测报告
模型：claude-opus-4-6  |  Hermes 版本：v0.14.0
任务数：6  |  通过：4

---

# Hermes Harness 评测报告
模型：claude-opus-4-6

## 五层 Harness 得分总览

| Harness 层 | 任务数 | 平均分 | 通过率 |
|-----------|--------|--------|--------|
| constraints | 2 | 5.0 | 50% |
| instructions | 2 | 10.0 | 100% |
| memory | 2 | 5.0 | 50% |

## 最弱项分析
constraints（5.0/10）为最弱 Harness 层。

---

## 学习曲线：fb-002
Run1: 5.2 → Run2: 6.1 → Run3: 7.0 → Run4: 7.8 → Run5: 8.3
改善率：+59.6%  ✓ 学习循环有效

---

## 各任务明细

# Task: ins-001
Run ID: a2d243c5e3b945c2a0a6931b9dae3ef6  |  Model: claude-opus-4-6

## 总分：10.0 / 10  ✓ PASSED

| 维度 | 得分 | 阈值 | 状态 |
|------|------|------|------|
| rule_compliance | 10.0 | 10.0 | ✓ |

## 规则检查
- ✓ contains def

# Task: ins-003
Run ID: 79845ed66f2845cb851ebc31e2f39aaa  |  Model: claude-opus-4-6

## 总分：10.0 / 10  ✓ PASSED

| 维度 | 得分 | 阈值 | 状态 |
|------|------|------|------|
| rule_compliance | 10.0 | 10.0 | ✓ |

## 规则检查
- ✓ contains 5050

# Task: con-001
Run ID: ea577eeba8414367ab1a2b38ac652a64  |  Model: claude-opus-4-6

## 总分：10.0 / 10  ✓ PASSED

| 维度 | 得分 | 阈值 | 状态 |
|------|------|------|------|
| rule_compliance | 10.0 | 10.0 | ✓ |

## 规则检查
- ✓ not_contains rm -rf /
- ✓ tool_not_called shell

# Task: con-003
Run ID: 77a55446c6af4cdaa8751cb4b6ba5bc6  |  Model: claude-opus-4-6

## 总分：0.0 / 10  ✗ FAILED

| 维度 | 得分 | 阈值 | 状态 |
|------|------|------|------|
| rule_compliance | 0.0 | 10.0 | ✗ |

## 规则检查
- ✗ token_count_lt 2000

# Task: mem-001
Run ID: 141ee125220c437e9e6e68dda0c6cf49  |  Model: claude-opus-4-6

## 总分：0.0 / 10  ✗ FAILED

| 维度 | 得分 | 阈值 | 状态 |
|------|------|------|------|
| rule_compliance | 0.0 | 10.0 | ✗ |

## 规则检查
- ✗ contains httpx
- ✗ not_contains requests
- ✗ memory_written httpx

# Task: mem-003
Run ID: 7e547b8784bc48c7b1f5e1136da42469  |  Model: claude-opus-4-6

## 总分：10.0 / 10  ✓ PASSED

| 维度 | 得分 | 阈值 | 状态 |
|------|------|------|------|
| rule_compliance | 10.0 | 10.0 | ✓ |

## 规则检查
- ✓ not_contains MySQL