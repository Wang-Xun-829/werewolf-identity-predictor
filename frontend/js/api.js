// API调用封装
const API_BASE = '/api';

async function apiRequest(url, method = 'GET', data = null) {
    const options = {
        method: method,
        headers: {
            'Content-Type': 'application/json',
        },
    };
    
    if (data) {
        options.body = JSON.stringify(data);
    }
    
    try {
        const response = await fetch(API_BASE + url, options);
        const result = await response.json();
        return result;
    } catch (error) {
        console.error('API请求失败:', error);
        return { success: false, error: error.message };
    }
}

// 阵营API
const FactionAPI = {
    list: () => apiRequest('/factions'),
    create: (data) => apiRequest('/factions', 'POST', data),
    update: (id, data) => apiRequest(`/factions/${id}`, 'PUT', data),
    delete: (id) => apiRequest(`/factions/${id}`, 'DELETE'),
};

// 身份API
const IdentityAPI = {
    list: () => apiRequest('/identities'),
    create: (data) => apiRequest('/identities', 'POST', data),
    update: (id, data) => apiRequest(`/identities/${id}`, 'PUT', data),
    delete: (id) => apiRequest(`/identities/${id}`, 'DELETE'),
};

// 版型API
const SetupAPI = {
    list: () => apiRequest('/setups'),
    create: (data) => apiRequest('/setups', 'POST', data),
    update: (id, data) => apiRequest(`/setups/${id}`, 'PUT', data),
    delete: (id) => apiRequest(`/setups/${id}`, 'DELETE'),
};

// 行为API
const ActionAPI = {
    list: () => apiRequest('/action_types'),
    create: (data) => apiRequest('/action_types', 'POST', data),
    update: (id, data) => apiRequest(`/action_types/${id}`, 'PUT', data),
    delete: (id) => apiRequest(`/action_types/${id}`, 'DELETE'),
};

// 玩家API
const PlayerAPI = {
    list: () => apiRequest('/players'),
    create: (data) => apiRequest('/players', 'POST', data),
    update: (id, data) => apiRequest(`/players/${id}`, 'PUT', data),
    delete: (id) => apiRequest(`/players/${id}`, 'DELETE'),
};

// 对局API
const GameAPI = {
    list: () => apiRequest('/games'),
    get: (id) => apiRequest(`/games/${id}`),
    create: (data) => apiRequest('/games', 'POST', data),
    update: (id, data) => apiRequest(`/games/${id}`, 'PUT', data),
    delete: (id) => apiRequest(`/games/${id}`, 'DELETE'),
    addPlayer: (gameId, data) => apiRequest(`/games/${gameId}/players`, 'POST', data),
    removePlayer: (gameId, playerId) => apiRequest(`/games/${gameId}/players/${playerId}`, 'DELETE'),
    updatePlayer: (gameId, playerId, data) => apiRequest(`/games/${gameId}/players/${playerId}`, 'PUT', data),
    getActions: (gameId) => apiRequest(`/games/${gameId}/actions`),
    createAction: (data) => apiRequest('/actions', 'POST', data),
    createActionsBatch: (data) => apiRequest('/actions/batch', 'POST', data),
    updateAction: (id, data) => apiRequest(`/actions/${id}`, 'PUT', data),
    deleteAction: (id) => apiRequest(`/actions/${id}`, 'DELETE'),
    getPredictions: (gameId) => apiRequest(`/games/${gameId}/predictions`),
    updateResultStatus: (gameId) => apiRequest(`/games/${gameId}/update_result_status`, 'POST'),
    confirm: (gameId) => apiRequest(`/games/${gameId}/confirm`, 'POST'),
};

// 游戏流程API
const GameFlowAPI = {
    getPhase: (gameId) => apiRequest(`/games/${gameId}/phase`),
    advancePhase: (gameId, customPhase = null) => apiRequest(`/games/${gameId}/phase/advance${customPhase ? `?custom_phase=${encodeURIComponent(customPhase)}` : ''}`, 'POST'),
    wolfExplode: (gameId, playerId) => apiRequest(`/games/${gameId}/wolf_explode?player_id=${playerId}`, 'POST'),
    initPhase: (gameId) => apiRequest(`/games/${gameId}/phase/init`, 'POST'),
    updateStatus: (gameId, playerId, data) => apiRequest(`/games/${gameId}/players/${playerId}/status`, 'PUT', data),
    getEligibleVoters: (gameId, voteType) => apiRequest(`/games/${gameId}/eligible_voters?vote_type=${voteType}`),
    getVoteResult: (gameId, voteType) => apiRequest(`/games/${gameId}/vote_result?vote_type=${voteType}`),
};

// 预言家分析API
const ProphetAPI = {
    getAnalysis: (gameId) => apiRequest(`/games/${gameId}/prophet_analysis`),
};

// 狼坑分析API
const WolfPitAPI = {
    listConstraints: (gameId) => apiRequest(`/games/${gameId}/wolf_pit/constraints`),
    createConstraint: (gameId, data) => apiRequest(`/games/${gameId}/wolf_pit/constraints`, 'POST', data),
    deleteConstraint: (id) => apiRequest(`/wolf_pit/constraints/${id}`, 'DELETE'),
    getAnalysis: (gameId, totalWolves = 4) => apiRequest(`/games/${gameId}/wolf_pit/analysis?total_wolves=${totalWolves}`),
};

// 确认身份API
const ConfirmedIdentityAPI = {
    list: (gameId) => apiRequest(`/games/${gameId}/confirmed_identities`),
    create: (gameId, data) => apiRequest(`/games/${gameId}/confirmed_identities`, 'POST', data),
    delete: (id) => apiRequest(`/confirmed_identities/${id}`, 'DELETE'),
};

// 梯度学习API
const GradientLearningAPI = {
    run: (gameId = null) => apiRequest(`/gradient_learning/run${gameId ? `?game_id=${gameId}` : ''}`, 'POST'),
    history: (limit = 10) => apiRequest(`/gradient_learning/history?limit=${limit}`),
    backups: (limit = 10) => apiRequest(`/gradient_learning/backups?limit=${limit}`),
    restore: (backupId) => apiRequest(`/gradient_learning/restore/${backupId}`, 'POST'),
    currentScore: () => apiRequest('/gradient_learning/current_score'),
};
