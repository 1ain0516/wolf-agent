"""Wolf Agent CLI — run_spectate / stats commands."""

from __future__ import annotations

import argparse
import json
import math
import os
import re
import sys
import time


class StubLLM:
    """人格感知的 mock LLM，各人格有不同发言风格和行为模式"""

    # 16 人格发言模板
    _SPEECH = {
        "BOSS": [
            "我认为局势很清楚，建议按我说的方向走。", "别浪费时间了，直接投票吧。",
            "我带队，大家跟上就行。", "分析了一圈，结论只有一个——投他。",
            "你们仔细想想，我的逻辑有没有问题？",
        ],
        "FAKE": [
            "说实话，我也不太确定谁才是狼。", "我观察了几轮，觉得情况有点复杂。",
            "如果我是狼，我没必要这么高调对吧？", "大家冷静分析，不要被情绪左右。",
            "我有一个大胆的推测，你们听听看合理不合理。",
        ],
        "THIN-K": [
            "投票数据显示 3 票指向同一人，这不合理。", "基于前两轮的行为，我有理由怀疑他。",
            "排除法和概率分析指向一个结论。", "先说事实，再谈推测。",
            "等一下，你的逻辑有个明显的漏洞。",
        ],
        "FUCK": [
            "你TM在搞笑吗？这还用分析？", "投他！这还用想？",
            "一群废物，这么明显的狼都看不出来？", "别废话了，干就完了！",
            "你们几个，能不能带点脑子？",
        ],
        "OJBK": [
            "随便吧，你们定。", "我跟票。",
            "行吧，就这么着。", "嗯，可以。",
            "无所谓，反正我都行。",
        ],
        "SHIT": [
            "呵呵，又一个骗子。", "你们每个人都在这演戏呢。",
            "投谁都差不多，反正这局已经凉了。", "我才不信你说的任何一个字。",
            "知道吗？我最烦你们这种装模作样的人。",
        ],
        "ZZZZ": [
            "过。", "没什么要说的。",
            "嗯。", "。",
            "跟着走。",
        ],
        "MALO": [
            "诶诶诶我也觉得！", "对对对，我也感觉是他！",
            "哇你说的好有道理啊！", "哈哈我觉得反正跟着大佬走就行。",
            "哎那我跟一个呗！",
        ],
        "JOKE-R": [
            "哈哈，我承认我就是狼，你信吗？", "这个问题嘛……你们猜？",
            "其实我有一说一，真的，假的。", "今天的演技可以打多少分？",
            "注意了，我要认真了——开个玩笑。",
        ],
        "LOVE-R": [
            "我相信你说的话，感觉你很真诚。", "大家不要互相猜疑了，我们要团结。",
            "我也不想投他，但实在是没办法……", "请大家相信自己的直觉。",
            "每个人都是好人，只是表达方式不一样。",
        ],
        "MUM": [
            "大家别急，慢慢分析。", "我觉得我们要照顾一下新手。",
            "听我说，不管怎样，团结最重要。", "各位注意，今天发言时间还剩不少。",
            "不要太紧张，胜负都是常事。",
        ],
        "IMSB": [
            "等等，死者到底是谁来着？", "我有点懵，现在到第几轮了？",
            "你们在说什么？能不能再讲一遍？", "啊？刚才投过了吗？",
            "我好像搞混了……谁是女巫？",
        ],
        "SOLO": [
            "我的判断是投他。理由不需要跟你们说。", "我跟你们不一样。",
            "不需要解释。这就是我的结论。", "走自己的路。",
            "投票我说了算。",
        ],
        "SEXY": [
            "嗯～我觉得你说得有道理呢～", "这个问题嘛，我们换个角度想想～",
            "别着急嘛，我们还多的是时间～", "投他的话，我会心疼的哦～",
            "哥哥姐姐们冷静一下好不好～",
        ],
        "MONK": [
            "我注意到一点细节。", "事实摆在眼前。",
            "沉默本身就是一种回答。", "我只陈述我所看到的。",
            "真相不需要修饰。",
        ],
        "DEAD": [
            "。", "。。。",
            "投。", "嗯。",
            "过。。",
        ],
    }

    def __init__(self, delay: float = 0.3):
        self.api_key = "stub"
        self.base_url = "http://stub"
        self.model = "stub"
        self._call_count = 0
        self._personalities = {}    # player_id -> personality_code
        self.delay = delay  # 每次调用延迟（秒），让实时观战可见

    def set_personalities(self, mapping: dict):
        """设置玩家 -> 人格映射"""
        self._personalities = mapping

    def _alive_from_context(self, messages: list[dict]) -> list[int]:
        for m in messages:
            if m["role"] == "user":
                for line in m["content"].split("\n"):
                    for prefix in ("存活:", "存活玩家:", "可投票对象:", "可选目标:"):
                        if prefix in line:
                            nums = re.findall(r"\d+", line)
                            return [int(n) for n in nums]
        return []

    def _player_from_context(self, messages: list[dict]) -> int:
        """提取当前玩家的 ID"""
        for m in messages:
            if m.get("role") == "system":
                for line in m.get("content", "").split("\n"):
                    nums = re.findall(r"\d+", line)
                    if nums:
                        return int(nums[0])
        return 0

    def _get_personality(self, player_id: int) -> str:
        if self._personalities:
            return self._personalities.get(str(player_id), "UNKNOWN")
        return "UNKNOWN"

    def _ensure_personalities_from_context(self, messages: list[dict]):
        """从 system prompt 中提取所有玩家的人格映射"""
        for m in messages:
            if m.get("role") == "system":
                content = m.get("content", "")
                # "你是 3 号玩家，身份为【狼人】。\n你的性格是【BOSS】（掌控者）：..."
                nums = re.findall(r"你是 (\d+) 号", content)
                pers = re.findall(r"性格是【(\w+(?:-\w+)?)】", content)
                if nums and pers:
                    pid = nums[0]
                    self._personalities[str(pid)] = pers[0]

    _LAST_WORDS = {
        "BOSS": "行吧，我认了。但记住我说的方向，别走偏了。",
        "FAKE": "呵呵，被你们发现了？不过……你们确定出对人了吗？",
        "THIN-K": "我的分析没错，只是来不及验证了。回头看看投票记录。",
        "FUCK": "操！你们这群蠢货，等着输吧！",
        "OJBK": "随便吧，反正我也没认真玩。",
        "SHIT": "呵，又一个替罪羊。这游戏真他妈可笑。",
        "ZZZZ": "……",
        "MALO": "呜呜我被冤枉啦！不过玩得挺开心的嘿嘿～",
        "JOKE-R": "谢幕表演到此结束。你们猜我到底是不是狼？",
        "LOVE-R": "没关系，我相信你们会替我报仇的。加油。",
        "MUM": "大家别自责，这就是游戏。接下来要小心。",
        "IMSB": "啊？我死了？我还没搞清楚谁是谁呢……",
        "SOLO": "无所谓。反正我也没指望过你们。",
        "SEXY": "哎呀，居然舍得杀我？你们会后悔的哦～",
        "MONK": "尘埃落定。真相自在人心。",
        "DEAD": "……",
    }

    def _delay(self):
        if self.delay > 0:
            time.sleep(self.delay)

    def speak(self, messages):
        self._delay()
        self._call_count += 1
        self._ensure_personalities_from_context(messages)
        pid = self._player_from_context(messages)
        pers = self._get_personality(pid)

        # 遗言检测
        for m in messages:
            if m.get("role") == "user":
                text = m.get("content", "")
                if "留下遗言" in text or "被杀害了" in text or "被投票出局" in text:
                    phrase = self._LAST_WORDS.get(pers, "再见。")
                    return phrase, "遗言"

        phrases = self._SPEECH.get(pers, self._SPEECH["OJBK"])
        phrase = phrases[self._call_count % len(phrases)]
        return phrase, f"{pers}风格第{self._call_count}次发言"

    def vote(self, messages):
        self._delay()
        alive = self._alive_from_context(messages)
        if not alive:
            return 1
        pid = self._player_from_context(messages)
        pers = self._get_personality(pid)
        # 排除自己
        others = [a for a in alive if a != pid]
        if not others:
            return alive[0]
        # 高投票独立性的人投自己判断的，低的人跟风
        from wolf_agent.agents.personality import PERSONALITY_TEMPLATES
        tpl = PERSONALITY_TEMPLATES.get(pers, {})
        independence = tpl.get("params", {}).get("vote_independence", 0.5)
        # 简单地用 call_count 模拟变化
        idx = (self._call_count + pid) % len(others)
        self._call_count += 1
        return others[idx]

    def act(self, messages):
        self._delay()
        alive = self._alive_from_context(messages)
        if not alive:
            return {"target": 1, "use_antidote": False, "poison_target": None}
        pid = self._player_from_context(messages)
        others = [a for a in alive if a != pid]
        if not others:
            return {"target": alive[0], "use_antidote": False, "poison_target": None}
        idx = (self._call_count + pid) % len(others)
        self._call_count += 1
        return {"target": others[idx], "use_antidote": False, "poison_target": None}

    def reflect(self, messages):
        self._delay()
        pid = self._player_from_context(messages)
        pers = self._get_personality(pid)
        reflections = {
            "BOSS": "这局我尽力带队了，结果虽然不是最好，但决策方向没错。",
            "FAKE": "每个人都在演戏，我只是演得比较真而已。",
            "THIN-K": "从数据分析来看，我的判断大部分是正确的。",
            "FUCK": "一群猪队友，带不动。",
            "OJBK": "随便吧，反正我也没怎么认真玩。",
            "SHIT": "这游戏就是骗子大集会，没一个可信的。",
            "ZZZZ": "……",
            "MALO": "哈哈哈我玩得挺开心的！虽然好像没什么用。",
            "JOKE-R": "你们分得清我哪句是真的吗？我自己也分不清。",
            "LOVE-R": "我真心相信大家，虽然可能信错了人……",
            "MUM": "大家辛苦了，胜负不重要，开心最重要。",
            "IMSB": "啊？结束了吗？我还没搞清楚谁是谁呢。",
            "SOLO": "一个人也挺好。反正我不指望别人。",
            "SEXY": "不管怎样，我依然是全场最靓的崽～",
            "MONK": "胜败乃兵家常事。真相已现，无需多言。",
            "DEAD": "。",
        }
        return reflections.get(pers, "一局游戏，学到了一些东西。")

    def _call(self, messages, temperature, max_tokens):
        return '{"content": "test", "strategy_summary": "test"}'

    def chat(self, messages, temperature=0.7, max_tokens=300):
        return "test"

    def chat_with_strategy(self, messages, temperature=0.7, max_tokens=350):
        return "test", "test"

    def witch_act(self, context, save_target, has_antidote, has_poison):
        self._delay()
        return {"use_antidote": False, "poison_target": None}

    def wolf_discuss(self, context, packmates):
        self._delay()
        return "今晚的目标已经很明确了，动手吧。"

    def night_kill(self, context, targets):
        """选择击杀目标。targets 已是 non_wolves 列表"""
        self._delay()
        if not targets:
            return 1
        # 优先杀编号最小的，但保持变化
        idx = self._call_count % len(targets)
        self._call_count += 1
        return targets[idx]

    def night_investigate(self, context, targets):
        self._delay()
        return targets[0]


