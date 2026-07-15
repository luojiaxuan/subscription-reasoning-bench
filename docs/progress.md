# 项目进度

## 2026-07-15：v0.2.0 长时程 AI research runner

### 当前目标

把主 benchmark 从一次性问答改为多轮、可执行、可恢复的 AI research 环境，测量 model × effort × speed × orchestration 对持续实验和后期进步的影响。旧短题 runner 只保留为 wiring / calibration。

### 已完成

- 完成长时程 prior-art 调研：ResearchGym、RECODE-H、FML-bench、RE-Bench、AIRS-Bench、IDRBench，并明确本项目不主张“长时程 research benchmark”概念本身的新颖性。
- 实现 research task manifest、starter workspace、objective、无 shell 的 grader argv、validation feedback 与 hidden test。
- 实现固定外层 `research_round`、Codex / Claude 持久 session、多轮 workspace、原子 checkpoint/resume、最终 JSONL 与可选 raw trace。
- 实现 final normalized improvement、AUC-over-rounds、first/best improvement、late gain、valid round、target reach、early stop、native turns、tools、subagents 等 trajectory metrics。
- 为 validation 与 hidden test 分开记录 baseline，避免 split 波动被误判为进步；未达到 `min_rounds` 的 timeout/session failure 不再算 completed。
- 实现 `srb research validate/run/matrix/report`，提供 2 配置 smoke 和 17 配置完整矩阵 dry run。
- 实现 Research Trajectories Dashboard：多配置逐轮曲线、宽表、空状态、短题/研究记录分流和移动端横向滚动。
- 增加 deterministic CPU synthetic research fixture；starter validation/test baseline 分别为 `0.78/0.74`。
- 真实最小 session smoke 已分别验证 Codex `exec resume` 和 Claude `--resume`：第二轮能读取第一轮 workspace 修改，session ID 一致。
- 本轮全量自动测试为 `41 passed`；Ruff、JavaScript syntax、wheel 安装、CLI doctor、manifest/grader validation 与 matrix dry run 均通过。
- 本地 Dashboard 已检查 desktop / 390px viewport、空状态和真实失败曲线，console 无 warning/error。

### 真实端到端 smoke 的失败记录

`configs/research-smoke.toml` 在本机已有多个 Codex / Claude 产品会话并发时各跑一个配置。两端第一轮均在 300 秒超时，且 CLI 未发出 init/session event；runner 正确保存 timeout、baseline artifact score 和 `session_id_missing`，没有进入第二轮。该 run 只说明当前并发/可用性条件下的端到端失败，不说明模型能力，也不推翻此前独立的两轮 session-resume smoke。

这次失败暴露并修复了两个统计问题：

- grader 仍能评分 baseline artifact 时，旧状态曾误标为 completed；现在未达到 `min_rounds` 会标为 failed。
- validation baseline `0.78` 与 hidden baseline `0.74` 不同；现在 trajectory 与 final improvement 分别使用对应 baseline。

原始失败结果只保留在本机 `runs/` staging，不上传 Hugging Face、不进入 leaderboard。

### 重要边界

- 当前 local synthetic runner 是可信 wiring 环境，不是 malicious-agent security sandbox。
- 正式 hidden grader/test 必须放在 agent 无法读取或修改的容器边界外，冻结 image digest 并审计越权。
- Claude 没有 Ultra effort；strict 与 orchestrated protocol 分开聚合，不能混榜。
- Provider `native_turns` 仍只做 provider 内诊断；跨 provider 以外层 research rounds、quality、completion 和 wall time 为主。

### 尚未完成

- 尚未导入或冻结真实 ResearchGym / AIRS / RE-Bench 派生任务。
- 尚未实现正式任务所需的 container isolation、资源预算和 image digest 记录。
- 尚未在低并发、稳定 entitlement 条件下完成两端 2+ research-round end-to-end run。
- 尚未创建 Hugging Face executable-task pack / trajectory repos；当前没有值得发布的正式 artifact。
- 尚未预注册 pilot 的任务、反馈策略、预算、重复次数和 paired statistical analysis。

### 下一步

1. 增加容器 backend，把 agent workspace、validation service 和 hidden test 隔离。
2. 选 1–2 个真实、客观可执行任务做 30 分钟 pilot，校准 headroom、timeout 和 quota。
3. 在没有其他产品会话竞争时各跑一个 Codex / Claude 两轮 smoke，确认完整 JSONL 与 resume path。
4. 冻结 3–5 个任务、container revisions 和 17 配置矩阵，再做 repeats ≥ 3 的 paired pilot。
5. 创建 Hugging Face task / trajectory repos，上传正式 artifact 并把 revision 回填到 README。

## 2026-07-15：v0.1.0 初始框架

### 当前目标

建立一个不依赖 API key、通过 ChatGPT / claude.ai 订阅登录运行的 text-only reasoning benchmark，并准确比较 model、effort、Standard/Fast 与执行轮数。

### 已完成

- 确认本机 Codex CLI 使用 ChatGPT 登录、Claude Code 使用 claude.ai Pro 登录。
- 确认 GPT‑5.6 的 Standard/Fast 与 `high/xhigh/max/ultra` 产品语义。
- 确认 Claude Opus 4.8、Sonnet 5、Fable 5 与 `high/xhigh/max`；拒绝把 `ultracode` 假装成 `ultra` effort。
- 实现 Codex/Claude subscription CLI adapters、trace parser、自动评分、断点续跑、paired randomized matrix、bootstrap CI 与本地 dashboard。
- 实现锁定 revision/hash 的 BBEH mini downloader 与可选 Reasoning Gym generator。
- 真实 smoke 已验证 GPT‑5.6 Sol `high/standard`、`high/fast`、`ultra/standard` 与 Claude Sonnet 5 `high`；均正确完成且未调用外部工具。
- 确认 macOS 必须优先使用 Codex app bundled CLI 才能获得当前 GPT‑5.6 catalog；裸 `gpt-5.6` ID 被订阅服务拒绝，精确 ID 为 `gpt-5.6-sol`。

### 重要决策

- Core score 不使用 LLM-as-judge。
- Strict single-agent 与 orchestrated text-only 分开报告。
- Provider 原生 turn 数只用于 provider 内比较。
- Raw suite/results 不进 Git；可复用公开 artifact 最终进入 Hugging Face，Git 保留代码、方法、轻量 summary 与 artifact revision 链接。

### 尚未完成

- 尚未消耗大量订阅额度跑正式 benchmark；当前只是单题 wiring smoke，不能用于模型优劣或 Fast 加速结论。
- 尚未创建正式 Reasoning Gym frozen suite 或 Hugging Face dataset repo。
- 尚未冻结 main experiment 的 category/config/seed 预注册清单。
- 尚未加入 LiveBench / GPQA / MMLU‑Pro 的直接 importer。

### 下一步

1. 在每个 provider 上各跑 1–2 题，验证真实 trace schema、model entitlement 与 fallback 记录。
2. 运行 20–50 题 pilot，检查正确率 floor/ceiling、timeout 和 parser miss。
3. 冻结 main suite 并上传 Hugging Face dataset repo，回填 revision。
4. 预注册主比较与样本量后运行完整 paired matrix。
5. 将轻量 evaluation summary 提交到 Git，并把完整 raw results 上传 Hugging Face。
