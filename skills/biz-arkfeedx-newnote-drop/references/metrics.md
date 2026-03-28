# 数据绑定 · biz-arkfeedx-newnote-drop

## Step1 · 确认下跌 {#step-1}

| 字段 | 值 |
|------|----|
| 数据类型 | metrics |
| Datasource | vms-recommend |
| 图表1 | 1h新笔记曝光占比 |
| PQL1 | `avg(avg_over_time(rt_new_one_hour_new_note_imp_ratio{data_source="holo_rawtracker",overview="true"}[5m]))` |
| PQL1 -1d | 同上加 `offset 1d` |
| PQL1 -7d | 同上加 `offset 7d` |
| 图表2 | 24h新笔记曝光占比 |
| PQL2 | `avg(avg_over_time(rt_new_note_imp_ratio{data_source="holo_rawtracker",overview="true"}[5m]))` |
| PQL2 -1d/-7d | 同上加对应 offset |
| 分析维度 | 全局 overview，分时段（凌晨/上午/下午/晚间）判断异常时段 |
| 异常阈值 | 当前值 < -1d 且 < -7d |
| 原子Skill | metrics-compare |

## Step2 · 定位阶段 {#step-2}

| 字段 | 值 |
|------|----|
| 数据类型 | metrics |
| Datasource | vms-recommend |
| 图表 | 各阶段1h新笔记占比 |
| PQL | `sum by (phase) (rate(new_note_cnt_sum{application="arkfeedx",sub_appid=~"arkfeedx-1-default",env=~"prod",zone=~"(alhz1|alsh1-gray|qcnj2|rcsh1|alhz1-3|alhz1-4|qcnj2-3|qcnj2-4|rcsh1-5)",type=~"1h",subphase="after"}[1m]))/sum by (phase) (rate(note_size_cnt_sum{application="arkfeedx",sub_appid=~"arkfeedx-1-default",env=~"prod",zone=~"(alhz1|alsh1-gray|qcnj2|rcsh1|alhz1-3|alhz1-4|qcnj2-3|qcnj2-4|rcsh1-5)",subphase="after"}[1m]))` |
| PQL -1d/-7d | 对 rate 内指标添加对应 offset |
| 分析维度 | group_by=phase，重点看 postrank 阶段 |
| 原子Skill | metrics-breakdown |

## Step3 · 召回渠道 {#step-3}

| 字段 | 值 |
|------|----|
| 数据类型 | metrics |
| Datasource | vms-recommend |
| 图表 | 各渠道召回量占比 |
| PQL | `sum by (name) (rate(recall_num_exp_sum{application="arkfeedx",sub_appid=~"arkfeedx-1-default",env=~"prod",name=~"dssm_model_base|dssm_model_base_rerank|mllm_cluster_mlp_1w|mllm_cluster|mllm_cluster_10w|mllm_sid_two|es|follow|dssm_inst|dssm_lownv|dssm_low_engage|mllm_note_embedding|u2u_mf|pdn|dssm_model|dssm_topk|dssm_tax_mask|dssm_picture|maxima_cold_start|maxima_out_of_24h|dssm_newnote_unity|dssm_outof24h_1000pv|dssm_emb_i2i_outof24h_1000pv|dssm_emb_i2i|mllm_seq_u2i|mllm_seq_u2i_v2"}[1m]))/sum by (name) (rate(recall_num_exp_sum{...}[1m] offset 1d))` |
| 分析维度 | group_by=name，找当前值同时低于-1d和-7d的渠道 |
| 原子Skill | metrics-breakdown |

## Step4 · 召回根因 {#step-4}