def _patch_stub():
    import wolf_agent.engine.game as game
    game.LLMClient = StubLLM  # type: ignore


def run_spectate(seed: int = 42, stub: bool = False, no_memory: bool = False,
                 memory_dir: str = ""):
    """Run a complete game with live terminal output."""
    mode = "STUB" if stub else "REAL"
    print(f"\n{'='*50}")
    print(f"  Wolf Agent v2 — 旁观模式 [{mode}]")
    print(f"  Seed: {seed}")
    if no_memory:
        print(f"  记忆: 关闭")
    if memory_dir:
        print(f"  记忆目录: {memory_dir}")
    print(f"{'='*50}\n")

    start = time.time()

    if stub:
        _patch_stub()

    from wolf_agent.engine.game import create_game, default_state

    initial = default_state(seed)
    initial["_no_memory"] = no_memory
    if memory_dir:
        initial["_memory_dir"] = memory_dir
    initial["_player_memories"] = {}

    from wolf_agent.engine import _build_and_run
    final_state = _build_and_run(initial)

    elapsed = time.time() - start

    winner = final_state.get("winner")
    winner_name = "🐺 狼人" if winner == "werewolf" else "👤 好人"
    print(f"\n{'='*50}")
    print(f"  游戏结束！{winner_name} 获胜！")
    print(f"  回合数: {final_state['round_num']}")
    print(f"  用时: {elapsed:.1f}s")
    print(f"  事件日志: {final_state.get('event_log_path', 'N/A')}")
    print(f"{'='*50}\n")

    print("最终状态:")
    for p in final_state["players"]:
        status = "存活" if p["id"] in final_state["alive"] else "死亡"
        role_map = {"werewolf": "狼人", "seer": "预言家", "witch": "女巫", "villager": "村民"}
        role_name = role_map.get(p["role"], p["role"])
        print(f"  {p['id']}号 [{p['personality']}] ({role_name}) — {status}")

    return final_state


