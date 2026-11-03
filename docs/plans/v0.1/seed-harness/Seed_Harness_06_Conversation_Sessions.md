# Seed Harness Step S06 — Conversation Session Model

> 归属：外部项目  
> 状态：PLANNED  
> 前置：S05 VERIFIED，RP-04/RP-05关闭
> Runtime规范定位：§41.44.1、§41.44.4、§41.25、§41.53

## 目标

把多轮对话落地到Runtime Task模型上：会话是Managed State绑定，一条用户消息是一个Task，跨Task上下文全部可追溯、可回放。

## 输入与首版范围

输入为S05包、公开State CAS和稳定命令重放/查询能力、固定Context与summary policy。
首版每Realm仅一个活动会话、每会话至多一个未完成消息；并发接纳、分支、多会话路由及自动merge延期。
`session_id → transcript_state_id + command_journal_state_id`记录在会话配置并由当前Composition显式绑定；切换新会话须创建/绑定新State并经过正常Composition切换，不把用户提供的任意state_id直接当作授权。

## 实施顺序

1. 定义session state schema（transcript摘要 + 会话配置），经Composition `BIND_STATE`绑定；Experiment只能从baseline clone新state_id，禁止写production state_id。
2. 每条用户消息提交为新Task：input artifact + 冻结的session state revision + budget；terminal输出作为独立durable command写回session state（`expected_state_revision_id`，`REVISION_CONFLICT`不自动merge）。
3. Context组装按§41.44.4预算顺序执行：system/constitution → task input → capability/tool schema → state summary → causally relevant facts；tokenizer取Provider profile。
4. 提供最小交互前端（REPL或CLI扩展），只经公共SDK/local RPC，不引入新协议面。
5. 会话诊断：why/lineage查询能解释一次完整多轮会话中的任意一轮。

## Seed应用schema与消息提交协议

交付`schemas/seed/session/v1`与`schemas/seed/session-command-journal/v1`，它们是Managed State内容schema，不新增Runtime实体或Task字段。
内容包含session/config/policy版本、顺序消息引用、summary及来源边界，以及至多一项pending消息；消息原文/结果仅引用授权的脱敏Artifact。
消息项记录`message_id,input_artifact_id,task_id,terminal_status,result_artifact_id`；pending记录稳定submit/writeback command身份及journal引用，提交前未知的Task/terminal字段显式可空。
完整可重放命令保存在独立journal State，按message/stage唯一登记并拒绝同键不同hash；写journal不得改变待写transcript的expected revision，避免把writeback命令写进目标State后使自己立即过期。
Context只读取会话配置、已提交消息和有来源摘要；pending控制字段、journal及授权签名不进入模型Projection，当前用户输入只出现一次。
完整schema在Seed版本中冻结并配golden；summary必须记录covered message refs、renderer/tokenizer/redaction版本，不能只有不可追溯摘要。

1. REPL生成稳定message_id；先将input Artifact和pending状态经CAS持久化，再调用Task.Submit。相同message_id/相同输入只恢复原操作，不生成新Task；不同输入返回冲突。
2. 提交前向journal持久化公开命令的完整可重放表示（含版本、command_id、payload、目标State expected revision及必要授权字段）；只用RP-05公开机制重放/查询，不能让SDK重试生成新command_id。
3. Task receipt写回pending；写回只更新协调元数据，不改变已接纳Task的冻结snapshot。原始提交结果丢失时先查/重放原command，不猜Task是否存在。
4. 从Task.Get/Wait取得已committed terminal；用原Task结果和当前transcript revision构造writeback command并先登记journal，再将terminal消息引用追加一次并清pending。失败/取消Task也记录terminal status。
5. terminal和session writeback是两个事务：写回前崩溃只补写已知结果，不重调模型；写回后响应丢失时确认同command/message已提交，不重复追加。
6. 每次State写携带已观察expected revision；CAS冲突停止本轮协调并报告，只有确认相同command已完成可作为幂等成功，不自动合并外部修改。
7. 客户端仅在writeback提交后确认本轮会话完成/接纳下一条；断线不取消Task。重启先处理pending，再开放新消息接纳。
8. 模型工具不得直接写transcript/pending/journal State；必要的业务State单独绑定。实验只使用clone，升级须保留/显式迁移会话schema及绑定。

RP-05须证明原command重放先于新命令revision校验；上述协调命令使用Contract允许的无全局meta guard路径和目标State CAS。若协议强制全局meta guard，则Runtime须提供原子prepare/execute等正式机制并版本化交付，不能在写journal后重签同一command来规避冲突。
journal自身CAS写丢响应时，先按message/stage/hash读取确认已登记；缺失且observed revision未变才重试，发生外部修改则报告冲突，不递归为journal写创建另一份journal。
授权nonce/签名的保留和重放必须遵守Runtime安全契约；不保存密钥或bearer secret。若公开命令契约不能跨重启安全恢复，RP-05保持OPEN，不以Seed本地SQL或任意文件日志替代。
恢复模型/effect本身仍由Host执行；Seed会话协调器只能恢复Task提交和结果写回，不能将UNKNOWN Task重新提交为新Task。

## 交付物与验证命令

- `session.py`、`repl.py`、两份Seed session/journal schema、summary/config/migration policy及操作runbook。
- `tests/contract/test_session_consistency.py`：去重/不同payload冲突、并发拒绝、summary provenance、journal写不使transcript命令自过期、控制字段不进Projection、State冲突与serving冻结。
- `tests/acceptance/test_session_recovery.py`：pending后/Task提交前、接受后receipt丢失、terminal后/writeback前、writeback后响应丢失逐点终止并重启。
- 对每个恢复场景断言Task数、Provider调用/effect次数和transcript追加数；同时验证失败/取消、升级和UNKNOWN不盲重试。

在Seed仓库运行：

```console
python -m pytest -q tests/contract/test_session_consistency.py tests/acceptance/test_session_recovery.py
python scripts/check_seed_traceability.py --profile session
```

## 退出门禁

- 进程重启后仅从committed session state恢复会话，无内存态依赖。
- 相同会话revision + 相同输入产生相同Redacted Projection Artifact。
- secret在Rank前被redact，不因排序影响摘要。
- 会话内每轮Task冻结的serving revision不随全局指针漂移。
- SH-SESS-01/02通过，RP-05丢响应/崩溃证明通过；会话恢复不依赖进程内状态、不重复已确认的模型调用或结果追加。
- 按S03发布session profile新版本，文档明确单Realm单活动会话限制及冲突处置。
