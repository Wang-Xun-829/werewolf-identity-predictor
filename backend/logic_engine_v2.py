"""
狼人杀综合逻辑引擎 v2.0
融合所有讨论的狼人杀逻辑，包括：

第一阶段：基础逻辑
1. 确定性逻辑（自爆=100%狼、认狼=98%狼、预言家查验链）
2. 行为结果推断（保错/踩对/站错/投错等）
3. 身份唯一性逻辑（对跳身份的人嫌疑增加）
4. 行为顺序逻辑（跳预言家又退水/跳别的身份，预言家概率降低）

第二阶段：进阶逻辑
5. 言行不一检测（死踩但没投、归票但没投）
6. 双边分析+公共狼（分别假设两个预言家，推狼坑，找交集）
7. 狼坑不够检测（某边狼坑凑不够→预言家概率降低）
8. 逆势保人逻辑（全场踩唯独保，最终是好人→保人者嫌疑降低）

第三阶段：高级逻辑
9. 收益逻辑（事件发生后谁是受益者）
10. 保打关系矛盾检测
11. 倒钩狼识别
"""
from sqlalchemy.orm import Session
from models import (
    Action, ActionType, Player, Game, ConfirmedIdentity, Identity,
    GamePlayer, Setup, SetupIdentity
)
from typing import Dict, List, Optional, Tuple
from collections import defaultdict
import re


# ==================== 辅助函数 ====================

def get_identity_name_map(db: Session) -> Dict[int, str]:
    """获取 identity_id -> name 映射"""
    identities = db.query(Identity).filter(Identity.is_active == True).all()
    return {ident.id: ident.name for ident in identities}


def get_identity_id_map(db: Session) -> Dict[str, int]:
    """获取 name -> identity_id 映射"""
    identities = db.query(Identity).filter(Identity.is_active == True).all()
    return {ident.name: ident.id for ident in identities}


def get_player_name_map(db: Session) -> Dict[int, str]:
    """获取 player_id -> name 映射"""
    players = db.query(Player).all()
    return {p.id: p.name for p in players}


def get_action_type_map(db: Session) -> Dict[int, ActionType]:
    """获取 action_type_id -> ActionType 映射"""
    return {at.id: at for at in db.query(ActionType).all()}


def is_wolf_identity(identity_name: str) -> bool:
    """判断是否是狼人阵营身份"""
    return "狼" in identity_name


def is_god_identity(identity_name: str) -> bool:
    """判断是否是神职身份"""
    god_keywords = ["预言家", "女巫", "猎人", "守卫", "骑士", "白痴", "摄梦人"]
    return any(kw in identity_name for kw in god_keywords)


def get_game_actions(db: Session, game_id: int) -> List[Action]:
    """获取对局的所有行为，按轮次和时间排序"""
    return db.query(Action).filter(
        Action.game_id == game_id
    ).order_by(Action.round_number, Action.created_at).all()


# ==================== 第一阶段：基础逻辑 ====================