def _compute_stats(summaries: list[dict]) -> dict:
    total = len(summaries)
    if total == 0:
        return {"batch": {"total_games": 0}, "winner_stats": {}, "round_stats": {}}

    wolf_wins = sum(1 for s in summaries if s.get("winner") == "werewolf")
    villager_wins = total - wolf_wins

    rounds = [s.get("rounds", 0) for s in summaries]
    mean_rounds = sum(rounds) / total
    variance = sum((r - mean_rounds) ** 2 for r in rounds) / total

    role_survival: dict[str, list[int]] = {}
    for s in summaries:
        for p in s.get("players", []):
            role = p.get("role", "")
            if role not in role_survival:
                role_survival[role] = []
            role_survival[role].append(s.get("rounds", 0) if p.get("alive") else 1)

    return {
        "winner_stats": {
            "werewolf": {"wins": wolf_wins, "win_rate": round(wolf_wins / total, 4)},
            "villager": {"wins": villager_wins, "win_rate": round(villager_wins / total, 4)},
        },
        "round_stats": {
            "mean": round(mean_rounds, 2),
            "min": min(rounds),
            "max": max(rounds),
            "std": round(math.sqrt(variance), 2),
        },
        "role_survival": {
            role: {"mean": round(sum(vals) / len(vals), 2)}
            for role, vals in role_survival.items()
        },
    }


