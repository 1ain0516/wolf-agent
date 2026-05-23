"""Web 界面 — 对局回放 + 统计分析"""
import json
import os
from pathlib import Path
from flask import Flask, jsonify, request, send_from_directory
from datetime import datetime

app = Flask(__name__, static_folder='../web', static_url_path='')

GAMES_DIR = Path('games')

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
        game_id = path.stem
        summary = load_summary(game_id)
        if summary:
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

    # 提取玩家信息
    roles = {}
    personalities = {}
    alive = set()

    for e in events:
        if e['type'] == 'role_assigned':
            player_id = e['from_player']
            roles[player_id] = e['metadata']['role']
            alive.add(player_id)
            if 'personality' in e['metadata']:
                personalities[player_id] = e['metadata']['personality']
        elif e['type'] == 'player_eliminated':
            alive.discard(e['from_player'])

    return jsonify({
        'game_id': game_id,
        'summary': summary,
        'events': events,
        'memories': memories,
        'roles': roles,
        'personalities': personalities,
        'alive': list(alive),
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
    personalities = {
        'BOSS': {'name': '掌控者', 'talk': 0.85, 'aggression': 0.85, 'trust': 0.20, 'lie': 0.50, 'independence': 0.20},
        'FAKE': {'name': '伪人', 'talk': 0.50, 'aggression': 0.30, 'trust': 0.50, 'lie': 0.95, 'independence': 0.70},
        'THIN-K': {'name': '思考者', 'talk': 0.50, 'aggression': 0.30, 'trust': 0.20, 'lie': 0.20, 'independence': 0.90},
        'FUCK': {'name': '草者', 'talk': 0.85, 'aggression': 0.95, 'trust': 0.80, 'lie': 0.20, 'independence': 0.05},
        'OJBK': {'name': '无所谓人', 'talk': 0.10, 'aggression': 0.20, 'trust': 0.50, 'lie': 0.50, 'independence': 0.05},
        'SHIT': {'name': '愤世者', 'talk': 0.85, 'aggression': 0.85, 'trust': 0.05, 'lie': 0.50, 'independence': 0.70},
        'ZZZZ': {'name': '装死者', 'talk': 0.05, 'aggression': 0.20, 'trust': 0.50, 'lie': 0.70, 'independence': 0.50},
        'MALO': {'name': '吗喽', 'talk': 0.85, 'aggression': 0.30, 'trust': 0.70, 'lie': 0.30, 'independence': 0.20},
        'JOKE-R': {'name': '小丑', 'talk': 0.85, 'aggression': 0.50, 'trust': 0.50, 'lie': 0.95, 'independence': 0.05},
        'LOVE-R': {'name': '多情者', 'talk': 0.50, 'aggression': 0.20, 'trust': 0.95, 'lie': 0.20, 'independence': 0.20},
        'MUM': {'name': '妈妈', 'talk': 0.50, 'aggression': 0.20, 'trust': 0.50, 'lie': 0.20, 'independence': 0.50},
        'IMSB': {'name': '傻者', 'talk': 0.85, 'aggression': 0.30, 'trust': 0.70, 'lie': 0.50, 'independence': 0.20},
        'SOLO': {'name': '孤儿', 'talk': 0.20, 'aggression': 0.70, 'trust': 0.05, 'lie': 0.50, 'independence': 0.95},
        'SEXY': {'name': '尤物', 'talk': 0.95, 'aggression': 0.50, 'trust': 0.50, 'lie': 0.70, 'independence': 0.50},
        'MONK': {'name': '僧人', 'talk': 0.20, 'aggression': 0.20, 'trust': 0.20, 'lie': 0.05, 'independence': 0.95},
        'DEAD': {'name': '死者', 'talk': 0.05, 'aggression': 0.20, 'trust': 0.50, 'lie': 0.70, 'independence': 0.05},
    }
    return jsonify(personalities)

if __name__ == '__main__':
    app.run(debug=True, port=5000)