class DeterministicLogic:
    """确定性逻辑：100%或接近100%确定的结论"""

    def __init__(self, db: Session, game_id: int):
        self.db = db
        self.game_id = game_id
        self.player_name_map = get_player_name_map(db)
        self.identity_name_map = get_identity_name_map(db)
        self.action_type_map = get_action_type_map(db)
        self.actions = get_game_actions(db, game_id)

    def get_confirmed_identities(self) -> Dict[int, Dict]:
        """获取所有确认身份（逻辑基点）"""
        confirmed = self.db.query(ConfirmedIdentity).filter(
            ConfirmedIdentity.game_id == self.game_id
        ).all()
        result = {}
        for c in confirmed:
            result[c.player_id] = {
                "identity_id": c.identity_id,
                "camp_only": c.camp_only,
                "reason": c.reason,
                "confirmed_at": c.confirmed_at
            }
        return result

    def detect_self_explode(self) -> List[Dict]:
        """检测自爆行为：自爆=100%狼人"""
        results = []
        explode_action_ids = [
            at.id for at in self.action_type_map.values()
            if "自爆" in at.name
        ]

        for action in self.actions:
            if action.action_type_id in explode_action_ids:
                player_name = self.player_name_map.get(action.player_id, f"玩家{action.player_id}")
                results.append({
                    "type": "self_explode",
                    "player_id": action.player_id,
                    "player_name": player_name,
                    "description": f"{player_name}自爆 → {player_name}是100%狼人",
                    "confidence": 1.0,
                    "action_id": action.id
                })
        return results

    def detect_wolf_claim(self) -> List[Dict]:
        """检测认狼行为：认狼=98%狼人"""
        results = []
        claim_action_ids = [
            at.id for at in self.action_type_map.values()
            if "认狼" in at.name
        ]

        for action in self.actions:
            if action.action_type_id in claim_action_ids:
                player_name = self.player_name_map.get(action.player_id, f"玩家{action.player_id}")
                results.append({
                    "type": "wolf_claim",
                    "player_id": action.player_id,
                    "player_name": player_name,
                    "description": f"{player_name}认狼 → {player_name}大概率是狼人(98%)",
                    "confidence": 0.98,
                    "action_id": action.id
                })
        return results

    def get_prophet_claims(self) -> List[Dict]:
        """获取所有跳预言家的玩家及其查验信息"""
        prophet_action_ids = [
            at.id for at in self.action_type_map.values()
            if "预言家" in at.name and ("跳" in at.name or "起跳" in at.name)
        ]

        check_action_ids = [
            at.id for at in self.action_type_map.values()
            if "金水" in at.name or "查杀" in at.name
        ]

        prophets = []
        for action in self.actions:
            if action.action_type_id in prophet_action_ids:
                prophet_id = action.player_id

                # 找该玩家的所有查验行为
                checks = []
                for ca in self.actions:
                    if ca.player_id == prophet_id and ca.action_type_id in check_action_ids:
                        check_type_name = self.action_type_map.get(ca.action_type_id, "").name if self.action_type_map.get(ca.action_type_id) else ""
                        is_gold = "金水" in check_type_name
                        checks.append({
                            "target_id": ca.target_player_id,
                            "target_name": self.player_name_map.get(ca.target_player_id, f"玩家{ca.target_player_id}"),
                            "is_gold": is_gold,
                            "round": ca.round_number,
                            "phase": ca.phase
                        })

                prophets.append({
                    "prophet_id": prophet_id,
                    "prophet_name": self.player_name_map.get(prophet_id, f"玩家{prophet_id}"),
                    "checks": checks,
                    "jump_round": action.round_number,
                    "jump_phase": action.phase
                })

        return prophets

    def analyze_check_chain(self) -> Dict:
        """分析预言家查验链"""
        prophets = self.get_prophet_claims()
        confirmed = self.get_confirmed_identities()

        derived_facts = []
        contradictions = []

        # 检查是否有确认的预言家
        confirmed_prophet_id = None
        for pid, c in confirmed.items():
            if c["identity_id"]:
                identity_name = self.identity_name_map.get(c["identity_id"], "")
                if "预言家" in identity_name:
                    confirmed_prophet_id = pid
                    break

        # 如果有确认的预言家，推导所有查验结果
        if confirmed_prophet_id:
            for prophet in prophets:
                if prophet["prophet_id"] == confirmed_prophet_id:
                    for check in prophet["checks"]:
                        if check["is_gold"]:
                            derived_facts.append({
                                "type": "gold_water",
                                "prophet_id": confirmed_prophet_id,
                                "target_id": check["target_id"],
                                "description": f"预言家给{check['target_name']}金水 → {check['target_name']}是铁好人",
                                "confidence": 1.0
                            })
                        else:
                            derived_facts.append({
                                "type": "check_kill",
                                "prophet_id": confirmed_prophet_id,
                                "target_id": check["target_id"],
                                "description": f"预言家查杀{check['target_name']} → {check['target_name']}是铁狼",
                                "confidence": 1.0
                            })

        # 检查查验链矛盾
        for i, p1 in enumerate(prophets):
            for j, p2 in enumerate(prophets):
                if i >= j:
                    continue
                p1_targets = {c["target_id"]: c["is_gold"] for c in p1["checks"]}
                p2_targets = {c["target_id"]: c["is_gold"] for c in p2["checks"]}

                for target_id in p1_targets:
                    if target_id in p2_targets and p1_targets[target_id] != p2_targets[target_id]:
                        target_name = self.player_name_map.get(target_id, f"玩家{target_id}")
                        contradictions.append({
                            "type": "check_contradiction",
                            "target_id": target_id,
                            "prophet_1": p1["prophet_id"],
                            "prophet_2": p2["prophet_id"],
                            "description": f"玩家{target_name}被一个预言家给金水，另一个给查杀，存在矛盾"
                        })

        return {
            "prophets": prophets,
            "derived_facts": derived_facts,
            "contradictions": contradictions,
            "confirmed_prophet_id": confirmed_prophet_id
        }

    def get_determined_wolves(self) -> List[int]:
        """获取确定的狼人列表（自爆、认狼、预言家查杀等）"""
        wolves = set()

        # 自爆的玩家
        for fact in self.detect_self_explode():
            wolves.add(fact["player_id"])

        # 认狼的玩家
        for fact in self.detect_wolf_claim():
            if fact["confidence"] >= 0.95:
                wolves.add(fact["player_id"])

        # 确认身份是狼人的玩家
        confirmed = self.get_confirmed_identities()
        for pid, c in confirmed.items():
            if c["identity_id"]:
                identity_name = self.identity_name_map.get(c["identity_id"], "")
                if is_wolf_identity(identity_name):
                    wolves.add(pid)

        # 预言家查杀的玩家
        check_analysis = self.analyze_check_chain()
        for fact in check_analysis["derived_facts"]:
            if fact["type"] == "check_kill":
                wolves.add(fact["target_id"])

        return list(wolves)

    def get_determined_good(self) -> List[int]:
        """获取确定的好人列表（预言家金水、确认身份等）"""
        good = set()

        # 确认身份是好人的玩家
        confirmed = self.get_confirmed_identities()
        for pid, c in confirmed.items():
            if c["identity_id"]:
                identity_name = self.identity_name_map.get(c["identity_id"], "")
                if not is_wolf_identity(identity_name) and "混血" not in identity_name:
                    good.add(pid)

        # 预言家金水的玩家
        check_analysis = self.analyze_check_chain()
        for fact in check_analysis["derived_facts"]:
            if fact["type"] == "gold_water":
                good.add(fact["target_id"])

        return list(good)


