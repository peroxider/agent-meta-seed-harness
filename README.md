# agent-meta-seed-harness

独立的 Seed Harness。Runtime 仅提供机制，Seed 持有 Loop、Context 和应用策略。
开发基于 `docs/plans/v0.1/seed-harness/` 中归档的计划。

当前为开发版本，未发布产品能力。实际完成情况见
[追踪表](docs/traceability.md) 和 [Runtime 依赖](docs/runtime-dependencies.md)。
公开接口缺失时保持门禁未满足，不使用 Runtime 私有存储或测试 fixture。

CPython 3.12，独立虚拟环境。先从显式 Runtime CI wheel 制备 wheelhouse，
随后在离线环境安装：

```console
python -m pip install --no-index --find-links wheelhouse --require-hashes -r requirements-ci.lock
python -m build --no-isolation
python -m pip install --no-index --no-deps dist/agent_meta_seed_harness-0.1.0.dev1-py3-none-any.whl
python scripts/check_boundary.py
python -m pytest -q tests/unit tests/contract tests/acceptance
python scripts/check_seed_traceability.py --profile minimal
```

最后一个命令是发布门禁，未实现需求、缺证据、跳过 required 测试都应失败。
构建不访问相邻 Runtime checkout，不联网，不自动获取或运行 Harness。

本地制备入口（只在允许联网的制备阶段执行）接受显式 wheel 路径与 hash：

```console
python scripts/prepare_ci.py --runtime-wheel <path-to-wheel> --runtime-sha256 <sha256> --update-lock
python scripts/archive_contract.py --source <explicit-runtime-source> --runtime-commit <full-commit> --runtime-wheel-sha256 <sha256>
```

`--update-lock`会重新解析当前平台的二进制依赖；review 后提交 lock。
不加此选项时只按现有 hash lock 制备。当前 lock 是 Windows/CPython 3.12；
其他平台需要各自实际制备、安装和 Host 报告。

`scripts/build_development.py`生成 wheel、sdist、CycloneDX SBOM 和标为
`DEVELOPMENT_NOT_RELEASED` 的 provenance。`scripts/build_release.py`运行完整
profile 证据门禁后，只为已测试的同一批制品生成待审阅 candidate manifest，
不会重建、发布或激活。当前最小版未完成，发布门禁应拒绝。证据格式和流程见
[发布证据](docs/release-evidence.md)。
预构建最终签名包的消费者入口是 `scripts/run_consumer.py`；完整操作流程见
[最小版运行手册](docs/runbook-minimal.md)。

开发 Host 已通过独立安装 wheel、签名 AMPAK 与真实 daemon 执行 Seed Loop、Context、
fake Provider 和 PURE echo；覆盖多段终态、工具顺序、自由文本不派发及进程 kill 后未知结果恢复。
支持范围和剩余矩阵见 [Host 集成](docs/host-integration.md)，RP-00～RP-07 仍为 OPEN。

开发工具包通过 `agent-meta-seed build-package <root> --profile tools` 选择，
沿用显式 publisher key、契约 hash 和 output 参数。它包含 Artifact 读写、
State 冻结读取/CAS 写入、JSON 规范化，以及 Scratch 创建/执行/观测/Source 导出/释放，
使用公开 Host；详情见[工具集成记录](docs/resource-tools-development.md)。
Scratch 依赖独立 worker 的可选运行栈，完整 S05 故障与发布门禁仍未完成。
