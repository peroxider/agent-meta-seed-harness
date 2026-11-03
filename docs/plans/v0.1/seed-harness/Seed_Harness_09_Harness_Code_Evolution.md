# Seed Harness Step S09 — Harness Code Self-Evolution

> 归属：外部项目  
> 状态：PLANNED  
> 目标版本：Seed v0.3+（演化梯度第3层，见S07"在演化梯度中的定位"）  
> 前置：S08 VERIFIED；包候选自动化所需的Runtime能力（若有缺口）已按ADR/Contract规则交付  
> Runtime规范定位：§41.43、§41.60.5、§24、§21

## 目标

把"harness自身代码"纳入演化对象：候选不再是同一包内的Composition ChangeSet，而是一个新的AMPAK包版本。agent可以基于运行证据提出代码级改进候选，但候选必须作为完整新版本通过S03全部门禁（install→验证/实验→activate→drain→uninstall，§41.60.5路径），`Activate`的operator签名门禁保留。本步不引入常驻自动循环，不宣称无人监督的代码自演化。

## 输入与首个验收场景

输入为S08包、真实运行证据（恢复/边界场景失败、回归fixture缺口）、S03发布流水线及授权操作者。
首个场景：从失败历史定位loop/toolset层的一个代码级缺陷，生成带完整源码变更的新包候选；候选在fake model World中运行S03等价E2E与回归fixture全部通过后，按S03流程发布并经operator签名激活。
与S07/S08的本质区别：候选是package版本而非Composition变更；安装/激活/排空链路与人工发布的版本升级完全同构，不存在"代码变更绕过发布门禁"的旁路。

## 实施顺序

1. package候选生成器：从Evidence/Fact与既有源码构造源码变更（diff形态），产出完整候选源码树；候选变更必须能以普通PR形态在Seed仓库被人工审阅。
2. 候选包构建：复用S01/S03的AMPAK构建、签名、SBOM/provenance/compatibility流程，产出与新版本发布完全同构的候选AMPAK；golden与contract更新随候选一起产出。
3. 候选验证：安装到独立安装位，运行fake model E2E、兼容矩阵与回归fixture；未通过则候选FAILED并保留证据，production serving与旧版本不变。
4. 晋升：候选通过全部门禁后由operator签署activate，走§41.60.5的install新版本→activate→drain旧版本路径；版本/权限/证据漂移须重新验证与批准，不复用旧签名。
5. 回滚：drain新版本、恢复旧版本；候选代码晋升与制品类晋升（S07/S08）使用不同operation记录，不混淆审计链。

## 有界策略与制品链

- 一个触发窗口最多一个包候选；生成→验证→批准是显式阶段，每阶段可独立失败退出，失败不自动重试。
- 候选包必须通过S03全部门禁（签名、contract golden、SBOM/provenance、兼容矩阵、支持矩阵）；任何门禁不可豁免，不存在"小改动走快速通道"。
- agent可以propose代码候选与发起验证，不得签署activate；签名材料与Root私钥不进入生成器上下文。
- 禁止跨外部installation拼装Composition；禁止直接修改live serving包内容；候选源码树与live源码物理隔离。
- 每候选/每日的总预算（生成token、实验wall time）由policy Artifact声明并受Host ceiling约束；预算耗尽记录结果并退出。
- 候选验证与S07/S08实验共用World隔离约束：fresh clone、不共享live cache/temp；代码候选的实验不修改裁决它的E2E fixture与criteria制品。

## 批准、晋升与回滚

1. 批准预览展示：候选源码diff摘要与hash、新旧包manifest对比、SBOM/provenance/compatibility结果、E2E与回归报告位置、expected版本/revision。
2. operator签署activate的CommandEnvelope规定字段；签名验证失败、制品漂移或证据缺失全部拒绝。
3. 激活失败保持旧版本serving；drain期间新请求路由不变，已有会话按§41.60.5排空。
4. Rollback创建新的tracked transition指向旧版本；不宣称撤销已发生的external effect；State迁移单独计划。

## 交付物与验证命令

- `evolution/package_candidate.py`、`code_release.py`及candidate policy制品。
- `tests/acceptance/test_evolution_code_release.py`：缺陷历史→代码候选→S03门禁E2E→签名激活→drain/回滚及重启恢复。
- `tests/contract/test_evolution_code_governance.py`：门禁不可豁免、agent不可签名、候选隔离、预算上限与无常驻循环。

在Seed仓库运行：

```console
python -m pytest -q tests/contract/test_evolution_code_governance.py
python -m pytest -q tests/acceptance/test_evolution_code_release.py
python scripts/check_seed_traceability.py --profile evolution-code
```

## 退出门禁

- 代码自演化只经"新包版本+S03门禁+签名激活"路径生效；不存在绕过发布链的代码变更路径。
- 失败候选不影响production serving与旧版本；回滚有具名证明。
- agent全程不可签署activate；无常驻自动循环、无递归无界候选生成。
- SH-EVO-05、SH-GOV-04通过。
