# 狼人杀对局记录汇总（含真实身份）

**数据库类型**: PostgreSQL (Neon)
**对局总数**: 4个
**导出时间**: 2026-09-01
**包含内容**: 对局基本信息、玩家列表（含真实身份）、行为记录、确认身份（逻辑基点）

---

## 对局 15: 未命名

- **状态**: 已确认
- **创建时间**: 2026-08-24 09:34:17
- **玩家数量**: 15人
- **版型**: 15人局（包含狼美人、狼王、骑士等特殊身份）

### 玩家列表（含真实身份）

| 座位 | 玩家ID | 玩家名称 | 真实身份 | 阵营 | 存活状态 |
|------|--------|----------|----------|------|----------|
| - | 14 | 东哥 | 骑士 | 好人 | 存活 |
| - | 16 | 栗子 | 女巫 | 好人 | 存活 |
| - | 17 | 小帕 | 狼人 | 狼人 | 存活 |
| - | 18 | 不黑 | 平民 | 好人 | 存活 |
| - | 19 | 阿潇 | 狼人 | 狼人 | 存活 |
| - | 20 | 魂（me） | 平民 | 好人 | 存活 |
| - | 22 | 大明 | 平民 | 好人 | 存活 |
| - | 27 | 钰 | 狼人 | 狼人 | 存活 |
| - | 30 | 安娜 | 猎人 | 好人 | 存活 |
| - | 31 | Ms.祭 | 守卫 | 好人 | 存活 |
| - | 32 | Mr.小安 | 狼王 | 狼人 | 存活 |
| - | 33 | FreeGas | 狼美人 | 狼人 | 存活 |
| - | 34 | 那年 | 平民 | 好人 | 存活 |
| - | 35 | 未来可期 | 预言家 | 好人 | 存活 |
| - | 21 | Mr.小羊 | 平民 | 好人 | 存活 |

**阵营统计**:
- **狼人阵营（5人）**: FreeGas(狼美人)、钰、阿潇、Mr.小安(狼王)、小帕
- **好人阵营（10人）**: 未来可期(预言家)、栗子(女巫)、安娜(猎人)、Ms.祭(守卫)、东哥(骑士)、那年、大明、魂（me）、不黑、Mr.小羊

### 确认身份（逻辑基点）

| 玩家名称 | 确认身份 | 阵营 | 确认原因 | 确认时间 |
|----------|----------|------|----------|----------|
| 未来可期 | 预言家 | 好人 | 跳预言家，夜间单死，新手玩家 | 2026-08-24 10:00:13 |
| 阿潇 | 狼人 | 狼人 | 自爆 | 2026-08-24 10:03:11 |
| 小帕 | 狼人 | 狼人 | 自爆 | 2026-08-24 10:03:28 |
| 安娜 | - | - | 预言家金水 | 2026-08-24 10:04:46 |

### 行为记录（共30条）