class IdentityUniquenessLogic:
    """身份唯一性逻辑：对跳身份的人嫌疑增加"""

    def __init__(self, db: Session, game_id: int):
        self.db = db
        self.game_id = game_id
        self.player_name_map = get_player_name_map(db)
        self.identity_name_map = get_identity_name_map(db)
        self.action_type_map = get_action_type_map(db)
        self.actions = get_game_actions(db, game_id)

    def detect_identity_conflicts(self) -> List[Dict]:
        """检测身份对跳冲突"""
        conflicts = []

        # 找所有跳身份的行为
        jump_actions = defaultdict(list)
        for action in self.actions:
            action_type = self.action_type_map.get(action.action_type_id)
            if not action_type:
                continue
            action_name = action_type.name

            # 匹配"跳XX"或"对跳XX"模式
            match = re.search(r'(?:对)?跳(.+)', action_name)
            if match:
                identity_name = match.group(1).strip()
                # 只考虑神职身份
                if is_god_identity(identity_name) or "预言家" in identity_name:
                    jump_actions[identity_name].append({
                        "player_id": action.player_id,
                        "player_name": self.player_name_map.get(action.player_id, f"玩家{action.player_id}"),
                        "round": action.round_number,
                        "action_name": action_name
                    })

        # 找出对跳的身份
        for identity_name, jumpers in jump_actions.items():
            unique_players = list({j["player_id"]: j for j in jumpers}.values())
            if len(unique_players) >= 2:
                player_names = [j["player_name"] for j in unique_players]
                conflicts.append({
                    "type": "identity_conflict",
                    "identity_name": identity_name,
                    "players": unique_players,
                    "player_names": player_names,
                    "description": f"{ '、'.join(player_names) }都跳{identity_name}，其中至少一个是狼",
                    "confidence": 0.7
                })

        return conflicts

    def get_conflict_suspicion_adjustments(self) -> Dict[int, float]:
        """获取对跳身份的嫌疑调整：对跳的人狼人概率增加"""
        adjustments = defaultdict(float)
        conflicts = self.detect_identity_conflicts()

        for conflict in conflicts:
            for player in conflict["players"]:
                # 对跳身份的人狼人概率增加
                adjustments[player["player_id"]] += 0.1

        return dict(adjustments)


