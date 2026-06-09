# 数据集管理

1. 查询：`qs dataset list --scope my --format json -q`
2. 详情：`qs dataset get <id> --format json -q`
3. 创建：按 [creation-protocol.md](creation-protocol.md) UCP 流程执行。RESOLVE 要点：
   - **input-dir 必须是 `oss://` 路径**（如 `oss://bucket/path/to/data`）。`/cloudfs/` 和 `/mnt/` 是 Pod 挂载路径，不能直接使用。如果用户只给了挂载路径，直接用文字告知需要 `oss://` 路径（不要用 AskUserQuestion）
   - format 从文件后缀推导（.jsonl→jsonl, .parquet→parquet）
   - desc 自动生成
   - dst-cluster 运行 `qs dataset clusters -o json -q` 后选使用率最低的集群
   - 所有必填参数 resolve 完毕后 PREVIEW → 确认 → `qs dataset create ... --yes`
4. 同步：`qs dataset clusters --format json -q` 查集群 → `qs dataset sync <did> <vid> --cluster <c>`
5. 查路径：`qs dataset storage-path <did> <vid> --cloud-id <cid> --format json -q`
