# 长时程 AI Research Benchmark

## 目标

核心评测不再把模型当作一次性答题器，而是把它放入一个有代码、数据、实验反馈和固定预算的研究环境。模型需要在同一个持久 session 中反复执行：

1. 理解研究目标并形成假设；
2. 修改 workspace、运行分析或实验；
3. 接收客观 validation score 与预先定义的 PI feedback；
4. 根据失败和新证据修改方向；
5. 在预算结束前提交可由 hidden test 复验的 artifact。

输入、反馈和输出仍然可以全部是 text；核心 benchmark 不需要 video 或视觉理解。但真实 AI research 必须允许 repo、terminal 和实验环境，否则测到的只是“描述研究”的能力。

## 与现有工作的关系

本框架不主张“长时程 AI research benchmark”本身是新概念。设计直接吸收以下工作的方法，并保留引用：

- [ResearchGym](https://arxiv.org/abs/2602.15112)：12–24 小时 closed-loop research、近期论文任务、客观执行评分，以及 Codex/Claude Code scaffold。
- [RECODE-H](https://arxiv.org/abs/2510.06186)：最多 10 轮的模拟研究者反馈与 unit-test verifier。
- [FML-bench](https://arxiv.org/abs/2605.17373)：固定执行基础设施、逐步搜索轨迹和 process-level metrics。
- [RE-Bench](https://arxiv.org/abs/2411.15114)：连续 objective、人类专家 time curve，以及 agent 早期领先但随后 plateau 的分析。
- [AIRS-Bench](https://arxiv.org/abs/2602.06855)：24 小时 full research lifecycle 与 sequential/parallel scaffold 对照。
- [IDRBench](https://arxiv.org/abs/2601.06676)：澄清问题、user simulator 和 interaction benefit/cost。

本项目当前的工程目标更窄：在用户已经订阅并登录的 Codex 与 Claude Code CLI 上，统一比较 model、speed、effort 和 orchestration configuration。是否构成新的学术贡献，需要在正式机制和实验完成后重新判断。

## 两种 turn

必须分开记录：

- `research_round`：benchmark harness 注入 objective 或 PI feedback 的轮次；跨 provider 可比较。
- `native_turns`：Codex/Claude trace 暴露的 provider 原生轮次；只适合 provider 内比较。

此外记录 tool calls、subagent calls、每轮 wall-clock、validation score 和最后一次 hidden-test score。不能把任意一种 turn 当作隐藏 thinking token 的代理。

## Research task manifest

每个 task 是一个目录，至少包含：

```text
task.toml
objective.md
starter/
grader.py 或其他客观 grader
```

`task.toml` 描述：task id/title、starter workspace、objective、grader argv、最大 research rounds、每轮 timeout、hidden-test baseline、可选的 validation baseline、target 和 score direction。validation trajectory 与最终 hidden-test improvement 分别使用对应 split 的 baseline，避免把 split 随机波动误记成研究进步。`grader_command` 是 argv list，不经过 shell；路径和 split/round 通过显式 placeholder 传入。

Grader 对 stdout 输出一个 JSON object：

```json
{
  "score": 0.84,
  "valid": true,
  "metrics": {"accuracy": 0.84},
  "feedback": "下一轮可见的、预先确定的 PI feedback"
}
```

Validation feedback 可以在每个 research round 后返回；最终 test split 不向 agent 暴露。正式任务应在容器中隔离 hidden grader、test data 和 agent workspace，并审计越权读取、grader 修改和 hard-coding。

## 主要指标

最终 quality 与 trajectory 同时报告：

- `final_score` 与相对 baseline 的 normalized improvement；
- score curve 的 AUC-over-rounds；
- first-improvement round 与 best-improvement round；
- late-gain fraction：后半程获得的 improvement 占比；
- valid-round ratio；
- target reached 与 early termination；
- 累计 native turns、tool calls、subagent calls 和 wall-clock；
- 相同 task/attempt 下配置之间的 paired delta。

这些指标用于区分“最终没做对”的不同原因：过早结束、重复失败方向、执行环境错误、只在早期获得简单收益、或者能够在后半程继续推进。

## 分阶段实验

### Stage 0：wiring smoke

- CPU-only synthetic research task；
- 2–3 个 research rounds；
- 每个 provider 选一个配置；
- 只验证 auth、session resume、workspace edit、grader、checkpoint 和 UI。

### Stage 1：30 分钟 pilot

- 1–2 个真实 task；
- 所有配置各 1 次；
- 检查 quota、timeout、fallback、grader headroom 和环境故障。

### Stage 2：2 小时 main pilot

- 3–5 个任务；
- 相同 task/attempt 内随机化配置顺序；
- 至少 3 repeats；
- 冻结 task revision、container image、GPU、CLI version 和 feedback policy。

### Stage 3：8–24 小时 confirmation

只对 Stage 2 中有分歧或明显 plateau 差异的配置运行。不能直接把短 pilot 与长 confirmation 平均成一个 leaderboard 分数。

## 公平性与订阅额度

- 每次运行复制相同 starter workspace，使用相同 grader、feedback schedule、round/time budget 和可用工具。
- Standard/Fast、effort 与 Ultra 是被测变量；不要额外改变 prompt 或 task budget。
- 默认顺序运行，避免并发限流成为混淆变量。
- quota exhaustion、provider fallback、CLI crash 和提前退出都进入 end-to-end 结果，不能从分母删除。
- Codex Ultra 允许 subagent；strict single-agent 与 orchestrated research 必须分轨报告。
- Claude Code 没有 `ultra` model effort，不能把 `ultracode` 静默映射为 Ultra。

## 当前 smoke task

[`examples/research-toy`](../examples/research-toy) 是一个确定性 CPU fixture：模型需要从训练样本发现一个含 feature interaction 的分类规则，逐轮接收 validation score 和 PI feedback，最后在独立随机 split 上评分。

它只用于验证 harness，不是可发表的数据集，也不进入正式能力结论。正式 ResearchGym/AIRS/RE-Bench 派生任务及运行结果应作为可复用数据 artifact 上传 Hugging Face，并把 revision 记录回 README。