| 序号 | 轮次 | 阶段 | 发起者 | 目标 | 行为 | 行为类型 | 结果状态 |
|------|------|------|--------|------|------|----------|----------|
| 1 | 1 | 警上发言 | 栗子 | 大明 | 保人 | stance_expression | unknown |
| 2 | 1 | 警上发言 | FreeGas | 大明 | 警前查杀 | check_result | unknown |
| 3 | 1 | 警上发言 | 安娜 | 无 | 直接过麦 | other | unknown |
| 4 | 1 | 警上发言 | 未来可期 | 无 | 警前金水 | check_result | unknown |
| 5 | 1 | 警上发言 | 未来可期 | 无 | 跳预言家 | identity_claim | unknown |
| 6 | 1 | 警上发言 | FreeGas | 无 | 跳预言家 | identity_claim | unknown |
| 7 | 1 | 警上发言 | Mr.小安 | 无 | 晃边 | stance_expression | unknown |
| 8 | 1 | 警上发言 | 魂（me） | 未来可期 | 软站边 | stance_expression | correct |
| 9 | 1 | 警上发言 | Mr.小羊 | 魂（me） | 踩人 | stance_expression | unknown |
| 10 | 1 | 警上发言 | Mr.小羊 | FreeGas | 软站边 | stance_expression | unknown |
| 11 | 1 | 警上发言 | 小帕 | 不黑 | 警下金水 | check_result | unknown |
| 12 | 2 | 死讯公布 | 东哥 | 无 | 单死 | event | unknown |
| 13 | 2 | 死讯公布 | 未来可期 | 无 | 单死 | event | unknown |
| 14 | 2 | 白天发言 | 大明 | FreeGas | 保人 | stance_expression | unknown |
| 15 | 2 | 白天发言 | 钰 | Mr.小羊 | 保人 | stance_expression | unknown |
| 16 | 2 | 白天发言 | 钰 | 无 | 踩人 | stance_expression | unknown |
| 17 | 2 | 白天发言 | 钰 | FreeGas | 踩人 | stance_expression | unknown |
| 18 | 2 | 白天发言 | 钰 | 大明 | 踩人 | stance_expression | unknown |
| 19 | 2 | 白天发言 | 那年 | 无 | 保人 | stance_expression | unknown |
| 20 | 2 | 白天发言 | 那年 | FreeGas | 保人 | stance_expression | unknown |
| 21 | 2 | 白天发言 | 那年 | 不黑 | 保人 | stance_expression | unknown |
| 22 | 2 | 放逐投票 | 魂（me） | 钰 | 投放逐票 | vote_action | unknown |
| 23 | 2 | 放逐投票 | Mr.小安 | 钰 | 投放逐票 | vote_action | unknown |
| 24 | 2 | 放逐投票 | Mr.小安 | 钰 | 投放逐票 | vote_action | unknown |
| 25 | 2 | 放逐投票 | FreeGas | 魂（me） | 投放逐票 | vote_action | unknown |
| 26 | 2 | 放逐投票 | 大明 | Mr.小羊 | 投放逐票 | vote_action | unknown |
| 27 | 2 | 放逐投票 | 钰 | FreeGas | 投放逐票 | vote_action | unknown |
| 28 | 2 | 放逐投票 | 不黑 | FreeGas | 投放逐票 | vote_action | unknown |
| 29 | 2 | 放逐投票 | Mr.小羊 | FreeGas | 投放逐票 | vote_action | unknown |
| 30 | 2 | 放逐投票 | 栗子 | Mr.小安 | 投放逐票 | vote_action | unknown |

---

## 对局 16: 未命名

- **状态**: 已确认
- **创建时间**: 2026-08-24 10:21:33
- **玩家数量**: 13人
- **版型**: 13人局（包含混血儿第三方、狼王等特殊身份）

### 玩家列表（含真实身份）

| 座位 | 玩家ID | 玩家名称 | 真实身份 | 阵营 | 存活状态 |
|------|--------|----------|----------|------|----------|
| 1 | 20 | 魂（me） | 守卫 | 好人 | 存活 |
| 2 | 32 | Mr.小安 | 狼王 | 狼人 | 存活 |
| 3 | 35 | 未来可期 | 狼人 | 狼人 | 存活 |
| 4 | 33 | FreeGas | 混血儿 | 第三方 | 存活 |
| 7 | 14 | 东哥 | 狼人 | 狼人 | 存活 |
| 8 | 22 | 大明 | 狼人 | 狼人 | 存活 |
| 9 | 19 | 阿潇 | 平民 | 好人 | 存活 |
| 10 | 18 | 不黑 | 猎人 | 好人 | 存活 |
| 11 | 30 | 安娜 | 平民 | 好人 | 存活 |
| 12 | 16 | 栗子 | 女巫 | 好人 | 存活 |
| 13 | 31 | Ms.祭 | 预言家 | 好人 | 存活 |
| 14 | 21 | Mr.小羊 | 平民 | 好人 | 存活 |
| 16 | 17 | 小帕 | 平民 | 好人 | 存活 |

**阵营统计**:
- **狼人阵营（4人）**: Mr.小安(狼王)、未来可期、东哥、大明
- **好人阵营（8人）**: 魂（me）(守卫)、不黑(猎人)、栗子(女巫)、Ms.祭(预言家)、阿潇、安娜、Mr.小羊、小帕
- **第三方（1人）**: FreeGas(混血儿)

### 确认身份（逻辑基点）

| 玩家名称 | 确认身份 | 阵营 | 确认原因 | 确认时间 |
|----------|----------|------|----------|----------|
| 魂（me） | 守卫 | 好人 | 已知自己身份 | 2026-08-24 11:04:11 |
| 未来可期 | 狼人 | 狼人 | - | 2026-08-24 11:50:13 |

