"""Web 界面 — v2.2-alpha 游戏验证页（run job + 回放）"""
import json
import os
import uuid
from pathlib import Path
from flask import Flask, jsonify, request, send_from_directory
from flask_socketio import SocketIO, emit, join_room
from datetime import datetime
import threading
import io
import time

app = Flask(__name__, static_folder='../web', static_url_path='/static')
socketio = SocketIO(app, cors_allowed_origins="*")

# 路径配置
_web_py_dir = os.path.dirname(os.path.abspath(__file__))
_project_root = os.path.dirname(_web_py_dir)

GAMES_DIR = Path(os.path.join(_project_root, 'games'))

# Run job 内存存储
RUNS = {}
RUNS_LOCK = threading.Lock()

# Phase 映射：day/night -> 具体阶段列表
PHASE_MAPPING = {
    'day': ['DAY', 'DEBATE', 'VOTE'],
    'night': ['NIGHT', 'WOLF_DEN', 'NIGHT_PREP'],
}

def load_events(game_id):
    """加载单局事件"""
    path = GAMES_DIR / f'{game_id}.events.jsonl'
    if not path.exists():
        return None
    events = []
    with open(path) as f:
        for line in f:
            if line.strip():
                events.append(json.loads(line))
    return events

def load_summary(game_id):
    """加载对局摘要"""
    path = GAMES_DIR / f'{game_id}.summary.json'
    if path.exists():
        with open(path) as f:
            return json.load(f)
    return None

def load_memories(game_id):
    """加载单局记忆"""
    path = GAMES_DIR / f'{game_id}.memories.jsonl'
    if not path.exists():
        return []
    memories = []
    with open(path) as f:
        for line in f:
            if line.strip():
                memories.append(json.loads(line))
    return memories

def extract_game_state(events, summary=None):
    """从事件流 + summary 提取游戏状态"""
    roles = {}
    personalities = {}
    alive = set()
    current_phase = None
    current_round = 0
    players_order = []

    # 从 summary 读取 roles 和 personalities
    if summary and 'players' in summary:
        for player in summary['players']:
            pid = player['id']
            roles[pid] = player.get('role')
            personalities[pid] = player.get('personality')
            alive.add(pid)
            if pid not in players_order:
                players_order.append(pid)

    # 从事件流推导 alive 和 current_phase/round
    for e in events:
        if e['type'] == 'role_assigned':
            player_id = e['from_player']
            if player_id not in roles:
                roles[player_id] = e['metadata'].get('role')
            if player_id not in personalities:
                personalities[player_id] = e['metadata'].get('personality')
            alive.add(player_id)
            if player_id not in players_order:
                players_order.append(player_id)
        elif e['type'] == 'phase_started':
            current_phase = e['metadata'].get('phase')
            current_round = e['metadata'].get('round', current_round)
        elif e['type'] == 'player_eliminated':
            alive.discard(e['from_player'])

    return {
        'roles': roles,
        'personalities': personalities,
        'alive': sorted(list(alive)),
        'current_phase': current_phase,
        'current_round': current_round,
        'players_order': players_order,
    }

def get_phase_events(events, phase_type):
    """按阶段类型过滤事件，包括该阶段内的所有事件"""
    if phase_type not in PHASE_MAPPING:
        return []

    target_phases = PHASE_MAPPING[phase_type]
    filtered = []
    current_phase = None

    for e in events:
        # 更新当前阶段
        if e['type'] == 'phase_started':
            current_phase = e['metadata'].get('phase')

        # 如果当前阶段属于目标阶段类型，则包含该事件
        if current_phase in target_phases:
            filtered.append(e)

    return filtered

