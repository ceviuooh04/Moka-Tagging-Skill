# Taxonomy v1.1 写回校验

v1.1 有六组：Country、Language、Project Category、Knowledge Domain、Tier、Rate。新版阅读稿是待 Admin 审批、Moka 发布的草稿；2026-11-18 的旧版批准记录不证明本次修订已获批或上线。一般非 Rate、非 Tier 标签可按实际支持的门控检查；Tier 须遵守下方独立项目阻断。Rate 仅用于适用的 ATS Talent Pool 记录，不属于 Benchmark，必须走专用数值与来源校验；文档快照不替代实际当前获批的 Moka 库。岗位关联 requisition 支持的 **Moka 手动项目标记**按 [Requisition 判断流程](requisition-project-mapping.md)独立处理，不伪装成 v1.1 的 Project Category 或个人能力证据。

## 输入和证据

复制 `templates/taxonomy-plan.example.json`、`taxonomy-context.example.json`、`taxonomy-library.example.json` 或 Rate 对应模板到任务私有目录。旧 Tier 模板和脚本可能仍体现历史候选人最高等级汇总，不是新版项目独立记录的实现依据或写入许可。模板虚构、未验证并默认阻断；不得用空引用、编造的 ID、角色或布尔值冒充真实核验，也不能把示例伪造的来源记录当作真实系统返回。

- 同一真实申请/候选人操作目标必须在相应计划、允许范围及来源中一致；实际申请 ID 和候选人 ID 的关系须另行核实，不可混淆。Tier 编辑对象、项目和 Target Profile 关联、同人多申请的身份及共享影响须按真实系统核实；不禁止 Candidate Profile 中有 Tier 字段，也不假定该字段按项目隔离。不能核实时报告待审核。用户授权写回的字段和操作必须涵盖实际动作；不得假定现有标签具有修改权限或用 `add` 冒充替换。
- 填写现有完整标签和实际组别，只有真实读全且验证组别后，才填写相应核验标记及可复核的引用。未知组不能伪装为已识别的其他组；不得擅自删除现有标签，仅在适用确认、修改权限及替换门控均满足时处理必要的 Tier 旧值替换，不改动其他标签或历史评估证据。
- 逐标签保存同一记录的真实来源 `source_id/system/record_id/url/captured_at/segments[{locator,text}]` 和连续逐字 `evidence[{source_id,locator,excerpt}]`。逐字引用只验证来源，不能自动证明能力。通用脚本只接收已核验的 Moka 记录来源；跨系统证据需使用适合的跨系统流程，不得冒充 Moka。
- 当前批准运行库和计划须使用同一真实 `taxonomy_version`；真实 `approval_reference`、`current_version_verification_reference`、`active_status_verification_reference`、`moka_id_mapping_reference` 与核验状态必须对应有权来源。目标组/值、当前 Active 状态和 Moka ID 必须一一核实；随附快照未核验，不能直接用于写回。
- 项目类别在 v1.1 是多选；使用经核实的 `project_category_selection_type: "multi"` 和该版本决议来源。若当前库/UI 与已批准口径冲突，停止该组并核实。
- Country 目标为当前所在地；可按用户确认综合已有同向线索作有依据的推断，保留各项真实来源及推断性质，不仅以国籍或单一岗位市场断定。资料不足或冲突则待审核，不用 `country not included` 代替未知；若当前获批政策与推断口径冲突，暂停写入并报告，不伪称所在地已核实。
- Tier 每项项目评估需真实项目与 Target Profile、已批准的具体工作评估规则及版本、完成和有效状态、必要维度和来源证据；各项目结果可不同，不跨项目取最高或自动覆盖。`tier not included` 需已评估且有据，不能表示未评估；评估、身份、关联或证据不明即待审核。此审核要求是安全实现，并非声称政策给出固定分数切线。
- 写 Tier 前必须核实新口径获批并上线，且真实系统支持在相应项目/Target Profile 下独立存储和保留历史，写入不会覆盖其他项目；还须核验实际字段、权限、必要确认、现有值及新口径适用门控。任何一项无法核实即阻断；不得臆造项目字段、ID、接口或布尔值。只看到共享候选人单选 Tier 而不能证明隔离，不满足此条件。
- 非 Rate 的组级 not-included 要填写真实的 `exception_assessment`（已知事实、核实无匹配的状态及比较出处），并以该事实的真实原文证据支持；不能用 unknown/空值/未评估当作事实。单选组异常和普通值冲突；多选组的普通值与异常仅可对应不同的已知事实。脚本检查结构和部分字面规则，不能自行证明语义上真的没有匹配。

