# Experimental Version Archive

The following snapshots preserve workflow designs that were tested after 0.2.1 and deliberately
rejected. They are historical engineering records, not supported releases. The stable `main`
branch continues from 0.2.1 to 0.2.2 without these experiments.

| Experimental version | Archive branch | Snapshot commit | Status |
|---|---|---|---|
| 0.3.0 | [`archive/failed-v0.3.0`](https://github.com/Sheldon12311815/origin-com-automation/tree/archive/failed-v0.3.0) | `ed3cf71` | Rejected |
| 0.3.1 | [`archive/failed-v0.3.1`](https://github.com/Sheldon12311815/origin-com-automation/tree/archive/failed-v0.3.1) | `aa8789f` | Rejected |
| 0.4.0 | [`archive/failed-v0.4.0`](https://github.com/Sheldon12311815/origin-com-automation/tree/archive/failed-v0.4.0) | `a9cb614` | Rejected |

## Why they were rejected

- **0.3.0** introduced a broader plan/validate/execute workflow, scientific parameter contracts,
  ledgers, manifests, checkpoints, and additional verification stages. The design improved formal
  traceability but made ordinary Origin tasks noticeably longer and less direct.
- **0.3.1** attempted to balance speed and recovery by reducing default checkpoints. It still
  retained too much workflow orchestration for the desired one-pass user experience.
- **0.4.0** consolidated the expanded architecture and tightened native-analysis enforcement.
  User testing still found the execution path cumbersome, and native formula/analysis selection
  did not consistently match the expected practical workflow.

## Archive rules

- Do not merge these branches into `main`.
- Do not install them as the current plugin unless explicitly reproducing historical behavior.
- Do not report their simulated or historical validation as evidence for 0.2.2.
- Useful internal ideas may be reimplemented on the lean stable path only after separate review.

---

# 实验版本归档

以下快照用于保留 0.2.1 之后曾经测试、随后明确放弃的工作流设计。它们只是工程历史记录，
不是受支持的正式版本。稳定 `main` 分支从 0.2.1 直接发展到 0.2.2，不包含这些实验历史。

- **0.3.0：**引入了更完整的规划、验证、执行流程，以及参数契约、账本、清单、恢复点和额外
  核验阶段。可追溯性更强，但普通 Origin 任务明显变慢、变得不够干练。
- **0.3.1：**尝试减少默认恢复点，在速度和恢复能力之间平衡，但整体调度层仍然过重。
- **0.4.0：**合并了扩展架构并加强原生分析约束，但实测执行路径仍然繁复，原生公式和分析
  选择也未能稳定符合预期工作方式。

这些分支不得合并回主分支，也不应作为当前插件安装。若其中某些内部设计以后仍有价值，
应当经过单独审查后，在 0.2.2 的精简路径上重新实现。
