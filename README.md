# 涂膜试片校准与离线质量核账

涂装厂的试验中心把试片网格和逐片称重交给站端计量员。计量员按修订发行毫米坐标站件。夜班关闭站库后仍可在中心选择切线，核定各区承载的涂膜质量，供班组选择复测区域。白班勘误时追加修订，交班人员仍能按既有报告号复领原来的分账和出处。

## 运行

使用 Python 3.11 标准库。由平台提供的回归入口和独立演示均从项目根目录运行。

```sh
python3 -B check_project.py
python3 -B demo.py
```

演示从 `samples/` 读入面积与勘误、相反折叠、贴切线的均匀质量与交点三份输入。在临时目录建立两份 SQLite 档案，经公开入口出件、点收，关闭站库后核定，重开中心后领取和导出实际定稿。回归还覆盖输入拒绝、重递冲突以及签存回滚和重提。

## 站端与中心 API

调用者持有并关闭两份独立的 `sqlite3.Connection`。每次打开后，站库调用 `station.issue.initialize_station(connection, station_id=None)`，中心库调用 `center.publish.initialize_center(connection)`。新站库须提供全局唯一且固定的站标识，由字母开头且至多 64 个 ASCII 字母、数字、下划线或连字符组成。重开可省略站标识，或传入原标识。初始化可重复执行并保留用户数据。写入口在空闲连接上自行管理事务。

| 入口 | 调用和结果 |
| --- | --- |
| `station.intake.import_batch` | `import_batch(station, pieces)` 接受试片记录的可迭代对象，每条含 `name`、`vertices`、`mass`，整批入档后返回整数批次号。批内片名唯一，三个二维源顶点须构成非退化三角片。 |
| `station.revisions.revise` | `revise(station, batch_id, calibrations)` 为指定批次追加修订并返回整数修订号。`calibrations` 的键必须精确覆盖原片名，每个值含两组三系数 `[a,b,c]`、`[d,e,f]`，目标坐标为 `(a*x+b*y+c, d*x+e*y+f)` 毫米。 |
| `station.issue.issue` | `issue(station, batch_id, revision_id)` 返回固定站件 JSON 文本。同一修订重复发行复用原身份和正文。 |
| `center.accept.accept` | `accept(center, station_piece)` 验证并保存实收正文，返回整数实收号。同发行身份同内容重递返回原号，同身份异内容抛出 `ValueError`。 |
| `center.publish.publish` | `publish(center, receipt_id, x_cut, y_cut)` 只根据指定实收件核定质量，签存成功后返回整数报告号。 |
| `center.report_lookup.read` | `read(center, report_id)` 按号返回 `ReportSnapshot` 或 `None`。`center.handoff_export.export_report(center, report_id)` 将同一快照连同报告号导出为 JSON 文本，缺号时返回 `None`。 |

坐标、质量和切线的 Python 输入接受整数、`Fraction` 或能由 `Fraction` 精确解释的字符串。片质量必须为正。非法输入抛出 `ValueError`，未知批次、未知或别批修订、未知实收号抛出 `KeyError`。SQLite 写入或提交错误沿调用返回，失败事务无新增记录。已签报告保存原切线、四区质量和实收出处，按号领取时直接使用该快照。

## 计量口径

各片质量在源三角片上均匀分布，经仿射校准形成毫米坐标下的质量分布。站件含可独立验证的规范正文摘要、发行出处及匿名质量单元。面元按共同裁切后的面积比例分配。线元以毫米端点确定的有理段参数表达分段一次质量密度，中心对区内参数范围积分。点元整量入账。重叠质量单元分别计量后相加。

四区依次为 `LL`、`HL`、`LH`、`HH`。每轴严格小于切线归低侧，等于切线归高侧。整条贴线的质量也按此归属。定稿保留四区零值，并校对合计与实收总量完全相等。站件和报告中的有理数使用规范分数字符串，报告的 `zones` 是有序列表。