def build_replay_data(game_id):
    """构建回放数据结构：按轮次分组 day/night 事件"""
    events = load_events(game_id)
    summary = load_summary(game_id)
    memories = load_memories(game_id)

    if not events or not summary:
        return None

    # 提取玩家信息
    players = []
    if 'players' in summary:
        for p in summary['players']:
            pid = p['id']
            player_memories = [m for m in memories if m.get('player_id') == pid]
            players.append({
                'id': pid,
                'personality': p.get('personality'),
                'role': p.get('role'),
                'alive': p.get('alive', True),
                'memory': player_memories[0] if player_memories else None,
            })

    # 按轮次组织事件
    rounds = []
    current_round = 0
    current_data = {'round': 0, 'night': {}, 'day': {}}

    for e in events:
        # 检测轮次变更
        if e['type'] == 'phase_started':
            round_num = e['metadata'].get('round', 0)
            if round_num != current_round:
                if current_round > 0:
                    rounds.append(current_data)
                current_round = round_num
                current_data = {'round': round_num, 'night': {}, 'day': {}}

        # 夜晚事件
        if e['type'] == 'message_posted' and e.get('channel') == 'wolf_den':
            current_data['night'].setdefault('messages', []).append({
                'event_id': e.get('event_id'),
                'player_id': e.get('from_player'),
                'role': 'werewolf',
                'content': e.get('content'),
                'strategy_summary': (e.get('strategy_summary') or (e.get('metadata', {}) or {}).get('strategy_summary', '')),
            })
        elif e['type'] == 'action_submitted' and e.get('metadata', {}).get('action') == 'kill':
            current_data['night']['kill_target'] = e['metadata'].get('target')
        elif e['type'] == 'player_eliminated':
            cause = e.get('metadata', {}).get('cause', '')
            if cause == 'night_kill':
                current_data['night'].setdefault('deaths', []).append(e.get('from_player'))
            elif cause == 'execution':
                current_data['day'].setdefault('deaths', []).append(e.get('from_player'))

        # 白天事件
        if e['type'] == 'message_posted' and e.get('channel') in ('announcement', 'public_board', 'last_will'):
            if e['channel'] == 'announcement':
                current_data['day'].setdefault('announcements', []).append(e.get('content'))
            else:
                # 查找该玩家的人格
                p_pers = None
                if 'players' in summary:
                    for sp in summary['players']:
                        if sp['id'] == e.get('from_player'):
                            p_pers = sp.get('personality')
                            break
                current_data['day'].setdefault('messages', []).append({
                    'event_id': e.get('event_id'),
                    'player_id': e.get('from_player'),
                    'role': summary.get('roles', {}).get(str(e.get('from_player'))),
                    'personality': p_pers,
                    'content': e.get('content'),
                    'strategy_summary': (e.get('strategy_summary') or (e.get('metadata', {}) or {}).get('strategy_summary', '')),
                })
        elif e['type'] == 'vote_cast':
            current_data['day'].setdefault('votes', []).append({
                'voter': e.get('from_player'),
                'target': e.get('metadata', {}).get('target'),
            })
        elif e['type'] == 'vote_resolved':
            meta = e.get('metadata', {})
            # 从 vote_cast 事件计算票数
            vote_counts = {}
            for v in current_data['day'].get('votes', []):
                t = v['target']
                vote_counts[t] = vote_counts.get(t, 0) + 1
            current_data['day']['vote_result'] = {
                'eliminated': meta.get('eliminated'),
                'tie': meta.get('tie', False),
                'counts': {str(k): v for k, v in vote_counts.items()},
            }

    if current_round > 0:
        rounds.append(current_data)

    return {
        'game_id': game_id,
        'seed': summary.get('seed'),
        'winner': summary.get('winner'),
        'rounds': rounds,
        'players': players,
        'memory_enabled': len(memories) > 0,
    }

def run_batch_games(run_id, batch_size, mode, memory_enabled, seed_mode, base_seed):
    """后台线程运行批量游戏"""
    from wolf_agent.engine.game import default_state, _build_and_run
    from wolf_agent.engine import game as game_module

    original_llm = game_module.LLMClient

    with RUNS_LOCK:
        RUNS[run_id]['status'] = 'running'
        RUNS[run_id]['started_at'] = datetime.utcnow().isoformat() + 'Z'

    try:
        if mode == 'stub':
            from wolf_agent.cli.main import StubLLM
            game_module.LLMClient = StubLLM

        for i in range(batch_size):
            try:
                seed = base_seed + i if seed_mode == 'fixed' else int(time.time() * 1000) % 100000 + i

                initial = default_state(seed)
                initial["_no_memory"] = not memory_enabled
                initial["_player_memories"] = {}

                final_state = _build_and_run(initial)
                game_id = final_state.get('game_id')
                events = load_events(game_id)
                summary = load_summary(game_id)

                result = {
                    'game_id': game_id, 'seed': seed,
                    'winner': final_state.get('winner'),
                    'rounds': final_state.get('round_num', 0),
                    'event_count': len(events) if events else 0,
                    'memory_count': len(load_memories(game_id)),
                }

                with RUNS_LOCK:
                    RUNS[run_id]['results'].append(result)
                    RUNS[run_id]['completed'] += 1
                    RUNS[run_id]['current_index'] = i + 1

            except Exception as e:
                with RUNS_LOCK:
                    RUNS[run_id]['failed'] += 1
                    RUNS[run_id]['errors'].append({
                        'game_index': i, 'seed': base_seed + i if seed_mode == 'fixed' else None, 'error': str(e),
                    })
                    RUNS[run_id]['current_index'] = i + 1

        # 最终状态
        with RUNS_LOCK:
            if RUNS[run_id]['failed'] == 0:
                RUNS[run_id]['status'] = 'completed'
            elif RUNS[run_id]['completed'] > 0:
                RUNS[run_id]['status'] = 'partial_success'
            else:
                RUNS[run_id]['status'] = 'failed'
            RUNS[run_id]['finished_at'] = datetime.utcnow().isoformat() + 'Z'

    except Exception as e:
        with RUNS_LOCK:
            RUNS[run_id]['status'] = 'failed'
            RUNS[run_id]['finished_at'] = datetime.utcnow().isoformat() + 'Z'
            RUNS[run_id]['errors'].append({'error': str(e)})
    finally:
        # P1-3: 恢复原始 LLMClient
        game_module.LLMClient = original_llm