class BehaviorSequenceLogic:
    """行为顺序逻辑：跳预言家又退水/跳别的身份，预言家概率降低"""

    def __init__(self, db: Session, game_id: int):
        self.db = db
        self.game_id = game_id
        self.player_name_map = get_player_name_map(db)
        self.action_type_map = get_action_type_map(db)
        self.actions = get_game_actions(db, game_id)

    def detect_behavior_changes(self) -> List[Dict]:
        """检测玩家行为变化（跳预言家又退水/跳别的身份）"""
        changes = []

        # 按玩家分组行为
        player_actions = defaultdict(list)
        for action in self.actions:
            player_actions[action.player_id].append(action)

        for player_id, actions in player_actions.items():
            actions.sort(key=lambda a: (a.round_number or 0, a.created_at or ""))

            jumped_prophet = False
            prophet_jump_round = None

            for action in actions:
                action_type = self.action_type_map.get(action.action_type_id)
                if not action_type:
                    continue
                action_name = action_type.name

                # 跳预言家
                if "预言家" in action_name and ("跳" in action_name or "起跳" in action_name):
                    jumped_prophet = True
                    prophet_jump_round = action.round_number

                # 跳预言家后又退水
                elif jumped_prophet and "退水" in action_name:
                    player_name = self.player_name_map.get(player_id, f"玩家{player_id}")
                    changes.append({
                        "type": "prophet_retreat",
                        "player_id": player_id,
                        "player_name": player_name,
                        "description": f"{player_name}起跳预言家后退水 → 大概率不是预言家(除非滴滴代跳)",
                        "confidence": 0.8,
                        "prophet_prob_adjustment": -0.3
                    })
                    jumped_prophet = False

                # 跳预言家后又跳别的身份
                elif jumped_prophet and prophet_jump_round == action.round_number:
                    match = re.search(r'跳(.+)', action_name)
                    if match and "预言家" not in match.group(1):
                        other_identity = match.group(1).strip()
                        if is_god_identity(other_identity):
                            player_name = self.player_name_map.get(player_id, f"玩家{player_id}")
                            changes.append({
                                "type": "identity_switch",
                                "player_id": player_id,
                                "player_name": player_name,
                                "description": f"{player_name}先跳预言家又跳{other_identity} → 大概率不是预言家",
                                "confidence": 0.75,
                                "prophet_prob_adjustment": -0.25
                            })

        return changes

    def get_prophet_prob_adjustments(self) -> Dict[int, float]:
        """获取预言家概率调整"""
        adjustments = {}
        changes = self.detect_behavior_changes()
        for change in changes:
            if "prophet_prob_adjustment" in change:
                adjustments[change["player_id"]] = change["prophet_prob_adjustment"]
        return adjustments


# ==================== 第二阶段：进阶逻辑 ====================

class InconsistencyLogic:
    """言行不一检测：死踩但没投、归票但没投"""

    def __init__(self, db: Session, game_id: int):
        self.db = db
        self.game_id = game_id
        self.player_name_map = get_player_name_map(db)
        self.action_type_map = get_action_type_map(db)
        self.actions = get_game_actions(db, game_id)

    def detect_inconsistencies(self) -> List[Dict]:
        """检测言行不一"""
        inconsistencies = []

        # 按轮次分组行为
        round_actions = defaultdict(list)
        for action in self.actions:
            round_actions[action.round_number or 0].append(action)

        for round_num, actions in round_actions.items():
            # 找出这一轮踩人的行为和投票行为
            attack_actions = []
            vote_actions = []

            for action in actions:
                action_type = self.action_type_map.get(action.action_type_id)
                if not action_type:
                    continue
                action_name = action_type.name

                if "踩" in action_name and action.target_player_id:
                    attack_actions.append(action)
                elif "投放逐票" in action_name or "投警徽票" in action_name:
                    vote_actions.append(action)

            # 检查每个踩人的玩家最后投了谁
            for attack in attack_actions:
                attacker_id = attack.player_id
                attacked_target = attack.target_player_id

                # 找该玩家这一轮的投票
                player_votes = [v for v in vote_actions if v.player_id == attacker_id]

                for vote in player_votes:
                    vote_target = vote.target_player_id

                    # 如果死踩A但最后没投A，投了别人 → 言行不一
                    if vote_target and vote_target != attacked_target:
                        attacker_name = self.player_name_map.get(attacker_id, f"玩家{attacker_id}")
                        attacked_name = self.player_name_map.get(attacked_target, f"玩家{attacked_target}")
                        voted_name = self.player_name_map.get(vote_target, f"玩家{vote_target}")

                        inconsistencies.append({
                            "type": "word_deed_inconsistency",
                            "player_id": attacker_id,
                            "player_name": attacker_name,
                            "round": round_num,
                            "description": f"{attacker_name}第{round_num}轮死踩{attacked_name}，但最后投了{voted_name} → 言行不一，大概率是狼",
                            "confidence": 0.65,
                            "wolf_prob_adjustment": 0.15
                        })

        return inconsistencies

    def get_wolf_prob_adjustments(self) -> Dict[int, float]:
        """获取狼人概率调整"""
        adjustments = defaultdict(float)
        inconsistencies = self.detect_inconsistencies()
        for inc in inconsistencies:
            adjustments[inc["player_id"]] += inc.get("wolf_prob_adjustment", 0.1)
        return dict(adjustments)


