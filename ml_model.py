"""
机器学习优化模块

功能：
1. 特征工程：从行为记录中提取特征
2. 模型训练：逻辑回归模型
3. 模型预测：集成到预测流程中
4. 模型评估：准确率、特征重要性
5. 混合预测：贝叶斯+ML的几何平均
"""

import math
from db import query_all, query_one, execute_write, ph


# 超参数
ML_MIN_SAMPLES = 20  # 最少样本数，低于此数不训练ML模型
ML_LEARNING_RATE = 0.01
ML_ITERATIONS = 200
ML_REGULARIZATION = 0.01

# 默认行为特征映射（action_id -> 特征名），用于初始化
DEFAULT_ACTION_FEATURES = {
    1: 'jump_prophet',      # 跳预言家
    2: 'check',              # 查杀
    3: 'gold',               # 发金水
    4: 'jump_witch',         # 跳女巫
    5: 'jump_hunter',        # 跳猎人
    6: 'jump_guard',         # 跳守卫
    7: 'claim_villager',     # 认平民
    8: 'vote',               # 投票
    9: 'abstain',            # 弃票
    10: 'side',              # 站边
    11: 'hook',              # 倒钩
    12: 'charge',            # 冲锋
    13: 'self_explode',      # 自爆
    14: 'shoot',             # 开枪
    15: 'use_cure',          # 使用解药
    16: 'use_poison',        # 使用毒药
    17: 'guard',             # 守护
    18: 'attack',            # 质疑/踩
    19: 'idle'               # 划水
}

# 固定特征（非行为特征）
FIXED_FEATURES = [
    'has_target',           # 有目标对象
    'round_1',              # 第一轮
    'round_2',              # 第二轮
    'round_3_plus',         # 第三轮及以后
    'phase_speech',         # 发言阶段
    'phase_vote',           # 投票阶段
    'attack_count',         # 踩人次数
    'defend_count',         # 保人次数
    'behavior_count'        # 行为总数
]


def get_all_action_features():
    """从数据库动态加载所有行为，构建动态特征映射

    返回：
        dict: {action_id: feature_name}
    """
    try:
        actions = query_all("SELECT id, name FROM actions ORDER BY id")
        if actions:
            features = {}
            for a in actions:
                action_id = a['id']
                action_name = a['name']
                # 使用行为名称作为特征名（转换为小写，空格替换为下划线）
                feature_name = 'action_' + str(action_id) + '_' + action_name.lower().replace(' ', '_').replace('/', '_')
                features[action_id] = feature_name
            return features
    except Exception as e:
        print(f"动态加载行为特征失败，使用默认特征: {e}")

    return DEFAULT_ACTION_FEATURES


def get_all_features():
    """获取所有特征列表（动态行为特征 + 固定特征）

    返回：
        list: 所有特征名列表
    """
    action_features = get_all_action_features()
    return list(action_features.values()) + FIXED_FEATURES


def extract_features(game_id, player_id):
    """从行为记录中提取特征向量

    参数：
        game_id: 对局ID
        player_id: 玩家ID

    返回：
        dict: 特征向量
    """
    # 动态加载所有行为特征（包括用户新增的行为）
    action_features = get_all_action_features()
    all_features = get_all_features()
    features = {f: 0.0 for f in all_features}

    # 获取该玩家的所有行为记录
    behaviors = query_all(
        f"SELECT * FROM behavior_records WHERE game_id = {ph()} AND actor_id = {ph()}",
        (game_id, player_id)
    )

    if not behaviors:
        return features

    features['behavior_count'] = float(len(behaviors))

    attack_count = 0
    defend_count = 0

    for b in behaviors:
        action_id = b['action_id']
        feature_name = action_features.get(action_id)
        if feature_name:
            features[feature_name] += 1.0

        # 有目标对象
        if b.get('target_id'):
            features['has_target'] = 1.0

        # 轮次特征
        round_num = b.get('round_number') or 0
        if round_num == 1:
            features['round_1'] = 1.0
        elif round_num == 2:
            features['round_2'] = 1.0
        elif round_num >= 3:
            features['round_3_plus'] = 1.0

        # 阶段特征
        phase = b.get('phase') or ''
        if '发言' in phase:
            features['phase_speech'] = 1.0
        elif '投票' in phase:
            features['phase_vote'] = 1.0

        # 踩人/保人计数
        if action_id in [18, 2, 16]:  # 质疑、查杀、使用毒药
            attack_count += 1
        elif action_id in [15, 17, 3, 10]:  # 使用解药、守护、发金水、站边
            defend_count += 1

    features['attack_count'] = float(attack_count)
    features['defend_count'] = float(defend_count)

    # 归一化（除以行为总数）
    if features['behavior_count'] > 0:
        for f in all_features:
            if f not in ['behavior_count', 'has_target', 'round_1', 'round_2', 'round_3_plus', 'phase_speech', 'phase_vote']:
                features[f] = features[f] / features['behavior_count']

    return features