### 行为记录（共65条）

| 序号 | 轮次 | 阶段 | 发起者 | 目标 | 行为 | 行为类型 | 结果状态 |
|------|------|------|--------|------|------|----------|----------|
| 1 | 1 | 警上发言 | 大明 | 阿潇 | 警后金水 | check_result | unknown |
| 2 | 1 | 警上发言 | 阿潇 | 安娜 | 保人 | stance_expression | unknown |
| 3 | 1 | 警上发言 | 不黑 | Mr.小羊 | 警后金水 | check_result | unknown |
| 4 | 1 | 警上发言 | 安娜 | 大明 | 强势站边 | stance_expression | unknown |
| 5 | 1 | 警上发言 | Ms.祭 | 不黑 | 警前金水 | check_result | unknown |
| 6 | 1 | 警上发言 | Mr.小羊 | Ms.祭 | 强势站边 | stance_expression | unknown |
| 7 | 1 | 警上发言 | Mr.小羊 | 不黑 | 保人 | stance_expression | unknown |
| 8 | 1 | 警上发言 | 小帕 | Ms.祭 | 强势站边 | stance_expression | unknown |
| 9 | 1 | 警徽投票 | Mr.小安 | Ms.祭 | 投警徽票 | vote_action | unknown |
| 10 | 1 | 警徽投票 | 未来可期 | Ms.祭 | 投警徽票 | vote_action | unknown |
| 11 | 1 | 警徽投票 | 东哥 | Ms.祭 | 投警徽票 | vote_action | unknown |
| 12 | 1 | 白天发言 | 不黑 | 栗子 | 踩人 | stance_expression | unknown |
| 13 | 1 | 白天发言 | 不黑 | 大明 | 踩人 | stance_expression | unknown |
| 14 | 1 | 白天发言 | 不黑 | Ms.祭 | 强势站边 | stance_expression | unknown |
| 15 | 1 | 白天发言 | 阿潇 | 不黑 | 踩人 | stance_expression | unknown |
| 16 | 1 | 白天发言 | 大明 | Ms.祭 | 踩人 | stance_expression | unknown |
| 17 | 1 | 白天发言 | 大明 | Mr.小羊 | 踩人 | stance_expression | unknown |
| 18 | 1 | 白天发言 | 东哥 | 大明 | 软站边 | stance_expression | unknown |
| 19 | 1 | 白天发言 | 东哥 | 栗子 | 保人 | stance_expression | unknown |
| 20 | 1 | 白天发言 | 东哥 | 无 | 复盘 | other | unknown |
| 21 | 1 | 白天发言 | FreeGas | 无 | 跳混子 | identity_claim | unknown |
| 22 | 1 | 白天发言 | FreeGas | Ms.祭 | 站边 | stance_expression | unknown |
| 23 | 1 | 白天发言 | FreeGas | 栗子 | 踩人 | stance_expression | unknown |
| 24 | 1 | 白天发言 | FreeGas | Ms.祭 | 站边 | stance_expression | unknown |
| 25 | 1 | 白天发言 | Mr.小安 | 大明 | 回头 | other | unknown |
| 26 | 1 | 放逐投票 | 魂（me） | 无 | 弃票 | vote_action | unknown |
| 27 | 1 | 放逐投票 | 东哥 | 无 | 弃票 | vote_action | unknown |
| 28 | 1 | 放逐投票 | 阿潇 | 无 | 弃票 | vote_action | unknown |
| 29 | 1 | 放逐投票 | 小帕 | 无 | 弃票 | vote_action | unknown |
| 30 | 1 | 放逐投票 | FreeGas | Mr.小安 | 投放逐票 | vote_action | unknown |
| 31 | 1 | 放逐投票 | 不黑 | Mr.小安 | 投放逐票 | vote_action | unknown |
| 32 | 1 | 放逐投票 | 安娜 | Mr.小安 | 投放逐票 | vote_action | unknown |
| 33 | 1 | 放逐投票 | Ms.祭 | Mr.小安 | 投放逐票 | vote_action | unknown |
| 34 | 1 | 放逐投票 | Mr.小羊 | Mr.小安 | 投放逐票 | vote_action | unknown |
| 35 | 1 | 放逐投票 | 未来可期 | Mr.小羊 | 投放逐票 | vote_action | unknown |
| 36 | 1 | 放逐投票 | Mr.小安 | Ms.祭 | 投放逐票 | vote_action | unknown |
| 37 | 1 | 放逐投票 | 栗子 | Mr.小羊 | 投放逐票 | vote_action | unknown |
| 38 | 1 | 放逐投票 | 大明 | Mr.小羊 | 投放逐票 | vote_action | unknown |
| 39 | 1 | 遗言 | Mr.小安 | 无 | 跳猎人 | identity_claim | unknown |
| 40 | 1 | 遗言 | Mr.小安 | Ms.祭 | 猎人开枪 | identity_confirm | unknown |
| 41 | 2 | 死讯公布 | 小帕 | 无 | 单死 | event | unknown |
| 42 | 2 | 白天发言 | 未来可期 | 无 | 点狼坑 | other | unknown |
| 43 | 2 | 白天发言 | 未来可期 | Ms.祭 | 踩人 | stance_expression | unknown |
| 44 | 2 | 白天发言 | 未来可期 | 不黑 | 踩人 | stance_expression | unknown |
| 45 | 2 | 白天发言 | 未来可期 | Mr.小羊 | 踩人 | stance_expression | unknown |
| 46 | 2 | 白天发言 | FreeGas | 未来可期 | 踩人 | stance_expression | incorrect |
| 47 | 2 | 白天发言 | FreeGas | 大明 | 踩人 | stance_expression | unknown |
| 48 | 2 | 白天发言 | FreeGas | 栗子 | 踩人 | stance_expression | unknown |
| 49 | 2 | 白天发言 | 阿潇 | Mr.小安 | 保人 | stance_expression | unknown |
| 50 | 2 | 白天发言 | 不黑 | Mr.小安 | 对跳猎人 | identity_conflict | unknown |
| 51 | 2 | 白天发言 | 安娜 | 魂（me） | 踩人 | stance_expression | incorrect |
| 52 | 2 | 白天发言 | 安娜 | 大明 | 踩人 | stance_expression | unknown |
| 53 | 2 | 放逐投票 | FreeGas | 大明 | 投放逐票 | vote_action | unknown |
| 54 | 2 | 放逐投票 | 阿潇 | 大明 | 投放逐票 | vote_action | unknown |
| 55 | 2 | 放逐投票 | 不黑 | 大明 | 投放逐票 | vote_action | unknown |
| 56 | 2 | 放逐投票 | 安娜 | 大明 | 投放逐票 | vote_action | unknown |
| 57 | 2 | 放逐投票 | Mr.小羊 | 大明 | 投放逐票 | vote_action | unknown |
| 58 | 2 | 放逐投票 | 未来可期 | 不黑 | 投放逐票 | vote_action | unknown |
| 59 | 2 | 放逐投票 | 大明 | FreeGas | 投放逐票 | vote_action | unknown |
| 60 | 2 | 放逐投票 | 栗子 | 安娜 | 投放逐票 | vote_action | unknown |
| 61 | 3 | 死讯公布 | Mr.小羊 | 无 | 单死 | event | unknown |
| 62 | 3 | 白天发言 | 东哥 | 无 | 跳女巫 | identity_claim | unknown |
| 63 | 3 | 白天发言 | 未来可期 | 无 | 跳守卫 | identity_claim | unknown |
| 64 | 3 | 白天发言 | 魂（me） | 未来可期 | 对跳守卫 | identity_conflict | unknown |
| 65 | 3 | 白天发言 | 栗子 | 东哥 | 对跳女巫 | identity_conflict | unknown |

