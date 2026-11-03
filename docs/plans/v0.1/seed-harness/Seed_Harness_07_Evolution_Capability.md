# Seed Harness Step S07 — Evolution Capability and Self-Iteration Loop

> 归属：外部项目  
> 状态：PLANNED  
> 前置：S06 VERIFIED，RP-06/RP-07关闭，所选Backend支持World全部required constraints
> Runtime规范定位：§41.43、§21、§23、§24、§41.32

## 目标

实现第一个由Harness拥有的Evolution Capability：从业务任务历史产生Proposal/ChangeSet，在隔离World中实验，合格者Promotion——形成"业务任务 → 自我改进"闭环。Runtime v0.1只提供机制（deterministic evaluator、scanner、Promotion gate），策略全部在Harness侧。

## 输入与首个验收场景

输入为S06包、真实任务的脱敏失败历史、已发布的演化Host/API、人工审阅的确定性fixture/criteria及授权操作者。
首个场景修复已安装Capability目录内的slot/wiring配置错误：从历史定位错误绑定，生成单个REWIRE候选，与冻结的正确绑定fixture比较。
只改变同一installation已有Capability或Runtime builtin的引用；不新增可执行源码、不扩大权限、不自主修改Evaluator或criteria。
本步验收“真实历史驱动的确定性配置修复”，fake World通过不证明真实模型任务质量提升；真实模型回归是独立观察，不计入v0.1实验判定。

## 实施顺序

1. 实现evidence collector capability：从Fact/Evidence/Evaluation查询聚合任务表现（失败模式、budget超限、工具schema违规等），产出Proposal（hypothesis + source_evidence_ids）。
2. 实现ChangeSet生成器：仅使用§41.43 tagged union操作，首个场景只开放`REWIRE`，后续再增`REPLACE_ARTIFACT`/`SET_POLICY`等；每项带target path、expected old value hash与new value，只生成新Composition，不修改baseline。
3. Candidate按§41.32分类trust class：默认隔离执行；请求更高权限的Candidate归类untrusted并要求Managed strong isolation。
4. Experiment遵守v0.1 World约束：fake Model + deterministic fixtures，network_policy=DENY；criteria使用`deterministic-evaluation/v1` assertions；Evaluator Artifact独立版本化，与被评对象分离。
5. 通过`Evolution.Promote`进入desired → Reconciler切换；Rollback创建指向父Composition的transition；实验期间baseline serving保持不变。
6. 治理约束：自迭代循环有显式触发策略与budget，不是常驻自动循环；operator批准点保留在Activate/Promote签名（§24 commitment）。
7. 发布门禁：S04–S07作为独立版本按S03流程发布——更新Runtime兼容矩阵与contract golden、SBOM/provenance/compatibility report，签名新AMPAK；升级走§41.60.5的install新版本 → activate → drain旧版本 → uninstall路径。

## 有界策略与制品链

- 仅由operator显式触发；默认一次触发最多一个Proposal、两个Candidate、两个Experiment，总wall预算300秒、真实model调用/费用为0；更改上限须新policy Artifact并受Host ceiling约束。
- 先固定baseline Composition/state revisions、历史采样边界、fixture、seed、Evaluator和criteria hash，再生成候选；预期正确结果由人工批准的fixture给出，不从候选输出反推。
- collector保留source Evidence/Fact引用、redaction policy和fixture构建provenance；缺源数据/不可确定预期时退出为“证据不足”，不伪造pass。
- ChangeSet严格校验expected old-value hash、路径重复/排序、允许操作及契约；生成不可变Candidate/Composition，绝不修改baseline。
- 按RP-06已发布接口登记ChangeSet/Candidate/World；禁止直接调用Runtime store、把ArtifactId冒充CandidateId，或假定`run_experiment`会自动创建缺失对象。
- baseline/candidate分别在fresh cloned State/workspace执行同seed fixtures，不共享live cache/temp；World使用fake Model、network DENY、空credential_handles。
- Backend不支持任一required constraint则Experiment INVALID并停止，不把Portable/Fake AgentOS宣称为强隔离；所需生产Managed能力未交付时对应profile不得发布。
- 所有required assertions须通过，且预声明slot匹配pass rate严格优于baseline、回归fixture不下降；缺值/unknown/无提升均不Promotion。
- 第一个合格候选结束本轮搜索；预算/次数耗尽或全部拒绝时记录结果并退出，不递归生成新Proposal、不自动补充权限/预算。
- 自动源码生成或新package候选留待后续profile：先关闭新版本安装、catalog归属和验证/实验/批准链路，禁止跨外部installation拼装Composition。

