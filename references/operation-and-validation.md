# Rate 组：页面操作与离线校验

## v1.1 的范围和边界

Rate 是 Taxonomy v1.1 第六个独立组，单选；在适用的 ATS Talent Pool 记录要求分类期望时薪时使用，不适用于 Benchmark。下列五档为本次会话 2026-11-17 16:28 在 Moka 的 Enabled/Rate 页面核验的精确标签，并被纳入 v1.1 待审核文档。执行新任务时仍须核实组织的当前批准版本、Active 状态、完整区间及真实 Moka 标签 ID；这份文档或现场快照不自动证明目前已发布。

| Moka 标签原文 | 数值条件（USD/小时） |
|---|---|
| `0 USD ≤ Expected Rate ≤ 10 USD` | 0 ≤ x ≤ 10 |
| `10 USD < Expected Rate ≤ 20 USD` | 10 < x ≤ 20 |
| `20 USD < Expected Rate ≤ 30 USD` | 20 < x ≤ 30 |
| `30 USD < Expected Rate ≤ 60 USD` | 30 < x ≤ 60 |
| `60 USD < Expected Rate ≤ 100 USD` | 60 < x ≤ 100 |

优先读取 Moka 中由 TA 与候选人进一步沟通后记录的 Note 期望时薪；若 Note 未记录期望时薪，再读取 Candidate Profile 中真实的 `Expected hourly rate in USD`。按用户确认，Note 是范围时用 Decimal 算上下限中点，只用于选择区间，保留 Note 完整原文、原始范围及计算依据。核实 Note 来源、关联申请、完整性、金额、USD/小时单位和范围边界；有多条不同费率或单位、范围不明时暂停，不擅自推断、换算或回退。10、20、30、60、100 各落在上界包含该数的前一档。非负有效 USD/小时数字大于 100，在完整五档均经核实且新标签获批并 Active 后，可按 v1.1 使用 `rate not included`；缺失、未知、非数字、非有限值、负数、币种/周期不明及不适用都不是超范围。

用户要求按 v1.1 的六组全面打标时应评估 Rate 是否适用于该记录；只要求其他组时不要扩大范围。正常 Rate 与 `rate not included` 属同一单选组，不得并存。已有不同 Rate 时，除非用户已授权对应纠正且确认身份、旧值、权限、目标、实际 UI 一对一替换步骤和恢复计划，否则暂停并报告；按 Note 纠正不可冒充普通新增。区间重叠、身份不明或库状态不明均暂停。

## 标签库、身份与来源

- 记录真实租户、岗位、筛选条件、申请总数、操作字段、当前身份与权限；分页和懒加载须核对完整性。不得复用历史任务的候选人、租户或 ID。
- 核实当前组织版本和每个目标标签是否批准、Active、对应真实 Moka 标签 ID。若可见 `id`、`tagId` 等字段，不猜测字段语义。新的 `rate not included` 不能因为写入文档就视为已经在 Moka 创建或启用。
- 核验申请 ID 与档案身份；申请 ID 不等于候选人 ID。相同姓名或联系方式不足以自动合并，须确认同人的多申请标签是否共享并比较实际费率。材料及审计留在私有目录。
- 混合多组计划必须基于同一申请/目标对象、同一当前批准版本、同一份完整旧标签快照及同一批准载荷；Rate 项必须通过专用费率门控，不能只用一般 Taxonomy 门控绕过边界。提交前如任何身份、证据、版本或旧值变更，重新核对。

## 安全交互与核验

1. 提交前核对申请 ID、姓名、费率原文、完整已加载旧标签及计划；旧标签和真实组别未经读取时不得视为空。
2. 在真实页面选择候选人自定义标签；对普通区间可搜索 `Expected Rate`，异常项按其实际获准的准确名称搜索。先核对编辑器中已选标签；不要用退格、清空、全选替换等方式删除已有 chips，不使用猜测的后台接口。
3. 新增后重开/读取同一申请，核验目标标签及全部旧值。若同步到共享申请，重读确认后再跳过，不能当成另一条已单独新增。超时或结果不明先查远端，不盲目重试。意外改变立即暂停，依授权修复并核验。

## 离线门控

Note 优先、范围中点或替换计划使用 `scripts/validate_note_rate_plan.py`，严格按脚本契约保留完整 Note 原文、真实来源核验、用户规则和前后值；不得通过伪造通信、截断原文、隐藏旧标签或伪装 Profile 绕过门控。非原子 UI 操作须有可核验的安全步骤、逐步验证和恢复计划。旧门控只适用于已确认没有可用 Note 时薪、且无既有 Rate 的 Profile 新增；不能用它绕过 Note 优先或替换检查。

复制 `templates/rate-plan.example.json`、`rate-evidence-context.example.json`、`rate-library.example.json` 到私有目录，只填真实信息。`candidate.moka_id` 对此门控指已经核验的申请记录 ID；源段落必须包含字段名和值的真实连续原文，证据为逐字值。库与旧标签/组别验证标志及出处须有真实来源，不能仅为通过校验填写。v1.1 的普通区间和 `rate not included` 均要求完整五档经核实及相应出处；具体字段见脚本说明。

```bash
python3 "<skill-dir>/scripts/validate_rate_write_plan.py" \
  --plan "<private-dir>/plan.json" \
  --context "<private-dir>/context.json" \
  --library "<private-dir>/approved-library.json"
```

单条门控不联网、不写 Moka。输入中已有任何 Rate 标签、ID/名称错、库不获准、区间异常、单位错误或原文证据不符均阻断；`ready_for_confirmation: true` 不等于授权或已执行。普通区间与异常标签必须区分：异常不是数值区间，不能伪造上下界让校验通过。

批量结构为 `{"items":[{"plan":{},"context":{},"sharing":{}}]}`。已核验同人多申请时，`sharing` 填本次可信身份键及已核验的共享关系；不得仅从姓名推断。校验器阻断重复申请、同名身份不明、同一人冲突费率或不明共享关系；共享且一致的申请仅保留一条 ready，其他延期，处理后重新读取。它无法发现所有同人记录，仍需人工交叉核对。

```bash
python3 "<skill-dir>/scripts/validate_rate_batch.py" \
  --batch "<private-dir>/batch.json" \
  --library "<private-dir>/approved-library.json" \
  --output "<private-dir>/batch-validation.json"
```

返回 0 仅表示无结构性阻断，可能包含需重读的 `deferred_shared`；2 为阻断、3 为输入/输出错误。始终还需真实许可、必要确认及实际远端核验。按申请记录读取时间、费率原文、旧标签、真实库版本和出处、执行/跳过/阻断、写后状态与核验时间，异常单列给用户。
