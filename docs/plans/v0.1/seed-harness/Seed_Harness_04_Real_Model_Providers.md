# Seed Harness Step S04 — Real Model Providers

> 归属：外部项目  
> 状态：PLANNED  
> 前置：S03 VERIFIED，RP-03及本步使用的公开Host入口关闭
> Runtime规范定位：§41.36.2、§41.44.4、§41.55、§22.1

## 目标

在S02 terminal-only adapter与fake provider之上接入真实Model Provider，同时保持确定性测试路径与真实路径共用同一条规范化管线。

## 输入与范围

输入为S03发布包、Runtime凭据/egress enforcement、显式批准的live测试配置及预算。
首发只实现一个Provider和一个model profile；供应商、endpoint、model ID、SDK版本、exact tokenizer及计价版本必须在`docs/provider-profile.md`中固定后进入live集成。
多Provider目录为后续扩展；本步不做自动路由、模型fallback、公开streaming或联网业务工具。

## 实施顺序

1. 定义Provider profile Artifact：model_id、参数allowlist、exact tokenizer、rate limit与finish reason映射；tokenizer不可用时model invocation前返回`FAILED_PRECONDITION`，不以字符数猜token。
2. 实现首个真实Provider adapter；credential只经Credential Store handle（§41.55）取得，任何secret不进入Fact、Artifact、Projection或日志。
3. 声明上游durable request lookup/idempotency支持矩阵，仅在上游支持时实现lookup：连接中断且无durable lookup时返回`EXTERNAL_EFFECT_UNKNOWN`，Retry Policy不自动重复调用；只有可证明未接纳且policy允许时才允许幂等重试。
4. 接入R2 captured-response replay：录制真实响应为fixture，确定性测试矩阵（NFR-M48）继续全绿。
5. Provider/profile进入capability surface声明；usage、finish reason、rate limit规范化与fake provider走同一代码路径。

## 安全、预算与恢复

- 在RP-03明确Provider worker placement与凭据注入接口；只有Runtime enforcement可解析scoped handle，secret不经Loop/普通DTO/Artifact/env dump返回。
- live请求按policy的scheme/host/port及解析IP/redirect检查授权；其egress与Experiment World的network DENY隔离，缺能力fail closed。
- unknown token/cost保持unknown，不填0；有硬cost ceiling却无法在调用前给出最大成本时返回`FAILED_PRECONDITION`。
- profile冻结max output tokens、context窗口、usage映射和定价版本；分别验证token预算、调用次数、effect与cost reservation/settlement及overrun。
- rate limit映射`RESOURCE_EXHAUSTED`与retry_after；重试attempt需持久化，不凭客户端超时推断Provider未接受请求。
- 覆盖请求发送前失败、已接受后断线、lookup命中/不可用、调用完成后提交前崩溃、cancel/deadline与迟到响应。
- 若Adapter内部消费stream，只在完整terminal后交付规范化response；取消/中断不让partial内容进入tool dispatcher。
- R2默认保存脱敏的规范化响应及允许的usage/finish信息；raw retention默认关闭，开启须经Restricted Raw Artifact路径，不把token/header/request secret录成fixture。

## 交付物与验证命令

- `providers/<selected_provider>.py`、`docs/provider-profile.md`及profile/Retry/egress/redaction/price policy制品。
- `tests/contract/test_provider_contract.py`、`test_provider_security.py`、`test_provider_replay.py`和去敏R2 fixtures。
- `tests/acceptance/test_live_provider.py`：显式启用、限定次数/费用/超时，不因缺凭据返回伪成功。

在Seed仓库运行离线证明与独立live job：

```console
python -m pytest -q tests/contract/test_provider_contract.py tests/contract/test_provider_security.py tests/contract/test_provider_replay.py
python -m pytest -q tests/acceptance/test_live_provider.py
python scripts/check_seed_traceability.py --profile provider
```

## 退出门禁

- 相同请求+相同captured response产生相同ArtifactId；真实路径与fake路径只差transport层。
- 网络故障场景下无durable lookup不产生重复model invocation。
- Provider credential只以handle形式出现在manifest/grant/Artifact；redaction与doctor扫描无泄漏。
- budget按Provider profile声明的exact tokenizer计数。
- SH-PROV-01/02/03及minimal门禁通过，RP-03有公开wheel证据；未运行live job的版本仅可声明replay能力。
- 按S03发布新版本并披露实际model/profile，不以fake或R2回放宣称上游行为已实测。
