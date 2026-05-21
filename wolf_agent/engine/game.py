"""Wolf Agent v1 game engine — LangGraph state machine."""

from __future__ import annotations

import json
import os
import random
import time
import uuid
from typing import Any, Optional

from langgraph.graph import StateGraph, END

from wolf_agent.events import EventLog
from wolf_agent.agents import LLMClient, Agent, MBTI_LIST

# --- Constants ---
PLAYER_COUNT = 9
ROLE_DISTRIBUTION = ["werewolf"] * 3 + ["seer"] + ["witch"] + ["villager"] * 4

NIGHT_ORDER = ["werewolf_kill", "seer_investigate", "witch_act"]
MAX_SPEECH_PER_ROUND = 3
MAX_SPEECH_CHARS = 200
DEBATE_ROUNDS = 2

GAMES_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "games")
os.makedirs(GAMES_DIR, exist_ok=True)


# --- State ---
class GameState(dict):
    """Mutable game state dict for LangGraph."""
    __slots__ = ()  # Don't add __dict__, keep it a plain dict subclass

    @property
    def alive_set(self) -> set[int]:
        return set(self.get("alive", []))

    @property
    def wolves(self) -> set[int]:
        return set(self.get("_wolves", []))

    @property
    def seer_id(self) -> int | None:
        return self.get("_seer_id")

    @property
    def witch_id(self) -> int | None:
        return self.get("_witch_id")


def default_state(seed: int) -> dict:
    return {
        "phase": "INIT",
        "game_id": "",
        "seed": seed,
        "round_num": 0,
        "players": [],
        "alive": [],
        "_wolves": [],
        "_seer_id": None,
        "_witch_id": None,
        "roles": {},  # player_id -> role
        "public_messages": [],
        "wolf_den_messages": [],
        "votes": {},
        "eliminated_today": None,
        "night_kill_target": None,
        "night_kill_initiator": None,
        "seer_target": None,
        "seer_result": None,
        "witch_antidote_used": False,
        "witch_poison_used": False,
        "witch_poison_target": None,
        "speech_count": {},
        "debate_round": 0,
        "winner": None,
        "event_log_path": "",
        "last_death": None,
        "executed_today": None,
        "last_will": None,
        "first_night": True,
    }


# --- Helper functions ---

def _pick_mbti(rng: random.Random, used_mbti: list[str]) -> str:
    available = [m for m in MBTI_LIST if m not in used_mbti]
    if not available:
        available = MBTI_LIST[:]
    chosen = rng.choice(available)
    return chosen


def _log_phase(evtlog: EventLog, phase: str, round_num: int):
    evtlog.append(
        type="phase_started",
        channel="system",
        visibility="public",
        metadata={"phase": phase, "round": round_num},
    )


def _check_winner_condition(state: dict) -> str | None:
    alive = set(state["alive"])
    wolves = set(state["_wolves"]) & alive  # only alive wolves count
    non_wolves = alive - wolves

    # Wolf win: wolves >= non-wolves (dead wolves excluded from count)
    if wolves and len(wolves) >= len(non_wolves):
        return "werewolf"

    # Villager win: all wolves eliminated
    if not wolves:
        return "villager"

    return None


