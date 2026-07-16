# Fast vs Standard long-loop pilot task

这是一个本地 synthetic pilot fixture，用来检查同一个 Codex model/effort 在
`standard` 与 `fast` 下能否完成固定 6 个外层 research rounds，每轮最多 300 秒。
它不是正式公开
dataset，也不进入长期 leaderboard。

训练 CSV 是确定性生成的本地 staging artifact，不进 Git：

```bash
python3 examples/research-longloop-pilot/generate_data.py \
  --output examples/research-longloop-pilot/starter/train.csv \
  --rows 512 \
  --seed 20260715

.venv/bin/srb research validate examples/research-longloop-pilot
.venv/bin/srb research matrix configs/fast-vs-standard-longloop.toml --dry-run
```

正式采用这个任务前，需要把版本化数据放到 Hugging Face、把 hidden grader/test
放到隔离容器，并记录 dataset revision 与 image digest。当前生成数据仅留在
`examples/research-longloop-pilot/starter/train.csv`，状态为 local staging。
