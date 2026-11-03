# Seed Harness Step S05 — First Capability Toolset

> 归属：外部项目  
> 状态：PLANNED  
> 前置：S04 VERIFIED，RP-04关闭
> Runtime规范定位：§41.36.3、§41.36.4、§41.44.1、§41.54

## 目标

提供第一批真实可用的工具Capability，使Loop能完成业务任务而不仅是conformance场景；全部工具走typed `tool_calls` dispatcher，不开旁路。

## 输入与范围

输入为S04包、公开Artifact/State/Scratch Host接口和冻结Capability Contract。
S02自有echo继续用于minimal回归；本步新增下表工具，不开放shell、任意文件路径、HTTP或Provider credential工具。

## 实施顺序

1. 定义最小工具目录，每个工具一个CapabilityDescriptor + CapabilityContract：
   - artifact读写：仅经公开Host使用已授权ArtifactId/内容，不读取data-dir/CAS文件路径；
   - Managed State读/写：Task冻结revision读取，写入带`expected_state_revision_id`；
   - IPython Scratch执行：按§41.54 trusted exploration边界，untrusted逻辑不走此路径；
   - 确定性计算/转换工具：作为E2E与Evolution实验的确定性基准。
2. 每个工具声明input/output schema、semantic_effects和最小scoped grant request；output先schema校验再redact成Artifact，违反schema即`INVALID_RESULT`并将Invocation置FAILED。
3. 更新Seed Composition模板（slots + wiring）与grant requests，重打AMPAK；capability surface冻结校验纳入install/activate链路。
4. 工具级negative fixtures：authority deny、schema违规、budget耗尽、重复call_id、未知kind全部fail closed。

## 首批operation清单

以下为Seed descriptor的计划operation ID；准确schema由本步生成并版本化，不增加Runtime内建RPC。

| Operation ID | 输入/输出要点 | 最小权限与效果/幂等 |
|---|---|---|
| `capability://seed.artifact#read` | ArtifactId → 允许的有界内容与hash；Restricted数据另授权 | 内容读取授权，Restricted需`artifact.read.restricted`；PURE |
| `capability://seed.artifact#put` | 已脱敏内容、media type → ArtifactId | `artifact.put`；KEYED，同request/payload返回同receipt |
| `capability://seed.state#read` | 已绑定state_id → Task冻结revision/本Task已提交overlay | `state.read`；PURE，不读取全局latest替代snapshot |
| `capability://seed.state#write` | state_id、expected revision、内容ArtifactId → 新revision | `state.write`；KEYED，冲突不merge，禁止写会话保留的transcript State |
| `capability://seed.scratch#execute` | source Artifact、session、deadline/budget → 受限输出refs | 对应`scratch.create/execute/inspect/release`授权按实际操作请求；KEYED，执行结果未知不得盲重跑 |
| `capability://seed.transform#normalize_json` | schema约束的JSON → 确定性规范化内容 | capability调用授权；PURE，禁止动态执行/文件/网络 |

所有工具还须通过Host通用`capability.invoke`及实际resource scope校验；不因标PURE跳过tool step计数或schema检查。
scratch权限名称使用Runtime registry；descriptor仅请求本工具实际用到的子集。
每个descriptor固定input/output schema、semantic_effects、contract version、scope、effect分类、request-id来源和Backend features。
统一输出默认1 MiB，分页/分块只使用已公开机制；Scratch沿用§41.54各输出通道上限，截断必须显式标记且不得破坏output schema。
input/output均先schema检查再记录受policy允许的脱敏内容；错误含稳定code和bounded diagnostic，不包含secret或live object。
State/Artifact写结果由Host提交；tool Adapter返回InvocationResult，不能直接改State引用或提交Fact。

## 交付物与验证命令

- `capabilities/artifact.py`、`state.py`、`scratch.py`、`transform.py`、对应descriptor/schema/grant及Composition更新。
- `tests/contract/test_capability_toolset.py`逐operation覆盖合法输入、边界大小、schema失败、越权、幂等重放/冲突和unsupported feature。
- `tests/acceptance/test_capability_toolset.py`覆盖公开Host实际读写、CAS冲突、Scratch取消/kill/restart/handle失效及source export门禁。

在Seed仓库运行：

```console
python -m pytest -q tests/contract/test_capability_toolset.py tests/acceptance/test_capability_toolset.py
python scripts/check_seed_traceability.py --profile tools
```

## 退出门禁

- 全部工具输出为redacted Artifact，provenance含child Action/Invocation因果链。
- 无工具绕过dispatcher固定顺序或冻结capability surface；即使声明并行也按响应顺序串行。
- 确定性工具在相同调用+相同state revision下产生相同输出ArtifactId。
- 文本中的形似工具指令不触发任何Capability或Backend effect（§41.53）。
- SH-CAP-01/02通过，复验S02 dispatcher与S04 Provider；不以进程内kernel作为独立Scratch worker的产品证明。
- 按S03发布新AMPAK，所有新增capability属于同一installation或Runtime builtin，遵守单package Composition限制。
