# 告警 Skill 绑定规则

这份文档用于把新建或更新后的告警 Skill 绑定到告警规则。绑定是创建/发布阶段的写操作，只能在用户明确要求绑定、替换或发布时执行；不得写进生成后的告警 Skill 运行时逻辑。

## 前置确认

执行前确认：

- `xray-cli` 版本不低于 `v0.0.31`。
- 当前登录身份有上传 Skill 和绑定告警规则的权限。
- 用户已明确给出或确认 `rule_id`。
- 目标 Skill 已经完成真实历史告警验证，或用户明确接受未验证风险。

## 绑定流程

1. 上传 Skill，记录返回的 `skill.name`。

   ```bash
   xray-cli alarm skill upload <skill_dir>
   ```

   `upload` 只会创建 Skill 或新版本，不会自动绑定告警规则。同名重复上传会创建新版本。

2. 确认告警规则 ID 和绑定类型。

   ```bash
   xray-cli alarm rule get <rule_id>
   ```

   规则详情里 `basic.type=pql` 时，绑定命令使用 `--type promql`；`basic.type=service` 时，使用 `--type service`；前端告警使用 `--type frontend`。如果规则类型无法确认，先查规则详情或告警事件，不要猜。

3. 查看规则当前已绑定的 Skill，明确替换影响面。

   ```bash
   xray-cli alarm skill list --rule-id <rule_id> --type <frontend|service|promql>
   ```

4. 绑定新 Skill。

   ```bash
   xray-cli alarm skill bind \
     --type <frontend|service|promql> \
     --rule-id <rule_id> \
     --skill <skill_name>
   ```

   `bind` 会先解绑同一规则、同一类型下已有的 Skill，再绑定新的 Skill。输出里的 `unbound_skills` 是本次被替换掉的旧 Skill ID，必须在结果中告知用户。

5. 绑定后复查。

   ```bash
   xray-cli alarm skill list --rule-id <rule_id> --type <frontend|service|promql>
   xray-cli alarm skill list --skill <skill_name> --type <frontend|service|promql>
   ```

6. 用历史告警验证绑定后的实际效果。

   ```bash
   xray-cli alarm event list \
     --rule-id <rule_id> \
     --start "<开始时间>" \
     --end "<结束时间>" \
     --page-size 5

   xray-cli alarm skill test \
     --skill-name <skill_name> \
     --alarm-event-id <历史告警事件 ID> \
     --stream
   ```

## 回滚

如果绑定后需要回滚，用第 4 步同样的 `bind` 命令把 `unbound_skills` 里的旧 Skill 重新绑回去。

不要使用 `delete` 回滚绑定；删除 Skill 是另一类高风险写操作。

## 输出给用户

绑定完成后输出：

- 上传后的 `skill_name` 和版本信息。
- 绑定的 `rule_id` 和 `type`。
- `bind` 返回的 `bound` 状态。
- `unbound_skills`，如果为空也明确说明没有替换旧 Skill。
- 复查命令结果。
- 历史告警测试结果；如果没有历史告警 ID，明确标记为未验证项。
