# Seed Harness — Scope and Verification Plan

> 状态：PLANNED；以下全部为计划中的具名证明，尚未执行。
> 通用执行规则见[开发交接](Seed_Harness_Development_Guide.md)；公共依赖见[S01A](Seed_Harness_01A_Public_Host_Contract.md)。

## 范围与状态

`SH-*`是Seed本地需求ID，不添加或改变Runtime的FR/NFR/AC集合。
从本表建立Seed仓库`docs/traceability.md`；每行记录状态、Seed commit、Runtime wheel/Contract hash和报告链接。
需求状态为`PLANNED → IN_PROGRESS → VERIFIED`；文件存在、测试被收集或fixture独立通过不等同于集成通过。
本目录仅规定验收，所有目标测试路径均相对于未来Seed仓库，不要求它们出现在Runtime源码中。

## 需求到证明

| Seed ID | 步骤/profile | 必须证明的行为 | 具名证明路径（Seed仓库） |
|---|---|---|---|
| SH-BOOT-01 | S00/minimal | 独立依赖锁、禁止private import、任意checkout构建 | `tests/contract/test_project_boundary.py` |
| SH-PKG-01 | S01/minimal | AMPAK逻辑内容确定性、签名/path/contract negative | `tests/contract/test_package_contract.py` |
| SH-HOST-01 | S01A/minimal | 公开import、entrypoint/facade、冻结snapshot与唯一提交者 | `tests/contract/test_public_imports.py`、`tests/contract/test_host_contract.py` |
| SH-HOST-02 | S01A/minimal | 独立包从空目录加载到Task完成，禁止mock readiness/直写状态 | `tests/acceptance/test_host_bootstrap.py` |
| SH-LOOP-01 | S02/minimal | text/LENGTH/混合内容、空响应、finish reason与完整结果数组 | `tests/contract/test_loop_semantics.py` |
| SH-CTX-01 | S02/minimal | Redact先于Rank、预算滚动、tokenizer/policy/source provenance | `tests/contract/test_context_projection.py` |
| SH-TOOL-01 | S02/minimal | Task内call_id唯一、16次上限、冻结surface与串行/stop策略 | `tests/contract/test_tool_dispatch.py` |
| SH-REC-01 | S01A/S02/minimal | cancel/deadline/丢响应/崩溃、已知结果不重复执行、UNKNOWN不盲重试 | `tests/contract/test_host_recovery.py`、`tests/contract/test_loop_recovery.py` |
| SH-REL-01 | S03/all | 干净wheel lifecycle/升级、拒绝越权、旧serving保留 | `tests/acceptance/test_release_lifecycle.py` |
| SH-REL-02 | S03/all | 追踪集合/证据/支持矩阵与包内容一致 | `tests/contract/test_release_evidence.py` |
| SH-PROV-01 | S04/provider+ | profile、usage unknown、cost上界、rate limit/lookup/retry映射 | `tests/contract/test_provider_contract.py` |
| SH-PROV-02 | S04/provider+ | secret/egress/取消/raw retention、R2断网重放 | `tests/contract/test_provider_security.py`、`tests/contract/test_provider_replay.py` |
| SH-PROV-03 | S04/provider+ | 所声明模型的真实受控调用及有限成本 | `tests/acceptance/test_live_provider.py` |
| SH-CAP-01 | S05/tools+ | 每个operation的schema/grant/effect/idempotency/output限制 | `tests/contract/test_capability_toolset.py` |
| SH-CAP-02 | S05/tools+ | 实际工具与Scratch取消/恢复、State冲突、Artifact授权 | `tests/acceptance/test_capability_toolset.py` |
| SH-SESS-01 | S06/session+ | message_id去重、串行接纳、CAS冲突、摘要来源与冻结revision | `tests/contract/test_session_consistency.py` |
| SH-SESS-02 | S06/session+ | Task完成/写回间崩溃、提交丢响应与重启后不重复模型调用 | `tests/acceptance/test_session_recovery.py` |
| SH-EVO-01 | S07/evolution | 历史→fixture→Proposal/ChangeSet/Candidate/World/Evaluation | `tests/acceptance/test_evolution_pipeline.py` |
| SH-EVO-02 | S07/evolution | 预算/次数有界、无提升退出、克隆隔离与拒绝场景 | `tests/contract/test_evolution_policy.py` |
| SH-GOV-01 | S07/evolution | 固定裁判、签名绑定、权限/跨包/陈旧revision拒绝 | `tests/contract/test_evolution_governance.py` |
| SH-GOV-02 | S07/evolution | operator批准后切换、新旧包drain/卸载和可追踪Rollback | `tests/acceptance/test_evolution_release.py` |
| SH-EVO-03 | S08/evolution+ | 失败历史事件触发→artifact候选（REPLACE_ARTIFACT/ADD_SLOT白名单）→确定性实验→Promotion | `tests/acceptance/test_evolution_tool_pipeline.py` |
| SH-EVO-04 | S08/evolution+ | 触发窗口/冷却/数量上限、artifact kind白名单、真实模型成本预算与INVALID路径 | `tests/contract/test_evolution_artifact_policy.py` |
| SH-GOV-03 | S08/evolution+ | agent不可签名、制品diff预览、旧值hash与evaluator独立 | `tests/contract/test_evolution_artifact_governance.py` |
| SH-EVO-05 | S09/evolution++ | 代码候选→新AMPAK版本→S03门禁E2E→签名激活→drain/回滚 | `tests/acceptance/test_evolution_code_release.py` |
| SH-GOV-04 | S09/evolution++ | 门禁不可豁免、候选隔离、预算上限与无常驻循环 | `tests/contract/test_evolution_code_governance.py` |

