# Seed Harness Step S01 — Package Contract

> 归属：外部项目  
> 状态：PLANNED  
> 前置：S00 VERIFIED  
> Runtime规范定位：§41.24、§41.37、§41.42、§41.60.2～41.60.5

## 目标

把Seed实现构建成Runtime可验证但无需import的AMPAK与Harness manifest。

## 输入与范围

输入为S00锁定环境、公开manifest/AMPAK/Capability contract资源及publisher身份。
本步只验证包结构与安装无执行副作用；entrypoint实际调用交给[S01A](Seed_Harness_01A_Public_Host_Contract.md)。

## 实施顺序

1. 定义稳定`package_name`和SemVer，不复用已卸载的同Realm name/version。
2. 构建AMPAK1，固定依赖锁、entrypoint、path canonicalization和provenance。
3. 生成`harness-package/v1` manifest、publisher/signature Artifact。
4. 提供Capability descriptors、单package Composition模板和loop policy Artifact。
5. 提供最小scoped grant requests，不请求Root/private credential权限。
6. 声明Public/Harness/Capability contract range和Backend required/optional features；使用manifest固定字段，不新增preferred字段。
7. 用Runtime public SDK执行Validate golden与negative fixtures。
8. 固定最小包的Loop/Context/fake Provider/echo descriptor与entrypoint引用；S02补行为实现，S01A只使用无业务逻辑的最小Host探针。

## 交付物与验证

- `package/`下的manifest模板、Composition、loop policy、最小grant requests和Capability descriptors。
- canonical AMPAK构建命令、dependency lock、publisher/signature/provenance制品与`tests/fixtures/package/` golden/negative样本。
- `tests/contract/test_package_contract.py`覆盖路径穿越/碰撞、未知字段、错误hash/signature、contract无交集、越权grant、unsupported placement和name/version冲突。
- canonical内容hash只由规范化源码/lock等语义输入决定；签名时间和构建机信息单独记录到provenance，不混入可复现package payload；平台依赖差异分别锁定、分别列profile，不强求不同依赖包同hash。

在Seed仓库运行：

```console
python -m pytest -q tests/contract/test_package_contract.py
```

## 退出门禁

- 相同源码/lock在支持平台产生相同逻辑package内容和可验证hash。
- 未知字段、签名错误、contract无交集、越权grant和不支持placement全部fail closed。
- Install不执行Seed代码、不创建Grant/Composition/Task或Backend request。
- SH-PKG-01通过；发布前必须以最终S02实现重新构建、校验并签名，不能把Host探针包当作Seed行为实现。
- 所有AMPAK/entrypoint contract缺口进入RP台账；下一步为S01A，不能跳过Host接入直接宣布Loop可运行。