class BilateralAnalysis:
    """双边分析+公共狼：分别假设两个预言家，推狼坑，找交集"""

    def __init__(self, db: Session, game_id: int):
        self.db = db
        self.game_id = game_id
        self.player_name_map = get_player_name_map(db)
        self.identity_name_map = get_identity_name_map(db)
        self.action_type_map = get_action_type_map(db)
        self.actions = get_game_actions(db, game_id)
        self.deterministic = DeterministicLogic(db, game_id)

    def get_prophet_candidates(self) -> List[Dict]:
        """获取预言家候选人"""
        return self.deterministic.get_prophet_claims()

    def analyze_from_prophet_perspective(self, prophet_id: int) -> Dict:
        """从某个预言家的视角分析狼坑"""
        prophets = self.get_prophet_candidates()
        prophet = next((p for p in prophets if p["prophet_id"] == prophet_id), None)

        if not prophet:
            return {"wolf_pit": [], "good_list": [], "wolf_count": 0}

        wolf_pit = set()
        good_list = set()

        # 预言家的查验
        for check in prophet["checks"]:
            if check["is_gold"]:
                good_list.add(check["target_id"])
            else:
                wolf_pit.add(check["target_id"])

        # 对跳预言家的人大概率是狼
        for other in prophets:
            if other["prophet_id"] != prophet_id:
                wolf_pit.add(other["prophet_id"])

        # 站边对跳预言家的人嫌疑增加
        for action in self.actions:
            action_type = self.action_type_map.get(action.action_type_id)
            if not action_type:
                continue
            action_name = action_type.name

            if "站边" in action_name and action.target_player_id:
                # 如果站边的是对跳预言家
                for other in prophets:
                    if other["prophet_id"] != prophet_id and action.target_player_id == other["prophet_id"]:
                        wolf_pit.add(action.player_id)

        # 排除确定的好人
        determined_good = self.deterministic.get_determined_good()
        for gid in determined_good:
            good_list.add(gid)
            wolf_pit.discard(gid)

        # 排除预言家自己
        good_list.add(prophet_id)
        wolf_pit.discard(prophet_id)

        return {
            "prophet_id": prophet_id,
            "prophet_name": self.player_name_map.get(prophet_id, f"玩家{prophet_id}"),
            "wolf_pit": list(wolf_pit),
            "wolf_pit_names": [self.player_name_map.get(pid, f"玩家{pid}") for pid in wolf_pit],
            "good_list": list(good_list),
            "good_names": [self.player_name_map.get(pid, f"玩家{pid}") for pid in good_list],
            "wolf_count": len(wolf_pit)
        }

    def find_common_wolves(self) -> List[Dict]:
        """找公共狼（所有视角都认为是狼的）"""
        prophets = self.get_prophet_candidates()
        if len(prophets) < 2:
            return []

        all_perspectives = []
        for prophet in prophets:
            perspective = self.analyze_from_prophet_perspective(prophet["prophet_id"])
            all_perspectives.append(perspective)

        # 找所有视角的交集
        if not all_perspectives:
            return []

        common_wolf_ids = set(all_perspectives[0]["wolf_pit"])
        for p in all_perspectives[1:]:
            common_wolf_ids &= set(p["wolf_pit"])

        common_wolves = []
        for wolf_id in common_wolf_ids:
            common_wolves.append({
                "player_id": wolf_id,
                "player_name": self.player_name_map.get(wolf_id, f"玩家{wolf_id}"),
                "description": f"{self.player_name_map.get(wolf_id, f'玩家{wolf_id}')}是所有预言家视角的公共狼 → 极大概率是狼(80%以上)",
                "confidence": 0.85,
                "wolf_prob_adjustment": 0.3
            })

        return common_wolves

    def check_wolf_pit_sufficiency(self) -> List[Dict]:
        """检查狼坑是否够（某边狼坑凑不够→预言家概率降低）"""
        prophets = self.get_prophet_candidates()
        if len(prophets) < 2:
            return []

        # 获取对局总狼数
        game = self.db.query(Game).filter(Game.id == self.game_id).first()
        total_wolves = 4  # 默认4狼
        if game and game.setup_id:
            setup_identities = self.db.query(SetupIdentity).filter(
                SetupIdentity.setup_id == game.setup_id
            ).all()
            for si in setup_identities:
                identity_name = self.identity_name_map.get(si.identity_id, "")
                if is_wolf_identity(identity_name):
                    total_wolves = si.count
                    break

        results = []
        for prophet in prophets:
            perspective = self.analyze_from_prophet_perspective(prophet["prophet_id"])
            wolf_count = perspective["wolf_count"]

            if wolf_count < total_wolves:
                prophet_name = perspective["prophet_name"]
                results.append({
                    "type": "wolf_pit_insufficient",
                    "prophet_id": prophet["prophet_id"],
                    "prophet_name": prophet_name,
                    "wolf_count": wolf_count,
                    "total_wolves": total_wolves,
                    "description": f"从{prophet_name}视角只能找到{wolf_count}只狼，不够{total_wolves}只 → {prophet_name}大概率不是真预言家（需考虑倒钩狼）",
                    "confidence": 0.6,
                    "prophet_prob_adjustment": -0.2
                })

        return results


