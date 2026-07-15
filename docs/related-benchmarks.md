# 长时程 text-only AI research benchmark 调研

本项目的主目标不是再做一套静态问答题，而是测量模型能否在数小时、多个研究轮次中持续完成「提出假设 → 修改代码 → 运行实验 → 接收客观反馈 → 再迭代」。这里的 text-only 指输入输出不含图片、视频或音频；允许使用受控的代码仓库、终端与实验环境，因为它们正是可执行 AI research 的载体。

## 主调研：长时程、可执行、多轮

| Benchmark | 核心方法 | 对本项目最有价值的设计 | 边界 |
| --- | --- | --- | --- |
| [ResearchGym](https://arxiv.org/abs/2602.15112)（[代码](https://github.com/Anikethh/ResearchGym)） | 从 5 篇顶会 oral/spotlight 论文构造 5 个容器化环境、39 个 sub-task；保留数据、评测器和 baseline，隐藏论文方法，让 agent 在 12–24 小时固定预算内提出假设、实验并超越 baseline | 采用裁剪后的真实研究仓库、隐藏方法、客观 grader、baseline-normalized improvement、固定时间/额度、断点续跑；同时报告完成率与失败模式，不能只看最好分数 | 更接近自主闭环研究，外层未必有固定的人类反馈轮次；任务数仍小且运行昂贵 |
| [RECODE-H](https://arxiv.org/abs/2510.06186)（[代码](https://github.com/ChunyuMiao98/RECODE-H)） | 102 个真实论文与仓库中的 research-code task；单元测试驱动，使用 5 级结构化模拟研究者反馈，最多 10 轮迭代，并按 MRR、Recall 和测试通过率评估 | 把外层 `research_round` 固定为跨产品可比单位；每轮保存 grader feedback、通过率与首次成功轮次，衡量模型能否利用反馈，而不只衡量一次生成 | 主要测论文方法实现与修复，不覆盖完整的假设搜索和实验设计 |
| [FML-bench](https://arxiv.org/abs/2605.17373)（[代码](https://github.com/qrzou/FML-bench)） | 18 个基础 ML 研究任务、10 个领域；统一代码编辑、实验执行和 validation/test split，把 agent strategy 与执行基础设施分离；固定 100-step 预算并定义 12 个过程指标 | 所有模型共享执行与评分环境；记录 first improvement、best-so-far、停滞、探索距离/集中度、失败实验与成本，让“为什么提前结束”可被分析 | 为控制变量移除了部分 agent 原生工具，可能低估完整产品形态；step 不等同于产品内部 native turn |
| [RE-Bench](https://arxiv.org/abs/2411.15114)（[代码](https://github.com/METR/RE-Bench)） | 7 个开放式 ML research-engineering 环境，并收集 61 位专家的 71 次 8 小时轨迹；用 2、8、32 小时等预算比较人类与 agent 的 returns-to-time | 使用真实时间预算、人类轨迹和公开 agent trajectory；除最终分数外画 score-vs-time/round 曲线，检验 Fast 或低 effort 是否只是更早停止 | 偏 research engineering，任务规模小；跨订阅产品时还需同时记录 quota 与不可控服务延迟 |
| [AIRS-Bench](https://arxiv.org/abs/2602.06855)（[代码](https://github.com/facebookresearch/airs-bench)） | 20 个来自 SOTA ML 论文的任务，覆盖从 idea generation、experiment analysis 到 iterative refinement 的完整研究周期；不提供 baseline code，并比较 sequential 与 parallel scaffold | 任务 manifest 应支持从空实现开始、理论上界、held-out test，以及 strict sequential / orchestrated parallel 两种 protocol；两种 protocol 必须分榜 | 计算开销大、领域跨度高；无 baseline code 会同时放大环境搭建能力与研究推理能力 |
| [IDRBench](https://arxiv.org/abs/2601.06676) | 将 deep research 建模为可主动请求澄清的交互过程；使用 reference-grounded user simulator，并联合衡量 alignment gain、交互轮数与 token 开销 | 借鉴可复现的外层反馈器与 interaction-efficiency 指标：同等质量下用了几轮、何时主动求证、无效往返多少 | 核心任务是带网页探索的 deep-research 报告，不是可执行 ML 实验；只借鉴交互评测，不作为本项目主任务源 |

## 对本项目的组合结论

没有一个现成 benchmark 单独覆盖“订阅产品模式 × 固定外层研究轮次 × 原生 agent session × 客观实验评分”。建议组合上述设计：

1. 任务形态以 ResearchGym / AIRS-Bench 为主：真实裁剪仓库、可执行实验、隐藏目标方法、validation/test 隔离。
2. 多轮协议以 RECODE-H 为主：grader 在每个固定 `research_round` 后给结构化、可复现反馈；产品内部 `native_turns` 只作诊断，不能当作跨产品轮次。
3. 过程分析以 FML-bench 为主：记录完整 score trajectory、首次提升、停滞、回退、无效实验和预算利用率。
4. 时间尺度以 RE-Bench 为主：同时做 round-budget 与 wall-clock-budget 曲线，避免单个最终分数掩盖提前结束。
5. 交互效率参考 IDRBench；strict sequential 与 orchestrated parallel 参考 AIRS-Bench，二者分别报告。

因此主 leaderboard 应报告 held-out final improvement、target attainment、AUC-over-rounds、first-improvement round、stagnation length、有效研究轮数、wall time 与订阅消耗代理量。最好成绩、平均成绩和可靠性都要保留，不能用 best-of-k 代替单次成功率。

## 短题 benchmark：仅作 wiring / calibration

下列题集仍适合验证账号接入、prompt 格式、答案解析、随机化和基础能力是否异常，但不应作为本项目的核心研究结论或主 leaderboard：

| Benchmark | 保留用途 | 为什么不能测目标能力 |
| --- | --- | --- |
| [Reasoning Gym](https://github.com/open-thought/reasoning-gym) | 程序生成 smoke test、fresh seed 与难度校准 | 单题、短反馈链，没有真实研究状态与实验迭代 |
| [BIG-Bench Extra Hard](https://github.com/google-deepmind/bbeh) | 广义 hard reasoning calibration | 静态公开题，无法观察持续规划、失败恢复与预算管理 |
| [LiveBench](https://github.com/LiveBench/LiveBench) | contamination-sensitive sanity check | 仍以最终答案为主，不是长时程可执行研究 |
| [GPQA](https://github.com/idavidrein/gpqa) / [MMLU-Pro](https://arxiv.org/abs/2406.01574) | 专业知识与广领域基础校准 | 知识和 reasoning 混合，选择题分数不能代表 agent research |
| [BIG-bench / BBH](https://github.com/google/BIG-bench) | legacy 回归与历史对照 | 新模型部分饱和、污染风险高，也没有多轮轨迹 |

ARC-AGI、AIME 等可作为窄能力诊断；SWE-bench / Terminal-Bench 更偏软件工程；GAIA / BrowseComp 依赖网页检索。它们都不应替代上面的 executable AI research task。

## 官方产品接入依据

- OpenAI Codex 官方资料说明 [ChatGPT subscription authentication](https://learn.chatgpt.com/docs/auth.md)、[Standard/Fast speed mode](https://learn.chatgpt.com/docs/agent-configuration/speed.md) 与 [model / reasoning selection](https://learn.chatgpt.com/docs/models.md)。Fast 是服务层加速并增加 credit consumption，不应先验假定它改变模型能力。
- [Claude Code CLI reference](https://code.claude.com/docs/en/cli-usage) 提供 `--print`、stream JSON、`--model`、`--effort` 与 `--max-turns` 等自动化入口。
- [Claude Code model configuration](https://code.claude.com/docs/en/model-config) 列出 Opus 4.8、Sonnet 5、Fable 5 的 effort 支持，并明确 `ultracode` 是 `xhigh` 加 dynamic workflow，不是 model effort。
- [Claude Code setup](https://code.claude.com/docs/en/getting-started) 说明 Pro/Max/Team/Enterprise subscription 可用于 Claude Code。
