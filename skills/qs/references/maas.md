# MaaS 模型即服务

1. 查看在线服务：`qs maas server list --format json -q`（`--scope my/all`、`--search`、`--brand`、`--source` 过滤）
2. 申请配额（分步收集参数）：
   - 必填：`--server-id`、`--tree-path`（业务目录树路径）
   - 可选：`--scene`（online/offline）、`--tpm`、`--rpm`、`--desc`
   - 参数收齐后：`qs maas quota apply ... --yes`
3. 查看 Token 用量概览：`qs maas usage get --start 2026-04-01 --end 2026-04-09 --format json -q`
4. 查看 Token 用量明细：`qs maas usage list --start 2026-04-01 --end 2026-04-09 --format json -q`
5. 查看已审批配置：`qs maas config list --format json -q`
6. 查看服务 Token 列表：`qs maas token list --server-id <id> --format json -q`
7. 查看模型品牌：`qs maas brand list --format json -q`
8. 停止服务（不可逆，清零配额）：`qs maas server stop --project-id <pid> --server-id <sid> --yes`（需先确认用户意图）
