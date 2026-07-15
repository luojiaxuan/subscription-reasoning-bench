# 项目进度

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