def _dump_summary(state: dict):
    path = state["event_log_path"].replace(".events.jsonl", ".summary.json")
    summary = {
        "game_id": state["game_id"],
        "seed": state["seed"],
        "winner": state["winner"],
        "rounds": state["round_num"],
        "roles": {str(k): v for k, v in state["roles"].items()},
        "players": [
            {"id": p["id"], "mbti": p["mbti"], "role": p["role"], "alive": p["id"] in state["alive"]}
            for p in state["players"]
        ],
    }
    with open(path, "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)


# --- Graph Nodes ---

def init_game(state: dict) -> dict:
    rng = random.Random(state["seed"])
    game_id = f"wolf-v1-{rng.getrandbits(32):08x}"
    evtlog_path = os.path.join(GAMES_DIR, f"{game_id}.events.jsonl")

    # Remove stale log from previous run (same seed → same game_id)
    if os.path.exists(evtlog_path):
        os.remove(evtlog_path)
    summary_path = evtlog_path.replace(".events.jsonl", ".summary.json")
    if os.path.exists(summary_path):
        os.remove(summary_path)

    players = []
    used_mbti = []
    for pid in range(1, PLAYER_COUNT + 1):
        mbti = _pick_mbti(rng, used_mbti)
        used_mbti.append(mbti)
        players.append({"id": pid, "mbti": mbti, "role": "", "alive": True})

    updates = dict(state)
    updates["game_id"] = game_id
    updates["players"] = players
    updates["alive"] = [p["id"] for p in players]
    updates["event_log_path"] = evtlog_path
    return updates


def assign_roles(state: dict) -> dict:
    rng = random.Random(state["seed"] + 1)
    player_ids = [p["id"] for p in state["players"]]
    roles = list(ROLE_DISTRIBUTION)
    rng.shuffle(roles)

    # Open event log
    evtlog = EventLog(state["game_id"], state["event_log_path"])
    evtlog.append(type="game_started", channel="system", visibility="public",
                  metadata={"seed": state["seed"], "player_count": PLAYER_COUNT})

    assignments = {}
    wolves = []
    seer_id = None
    witch_id = None
    for pid, role in zip(player_ids, roles):
        assignments[pid] = role
        if role == "werewolf":
            wolves.append(pid)
        elif role == "seer":
            seer_id = pid
        elif role == "witch":
            witch_id = pid

        evtlog.append(
            type="role_assigned",
            channel="system",
            visibility=f"role_private:{pid}",
            from_player=pid,
            metadata={"role": role},
        )

    # Update player roles
    players = list(state["players"])
    for p in players:
        p["role"] = assignments[p["id"]]

    evtlog.close()

    updates = dict(state)
    updates["phase"] = "ASSIGN_ROLES"
    updates["players"] = players
    updates["roles"] = assignments
    updates["_wolves"] = wolves
    updates["_seer_id"] = seer_id
    updates["_witch_id"] = witch_id
    return updates


def night_phase(state: dict) -> dict:
    rng = random.Random(state["seed"] + state["round_num"] * 10 + 2)
    evtlog = EventLog(state["game_id"], state["event_log_path"])
    llm = LLMClient()

    updates = dict(state)
    updates["round_num"] = state["round_num"] + 1
    updates["phase"] = "NIGHT"
    _log_phase(evtlog, "NIGHT", updates["round_num"])
    evtlog.close()

    print(f"  {'='*35}\n  【第 {updates['round_num']} 轮 夜晚】\n  {'='*35}")

    # Build agents for night actions
    agents = {}
    for p in state["players"]:
        if p["id"] in state["alive"]:
            agents[p["id"]] = Agent(p["id"], p["role"], p["mbti"], llm)

    # Build context
    context_parts = [f"第 {updates['round_num']} 轮夜晚"]
    alive_names = ", ".join(f"{pid}号" for pid in state["alive"])
    context_parts.append(f"存活: {alive_names}")
    if state["public_messages"]:
        recent = state["public_messages"][-6:]
        context_parts.append("白天发言摘要:")
        for m in recent:
            context_parts.append(f"  {m['from']}号: {m['content'][:80]}")
    context = "\n".join(context_parts)

    # --- Wolf kill ---
    alive_wolves = [w for w in state["_wolves"] if w in state["alive"]]
    non_wolves = [p for p in state["alive"] if p not in state["_wolves"]]
    kill_target = None
    kill_initiator = None

    evtlog = EventLog(state["game_id"], state["event_log_path"])
    _log_phase(evtlog, "WOLF_DEN", updates["round_num"])

    if alive_wolves:
        print(f"  狼人({', '.join(f'{w}号' for w in alive_wolves)}) 商议中...")

        # Wolf den discussion
        if len(alive_wolves) > 1:
            for wid in alive_wolves:
                agent = agents[wid]
                packmates = [w for w in alive_wolves if w != wid]
                speech = agent.wolf_discuss(context, packmates)
                evtlog.append(
                    type="message_posted", channel="wolf_den", visibility="wolf_den",
                    from_player=wid, content=speech,
                    strategy_summary="与狼队友商议击杀目标",
                )

        # Kill vote among wolves
        wolf_votes = {}
        for wid in alive_wolves:
            agent = agents[wid]
            target = agent.night_kill(context, non_wolves)
            wolf_votes[wid] = target

        if wolf_votes:
            # Most votes wins; tie = rng
            from collections import Counter
            cnt = Counter(wolf_votes.values())
            max_votes = cnt.most_common(1)[0][1]
            top_targets = [t for t, c in cnt.items() if c == max_votes]
            kill_target = rng.choice(top_targets)
            kill_initiator = wid  # last voter as initiator

    if kill_target:
        print(f"  → 狼人决定杀死 {kill_target} 号")
        evtlog.append(
            type="action_submitted", channel="wolf_den", visibility="wolf_den",
            from_player=kill_initiator,
            metadata={"action": "kill", "target": kill_target},
        )

    updates["night_kill_target"] = kill_target

    # --- Seer investigate ---
    seer = state["_seer_id"]
    if seer and seer in state["alive"]:
        agent = agents[seer]
        seer_targets = [p for p in state["alive"] if p != seer]
        print(f"  预言家查验中...", end=" ")
        target = agent.night_investigate(context, seer_targets)
        is_wolf = target in state["_wolves"]
        print(f"{target} 号是{'狼人' if is_wolf else '好人'}")
        updates["seer_target"] = target
        updates["seer_result"] = is_wolf

        evtlog.append(
            type="action_submitted", channel="seer_vision", visibility=f"role_private:{seer}",
            from_player=seer,
            metadata={"action": "investigate", "target": target, "is_wolf": is_wolf},
        )
        evtlog.append(
            type="message_posted", channel="seer_vision", visibility=f"role_private:{seer}",
            from_player=seer,
            content=f"你查验了 {target} 号，身份是{'狼人' if is_wolf else '好人'}。",
        )
    else:
        updates["seer_target"] = None
        updates["seer_result"] = None

    # --- Witch act ---
    witch = state["_witch_id"]
    antidote_used = state["witch_antidote_used"]
    poison_used = state["witch_poison_used"]

    if witch and witch in state["alive"] and kill_target:
        agent = agents[witch]
        is_first_night = state.get("first_night", True)
        can_save = not antidote_used
        can_poison = not poison_used

        print(f"  女巫思考中...")
        witch_decision = agent.witch_act(context, kill_target, can_save, can_poison)
        use_antidote = witch_decision.get("use_antidote", False)
        poison_target = witch_decision.get("poison_target")

        if use_antidote and can_save:
            updates["witch_antidote_used"] = True
            updates["night_kill_target"] = None  # Saved!
            evtlog.append(
                type="action_submitted", channel="witch_chamber", visibility=f"role_private:{witch}",
                from_player=witch,
                metadata={"action": "use_antidote", "target": kill_target},
            )
        else:
            updates["witch_antidote_used"] = antidote_used

        if poison_target and can_poison and poison_target != kill_target:
            updates["witch_poison_used"] = True
            updates["witch_poison_target"] = poison_target
            evtlog.append(
                type="action_submitted", channel="witch_chamber", visibility=f"role_private:{witch}",
                from_player=witch,
                metadata={"action": "use_poison", "target": poison_target},
            )

    updates["first_night"] = False

    # --- Night resolve ---
    deaths = []
    if updates.get("night_kill_target"):
        deaths.append(updates["night_kill_target"])
    if updates.get("witch_poison_target"):
        deaths.append(updates["witch_poison_target"])

    # Apply deaths (but don't mark eliminated yet for last-will purposes)
    alive = list(state["alive"])
    death_msg_parts = []

    for died in deaths:
        if died in alive:
            alive.remove(died)
            role = state["roles"].get(died, "unknown")
            death_msg_parts.append(f"{died}号")
            evtlog.append(
                type="player_eliminated", channel="system", visibility="public",
                from_player=died,
                metadata={"cause": "night_kill", "role": role},
            )

    # Last will for first-night kill (has last will)
    for died in deaths:
        if died == state.get("night_kill_target") and state.get("first_night"):
            player_info = next((p for p in state["players"] if p["id"] == died), None)
            if player_info:
                death_agent = Agent(died, player_info["role"], player_info["mbti"], llm)
                will_context = f"你是 {died} 号，身份为【{player_info['role']}】。你被杀了。留下遗言（≤100字）。"
                will, _ = death_agent.speak([{"role": "system", "content": death_agent.system_prompt},
                                              {"role": "user", "content": will_context}])
                updates["last_will"] = will
                evtlog.append(
                    type="message_posted", channel="last_will", visibility="public",
                    from_player=died, content=will,
                    strategy_summary="遗言",
                )

    death_msg = ", ".join(death_msg_parts) if death_msg_parts else "无人死亡"
    print(f"  ☀ 天亮了：{death_msg}")
    updates["alive"] = alive
    updates["last_death"] = death_msg

    evtlog.append(
        type="phase_resolved", channel="system", visibility="public",
        metadata={"phase": "NIGHT", "deaths": deaths},
    )
    evtlog.close()

    return updates


def day_phase(state: dict) -> dict:
    evtlog = EventLog(state["game_id"], state["event_log_path"])
    llm = LLMClient()

    updates = dict(state)
    updates["phase"] = "DAY"
    updates["speech_count"] = {}
    updates["debate_round"] = 0
    _log_phase(evtlog, "DAY", state["round_num"])

    print(f"\n  【第 {state['round_num']} 轮 白天】")
    print(f"  存活: {', '.join(f'{p}号' for p in sorted(state['alive']))}")

    evtlog.append(
        type="message_posted", channel="announcement", visibility="public",
        content=f"昨晚 {state['last_death']} 死亡。",
    )

    # Build agents
    agents = {}
    for p in state["players"]:
        if p["id"] in state["alive"]:
            agents[p["id"]] = Agent(p["id"], p["role"], p["mbti"], llm)

    all_messages = list(state["public_messages"])

    # Ordered speech (each alive player speaks up to MAX_SPEECH_PER_ROUND times)
    alive_order = sorted(state["alive"])
    speech_count = {}

    for _round in range(MAX_SPEECH_PER_ROUND):
        for pid in alive_order:
            agent = agents[pid]
            count = speech_count.get(pid, 0)
            if count >= MAX_SPEECH_PER_ROUND:
                continue

            context = _build_day_context(state, all_messages, pid)
            content, strategy = agent.speak(context)
            if not content:
                continue

            speech_count[pid] = count + 1
            msg_entry = {"from": pid, "content": content}
            all_messages.append(msg_entry)

            print(f"  [{pid}号] {content[:80]}")
            evtlog.append(
                type="message_posted", channel="public_board", visibility="public",
                from_player=pid, content=content,
                strategy_summary=strategy or None,
            )

    # Debate rounds
    for d_round in range(DEBATE_ROUNDS):
        updates["debate_round"] = d_round + 1
        for pid in alive_order:
            agent = agents[pid]
            context = _build_day_context(state, all_messages, pid)
            context += "\n\n现在是自由辩论时间。"
            content, strategy = agent.speak(context)
            if not content:
                continue

            msg_entry = {"from": pid, "content": content}
            all_messages.append(msg_entry)

            print(f"  [{pid}号·辩论] {content[:80]}")
            evtlog.append(
                type="message_posted", channel="public_board", visibility="public",
                from_player=pid, content=content,
                strategy_summary=strategy or None,
            )

    updates["public_messages"] = all_messages
    updates["speech_count"] = speech_count

    evtlog.close()
    return updates


def vote_phase(state: dict) -> dict:
    evtlog = EventLog(state["game_id"], state["event_log_path"])
    llm = LLMClient()

    updates = dict(state)
    updates["phase"] = "VOTE"
    _log_phase(evtlog, "VOTE", state["round_num"])

    print(f"\n  【投票】")

    # First round vote
    votes, eliminated = _run_vote(state, llm, evtlog)

    # Handle tie: re-vote once
    tie = eliminated is None
    if tie:
        evtlog.append(
            type="vote_resolved", channel="system", visibility="public",
            metadata={"tie": True, "revote": True},
        )
        votes, eliminated = _run_vote(state, llm, evtlog, revote=True)

    evtlog.append(
        type="vote_resolved", channel="system", visibility="public",
        metadata={"tie": False, "eliminated": eliminated},
    )

    updates["votes"] = votes
    updates["eliminated_today"] = eliminated

    evtlog.close()
    return updates


def _run_vote(state: dict, llm: LLMClient, evtlog: EventLog, revote: bool = False) -> tuple[dict, int | None]:
    alive = sorted(state["alive"])
    votes = {}

    agents = {}
    for p in state["players"]:
        if p["id"] in state["alive"]:
            agents[p["id"]] = Agent(p["id"], p["role"], p["mbti"], llm)

    context_parts = [f"第 {state['round_num']} 轮白天投票"]
    if state["public_messages"]:
        recent = state["public_messages"][-8:]
        context_parts.append("最近发言:")
        for m in recent:
            context_parts.append(f"  {m['from']}号: {m['content'][:100]}")
    context = "\n".join(context_parts)

    for pid in alive:
        agent = agents[pid]
        candidates = [p for p in alive if p != pid]
        target = agent.vote(context, candidates)
        if target in candidates:
            votes[pid] = target

        evtlog.append(
            type="vote_cast", channel="public_board", visibility="public",
            from_player=pid,
            metadata={"target": target},
        )

    # Count votes
    from collections import Counter
    cnt = Counter(votes.values())
    if not cnt:
        return votes, None

    max_votes = cnt.most_common(1)[0][1]
    top = [p for p, c in cnt.items() if c == max_votes]

    if len(top) > 1:
        # Tie
        return votes, None

    eliminated = top[0]
    return votes, eliminated


def execute_phase(state: dict) -> dict:
    evtlog = EventLog(state["game_id"], state["event_log_path"])
    llm = LLMClient()

    updates = dict(state)
    updates["phase"] = "EXECUTION"
    eliminated = state["eliminated_today"]

    if eliminated is None:
        print("  投票结果：平票，无人出局")
        evtlog.append(
            type="message_posted", channel="announcement", visibility="public",
            content="今天平票，无人出局。",
        )
        evtlog.close()
        return updates

    # Eliminate player
    print(f"  投票结果：{eliminated} 号被投出局")
    alive = list(state["alive"])
    if eliminated in alive:
        alive.remove(eliminated)

    role = state["roles"].get(eliminated, "unknown")
    updates["alive"] = alive
    updates["executed_today"] = eliminated

    evtlog.append(
        type="player_eliminated", channel="system", visibility="public",
        from_player=eliminated,
        metadata={"cause": "execution", "role": role},
    )

    # Last will (daytime execution gets last will)
    player_info = next((p for p in state["players"] if p["id"] == eliminated), None)
    if player_info:
        agent = Agent(eliminated, player_info["role"], player_info["mbti"], llm)
        will_context = f"你是 {eliminated} 号，身份为【{player_info['role']}】。你被投票出局。留下遗言（≤100字）。"
        will, _ = agent.speak([{"role": "system", "content": agent.system_prompt},
                                {"role": "user", "content": will_context}])
        updates["last_will"] = will
        evtlog.append(
            type="message_posted", channel="last_will", visibility="public",
            from_player=eliminated, content=will or "...",
            strategy_summary="遗言",
        )

    evtlog.close()
    return updates


def check_winner(state: dict) -> dict:
    evtlog = EventLog(state["game_id"], state["event_log_path"])
    updates = dict(state)
    updates["phase"] = "CHECK_WINNER"

    winner = _check_winner_condition(state)
    updates["winner"] = winner

    if winner:
        winner_name = "狼人" if winner == "werewolf" else "好人"
        print(f"\n  🏁 {winner_name} 获胜！（{len(state['alive'])} 人存活）")
        evtlog.append(
            type="game_ended", channel="system", visibility="public",
            metadata={"winner": winner, "winner_name": winner_name},
        )
        evtlog.append(
            type="phase_resolved", channel="system", visibility="public",
            metadata={"phase": "GAME_OVER", "winner": winner},
        )
    else:
        _log_phase(evtlog, "NIGHT_PREP", state["round_num"])

    evtlog.close()

    if winner:
        _dump_summary(updates)

    return updates


def _build_day_context(state: dict, messages: list[dict], current_pid: int) -> str:
    parts = [f"第 {state['round_num']} 轮白天"]
    alive_names = ", ".join(f"{p}号" for p in sorted(state["alive"]))
    parts.append(f"存活: {alive_names}")
    if state.get("last_death") and state["last_death"] != "无人死亡":
        parts.append(f"昨晚死亡: {state['last_death']}")

    if messages:
        recent = messages[-10:]
        parts.append("最近发言:")
        for m in recent:
            parts.append(f"  {m['from']}号: {m['content'][:120]}")

    return "\n".join(parts)


# --- Graph construction ---

def create_game(seed: int = 42) -> tuple[dict, Any]:
    """Create and run a complete game. Returns (final_state, graph)."""
    builder = StateGraph(dict)

    builder.add_node("init_game", init_game)
    builder.add_node("assign_roles", assign_roles)
    builder.add_node("night_phase", night_phase)
    builder.add_node("day_phase", day_phase)
    builder.add_node("vote_phase", vote_phase)
    builder.add_node("execute_phase", execute_phase)
    builder.add_node("check_winner", check_winner)

    builder.set_entry_point("init_game")

    # Linear flow
    builder.add_edge("init_game", "assign_roles")
    builder.add_edge("assign_roles", "night_phase")
    builder.add_edge("night_phase", "day_phase")
    builder.add_edge("day_phase", "vote_phase")
    builder.add_edge("vote_phase", "execute_phase")
    builder.add_edge("execute_phase", "check_winner")

    # Conditional: continue or end
    def decide_next(state: dict) -> str:
        if state.get("winner"):
            return "end"
        return "continue"

    builder.add_conditional_edges("check_winner", decide_next, {
        "continue": "night_phase",
        "end": END,
    })

    graph = builder.compile()
    initial = default_state(seed)
    final = graph.invoke(initial)

    return final, graph
