"""Web 界面 — 对局回放 + 实时观测（v2.1-alpha）"""
import json
import os
from pathlib import Path
from flask import Flask, jsonify, request, send_from_directory
from flask_socketio import SocketIO, emit, join_room
from datetime import datetime
import threading
import time

app = Flask(__name__, static_folder='../web', static_url_path='')
socketio = SocketIO(app, cors_allowed_origins="*")

# 使用绝对路径确保无论从哪个目录启动都能找到 games 目录
GAMES_DIR = Path(__file__).parent.parent / 'games'

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

@app.route('/')
def index():
    """主页"""
    return send_from_directory('../web', 'index.html')

@app.route('/api/games')
def list_games():
    """列出所有对局"""
    if not GAMES_DIR.exists():
        return jsonify([])

    games = []
    for path in sorted(GAMES_DIR.glob('*.events.jsonl'), reverse=True):
        # 正确提取 game_id：wolf-v2-a3b1799d.events.jsonl -> wolf-v2-a3b1799d
        game_id = path.name.replace('.events.jsonl', '')
        summary_path = GAMES_DIR / f'{game_id}.summary.json'
        if summary_path.exists():
            with open(summary_path) as f:
                summary = json.load(f)
                games.append({
                    'game_id': game_id,
                    'winner': summary.get('winner'),
                    'rounds': summary.get('rounds'),
                    'events': summary.get('event_count'),
                    'timestamp': summary.get('timestamp'),
                })
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
    emit('response', {'data': 'Connected to Wolf Agent v2.1'})

@socketio.on('join_game')
def on_join_game(data):
    """加入游戏观测"""
    game_id = data.get('game_id')
    join_room(game_id)

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