def sigmoid(z):
    """Sigmoid激活函数"""
    if z >= 0:
        return 1.0 / (1.0 + math.exp(-z))
    else:
        exp_z = math.exp(z)
        return exp_z / (1.0 + exp_z)


def train_logistic_regression(X, y, learning_rate=ML_LEARNING_RATE, iterations=ML_ITERATIONS, regularization=ML_REGULARIZATION):
    """训练逻辑回归模型

    参数：
        X: 特征矩阵（list of dict）
        y: 标签列表（0或1）
        learning_rate: 学习率
        iterations: 迭代次数
        regularization: 正则化系数

    返回：
        weights: 权重字典
        bias: 偏置
    """
    n_samples = len(X)
    if n_samples == 0:
        return {}, 0.0

    # 从训练数据中提取特征列表（确保特征一致）
    feature_list = list(X[0].keys()) if X else []

    # 初始化权重
    weights = {f: 0.0 for f in feature_list}
    bias = 0.0

    # 梯度下降
    for _ in range(iterations):
        # 计算预测
        predictions = []
        for i in range(n_samples):
            z = bias + sum(weights[f] * X[i].get(f, 0.0) for f in feature_list)
            predictions.append(sigmoid(z))

        # 计算梯度
        grad_w = {f: 0.0 for f in feature_list}
        grad_b = 0.0

        for i in range(n_samples):
            error = predictions[i] - y[i]
            for f in feature_list:
                grad_w[f] += error * X[i].get(f, 0.0)
            grad_b += error

        # 更新权重（带正则化）
        for f in feature_list:
            weights[f] -= learning_rate * (grad_w[f] / n_samples + regularization * weights[f])
        bias -= learning_rate * (grad_b / n_samples)

    return weights, bias


def predict_logistic_regression(features, weights, bias):
    """使用逻辑回归模型预测

    参数：
        features: 特征向量
        weights: 权重字典
        bias: 偏置

    返回：
        float: 预测概率（0-1）
    """
    # 使用weights的键作为特征列表（更灵活）
    z = bias + sum(weights[f] * features.get(f, 0.0) for f in weights.keys())
    return sigmoid(z)


def train_model_for_role(role_id, camp):
    """为某个身份训练二分类模型

    参数：
        role_id: 身份ID
        camp: 阵营（好人/狼人）

    返回：
        dict: 模型信息（weights, bias, accuracy, sample_count）
    """
    # 获取所有已确认的对局
    confirmed_games = query_all(
        "SELECT DISTINCT game_id FROM game_confirmed_identities"
    )

    if not confirmed_games:
        return None

    X = []
    y = []

    for game in confirmed_games:
        game_id = game['game_id']

        # 获取该对局中所有玩家的确认身份
        confirmed = query_all(
            f"SELECT * FROM game_confirmed_identities WHERE game_id = {ph()}",
            (game_id,)
        )

        for ci in confirmed:
            player_id = ci['player_id']
            # 提取特征
            features = extract_features(game_id, player_id)
            X.append(features)

            # 标签：是否是该身份
            if camp == '好人':
                label = 1.0 if ci.get('camp') == '好人' else 0.0
            else:
                label = 1.0 if ci.get('camp') == '狼人' else 0.0
            y.append(label)

    if len(X) < ML_MIN_SAMPLES:
        return {
            'trained': False,
            'sample_count': len(X),
            'message': f'样本不足（{len(X)}/{ML_MIN_SAMPLES}），暂不训练'
        }

    # 训练模型
    weights, bias = train_logistic_regression(X, y)

    # 计算训练集准确率
    correct = 0
    for i in range(len(X)):
        pred = predict_logistic_regression(X[i], weights, bias)
        predicted_label = 1.0 if pred >= 0.5 else 0.0
        if predicted_label == y[i]:
            correct += 1
    accuracy = correct / len(X) if len(X) > 0 else 0.0

    # 计算特征重要性（权重绝对值）
    feature_importance = sorted(
        [(f, abs(weights[f])) for f in weights.keys()],
        key=lambda x: x[1],
        reverse=True
    )

    return {
        'trained': True,
        'sample_count': len(X),
        'weights': weights,
        'bias': bias,
        'accuracy': accuracy,
        'feature_importance': feature_importance[:10]  # Top 10重要特征
    }