@app.route('/api/debug')
def debug():
    """调试端点"""
    return jsonify({
        'GAMES_DIR': str(GAMES_DIR),
        'GAMES_DIR.exists()': GAMES_DIR.exists(),
        'files': [f.name for f in GAMES_DIR.glob('*.events.jsonl')] if GAMES_DIR.exists() else [],
    })

# ======================================================================
# v2.2 Run Job API
# ======================================================================

@app.route('/api/runs', methods=['POST'])
def create_run():
    """创建 run job"""
    data = request.get_json() or {}
    mode = data.get('mode', 'stub')
    batch_size = data.get('batch_size', 1)
    memory_enabled = data.get('memory_enabled', False)
    seed_mode = data.get('seed_mode', 'random')
    base_seed = data.get('base_seed')

    # 验证
    if mode not in ('stub', 'real'):
        return jsonify({'error': 'Mode must be stub or real'}), 400
    if mode == 'stub' and not (1 <= batch_size <= 50):
        return jsonify({'error': 'Stub mode batch_size must be 1-50'}), 400
    if mode == 'real' and not (1 <= batch_size <= 5):
        return jsonify({'error': 'Real mode batch_size must be 1-5'}), 400
    if seed_mode not in ('random', 'fixed'):
        return jsonify({'error': 'seed_mode must be random or fixed'}), 400
    if seed_mode == 'fixed' and not isinstance(base_seed, int):
        return jsonify({'error': 'base_seed must be integer when seed_mode is fixed'}), 400

    # 检查活跃 run
    with RUNS_LOCK:
        for rid, rdata in RUNS.items():
            if rdata['status'] in ('queued', 'running'):
                return jsonify({'error': 'Another run is already active'}), 409

        run_id = f"run-{datetime.utcnow().strftime('%Y%m%d-%H%M%S')}-{uuid.uuid4().hex[:8]}"
        if seed_mode == 'fixed':
            base_seed_val = base_seed
        else:
            import random as _random
            base_seed_val = _random.randint(1, 99999)

        RUNS[run_id] = {
            'run_id': run_id,
            'status': 'running',
            'mode': mode,
            'total': batch_size,
            'completed': 0,
            'failed': 0,
            'current_index': 0,
            'started_at': None,
            'finished_at': None,
            'results': [],
            'errors': [],
        }

    # 启动后台线程
    t = threading.Thread(
        target=run_batch_games,
        args=(run_id, batch_size, mode, memory_enabled, seed_mode, base_seed_val),
        daemon=True,
    )
    t.start()

    return jsonify({
        'run_id': run_id,
        'status': 'running',
        'total': batch_size,
        'completed': 0,
        'failed': 0,
        'results': [],
        'errors': [],
    }), 201

@app.route('/api/runs/<run_id>', methods=['GET'])
def get_run(run_id):
    """获取 run 状态（含实时输出）"""
    with RUNS_LOCK:
        if run_id not in RUNS:
            return jsonify({'error': 'Run not found'}), 404
        rdata = dict(RUNS[run_id])
    return jsonify(rdata)

# ======================================================================
# v2.2 Replay API
# ======================================================================

@app.route('/api/games/<game_id>/replay')
def get_replay(game_id):
    """获取对局回放数据"""
    data = build_replay_data(game_id)
    if not data:
        return jsonify({'error': 'Game not found'}), 404
    return jsonify(data)

