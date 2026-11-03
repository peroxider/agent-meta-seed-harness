# Seed Harness — Development Handoff

> 归属：外部项目；状态：PLANNED
> 审阅基准：2026-10-30工作区；所有测试路径和交付物均为开发目标，不是已通过的证据。

## 阅读与权威顺序

1. Runtime主规范第41章及其scope/traceability决定协议、权限和持久化语义。
2. 本目录规定Seed实施顺序、应用策略和验收；不新增Runtime RPC、schema字段或隐式权限。
3. [公共Host接入](Seed_Harness_01A_Public_Host_Contract.md)记录实际接口缺口；改变冻结Contract须由Runtime先完成ADR、规范/追踪更新和版本化发布。
4. [Seed追踪表](Seed_Harness_Traceability.md)记录Seed自己的证明，不把Seed失败计入Runtime发布结论。

本目录可整体复制到Seed仓库。规范基线须作为显式版本化文档包归档到Seed的`docs/runtime-contract/`，记录版本、commit和hash；开发/CI不得依赖Runtime相邻checkout。
执行下文命令、创建测试、构建AMPAK和发布产品均发生在Seed仓库；本次规划修订没有执行这些发布动作。

## 阶段与发布范围

| 步骤 | 输入 | 输出/准入 |
|---|---|---|
| S00 | 命名、Runtime wheel和contract文档包 | 独立工程、依赖锁、架构检查与初始追踪表 |
| S01 | S00 | 不执行代码的签名AMPAK、manifest与golden |
| S01A | S01包及显式Runtime版本 | 最小Host加载/调用/终态链路；基线依赖关闭 |
| S02 | S01A VERIFIED | fake Provider、确定性Loop/Context、Seed自有echo工具 |
| S03 | S00/S01/S01A/S02 VERIFIED | 最小版：fake模型E2E与独立distribution/AMPAK |
| S04 | S03及Provider所需Runtime能力 | 首个真实Provider与录制回放，新版本发布 |
| S05 | S04及工具所需Runtime能力 | Artifact/State/Scratch/确定性工具，新版本发布 |
| S06 | S05及会话恢复所需Runtime能力 | 单Realm单活动会话与恢复，新版本发布 |
| S07 | S06及演化所需Runtime能力 | 有界、确定性验证的改进闭环，新版本发布 |

实施链为`S00 → S01 → S01A → S02 → S03 → S04 → S05 → S06 → S07`。
每一步只在自己的Runtime依赖关闭后进入产品集成；纯schema、fixture和文档可提前准备。
S03不声称支持真实模型、业务工具、多轮会话或自迭代；后续版本累积重跑S03流程及该版本新增门禁。
多Provider路由、并行工具、多会话并发、联网业务工具、统计显著性评估和自主修改Evaluator不属于首轮交付。

## 每一步的交接格式

- 输入：前置步骤、Runtime release/wheel hash、Contract版本、Backend feature profile与fixture版本。
- 范围：本次新增行为及明确延期项；不以“兼容所有版本”替代支持矩阵。
- 交付物：模块、schema/policy/lock、AMPAK/manifest与具名测试路径。
- 验证：命令、预期结果、negative/fault场景及原始报告位置。
- 退出：所有必需测试通过、所需Runtime依赖关闭、追踪表附证据才可标记VERIFIED。

每份步骤文档按此格式补齐；协议字段只引用固定规范/contract资源，不在多份文档复制定义。
新增Seed应用schema需版本化并提供golden、拒绝未知字段及迁移测试；不得伪装成Runtime内建schema。

## 环境与通用验证命令

Seed的`requirements-ci.lock`锁定开发、构建、Runtime及可选Provider依赖并含hash；CI先在允许联网的制备阶段生成wheelhouse，再执行隔离测试。
在Seed仓库使用CPython 3.12、独立venv；以下命令是待实现的统一验收入口：

```console
python -m pip install --no-index --find-links wheelhouse --require-hashes -r requirements-ci.lock
python -m pytest -q tests/unit tests/contract
python -m pytest -q tests/acceptance
python scripts/check_seed_traceability.py --profile minimal
python -m build --no-isolation
```

步骤中的pytest命令必须真实收集测试；缺文件、零收集、required用例skip/xfail均不算通过。
`scripts/check_seed_traceability.py`及所有示例路径由S00/S03交付；本目录存在规划不表示这些文件已经存在。
live Provider独立使用显式启用的CI job：受限凭据、成本上限、超时和egress allowlist；无凭据时不运行该job，不把跳过当作live支持证据。
fake/R2回放job完全断网且无Provider secret；支持Linux/Windows的产品声明分别需要干净wheel安装和实际Host E2E，macOS只列实际smoke profile。

## 证据与状态管理

Seed的`docs/traceability.md`是追踪表的实例，`docs/runtime-dependencies.md`是Host依赖台账的实例。
每份证据包含Seed commit、Runtime wheel/Contract hash、Python/OS/Backend、命令、collected/passed/skipped、报告及fixture hash。
保存JUnit、测试摘要与制品hash到`reports/<profile>/`；报告内容先redact，不归档Provider secret、未授权raw response或签名密钥。
Runtime消费者证明须从公开wheel运行，不使用Runtime测试fixture、DB连接或私有mutator。
相同fixture的确定性比较采用固定测试clock/ID source或显式语义归一化；只比较声明的事件语义与内容hash，不要求随机UUID/真实时间相同。
raw retention默认关闭；录制回放只保存允许保留且脱敏的规范化响应，确需raw时遵守§41.11的Restricted Raw Artifact策略。

## 开发完成条件

- 对应profile的所有Seed需求均有具名、已运行的证明；AC-M17/AC-M48/NFR-M48路径与Runtime外部引用一致。
- 最小版没有开放的基线Host依赖；扩展版没有开放的本阶段依赖，不使用private hook或空成功替代。
- 新包先安装、验证/实验，再经过授权切换；旧包drain后才能卸载，历史制品与会话状态遵守retention。
- 发布复用S03流程，列明实际能力和延期项；主规范冲突、接口缺失或环境缺失均记录为未满足门禁。