class ContrarianProtectLogic:
    """逆势保人逻辑：全场踩唯独保，最终是好人→保人者嫌疑降低"""

    def __init__(self, db: Session, game_id: int):
        self.db = db
        self.game_id = game_id
        self.player_name_map = get_player_name_map(db)
        self.action_type_map = get_action_type_map(db)
        self.actions = get_game_actions(db, game_id)
        self.deterministic = DeterministicLogic(db, game_id)

    def detect_contrarian_protects(self) -> List[Dict]:
        """检测逆势保人"""
        results = []

        # 统计每个玩家被多少人踩、多少人保
        attack_count = defaultdict(int)
        protect_count = defaultdict(int)
        protecters = defaultdict(list)

        for action in self.actions:
            action_type = self.action_type_map.get(action.action_type_id)
            if not action_type or not action.target_player_id:
                continue
            action_name = action_type.name

            if "踩" in action_name:
                attack_count[action.target_player_id] += 1
            elif "保" in action_name:
                protect_count[action.target_player_id] += 1
                protecters[action.target_player_id].append(action.player_id)

        # 找被很多人踩但被少数人保的玩家
        determined_good = self.deterministic.get_determined_good()
        determined_wolves = self.deterministic.get_determined_wolves()

        for target_id, attack_num in attack_count.items():
            if attack_num >= 3:  # 至少3人踩
                protect_num = protect_count.get(target_id, 0)
                if protect_num <= 2:  # 最多2人保
                    # 如果最终确定是好人
                    if target_id in determined_good:
                        target_name = self.player_name_map.get(target_id, f"玩家{target_id}")
                        for protector_id in protecters.get(target_id, []):
                            protector_name = self.player_name_map.get(protector_id, f"玩家{protector_id}")
                            results.append({
                                "type": "contrarian_protect",
                                "protector_id": protector_id,
                                "protector_name": protector_name,
                                "target_id": target_id,
                                "target_name": target_name,
                                "description": f"全场{attack_num}人踩{target_name}(最终是好人)，唯独{protector_name}保了他 → {protector_name}大概率是好人",
                                "confidence": 0.7,
                                "good_prob_adjustment": 0.2
                            })

        return results

    def get_good_prob_adjustments(self) -> Dict[int, float]:
        """获取好人概率调整"""
        adjustments = defaultdict(float)
        protects = self.detect_contrarian_protects()
        for p in protects:
            adjustments[p["protector_id"]] += p.get("good_prob_adjustment", 0.15)
        return dict(adjustments)


# ==================== 第三阶段：高级逻辑 ====================

