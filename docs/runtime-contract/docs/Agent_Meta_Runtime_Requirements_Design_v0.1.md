# Reflective + Evolvable Agent Meta-Runtime
## 面向可独立部署外部 Agent Harness 的白盒自我模型、因果历史与后继式自我演化需求与架构设计

> **版本**：v0.1-r11  
> **日期**：2026-09-14  
> **状态**：v0.1 实现基线（由 Reflective + Evolvable AgentOS v0.4 提纯）  
> **目标读者**：Agent Runtime / Harness / Self-Evolution / Agent Infrastructure 开发者  
> **设计目标**：让 Agent/Harness 自身成为 Agent 可以观察、解释、组合、实验、版本化、治理和演化的一等对象。  
> **当前范围**：本仓库只实现 Agent Meta-Runtime、公共 Harness Contract/SDK 与测试专用 Conformance Harness。Seed Harness 是位于另一项目中的外部消费者，不进入本仓库源码、wheel、bootstrap 或发布门禁。  
> **分步实施计划**：[`docs/plans/v0.1/README.md`](plans/v0.1/README.md)；Runtime按00～09实施，外部Seed按带`Seed_Harness_`前缀的S00～S03计划实施（S00～S03为最小可发布闭环，S04～S07为后续能力波次，均独立于Runtime发布）。
> **下层依赖**：Execution Backend Contract；完整 AgentOS Kernel 是提供 production-grade 语义的标准 Backend，但不是 Meta-Runtime 在普通 OS 上启动的必要前提。  
> **参考实现**：Prime Agent、DeepSeek Harness、python-cordis、IPython/ipykernel 仅用于机制参考，不定义 Meta-Runtime ontology。
> **首版实现决策**：采用 **CPython 3.12 Agent Meta-Runtime**。Managed profile 通过第 41.28 节冻结的 Protobuf v1 ABI 连接 AgentOS Kernel：Linux/macOS 使用 Unix Domain Socket，Windows 使用 Named Pipe；Portable profile 使用同一 Backend Contract 的本地实现。IPython 是 v0.1 Required Scratch Adapter，python-cordis 是 Optional Adapter，二者均不是 Meta-Runtime Core 硬依赖。

> **r5 实现闭环修订**：补充 Task canonical model、统一 mutation receipt、Backend terminal acknowledgement、Public/Backend wire contract、Authority bootstrap、Artifact canonicalization、Raw Artifact 加密与 retention、State Migration sandbox、Portable Candidate trust class、平台支持矩阵、Seed 默认 policy 与 FR/NFR/AC 追踪要求。

> **r6 编码级规范修订**：冻结 SQLite schema/transaction profile、local RPC framing、canonical value encoding、Fact catalog、Provider/Tool SPI、Composition validation、Reconciler crash boundaries、配置与发布约束，使 v0.1 实现不再依赖隐含的存储和协议决策。

> **r7 运行与验收闭环修订**：补充 Portable worker durable claim/process-tree cancellation、peer authentication/redaction、Architecture lint、readiness/backpressure、Public query/CLI、Seed Loop terminal semantics、IPython Scratch 生命周期和 source-only export，并扩展至 AC-M49。

> **r8 数据与信任闭环修订**：分离 Artifact/Encrypted Blob identity，补齐 Epoch/Principal/Instance/Surface/World/Evidence/Effect/历史 ref authority tables，冻结 Root recovery、Authority scope/counter、execution token、platform credential store，并建立逐 ID traceability 文档。

> **r9 实现交接闭环修订**：冻结 Capability Surface cache/invalidation、Health Probe、State migration/cutover/rollback、Outbox clock rollback 语义与实现交接清单；文档状态由草案提升为 v0.1 实现基线。

> **r10 Python 命名修订**：PyPI distribution与仓库保持`agent-meta-runtime`，Python import namespace冻结为更具体的`agent_meta_runtime`；CLI保持`agent-meta`，语言中立Protobuf package保持`agent_meta.*`。

> **r11 跨项目解耦修订**：Seed Harness迁移为外部项目`agent-meta-seed-harness`；Meta-Runtime不反向依赖其代码、Artifact、Composition或测试结果，并冻结core/serving双readiness、Harness install协议与跨仓库兼容矩阵。
>
> **Context开发补充**：[ADR 039](adr/039-frozen-context-policy-and-host-recomputation.md)定义公开通用Context机制、冻结来源和Host独立重算。外部Harness拥有应用策略；§41.44.4及External-Seed验收范围不变，开发回归不等于完整门禁通过。

---

# 0. 执行摘要

原 `Reflective + Evolvable AgentOS v0.4` 的核心强项不是传统 OS 的调度、资源仲裁和 IPC，而是：

```text
Agent 如何知道自己是什么？
Agent 如何知道自己为什么变成现在这样？
Agent 如何把自己的 Harness 当作可修改对象？
Agent 如何形成 Candidate、Experiment、Evidence 与 Evaluation？
Evaluation / Evolution 本身如何继续演化？
当前 Runtime / Constitution 成为瓶颈时如何构造 successor？
```

因此本设计将 v0.4 提纯为 **Agent Meta-Runtime**。

定义：

> **Agent Meta-Runtime 是建立在稳定 Execution Backend Contract 之上的反射式、自描述、版本化、因果可追踪和可自演化控制运行时。它把 Agent/Harness 的 Composition、Capability、Artifact、Managed State、Context、Authority、Fact、Evidence 与 Evolution 过程表示为一等对象，并允许 Agent 构造、验证和继任新的 Harness / Meta-Runtime 版本。完整 AgentOS Kernel 提供 Managed/Distributed 模式的强执行语义，但不是 Meta-Runtime 在普通 OS 上运行的必要前提。**

一句话使命：

> **The Meta-Runtime makes an agent system a first-class object to itself.**

中文：

> **Meta-Runtime 的目的，是让 Agent 系统自身成为 Agent 可以观察、解释、组合、实验和演化的一等对象。**

本设计的主线进一步提纯为三个核心域：

```text
Self-Model
  What am I?

Self-History
  Why am I this way?

Self-Transformation
  What can I become?
```

以及一个当前仍放在本文中的启动层：

```text
Seed Harness
  How do I start acting before I have evolved myself?
```

总体架构：

```text
┌──────────────────────────────────────────────┐
│ Seed / Evolved Harness                      │
│ Model · Task · Loop · Context · Skills ...  │
└──────────────────────┬───────────────────────┘
                       │
                       ▼
┌──────────────────────────────────────────────┐
│ Agent Meta-Runtime                           │
│                                              │
│ Self-Model                                   │
│   Composition · Capability · Artifact        │
│   State · Context · Authority · RuntimeView  │
│                                              │
│ Self-History                                 │
│   Fact · Action · Invocation · Evidence      │
│   Causal Graph · World                       │
│                                              │
│ Self-Transformation                          │
│   ChangeSet · Experiment · Evaluation        │
│   Evolution · Governance · Succession        │
└──────────────────────┬───────────────────────┘
                       │ Execution Backend Contract
                       ▼
┌──────────────────────────────────────────────┐
│ Execution Backend                            │
│                                              │
│ Portable: Linux / Windows / macOS            │
│ Managed:  AgentOS Kernel                     │
│ Distributed: Remote/Cluster AgentOS          │
└──────────────────────┬───────────────────────┘
                       ▼
               Physical Substrate
```

---

# 1. 设计目标与边界

## 1.1 目标

Meta-Runtime 必须支持：

- Harness 作为 Versioned Composition 被观察和替换；
- Capability identity 与 implementation Artifact 分离；
- Agent 的关键长期状态显式 Managed 或 Opaque；
- 对关键 Model/Capability Invocation 提供 Behavioral White-box；
- 维护 Fact / Evidence / Causal History；
- 区分 Evidence 与 Evaluation，使 Evaluator 自身可演化；
- 将 scratch exploration 晋升为正式 Capability；
- 支持 Proposal / ChangeSet / Candidate / Experiment / Evaluation / Promotion；
- Evaluation / Evolution / Governance 本身可替换；
- 高信任 Meta-Runtime / Constitution 可以通过 successor + witness + Root Succession 进入下一 Epoch；
- 不把 Planner / Memory / Skill / Subagent 等当前常见 Agent 结构固化为 Core；
- 不依赖某一语言 Runtime 或特定 plugin framework；
- 通过统一 **Execution Backend Contract** 获取执行能力；在 Managed/Distributed 模式下由 AgentOS Kernel 提供完整资源、隔离、监督与恢复语义，在 Portable 模式下由普通 OS 兼容 Backend 提供最小可移植执行能力。

## 1.2 非目标

Meta-Runtime 不负责：

```text
CPU scheduling
GPU placement
model concurrency arbitration
process hard kill
worker restart mechanics
IPC transport implementation
container / VM lifecycle
cgroup / namespace
network stack
physical credential injection
```

这些属于完整 AgentOS Kernel；Portable Backend 可以提供其中一部分的降级实现，但不得伪装成具有完整 Kernel 保证。

Meta-Runtime 只描述上层语义需求：

```text
EffectIntent
ResourceIntent
LogicalRealm
Authority relation
Candidate execution request
Experiment World requirement
```

## 1.3 与外部 Seed Harness 的关系

Seed Harness位于独立项目中，推荐仓库名与distribution为`agent-meta-seed-harness`、Python import为`agent_meta_seed_harness`。本地多仓库开发的默认示例路径是本仓库同级`../agent-meta-seed-harness`；该路径只属于开发工具配置，不写入Artifact identity、Meta DB、协议或release manifest，CI和部署必须允许任意checkout路径。

依赖方向严格为：

```text
agent-meta-seed-harness
    → agent-meta-runtime public Contract/SDK/local RPC
    → Execution Backend Contract
```

Meta-Runtime不得import、安装、定位或在启动时下载Seed项目，不得硬编码`capability://seed.*`、默认Loop/Context/Model policy或Seed Composition。Seed通过版本化AMPAK、Composition和scoped Grant request使用Meta-Runtime；它不得访问Runtime private repository、Unit of Work、credential或adapter实现。

Meta-Runtime发行测试专用、不可安装到产品Realm的`conformance_harness` fixture，用于证明Host Contract，不代表Seed实现。Meta-Runtime与Seed可以分别构建、测试、发布和升级；缺少Seed只意味着没有serving Composition，不影响Runtime core启动、管理和诊断。

---

# 2. Meta-Runtime Constitution

原 v0.4 的七条 Constitutional Basis 主要约束 Meta-Runtime，因此在本文保留，但重新命名为 `M-01 ~ M-07`，避免与 AgentOS Kernel Constitution 混淆。

> **Meta Core Admission Rule**  
> 任何进入 Meta-Runtime Core 的机制都必须指出其直接维护的 Meta Constitutional Principle / Invariant；否则默认属于 Protocol、Seed/Evolved Capability 或 AgentOS Kernel。

## 2.1 M-01 — Ontology Independence

> **Meta-Runtime ontology 先于任何实现。**

回答：**Agent 自我模型由谁定义？**

Prime Agent、DeepSeek Harness、python-cordis、IPython、Jupyter 等只能作为机制参考。

Meta ontology：

```text
Capability
Artifact
Composition
Managed State
Fact
Evidence
Authority
World
Action
Invocation
Experiment
Epoch
```

必须保持 language/runtime-neutral。

## 2.2 M-02 — Mechanism / Intelligence Separation

> **Meta-Runtime 固化自描述、自修改和验证机制，不固定具体智能策略。**

以下不得成为永久 Core intelligence：

```text
Planner
Memory strategy
Context strategy
Model router
Evaluator
Evolution search strategy
Governance policy
Curriculum
Meta-evaluator
```

## 2.3 M-03 — Consequential State Explicitness

> **任何影响未来 Agent 控制行为的长期状态必须 Managed，或显式声明 Opaque。**

```text
Consequential Persistent State
        ├─ Managed
        └─ Declared Opaque
```

不允许正式 Harness 依赖 Meta-Runtime 完全不知道其存在的长期 hidden control state。

## 2.4 M-04 — Non-destructive Versioned Evolution

> **Committed control state 不原地覆盖；变化形成新的 Artifact / State Revision / Composition，并通过显式 Transition 激活。**

适用于：

```text
Capability code
Prompt / Context policy
Managed State
Composition
Evaluation Criteria
Evolution Policy
Constitution Artifact
```

## 2.5 M-05 — Epistemic & Causal Integrity

> **发生过什么与如何解释它必须分离；重要 control transition 必须保留 actor、cause、authority 与 evidence lineage。**

```text
Fact / Observation
      ↓
Evidence
      ↓ interpreted by
Versioned Evaluation
```

## 2.6 M-06 — Authority-relative Mutation

> **Mutability 是 Principal × Authority × Scope × Epoch 的关系，而不是组件自己的 mutable bool。**

Ownership 与 Authority 必须分离。

## 2.7 M-07 — Successor-based Root Evolution

> **受保护 Meta-Root / Constitution 的演化必须通过 successor construction + independent validation + authority transfer，而不是 in-place self-overwrite。**

---

# 3. Derived Rules 与 Evolution Objectives

## DR-M01 — Scratch Freedom, Control Discipline

来源：`M-03 + M-02`

```text
Scratch / Exploration
      │ promote
      ▼
Managed Meta-Control Plane
```

临时 Python/JS/Rust object 不必全部治理；一旦进入长期 Harness control path，就必须有正式语义。

## DR-M02 — Intelligent Components Must Be Replaceable

来源：`M-02 + M-07`

任何包含 intelligence/policy 的组件都必须存在 replacement / succession path。

## DR-M03 — Immutable Committed Artifact, Mutable Active Reference

来源：`M-04`

## DR-M04 — Facts Stable, Interpretations Evolve

来源：`M-05`

## DR-M05 — No Protected In-place Self-overwrite

来源：`M-04 + M-07`

## EO-M01 — Minimize Externally Fixed Intelligence

随着 Agent self-governance 能力增强，应减少永久固定的 intelligent scaffolding。

## EO-M02 — Keep Meta-Root Mechanically Minimal

Meta-Root 长期仅保留：

```text
identity
artifact integrity
fact append
meta authority anchor
transition/succession protocol
AgentOS cutover/recovery ABI
```

不固定“什么叫更好”。

---

# 4. Unified Orthogonality Gate

正交性测试同时用于 Meta Constitution 与 Meta Primitive：

| Test | Constitutional Basis | Primitive |
|---|---|---|
| O-1 Non-derivability / Non-composability | 不得由已有 Basis 自然推出 | 可由已有 primitive 自然组合则应为 Protocol |
| O-2 Distinct Semantic Axis | 回答独立 Meta 问题 | 作用于独立机制维度 |
| O-3 Independent Violation / Necessity | 可单独违反 | 缺少时存在无法等价实现的核心场景 |
| O-4 Policy / Implementation Independence | 不绑定框架/当前模型 | 不携带 Agent policy |
| O-5 Minimal Responsibility | 不捆绑多个独立约束 | 不承担可拆职责 |

Meta-Runtime 当前 Primitive Basis 继续采用：

```text
Execute · Reflect · Transition · Effect
```

这里的 `Execute` 是 Meta-Runtime 语义：

> 请求一次计算 / invocation 发生。

实际如何执行由 Execution Backend 实现；完整调度、资源仲裁与强隔离由 Managed/Distributed AgentOS Kernel Backend 提供。

---

# 5. 三大核心域

## 5.1 Self-Model — What am I?

Self-Model 描述当前 Agent/Harness 的正式结构：

```text
Identity
Composition
Capability
Contract
Artifact
Instance
Managed State
Context Projection
Logical Authority
Logical Realm
Runtime View
```

它不试图枚举整个底层机器状态。

## 5.2 Self-History — Why am I this way?

```text
Fact
Action
Invocation
Evidence
Temporal Causal Graph
World
Evaluation lineage
Transaction lineage
```

目标是回答：

```text
为什么 Planner 现在是 v8？
谁创建了这个 Capability？
哪个 Invocation 产生了这次 EffectIntent？
哪些 Evidence 导致 candidate 被采用？
当时模型看见了什么 Context？
```

## 5.3 Self-Transformation — What can I become?

```text
Proposal
ChangeSet
Candidate
Experiment
Evaluation
Promotion
Rollback
Governance
Commitment
Witness
Succession
Archive / Population
```

这三类对象共同构成 Meta-Runtime 本体。

---

# 6. White-box Contract

“完全白盒”不等于扫描 AgentOS Kernel / Host OS 全部状态。

Meta-Runtime 的强保证边界是：

> **Agent Meta-Control Plane + 通过 Execution Backend Contract 暴露的 Execution Handles / Facts。**

## 6.1 六维 White-box

| 维度 | Meta-Runtime 必须回答 |
|---|---|
| Structural | 有哪些 Principal / Capability / Artifact / Instance / State / Handle？ |
| State | 哪些 Managed State 影响未来决策？ |
| Causal | 谁、为什么、通过什么 Action 导致当前状态？ |
| Historical | revision / mutation / rollback / epoch 历史？ |
| Authority | 谁有权观察/调用/替换/继任什么？ |
| Behavioral | 某次 Invocation 模型/Capability 实际看见了什么？ |

Replay 是可选第七维。

## 6.2 Managed / Observed / Opaque

```text
Managed
  Meta-Runtime 提供正式 identity/state/version/lifecycle

Observed
  可检查，但不保证 owner/persistence/rollback

Opaque
  知道存在与影响范围，但无法安全 introspect
```

禁止：

```text
Unknown consequential state
```

## 6.3 Execution Backend 作为外部受管执行基座

Meta-Runtime 不要求知道：

```text
Linux PID internals
GPU allocator internal heap
container namespace implementation
scheduler queue internals
```

只需要 Execution Backend 暴露；在 Managed 模式下对应 AgentOS Kernel ABI：

```text
ProcessHandle
ActivityHandle
ExecutionRealmHandle
ResourceLease
ChannelHandle
UsageSnapshot
KernelFact
```

---

# 7. Identity Model

## 7.1 Identity 分离

```text
CapabilityId
ArtifactId
InstanceId
StateRevisionId
CompositionId
PrincipalId
ActionId
InvocationId
FactId
EvidenceId
WorldId
ExperimentId
EvaluationId
EpochId
```

## 7.2 Execution identity 不纳入 Meta identity 复用

Execution Backend 提供 execution handle；完整 AgentOS Kernel Backend 进一步提供：

```text
ProcessHandle
ActivityHandle
ResourceLease
ExecutionRealmHandle
```

Meta-Runtime 可以引用这些 handle，但不将其 substrate metadata 当自己的 canonical identity。

## 7.3 Identity invariant

- logical identity 与 display name 分离；
- logical identity 与 authority 分离；
- Artifact identity 与 Instance identity 分离；
- State Revision 与 code Artifact 分离；
- execution handle 可失效，semantic identity 可跨 restart 恢复。

---

# 8. Artifact Model

Committed Artifact 必须 immutable。

```yaml
artifact_id: artifact://sha256/abc
kind: capability-code
created_by: principal://agent-a
created_from:
  - artifact://sha256/old
content_hash: abc
schema: artifact/v1
```

Artifact 类型：

```text
Capability Code
Configuration
Prompt / Context Policy
Harness Composition
Evaluation Criteria
Evolution/Search Policy
Schema
State Migration
Meta-Runtime Implementation
Constitution
Test / Benchmark Package
```

Active Reference：

```yaml
capability: capability://planner
active_artifact: artifact://sha256/abc
expected_previous: artifact://sha256/old
revision: 91
```

Transition 必须 CAS / version-aware。

---

# 9. Harness Composition

Harness 不定义为 Planner + Memory + Skill 的固定集合。

```text
Harness
=
Versioned Composition
+ Capability Artifacts
+ Managed State Bindings
+ Wiring
+ Authority Bindings
```

示例：

```yaml
composition_id: composition://agent-main/82
parent: composition://agent-main/81
slots:
  model:
    capability: capability://model
    artifact: artifact://...
  loop:
    capability: capability://loop
    artifact: artifact://...
  context:
    capability: capability://context
    artifact: artifact://...
  evaluation:
    capability: capability://evaluation
    artifact: artifact://...
wiring:
  - from: loop
    to: model
    interface: model.invoke/v2
state_bindings: ...
authority_bindings: ...
```

## 9.1 Desired、Serving 与 Realized

```text
Composition Artifact
     │ desired
     ▼
Meta Reconciler
     │ requests Execution Backend realization where needed
     ▼
Capability Instances + Execution Handles
```

Harness 不等于当前 live object graph。为避免“Composition 已提交，但实例尚未就绪”时产生语义歧义，运行时必须维护三个相互独立的 revision：

```text
desired_revision
    已经 committed、Reconciler 希望实现的 Composition

serving_revision
    新建 Task/Action 实际绑定并使用的 Composition

realized_revision
    Reconciler 已完成实例化、health check 与 binding 的 Composition
```

安全切换顺序：

```text
commit desired N+1
→ instantiate and health-check N+1
→ atomic CAS serving N → N+1
→ drain instances unique to N
→ mark realized N+1
```

任务在创建时冻结 `serving_revision`、`composition_id` 与 `capability_surface_revision`，运行中不得随全局指针漂移。Reconciliation 失败时继续保留旧 serving revision，禁止仅因 desired ref 已提交就把未就绪版本暴露给新任务。

---

# 10. Capability Contract

CapabilityDescriptor 回答：

> 当前实例是什么？

CapabilityContract 回答：

> 这个能力应该怎样被正确使用？

```yaml
capability: capability://planner
interface_version: planner/v4
requires:
  - interface: model.invoke/v2
provides:
  - interface: planner.plan/v4
operations:
  - name: plan
    input_schema: ...
    output_schema: ...
semantic_effects:
  - model_invoke
state:
  schema: planner-state/v7
authority:
  required:
    - capability.invoke
execution_profile:
  preferred_class: interactive
  kernel_requirements:
    resource_profile: profile://planner
```

注意：

`execution_profile` 是对 Execution Backend 的语义要求，不规定具体 GPU/process placement；若 Portable Backend 无法满足，必须显式 degrade/warn/reject。

Contract compatibility 不只依赖 SemVer。Composition validation 必须同时检查并生成 machine-readable `CompatibilityReport`：

```text
interface identifier + major version
input/output schema compatibility
semantic effect set
authority requirements
Backend feature requirements
state schema + migration availability
idempotency/retry semantics
```

新增外部 effect、扩大 Authority、降低隔离要求、改变 state schema、将 optional 输出改为 required，或改变幂等/重试语义，均属于 breaking change，即使作者没有修改版本号也必须拒绝兼容绑定。

---

# 11. Fact / Evidence Ledger

## 11.1 Semantic Fact 与 Kernel Fact

Meta-Runtime 维护 semantic facts：

```text
capability_defined
composition_committed
candidate_created
evaluation_finished
mutation_committed
```

Execution Backend 提供 execution facts；Managed Backend 中主要表现为 AgentOS Kernel facts：

```text
activity_started
lease_granted
process_failed
channel_closed
```

Meta-Runtime 可以统一投影，但不篡改 Kernel 原始执行事实。

## 11.2 Signal ≠ Fact

```text
Signal
  ephemeral coordination

Fact
  canonical history
```

## 11.3 Fact Envelope

```yaml
fact_id: fact://...
seq: ...
realm: logical-realm://...
actor: principal://...
action: action://...
causal_parent: action://...
transaction: transaction://...
entity: capability://planner
event: capability_activated
payload: ...
schema: ...
```

## 11.4 Evidence

Evidence 来源于：

```text
Meta Fact
Kernel Fact
External verified observation
Stable derived data
```

Evaluator 无权回写 source evidence。

---

# 12. Temporal Causal Runtime Graph

Graph 是 Fact Ledger + current projections 的查询模型，不是第四份独立 truth。

Node：

```text
Principal
Action
Invocation
Capability
Contract
Artifact
Instance
State Revision
Composition
Transaction
Proposal / ChangeSet
Experiment
World
Evidence
Evaluation
Commitment
Epoch
Kernel ExecutionHandle reference
```

Edges：

```text
owns
provides
depends_on
implements
instantiates
created_by
caused_by
requested_by
executed_by
authorized_by
derived_from
consumes
produces
evaluated_by
committed_by
version_of
realized_by_kernel
```

重要查询：

```text
why(entity)
lineage(entity)
what_changed(revA, revB)
who_authorized(action)
which_context(invocation)
which_kernel_execution(action)
```

---

# 13. Action / Invocation Model

## 13.1 Action

Action 是 Meta-Runtime 因果控制单位：

```yaml
action_id: action://...
actor: principal://agent-main
intent: ...
authority: grant://...
causal_parent: action://...
composition: composition://82
```

## 13.2 Invocation

Invocation 是一次实际调用：

```text
Model Invocation
Capability Invocation
Tool Invocation
Meta-Runtime operation
AgentOS Kernel request
```

## 13.3 与 AgentOS Activity 区分

```text
Action / Invocation
  semantic / causal

Activity
  execution / scheduling
```

建立引用：

```text
Action
  └ realized_by → ActivityHandle
```

---

# 14. Snapshot Runtime View 与一致性

Agent reasoning 不应在一次逻辑操作中读取不断漂移的 meta state。

```python
view = runtime.reflect.begin_view()
view.capabilities(...)
view.state(...)
view.authority(...)
```

返回：

```text
meta_revision
kernel_execution_snapshot_revision (optional)
```

一致性模型：

| Domain | Model |
|---|---|
| Artifact | immutable |
| Meta Fact Ledger | ordered per logical realm |
| Composition refs | desired/serving/realized 分别 atomic CAS |
| Managed State | revision / MVCC |
| Meta RuntimeView | snapshot revision |
| Scratch object | best-effort live view |
| Kernel execution state | handle snapshot / eventual reconciliation |

---

# 15. Managed State

正式 Capability 长期状态必须声明：

```yaml
state_id: state://planner/193
owner: capability://planner
schema: planner-state/v7
revision: 193
serializer: ...
parent_revision: 192
```

分类：

```text
Ephemeral Scratch
Session Managed State
Persistent Capability State
Derived Cache
Opaque External State
```

Migration 是一等 Artifact：

```text
state v7
 + migration artifact
 → state v8
```

不尝试 pickle 整个 AgentOS Kernel / process heap。

---

# 16. Scratch Runtime

Scratch 是 Meta-Runtime 允许的自由探索区。

可由：

```text
IPython
Node REPL
Rust evaluator
WASM runtime
remote compute session
```

提供。

Scratch execution 通过 `ExecutionBackend` 实现；Managed 模式映射为 AgentOS Kernel `Activity`，Portable 模式使用本地兼容 execution handle。Meta-Runtime 保留对象反射与 promotion 语义。

## 16.1 Object-level Reflection

支持：

```text
BindingHandle
ObservedObjectHandle
ManagedObjectHandle
```

安全检查默认避免：

```text
arbitrary repr
property invocation
custom iterator
unsafe getter
```

## 16.2 Promotion

```text
Ephemeral object/code
  → Observed
  → Managed
  → Artifact Candidate
  → Experiment
  → Capability
  → Composition
```

## 16.3 Scratch 不得变成隐式 Control Plane

若长期 Planner state 实际藏在未管理 dict / closure 中，则违反 M-03。

---

# 17. EffectIntent 与 ResourceIntent

v0.4 中 Effect/Resource System 被拆成上下两层。

Meta-Runtime 保留 **语义意图**：

```yaml
effect_intent: effect-intent://...
actor: principal://agent-main
action: action://...
owner: capability://planner
kind: process_spawn
authority: grant://...
reversibility_expectation: reversible
requirements:
  cpu: 2
  memory_mb: 4096
```

Execution Backend 负责真实执行；完整 AgentOS Kernel Backend 负责：

```text
admission
resource lease
activity/process realization
physical cleanup
hard kill
```

Portable Backend 只需提供最小 spawn/await/cancel/basic channel 兼容语义，并明确缺失的强保证。

返回：

```text
ActivityHandle
ProcessHandle
ResourceLease
KernelFact
```

Meta-Runtime 把结果纳入 causal history。

## 17.1 Effect reversibility

Meta-Runtime 仍需要语义区分：

```text
reversible
compensatable
irreversible
unknown
```

因为 Evolution Transaction 不能把 external irreversible effect 假装成 rollback 成功。

---

# 18. Authority Graph

Meta-Runtime Authority Graph 表达：

```text
谁应该有权做什么？
```

AgentOS Kernel enforcement 表达：

```text
未授权的实际执行确实做不到。
```

Authority 操作：

```text
grant
check
delegate
attenuate
revoke
```

Grant：

```yaml
grant_id: grant://...
issuer: authority-root://...
subject: principal://evolution-agent
permissions:
  - proposal.create
  - candidate.run
scope:
  target: capability://planner
constraints:
  epoch: epoch://17
  expires_at: ...
delegable: false
```

Meta-Runtime 可以将授权编译/映射为 Kernel execution grant/token。

## 18.1 Mutation Scope

```text
S0 Scratch
S1 Capability / Harness
S2 Meta-Runtime Architecture
S3 Meta Epoch Root / Constitution
S4 External AgentOS Kernel / physical substrate
```

S4 不是 Meta-Runtime ordinary authority；如需 AgentOS Kernel 升级，通过 Kernel 自己的升级/Root mechanism。

---

# 19. Context Projection 与 Behavioral White-box

Context 不是字符串拼接，而是可解释 projection：

```text
Context Projection
=
Fact / Session History
+ Managed State
+ Capability Index
+ Context Policy Artifact
+ Token / Budget Constraints
→ Model-visible Surface
```

Descriptor：

```yaml
projection_id: context://projection/88
policy_artifact: artifact://context-policy-v8
source_fact_range: [17001, 18300]
source_state_revisions:
  memory: state://memory/29
sections:
  - id: runtime-summary
    source: runtime-view://18300
budget:
  max_tokens: 120000
```

关键 ModelInvocation 必须可以回答：

```text
模型是谁？
模型看见了什么？
来自哪些事实/状态？
使用什么 Context Policy？
工具/Capability surface 是哪个 revision？
Harness Composition 是什么？
对应哪个 AgentOS ActivityHandle？
```

---

# 20. Lifecycle / Transaction / Meta-Reconciliation

## 20.1 Lifecycle

Capability lifecycle：

```text
define
validate
instantiate
activate
deactivate
drain
replace
release
```

## 20.2 Define ≠ Run

新 Artifact 定义不得自动执行。

```text
Construct Artifact
   ↓
Candidate
   ↓
Ask AgentOS Kernel to stage/run
   ↓
Evidence
   ↓
Activate Composition reference
```

## 20.3 Transaction

Meta Transaction 管理：

```text
Artifact reference
Managed State Revision
Composition
Authority binding
Meta schema
```

不承诺回滚 AgentOS Kernel 外部不可逆副作用。

## 20.4 Meta Reconciler

```text
Desired Meta Composition
     ↓
Meta Reconciler
     ├ create capability instance
     ├ request Kernel activity/process
     ├ migrate managed state
     ├ update binding
     └ drain old realization
```

Meta Reconciler 不自己决定 CPU/GPU placement。

---

# 21. Evolution Model

Evolution 不是固定 singleton engine，而是可替换 Capability。

标准对象：

```text
Observation
Diagnosis
Proposal
ChangeSet
Candidate
Experiment
World
Evidence
Evaluation
Decision
Promotion / Rollback
Archive
```

## 21.1 Proposal

```yaml
proposal_id: proposal://...
target: composition://82
hypothesis: ...
source_evidence: [...]
```

## 21.2 ChangeSet

跨多个 Capability：

```yaml
changeset: changeset://91
base_composition: composition://82
changes:
  - loop v4 -> v5
  - context v7 -> v8
preconditions:
  composition_revision: 82
rollback_target: composition://82
```

## 21.3 Candidate

Candidate 是未激活 successor Artifact / Composition。

## 21.4 Experiment

```yaml
experiment_id: experiment://...
baseline: composition://82
candidate: composition://83
worlds: [...]
evaluator_artifacts: [...]
budget:
  tokens: ...
  wall_time: ...
```

Experiment 的实际执行通过 AgentOS Kernel candidate Realm / Activity。

---

# 22. Execution World

Meta-Runtime 的 `World` 不是实际调度器，而是实验可比较性描述：

```text
workspace revision
filesystem snapshot
model/provider/version
Meta composition
AgentOS execution profile / realm constraints
environment variables
network mode
clock/randomness
dependency versions
hardware class constraints
```

Meta-Runtime 请求 AgentOS Kernel 尽可能实现 World constraint。

## 22.1 Replay 等级

```text
R0 none
R1 semantic input replay
R2 captured external response replay
R3 deterministic sandbox replay
```

必须声明实际 replay guarantee，不能伪造确定性。

---

# 23. Evaluation 与 Meta-Evaluation

EvaluationResult：

```yaml
evaluation_id: evaluation://...
evaluator_artifact: artifact://eval-v7
criteria_artifact: artifact://criteria-v9
evidence_set: [...]
worlds: [...]
baseline: composition://82
candidate: composition://83
result: ...
confidence: ...
```

Evaluation 是 interpretation，不是 Fact。

Evaluator v7 可以重新评价 Evaluator v3 曾使用的 Evidence。

## 23.1 防止“改裁判后宣布自己获胜”

保留：

```text
old evaluator result
new evaluator result
shared evidence
criteria lineage
external/peer witnesses
```

不要求一个永久固定 evaluator。

---

# 24. Self-Governance / Commitment

Commitment 是 Agent 自己形成的长期规则：

```text
修改核心 Capability 前执行 regression
关键结论要求独立 verification
重复失败优先修复相关能力
周期性审查 Context/Memory strategy
```

区分：

```text
Constitution
  Root-level meta invariant

Governance Commitment
  Agent self-imposed rule

Runtime Policy
  operational setting
```

Commitment 可普通 Evolution 修改；Constitution 只能 Root Succession 修改。

---

# 25. Evolution Scope

不再用 mutable / immutable 二元模型：

| Scope | 对象 | 路径 |
|---|---|---|
| M-S0 Scratch | 临时对象 | direct Meta Execute |
| M-S1 Harness Capability | Loop/Context/Memory/Evaluator | normal Meta Transaction |
| M-S2 Meta Architecture | protocol/schema/meta-runtime component | Meta-Transaction |
| M-S3 Meta Epoch Root | Constitution/Meta authority/fact root | Root Succession |
| M-S4 AgentOS Kernel | execution substrate | AgentOS Kernel own upgrade protocol |

Meta-Runtime 不能通过普通 mutation path 任意改写 AgentOS Kernel 本身。

---

# 26. Trust Epoch

Trust Epoch 表示 Meta-Runtime 当前受保护 Root：

```yaml
epoch: epoch://17
constitution: artifact://constitution-v4
meta_runtime_root: artifact://meta-runtime-v8
authority_root: ...
fact_root: ...
agentos_kernel_requirement:
  abi: agentos-kernel/v1
```

当前 Epoch 内 Root 不被 ordinary Meta Transaction 原地修改。

---

# 27. Root Succession

Root Succession 现在明确拆成：

## 27.1 Meta-Runtime 负责

```text
construct successor
constitution successor
meta experiment
semantic evidence
witness collection
decide/select candidate
request authority transfer
```

## 27.2 AgentOS Kernel 负责

```text
create isolated ExecutionRealm
boot successor runtime
health probe
run replay activity
atomic route switch
drain old runtime
revert on failure
```

## 27.3 No Self-Overwrite

```text
Current Meta-Root A
   │ construct
   ▼
Candidate Meta-Root B
   │ AgentOS isolated realization
   ▼
Experiment / Witness
   │
   ▼
Kernel-assisted atomic cutover
   │
   ▼
Epoch N+1
```

---

# 28. Witness Set

双 AgentOS / 双 Meta-Runtime 只是一种 witness strategy。

Witness：

```text
Self Witness
Peer Meta-Runtime
Alternative Model
Replay Suite
Benchmark
Formal/Static Verifier
Environment Test
Human/External Witness
```

Witness 不天然拥有 commit authority。

```yaml
witness_id: witness://peer-b
kind: peer-runtime
artifact_or_endpoint: ...
independence_class: same-model-different-context
scope: candidate-evaluation
```

---

# 29. Peer Meta-Runtime / Cross-Evolution

```text
A proposes A'
B evaluates A'

B proposes B'
A evaluates B'
```

可以降低单一系统 self-confirmation，但不保证消除 correlated blind spots。

因此核心只定义 WitnessSet / Archive，不固定 pair topology。

---

# 30. Population / Archive Evolution

允许分支：

```text
Composition 82
   ├ 83-A
   ├ 83-B
   │  └ 84-B1
   └ 83-C
```

Archive 保存：

```text
candidate artifact
parent lineage
world/evidence
evaluator/criteria
failure reason
resource cost
```

Search/population policy 属于 Evolvable Capability。

---

# 31. Meta-Root / External Trust Boundary

Meta-Runtime 不再把 process isolation/hard quota 自己当 Core implementation；这些由 AgentOS Kernel 提供。

长期 Meta-Root 趋向：

```text
Meta Root
├ identity / artifact integrity semantics
├ Meta authority anchor
├ trusted semantic fact append
├ version/transition protocol
├ Constitution artifact
├ AgentOS ABI client + cutover protocol
└ prior epoch semantic recovery pointer
```

它不固定：

```text
Planner
Memory
Evaluator
Evolution strategy
Scheduler
GPU allocator
```

---

# 32. Logical Multi-Agent / Distributed Meta-Runtime

Meta-Runtime 的 Realm 改称 **LogicalRealm**：

```text
logical-realm://session-a
logical-realm://candidate-91
logical-realm://peer-b
```

包含：

```text
fact order
principal namespace
meta state revision
authority bindings
composition scope
```

物理/执行隔离由 AgentOS `ExecutionRealm` 提供。

映射：

```text
LogicalRealm
   │ requests
   ├─ ExecutionRealm A
   ├─ ExecutionRealm B
   └─ Remote Activity
```

Cross-Realm semantic handle：

```text
ArtifactHandle
RemoteCapabilityHandle
ManagedStateHandle
Logical RPC Contract
```

实际 transport 由 AgentOS Channel 实现。

---

# 33. Semantic Persistence / Recovery

Authoritative semantic recovery format：

```text
Meta Epoch Manifest
+ Active Harness Composition
+ Immutable Artifacts
+ Managed State Revisions
+ Meta Fact Ledger Boundary
+ Logical Authority Bindings
+ AgentOS ABI / execution handle reconciliation info
```

不把 Kernel process heap 当 authoritative source。

恢复：

```text
Meta-Runtime restarts
  ↓
reads committed epoch/composition
  ↓
rebuilds semantic state
  ↓
asks AgentOS to create/reconcile execution realizations
  ↓
marks lost/expired Kernel handles
  ↓
resumes from stable semantic fact boundary
```

---

# 34. Memory / Object Lifetime

Meta-Runtime 只管理自身 object registry / scratch adapter，不负责 OS memory scheduler。

要求：

- Observed object 默认 weak/non-owning；
- Managed object 才允许 strong ownership；
- history 不保存旧对象强引用；
- object release 返回 semantic result；
- AgentOS ResourceLease 的实际内存回收由 Kernel 管理；
- Python/IPython output cache 等属于 Scratch Adapter 工程约束。

---

# 35. 安全模型

## 35.1 Reflection Authority

White-box 不意味着所有 Principal 可见所有 secret。

```text
metadata
preview
full
secret
```

## 35.2 Secret separation

普通 Runtime Graph / Fact payload 不保存原始 secret value。

Meta-Runtime 只保存：

```text
credential handle
scope
issuer
expiry
usage facts
```

实际 secret broker 在 AgentOS Kernel / external substrate。

## 35.3 Safe Reflection

默认不调用 arbitrary repr/property/descriptor。

## 35.4 Candidate sandbox

Meta-Runtime 只声明 candidate isolation requirement；AgentOS Kernel 提供 ExecutionRealm。

---

# 36. Meta-Runtime API

## 36.1 Reflect

```text
runtime.reflect.view()
runtime.capabilities.list()
runtime.capabilities.inspect(...)
runtime.contracts.describe(...)
runtime.state.inspect(...)
runtime.graph.why(...)
runtime.invocations.inspect(...)
```

## 36.2 Artifact / Composition

```text
runtime.artifacts.put(...)
runtime.compositions.get(...)
runtime.compositions.branch(...)
runtime.compositions.diff(...)
```

## 36.3 Transition / Transaction

```text
runtime.transaction.begin(...)
runtime.transition.apply(...)
runtime.transaction.commit(...)
runtime.transaction.rollback(...)
```

## 36.4 EffectIntent / Execution Request

```text
runtime.effects.request(...)
runtime.agentos.activity.submit(...)
runtime.agentos.resource.request(...)
```

## 36.5 Authority

```text
runtime.authority.inspect(...)
runtime.authority.grant(...)
runtime.authority.delegate(...)
runtime.authority.revoke(...)
```

Physical enforcement 通过 Execution Backend；Managed/Distributed 模式由 AgentOS Kernel ABI 提供强制执行。

## 36.6 Evolution

```text
ctx.evolution.propose(...)
ctx.evaluation.evaluate(...)
ctx.governance.review(...)
```

仅对应 capability 已安装时存在。

## 36.7 Succession

```text
runtime.succession.propose(...)
runtime.succession.stage(...)
runtime.succession.witness(...)
runtime.succession.request_cutover(...)
```

---

# 37. Execution Backend Contract 与 AgentOS Kernel ABI

Meta-Runtime **依赖稳定的 Execution Backend Contract，而不是必须依赖某个 AgentOS Kernel daemon**。完整 AgentOS Kernel 是该 Contract 的标准、最强语义实现。

## 37.0 依赖方向

```text
Seed / Evolved Harness
        ↓
Agent Meta-Runtime
        ↓
Execution Backend Contract
   ┌────┼───────────────┐
   ▼    ▼               ▼
Portable Backend   AgentOS Kernel   Remote AgentOS
Linux/Windows/     Managed          Distributed
macOS              semantics        semantics
```

Meta-Runtime 的 Composition / Artifact / Fact / Evolution ontology 对三个 Backend 保持不变。

### 37.0.1 Execution Profiles

| Profile | 典型环境 | 最低语义 |
|---|---|---|
| **Portable** | 普通 Linux / Windows / macOS | spawn/await/cancel、basic channel/workspace、basic usage/facts |
| **Managed** | 本地 AgentOS Kernel | Realm isolation、ResourceLease、Supervisor、Credential Broker、hard quota/recovery |
| **Distributed** | AgentOS cluster / remote Kernel | placement、distributed lease、cross-node channel、cluster recovery |

Portable 模式的目标是**不要求安装本设计的 AgentOS Kernel**即可开发和运行 Meta-Runtime，并允许外部 Harness 通过公共协议接入；它不是重新实现一套完整 Python AgentOS。

### 37.0.2 Backend Capability Profile

Backend 必须报告真实能力，禁止语义冒充：

```yaml
backend: local-windows
profile: portable
features:
  process: true
  activity: true
  channel: true
  hard_memory_quota: partial
  isolated_realm: partial
  gpu_lease: false
  distributed_schedule: false
  credential_broker: false
```

Meta-Runtime / Governance 根据 feature 决定 degrade、warn、reject 或要求 Managed Backend。

### 37.0.3 ExecutionBackend Protocol

概念接口：

```python
class ExecutionBackend(Protocol):
    async def submit(...): ...
    async def await_activity(...): ...
    async def cancel(...): ...
    async def open_channel(...): ...
    async def inspect(...): ...
    async def capabilities(...): ...
```

`AgentOSKernelBackend`、`PortableLinuxBackend`、`PortableWindowsBackend`、`PortableMacOSBackend` 都是该 Contract 的实现。

## 37.1 Full AgentOS Kernel surface

当 Backend 为完整 AgentOS Kernel 时，Meta-Runtime 使用稳定 AgentOS ABI，而不是 Host-specific API。

最小 client surface：

```text
process.spawn / stop / inspect
activity.submit / cancel / await / inspect
realm.create / destroy
resource.request / release / inspect
channel.open / send / recv / close
facts.stream
supervisor operations
credential scoped-use
```

Kernel 返回：

```text
ProcessHandle
ActivityHandle
ExecutionRealmHandle
ResourceLease
ChannelHandle
KernelFact
UsageSnapshot
RecoveryReport
```

## 37.2 Meta EffectIntent 到 Kernel operation

例如：

```text
Meta EffectIntent(process_spawn)
      ↓
AgentOS activity.submit + resource.request
      ↓
ProcessHandle / Lease / KernelFacts
      ↓
Meta Fact / Causal Graph
```

## 37.3 Managed Backend 依赖方向

```text
External Seed Harness project
  ↓
Meta-Runtime
  ↓
ExecutionBackend
      ├ Portable local OS
      └ AgentOS Kernel
```

完整 AgentOS Kernel 禁止 import Meta Evolution/Evaluator；Portable Backend 也只能实现 execution compatibility，不得反向把 Harness policy 塞进 Backend。

---

# 38. Reference Implementation Mapping

本章仅映射实现，不定义 ontology。

## 38.1 IPython / ipykernel

定位：

> **Scratch Execution + Object Reflection Adapter**

保留能力：

```text
persistent namespace
safe/bounded object inspection
execution event metadata
scratch object promotion
```

进程生命周期等真实执行下沉 Execution Backend；hard quota、worker isolation 等强保证由 AgentOS Kernel Backend 提供。

## 38.2 python-cordis

定位：

> **Capability Lifecycle / Service Composition Adapter**

适合映射：

```text
Context
Fiber
Effect registration
Service graph
Loader/Reconciler seed
```

但 Cordis resource spawn 的物理执行最终应走 Execution Backend Contract；Managed 模式走 AgentOS ABI。

## 38.3 Prime Agent

参考：

```text
persistent programmable environment
minimal fixed tool surface
continual harness state
host-authoritative operations
```

不把其固定 Harness state ontology 作为 Meta-Runtime ontology。

## 38.4 DeepSeek Harness

参考：

```text
append-only SessionEvent
replayable surface
Everything is Plugin
immutable package + current/next pointer
Define != Run
```

动态 plugin/session-local 的具体限制不进入 Meta-Runtime定义。

---

# 39. CPython v0.1 实现 Profile

本节记录 v0.1 的**已冻结实现 Profile**。`M-01 Ontology Independence` 仍要求 Meta-Runtime ontology 与 Python、IPython、Cordis、Rust Kernel 实现解耦；这些选择约束 v0.1 产品与验收，但不永久绑定未来实现。

## 39.1 为什么 v0.1 选择 CPython-first

Meta-Runtime 的主要工作是：

```text
schema / descriptor
Artifact / Composition / Managed State
Fact / Causal Graph
Context Projection
Model / Capability invocation
Evaluation / Experiment / Evolution
动态反射 / promotion
Adapter orchestration
```

这些路径通常不是 Kernel 微秒级 hot path，更重视动态性、可修改性、Agent/ML 生态集成与开发迭代速度。因此 v0.1 产品实现固定使用 CPython 3.12。

Python 同时天然连接：

```text
IPython / Jupyter
LLM SDK
PyTorch / Transformers
NumPy / pandas
机器人 / ML / evaluation 生态
```

但：

> **CPython 3.12 是 v0.1 实现语言，不是 Meta-Runtime ontology 依赖。**

## 39.2 Meta-Runtime 的硬依赖与默认 Adapter

真正的硬依赖应尽量收缩为：

```text
1. Execution Backend Contract
2. Meta persistent state / Fact / Artifact storage
3. language-neutral schema / serialization
```

`AgentOS Kernel ABI client` 是 Managed/Distributed Backend 的默认实现，不再是 Meta-Runtime Core 的唯一执行依赖。

Adapter的v0.1范围固定为：

```text
IPython / ipykernel    → Required Runtime Scratch Adapter
python-cordis         → Optional Runtime Capability Lifecycle Adapter
Conformance Provider  → tests-only Runtime fixture
Model Providers       → external Harness-owned adapters
```

因此 Core package 不应直接 `import IPython` 或假设 `Cordis Fiber` 就是 `Capability` ontology。

## 39.3 与 Rust AgentOS Kernel 的语言边界

Managed profile的边界固定为：

```text
Python
Seed / Evolved Harness
        ↓
Python
Agent Meta-Runtime
        ↓
AgentOS ABI v1: framed Protobuf + UDS / Windows Named Pipe
        ↓
Rust
AgentOS Kernel (agentosd)
        ↓
Linux / Container / GPU / Model / Browser
```

Meta-Runtime 应把 Kernel 当作一个**独立服务/故障域**，即使二者位于同一台机器，也不得依赖：

```text
same process
same heap
Rust native pointer
Linux PID as semantic identity
Kernel private queue / registry
```

这会强迫 timeout、reconnect、version negotiation、handle identity 与 failure semantics 真实成立。

## 39.4 ABI / Transport v0.1 决策

单机 v0.1 固定为：

```text
Protobuf schema
+
POSIX Unix Domain Socket / Windows Named Pipe transport
```

v0.2+ 可增加（不得改变 v1 语义）：

```text
gRPC / remote transport
QUIC
in-process test transport
```

但语义必须保持一致。

建立 Kernel session 时应完成：

```text
ABI version negotiation
feature negotiation
optional capability discovery
```

Meta-Runtime 根据 feature 判断可用能力，而不是判断 Rust crate version。

`PyO3` 可以用于 hashing / codec / graph indexing 等局部 fast path，但**不应成为唯一 AgentOS Kernel ABI**；否则 Meta-Runtime 会重新绑定 Rust 内部实现。

## 39.5 Meta-Runtime v0.1 持久化

v0.1 固定分成：

```text
Meta Metadata / Fact Store
    → SQLite STRICT schema

Artifact Store
    → local filesystem / content-addressed directory
```

Meta store 保存：

```text
semantic identity
Artifact metadata
Composition
Managed State revision
Authority Graph
Fact / Action / Invocation
Evidence / Evaluation
Experiment / Evolution history
Epoch / succession metadata
```

不保存 Kernel authoritative state：

```text
AgentProcess scheduling state
ResourceLease physical allocation
ExecutionRealm physical realization
Channel transport internals
Supervisor execution tree
```

Kernel 与 Meta-Runtime 即使首版都使用 SQLite，也应使用独立 DB/schema，避免通过共享表形成隐藏耦合。

## 39.6 package 依赖边界

```text
agent-meta-runtime-core
    ├─ 不硬依赖 IPython
    ├─ 不硬依赖 python-cordis
    └─ 只依赖 ExecutionBackend abstraction + stores

agent-meta-runtime-ipython
    └─ depends on core

agent-meta-runtime-cordis
    └─ depends on core

agent-meta-seed-harness             separate repository/distribution
    └─ depends on agent_meta_runtime.sdk / public local RPC
```

Seed不得放入Runtime monorepo的产品source、wheel或extras；本地工作区可以并列checkout，但两者独立version/release。


## 39.7 Portable Execution Backend

为了让Meta-Runtime及任意外部Harness在普通开发机上直接运行，首版提供轻量Portable Backend：

```text
PortableLinuxBackend
  → asyncio/subprocess + process group + pipe/socket + filesystem

PortableWindowsBackend
  → process + Job Object（可用时）+ named pipe/socket + filesystem

PortableMacOSBackend
  → process group + pipe/socket + filesystem
```

Portable Backend 只负责最低 execution compatibility：

```text
spawn / submit
await / timeout
cooperative + best-effort forced cancel
basic channel
workspace / env
basic usage / execution facts
```

它**不应复制完整 AgentOS**。以下能力允许缺失或 partial：

```text
multi-tenant fair scheduler
strong multi-resource lease
hard Realm isolation
credential broker
distributed placement
crash-consistent lease recovery
```

Meta-Runtime 必须根据 `BackendCapabilityProfile` 诚实显示这些差异。

## 39.8 Managed Backend：Rust AgentOS Kernel

生产/多 Agent/强隔离场景继续推荐：

```text
Python Meta-Runtime
    ↓ framed Protobuf + UDS/Windows Named Pipe
Rust agentosd
    ↓
Linux / Container / GPU / Model / Browser
```

它提供 Portable 模式之外的强语义：ResourceLease、Scheduler、ExecutionRealm、Supervisor、Credential Broker、structured recovery 等。

## 39.9 首版 Managed 模式进程拓扑

```text
Host Machine
│
├─ agentosd                         Rust / Kernel
│   ├─ scheduler
│   ├─ resource broker
│   ├─ supervisor
│   ├─ realm/isolation
│   ├─ channel
│   └─ credentials
│
├─ agent-meta-runtime               Python
│   ├─ meta core
│   ├─ Fact / Causal Graph
│   ├─ Cordis adapter
│   ├─ Evolution
│   └─ Generic Harness Host
│
└─ AgentOS-managed Workers
    ├─ ipykernel                     Python
    ├─ shell/tool worker
    ├─ browser worker
    ├─ model service adapter
    └─ subagent / isolated capability
```

IPython worker 不应长期通过 Meta-Runtime 直接 `subprocess.Popen()` 管理；正确方向是：

```text
Meta-Runtime
    ↓ AgentOS Activity/Process request
AgentOS Kernel
    ↓
IPython Worker
    ↓
Meta-Runtime Scratch Adapter connects
```

## 39.10 Crash / Restart 边界

### Meta-Runtime crash

若 Python Meta-Runtime 因异常、OOM 或错误自修改退出：

```text
Rust AgentOS Kernel 继续存活
→ supervisor 记录/冻结/回收相关 workload（按 policy）
→ restart Meta-Runtime
→ reconnect AgentOS ABI
→ reload Composition / State / Fact boundary
→ reconcile ProcessHandle / ActivityHandle / Lease
→ semantic resume
```

### Kernel restart

若 Kernel daemon 重启：

```text
Meta-Runtime reconnect
→ ABI renegotiate
→ Kernel reconcile physical workload
→ return renewed logical handles / recovery report
→ Meta-Runtime reconcile semantic graph
```

因此必须坚持：

```text
logical identity ≠ native process identity
```

## 39.11 Capability placement 与信任边界

第一版内建且受信的 Cordis Adapter 可以默认 in-process，但长期 Contract 应允许：

```text
placement:
  in_process
  isolated_activity
  isolated_process
  remote
```

映射：

```text
in_process        → Python/Cordis instance
isolated_activity → AgentOS Activity
isolated_process  → AgentOS AgentProcess
remote            → RemoteCapabilityHandle / RPC
```

这样 Meta-Runtime 不会退化成一个持续膨胀的 Python monolith。

`in_process` 不只是性能选项，而是显式信任声明：运行在 Meta-Runtime 进程内的 Python 代码理论上可以访问进程内存、import private module 并绕过语义 Authority。因此默认 placement policy 为：

| Capability 来源 | 默认 placement |
|---|---|
| Meta-Runtime 内建且经过发布签名 | `in_process` |
| 受信外部 Harness Capability | `in_process` 或 `isolated_process` |
| 第三方 Capability | `isolated_process` |
| Candidate / Evolved Capability | `isolated_process` |
| 未知来源代码或高风险工具 | Managed Backend `isolated_realm` |

第三方或 Candidate 不得仅为降低延迟而静默回退到 `in_process`。Portable Backend 无法提供 required isolation 时必须拒绝运行。

上述来源分类还必须经过 41.32 的 trust-class 判定；来源标签本身不能把未知代码降级为 `trusted_candidate`。`isolated_process` 只满足 Portable trusted isolation，不等价于 Managed strong isolation。

## 39.12 v0.1 依赖决策

| 类别 | v0.1 决策 | 架构地位 |
|---|---|---|
| Language | CPython 3.12 | v0.1 implementation only |
| Async runtime | asyncio | Python implementation detail |
| Kernel client schema | Protobuf-generated Python types | AgentOS ABI implementation |
| Kernel transport | Linux/macOS UDS；Windows Named Pipe | replaceable transport |
| Meta DB | SQLite | replaceable store |
| Artifact store | local content-addressed filesystem | replaceable store |
| Scratch | IPython/ipykernel | Required v0.1 Adapter |
| Capability runtime | builtin SPI；python-cordis Optional | Adapter |
| Model | Runtime只发布SPI/schema；具体Provider由外部Harness提供 | External capability |

## 39.13 概念模块结构

```text
agent-meta-runtime/
├── constitution/
│   ├── schema/
│   ├── orthogonality_lint/
│   └── traceability/
├── core/
│   ├── identity/
│   ├── artifact/
│   ├── composition/
│   ├── capability/
│   ├── state/
│   ├── authority/
│   └── view/
├── history/
│   ├── facts/
│   ├── actions/
│   ├── invocations/
│   ├── evidence/
│   └── causal_graph/
├── stores/
│   ├── metadata/
│   ├── facts/
│   └── artifacts/
├── adapters/
│   ├── ipython/
│   └── cordis/
├── scratch/
│   ├── object_registry/
│   └── promotion/
├── evolution/
│   ├── proposal/
│   ├── changeset/
│   ├── experiment/
│   ├── evaluation/
│   ├── archive/
│   └── succession/
├── agentos_client/
│   ├── abi/
│   ├── transport/
│   ├── handles/
│   └── facts/
└── sdk/
    ├── client/
    ├── contracts/
    └── manifest/
```

上图仅表达概念归属；实际 v0.1 repository与package边界固定遵守41.59.5，不定义 Meta-Runtime ontology。

---

# 40. External Harness Integration Boundary

## 40.1 Meta-Runtime拥有的边界

Meta-Runtime拥有Task/Action/Invocation/Fact等通用实体、Capability/Composition/Authority/Artifact协议、Harness安装与卸载use case、local RPC/SDK、Backend Port及conformance fixtures。它不拥有任何具体的Model选择、Loop、Context policy、tool catalog、Evaluation policy或Evolution strategy。

## 40.2 外部Seed项目拥有的边界

外部Seed项目拥有Minimal Loop、Minimal Context、Model Provider adapter、tool dispatch policy、默认Composition、Seed-specific Grant模板、Fake Model场景以及其自身E2E。它输出签名/内容寻址AMPAK和Composition manifest，通过Meta-Runtime公共API安装；不得要求Runtime wheel增加Seed dependency或private hook。

## 40.3 Contract兼容

外部Harness manifest必须声明`public_api_range`、`harness_contract_range`、`capability_contract_range`、`artifact_format`、`required_backend_features[]`和`package_artifact_id`。Runtime在发布任何Artifact或创建Grant前完成纯兼容校验；不兼容返回`CONTRACT_INCOMPATIBLE`且无副作用。兼容范围只允许41.42定义的comparator conjunction。

## 40.4 独立生命周期保证

- Runtime在未安装任何Harness时可以init、start、upgrade、backup、restore和doctor；
- 安装、升级、停用或删除Seed不能升级Runtime wheel、修改DB schema或替换Root；
- Runtime升级通过当前与前一个Harness Contract major的consumer fixtures，Seed升级通过其声明范围内Runtime release matrix；
- 第二个Harness与Seed使用完全相同的install/activate/deactivate/uninstall路径；
- 外部项目不可用、构建失败或发布延迟不得阻塞Meta-Runtime release。

---

# 41. 产品落地实现规格

本章将前述 ontology 与架构约束收敛为首个可编码、可测试、可部署的实现基线。除标记为 `Optional` 或 `Deferred` 的项目外，本章内容均属于 v0.1 MVP 的规范性要求。

规范词含义：

- **MUST**：缺失即不满足 v0.1 的正确性或安全边界；
- **SHOULD**：默认必须实现，只有记录 ADR 后才能偏离；
- **MAY**：兼容扩展点，不构成首版交付阻塞；
- **Deferred**：保留 schema/API 位置，但不在 v0.1 中实现完整策略。

## 41.0 v0.1 已决策实现基线

以下事项在 v0.1 中不再作为开放问题，变更必须通过 ADR：

| 决策 | v0.1 结论 |
|---|---|
| 持久化模型 | `Transactional State Store + Append-only Audit/Causal Log`，不采用完整 Event Sourcing |
| Composition 指针 | 分离 `desired_revision`、`serving_revision`、`realized_revision` |
| 外部执行一致性 | transactional outbox + Backend 持久幂等 + reconciliation；不宣称通用 exactly-once |
| 产品进程模型 | runtime daemon 是唯一 Meta Store writer 与 Reconciler leader；embedded 仅用于测试/开发 |
| Capability 信任 | `in_process` 仅允许显式受信代码；第三方/Candidate 默认隔离进程 |
| Portable 安全 | required 强安全语义缺失时拒绝，不允许用 warning 或 emulation 静默代替 |
| API 边界 | 外部Harness只使用versioned public SDK/local RPC；Domain不暴露repository、protobuf generated class或provider-native object |
| 项目边界 | Runtime不依赖任何Seed distribution/source/path/release；测试仅使用不可发布到产品Realm的Conformance Harness |
| 扩展方式 | 小型 Port + composition + handler registry，避免宽接口和深继承树 |

这些决策维护 M-03、M-04、M-05、M-06，并直接约束第 41.3～41.16 节的实现。

## 41.1 v0.1 MVP 产品切片

### 41.1.1 首版必须跑通的纵向链路

v0.1 不以“实现所有 Meta-Evolution 概念”为完成标志，而以如下单机闭环为交付边界：

```text
启动 Meta-Runtime
  → 初始化/恢复 Realm 与 Epoch
  → 在无Harness状态达到core_ready
  → 通过公共API安装测试专用Conformance Harness Artifact
  → 提交并激活任意兼容Composition
  → 接收通用Task
  → 构造测试Context Projection
  → 执行Conformance Capability Invocation
  → 记录 Action、Fact、Invocation 与 Evidence
  → 通过 why/lineage 查询解释一次行为
  → 构造 Candidate 并在隔离执行上下文中评估
  → CAS Promotion 或保持原 Composition
  → 进程重启后从 committed boundary 恢复
```

同一套测试专用Conformance Harness至少在以下两种 Backend 上通过契约测试；它只存在于`tests/fixtures`，不得进入wheel、init builtin registry或产品release manifest：

1. `PortableExecutionBackend`：开发机默认路径，必须可独立运行；
2. `InMemoryExecutionBackend`：确定性单元测试路径。

`AgentOSKernelBackend` 在 v0.1 中 MUST 完成 ABI、feature negotiation、错误映射与 contract test；若 Rust AgentOS Kernel 尚未完成，可以使用 protocol-compatible fake server 验证，不阻塞 Portable MVP。

### 41.1.2 v0.1 必须具备

| 范围 | v0.1 交付能力 |
|---|---|
| Core | Identity、Artifact、Composition、Capability Contract、Managed State、Authority Check、RuntimeView |
| History | append-only Fact、Action、Invocation、基础 Causal Projection、why/lineage 查询 |
| Execution | InMemory + Portable Backend；AgentOS ABI client 与 fake contract server |
| Harness Host | Harness Contract/SDK、install/activate/deactivate/uninstall、通用Task/Invocation/Capability dispatch；不含Seed实现 |
| Scratch | IPython Adapter、受限 introspection、显式 promotion |
| Evolution | Proposal、ChangeSet、Candidate、Experiment、Evidence、Evaluation、Promotion/Rollback |
| Recovery | SQLite crash recovery、outbox replay、orphan handle reconciliation |
| Operations | CLI、structured log、health/readiness、schema migration、diagnostic bundle |

### 41.1.3 明确延期

以下能力保留模型与接口，但不应扩大 v0.1 实现面：

- 自动 Root Succession 与跨 Epoch 无人值守 cutover；
- 分布式 Fact 全序、跨节点强一致事务与跨集群调度；
- 多租户计费、公平调度和完整 GPU broker；
- 通用可视化 IDE、Marketplace 与远程控制台；
- 自动发现“最优”Evolution/Evaluation 策略；
- 对 Opaque 第三方状态做不可验证的伪恢复。

## 41.2 运行进程与组件拓扑

产品化 Portable/Managed 模式采用 daemon 作为唯一写入者；CLI、SDK 与其他 client 不得直接打开 Meta SQLite 文件：

```text
agent-meta CLI / API client
          │
          │ UDS / Windows Named Pipe
          ▼
agent-meta-runtime daemon (Python process)
  ├─ Application Services
  ├─ Domain Core
  ├─ SQLite Meta Store
  ├─ Artifact CAS
  ├─ Generic Harness Host / public SDK server
  ├─ Portable Backend
  └─ Adapter Supervisor
          │
          ├─ ipykernel worker
          ├─ tool/capability subprocess
          └─ model provider API/process
```

Managed 模式只替换 Execution Port：

```text
Application Services
        │ ExecutionBackend
        ▼
AgentOSKernelBackend client
        │ framed Protobuf + UDS/Windows Named Pipe
        ▼
agentosd → managed workers
```

daemon 独占以下职责：

```text
Meta Store writer
Fact realm sequence allocator
Outbox dispatcher ownership
Reconciler leader
Backend session ownership
Readiness state
```

Embedded runtime 只允许用于单元测试、Notebook、fake provider 和单进程开发，并必须确保同一 data directory 不存在 daemon。未来若支持高可用多实例，必须先替换 leader、sequence 与 store consistency 实现，不得直接让多个 SQLite writer 共享当前部署目录。

约束：

- Domain Core MUST 不 import `sqlite3`、`IPython`、`grpc`、provider SDK 或 OS process API；
- Application Service 负责 transaction orchestration，不把事务边界下放给 Adapter；
- Adapter 不得直接更新 Composition refs 或 Authority Graph；
- 所有外部执行都先形成 `Action + EffectIntent`，再调用 Execution Port；
- CLI 与未来 HTTP/gRPC API 复用同一 Application Service，不复制业务逻辑。

## 41.3 代码分层与依赖规则

v0.1 实现必须采用 Ports and Adapters + Domain Model：

| 层 | 职责 | 可依赖 | 禁止依赖 |
|---|---|---|---|
| `domain` | entity、value object、invariant、纯状态转换 | 标准库、schema value types | DB、网络、IPython、Cordis、provider SDK |
| `application` | use case、Unit of Work、权限检查、事务与 outbox 编排 | domain、ports | 具体 adapter |
| `ports` | Store、Backend、Clock、IdGenerator、Model、Task、Serializer 协议 | domain DTO | 具体实现 |
| `adapters` | SQLite、CAS filesystem、IPython、Cordis、AgentOS client | ports、外部库 | 反向定义 domain 语义；内置具体Harness/LLM policy |
| `interfaces` | CLI、local API、diagnostics | application | 直接访问 DB/adapter 内部状态 |
| `sdk` | 外部Harness使用的typed client、schema与contract helpers | public protocols/DTO | server private module、repository/UoW、credential implementation |

CI MUST 通过 import-linter 加 41.50 定义的 AST rule 检查依赖方向。跨层输入输出使用 frozen DTO；不得把 SQL row、protobuf generated class 或 Cordis object 暴露为公共 domain object。

### 41.3.1 Aggregate 边界

首版明确以下一致性边界，避免 `UnitOfWork` 退化为可任意修改全部表的“超级事务对象”：

| Aggregate | Root | 内部维护的 invariant |
|---|---|---|
| Realm | `Realm` | meta revision、desired/serving/realized refs |
| Composition | `CompositionRevision` | slot、wiring、contract、state/authority binding |
| Capability Instance | `CapabilityInstance` | lifecycle 与 execution binding incarnation |
| Harness Installation | `HarnessInstallation` | immutable package identity、contract fingerprint、lifecycle/history |
| Managed State | `ManagedState` | revision chain、schema、migration |
| Authority | `AuthorityGrant` | attenuation、scope、expiry、revocation |
| Task Execution | `TaskRecord` | child Action/Invocation/EffectIntent、budget reservation/settlement、terminal state |
| Experiment | `ExperimentRecord` | frozen candidate/baseline/world/criteria、Evidence 与 Evaluation reference |

每个本地事务 MUST 声明且只改变一个 primary Aggregate consistency group 的可变 current state；Task Execution group包含 Task及其 child Action/Invocation/EffectIntent/budget rows。允许同时插入该命令生成的不可变 child/revision，以及 command/meta revision/Fact/outbox/index companion rows。例如 Composition commit 的 primary 是 Realm refs，新 CompositionRevision 是不可变 revision；Task accept/settle 的 primary 是 Task Execution。需要改变两个独立业务 Aggregate current ref 的 use case必须拆成可恢复步骤并以 Fact/Outbox编排，不得用“大事务方便”绕过边界。非 Task control Action是所属 Realm/State/Authority/Experiment transition 的 audit child，不是独立 current Aggregate。领域规则放入 Aggregate 方法，例如 `grant.delegate()`、`task.finish_action()`、`experiment.freeze()`，不得只用 DTO + 巨大 Application Service 拼接规则。

### 41.3.2 公共 façade 而非 Service Locator

`MetaRuntime` 是 client façade，不得成为 Capability 可任意取用所有高权限服务的 Service Locator。外部Harness通过`agent_meta_runtime.sdk`或local RPC取得任务执行所需的受限 façade：

```text
TaskRuntime
ContextRuntime
InvocationRuntime
CapabilityRuntime
ReflectionRuntime
```

其中不暴露 repository、raw transaction、authority grant签发权、force activation或Root Succession。外部Harness只能提交公开Command/DTO；Runtime按Capability Contract和Handler Registry路由，不理解其Loop内部policy。

## 41.4 标识、时间与公共 Envelope

### 41.4.1 ID 生成

首版统一使用可排序 UUIDv7；URI 只是外部表示：

```text
artifact://sha256/<hex>         内容寻址，例外使用 SHA-256
blob://sha256/<hex>             实际 plaintext/encrypted storage blob
realm://<stable-name>           Realm semantic name
epoch://<uuidv7>
principal://<kind>/<uuidv7>
grant://<uuidv7>
composition://<uuidv7>
capability://<stable-name>
harness://<uuidv7>
instance://<uuidv7>
state://<uuidv7>
state-revision://<uuidv7>
fact://<uuidv7>
task://<uuidv7>
action://<uuidv7>
invocation://<uuidv7>
transaction://<uuidv7>
effect-intent://<uuidv7>
context://projection/<uuidv7>
proposal://<uuidv7>
change-set://<uuidv7>
candidate://<uuidv7>
world://<uuidv7>
experiment://<uuidv7>
evidence://<uuidv7>
evaluation://<uuidv7>
operation://<uuidv7>
scratch-session://<uuidv7>
workspace://<uuidv7>
```

`CapabilityId` 是稳定语义名；同名 capability 的不同实现由 `ArtifactId` 区分。`realm/capability` stable-name 使用 41.34.1 regex；`principal kind` 仅 `operator-root|agent|capability|service|peer`。SHA-256 hex固定 lowercase 64 chars；UUIDv7 canonical lowercase `8-4-4-4-12`，version nibble 7且variant RFC 4122。所有 ID MUST 在进入持久层前校验完整字符串/长度，不做 URL decode、Unicode case-fold或尾斜杠容忍，比较区分大小写，不允许将 display name 当 ID。

### 41.4.2 时间、顺序与幂等

- 外部显示时间使用 UTC RFC 3339，内部保存 Unix microseconds；
- 因果顺序依赖每个 `LogicalRealm` 的单调 `seq`，不得依赖 wall clock 排序；
- 写 API MUST 接受 `command_id` 作为幂等键；
- 相同 `command_id + authorization_hash` 返回首次结果；相同 `command_id` 配不同 realm/actor/grant/payload 返回 `IDEMPOTENCY_CONFLICT`；
- Backend request 使用稳定 `request_id`，重试不得创建重复 workload。

Backend 的 `request_id` 去重必须持久化，至少保留到 Meta-Runtime 明确确认 terminal result 或超过声明的 retention window；仅在 Backend 进程内使用临时缓存不满足幂等契约。

### 41.4.3 公共命令与事实 Envelope

```python
@dataclass(frozen=True)
class CommandEnvelope:
    command_id: str
    realm_id: str
    actor_id: str
    authority_grant_id: str | None
    expected_meta_revision: int | None
    causal_parent_action_id: str | None
    payload_type: str
    payload_schema_version: int
    payload: Mapping[str, JsonValue]
    auth_nonce: str | None
    auth_issued_at_us: int | None
    auth_signature: bytes | None

@dataclass(frozen=True)
class FactEnvelope:
    fact_id: str
    realm_id: str
    seq: int
    occurred_at_us: int
    recorded_at_us: int
    actor_id: str
    action_id: str | None
    transaction_id: str | None
    entity_type: str
    entity_id: str
    event_type: str
    schema_version: int
    payload: Mapping[str, JsonValue]
    payload_hash: str
    prev_fact_hash: str
    fact_hash: str
```

`payload` MUST 是可验证 JSON value；大型内容、prompt、response、trace 与二进制对象存 Artifact Store，只在 Fact 中保存 hash、size、media type 与受权限保护的引用。

## 41.5 核心领域对象的最小字段

| 对象 | 必填字段 | 关键 invariant |
|---|---|---|
| `ArtifactManifest` | id、kind、media_type、size、created_by、created_at、schema_version、parents | `id == sha256(canonical_content_bytes)` |
| `CapabilityDescriptor` | capability_id、artifact_id、contract_version、provides、requires、state_schema、placement | provides/requires 可解析且无重复 operation |
| `CompositionRevision` | composition_id、realm_id、revision、parent_id、slots、wiring、state_bindings、authority_bindings | committed 后不可变；wiring 类型兼容 |
| `CompositionRefs` | realm_id、desired_revision、serving_revision、realized_revision | 三个指针分别 CAS；任务只读取 serving |
| `ManagedStateRevision` | state_revision_id、state_id、owner、schema_id、parent_revision、artifact_id | 单父版本；写入前 schema validation |
| `AuthorityGrant` | grant_id、issuer、subject、permissions、scope、constraints、delegable、status | delegation 权限不得超过 issuer |
| `TaskRecord` | task_id、realm_id、actor_id、input_artifact_id、serving_composition_id、capability_surface_revision、budget、status、root_action_id | 接纳时冻结 serving Composition；terminal 后不可回到运行态 |
| `ActionRecord` | action_id、actor、intent、composition_id、grant_id、causal_parent、status | terminal 后不可回到 running |
| `InvocationRecord` | invocation_id、action_id、kind、target、input_artifact、context_projection_id、backend_ref、status | terminal output/error 二选一 |
| `ExperimentRecord` | experiment_id、candidate_id、baseline_id、world_id、criteria_artifact、budget、status | criteria 在开始后冻结 |
| `EvaluationRecord` | evaluation_id、experiment_id、evaluator_artifact、evidence_ids、result_artifact、decision | 不修改 Evidence |

Domain object 的枚举与状态转换必须集中定义；数据库 `CHECK` constraint 是第二道防线，不作为唯一业务规则实现。

## 41.6 SQLite Meta Store 物理模型

首版使用 WAL 模式与单 writer/multiple readers。每个业务 transaction 在一个 SQLite transaction 中同时提交 domain row、Fact 与 outbox，避免“状态已变但事件丢失”。

最小表集合：

| 表 | 主键/唯一键 | 用途 |
|---|---|---|
| `meta_revisions` | `(realm_id, revision)` | 每次 committed meta mutation 的全局快照边界 |
| `realms` / `epochs` / `principals` | 对应 ID | Realm sequence/revision、Epoch roots 与 Principal public identity |
| `transactions` | `transaction_id` | committed command 与 primary Aggregate/meta revision 的关联 |
| `commands` | `command_id`、`payload_hash` | 幂等响应与冲突检测 |
| `artifacts` | `artifact_id` | Artifact manifest；字节在 CAS |
| `artifact_blobs` / `artifact_encryption` | `blob_id` / `(artifact_id, realm_id, encryption_revision)` | plaintext/encrypted storage identity 与 Realm-scoped envelope metadata |
| `capabilities` | `(capability_id, descriptor_revision)` | Capability descriptor 历史 |
| `capability_instances` / `capability_surfaces` | `instance_id` / `(realm_id, surface_revision)` | lifecycle/binding 与模型可见 operation surface |
| `compositions` | `composition_id`、`(realm_id, revision)` | 不可变 Composition revisions |
| `harness_installations` / `harness_installation_history` | `harness_id` / `(harness_id, meta_revision)` | 外部Harness package identity、生命周期与历史 |
| `composition_refs` | `realm_id` | desired/serving/realized ref 与各自 CAS revision |
| `composition_ref_history` / `state_ref_history` | `(entity, meta_revision)` | historical RuntimeView 的 immutable current-ref boundary |
| `managed_states` / `state_revisions` | `state_id` / `state_revision_id` | State 当前 CAS ref 与 revision DAG 的 v0.1 单父子集 |
| `authority_grants` / `authority_grant_history` | `grant_id` / `(grant_id, meta_revision)` | immutable grant definition、current status 与历史授权边界 |
| `tasks` | `task_id` | Task 生命周期、冻结的 Composition/capability surface、budget 与 terminal result |
| `actions` | `action_id` | semantic action lifecycle |
| `effect_intents` | `effect_intent_id` | effect reservation、Backend request 与 terminal/unknown 状态 |
| `invocations` | `invocation_id` | model/tool/capability/backend invocation |
| `facts` | `fact_id`、`(realm_id, seq)` | append-only canonical ledger |
| `causal_edges` | `(realm_id, from_id, edge_type, to_id)` | 可重建 projection/cache |
| `context_projections` | `projection_id` | 上下文来源与 budget；正文保存为 Artifact |
| `scratch_sessions` / `scratch_bindings` | session/binding generation | Scratch kernel lifecycle 与 non-owning observed binding metadata |
| `worlds` / `evidence` | `world_id` / `evidence_id` | 冻结 Execution World 与不可变实验/行为证据 |
| `proposals` / `candidates` | 对应 ID | Evolution lineage |
| `experiments` / `evaluations` | 对应 ID | 实验与评价记录 |
| `execution_bindings` | `(backend_id, semantic_id, incarnation)` | semantic ID 到临时 handle 的映射 |
| `outbox` | `outbox_id`、`dedupe_key` | commit 后异步执行/发布 |
| `operations` | `operation_id` | backup/GC/rebuild 等异步 operator use case lifecycle |
| `workspaces` | `workspace_id` | Task/Scratch/Candidate 的受控 local root、quota 与 cleanup lifecycle |
| `checkpoints` | `(realm_id, projection, seq)` | projector/reconciler 恢复游标 |
| `schema_migrations` | `version` | DB migration 记录与 checksum |

关键索引：

```sql
CREATE UNIQUE INDEX uq_fact_seq ON facts(realm_id, seq);
CREATE INDEX ix_fact_entity ON facts(realm_id, entity_type, entity_id, seq);
CREATE INDEX ix_fact_action ON facts(action_id, seq);
CREATE INDEX ix_invocation_action ON invocations(action_id, started_at_us);
CREATE INDEX ix_edge_to ON causal_edges(realm_id, to_id, edge_type);
CREATE UNIQUE INDEX uq_outbox_dedupe ON outbox(dedupe_key);
```

持久化规则：

- v0.1 的权威模型是 `Transactional State Store + Append-only Audit/Causal Log`，不是完整 Event Sourcing；
- Artifact manifest/bytes、Composition Revision、Managed State Revision、Authority Grant 与 Realm Composition refs 是当前状态的 canonical truth；
- Fact Ledger 是发生过什么、由谁授权及因果关系的 canonical truth，但不要求单独重建全部业务状态；
- RuntimeView、Causal Graph、搜索索引与摘要是 projection，可由 canonical tables + Fact Ledger 重建；

- `facts` 禁止 UPDATE/DELETE；开发测试清库除外；
- 修正使用 `fact_corrected` 新事实，并引用被修正 `fact_id`；
- `causal_edges`、搜索索引与摘要属于 projection，可由 Fact + canonical tables 重建；
- `composition_refs` 与 `meta_revisions` 必须在同一事务更新；
- JSON 列写入前必须通过 versioned schema validator；
- v0.1 不跨 SQLite 与 Backend 建立分布式事务，使用 transactional outbox + reconciliation。

## 41.7 Artifact CAS 实现

默认目录布局：

```text
data/
├── meta.db
├── artifacts/
│   └── sha256/ab/cd/<full-hash>
├── staging/
├── locks/
└── diagnostics/
```

写入算法：

1. 将输入流写入同一文件系统的 `staging/<uuid>.tmp`，同时计算 SHA-256 与 size；
2. 执行 size/media-type/policy 校验；
3. `fsync(file)`；
4. 普通 Artifact 以 plaintext content hash 计算最终路径；Restricted Raw 按 41.30 加密后以 ciphertext BlobId 计算 encrypted 路径；
5. 若目标已存在，逐项校验 size/hash 后复用；
6. 否则使用 atomic rename 发布，并 `fsync(parent directory)`；
7. 在 SQLite transaction 中登记 `ArtifactManifest` 与引用关系；
8. 定期垃圾回收未登记且超过 TTL 的 staging 文件。

Artifact 每次从 CAS 打开时 MUST 校验 path、size 和完整 SHA-256；用于 Root、Composition、Migration、Evaluator 的 Artifact 在每次激活前再次完整校验。v0.1 不使用“抽样校验”优化；未来只有在具备受信 filesystem integrity proof 与 ADR 时才能引入缓存。GC 只删除“未被 committed object、archive retention、legal hold 或 active experiment 引用”的内容，并先生成可审计 GC plan。

Capability Code Artifact 必须是可复现 Package，而不是单个源文件 hash。v0.1 Package manifest遵守41.29的精确编码，并包含下列语义字段：

```text
source archive / wheel
dependency lock
entrypoint
Capability Contract
state schema + migrations
Python/runtime/platform constraints
build provenance
```

同一 `ArtifactId` 不得在解析依赖时隐式使用不同版本；无法满足 runtime constraint 时返回 compatibility failure，而不是现场更新依赖。

## 41.8 Unit of Work、CAS 与事务提交

所有写 use case 使用统一 `UnitOfWork`：

```python
class UnitOfWork(Protocol):
    artifacts: ArtifactRepository
    compositions: CompositionRepository
    states: StateRepository
    authority: AuthorityRepository
    facts: FactRepository
    outbox: OutboxRepository

    async def commit(self) -> CommitResult: ...
    async def rollback(self) -> None: ...
```

以激活 Composition 为例：

```text
1. validate command_id / schema
2. load snapshot(expected_meta_revision)
3. authority.check(actor, composition.activate, scope)
4. validate artifacts/contracts/wiring/state migrations
5. insert immutable composition
6. CAS composition_refs.desired_revision
7. append action + composition_committed facts
8. enqueue reconcile_requested in outbox
9. increment meta_revision
10. COMMIT
11. dispatcher delivers outbox item to Reconciler
```

步骤 1–10 任一失败不得出现部分 committed semantic state。步骤 11 可失败并重试；Reconciler 必须幂等。Backend 调用不得在持有 SQLite write transaction 时执行，以避免外部超时阻塞全局 writer。

## 41.9 核心状态机

### 41.9.1 Capability Instance

```text
DEFINED → VALIDATED → INSTANTIATING → INACTIVE → ACTIVE → DRAINING → RELEASED
                       └────────────→ FAILED
ACTIVE → DEGRADED → ACTIVE | DRAINING
```

只有 `INACTIVE` 可进入 `ACTIVE`；replace 时必须先激活新实例并更新 binding，再 drain 旧实例。强制终止产生 `release_forced` Fact，不能伪装为正常 release。

### 41.9.2 Task

```text
ACCEPTED → RUNNING → SUCCEEDED
                 ├→ FAILED
                 ├→ FAILED_RECOVERY
                 ├→ TIMED_OUT
                 └→ CANCELLED
```

Task 在 `ACCEPTED` 时必须原子冻结：

```text
serving_composition_id
serving_revision
capability_surface_revision
authority_grant_id
budget
input_artifact_id
```

一个 Task 拥有一个 `root_action_id`，turn、model、tool、capability 与 Backend 操作均通过 Action/Invocation 子树关联。Task terminal 状态不可修改；超时或取消后到达的结果仅形成 `late_completion_observed` Fact。Task 只有在 terminal Fact 与 terminal row 同一事务 committed 后才可向 client 返回完成。重启时，非 terminal Task 必须按其冻结的 Composition 恢复、取消或显式标记 `FAILED_RECOVERY`，不得自动漂移到新的 serving revision。

### 41.9.3 Invocation

```text
CREATED → DISPATCHED → RUNNING → SUCCEEDED
                         ├────→ FAILED
                         ├────→ TIMED_OUT
                         └────→ CANCELLED
```

Terminal status 不可修改；迟到的 Backend completion 保存为 `late_completion_observed` Fact，不反转已经对外可见的 terminal result。

### 41.9.4 Experiment 与 Promotion

```text
DRAFT → VALIDATED → STAGED → RUNNING → COLLECTING → EVALUATED
           │           │        │                        ├→ ACCEPTED → PROMOTING → PROMOTED
           └→ INVALID  └→ FAILED└→ ABORTED               └→ REJECTED → ARCHIVED
```

`criteria_artifact`、baseline、candidate、World 与 budget 在 `RUNNING` 前冻结。Promotion 是新的 Meta Transaction，不是 Experiment transaction 的尾部副作用。

Promotion Gate 必须在独立事务前验证：

```text
Evaluation accepted
+ evaluator/criteria artifact authorized and frozen
+ required Evidence complete
+ no unresolved EXTERNAL_EFFECT_UNKNOWN
+ candidate Artifact integrity valid
+ state migration validated
+ Backend requirements satisfied
+ promotion Authority valid
+ expected serving revision still matches baseline
```

任一条件失败只能保持/归档 Candidate，不得部分更新 serving Composition。

### 41.9.5 Composition Reconciliation

```text
PENDING → APPLYING → READY
             ├────→ DEGRADED
             └────→ FAILED → RETRYING | ROLLED_BACK
```

状态转换必须遵循三指针规则：

```text
PENDING     desired=N+1, serving=N,   realized=N
APPLYING    desired=N+1, serving=N,   realized=N
READY       desired=N+1, serving=N+1, realized=N+1
FAILED      desired=N+1, serving=N,   realized=N
ROLLBACK    desired=N,   serving=N,   realized=N
```

只有新实例全部通过 validation、state migration、health check 与 required feature 检查后，才允许 CAS 更新 `serving_revision`。API 与 UI 必须同时返回三个 revision。

任务接纳策略：

| Reconciliation 状态 | 新 Task 行为 |
|---|---|
| `READY` | 使用当前 serving revision |
| `PENDING/APPLYING` | 继续使用旧 serving revision |
| `DEGRADED` | 根据 Capability `criticality/degradation_policy` 决定拒绝、忽略或 fallback |
| `FAILED` | 保持旧 serving revision，不自动切换 |
| `UNKNOWN` | 阻止依赖未知实例或未知外部副作用的任务 |

## 41.10 Application API 与 CLI

### 41.10.1 Python API

首版公共入口保持粗粒度 use case，不暴露 repository：

```python
class MetaRuntime:
    async def start(self, options: StartOptions) -> RuntimeInfo: ...
    async def stop(self, mode: StopMode) -> None: ...
    async def get_view(self, query: ViewQuery) -> RuntimeView: ...
    async def submit_task(self, command: SubmitTask) -> TaskHandle: ...
    async def wait_task(self, task_id: str, timeout_s: float | None) -> TaskResult: ...
    async def cancel_task(self, command: CancelTask) -> ActionResult: ...
    async def put_artifact(self, command: PutArtifact) -> ArtifactManifest: ...
    async def register_capability(self, command: RegisterCapability) -> CapabilityDescriptor: ...
    async def commit_composition(self, command: CommitComposition) -> CommitResult: ...
    async def create_state(self, command: CreateState) -> ManagedStateRevision: ...
    async def write_state(self, command: WriteState) -> ManagedStateRevision: ...
    async def grant_authority(self, command: GrantAuthority) -> AuthorityGrant: ...
    async def delegate_authority(self, command: DelegateAuthority) -> AuthorityGrant: ...
    async def revoke_authority(self, command: RevokeAuthority) -> AuthorityGrant: ...
    async def propose_change(self, command: ProposeChange) -> ProposalResult: ...
    async def create_candidate(self, command: CreateCandidate) -> CandidateResult: ...
    async def run_experiment(self, command: RunExperiment) -> ExperimentHandle: ...
    async def promote_candidate(self, command: PromoteCandidate) -> CommitResult: ...
    async def rollback_composition(self, command: RollbackComposition) -> CommitResult: ...
    async def why(self, query: WhyQuery) -> CausalExplanation: ...
```

每个 mutating method MUST 接收 `CommandEnvelope` 信息并通过统一回执返回 `command_id`、`action_id`、`meta_revision`。上面为便于阅读保留具体业务返回类型；规范签名等价于 `MutationResult[T]`：

```python
@dataclass(frozen=True)
class MutationReceipt:
    command_id: str
    action_id: str
    transaction_id: str
    meta_revision: int
    committed_at_us: int

@dataclass(frozen=True)
class MutationResult(Generic[T]):
    receipt: MutationReceipt
    resource: T
```

上述所有 mutating method 均返回这一 envelope；幂等重放必须返回首次 committed 的相同 receipt 与 resource。异步操作的 resource 可以是 Handle，但 Handle 的创建事实必须已经 committed。异常统一映射为稳定 error code，Python exception message 不作为协议。

### 41.10.2 CLI

```text
agent-meta init
agent-meta doctor
agent-meta run --task <file-or-text>
agent-meta task inspect <task-id>
agent-meta reflect view [--revision N]
agent-meta graph why <entity-id>
agent-meta artifact put <path>
agent-meta capability register <descriptor>
agent-meta harness validate|install|list|inspect|activate|deactivate|uninstall ...
agent-meta composition validate <file>
agent-meta composition apply <file> --expected-revision N
agent-meta state create|inspect|write ...
agent-meta authority inspect|grant|delegate|revoke ...
agent-meta scratch create|execute|bindings|inspect|export|release ...
agent-meta proposal create <file>
agent-meta candidate create <change-set>
agent-meta candidate run <candidate-id>
agent-meta candidate promote <candidate-id> --expected-revision N
agent-meta composition rollback <parent-id> --expected-revision N
agent-meta backup create <absolute-dir>
agent-meta gc plan|apply ...
agent-meta backend reconcile [--dry-run]
agent-meta restore <backup-dir> --target <empty-data-dir>       # offline
agent-meta recover-root --recovery-code-stdin                  # offline
agent-meta diagnostics collect
```

CLI 默认输出 human-readable table；`--output json` 提供稳定 machine-readable schema。所有破坏性/高风险操作支持 `--dry-run`，非交互模式不得弹出隐式确认。

### 41.10.3 Local service API

产品模式 MUST 启用 local-only daemon API：Unix Domain Socket（Windows 使用 Named Pipe）+ versioned Protobuf RPC；JSON 只作为 CLI/diagnostics 的规范映射输出。CLI/SDK 不得直接写 Meta Store。默认不得监听公网地址。远程 API、认证代理与 Web UI 另立 deployment profile，不进入 Core。Embedded API 仅用于测试、Notebook 与单进程开发。Windows transport fallback 受 41.26 约束。

## 41.11 External Harness Loop Conformance Algorithm

Minimal Loop必须是外部项目中的可替换Capability。以下算法定义`harness-contract/v1` conformance profile与test vectors；Meta-Runtime只负责host enforcement和test-only fixture，不在产品source提供默认Loop：

```python
async def run_turn(task: TaskEnvelope, runtime: TaskRuntime) -> TurnResult:
    view = await runtime.get_view(ViewQuery.latest(task.realm_id))
    action = await runtime.actions.begin(
        actor=task.actor_id,
        intent="task.turn",
        composition_id=view.serving_composition_id,
        causal_parent=task.causal_parent_action_id,
    )
    try:
        projection = await runtime.context.project(task, view, action)
        invocation = await runtime.models.invoke(
            action=action,
            projection=projection,
            tool_surface_revision=view.capability_surface_revision,
        )
        decision = await runtime.loop.interpret(invocation)

        command = runtime.decision_parser.parse(invocation)
        turn_result = await runtime.command_handlers.dispatch(command, action)

        await runtime.actions.finish(action, "SUCCEEDED")
        return turn_result
    except CancelledError:
        await runtime.actions.finish(action, "CANCELLED")
        raise
    except Exception as exc:
        error = runtime.errors.sanitize(exc)
        await runtime.actions.finish(action, "FAILED", error=error)
        raise
```

实现必须补充：

- turn/step/max wall time/max model calls/max effect budget；
- cancellation token 从 Task 传播到 Model、Capability 与 Backend；
- 每一步先校验 authority 与 budget，再产生外部 effect；
- model response 原文仅在有效 Raw Retention Policy 明确允许时作为加密的 Restricted Raw Artifact 保存；默认不持久化原文，解析/脱敏结果单独记录；
- tool 参数 schema validation 失败不得调用工具；
- 重试由 versioned Retry Policy 决定，并记录每次 attempt；
- task completion 在 terminal Fact committed 后才对 client 可见。

## 41.12 Context Projection 与 Invocation 落地格式

Context Builder 分两阶段：

```text
Select sources → Normalize/Redact → Rank → Budget → Render
                                      │
                                      └→ Projection Manifest
```

`ProjectionManifest` v1 必须且只能使用下列 required 字段；允许新增以 `x_` 开头的非语义扩展字段，扩展字段不参与 projection identity：

```yaml
projection_id: context://projection/<uuid>
policy_artifact_id: artifact://sha256/...
composition_id: composition://...
meta_revision: 1842
source_refs:
  - kind: fact_range
    ref: realm://main#17001-18300
    content_hash: ...
sections:
  - section_id: runtime-summary
    renderer: artifact://sha256/...
    output_artifact_id: artifact://sha256/...
    token_count: 812
redaction_policy_artifact_id: artifact://sha256/...
tokenizer_id: tokenizer://provider/model/revision
total_tokens: 6412
budget_tokens: 8192
```

`ModelInvocation` 记录 provider、model、parameters、projection、tool schema Artifact、request/response Artifact、usage、attempt、latency、finish reason 与 sanitized error。Provider request id 可用于诊断，但不得作为 `InvocationId`。

Prompt、response 与 tool result 分层保存：

```text
Restricted Raw Artifact
    原始内容；加密；严格 Authority；独立 retention policy
          │ derived_from
          ▼
Redacted Derived Artifact
    供普通 reflection、diagnostics 与 evaluation 使用
```

部署可以通过 policy 关闭 Raw Artifact 持久化；此时必须记录 `raw_content_not_retained`，不得声称可进行原文 replay。Raw 与 Redacted 分别计算 content hash，Evaluator 是否可读取 Raw 由明确 Authority 决定。

## 41.13 Adapter SPI

### 41.13.1 Capability Adapter Ports

```python
class CapabilityLifecyclePort(Protocol):
    async def validate(self, descriptor: CapabilityDescriptor) -> ValidationReport: ...
    async def instantiate(self, request: InstantiateRequest) -> InstanceHandle: ...
    async def drain(self, instance: InstanceHandle, deadline: Deadline) -> None: ...
    async def release(self, instance: InstanceHandle) -> ReleaseReport: ...

class CapabilityInvocationPort(Protocol):
    async def invoke(self, request: CapabilityInvocation) -> InvocationResult: ...

class CapabilityReflectionPort(Protocol):
    async def inspect(self, instance: InstanceHandle, budget: InspectBudget) -> SafeSnapshot: ...
```

同一 Adapter 可以实现多个 Port；调用方只依赖实际需要的最小接口。

### 41.13.2 Model Provider

```python
class ModelProvider(Protocol):
    async def capabilities(self) -> ModelProviderProfile: ...
    async def count_tokens(self, request: ModelRequest) -> TokenCount: ...
    async def invoke(self, request: ModelRequest, cancel: CancelToken) -> ModelResponse: ...
```

Provider Adapter MUST 规范化 usage、finish reason、rate limit、retry-after、stream cancellation 与 tool call；不得将 provider-specific response 直接传播到外部 Harness Loop。

### 41.13.3 Scratch Adapter

Scratch Adapter 必须实现 `execute`、`bindings`、`safe_inspect`、`observe`、`release` 与 `export_candidate`。IPython 的 `_oh` output cache、display hook 与 history size 在启动时设上限；`safe_inspect` 使用静态属性查询和类型白名单，不调用用户定义 `__repr__`、property 或 iterator。

### 41.13.4 Execution Backend Ports

除 37.0.3 的方法外，v0.1 Contract 增加：

```python
class BackendCapabilityPort(Protocol):
    async def negotiate(self, client: ClientHello) -> BackendSession: ...

class ExecutionSubmitPort(Protocol):
    async def submit(self, request: ExecutionRequest) -> ExecutionHandle: ...

class ExecutionControlPort(Protocol):
    async def await_result(self, handle: ExecutionHandle, deadline: Deadline) -> ExecutionResult: ...
    async def cancel(self, handle: ExecutionHandle, mode: CancelMode) -> CancelReport: ...

class ExecutionInspectPort(Protocol):
    async def inspect(self, handle: ExecutionHandle) -> ExecutionSnapshot: ...

class ExecutionReconcilePort(Protocol):
    async def reconcile(self, known: Sequence[ExecutionBinding]) -> ReconcileReport: ...

class ExecutionIdempotencyPort(Protocol):
    async def acknowledge_terminal(self, request_id: str, result_hash: str) -> AckReport: ...

class ExecutionSessionPort(Protocol):
    async def close(self) -> None: ...
```

`ExecutionBackend` 是上述 Ports 的组合类型，而不是要求每个调用方依赖一个宽接口。`StrongIsolationPort`、`CredentialBrokerPort` 等只由支持相应强语义的 Backend 实现，从类型和 feature negotiation 两个层面防止违反 LSP。

## 41.14 Backend feature negotiation 与错误模型

启动时 Meta-Runtime 提交 `ClientHello(protocol range, required features, optional features)`；Backend 返回选择的 protocol version、backend/session identity、feature states 与 limits。

Feature 状态统一为：

```text
SUPPORTED | PARTIAL | EMULATED | UNSUPPORTED
```

每个 `PARTIAL/EMULATED` 必须包含 limitation code。Composition 可声明：

```yaml
execution_requirements:
  isolated_realm: required
  hard_memory_quota: preferred
  credential_broker: forbidden_to_emulate
on_missing:
  preferred: warn
  required: reject
```

Portable profile 中以下语义默认 `forbidden_to_emulate`：

```text
credential isolation
candidate strong isolation
hard memory quota
multi-tenant filesystem isolation
Root Succession cutover
untrusted code execution
high-risk irreversible effect authorization
```

若 Composition 将其声明为 required，而 Backend 没有 `SUPPORTED` 实现，则 validation/submit 必须返回 `FEATURE_UNAVAILABLE`，不得只记录 warning 后继续执行。

每个可能创建外部 workload/effect 的 `ExecutionRequest` 必须包含：

```text
request_id
operation_kind
payload_hash
idempotency_class
reversibility
dedupe_scope
requested_retention
```

Backend 对同一 `request_id + payload_hash` 返回首次结果；同一 `request_id` 配不同 hash 返回 `IDEMPOTENCY_CONFLICT`。系统只在 Backend 遵守持久幂等契约时提供 effectively-once semantic execution，不宣称通用 exactly-once。

Backend 必须在 durable terminal result 被 Meta-Runtime 记录前保留 dedupe record。Meta-Runtime 将 terminal result、Fact 与待发送的 acknowledgement 写入同一事务；dispatcher 随后调用 `acknowledge_terminal(request_id, result_hash)`。Backend 收到确认后仍必须保留 tombstone 至其声明的 `minimum_dedupe_retention`。空间不足时必须拒绝新的可能产生 effect 的 request 并返回 `RESOURCE_EXHAUSTED`，不得提前遗忘未确认 request。重复 acknowledgement 必须幂等。

稳定错误分类：

| Error code | 是否可重试 | 含义 |
|---|---:|---|
| `INVALID_ARGUMENT` | 否 | schema/contract 不合法 |
| `AUTHORITY_DENIED` | 否 | grant 缺失、过期或 scope 不匹配 |
| `REVISION_CONFLICT` | 重新读取后 | CAS 失败 |
| `IDEMPOTENCY_CONFLICT` | 否 | 相同 command_id 对应不同请求 |
| `FEATURE_UNAVAILABLE` | 视 policy | Backend 不满足 required feature |
| `NO_SERVING_COMPOSITION` | 否 | core ready但尚无已激活Harness/serving Composition |
| `SERVING_NOT_READY` | 是 | serving transition存在但尚未安全收敛 |
| `CONTRACT_INCOMPATIBLE` | 否 | 外部Harness声明的公共Contract范围与Runtime不相交 |
| `RESOURCE_EXHAUSTED` | 是 | 临时资源不足，返回 retry hint |
| `DEADLINE_EXCEEDED` | 视 effect | deadline 到期，结果可能未知 |
| `BACKEND_UNAVAILABLE` | 是 | 连接/daemon 暂时不可用 |
| `HANDLE_EXPIRED` | reconcile 后 | execution handle 已失效 |
| `EXTERNAL_EFFECT_UNKNOWN` | 不自动 | 无法确认外部副作用是否发生 |
| `INTEGRITY_ERROR` | 否 | hash、ledger 或 invariant 不一致 |

重试策略必须依据 operation 的 idempotency 与 effect reversibility；`EXTERNAL_EFFECT_UNKNOWN` 不得自动重试不可幂等操作。

## 41.15 Reconciler 与恢复算法

Reconciler 是单独 Application Service，可同进程运行，但具有独立 checkpoint 与 leader lock。每轮执行：

```text
1. 读取 committed desired/serving/realized refs 与 meta_revision
2. 读取 execution_bindings 和 Backend capability/session
3. 调用 backend.reconcile(known bindings)
4. 构造 desired/serving/realized 与 live execution diff
5. 按 dependency DAG：create → instantiate → migrate → health check → bind
6. CAS serving_revision：old → desired
7. 对旧 serving 独占实例：drain → release
8. 写入 execution facts/bindings，并将 realized_revision 更新为 serving_revision
9. 推进 reconciler checkpoint
```

恢复分类：

| 发现 | 处理 |
|---|---|
| semantic desired 存在，live 缺失 | 以稳定 reconcile key 重建 |
| live 存在，semantic binding 缺失 | quarantine；确认无引用后回收 |
| handle expired，但 workload 仍在 | 接受 Backend 返回的 renewed handle 并创建新 binding incarnation |
| workload status unknown | 标记 `UNKNOWN`，阻止依赖其结果的 promotion |
| outbox 已提交未投递 | 按 dedupe key 重放 |
| projection checkpoint 落后 | 从下一 Fact seq 重建 |
| CAS Artifact 损坏 | `INTEGRITY_ERROR`；禁止激活并尝试从可信副本修复 |

启动阶段顺序固定为：store integrity check → schema compatibility → Artifact root check → Backend negotiation → outbox recovery → reconciliation → readiness。未达到`core_ready`时只允许只读反射、诊断与显式恢复；达到`core_ready`但未达到`serving_ready`时允许管理面与Harness lifecycle，但不接受新的普通Task。

## 41.16 Authority 与安全执行细节

每个高影响 use case 必须在两个位置校验：

1. Application Service 基于 Authority Graph 做语义授权；
2. Backend/AgentOS 基于短期 scoped execution token 做物理约束。

Token 至少绑定 actor、action、effect kind、resource ceiling、realm、expiry、nonce；只保存 token handle 与使用事实，不写入普通日志/Fact payload。

v0.1 execution token 使用 JCS payload + daemon Service Principal Ed25519 signature，不使用可变 JWT library defaults。Init 生成独立 service key存 Credential Store，Root签署其 `{service_principal_id,public_key,realm_id,epoch_id,permissions,not_after}` certificate Artifact；它绝不复用 Root private key。Token payload固定为 `{token_version:1,token_id,backend_session_id,realm_id,actor_id,action_id,effect_kind,target_scope_hash,resource_ceiling,issued_at_us,expires_at_us,nonce}`；signature preimage 为 `agent-meta-execution-token-v1\0` + JCS bytes。TTL 默认 60 秒且不得超过 Task deadline。Backend session negotiation取得 certificate chain并验证 Root public key、service certificate、signature/session/expiry/nonce；相同 token_id 仅允许相同 request_id重放。Meta Store只保存 token_id/payload hash/public key id/use Fact，不保存 serialized token。Portable同进程 Adapter仍执行相同 verifier contract。

[ADR 047](adr/047-root-certified-service-execution-tokens.md)固定证书/token的JCS envelope、Root证书
签名域与有限重放缓存。验证方独立pin Root/Realm/Epoch，并从已登记操作推导binding，不信任token自报scope。
该纯契约实现不代替实际bootstrap证书、worker装配、效果预留与持久terminal acknowledgement。

[ADR 049](adr/049-bootstrap-public-service-certificate.md)在native init的同一bootstrap事务登记实际
Root签名Service公开证书；worker只取得公开链并用独立Service签名验证，证书本身不产生effect授权。
旧开发数据缺证书时不隐式补签，未来执行profile须明确拒绝；证书更新与实际Backend装配仍按各自门禁验证。

默认安全策略：

- `in_process` 仅允许内建/签名/显式信任的 Capability；第三方与 Candidate 默认 `isolated_process`；
- Scratch 只能写入隔离 workspace，promotion 后才可成为 committed Artifact；
- Candidate 与 baseline 使用不同 workspace/realm；
- network、credential、filesystem、subprocess 权限显式声明，默认 deny；
- `OpaqueState` 必须标明 owner、external system、impact、backup/recovery policy；
- Prompt/response/tool result 按 Restricted Raw / Redacted Derived Artifact 分层；
- diagnostics bundle 默认排除 secrets、原始 prompt、模型响应与用户文件内容；
- Portable Backend 缺失 required 强安全能力时必须拒绝操作；仅 preferred 能力允许产生 warning 后降级；
- 安全策略降级必须产生高优先级 Fact 和 operator-visible warning。

## 41.17 可观测性与诊断

统一关联键：

```text
realm_id
epoch_id
meta_revision
command_id
action_id
invocation_id
transaction_id
experiment_id
backend_session_id
execution_handle
```

首版输出：

- structured JSON logs；
- OpenTelemetry traces（无 collector 时本地 no-op/export file）；
- local RPC `Runtime.GetMetrics` 返回 OpenMetrics text snapshot；v0.1 不启动 HTTP metrics server；
- `Runtime.GetInfo.live` 只表示进程/event loop可响应；
- `Runtime.GetInfo.core_ready` 表示41.51的Runtime基础gate通过；`serving_ready`表示存在可接纳Task的serving Composition；兼容字段`ready`等于`core_ready`；
- `agent-meta doctor` 检查 schema、CAS、Backend feature、已安装Capability、workspace 权限与 clock；不得要求外部Seed项目存在；
- diagnostics bundle 包含版本、配置摘要、feature profile、最近错误、checkpoint 与 redacted trace。

最低指标：task/invocation latency、success/failure/cancel、model tokens/cost、outbox lag、fact projection lag、reconcile duration/failure、active/degraded instances、CAS bytes、SQLite transaction latency/lock wait。

JSON log默认写 stderr和 `<data_dir>/diagnostics/runtime.jsonl`，单文件10 MiB、保留5个轮转文件；轮转使用 atomic rename，失败继续 stderr并增加metric，不阻止核心执行。OpenTelemetry默认 no-op；配置 `otel.export=file` 时写同目录 10 MiB×5 redacted JSONL。Metrics仅内存累计，daemon restart重置并以 `runtime_instance_id`作为snapshot字段而非label。所有字段/label受41.49 allowlist。

## 41.18 配置、启动与部署

配置优先级：CLI flag > environment > config file > defaults。启动后将去密配置规范化并计算 `config_fingerprint`，写入 `runtime_started` Fact。

```yaml
runtime:
  realm_id: realm://main
  data_dir: ./data
  log_level: INFO
store:
  url: sqlite:///./data/meta.db
  busy_timeout_ms: 5000
artifact_store:
  kind: filesystem
  root: ./data/artifacts
backend:
  kind: portable
  required_features: []
ingress:
  require_serving_composition: true
limits:
  max_turns: 32
  max_steps: 128
  max_model_calls: 64
  max_output_tokens_per_call: 4096
  max_effects: 32
  max_cost_microunits: 0
  task_timeout_s: 1800
context:
  budget_tokens: 8192
reflection:
  max_depth: 4
  max_items: 1000
  max_bytes: 1048576
  timeout_ms: 500
queue:
  max_pending_tasks: 1000
workspace:
  task_quota_bytes: 536870912
  scratch_candidate_quota_bytes: 1073741824
raw_retention:
  enabled: false
  retention_days: 7
operations:
  allowed_backup_roots: []   # empty means default sibling agent-meta-backups only
```

Secrets 只允许来自 environment secret reference、OS keychain 或 AgentOS Credential Broker；配置文件中出现 plaintext secret 时默认拒绝启动，开发模式必须显式 opt-in。

部署 profile：

| Profile | 组成 | 适用场景 |
|---|---|---|
| `dev` | 单 Python 进程 + SQLite + filesystem CAS + InMemory/Portable Backend | 开发与单测 |
| `portable` | runtime service + worker subprocess + SQLite/CAS | 单机个人 Agent |
| `managed` | runtime service + agentosd + managed workers | 生产、强隔离、多 Agent |

## 41.19 Schema 与协议演进

版本分四层管理：

```text
DB schema version
Domain payload schema version
Public API version
Execution Backend protocol version
```

规则：

- DB migration 使用 forward-only 脚本；升级前自动备份 manifest，但不静默覆盖用户数据；
- Fact payload 读取器至少支持当前与前一个 major schema；旧 Fact 不原地迁移；
- upcaster 只生成内存视图或新 projection，不篡改 canonical payload；
- 公共 API 删除字段必须跨 major version；新增字段默认 optional；
- Backend 通过 version range 协商，不以 client/server 软件版本字符串判断兼容；
- 每次 migration 在临时副本上运行 crash/fault injection 测试。

## 41.20 测试策略与质量门禁

测试金字塔：

| 层级 | 重点 | 是否阻塞合并 |
|---|---|---:|
| Domain unit | invariant、状态机、authority attenuation、pure diff | 是 |
| Store contract | SQLite repository、MVCC、Fact append、migration | 是 |
| Adapter contract | InMemory/Portable/AgentOS fake 的同一测试套件 | 是 |
| Integration | Conformance Harness host、IPython、reconciler/outbox | 是 |
| Recovery/fault | kill -9、DB busy、outbox duplicate、handle expiry、disk full | 是 |
| Security | unsafe reflection、secret leakage、scope bypass、path escape | 是 |
| E2E | core init → external package install → task → evidence → promotion → uninstall → restart | 是 |
| Performance | latency/throughput/ledger growth baseline | 发布门禁 |

必须采用 deterministic clock、ID generator、test-only Conformance Harness/Provider 与 InMemory Backend，保证核心测试不依赖真实LLM或外部Seed repository。AgentOS ABI 使用 consumer/provider contract tests；Portable Linux 与 Windows 都是 blocking CI matrix成员。

v0.1 发布性能门禁以 correctness-first 为原则：

| 指标 | v0.1 目标 |
|---|---:|
| 不含外部调用、Artifact byte IO/full hash/migration 的 metadata command p95 | ≤ 50 ms |
| RuntimeView（1 万 entity 内）p95 | ≤ 200 ms |
| Fact append sustained | ≥ 1,000 facts/s（单 realm，本地 SSD） |
| 重启恢复 10 万 facts | ≤ 30 s（有 checkpoint） |
| outbox/reconcile 最终收敛 | 正常 Backend 下 ≤ 5 s |

这些数字是工程基线，不是 ontology invariant；变更时通过 benchmark 报告与 ADR 调整。

## 41.21 v0.1 仓库布局与首个开发顺序

```text
agent-meta-runtime/
├── pyproject.toml
├── proto/
│   ├── public_api/v1/
│   └── execution_backend/v1/
├── src/agent_meta_runtime/
│   ├── domain/
│   ├── application/
│   ├── ports/
│   ├── adapters/
│   │   ├── sqlite/
│   │   ├── artifact_fs/
│   │   ├── execution_memory/
│   │   ├── execution_portable/
│   │   ├── execution_agentos/
│   │   ├── ipython/
│   │   └── model_providers/
│   ├── interfaces/
│   │   ├── cli/
│   │   └── local_api/
│   ├── sdk/
│   └── protocols/
├── migrations/
├── schemas/
├── tests/
│   ├── unit/
│   ├── contract/
│   ├── integration/
│   ├── recovery/
│   ├── e2e/
│   └── fixtures/conformance_harness/  # test-only；禁止打入wheel
└── examples/
```

按以下可持续运行的薄切片顺序开发：

```text
Slice 1  Identity + Artifact CAS + SQLite UoW
Slice 2  Fact Ledger + Action + RuntimeView
Slice 3  Capability/Composition + validation + CAS activation
Slice 4  InMemory/Portable Backend + contract suite
Slice 5  Generic Task/Invocation/Harness Host with conformance fixture
Slice 6  Invocation provenance + why/lineage
Slice 7  Reconciler + outbox + crash recovery
Slice 8  IPython Scratch + safe inspect + promotion
Slice 9  Candidate/Experiment/Evaluation/Promotion
Slice 10 AgentOS client + fake server + backend swap E2E
```

每个 Slice 必须同时交付 schema、implementation、migration（若需要）、tests、CLI demo 与最小文档，避免先铺设大量无法端到端运行的抽象层。

## 41.22 v0.1 Definition of Done

v0.1 只有同时满足以下条件才可视为可产品化基线：

- 新用户可在普通 Linux/Windows 上只安装Runtime wheel，并在无Harness时完成init/start/doctor/backup；
- Runtime E2E只使用仓库内test-only Conformance Harness，不检出、安装或调用外部Seed repository；
- 任意符合Contract的外部Harness AMPAK可经公共API安装、激活、停用和卸载；无serving Composition时Task.Submit稳定返回`NO_SERVING_COMPOSITION`；
- 一次任务的 model context、tool surface、actions、facts、backend execution 与结果可追溯；
- Composition/State 并发修改经过 CAS，无 silent lost update；
- 任意步骤 kill -9 后重启，不产生重复不可幂等 effect，或明确报告 `EXTERNAL_EFFECT_UNKNOWN`；
- Artifact tamper、unsafe reflection、authority bypass 与 secret-in-log 测试通过；
- Candidate 或 desired reconciliation 失败不影响 current serving Composition；
- promotion 后可 rollback 到父 Composition；
- desired/serving/realized revision 在切换与失败场景中保持可解释；
- runtime daemon 是产品模式唯一 writer、Reconciler leader 与 Backend session owner；
- 第三方/Candidate Capability 不得静默以 `in_process` 运行；
- Portable Backend 缺失 required 强安全能力时拒绝执行；
- Portable 与 AgentOS fake backend 通过同一 contract suite；
- DB、Fact payload、public API、Backend protocol 都有显式版本；
- `doctor`、readiness、diagnostics 与升级/备份说明可用；
- 第41.33/41.58追踪矩阵列入Runtime Required的Acceptance Criteria（AC-M01～M09B、M12～M16、M18～M47、M49～M54）全部自动化；AC-M17/M48由外部Seed项目验收且不阻塞Runtime。

## 41.23 已采纳的 ADR 实现决策

下列决策已作为 v0.1 实现基线，但不应上升为 Meta Constitution；实现仓库必须建立对应 ADR 文件并保留替换接口：

| ADR | 默认决策 | 触发重评条件 |
|---|---|---|
| ADR-001 | CPython 3.12 / asyncio | CPU hot path 或运行时安全成为瓶颈 |
| ADR-002 | SQLite WAL；runtime daemon 单 writer | 多机写、ledger 规模或写延迟越过目标 |
| ADR-003 | filesystem SHA-256 CAS | 需要远程复制、对象存储或跨节点去重 |
| ADR-004 | UUIDv7 semantic IDs | 外部互操作标准要求其他格式 |
| ADR-005 | transactional outbox + Backend persistent idempotency | Backend 支持可证明的原子事务协议 |
| ADR-006 | Portable-first MVP | AgentOS Kernel ABI 与 daemon 达到稳定可用 |
| ADR-007 | IPython/Cordis 均为 Adapter | 出现更小、更安全或跨语言的实现 |
| ADR-008 | local-only daemon control API；embedded 仅开发/测试 | 明确提出远程、多租户产品需求 |
| ADR-009 | transactional state + append-only audit/causal log，不做完整 Event Sourcing | 出现必须仅靠事件重建全部状态的明确需求 |
| ADR-010 | desired/serving/realized 三指针切换 | 证明单指针仍能安全表达未就绪/降级状态 |
| ADR-011 | 第三方/Candidate 默认 isolated process | 出现可验证的安全 in-process runtime |
| ADR-012 | Portable 对 required 强安全语义 fail closed | Portable Backend 提供等价且可验证的物理保证 |
| ADR-013 | Restricted Raw + Redacted Derived Artifact | 隐私、法规或产品策略要求完全禁存 Raw |
| ADR-014 | 小型 Port + façade + handler registry | 接口拆分导致可测量的维护或性能负担 |
| ADR-015 | Public API v1 使用 Protobuf 单一语义；JSON 仅为映射输出 | 需要独立 REST compatibility contract |
| ADR-016 | Task 是一等持久化对象并在接纳时冻结 serving surface | 产品明确采用无状态一次性调用模型 |
| ADR-017 | Root credential 由 OS keychain/AgentOS Broker 托管 | 引入外部组织级 KMS/HSM |
| ADR-018 | Artifact Package v1 使用跨平台 canonical logical encoding | 采用具备相同保证的标准制品格式 |
| ADR-019 | Raw 默认不持久化；启用时 envelope encryption、默认 7 天 | 法规/产品 retention policy 变更 |
| ADR-020 | Migration 默认隔离且禁止外部 effect | 出现经证明安全的其他 migration 模型 |
| ADR-021 | Portable 只运行 trusted candidate；untrusted/high-risk 要求 Managed strong isolation | Portable 获得可验证强隔离能力 |
| ADR-022 | Linux/Windows 为 v0.1 MUST；macOS 为 Experimental | macOS 进入完整 CI 与发布支持矩阵 |
| ADR-023 | v0.1 local RPC 为 4-byte framed Protobuf over UDS/Named Pipe，不用 gRPC/TCP fallback | 远程 deployment profile 进入范围 |
| ADR-024 | JSON/hash canonicalization 使用 RFC 8785 JCS | 标准互操作要求替换 encoding |
| ADR-025 | SQLite STRICT schema、WAL、synchronous FULL、BEGIN IMMEDIATE writer | durability/throughput profile 经 fault test 证明需调整 |
| ADR-026 | Managed State 为 immutable revision + CAS current ref；Task 冻结 read revision | 引入已验证 merge/CRDT 语义 |
| ADR-027 | Evolution v0 使用 typed ChangeSet 与 ALL_REQUIRED_PASS evaluator | 引入统计/学习型 evaluator policy |
| ADR-028 | Raw encryption 使用 AES-256-GCM envelope encryption，Root identity 使用 Ed25519 | crypto policy/平台合规要求调整 |
| ADR-029 | Surface/Health/State cutover/Outbox clock 使用41.59的race-closed语义 | 引入多writer或分布式lease profile |
| ADR-030 | Seed Harness是独立项目；Runtime仅拥有公共Contract/SDK、Generic Host与test-only Conformance Harness | Harness Contract major或部署边界发生变化 |

---

## 41.24 v0.1 规范冻结清单

本节补齐从架构设计进入实现所需的规范性决定。标记为 `FROZEN` 的项目在 v0.1 实现中不得由各 Adapter 自行解释；变更必须通过 ADR，并同步更新 schema、contract tests 与需求追踪矩阵。

| 规范 | 状态 | 权威交付物 |
|---|---|---|
| Task 生命周期与 serving freeze | FROZEN | `schemas/domain/v1/task.schema.json` |
| 公共 mutation/result/error envelope | FROZEN | `schemas/public-api/v1/` |
| Execution Backend wire contract | FROZEN | `proto/execution_backend/v1/backend.proto` |
| Authority bootstrap 与 permission registry | FROZEN | Authority schema + ADR |
| Artifact canonicalization | FROZEN | canonicalization spec + golden vectors |
| Raw Artifact encryption/retention | FROZEN | privacy policy + crypto adapter contract |
| Managed State migration contract | FROZEN | migration schema + isolation contract |
| Portable Candidate trust profile | FROZEN | backend profile fixtures |
| External Harness Contract/lifecycle | FROZEN | `schemas/harness-contract/v1/` + §40/41.60 |
| Surface/Health/State cutover/Outbox clock | FROZEN | §41.59 + race fixtures |
| FR/NFR/AC traceability | maintained continuously | `docs/spec/v0.1-scope-and-traceability.md` |

实现仓库必须建立以下规范目录；尚未拆分的内容先以本文对应章节为权威源：

```text
docs/spec/
├── v0.1-scope-and-traceability.md
├── v0.1-implementation-handoff.md
├── domain-state-machines.md
├── task-and-harness-contract.md
├── public-api-v1.md
├── external-harness-lifecycle.md
├── execution-backend-v1.md
├── authority-bootstrap.md
├── artifact-canonicalization.md
├── storage-and-recovery.md
├── portable-security-profiles.md
└── privacy-retention-key-management.md

schemas/
├── domain/v1/
├── facts/v1/
├── public-api/v1/
├── harness-contract/v1/
└── capability-contract/v1/

proto/
└── execution_backend/v1/backend.proto
```

这些文件是本文规范的可执行展开；CI必须验证其版本与本文/ADR一致。若发现冲突，在修订规范、traceability、schema/proto和golden test并完成review前不得发布，禁止任何一方静默取得优先级或长期双轨。

## 41.25 Task 与 Harness Host 的完整契约

Task 最小字段：

```yaml
task_id: task://<uuidv7>
realm_id: realm://main
actor_id: principal://...
authority_grant_id: grant://...
input_artifact_id: artifact://sha256/...
accepted_at_us: 0
deadline_at_us: 0
serving_composition_id: composition://...
serving_revision: 82
capability_surface_revision: 17
budget:
  max_turns: 32
  max_steps: 128
  max_model_calls: 64
  max_effects: 32
  max_cost_microunits: 0
root_action_id: action://...
status: ACCEPTED
result_artifact_id: null
error: null
```

约束：

- `task_id` 使用 UUIDv7，加入 41.4.1 的 ID registry；
- `capability_surface_revision` 指向由冻结 Composition、有效 Authority 和 Backend feature profile 确定的不可变 Tool/Capability Schema Artifact；
- initial `budget_json` 冻结；消耗只增加 `consumed_budget_json`。拥有 `task.budget.extend` 的 Principal可追加正数 `task_budget_adjustments`，effective ceiling为initial加按ordinal求和的delta；不得原地改initial、负向调整或因重试重置；
- `SUCCEEDED` 必须有 `result_artifact_id`；`FAILED/FAILED_RECOVERY` 必须有 sanitized `error`；`CANCELLED/TIMED_OUT` 可以二者均无；
- Task 与根 Action 必须在接纳事务中共同创建；后续 Action 必须可沿 causal parent 回到根 Action；
- cancel 是请求而不是结果；只有 cancellation 已传播并提交 terminal Fact 后，Task 才变为 `CANCELLED`；无法确认 effect 状态时必须携带 `EXTERNAL_EFFECT_UNKNOWN`。

重启时，对非 terminal Task 按以下顺序处理：读取冻结的 Composition 与 execution binding；通过 Backend `reconcile` 查明 workload；可续接且 budget/deadline 有效时继续；已有 durable result 时提交 terminal row + Fact；无法续接时标记 `FAILED_RECOVERY`；存在未知 effect 时追加 `external_effect_unknown` Fact。不得使用最新 serving Composition 重新执行旧 Task。

## 41.26 Public API v1 与 Local Transport

v0.1 wire format 采用 **versioned Protobuf messages over local transport**。POSIX 使用 UDS；Windows 使用 Named Pipe；v0.1 不使用 gRPC，也不允许自动回退到 TCP。两种 transport 使用 4-byte big-endian unsigned length + serialized `RpcEnvelope`，单帧上限 16 MiB；超限 payload 必须先进入 Artifact Store。每个连接可有多个按 `request_id` 关联的 in-flight request，但同一 `request_id` 在连接内只允许一次。JSON 仅作为 CLI `--output json` 与 diagnostics 的映射格式，不作为第二套 mutation protocol。

安全与发现规则固定为：POSIX socket 位于 `<data_dir>/run/agent-meta.sock`、目录 mode `0700`、socket mode `0600`；Windows pipe 名为 `\\.\pipe\agent-meta-<sha256(canonical-data-dir)[0:16]>`，DACL 只允许 daemon 所属用户 SID 和 LocalSystem。endpoint 写入 `<data_dir>/run/endpoint.json`，文件权限仅当前用户可读；其中只含 transport、address、pid、instance id、API version 和启动时间，不含 secret。连接后第一条消息必须是 `Hello`，协商 API major/minor；major 不相交则关闭连接。客户端断线不取消 Task，只有显式 `Task.Cancel` 才触发取消。

Daemon 默认最多 64 个 local connection、每连接最多 32 个 in-flight request；accept 后 5 秒内必须收到完整 Hello，普通 frame header/body 间隔不得超过 30 秒，idle 5 分钟关闭。长度字段在分配 buffer 前校验；非法/截断/超限 frame 关闭该连接并增加 metric，不影响其他连接。Server 对每个 request 强制默认 deadline 30 秒；Task.Wait 最大单次 60 秒，timeout 只结束 Wait RPC，不改变 Task。

公共 API 至少定义：

```text
Runtime.GetInfo / GetView / Doctor / GetMetrics
Task.Submit / Get / Wait / Cancel
Artifact.Put / GetManifest / Verify
Harness.ValidatePackage / Install / Get / List / Activate / Deactivate / Uninstall
Composition.Validate / Commit / GetRefs
Evolution.Propose / RunExperiment / Promote / Rollback
Graph.Why / Lineage
```

所有 RPC response 使用 `api_version + request_id + (result | error)`。写请求的 result 必须含 `MutationReceipt`。错误 envelope v1字段固定为稳定 `code`、`retryable`、`message_safe`、`details_schema_version`、`details` 与 `correlation_id`；可新增字段只能使用41.41保留的field number，不得在`details`之外发明第二种错误载荷，也不得暴露 traceback、secret、raw prompt 或 provider-native body。列表查询必须使用稳定排序键和 opaque cursor；默认 limit 100，服务端最大 1000。Wait 使用 deadline/cancellation，不以无限阻塞连接表达任务所有权。

## 41.27 Execution Backend v1 Wire Contract

`backend.proto` 在 Slice 4 前必须冻结以下 RPC：

```text
Negotiate(ClientHello) → BackendSession
Submit(ExecutionRequest) → ExecutionHandle
Await(ExecutionHandle, Deadline) → ExecutionResult
Cancel(ExecutionHandle, CancelMode) → CancelReport
Inspect(ExecutionHandle) → ExecutionSnapshot
Reconcile(ReconcileRequest) → ReconcileReport
AcknowledgeTerminal(request_id, result_hash) → AckReport
CloseSession(BackendSession) → CloseReport
```

协议要求：

- 每个请求携带 negotiated protocol version、backend session id、realm id、request id 与 deadline；
- `Submit` 的幂等 identity 是 `dedupe_scope + request_id + payload_hash`；
- handle 包含 backend id、opaque handle bytes、incarnation 与 expiry hint，不得将 PID 当 canonical handle；
- transport 断开不等于 workload 失败；client 必须 `Inspect/Reconcile` 后才能决定；
- stream 只用于进度/fact observation，terminal result 仍可通过 `Await/Inspect` 幂等取得；
- error 使用 41.14 稳定错误码，并通过 typed details 表达 retry hint、feature limitation 与 unknown-effect；
- contract suite 覆盖 response-lost-after-create、duplicate submit、payload conflict、session restart、handle renewal、late completion 与 acknowledgement replay。

## 41.28 Authority Bootstrap 与 Permission Registry

首次 `agent-meta init` 必须原子执行：创建 Realm 与 Epoch 0；生成 Ed25519 operator Root key pair与UUIDv7 `principal://operator-root/<uuid>`；public identity保存raw public key及其SHA-256 fingerprint；创建仅属于Epoch 0的Root Grant；将private key保存到OS keychain；Meta Store只保存public key、grant、credential handle与Fact。无keychain的CI/dev环境只允许显式 `--insecure-dev-credential-file`，POSIX mode必须`0600`，Windows DACL只允许当前用户SID。重复`init`不得创建第二个Root。

Root-authorized `CommandEnvelope` 必须携带 `auth_nonce`、`auth_issued_at_us` 与 Ed25519 signature；签名 preimage 为 ASCII domain separator `agent-meta-command-v1\0` + 32-byte authorization hash + NUL + nonce UTF-8 + NUL + issued time decimal ASCII。Daemon 校验 public key、时间偏差不超过 5 分钟、nonce 在 10 分钟 replay cache 中未使用，再在同一 command transaction 持久登记 nonce hash。普通 scoped execution token 由 daemon 在完成 Authority check 后签发，不能替代 Root signature 扩权。

Root Grant 不能通过普通 `authority.grant` 创建、扩大或恢复。Init 同时生成256-bit random recovery code，只向operator stdout显示一次；`root_recovery`只保存 `sha256("agent-meta-root-recovery-v1\0" + raw-code)` 与generation，日志/diagnostics不记录。`agent-meta recover-root --recovery-code-stdin` 必须在daemon停止并取得data-dir lock后运行：验证active hash → 完整backup → 生成新Ed25519 Root Principal/key handle → 创建等权限、同Epoch的replacement Root Grant → revoke旧Root Grant → 将旧hash/generation写`root_recovery_history` → 生成新的one-time code并更新active hash/generation → 在单一SQLite transaction写Fact/meta revision。命令不接受argv code或环境变量，防止进程列表/环境泄露；失败尝试不披露hash相似度并以1秒固定延迟返回。旧code因不再是active且history unique不能复用；旧private key因grant revoked失效。recovery code和备份都丢失时无绕过路径，只能重新初始化新Realm。

权限名使用稳定的 `<resource>.<verb>`，v0.1 registry 完整集合如下；未列名称一律 unknown/fail closed，新增需 schema minor + ADR：

```text
task.submit / task.execute / task.cancel / task.budget.extend
model.invoke
artifact.put / artifact.read.restricted / artifact.verify
composition.validate / composition.commit / composition.promote / composition.rollback
capability.invoke / capability.inspect
harness.install / harness.activate / harness.deactivate / harness.uninstall
state.read / state.write / state.migrate
authority.inspect / authority.grant / authority.delegate / authority.revoke
experiment.run / evaluation.record
runtime.reflect / runtime.diagnostics
runtime.reconcile / runtime.project / runtime.token.issue / runtime.admin.stop
scratch.create / scratch.execute / scratch.inspect / scratch.export / scratch.release
operations.backup / operations.gc / operations.repair
effect.execute.irreversible
```

Scope 是 Realm、Capability、Artifact kind、Task、Experiment 或 Effect kind 的 typed union，不是任意字符串。授权顺序固定为：grant status/epoch → subject → permission → scope → constraints/expiry → revocation。Delegation 的 permission、scope、expiry、budget 与 delegable depth 必须逐维不扩大；未知 permission/scope fail closed。

Scope v1 schema 是 `{realm_id, targets:[{type,id}]}`。`type` 仅为 `REALM_ALL/CAPABILITY/HARNESS/ARTIFACT_KIND/TASK/EXPERIMENT/EFFECT_KIND`；除 `REALM_ALL` 外 id 必须精确相等，不支持 glob、prefix、regex 或隐式 parent。一次 check 的 resource必须提供 realm和一个 concrete target；grant含同 realm `REALM_ALL` 或 exact target才匹配。多 target 是 OR，permissions 是显式 set。Constraint v1 只有 `epoch_id, not_before_us, expires_at_us, max_uses, resource_ceiling, delegation_depth_remaining`；不同维度是 AND。Delegation containment：child permissions/targets为 parent子集；child time interval在 parent内；每个 numeric ceiling ≤ parent；depth减少 1；parent max_uses 的每次成功 delegate和实际 use都通过原子 counter reservation计算。缺失 parent ceiling不代表无限扩大：child可以保持缺失或设更小显式值；Root Grant才可声明 `unbounded=true`。

Authority check 与 Action/Effect reservation在同一 Meta Store transaction 写 `authority_uses(grant_id, action_id, use_kind, amount, meta_revision)`，`UNIQUE(grant_id, action_id, use_kind)` 防重；撤销与并发使用由 writer序列化，先提交者生效。检查时 wall time来自 injectable Clock，过期 grant可以惰性把 current status改 EXPIRED并写 history/Fact，但拒绝本次命令。

Grant definition/parent/scope/constraints committed 后不可改；`authority_grants.status` 是 current active reference，任何 revoke/expire 必须在同一事务写 `authority_grant_history` + Fact。Historical Authority query 按 meta revision读取最近 history row，不能用当前 status 解释旧 Action。

## 41.29 Artifact Canonicalization 与 Package Identity

`ArtifactId` 的 hash preimage 是 **canonical payload bytes**，不包含 `artifact_id` 自身、存储路径、创建时间或数据库 row。Manifest 保存 payload hash 与非身份 metadata；影响能力语义的 metadata 必须放入 versioned package manifest 并参与 canonicalization。

Capability Package v1 canonical payload 精确编码为：ASCII magic `AMPAK1\n`；8-byte big-endian manifest byte length；RFC 8785 JCS manifest；随后按 manifest entries 顺序，对每个 FILE 写 8-byte big-endian content length + raw bytes，DIRECTORY 不写 content。Manifest 为 `{format_version:1, package, entries[]}`；`package`固定字段为 `{name,version,artifact_kind,entrypoint,contract_artifact_id,dependency_lock_artifact_id,state_schema_artifact_ids[],migration_artifact_ids[],runtime_constraints,platform_constraints,build_provenance_artifact_id}`，数组按ArtifactId排序去重且没有适用项时使用空数组；不得省略字段或加入未知字段。entry 固定字段 `{path,kind,permission_class,size,sha256}`，entries 按 path 的 UTF-8 bytes 升序。`permission_class` 只有 `DATA|EXECUTABLE`；Windows executable 来源由 package manifest 显式指定，不从本机 ACL 推断。

路径使用 `/`、UTF-8 NFC；禁止绝对路径、空 segment、`.`、`..`、NUL、反斜杠、重复路径、Windows reserved/device name、尾随点/空格、ADS colon、Unicode normalization duplicate、case-fold duplicate、设备文件、FIFO、socket 和 symlink。目录必须显式列出且先于子项；root 不列入。mtime、uid、gid 与本机 ACL 不参与 identity。Decoder 必须核验 size/hash、entry count ≤ 10000、单文件 ≤ 256 MiB、总 package ≤ 1 GiB、路径 UTF-8 bytes ≤ 512。必须提供跨 Linux/Windows golden vectors，覆盖空文件、Unicode、大小写冲突、路径穿越和不同枚举顺序。

File content不做通用 newline/encoding normalization；相同 package意味着相同 raw file bytes。Repository/build pipeline必须从锁定 source archive构建，不能依赖会改行尾的工作树 checkout。Scratch cell source是例外：Adapter在创建 source Artifact前将 CRLF/CR统一为 LF并编码 UTF-8（无 BOM），不自动增删末尾换行；该规则写入 source media type `text/x-python; canonical=lf-utf8-v1`。

## 41.30 Restricted Raw Artifact：加密、保留与审计

v0.1 采用 envelope encryption：每个 Restricted Raw Artifact 使用 CSPRNG 生成的 256-bit DEK，以 AES-256-GCM、96-bit random nonce 加密；AAD 是 `artifact_id + NUL + realm_id + NUL + media_type + NUL + schema_version` 的 UTF-8 bytes。DEK 由独立 256-bit KEK 使用 AES-256-GCM 和另一随机 nonce 包装。KEK 来自 OS keychain 或 AgentOS Credential Broker，Meta Store、CAS 与日志均不得保存明文 key。禁止 nonce 在同一 key 下复用；随机源失败则拒绝写入。

`ArtifactId` 仍是 plaintext canonical content hash；实际存储单元另有 `BlobId = blob://sha256/<ciphertext-and-tag-bytes>`。普通 Artifact 的 blob 可使用相同 content hash；Restricted blob固定存于 `artifacts/encrypted/sha256/<prefix>/<ciphertext-hash>`，文件内容为 GCM ciphertext后直接附16-byte tag，不得放入plaintext CAS path。加密metadata按 `(artifact_id, realm_id, encryption_revision)` 保存，同一Artifact在不同Realm必须独立加密/授权，不能因内容相同跨Realm复用DEK/blob。读取先Authority，再选择该Realm唯一ACTIVE encryption revision，验证ciphertext hash/GCM tag，最后验证plaintext ArtifactId。

必须定义：

- key handle、`AES-256-GCM/v1`、content nonce、wrap nonce、wrapped DEK/tag 与 ciphertext hash 的 manifest 字段；
- KEK rotation 可只重包 DEK 并新增 encryption revision；DEK/content rotation 创建新 ciphertext BlobId。两者都在新 revision ACTIVE 后将旧 revision 标 ROTATED 并进入 7 天 quarantine，不改变明文 ArtifactId；
- 每次 restricted read 校验 `artifact.read.restricted` 并写访问 Fact；
- retention 到期先生成 auditable deletion plan，再删除 wrapped DEK/ciphertext；crypto-erasure 后保留 tombstone Fact；
- backup 同时声明 encrypted CAS、wrapped keys 和恢复依赖；缺 key 返回 `KEY_UNAVAILABLE`，不得伪报 Artifact 损坏；
- dev plaintext 模式必须显式开启并显示高优先级 warning，不得用于产品 profile 或安全验收。

默认 policy 为不持久化 Raw；显式开启时默认保留 7 天。Redacted Derived Artifact 按 Realm policy 管理。部署可覆盖期限，但 policy 必须是 versioned Artifact 并记录在 Invocation。

## 41.31 Managed State Migration Contract

State Migration Artifact 必须声明：

```text
source_schema_id
target_schema_id
entrypoint
runtime_constraint
resource_budget
determinism_level
expected_output_schema
```

Migration 接收旧 State Artifact，只能产生新 State Artifact、structured log 和 Evidence；禁止 network、credential、外部 effect 和对 committed state 的原地写。默认在 isolated subprocess 中运行，使用只读输入和全新输出目录。相同 migration Artifact + input Artifact + parameters 使用稳定 request id；非确定性 migration 必须声明且不得自动重试。

流程固定为：validate manifest → isolated execute → validate output schema/hash → record Evidence → 在 Promotion/Reconcile transaction 中绑定新 `ManagedStateRevision`。任何步骤失败均保留旧 serving Composition 与 State Revision。回滚要求 parent Composition 的 State Revision 仍可读取；不得默认假设存在 downgrade migration。

## 41.32 Portable 平台与 Candidate 信任等级

v0.1 平台范围：

| 平台 | v0.1 等级 | CI 要求 |
|---|---|---|
| Linux | MUST | unit + contract + integration + E2E |
| Windows | MUST | unit + contract + integration + E2E |
| macOS | Experimental/SHOULD | contract smoke；缺失不阻塞 v0.1 发布，但必须报告 feature profile |

Portable Candidate 分级：

| Trust class | 最低 placement | Portable 是否允许 |
|---|---|---|
| `builtin_or_signed` | in-process 或 process | 是，按 policy |
| `trusted_candidate` | isolated process/workspace，无 credential，network deny | Linux/Windows 是 |
| `untrusted_candidate` | strong isolated realm | 否；要求 Managed Backend `SUPPORTED` |
| `high_risk_effect_candidate` | strong isolation + explicit effect authority | 否；要求 Managed Backend |

v0.1 Portable Candidate E2E/AC-M18 使用 `trusted_candidate`，验证 process/workspace isolation 与 permission deny，不描述为 adversarial strong sandbox。来源不明、请求 credential/network、包含 native extension、尝试越过 workspace 或产生不可逆 effect 的 Candidate 自动升级为 `untrusted_candidate`，Portable Backend 返回 `FEATURE_UNAVAILABLE`。

Linux Portable 使用 process group、独立 workspace、最小 environment 和可用的 rlimit；Windows 使用 Job Object、独立 workspace、restricted handle inheritance 和最小 environment。二者均不声称提供多租户文件系统或 credential strong isolation。

## 41.33 Runtime 内建 Artifact 与需求追踪

v0.1 Runtime发行物只包含以下可版本化的基础Artifact/Contract；它们定义安全边界与互操作语义，不实现Model、Loop、Context、tool dispatch或Seed策略：

```text
runtime-constitution/v1       admission principles and invariants
harness-package-contract/v1   external package manifest and lifecycle
harness-loop-contract/v1      terminal Model response and typed tool-call DTOs
task-budget-contract/v1       host-enforced hard ceilings and accounting
authority-permissions/v1      permission/scope registry and delegation rules
redaction-policy/v1           structured allowlist and secret handling
retention-policy/v1           Raw off; redacted/diagnostic bounded retention
compatibility-report/v1       deterministic validation result and plan hash
```

Runtime可配置Host hard ceiling；外部Harness可以在其范围内声明更严格budget/policy。有效结果必须形成fingerprint并进入Task/Invocation provenance。内建Artifact与外部Harness均不拥有隐式Authority。

首版最低追踪矩阵：

| Slice | 主要 FR/NFR | 必须通过的 AC |
|---|---|---|
| 1 Identity/CAS/UoW | FR-MID-001~005、FR-MSTORE-001/003/004/009 | AC-M04、AC-M14、AC-M15、AC-M28、AC-M35 |
| 2 Fact/Action/View | FR-MFACT-001~006、NFR-M06/07/52 | AC-M02、AC-M12、AC-M35、AC-M52 |
| 3 Composition/State/Authority | FR-MCAP-001~008、FR-MSTATE-001~005、FR-MAUTH-001~005 | AC-M05、AC-M21、AC-M25、AC-M29、AC-M38 |
| 4 Execution Backends | FR-MOS-001~011、FR-MSEC-002、FR-MEFFECT-001~002、NFR-M18/20/27 | AC-M09A、AC-M09B、AC-M22、AC-M30、AC-M34、AC-M39、AC-M43 |
| 5 Harness Host/Task | FR-MRUN-001~006/008、FR-MTASK-001~003、FR-MAPI-001~004 | AC-M20、AC-M31、AC-M41、AC-M47、AC-M51、AC-M54；FR-MRUN-007与AC-M17/M48为External-Seed |
| 6 Invocation/Why | FR-MINV-001、FR-MCTX-001~004、FR-MSEC-001 | AC-M03、AC-M26、AC-M32、AC-M37 |
| 7 Reconcile/Recovery | FR-MSTORE-005~010、FR-MTASK-002~003、FR-MOPS-004、NFR-M23/24/28 | AC-M16、AC-M21、AC-M23、AC-M33、AC-M40 |
| 8 Scratch | FR-MREF-001~006 | AC-M08、AC-M19、AC-M36、AC-M49 |
| 9 Evolution/Promotion | FR-MEVO-001~006、FR-MRUN-005、FR-MSTATE-004、FR-MSEC-002 | AC-M06、AC-M18、AC-M34、AC-M42 |
| 10 AgentOS contract | FR-MOS-001~011、FR-MAPI-003~004 | AC-M09、AC-M22、AC-M30、AC-M41、AC-M43、AC-M47 |
| Cross-cutting Security | FR-MSEC-001~004、FR-MAUTH-001~005 | AC-M19、AC-M26、AC-M29、AC-M32、AC-M34、AC-M44、AC-M50 |
| Cross-cutting Architecture | FR-MARCH-001~006、FR-MSPEC-001 | AC-M07、AC-M13、AC-M27、AC-M45、AC-M54 |
| Cross-cutting Operations | FR-MOPS-001~005、NFR-M28/40/46 | AC-M20、AC-M23、AC-M40、AC-M46 |

完整 `docs/spec/v0.1-scope-and-traceability.md` 必须逐条列出每个 FR/NFR 的 owner Slice、schema/proto、test id 与状态。CI 至少校验所有 MUST FR 有测试映射、所有 v0.1 AC 有自动化测试、Deferred 项没有被误标为已交付。

## 41.34 Canonical Encoding、SQLite Schema 与事务 Profile

### 41.34.1 Canonical scalar/JSON rules

所有 hash、幂等 payload 与 JSON BLOB 使用 RFC 8785 JSON Canonicalization Scheme（JCS）UTF-8 bytes，并遵守 I-JSON。JSON integer 限制为 IEEE-754 safe integer `[-9007199254740991, 9007199254740991]`；更大 int64/uint64 必须由 schema 定义为 canonical decimal string。传入 JSON number 若非有限值、超 safe range 或出现 `-0` 语义依赖必须拒绝。JCS string 必须保留原 Unicode code points，不做 NFC/NFD；只有 41.29 package path 另行要求 NFC。时间统一为 Unix microseconds且当前范围安全，duration/deadline 同样使用整数，不使用浮点秒参与 hash。二进制只使用 Artifact 或 Protobuf `bytes`，JSON 映射使用无 padding、无换行 base64url。枚举使用文档定义的大写 ASCII token；未知枚举值在写路径拒绝，在读路径映射为 `UNKNOWN_TO_CLIENT` 并保留原数值用于 round-trip。

ID 最大 255 UTF-8 bytes。除 `capability://<stable-name>` 外均为规定 scheme + lowercase UUIDv7 或 lowercase hex；Capability stable name 匹配 `[a-z][a-z0-9]*(?:[._-][a-z0-9]+)*`，最长 128。Realm 内 sequence、revision 从 1 开始；0 表示尚无 committed revision，不分配给业务对象。

### 41.34.2 SQLite connection profile

每个 writer/reader connection 必须执行并验证：

```sql
PRAGMA foreign_keys = ON;
PRAGMA journal_mode = WAL;
PRAGMA synchronous = FULL;
PRAGMA busy_timeout = 5000;
PRAGMA trusted_schema = OFF;
PRAGMA recursive_triggers = ON;
```

Writer command 使用 `BEGIN IMMEDIATE`；读取 snapshot 使用显式 deferred transaction。一个 command 的 idempotency claim、canonical mutation、Fact、outbox 与 meta revision 在同一 transaction 提交。禁止在 transaction 中调用 Backend、Provider、filesystem network mount 或任意用户代码。SQLite error `BUSY/LOCKED` 在 deadline 内使用 25/50/100/200/400 ms full-jitter backoff，之后返回 `RESOURCE_EXHAUSTED`；不得无限重试。

DB 初始化设置 `PRAGMA application_id=1095586388`（ASCII `AMRT`）和 `PRAGMA user_version=1`；启动时值不匹配即拒绝 writer。`schema_migrations` checksum 是 migration UTF-8 bytes 的 SHA-256，按 version连续且与 wheel manifest完全一致。

### 41.34.3 v0.1 authoritative DDL

下面是 v0.1 逻辑 DDL；migration 文件必须与其等价，并以 schema contract test 校验。`*_json` 是已通过对应 schema 校验的 JCS UTF-8 BLOB，布尔值为 `0/1`。

```sql
CREATE TABLE realms (
  realm_id TEXT PRIMARY KEY, epoch_id TEXT NOT NULL,
  next_seq INTEGER NOT NULL CHECK(next_seq >= 1),
  fact_head_hash TEXT NOT NULL,
  current_meta_revision INTEGER NOT NULL CHECK(current_meta_revision >= 0),
  created_at_us INTEGER NOT NULL
) STRICT;

CREATE TABLE epochs (
  epoch_id TEXT PRIMARY KEY, realm_id TEXT NOT NULL, ordinal INTEGER NOT NULL,
  constitution_artifact_id TEXT NOT NULL, meta_root_artifact_id TEXT NOT NULL,
  authority_root_principal_id TEXT NOT NULL, fact_root_hash TEXT NOT NULL,
  status TEXT NOT NULL CHECK(status IN ('ACTIVE','PRIOR','CANDIDATE')),
  created_at_us INTEGER NOT NULL, UNIQUE(realm_id, ordinal)
) STRICT;

CREATE TABLE principals (
  principal_id TEXT PRIMARY KEY, realm_id TEXT NOT NULL,
  kind TEXT NOT NULL CHECK(kind IN ('OPERATOR_ROOT','AGENT','CAPABILITY','SERVICE','PEER')),
  public_identity_json BLOB NOT NULL,
  status TEXT NOT NULL CHECK(status IN ('ACTIVE','REVOKED','ARCHIVED')),
  created_at_us INTEGER NOT NULL, FOREIGN KEY(realm_id) REFERENCES realms(realm_id)
) STRICT;

CREATE TABLE root_recovery (
  realm_id TEXT PRIMARY KEY, active_recovery_hash TEXT NOT NULL UNIQUE,
  generation INTEGER NOT NULL CHECK(generation >= 1), created_at_us INTEGER NOT NULL,
  FOREIGN KEY(realm_id) REFERENCES realms(realm_id)
) STRICT;

CREATE TABLE root_recovery_history (
  realm_id TEXT NOT NULL, generation INTEGER NOT NULL, recovery_hash TEXT NOT NULL UNIQUE,
  used_at_us INTEGER NOT NULL, replacement_principal_id TEXT NOT NULL,
  PRIMARY KEY(realm_id, generation), FOREIGN KEY(realm_id) REFERENCES realms(realm_id)
) STRICT;

CREATE TABLE meta_revisions (
  realm_id TEXT NOT NULL, revision INTEGER NOT NULL CHECK(revision >= 1),
  transaction_id TEXT NOT NULL UNIQUE, command_id TEXT NOT NULL,
  committed_at_us INTEGER NOT NULL,
  PRIMARY KEY(realm_id, revision), FOREIGN KEY(realm_id) REFERENCES realms(realm_id)
) STRICT;

CREATE TABLE transactions (
  transaction_id TEXT PRIMARY KEY, realm_id TEXT NOT NULL, command_id TEXT NOT NULL,
  primary_aggregate_type TEXT NOT NULL, primary_aggregate_id TEXT NOT NULL,
  status TEXT NOT NULL CHECK(status IN ('COMMITTED')),
  meta_revision INTEGER NOT NULL, committed_at_us INTEGER NOT NULL,
  UNIQUE(realm_id, meta_revision), FOREIGN KEY(realm_id) REFERENCES realms(realm_id)
) STRICT;

CREATE TABLE commands (
  command_id TEXT PRIMARY KEY, realm_id TEXT NOT NULL, payload_hash TEXT NOT NULL,
  authorization_hash TEXT NOT NULL,
  auth_nonce_hash TEXT,
  status TEXT NOT NULL CHECK(status IN ('COMMITTED','REJECTED')),
  meta_revision INTEGER NOT NULL CHECK(meta_revision >= 0),
  receipt_json BLOB, resource_json BLOB, error_json BLOB,
  created_at_us INTEGER NOT NULL, completed_at_us INTEGER NOT NULL,
  CHECK((status='COMMITTED' AND receipt_json IS NOT NULL AND error_json IS NULL)
     OR (status='REJECTED' AND receipt_json IS NULL AND error_json IS NOT NULL))
) STRICT;

CREATE TABLE artifacts (
  artifact_id TEXT PRIMARY KEY, kind TEXT NOT NULL, media_type TEXT NOT NULL,
  size_bytes INTEGER NOT NULL CHECK(size_bytes >= 0), schema_version INTEGER NOT NULL,
  created_by TEXT NOT NULL, created_at_us INTEGER NOT NULL,
  parents_json BLOB NOT NULL, manifest_json BLOB NOT NULL,
  integrity_status TEXT NOT NULL CHECK(integrity_status IN ('VALID','MISSING','CORRUPT'))
) STRICT;

CREATE TABLE artifact_blobs (
  blob_id TEXT PRIMARY KEY, artifact_id TEXT NOT NULL, realm_id TEXT,
  storage_class TEXT NOT NULL CHECK(storage_class IN ('PLAIN_CAS','ENCRYPTED_RESTRICTED')),
  size_bytes INTEGER NOT NULL CHECK(size_bytes >= 0), storage_relpath TEXT NOT NULL UNIQUE,
  status TEXT NOT NULL CHECK(status IN ('ACTIVE','QUARANTINED','MISSING','CORRUPT','DELETED')),
  created_at_us INTEGER NOT NULL, deleted_at_us INTEGER,
  FOREIGN KEY(artifact_id) REFERENCES artifacts(artifact_id)
) STRICT;

CREATE TABLE artifact_encryption (
  artifact_id TEXT NOT NULL, realm_id TEXT NOT NULL, encryption_revision INTEGER NOT NULL,
  blob_id TEXT NOT NULL UNIQUE, algorithm TEXT NOT NULL,
  key_handle TEXT NOT NULL, wrapped_dek BLOB NOT NULL,
  content_nonce BLOB NOT NULL, wrap_nonce BLOB NOT NULL,
  aad_hash TEXT NOT NULL, ciphertext_hash TEXT NOT NULL, retention_until_us INTEGER,
  status TEXT NOT NULL CHECK(status IN ('ACTIVE','ROTATED','CRYPTO_ERASED')),
  created_at_us INTEGER NOT NULL, deleted_at_us INTEGER,
  PRIMARY KEY(artifact_id, realm_id, encryption_revision),
  FOREIGN KEY(artifact_id) REFERENCES artifacts(artifact_id),
  FOREIGN KEY(blob_id) REFERENCES artifact_blobs(blob_id)
) STRICT;

CREATE TABLE capabilities (
  capability_id TEXT NOT NULL, descriptor_revision INTEGER NOT NULL CHECK(descriptor_revision >= 1),
  artifact_id TEXT NOT NULL, descriptor_json BLOB NOT NULL, created_at_us INTEGER NOT NULL,
  PRIMARY KEY(capability_id, descriptor_revision),
  FOREIGN KEY(artifact_id) REFERENCES artifacts(artifact_id)
) STRICT;

CREATE TABLE capability_instances (
  instance_id TEXT PRIMARY KEY, realm_id TEXT NOT NULL, capability_id TEXT NOT NULL,
  descriptor_revision INTEGER NOT NULL, composition_id TEXT NOT NULL,
  placement TEXT NOT NULL, trust_class TEXT NOT NULL,
  status TEXT NOT NULL CHECK(status IN
    ('DEFINED','VALIDATED','INSTANTIATING','INACTIVE','ACTIVE','DEGRADED','DRAINING','RELEASED','FAILED')),
  binding_incarnation INTEGER, created_at_us INTEGER NOT NULL, updated_at_us INTEGER NOT NULL,
  FOREIGN KEY(capability_id, descriptor_revision)
    REFERENCES capabilities(capability_id, descriptor_revision)
) STRICT;

CREATE TABLE capability_surfaces (
  realm_id TEXT NOT NULL, surface_revision INTEGER NOT NULL,
  composition_id TEXT NOT NULL, artifact_id TEXT NOT NULL,
  authority_fingerprint TEXT NOT NULL, backend_profile_hash TEXT NOT NULL,
  created_at_us INTEGER NOT NULL,
  PRIMARY KEY(realm_id, surface_revision),
  UNIQUE(realm_id, composition_id, authority_fingerprint, backend_profile_hash),
  FOREIGN KEY(composition_id) REFERENCES compositions(composition_id),
  FOREIGN KEY(artifact_id) REFERENCES artifacts(artifact_id)
) STRICT;

CREATE TABLE compositions (
  composition_id TEXT PRIMARY KEY, realm_id TEXT NOT NULL, revision INTEGER NOT NULL,
  parent_id TEXT, body_json BLOB NOT NULL, body_hash TEXT NOT NULL,
  created_by TEXT NOT NULL, created_at_us INTEGER NOT NULL,
  UNIQUE(realm_id, revision), FOREIGN KEY(parent_id) REFERENCES compositions(composition_id)
) STRICT;

CREATE TABLE harness_installations (
  harness_id TEXT PRIMARY KEY, realm_id TEXT NOT NULL,
  package_name TEXT NOT NULL, package_version TEXT NOT NULL,
  package_artifact_id TEXT NOT NULL, manifest_artifact_id TEXT NOT NULL,
  contract_fingerprint TEXT NOT NULL,
  status TEXT NOT NULL CHECK(status IN ('INSTALLED','ACTIVE','INACTIVE','UNINSTALLED')),
  active_composition_id TEXT, installed_by TEXT NOT NULL,
  installed_at_us INTEGER NOT NULL, updated_at_us INTEGER NOT NULL,
  CHECK((status='ACTIVE' AND active_composition_id IS NOT NULL)
     OR (status<>'ACTIVE' AND active_composition_id IS NULL)),
  UNIQUE(realm_id, package_name, package_version),
  FOREIGN KEY(realm_id) REFERENCES realms(realm_id),
  FOREIGN KEY(package_artifact_id) REFERENCES artifacts(artifact_id),
  FOREIGN KEY(manifest_artifact_id) REFERENCES artifacts(artifact_id),
  FOREIGN KEY(active_composition_id) REFERENCES compositions(composition_id)
) STRICT;

CREATE TABLE harness_installation_history (
  harness_id TEXT NOT NULL, meta_revision INTEGER NOT NULL,
  status TEXT NOT NULL, composition_id TEXT, source_fact_id TEXT NOT NULL,
  PRIMARY KEY(harness_id, meta_revision),
  FOREIGN KEY(harness_id) REFERENCES harness_installations(harness_id),
  FOREIGN KEY(composition_id) REFERENCES compositions(composition_id),
  FOREIGN KEY(source_fact_id) REFERENCES facts(fact_id)
) STRICT;

CREATE TABLE composition_refs (
  realm_id TEXT PRIMARY KEY,
  desired_revision INTEGER NOT NULL DEFAULT 0,
  serving_revision INTEGER NOT NULL DEFAULT 0,
  realized_revision INTEGER NOT NULL DEFAULT 0,
  desired_cas INTEGER NOT NULL DEFAULT 0,
  serving_cas INTEGER NOT NULL DEFAULT 0,
  realized_cas INTEGER NOT NULL DEFAULT 0,
  reconcile_status TEXT NOT NULL CHECK(reconcile_status IN
    ('PENDING','APPLYING','READY','DEGRADED','FAILED','RETRYING','ROLLED_BACK','UNKNOWN')),
  last_error_json BLOB, FOREIGN KEY(realm_id) REFERENCES realms(realm_id)
) STRICT;

CREATE TABLE composition_ref_history (
  realm_id TEXT NOT NULL, meta_revision INTEGER NOT NULL,
  desired_revision INTEGER NOT NULL, serving_revision INTEGER NOT NULL,
  realized_revision INTEGER NOT NULL, reconcile_status TEXT NOT NULL,
  source_fact_id TEXT NOT NULL,
  PRIMARY KEY(realm_id, meta_revision),
  FOREIGN KEY(source_fact_id) REFERENCES facts(fact_id)
) STRICT;

CREATE TABLE state_revisions (
  state_revision_id TEXT PRIMARY KEY, state_id TEXT NOT NULL, owner_id TEXT NOT NULL,
  schema_id TEXT NOT NULL, parent_revision_id TEXT, artifact_id TEXT NOT NULL,
  created_by TEXT NOT NULL, created_at_us INTEGER NOT NULL,
  FOREIGN KEY(parent_revision_id) REFERENCES state_revisions(state_revision_id),
  FOREIGN KEY(artifact_id) REFERENCES artifacts(artifact_id)
) STRICT;

CREATE TABLE managed_states (
  state_id TEXT PRIMARY KEY, owner_id TEXT NOT NULL, schema_id TEXT NOT NULL,
  current_revision_id TEXT NOT NULL, cas_revision INTEGER NOT NULL CHECK(cas_revision >= 1),
  status TEXT NOT NULL CHECK(status IN ('ACTIVE','MIGRATING','DEGRADED','ARCHIVED')),
  updated_at_us INTEGER NOT NULL,
  FOREIGN KEY(current_revision_id) REFERENCES state_revisions(state_revision_id)
) STRICT;

CREATE TABLE state_ref_history (
  state_id TEXT NOT NULL, meta_revision INTEGER NOT NULL,
  state_revision_id TEXT NOT NULL, source_fact_id TEXT NOT NULL,
  PRIMARY KEY(state_id, meta_revision),
  FOREIGN KEY(state_revision_id) REFERENCES state_revisions(state_revision_id),
  FOREIGN KEY(source_fact_id) REFERENCES facts(fact_id)
) STRICT;

CREATE TABLE authority_grants (
  grant_id TEXT PRIMARY KEY, epoch_id TEXT NOT NULL, issuer_id TEXT NOT NULL,
  subject_id TEXT NOT NULL, parent_grant_id TEXT, permissions_json BLOB NOT NULL,
  scope_json BLOB NOT NULL, constraints_json BLOB NOT NULL,
  delegable INTEGER NOT NULL CHECK(delegable IN (0,1)), delegation_depth INTEGER NOT NULL,
  status TEXT NOT NULL CHECK(status IN ('ACTIVE','REVOKED','EXPIRED')),
  issued_at_us INTEGER NOT NULL, expires_at_us INTEGER, revoked_at_us INTEGER,
  FOREIGN KEY(parent_grant_id) REFERENCES authority_grants(grant_id)
) STRICT;

CREATE TABLE authority_grant_history (
  grant_id TEXT NOT NULL, meta_revision INTEGER NOT NULL,
  status TEXT NOT NULL CHECK(status IN ('ACTIVE','REVOKED','EXPIRED')),
  effective_at_us INTEGER NOT NULL, source_fact_id TEXT NOT NULL,
  PRIMARY KEY(grant_id, meta_revision),
  FOREIGN KEY(grant_id) REFERENCES authority_grants(grant_id),
  FOREIGN KEY(source_fact_id) REFERENCES facts(fact_id)
) STRICT;

CREATE TABLE authority_uses (
  grant_id TEXT NOT NULL, action_id TEXT NOT NULL, use_kind TEXT NOT NULL,
  amount_json BLOB NOT NULL, meta_revision INTEGER NOT NULL, used_at_us INTEGER NOT NULL,
  PRIMARY KEY(grant_id, action_id, use_kind),
  FOREIGN KEY(grant_id) REFERENCES authority_grants(grant_id)
) STRICT;

CREATE TABLE tasks (
  task_id TEXT PRIMARY KEY, realm_id TEXT NOT NULL, actor_id TEXT NOT NULL,
  authority_grant_id TEXT, input_artifact_id TEXT NOT NULL,
  serving_composition_id TEXT NOT NULL, serving_revision INTEGER NOT NULL,
  capability_surface_revision INTEGER NOT NULL, capability_surface_artifact_id TEXT NOT NULL,
  state_snapshot_json BLOB NOT NULL, budget_json BLOB NOT NULL,
  consumed_budget_json BLOB NOT NULL, root_action_id TEXT NOT NULL UNIQUE,
  status TEXT NOT NULL CHECK(status IN
    ('ACCEPTED','RUNNING','SUCCEEDED','FAILED','FAILED_RECOVERY','TIMED_OUT','CANCELLED')),
  accepted_at_us INTEGER NOT NULL, started_at_us INTEGER, deadline_at_us INTEGER,
  completed_at_us INTEGER, result_artifact_id TEXT, error_json BLOB,
  FOREIGN KEY(input_artifact_id) REFERENCES artifacts(artifact_id),
  FOREIGN KEY(serving_composition_id) REFERENCES compositions(composition_id),
  FOREIGN KEY(realm_id, capability_surface_revision)
    REFERENCES capability_surfaces(realm_id, surface_revision),
  FOREIGN KEY(capability_surface_artifact_id) REFERENCES artifacts(artifact_id)
) STRICT;

CREATE TABLE task_budget_adjustments (
  task_id TEXT NOT NULL, ordinal INTEGER NOT NULL, delta_json BLOB NOT NULL,
  grant_id TEXT NOT NULL, action_id TEXT NOT NULL, created_at_us INTEGER NOT NULL,
  PRIMARY KEY(task_id, ordinal), FOREIGN KEY(task_id) REFERENCES tasks(task_id)
) STRICT;

CREATE TABLE actions (
  action_id TEXT PRIMARY KEY, task_id TEXT, actor_id TEXT NOT NULL, intent TEXT NOT NULL,
  composition_id TEXT NOT NULL, grant_id TEXT, causal_parent_action_id TEXT,
  status TEXT NOT NULL CHECK(status IN ('CREATED','RUNNING','SUCCEEDED','FAILED','TIMED_OUT','CANCELLED')),
  budget_json BLOB NOT NULL, consumed_budget_json BLOB NOT NULL,
  created_at_us INTEGER NOT NULL, started_at_us INTEGER, completed_at_us INTEGER,
  error_json BLOB, FOREIGN KEY(task_id) REFERENCES tasks(task_id),
  FOREIGN KEY(causal_parent_action_id) REFERENCES actions(action_id)
) STRICT;

CREATE TABLE effect_intents (
  effect_intent_id TEXT PRIMARY KEY, action_id TEXT NOT NULL, kind TEXT NOT NULL,
  target_scope_json BLOB NOT NULL, payload_artifact_id TEXT,
  idempotency_class TEXT NOT NULL, reversibility TEXT NOT NULL,
  required_permissions_json BLOB NOT NULL, required_features_json BLOB NOT NULL,
  reservation_json BLOB NOT NULL, request_id TEXT NOT NULL UNIQUE,
  status TEXT NOT NULL CHECK(status IN
    ('VALIDATED','RESERVED','DISPATCHED','SUCCEEDED','FAILED','UNKNOWN','COMPENSATED')),
  created_at_us INTEGER NOT NULL, completed_at_us INTEGER,
  FOREIGN KEY(action_id) REFERENCES actions(action_id)
) STRICT;

CREATE TABLE invocations (
  invocation_id TEXT PRIMARY KEY, action_id TEXT NOT NULL, kind TEXT NOT NULL,
  target TEXT NOT NULL, attempt INTEGER NOT NULL CHECK(attempt >= 1),
  input_artifact_id TEXT NOT NULL, context_projection_id TEXT,
  backend_ref_json BLOB, status TEXT NOT NULL CHECK(status IN
    ('CREATED','DISPATCHED','RUNNING','SUCCEEDED','FAILED','TIMED_OUT','CANCELLED')),
  started_at_us INTEGER, completed_at_us INTEGER, output_artifact_id TEXT, error_json BLOB,
  usage_json BLOB NOT NULL, latency_us INTEGER,
  CHECK(NOT(output_artifact_id IS NOT NULL AND error_json IS NOT NULL)),
  FOREIGN KEY(action_id) REFERENCES actions(action_id)
) STRICT;

CREATE TABLE facts (
  fact_id TEXT PRIMARY KEY, realm_id TEXT NOT NULL, seq INTEGER NOT NULL,
  occurred_at_us INTEGER NOT NULL, recorded_at_us INTEGER NOT NULL,
  actor_id TEXT NOT NULL, action_id TEXT, transaction_id TEXT,
  entity_type TEXT NOT NULL, entity_id TEXT NOT NULL, event_type TEXT NOT NULL,
  schema_version INTEGER NOT NULL, payload_json BLOB NOT NULL, payload_hash TEXT NOT NULL,
  prev_fact_hash TEXT NOT NULL, fact_hash TEXT NOT NULL UNIQUE,
  UNIQUE(realm_id, seq), FOREIGN KEY(realm_id) REFERENCES realms(realm_id)
) STRICT;

CREATE TABLE causal_edges (
  realm_id TEXT NOT NULL, from_id TEXT NOT NULL, edge_type TEXT NOT NULL,
  to_id TEXT NOT NULL, source_fact_id TEXT NOT NULL,
  PRIMARY KEY(realm_id, from_id, edge_type, to_id),
  FOREIGN KEY(source_fact_id) REFERENCES facts(fact_id)
) STRICT;

CREATE TABLE outbox (
  outbox_id TEXT PRIMARY KEY, realm_id TEXT NOT NULL, kind TEXT NOT NULL,
  dedupe_key TEXT NOT NULL UNIQUE, payload_json BLOB NOT NULL, payload_hash TEXT NOT NULL,
  state TEXT NOT NULL CHECK(state IN ('PENDING','LEASED','DELIVERED','DEAD_LETTER')),
  available_at_us INTEGER NOT NULL, lease_owner TEXT, lease_expires_at_us INTEGER,
  attempts INTEGER NOT NULL DEFAULT 0, last_error_json BLOB,
  created_at_us INTEGER NOT NULL, delivered_at_us INTEGER
) STRICT;

CREATE TABLE operations (
  operation_id TEXT PRIMARY KEY, realm_id TEXT NOT NULL, kind TEXT NOT NULL,
  command_id TEXT NOT NULL, status TEXT NOT NULL CHECK(status IN
    ('ACCEPTED','RUNNING','SUCCEEDED','FAILED','FAILED_RECOVERY','CANCELLED')),
  request_json BLOB NOT NULL, result_json BLOB, error_json BLOB,
  created_at_us INTEGER NOT NULL, started_at_us INTEGER, completed_at_us INTEGER,
  CHECK(NOT(result_json IS NOT NULL AND error_json IS NOT NULL))
) STRICT;

CREATE TABLE workspaces (
  workspace_id TEXT PRIMARY KEY, realm_id TEXT NOT NULL, owner_entity_id TEXT NOT NULL,
  root_relpath TEXT NOT NULL UNIQUE, quota_bytes INTEGER NOT NULL,
  status TEXT NOT NULL CHECK(status IN ('ACTIVE','QUARANTINED','RELEASING','RELEASED')),
  created_at_us INTEGER NOT NULL, expires_at_us INTEGER, released_at_us INTEGER
) STRICT;

CREATE TABLE execution_bindings (
  backend_id TEXT NOT NULL, semantic_id TEXT NOT NULL, incarnation INTEGER NOT NULL,
  request_id TEXT NOT NULL, payload_hash TEXT NOT NULL, handle_bytes BLOB NOT NULL,
  session_id TEXT NOT NULL, status TEXT NOT NULL, expires_at_us INTEGER,
  last_observed_at_us INTEGER NOT NULL,
  PRIMARY KEY(backend_id, semantic_id, incarnation), UNIQUE(backend_id, request_id)
) STRICT;

CREATE TABLE checkpoints (
  realm_id TEXT NOT NULL, projection TEXT NOT NULL, seq INTEGER NOT NULL,
  updated_at_us INTEGER NOT NULL, PRIMARY KEY(realm_id, projection)
) STRICT;

CREATE TABLE context_projections (
  projection_id TEXT PRIMARY KEY, task_id TEXT NOT NULL, action_id TEXT NOT NULL,
  policy_artifact_id TEXT NOT NULL, composition_id TEXT NOT NULL,
  meta_revision INTEGER NOT NULL, manifest_json BLOB NOT NULL,
  rendered_artifact_id TEXT NOT NULL, created_at_us INTEGER NOT NULL
) STRICT;

CREATE TABLE scratch_sessions (
  session_id TEXT PRIMARY KEY, realm_id TEXT NOT NULL, owner_principal_id TEXT NOT NULL,
  status TEXT NOT NULL CHECK(status IN ('STARTING','ACTIVE','LOST','RELEASING','RELEASED','FAILED')),
  workspace_id TEXT NOT NULL, backend_request_id TEXT NOT NULL UNIQUE,
  idle_expires_at_us INTEGER NOT NULL, wall_expires_at_us INTEGER NOT NULL,
  last_activity_at_us INTEGER NOT NULL, created_at_us INTEGER NOT NULL, updated_at_us INTEGER NOT NULL
) STRICT;

CREATE TABLE scratch_bindings (
  session_id TEXT NOT NULL, binding_name TEXT NOT NULL, generation INTEGER NOT NULL,
  type_module TEXT NOT NULL, type_name TEXT NOT NULL, source_artifact_id TEXT NOT NULL,
  last_cell_action_id TEXT NOT NULL, observed_handle_hash TEXT,
  status TEXT NOT NULL CHECK(status IN ('LIVE','EXPIRED','EXPORTED','RELEASED')),
  metadata_json BLOB NOT NULL,
  PRIMARY KEY(session_id, binding_name, generation),
  FOREIGN KEY(session_id) REFERENCES scratch_sessions(session_id)
) STRICT;

CREATE TABLE worlds (
  world_id TEXT PRIMARY KEY, realm_id TEXT NOT NULL, backend_profile_hash TEXT NOT NULL,
  body_json BLOB NOT NULL, body_hash TEXT NOT NULL, created_at_us INTEGER NOT NULL
) STRICT;

CREATE TABLE evolution_objects (
  object_id TEXT PRIMARY KEY, realm_id TEXT NOT NULL,
  object_type TEXT NOT NULL CHECK(object_type IN ('PROPOSAL','CHANGE_SET','CANDIDATE')),
  parent_id TEXT, body_json BLOB NOT NULL, status TEXT NOT NULL,
  created_by TEXT NOT NULL, created_at_us INTEGER NOT NULL
) STRICT;

CREATE TABLE experiments (
  experiment_id TEXT PRIMARY KEY, realm_id TEXT NOT NULL, candidate_id TEXT NOT NULL,
  baseline_id TEXT NOT NULL, world_id TEXT NOT NULL, criteria_artifact_id TEXT NOT NULL,
  budget_json BLOB NOT NULL, status TEXT NOT NULL, body_json BLOB NOT NULL,
  created_at_us INTEGER NOT NULL, completed_at_us INTEGER
) STRICT;

CREATE TABLE evidence (
  evidence_id TEXT PRIMARY KEY, experiment_id TEXT, producer_action_id TEXT NOT NULL,
  kind TEXT NOT NULL, subject_id TEXT NOT NULL, artifact_id TEXT NOT NULL,
  world_id TEXT, observed_at_us INTEGER NOT NULL, metadata_json BLOB NOT NULL,
  FOREIGN KEY(experiment_id) REFERENCES experiments(experiment_id),
  FOREIGN KEY(producer_action_id) REFERENCES actions(action_id),
  FOREIGN KEY(artifact_id) REFERENCES artifacts(artifact_id),
  FOREIGN KEY(world_id) REFERENCES worlds(world_id)
) STRICT;

CREATE TABLE evaluations (
  evaluation_id TEXT PRIMARY KEY, experiment_id TEXT NOT NULL,
  evaluator_artifact_id TEXT NOT NULL, evidence_ids_json BLOB NOT NULL,
  result_artifact_id TEXT NOT NULL, decision TEXT NOT NULL CHECK(decision IN ('ACCEPT','REJECT')),
  created_at_us INTEGER NOT NULL, FOREIGN KEY(experiment_id) REFERENCES experiments(experiment_id)
) STRICT;

CREATE TABLE schema_migrations (
  version INTEGER PRIMARY KEY, name TEXT NOT NULL UNIQUE, checksum TEXT NOT NULL,
  applied_at_us INTEGER NOT NULL, runtime_version TEXT NOT NULL
) STRICT;

CREATE UNIQUE INDEX uq_artifact_encryption_active
ON artifact_encryption(artifact_id, realm_id) WHERE status='ACTIVE';
CREATE UNIQUE INDEX uq_artifact_plain_blob
ON artifact_blobs(artifact_id) WHERE storage_class='PLAIN_CAS' AND status='ACTIVE';
CREATE UNIQUE INDEX uq_epoch_active
ON epochs(realm_id) WHERE status='ACTIVE';
CREATE UNIQUE INDEX uq_command_auth_nonce
ON commands(realm_id, auth_nonce_hash) WHERE auth_nonce_hash IS NOT NULL;
CREATE INDEX ix_fact_entity ON facts(realm_id, entity_type, entity_id, seq);
CREATE INDEX ix_fact_action ON facts(action_id, seq);
CREATE INDEX ix_fact_transaction ON facts(transaction_id, seq);
CREATE INDEX ix_task_queue ON tasks(realm_id, status, accepted_at_us, task_id);
CREATE INDEX ix_action_task ON actions(task_id, created_at_us);
CREATE INDEX ix_invocation_action ON invocations(action_id, started_at_us);
CREATE INDEX ix_edge_to ON causal_edges(realm_id, to_id, edge_type);
CREATE INDEX ix_outbox_dispatch ON outbox(state, available_at_us, lease_expires_at_us);
CREATE INDEX ix_binding_request ON execution_bindings(backend_id, request_id);
CREATE INDEX ix_harness_status ON harness_installations(realm_id, status, package_name);
CREATE INDEX ix_harness_history ON harness_installation_history(harness_id, meta_revision DESC);
CREATE INDEX ix_comp_ref_history ON composition_ref_history(realm_id, meta_revision DESC);
CREATE INDEX ix_state_ref_history ON state_ref_history(state_id, meta_revision DESC);
CREATE INDEX ix_evidence_experiment ON evidence(experiment_id, observed_at_us);
CREATE INDEX ix_operation_status ON operations(realm_id, status, created_at_us);
CREATE INDEX ix_workspace_status ON workspaces(realm_id, status, expires_at_us);
```

由于 Task 与 root Action 互相引用，`tasks.root_action_id` 不声明立即 FK；Application invariant 和启动 doctor 必须检查其存在且 `actions.task_id` 指回同一 Task。所有其他逻辑 Artifact/ID 引用由 repository 写前验证；为保留 append-only 历史，即使被引用对象进入 archive 也不得物理删除 canonical row。

必须安装防篡改 trigger：

```sql
CREATE TRIGGER facts_no_update BEFORE UPDATE ON facts BEGIN
  SELECT RAISE(ABORT, 'FACT_APPEND_ONLY');
END;
CREATE TRIGGER facts_no_delete BEFORE DELETE ON facts BEGIN
  SELECT RAISE(ABORT, 'FACT_APPEND_ONLY');
END;
CREATE TRIGGER compositions_no_update BEFORE UPDATE ON compositions BEGIN
  SELECT RAISE(ABORT, 'COMPOSITION_IMMUTABLE');
END;
CREATE TRIGGER compositions_no_delete BEFORE DELETE ON compositions BEGIN
  SELECT RAISE(ABORT, 'COMPOSITION_IMMUTABLE');
END;
CREATE TRIGGER state_revisions_no_update BEFORE UPDATE ON state_revisions BEGIN
  SELECT RAISE(ABORT, 'STATE_REVISION_IMMUTABLE');
END;
CREATE TRIGGER state_revisions_no_delete BEFORE DELETE ON state_revisions BEGIN
  SELECT RAISE(ABORT, 'STATE_REVISION_IMMUTABLE');
END;
CREATE TRIGGER evidence_no_update BEFORE UPDATE ON evidence BEGIN
  SELECT RAISE(ABORT, 'EVIDENCE_IMMUTABLE');
END;
CREATE TRIGGER evidence_no_delete BEFORE DELETE ON evidence BEGIN
  SELECT RAISE(ABORT, 'EVIDENCE_IMMUTABLE');
END;
CREATE TRIGGER evaluations_no_update BEFORE UPDATE ON evaluations BEGIN
  SELECT RAISE(ABORT, 'EVALUATION_IMMUTABLE');
END;
CREATE TRIGGER evaluations_no_delete BEFORE DELETE ON evaluations BEGIN
  SELECT RAISE(ABORT, 'EVALUATION_IMMUTABLE');
END;
CREATE TRIGGER capabilities_no_update BEFORE UPDATE ON capabilities BEGIN
  SELECT RAISE(ABORT, 'CAPABILITY_REVISION_IMMUTABLE');
END;
CREATE TRIGGER capabilities_no_delete BEFORE DELETE ON capabilities BEGIN
  SELECT RAISE(ABORT, 'CAPABILITY_REVISION_IMMUTABLE');
END;
CREATE TRIGGER harness_identity_immutable BEFORE UPDATE ON harness_installations
WHEN OLD.harness_id IS NOT NEW.harness_id OR OLD.realm_id IS NOT NEW.realm_id
  OR OLD.package_name IS NOT NEW.package_name OR OLD.package_version IS NOT NEW.package_version
  OR OLD.package_artifact_id IS NOT NEW.package_artifact_id
  OR OLD.manifest_artifact_id IS NOT NEW.manifest_artifact_id
  OR OLD.contract_fingerprint IS NOT NEW.contract_fingerprint
  OR OLD.installed_by IS NOT NEW.installed_by OR OLD.installed_at_us IS NOT NEW.installed_at_us
BEGIN SELECT RAISE(ABORT, 'HARNESS_IDENTITY_IMMUTABLE'); END;
CREATE TRIGGER harness_uninstalled_terminal BEFORE UPDATE ON harness_installations
WHEN OLD.status='UNINSTALLED' AND NEW.status IS NOT OLD.status
BEGIN SELECT RAISE(ABORT, 'HARNESS_UNINSTALLED_TERMINAL'); END;
CREATE TRIGGER harness_status_transition BEFORE UPDATE OF status ON harness_installations
WHEN NOT (
  OLD.status=NEW.status
  OR (OLD.status='INSTALLED' AND NEW.status IN ('ACTIVE','UNINSTALLED'))
  OR (OLD.status='INACTIVE' AND NEW.status IN ('ACTIVE','UNINSTALLED'))
  OR (OLD.status='ACTIVE' AND NEW.status='INACTIVE')
)
BEGIN SELECT RAISE(ABORT, 'INVALID_HARNESS_STATUS_TRANSITION'); END;
CREATE TRIGGER harness_no_delete BEFORE DELETE ON harness_installations BEGIN
  SELECT RAISE(ABORT, 'HARNESS_HISTORY_REQUIRED');
END;
CREATE TRIGGER harness_history_no_update BEFORE UPDATE ON harness_installation_history BEGIN
  SELECT RAISE(ABORT, 'HARNESS_HISTORY_IMMUTABLE');
END;
CREATE TRIGGER harness_history_no_delete BEFORE DELETE ON harness_installation_history BEGIN
  SELECT RAISE(ABORT, 'HARNESS_HISTORY_IMMUTABLE');
END;
CREATE TRIGGER worlds_no_update BEFORE UPDATE ON worlds BEGIN
  SELECT RAISE(ABORT, 'WORLD_IMMUTABLE');
END;
CREATE TRIGGER worlds_no_delete BEFORE DELETE ON worlds BEGIN
  SELECT RAISE(ABORT, 'WORLD_IMMUTABLE');
END;
CREATE TRIGGER artifacts_identity_immutable BEFORE UPDATE ON artifacts
WHEN OLD.artifact_id IS NOT NEW.artifact_id OR OLD.kind IS NOT NEW.kind
  OR OLD.media_type IS NOT NEW.media_type OR OLD.size_bytes IS NOT NEW.size_bytes
  OR OLD.schema_version IS NOT NEW.schema_version OR OLD.created_by IS NOT NEW.created_by
  OR OLD.created_at_us IS NOT NEW.created_at_us OR OLD.parents_json IS NOT NEW.parents_json
  OR OLD.manifest_json IS NOT NEW.manifest_json
BEGIN SELECT RAISE(ABORT, 'ARTIFACT_IDENTITY_IMMUTABLE'); END;
CREATE TRIGGER artifacts_no_delete BEFORE DELETE ON artifacts BEGIN
  SELECT RAISE(ABORT, 'ARTIFACT_MANIFEST_IMMUTABLE');
END;
CREATE TRIGGER authority_grant_definition_immutable BEFORE UPDATE ON authority_grants
WHEN OLD.grant_id IS NOT NEW.grant_id OR OLD.epoch_id IS NOT NEW.epoch_id
  OR OLD.issuer_id IS NOT NEW.issuer_id OR OLD.subject_id IS NOT NEW.subject_id
  OR OLD.parent_grant_id IS NOT NEW.parent_grant_id
  OR OLD.permissions_json IS NOT NEW.permissions_json OR OLD.scope_json IS NOT NEW.scope_json
  OR OLD.constraints_json IS NOT NEW.constraints_json OR OLD.delegable IS NOT NEW.delegable
  OR OLD.delegation_depth IS NOT NEW.delegation_depth OR OLD.issued_at_us IS NOT NEW.issued_at_us
  OR OLD.expires_at_us IS NOT NEW.expires_at_us
BEGIN SELECT RAISE(ABORT, 'GRANT_DEFINITION_IMMUTABLE'); END;
CREATE TRIGGER task_frozen_fields_immutable BEFORE UPDATE ON tasks
WHEN OLD.realm_id IS NOT NEW.realm_id OR OLD.actor_id IS NOT NEW.actor_id
  OR OLD.authority_grant_id IS NOT NEW.authority_grant_id
  OR OLD.input_artifact_id IS NOT NEW.input_artifact_id
  OR OLD.serving_composition_id IS NOT NEW.serving_composition_id
  OR OLD.serving_revision IS NOT NEW.serving_revision
  OR OLD.capability_surface_revision IS NOT NEW.capability_surface_revision
  OR OLD.capability_surface_artifact_id IS NOT NEW.capability_surface_artifact_id
  OR OLD.state_snapshot_json IS NOT NEW.state_snapshot_json
  OR OLD.budget_json IS NOT NEW.budget_json OR OLD.root_action_id IS NOT NEW.root_action_id
  OR OLD.accepted_at_us IS NOT NEW.accepted_at_us OR OLD.deadline_at_us IS NOT NEW.deadline_at_us
BEGIN SELECT RAISE(ABORT, 'TASK_FROZEN_FIELDS_IMMUTABLE'); END;
CREATE TRIGGER action_identity_immutable BEFORE UPDATE ON actions
WHEN OLD.task_id IS NOT NEW.task_id OR OLD.actor_id IS NOT NEW.actor_id
  OR OLD.intent IS NOT NEW.intent OR OLD.composition_id IS NOT NEW.composition_id
  OR OLD.grant_id IS NOT NEW.grant_id OR OLD.causal_parent_action_id IS NOT NEW.causal_parent_action_id
  OR OLD.budget_json IS NOT NEW.budget_json OR OLD.created_at_us IS NOT NEW.created_at_us
BEGIN SELECT RAISE(ABORT, 'ACTION_IDENTITY_IMMUTABLE'); END;
CREATE TRIGGER invocation_identity_immutable BEFORE UPDATE ON invocations
WHEN OLD.action_id IS NOT NEW.action_id OR OLD.kind IS NOT NEW.kind
  OR OLD.target IS NOT NEW.target OR OLD.attempt IS NOT NEW.attempt
  OR OLD.input_artifact_id IS NOT NEW.input_artifact_id
  OR OLD.context_projection_id IS NOT NEW.context_projection_id
BEGIN SELECT RAISE(ABORT, 'INVOCATION_IDENTITY_IMMUTABLE'); END;
CREATE TRIGGER effect_intent_identity_immutable BEFORE UPDATE ON effect_intents
WHEN OLD.action_id IS NOT NEW.action_id OR OLD.kind IS NOT NEW.kind
  OR OLD.target_scope_json IS NOT NEW.target_scope_json
  OR OLD.payload_artifact_id IS NOT NEW.payload_artifact_id
  OR OLD.idempotency_class IS NOT NEW.idempotency_class
  OR OLD.reversibility IS NOT NEW.reversibility
  OR OLD.required_permissions_json IS NOT NEW.required_permissions_json
  OR OLD.required_features_json IS NOT NEW.required_features_json
  OR OLD.reservation_json IS NOT NEW.reservation_json OR OLD.request_id IS NOT NEW.request_id
BEGIN SELECT RAISE(ABORT, 'EFFECT_INTENT_IMMUTABLE'); END;
CREATE TRIGGER experiment_frozen_fields_immutable BEFORE UPDATE ON experiments
WHEN OLD.candidate_id IS NOT NEW.candidate_id OR OLD.baseline_id IS NOT NEW.baseline_id
  OR OLD.world_id IS NOT NEW.world_id OR OLD.criteria_artifact_id IS NOT NEW.criteria_artifact_id
  OR OLD.budget_json IS NOT NEW.budget_json OR OLD.created_at_us IS NOT NEW.created_at_us
BEGIN SELECT RAISE(ABORT, 'EXPERIMENT_FROZEN_FIELDS_IMMUTABLE'); END;
CREATE TRIGGER task_terminal_immutable BEFORE UPDATE ON tasks
WHEN OLD.status IN ('SUCCEEDED','FAILED','FAILED_RECOVERY','TIMED_OUT','CANCELLED')
  AND NEW.status IS NOT OLD.status
BEGIN SELECT RAISE(ABORT, 'TASK_TERMINAL_IMMUTABLE'); END;
CREATE TRIGGER action_terminal_immutable BEFORE UPDATE ON actions
WHEN OLD.status IN ('SUCCEEDED','FAILED','TIMED_OUT','CANCELLED') AND NEW.status IS NOT OLD.status
BEGIN SELECT RAISE(ABORT, 'ACTION_TERMINAL_IMMUTABLE'); END;
CREATE TRIGGER invocation_terminal_immutable BEFORE UPDATE ON invocations
WHEN OLD.status IN ('SUCCEEDED','FAILED','TIMED_OUT','CANCELLED') AND NEW.status IS NOT OLD.status
BEGIN SELECT RAISE(ABORT, 'INVOCATION_TERMINAL_IMMUTABLE'); END;
CREATE TRIGGER operation_terminal_immutable BEFORE UPDATE ON operations
WHEN OLD.status IN ('SUCCEEDED','FAILED','FAILED_RECOVERY','CANCELLED') AND NEW.status IS NOT OLD.status
BEGIN SELECT RAISE(ABORT, 'OPERATION_TERMINAL_IMMUTABLE'); END;
```

测试清库必须删除整个临时 data directory，不得关闭 trigger 后操作产品 DB。`seq` 分配通过同一 writer transaction 读取并更新 `realms.next_seq`；rollback 不消费 seq，允许因灾难恢复导入产生显式 gap，但正常写入不得产生 gap。

### 41.34.4 Command transaction algorithm

```text
canonicalize command payload → payload_hash；canonicalize command_id/realm/actor/grant/expected_revision/causal_parent/payload_hash → authorization_hash
BEGIN IMMEDIATE
  SELECT commands WHERE command_id
    same authorization_hash + COMMITTED → return stored result after ROLLBACK read transaction
    different authorization_hash        → IDEMPOTENCY_CONFLICT
    same authorization_hash + REJECTED   → return stored stable error
  validate schema, revision, authority and aggregate invariant
  allocate transaction_id, action_id where applicable
  mutate exactly one primary Aggregate plus required index/canonical companions
  allocate consecutive Fact seq and append Facts
  insert Outbox items with deterministic dedupe_key
  increment realms.current_meta_revision by exactly 1
  insert transactions, meta_revisions and commands(COMMITTED)
COMMIT
return persisted MutationResult
```

Schema/compatibility/revision conflict 不增加 meta revision；可单独短事务写 `commands(REJECTED, meta_revision=0)`，不得创建 Action/Fact。已通过 peer/signature authentication 后的 Authority denial 是安全事实：单一短事务写 `authority_denied` Fact、transaction/meta revision与 `commands(REJECTED, meta_revision=N)`，但不创建可执行 Action/outbox；未认证/签名失败只记内存 rate-limited metric，防止攻击者填充 ledger。暂态基础设施错误不写 commands，允许 client 使用相同 command id 重试。任何 REJECTED idempotent replay返回首次相同 error/meta revision。

## 41.35 Fact Catalog 与 Causal Edge 规则

v0.1 canonical event type 不允许 Adapter 自创；新增类型必须先加入 registry 和 payload schema。最低 catalog：

| Entity | Event types |
|---|---|
| Runtime/Realm | `runtime_initialized`、`runtime_started`、`runtime_stopping`、`readiness_changed`、`epoch_created` |
| Artifact | `artifact_registered`、`artifact_verified`、`artifact_corrupt_observed`、`artifact_accessed_restricted`、`artifact_crypto_erased` |
| Capability | `capability_defined`、`capability_validated`、`instance_transitioned`、`instance_degraded` |
| Harness | `harness_installed`、`harness_activated`、`harness_deactivated`、`harness_uninstalled`、`harness_contract_rejected`、`provider_configured`（ADR 055） |
| Composition | `composition_committed`、`reconcile_started`、`serving_switched`、`realization_completed`、`reconcile_failed`、`composition_rolled_back` |
| State | `state_revision_created`、`migration_started`、`migration_completed`、`migration_failed` |
| Authority | `principal_registered`、`grant_created`、`grant_delegated`、`grant_revoked`、`authority_denied`、`root_recovery_performed` |
| Task | `task_accepted`、`task_started`、`task_succeeded`、`task_failed`、`task_recovery_failed`、`task_cancel_requested`、`task_cancelled`、`task_timed_out` |
| Action/Invocation | `action_started`、`action_finished`、`invocation_created`、`invocation_attempted`、`invocation_finished`、`provider_cost_reserved`、`provider_cost_settled`、`provider_dispatch_authorized`（ADR 052/053：内部费用/dispatch账本，公开Provider接入仍OPEN）、`late_completion_observed` |
| Execution | `execution_submitted`、`execution_bound`、`execution_status_observed`、`execution_orphan_quarantined`、`external_effect_unknown`、`terminal_acknowledged` |
| Evolution | `proposal_created`、`candidate_created`、`experiment_started`、`evidence_recorded`、`evaluation_recorded`、`promotion_requested`、`candidate_promoted`、`candidate_rejected` |
| Operations | `outbox_dead_lettered`、`projection_rebuilt`、`security_degradation_observed`、`diagnostics_collected` |

Fact payload 只保存该事件不可缺少的标量和 Artifact references；禁止复制整个 Aggregate snapshot。每个 payload schema 要求 `schema_version=1`、`reason_code`（状态变化类）、旧/新状态（transition 类）以及相关 ID。

每 Realm Fact 使用连续 hash chain。Genesis `fact_head_hash` 是 64 个 ASCII `0`。`fact_hash = sha256("agent-meta-fact-v1\0" + prev_fact_hash + NUL + realm_id + NUL + seq-decimal + NUL + occurred_at_us-decimal + NUL + recorded_at_us-decimal + NUL + actor_id + NUL + action_id-or-empty + NUL + transaction_id-or-empty + NUL + entity_type + NUL + entity_id + NUL + event_type + NUL + schema_version-decimal + NUL + payload_hash)`；文本均 UTF-8，hash为 lowercase hex。一个 transaction写多个 Fact时按预分配 seq依次链接，最后 CAS更新 `realms.fact_head_hash`。外部 `occurred_at_us` 只用于展示/因果约束，排序仍只用 seq；不可信或超合理范围时 payload标 clock quality，但该原始值仍进入 hash防篡改。

启动 doctor 从最新 trusted checkpoint向后重算；首次/深度校验重算全链。Checkpoint Artifact记录 realm、seq、fact_hash、meta revision和可选 operator Ed25519 signature；它加速校验但不替代链。seq缺失、prev/head/hash不符立即 `INTEGRITY_ERROR`、readiness false。合法 correction只追加新 Fact；任何工具直接改旧 row都会破坏 chain并被检测。

Causal edge type registry：

```text
caused_by       entity/action → parent action
part_of         invocation/action → task or parent action
used            action/evaluation → artifact/state/evidence
produced        action/invocation → artifact/evidence
authorized_by   action/transition → grant
derived_from    artifact/state/evidence → source
evaluated_by    experiment/evidence → evaluation
promoted_to     candidate → composition
executed_as     action/invocation → execution binding
supersedes      revision/fact → prior revision/fact
```

边方向固定为“subject → referenced cause/input/result target”，查询器不得凭名称猜方向。Projection 插入 edge 时必须记录 `source_fact_id`；重复 edge 幂等。`why(entity)` 从 entity 起反向遍历 `caused_by/part_of/authorized_by/used/derived_from/executed_as`，默认 depth 8、节点 500、byte 1 MiB；截断时返回 `truncated=true` 和 continuation cursor。Projection 落后时返回 `projection_seq/current_fact_seq`，不得将不完整结果标成完整解释。

## 41.36 Provider、Tool 与 Capability Invocation SPI

### 41.36.1 Task ingress

v0.1 唯一产品 Task ingress 是 local API `Task.Submit`；`TaskProvider` 是可选 Adapter，不属于首版必需面。Daemon 使用 SQLite `tasks` 作为 durable queue，调度顺序为同 Realm `accepted_at_us, task_id` FIFO，默认单 worker、最大 pending 1000。队列满返回 `RESOURCE_EXHAUSTED`，不创建 Task。多 worker、公平调度和 priority Deferred。

### 41.36.2 Model request/response

```python
@dataclass(frozen=True)
class ModelRequest:
    invocation_id: str
    provider_id: str
    model_id: str
    context_artifact_id: str
    tool_schema_artifact_id: str
    parameters: Mapping[str, JsonValue]
    deadline_at_us: int
    max_output_tokens: int
    idempotency_key: str | None

@dataclass(frozen=True)
class ModelResponse:
    provider_request_id: str | None
    raw_bytes: bytes | None
    parts: tuple[ContentPart, ...]
    usage: Usage
    finish_reason: str
```

`parameters` v1 允许 `temperature`、`top_p`、`seed`、`stop`；未知参数由 Provider profile 声明后才能使用。Runtime test-only Conformance Provider必须按request Artifact中的fixture key返回确定性response/usage，不访问网络且不进入wheel。外部Harness的真实Provider默认视为非幂等：连接中断且无durable provider request lookup时返回`EXTERNAL_EFFECT_UNKNOWN`，Retry Policy不自动重复调用。

### 41.36.3 Tool command schema

Model-visible tool call 是严格 tagged union：

```yaml
call_id: string
operation_id: capability://name#operation
arguments: {}
expected_contract_version: string
```

Dispatcher 固定顺序：解析 JSON → 校验唯一 call_id → 查冻结 capability surface → 比较 contract version → input schema validation → Authority → Task/effect budget → Backend feature → 创建 child Action/Invocation → invoke。任一前置失败都不得进入 Adapter。并行 tool calls 在 v0.1 按响应顺序串行执行；一个失败后是否继续由外部Harness manifest中显式、带fingerprint的`stop_on_tool_error`策略决定，缺省为`true`。Tool output 先验证 output schema，再生成 Redacted Artifact；违反 schema 返回 `INVALID_RESULT` 并将 Invocation 标记 FAILED。

### 41.36.4 Capability adapter terminal semantics

Adapter 调用必须返回 `InvocationResult(status, output_bytes|error, usage, backend_ref)`，不得直接 commit Fact/State/Composition。Application Service 是唯一 terminal committer。Adapter cancellation 在 deadline 内未确认时，Application 先将 Invocation 置为 `TIMED_OUT`，随后通过 reconciliation 记录迟到状态；不可逆 effect 未知时阻止 Task 自动重试和 Candidate Promotion。

## 41.37 Composition Validation 与 capability surface

Composition validation 是纯函数 `validate(base, candidate, catalog, backend_profile) -> CompatibilityReport`，输入均以 revision/hash 冻结。检查顺序和稳定 issue code 固定为：

1. `STRUCTURE_INVALID`：slot 名唯一、引用存在、DAG 无非法 cycle、required slot 完整；
2. `ARTIFACT_INVALID`：Artifact 存在、hash/size/manifest/runtime/platform constraint 有效；
3. `INTERFACE_MISSING`：每个 requires 恰有一个 compatible provider；
4. `SCHEMA_BREAKING`：input 使用 consumer-compatible contravariance，output 使用 covariance；JSON Schema v1 仅接受可静态证明的 object/array/scalar 子集；无法证明即 breaking；
5. `EFFECT_EXPANDED`：candidate effect set 不是 baseline 子集且未显式批准；
6. `AUTHORITY_EXPANDED`：required permission/scope/budget 扩大且无新 grant；
7. `STATE_MIGRATION_MISSING`：state schema 改变但没有从 active schema 到 target 的 migration path；
8. `RETRY_SEMANTICS_BREAKING`：idempotency/retry/reversibility 变化；
9. `BACKEND_FEATURE_MISSING`：required/forbidden-to-emulate 不满足；
10. `PLACEMENT_UNSAFE`：trust class 与 placement 不兼容；
11. `BUDGET_INCOMPATIBLE`：resource minimum 超出 Composition/Realm ceiling；
12. `VALID`。

JSON Schema compatibility v1 仅支持：`type`、`properties`、`required`、`additionalProperties`、`items`、`enum`、`const`、数值/长度边界和 nullable union。`oneOf/anyOf/allOf/not`、动态 ref、自定义 format 或正则差异一律返回 `COMPATIBILITY_UNKNOWN`，在 activation 路径按 breaking 处理。Schema 使用 Draft 2020-12，所有 `$ref` 必须是同 Package 内 content-addressed reference，禁止运行时网络解析。

`CapabilitySurfaceArtifact` 是排序后的 operation descriptors、input schema hashes、display descriptions、Authority filter result 和 Backend availability 的 JCS hash。Task 接纳时生成或复用；运行时只能按该 Artifact dispatch。Description 改变也产生新 surface revision，防止模型看见的工具文本与执行 contract 不一致。

`CompatibilityReport` v1 必须包含 `report_version=1`、`base_composition_id`、`candidate_composition_id`、`catalog_revision`、`backend_profile_hash`、`validator_artifact_id`、`validated_at_meta_revision`、按 `(severity-rank, code, path, old_value_hash, new_value_hash)` 排序的 `issues[]`，以及 `activatable`。每个 issue 必须包含 `code`、`severity(ERROR|WARNING)`、RFC 6901 `path`、可空的 `old_value_hash/new_value_hash`、排序去重的 `required_permissions[]` 和 `message_template_id`；不得保存依赖 locale 的自由文本作为判定输入。任何 ERROR 使 `activatable=false`；WARNING 只允许 preferred feature degradation，并必须写 operator-visible Fact。相同冻结输入必须产生逐字节相同的 JCS report；`validated_at_meta_revision` 来自输入快照而非当前时钟。

## 41.38 Reconciler 精确提交点与失败策略

每个 desired revision 使用稳定 `reconcile_id = sha256(realm_id || desired_revision || composition_body_hash)`。所有 Backend request id 由 `reconcile_id + slot + operation + attempt-group` 派生；进程重启不得生成新 request id。单轮算法：

```text
A. 短读事务取得 refs/meta revision/desired body/bindings/checkpoint
B. 纯计算 dependency DAG 与 ReconcilePlan Artifact
C. 短写事务 CAS status → APPLYING，写 reconcile_started + outbox(plan)
D. transaction 外依 DAG 执行 validate/instantiate/migrate/health
E. 每个外部结果用独立短事务写 binding incarnation + Fact
F. 全部 required slot ready 后，短写事务同时：
   CAS expected serving → desired
   写 serving_switched Fact
   将新 binding 标 ACTIVE
   status 保持 APPLYING
G. transaction 外 drain/release 只属于旧 serving 的 instance
H. 短写事务 CAS realized → serving，status → READY，写 realization_completed，推进 checkpoint
```

崩溃恢复判定：

| Crash point | 恢复行为 |
|---|---|
| A–C 前 | refs 未变；重新计划 |
| C 后、提交 Backend 前 | 重放相同 outbox/dedupe key |
| Backend 已执行、E 前 | `reconcile` 找到 request id，登记新 incarnation，不重建 workload |
| E 后、F 前 | 新 instance 保持 INACTIVE；继续 health/CAS，旧 serving 接流量 |
| F 后、G 前 | 新 Task 使用新 serving；旧 Task 仍冻结旧版本；继续 drain |
| G 后、H 前 | 根据 binding/facts 证明旧独占 instance 已 release，再推进 realized |
| 状态无法证明 | refs 不猜测；status → UNKNOWN，readiness false，doctor 给出修复计划 |

失败策略固定为：validation/migration/health/required feature 失败时 status `FAILED`、serving/realized 保持原值；瞬态 Backend 错误最多按 1/2/4/8/16 秒重试 5 次，使用 stable request id；之后 `FAILED`。serving CAS 冲突立即废弃当前 Plan 并基于新 refs 重算，不继续 drain。drain 超时默认 30 秒，随后 Portable trusted instance force terminate 并写 `release_forced`；Managed/untrusted 由 Backend policy 处理。realized 只在所有旧独占 binding 已 terminal/released 或明确标记 quarantined 后更新。

Outbox worker lease 30 秒，每 10 秒续租；进程失联后其他轮次可在 lease expiry 后接管。单进程 v0.1 仍实施 lease，确保 crash test 与未来实现一致。超过 20 次或持续 24 小时的 item 进入 `DEAD_LETTER`，readiness 对 critical reconcile/outbound effect 为 false，对 non-critical telemetry 保持 true。

Outbox `dedupe_key = sha256(kind + NUL + realm_id + NUL + semantic_entity_id + NUL + transition_revision_or_request_id + NUL + payload_hash)`。固定 kind：`RECONCILE_REQUEST/EXECUTION_SUBMIT/TERMINAL_ACK/PROJECTION_ADVANCE/OPERATION_RUN`；同一 semantic transition只能有一个 key。Dispatcher取得 lease时不改变业务 Aggregate，只更新 outbox lease；delivery成功后短事务标 DELIVERED并写必要 Fact。Backend timeout不等于 delivery失败：EXECUTION_SUBMIT必须 Inspect/Reconcile同 request id后再决定重试。

## 41.39 配置、目录、锁与发布规格

### 41.39.1 路径和配置

默认 data directory：Linux `${XDG_STATE_HOME:-$HOME/.local/state}/agent-meta`，macOS `$HOME/Library/Application Support/agent-meta`，Windows `%LOCALAPPDATA%\agent-meta`。所有相对路径相对于配置文件目录解析；CLI 显式路径先 absolute normalize，再做 workspace/policy 检查。环境变量统一前缀 `AGENT_META_`，嵌套键使用双下划线，例如 `AGENT_META_STORE__BUSY_TIMEOUT_MS`。未知配置键、类型错误或同一 secret 同时由多个来源提供时启动失败。

配置加载后写 `effective-config.redacted.json`，采用 JCS 和 `config_fingerprint`；secret value 替换为 `{source, handle, present}`。热更新 v0.1 仅支持 log level 和 metrics export interval；其他变化要求 graceful restart。

### 41.39.2 daemon lock 与 shutdown

Public API 1.1管理面实现见[ADR 035](adr/035-local-daemon-lifecycle.md)：公开`Runtime.Stop`
使用现有CommandRequest/MutationResponse，签名payload固定`instance_id,reason_code`，要求
`runtime.admin.stop`。Hello返回的实例身份经SDK暴露；旧停止命令可恢复原回执但不能停止新实例。
`agent-meta start`以前台方式持锁运行，`info`发现实际连接实例，`stop`提交签名请求；
没有绑定真实执行Host时不得仅凭持久refs宣布serving ready。

`<data_dir>/run/daemon.lock` 使用 OS advisory exclusive lock，文件内容为 instance id、pid、process start identity 和 endpoint。不得仅用 PID 文件判断所有权。无法获取锁时 daemon 返回 exit code 12/`ALREADY_RUNNING`。`init` 与 offline migration 必须获得同一锁；CLI read/write 只经 daemon。

Graceful shutdown 顺序：停止 Task ingress → 等待 running Task 最多 `shutdown_grace_s=30` → 请求取消 → 停止 dispatcher/reconciler 新租约 → flush terminal commits/checkpoints → close Backend session → checkpoint WAL → 释放 lock。超时 exit 仍保留可恢复状态。exit code：0 正常；2 配置；3 schema/integrity；4 Authority/credential；5 Backend negotiation；12 已运行；70 内部错误。

### 41.39.3 Python package 与 dependency policy

发行一个 `agent-meta-runtime` wheel，要求 CPython 3.12。Python源码根目录固定为`src/agent_meta_runtime/`，公共import namespace固定为`agent_meta_runtime`，console script固定为`agent-meta`；不得同时安装兼容别名`agent_meta`，避免与泛化的metadata模块冲突。语言中立Protobuf package继续使用`agent_meta.transport.v1`、`agent_meta.public.v1`和`agent_meta.execution_backend.v1`，其名称不等于Python import namespace；生成的Python代码必须置于`agent_meta_runtime.protocols.*`下。Runtime extras固定为`[ipython]`、`[otel]`、`[dev]`，不得提供依赖Seed或具体Model Provider的`[seed]`/`[providers]` extra；Core/SQLite/InMemory不依赖extras，Conformance Provider只存在于test fixture。所有发布wheel使用hash-locked dependency file、SBOM和provenance；CI在Linux/Windows从空环境安装wheel后运行smoke E2E。禁止启动时自动`pip install`；Capability dependency必须在staging/build阶段解析为独立environment Artifact。

版本采用 SemVer：0.x minor 可改变实验 API，但 `public-api/v1`、Fact schema v1 与 Backend protocol v1 在同一 minor 支持周期内不得 breaking。数据库升级只允许相邻版本逐步 forward migration；启动发现 DB 新于 runtime 时只读 diagnostics，readiness false。

## 41.40 验收环境、Fixture 与可重复性

v0.1 release gate 使用以下固定逻辑环境；具体 OS patch 与依赖 hash 记录在当次 release manifest，不写死在 ontology：

```text
Linux latest supported LTS runner + CPython 3.12
Windows current supported runner + CPython 3.12
macOS smoke runner + CPython 3.12（non-blocking）
filesystem: local disk, free space >= 2 GiB
fake clock/id/model/backend seeds: 0xA63E7A
timezone/locale: UTC / C.UTF-8（Windows 使用 invariant culture）
```

Golden fixtures 必须纳入仓库且禁止由测试运行时自动覆盖：Artifact packages、JCS payload/hash、UUID/sequence、Fact payload、API/Backend protobuf bytes、CompatibilityReport、Context Projection、redaction、migration、why graph。更新需要显式 review label `golden-change` 和变更原因。

Fault injection points 使用稳定名称：

```text
commit.after_command_claim
commit.after_domain_row
commit.after_fact
commit.after_outbox
commit.before_sqlite_commit
artifact.after_fsync_file
artifact.after_publish_before_register
reconcile.after_submit_before_binding
reconcile.after_binding_before_serving_cas
reconcile.after_serving_cas_before_drain
reconcile.after_drain_before_realized
task.after_terminal_row_before_fact
backend.after_create_before_response
```

SQLite transaction 内的 injection 通过进程终止验证原子性；不能只抛 Python exception。Windows 使用强制终止进程，Linux 使用 SIGKILL。每个恢复测试使用独立 absolute temp data directory，测试结束只删除已验证位于 test root 内的目录。

Runtime Release判定必须同时满足：所有blocking CI；第41.33 traceability检查；AC-M01～M09B、M12～M16、M18～M47、M49～M54；安装/升级/备份/恢复演练；性能基线无未批准回退。AC-M10/M11为Deferred；AC-M17/M48为External-Seed，不得计入Runtime release成功或失败。

## 41.41 Protobuf Envelope 与 v1 Field Registry

Public API 与 Backend ABI 共用 framing，但使用不同 package。`.proto` 必须保留下列 field number；字段只允许新增，不复用已删除编号：

```proto
syntax = "proto3";
package agent_meta.transport.v1;

message RpcEnvelope {
  uint32 protocol_major = 1;       // v1 固定 1
  uint32 protocol_minor = 2;
  string request_id = 3;           // UUIDv7；response 原样返回
  string method = 4;               // registry 中的完整方法名
  int64 deadline_at_us = 5;        // 0 表示 server 默认，不能表示无限
  map<string,string> trace = 6;    // 只允许 traceparent/tracestate
  oneof body {
    bytes payload = 7;             // 对应 method request/response protobuf
    RpcError error = 8;            // response error 时设置
  }
  bool is_response = 9;
}

message RpcError {
  string code = 1;
  bool retryable = 2;
  string message_safe = 3;
  uint32 details_schema_version = 4;
  bytes details_jcs = 5;
  string correlation_id = 6;
}

message HelloRequest {
  repeated VersionRange supported = 1;
  string client_instance_id = 2;
}
message HelloResponse {
  uint32 selected_major = 1;
  uint32 selected_minor = 2;
  string server_instance_id = 3;
  int64 server_time_us = 4;
  uint32 max_frame_bytes = 5;
}
message VersionRange {
  uint32 major = 1;
  uint32 min_minor = 2;
  uint32 max_minor = 3;
}
```

Backend package 核心字段：

```proto
package agent_meta.execution_backend.v1;

message ClientHello {
  repeated agent_meta.transport.v1.VersionRange supported = 1;
  string client_instance_id = 2;
  repeated string required_features = 3;
  repeated string optional_features = 4;
}
message BackendSession {
  uint32 protocol_major = 1;
  uint32 protocol_minor = 2;
  string backend_id = 3;
  string session_id = 4;
  string profile = 5;              // PORTABLE|MANAGED|DISTRIBUTED
  bytes features_jcs = 6;
  bytes limits_jcs = 7;
  int64 established_at_us = 8;
}
message ExecutionRequest {
  string session_id = 1;
  string realm_id = 2;
  string request_id = 3;
  string operation_kind = 4;
  string payload_hash = 5;
  bytes payload_jcs = 6;
  string idempotency_class = 7;
  string reversibility = 8;
  string dedupe_scope = 9;
  int64 requested_retention_us = 10;
  int64 deadline_at_us = 11;
  bytes authority_token = 12;       // 日志/Fact 必须丢弃
}
message ExecutionHandle {
  string backend_id = 1;
  string session_id = 2;
  bytes opaque_handle = 3;
  uint64 incarnation = 4;
  int64 expires_at_us = 5;
  string request_id = 6;
}
message ExecutionResult {
  string status = 1;
  string request_id = 2;
  oneof outcome {
    string result_artifact_id = 3;
    bytes error_jcs = 5;
  }
  bytes usage_jcs = 4;
  string result_hash = 6;
  int64 completed_at_us = 7;
  bool effect_state_unknown = 8;
}
message ExecutionSnapshot {
  ExecutionHandle handle = 1;
  string status = 2;
  bytes usage_jcs = 3;
  int64 observed_at_us = 4;
  ExecutionResult terminal = 5;
}
message CancelRequest { ExecutionHandle handle = 1; string mode = 2; int64 deadline_at_us = 3; }
message CancelReport { string status = 1; bool terminal_confirmed = 2; bytes details_jcs = 3; }
message ReconcileRequest { string session_id = 1; string realm_id = 2; repeated KnownBinding known = 3; }
message KnownBinding { string semantic_id = 1; string request_id = 2; ExecutionHandle handle = 3; string payload_hash = 4; }
message ReconcileReport { repeated ReconciledBinding bindings = 1; repeated OrphanWorkload orphans = 2; int64 observed_at_us = 3; }
message ReconciledBinding { KnownBinding known = 1; string status = 2; ExecutionHandle renewed_handle = 3; ExecutionResult terminal = 4; }
message OrphanWorkload { ExecutionHandle handle = 1; string request_id = 2; string payload_hash = 3; string recommended_action = 4; }
message TerminalAck { string session_id = 1; string request_id = 2; string result_hash = 3; }
message AckReport { string status = 1; int64 retained_until_us = 2; }
```

空 string 不表示 optional identity；写路径必须按 schema 检查 required。`authority_token` 在收到后只允许传给 enforcement layer，serialization debug/repr 必须输出 `[REDACTED]`。`payload_hash` 是 `payload_jcs` 的 lowercase SHA-256；Backend 必须重算验证。v1 `Await` 是普通 request/response：server 等待到 terminal 或 envelope deadline，未 terminal 返回 `DEADLINE_EXCEEDED` 加当前 typed snapshot；client 之后可重试相同 Await，不重新 Submit。

Public method registry 精确为：

```text
agent_meta.public.v1.Runtime.GetInfo
agent_meta.public.v1.Runtime.GetView
agent_meta.public.v1.Runtime.Doctor
agent_meta.public.v1.Runtime.GetMetrics
agent_meta.public.v1.Task.Submit
agent_meta.public.v1.Task.Get
agent_meta.public.v1.Task.Wait
agent_meta.public.v1.Task.Cancel
agent_meta.public.v1.Artifact.BeginPut
agent_meta.public.v1.Artifact.PutChunk
agent_meta.public.v1.Artifact.Put
agent_meta.public.v1.Artifact.GetManifest
agent_meta.public.v1.Artifact.Verify
agent_meta.public.v1.Capability.Register
agent_meta.public.v1.Capability.Get
agent_meta.public.v1.Capability.List
agent_meta.public.v1.Harness.ValidatePackage
agent_meta.public.v1.Harness.Install
agent_meta.public.v1.Harness.Get
agent_meta.public.v1.Harness.List
agent_meta.public.v1.Harness.Activate
agent_meta.public.v1.Harness.Deactivate
agent_meta.public.v1.Harness.Uninstall
agent_meta.public.v1.Composition.Validate
agent_meta.public.v1.Composition.Commit
agent_meta.public.v1.Composition.GetRefs
agent_meta.public.v1.State.Create
agent_meta.public.v1.State.Get
agent_meta.public.v1.State.Write
agent_meta.public.v1.Authority.Inspect
agent_meta.public.v1.Authority.Grant
agent_meta.public.v1.Authority.Delegate
agent_meta.public.v1.Authority.Revoke
agent_meta.public.v1.Evolution.Propose
agent_meta.public.v1.Evolution.CreateCandidate
agent_meta.public.v1.Evolution.RunExperiment
agent_meta.public.v1.Evolution.GetExperiment
agent_meta.public.v1.Evolution.WaitExperiment
agent_meta.public.v1.Evolution.Promote
agent_meta.public.v1.Evolution.Rollback
agent_meta.public.v1.Scratch.Create
agent_meta.public.v1.Scratch.Get
agent_meta.public.v1.Scratch.Execute
agent_meta.public.v1.Scratch.Bindings
agent_meta.public.v1.Scratch.Inspect
agent_meta.public.v1.Scratch.ExportCandidate
agent_meta.public.v1.Scratch.Release
agent_meta.public.v1.Graph.Why
agent_meta.public.v1.Graph.Lineage
agent_meta.public.v1.Operations.Backup
agent_meta.public.v1.Operations.Get
agent_meta.public.v1.Operations.Wait
agent_meta.public.v1.Operations.GcPlan
agent_meta.public.v1.Operations.GcApply
agent_meta.public.v1.Operations.RetryOutbox
agent_meta.public.v1.Operations.Reconcile
agent_meta.public.v1.Operations.RebuildProjection
```

`Runtime.Start/Stop` 不作为普通 RPC：Start 是 daemon process lifecycle；Stop 仅由 CLI 在持有 `runtime.admin.stop` 时发送内部 admin method，默认 CLI 不展示。`Artifact.Put` 不把文件路径传给 daemon，而是 client 读取 bytes、按最多 1 MiB chunk 发送 `BeginPut/PutChunk/FinishPut` 子协议；每 chunk 带 index/hash，Finish 带总 size/canonical ArtifactId。断线 staging 保留 1 小时后 GC。

### 41.41.1 Normalized content types

`ContentPart` 是 tagged union：`text{text_utf8}`、`json{value_jcs}`、`artifact{artifact_id,media_type}`、`tool_call{call_id,operation_id,arguments_jcs,expected_contract_version}`、`tool_result{call_id,status,artifact_id,error_jcs}`。v0.1 不在公共 DTO 内嵌图片/音频 bytes。`Usage` 固定字段为 input/output/total tokens、cached input tokens、reasoning tokens、cost microunits、provider-reported flag；未知值用 presence flag，不用负数。`finish_reason` registry 为 `STOP/LENGTH/TOOL_CALL/CONTENT_FILTER/CANCELLED/ERROR/UNKNOWN_PROVIDER_VALUE`，后者同时保存 sanitized provider value hash。

## 41.42 Core Schema Registry 与 Composition Validation

### 41.42.1 Capability Contract v1

```yaml
schema: capability-contract/v1
capability_id: capability://planner
contract_version: 1.0.0
operations:
  - operation_id: plan
    input_schema_artifact_id: artifact://sha256/...
    output_schema_artifact_id: artifact://sha256/...
    idempotency: NONE                 # NONE|KEYED|PURE
    retry_semantics: NEVER            # NEVER|SAME_KEY_TRANSIENT
    effects: [model.invoke]
    required_permissions: [capability.invoke]
requires:
  - interface_id: model.invoke
    version_range: ">=2.0.0 <3.0.0"
provides:
  - interface_id: planner.plan
    version: 4.0.0
state:
  schema_artifact_id: artifact://sha256/...
  migration_artifact_ids: []
execution_requirements: {}
runtime_constraints: {}
```

SemVer range 只允许 comparator conjunction，不支持 OR、wildcard、pre-release 隐式匹配；parser 行为由 golden vectors 固定。Schema 使用 JSON Schema Draft 2020-12 的受限 profile：运行时 validation 允许 type/properties/required/items/enum/const/oneOf/allOf/$defs/$ref（仅同 Artifact fragment）；兼容性比较时 oneOf/allOf 只有 schema hash 完全相同才直接兼容，否则按 41.37 返回 `COMPATIBILITY_UNKNOWN`。禁止 remote `$ref`、动态 anchor、执行自定义代码的 format，以及可能灾难性回溯的正则表达式。`additionalProperties` 未写时按 `false`，避免输入面静默扩大。Regex validation 使用有时间/长度预算的安全实现；无法保证时拒绝包含 pattern 的外部 schema。

Effect registry v1：

```text
none
model.invoke
filesystem.read / filesystem.write
network.request
process.spawn
credential.use
state.read / state.write
external.reversible / external.irreversible
```

未知 effect 是 breaking/required-unknown，validation fail closed。`PURE` operation 必须 effects 仅为 `none/state.read` 且不读取 wall clock/random/opaque state；`KEYED` 必须接收 idempotency key；`NONE` 不自动重试。

### 41.42.2 Composition v1

```yaml
schema: composition/v1
composition_id: composition://...
realm_id: realm://main
revision: 82
parent_id: composition://...
slots:
  planner:
    capability_id: capability://planner
    descriptor_revision: 4
    artifact_id: artifact://sha256/...
    criticality: REQUIRED             # REQUIRED|OPTIONAL
    degradation_policy: REJECT_TASK   # REJECT_TASK|OMIT|FALLBACK
    fallback_slot: null
wiring:
  - consumer_slot: planner
    requirement_interface: model.invoke
    provider_slot: model
    provider_interface: model.invoke
state_bindings: {}
authority_bindings: {}
execution_requirements: {}
policy_artifact_ids: []
```

Slot 名匹配 `[a-z][a-z0-9_-]{0,63}`。`REQUIRED` 只能使用 `REJECT_TASK` 或合法 fallback；`OPTIONAL` 可 `OMIT`。fallback 不得成环且必须提供相同 compatible interface。每个 require 必须恰有一个 wiring，除非 contract 标记 optional。生命周期 dependency graph 使用 consumer → provider，拓扑实例化时反向排序（provider first），drain 时正向；存在环即 validation ERROR。动态 runtime recursion 不通过 wiring 表达。

Compatibility algorithm 顺序固定：

1. 解析所有 ID、Artifact integrity、schema/profile；
2. 验证 slot 唯一性、Capability/artifact/descriptor 三者绑定；
3. 对每个 wiring 检查 interface id 完全相等与 SemVer range；
4. 使用 JSON Schema compatibility：candidate input 可接受 baseline 的全部有效输入；candidate output 必须仍满足 baseline output；不能证明即 breaking；
5. candidate effect/permission/required Backend feature 集合不得扩大，除非 ChangeSet 明确列出且 Promotion grant 覆盖新增项；
6. state schema 相同时直接兼容；不同时必须存在 source→target Migration Artifact；
7. `PURE→KEYED/NONE`、`KEYED→NONE`、retry 变宽均 breaking；
8. 检查 fallback、dependency DAG、placement/trust class；
9. 生成路径稳定排序的 `CompatibilityReport`。

“Schema 可接受集合”一般不可判定，因此 v0.1 使用保守 syntactic rules：删除 input required、增加 optional input property、扩大 enum/range 为 compatible；新增 input required、删除 property、缩小 enum/range 为 breaking。Output 方向相反。使用 oneOf/allOf 或无法比较的 constraint 时返回 `COMPATIBILITY_UNKNOWN` ERROR，必须由 version bump + explicit migration/adapter 解决，不能人工点选忽略。

### 41.42.3 Error code 完整 registry

除 41.14 外，v0.1 增加：

| Code | Retry | Meaning |
|---|---:|---|
| `INVALID_RESULT` | 否 | Adapter output 不满足 contract |
| `NOT_FOUND` | 否 | canonical object 不存在或无权暴露其存在 |
| `ALREADY_EXISTS` | 否 | 非幂等 identity 冲突 |
| `ALREADY_RUNNING` | 否 | data directory 已有 daemon owner |
| `FAILED_PRECONDITION` | 修复后 | 当前 lifecycle/readiness 不允许操作 |
| `COMPATIBILITY_UNKNOWN` | 否 | 无法证明 contract compatibility |
| `CONTRACT_INCOMPATIBLE` | 否 | Harness声明的协议范围与Runtime不相交 |
| `NO_SERVING_COMPOSITION` | 否 | 尚未激活任何Harness Composition |
| `SERVING_NOT_READY` | 是 | desired/serving/realized尚未安全收敛 |
| `KEY_UNAVAILABLE` | 修复 key 后 | Restricted Artifact key 无法取得 |
| `DATA_LOSS` | 否 | durable content 缺失或无法恢复 |
| `INTERNAL` | 视 details | 已脱敏的未分类实现错误 |

同一安全域内 `NOT_FOUND` 同时用于不存在和无读取权限的敏感对象，防止枚举；管理员 diagnostics 可在授权后查看内部 reason hash。

## 41.43 Evolution v0 Deterministic Baseline

v0.1 实现 Proposal/ChangeSet/Candidate/Experiment/Evaluation/Promotion，但不实现自动搜索策略。对象最小 schema：

```text
Proposal: id, hypothesis, source_evidence_ids, target_composition_id, proposer, created_at
ChangeSet: id, proposal_id, baseline_id, operations[], expected_serving_revision
Candidate: id, change_set_id, composition_id, trust_class, artifact_ids[], status
World: id, backend_profile_hash, fixture_artifact_ids[], env_policy, seed, replay_level
Experiment: id, candidate_id, baseline_id, world_id, criteria_artifact_id, budget, status
Evidence: id, experiment_id, producer_action_id, kind, subject_id, artifact_id, observed_at
Evaluation: id, experiment_id, evaluator_artifact_id, evidence_ids[], assertion_results[], decision
```

ChangeSet operation 是 tagged union：`ADD_SLOT/REMOVE_SLOT/REPLACE_ARTIFACT/REWIRE/BIND_STATE/BIND_AUTHORITY/SET_POLICY`；每项带 target path、expected old value hash 与 new value。应用操作前按 path 排序但保留 author order 用于审计；同一路径多次写入拒绝。ChangeSet 只生成新 Composition，不修改 baseline。

Runtime的deterministic evolution baseline使用`deterministic-evaluation/v1` assertions：

```yaml
assertions:
  - kind: artifact_integrity
  - kind: compatibility_report
    require_activatable: true
  - kind: test_suite
    suite_artifact_id: artifact://sha256/...
    required_pass_rate_ppm: 1000000
  - kind: security_policy
    allow_high_findings: 0
  - kind: budget
    max_wall_time_us: 300000000
    max_cost_microunits: 0
decision_rule: ALL_REQUIRED_PASS
```

v0.1 没有统计显著性推断。可选 metric assertion 必须声明方向、baseline value、candidate value、absolute/relative threshold 与 sample count；缺值为 fail，不用默认 0。Evaluation 只读取冻结 Evidence，按 criteria 顺序产生 assertion results；任一 required assertion fail 或 unknown，decision 为 REJECT。Evaluator 自身的异常产生 FAILED Evaluation，不产生 ACCEPT/REJECT。

World v1固定字段：`backend_profile_hash, fixture_artifact_ids, state_snapshot_ids, environment_allowlist, network_policy=DENY, credential_handles=[], workspace_quota, process/model/effect budget, seed, replay_level`。v0.1 Candidate Experiment仅允许 fake Model和 deterministic fixtures；baseline先在fresh cloned state/workspace运行，candidate再在另一fresh clone以相同seed运行，二者不得共享live process/cache/temp文件。顺序固定用于可重复性，不做性能无偏推断；性能metric只作工程观察，除非criteria明确允许。World任一required constraint未被Backend `SUPPORTED`满足则Experiment INVALID，不降级。

`security_policy` assertion v1由内建 deterministic package/AST scanner实现，不调用网络服务：验证 AMPAK/path/hash、无 native binary/extension/symlink；Python AST拒绝动态 `eval/exec/compile/__import__`、`ctypes/cffi`、`subprocess/os.system`、`socket`、非 allowlist import、修改 `sys.path/modules` 和访问 private `agent_meta_runtime` module。Finding severity/code/path/node hash写 Evidence。该 scanner只决定是否满足 `trusted_candidate` policy，不宣称证明代码安全；扫描无法解析或存在动态语法即 HIGH/REJECT。请求更高权限的 Candidate归类 untrusted并要求 Managed strong isolation。

Promotion 的唯一入口是 `Evolution.Promote`：重跑 Artifact/Compatibility/Authority/unknown-effect/expected-serving gate；事务只提交 desired Composition 和 outbox，不直接设置 serving。Rollback 创建指向父 Composition 的新 desired transition，不删除已 promotion 的 revision。Candidate archive 是状态变化，不删除 Artifact/Evidence。

## 41.44 Managed State、RuntimeView、Reflection 与 Context 默认算法

### 41.44.1 Managed State MVCC

`managed_states` 保存可变 CAS ref，`state_revisions` 保存不可变内容。Composition binding 指定 `state_id + required_schema_id + access(READ|READ_WRITE)`，不指向“最新”字符串。Task 接纳事务读取每个 state ref 并把 `{state_id: state_revision_id}` 保存进 Task budget/snapshot manifest；Task 普通 read 始终使用冻结 revision，自己的成功 write 通过 task-local overlay 可见。

写 State 命令必须含 `expected_state_revision_id`。事务校验 schema、Authority、当前 ref 与 expected 相等，登记新 Artifact/revision、CAS `managed_states.current_revision_id/cas_revision`、Fact、`state_ref_history` 和 outbox；冲突返回 `REVISION_CONFLICT`，不自动 merge。Composition ref 每次变化同样在事务内写 `composition_ref_history`。v0.1 revision 单父，不支持 CRDT/多父 merge。Task 结束不自动批量 commit 未提交 overlay；每次写都是独立 durable command。Experiment 从 baseline revision clone 新 state_id，禁止写 production state_id。

Serializer v1：JSON state 使用 JCS 和 JSON Schema；binary state 必须声明 media type、serializer Artifact、serializer version 和 architecture portability。Pickle、marshal、任意 Python object graph 不允许作为 portable Managed State；只能标记 Opaque，并提供 impact/backup/recovery policy。Migration 按 41.31。

Public execution SPI 1.11依[ADR 060](adr/060-task-scoped-meta-resource-host.md)增加
`ArtifactRead/ArtifactPut/StateRead/StateWrite/ResourceReceipt/ResourceAdapter`。
`HarnessAdapter.resource_tools`通过纯计划与回执normalization绑定资源operation；
签名descriptor和冻结Surface含`resource_contract`（Capability Contract 1.1）。
Root先验证Actor和冻结安装代Service的capability与实际resource scope，再预留一次
budget/grant use；Meta写入、child Action、Invocation terminal和provenance Fact原子提交。
confirmed replay不再运行回调、不再写State或重复计数。`artifact.put`进入effect registry；
PURE `state.read`计tool step而不计mutation effect。State写入还校验源Artifact种类的读取权限。
State Realm归属来自不可变initial revision Fact；冻结View记录CAS revision，读取只使用
冻结revision或本Task已提交overlay，写入严格CAS且不merge。会话transcript/journal State
的保留purpose来自birth Fact；普通模型工具不能写入。JSON/UTF-8内容及结果上限1 MiB，
normalize/schema → frozen redaction → schema验证均在publication之前完成。缺失serializer、
restricted内容或Scratch placement能力时fail closed；这些入口不声明Managed隔离或RP-04关闭。

普通PURE callback工具依[ADR 062](adr/062-tool-child-actions-and-execution-bindings.md)同样
在admission事务内创建独立child Action；Invocation的part_of/produced与child的
caused_by/authorized_by/used构成因果链。InMemory execution token绑定实际child，
model仍绑定Task root；Root签发前和授权提交时验证同一Task/Actor/Realm/Composition/
target/parent及已验证token的预期Action。完成重放复用原child；失败、取消和UNKNOWN
恢复终止child，不遗留RUNNING Action。旧的已确认root-bound结果保持历史身份。

### 41.44.2 RuntimeView snapshot

`GetView` 在一个 SQLite read transaction 中先读取 `realms.current_meta_revision` 和 `realms.next_seq-1`，再读取 refs、Composition、capabilities、state refs、Authority summary、Backend profile snapshot 与 readiness。返回：

```text
realm_id / epoch_id / meta_revision / fact_boundary_seq
desired/serving/realized revision + composition ids
capability_surface_revision + artifact id
state_revision_bindings
authority_summary_artifact_id
backend_profile_hash / session id / observed_at
core_ready / serving_ready / core_reasons / serving_reasons
projection checkpoints
```

Backend live data不属于同一 SQLite snapshot，必须携带 `observed_at_us` 和 session id；超出 `backend_snapshot_max_age_ms=1000` 时标记 `STALE`，不得伪称原子一致。`GetView(revision=N)` 从 `composition_ref_history/state_ref_history` 读取最近不晚于 N 的 committed ref，并读取当时已存在的 immutable rows/Facts；不查询当前 Backend live state。若 N 不存在于 `meta_revisions` 返回 `NOT_FOUND`，不近似到其他 revision。

### 41.44.3 Safe Python reflection

Reflection 对 Managed DTO 直接读取 frozen fields；对 Observed Python object 只允许：`type(obj)`、`id` 的 session-scoped opaque token、`object.__getattribute__(obj, '__dict__')` 在 builtin dict 情况下的 key snapshot、`inspect.getattr_static` 和明确白名单 builtin container 的有界遍历。禁止调用 `repr/str/bool/len/iter/getattr` 的用户 override、descriptor、property、`__getattr__`、generator next 或 async hook。

可直接渲染的值仅为 None/bool/int/受限 float/str/bytes metadata 以及 exact builtin `list/tuple/dict/set/frozenset`；subclass 一律 opaque。str 最长 4096 code points，bytes 只返回 size/hash/前 0 bytes，container 默认最多 100 项并稳定排序 scalar dict key；不能稳定排序时保留 snapshot insertion order 并标记 non-deterministic。达到 depth/item/byte/time 任一 budget 即返回 `TRUNCATED`，包含 consumed budget；异常转为 opaque reason hash，不执行 fallback repr。

Observed registry 使用 weakref；不可 weakref 对象只在一次 request stack 内存在，不进入全局 registry。`observe` 只记录 type、origin Action、impact 声明和 weak handle。Promotion 必须导出 source/package bytes，不允许把 live object pointer 变成 Artifact。IPython Scratch 被视为 trusted exploration，不是 security sandbox；untrusted code 必须转 Candidate 并按 41.32 执行。

### 41.44.4 Seed Context Projection v1

默认 context budget 按以下顺序和上限确定，未用额度向下一段滚动：

```text
system/constitution       min(20%, required full; overflow => reject)
task input                min(30%, tail-truncate only if task policy permits)
capability/tool schema    min(20%, required selected operations full)
state/runtime summary     min(15%)
causally relevant facts  remaining up to 15%
```

选择 Fact：从 Task causal parent、绑定 State、serving Composition 相关 entity 开始，按 causal graph breadth-first depth 4；排序键为 causal distance asc、realm seq desc、fact id asc；去重后按 budget 截断。State summary renderer、Fact renderer、tokenizer 和 redaction policy 都必须是 Artifact。Tokenizer 必须使用 Provider profile 指定的 exact tokenizer；不可用时 Task 在 model invocation 前返回 `FAILED_PRECONDITION`，不以字符数猜 token。

Normalize 只接受 schema-known fields；Redact 在 Rank 前执行，防止 secret 影响排序摘要。Render section 之间使用固定 UTF-8 delimiter，并把每段 output Artifact/hash/token count 写入 Projection Manifest。相同 source revisions、policy、tokenizer、budget 必须产生相同 Redacted Projection Artifact。

## 41.45 EffectIntent、Budget 与外部副作用

EffectIntent v1：

```yaml
effect_intent_id: effect-intent://<uuidv7>
action_id: action://...
kind: filesystem.write
target_scope: {workspace_id: workspace://...}
payload_artifact_id: artifact://sha256/...
idempotency_class: KEYED          # PURE|KEYED|NONE
reversibility: REVERSIBLE         # REVERSIBLE|COMPENSATABLE|IRREVERSIBLE|UNKNOWN
required_permissions: [filesystem.write]
required_backend_features: []
budget_cost: {effects: 1, cost_microunits: 0}
compensation_artifact_id: null
```

提交顺序固定：validate schema → resolve canonical target → Authority → budget reservation → Backend features → commit Action/Intent/outbox → execute outside transaction → commit result/Fact → settle reservation。Validation/Authority 失败不消耗 budget；成功 reservation 后即计入 effect count，重试相同 request id 不重复计数。实际 cost 超过 reservation 时记录 overrun 并阻止后续 effect；不得回写降低已消费值。

`REVERSIBLE` 必须能在同一 Backend 中通过 stable inverse request 恢复；`COMPENSATABLE` 只承诺业务补偿且必须提供 compensation Artifact；`IRREVERSIBLE/UNKNOWN` 默认要求显式 `effect.execute.irreversible` grant、Managed Backend 和 operator-visible intent preview。Portable v0.1 拒绝高风险 irreversible effect。Rollback 只回滚 semantic serving/state refs；external effect 只能记录 compensation outcome，不能宣称时间倒流。

Filesystem target 必须在 workspace root 下通过 handle-relative/openat 类机制解析；仅做字符串 prefix 检查不合格。拒绝 symlink/reparse-point escape、device path、ADS 和 case-fold collision。Network v0.1 默认 deny；启用时 destination 必须是 policy Artifact 中的 scheme/host/port allowlist，解析后 IP 仍需检查 private/link-local policy，redirect 每跳重新授权。Credential 永不作为 payload bytes，由 scoped credential handle 使用。

## 41.46 写命令 Payload Registry

所有写命令外层使用 41.4.3 `CommandEnvelope`；`payload_type` 与 payload required fields 固定如下：

| payload_type | Required payload fields |
|---|---|
| `task.submit/v1` | `input_artifact_id, budget, deadline_at_us, requested_capabilities[]` |
| `task.cancel/v1` | `task_id, mode(GRACEFUL|FORCE), reason_code` |
| `artifact.put/v1` | `kind, media_type, expected_sha256, expected_size, source_staging_handle, parents[]` |
| `capability.register/v1` | `capability_id, descriptor_artifact_id, expected_descriptor_revision` |
| `harness.install/v1` | `manifest_artifact_id, package_artifact_id, expected_meta_revision` |
| `harness.activate/v1` | `harness_id, composition_body_artifact_id, grant_requests_artifact_id, expected_meta_revision, expected_serving_revision` |
| `harness.configure-provider/v1` | `harness_id, capability_id, profile_artifact_id, credential_handle, enabled, expected_configuration_revision`；envelope required `expected_meta_revision`；当前Epoch Root operator专用（ADR 055） |
| `harness.deactivate/v1` | `harness_id, expected_meta_revision, expected_serving_revision, reason_code` |
| `harness.uninstall/v1` | `harness_id, expected_meta_revision, expected_status, reason_code` |
| `composition.commit/v1` | `composition_body_artifact_id, expected_meta_revision, expected_desired_revision` |
| `state.create/v1` | `state_id, owner_id, schema_id, content_artifact_id` |
| `state.read/v1` | `state_id`；optional `state_revision_id`；签名、计一次grant use并持久化snapshot，原command重放返回原snapshot（ADR 061） |
| `state.write/v1` | `state_id, expected_state_revision_id, expected_cas_revision, content_artifact_id, schema_id`；无全局meta guard，严格aggregate CAS（ADR 061） |
| `authority.grant/v1` | `subject_id, permissions[], scope, constraints, delegable, expires_at_us` |
| `authority.delegate/v1` | `parent_grant_id, subject_id, permissions[], scope, constraints, delegable, expires_at_us` |
| `authority.revoke/v1` | `grant_id, reason_code` |
| `evolution.propose/v1` | `hypothesis_artifact_id, source_evidence_ids[], target_composition_id` |
| `evolution.create-candidate/v1` | `proposal_id, change_set_artifact_id, baseline_id, trust_class` |
| `experiment.run/v1` | `candidate_id, baseline_id, world_id, criteria_artifact_id, budget` |
| `candidate.promote/v1` | `candidate_id, evaluation_id, expected_serving_revision` |
| `composition.rollback/v1` | `target_parent_id, expected_serving_revision, state_strategy(KEEP_COMPATIBLE|RESTORE_PARENT), expected_state_revisions{state_id:revision_id}, reason_code` |
| `scratch.create/v1` | `realm_id, idle_ttl_us, wall_ttl_us` |
| `scratch.execute/v1` | `session_id, source_artifact_id, deadline_at_us, budget` |
| `scratch.export-candidate/v1` | `session_id, source_artifact_ids[], export_names[], contract_artifact_id, dependency_lock_artifact_id, entrypoint` |
| `scratch.release/v1` | `session_id, reason_code` |
| `operations.backup/v1` | `absolute_destination, expected_meta_revision` |
| `operations.gc-plan/v1` | `realm_id, expected_meta_revision` |
| `operations.gc-apply/v1` | `gc_plan_artifact_id, expected_meta_revision` |
| `operations.retry-outbox/v1` | `outbox_id, expected_state` |
| `operations.reconcile/v1` | `realm_id, expected_desired_revision` |
| `operations.rebuild-projection/v1` | `realm_id, projection, expected_checkpoint_seq` |

`expected_meta_revision` 只在会改变 Realm-wide refs/Authority/Root-affecting registry 的命令 required；其余使用 aggregate-specific expected revision。`artifact.put` 采用两阶段 local upload：`BeginPut(expected_size, expected_sha256)` 返回 256-bit random staging handle、chunk size 1 MiB 和 1 小时 expiry；`PutChunk(handle, offset, bytes, chunk_sha256)` 只接受从当前 committed offset 开始的连续 chunk，相同 offset/hash 重放幂等，不同内容冲突；完成后 `artifact.put/v1` 引用 staging handle。daemon 验证连接用户、expiry、总 size/hash 后发布并立即失效 handle。Staging handle 视为 secret，只存 hash；不得接受任意本地路径让 daemon 代读。断线不删除 staging，expiry 后由 GC 清理。

Canonical `payload_hash = sha256(payload_type + NUL + payload_schema_version + NUL + JCS(payload))`，不包含 transport deadline/trace。`authorization_hash = sha256(command_id + NUL + realm_id + NUL + actor_id + NUL + authority_grant_id-or-empty + NUL + expected_meta_revision-or-empty + NUL + causal_parent_action_id-or-empty + NUL + payload_hash)`；Root signature preimage 还追加 auth nonce/issued time。idempotency conflict 比较 authorization_hash，防止同一 command被换 actor/grant/revision/parent 重放。服务端生成 Action id；client 不得指定，以免跨 command alias。

## 41.47 Backup、Restore、Upgrade 与 GC

### 41.47.1 Consistent backup

在线备份由 daemon 独占执行且固定 `quiesce=true`：停止新 Task/Experiment/Scratch/effect ingress → 等待除本次 Backup Operation 外的 running工作最多30秒但不自动取消 → 若仍有 RUNNING/UNKNOWN external effect或live Scratch则以 `FAILED_PRECONDITION` 失败并恢复 ingress → 暂停新的 Artifact publication/Backend submit → 分别用 SQLite backup API复制 `meta.db` 与 Portable `backend/portable.db` → 复制 durable request/result marker（不复制live PID/pipe handle）→ 读取备份 DB中全部 live Artifact/Blob → hardlink/copy CAS bytes/encrypted metadata → 生成 JCS `backup-manifest.json` → 必须写 SHA-256；配置backup signing identity时额外写 Ed25519 signature → 恢复 publication/ingress。Manifest包含 runtime/API/DB schema版本、realm/epoch/meta revision/fact boundary、Backend identity/profile/dedupe boundary、每个文件relative path/size/hash、key dependency handles和完成时间。v0.1本地profile以 SHA-256 + operator-controlled backup directory为基线，签名为 Managed deployment policy，不影响备份格式。

默认 backup root 为 data directory 同级的 `agent-meta-backups/`；`operations.allowed_backup_roots` 可配置额外 absolute roots。Backup destination canonicalize 后必须是某个 allowed root 的直接新建子目录，不能已存在、不能经 symlink/reparse point 跳出、不能位于 data directory/CAS 内。Hardlink只在相同 volume且 destination 安全策略允许时使用，否则 copy；最终 manifest不依赖 link 类型。

不允许直接复制运行中的 `meta.db` 文件。备份缺少任何 required Artifact、wrapped key metadata 或 checksum 不匹配即失败，不产生“成功”manifest。默认不把 OS keychain secret 导出到备份；manifest 必须列出恢复前置的 external key handles。

Restore 只允许到不存在或空的 data directory：验证 manifest/version/hash → 恢复 CAS 到 staging → 原子发布 → 恢复 Meta/Portable DB与durable request marker → 运行 integrity/schema/FK/Fact chain/Artifact root check → 生成新 Backend session但保留 request dedupe records → Backend negotiation/reconcile → readiness。禁止 merge restore。恢复到不同主机而 key unavailable时保持 diagnostics-only，直到operator导入外部 key；不得删除 encrypted Artifact。Managed/Distributed Backend自身不进入备份，manifest只记录外部 backend identity/requirements；restore后所有非terminal binding先 UNKNOWN并通过真实 Backend reconcile，绝不凭旧 handle重建/重放不可幂等 workload。

备份 snapshot内的本次 Backup Operation预期仍为 RUNNING；restore识别其 operation id与manifest一致后，将其标 `FAILED_RECOVERY` 并写 `backup_snapshot_restored` Fact，不会重新执行备份。其他非terminal Operation按各自恢复规则处理，默认 fail closed而非重放operator副作用。

### 41.47.2 Upgrade

升级前自动创建 manifest-only preflight 和完整 backup，检查 free space 至少为 DB + live CAS 的 1.2 倍。Migration 获得 daemon lock，在 DB transaction 中逐个相邻版本执行；migration checksum 与发布 wheel 内记录不一致返回 `INTEGRITY_ERROR`。迁移失败回滚当前 DB transaction并保持旧数据，runtime 不启动 writer。Artifact format migration 创建新 Artifact/refs，禁止原地改 bytes。

代码 downgrade 仅在 DB/public schema 仍被旧版本明确支持时允许；否则通过 restore 旧 backup 完成，不执行 reverse SQL。升级成功写 `runtime_upgraded` Fact，包含 old/new runtime、DB、API、Fact reader、Backend protocol version。

### 41.47.3 Garbage collection

GC mark roots 固定为：所有 canonical table Artifact refs、非 terminal Task/Invocation、active/archived Experiment retention、Composition/State/Fact payload refs、legal hold、backup pin 和 Restricted retention tombstone policy。通过 schema registry 提取 refs，不扫描任意 JSON 字符串猜测。Mark 生成带 meta revision/fact boundary 的 `gc-plan` Artifact；sweep 前重新读取 revision，若变化则废弃重算。

Sweep 只处理未标记且 `created_at < now-24h` 的 CAS entry：先移动到同 filesystem `trash/<gc-id>/`，提交 `artifact_gc_quarantined` Fact；7 天后且无新引用才删除。Artifact DB row不删除，更新 availability/tombstone projection；Fact 永不删除。Staging expiry 为 1 小时，清理前验证 staging path 位于 canonical staging root。Windows 无可靠 directory fsync 时必须对文件调用 `FlushFileBuffers`、使用同 volume atomic move，并在 Backend profile/doctor 报告 `directory_fsync=UNSUPPORTED`；不得宣称等价于 POSIX crash guarantee。

---

## 41.48 Portable Backend Worker、幂等与取消规范

### 41.48.1 Worker process contract

Portable Backend 只执行 `builtin_or_signed` 或 `trusted_candidate`。每个 workload 使用 `<data_dir>/backend/workloads/<request-id>/`，其中 `request.jcs`、`claim`、`started.jcs`、`result.jcs`、`stdout.bin`、`stderr.bin` 均以 temp + flush + atomic replace 写入。目录名必须由已校验 UUID 派生，禁止直接拼接任意 request id。

Workspace 位于 `<data_dir>/workspaces/<realm-hash-16>/<workspace-uuid>/`，DB只保存相对路径。Task 默认 quota 512 MiB，Scratch/Candidate 1 GiB；写入前后都检查 quota，超过即 `RESOURCE_EXHAUSTED` 并停止后续 effect。成功 terminal workspace 1 小时后释放；失败/UNKNOWN 进入 QUARANTINED 24 小时供 diagnostics，之后按 auditable cleanup plan处理。legal hold/active Evidence引用阻止清理。Adapter只能获得已打开的 workspace directory handle，不获得任意 host path。

Python worker 使用运行时提供的独立 worker entrypoint，启用 isolated mode，工作目录为新 workspace；环境变量只保留 `PATH` 的受控 runtime 路径、locale、timezone、request/workspace handle 和显式 Composition allowlist。默认不继承 provider key、Root credential、用户 home override、proxy、Python path 或动态 loader 变量。Capability environment 由锁定 wheel/package Artifact 预先构建，worker 启动期间不得联网安装依赖。

stdout/stderr 各限制 8 MiB；超过限制时停止读取不会导致 pipe deadlock，而是继续 drain 并只保留前 4 MiB + 后 4 MiB，写 `output_truncated`；结构化结果只通过独立 framed control channel 返回，不能从 stdout 猜测。control frame 同样限制 16 MiB，结果过大必须写 workspace Artifact staging。

### 41.48.2 Durable request claim

Portable Backend 使用独立 `<data_dir>/backend/portable.db`，不得写 Meta Store 表。它使用与 Meta DB相同 PRAGMA/application crash profile，但 `application_id=1095582276`（ASCII `AMBD`）、`user_version=1`，DDL固定为：

```sql
CREATE TABLE backend_meta (
  singleton INTEGER PRIMARY KEY CHECK(singleton=1), backend_id TEXT NOT NULL,
  generation INTEGER NOT NULL, created_at_us INTEGER NOT NULL
) STRICT;
CREATE TABLE requests (
  request_id TEXT PRIMARY KEY, realm_id TEXT NOT NULL, operation_kind TEXT NOT NULL,
  payload_hash TEXT NOT NULL, payload_jcs BLOB NOT NULL,
  idempotency_class TEXT NOT NULL, reversibility TEXT NOT NULL,
  state TEXT NOT NULL CHECK(state IN ('PREPARED','CLAIMED','RUNNING','TERMINAL','UNKNOWN')),
  handle_bytes BLOB NOT NULL, request_relpath TEXT NOT NULL UNIQUE,
  worker_pid INTEGER, worker_start_identity TEXT, launch_nonce_hash TEXT,
  result_hash TEXT, result_jcs BLOB, effect_state_unknown INTEGER NOT NULL DEFAULT 0,
  terminal_acknowledged INTEGER NOT NULL DEFAULT 0,
  created_at_us INTEGER NOT NULL, started_at_us INTEGER, completed_at_us INTEGER,
  retained_until_us INTEGER NOT NULL, updated_at_us INTEGER NOT NULL,
  CHECK(NOT(state='TERMINAL' AND result_jcs IS NULL)),
  CHECK(effect_state_unknown IN (0,1)), CHECK(terminal_acknowledged IN (0,1))
) STRICT;
CREATE TABLE request_events (
  request_id TEXT NOT NULL, ordinal INTEGER NOT NULL, event_type TEXT NOT NULL,
  event_jcs BLOB NOT NULL, occurred_at_us INTEGER NOT NULL,
  PRIMARY KEY(request_id, ordinal), FOREIGN KEY(request_id) REFERENCES requests(request_id)
) STRICT;
CREATE INDEX ix_requests_recovery ON requests(state, updated_at_us);
CREATE INDEX ix_requests_retention ON requests(terminal_acknowledged, retained_until_us);
```

Submit 流程：

```text
BEGIN IMMEDIATE portable.db
  absent request       → insert PREPARED(payload hash)
  same request/hash    → return stored handle/result/current state
  different hash       → IDEMPOTENCY_CONFLICT
COMMIT
create request directory + request.jcs
spawn worker with request directory handle
worker atomically creates claim using create-new semantics
worker flushes started.jcs before loading Capability or producing effect
parent records RUNNING; response may now be returned
worker atomically writes result.jcs
parent/recovery records TERMINAL
```

若 parent 在 spawn 后丢失响应，重放 Submit 查 portable.db/request directory；只有成功持有 claim 的 worker 可执行。`PREPARED` 且无 claim/started 的请求可重新 spawn；存在 live claim 时不得 spawn 第二个；claim owner 已死且无 terminal result 时，根据 operation idempotency/reversibility 标为 UNKNOWN 或使用同一 request id 恢复。Worker identity 包含 PID、OS process-start identity 和 128-bit launch nonce，不能仅比较 PID。

InMemory Backend contract tests 使用可注入 `DurableFakeBackendState` 模拟 restart；生产 InMemory profile 明确报告 `persistent_idempotency=EMULATED`，只允许无外部 effect 的测试 workload。AgentOS fake provider 使用文件/SQLite durable request ledger，验证相同 provider contract。

### 41.48.3 Platform cancellation

Linux worker 使用新 session/process group。GRACEFUL 先通过 control channel 发 cancel，等待 5 秒，再向 process group 发 SIGTERM，继续等待 5 秒，最后 SIGKILL；每步 inspect 防止向 PID reuse 对象发信号。Windows worker 创建 Job Object 并设置 kill-on-job-close；GRACEFUL 先 control cancel 等待 5 秒，再 terminate Job Object。macOS 使用 process group，语义与 Linux 相同但 resource accounting 可 PARTIAL。

`CancelReport.terminal_confirmed=true` 只有 worker process tree 已退出且 result/exit status 已观察时成立。关闭 control connection、发送 signal 或调用 terminate 成功都不单独等于 terminal。强制取消产生 `release_forced` Fact。若无法确认子进程树，状态为 UNKNOWN，Task/Promotion fail closed。

### 41.48.4 Portable feature truthfulness

Linux/Windows Portable 的 workspace、environment 和 process tree 约束只对 trusted code 提供 accident containment，不是 adversarial sandbox。`isolated_realm`、`network_isolation`、`credential_isolation`、`hard_memory_quota` 对默认 Portable 必须报告 `PARTIAL` 或 `UNSUPPORTED`，不得因未注入 credential/network API 就报告 `SUPPORTED`。需要这些 required feature 的 workload 自动归类 untrusted/high-risk 并返回 `FEATURE_UNAVAILABLE`。

## 41.49 Threat Model、Peer Authentication 与 Redaction

### 41.49.1 v0.1 threat boundary

产品 profile 假设 daemon OS account 与 host kernel/administrator 可信；防御非特权本机其他用户、恶意输入/Artifact、越权 Capability、路径穿越、secret 泄露、崩溃/重放和不可信远端 Provider response。Portable 不防御已取得同一 OS account 权限的攻击者，也不把 trusted candidate 当 adversarial code sandbox。Managed strong isolation 是处理 untrusted code 的必要条件。

POSIX daemon 从 UDS peer credential 读取 UID，必须等于 daemon UID；Windows Named Pipe 通过 client token/SID 校验等于 daemon owner SID，校验前不处理 Hello payload。不能取得 peer identity 即关闭连接。Session Principal 由 peer identity 映射，client 提交的 `actor_id` 必须等于 session principal，除非携带 daemon 签发的 scoped delegation token。Root operation 还必须通过 41.28 Ed25519 signature；peer identity 本身不是 Root Authority。

每 peer identity/daemon instance 的 authentication/signature failure token bucket容量 10、补充速率 1/min；耗尽后立即关闭新连接并返回通用延迟（250～500 ms jitter），不写 durable Fact。成功认证不清空bucket。该限制只缓解本机滥用，不替代 OS ACL。

### 41.49.2 Secret classes

以下值一律视为 secret：Root/private signing key、DEK/KEK、Authority/execution/staging bearer token、Provider credential、cookie/session token、Authorization header、用户标记 secret 的配置值。Secret 以 opaque handle 在 Domain DTO 中流转；只有 Credential Adapter/Backend enforcement 可解引用。Secret value 禁止进入 exception message、repr、trace attribute、metric label、Fact payload、JCS config、command result和 diagnostics。

### 41.49.3 Deterministic redaction v1

Redaction 先做结构化规则，再做文本扫描：

1. key（ASCII case-insensitive）匹配 `authorization|proxy-authorization|cookie|set-cookie|api[_-]?key|secret|token|password|private[_-]?key|wrapped[_-]?dek|authority[_-]?token`，value 替换为 `{"redacted":true,"kind":"KEY_MATCH","sha256_prefix":"<12hex>"}`；
2. 已登记 Secret Registry 中 value 做 exact byte replacement；短于 8 bytes 的 secret 不输出 hash prefix，仅输出 kind；
3. 文本识别 PEM private key block、`Bearer <token>`、常见 URL userinfo；整段替换，不记录原值；
4. Provider-specific redactor 可额外减少内容，但不得恢复前面删除的信息；
5. 输出重新通过 schema/size validation。

sha256 prefix 只用于同一诊断 bundle 内关联，使用每 bundle random salt 的 HMAC-SHA256 前 12 hex，不允许离线字典比较。Redaction failure 默认丢弃整个字段并写 `redaction_failed` counter；不得退回原文。Raw content 的 redacted derived Artifact 记录 redaction policy ArtifactId 与 source plaintext ArtifactId（有权时）或 source content hash。

### 41.49.4 Log/diagnostics allowlist

Structured log v1 只允许：timestamp、level、event_name、realm_id、epoch_id、meta_revision、command/action/invocation/task/experiment id、stable error code、duration/usage numeric、backend id/session hash、status 和 redacted message。禁止任意 `extra` mapping。Trace attribute 使用同一 allowlist。Metrics label 只允许 operation kind、status、stable error code、Backend profile；不得使用 entity ID、用户文本、文件路径或 provider request id。

Diagnostics bundle 使用 allowlist 构造，包含 version/feature/config fingerprint/schema/checkpoint/aggregate counts/recent stable errors/redacted logs；默认不含 Artifact bytes、Task input、prompt/response、environment、完整路径、SQL row dump、key handle。显式包含 restricted data 需要独立 `diagnostics.include_restricted` grant，并仍不得包含 plaintext key/token。

## 41.50 Architecture Lint 与 Replaceability 验收

每个 `agent_meta_runtime.{domain,application,ports,adapters,interfaces,sdk,protocols}` Python package 必须在 `architecture.toml` 声明 layer、allowed imports、forbidden imports、primary principle、最多两个 secondary principles、owner Slice。CI 固定使用 import-linter，并额外用AST rule禁止所有`src/agent_meta_runtime/**` import `agent_meta_seed_harness`或任何`seed_harness`产品module；禁止`tests/fixtures/conformance_harness`和第三方Capability import `agent_meta_runtime.adapters.*`、private repository/UoW、Root succession或credential implementation。Conformance fixture只能import`agent_meta_runtime.sdk`、公开DTO和标准库。

每个 Core subsystem admission record 使用 schema：`id, mechanism, primary_principle, secondary_principles[], O1..O5{claim,evidence_artifact_id,reviewer,decision}, alternatives[], accepted_at`。缺字段、secondary 超 2、decision 非 ACCEPT 或 evidence 不存在时 lint fail。新 intelligent policy 不得放 domain Core；Evaluator/Evolution/Retry/Context/Governance 必须能通过 Composition 删除/替换，并由 AC-M07/AC-M13 使用Conformance Harness验证普通Task仍运行。

Replaceability contract：Adapter 只通过 Port 注册，关闭后不得遗留 global monkey patch、atexit owner、隐式 singleton 或未追踪 thread/process；`release` 后 RuntimeView 无 ACTIVE binding，重复 release 幂等。替换 Context/Retry/Evaluator 时历史 Invocation/Evaluation 仍按旧 ArtifactId 可解释，不能将旧记录重新解释为当前 policy。

## 41.51 Core/Serving Readiness、Backpressure 与 Operator Recovery

`/health/live` 不通过公网 HTTP 暴露，而是 local RPC `Runtime.GetInfo` 的 liveness field；event loop 在 1 秒 probe deadline 内响应即 true，不检查 Backend。`core_ready`是以下条件的 AND：daemon lock owner 有效；DB schema/integrity/FK/append trigger正常；Root与Runtime critical Artifact hash正常；Backend session negotiated且Runtime自身required features满足；critical outbox无DEAD_LETTER；reconciler不为UNKNOWN；Root credential handle可用（只读profile除外）；disk free ≥ max(512 MiB, configured 5%)。没有Composition时reconciler以空desired/serving/realized=0收敛，不使`core_ready`失败。

`serving_ready = core_ready AND serving_revision > 0 AND serving/realized对全部required instance可解释 AND active Composition critical Artifact/Surface hash正常`。兼容字段`ready`固定等于`core_ready`，不得随Harness安装而改变含义。`Task.Submit`要求`serving_ready=true`，否则返回`NO_SERVING_COMPOSITION`（没有serving）或`SERVING_NOT_READY`（存在但未收敛）；Artifact、Capability、Composition、Authority、RuntimeView、Doctor、backup/restore/upgrade和Harness lifecycle在`core_ready=true`时保持可用。两种readiness分别产生`core_readiness_changed`与`serving_readiness_changed` Fact和稳定reason list。

Readiness reason 使用稳定 code：`STORE_UNAVAILABLE/SCHEMA_INCOMPATIBLE/ARTIFACT_MISSING/ARTIFACT_CORRUPT/KEY_UNAVAILABLE/BACKEND_UNAVAILABLE/FEATURE_UNAVAILABLE/RECONCILE_UNKNOWN/CRITICAL_DEAD_LETTER/DISK_LOW/ROOT_AUTH_UNAVAILABLE`。`core_ready=false`时只允许GetInfo/GetView/Doctor/Graph read/Artifact verify/diagnostics和显式recovery API；Task、Composition mutation、Harness lifecycle、State write、Experiment/Promotion返回`FAILED_PRECONDITION`。

Backpressure 阈值：pending Task 1000、outbox pending 10000、projection lag 100000 Facts、SQLite WAL 1 GiB、free disk 上述阈值。Task/outbox 超阈值拒绝新增对应写；projection lag 不拒绝 Task，但 `why` 标记 incomplete；WAL 超阈值尝试 PASSIVE checkpoint，仍超限则`core_ready=false`；disk low立即停止Artifact/upload/effect并使`core_ready=false`，保留read/diagnostics/cancel。

`doctor` 每个 check 返回 `id,status(PASS|WARN|FAIL),observed,expected,repair_code`，不得自动修复。v0.1 repair 命令只有：`outbox retry <id>`、`artifact restore <id> --from-backup`、`projection rebuild <name>`、`backend reconcile`、`wal checkpoint`、`staging gc --plan`。每个 repair 默认 `--dry-run`，实际执行使用 CommandEnvelope/Authority/Fact。`force serving`、直接 SQL、删除 Fact、忽略 hash 或把 UNKNOWN 标成功不属于支持的 repair。

## 41.52 Public API Message、Query 与 CLI Contract

Public API command message 不重复定义领域字段，而是封装 canonical CommandEnvelope：

```proto
package agent_meta.public.v1;
message RuntimeInfo {
  bool live = 1;
  bool core_ready = 2;
  bool serving_ready = 3;
  bool ready = 4;                    // v1 alias，必须等于core_ready
  repeated string core_reasons = 5;
  repeated string serving_reasons = 6;
  uint64 desired_revision = 7;
  uint64 serving_revision = 8;
  uint64 realized_revision = 9;
}
message CommandRequest { bytes command_envelope_jcs = 1; }
message MutationResponse { bytes receipt_jcs = 1; bytes resource_jcs = 2; }
message QueryPage { bytes items_jcs = 1; string next_cursor = 2; uint64 snapshot_revision = 3; }
message GetViewRequest { string realm_id = 1; optional uint64 meta_revision = 2; bool include_backend = 3; }
message GetTaskRequest { string task_id = 1; }
message WaitTaskRequest { string task_id = 1; int64 wait_deadline_at_us = 2; }
message GetArtifactRequest { string artifact_id = 1; }
message VerifyArtifactRequest { string artifact_id = 1; }
message ValidateHarnessPackageRequest { string manifest_artifact_id = 1; }
message GetHarnessRequest { string harness_id = 1; }
message ListHarnessRequest { string realm_id = 1; string status = 2; uint32 limit = 3; string cursor = 4; }
message ValidateCompositionRequest { string body_artifact_id = 1; string baseline_id = 2; }
message GetRefsRequest { string realm_id = 1; }
message WhyRequest { string entity_id = 1; uint32 max_depth = 2; uint32 max_nodes = 3; uint32 max_bytes = 4; string cursor = 5; }
message LineageRequest { string entity_id = 1; string direction = 2; repeated string edge_types = 3; uint32 limit = 4; string cursor = 5; }
message BeginPutRequest { uint64 expected_size = 1; string expected_sha256 = 2; }
message BeginPutResponse { string staging_handle = 1; uint32 chunk_size = 2; int64 expires_at_us = 3; }
message PutChunkRequest { string staging_handle = 1; uint64 offset = 2; bytes data = 3; string chunk_sha256 = 4; }
message PutChunkResponse { uint64 committed_offset = 1; }
```

所有 resource JCS 的 `resource_type` 固定：`task-handle/v1`、`task-result/v1`、`artifact-manifest/v1`、`capability-descriptor/v1`、`harness-validation/v1`、`harness-installation/v1`、`composition-commit/v1`、`state-revision/v1`、`authority-grant/v1`、`proposal-result/v1`、`candidate-result/v1`、`experiment-handle/v1`、`promotion-result/v1`、`scratch-session/v1`、`scratch-execution/v1`、`operation-handle/v1`、`action-result/v1`。Reader 使用 `schema_version`，未知 optional field 忽略并 round-trip；未知 required semantic 通过 schema major 失败。

Public API 1.12依[ADR 061](adr/061-public-managed-state-commands.md)增加签名
`State.Create/Get/Write`（现有`CommandRequest/MutationResponse`）。`managed-state/v1`
资源给出选中revision/content/schema、当前head与CAS、owner、purpose、controller及固定redaction policy引用；
历史读取的CAS对应同snapshot中的current head，不能把历史revision伪作当前head写入。
`State.Get`为审计快照命令，使用`state.read/v1`、消耗一次授权use并写`state_accessed`；
原命令重放保持原snapshot。创建/写入要求owner的`state.write`及实际schema/content（创建时还含自选policy）
Artifact种类的`capability.invoke`；只使用envelope中的同一明确Grant，未实现的金额ceiling拒绝。
创建派生controller身份并固定schema/redaction，purpose仅GENERAL/SESSION_TRANSCRIPT/SESSION_JOURNAL；
保留State仅允许controller或当前Epoch Root通过管理命令读写，模型资源工具一律拒绝。
内容仅支持JSON、至多1 MiB（脱敏后再次检查）；schema/data结构分别限制2048/8192节点，
schema depth 32、data depth 48。Schema支持nullable type union，未知assertion fail closed；
enum/const校验缓存仅限一次调用。State revision schema引用和birth Fact中的policy引用均为GC root。
write允许同Realm且同Actor/Root授权的`causal_parent_action_id`，并记录新revision的supersedes、
derived_from及可选caused_by边；不改动既有why/lineage方向。CLI `state create/get/write`
及本地`--dry-run`、SDK envelope builders均不要求全局meta guard，严格使用revision+CAS。
此接口不关闭S05/S06、RP-04/RP-05，也不宣称Scratch、migration、rollback或Managed支持。

Public API 1.2依[ADR 040](adr/040-public-task-execution-inspection.md)新增`Task.GetExecution`
（现有`GetTaskRequest/ResourceResponse`消息）与`task-execution/v1`资源。它在同owner本地管理边界
只读返回真实Task/Invocation/Projection引用、规范化usage和预算元数据；不返回原始Artifact内容、
Provider/native对象或凭据。记录/字节上限、Realm范围、schema版本与旧minor拒绝由该ADR固定。

Public API 1.3依[ADR 042](adr/042-public-ordinary-artifact-content.md)新增`Artifact.GetContent`
（现有`GetArtifactRequest/ResourceResponse`）与`artifact-content/v1`资源。普通内容每次最多1 MiB，
返回经完整性核对的hex编码，SDK再次验证ArtifactId/size/hash；响应及错误不泄露CAS路径。
有加密或Restricted tombstone记录的Artifact始终拒绝，不能凭同owner身份或明文副本绕过受权读取。

Public API 1.4依[ADR 044](adr/044-public-ordinary-principals-and-delegation.md)增加签名命令
`Authority.CreatePrincipal/Delegate/Revoke`，复用`CommandRequest/MutationResponse`与既有42项权限。
新增`principal-identity/v1`资源及以PrincipalId为entity的`authority.principal_registered` Fact；
仅注册普通AGENT/CAPABILITY/PEER的公开Ed25519身份，Root/Service仍走专用生命周期。
委派的父Grant固定为签名envelope中的授权Grant，严格衰减scope/权限/time/epoch/use/depth；
未实现的非空金额上限明确拒绝。撤销须有权限、归属和完整scope覆盖，不改变历史uses或已提交命令重放。
CLI的`authority create-principal/delegate/revoke`只传公开身份与显式范围；不导出Root私钥。

Public API 1.5依[ADR 046](adr/046-public-task-state-trace.md)增加`Task.GetTrace`与`task-trace/v1`，
在同owner管理边界、单一SQLite snapshot中返回本Realm Task的有界Action/Fact状态元数据与causal edges。
它只返回实际持久化的顺序/状态/原因，不返回原始Fact payload，不从当前状态补造历史。
SDK为`get_task_trace`，CLI为`task trace`。该观察入口不改变Host权限或声明外部验收完成。

Backup、GC apply、projection rebuild、forced reconcile 和 Experiment 是异步 operation：mutation response 返回 `operation-handle/v1`/`experiment-handle/v1`；`Operations.Get/Wait` 或 `Evolution.GetExperiment/WaitExperiment` 读取 terminal。Operation ACCEPTED row、Action、Fact/outbox先原子提交，外部工作在 transaction外执行，terminal row + Fact再原子提交。Wait timeout不取消 operation；v0.1只有明确支持 cancellation的 Task/Scratch execute暴露 Cancel。

Cursor 是 daemon 使用每次启动 session key 计算的 opaque authenticated token，内容为 query kind、snapshot revision/fact boundary、last sort key、expiry；默认 15 分钟。篡改、query 不匹配或过期返回 `INVALID_ARGUMENT`。分页期间 snapshot 已被 GC（v0.1 canonical row不删除，正常不会发生）则返回 `FAILED_PRECONDITION`。Why cursor还保存 traversal frontier hash，不允许 client 修改 budget 绕过 Authority。

CLI 到 RPC/exit code 固定映射：成功 0；参数/schema 2；Authority 3；not found 4；revision/idempotency conflict 5；feature/precondition/readiness 6；temporary Backend/resource/deadline 7；integrity/data loss/key 8；internal 70。Human output 可以演进；`--output json` 必须输出 `{api_version,ok,result|error}`，stderr只输出 redacted diagnostic，stdout只输出一个 JSON document。`--dry-run` 运行全部纯 validation/Authority/plan 但不 claim command id、不写 DB/CAS/outbox、不调用 Backend；结果包含 `would_change`、expected revisions、required permissions/features 和 plan Artifact hash（内容在内存生成，不发布）。

## 41.53 External Harness Loop Contract 与 Model Terminal Semantics

[ADR 050](adr/050-inmemory-host-activity-and-durable-ack.md)定义显式`execution.host_backend=in_memory`
开发Host：真实session/submit/handle/await与Root认证Service token，实际Capability instance因果绑定，
Invocation终态与terminal-ack outbox同事务提交，事务外发送ack；丢失ephemeral session明确标为不可确认，
不重新执行已确认结果。Public API 1.6的Task.GetExecution只公开binding摘要，当前GetView可选择profile。
该profile仍为trusted Python、PURE/明确零成本、协作取消和EMULATED持久性，不增加隔离或发布支持声明。

公共执行期SPI的精确Python DTO/Protocol与规范化结果编码见
[ADR 032](adr/032-public-host-spi.md)，公开import路径为`agent_meta_runtime.sdk.host`。
该增量仍在开发中：只有实际Host绑定与公开wheel恢复证明通过后，Runtime才可声明
Harness Contract 1.2.0/Host SPI 1.0.0；仅DTO/Protocol可import不关闭Seed的RP-01/RP-02。
当前已发布到开发wheel的1.1.0包校验能力不隐含可执行Host支持。

Public API 1.7依[ADR 054](adr/054-public-provider-plan-and-normalization-spi.md)新增
`ProviderAdapter`、`ProviderRequestPlan`及`ProviderTerminalResponse`，不改变RPC字段编号。
计划只携带profile ArtifactId及有界canonical terminal Messages body；endpoint、credential及worker由Runtime选择。
新callback与旧`invoke_model`二选一，共用规范化和串行tool dispatcher；Root Provider edge拥有终态提交。
缺少批准的profile、exact tokenizer或firm maximum cost时必须在Invocation/调用预留前拒绝。
当前daemon没有配置该执行入口，公开失败路径证明不等于配置成功、真实Provider支持或RP-03关闭。

Public API 1.8依[ADR 055](adr/055-provider-profile-approval-and-frozen-pricing.md)增加签名
`Harness.ConfigureProvider`及只含handle的`harness-provider-configuration/v1`批准记录。
使用精确HARNESS scope的`harness.activate`权限并额外要求当前Epoch Root operator，不向委派的激活主体隐式授予凭据改绑权。
profile必须匹配签名包及model descriptor；双修订guard保护writer事务，Task View冻结批准FactId，GC保留完整制品closure。
`enabled`只表示批准，不表示执行就绪。Root冻结profile/计价/usage解析逻辑已实现，公开执行桥仍OPEN；缺exact tokenizer/firm maximum不填0。

Public API 1.9依[ADR 056](adr/056-provider-credential-provisioning-and-reviewable-cli.md)增加签名只读
`Harness.ValidateProviderConfiguration`及配置CLI dry-run；验证不占用Command、Authority use或Fact，writer仍复查双修订guard。
独立native `agent-meta-provider-credential`只允许当前Realm Root operator向Provider专用受保护目录导入凭据；
它直接执行Credential Store及只读Authority验证，属于native enforcement，不改变普通CLI仅走公开API的约束。
CLI显式读取有界stdin或指定settings文件，输出只有handle/profile；轮换保留旧item，备份只包含完整已发布item。
Windows使用DPAPI，Linux显式测试存储仍为INSECURE_TEST_ONLY。该操作不批准绑定、不执行模型、不关闭RP-03。

[ADR 057](adr/057-frozen-provider-admission-and-controlled-daemon-assembly.md)实现Root专用的loopback/TEST装配，
不改变默认daemon的真实Provider门禁。内部预留v2绑定批准Fact和绝对deadline；预留及发送前writer事务均重读
Task实际冻结View、当前批准、完整profile closure、handle、request和独立最大成本。
Root以原始wire usage和冻结计价替换包的usage声明；规范化失败仍保留已知费用，unknown不填0，overrun阻止成功交付。
显式测试CA只由embedded Root constructor选择，使用独立Host profile hash；不开放公开CLI选择，不宣称Managed/真实上游/RP-03关闭。

[ADR 058](adr/058-explicit-native-provider-test-launch.md)进一步增加native启动参数
`agent-meta start --controlled-provider-test-ca <file>`，供独立consumer仅经已安装console入口选择该测试装配。
launcher先进行有界文件读取和PEM校验；dry-run不创建store/daemon，显式InMemory冲突拒绝。
该增量覆盖ADR 057最初的“仅embedded constructor”限制，仍只允许loopback/TEST，不是生产Provider入口或新的RPC。

Public API 1.10依[ADR 059](adr/059-provider-terminal-observation-and-public-accounting.md)为
`task-execution/v1`的Invocation增加可选`provider`投影：冻结profile/config引用、输入/输出/成本预留、保守结算和有界HTTP terminal。
`provider_terminal_observed` Fact与结算/Invocation终态原子提交，查询核对Fact、journal、request hash和outcome；篡改或缺Fact返回INTEGRITY_ERROR。
429的RESOURCE_EXHAUSTED及有界`retry_after_us`持久可查，但不触发重试、不把unknown cost填0、不改变真实Provider/Managed门禁。

协作式可信Host依[ADR 045](adr/045-cooperative-host-call-scheduling.md)在三个异步facade操作入口
先于任何事务/回调让出事件循环，再检查取消、期限和授权，避免连续立即完成的调用饿死管理面。
该调度点不跨事务持锁，不提供回调内部的硬抢占或隔离保证。

本节是外部Harness的互操作Contract：Runtime必须提供DTO/schema、budget/authority/effect enforcement与Conformance Host tests，但不在产品源码实现该Loop。外部Seed v0.1 Loop不得从自由文本解析自定义命令；唯一effect路径是Provider正规化后的`tool_calls`。每个turn精确定义为一次Model Invocation加其返回的全部tool call串行处理：

```text
accept Task and frozen snapshot
for turn in 1..max_turns:
  reserve one model_call; build deterministic Projection
  invoke Model with deadline/cancel
  normalize response
  tool_calls = tool_call parts in response order
  if tool_calls not empty:
    reject if finish_reason not TOOL_CALL/STOP or duplicate call_id
    for call in response order:
      consume one step; dispatch using frozen surface
      append tool result Fact/Artifact to task-local turn history
      if failed and stop_on_tool_error: fail Task
    continue next turn
  else if parts contains non-empty text/json/artifact:
    require finish_reason STOP or LENGTH
    commit normalized content as Task result Artifact
    status SUCCEEDED (LENGTH adds result_truncated=true)
    stop
  else:
    fail INVALID_RESULT
if max_turns/max_steps/model_calls exhausted: fail RESOURCE_EXHAUSTED
```

一个 tool call 消耗一个 step；一次 model invocation 也消耗一个 step，因此 `max_steps` 是二者总和。预算 reservation 在 Invocation row 创建事务完成，Provider 未被调用前取消则释放未实际消费的 cost reservation但 model-call count仍记 1，防止取消重试绕过限额。Provider usage unknown 时 token/cost 标记 unknown，不用 0；若 policy 有硬 cost ceiling且 Provider 无法在调用前给出 max cost，真实 Provider invocation 返回 `FAILED_PRECONDITION`。

单次 response 最多16个 tool_call part，call_id在整个 Task内唯一。含 tool_call时可以同时含 text/json/artifact part；这些非工具 part作为assistant turn-history Artifact保留但不作为Task terminal result，随后仍执行 tool并进入下一turn。无 tool_call时 tool_result part非法。Provider返回多个 text part按原顺序保存，不隐式拼接后重新解析；Task result Artifact是完整 ContentPart array。

v0.1公共Model SPI是非streaming terminal response。外部Provider Adapter可以在内部消费provider stream，但不得在terminal commit前把部分内容交给Loop/Tool dispatcher；取消时丢弃未完成partial raw，仅记录受policy允许的redacted diagnostic。Runtime release gate只要求test-only Conformance Provider通过Host Contract，不要求或发布真实/Fake Seed Provider。Provider rate limit映射`RESOURCE_EXHAUSTED`+retry_after，只有尚未确认provider接受request且Retry Policy允许时自动重试；否则按unknown/non-idempotent规则处理。

Task timeout 包含 durable queue 等待；`deadline_at_us` 是从接纳起生效的绝对 wall deadline。Scheduler 取到已过 deadline 的 ACCEPTED Task，直接原子提交 TIMED_OUT，不创建 Model Invocation。每次外部 await 使用 `min(task deadline, operation deadline)`。

接纳标量依[ADR 043](adr/043-strict-task-submission-scalars.md)严格校验，不接受bool、浮点或字符串
到预算/期限整数的隐式转换；deadline 0必须保留为已过期Unix时间，不能表示无期限。CLI的
`task submit --deadline-at-us`公开同一既有字段，纯dry-run使用相同校验。

## 41.54 IPython Scratch v0 Adapter

[ADR 071](adr/071-owned-scratch-composition-retirement.md)的兼容修复候选将Root拥有的
Scratch关闭/清理接入Composition drain；失败保留绑定并为重试保留旧serving/realized
generation，不得在native owner/workspace尚未确认释放时报告退休完成。

Public API 1.15候选由[ADR 070](adr/070-public-source-only-scratch-export.md)增加
`ScratchExportCandidate`：Root授权会话Source及显式依赖闭包，构造后在成功Invocation事务中
发布`trusted_candidate`包和provenance。导出不安装或改变serving，Experiment/Promotion、
独立Seed消费及完整生命周期门禁仍须分别验证。

Public API 1.14候选由[ADR 069](adr/069-public-bounded-scratch-observation.md)增加
`ScratchBindings/ScratchInspect`及Root派生的Source/Action绑定来源。名称写入跟踪限于
CPython 3.12 cell主线程；heap mutation仍为`UNKNOWN_RISK`，不完整和截断必须显式标记。
source-only export、Seed消费验证及完整S05/RP-04仍开放。下述1.13说明保留其阶段边界。

Public API 1.13候选实现由[ADR 068](adr/068-public-async-scratch-create-execute-release.md)固定
`sdk.host.ScratchCreate/ScratchExecution/ScratchRelease`和异步Root resource port；它仅覆盖
创建、执行与释放。公开bindings/inspect、完整binding provenance及source-only Candidate export
尚未关闭，不得据此前三项宣布S05或RP-04完成。精确输入、权限、effects、输出分块、证书前置
和保守binding-name标记以该ADR为准；无writer transaction跨越native kernel执行。

Scratch Adapter 运行在独立 ipykernel worker，不在 daemon 进程内。v0.1 每个 Realm 最多一个显式 ScratchSession；创建需要 `scratch.execute`，session 默认 idle TTL 30 分钟、wall TTL 4 小时，daemon restart 后不恢复 kernel heap。Session identity、cell source Artifact、execution Action/Invocation 和 exported binding metadata持久化；live value 只 Observed/weak handle。

启动配置固定：独立 workspace、history SQLite disabled、`HistoryManager.enabled=False`、`InteractiveShell.cache_size=0`、不加载用户 profile/startup/extensions、`PYTHONNOUSERSITE=1`、受控 `sys.path`、无 Provider/Root credential。IPython magics 默认 deny，只允许 `%time`、`%timeit`、`%whos` 的无 effect 子集；`!` shell、`%%script`、`%run`、`%load_ext`、`%pip`、`%conda`、filesystem/network magics 拒绝。该限制是防误用，不是 adversarial sandbox。

`execute` 输入必须是 source Artifact、deadline、budget 与 session id；stdout/stderr/display data各有 1 MiB limit，超限截断并记录。Cell 完成后 Adapter 返回 execution count、declared/changed binding names、mime bundle Artifact refs、sanitized exception；不返回 live object serialization。Cancel 先发 kernel interrupt，5 秒未 terminal按 Portable process-tree cancellation；kernel被杀后 Session status LOST，所有 live handles EXPIRED。

`bindings` 只列 identifier、exact type module/name、created/last-changed cell、safe summary和 weak handle；不调用 repr。`safe_inspect` 完全复用 41.44.3。`release` 关闭 kernel并清 workspace（先 auditable plan），重复调用幂等。

`export_candidate` 只接受以下显式输入：一个或多个 cell source Artifact、用户选择的 top-level function/class name、Capability Contract Artifact、dependency lock Artifact和 entrypoint。禁止 cloudpickle/pickle live closure、lambda、动态 module、C extension或引用未选择 hidden binding。Adapter 用 Python AST 验证 entrypoint 存在、收集 import；任何 free variable 除 builtin/locked module 都返回 `OPAQUE_DEPENDENCY`。成功后构建 41.29 canonical Capability Package，trust class 默认为 `trusted_candidate`；随后必须走 Experiment/Promotion，不能直接加载到 serving。

## 41.55 Platform Credential Store v1

Credential Store 是 Port，v0.1 platform Adapter 固定如下：

| Platform | Product storage | Handle format |
|---|---|---|
| Windows | DPAPI CurrentUser 加密 blob，文件 DACL 仅 daemon owner SID | `credential://windows-dpapi/<uuid>` |
| macOS | Login Keychain generic-password item，service `agent-meta-runtime` | `credential://macos-keychain/<uuid>` |
| Linux desktop | Secret Service item，collection必须 locked/unlockable | `credential://linux-secret-service/<uuid>` |
| Linux headless | operator-provided master key file，absolute path、owner=daemon UID、mode 0600、不得位于 data/backup/CAS | `credential://linux-keyfile/<sha256-path-prefix>/<uuid>` |

Linux headless init 若未提供 `AGENT_META_MASTER_KEY_FILE` 必须停止并给出配置错误；不自动把明文 master key生成到 data directory。CI/dev 可使用 41.28 的 insecure fixture file，但 feature report 标 `credential_store=INSECURE_TEST_ONLY`，不能满足产品安全 AC。

Master key file/DPAPI/Keychain/Secret Service 只保护 KEK 与 Root Ed25519 private key；Provider credential单独作为 item存储并按 handle授权。Credential Adapter API 只有 `create/get_for_scoped_use/rotate/delete_metadata`，返回 secret 的方法只能被 Authority/Backend enforcement package import。读取 secret 使用 mutable buffer并在使用后 best-effort zeroize；Python 无法保证所有副本清除，threat model明确依赖同 OS account/process boundary。

Key handle rotation：创建新 key item → 验证可读 → 逐批重包 DEK/切换 Root public identity需走 recovery ceremony → 标旧 handle RETIRING → 确认无 ACTIVE encryption/token引用 → 删除旧 item metadata并写 Fact。删除 key前必须输出依赖计数，非零时 fail closed。Doctor 只测试 handle exists/authorized decrypt challenge，不读取或输出真实 key。

SQLite runtime minimum 为 3.37.0（STRICT table）；启动必须检查 `sqlite_version`、JSON/backup API 和 compile options。缺失即 `SCHEMA_INCOMPATIBLE`，不静默创建非 STRICT schema。

## 41.56 Normative External References

实现和 golden test 必须以以下外部规范为准；本文另有更严格约束时采用更严格者：

- [RFC 8785 — JSON Canonicalization Scheme](https://www.rfc-editor.org/rfc/rfc8785.html)：JCS/I-JSON、IEEE-754 number serialization、UTF-16 property sort；特别注意 JCS 不做 Unicode normalization。
- [SQLite STRICT Tables](https://www.sqlite.org/stricttables.html)：STRICT 自 3.37.0 提供；低版本不得用 writable-schema workaround 冒充支持。
- [SQLite PRAGMA trusted_schema](https://www.sqlite.org/pragma.html#pragma_trusted_schema)：所有连接关闭 trusted schema。
- [Protocol Buffers proto3 guide](https://protobuf.dev/programming-guides/proto3/) 与 [field presence](https://protobuf.dev/programming-guides/field_presence/)：field number 永不复用；有“未设置”和零值差异的 scalar 使用 `optional`/oneof。
- [IPython configuration](https://ipython.readthedocs.io/en/stable/config/intro.html)：配置必须通过显式 traitlets Config 注入，不读取用户可执行 config；output cache size 0 表示关闭。
- [Windows CryptProtectData](https://learn.microsoft.com/en-us/windows/win32/api/dpapi/nf-dpapi-cryptprotectdata)：Windows product key storage 使用 CurrentUser DPAPI，并记录其通常绑定同一用户/主机的恢复限制。
- [Windows Named Pipe impersonation](https://learn.microsoft.com/en-us/windows/win32/ipc/impersonating-a-named-pipe-client)：server 读取消息后验证 client token/SID；同时使用 Pipe DACL，不能只依赖 pipe name secrecy。

External dependency 的新版本若改变上述行为，先由 contract/golden test 检出，再通过 ADR 更新；不得因库升级静默改变 canonical bytes、安全边界或 wire compatibility。

## 41.57 Core Bootstrap（无Harness）

### 41.57.1 Init sequence

`agent-meta init`只作用于不存在或空data directory，固定执行：

1. canonicalize data/config/backup/key paths，建立mode/DACL安全目录；
2. 获取daemon lock，检查Python/SQLite/crypto/filesystem capability；
3. 创建DB version 1、STRICT tables、trigger/index，并运行integrity/FK check；
4. 初始化filesystem CAS/staging/workspace/backend/run/diagnostics目录；
5. 创建Realm `realm://main`、Epoch `epoch://<uuidv7>` ordinal 0；
6. 创建Root/Service Ed25519 identity、credential handles、one-time recovery code/hash；
7. 发布Constitution、schema、permission registry、redaction/retention/retry/budget和Harness Contract等Runtime builtin Artifact；
8. 创建Root Grant与仅含reconcile、Task scheduler、Fact projection、token issue、Harness lifecycle所需权限的Service Grant；
9. 创建`composition_refs`，固定`desired=serving=realized=0`、各CAS为0、status=`READY`；revision 0是“无Composition”sentinel，不在`compositions`表创建伪row；
10. 写`runtime_initialized`、`core_readiness_changed`和backup dependency Facts，关闭临时资源并释放lock；
11. stdout只显示Realm、data dir、`core_ready=true/serving_ready=false`、feature summary和one-time recovery code。

步骤5～10在单一SQLite transaction中提交；credential key item和CAS bytes先staging，事务失败则best-effort删除未引用item/staging。若外部credential已创建但清理失败，记录在`<data_dir>/staging/init-orphans.jcs`（只含handle，不含secret），下一次init先清理。Init不得探测`../agent-meta-seed-harness`、Python environment中的Seed distribution、网络registry或任何Harness路径。

对已存在且bootstrap transaction完整的同版本data directory重复init：验证config fingerprint兼容、清理init orphan并返回现有Realm；不创建新key/grant/code，不再次显示recovery code。发现部分DB schema、缺Runtime builtin Artifact或版本不兼容时fail closed，要求restore/upgrade，不能“补几行”形成未知lineage。缺少Harness、serving=0或外部Seed不可用不属于bootstrap损坏。

### 41.57.2 Runtime builtin identity boundary

Runtime builtin只包括Constitution/schema/permission/redaction/retention/retry/budget/Harness Contract及可选Scratch Adapter descriptor；不得包含`capability://seed.*`、Model/Loop/Context/Dispatch/Evaluation/Evolution/Governance实现、Seed Grant模板或Seed Composition。ArtifactId由Runtime release内容决定并记录在signed release manifest。

### 41.57.3 Test-only Conformance Harness

`tests/fixtures/conformance_harness/`提供最小Task ingress、deterministic provider、context、single-step loop和echo capability，仅用于Runtime contract/E2E。其ID使用`capability://conformance.*`和`composition://conformance/<uuid>`；构建脚本必须断言wheel/sdist/SBOM/product builtin registry均不含该目录、ID或Artifact。Conformance fixture失败阻塞Runtime release；外部Seed repository不可用不阻塞。

### 41.57.4 External installation entry

Core bootstrap后，operator通过41.60 Harness lifecycle安装任意外部package。首次成功activate分配Composition revision 1并使desired→serving→realized收敛到1；这不是Seed专属revision。卸载最后一个Harness后refs收敛回0，`core_ready`保持true、`serving_ready`变false。

### 41.57.5 Initial grants

Root Grant为同Realm `REALM_ALL + unbounded`。Service Grant不含Root recovery/succession，也不代表外部Harness。Harness请求的permission/scope/budget在Install dry-run中展示，只有Root授权的Activate命令才创建scoped Grant；package名称、签名或安装动作本身不授予Authority。Scratch principal/grant在显式Scratch.Create时按session创建，release/expiry时revoke。

## 41.58 v0.1 Scope Closure

“v0.1 可完整实现并验收”严格表示：独立实现Meta-Runtime单机Portable产品切片、公共Harness Contract/SDK、test-only Conformance Harness、AgentOS ABI client/fake contract、Architecture lint以及本节列为Runtime Required的要求；不要求checkout、构建、安装或执行外部Seed项目。

| Item | v0.1 applicability | Evidence |
|---|---|---|
| FR-MID/MREF/MFACT/MCAP/MSTATE/MAUTH/MCTX/MINV/MSTORE/MAPI/MOPS/MARCH及43.14新增Runtime项 | Runtime Required | traceability + automated tests |
| FR-MRUN-001～009 | Runtime Required（通用Task/Host schema、golden与enforcement） | conformance fixture tests；其中Seed实现符合性另由外部CI证明 |
| FR-MOS-001～010 | Required for InMemory/Portable；AgentOS 侧以 client + fake provider 验证 | shared provider/consumer contract |
| FR-MEVO-001～005 | Required deterministic v0 baseline | Candidate E2E |
| FR-MSUC-001～005 | Schema/API reservation Required；automatic execution Deferred | schema lint；不计功能完成 |
| AC-M01～M09B、M12～M16、M18～M47、M49～M54 | Runtime Required，按v0.1 Backend/profile解释 | blocking Runtime CI |
| AC-M10/M11 | Deferred to M5 | 不得标绿或宣传已支持 |
| AC-M17/M48 | External-Seed | 不阻塞Runtime release；阻塞Seed release |
| Rust `agentosd` production behavior | External/Deferred | fake provider only in v0.1 |
| Cordis Adapter | Optional extra | 不阻塞 release |
| IPython Scratch Adapter | Required | integration/security tests |
| macOS | Experimental | smoke result，不阻塞 release |
| percentage traffic canary | Deferred | v0.1 仅做 isolated pre-serving probe + atomic cutover |
| M4 evaluator/search evolution、peer/population | Deferred | schema 可保留 |
| M6 distributed runtime | Deferred | 不进入 v0.1 API guarantee |
| `agent-meta-seed-harness` repository/distribution | External independent consumer | 不得成为Runtime dependency或release input |

Deferred 对象可以有 DTO/schema placeholder，但默认 CLI/API 必须返回 `FEATURE_UNAVAILABLE` 加 `deferred_until_phase`，不得返回假 Handle。README、version response 和 diagnostics 必须列出 compiled/available/deferred features。

v0.1 的 Architecture lint/AC-M13 是 Required：它检查 Core subsystem 的 primary/secondary principle metadata、O-1～O-5 decision record schema、import boundary 和 forbidden dependencies；它不自动证明哲学上的正交性，只验证每个 admission 有完整、可审计、由 reviewer 接受的记录。

## 41.59 最终运行边界与实现交接冻结

本节覆盖前文中仍可能产生多种合理实现的运行边界。发生冲突时，本节优先于 41.12、41.31、41.37、41.38 和 41.44 的概括性描述；实现不得另选语义。

### 41.59.1 Capability Surface 生成、缓存与权限变化

Surface cache key 固定为 `(realm_id, composition_id, authority_fingerprint, backend_profile_hash)`。`authority_fingerprint` 是下列 JCS 对象的 SHA-256：`principal_id`、`epoch_id`、`authority_history_boundary_meta_revision`，以及按 `(grant_id, permission, canonical_scope, not_before_us, expires_at_us, remaining_uses)` 排序的、在 Task 接纳时对该 Composition operation 仍有效的 grant projection。`authority_history_boundary_meta_revision`取该Principal可达Grant的`authority_grant_history.meta_revision`与`authority_uses.meta_revision`最大值，无记录时为0。Root 身份也必须投影，不得用空值代表隐含全权。Backend profile hash 包括 protocol、feature level、limits 与 placement truthfulness；仅 session id 变化不改变 hash。

Task 接纳事务在同一 SQLite snapshot 内完成：读取 serving Composition与 Authority boundary → 计算 cache key → 复用现有 row，或以`1 + COALESCE(MAX(surface_revision),0)`为该Realm原子分配下一个 `surface_revision`、注册 Surface Artifact和 row → 创建 Task/root Action。单writer使revision分配串行；唯一key约束仍用于检测实现错误，命中冲突时重新读取并复用，不得产生两个 revision。Surface Artifact中的 operation按 `operation_id` 排序，包含 contract version、input/output schema hash、description、effect/idempotency、所需 permission/scope和 availability reason；Authority filter未通过的 operation不进入 Surface。

grant create/delegate/revoke/expire/use-counter变化、Composition serving变化或 Backend profile hash变化不修改旧 Surface，只使后续 Task使用新 cache key。过期由接纳/调用时根据数据库时间值计算，不依赖后台清扫及时性。Surface只是模型可见快照，不是授权凭据：每次 invocation仍在执行前按当前 Authority history与 counter原子检查；Task运行期间被 revoke、expire或耗尽的 grant返回 `PERMISSION_DENIED`，不得因冻结 Surface继续执行。Task历史永远引用原 Surface Artifact，因此权限变化不改写既有解释。

### 41.59.2 Capability Health Probe v1

每个 required slot必须声明 `health_probe`；builtin probe也不得隐式省略。Descriptor固定字段为 `operation_id`、`timeout_ms`（1～10000，默认5000）、`max_attempts`（1～3，默认1）、`success_statuses`（只能含 `READY`）和 `effect=PURE`。Probe request固定包含 `reconcile_id`、`composition_id`、`slot`、`instance_id`、`descriptor_revision`、`backend_session_id`和稳定 `request_id`，不得包含 Root/Provider credential原值。

Probe只能返回 `READY | DEGRADED | UNHEALTHY`、稳定 `reason_code`、sanitized detail Artifact和观测时间。超时、异常、schema错误均归一为 `UNHEALTHY`。required slot只有 `READY`可通过 serving gate；preferred slot允许 `DEGRADED`，但 CompatibilityReport必须已有对应 WARNING且切换事务写 degradation Fact；`UNHEALTHY`永不通过。尝试间隔固定为1秒、2秒且复用同一 probe request id；probe不得写 Managed State或产生 network/filesystem/credential/external effect。候选 probe在隔离的 pre-serving binding上运行，绝不能通过生产 routing调用。

### 41.59.3 State Migration、Serving Cutover 与 Rollback

Migration以计划时的 `source_revision_id`为输入，生成未绑定的 immutable `target_revision_id`。运行 migration期间不修改 `managed_states.current_revision_id`；旧 serving Task可继续读写。进入 serving cutover事务时，对计划涉及的每个 state执行 CAS：当前 revision必须仍等于 source；任一冲突则整个事务 rollback，丢弃本次未绑定 target（保留为可审计 Artifact但不可成为 current），以新 source重跑 migration。不得把旧输入的 migration结果绑定到更新后的 State。

同一 serving cutover事务必须完成：所有 state CAS到 target、逐条写 `state_ref_history`和 Fact、Composition serving CAS、binding ACTIVE与 `serving_switched` Fact；任何一步失败全部回滚。Task接纳只读取该事务提交后的 state refs，因此不会观察到“新 Composition + 旧 schema”或反向组合。旧 Task继续使用冻结 revision；其后续写若 expected revision已过期返回 `REVISION_CONFLICT`，不自动把旧 schema写入新 current。

Rollback命令必须选择唯一 `state_strategy`：

- `KEEP_COMPATIBLE`：当前每个 state schema都被目标父 Composition静态接受时保留当前 revision；任一不兼容则整条命令失败 `STATE_ROLLBACK_REQUIRED`。
- `RESTORE_PARENT`：要求 `state.rollback` permission，并要求 `expected_state_revisions`逐项等于当前 ref；目标 revision必须是该父 Composition最后一次 serving cutover记录的 revision且 Artifact仍可读。切换会显式回退 state内容，Fact必须列出被遮蔽的新 revision；不删除任何 revision。

Rollback也只提交新的 desired transition；Reconciler按上述规则完成原子 cutover。没有记录过成功 serving binding的 Composition、缺失旧 Artifact、expected map不完整或状态在计划后变化时 fail closed；v0.1不推断 downgrade migration、不 merge分支，也不静默丢弃并发写。

### 41.59.4 Outbox Lease 与时钟回拨

数据库保存 UTC microseconds仅用于跨进程接管；同一 daemon进程内的 lease deadline和10秒续租调度必须使用 monotonic clock。daemon获得唯一 lock后，使用新的随机 `instance_id`，并在第一笔恢复事务把所有 `state='LEASED'` 且 `lease_owner != instance_id` 的 row重置为 `PENDING`、清空 lease字段；唯一 daemon lock已经证明旧 owner不再有提交权。所有 delivery terminal commit仍以 `state='LEASED' AND lease_owner=current_instance`作 CAS，迟到 owner不能标记 delivered。

运行中每10秒比较 wall delta与 monotonic delta；绝对差超过5秒即设置 `CLOCK_UNSTABLE`、readiness=false并停止取得新 lease。已持有 lease可在本进程 monotonic deadline内完成或放弃为 PENDING，但不得仅因回拨后的 wall time延长。连续3次、间隔10秒的差值不超过1秒后自动恢复。向前跳跃不会抢占本进程尚未到 monotonic deadline的 lease；其他进程不可能同时存在。测试必须覆盖±1小时跳变、restart接管和旧 owner迟到提交。

### 41.59.5 实现交付物与允许裁量边界

v0.1 repository必须包含：`src/agent_meta_runtime/{domain,application,ports,adapters,interfaces,sdk,protocols}`、Public/Backend `.proto`源、SQLite migration、JSON Schema、Runtime builtin AMPAK source与lock、`tests/fixtures/conformance_harness`、golden fixtures、contract/integration/E2E/fault-injection tests、`architecture.toml`、SBOM/provenance生成配置、operator runbook、release manifest模板，以及`docs/spec/v0.1-scope-and-traceability.md`。产品source/wheel不得含`seed_harness`或`agent_meta_seed_harness`；生成代码不得成为协议唯一来源；migration不得由ORM模型反向生成后未经审查直接发布。

实现者可以裁量私有函数拆分、变量名、等价索引优化、日志文案和UI排版；不得裁量ID/preimage、wire/storage schema、事务边界、状态机、Authority/effect判断、默认值、超时/重试、平台truthfulness、错误码、验收fixture或Required/Deferred范围。若实现发现规范内部冲突，必须先以ADR修订规范和traceability，不能在代码中选择一种解释后把另一种解释留给测试。

## 41.60 External Harness Package 与跨项目生命周期

### 41.60.1 项目和依赖边界

外部Seed的推荐仓库/distribution/import分别为`agent-meta-seed-harness`、`agent-meta-seed-harness`、`agent_meta_seed_harness`。本地开发工具可以把`../agent-meta-seed-harness`作为默认checkout hint，但Runtime daemon、wheel、tests和release workflow不得读取该相对路径；显式cross-repository job通过CI input传入checkout path。Runtime的`pyproject.toml` dependencies、optional-dependencies、entry points和wheel RECORD中均不得出现Seed distribution/module。

Seed可以在build/test环境依赖`agent-meta-runtime`的公开`agent_meta_runtime.sdk`，但产品安装物必须构建为AMPAK并通过local RPC导入。Runtime启动时禁止`pip install`、Python entry-point自动发现、扫描`sys.path`或联网取得Harness。协议依赖方向由architecture lint和wheel content test证明。

### 41.60.2 Harness manifest v1

Manifest是JCS Artifact，required字段固定为：

```yaml
schema: harness-package/v1
package_name: org.example.harness
package_version: 0.1.0
package_artifact_id: artifact://sha256/...
publisher_identity_artifact_id: artifact://sha256/...
signature_artifact_id: artifact://sha256/...
public_api_range: ">=1.0.0 <2.0.0"
harness_contract_range: ">=1.0.0 <2.0.0"
capability_contract_range: ">=1.0.0 <2.0.0"
artifact_format: AMPAK1
capability_descriptor_artifact_ids: []
composition_template_artifact_id: artifact://sha256/...
grant_requests_artifact_id: artifact://sha256/...
loop_policy_artifact_id: artifact://sha256/...
required_backend_features: []
optional_backend_features: []
build_provenance_artifact_id: artifact://sha256/...
```

字段不得省略或加入未知字段；数组按UTF-8 byte排序去重。`loop_policy_artifact_id`指向符合`harness-loop-policy/v1`的JCS，至少固定`stop_on_tool_error,max_turns,max_steps,max_model_calls`；Harness值不得放宽Host hard ceiling。`package_name`匹配`^[a-z0-9]+(?:[.-][a-z0-9]+)*$`，version使用41.42 SemVer profile。Signature preimage为`agent-meta-harness-manifest-v1\0`加除`signature_artifact_id`外manifest的JCS bytes；签名只证明publisher provenance，不自动提升trust class或Authority。`contract_fingerprint`是三个range、artifact format、loop policy hash、排序feature集合和Runtime所选具体contract versions的JCS SHA-256。

### 41.60.3 Validate 与 Install

Harness Contract 1.1.0（[ADR 031](adr/031-public-harness-consumer-contract.md)）补齐消费者打包入口
`agent_meta_runtime.sdk.packages`，不改变AMPAK1编码和manifest字段。
publisher identity Artifact内容为32-byte raw Ed25519 public key，signature Artifact内容为64-byte raw Ed25519 signature；
两者均按内容SHA-256寻址。自签名不等于受信publisher；只有operator显式配置的publisher fingerprint
才允许按`builtin_or_signed`placement执行，其余采用`trusted_candidate`约束。
grant request的`scope`使用§41.28的typed Scope对象，拒绝`REALM_ALL`及authority/harness/runtime管理权限请求。
`ValidatePackage`对每个引用校验内容hash；JSON制品必须为无重复key的JCS object。
plan hash绑定manifest、所有验证过的ArtifactId、resolved contract versions、Backend feature levels和trust class。
`Install`重跑验证且请求identity必须与签名manifest一致；已提交command重放先返回原receipt。

`Harness.ValidatePackage`是纯query：验证AMPAK/hash/path、manifest/schema/signature、contract range、Capability descriptor、Composition template、loop policy、grant request、Backend feature和placement；返回排序issue、resolved contract versions、trust class、requested permissions/features和plan hash，不写DB/CAS或执行代码。`Harness.Get`按`harness_id`读取单个installation；`Harness.List`按`(package_name,package_version,harness_id)`升序、使用41.52 authenticated snapshot cursor分页，默认/最大limit为100/1000，空`status`表示全部，非空必须是状态枚举。

`Harness.Install`要求`harness.install`，只接受已经由Artifact.Put进入staging/CAS的manifest/package Artifact。单一事务登记Artifact引用、immutable Capability descriptors、`harness_installations(status=INSTALLED)`、history、Action/Fact；`harness_id`为`harness://<uuidv7>`。Install不得创建Grant、Composition revision、Instance、Task或Backend request，不运行package entrypoint。相同command幂等重放；同Realm相同package name/version但不同hash返回`IDEMPOTENCY_CONFLICT`。安装成功不改变serving readiness。

### 41.60.4 Activate 与 Deactivate

具体CommandEnvelope绑定见[ADR 034](adr/034-signed-activation-plan-and-delegation.md)：
`plan_hash`必须等于当前ValidatePackage报告值，`grant_request_hash`为完整请求数组JCS的SHA-256；
envelope必须有`expected_meta_revision`，签名payload必须有`expected_serving_revision`。
实际Composition的slot只能引用该installation签名descriptor的精确code Artifact或显式Runtime builtin。
SDK `prepare_harness_activation`只读查询并返回完整可持久重发的签名命令；缺失/陈旧guard或委派扩权均拒绝。

`Harness.Activate`要求`harness.activate`以及grant request中每项permission的签发权。事务前重跑Validate并生成CompatibilityReport；operator必须签署包含plan hash、grant request hash、expected meta/serving revision的CommandEnvelope。v0.1每个由Harness提交的Composition只能引用该installation提供的Capability与Runtime builtin；跨多个外部package拼装同一Composition延期。事务创建显式scoped Grants、immutable Composition revision、desired CAS、Harness activation Operation/Action/Fact/outbox；不直接改变serving。Reconciler成功切换后，在同一terminal事务把新installation标`ACTIVE`，把先前ACTIVE installation标`INACTIVE`并撤销其scoped Grants，然后写双方history和`harness_activated`；切换前新installation保持`INSTALLED/INACTIVE`。失败时撤销本次所有activation-scoped Grants（已发生的use审计历史保留）、保持旧serving，installation状态不变。

`Harness.Deactivate`要求`harness.deactivate`。只有该Harness对应当前serving Composition时才把desired CAS到revision 0 sentinel并排队drain；Reconciler原子使serving/realized收敛到0后，状态改`INACTIVE`、清空`active_composition_id`并撤销Harness scoped Grants。切换失败保持旧serving和`ACTIVE`。一个Realm只有一个serving Composition和至多一个`ACTIVE` Harness installation。

### 41.60.5 Uninstall、升级与保留

`Harness.Uninstall`要求`harness.uninstall`，仅允许`INSTALLED/INACTIVE`且不存在desired/serving/realized Composition、non-terminal Task、active Instance、State owner或unsettled Effect引用。事务撤销残余Grant、标`UNINSTALLED`、写history/Fact；不删除Artifact、Fact、Composition、Evidence或历史row。GC以后按41.47 retention决定不可达bytes。UNINSTALLED是terminal；v0.1同一Realm不得重新安装相同`package_name + package_version`，必须发布新版本并获得新`harness_id`，历史不复活。

升级固定为install新version → validate/experiment → activate新Composition → drain旧version → uninstall旧installation；禁止原地改package/hash/version。回滚只切换到仍installed且Artifact可读的旧Composition/State，遵守41.59.3。

归属检查依[ADR 041](adr/041-installation-reference-and-grant-generation-guards.md)：卸载阻止项必须
属于目标installation的不可变Composition/Capability版本闭包，而不是Realm内其他包的正常serving或
Task。State owner和未决Effect（含UNKNOWN）仍必须阻止卸载。生命周期撤销覆盖旧激活代的所有
scoped Grants；同一installation再次激活时只保留当前代，不能留下更早代的隐式权限。

### 41.60.6 CLI、跨仓库CI与失败隔离

CLI固定提供：

```text
agent-meta harness validate <manifest-artifact-id>
agent-meta harness install <manifest-artifact-id> --expected-revision N
agent-meta harness list|inspect ...
agent-meta harness activate <harness-id> --expected-revision N --expected-serving N
agent-meta harness deactivate <harness-id> --expected-revision N --expected-serving N
agent-meta harness uninstall <harness-id> --expected-revision N
```

Runtime blocking CI只使用`tests/fixtures/conformance_harness`，并设置network deny和不存在的Seed checkout path，证明无隐藏依赖。Seed项目CI自行checkout/pin Runtime版本，并对每个声明支持的Runtime minor执行SDK compile、manifest golden、install/activate/task/deactivate/uninstall contract suite。外部Seed CI失败、仓库不可达或版本尚未发布不得改变Runtime release结论；Runtime只对公开Contract兼容负责。

---

# 42. 分阶段实施路线

本章只保留阶段级路线。v0.1的实际编码顺序、每步交付物和退出门禁已拆分到[`docs/plans/v0.1/README.md`](plans/v0.1/README.md)及其10个Runtime步骤文档；可整体迁移到外部仓库的Seed计划位于`docs/plans/v0.1/seed-harness/`，文件名统一以`Seed_Harness_`开头。步骤文档不得复制或覆盖本规范的字段、DDL、状态机和FR/NFR/AC定义。

## Phase M0 — Meta Schema / Constitution PoC

先固定与语言无关的 Meta schema，并同步定义/消费 AgentOS Protobuf ABI：

```text
Constitution Artifact
Orthogonality Lint
Identity
Artifact
Fact
Action
Invocation
CapabilityContract
Composition
Authority
World
Execution Backend / AgentOS ABI schema / feature negotiation contract
```

成功标准：schema 不引用 IPython/Cordis/Linux/Rust 私有类型；Python client 只通过 public ABI handle 访问 Kernel。

## Phase M1 — Reflective Python Meta-Runtime

```text
Python asyncio core
SQLite Meta Store + local Artifact Store
runtime daemon + local-only API + single-writer lock
Protobuf AgentOS client over UDS
IPython Scratch Adapter
Object Reflection
Cordis Capability Adapter
Capability Catalog
Fact Ledger
Causal Graph
Snapshot Runtime View
Execution Backend client（Portable + AgentOS）
```

## Phase M2 — Meta-Control Plane

```text
Artifact Store
Versioned Composition
desired / serving / realized refs
Managed State MVCC
Authority Graph
Meta Transaction
transactional outbox + persistent Backend idempotency
Meta Reconciler
EffectIntent → AgentOS mapping
```

## Phase M3 — Harness Contract + Evolvable Composition

```text
External Harness Contract + test-only Conformance Harness
Proposal / ChangeSet
Experiment
World
Evidence
Evaluation
Candidate staging through AgentOS
Promotion Gate
isolated pre-serving probe / atomic serving cutover / rollback
```

## Phase M4 — Meta-Evolution

```text
Evaluator evolution
Evolution strategy evolution
Context/Composition schema evolution
Peer witnesses
Population/archive
```

## Phase M5 — Meta Root Succession

```text
Trust Epoch
Constitution Artifact
Meta-Root Candidate
WitnessSet
AgentOS-assisted isolated boot
atomic cutover request
semantic fallback
```

## Phase M6 — Distributed Meta-Runtime

```text
LogicalRealm
cross-realm semantic handles
distributed causal projection
multiple AgentOS Kernel backends
```

---

# 43. 功能需求（FR）

## 43.1 Identity / Artifact

### FR-MID-001
Semantic identity 不得使用 AgentOS ProcessHandle / Python id / PID 作为唯一长期 identity。

### FR-MID-002
Committed Artifact 内容变化必须生成新 ArtifactId。

### FR-MID-003
Capability instance incarnation 与 Artifact identity 分离。

### FR-MID-004
Managed State committed change 产生新 revision。

## 43.2 White-box

### FR-MREF-001
必须支持 revision-consistent Meta RuntimeView。

### FR-MREF-002
Managed entity 必须支持 why/lineage query。

### FR-MREF-003
Opaque consequential dependency 必须声明存在与影响范围。

### FR-MREF-004
Safe reflection 默认不得执行 arbitrary getter/repr。

## 43.3 Fact / Causality

### FR-MFACT-001
Meta canonical Fact append-only；修正通过新 Fact 表达。

### FR-MFACT-002
Committed control transition 至少记录 actor/action/authority/transaction。

### FR-MFACT-003
Meta Graph 必须可由 canonical Meta state + authoritative Facts 重建；旧 Graph projection 不得成为重建所必需的权威输入。

### FR-MFACT-004
Kernel Fact 可被引用/投影，但不得被 Meta Evaluator 改写。

## 43.4 Capability / Composition

### FR-MCAP-001
Capability Contract machine-readable。

### FR-MCAP-002
Harness 必须可以由 Versioned Composition 描述。

### FR-MCAP-003
支持跨 Capability ChangeSet。

### FR-MCAP-004
Define Artifact 不得自动运行/激活。

### FR-MCAP-005
卸载 Evaluation/Evolution 不得破坏基本 task execution，只丧失自主改进能力。

### FR-MCAP-006
Capability compatibility 必须联合检查 interface/schema、effect、authority、Backend requirement、state migration 与幂等语义，并输出 machine-readable CompatibilityReport。

### FR-MCAP-007
`in_process` placement 必须是显式信任决策；第三方与 Candidate 默认隔离执行，缺失 required isolation 时不得静默回退。

## 43.5 State

### FR-MSTATE-001
长期 Capability state 必须有 schema/serializer 或 Opaque declaration。

### FR-MSTATE-002
不兼容 schema transition 必须有 Migration Artifact。

### FR-MSTATE-003
Managed write 支持 expected revision / CAS。

## 43.6 Execution Backend / AgentOS Interaction

### FR-MOS-001
正式 execution 操作必须通过 `ExecutionBackend`；Managed/Distributed profile 使用 AgentOS ABI，Portable profile 使用显式兼容 Backend。

### FR-MOS-002
Meta EffectIntent 必须可关联 backend execution handle；Managed Backend 应可进一步关联 AgentOS Activity/Process/Lease Handle。

### FR-MOS-003
Meta-Runtime 不得假定任一 backend native/process handle 永久有效；长期 semantic identity 与 execution handle 分离。

### FR-MOS-004
Execution Backend facts 必须可进入 Meta causal projection；AgentOS KernelFact 是 Managed Backend 的标准实现。

### FR-MOS-005
Meta-Runtime必须在未安装AgentOS Kernel或外部Seed的普通Linux/Windows/macOS上以Portable profile运行core workflow；test-only Conformance Harness验证task/invocation/context/capability/scratch Host Contract，外部Harness可在相同Contract上运行。

### FR-MOS-006
Backend 必须暴露 machine-readable Capability Profile；Meta-Runtime 不得把 partial Portable semantics 宣称为完整 AgentOS guarantees。

### FR-MOS-007
Harness/Composition 不得因从 Portable Backend 切换到 Managed/Distributed AgentOS Backend 而被要求修改其核心 ontology；差异通过 execution profile / capability requirements 表达。

### FR-MOS-008
可能产生外部 workload/effect 的 Backend request 必须使用持久化 `request_id + payload_hash` 幂等契约，并报告 dedupe scope/retention。

### FR-MOS-009
Portable Backend 对 credential isolation、candidate strong isolation、Root cutover、untrusted code 与高风险不可逆 effect 等 required 强安全能力必须 fail closed。

## 43.7 Authority

### FR-MAUTH-001
Authority Graph 是一等可反射关系。

### FR-MAUTH-002
Delegation 默认 attenuation。

### FR-MAUTH-003
高风险 Meta Transition 记录实际 grant。

### FR-MAUTH-004
普通 Capability 不得 self-escalate Root Authority。

## 43.8 Context / Invocation

### FR-MINV-001
关键 ModelInvocation 记录 model/context/capability surface/composition/world 与 Kernel ActivityHandle。

### FR-MCTX-001
Model-visible section 可说明来源/producer。

### FR-MCTX-002
Context Policy 是 versioned Artifact。

### FR-MCTX-003
Prompt/response/tool result 必须区分受限 Raw Artifact 与 Redacted Derived Artifact；禁存 Raw 时必须显式记录 replay limitation。

## 43.9 Evolution

### FR-MEVO-001
Proposal / Experiment / Evidence / Evaluation / Decision 分离。

### FR-MEVO-002
Evaluation 不得回写旧 Evidence。

### FR-MEVO-003
Comparative evaluation 明确 baseline/candidate lineage。

### FR-MEVO-004
高风险 candidate 必须能够请求 AgentOS isolated Realm 执行。

### FR-MEVO-005
Rejected candidate/evidence 可进入 archive。

## 43.10 Succession

### FR-MSUC-001
每次 Meta Root transition 创建新 EpochId。

### FR-MSUC-002
普通 Meta Transaction 无权原地改写当前 Constitution/Root Artifact。

### FR-MSUC-003
Successor 必须先作为独立 candidate 构造。

### FR-MSUC-004
WitnessSet 不硬编码双系统。

### FR-MSUC-005
Cutover 必须通过 AgentOS/外层受信机制执行并支持 revert。

## 43.11 Architecture Integrity

### FR-MARCH-001
Meta Constitution 以 versioned Root Artifact 表达。

### FR-MARCH-002
新 Basis / Primitive 必须通过 O-1~O-5。

### FR-MARCH-003
每个 Meta Core subsystem exactly one Primary Principle，最多两个 Secondary。

### FR-MARCH-004
无法说明维护哪个 invariant 的机制不得进入 Meta Core。

## 43.12 Persistence / Transaction / Recovery

### FR-MSTORE-001
每个 committed semantic mutation 必须在单一 Meta Store transaction 中同时写入 canonical state、Fact 与 outbox item。

### FR-MSTORE-002
Fact Ledger 必须 append-only；修正通过引用原 Fact 的新 Fact 表达。

### FR-MSTORE-003
Artifact Store 必须按内容寻址，发布前完成 hash/size 校验并使用原子发布操作。

### FR-MSTORE-004
所有 mutation command 必须支持 `command_id` 幂等语义；相同 ID 的不同 payload 必须拒绝。

### FR-MSTORE-005
外部 Backend 调用不得在持有 Meta Store write transaction 时执行；跨边界一致性通过 transactional outbox 与 idempotent reconciliation 实现。

### FR-MSTORE-006
启动恢复必须依次完成 store/schema/Artifact 检查、Backend negotiation、outbox replay 与 desired/serving/realized reconciliation；达到`core_ready`后开放管理面，达到`serving_ready`后才接受新任务。

### FR-MSTORE-007
Artifact、Composition、Managed State、Authority/Realm refs 与 Fact Ledger 的权威范围必须按 41.6 明确区分；RuntimeView/Causal Graph 等 projection 不得成为隐藏的第二写入源。

### FR-MSTORE-008
Capability Code Artifact 必须包含依赖锁、entrypoint、Contract、runtime constraint 与 build provenance，确保相同 ArtifactId 不隐式解析为不同执行环境。

## 43.13 Task Host / External Harness Contract / API / Operations

### FR-MRUN-001
Harness Host必须强制执行Task声明的turn、wall-time、model-call与effect budget，并将cancellation传播到外部Harness Invocation、Capability与Execution Backend；外部Loop不能绕过这些ceiling。

### FR-MRUN-002
Model/Tool/Capability Invocation 必须记录 input/output Artifact、Context Projection、attempt、usage、latency、terminal status 与 sanitized error。

### FR-MRUN-003
Tool/Capability 输入在产生 effect 前必须完成 schema、authority、budget 与 backend feature 校验。

### FR-MRUN-004
Task/Action 创建时必须冻结 serving Composition 与 capability surface revision；运行中的任务不得随全局 desired/serving 指针变化。

### FR-MRUN-005
Promotion 必须通过独立 Gate 与 Meta Transaction，至少检查 Evidence、Authority、Artifact integrity、state migration、Backend requirement、unknown effect 与 expected serving revision。

### FR-MAPI-001
公共 mutating API 必须返回 `command_id`、`action_id` 与 committed `meta_revision`，并使用稳定 error code。

### FR-MOPS-001
实现必须提供liveness、`core_ready`、`serving_ready`、doctor、structured log与redacted diagnostics；`core_ready=false`时仍允许只读reflection与diagnostics。

### FR-MOPS-002
desired、serving 与 realized Composition revision 必须分别可查询，不得以 desired ref 冒充任务已经开始使用或 live realization 已收敛。

### FR-MOPS-003
产品模式必须由 runtime daemon 独占 Meta Store writer、realm sequence、outbox dispatcher、Reconciler leadership 与 Backend session；CLI/SDK 不得直接写 DB。

## 43.14 实现闭环补充要求

### FR-MTASK-001
Task 必须是具有 canonical row、状态机和 Fact 的一等对象，并在接纳事务中冻结 serving Composition、capability surface、Authority 与 budget。

### FR-MTASK-002
Task terminal row 与 terminal Fact 必须原子提交；迟到结果不得反转 terminal 状态。

### FR-MTASK-003
非 terminal Task 重启恢复不得漂移到新的 serving Composition；无法安全续接时进入 `FAILED_RECOVERY`。

### FR-MAPI-002
所有公共写 API 必须使用 `MutationResult[T]`，幂等重放返回首次 committed 的相同 receipt/resource。

### FR-MOS-010
Backend 必须支持 terminal acknowledgement；未确认幂等记录不得因容量压力提前清除。

### FR-MAUTH-005
Realm 初始化必须建立唯一 Root Principal/Grant 与外部 credential handle；普通 Authority API 不得创建或扩大 Root Grant。

### FR-MID-005
Artifact canonicalization 必须有 versioned preimage 规范与 Linux/Windows 跨平台 golden vectors。

### FR-MSTATE-004
State Migration 必须隔离、无外部 effect、保留旧 revision，并在输出 schema/hash 验证后才能绑定。

### FR-MSEC-001
Restricted Raw Artifact 必须使用 envelope encryption、受权读取审计、versioned retention 与可验证 crypto-erasure；默认不持久化 Raw。

### FR-MSEC-002
Portable Candidate 必须依据 trust class 决定 placement；`untrusted/high_risk` 在缺少 strong isolation 时 fail closed。

### FR-MSPEC-001
每个 v0.1 MUST FR/NFR/AC 必须映射到 owner Slice、machine-readable contract 与自动化测试；Deferred 项不得被报告为已交付。

### FR-MSTORE-009
SQLite 实现必须遵守 41.34 的 STRICT DDL、connection PRAGMA、`BEGIN IMMEDIATE` writer profile 与 Fact append-only trigger；偏离必须是带等价 contract proof 的 ADR。

### FR-MFACT-005
Fact/Causal Edge 只能使用 versioned registry 类型，projection edge 必须引用 source Fact，并报告 projection completeness boundary。

### FR-MAPI-003
Local API 与 Backend ABI 必须使用 41.26/41.41 的 framed Protobuf、固定 method/field registry、peer-local access control 与 16 MiB frame limit；v0.1 不自动回退 TCP/gRPC。

### FR-MCAP-008
Composition compatibility 必须按 41.42 保守算法执行；无法证明 schema compatibility 时返回 `COMPATIBILITY_UNKNOWN`，不得人工忽略后激活。

### FR-MRUN-006
通用Task ingress、Model ContentPart normalization contract与Capability dispatch必须遵守41.36的durable FIFO、严格schema/Authority/budget顺序、调用次序和terminal commit ownership；具体Loop/Provider由外部Harness实现。

### FR-MSTORE-010
Reconciler 必须使用 stable reconcile/request id 和 41.38 的提交点；serving CAS 后的恢复不得把新 Task 路由回旧 serving，也不得提前更新 realized。

### FR-MREF-005
Safe Reflection 不得调用用户可覆盖的 repr/str/len/iter/getattr/descriptor/property，并必须对 depth/item/byte/time budget fail bounded。

### FR-MCTX-004
Runtime提供的Context Projection Contract/conformance implementation必须按41.44.4的确定性选择、redact-before-rank、exact tokenizer与provenance manifest生成；外部Harness可提供其他versioned policy但不得绕过redaction/provenance。

### FR-MSTATE-005
Managed State 必须使用 immutable revision + mutable CAS ref；Task 冻结读取 revision，写冲突不自动 merge，Experiment 不得写 production state id。

### FR-MEFFECT-001
EffectIntent 必须在执行前完成 target resolution、Authority、budget reservation 和 Backend feature 检查；effect result 结算不得重复计费。

### FR-MEFFECT-002
Irreversible/unknown effect 默认要求显式 grant 与 Managed Backend；semantic rollback 不得伪装成 external effect rollback。

### FR-MOPS-004
Backup、restore、upgrade 与 GC 必须遵守 41.47 的 consistent snapshot、manifest/hash、empty-target restore、forward migration 和 revision-checked mark/sweep。

### FR-MEVO-006
Evolution v0 必须使用 41.43 的 typed ChangeSet、冻结 criteria/Evidence 与 `ALL_REQUIRED_PASS` deterministic decision；Evaluator error 不得产生 ACCEPT。

### FR-MOS-011
Portable Backend 必须使用 41.48 的独立 durable request ledger、create-new worker claim、request directory 和 platform process-tree cancellation；不得仅用进程内 cache 或 PID 实现幂等/恢复。

### FR-MSEC-003
Local peer authentication、Secret Registry、redaction、log/trace/metric/diagnostics allowlist 必须遵守 41.49；redaction 失败必须丢弃字段，不能输出原文。

### FR-MARCH-005
Architecture lint 必须使用 41.50 的 manifest/admission schema、import-linter 与 AST forbidden-import rules，并验证 intelligent policies 可删除/替换。

### FR-MOPS-005
Readiness、backpressure、doctor 与 repair 必须遵守 41.51 的 AND gate、稳定 reason、阈值与 allowlist；doctor 不得隐式修复。

### FR-MAPI-004
Public query/upload/CLI 必须遵守 41.52 的 Protobuf field、resource schema、authenticated cursor、exit code、JSON stdout 与 side-effect-free dry-run contract。

### FR-MRUN-007
Runtime必须发布41.53的External Harness Loop schema/golden和Host enforcement，并用test-only Conformance Harness证明自由文本不能触发effect、只有typed tool call可进入dispatch。外部Seed实现符合性由其自身CI证明，不进入Runtime源码或release gate。

### FR-MREF-006
Required IPython Scratch Adapter 必须遵守 41.54 的独立 kernel、disabled history/cache/profile/magics、bounded output、non-restored live heap 与 source-only Candidate export。

### FR-MSEC-004
Platform credential storage、handle lifecycle、rotation 与 SQLite runtime check 必须遵守 41.55；Linux headless 无外部 master key必须拒绝产品启动。

### FR-MRUN-008
Core init、Runtime builtin boundary、refs revision 0、test-only Conformance Harness与initial Root/Service grants必须遵守41.57；重复init不得创建或泄露第二组Root/recovery material，且不得探测或安装外部Seed。

### FR-MFACT-006
Fact Ledger必须按41.35构造per-Realm continuous hash chain、持久head和可验证checkpoint；任意gap/hash/head mismatch使`core_ready=false`。

### FR-MCAP-009
Capability Surface 必须按 41.59.1 的 Composition/Authority/Backend cache key确定生成与复用；权限变化不得改写旧 Surface，且每次实际调用必须重新授权。

### FR-MSTATE-006
State migration产物必须保持未绑定，直到与 serving Composition在同一 CAS事务切换；rollback必须显式选择 KEEP_COMPATIBLE或RESTORE_PARENT，不得推断降级或丢弃并发写。

### FR-MRUN-009
Capability health probe与Outbox lease必须遵守41.59.2/41.59.4的固定结果、timeout/retry、monotonic deadline、restart takeover和clock instability语义。

### FR-MARCH-006
Meta-Runtime不得依赖Seed Harness的distribution、module、checkout path、Artifact或release状态；必须通过41.60公共Contract支持外部Harness独立install/activate/deactivate/uninstall。

---

# 44. 非功能需求（NFR）

| ID | 要求 |
|---|---|
| NFR-M01 | Meta ontology 与 AgentOS Kernel/IPython/Cordis 类型解耦 |
| NFR-M02 | Reflection 不显著改变被观察语言语义 |
| NFR-M03 | Reflect 有 depth/item/byte/time budget |
| NFR-M04 | Meta fact + desired/serving/realized composition transition crash-consistent |
| NFR-M05 | committed Artifact 可内容校验 |
| NFR-M06 | RuntimeView 返回明确 revision |
| NFR-M07 | mutation 可追溯 actor/authority/evidence |
| NFR-M08 | candidate failure 不破坏 current Meta Root |
| NFR-M09 | semantic recovery 不要求旧 Kernel heap pointer |
| NFR-M10 | observed object registry 默认不延长对象寿命 |
| NFR-M11 | irreversible external effect 不得伪装为已 rollback |
| NFR-M12 | protocol/schema versioned |
| NFR-M13 | core 不依赖单一 evaluator |
| NFR-M14 | Meta Root Succession 可回 prior epoch |
| NFR-M15 | concurrent Meta mutation 不允许 silent lost update |
| NFR-M16 | raw secret 不进入普通 Meta Graph/Fact payload |
| NFR-M17 | Constitution/Primitive admission machine-checkable |
| NFR-M18 | Meta-Runtime 可以使用不同 Execution Backend；AgentOS Kernel 只是完整语义 Backend |
| NFR-M19 | Portable mode 不要求安装/运行本设计的 Rust agentosd |
| NFR-M20 | Backend capability degradation 必须显式可查询，不得 silent semantic weakening |
| NFR-M21 | Harness core ontology 不绑定 Linux/Windows/macOS 或 AgentOS-specific handle |
| NFR-M22 | Domain Core 不直接依赖数据库、网络、IPython/Cordis、provider SDK 或 OS process API |
| NFR-M23 | Backend/outbox/reconciler 至少提供一次交付下不得造成重复不可幂等 effect |
| NFR-M24 | 任何 terminal Invocation/Action 状态不可被迟到结果反转 |
| NFR-M25 | 配置、日志、Fact、trace 与 diagnostics 默认不得包含 plaintext secret |
| NFR-M26 | DB schema、Fact payload、public API 与 Backend protocol 独立版本化 |
| NFR-M27 | Portable Linux 与 Windows 必须运行相同 Backend contract suite |
| NFR-M28 | 正常本地环境中 outbox/reconcile 应在 5 秒内最终收敛；偏离需可观测 |
| NFR-M29 | 外部Harness只依赖public SDK/local RPC受限façade，不得通过MetaRuntime Service Locator或Python private import获得高权限服务 |
| NFR-M30 | Capability 与 Execution 调用方必须依赖最小 Port；高级强语义不得伪装为所有 Backend 都能替换的基础接口 |
| NFR-M31 | 同一 Capability Artifact 在相同声明平台上必须使用锁定依赖与 runtime constraint 可重复解析 |
| NFR-M32 | Task 在重启、重试与 serving 切换期间保持冻结的 Composition/capability surface，不发生语义漂移 |
| NFR-M33 | Artifact canonicalization 在 Linux 与 Windows 对相同逻辑 package 产生相同 ArtifactId |
| NFR-M34 | Restricted Raw Artifact 的 plaintext、DEK 与 credential 不进入 Meta DB、普通日志、Fact payload 或 diagnostics |
| NFR-M35 | v0.1 Public API 与 Backend ABI 必须有单一规范语义；JSON/Protobuf 映射不得形成行为不同的双实现 |
| NFR-M36 | Canonical JSON、ID、time、hash 与 protobuf golden bytes 在受支持平台完全一致 |
| NFR-M37 | Safe Reflection 对恶意 descriptor/container 在所有 budget 下均有限时、有限内存且无用户代码执行 |
| NFR-M38 | serving CAS 前后任意 crash 均保持 Task routing 与 realized 状态可证明，不依赖进程内锁恢复 |
| NFR-M39 | Context Projection 对相同 committed inputs/policy/tokenizer 产生相同 Redacted ArtifactId |
| NFR-M40 | Backup 可在新空 data directory 恢复至相同 realm/meta/fact boundary，并明确外部 key/Backend 依赖 |
| NFR-M41 | 所有 external effect 在至少一次 outbox/Backend delivery 下最多结算一次 budget，并可报告未知状态 |
| NFR-M42 | v0.1 feature report 必须区分 implemented、external-contract-only、experimental 与 deferred |
| NFR-M43 | Portable daemon 在 spawn 前后 crash 与响应丢失时，同一 request 最多只有一个 worker claim 可进入 Capability/effect 执行 |
| NFR-M44 | Secret/redaction/logging 对相同结构化输入行为确定，恶意异常和 Provider body 不得绕过 allowlist |
| NFR-M45 | Architecture boundary 与 policy replaceability 必须由静态 lint 加动态卸载测试共同证明 |
| NFR-M46 | `core_ready=false`、低磁盘或critical dead-letter状态必须在1秒内拒绝新增危险工作；`serving_ready=false`必须拒绝新Task，同时保留相应诊断和取消能力 |
| NFR-M47 | Public query pagination 在同一 snapshot 上稳定且 cursor 不可伪造；dry-run 与失败 validation 不产生持久或外部副作用 |
| NFR-M48 | 外部Seed Loop对相同fake Model terminal responses、snapshot与budget产生相同Action/Invocation/Fact状态序列；由Seed项目验收，不阻塞Runtime release |
| NFR-M49 | Scratch kernel 崩溃或 daemon restart 后 live handle 必须失效，且不能通过 pickle/closure 将 hidden consequential state 晋升 |
| NFR-M50 | Root/KEK/Provider secret 的 product storage 不得依赖 data directory 文件权限之外的未声明保护，并可审计轮换依赖 |
| NFR-M51 | 从空目录init到revision 0的core bootstrap，以及随后用test-only Conformance Harness达到serving/realized revision 1，均必须确定、可重试、无重复identity/grant并可离线验收 |
| NFR-M52 | Fact chain 从任意 trusted checkpoint重算至 head必须产生唯一相同 hash，旧 row/seq/payload任何变化均可检测 |
| NFR-M53 | Authority/Backend变化、state migration并发写、daemon restart与wall-clock跳变均不得造成陈旧授权、混合schema/composition、重复delivery terminal commit或无限lease |
| NFR-M54 | 在Seed repository不存在且network deny的环境中，Runtime必须可独立build/install/init/start/doctor/backup/upgrade；外部Harness失败不得改变Runtime release结论 |

---

# 45. Acceptance Criteria

## AC-M01：Semantic Harness 可重建

仅使用：

```text
Meta Epoch
Composition
Artifacts
Managed State
Meta Fact Boundary
Authority Bindings
```

可在新的 Meta-Runtime/Execution Backend 进程上重建 Harness，不要求旧 PID/heap；v0.1 至少在 Portable 与 AgentOS fake provider 上验证。

## AC-M02：Causal Query 跨层

对于一次 Capability Action 创建 process：

```text
Meta Action
→ EffectIntent
→ AgentOS ActivityHandle
→ ProcessHandle
→ KernelFacts
```

能够反向查询完整关联。

## AC-M03：Behavioral White-box

给定 ModelInvocation，可以重建：

```text
Context Policy
source facts/state
capability surface
composition
model config
AgentOS ActivityHandle / execution facts
```

## AC-M04：Artifact Immutability

原地修改 committed artifact 失败或产生新 ArtifactId。

## AC-M05：CAS

两个 Agent 基于 composition 82 修改，后提交者不能 silent overwrite composition 83。

## AC-M06：Evaluator Replacement

Evaluator v2 可重新评价 v1 使用过的历史 Evidence，Evidence 不变化。

## AC-M07：Evolution Capability Removal

卸载 Evaluation/Evolution/Governance 后，test-only Conformance Harness仍可通过Backend完成普通Task execution；外部Seed项目可复用同一contract test证明该性质。

## AC-M08：Scratch Promotion

临时函数：

```text
observe
→ artifact candidate
→ Portable trusted isolated process 或 AgentOS isolated activity
→ experiment/evidence
→ composition update
```

全程保留 lineage。

## AC-M09：AgentOS Independence

同一个 Meta-Runtime 可在两个独立的 protocol-compatible AgentOS fake provider profile 上运行，semantic Composition/Artifact/Fact ontology 不改变；连接真实 Kernel 的生产证明 Deferred，但必须复用相同 contract suite。


## AC-M09A：Portable Linux/Windows 运行

在未安装/未运行AgentOS Kernel daemon且不存在外部Seed checkout/distribution的普通Linux与Windows环境中，使用Portable Backend启动Runtime并完成core/conformance workflow；随后可仅通过public API安装任意测试Harness。缺失hard quota/distributed lease等能力必须通过capability profile显式报告，而不是失败后才暴露隐藏依赖。

## AC-M09B：Backend Switch without Harness Rewrite

同一个 Harness Composition 从 `PortableExecutionBackend` 切换到 `AgentOSKernelBackend` 后，不修改 Planner/Loop/Context/Capability ontology 即可运行；新增强隔离/ResourceLease/Supervisor 能力通过 execution profile 获得。

## AC-M10：Root Succession

新 Meta Root 只能通过：

```text
construct
→ AgentOS isolated boot
→ experiment/witness
→ cutover request
→ atomic switch
```

不能普通 transaction 原地覆盖当前 Root。

## AC-M11：Peer Witness 非特权

Peer 可提供 Evidence/Proposal，但没有 Authority 不能要求 AgentOS cutover。

## AC-M12：Opaque

native/external state 无法 introspect 时返回 opaque + impact，而非伪造 white-box。

## AC-M13：Orthogonality Gate

可推导 Principle / 可组合 Primitive 被 Architecture Lint 降级，而非膨胀 Core。

## AC-M14：Atomic Semantic Commit

在 Composition 提交事务的 artifact registration、desired ref、Fact、outbox、meta revision 各写点注入故障；重启后只能观察到“全部 committed”或“全部未 committed”，不得出现部分状态。

## AC-M15：Idempotent Command / Effect

同一 `command_id + payload` 重放返回相同语义结果；同一 `command_id` 配不同 payload 返回 `IDEMPOTENCY_CONFLICT`。outbox 重复投递与 Reconciler 重跑不得创建重复不可幂等 workload。

## AC-M16：Crash Recovery / Reconciliation

在 task、invocation、composition reconcile 与 experiment 各阶段 kill Meta-Runtime；重启后能够重放 outbox、续接或标记失效 handle、隔离 orphan workload，并使 desired/serving/realized 状态收敛或显式进入 `DEGRADED/UNKNOWN`。

## AC-M17：External Seed Loop E2E（Seed项目阻塞项）

使用 fake Model Provider 与 InMemory Backend 完成：

```text
task
→ context projection
→ model invocation
→ capability invocation
→ facts/evidence
→ why query
→ task completion
```

链路中每个对象均可通过`action_id`或causal edge关联。本项由`agent-meta-seed-harness`项目对声明支持的Runtime版本执行，不是Meta-Runtime release gate。

## AC-M18：Candidate Isolation / Promotion

`trusted_candidate` 在 Portable process/workspace isolation（或更强的 Managed isolated realm）中失败时不改变 serving Composition；Evaluation 接受并通过 Promotion Gate 后，使用独立 CAS transaction 更新 desired revision，经 Reconciler 就绪后切换 serving，随后可以切换回父 Composition，并保留完整 lineage。`untrusted/high_risk` Candidate 不得以 Portable 隔离冒充 strong isolation。

## AC-M19：Security Boundary

unsafe `repr/property`、path escape、过度 delegation、过期 grant、未满足 required backend feature 与 plaintext secret logging 均被自动化测试拒绝或显式标记。

## AC-M20：Operational Readiness

store、Artifact或Backend未通过启动检查时`core_ready=false`、普通Task和管理mutation被拒绝，而只读reflect/doctor/diagnostics仍可使用；核心恢复后无需重启转为`core_ready=true`。没有serving Composition时`serving_ready=false`且Task返回`NO_SERVING_COMPOSITION`；激活并收敛后无需重启转为`serving_ready=true`。

## AC-M21：Three-revision Composition Cutover

提交 Composition N+1 后，在实例化、migration、health check 与 CAS 前分别注入失败；所有情况下新 Task 继续绑定 serving N。只有 N+1 全部就绪后，serving 才原子切换到 N+1，随后 realized 收敛到 N+1。

## AC-M22：Persistent Backend Idempotency

Backend 已创建 workload 但响应丢失时，重启 Meta-Runtime 与 Backend 后重放相同 `request_id + payload_hash`，返回原 execution result/handle，不创建第二个 workload；不同 payload 返回 `IDEMPOTENCY_CONFLICT`。

## AC-M23：Daemon Single Writer

daemon 持有 data directory 时，第二个 daemon 或 embedded writer 启动失败并返回明确诊断；CLI/SDK 只能通过 local API mutation，不能绕过 daemon 直接写 DB。

## AC-M24：Capability Trust Placement

未签名第三方 Capability 与 Candidate 请求 `in_process` 时默认拒绝或强制转换为隔离 placement；Portable Backend 无 required isolation 时返回 `FEATURE_UNAVAILABLE`。

## AC-M25：Contract Compatibility

分别注入 effect 扩大、Authority 扩大、state schema 无 migration、输出 requiredness 变化与幂等语义变化；即使 interface version 字符串未变，Composition validation 仍返回 breaking incompatibility。

## AC-M26：Raw / Redacted Artifact Boundary

普通 Reflection 和 diagnostics 只能读取 Redacted Artifact；无显式 grant 时无法读取 Restricted Raw Artifact。关闭 Raw retention 后系统记录 replay limitation，且不生成虚假的 Raw 引用。

## AC-M27：Restricted Harness Façade

外部Harness/第三方Capability的依赖注入对象中不存在repository、raw transaction、grant、force activation或Root Succession接口；静态依赖测试阻止其import private application/store module。

## AC-M28：Artifact Canonicalization

同一逻辑 Capability Package 在 Linux 与 Windows、不同文件枚举顺序和不同本机 metadata 下产生相同 ArtifactId；路径穿越、大小写冲突、非法 entry 与 symlink 被拒绝。

## AC-M29：Authority Bootstrap

首次 init 只创建一个 Root Principal/Grant；重复 init 幂等。普通 grant/delegate API 无法创建、恢复或扩大 Root；DB、Fact、日志和 diagnostics 不包含 Root/recovery secret。recovery code只能从 stdin 使用一次，成功后旧 grant失效、新 code生成；argv/env code被拒绝，丢失全部 recovery material 时没有隐藏绕过路径。

## AC-M30：Backend Wire Contract

InMemory、Portable 与 AgentOS fake provider 通过同一 Protobuf consumer/provider contract suite，包括响应丢失、重复 submit、payload conflict、session restart、handle renewal、late completion 和 terminal acknowledgement replay。

## AC-M31：Task Freeze 与 Recovery

Task 接纳后切换全局 serving Composition，再分别于 model、tool、Backend wait 阶段终止 daemon；恢复后的 Task 始终使用原冻结版本，或显式进入 `FAILED_RECOVERY`，且 terminal row/Fact 不分裂。

## AC-M32：Raw Artifact Confidentiality

开启 Raw retention 后，CAS、SQLite、普通日志、Fact 和 diagnostics 中搜索不到 plaintext/DEK；授权读取成功并产生访问 Fact，未授权读取失败；关闭 retention 时不生成虚假 Raw 引用。

## AC-M33：Reconcile Crash Points

在 create、instantiate、migrate、health check、bind、serving CAS、drain、realized update 与 checkpoint 后分别注入崩溃；恢复后保持旧 serving 或收敛到完整新版本，不出现混合 binding、重复不可幂等 workload 或 Task version drift。

## AC-M34：Portable Candidate Trust Placement

`trusted_candidate` 可在 Linux/Windows Portable process/workspace isolation 下完成 E2E；请求 native extension、credential、network、越界 filesystem 或不可逆 effect 时升级为 `untrusted/high_risk` 并返回 `FEATURE_UNAVAILABLE`，除非 Managed Backend 报告 strong isolation 为 `SUPPORTED`。

## AC-M35：Canonical Store Contract

Linux/Windows 对 canonical JSON、Artifact package、payload hash、ID validation 与 protobuf fixtures 逐 byte 一致；SQLite schema/PRAGMA/trigger contract 检测任何 drift，Fact UPDATE/DELETE 必须失败。

## AC-M36：Safe Reflection Non-execution

使用恶意 `__repr__`、`__str__`、`__len__`、`__iter__`、property、descriptor、`__getattr__`、container subclass 与无限/阻塞对象测试；钩子调用计数始终为 0，Reflection 在 time/byte/item/depth budget 内返回 opaque/truncated。

## AC-M37：Deterministic Context Projection

相同 Task snapshot、Fact/State、policy、tokenizer 和 budget 重放 100 次产生相同 section order、manifest hash、token count 与 Redacted ArtifactId；改变任一 source revision 会改变 provenance，即使 rendered text 恰好相同。

## AC-M38：Managed State MVCC

两个 writer 基于同一 state revision 写入时仅一个 CAS 成功；失败者返回 `REVISION_CONFLICT`。Task 在全局 state ref 更新后仍读取冻结 revision，同时能读取自己的 committed overlay；Experiment 写 production state id 被拒绝。

## AC-M39：Effect Reservation 与 Unknown State

在 outbox、Backend submit 和 response commit 前后重复投递/终止进程，effect count 只 reservation/settle 一次；不可确认的非幂等 effect 进入 `EXTERNAL_EFFECT_UNKNOWN`，不会自动重试或被 rollback 标记为已撤销。

## AC-M40：Backup/Restore/Upgrade/GC

运行中创建一致性备份并恢复至空 data directory，realm/meta revision/fact boundary 与 live Artifact hash 完全一致；缺 Artifact/key、manifest tamper、较新 DB、migration crash 和 GC mark 后 revision 变化均 fail closed，不删除 live content。

## AC-M41：Local RPC Boundary

非所属用户无法连接 UDS/Named Pipe；错误 major、重复 in-flight request id、超 16 MiB frame、截断 frame、未知 method 与 payload hash mismatch 被拒绝且 daemon 保持可用。客户端断线不会取消已提交 Task。

## AC-M42：Deterministic Evolution v0

Typed ChangeSet 重复路径、stale old-value hash、缺 Evidence、unknown assertion、Evaluator crash 与 serving revision conflict 均不能 Promotion；相同 frozen Evidence/criteria 重评产生相同 assertion result/decision Artifact。

## AC-M43：Portable Worker Claim 与 Process Tree

在 portable.db PREPARED、request directory、spawn、claim、started、RUNNING、result 写入和 response 返回前后逐点终止 daemon/worker并重放相同 request；最多一个 claim 进入 Capability，payload conflict 被拒绝，orphan 可 reconcile。取消包含孙进程的 workload 后，所有可识别进程退出或状态明确 UNKNOWN，不能仅凭父 PID 退出报告 terminal。

## AC-M44：Peer Authentication 与 Redaction

不同 OS 用户/SID 连接 local endpoint 被拒绝；伪造 actor、重放 Root nonce、过期 signature 和 delegation 扩权失败。向配置、异常、Provider body、header、tool output、trace/log extra 注入 canary secrets，DB/Fact/log/trace/metric/diagnostics/CLI JSON 中均找不到原值；redactor 抛错时字段被删除。

## AC-M45：Architecture Lint 与 Policy Replaceability

逐个注入Domain→Adapter、External Harness→Repository、Capability→Credential/Root API等非法import，CI lint必须失败。卸载Context/Retry/Evaluation/Evolution/Governance后Conformance fake Task仍可执行；换入新版本后历史行为仍解析到旧Artifact，release后无残留ACTIVE binding/thread/process。

## AC-M46：Readiness 与 Backpressure

逐项模拟 schema/hash/key/Backend/feature/reconcile/dead-letter/disk 故障，readiness reason 精确匹配且危险写被拒绝，GetView/Doctor/diagnostics/cancel 保持可用。触发 Task/outbox/projection/WAL 阈值时行为符合 41.51；doctor 默认运行不改变 DB/CAS/Backend 状态，repair dry-run 不产生 mutation。

## AC-M47：Public Query、Upload 与 CLI

分页期间并发写入不会改变当前 cursor snapshot 的结果或产生重复/遗漏；篡改/过期/跨 query cursor 被拒绝。Artifact chunk 重放幂等且乱序/冲突失败。每类稳定错误映射到规定 CLI exit code；JSON 模式 stdout 可由 schema 解析且无额外文本。对所有 mutating CLI 执行 dry-run 后，DB/CAS/outbox/Backend hash 与调用前一致。

## AC-M48：External Seed Loop Determinism 与文本无副作用（Seed项目阻塞项）

Seed项目的Fake Provider分别返回text、LENGTH、单/多tool call、重复call id、空response、错误finish reason和budget exhaustion；状态序列符合41.53。向纯文本注入看似tool/JSON/shell的指令不得触发任何Capability/Backend effect。相同fixture重放产生等价causal graph与同内容ArtifactId。本项不要求Runtime仓库包含Seed实现。

## AC-M49：IPython Scratch Lifecycle 与 Export

用户 profile/startup/magics/history/cache 未加载；恶意 repr/property 不执行；输出受限。中断、kernel kill、daemon restart 后 handle 状态正确。含 closure/lambda/hidden binding/C extension/path escape 的 export 被拒绝；显式 top-level source + lock + Contract 成功生成 canonical Candidate，并且未经过 Promotion 前无法进入 serving。

## AC-M50：Platform Credential Store

Windows DPAPI、Linux Secret Service/headless key-file 必须在对应 blocking CI/profile contract test通过；macOS smoke验证 Keychain。错误 OS user、宽松 key-file permission、位于 data/backup 内的 master key、缺 handle、轮换仍有引用和不支持 STRICT 的 SQLite 均 fail closed。DB/CAS/backup/diagnostics 中找不到 Root/KEK/Provider secret。

## AC-M51：Empty-directory Bootstrap E2E

在Linux/Windows、network deny且外部Seed checkout/distribution不存在的空目录执行init，验证Runtime schema/builtin/Root-Service grant、desired=serving=realized=0、core_ready=true和serving_ready=false；Task.Submit返回NO_SERVING_COMPOSITION，而doctor/backup/upgrade可用。分别在credential/CAS/DB commit阶段kill后重试，不产生重复Root/grant/recovery code；已提交bootstrap的重复init不再次显示recovery secret。随后仅用test-only Conformance Harness经公共API完成install/activate/task/deactivate/uninstall，最终refs回0且core仍ready。

## AC-M52：Fact Hash Chain Integrity

跨多 transaction/多 Fact提交后，从 genesis和checkpoint分别重算得到 realms.fact_head_hash。复制 DB后分别修改 payload/actor/action/seq/prev/hash、删除/交换/插入 Fact或改 head，doctor必须全部报 INTEGRITY_ERROR且不 ready；追加 correction Fact保持旧 hash不变并得到合法新 head。

## AC-M53：Surface、Migration 与 Lease Race Closure

并发执行以下矩阵：Task接纳时grant revoke/expire/use耗尽与Backend profile变化；旧 serving Task写State时新Composition migration/cutover；两种rollback strategy；Outbox持有lease时daemon crash/restart、旧owner迟到commit以及wall clock正负1小时跳变。断言新Task只复用匹配完整cache key的Surface、每次调用重新授权、cutover不会出现混合Composition/schema或覆盖并发写、rollback不会隐式回退State、每个Outbox item只有当前owner可terminal commit，且CLOCK_UNSTABLE期间readiness false并停止新lease。required/preferred health probe还必须覆盖READY/DEGRADED/UNHEALTHY、timeout、重复response和pre-serving routing隔离。

## AC-M54：Cross-project Harness Decoupling

Runtime wheel metadata/RECORD/SBOM/source import graph不含`agent-meta-seed-harness`、`agent_meta_seed_harness`或`seed_harness`产品module；把Seed checkout path设为不存在并禁止network后，Runtime仍完成build/install/AC-M51。使用两个由test fixture独立构建、package name不同的Harness依次执行Validate/Install/Activate/Task/Deactivate/Uninstall，均只通过public SDK/local RPC；任一fixture注入private import、越权grant request、不兼容contract、失败health或残留引用时fail closed且旧serving/core readiness正确。外部Seed CI结果不得出现在Runtime release gate输入中。

---

# 46. 测试矩阵

| 类别 | 测试重点 |
|---|---|
| Constitution | O-1~O-5 / traceability |
| Artifact | immutability / hash / lineage |
| Artifact Canonicalization | cross-platform golden vectors / invalid path / logical package identity |
| Composition | diff / branch / three refs / serving freeze / CAS cutover |
| State | MVCC / migration / serializer |
| Task | serving freeze / budget / cancellation / terminal atomicity / recovery |
| Context | deterministic selection / redact-before-rank / tokenizer / provenance golden |
| Reflection | safe inspect / opaque / snapshot |
| Fact | append / hash chain/head/checkpoint / tamper / rebuild / correction fact |
| Causal Graph | why / lineage / cross-kernel fact link |
| Invocation | context provenance / activity link |
| AgentOS ABI | backend swap / persistent idempotency / handle expiry / structured error |
| Backend Wire | response loss / duplicate submit / payload conflict / session restart / terminal ack |
| Portable Worker | durable claim / parent-child crash / process tree cancel / output bounds / orphan reconcile |
| Scratch | kernel lifecycle / disabled profile-history-magics / weakref / source-only promotion / hidden control state |
| EffectIntent | resource/process mapping / irreversible effect |
| Effect Accounting | reservation / retry dedupe / settle / unknown outcome |
| Authority | delegate / revoke / self-escalation |
| Experiment | world mismatch / budget / isolated realm |
| Evaluation | re-evaluation / criteria drift |
| Evolution | candidate / rollback / archive |
| Evolution v0 | typed ChangeSet / frozen assertions / deterministic decision |
| Witness | peer/human/replay / no implicit authority |
| Succession | boot fail / witness reject / cutover fail / revert |
| Recovery | semantic rebuild on new process/kernel backend |
| Transaction | atomic commit / idempotency / outbox duplicate delivery |
| Reconciliation | desired/serving/realized diff / orphan / renewed handle / eventual convergence |
| External Seed Contract | terminal-only response / text no-effect / tool order；在Seed项目执行，不阻塞Runtime |
| Bootstrap | empty-dir core init / refs 0 / core-serving readiness / kill-retry / no Seed discovery |
| Harness Lifecycle | two independent packages / validate-install-activate-deactivate-uninstall / contract mismatch / reference safety |
| API/CLI | stable error code / JSON schema / dry-run |
| Operations | liveness/readiness / doctor / redacted diagnostics |
| Backpressure | task/outbox/projection/WAL/disk threshold / safe-operation allowlist |
| Data Lifecycle | consistent backup / empty restore / forward upgrade / revision-checked GC |
| Security | unsafe reflection / secret leak / raw-redacted access / path escape / authority bypass / placement |
| Peer/Auth/Redaction | OS peer credential / Root signature replay / structured-text redaction / allowlist failure |
| Raw Encryption | key unavailable / authorized read audit / retention / crypto-erasure / backup recovery |
| Credential Store | DPAPI / Secret Service / Linux key-file / Keychain smoke / rotation dependency |
| Local Transport | peer ACL / framing / version mismatch / disconnect / oversized payload |
| Architecture | manifest/admission schema / import boundaries / restricted façade / Port segregation / dynamic policy unload |

---

# 47. 从 v0.4 的迁移与提纯

## 47.1 保留在 Meta-Runtime

```text
Constitution / Orthogonality
White-box Contract
Identity semantic model
Artifact
Harness Composition
Capability Contract
Fact / Evidence
Temporal Causal Graph
Action / Invocation
Snapshot Meta View
Managed State
Scratch Object Reflection
Context Projection
Meta Transaction / Reconciliation
Evolution / Experiment / Evaluation
Self-Governance / Commitment
Trust Epoch
Witness / Peer / Archive
Semantic Recovery
```

Seed Harness不从v0.4“保留进”Runtime，而是迁移为独立项目，通过41.60公共Harness Contract接入。

## 47.2 下沉到 AgentOS Kernel

```text
physical process lifecycle
Activity scheduling
resource admission/allocation/lease
GPU/model/browser slot arbitration
hard quota / hard kill
IPC transport
Supervisor Tree
Cancellation / Deadline
ExecutionRealm physical isolation
Credential Broker
execution recovery
worker provisioning
```

## 47.3 拆成跨层协议

| v0.4 概念 | Meta-Runtime | AgentOS Kernel |
|---|---|---|
| Effect | EffectIntent / semantic reversibility | physical operation / lease / cleanup |
| Resource | semantic requirement / ownership | allocation / lease / accounting |
| Realm | LogicalRealm | ExecutionRealm |
| Authority | logical Authority Graph | enforcement/token/credential boundary |
| Fact | semantic Fact/Evidence | execution facts |
| Recovery | semantic reconstruction | execution recovery |
| Root Succession | candidate/witness/decision | isolated boot/cutover/revert |
| World | experiment requirements | realization of constraints |
| Signal/RPC | semantic contract | IPC transport/channel |

---

# 48. 两份设计的稳定分界

> **重要修订**：Meta-Runtime 与 AgentOS Kernel 是独立系统。Meta-Runtime 的执行依赖是 `Execution Backend Contract`；AgentOS Kernel 是完整语义 Backend，而非 Meta-Runtime 唯一可运行环境。


```text
Agent Meta-Runtime
负责：Agent 是什么、为什么如此、如何改变。

AgentOS Kernel
负责：Agent 如何运行、何时运行、使用什么资源、如何通信和恢复。
```

判断某个新机制属于哪一层时使用以下测试：

```text
如果问题是：
“这个状态/能力/版本/因果/评价意味着什么？”
→ Meta-Runtime

如果问题是：
“这个 workload 在哪里/何时/用多少资源/如何阻塞和终止？”
→ AgentOS Kernel
```

---

# 49. 最终定义

实现补充（2026-10-30）：[ADR 033](adr/033-local-command-authority-and-credential-storage.md)
固定公开CommandEnvelope签名/Grant执行规则、可重发SDK表示以及Windows DPAPI/DACL凭据存储。
本补充保留Public API v1的现有字段与冻结权限词表；非Windows安全凭据后端、完整Host恢复与
外部Seed验收仍待实现，不因局部单元证明而改变发布状态。

Host生命周期补充见[ADR 036](adr/036-task-free-factories-and-async-reconciliation.md)：
AMPAK同步factory不接收Task，实际Task只在执行入口传入；PURE health有独立DTO与异步回调。
异步Reconciler复用原A–H事务程序，外部await期间不持SQLite事务，所有切换/完成受冻结desired CAS约束。
后续实现见[ADR 037](adr/037-bound-trusted-host-and-durable-invocation-journal.md)：
显式信任的进程内Host已接通冻结接收View、Context登记、模型/PURE工具调用、同事务Authority/预算
预留以及已确认结果重放/未知结果终止恢复。仅支持独立计数的utf8-bytes Context子集和显式零成本
模型结果；不宣称完整Context、受控联网/凭据、强隔离或外部Seed最小版门禁已经完成。

[ADR 038](adr/038-harness-source-audit-and-serving-recovery.md)实现全包源码边界与provenance/code归属
验证，并使实际serving health独立于desired候选状态；候选失败后，旧serving继续接收Task，重启时
必须实际重绑定并重新探活原快照。相对导入架构lint现按真实Python import root解析；Reconciler通过
显式端口复用Service同事务授权，不直接依赖Adapter。该实现不提升任何完整发布验收状态。

本设计中的 **Agent Meta-Runtime** 定义为：

> 一个建立在稳定 Execution Backend Contract 之上的反射式、版本化、因果可追踪且可自演化的 Agent/Harness 元运行时。它维护 Agent 的 Self-Model、Self-History 与 Self-Transformation，把 Composition、Capability、Artifact、State、Context、Authority、Fact、Evidence、Evaluation 与 Successor 作为一等对象。Portable Backend 使其可直接运行在普通 Linux/Windows/macOS；完整 AgentOS Kernel Backend 则提供强隔离、资源仲裁、监督、凭据和恢复等 production-grade 语义。

本设计中的 **Seed Harness** 定义为一个外部项目：

> 一组通过公共Harness Contract安装到Meta-Runtime、足以产生有用Agent行为的最小可替换Capability，包括Model、Task/Event、Minimal Loop与Minimal Context；它可以附带Evaluation/Evolution/Governance scaffolding，但不拥有永久特权，也不是Runtime bootstrap、源码、依赖或发布门禁的一部分。

因此“Seed”描述的是外部参考实现的初始策略，而不是Runtime内部层。Runtime在Seed项目完全不存在时仍可独立build/install/init/start/doctor/backup/upgrade；Seed只单向依赖`agent_meta_runtime.sdk`和local RPC，并可在任意仓库路径独立版本化、测试与发布。

最终核心哲学：

```text
Self-Model
  What am I?

Self-History
  Why am I this way?

Self-Transformation
  What can I become?

Seed Harness
  How do I start before I have evolved myself?
```

以及与 Execution Backend / AgentOS Kernel 的关系：

> **Meta-Runtime makes the agent itself manageable.**  
> **Portable Backend makes the agent runnable on conventional OSes.**  
> **AgentOS Kernel makes the agent's execution manageable at production scale.**
