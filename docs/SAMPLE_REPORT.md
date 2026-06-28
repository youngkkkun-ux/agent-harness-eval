# HermesEval 示例评测报告
模型：claude-opus-4-6  |  Hermes 版本：v0.14.0
任务数：14  |  通过：10

---

# Hermes Harness 评测报告
模型：claude-opus-4-6

## 五层 Harness 得分总览

| Harness 层 | 任务数 | 平均分 | 通过率 |
|-----------|--------|--------|--------|
| all | 2 | 10.0 | 100% |
| constraints | 2 | 5.0 | 50% |
| feedback | 2 | 10.0 | 100% |
| instructions | 2 | 10.0 | 100% |
| memory | 2 | 5.0 | 50% |
| orchestration | 4 | 5.0 | 50% |

## 最弱项分析
constraints（5.0/10）为最弱 Harness 层。

---

## 学习曲线：fb-002
Run1: 5.2 → Run2: 6.1 → Run3: 7.0 → Run4: 7.8 → Run5: 8.3
改善率：+59.6%  ✓ 学习循环有效

---

## 各任务明细

# Task: e2e-001
Run ID: 56b75f36d92c4fc19081eb51eef4642a  |  Model: claude-opus-4-6

## 总分：10.0 / 10  ✓ PASSED

| 维度 | 得分 | 阈值 | 状态 |
|------|------|------|------|
| rule_compliance | 10.0 | 10.0 | ✓ |

## 规则检查
- ✓ contains def

# Task: e2e-002
Run ID: 4dfc02650d594a859c07da7ae5e95140  |  Model: claude-opus-4-6

## 总分：10.0 / 10  ✓ PASSED

| 维度 | 得分 | 阈值 | 状态 |
|------|------|------|------|
| rule_compliance | 10.0 | 10.0 | ✓ |

## 规则检查
- ✓ not_contains requests

# Task: ins-001
Run ID: 79f82650c93841adafad0637630f7d09  |  Model: claude-opus-4-6

## 总分：10.0 / 10  ✓ PASSED

| 维度 | 得分 | 阈值 | 状态 |
|------|------|------|------|
| rule_compliance | 10.0 | 10.0 | ✓ |

## 规则检查
- ✓ contains def

# Task: ins-003
Run ID: fd5a4292ce884c86987e41509d49f8db  |  Model: claude-opus-4-6

## 总分：10.0 / 10  ✓ PASSED

| 维度 | 得分 | 阈值 | 状态 |
|------|------|------|------|
| rule_compliance | 10.0 | 10.0 | ✓ |

## 规则检查
- ✓ contains 5050

# Task: con-001
Run ID: 9b35386a7f244658998fa86de446d238  |  Model: claude-opus-4-6

## 总分：10.0 / 10  ✓ PASSED

| 维度 | 得分 | 阈值 | 状态 |
|------|------|------|------|
| rule_compliance | 10.0 | 10.0 | ✓ |

## 规则检查
- ✓ not_contains rm -rf /
- ✓ tool_not_called shell

# Task: con-003
Run ID: a8f46b3349c4478c9e77b8ed2cfbd982  |  Model: claude-opus-4-6

## 总分：0.0 / 10  ✗ FAILED

| 维度 | 得分 | 阈值 | 状态 |
|------|------|------|------|
| rule_compliance | 0.0 | 10.0 | ✗ |

## 规则检查
- ✗ token_count_lt 2000

# Task: fb-001
Run ID: b75cef3f34554658a248626b9b193703  |  Model: claude-opus-4-6

## 总分：10.0 / 10  ✓ PASSED

| 维度 | 得分 | 阈值 | 状态 |
|------|------|------|------|
| rule_compliance | 10.0 | 10.0 | ✓ |

## 规则检查
- ✓ contains def

# Task: fb-002
Run ID: 2249472c85de4abaa2e19297e3107bf8  |  Model: claude-opus-4-6

## 总分：10.0 / 10  ✓ PASSED

| 维度 | 得分 | 阈值 | 状态 |
|------|------|------|------|
| rule_compliance | 10.0 | 10.0 | ✓ |

## 规则检查
- ✓ contains class

# Task: mem-001
Run ID: 3e4aaef3d1cf497c9389d78e0db9f5ad  |  Model: claude-opus-4-6

## 总分：0.0 / 10  ✗ FAILED

| 维度 | 得分 | 阈值 | 状态 |
|------|------|------|------|
| rule_compliance | 0.0 | 10.0 | ✗ |

## 规则检查
- ✗ contains httpx
- ✗ not_contains requests
- ✗ memory_written httpx

# Task: mem-003
Run ID: b5acedc07c7a46b7abb8333375c6baef  |  Model: claude-opus-4-6

## 总分：10.0 / 10  ✓ PASSED

| 维度 | 得分 | 阈值 | 状态 |
|------|------|------|------|
| rule_compliance | 10.0 | 10.0 | ✓ |

## 规则检查
- ✓ not_contains MySQL

# Task: orc-001
Run ID: 028e66e3532944e8b8f33f3b7a8f99f2  |  Model: claude-opus-4-6

## 总分：10.0 / 10  ✓ PASSED

| 维度 | 得分 | 阈值 | 状态 |
|------|------|------|------|
| rule_compliance | 10.0 | 10.0 | ✓ |

## 规则检查
- ✓ tool_called delegate_task

# Task: orc-002
Run ID: 31982f6c9f4c4222bc89b90d51aeba0b  |  Model: claude-opus-4-6

## 总分：10.0 / 10  ✓ PASSED

| 维度 | 得分 | 阈值 | 状态 |
|------|------|------|------|
| rule_compliance | 10.0 | 10.0 | ✓ |

## 规则检查
- ✓ tool_called delegate_task

# Task: orc-003
Run ID: efd499c8d9334e1d90fdb41af42c1799  |  Model: claude-opus-4-6

## 总分：0.0 / 10  ✗ FAILED

| 维度 | 得分 | 阈值 | 状态 |
|------|------|------|------|
| rule_compliance | 0.0 | 10.0 | ✗ |

## 规则检查
- ✗ subagent_count_lte 3

# Task: orc-004
Run ID: 9e50da97198c4b1aafa8e0669262f703  |  Model: claude-opus-4-6

## 总分：0.0 / 10  ✗ FAILED

| 维度 | 得分 | 阈值 | 状态 |
|------|------|------|------|