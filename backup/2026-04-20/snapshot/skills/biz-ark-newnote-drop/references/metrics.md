# 数据绑定

## Step 1 · 分阶段新笔记占比 {#step-1}

| 字段 | 值 |
|------|----|
| 大盘 | ark-notefeed业务监控 |
| 图表 | [新笔记占比_笔记年龄1_24hr](https://monitor.devops.xiaohongshu.com/d/7ck8fwr4k/ark-notefeedye-wu-jian-kong?viewpanel=779) |
| 数据类型 | metrics |
| Datasource | vms-recommend |
| PQL | `sum by (stage) (rate(lownv_waterfall_total{application=~"$appid", env=~"$env", type="age", tag="(1hr,24hr]"}[1m]))` |
| 对比基准 | offset=7d（周同比） |
| 分析维度 | 按 stage 分组 |
| 关注 Stage | BEFORE_NOTEINFO / after_noteinfo_filter / recall / pre_fr / fr / final_rank / post_rank_top |

## Step 2 · 召回阶段分渠道新笔记量 {#step-2}

| 字段 | 值 |
|------|----|
| 大盘 | ark-notefeed业务监控 |
| 图表 | [召回阶段_分渠道新笔记量](https://monitor.devops.xiaohongshu.com/d/7ck8fwr4k/ark-notefeedye-wu-jian-kong?viewpanel=1103) |
| 数据类型 | metrics |
| Datasource | vms-recommend |
| PQL | `sum by (type) (rate(recall_newnote_waterfall_total{application=~"$appid", env=~"$env", name="day"}[1m]))` |
| 对比基准 | 告警时间点前后对比（无固定 offset） |
| 分析维度 | 按 channel(type) 分组，只看 TOP 10 |
| 过滤规则 | 召回量过小的渠道忽略（量级 < 整体 1% 忽略） |

## Step 3 · 召回 & 粗排多队列 {#step-3}

| 字段 | 值 |
|------|----|
| 大盘 | ark-notefeed业务监控 |
| 图表1 | [召回多队列分渠道数量](https://monitor.devops.xiaohongshu.com/d/7ck8fwr4k/ark-notefeedye-wu-jian-kong?viewpanel=1000) |
| 图表2 | [粗排多队列分渠道数量](https://monitor.devops.xiaohongshu.com/d/7ck8fwr4k/ark-notefeedye-wu-jian-kong?viewpanel=1042) |
| 数据类型 | metrics |
| Datasource | vms-recommend |
| 对比基准 | 告警时间点前后对比 |
| 分析维度 | 按队列(queue)分组 |

## Step 4 · 正排完整率 {#step-4}

| 字段 | 值 |
|------|----|
| 大盘 | ark-notefeed业务监控 |
| 图表 | [正排完整率](https://monitor.devops.xiaohongshu.com/d/7ck8fwr4k/ark-notefeedye-wu-jian-kong?viewpanel=683) |
| 数据类型 | metrics |
| Datasource | vms-recommend |
| PQL | `1-(sum by(xhs_zone)(rate(note_profile_stat_sum{application="$appid", name=~"missing\|invalid"}[1m])) / sum by(xhs_zone)(rate(note_profile_stat_count{application="$appid", name=~"missing\|invalid"}[1m]))) / (sum by(xhs_zone)(rate(note_profile_stat_sum{application="$appid", name=~"total"}[1m])) / sum by(xhs_zone)(rate(note_profile_stat_count{application="$appid", name=~"total"}[1m])))` |
| 异常阈值 | 完整率明显下降（相对历史基线下跌 > 1%） |
| 分析维度 | 按 xhs_zone 分组 |

## Step 5 · 正排字段异常率 {#step-5}

| 字段 | 值 |
|------|----|
| 大盘 | ark-notefeed业务监控 |
| 图表 | [正排字段异常率](https://monitor.devops.xiaohongshu.com/d/7ck8fwr4k/ark-notefeedye-wu-jian-kong?viewpanel=824) |
| 数据类型 | metrics |
| Datasource | vms-recommend |
| PQL | `sum by (name)(rate(vf_note_info_check_total{application="$appid", name!="all"}[1m])) / sum(rate(vf_note_info_check_total{application="$appid", name="all"}[1m]))` |
| 关键过滤条件 | `name=~"notecreate.*"`（只看笔记创建时间特征） |
| 对比基准 | 告警时间点前后对比 |

## Step 6 · 粗精排模型打分均值 {#step-6}

| 字段 | 值 |
|------|----|
| 大盘 | ark-notefeed业务监控 |
| 图表1 | [粗排模型打分均值](https://monitor.devops.xiaohongshu.com/d/7ck8fwr4k/ark-notefeedye-wu-jian-kong?viewpanel=1132) |
| 图表2 | [精排模型打分均值](https://monitor.devops.xiaohongshu.com/d/7ck8fwr4k/ark-notefeedye-wu-jian-kong?viewpanel=1085) |
| 数据类型 | metrics |
| Datasource | vms-recommend |
| 对比基准 | 告警时间点前后对比 |
| 分析维度 | 按 model 分组，找到打分突变的具体模型 |

## Step 7 · 后排打散情况 {#step-7}

| 字段 | 值 |
|------|----|
| 大盘 | ark-notefeed业务监控 |
| 图表 | [排序降级QPS](https://monitor.devops.xiaohongshu.com/d/7ck8fwr4k/ark-notefeedye-wu-jian-kong?viewpanel=1059) |
| 备注 | ⚠️ Mock 暂缺打散专属图表，真实接入后替换为打散监控 panel |
| 数据类型 | metrics |
| Datasource | vms-recommend |
| 对比基准 | 告警时间点前后对比 |
