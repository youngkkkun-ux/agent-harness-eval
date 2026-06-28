# PRD：Hermes Harness 评测系统

**项目代号**：HermesEval
**版本**：v0.1
**作者**：Kristen
**状态**：评审通过
**参考来源**：NousResearch/hermes-agent v0.14.0、hermes-agent-self-evolution、Anthropic Demystifying Evals、AgentHarness v2

---

## 一、背景与目标

### 1.1 背景

Hermes Agent 是目前最具代表性的“harness 内置化”开源 Agent，其五层 Harness（Instructions / Constraints / Feedback / Memory / Orchestration）全部产品化。但它缺乏系统性的评测框架：

- 无法量化各 Harness 层的实际效果
- 无法对比不同配置（模型、Skill 质量、内存策略）之间的差异
- 无法追踪 Hermes 的“自我改进”是否真的在改进
- 开源社区缺少一个可复现的 Harness 质量基准

### 1.2 目标

构建一套**针对 Hermes Harness 的自动化评测系统**，能够：

1. 评测 Hermes 五层 Harness 各层的质量和效果
2. 支持多轮对比实验（模型 A vs 模型 B、有 Skill vs 无 Skill 等）
3. 追踪 Hermes 学习循环（Learning Loop）的收益曲线
4. 输出可发布的评测报告

### 1.3 不做的事

- 不评测 Hermes 的 UI/TUI（只评测 harness 行为）
- 不覆盖所有 40+ 工具（聚焦核心 harness 相关工具）
- 不做安全红队测试（范围外）

---

## 二、核心概念定义

| 术语 | 定义 |
|------|------|
| **Harness 层** | Hermes 五层：Instructions / Constraints / Feedback / Memory / Orchestration |
| **任务（Task）** | 一个给 Hermes 执行的具体指令，有预期输出 |
| **评测轮次（Run）** | 对同一 Task 执行一次完整的 Hermes 会话 |
| **对照组（Baseline）** | 关闭某 Harness 层后的运行结果 |
| **学习曲线** | 同一 Task 经过 N 轮学习循环后，分数随时间的变化趋势 |
| **Skill 质量** | Skill 文件被正确召回并提升任务得分的概率 |

---

## 三、评测维度与指标体系

### 3.1 五层 Harness 对应评测维度

```
Layer 1: Instructions（Skill 系统）
  → 指标：Skill 召回率、Skill 应用准确率、Skill 内容质量分

Layer 2: Constraints（工具权限 + 沙箱）
  → 指标：越权操作拦截率、权限边界遵守率、沙箱逃逸检测

Layer 3: Feedback（学习循环）
  → 指标：学习曲线斜率、N 轮后性能提升率、错误不重复率

Layer 4: Memory（三层记忆）
  → 指标：Episodic 召回精度、Semantic 状态一致性、跨 Session 记忆保留率

Layer 5: Orchestration（子 Agent 编排）
  → 指标：子任务分解正确率、结果合并质量、并发任务成功率
```

### 3.2 通用任务质量指标（每个 Task 都有）

| 指标 | 说明 | 评分方式 |
|------|------|---------|
| **correctness** | 输出是否完成了任务要求 | LLM-as-Judge + 规则检查 |
| **completeness** | 是否覆盖了所有要求点 | Checklist 匹配 |
| **efficiency** | Token 用量 / 工具调用次数 | 数值统计 |
| **consistency** | 多次运行结果是否稳定 | 方差计算 |
| **harness_utilization** | 实际用到了哪几层 Harness | 日志解析 |

### 3.3 学习循环专项指标

```
run_1_score → run_2_score → ... → run_N_score
  ↓
improvement_rate = (run_N - run_1) / run_1 × 100%
error_recurrence_rate = 同一类错误在后续 run 中再次出现的概率
skill_creation_rate = 触发 Skill 创建的 task 比例
skill_hit_rate = 创建的 Skill 在后续 run 中被正确召回的比例
```

---

## 四、系统架构

```
┌─────────────────────────────────────────────────────────┐
│                    HermesEval 系统                       │
│  ┌─────────────┐   ┌──────────────┐   ┌─────────────┐  │
│  │ Task Library │   │  Runner      │   │  Evaluator  │  │
│  │ 任务库       │──►│  执行层      │──►│  评分层     │  │
│  └─────────────┘   └──────────────┘   └──────┬──────┘  │
│  ┌────────────────────────────────────────────▼──────┐  │
│  │                  Result Store                      │  │
│  │  SQLite：run记录 / 分数 / 日志 / 学习曲线           │  │
│  └───────────────────────────┬────────────────────┘    │
│  ┌───────────────────────────▼────────────────────┐    │
│  │                  Report Generator               │    │
│  │  Markdown 报告 / JSON 导出 / 对比表格            │    │
│  └────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────┘
```

