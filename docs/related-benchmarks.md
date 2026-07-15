# Text-only reasoning benchmark 调研

## 推荐组合

| Benchmark | 适合本项目的原因 | 主要限制 | 建议角色 |
| --- | --- | --- | --- |
| [Reasoning Gym](https://github.com/open-thought/reasoning-gym) | 100+ 程序生成环境、难度可调、verifiable rewards、可无限生成新 seed | 某些任务偏合成；需要冻结版本/config | Primary，抗污染与 scaling curve |
| [BIG-Bench Extra Hard](https://github.com/google-deepmind/bbeh) | 23 类广义 reasoning、比 BBH 难、mini 460 题、Apache-2.0 | 静态公开题；部分题很长 | Primary，广覆盖 hard suite |
| [LiveBench](https://github.com/LiveBench/LiveBench) | 定期更新、客观 ground truth、专门降低 contamination | 公开 release 有滞后；整套还含 coding/data 等非目标类别 | Secondary，只取 reasoning/language 中客观子集 |
| [GPQA](https://github.com/idavidrein/gpqa) | Graduate-level、Google-proof science QA、客观选择题 | 强依赖专业知识；静态公开 | Secondary，expert reasoning |
| [MMLU-Pro](https://arxiv.org/abs/2406.01574) | 10 选项、更难、比 MMLU 更强调 CoT reasoning，prompt sensitivity 较低 | 知识与 reasoning 混合；静态 | Secondary，广领域稳健性 |
| [BIG-bench / BBH](https://github.com/google/BIG-bench) | 任务类型丰富、历史可比性强 | 新模型上部分饱和且 contamination 风险高 | 仅作 legacy calibration |

Reasoning Gym 论文把程序生成与可验证奖励作为核心；BBEH 论文则指出 BBH 已在多个任务趋于饱和，并用更难的新任务覆盖相近能力。因此本项目把两者结合：前者负责 fresh/generated，后者负责统一且多样的 hard snapshot。

## 暂不作为 core

- Humanity's Last Exam：难度高，但包含多模态题，而且部分学科答案质量曾引发讨论；可只做独立 text-only audit。
- ARC-AGI：很适合抽象推理，但其二维 grid 不是本项目要测的自然语言 text reasoning 主体。
- AIME / competition math：区分度高，但单一 math domain 不能代表 broad reasoning，题目版权与公开污染也需要单独处理。
- SWE-bench / Terminal-Bench：测 agentic coding 与环境交互，不是纯 text-only reasoning。
- GAIA / BrowseComp：依赖工具和网页检索，违反 closed-book core protocol。

## 官方产品接入依据

- OpenAI Codex 官方资料说明 [ChatGPT subscription authentication](https://learn.chatgpt.com/docs/auth.md)、[Standard/Fast speed mode](https://learn.chatgpt.com/docs/agent-configuration/speed.md) 与 [model / reasoning selection](https://learn.chatgpt.com/docs/models.md)。Fast 是服务层加速并增加 credit consumption，不应先验假定它改变模型能力。
- [Claude Code CLI reference](https://code.claude.com/docs/en/cli-usage) 提供 `--print`、stream JSON、`--model`、`--effort` 与 `--max-turns` 等自动化入口。
- [Claude Code model configuration](https://code.claude.com/docs/en/model-config) 列出 Opus 4.8、Sonnet 5、Fable 5 的 effort 支持，并明确 `ultracode` 是 `xhigh` 加 dynamic workflow，不是 model effort。
- [Claude Code setup](https://code.claude.com/docs/en/getting-started) 说明 Pro/Max/Team/Enterprise subscription 可用于 Claude Code。
