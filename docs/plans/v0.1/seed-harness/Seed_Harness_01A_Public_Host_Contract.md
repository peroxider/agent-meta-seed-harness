# Seed Harness Step S01A — Public Contract and Host Integration

> 归属：Seed消费验证；缺失Runtime接口由Runtime负责交付
> 状态：PLANNED；前置：S00/S01 VERIFIED
> Runtime规范定位：§40、§41.11、§41.36、§41.44、§41.53、§41.55、§41.60

## 目标、输入与范围

输入为S01签名包、显式pin的Runtime wheel/文档包及目标Backend profile。
先证明AMPAK如何加载、取得Task上下文并返回结果，再开始S02 Loop集成。
本文件列出必须关闭的依赖，不把规范伪代码或私有实现名称宣布为现有公共API。
S01A只关闭最小版依赖RP-00～RP-02；扩展依赖先登记，由S04～S07分别关闭。

## 管理面与执行面

- 管理面使用公开SDK/local RPC：上传制品、Harness生命周期、Task提交/查询/取消、Composition及Evolution已有管理调用。
- 执行面使用版本化Host SPI：冻结Task/View/Surface、context/model/tool调用、State/Scratch、执行记录及结果返回。
- Seed Adapter返回规范化InvocationResult；只有Runtime Application Service可提交Fact、State、Composition和terminal。
- 模型/工具操作必须经Host的Authority、budget、effect与Backend enforcement；Seed没有Root、数据库或底层Backend直连权限。
- `TaskEnvelope/TaskRuntime/TurnResult`仅引用§41.11的概念名，准确签名和公开import路径必须由所选Contract实际提供并通过consumer compile测试。

## Runtime依赖台账

下表是2026-10-30工作区的静态审阅结果，均为待验证状态。已有SDK方法只证明入口存在，不证明其后端链路完整。

| ID | 消费步骤 | 所需能力/公共入口 | 当前缺口 | Runtime owner/关闭证明 |
|---|---|---|---|---|
| RP-00 | S01A/S03 | 公开Transport连接、daemon启动/发现/停止、安装包加载 | SDK需注入Transport；完整产品启动装配及独立AMPAK执行路径未证实 | Runtime 06/07；干净wheel加载E2E |
| RP-01 | S01A/S02 | Host entrypoint、冻结Task/View/Surface、deadline/cancel、Model/Tool SPI | SDK没有完整公开执行期DTO/facade；不得借用domain或tests fixture绕过 | Runtime 07；公开import与Host consumer suite |
| RP-02 | S01A/S02 | Action/Invocation/Projection记录、幂等effect与terminal提交/恢复 | 现有记录mutator主要在私有store；公开Host提交通路待证明 | Runtime 05/07；崩溃/重放/唯一终态证明 |
| RP-03 | S04 | scoped credential注入、Provider egress、usage/cost enforcement | handle如何到受控Provider worker未有公开完整路径 | Runtime 04/07；凭据与联网边界测试 |
| RP-04 | S05/S06 | Artifact内容读取、State读/写/overlay、Scratch生命周期 | SDK有manifest/verify，缺内容读取及完整State/Scratch入口 | Runtime 02/03/07；授权、CAS与Scratch E2E |
| RP-05 | S06 | 稳定命令重放/结果查询、会话恢复所需公开State mutation | SDK便捷方法不能视作已支持跨重启重用同一完整CommandEnvelope | Runtime 06/07；丢响应与崩溃恢复测试 |
| RP-06 | S07 | Fact/Evidence/Evaluation查询；ChangeSet/Candidate/World登记 | `propose/run_experiment`存在；不能从其参数推定创建接口存在 | Runtime 06/08；纯公开Evolution E2E |
| RP-07 | S07 | 候选包/installation归属、Promotion签名、Evaluator重评入口 | 单installation约束与候选新源码激活/批准路径须明确 | Runtime 03/07/08；越权、跨包、陈旧签名negative suite |

Seed的`docs/runtime-dependencies.md`为每项记录：准确公开symbol/RPC/schema、wheel hash、Contract版本、权限、幂等语义、状态和证明链接。
状态为`OPEN → CONTRACT_PUBLISHED → VERIFIED`；只有Seed consumer test在该公开wheel上通过才能VERIFIED。
缺失能力先提交Runtime依赖项；若涉及冻结协议改变，先ADR/规范/追踪与兼容版本发布，再pin新wheel。
不得把任意payload塞进现有RPC、导入私有`_call/_mutate`、读DB/CAS路径或使用测试Fake来关闭产品依赖。

## Host装配检查表

1. 明确AMPAK entrypoint位置、依赖锁、加载验证、Backend placement、进程身份与生命周期；不依赖pip自动发现Seed。
2. 契约包给出Task输入、冻结snapshot、Context/Model/Tool request/result及stable error的公开DTO/schema；固定chosen contract versions。
3. Host只向Seed传递有界facade和scoped handle；不泄露repository/UoW、credential实现、native Provider对象或Root key。
4. 证明cancel/deadline从Task传播到Provider/Capability/worker；只有确认的终态才可发布，unknown effect阻止自动重试和Promotion。
5. 证明重启后通过durable request/Invocation状态恢复；已确认结果重放提交而不重复产生模型调用/副作用。
6. fake模型、Seed自有echo能力与真实Provider使用同一enforcement通道；测试结果不替代尚未交付的产品入口。

## 交付物

- `docs/runtime-dependencies.md`、`docs/host-integration.md`与pin的contract资源清单。
- `src/agent_meta_seed_harness/host_binding.py`：只绑定已公开SPI，不实现Runtime事务或复制enforcement。
- `tests/contract/test_public_imports.py`、`test_host_contract.py`、`test_host_recovery.py`。
- `tests/acceptance/test_host_bootstrap.py`：空目录启动、上传/安装/激活独立包、fake Task、停止/重启/停用/卸载。

## 验证与退出门禁

在Seed仓库运行：

```console
python -m pytest -q tests/contract/test_public_imports.py tests/contract/test_host_contract.py tests/contract/test_host_recovery.py
python -m pytest -q tests/acceptance/test_host_bootstrap.py
```

- 所有公开import及加载、冻结上下文、取消、幂等提交和终态恢复场景通过；required场景不得skip。
- 测试只安装发布wheel，不访问Runtime源码/私有store，不伪造readiness或直接推进Task状态。
- RP-00～RP-02关闭并附实际运行报告；RP-03～RP-07明确消费者和交付版本，不阻塞不依赖它们的最小版。
- 未满足时保留PLANNED/IN_PROGRESS；S02可以准备纯fixture，不能声明产品Host已接通。