---

## 对局 17: 未命名

- **状态**: 已确认
- **创建时间**: 2026-08-25 05:21:10
- **玩家数量**: 15人
- **版型**: 15人局（包含狼王、狼美人、骑士等特殊身份）

### 玩家列表（含真实身份）

| 座位 | 玩家ID | 玩家名称 | 真实身份 | 阵营 | 存活状态 |
|------|--------|----------|----------|------|----------|
| 1 | 32 | Mr.小安 | 骑士 | 好人 | 存活 |
| 2 | 34 | 那年 | 平民 | 好人 | 存活 |
| 3 | 35 | 未来可期 | 狼人 | 狼人 | 存活 |
| 4 | 33 | FreeGas | 狼王 | 狼人 | 存活 |
| 6 | 27 | 钰 | 女巫 | 好人 | 存活 |
| 7 | 14 | 东哥 | 狼美人 | 狼人 | 存活 |
| 8 | 22 | 大明 | 平民 | 好人 | 存活 |
| 9 | 19 | 阿潇 | 预言家 | 好人 | 存活 |
| 10 | 18 | 不黑 | 猎人 | 好人 | 存活 |
| 11 | 30 | 安娜 | 守卫 | 好人 | 存活 |
| 12 | 16 | 栗子 | 狼人 | 狼人 | 存活 |
| 13 | 31 | Ms.祭 | 平民 | 好人 | 存活 |
| 14 | 17 | 小帕 | 平民 | 好人 | 存活 |
| 15 | 21 | Mr.小羊 | 狼人 | 狼人 | 存活 |
| 16 | 20 | 魂（me） | 平民 | 好人 | 存活 |