class BenefitLogic:
    """收益逻辑：事件发生后谁是受益者"""

    def __init__(self, db: Session, game_id: int):
        self.db = db
        self.game_id = game_id
        self.player_name_map = get_player_name_map(db)
        self.action_type_map = get_action_type_map(db)
        self.actions = get_game_actions(db, game_id)
        self.deterministic = DeterministicLogic(db, game_id)

    def analyze_benefit(self) -> List[Dict]:
        """分析收益逻辑"""
        results = []

        # 找自爆行为，分析谁是受益者
        explode_action_ids = [
            at.id for at in self.action_type_map.values()
            if "自爆" in at.name
        ]

        for action in self.actions:
            if action.action_type_id in explode_action_ids:
                exploder_id = action.player_id
                exploder_name = self.player_name_map.get(exploder_id, f"玩家{exploder_id}")

                # 找自爆前的查验信息，看谁是受益者
                prophets = self.deterministic.get_prophet_claims()
                for prophet in prophets:
                    for check in prophet["checks"]:
                        if check["target_id"] == exploder_id and not check["is_gold"]:
                            # 自爆的人被某个预言家查杀，受益者是另一个预言家
                            for other in prophets:
                                if other["prophet_id"] != prophet["prophet_id"]:
                                    other_name = self.player_name_map.get(other["prophet_id"], f"玩家{other['prophet_id']}")
                                    results.append({
                                        "type": "benefit_analysis",
                                        "player_id": other["prophet_id"],
                                        "player_name": other_name,
                                        "description": f"{exploder_name}自爆(被{prophet['prophet_name']}查杀)，唯一受益者是{other_name} → {other_name}大概率是狼(狼查杀狼)",
                                        "confidence": 0.75,
                                        "wolf_prob_adjustment": 0.25
                                    })

        return results

    def get_wolf_prob_adjustments(self) -> Dict[int, float]:
        """获取狼人概率调整"""
        adjustments = defaultdict(float)
        benefits = self.analyze_benefit()
        for b in benefits:
            adjustments[b["player_id"]] += b.get("wolf_prob_adjustment", 0.2)
        return dict(adjustments)


class ProtectAttackContradiction:
    """保打关系矛盾检测"""

    def __init__(self, db: Session, game_id: int):
        self.db = db
        self.game_id = game_id
        self.player_name_map = get_player_name_map(db)
        self.action_type_map = get_action_type_map(db)
        self.actions = get_game_actions(db, game_id)

    def detect_contradictions(self) -> List[Dict]:
        """检测保打关系矛盾"""
        results = []

        # 按玩家分组行为
        player_actions = defaultdict(list)
        for action in self.actions:
            player_actions[action.player_id].append(action)

        # 找A保B打C的模式
        for player_id, actions in player_actions.items():
            protected = set()
            attacked = set()

            for action in actions:
                action_type = self.action_type_map.get(action.action_type_id)
                if not action_type or not action.target_player_id:
                    continue
                action_name = action_type.name

                if "保" in action_name:
                    protected.add(action.target_player_id)
                elif "踩" in action_name:
                    attacked.add(action.target_player_id)

            # 找D说B是狼、A是好人的矛盾
            for other_id, other_actions in player_actions.items():
                if other_id == player_id:
                    continue

                other_says_wolf = set()
                other_says_good = set()

                for action in other_actions:
                    action_type = self.action_type_map.get(action.action_type_id)
                    if not action_type or not action.target_player_id:
                        continue
                    action_name = action_type.name

                    if "踩" in action_name or "查杀" in action_name:
                        other_says_wolf.add(action.target_player_id)
                    elif "保" in action_name or "金水" in action_name:
                        other_says_good.add(action.target_player_id)

                # 检查矛盾：A保了B(D认为是狼)，但D说A是好人
                for b_id in protected:
                    if b_id in other_says_wolf and player_id in other_says_good:
                        a_name = self.player_name_map.get(player_id, f"玩家{player_id}")
                        b_name = self.player_name_map.get(b_id, f"玩家{b_id}")
                        d_name = self.player_name_map.get(other_id, f"玩家{other_id}")

                        results.append({
                            "type": "protect_attack_contradiction",
                            "player_id": other_id,
                            "player_name": d_name,
                            "description": f"{a_name}保了{d_name}认为是狼的{b_name}，但{d_name}却说{a_name}是好人 → 矛盾，{d_name}大概率是狼",
                            "confidence": 0.6,
                            "wolf_prob_adjustment": 0.15
                        })

        return results

    def get_wolf_prob_adjustments(self) -> Dict[int, float]:
        """获取狼人概率调整"""
        adjustments = defaultdict(float)
        contradictions = self.detect_contradictions()
        for c in contradictions:
            adjustments[c["player_id"]] += c.get("wolf_prob_adjustment", 0.1)
        return dict(adjustments)


# ==================== 综合逻辑引擎 ====================

