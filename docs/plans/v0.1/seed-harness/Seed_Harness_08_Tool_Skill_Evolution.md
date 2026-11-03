# Seed Harness Step S08 — Tool/Skill Artifact Evolution

> 归属：外部项目  
> 状态：PLANNED  
> 目标版本：Seed v0.2（演化梯度第2层，见S07"在演化梯度中的定位"）  
> 前置：S07 VERIFIED；真实模型实验World与制品类criteria所需的Runtime能力已按ADR/Contract规则发布  
> Runtime规范定位：§41.43、§41.32、§41.53、§24

## 目标

把S07的演化对象从"配置接线"扩展到"工具与skill制品"：agent在任务执行中产生的失败历史可以事件驱动地触发Proposal，候选通过`REPLACE_ARTIFACT`/`ADD_SLOT`替换或新增工具descriptor、skill文档与prompt policy制品，在World中实验后经Promotion生效。触发不再要求operator逐次手动发起，但`Promote`上的operator签名门禁保留。

## 输入与首个验收场景

输入为S07包、真实任务的脱敏失败历史（工具调用失败、schema违规、超时重试模式）、已发布的演化Host/API及授权操作者。
首个场景改进一个既有工具的descriptor/skill文档：从历史定位高频失败调用模式，生成单个`REPLACE_ARTIFACT`候选（新工具descriptor或skill文档），与冻结的正确行为fixture比较，确定性assertion全部通过后Promotion。
不新增可执行源码、不扩大权限、不修改Evaluator/criteria、不触碰harness包源码（该路径归S09）。

## 实施顺序

1. 事件驱动触发策略：policy Artifact登记触发条件（失败模式阈值、采样窗口、冷却期），harness内collector从Fact/Evidence流聚合，满足条件时自动产出Proposal（hypothesis + source_evidence_ids）；每个触发窗口的Proposal/Candidate/Experiment数量有上限。
2. 开放`REPLACE_ARTIFACT`/`ADD_SLOT`：限定artifact kind白名单（tool descriptor、skill文档、prompt policy），生成器与admission两处校验；每项带target path、expected old value hash与new value，只生成新Composition，不修改baseline。
3. 分层criteria：确定性assertion（test_suite、artifact_integrity、compatibility_report、budget）为Promotion必要条件；真实模型metric断言作为可选profile，须显式声明`max_cost_microunits`与`max_wall_time_us`，缺预算或缺live profile时该断言INVALID而非默认通过。
4. 真实模型实验World：复用Experiment框架，真实模型调用走S04 Provider链路与credential handle；fake fixture实验与真实模型回归分开记录；真实模型结果只影响声明为required的metric断言，不推翻已记录的确定性结论。
5. Promote/Rollback复用S07全部路径；批准预览新增制品前后内容diff与受影响工具调用面说明。

## 有界策略与制品链

- 触发有界：每个触发窗口默认最多1个Proposal、2个Candidate、2个Experiment；冷却期内同一target_path不重复propose；上限由policy Artifact声明并受Host ceiling约束，agent不可自行调高。
- 候选制品内容由历史evidence与人工批准的模板/约束生成，预期结果来自人工批准的fixture，不从候选输出反推；缺源数据或不可确定预期时退出为"证据不足"，不伪造pass。
- 工具/skill制品不得携带可执行代码载荷：artifact kind白名单在生成器与admission两处校验，越界即INVALID并停止本轮。
- 真实模型实验成本硬上限，超限即FAILED不重试；未过required断言不Promotion，无论确定性assertion多好。
- Evaluator/criteria/fixture hash先冻结再生成候选；本轮候选不得修改用来裁决自己的Evaluator/criteria。
- baseline/candidate分别在fresh cloned State/workspace执行，不共享live cache/temp；实验期间baseline serving不变。

## 批准、晋升与回滚

1. 批准预览在S07字段之上增加：候选制品canonical JSON diff hash、受影响工具/skill调用面、触发窗口内被采纳/拒绝的历史Proposal引用。
2. agent可以propose与run_experiment，不得签署`Promote`；operator签署CommandEnvelope规定字段，签名绑定不全则拒绝。
3. Rollback与S07一致：创建指向父Composition的新transition；制品类晋升回滚后，受影响工具按旧制品执行。
4. 升级Seed发行包复用S03流程；候选制品晋升与Harness发行包升级分别记录，不直接覆盖。

## 交付物与验证命令

- `evolution/tool_trigger.py`、`artifact_candidate.py`、`artifact_criteria.py`及trigger policy/criteria/fixture制品。
- `tests/acceptance/test_evolution_tool_pipeline.py`：失败历史→事件触发→artifact候选→确定性实验→Promotion，因果链可why/lineage追溯，无DB种子对象旁路。
- `tests/contract/test_evolution_artifact_policy.py`：触发窗口/冷却期/数量上限、artifact kind白名单、真实模型成本上限与INVALID路径。
- `tests/contract/test_evolution_artifact_governance.py`：agent不可签名、制品diff预览、旧值hash、越权/跨包与evaluator独立。

在Seed仓库运行：

```console
python -m pytest -q tests/contract/test_evolution_artifact_policy.py tests/contract/test_evolution_artifact_governance.py
python -m pytest -q tests/acceptance/test_evolution_tool_pipeline.py
python scripts/check_seed_traceability.py --profile evolution-artifact
```

## 退出门禁

- 事件驱动的Proposal由真实失败历史驱动，触发策略全部有界且因果链可why/lineage追溯。
- 确定性assertion是Promotion的必要条件；真实模型metric断言仅在有预算与live profile时可声明为required，否则一律作为观察项不计入判定。
- 无任何路径让候选携带可执行源码、扩大权限或修改Evaluator/criteria。
- `Promote`签名门禁保留；失败实验与FAILED Evaluation不改serving。
- SH-EVO-03/04、SH-GOV-03通过。