**阵营统计**:
- **狼人阵营（5人）**: 未来可期、FreeGas(狼王)、东哥(狼美人)、栗子、Mr.小羊
- **好人阵营（10人）**: Mr.小安(骑士)、钰(女巫)、阿潇(预言家)、不黑(猎人)、安娜(守卫)、那年、大明、Ms.祭、小帕、魂（me）

### 确认身份（逻辑基点）

| 玩家名称 | 确认身份 | 阵营 | 确认原因 | 确认时间 |
|----------|----------|------|----------|----------|
| 魂（me） | 平民 | 好人 | 本人已知 | 2026-08-25 05:29:35 |
| Mr.小安 | 骑士 | 好人 | 发动技能 | 2026-08-25 07:13:23 |
| 钰 | - | - | 骑士技能确认 | 2026-08-25 07:16:28 |

### 行为记录（共46条）

| 序号 | 轮次 | 阶段 | 发起者 | 目标 | 行为 | 行为类型 | 结果状态 |
|------|------|------|--------|------|------|----------|----------|
| 1 | 1 | 警上发言 | Mr.小安 | 魂（me） | 警后查杀 | check_result | unknown |
| 2 | 1 | 警上发言 | Mr.小安 | 魂（me） | 跳预言家 | identity_claim | unknown |
| 3 | 1 | 警上发言 | FreeGas | Mr.小安 | 软站边 | stance_expression | unknown |
| 4 | 1 | 警上发言 | 东哥 | Mr.小安 | 强势站边 | stance_expression | unknown |
| 5 | 1 | 警上发言 | 大明 | Mr.小安 | 站边 | stance_expression | unknown |
| 6 | 1 | 警上发言 | 大明 | 东哥 | 保人 | stance_expression | unknown |
| 7 | 1 | 警上发言 | 阿潇 | 不黑 | 警下金水 | check_result | unknown |
| 8 | 1 | 警上发言 | 阿潇 | 不黑 | 跳预言家 | identity_claim | unknown |
| 9 | 1 | 警上发言 | 安娜 | 无 | 晃边 | stance_expression | unknown |
| 10 | 1 | 警上发言 | 栗子 | 阿潇 | 跳女巫 | identity_claim | unknown |
| 11 | 1 | 警上发言 | 栗子 | 阿潇 | 报银水 | other | unknown |
| 12 | 1 | 白天发言 | 大明 | Mr.小安 | 保人 | stance_expression | incorrect |
| 13 | 1 | 白天发言 | 大明 | 安娜 | 踩人 | stance_expression | unknown |
| 14 | 1 | 白天发言 | 东哥 | Mr.小安 | 保人 | stance_expression | incorrect |
| 15 | 1 | 白天发言 | 东哥 | FreeGas | 保人 | stance_expression | unknown |
| 16 | 1 | 白天发言 | 东哥 | 大明 | 保人 | stance_expression | unknown |
| 17 | 1 | 白天发言 | 东哥 | 阿潇 | 保人 | stance_expression | unknown |
| 18 | 1 | 白天发言 | 东哥 | 安娜 | 保人 | stance_expression | unknown |
| 19 | 1 | 白天发言 | 东哥 | 栗子 | 保人 | stance_expression | unknown |
| 20 | 1 | 白天发言 | 钰 | FreeGas | 踩人 | stance_expression | unknown |
| 21 | 1 | 白天发言 | 钰 | FreeGas | 踩人 | stance_expression | unknown |
| 22 | 1 | 白天发言 | 钰 | FreeGas | 踩人 | stance_expression | unknown |
| 23 | 1 | 白天发言 | 钰 | 东哥 | 踩人 | stance_expression | unknown |
| 24 | 1 | 白天发言 | FreeGas | 钰 | 保人 | stance_expression | correct |
| 25 | 1 | 白天发言 | FreeGas | 东哥 | 踩人 | stance_expression | unknown |
| 26 | 1 | 白天发言 | FreeGas | 大明 | 踩人 | stance_expression | unknown |
| 27 | 1 | 白天发言 | FreeGas | 魂（me） | 踩人 | stance_expression | incorrect |
| 28 | 1 | 白天发言 | 那年 | 东哥 | 踩人 | stance_expression | unknown |
| 29 | 1 | 白天发言 | 那年 | 大明 | 踩人 | stance_expression | unknown |
| 30 | 1 | 白天发言 | Mr.小安 | 无 | 跳骑士 | identity_claim | unknown |
| 31 | 1 | 白天发言 | Mr.小羊 | 那年 | 踩人 | stance_expression | unknown |
| 32 | 1 | 白天发言 | 小帕 | 无 | 拍平民 | other | unknown |
| 33 | 1 | 白天发言 | Ms.祭 | 无 | 拍平民 | other | unknown |
| 34 | 1 | 白天发言 | 不黑 | 魂（me） | 踩人 | stance_expression | incorrect |
| 35 | 1 | 放逐投票 | Mr.小安 | 无 | 单死 | event | unknown |
| 36 | 1 | 放逐投票 | 那年 | 东哥 | 投放逐票 | vote_action | unknown |
| 37 | 1 | 放逐投票 | 阿潇 | 东哥 | 投放逐票 | vote_action | unknown |
| 38 | 1 | 放逐投票 | 小帕 | 东哥 | 投放逐票 | vote_action | unknown |
| 39 | 1 | 放逐投票 | 未来可期 | Ms.祭 | 投放逐票 | vote_action | unknown |
| 40 | 1 | 放逐投票 | Mr.小羊 | Ms.祭 | 投放逐票 | vote_action | unknown |
| 41 | 1 | 放逐投票 | 东哥 | 小帕 | 投放逐票 | vote_action | unknown |
| 42 | 1 | 放逐投票 | 大明 | 无 | 投放逐票 | vote_action | unknown |
| 43 | 1 | 放逐投票 | 不黑 | 无 | 投放逐票 | vote_action | unknown |
| 44 | 1 | 放逐投票 | 安娜 | 无 | 投放逐票 | vote_action | unknown |
| 45 | 1 | 放逐投票 | 栗子 | 无 | 投放逐票 | vote_action | unknown |
| 46 | 1 | 放逐投票 | Mr.小羊 | 栗子 | 对跳女巫 | identity_conflict | unknown |