class ComprehensiveLogicEngine:
    """综合逻辑引擎：整合所有逻辑模块"""

    def __init__(self, db: Session, game_id: int):
        self.db = db
        self.game_id = game_id
        self.player_name_map = get_player_name_map(db)
        self.identity_name_map = get_identity_name_map(db)

        # 初始化所有逻辑模块
        self.deterministic = DeterministicLogic(db, game_id)
        self.identity_uniqueness = IdentityUniquenessLogic(db, game_id)
        self.behavior_sequence = BehaviorSequenceLogic(db, game_id)
        self.inconsistency = InconsistencyLogic(db, game_id)
        self.bilateral = BilateralAnalysis(db, game_id)
        self.contrarian = ContrarianProtectLogic(db, game_id)
        self.benefit = BenefitLogic(db, game_id)
        self.protect_attack = ProtectAttackContradiction(db, game_id)

    def run_full_analysis(self) -> Dict:
        """运行完整分析"""
        results = {
            "game_id": self.game_id,
            "determined_facts": [],
            "derived_facts": [],
            "contradictions": [],
            "warnings": [],
            "wolf_prob_adjustments": defaultdict(float),
            "good_prob_adjustments": defaultdict(float),
            "prophet_prob_adjustments": defaultdict(float),
            "prophet_analysis": None,
            "bilateral_analysis": [],
            "common_wolves": []
        }

        # 1. 确定性逻辑
        self_explodes = self.deterministic.detect_self_explode()
        wolf_claims = self.deterministic.detect_wolf_claim()
        check_analysis = self.deterministic.analyze_check_chain()

        results["determined_facts"].extend(self_explodes)
        results["determined_facts"].extend(wolf_claims)
        results["derived_facts"].extend(check_analysis["derived_facts"])
        results["contradictions"].extend(check_analysis["contradictions"])
        results["prophet_analysis"] = check_analysis

        # 2. 身份唯一性逻辑
        identity_conflicts = self.identity_uniqueness.detect_identity_conflicts()
        results["warnings"].extend(identity_conflicts)
        for pid, adj in self.identity_uniqueness.get_conflict_suspicion_adjustments().items():
            results["wolf_prob_adjustments"][pid] += adj

        # 3. 行为顺序逻辑
        behavior_changes = self.behavior_sequence.detect_behavior_changes()
        results["warnings"].extend(behavior_changes)
        for pid, adj in self.behavior_sequence.get_prophet_prob_adjustments().items():
            results["prophet_prob_adjustments"][pid] += adj

        # 4. 言行不一检测
        inconsistencies = self.inconsistency.detect_inconsistencies()
        results["warnings"].extend(inconsistencies)
        for pid, adj in self.inconsistency.get_wolf_prob_adjustments().items():
            results["wolf_prob_adjustments"][pid] += adj

        # 5. 双边分析
        prophets = self.bilateral.get_prophet_candidates()
        for prophet in prophets:
            perspective = self.bilateral.analyze_from_prophet_perspective(prophet["prophet_id"])
            results["bilateral_analysis"].append(perspective)

        common_wolves = self.bilateral.find_common_wolves()
        results["common_wolves"] = common_wolves
        for cw in common_wolves:
            results["wolf_prob_adjustments"][cw["player_id"]] += cw.get("wolf_prob_adjustment", 0.2)

        wolf_pit_checks = self.bilateral.check_wolf_pit_sufficiency()
        results["warnings"].extend(wolf_pit_checks)
        for wpc in wolf_pit_checks:
            results["prophet_prob_adjustments"][wpc["prophet_id"]] += wpc.get("prophet_prob_adjustment", -0.15)

        # 6. 逆势保人
        contrarian_protects = self.contrarian.detect_contrarian_protects()
        results["derived_facts"].extend(contrarian_protects)
        for pid, adj in self.contrarian.get_good_prob_adjustments().items():
            results["good_prob_adjustments"][pid] += adj

        # 7. 收益逻辑
        benefit_analysis = self.benefit.analyze_benefit()
        results["derived_facts"].extend(benefit_analysis)
        for pid, adj in self.benefit.get_wolf_prob_adjustments().items():
            results["wolf_prob_adjustments"][pid] += adj

        # 8. 保打关系矛盾
        pa_contradictions = self.protect_attack.detect_contradictions()
        results["contradictions"].extend(pa_contradictions)
        for pid, adj in self.protect_attack.get_wolf_prob_adjustments().items():
            results["wolf_prob_adjustments"][pid] += adj

        # 转换为普通字典
        results["wolf_prob_adjustments"] = dict(results["wolf_prob_adjustments"])
        results["good_prob_adjustments"] = dict(results["good_prob_adjustments"])
        results["prophet_prob_adjustments"] = dict(results["prophet_prob_adjustments"])

        return results

    def get_determined_wolves(self) -> List[int]:
        """获取确定的狼人列表"""
        return self.deterministic.get_determined_wolves()

    def get_determined_good(self) -> List[int]:
        """获取确定的好人列表"""
        return self.deterministic.get_determined_good()
