# Calendar References

`references/` 只保留 3 类材料：

- [api-analysis.md](./api-analysis.md)
  - 会议创建 / 修改 / 删除相关接口分析
- [cli-design.md](./cli-design.md)
  - `run.sh` / `cli.ts` / `service.ts` 当前分层与命令设计
- [verification.md](./verification.md)
  - 基于真实登录态的回放结果与已确认结论

使用建议：

1. 想补接口或字段时，先看 `api-analysis.md`
2. 想改命令、Skill 路由或模块边界时，先看 `cli-design.md`
3. 想确认哪些结论已经被真实验证，先看 `verification.md`
