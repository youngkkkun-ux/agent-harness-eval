# HermesEval 技术方案（TDD）

> 配套文档：`PRD.md`（产品需求）。本文档描述 **Phase 1 (MVP)** 的技术实现方案，采用测试驱动开发（TDD）。

## 1. 范围

实现 PRD 第七节的 **Phase 1 MVP**：

- Task Library：YAML 任务定义 + Pydantic 校验
- Runner：CLI 子进程驱动 Hermes（驱动层抽象，可注入 Fake 以便测试）
- Evaluator：RuleEvaluator + LLMEvaluator（Judge 客户端可注入）+ StateEvaluator + ScoreAggregator
- Result Store：SQLite + FTS5
- Report Generator：单次运行报告 + Harness 层汇总报告（Markdown / JSON）
- 数据模型覆盖 Phase 2/3 字段（学习曲线、对比），保证可扩展

显式不做（留待 Phase 2/3）：真实 LLM Judge 联网调用（用接口隔离）、L5 编排任务执行、CI 定时运行。

## 2. 设计原则

1. **依赖倒置 / 可测性**：所有外部副作用（启动 Hermes 进程、调用 Judge LLM、读取 `~/.hermes/`）都隐藏在 `Protocol` 接口后，测试用内存 Fake 注入。核心评分/聚合/存储逻辑 100% 纯函数化、可离线测试。
2. **数据模型先行**：Pydantic 模型是系统契约，先为模型写测试。
3. **TDD 红-绿-重构**：每个模块先写失败测试，再写实现至通过。
4. **零运维存储**：SQLite 单文件，WAL 模式，FTS5 全文索引。

## 3. 架构与模块映射

```
src/hermes_eval/
├── models.py              # Pydantic 契约：Task / RunConfig / RunRecord / EvalResult ...
├── task_library.py        # 加载+校验 YAML 任务，task_id 去重
├── runner.py              # HermesDriver(Protocol) + SubprocessDriver + Runner
├── evaluators/
│   ├── base.py            # Evaluator 协议 + DimensionScore
│   ├── rule.py            # RuleEvaluator（contains/regex/tool_called/...）
│   ├── llm.py             # LLMEvaluator + JudgeClient(Protocol)
│   ├── state.py           # StateEvaluator（读取 hermes 状态快照）
│   └── aggregator.py      # ScoreAggregator → EvalResult
├── store.py               # SQLite ResultStore（runs/eval_results/learning_curves/FTS5）
├── report.py              # ReportGenerator（run / harness-summary / 对比）
└── cli.py                 # 命令行入口（list/run/report）
```

每个 `src` 模块对应一个 `tests/test_*.py`。

## 4. 关键设计决策

### 4.1 Hermes 驱动抽象（对应 PRD 开放问题 1）

```python
class HermesDriver(Protocol):
    def health_check(self) -> bool: ...
    def run(self, prompt: str, config: RunConfig, session_id: str) -> DriverResult: ...
    def snapshot_state(self, session_id: str) -> dict: ...  # 读取 ~/.hermes/ 灰盒状态
```

- 生产实现 `SubprocessDriver`（PRD 方式 A + C）。
- 测试实现 `FakeDriver`（返回预设输出/状态），使 Runner 全链路可离线测试。
- 这样 PRD「CLI vs API」的开放问题被收敛为一个可替换实现，不阻塞系统其余部分。

### 4.2 评分管线

`RunRecord` →（RuleEvaluator ∥ LLMEvaluator ∥ StateEvaluator）→ `list[DimensionScore]` → `ScoreAggregator` → `EvalResult`。

- 加权平均：`overall = Σ(score_i × weight_i) / Σ(weight_i)`，跳过 `score is None` 的维度（StateEvaluator 不可用时降级，对应 PRD 6.2）。
- `passed = 所有参与维度 score >= threshold`。
- LLM Judge 通过 `JudgeClient` 协议注入；非 JSON 输出重试一次再降级（PRD 6.2）；分数 clamp 到 [0,10]。

### 4.3 异常处理

按 PRD 第六节实现关键路径：Hermes 不可用→跳过并记 `error`；超时→`TIMEOUT`；空输出→全 0 不计均分；DB 写失败→JSON 备份；Task YAML 非法→拒绝入库不影响其他。每条都有对应测试。

### 4.4 学习曲线

`learning_curves` 表按 `(task_id, config_id, run_number)` 记录分数序列，断点记 null。`improvement_rate = (run_N - run_1)/run_1`，由 ReportGenerator 计算。

## 5. 测试策略

| 层 | 测试方式 |
|----|---------|
| models | 合法/非法输入校验、序列化 |
| task_library | 加载目录、重复 id 拒绝、非法 YAML 拒绝、空集报错 |
| runner | FakeDriver 注入：正常 / 超时 / 空输出 / 不可用 |
| rule evaluator | 每种规则的真/假分支 |
| llm evaluator | FakeJudge：正常 JSON / 坏 JSON 重试 / 越界 clamp |
| aggregator | 加权平均、None 跳过、阈值判定 |
| store | 写读往返、FTS5 搜索、学习曲线、WAL |
| report | 快照式断言关键字段 |

运行：`pytest -q`。目标：核心逻辑全绿，无需网络/无需真实 Hermes。

## 6. 分阶段交付（与 PRD 第七节一致）

- **本次（Phase 1）**：上述全部 + 覆盖 L1/L2/L4 的样例任务。
- Phase 2：StateEvaluator 接真实 `~/.hermes/`、学习曲线追踪、对比报告、L3。
- Phase 3：L5 编排、e2e、CI。