| 字段 | 值 |
|------|----|
| 数据类型 | metrics（3个图表） |
| Datasource | vms-recommend |
| 图表1 | 种子个数（by reason_type） |
| PQL1 | `sum by (reason_type) (rate(retrieval_end_to_end_reasontype_seed_num_sum{application="arkfeedx",sub_appid=~"arkfeedx-1-default",env=~"prod",zone=~"(alhz1|...)",reason_type=~"dssm_low_engage"}[1m]))/sum by (reason_type) (rate(retrieval_end_to_end_reasontype_seed_num_count{...}[1m]))` |
| 图表2 | 召回笔记平均年龄（by type, phase=recall） |
| PQL2 | `(sum by (type) (rate(avg_note_age_sum{application="arkfeedx",env=~"prod",type=~"dssm_model_base|...",phase=~"recall"}[1m]))/sum by (type) (rate(avg_note_age_count{...}[1m])))` |
| 图表3 | 向量索引池quota（by reason_type, name） |
| PQL3 | `sum by (reason_type,name) (rate(vec_reason_and_pool_cnt_sum{application="arkfeedx",sub_appid=~"arkfeedx-1-default",env=~"prod",zone=~"(alhz1|...)",reason_type=~"<step5.0返回值>"}[1m]))/sum by (reason_type,name) (rate(vec_reason_and_pool_cnt_count{...}[1m]))` |
| 含-1d/-7d对比 | 是 |
| 原子Skill | metrics-multi-compare |

## Step5 · 索引排查 {#step-5}

### 5.0 前置检测
| 字段 | 值 |
|------|----|
| 数据类型 | metrics |
| Datasource | vms-recommend |
| PQL | 笔记年龄变老检测（比-7d变老>20% 且 比-1d变老>20%的复合PromQL） |
| 返回值 | type（异常渠道名），传入5.1的 reason_type |

### 5.1 向量索引池quota
| 字段 | 值 |
|------|----|
| Datasource | vms-recommend |
| PQL | `sum by (reason_type,name) (rate(vec_reason_and_pool_cnt_sum{...,reason_type=~"<5.0返回值>"}[1m]))/...` |
| 工具 | index-switch-check，参数：name=异常索引表名 |
| 原子Skill | metrics-compare + tool-invoke(index-switch-check) |

### 5.2 omega侧笔记年龄
| 字段 | 值 |
|------|----|
| Datasource | vms-search |
| PQL | `avg by (scene,graphs,channels) ({__name__=~".*note_age_one_hour",cluster_name="omega-hf-merger-vec",sd_xhs_com_service=~"omega-hf-merger-vec-m.*",proc!~".*response_processor",extra="before_plugin"} >0)` |
| 含-1d/-7d对比 | 是 |
| 原子Skill | metrics-compare |

## Step6 · 内容供给 {#step-6}

| 字段 | 值 |
|------|----|
| 数据类型 | metrics（4个图表，跨datasource） |
| 图表1 | 内容池1h新笔记数（vms-recommend） |
| PQL1 | `(avg(avg_over_time(zebraindex_inc_note_cnt_by_datakey_age{datakey="hf_note_info",datasource="holo",group_type="3600"}[5m])) * 10)` |
| 图表2 | 内容池24h新笔记数（vms-recommend） |
| PQL2 | 同上，group_type="86400" |
| 图表3 | 审核重试任务数（vms-shequ） |
| PQL3 | `sum(avg_over_time(postnotescanner_singleshardtablescanner_scansingleshard_needretrytasknumber{quantile="0.999",code="note_spam"}[1m])) by (biz,code)` |
| 图表4-a | 转码延迟P95（vms-shequ） |
| PQL4-a | `avg(max_over_time(post_task_finish_seconds{quantile="0.95",code="completed",biz=~"note_spam|note_transcode|note_new_transcode"}[1m])) by (biz,code)` |
| 图表4-b | 发布QPS（vms-shequ） |
| PQL4-b | `sum by (endpoint)(rate(api_request_count{env=~"prod|canary",application="noteupdater",endpoint=~"newnote|editnote"}[30s]))` |
| 含-1d/-7d对比 | 是 |
| 原子Skill | metrics-multi-compare |
