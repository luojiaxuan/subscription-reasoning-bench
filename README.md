# Subscription Research Bench

一个通过官方本地 CLI 和账号订阅额度运行的 long-horizon、text-only AI research benchmark。它测的不是模型能否一次答对一道题，而是模型能否在同一个持久 session 中反复：

1. 理解研究目标并提出假设；
2. 检查 repo / 数据并运行本地实验；
3. 修改提交 artifact；
4. 接收客观 validation score 与固定 PI feedback；
5. 在多个 `research_round` 后通过 hidden test。

`text-only` 表示不测图片、视频或音频理解；repo、terminal、代码和实验结果仍然是研究环境的一部分。框架不需要 OpenAI / Anthropic API key，不读取或复制登录凭据，当前支持：

- ChatGPT 登录的 Codex CLI：`gpt-5.6-sol`，`standard` / `fast`，`high` / `xhigh` / `max` / `ultra`。
- claude.ai 登录的 Claude Code：`claude-opus-4-8`、`claude-sonnet-5`、`claude-fable-5`，`high` / `xhigh` / `max`。

> 当前是 `v0.2.0` alpha。Git 中的 synthetic task 只验证 wiring，不是可发表 benchmark。正式跑 17 个配置前，先冻结真实任务、容器、预算和 artifact revision；完整运行会消耗大量订阅额度。

## 快速开始

要求 Python 3.11+，并至少安装一个已登录订阅账号的 CLI：

```bash
python3 -m venv .venv
.venv/bin/pip install '.[dev]'

.venv/bin/srb doctor
.venv/bin/srb capabilities
.venv/bin/srb research validate examples/research-toy
.venv/bin/srb research matrix configs/research-smoke.toml --dry-run
```

确认 dry run 的任务、配置和最大研究轮数后，再消耗订阅额度：

```bash
.venv/bin/srb research matrix configs/research-smoke.toml --keep-traces
.venv/bin/srb research report runs/research-smoke.jsonl
.venv/bin/srb ui --results-dir runs
```

浏览器打开 `http://127.0.0.1:8765`。Dashboard 会分别显示长时程 Research Trajectories 和旧的短题 calibration，二者不会混在一个总分里。

### 单配置研究运行

```bash
.venv/bin/srb research run examples/research-toy \
  --output runs/codex-research.jsonl \
  --workspace-root runs/research-workspaces \
  --provider codex \
  --model gpt-5.6-sol \
  --effort high \
  --speed standard \
  --protocol strict \
  --keep-traces
```

中断后重复同一个命令，会从上一个原子 checkpoint、workspace 和 provider session 继续；最终 JSONL 已存在时会跳过该 run。正式矩阵模板见 [`configs/research-matrix.toml`](configs/research-matrix.toml)：8 个 Codex 配置加 9 个 Claude 配置，共 17 个。

## Research task

每个任务是一个独立目录：

```text
task.toml
objective.md
starter/
grader.py
```

[`examples/research-toy`](examples/research-toy) 要求 agent 从训练样本发现含 feature interaction 的分类规则。它固定运行 2–3 个外层研究轮次；每轮评分 fresh validation split，最后评分独立 hidden split。

`task.toml` 的核心字段：

```toml
schema_version = 1
id = "my-research-task"
title = "..."
objective_file = "objective.md"
starter_dir = "starter"
grader_command = ["python3", "grader.py", "--workspace", "{workspace}", "--split", "{split}", "--round", "{round}"]
max_rounds = 10
min_rounds = 2
round_timeout_seconds = 1800
baseline_score = 0.42
validation_baseline_score = 0.44
target_score = 0.65
higher_is_better = true
```

`grader_command` 是 argv list，不经过 shell。grader 必须输出一个 JSON object：

```json
{
  "score": 0.51,
  "valid": true,
  "metrics": {"accuracy": 0.51},
  "feedback": "预先定义、下一轮可见的 PI feedback"
}
```

Validation feedback 会进入下一轮 prompt；test feedback 永不发送给 agent。validation 与 hidden test 分别使用自己的 baseline，避免 split 波动被误记成研究进步。

## 测量什么

框架明确区分两类轮数：

- `research_round`：harness 注入 objective / PI feedback 的外层轮次，跨 provider 可比较。
- `native_turns`：Codex / Claude trace 暴露的内部轮次，只适合 provider 内诊断。

最终记录包含：

- hidden-test `final_score` 和 baseline-normalized improvement；
- score curve 的 AUC-over-rounds；
- first-improvement / best-improvement round；
- late-gain fraction、valid-round ratio、target reach 和 early termination；
- 每轮 validation score、feedback、latency、native turns、tools 和 subagents；
- requested / observed model、CLI version、timeout、fallback 与错误；
- 相同 task / attempt 下配置间的 paired comparison 所需字段。

失败、超时、缺少可恢复 session、限流和提前停止不会从分母删除。未达到 `min_rounds` 的 run 标为 failed；即使 workspace 中的 baseline 仍能被 grader 评分，也不会伪装成 completed。

