# Benchmark 设计

## 1. 研究问题

本项目要分别回答四个问题：

1. 同一个 GPT‑5.6 Sol 在 Standard 与 Fast 下，最终正确率是否等价，wall-clock 能缩短多少？
2. `high → xhigh → max` 增加 reasoning effort 后，收益是否稳定，是否出现 overthinking 或更高失败率？
3. `ultra` 的 subagent 编排对可分解和不可分解任务是否有不同效果？
4. GPT‑5.6 与 Claude Opus 4.8 / Sonnet 5 / Fable 5 在相同 text-only、closed-book 约束下的质量—时延 Pareto frontier 如何？

这些问题不能压缩成一个 leaderboard 分数。Standard/Fast 是服务层；effort 是模型推理配置；Ultra 还改变编排拓扑。框架保留每个维度，不做未经验证的加权总分。

## 2. 两条实验协议

### Strict single-agent

- 输入只有文本。
- 禁止 search、browser、shell、file、code execution、MCP 与 subagent。
- 主比较：所有 provider 的 `high/xhigh/max`；GPT‑5.6 额外比较 Standard/Fast。
- 发现调用即记录 `protocol_violation=true`，结果不删除，以避免 survivorship bias。

### Orchestrated text-only

- 仍禁止任何外部信息、文件与代码执行。
- 允许内部 subagents 只基于题面并行推理。
- 主比较：GPT‑5.6 `max` 与 `ultra`，并按 task decomposability 分层。
- 不把它与 strict 结果混成一个分数。

## 3. Suite 结构

### Primary A：Reasoning Gym

程序生成、seed 可复现、难度可调、答案可验证，适合降低公开静态题的 contamination 风险。建议覆盖：

- logic：propositional logic、zebra / logic puzzle、syllogism；
- algorithmic：graph、sorting、sequence；
- arithmetic / algebra：多步计算、方程；
- cognition：spatial、calendar、deduction。

正式 suite 应冻结 generator package version、任务列表、每任务 config、seed 与生成后 JSONL hash。

### Primary B：BBEH mini

460 题、23 类 general reasoning，目标是替代已经趋于饱和的 BBH。它覆盖比纯 math/code 更广的推理能力，且使用客观答案。当前 downloader 锁定上游 commit 与文件 SHA-256。

### Secondary

- LiveBench reasoning：近期题、持续更新、客观评分；适合 freshness/contamination audit。
- GPQA Diamond：研究生级科学知识与推理；适合 expert reasoning，但静态且对专业知识敏感。
- MMLU‑Pro：10 选项、比 MMLU 更强调推理，对 prompt variation 更稳定；仍混合知识与推理。

Secondary 结果必须分开报告，不能把知识问答与程序生成逻辑题平均成一个不可解释的总分。

## 4. 运行设计

### 分阶段控制额度

1. Wiring smoke：2 题 × 3 配置 × 1 repeat，确认 auth、parser、scorer、resume。
2. Pilot：每个主 category 10–20 题 × 1 repeat，用于排查 ceiling/floor、timeout 与 fallback。
3. Main：冻结 100–200 题，所有配置至少 3 repeats。
4. Confirmation：在配置间 disagreement、失败或高方差题上追加到 5 repeats；这部分单独标记，不混淆预注册主分析。

完整示例矩阵是 17 个配置。直接运行 BBEH mini × 3 repeats 是 23,460 次订阅请求，不应作为第一步。

### 随机化与配对

- 实验单位为 `(task_id, attempt)`。
- 每个 repeat 随机 task 顺序；每题内部再随机 configuration 顺序。
- comparison 只在共有的 `(task_id, attempt)` 上做 paired delta。
- 固定随机 seed，并记录 suite SHA-256。

### Rate limit 与时间漂移

- 默认顺序运行，避免并发把 provider rate limit 当成模型能力。
- 大矩阵应拆成平衡 block，让每个配置均匀分布在不同时段。
- 记录运行日期、CLI 版本、登录方案和 completion rate。
- 服务端模型更新后，旧结果保留并使用新的 experiment id，不覆盖。

## 5. 指标定义

### 主要质量指标

- End-to-end accuracy：所有计划运行进入分母；timeout、CLI error、无答案均为 0。
- Valid accuracy：只在成功解析与评分的运行上计算，用于诊断但不作为唯一结论。
- Completion rate：成功评分数 / 计划运行数。
- Paired accuracy delta：同题同 attempt 的 score difference，报告 bootstrap 95% CI。

### 执行形态指标

- Wall-clock latency：本地启动 CLI 到进程退出的时间；报告 P50/P95。
- Native turns：provider 原生字段或 trace 中的 turn start 数。
- Reasoning/message events：可观察事件数，不等于隐藏 thinking token。
- External tool calls / subagent calls：由 trace 分类。
- Token fields：只记录 provider trace 实际提供的字段。

`native_turns` 不是跨 provider 统一标准。Claude `num_turns` 与 Codex trace 的 `turn.started` 语义可能不同；它们只适合 provider 内消融。跨 provider 结论优先使用 accuracy、completion 与 wall-clock。

### 稳定性

- 每题 pass variance 与 configuration disagreement rate。
- 同配置多次运行的 score/latency coefficient of variation。
- fallback rate：requested model 与 observed model 不一致或出现多个 observed models。
- early-exit rate：成功返回但答案为空、格式错误或显著短于任务约束。

## 6. Prompt 与评分

所有 runner 使用同一用户 prompt envelope：只给题面、协议约束与 `<final_answer>` 终止格式。不要求展示 chain-of-thought。评分器先提取 final tag，再按 suite scorer 自动判断。

不使用 LLM-as-judge。开放式写作、主观规划、不可客观验证任务不进入 core score；未来如添加，应成为独立 human rubric track。

## 7. 已知威胁

- Subscription surface 不是固定 API snapshot；alias 和服务端版本会变化。
- Fast 可能只改变服务优先级，但订阅限流与网络噪声会制造表面质量差异。
- Static benchmark contamination 无法完全排除；Reasoning Gym 只能降低，不能证明不存在。
- Ultra 与普通 effort 的计算拓扑不同，不能解释为单纯“更多思考”。
- Claude Fable 5 在某些安全/生物内容上可能自动 fallback；必须记录 observed models。
- Provider 可能不暴露完整隐藏 reasoning/token 指标；框架只报告可观察证据。