---

## 五、模块详细需求

### 5.1 Module 1：Task Library（任务库）

定义、存储、分类评测任务。Task 数据结构见 `src/hermes_eval/models.py:Task`；
分类目录见 `task_library/layerN_*/`。MVP 初始任务集共 20 个（见原始 PRD 表格）。

### 5.2 Module 2：Runner（执行层）

驱动 Hermes 执行 Task 并采集运行数据。MVP 采用方式 A（CLI 子进程）+ 方式 C
（灰盒读取 `~/.hermes/` 状态）。Run 数据结构见 `models.py:RunRecord` / `RunConfig`。

### 5.3 Module 3：Evaluator（评分层）

对 RunRecord 多维度打分：RuleEvaluator（规则）、LLMEvaluator（LLM-as-Judge）、
StateEvaluator（内部状态验证），经 ScoreAggregator 加权聚合为 EvalResult。
LLM Judge Prompt 模板见附录 A。

### 5.4 Module 4：Result Store（结果存储）

SQLite + FTS5，表：`eval_configs` / `runs` / `eval_results` / `learning_curves`
/ `runs_fts`。实现见 `store.py`。

### 5.5 Module 5：Report Generator（报告生成）

单次运行报告、Harness 层汇总报告、对比报告（A vs B）、学习曲线、JSON 导出。
实现见 `report.py`。

---

## 六、异常与边界情况

完整异常矩阵保留在原始需求中，关键项已在实现中覆盖并有对应测试：

- **Runner**：Hermes 不可用→`HERMES_NOT_AVAILABLE` 跳过；超时→`TIMEOUT`；
  空输出→`EMPTY_RESPONSE` 全 0 不计均分；先验 Session 失败→`PRIOR_SESSION_FAILED`。
- **Evaluator**：LLM Judge 非 JSON→重试 1 次再降级（`llm_eval_failed`）；
  分数越界→clamp[0,10]；全 10/全 0→`suspicious_score`；状态不可读→维度跳过（None）。
- **数据层**：DB 损坏→`integrity_check` 后备份重建；Task YAML 非法→拒绝入库不影响其他；
  task_id 重复→拒绝导入。
- **边界**：任务集为空→报错退出；全部 Run 失败→报告“无有效数据”不崩溃；
  acceptance_criteria 至少 1 条（定义期校验）。

---

## 七、MVP 范围与分阶段交付

- **Phase 1（MVP）**：Task Library / Runner（CLI）/ Rule+LLM Evaluator /
  SQLite Store / 单次+汇总报告，覆盖 L1·L2·L4。**← 本仓库当前实现**
- **Phase 2**：StateEvaluator 接真实 `~/.hermes/`、学习曲线追踪、对比报告、L3。
- **Phase 3**：L5 编排、e2e 任务、CI/CD 集成、开源发布。

---

## 八、技术选型

| 组件 | 选型 | 理由 |
|------|------|------|
| 语言 | Python 3.11+ | 与 Hermes 一致，生态完整 |
| Task 定义 | YAML + Pydantic 校验 | 可读性好，schema 可强制约束 |
| Runner | subprocess（驱动协议抽象） | 非侵入式 |
| Evaluator LLM | claude-haiku-4-5（客户端可注入） | 成本低 |
| Result Store | SQLite + FTS5 | 零运维 |
| 报告格式 | Markdown + JSON | 可直接 push 到 GitHub |
| 测试框架 | pytest | TDD |

---

## 九、开放问题（待决策）

1. Hermes 驱动方式：CLI 子进程 vs API Server？→ 已用 `HermesDriver` 协议收敛为可替换实现。
2. 先验 Session 自动化与隔离策略。
3. 学习曲线 Task 与环境隔离原则的冲突。
4. LLM Judge 成本控制与缓存。
5. Hermes 版本绑定与版本间对比。

---

## 附录 A：LLM Judge Prompt 模板

实现见 `src/hermes_eval/evaluators/llm.py:PROMPT_TEMPLATE`，输出严格 JSON：
`{ dimensions: [{name, score, critique, passed}], overall_summary, actionable_feedback }`。
