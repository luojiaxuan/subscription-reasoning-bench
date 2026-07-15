# Subscription Reasoning Bench

一个通过官方本地 CLI 与账号订阅额度运行的 text-only reasoning benchmark。它目前面向：

- ChatGPT 登录的 Codex CLI：GPT‑5.6 family 的 Power/旗舰变体 `gpt-5.6-sol`，`standard` / `fast`，`high` / `xhigh` / `max` / `ultra`。
- claude.ai 登录的 Claude Code：`claude-opus-4-8`、`claude-sonnet-5`、`claude-fable-5`，`high` / `xhigh` / `max`。

框架同时记录最终正确率与执行轨迹指标，包括原生 turns、reasoning/message events、tool calls、subagents、tokens、wall-clock latency、失败和提前结束。它不需要 OpenAI 或 Anthropic API key，也不会读取或复制登录凭据。

> 当前是 `v0.1.0` alpha。先跑小规模 pilot；完整示例矩阵包含 17 个配置，直接跑满 BBEH mini × 3 repeats 会消耗大量订阅额度。

## 快速开始

要求 Python 3.11+，并至少安装一个已登录订阅账号的 CLI：

```bash
python3 -m venv .venv
.venv/bin/pip install -e '.[dev]'

srb doctor
srb capabilities
srb suite bbeh-mini
srb matrix configs/smoke.toml --limit 2 --dry-run
srb matrix configs/smoke.toml --limit 2
srb report runs/smoke.jsonl
srb ui --results-dir runs
```

浏览器打开 `http://127.0.0.1:8765` 查看本地 dashboard。

### 单配置运行

```bash
srb run \
  --suite data/bbeh-mini.jsonl \
  --output runs/gpt56-high-standard.jsonl \
  --provider codex \
  --model gpt-5.6-sol \
  --effort high \
  --speed standard \
  --protocol strict \
  --limit 10
```

中断后重复同一个命令会按 `task + attempt + configuration` 自动续跑。加 `--keep-traces` 才会保存原始 provider JSONL trace。

### Reasoning Gym 程序生成套件

```bash
.venv/bin/pip install -e '.[reasoning-gym]'
srb suite reasoning-gym \
  --dataset basic_arithmetic \
  --dataset propositional_logic \
  --size 50 \
  --seed 20260715 \
  --output data/reasoning-gym.jsonl
```

生成器 seed、上游数据集名和评分 entry 都写入 JSONL，便于复现。`data/` 与 `runs/` 默认不进 Git。

## 为什么这样设计

- 只使用可程序验证或客观 ground truth 的 scorer，不把另一个 LLM 当裁判。
- 用相同 `task + attempt` 做 paired comparison，并随机化每道题内部的配置顺序。
- 把失败、限流和提前退出计为 end-to-end 零分，同时单独报告 valid accuracy 与 completion rate。
- 不把不同 provider 的 `native_turns` 当成同一个物理量；跨 provider 主要比较正确率、完成率与 wall-clock，同 provider 才比较 turns 的变化。
- `ultra` 不是简单的“更多 thinking tokens”：Codex 文档把它描述为可主动使用 subagents 的编排模式。因此 strict single-agent 与 orchestrated text-only 分轨报告。

完整实验方法、推荐样本量与统计口径见 [docs/benchmark-design.md](docs/benchmark-design.md)，已有 benchmark 调研见 [docs/related-benchmarks.md](docs/related-benchmarks.md)。

## 能力边界

| Runner | 模型 | Effort | Speed | 说明 |
| --- | --- | --- | --- | --- |
| Codex CLI | `gpt-5.6-sol` | `high`, `xhigh`, `max`, `ultra` | `standard`, `fast` | GPT‑5.6 Power/旗舰变体；使用 ChatGPT 登录订阅额度 |
| Claude Code | Opus 4.8 / Sonnet 5 / Fable 5 | `high`, `xhigh`, `max` | `standard` | 使用 claude.ai 登录订阅额度 |

Claude Code 的 `ultracode` 是“`xhigh` + dynamic workflows”，不是 `ultra` model effort；本框架不会把它静默伪装成 `ultra`。当前官方说明见 [Claude model configuration](https://code.claude.com/docs/en/model-config)。

账号方案或组织策略可能限制模型与 effort。`srb doctor` 只验证 CLI 和登录状态，不通过消耗额度来探测 entitlement；实际 entitlement 在第一次真实运行时确定，结果会记录 requested model 与 trace 中可观察到的 models，以发现 fallback。

之所以使用精确 ID `gpt-5.6-sol`，是因为当前 Codex model catalog 将 GPT‑5.6 分为 Sol/Terra/Luna，而默认 Power 档使用 Sol；裸 ID `gpt-5.6` 在真实订阅 smoke 中被服务端拒绝。runner 在 macOS 上优先使用 Codex app 自带的 CLI，以保持与桌面端 model catalog 一致。

## Suite JSONL

每行一个任务：

```json
{
  "id": "logic-001",
  "prompt": "...",
  "reference": "A",
  "scorer": "exact",
  "category": "logic",
  "source": "my-suite",
  "metadata": {"revision": "v1"}
}
```

内置 scorer：`exact`、`numeric`、`regex`、`contains`、`bbeh`、`reasoning_gym`。

## Source of Truth

### Code and progress

- GitHub: <https://github.com/luojiaxuan/subscription-reasoning-bench>
- 当前可复用状态：`main`
- 方法与决策：[docs/benchmark-design.md](docs/benchmark-design.md)
- 进度与下一步：[docs/progress.md](docs/progress.md)

### Data and evaluation artifacts

| Artifact | Canonical location | Revision/status | Notes |
| --- | --- | --- | --- |
| BBEH mini 上游数据 | [google-deepmind/bbeh](https://github.com/google-deepmind/bbeh) | `80d12ca916b7158f22293fcf3144f4d3d854d4be` | 下载器校验 SHA-256；Apache-2.0 |
| Reasoning Gym generator | [open-thought/reasoning-gym](https://github.com/open-thought/reasoning-gym) | 运行时记录 package version/seed | Apache-2.0；本仓库不复制数据 |
| 新生成的公开 suite | Hugging Face dataset repo | pending, 尚未生成 | 建议名称：`luojiaxuan/subscription-reasoning-bench-text-reasoning` |
| 可公开的完整 raw results | Hugging Face dataset repo | pending, 尚未运行 | Git 仅保留轻量 summary 与方法 |

本机 `data/`、`runs/` 都是 staging/cache，不是 canonical artifact。生成可复用 suite 或完成正式评测后，应上传到上表记录的 Hugging Face dataset repo，并把 revision 写回 README/docs。

## 安全与公平性

- 只调用官方 `codex exec` 与 `claude --print`；不做网页 DOM 抓取或 cookie 复制。
- runner 继承 CLI 已有登录状态，不输出 token 或 credential 文件。
- 默认禁用外部搜索、浏览器与文件写入。strict 协议发现任何 tool/subagent call 都标记为 protocol violation。
- 订阅限额、fallback、服务端更新和网络时段都会造成漂移；发布结果必须记录日期、CLI 版本、suite hash、重复次数和 completion rate。

## License

框架代码使用 [MIT License](LICENSE)。各 benchmark 数据仍受各自上游许可证约束。
