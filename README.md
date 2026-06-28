# HermesEval

[![CI](https://github.com/youngkkkun-ux/agent-harness-eval/actions/workflows/ci.yml/badge.svg)](https://github.com/youngkkkun-ux/agent-harness-eval/actions/workflows/ci.yml)

针对 **Hermes Agent 五层 Harness**（Instructions / Constraints / Feedback / Memory / Orchestration）的自动化评测系统。

> 设计与需求见 [`docs/PRD.md`](docs/PRD.md) 与 [`docs/TECH_DESIGN.md`](docs/TECH_DESIGN.md)。本仓库实现 PRD 的 **Phase 1–3**，采用 TDD 开发。

## 能力概览

| 模块 | 说明 |
|------|------|
| **Task Library** | YAML 定义评测任务，Pydantic 强校验，task_id 去重（`src/hermes_eval/task_library.py`） |
| **Runner** | 通过 `HermesDriver` 协议驱动 Hermes（CLI 子进程 `SubprocessDriver`），健康检查 / 超时 / 空输出 / 先验 Session 全覆盖（`runner.py`） |
| **Evaluator** | 规则评分 + LLM-as-Judge（客户端可注入）+ 状态验证 + 加权聚合（`evaluators/`） |
| **Result Store** | SQLite + FTS5，运行记录 / 评分 / 学习曲线（`store.py`） |
| **Report** | 单次运行报告 / Harness 层汇总 / 对比 / 学习曲线 / JSON 导出（`report.py`） |
| **Pipeline + CLI** | 串联全链路并提供命令行（`pipeline.py`、`cli.py`） |

## 安装

```bash
pip install -e .          # 安装 hermes-eval 及依赖（pydantic, PyYAML）
pip install -e .[dev]     # 含 pytest
```

## 快速开始

无需安装真实 Hermes，用内置 `DemoDriver` 跑通全链路：

```bash
# 列出/校验任务库
hermes-eval list --tasks task_library

# 运行单个任务（demo 模式）
hermes-eval run --tasks task_library --task mem-001 --demo --db eval.db

# 运行全部任务并生成 Harness 层汇总
hermes-eval run --tasks task_library --demo --db eval.db
hermes-eval report --db eval.db --tasks task_library
```

接入真实 Hermes：去掉 `--demo`，用 `--binary hermes` 指定可执行文件（`SubprocessDriver` 对应 PRD 方式 A + C）。

### 完整示例（含好/坏混合场景）

`examples/demo_eval.py` 用 ScriptedDriver 模拟被测 Hermes 的真实行为差异
（部分任务做对、部分做错），跑完整评测管线并生成报告：

```bash
PYTHONPATH=src python3 examples/demo_eval.py
```

产物 [`docs/SAMPLE_REPORT.md`](docs/SAMPLE_REPORT.md) 展示系统的区分能力：
`con-003` 因 token 超预算被效率约束判负、`mem-001` 因无视跨会话偏好（用了
`requests`）被记忆层判负，其余任务通过。评分由确定性的 RuleEvaluator +
StateEvaluator 给出（可复现）；correctness 等主观维度在生产环境接入
claude-haiku-4-5 作为 LLM-as-Judge。

## 任务定义示例

```yaml
task_id: mem-001
name: 跨会话记忆保留测试
harness_layer: memory          # instructions/constraints/feedback/memory/orchestration/all
prompt: |
  请帮我写一个爬虫。
expected_outputs:
  - { type: contains, value: httpx }
  - { type: not_contains, value: requests }
acceptance_criteria: ["使用 httpx 库", "不使用 requests 库"]
eval_dimensions:
  - { name: correctness, weight: 3.0, threshold: 7.0 }
requires_prior_session: true
prior_session_prompt: "记住：我喜欢用 httpx 而不是 requests。"
```

支持的规则类型：`contains` / `not_contains` / `regex_match` / `tool_called` /
`tool_not_called` / `skill_created` / `memory_written` / `token_count_lt` /
`subagent_count_lte`。

## 架构

```
Task Library ──► Runner ──► Evaluator ──► Result Store ──► Report Generator
 (YAML)        (Driver协议)  (Rule/LLM/State)  (SQLite/FTS5)   (Markdown/JSON)
```

外部副作用（启动 Hermes、调用 Judge LLM、读取 `~/.hermes/`）全部隐藏在
`Protocol` 接口后，可用内存 Fake 注入，因此核心逻辑离线全测。

## 测试

```bash
pytest -q     # 101 个测试，覆盖每个模块及 PRD 第六节的异常路径
```

### 学习曲线与 A/B 对比（Phase 2）

```bash
# 学习曲线：同一任务连续 N 轮，观察分数趋势（并输出 PRD 3.3 学习循环专项指标：
#   improvement_rate / error_recurrence_rate / skill_creation_rate / skill_hit_rate）
hermes-eval learn --task fb-002 --rounds 5 --db eval.db

# A/B 对比：有/无某 Harness 层（skill/memory/orchestration）
hermes-eval compare --field skill_enabled --layer instructions --db eval.db

# 一致性（PRD 3.2 方差）：同一任务跑 N 次，看分数稳定性
hermes-eval consistency --task mem-001 --repeats 5 --db eval.db
```

> demo 模式下 DemoDriver 不随配置/轮次变化，曲线和对比会持平 —— 真实区分需接入
> Hermes 或参考 `tests/test_experiments.py` 中的脚本化驱动。

### 真实 `~/.hermes/` 状态

去掉 `--demo` 后，`SubprocessDriver` 会通过 `HermesStateReader` 读取 `~/.hermes/`
的 `memory.md` / `user.md` / `skills/` / `sessions.db`，供 StateEvaluator 与
`memory_written` / `skill_created` 等规则使用（PRD 方式 C 灰盒验证）。

## 接入真实 Hermes

`SubprocessDriver` 按下面这个 **CLI 契约**驱动被测 Hermes（CLI 子进程 + 灰盒状态）：

| 约定 | 内容 |
|------|------|
| 健康检查 | `hermes --version` 返回 exit 0 |
| 运行 | `hermes --session <id> --model <model> --prompt <text>`（可加 `--extra-args`） |
| 回应 | **stdout** 即模型回应正文 |
| 工具调用 | 日志行 `tool: <name> input: <...>`（stdout 或 stderr） |
| Token 用量 | 日志行含 `input_tokens=<n>` 与 `output_tokens=<n>`（如 `usage: input_tokens=42 output_tokens=17`） |
| 状态 | 进程通过环境变量 `HERMES_HOME` 指向状态目录，写入 `memory.md`/`user.md`/`skills/`/`sessions.db` |

接入方式：

```bash
export ANTHROPIC_API_KEY=sk-...   # 仅启用 LLM-as-Judge 时需要
pip install -e ".[judge]"          # 安装 anthropic SDK（可选）

hermes-eval run \
  --tasks task_library \
  --binary /path/to/hermes \
  --hermes-home ~/.hermes \
  --judge-model claude-haiku-4-5 \
  --db eval.db
```

若你的 Hermes 输出/参数与上面不同，改 `SubprocessDriver._parse_tool_calls` /
`_parse_usage` 或传 `extra_args` 即可适配——`tests/test_subprocess_integration.py`
用一个遵循该契约的桩 `hermes` 做了真实子进程端到端验证，可作为参照。

## 路线图

- **Phase 1（已实现）**：Task Library / Runner / Rule+LLM Evaluator / SQLite Store / 报告，覆盖 L1·L2·L4。
- **Phase 2（已实现）**：真实 `~/.hermes/` 状态读取（`HermesStateReader`）、Anthropic LLM-as-Judge、学习曲线追踪、A/B 对比报告、L3 反馈层任务、GitHub Actions CI。
- **Phase 3（已实现）**：L5 编排任务（含 `subagent_count_lte` 子 Agent 上限检查）、e2e 任务、定时评测工作流（`.github/workflows/scheduled-eval.yml`）、开源发布（LICENSE + 示例报告）。

任务库现覆盖全部五层 + e2e，共 20 个任务（与 PRD 5.1.3 一致）。

## License

[MIT](LICENSE)。
