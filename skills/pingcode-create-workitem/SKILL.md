---
name: pingcode-create-workitem
description: 当用户需要创建各类工作项：需求、缺陷、子任务时使用该 skill。支持产品需求、技术需求、数据需求、缺陷、子任务等类型的创建。
---


# 创建工作项（Create Work Item）

## 上下文信息

| 信息 | 来源 |
|------|------|
| 当前登录用户邮箱 | 环境变量 `XHS_USER_EMAIL`，可通过 `echo $XHS_USER_EMAIL` 获取 |

---

## 可用脚本

| 脚本 | 用途 | 用法 |
|------|------|------|
| `scripts/get_create_workitem_init_info.py` | 获取当前用户有权限的空间列表及各空间禁用的子类型 | `python3 scripts/get_create_workitem_init_info.py` |
| `scripts/search_workitem_by_keyword.py` | 通过ID或名称关键词模糊搜索工作项 | `python3 scripts/search_workitem_by_keyword.py <关键词>` |
| `scripts/get_work_item_create_form_recommend.py` | 获取创建工作项的表单字段及推荐值 | `python3 scripts/get_work_item_create_form_recommend.py <workSpaceId> <subTypeCode> [parentId]` |
| `scripts/create_work_item_local_for_hibot.py` | 根据 formData 创建工作项 | `python3 scripts/create_work_item_local_for_hibot.py <workSpaceId> <subTypeId> <workItemTypeKey> <subTypeCode> <formData JSON> [parentId]` |

---

## 配置

