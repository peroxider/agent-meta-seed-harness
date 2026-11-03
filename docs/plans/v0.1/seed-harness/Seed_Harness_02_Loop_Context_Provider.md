# Seed Harness Step S02 — Loop, Context and Provider

> 归属：外部项目  
> 状态：PLANNED  
> 前置：S01/S01A VERIFIED，RP-00～RP-02关闭
> Runtime规范定位：§40.2、§41.11、§41.36、§41.44.4、§41.53

## 目标

实现最小但有用的Seed行为：Model、Task/Event、Loop、Context和tool dispatch policy，不把策略放回Runtime。

## 输入与范围

输入为S01A公开Host facade/DTO与S01包、loop policy、冻结snapshot和fake Provider脚本。
terminal-only表示一次调用只交付完整规范化response，不表示禁止tool calls；本阶段不接真实网络Provider。
交付Seed自有确定性echo Capability供S02/S03使用，不依赖S05，也不导入Runtime test-only Conformance Harness。

## 实施顺序

1. 实现terminal-only Model Provider adapter并规范化usage、finish reason、rate limit和tool calls。
2. 实现deterministic Context selection，先redact再排序/budget并保留provenance。
3. 实现bounded Loop，读取manifest loop policy并受Runtime hard ceiling约束。
4. 纯文本输出只形成content Artifact；只有typed `tool_calls`进入公共dispatch DTO。
5. tool calls按响应顺序串行，重复call id、未知kind和schema错误fail closed。
6. 实现fake provider场景：text、LENGTH、单/多tool、空响应、错误finish、budget exhaustion。
7. 经公开Host请求记录Action/Invocation/Fact因果链，Adapter不直接commit，不保存provider-native object为协议状态。

## Loop与恢复验证

- call_id在整个Task内唯一；单响应最多16个tool calls，校验冻结surface、operation contract及input schema后才申请执行。
- 覆盖纯text/JSON/artifact、多text part、LENGTH截断标记、空response、非法tool_result、错误finish reason及重复call_id跨turn场景。
- 混合text/tool保留assistant history，串行执行工具后进入下一turn；完整ContentPart数组形成terminal结果，不把历史内容误当终态。
- 模型调用和每个tool各消耗一个step；turn/model/effect/cost/deadline分别测试边界，取消不得释放已消费调用计数。
- `stop_on_tool_error=true/false`分别验证；任何可继续错误也不能绕过下一工具的Authority/budget/feature检查。
- Task deadline包含排队等待；所有外部await使用Task/operation较早deadline，cancel从Host传播到Provider/tool/worker。
- 注入取消前调用、调用中断、已知Invocation结果提交后/Task terminal前崩溃及丢响应；已知结果恢复不重执行，未知非幂等effect停止自动重试。
- Context按§41.44.4预算与溢出规则执行，tokenizer/renderer/redaction/policy版本均入provenance；固定clock/ID或声明语义归一化后比较状态序列。
- 默认不留raw response，只有显式Raw Retention Policy允许时通过Host保存Restricted Raw Artifact。

## 交付物与验证命令

- `loop.py`、`context.py`、`providers/fake.py`、`capabilities/echo.py`及其contract/policy/fixture制品。
- `tests/contract/test_loop_semantics.py`、`test_context_projection.py`、`test_tool_dispatch.py`、`test_loop_recovery.py`、`test_nfr_m48.py`。
- `tests/acceptance/test_ac_m17.py`、`test_ac_m48.py`使用实际公开Host与Seed自有echo，S03在干净发布环境复验。

在Seed仓库运行：

```console
python -m pytest -q tests/contract/test_loop_semantics.py tests/contract/test_context_projection.py tests/contract/test_tool_dispatch.py tests/contract/test_loop_recovery.py tests/contract/test_nfr_m48.py
python -m pytest -q tests/acceptance/test_ac_m17.py tests/acceptance/test_ac_m48.py
```

## 退出门禁

- 相同provider terminal response、snapshot和budget产生相同状态序列与内容ArtifactId。
- 文本中的JSON/shell/tool形似指令不会触发Capability或Backend effect。
- Provider重试只发生在可证明未接纳且policy允许的幂等场景。
- 满足外部NFR-M48的确定性要求。
- SH-LOOP-01/SH-CTX-01/SH-TOOL-01/SH-REC-01通过；重启证明不得通过手工修改Runtime状态或mock readiness完成。