# ======================================================================
# 兼容端点 (v2.1)
# ======================================================================

@app.route('/')
def index():
    """主页"""
    return send_from_directory('../web', 'index.html')

@app.route('/api/games')
def list_games():
    """列出所有对局"""
    import sys
    print(f"DEBUG: GAMES_DIR={GAMES_DIR}", file=sys.stderr, flush=True)
    print(f"DEBUG: GAMES_DIR.exists()={GAMES_DIR.exists()}", file=sys.stderr, flush=True)

    if GAMES_DIR.exists():
        files = list(GAMES_DIR.glob('*.events.jsonl'))
        print(f"DEBUG: found {len(files)} .events.jsonl files", file=sys.stderr, flush=True)
        for f in files[:3]:
            print(f"DEBUG:   - {f.name}", file=sys.stderr, flush=True)

    if not GAMES_DIR.exists():
        print(f"DEBUG: GAMES_DIR does not exist, returning empty list", file=sys.stderr, flush=True)
        return jsonify([])

    games = []
    for path in sorted(GAMES_DIR.glob('*.events.jsonl'), reverse=True):
        # 正确提取 game_id：wolf-v2-a3b1799d.events.jsonl -> wolf-v2-a3b1799d
        game_id = path.name.replace('.events.jsonl', '')
        summary_path = GAMES_DIR / f'{game_id}.summary.json'
        print(f"DEBUG: checking {summary_path}", file=sys.stderr, flush=True)
        if summary_path.exists():
            with open(summary_path) as f:
                summary = json.load(f)
                # 计算事件数
                event_count = 0
                events_path = GAMES_DIR / f'{game_id}.events.jsonl'
                if events_path.exists():
                    with open(events_path) as ef:
                        event_count = sum(1 for line in ef if line.strip())

                games.append({
                    'game_id': game_id,
                    'winner': summary.get('winner'),
                    'rounds': summary.get('rounds'),
                    'events': event_count,
                    'timestamp': summary.get('timestamp'),
                })
    print(f"DEBUG: returning {len(games)} games", file=sys.stderr, flush=True)
    return jsonify(games)

@app.route('/api/games/<game_id>')
def get_game(game_id):
    """获取单局详情"""
    events = load_events(game_id)
    summary = load_summary(game_id)
    memories = load_memories(game_id)

    if not events:
        return jsonify({'error': 'Game not found'}), 404

    state = extract_game_state(events, summary)

    return jsonify({
        'game_id': game_id,
        'summary': summary,
        'events': events,
        'memories': memories,
        'state': state,
    })

@app.route('/api/games/<game_id>/phase/<phase_type>')
def get_phase_events_api(game_id, phase_type):
    """获取特定阶段的事件"""
    events = load_events(game_id)
    summary = load_summary(game_id)

    if not events:
        return jsonify({'error': 'Game not found'}), 404

    phase_events = get_phase_events(events, phase_type)
    state = extract_game_state(events, summary)

    return jsonify({
        'game_id': game_id,
        'phase': phase_type,
        'events': phase_events,
        'state': state,
    })

@app.route('/api/stats')
def get_stats():
    """获取批量统计"""
    if not GAMES_DIR.exists():
        return jsonify({})

    # 查找最新的统计文件
    stat_files = list(GAMES_DIR.glob('stats-batch-*.json'))
    if not stat_files:
        return jsonify({})

    latest = sorted(stat_files, reverse=True)[0]
    with open(latest) as f:
        return jsonify(json.load(f))