---

## 对局 19: 未命名

- **状态**: 进行中
- **创建时间**: 2026-08-31 05:46:41
- **玩家数量**: 10人

### 玩家列表

| 座位 | 玩家ID | 玩家名称 | 真实身份 | 阵营 | 存活状态 |
|------|--------|----------|----------|------|----------|
| 1 | 28 | 高老师 | 未知 | 未知 | 存活 |
| 2 | 20 | 魂（me） | 预言家 | 好人 | 存活 |
| 3 | 32 | Mr.小安 | 未知 | 未知 | 存活 |
| 4 | 42 | 讨厌鬼 | 未知 | 未知 | 存活 |
| 6 | 14 | 东哥 | 未知 | 未知 | 存活 |
| 8 | 33 | FreeGas | 未知 | 未知 | 存活 |
| 9 | 18 | 不黑 | 未知 | 未知 | 存活 |
| 12 | 16 | 栗子 | 未知 | 未知 | 存活 |
| 14 | 21 | Mr.小羊 | 未知 | 未知 | 存活 |
| 16 | 29 | 夏老师 | 未知 | 未知 | 存活 |

### 确认身份（逻辑基点）

| 玩家名称 | 确认身份 | 阵营 | 确认原因 | 确认时间 |
|----------|----------|------|----------|----------|
| 魂（me） | 预言家 | 好人 | - | 2026-08-31 06:46:14 |

### 行为记录（共29条）