def _collect_summaries(directory: str) -> list[dict]:
    summaries = []
    if not os.path.isdir(directory):
        print(f"警告: 目录不存在 {directory}", file=sys.stderr)
        return summaries

    for fname in os.listdir(directory):
        if not fname.endswith(".summary.json"):
            continue
        path = os.path.join(directory, fname)
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            if not isinstance(data, dict) or "winner" not in data:
                raise ValueError("missing winner field")
            summaries.append(data)
        except (json.JSONDecodeError, ValueError, OSError) as e:
            print(f"警告: 跳过异常文件 {fname} — {e}", file=sys.stderr)
            continue

    return summaries


def cmd_run_spectate(args: argparse.Namespace):
    no_memory = args.no_memory or args.stub  # --stub implies --no-memory
    if args.batch:
        batch_seed = args.batch_seed or args.seed
        from wolf_agent.engine.game import default_state, _build_and_run

        results = []
        for i in range(args.batch):
            seed = batch_seed + i if batch_seed else 42 + i
            initial = default_state(seed)
            initial["_no_memory"] = no_memory
            if args.memory_dir:
                initial["_memory_dir"] = args.memory_dir
            initial["_player_memories"] = {}

            if args.stub:
                _patch_stub()

            final = _build_and_run(initial)
            results.append(final)
            print(f"  [{i + 1}/{args.batch}] game={final['game_id']} winner={final.get('winner')}")

        summaries = []
        for final in results:
            from wolf_agent.engine.game import _dump_summary
            # Build summary dict from final state
            players_data = [
                {"id": p["id"], "personality": p["personality"],
                 "role": p["role"], "alive": p["id"] in final["alive"]}
                for p in final["players"]
            ]
            summaries.append({
                "game_id": final["game_id"],
                "seed": final["seed"],
                "winner": final["winner"],
                "rounds": final["round_num"],
                "roles": {str(k): v for k, v in final["roles"].items()},
                "players": players_data,
            })

        stats = _compute_stats(summaries)
        batch_seed_val = batch_seed if batch_seed else 42
        timestamp = time.strftime("%Y%m%d-%H%M%S")
        games_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "games")
        os.makedirs(games_dir, exist_ok=True)
        output_path = os.path.join(games_dir, f"stats-batch-{batch_seed_val}-{timestamp}.json")

        stats["batch"] = {
            "total_games": args.batch,
            "seed": batch_seed_val,
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "memory_enabled": not no_memory,
            "memory_dir": args.memory_dir or "games/",
        }

        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(stats, f, ensure_ascii=False, indent=2)
        print(f"\n批量统计已保存: {output_path}")
    else:
        run_spectate(seed=args.seed, stub=args.stub,
                     no_memory=no_memory, memory_dir=args.memory_dir or "")