## 批准、晋升与回滚

1. 批准预览展示baseline/candidate/ChangeSet、Evidence/Evaluation/criteria/evaluator hash、权限/State影响、expected meta/serving revision及plan hash。
2. operator签署Runtime Contract规定的CommandEnvelope字段；Seed只能请求签名，不读取Root私钥。签名绑定不全或缺公开验证入口时RP-07不关闭。
3. Evo循环只经`Evolution.Promote`提交desired，由Reconciler完成serving；批准后版本/权限/证据漂移须重新验证和批准，不复用旧签名。
4. UNKNOWN effect、FAILED Evaluation、未知assertion、缺Evidence、hash错误、权限增长或stale revision全部拒绝；失败保持旧serving与production State。
5. Rollback使用公开入口创建新transition，目标必须仍installed且制品可读；State迁移单独计划，不宣称撤销已发生external effect。
6. Evaluator升级必须新Artifact与独立批准，在冻结Evidence上重评，保留旧Evaluation；本轮候选不能修改用来裁决自己的Evaluator/criteria。
7. 升级Seed发行包复用S03；候选配置晋升与Harness发行包升级分别记录operation、批准和drain结果，不直接覆盖旧包。

## 交付物与验证命令

- `evolution/collector.py`、`candidate.py`、`policy.py`、`approval.py`及collector/policy/fixture/criteria制品。
- `tests/acceptance/test_evolution_pipeline.py`：经公开接口从历史到配置修复及why/lineage，无DB种子对象旁路。
- `tests/contract/test_evolution_policy.py`：预算/次数、无提升/证据不足、clone隔离、unsupported World及所有拒绝路径。
- `tests/contract/test_evolution_governance.py`：签名绑定、旧值hash、越权/跨包、裁判独立与重评。
- `tests/acceptance/test_evolution_release.py`：批准、切换失败、drain/卸载、Rollback及重启恢复。

在Seed仓库运行：

```console
python -m pytest -q tests/contract/test_evolution_policy.py tests/contract/test_evolution_governance.py
python -m pytest -q tests/acceptance/test_evolution_pipeline.py tests/acceptance/test_evolution_release.py
python scripts/check_seed_traceability.py --profile evolution
```

## 退出门禁

- Proposal → ChangeSet → Candidate → Experiment → Evaluation → Promotion由真实历史构建的确定性fixture驱动跑通，因果链可why/lineage追溯；不宣称已证明真实模型效果提升。
- 失败实验或FAILED Evaluation不改变serving；promotion失败自动保持旧serving。
- Evaluator可被新版本替换并重评旧Evidence；不存在"改裁判后宣布自己获胜"的路径。
- 无任何路径绕过`Evolution.Promote` gate直接修改serving Composition。
- 新版本AMPAK通过S03全部门禁且支持矩阵只列实际通过的Runtime版本。
- SH-EVO-01/02、SH-GOV-01/02通过，Runtime依赖和Backend约束全部有运行证据；fixture配置修复能力与未来自主代码演化明确区分。

## 在演化梯度中的定位

S07是自迭代闭环的第一层（配置修复）：开放`REWIRE`/`SET_POLICY`，确定性fixture评判，operator显式触发。后续按风险递增逐层解锁，Runtime机制不变，只新增Harness侧策略与制品：

1. **S08 工具/skill制品演化**：开放`REPLACE_ARTIFACT`/`ADD_SLOT`（artifact kind白名单，不含可执行源码），触发改为失败历史驱动的事件触发（有界），确定性assertion为必要条件、真实模型metric为可选profile——见[Seed_Harness_08](Seed_Harness_08_Tool_Skill_Evolution.md)。
2. **S09 harness代码自演化**：候选不再是Composition ChangeSet而是新AMPAK包版本，复用S03全部门禁与§41.60.5升级路径——见[Seed_Harness_09](Seed_Harness_09_Harness_Code_Evolution.md)。

以下不变式贯穿全部梯度，任何一层不得放宽：Evaluator/criteria与被评对象分离且候选不得修改裁决自己的Evaluator；`Promote`/`Activate`的operator签名门禁保留；实验期间baseline serving与production State不变；失败候选fail-closed并保留证据；无递归无界的常驻自动循环。
