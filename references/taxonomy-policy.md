# Global Talent Taxonomy v1.1 与 Moka 打标

## 依据和版本状态

- `assets/source/Global_Talent_Taxonomy_v1.1.docx` 是用户提供的已接受修订的新版阅读稿备份，状态仍为 Draft for review — pending Admin approval and Moka publication；旧版另存 `assets/source/Global_Talent_Taxonomy_v1.1_旧版_历史.docx`。Global Talent Tag Management Specification v1.0 是标签库治理规范，v1.0 原件及快照仅供历史追溯。
- 历史记录：2026-11-18 用户曾确认当时 v1.1 正式批准；该确认不是本次新版修订的审批或上线证明。每次须向有权来源核实本次新口径的审批、生效版本、Moka 发布、Active 状态及映射；若无法核实或现行正式政策冲突，暂停受影响写入。技能同步本身不授予权限或发布标签。
- `assets/tag-library.snapshot.json` 是文档值及历史出处的未验证快照；每次使用需读取 `assets/tagging-policy.json`、`assets/policy-decisions.json`。历史候选人级最高 Tier 决议仅用于追溯，不再作为本次新口径的执行规则。Country 仍以实际所在地为目标，用户于 2026-11-20 明确允许在不直接写明时综合已有线索推断；详见[证据判断](evidence-based-recommendations.md)。
- Admin 负责变更、导入/导出及批准发布标签库；User 使用已批准标签。版本生效、新旧对应关系、状态及生效日期以有权来源为准；候选人标签的写入仍要核验账户权限和当前 Active 状态。不创建、停用、合并、导入标签库或自动修改历史记录。

## 六个独立、平铺的标签组

| 组 | 规则 | 判定重点 |
|---|---|---|
| `country` | 单选；必填 | 目标是候选人当前实际所在地；优先明确现居地，未明确时可综合简历和申请中同向线索合理推断并说明，不能仅凭国籍或姓名。信息不足或冲突则待核实。 |
| `language` | 多选；必填 | 能用于相关项目的语言；不根据国家推断，不在 v1.1 创建熟练度标签。 |
| `project category` | 多选；必填 | 候选人能从事的工作类型。按实际能力与证据选择；E、F、G 标题仍只是组织标题，不是父级标签。 |
| `knowledge domain` | 多选；可选 | 候选人的实质知识、技术或实践；不同于可以从事的项目工作。 |
| `tier` | 项目评估上下文单选；适用的新人才/定价记录必填 | 各项目关联具体 Target Profile 和证据，独立记录；不跨项目取最高或自动覆盖。 |
| `rate` | 单选；适用 ATS Talent Pool 记录要求时必填，不适用于 Benchmark | 明确的 USD/小时期望费率；精确匹配 v1.1 的五个 Moka 区间，详见 [Rate 细则](operation-and-validation.md)。 |

补充既有记录时只处理用户授权的组；缺其他必填组时不强行编造或称分类完整。组和值共同标识一个标签：`model fine-tuning` 在 Project Category 和 Knowledge Domain 分别存在，不能自动合并。标准标签值通常为小写；Rate 的五个区间标签为保持系统兼容而沿用 Moka 原有英文大小写与数学符号。

按岗位关联的 requisition 判断项目工作类型及 Moka 手动项目标记时，参照 [Requisition 项目类别判断](requisition-project-mapping.md)。岗位工作要求能够支持岗位项目标记，但不单独证明某候选人具备该项目能力；Moka 手动项目标签的实际组和值也不能伪装成 v1.1 Project Category 规范词条。

Country 原文明示的别名例：`usa`、`united states of america` → `united states`，`uk` → `united kingdom`。原始 Country/Language 清单中重复出现的 `pashto` 与 `uzbek` 各作为一个组内规范值保留；新版草稿以 `persian` 为规范值、`farsi` 为别名，新记录使用 `persian`，仍须核实新口径获批及标签 Active，历史 `farsi` 未经另行批准不自动迁移或删除。必要时 `chinese` 与 `mandarin` 保持区分。`city` 是可选自由文本而非标签组。

## 组级异常标签

六个值分别为 `country not included`、`language not included`、`project category not included`、`knowledge domain not included`、`tier not included`、`rate not included`。仅当候选人的相关事实**已知**、有证据，且该事实与当前批准的该组词表比较后确实无适用标准值时使用；记录原始事实、证据和比对依据。不得把未知、资料缺失、未收集、尚未评估、不适用、权限不足或冲突当作 not included。标签未在当前库批准并于 Moka Active 时，不可正式添加，列待处理。