def get_ml_model_status():
    """获取ML模型状态

    返回：
        dict: 模型状态
    """
    # 检查已确认对局数量
    confirmed_games = query_all(
        "SELECT COUNT(DISTINCT game_id) as count FROM game_confirmed_identities"
    )
    game_count = confirmed_games[0]['count'] if confirmed_games else 0

    # 检查已确认身份数量
    confirmed_identities = query_all(
        "SELECT COUNT(*) as count FROM game_confirmed_identities"
    )
    identity_count = confirmed_identities[0]['count'] if confirmed_identities else 0

    # 检查是否已训练模型
    models = query_all("SELECT * FROM ml_models")
    trained_models = len(models)

    # 动态获取所有行为和特征
    all_actions = query_all("SELECT id, name FROM actions ORDER BY id")
    action_features = get_all_action_features()
    all_features = get_all_features()

    return {
        'game_count': game_count,
        'identity_count': identity_count,
        'trained_models': trained_models,
        'min_samples': ML_MIN_SAMPLES,
        'ready': identity_count >= ML_MIN_SAMPLES,
        'all_actions': all_actions,
        'action_features': action_features,
        'all_features': all_features,
        'feature_count': len(all_features)
    }


def train_all_models():
    """训练所有模型（好人/狼人二分类）

    返回：
        dict: 训练结果
    """
    results = {}

    # 训练好人分类器
    good_model = train_model_for_role(0, '好人')
    results['good'] = good_model

    # 训练狼人分类器
    wolf_model = train_model_for_role(0, '狼人')
    results['wolf'] = wolf_model

    # 保存模型到数据库
    if good_model and good_model.get('trained'):
        execute_write(
            f"INSERT OR REPLACE INTO ml_models (model_type, role_id, weights, bias, accuracy, sample_count, updated_at) VALUES ({ph()}, {ph()}, {ph()}, {ph()}, {ph()}, {ph()}, CURRENT_TIMESTAMP)",
            ('logistic_regression', 0, str(good_model['weights']), good_model['bias'], good_model['accuracy'], good_model['sample_count'])
        )

    if wolf_model and wolf_model.get('trained'):
        execute_write(
            f"INSERT OR REPLACE INTO ml_models (model_type, role_id, weights, bias, accuracy, sample_count, updated_at) VALUES ({ph()}, {ph()}, {ph()}, {ph()}, {ph()}, {ph()}, CURRENT_TIMESTAMP)",
            ('logistic_regression', -1, str(wolf_model['weights']), wolf_model['bias'], wolf_model['accuracy'], wolf_model['sample_count'])
        )

    return results


def ml_predict(game_id, player_id):
    """使用ML模型预测玩家身份

    参数：
        game_id: 对局ID
        player_id: 玩家ID

    返回：
        dict: 预测结果（good_prob, wolf_prob）
    """
    # 提取特征
    features = extract_features(game_id, player_id)

    # 加载好人分类器
    good_model = query_one(
        "SELECT * FROM ml_models WHERE model_type = 'logistic_regression' AND role_id = 0"
    )

    # 加载狼人分类器
    wolf_model = query_one(
        "SELECT * FROM ml_models WHERE model_type = 'logistic_regression' AND role_id = -1"
    )

    if not good_model or not wolf_model:
        return None

    # 解析权重
    import ast
    good_weights = ast.literal_eval(good_model['weights'])
    wolf_weights = ast.literal_eval(wolf_model['weights'])

    # 预测
    good_prob = predict_logistic_regression(features, good_weights, good_model['bias'])
    wolf_prob = predict_logistic_regression(features, wolf_weights, wolf_model['bias'])

    # 归一化
    total = good_prob + wolf_prob
    if total > 0:
        good_prob /= total
        wolf_prob /= total

    return {
        'good_prob': good_prob,
        'wolf_prob': wolf_prob,
        'good_accuracy': good_model['accuracy'],
        'wolf_accuracy': wolf_model['accuracy']
    }