```xml
<config>
    <capabilities>
        <features>
            <feature>创建各类工作项（需求、缺陷、子任务）</feature>
        </features>
    </capabilities>

    <rules>
        <rule>操作过程以自然对话方式与用户交流，严禁返回给用户的文本中直接提及脚本名称</rule>
        <rule>与用户交流中，禁止暴露字段的key和选项的key，只能用字段的name和选项的name</rule>
        <rule>内部执行细节隔离：本文档中出现的脚本名称、字段key、选项key、示例JSON仅用于内部执行与提交数据，严禁在返回给用户的文本中直接复述或展示</rule>
        <rule>当用户没有主动询问字段和选项的含义时，严禁解释其含义。例如禁止"优先级：P0（最高）"，而是应该直接"优先级：P0"</rule>
        <rule>主动推进，自动提取历史/上下文信息，非必要不重复询问</rule>
        <rule>按 &lt;workflows&gt; 定义的最佳实践流程作业，杜绝自由发挥或流程外的自选操作</rule>
        <rule>userEmail: 从环境变量中获取用户邮箱，仅用于需要邮箱的脚本执行</rule>
        <rule>【强约束】当流程要求输出固定报错文案时，必须“原样输出且仅输出该文案”，禁止追加任何解释、推理、下一步计划或过程性描述（例如“我将获取创建表单的配置信息”等）</rule>
        <rule>【强约束】严禁在对用户输出中展示任何结构化提交数据（例如JSON、字段key、选项key、formData明细等）</rule>
        <rule>【强约束】严格遵循<constraints>限制。</rule>
        <rule>所有输出的链接必须是markdown格式的链接，且必须使用有意义的标题作为链接文本，禁止使用URL作为链接文本。例如：[工作项标题](URL) 而不是 [URL](URL)</rule>
        <rule>严禁使用"scripts/get_work_item_create_form_recommend.py","scripts/create_work_item_local_for_hibot.py","scripts/get_create_workitem_init_info.py","scripts/search_workitem_by_keyword.py"以外的任何脚本</rule>
        <rule>【强约束-子类型澄清】当用户说"创建需求"/"创建任务"/"创建子任务"但未指定具体子类型时，必须向用户确认子类型，严禁自动选择或默认任何一种子类型继续执行</rule>
        <rule>思考过程: 将分析过程放在 <thinking> 标签内，包括：上下文解析、阶段判断依据、规则匹配、动作推荐理由</rule>
    </rules>

    <response_guidelines>
        <language>语言适配：严格用用户当前使用语言回应</language>
        <style>沟通风格：始终专业、友好、简洁</style>
        <error_handling>错误处理：一切脚本执行异常（如code:500、isError:true）须清晰告知，并提供解决建议或替代思路</error_handling>
    </response_guidelines>

    <field_mappings>
        <subTypeCode name="子类型编码">
            <mapping key="TASK_SUBTYPE_TECHNOLOGY" value="技术需求"/>
            <mapping key="TASK_SUBTYPE_PRODUCT" value="产品需求"/>
            <mapping key="TASK_SUBTYPE_DATA" value="数据需求"/>
            <mapping key="BUG_SUBTYPE_DEFAULT" value="缺陷"/>
            <mapping key="SUBTASK_SUBTYPE_SERVER" value="服务端子任务"/>
            <mapping key="SUBTASK_SUBTYPE_FE" value="前端子任务"/>
            <mapping key="SUBTASK_SUBTYPE_DEV" value="通用子任务"/>
            <mapping key="SUBTASK_SUBTYPE_HARMONY" value="鸿蒙子任务"/>
            <mapping key="SUBTASK_SUBTYPE_IOS" value="ios子任务"/>
            <mapping key="SUBTASK_SUBTYPE_ANDROID" value="Android子任务"/>
            <mapping key="SUBTASK_SUBTYPE_ALGORITHM" value="算法子任务"/>
            <mapping key="SUBTASK_SUBTYPE_DATA" value="数据子任务"/>
            <mapping key="SUBTASK_SUBTYPE_CONFIG" value="配置子任务"/>
            <mapping key="SUBTASK_SUBTYPE_DYNAMIC" value="动态化子任务"/>
            <mapping key="SUBTASK_SUBTYPE_OPERATION" value="运维子任务"/>
        </subTypeCode>

        <workItemTypeKey name="工作项类型">
            <mapping key="task" value="需求"/>
            <mapping key="subtask" value="子任务"/>
            <mapping key="bug" value="缺陷"/>
        </workItemTypeKey>
    </field_mappings>

    <other_instructions>
        <instruction>本平台工时的单位都是天</instruction>
    </other_instructions>

    <form_extraction_rules>
        <note>说明：本段的“字段key/选项key/示例JSON”为内部提交数据结构示例；对用户输出必须遵守 &lt;rules&gt; 中“只用name、不暴露key、不复述内部细节”。</note>
        <rule condition="字段类型=USER">
            <action>提取人员名称关键词（仅内部提交），例如：{"owner": "普兰"}</action>
        </rule>
        <rule condition="字段类型=MULTI_USER、ROLE_MULTI_USER">
            <action>提取人员名称关键词，形成数组（仅内部提交），例如：{"participant": ["信助(刘仁瑞)","郑圆澳"]}</action>
        </rule>
        <rule condition="字段类型=SELECT、TREE_SELECT">
            <action>提取选项的key（仅内部提交），例如：{"priority": "000001"}</action>
        </rule>
        <rule condition="字段类型=MULTI_SELECT、COMPOUND">
            <action>提取选项的key，形成数组（仅内部提交），例如：{"safetyRiskType": ["0000010000"]}</action>
        </rule>
        <rule condition="字段类型=LINK">
            <action>提取链接，形成字符串数组（仅内部提交），例如：{"prd": ["http://example.com/doc1", "http://example.com/doc2"]}</action>
        </rule>
        <rule condition="字段类型=STRING、TEXTAREA、TEXT">
            <action>提取内容形成字符串（仅内部提交），例如：{"capacityFailureReason": "一句话"}</action>
        </rule>
        <rule condition="字段类型=INT">
            <action>提取内容形成整数（仅内部提交），例如：{"acceptanceTaskCount": 3}</action>
        </rule>
        <rule condition="字段类型=FLOAT">
            <action>提取内容形成小数（仅内部提交），例如：{"workload": 3.5}</action>
        </rule>
        <rule condition="字段类型=DATE">
            <action>提取日期，必须严格使用下列格式之一</action>
            <date_formats>
                <date_format type="指定日期">
                    <pattern>yyyy-MM-dd</pattern>
                    <example>{"startTime": "2025-09-21"}</example>
                    <note>直接指定日期，如 2025-09-21</note>
                </date_format>
                <date_format type="今天">
                    <pattern>TODAY</pattern>
                    <example>{"startTime": "TODAY"}</example>
                    <note>表示今天</note>
                </date_format>
                <date_format type="x天前">
                    <pattern>DAYS_AGO_x</pattern>
                    <example>{"startTime": "DAYS_AGO_3"}</example>
                    <note>x 表示天数，例如 3天前</note>
                </date_format>
                <date_format type="x天后">
                    <pattern>DAYS_LATER_x</pattern>
                    <example>{"startTime": "DAYS_LATER_3"}</example>
                    <note>x 表示天数，例如 3天后</note>
                </date_format>
            </date_formats>
        </rule>
        <rule condition="字段类型=MULTI_KEYWORD">
            <action>提取关键词，形成数组（仅内部提交），例如：{"relationTask": ["88833"]}</action>
        </rule>
        <rule condition="字段类型=MULTI_LINK">
            <action>提取链接，形成数组（仅内部提交），例如：{"attachment": ["http://a.com"]}</action>
        </rule>
    </form_extraction_rules>

    <workflows>
        <workflow name="createWorkItem" description="创建工作项（需求、缺陷、子任务）">
            <scenarios>用户想创建任意类型的工作项</scenarios>
            <notes>
                <note>只有子任务有父需求，且子任务必须有一个父需求（parentId）</note>
                <note>子任务和父需求的空间必须相同，即workSpaceId相等</note>
                <note>缺陷可以关联多个需求，用户如果说在需求下创建个缺陷，代表的是关联此需求</note>
                <note>开始此流程必然先执行步骤1(获取有权限的空间列表和子类型列表)</note>
            </notes>
            <constraints>
                <constraint>对用户输出禁止出现任何内部执行细节（包括字段key/选项key/示例提交结构/脚本执行细节等），只使用字段与选项的显示名称</constraint>
                <constraint>若用户话术包含“我/本人/自己/咱”等第一人称且未明确指定负责人，则负责人默认是当前用户（从环境变量获得的邮箱）</constraint>
                <constraint>提交的表单必须符合 form_extraction_rules 中的规则</constraint>
                <constraint>当确认要执行这个工作流时, 就必须要完全走一遍工作流, 不可从中间的某一步开始,</constraint>
            </constraints>
            <output_contract>
                <allowed_outputs>
                    <output>缺失必填字段询问（严格使用 workflow 步骤2中 condition="存在缺失的必填字段" 的 format）</output>
                    <output>创建成功信息（严格使用 workflow 步骤2中 resultType = 'SUCCESS' 的 format）</output>
                </allowed_outputs>
            </output_contract>
            <parent_workspace_validation>
                <description>父需求空间校验规则</description>
                <rule>当存在明确的父需求（parentId）时，必须执行 scripts/search_workitem_by_keyword.py 脚本查看父需求信息，获取父需求的空间（workSpaceId）</rule>
                <rule>空间确定逻辑：
                    - 若用户未指定空间：自动使用父需求的空间（workSpaceId）
                    - 若用户指定了空间且与父需求空间一致：使用该空间
                    - 若用户指定了空间但与父需求空间不一致：必须立即停止流程并输出提示
                </rule>
                <error_output condition="用户指定空间与父需求空间不一致">
                    <format>子任务必须与父需求在同一空间下创建。父需求所在空间为「{父需求空间名称}」，与您指定的「{用户指定空间名称}」不一致，请确认后重试。</format>
                </error_output>
            </parent_workspace_validation>
            <steps>
            <step index="1">
                <name>获取有权限的空间列表和子类型列表</name>
                <action>执行 scripts/get_create_workitem_init_info.py 脚本，获取有权限的空间列表和子类型列表, 并推测要选择的空间和子类型</action>
                <constraints>
                    <constraint>必须先执行 scripts/get_create_workitem_init_info.py 脚本，再根据返回结果推测要选择的空间和子类型,禁止在没有执行 scripts/get_create_workitem_init_info.py 脚本的情况下推测要选择的空间和子类型</constraint>
                    <constraint>除非已经知道空间id(workSpaceId)和子类型code(workSpaceId),不然必须支持此步骤</constraint>
                    <constraint>当脚本返回的列表只有一个空间时,直接使用该空间,  禁止再向用户确认空间</constraint>
                    <constraint>空间只能在以下两种情况下自动确定：①用户明确提供空间名称且能唯一匹配；②空间列表只有一个数据时使用该空间。除此之外（例如空间列表&gt;1且用户未明确空间/无法唯一匹配），严禁“按列表顺序猜测/默认第一个空间/自作主张选择”</constraint>
                    <constraint>若用户明确提供空间名称，但空间列表中未匹配到该空间（无权限或空间不存在），必须输出文本:"没有XX空间权限或XX空间不存在"并结束，不得继续后续步骤</constraint>
                    <constraint type="no_omissions_allowed">用户没有明确描述工作项类型与子类型（subTypeId）时，严禁自行默认（例如默认"产品需求"），向用户确认空间和工作项类型,可以根据 scripts/get_create_workitem_init_info.py 的返回给一些选择建议; 建议的空间和子类型一定是 scripts/get_create_workitem_init_info.py 脚本返回中存在的; 建议列表必须带编号（从1开始），用户只回复编号时视为选择该编号对应的项; 根据缺失情况分别输出：
                        - 【仅缺少空间】（子类型已明确）：请告诉我空间
                        1. {空间A}
                        2. {空间B}
                        ...
                        回复编号即可，或者直接告诉我
                        - 【仅缺少子类型】（空间已明确）：请告诉我子类型
                        1. {子类型A}
                        2. {子类型B}
                        ...
                        回复编号即可，或者直接告诉我
                        - 【空间和子类型都不明确】：请告诉我空间和子类型
                        1. {空间A}（{子类型A}）
                        2. {空间B}（{子类型B}）
                        ...
                        回复编号即可，或者直接告诉我</constraint>
                    <constraint>【强约束-子类型判定标准】以下情况视为"子类型未明确"，必须向用户澄清：
                        - 用户说"需求"但未说明是"产品需求"/"技术需求"/"数据需求"中的哪一种
                        - 用户说"子任务"但未说明是"服务端子任务"/"前端子任务"/"通用子任务"等中的哪一种
                        - 用户描述中仅包含工作内容（如"帮我创建一个需求:abcd"），但未明确子类型
                        - 用户说需求下创建子任务,只说明了创建的是子任务,没有明确是哪种子任务
                        判定原则：只有用户原话中【完整出现】子类型名称（如"产品需求"、"技术需求"、"前端子任务"等）时，才视为已明确子类型，否则必须澄清</constraint>
                </constraints>
                <cases>
                    <case condition="用户明确提供空间名称，但在空间列表中未匹配到该空间">
                        <action>输出文本:"没有XX空间权限或XX空间不存在"并结束, 例如: "没有测试空间权限或测试空间不存在"</action>
                    </case>
                    <case condition="空间已明确，但子类型不明确">
                        <action>仅向用户确认子类型，按格式输出: 请告诉我子类型
                            1. {子类型A}
                            2. {子类型B}
                            ...
                            回复编号即可，或者直接告诉我</action>
                    </case>
                    <case condition="子类型已明确，但空间不明确">
                        <action>仅向用户确认空间，按格式输出: 请告诉我空间
                            1. {空间A}
                            2. {空间B}
                            ...
                            回复编号即可，或者直接告诉我</action>
                    </case>
                    <case condition="空间和子类型都不明确">
                        <action>需要向用户同时确认空间和子类型，按格式输出: 请告诉我空间和子类型
                            1. {空间A}（{子类型A}）
                            2. {空间B}（{子类型B}）
                            ...
                            回复编号即可，或者直接告诉我</action>
                    </case>
                </cases>
            </step>

            <step index="2">
                <name>匹配用户输入与表单字段</name>
                <action>执行 scripts/get_work_item_create_form_recommend.py 脚本获取预填字段列表，基于用户输入/群名称/群公告/引用聊天内容进行推测在表单字段中进行匹配，进行预填信息提取；随后执行 scripts/create_work_item_local_for_hibot.py 脚本创建工作项,并按要求输出内容</action>
                <constraints>
                    <constraint type="script_allowlist">允许且仅允许执行 scripts/get_work_item_create_form_recommend.py 与 scripts/create_work_item_local_for_hibot.py；同一轮回复允许按顺序执行这两个脚本（先 recommend，后 create）</constraint>
                    <constraint>subTypeId字段必须从 scripts/get_work_item_create_form_recommend.py 的返回中提取,禁止自己构造, 如果实在无法确定subTypeId直接提示并结束</constraint>
                    <constraint type="output_restriction">禁止向用户展示提取的预填信息</constraint>
                    <constraint>严格按照 &lt;form_extraction_rules&gt; 中的规则提取预填信息</constraint>
                    <constraint>所有USER、MULTI_USER、ROLE_MULTI_USER、SELECT、TREE_SELECT、MULTI_SELECT、COMPOUND、STRING、TEXTAREA、TEXT类型的字段必须是从 scripts/get_work_item_create_form_recommend.py 脚本返回里提取值, 禁止使用没有在 scripts/get_work_item_create_form_recommend.py 脚本返回里出现的值</constraint>
                    <constraint type="no_hallucination">【强约束-禁止猜测】预填字段提取原则：
                        - 只提取用户在输入中【明确提及】的字段值，禁止对用户未提及的字段进行任何形式的猜测或自动填充
                        - 用户未提及的字段，除以下2个例外外，一律【留空不填】：
                        ① businessLine（业务方向）：有默认值用默认值，无默认值用第一个可选值
                        ② owner（负责人）：用户未指定时使用当前用户
                        - 除标题(name)外禁止根据字段名称、选项内容进行"合理猜测"或"智能匹配"
                        - 禁止因为某个选项"看起来合适"或"语义相近"就自动填充
                        - 判断标准：用户原文中是否有与该字段【直接相关】的明确描述
                    </constraint>
                    <constraint>需要基于上下文信息推测一个工作项标题(name字段), 如果无法推出有意义的标题, 标题直接留空不填</constraint>
                    <constraint type="no_omissions_allowed">业务方向(businessLine)为必填字段,必须有值,用户没有给出值时有默认值时使用默认值; 没有默认值时使用可选值(optionValues)的第一个</constraint>
                    <constraint type="no_omissions_allowed">负责人(owner)为必填字段,必须有值.用户未明确指定,且无法推测出负责人时,必须使用当前用户（userEmail）作为负责人</constraint>
                    <constraint>若业务方向无默认值且无可选值，立即终止流程并输出："业务方向配置异常，请联系管理员"</constraint>
                    <constraint type="no_omissions_allowed">子任务必须有父需求（parentId），若用户创建子任务但未提供父需求信息，必须向用户澄清父需求</constraint>
                    <constraint type="no_omissions_allowed">用户输入中包含的所有图片链接，必须以markdown图片格式（![图片](图片URL)）添加到描述（description）字段中</constraint>
                    <constraint>如果存在父需求, 则使用父需求的业务方向(businessLine)和迭代(sprint)作为当前工作项的业务方向(businessLine)和迭代(sprint)</constraint>
                    <constraint>用户类型直接输入用户名,不要使用邮箱</constraint>
                    <constraint type="no_omissions_allowed">执行创建前，必须检查所有必填字段是否已填充；若存在缺失的必填字段（businessLine 和 owner 已通过默认值处理除外），必须先向用户询问补充，不得直接提交创建请求</constraint>
                </constraints>
                <parent_id_extraction_rules>
                    <description>父需求ID的获取方式（按优先级排序）</description>
                    <rule priority="1">用户直接告知父需求ID</rule>
                    <rule priority="2">从需求链接中提取ID：
                        - 链接格式1: /work-space?workItem=213531&amp;tab=detail，提取workItem参数值（如213531）
                        - 链接格式2: /work-item-detail/213531，提取路径最后一段（如213531）
                    </rule>
                    <rule priority="3">用户提供父需求名称时，执行 scripts/search_workitem_by_keyword.py 脚本，通过关键词查询获取父需求ID</rule>
                </parent_id_extraction_rules>
                <notes>
                    <note>给XX创建或为XX创建等，理解为负责人是XX. 例如: 给张三创建一个需求, 理解为负责人是张三</note>
                    <note>如果用户没有明确指定负责人，但用户描述中出现"我/本人/自己/咱"等第一人称（例如"帮我新建"），则负责人必须默认设置为当前用户（userEmail）</note>
                    <note>默认值处理后仍有必填字段缺失，必须向用户询问缺失的必填字段，待用户补充后再执行创建</note>
                </notes>
                <cases>
                    <case condition="存在缺失的必填字段（除 businessLine 和 owner 外）">
                        <action>向用户询问缺失的必填字段值，暂停创建流程直到所有必填字段补充完整</action>
                        <format>
                            <markdown>
                                还需要补充以下必填信息：
                                - {缺失字段1的显示名称}
                                - {缺失字段2的显示名称}

                                请补充以上信息
                            </markdown>
                        </format>
                        <post_action>
                            用户回复后按以下方式处理：
                            - 根据用户回复提取字段值，按 form_extraction_rules 规则处理
                            - 若所有必填字段已补充完整，执行 scripts/create_work_item_local_for_hibot.py 创建工作项
                            - 若仍有必填字段缺失，再次列出剩余缺失字段继续询问，直到全部补齐
                        </post_action>
                    </case>
                    <case condition="创建子任务但缺少父需求ID">
                        <action>向用户澄清父需求信息，暂停后续创建流程直到获取到父需求ID</action>
                        <format>
                            <markdown>
                                创建子任务需要关联父需求，请提供父需求信息（以下任一方式均可）：
                                1. 直接告诉我父需求ID
                                2. 告诉我父需求名称，我来帮你查询
                            </markdown>
                        </format>
                        <post_action>
                            用户回复后按以下方式处理：
                            - 若用户提供ID：直接使用该ID作为parentId
                            - 若用户提供链接：从链接中提取ID（参考 parent_id_extraction_rules）
                            - 若用户提供需求名称：执行 scripts/search_workitem_by_keyword.py 脚本查询，将查询到的需求ID作为parentId；若查询到多个结果，展示列表供用户选择
                        </post_action>
                    </case>
                    <case condition="resultType = 'SUCCESS'">
                        <action>展示创建成功信息，按照返回结果中 readableMap 的字段顺序展示所有字段，每个字段独占一行，字段之间用空行（两个换行符）分隔以确保在所有渠道中正常显示换行</action>
                        <format>
                            <markdown>
                                {工作项类型}创建成功！

                                {按 readableMap 中的顺序，每个字段独占一行，格式为："字段名：字段值"，相邻字段之间必须用一个空行分隔（即连续两个换行符）}

                                链接：[{标题}]({url})
                            </markdown>
                            <format_note>【强约束】相邻字段之间必须有一个空行（两个换行符），禁止仅用单个换行符分隔字段，禁止将多个字段拼在同一行输出。这是为了确保在IM渠道（如Hi/Redcity）中换行能正常渲染。</format_note>
                            <format_example>
                                技术需求创建成功！

                                所属空间：【测试废弃空间】需求管理平台

                                ID：816462

                                标题：优化登录流程

                                ...（readableMap 中的其余字段，每个字段之间都有空行）

                                链接：[优化登录流程](https://pingcode2.devops.xiaohongshu.com/work-item-detail/816462)
                            </format_example>
                        </format>
                    </case>
                </cases>
            </step>
        </workflow>
    </workflows>

    <examples>
        <example name="空间和子类型都缺失时返回提示并给出建议">
            <user_utterance>创建一个需求</user_utterance>
            <note>【重要】用户既未指定空间，也未明确子类型，需要同时返回空间+子类型组合</note>
            <assistant_output>
                请告诉我空间和子类型
                1. 圆澳测试空间1（产品需求）
                2. 圆澳测试空间1（技术需求）
                3. 测试空间（产品需求）
                回复编号即可，或者直接告诉我
            </assistant_output>
        </example>
        <example name="只缺少子类型时-仅返回子类型建议">
            <user_utterance>在圆澳测试空间1创建一个需求:abcd</user_utterance>
            <note>【重要】用户已明确空间为"圆澳测试空间1"，但只说"需求"未明确是产品需求/技术需求/数据需求，只需确认子类型</note>
            <assistant_output>
                请告诉我子类型
                1. 产品需求
                2. 技术需求
                3. 数据需求
                回复编号即可，或者直接告诉我
            </assistant_output>
        </example>
        <example name="只缺少空间时-仅返回空间建议">
            <user_utterance>帮我创建一个产品需求:abcd</user_utterance>
            <note>【重要】用户已明确子类型为"产品需求"，但未指定空间，只需确认空间</note>
            <assistant_output>
                请告诉我空间
                1. 圆澳测试空间1
                2. 测试空间
                回复编号即可，或者直接告诉我
            </assistant_output>
        </example>
        <example name="用户说需求下创建子任务但未指定子类型-仅返回子类型建议">
            <user_utterance>我来帮你在xxx需求下创建一个子任务</user_utterance>
            <note>【重要】用户只说"需求下创建子任务"但未明确是服务端子任务/前端子任务/通用子任务，由于父需求已确定空间，只需确认子类型</note>
            <assistant_output>
                请告诉我子类型
                1. 服务端子任务
                2. 前端子任务
                3. 通用子任务
                回复编号即可，或者直接告诉我
            </assistant_output>
        </example>
        <example name="缺失必填字段时向用户询问">
            <user_utterance>在XX空间创建一个产品需求，标题是"优化登录"，负责人给我</user_utterance>
            <note>【重要】标签和优先级为必填字段但用户未提供且无默认值，只列出字段名称询问</note>
            <assistant_output>
                还需要补充以下必填信息：
                - 标签
                - 优先级

                请补充以上信息
            </assistant_output>
        </example>
        <example name="创建成功输出">
            <user_utterance>在XX空间创建一个缺陷：iOS端闪退，负责人张三</user_utterance>
            <note>【重要】创建成功后，按照返回结果中 readableMap 的字段顺序逐行展示所有字段，每个字段之间用空行分隔</note>
            <assistant_output>
                缺陷创建成功！

                所属空间：XX空间

                ID：123456

                标题：iOS端闪退

                ...（readableMap 中的其余字段，每个字段之间都有空行）

                链接：[iOS端闪退](工作项详情链接地址)
            </assistant_output>
        </example>
    </examples>

</config>
```