Country/Tier/Rate 为单选，正常值与本组异常值不得在同一适用上下文并存。Language/Project Category/Knowledge Domain 多选：若一个有证据的事实已有标准值，而另一个独立有证据的事实确实未被该组覆盖，可以共存对应普通值和 not included；同一事实不得为了泛化而重复贴异常标签。Tier 异常只适用于已按项目完成有效评估、已知情况确实无法归入四档，不代表未评估；不得以一个项目的异常覆盖或决定其他项目的等级。Rate 异常仅适用于有效非负 USD/小时数字超出五档；按 v1.1 的五档即大于 100，不将非 USD、非小时、负数或未知当作超范围。

## 精简后的 Project Category E–G

- E. LLM Evaluation：`llm general response evaluation`、`llm safety evaluation`、`llm coding evaluation`、`llm preference evaluation`。一般响应类涵盖一般或未细分响应评价及推理、知识、指令遵循、事实性等评价，不表示这些专项能力相互等价；其他专类各自依证据选择。
- F. Agent Evaluation：`agent task completion evaluation`、`agent planning and reasoning evaluation`、`agent tool and interface evaluation`、`agent workflow and trajectory evaluation`。工具/界面涵盖工具、浏览器和计算机操作；工作流/轨迹关注多步过程。不能从某一方面自动推断其他方面。
- G. Prompt & Model Development：`prompt development`、`general ai training`、`model fine-tuning`、`agent training`。通用或未细分 AI 训练不自动证明模型微调或 Agent 训练；`prompt development` 不自动证明其他技能。

A–D、H–J 和 Knowledge Domain 原有组/值保持不变，另加组级异常值。项目类别多选，每个新增值均需证据；不得仅因标题属于 E/F/G 就添加全部子项。旧细项和新粗项的完整对照见 v1.1 附录；对照用于人工审核、版本兼容和检索参考，不是自动迁移、自动删旧标签或自动认定能力的授权。

## Tier 与证据

- `tier 1`：顶级专业能力，可设计方法、作高风险判断及复杂最终裁决。
- `tier 2`：强专业能力，可处理复杂任务、困难案例、错误归因和专家质检。
- `tier 3`：能独立完成领域工作、识别问题并处理常规升级事项。
- `tier 4`：能按 SOP、指南和示例完成标准化任务。

围绕专业知识、相关实践、任务复杂度、独立性、专业判断、对决定与结果的责任六维；不能只凭工作年限、岗位或单一总分推断。没有 Note 或项目专用已批准 rubric 时，也应按[证据判断](evidence-based-recommendations.md)基于简历及项目任务提出有证据的初步 Tier 建议；区分建议和已完成正式评估，必要证据实质不足或冲突则待审核。正式项目评估需适用的批准规则及充分证据，逐项目保存项目 ID、规则及版本、完成状态、有效性、结果和原始证据；不把初步建议冒充正式评估，不贴 `tier not included` 表示未评估。涉及 Benchmark 时需核验候选人跨系统身份、目标项目、测评版本和所选 attempt；不能擅自选择最高分。

每项 Tier 评估独立关联具体项目、Target Profile 和真实证据；同一候选人在不同项目可以有不同 Tier，禁止跨项目取最高、自动覆盖或互相决定。保留各项目历史值及证据。新口径不禁止 Candidate Profile 有 Tier 字段，但不定义跨项目汇总；实际编辑对象、单选范围及共享影响必须据系统实况核验。

用户指定使用 Moka Note 中 TA 已记录的人工作出等级时，直接引用完整 Note、作者、日期、所在档案及采集时间；还须从可靠来源确认该结论对应的项目、Target Profile 和评估证据，不得凭空补写或把跨项目 Note 聚合为最高值。同一项目评估的矛盾修订无法判断时暂停。`Not Tier 1` 或只满足 Tier 2 教育条件不是总体评级；无明确结论、身份或项目关联不明、证据冲突时待审核。

**示例（虚构）：** 同一候选人项目 A 有效评估为 `tier 1`，项目 B 为 `tier 3`；A 与 B 分别保留各自等级及证据，B 不覆盖 A，也不取两者最高作为候选人汇总。

已有值与本项目结果不同时，先核实其项目归属、实际存储隔离、历史保存、权限、前后值及必要确认；不得由其他项目的值触发替换。无法验证真实系统能独立保存项目结果且不改动其他项目或历史时，阻断 Tier 写入；不能虚构字段、接口或验证结果来解决。Candidate Profile 的单一共享字段若无法证明隔离，不可用作不同项目独立存储。

历史最高等级门控与新规则不兼容，不能据其通过结果执行 Tier 写回；只有在真实当前审批与部署状态、项目独立存储、权限及适配新口径的校验均经核实后才能考虑写回。现有门控是否支持，以实际实现和测试为准；在验证完成前仅建议、不写 Tier，详见 [写回校验](taxonomy-writeback.md)。

每条建议记录标准组/值、原文证据、来源及时间、判断理由、当前标签和版本。每项判断应符合上下文，逐字引用本身不证明能力；材料没写不等于候选人没有能力。不得自动录用、淘汰、定价或重写历史。