## 离线检查

```bash
python3 "<skill-dir>/scripts/validate_taxonomy_plan.py" \
  --plan "<private-dir>/taxonomy-plan.json" \
  --context "<private-dir>/taxonomy-context.json" \
  --library "<private-dir>/approved-library.json"
```

不指定 `--library` 使用随附 v1.1 文档快照；它未核验批准状态、Active 或 ID，正常情况下应阻断。多组可以按组分开计划，使一组受阻时仍能处理其他有依据的组；Rate 另用 [专用门控](operation-and-validation.md)。Rate 的已确认 v1.1 期望时薪 >100 的异常项，还要证明完整五档及异常标签均已获批准并启用。

**Tier 门控限制：** 旧版 `validate_taxonomy_plan.py`、`validate_note_tier_plan.py`、`validate_user_tier_plan.py` 及旧混合/批量流程可能按候选人最高值运行，不能用其通过结果替代项目隔离和新版政策的验证，也不能以旧格式绕过阻断。仅当适配新版的实际校验器已实现并经测试、能核验相关来源和上下文时，才可将其作为必要检查之一；离线校验仍不证明系统存储隔离、实际权限或审批。当前未核实前一律只提出项目级建议，不写 Tier。结构化结果、Note 或用户确认均须保留真实原文并核实项目与 Target Profile；不得虚构来源或将其他项目值归并。

同一个候选人同时写 Rate 和其他组时，用同一份真实当前运行库、同一完整旧标签快照和同一批准载荷，运行适用的混合门控。含 Tier 的联合计划在项目独立存储与适用门控未经核实前阻断；不能借分开计划或 ID 相同绕过阻断。其他可处理的混合计划中，两份上下文须各自记录相同且真实的 `snapshot_id`，仅在本次确已读取且核实后提供 `current_tags_snapshot_verified: true` 和 `current_tags_snapshot_verification_reference`；两份旧标签组/值必须一致。不要虚构快照凭证。混合门控会进一步调用两个单条门控：

```bash
python3 "<skill-dir>/scripts/validate_mixed_plan.py" \
  --taxonomy-plan "<private-dir>/taxonomy-plan.json" \
  --taxonomy-context "<private-dir>/taxonomy-context.json" \
  --rate-plan "<private-dir>/rate-plan.json" \
  --rate-context "<private-dir>/rate-context.json" \
  --library "<private-dir>/approved-library.json"
```

相同快照 ID 或布尔标志不能替代真实核验，提交前仍须重读并确认载荷。单条、批量及混合方案中的 v1.1 费率和区间端点输入以十进制字符串或整数表示，不用可能已被二进制浮点舍入的数字。

返回码 0 仅代表输入满足结构门槛，2 为规则阻断，3 为输入错误。所有输出均明确 `authorized:false`、`executed:false`；必须另核对实际身份、证据语义、权限、必要确认及远端保存结果。

## 提交与审计

按适用确认要求明确目标、旧值、新值、项目评估证据和例外；提交前重读身份、资料、版本及旧标签。普通新增只通过经授权页面/接口执行；不得以搜索、退格、清空 chips 的方式移除其他标签。Tier 在实际项目上下文单选：已有同项目不同值时核实归属、存储隔离、历史保留、前后值、实际修改权限、适用确认及安全替换机制；不能新增两个单选值或用普通 `add` 冒充替换。其他项目的结果不触发替换；任一必备条件不明即阻断，不得覆盖、删除或改写历史项目评估及证据。

逐条重读核验全部前后标签，处理共享申请时先检查同步结果。超时先读状态，不盲目重试。保留候选人档案及申请级别的核验时间、使用版本、来源、状态与任何未完成原因，同时保留各项目评估证据；旧 v1.0 → v1.1 映射不构成自动迁移授权。