| 序号 | 轮次 | 阶段 | 发起者 | 目标 | 行为 | 行为类型 | 结果状态 |
|------|------|------|--------|------|------|----------|----------|
| 1 | 1 | 警上发言 | 夏老师 | 栗子 | 跳预言家 | identity_claim | unknown |
| 2 | 1 | 警上发言 | 夏老师 | 栗子 | 警下查杀 | check_result | unknown |
| 3 | 1 | 警上发言 | Mr.小羊 | 夏老师 | 跳预言家 | identity_claim | unknown |
| 4 | 1 | 警上发言 | Mr.小羊 | 夏老师 | 警前查杀 | check_result | unknown |
| 5 | 1 | 警上发言 | 东哥 | Mr.小安 | 跳预言家 | identity_claim | unknown |
| 6 | 1 | 警上发言 | 东哥 | Mr.小安 | 警后金水 | check_result | unknown |
| 7 | 1 | 警上发言 | 东哥 | 不黑 | 踩人 | stance_expression | unknown |
| 8 | 1 | 警上发言 | Mr.小安 | 东哥 | 强势站边 | stance_expression | unknown |
| 9 | 1 | 警上发言 | 魂（me） | 栗子 | 跳预言家 | identity_claim | unknown |
| 10 | 1 | 警上发言 | 魂（me） | 栗子 | 警下金水 | check_result | unknown |
| 11 | 1 | 警徽投票 | 高老师 | 无 | 弃票 | vote_action | unknown |
| 12 | 1 | 警徽投票 | FreeGas | 东哥 | 投警徽票 | vote_action | unknown |
| 13 | 1 | 警徽投票 | 栗子 | 无 | 弃票 | vote_action | unknown |
| 14 | 1 | 白天发言 | 讨厌鬼 | 无 | 晃边 | stance_expression | unknown |
| 15 | 1 | 白天发言 | 讨厌鬼 | 魂（me） | 踩人 | stance_expression | unknown |
| 16 | 1 | 白天发言 | Mr.小安 | 讨厌鬼 | 保人 | stance_expression | unknown |
| 17 | 1 | 白天发言 | 高老师 | 魂（me） | 保人 | stance_expression | unknown |
| 18 | 1 | 白天发言 | 高老师 | 魂（me） | 站边 | stance_expression | unknown |
| 19 | 1 | 白天发言 | 夏老师 | 讨厌鬼 | 保人 | stance_expression | unknown |
| 20 | 1 | 放逐投票 | 高老师 | 高老师 | 投放逐票 | vote_action | unknown |
| 21 | 1 | 放逐投票 | 魂（me） | 讨厌鬼 | 投放逐票 | vote_action | unknown |
| 22 | 1 | 放逐投票 | Mr.小安 | 高老师 | 投放逐票 | vote_action | unknown |
| 23 | 1 | 放逐投票 | 讨厌鬼 | 魂（me） | 投放逐票 | vote_action | unknown |
| 24 | 1 | 放逐投票 | 东哥 | 无 | 弃票 | vote_action | unknown |
| 25 | 1 | 放逐投票 | FreeGas | 讨厌鬼 | 投放逐票 | vote_action | unknown |
| 26 | 1 | 放逐投票 | 不黑 | 夏老师 | 投放逐票 | vote_action | unknown |
| 27 | 1 | 放逐投票 | 栗子 | 东哥 | 投放逐票 | vote_action | unknown |
| 28 | 1 | 放逐投票 | Mr.小羊 | 高老师 | 投放逐票 | vote_action | unknown |
| 29 | 1 | 放逐投票 | 夏老师 | 夏老师 | 投放逐票 | vote_action | unknown |

---

## 数据统计

- **总对局数**: 4个
- **已确认对局**: 3个（对局15、16、17）
- **进行中对局**: 1个（对局19）
- **总行为记录数**: 170条
- **涉及玩家数**: 约20个不同玩家
- **涉及特殊身份**: 预言家、女巫、猎人、守卫、骑士、狼王、狼美人、混血儿(第三方)

### 各对局阵营分布

| 对局 | 狼人数量 | 好人数量 | 第三方数量 | 总人数 |
|------|----------|----------|------------|--------|
| 对局15 | 5 | 10 | 0 | 15 |
| 对局16 | 4 | 8 | 1 | 13 |
| 对局17 | 5 | 10 | 0 | 15 |
| 对局19 | 未知 | 未知 | 未知 | 10 |