@app.route('/api/personalities')
def get_personalities():
    """获取 SBTI 人格定义"""
    try:
        from wolf_agent.agents.personality import PERSONALITY_TEMPLATES
        result = {}
        for name, tpl in PERSONALITY_TEMPLATES.items():
            result[name] = {
                'title': tpl.get('title'),
                'description': tpl.get('description'),
                'params': tpl.get('params'),
            }
        return jsonify(result)
    except ImportError:
        # 如果导入失败，返回硬编码的人格定义
        personalities = {
            'BOSS': {'title': '掌控者', 'params': {'talk': 0.85, 'aggression': 0.85, 'trust': 0.20, 'lie': 0.50, 'independence': 0.20}},
            'FAKE': {'title': '伪人', 'params': {'talk': 0.50, 'aggression': 0.30, 'trust': 0.50, 'lie': 0.95, 'independence': 0.70}},
            'THIN-K': {'title': '思考者', 'params': {'talk': 0.50, 'aggression': 0.30, 'trust': 0.20, 'lie': 0.20, 'independence': 0.90}},
            'FUCK': {'title': '草者', 'params': {'talk': 0.85, 'aggression': 0.95, 'trust': 0.80, 'lie': 0.20, 'independence': 0.05}},
            'OJBK': {'title': '无所谓人', 'params': {'talk': 0.10, 'aggression': 0.20, 'trust': 0.50, 'lie': 0.50, 'independence': 0.05}},
            'SHIT': {'title': '愤世者', 'params': {'talk': 0.85, 'aggression': 0.85, 'trust': 0.05, 'lie': 0.50, 'independence': 0.70}},
            'ZZZZ': {'title': '装死者', 'params': {'talk': 0.05, 'aggression': 0.20, 'trust': 0.50, 'lie': 0.70, 'independence': 0.50}},
            'MALO': {'title': '吗喽', 'params': {'talk': 0.85, 'aggression': 0.30, 'trust': 0.70, 'lie': 0.30, 'independence': 0.20}},
            'JOKE-R': {'title': '小丑', 'params': {'talk': 0.85, 'aggression': 0.50, 'trust': 0.50, 'lie': 0.95, 'independence': 0.05}},
            'LOVE-R': {'title': '多情者', 'params': {'talk': 0.50, 'aggression': 0.20, 'trust': 0.95, 'lie': 0.20, 'independence': 0.20}},
            'MUM': {'title': '妈妈', 'params': {'talk': 0.50, 'aggression': 0.20, 'trust': 0.50, 'lie': 0.20, 'independence': 0.50}},
            'IMSB': {'title': '傻者', 'params': {'talk': 0.85, 'aggression': 0.30, 'trust': 0.70, 'lie': 0.50, 'independence': 0.20}},
            'SOLO': {'title': '孤儿', 'params': {'talk': 0.20, 'aggression': 0.70, 'trust': 0.05, 'lie': 0.50, 'independence': 0.95}},
            'SEXY': {'title': '尤物', 'params': {'talk': 0.95, 'aggression': 0.50, 'trust': 0.50, 'lie': 0.70, 'independence': 0.50}},
            'MONK': {'title': '僧人', 'params': {'talk': 0.20, 'aggression': 0.20, 'trust': 0.20, 'lie': 0.05, 'independence': 0.95}},
            'DEAD': {'title': '死者', 'params': {'talk': 0.05, 'aggression': 0.20, 'trust': 0.50, 'lie': 0.70, 'independence': 0.05}},
        }
        return jsonify(personalities)

# WebSocket 事件处理
@socketio.on('connect')
def handle_connect():
    """客户端连接"""
    emit('response', {'data': 'Connected to Wolf Agent v2.2'})

@socketio.on('join_game')
def on_join_game(data):
    """加入游戏观测"""
    game_id = data.get('game_id')
    join_room(game_id)

    # 优先返回回放数据
    replay = build_replay_data(game_id)
    if replay:
        emit('game_state', {
            'game_id': game_id,
            'replay': replay,
        })
        return

    events = load_events(game_id)
    summary = load_summary(game_id)
    if events:
        state = extract_game_state(events, summary)
        emit('game_state', {
            'game_id': game_id,
            'state': state,
            'total_events': len(events),
        })

@socketio.on('request_phase')
def on_request_phase(data):
    """请求特定阶段的事件流"""
    game_id = data.get('game_id')
    phase_type = data.get('phase')  # 'day' or 'night'

    events = load_events(game_id)
    summary = load_summary(game_id)
    if not events:
        emit('error', {'message': 'Game not found'})
        return

    phase_events = get_phase_events(events, phase_type)
    state = extract_game_state(events, summary)

    emit('phase_events', {
        'game_id': game_id,
        'phase': phase_type,
        'events': phase_events,
        'state': state,
    })

@socketio.on('request_memories')
def on_request_memories(data):
    """请求玩家记忆"""
    game_id = data.get('game_id')
    player_id = data.get('player_id')

    memories = load_memories(game_id)
    player_memories = [m for m in memories if m.get('player_id') == player_id]

    emit('player_memories', {
        'game_id': game_id,
        'player_id': player_id,
        'memories': player_memories,
    })

if __name__ == '__main__':
    socketio.run(app, debug=True, port=5000, host='0.0.0.0')
