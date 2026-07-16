# 项目进度

## 2026-07-15：Fast vs Standard long-loop pilot

### 直接结论

- **Fast 能做 long loop。** 一条 Fast autonomous run 持续 `637.584s`，产生
  `18` 次唯一命令执行、`11` 条中间消息和 `27,648` output tokens，完成数据检查、
  多类模型比较、交叉验证、残差特征选择、网格搜索、ablation、slice check 与
  1,000 次系数扰动检查；validation/hidden accuracy 为 `0.9600/0.9742`。
- **没有观察到 long-loop 加速。** 唯一双方均成功的 autonomous pair 中，Standard
  用时 `430.344s`，Fast 用时 `637.584s`；`Standard/Fast=0.675`，即 Fast 反而
  多用 `207.240s`、慢 `48.2%`。
- **本次没有观察到 Fast 质量损失。** 成功 pair 中 Fast hidden accuracy 比
  Standard 高 `1.92` 个百分点，并多做 `7` 次唯一命令执行。但只有一个 both-completed
  pair，不能据此证明 quality non-inferiority，更不能证明 Fast 普遍更好。
- **可靠性噪声大于可识别的 speed 主效应。** 900 秒矩阵中两种模式都是 `1/2`
  成功；第二个 pair 两边都没有 session/trace/artifact edit，并在上限 timeout。
  这些零 turns/tools 是 censored/unobserved，不能解释成模型没有内部工作。

因此，这次 pilot 反驳了“Fast 必然无法 long loop”这一强说法，但不支持“Fast
一定能让 agentic research 更快且质量不变”。更准确的工程判断是：Fast 有时能
降低短请求延迟，但自主长任务的端到端时间还由模型选择的实验深度、服务状态和
timeout 主导。

### 冻结设计

- 六轮机制 pilot：Git `3f6372ff0ebf313ea55e497233206f5beffae5ec`，task
  digest `78898ab353a47784f369637fa82a16d7633b05e7dd078c75abd35852130f078e`，
  config SHA-256 `6f33a57b25c4d80f07f4868e158cfa2a427733080240a75c40bbfc2f8fe753e5`。
- Autonomous pilot：Git `429d0d02e27d56023f95783d1b50e90c34368eb2`，task
  digest `458c01bcb79fe0da1fdf8180fb5e4f8e387f2aa64f1e74106dfdc3a434c3ccb2`，
  config SHA-256 `764848b56268bd852878a19a54d939bbfc0d7b9d59269fae7147fbd1d472c2f0`。
- 训练数据：seed `20260715`，512 rows，56,860 bytes，SHA-256
  `8057a956fad9ad128753b613235354bc4b78db483855be818bde21497d9693d4`。
- Validation/test：seed `20260716/20260717`，`700/1200` examples；starter
  accuracy `0.6371428571/0.6816666667`，target `0.94`。
- 被测配置：Codex requested model `gpt-5.6-sol`、`high`、`strict`、
  Standard/Fast。六轮任务为固定 6 rounds、300 秒/round、2 repeats；autonomous
  任务为单个 uninterrupted turn、900 秒、2 repeats、seed `4`。
- Autonomous 实际顺序为 Fast→Standard、Standard→Fast；命令为
  `.venv/bin/srb research matrix configs/fast-vs-standard-autonomous.toml --keep-traces`。
- 环境：SRB `0.2.0`、Python `3.14.6`、macOS `15.3.2` arm64、ChatGPT
  subscription auth。Autonomous raw runs 均报告 `codex-cli 0.144.2`，但没有返回
  observed model，因此只能确认 requested model，不能独立确认实际 served model。

### 实际结果

先做 60 秒短题 canary：初始顺序 Standard→Fast，双方都满分，耗时
`5.438s/10.151s`。长实验结束后的反序 Fast→Standard canary 也都满分，耗时
`3.920s/11.062s`，此时 Fast 约 `2.82×`。两次短题的方向相反，且 CLI 从
`0.144.0-alpha.4` 变为 `0.144.2`，只能说明短请求延迟方差很大；后置 canary
也确认第二组 long-task timeout 后账号通道仍能处理简单请求。