## Runtime外部证明的固定映射

| Runtime外部ID | Seed必需路径 | 验证内容 |
|---|---|---|
| NFR-M48 | `tests/contract/test_nfr_m48.py` | 同fake response/snapshot/budget的等价状态序列与内容ArtifactId |
| AC-M17 | `tests/acceptance/test_ac_m17.py` | fake Model + InMemory的context→model→echo→facts/evidence→why→completion |
| AC-M48 | `tests/acceptance/test_ac_m48.py` | 非法响应/预算边界及文本注入不触发effect |

这些测试应调用真实公共Host流程，共享SH场景允许，但不得只检查fixture字段或直接更新Runtime数据库。
Runtime追踪表保留`external://agent-meta-seed-harness/...`引用；Seed证明不进入Runtime本仓库通过率。
FR-MRUN-007在Runtime文档间存在owner表述差异，Seed不自行重分类；以Runtime权威追踪审计处理，记录在依赖台账。

## 故障注入最小矩阵

| 注入点 | 必需观察 | 所属证明 |
|---|---|---|
| 模型调用前取消/排队超时 | 不调用Provider；计数/reservation符合§41.53 | SH-REC-01 |
| Provider接受后断线且无lookup | UNKNOWN，停止盲重试，保留durable request引用 | SH-REC-01/SH-PROV-01 |
| 模型或工具已提交结果、Task terminal前崩溃 | 恢复使用已提交结果，不重复effect | SH-HOST-01/SH-REC-01 |
| tool调用中撤销Grant或到deadline | 之后的effect拒绝；迟到结果审计且不逆转终态 | SH-REC-01/SH-CAP-02 |
| 会话pending提交后、Task提交前；Task receipt丢失 | 使用原command身份恢复，一个message只对应一个Task | SH-SESS-02 |
| Task已terminal、会话写回前；写回后响应丢失 | 补写/确认同一结果，不重新调用模型，不重复transcript | SH-SESS-02 |
| 外部State写入或serving切换 | 冲突显式报告；已接纳Task保持冻结revision | SH-SESS-01/SH-REL-01 |
| 实验失败、签名陈旧或reconcile失败 | 旧serving/production State保持，证据与拒绝原因可查 | SH-EVO-02/SH-GOV-01/02 |
| 候选制品/包未过门禁或激活失败 | 候选隔离，production serving与旧版本保持，证据可查 | SH-GOV-03/SH-GOV-04 |

## Profile判定

`minimal`要求S00～S03（含S01A）及三个Runtime外部ID；`provider/tools/session/evolution/evolution-artifact/evolution-code`逐层累积对应需求。
每个扩展profile同时重跑minimal；live job与离线fake/R2 job分开，未运行live证明只能声明replay支持。
`scripts/check_seed_traceability.py --profile <name>`检查ID唯一、测试可收集、required无skip/xfail、Runtime依赖已验证及报告hash匹配。
支持矩阵键为Seed version × Runtime wheel hash/Contract × OS/Python × Backend × Provider/profile；仅列有实际报告的组合。
已规划但接口未发布、测试未实现或环境缺失的行保持未验证，不用占位assert或伪造handle满足门禁。
