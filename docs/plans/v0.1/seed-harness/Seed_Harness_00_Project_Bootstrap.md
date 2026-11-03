# Seed Harness Step S00 — Project Bootstrap

> 归属：外部项目  
> 状态：PLANNED  
> Runtime规范定位：§1.3、§40、§41.60.1

## 目标

在独立路径建立Seed项目，并从第一天保持依赖方向只有Seed → Runtime public SDK/Contract。

## 固定命名

- repository/distribution：`agent-meta-seed-harness`
- Python import：`agent_meta_seed_harness`
- 推荐本地checkout：Runtime同级`../agent-meta-seed-harness`，仅作为开发提示。
- Runtime依赖：显式pin的`agent-meta-runtime`公开版本或CI wheel。

## 输入与范围

输入为Runtime公开wheel/Contract文档包、目标Python/OS和Backend profile；统一规则见[开发交接](Seed_Harness_Development_Guide.md)。
本步只建立独立工程、依赖锁和验证入口；不以相邻Runtime源码替代尚未发布的接口。

## 实施顺序

1. 建立独立Git仓库、`pyproject.toml`、source/tests/docs目录和版本策略。
2. 只允许import `agent_meta_runtime.sdk`、公开DTO与生成的公共协议包。
3. 增加lint，禁止import Runtime adapters/application/repository/UoW/private module。
4. CI通过显式artifact/version输入取得Runtime，不读取相对checkout路径。
5. 建立独立changelog、SBOM、provenance和release workflow。
6. 从[追踪计划](Seed_Harness_Traceability.md)建立Seed的`docs/traceability.md`；从[S01A](Seed_Harness_01A_Public_Host_Contract.md)建立Runtime依赖台账。
7. CI制备带hash的wheelhouse与`requirements-ci.lock`，归档固定Runtime规范/contract资源；离线阶段验证无源码路径和网络依赖。

## 交付物与验证

- `pyproject.toml`、`requirements-ci.lock`、`src/agent_meta_seed_harness/`、独立CI与release workflow。
- `docs/traceability.md`、`docs/runtime-dependencies.md`、`docs/runtime-contract/`及支持矩阵模板。
- `tests/contract/test_project_boundary.py`：允许的公开import、禁止私有/相邻checkout依赖、目录迁移及wheel metadata检查。
- `scripts/check_seed_traceability.py`骨架：读取profile、拒绝重复ID/伪证据；未实现需求保持未验证，S03完成发布判定。

在Seed仓库的锁定环境运行：

```console
python -m pytest -q tests/contract/test_project_boundary.py
python -m build --no-isolation
```

## 退出门禁

- Seed可在任意目录build/test，移动checkout不改变ArtifactId或manifest。
- Runtime仓库/网络不可用时，已pin依赖的Seed构建行为明确；Seed失败不回写Runtime发布状态。
- package metadata与import namespace分别使用连字符和下划线命名。
- SH-BOOT-01通过并记录运行报告；缺Host/State等接口登记OPEN，不影响本步工程准备，也不声称S01A已完成。
