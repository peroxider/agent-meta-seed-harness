# Seed Harness Step S03 — Integration and Release

> 归属：外部项目  
> 状态：PLANNED  
> 前置：S00/S01/S01A/S02 VERIFIED
> Runtime规范定位：§41.53、§41.58、§41.60.6、§45 AC-M17/M48

## 目标

在Seed仓库独立证明与声明Runtime版本的兼容性，并独立发布Seed distribution与AMPAK。

## 输入与发布范围

输入为最终Seed源码/lock、已关闭的基线Runtime依赖、S02测试与签名配置。
首个`minimal`版本提供fake Provider + Seed echo的可安装闭环，不声称已提供S04～S07能力。
后续`provider/tools/session/evolution`版本按[追踪表](Seed_Harness_Traceability.md)累积验收并复用本步发布流程；非所有后续工作都必须等到S07才发布。

## 实施顺序

1. 对每个声明支持的Runtime minor pin公开wheel、SDK和contract golden。
2. 执行SDK compile、manifest validate、Install/Activate/Task/Deactivate/Uninstall全链路。
3. 覆盖Runtime restart、旧serving保留、health失败、grant deny和残留引用。
4. 执行AC-M17的Seed Loop E2E及AC-M48的确定性/文本无副作用矩阵。
5. 生成Seed自己的SBOM、provenance、compatibility report和release notes。
6. 发布distribution与签名AMPAK；不得修改Runtime wheel、schema或release manifest。
7. 完成`check_seed_traceability.py`：校验需求ID集合、具名测试收集、required无skip/xfail、依赖关闭与证据hash，不只检查测试文件存在。
8. 用新name/version包验证install → validate/experiment → activate → drain旧版 → uninstall；health失败保留旧serving，禁止原地替换包。

## 交付物与验证

- `tests/acceptance/test_release_lifecycle.py`、`tests/contract/test_release_evidence.py`及三个固定外部证明路径。
- `reports/<profile>/`下的JUnit/环境/制品hash，`docs/compatibility.md`、release notes、SBOM/provenance和签名AMPAK。
- Runbook覆盖init/start/stop、上传/安装/批准激活、Task/why、升级/停用/卸载、取消与UNKNOWN处置；扩展版补Provider配置、会话恢复及演化批准。
- clean-install job只使用wheel/AMPAK及公开契约；Linux/Windows各自运行，macOS按实际smoke声明；无Runtime/Seed相邻checkout。

在Seed仓库运行（初版使用`minimal`，扩展版另运行对应profile）：

```console
python -m pytest -q tests/contract tests/acceptance --ignore=tests/acceptance/test_live_provider.py
python scripts/check_seed_traceability.py --profile minimal
python -m build --no-isolation
```

live Provider证明由S04的显式job另行执行；发布判定合并离线/online报告，缺live证据只允许声明replay支持。

## 发布门禁

- AC-M17、AC-M48和NFR-M48在Seed CI中通过。
- 支持矩阵只列实际通过的Runtime版本和Backend feature profile。
- Seed安装、升级、停用和卸载全部使用公共SDK/local RPC。
- Seed CI失败只阻塞Seed发布，不改变Runtime release conclusion。
- SH-REL-01/02通过；证据绑定最终wheel/AMPAK/源码hash，构建后改源码或lock必须重跑受影响检查。
- Runtime安全/Host前置能力尚不可用时，不以fixture或INSECURE_TEST_ONLY profile作为产品安全支持证据。