def cmd_stats(args: argparse.Namespace):
    directory = args.dir or os.path.join(
        os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "games")
    summaries = _collect_summaries(directory)
    stats = _compute_stats(summaries)
    stats["batch"] = {"total_games": len(summaries)}

    output = json.dumps(stats, ensure_ascii=False, indent=2)
    if args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            f.write(output + "\n")
    else:
        print(output)


def cmd_web(args: argparse.Namespace):
    """启动 web 界面"""
    try:
        from wolf_agent.web import app, socketio
    except ImportError:
        print("错误: Flask 未安装。请运行: pip install flask", file=sys.stderr)
        sys.exit(1)

    port = args.port or 5000
    print(f"\n{'='*50}")
    print(f"  Wolf Agent v2 — Web 界面")
    print(f"  访问: http://localhost:{port}")
    print(f"{'='*50}\n")
    socketio.run(app, debug=False, port=port, host='127.0.0.1', allow_unsafe_werkzeug=True)


def main():
    parser = argparse.ArgumentParser(description="Wolf Agent v2 — AI vs AI 狼人杀引擎")
    subparsers = parser.add_subparsers(dest="command", help="子命令")

    # run_spectate
    spectate_parser = subparsers.add_parser("run_spectate", help="旁观模式")
    spectate_parser.add_argument("--seed", type=int, default=42, help="随机种子")
    spectate_parser.add_argument("--stub", action="store_true", help="使用确定性 mock（无需 API key）")
    spectate_parser.add_argument("--no-memory", action="store_true", help="不读写记忆（退化为 v1 行为）")
    spectate_parser.add_argument("--memory-dir", type=str, default="", help="记忆存储目录")
    spectate_parser.add_argument("--batch", type=int, default=0, help="批量跑 N 局")
    spectate_parser.add_argument("--batch-seed", type=int, default=0, help="批量种子")

    # stats
    stats_parser = subparsers.add_parser("stats", help="统计分析已有对局")
    stats_parser.add_argument("--dir", type=str, default="", help="游戏日志目录")
    stats_parser.add_argument("--output", type=str, default="", help="输出文件路径")

    # web
    web_parser = subparsers.add_parser("web", help="启动 web 界面")
    web_parser.add_argument("--port", type=int, default=5000, help="端口号")

    args = parser.parse_args()

    if args.command == "run_spectate":
        cmd_run_spectate(args)
    elif args.command == "stats":
        cmd_stats(args)
    elif args.command == "web":
        cmd_web(args)
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