## 协议与公平性

- 相同 task / attempt 复制同一个 starter，使用相同 grader、反馈策略、round budget 和 timeout。
- 配置顺序在 task 内随机化，默认串行运行，减少并发限流混淆。
- Standard/Fast、effort 和 Ultra 是被测变量，不能同时偷偷更换 prompt 或预算。
- `strict` 允许本地研究工具但禁止 subagent；`orchestrated` 允许内部 subagent。两种协议分别聚合。
- Claude Code 没有 `ultra` model effort；`ultracode` 是 orchestration workflow，框架不会把它静默映射成 Ultra。
- Raw trace 只有显式 `--keep-traces` 才保存；账号凭据不会写入结果。

### 当前隔离边界

本地 synthetic task 用于可信 wiring smoke。Codex 使用 `workspace-write`，Claude 只开放 Bash/Read/Edit/Write/Glob/Grep（`orchestrated` 另开放 Agent），两端禁用 web / browser / MCP。

这还不是针对恶意或主动越权 agent 的 hidden-test 安全边界。正式 ResearchGym / AIRS / RE-Bench 派生任务必须把 agent workspace 与 hidden grader / test data 放入隔离容器，冻结 image digest，并审计越权读取、grader 修改和 hard-coding。当前 local runner 的结果不能代替这一步。

## 与现有 benchmark 的关系

本项目不主张“长时程 AI research benchmark”本身是新概念。设计主要吸收：

- [ResearchGym](https://arxiv.org/abs/2602.15112)：12–24 小时可执行研究环境与客观评分；
- [RECODE-H](https://arxiv.org/abs/2510.06186)：最多 10 轮结构化研究者反馈；
- [FML-bench](https://arxiv.org/abs/2605.17373)：统一执行基础设施与 process metrics；
- [RE-Bench](https://arxiv.org/abs/2411.15114)：score-vs-time 与人类专家轨迹；
- [AIRS-Bench](https://arxiv.org/abs/2602.06855)：完整研究 lifecycle 和 sequential / parallel scaffold；
- [IDRBench](https://arxiv.org/abs/2601.06676)：交互收益与成本。

本项目更窄的工程问题是：在用户已订阅并登录的产品 CLI 上，如何统一测量 model × effort × speed × orchestration 对长时程研究轨迹的影响。完整 prior-art 对照和边界见 [`docs/related-benchmarks.md`](docs/related-benchmarks.md)，实验协议见 [`docs/long-horizon-research.md`](docs/long-horizon-research.md)。

## 短题 calibration（legacy）

旧的 BBEH / Reasoning Gym 单题 runner 仍保留，用来验证 auth、trace parser、答案抽取和基础 reasoning 是否异常，但不再是主 leaderboard：

```bash
.venv/bin/srb suite bbeh-mini
.venv/bin/srb matrix configs/smoke.toml --limit 2 --dry-run
.venv/bin/srb matrix configs/smoke.toml --limit 2
.venv/bin/srb report runs/smoke.jsonl
```

短题 JSONL schema 和 scorer 见 [`docs/benchmark-design.md`](docs/benchmark-design.md)。

## Source of Truth

### Code and project state

- GitHub: <https://github.com/luojiaxuan/subscription-reasoning-bench>
- 当前可复用状态：`main`
- 长时程设计：[`docs/long-horizon-research.md`](docs/long-horizon-research.md)
- prior art：[`docs/related-benchmarks.md`](docs/related-benchmarks.md)
- 进度与失败记录：[`docs/progress.md`](docs/progress.md)

### Data and evaluation artifacts

| Artifact | Canonical location | Revision/status | Notes |
| --- | --- | --- | --- |
| Synthetic wiring task | 本 Git repo 的 [`examples/research-toy`](examples/research-toy) | `main` | 小型 source fixture，不是正式数据集 |
| 正式 executable research task pack | Hugging Face dataset repo | pending，尚未构建 | 建议：`luojiaxuan/subscription-research-bench-executable-tasks` |
| 正式 raw trajectories / results | Hugging Face dataset repo | pending，尚未运行 | 建议：`luojiaxuan/subscription-research-bench-trajectories` |
| 旧 BBEH mini 上游数据 | [google-deepmind/bbeh](https://github.com/google-deepmind/bbeh) | `80d12ca916b7158f22293fcf3144f4d3d854d4be` | 仅 calibration；Apache-2.0 |

本机 `data/`、`runs/` 和 research workspaces 都是 staging/cache，不是 canonical artifact。正式任务、可复用数据和完整 trajectories 应上传 Hugging Face，并把 revision / image digest 回填到 Git README/docs；代码、配置、轻量 summary 和项目决策留在 Git。

## License

框架代码使用 [MIT License](LICENSE)。上游 benchmark、论文仓库和数据仍受各自许可证约束。