120 秒校准中，Fast/Standard attempt 1 均在第一轮 timeout。随后冻结的 300 秒
六轮矩阵得到 4/4 第一轮 timeout，全部没有 session 或 trace，hidden score 只是
未修改 starter 的 `0.6817`。这批结果是预算校准，不能用于比较质量或速度，也不应
把 baseline 均值误报成两种模式质量相同。两次实际顺序均为 Fast→Standard，没有
counterbalance，也是这批结果不能外推的限制。

900 秒 autonomous 矩阵给出可识别的内部 loop：

| Attempt / 实际顺序 | Fast | Standard | Pair 解释 |
| --- | --- | --- | --- |
| 1 / Fast→Standard | `target_reached`；`637.584s`；val `0.9600`；hidden `0.9742`；18 unique commands；11 messages；27,648 output tokens | `target_reached`；`430.344s`；val `0.9571`；hidden `0.9550`；11 unique commands；8 messages；13,613 output tokens | Fast 高 `1.92pp`，但慢 `48.2%`，执行轨迹更深 |
| 2 / Standard→Fast | `failed`；`900.008s` timeout；无 session/trace；baseline `0.6817` | `failed`；`900.019s` timeout；无 session/trace；baseline `0.6817` | 两边均右删失，不可比较质量或真实速度 |

运行时间为 2026-07-16 UTC `00:36:19` 至 `01:24:08`。成功提交经独立 grader
重跑复现 `0.9741666667/0.9550`；人工审计 trace 与 `solution.py` 未发现读取 grader、
hidden target、外部路径或网络。候选预测已改为隔离 Python 子进程执行，并增加
reflection regression test；这关闭了直接 `import __main__.target` 的漏洞，但 local
pilot 仍不是恶意 agent 的容器安全边界。

冻结的 v0.2 raw JSONL 把 `item.started` 与 `item.completed` 都计入
`external_tool_calls`，所以原字段为 Fast/Standard `36/22`。按 item ID 重解析后是
`18/11` 个唯一 command executions；adapter 已改为去重并增加回归测试，raw artifact
不做事后改写。

### 结论边界与下一轮设计

- 只有一个 synthetic formula-recovery task、一个 effort、两个 paired attempts，且
  只有一个 both-completed pair；不能做统计显著性或 non-inferiority 结论。
- Autonomous 单 turn 测的是自发内部 loop；固定 6 个 harness rounds 测的是 session
  续接能力。两者不能混成同一个“轮数”。本轮只有前者成功得到可识别结果。
- Attempt 2 在两条长成功运行之后才执行，可能混入订阅额度、服务负载或时段效应；
  AB/BA 只平衡了 pair 内 speed 顺序，没有平衡跨时段状态。
- AUC、均值质量和 capped latency 若把 timeout 的 baseline/900 秒直接混入，会产生
  误导。主报告必须先给 completion，再只在 both-completed pairs 比质量与速度。
- 下一轮至少使用 5 个真实 executable tasks、每任务 ≥10 个跨时段 paired repeats，
  用 ABBA/Latin-square 排序；预注册 `1pp` quality non-inferiority margin，并同时报告
  completion、both-completed quality、restricted wall time 与 quality-time Pareto。
- 为区分服务推理加速与 agent 自主选择的轨迹深度，应增加两条实验：固定 work/replay
  测 service latency；开放工具的 autonomous task 测端到端 research effectiveness。
  Runner 还需要 first-event latency/流式 trace telemetry 和每个 block 前后的 canary。

Raw JSONL、trace 和 workspaces 当前只在本机 `runs/` staging，未上传 Hugging Face，
不进入正式 leaderboard。拟定 canonical destination 为
`luojiaxuan/subscription-research-bench-trajectories`；本轮仅把冻结配置、轻量 summary
和失败模式提交到 Git。

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
- 尚未预注册正式多任务 pilot 的任务、反馈策略、预算、重复次数和 paired statistical analysis。

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
