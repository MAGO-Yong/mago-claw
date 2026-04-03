---
name: service-tree-query
description:
  查询 Xray 服务树节点信息，解析服务归属的 prdLine/bizLine/app/service
  层级路径。当用户输入服务名称、询问其在服务树中的归属（产品线/业务线/app），或需要确认某个名称是
  service 还是 app 时触发。
metadata:
  category: service-tree
  platform: xray
  trigger: service_name/app_name
  input: [service]
  output: [full_path, prdLine, bizLine, app, service]
  impl: python-script
---

# 服务树查询

## 能力说明

通过 Xray OpenAPI 查询服务节点的完整服务树路径，解析出各层级归属（prdLine、bizLine、app、service）。

## 服务树层级说明

```
prdLine（产品线）> bizLine（业务线）> app > service
```

## 工作流程

### Step 1：执行查询脚本

```bash
python3 {SKILL_DIR}/scripts/query_service_tree.py --service <service_or_app_name>
```

> `{SKILL_DIR}` 为本 skill 所在目录的绝对路径，执行时必须使用绝对路径。

**调用示例：**

```bash
python3 {SKILL_DIR}/scripts/query_service_tree.py --service xrayaiagent-service-diagnosis
```

### Step 2：输出结果

脚本输出 JSON，单节点返回对象，多节点返回数组。字段说明：

| 字段        | 含义                              |
| ----------- | --------------------------------- |
| `name`      | 节点名称                          |
| `full_path` | 完整服务树路径（去掉顶级 xhs）    |
| `prdLine`   | 产品线                            |
| `bizLine`   | 业务线                            |
| `app`       | App                               |
| `service`   | Service（若输入为 app 则为 null） |

**输出示例**（输入 `xrayaiagent-service-diagnosis`）：

```json
{
  "name": "xrayaiagent-service-diagnosis",
  "full_path": "base.obs.xrayaiagent.xrayaiagent-service-diagnosis",
  "prdLine": "base",
  "bizLine": "obs",
  "app": "xrayaiagent",
  "service": "xrayaiagent-service-diagnosis"
}
```

展示给用户时，按层级格式化输出：

```
服务全路径：base.obs.xrayaiagent.xrayaiagent-service-diagnosis
- 产品线 (prdLine)：base
- 业务线 (bizLine)：obs
- App：xrayaiagent
- Service：xrayaiagent-service-diagnosis
```

## 错误处理

| 错误情况       | 处理方式                                         |
| -------------- | ------------------------------------------------ |
| 脚本退出码非 0 | 将 stderr 内容返回用户                           |
| 未找到节点     | 告知用户该名称在服务树中未找到，确认拼写是否正确 |
| 返回多个节点   | 逐条展示每个节点的完整路径及层级信息             |
| 网络不通       | 提示用户确认是否在内网环境                       |
