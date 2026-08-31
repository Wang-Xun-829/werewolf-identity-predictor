// 对局详情页

const gameId = document.getElementById('game-id').value;
let gameData = null;
let allPlayers = [];
let allActions = [];
let allRoles = [];
let gamePlayers = [];
let predictions = [];
let selectedPlayerId = null;  // 当前选中的玩家ID（书签切换）

// 多情景假设推理
let scenarios = [];  // 所有情景列表
let currentScenarioId = '';  // 当前用于预测的情景ID（空字符串表示综合预测）
let editingScenarioId = null;  // 当前在模态框中编辑的情景ID

// 当前游戏阶段信息
let currentGamePhase = null;  // {phase, round, display, time}

// 添加玩家模态框的临时勾选状态（搜索过滤时保留）
let tempSelectedPlayers = {};  // { playerId: { checked: true, seat_number: 1 } }

// 通用模态框函数

// 折叠/展开区域
function toggleSection(contentId, toggleId) {
    const content = document.getElementById(contentId);
    const toggle = document.getElementById(toggleId);
    if (!content) return;
    if (content.style.display === 'none') {
        content.style.display = 'block';
        if (toggle) toggle.textContent = '▲';
    } else {
        content.style.display = 'none';
        if (toggle) toggle.textContent = '▼';
    }
}
function hideModal(id) {
    document.getElementById(id).classList.remove('show');
}

document.addEventListener('DOMContentLoaded', async () => {
    await Promise.all([loadAllPlayers(), loadAllActions(), loadAllRoles()]);
    await loadGame();
});

// 加载所有玩家（用于下拉选择）
async function loadAllPlayers() {
    const result = await api('GET', '/players');
    if (result) allPlayers = result.data;
}

async function loadAllActions() {
    const result = await api('GET', '/actions');
    if (result) {
        allActions = result.data;
        // 按名称字母排序（支持中文拼音排序）
        allActions.sort((a, b) => a.name.localeCompare(b.name, 'zh-CN'));
    }
}

async function loadAllRoles() {
    const result = await api('GET', '/roles');
    if (result) allRoles = result.data;
}

// 加载对局详情
async function loadGame() {
    const result = await api('GET', '/games/' + gameId);
    if (!result) return;
    gameData = result.data;
    gamePlayers = gameData.players || [];

    // 更新头部
    document.getElementById('game-header').innerHTML =
        `<strong>${escapeHtml(gameData.game_code)}</strong> <span style="color:#999;font-size:13px;font-weight:normal;">${escapeHtml(gameData.setup_name || '')}</span>`;
    document.getElementById('game-status').innerHTML = statusBadge(gameData.status);

    // 按钮状态
    document.getElementById('btn-finish').style.display = gameData.status === '进行中' ? 'inline-flex' : 'none';
    document.getElementById('btn-confirm').style.display = gameData.status === '已结束' ? 'inline-flex' : 'none';

    // 填充下拉选项
    populateSelects();
    // 渲染玩家预测
    await loadPredictions();
    // 渲染行为记录
    renderBehaviors(gameData.behaviors || []);
    // 加载情景列表和铁狼/铁好人
    await loadScenarios();
    await loadInvariantPlayers();
    // 加载当前游戏阶段
    await loadCurrentPhase();
    // 加载系统推导事实
    await loadInferenceFacts();
}

// 填充下拉选择框
function populateSelects() {
    const actorSelect = document.getElementById('behavior-actor');
    const targetSelect = document.getElementById('behavior-target');
    const actionSelect = document.getElementById('behavior-action');
    const roleSelect = document.getElementById('behavior-role');
    const filterPlayerSelect = document.getElementById('behavior-filter-player');

    actorSelect.innerHTML = '<option value="">请选择发起者</option>';
    targetSelect.innerHTML = '<option value="">无目标</option>';
    // 保留"全部玩家"选项
    if (filterPlayerSelect) {
        filterPlayerSelect.innerHTML = '<option value="">全部玩家</option>';
    }

    gamePlayers.forEach(gp => {
        const seat = gp.seat_number ? `${gp.seat_number}号 ` : '';
        actorSelect.innerHTML += `<option value="${gp.player_id}">${seat}${escapeHtml(gp.player_name)}</option>`;
        targetSelect.innerHTML += `<option value="${gp.player_id}">${seat}${escapeHtml(gp.player_name)}</option>`;
        if (filterPlayerSelect) {
            filterPlayerSelect.innerHTML += `<option value="${gp.player_id}">${seat}${escapeHtml(gp.player_name)}</option>`;
        }
    });

    // 行为选择使用多选标签
    initActionMultiSelect();

    roleSelect.innerHTML = '<option value="">不声明</option>';
    allRoles.forEach(r => {
        roleSelect.innerHTML += `<option value="${r.id}">${escapeHtml(r.name)} (${r.camp})</option>`;
    });

    // 玩家选择下拉框增加搜索功能
    setTimeout(() => {
        initSearchableSelect('behavior-actor', '搜索发起者...');
        initSearchableSelect('behavior-target', '搜索目标玩家...');
        if (filterPlayerSelect) {
            initSearchableSelect('behavior-filter-player', '搜索玩家...');
        }
    }, 50);
}

// 加载预测结果
async function loadPredictions() {
    // 支持情景参数
    const url = currentScenarioId
        ? `/games/${gameId}/predictions?scenario_id=${currentScenarioId}`
        : `/games/${gameId}/predictions`;
    const result = await api('GET', url);
    const bookmarksContainer = document.getElementById('players-bookmarks');
    const predictionCard = document.getElementById('selected-player-prediction-card');
    const predictionContainer = document.getElementById('selected-player-prediction');

    if (!result || !result.data || result.data.length === 0) {
        bookmarksContainer.innerHTML = '<div class="empty-state"><p>暂无玩家</p></div>';
        predictionCard.style.display = 'none';
        return;
    }
    predictions = result.data;

    // 如果没有选中玩家，默认选中第一个
    if (!selectedPlayerId || !predictions.find(p => p.player_id === selectedPlayerId)) {
        selectedPlayerId = predictions[0].player_id;
    }

    // 渲染玩家书签列表
    renderPlayerBookmarks();

    // 渲染选中玩家的预测结果
    renderSelectedPlayerPrediction();

    // 加载预言家查验推导信息
    await loadProphetInference();

    // 加载逻辑一致性与视角分析
    await loadLogicAnalysis();
}

// 渲染玩家书签列表
function renderPlayerBookmarks() {
    const container = document.getElementById('players-bookmarks');
    let html = '';
    // 按座位号从小到大排序（没有座位号的排在最后）
    const sortedPredictions = [...predictions].sort((a, b) => {
        const seatA = gamePlayers.find(gp => gp.player_id === a.player_id)?.seat_number;
        const seatB = gamePlayers.find(gp => gp.player_id === b.player_id)?.seat_number;
        if (!seatA && !seatB) return 0;
        if (!seatA) return 1;
        if (!seatB) return -1;
        return seatA - seatB;
    });
    sortedPredictions.forEach(p => {
        const seat = gamePlayers.find(gp => gp.player_id === p.player_id)?.seat_number;
        const seatLabel = seat ? `${seat}号 ` : '';
        const isActive = p.player_id === selectedPlayerId;
        const topCamp = p.all_probabilities && p.all_probabilities[0] ? p.all_probabilities[0].camp : '';
        const topRoleCls = getCampClass(topCamp);
        const canRemove = gameData && gameData.status === '进行中';
        // 获取玩家状态
        const gp = gamePlayers.find(g => g.player_id === p.player_id);
        const isAlive = gp ? gp.is_alive !== false : true;
        const isOnPolice = gp ? gp.is_on_police : false;
        const isRetired = gp ? gp.is_retired : false;
        const deathType = gp ? gp.death_type : null;
        // 状态标签
        let statusBadges = '';
        if (!isAlive) {
            const deathLabel = deathType === 'night_death' ? '夜死' : '出局';
            statusBadges += `<span class="badge badge-dead" title="已死亡">${deathLabel}</span>`;
        }
        if (isOnPolice && !isRetired) {
            statusBadges += `<span class="badge badge-police" title="上警中">警</span>`;
        }
        if (isRetired) {
            statusBadges += `<span class="badge badge-retired" title="已退水">退</span>`;
        }
        html += `<div class="player-bookmark ${isActive ? 'active' : ''} ${!isAlive ? 'dead' : ''}" onclick="selectPlayer(${p.player_id})" oncontextmenu="event.preventDefault(); showPlayerStatusMenu(${p.player_id}, event);">
            <span class="bookmark-name">${seatLabel}${escapeHtml(p.player_name)}</span>
            <span style="display:flex;align-items:center;gap:4px;flex-wrap:wrap;">
                ${statusBadges}
                <span class="bookmark-role badge badge-${topRoleCls}">${escapeHtml(p.top_role_name || '-')}</span>
                ${canRemove ? `<span class="bookmark-remove" onclick="event.stopPropagation(); removePlayerFromGame(${p.player_id}, '${escapeHtml(p.player_name)}')" title="移除玩家">✕</span>` : ''}
            </span>
        </div>`;
    });
    container.innerHTML = html;
}

// 切换选中玩家（点击玩家显示预测结果覆盖层）
function selectPlayer(playerId) {
    // 如果点击的是当前已选中的玩家，则隐藏覆盖层
    if (selectedPlayerId === playerId) {
        hidePredictionCard();
        return;
    }
    // 否则显示该玩家的预测结果，并显示覆盖层
    selectedPlayerId = playerId;
    renderPlayerBookmarks();
    renderSelectedPlayerPrediction();
    // 显示预测结果覆盖层
    showPredictionOverlay();
}

// 显示预测结果覆盖层
function showPredictionOverlay() {
    const overlay = document.getElementById('prediction-overlay');
    if (overlay) overlay.classList.add('show');
}

// 隐藏预测结果覆盖层
function hidePredictionOverlay() {
    const overlay = document.getElementById('prediction-overlay');
    if (overlay) overlay.classList.remove('show');
}

// 隐藏预测结果卡片（关闭覆盖层）
function hidePredictionCard() {
    selectedPlayerId = null;
    renderPlayerBookmarks();
    hidePredictionOverlay();
}

// 从对局移除玩家
async function removePlayerFromGame(playerId, playerName) {
    if (!confirmAction(`确定要从对局中移除玩家「${playerName}」吗？该玩家的所有行为记录也将被删除。`)) return;
    const result = await api('DELETE', `/games/${gameId}/players/${playerId}`);
    if (result) {
        showToast(`玩家「${playerName}」已移除`, 'success');
        // 如果移除的是当前选中的玩家，清空选中
        if (selectedPlayerId === playerId) {
            selectedPlayerId = null;
        }
        await loadGame();
        await refreshPredictions();
    }
}

// 渲染选中玩家的详细预测结果
function renderSelectedPlayerPrediction() {
    const card = document.getElementById('selected-player-prediction-card');
    const container = document.getElementById('selected-player-prediction');
    const nameEl = document.getElementById('selected-player-name');
    const topRoleEl = document.getElementById('selected-player-top-role');

    const p = predictions.find(x => x.player_id === selectedPlayerId);
    if (!p) {
        return;
    }

    const seat = gamePlayers.find(gp => gp.player_id === p.player_id)?.seat_number;
    const seatLabel = seat ? `${seat}号 ` : '';
    nameEl.textContent = `${seatLabel}${p.player_name} 的身份预测`;
    topRoleEl.textContent = `${p.top_role_name || '-'} (${(p.top_probability * 100).toFixed(1)}%)`;
    const topCamp = p.all_probabilities && p.all_probabilities[0] ? p.all_probabilities[0].camp : '';
    topRoleEl.className = `badge badge-${getCampClass(topCamp)}`;

    let html = '<div class="prob-list">';
    p.all_probabilities.forEach(prob => {
        const cls = getCampClass(prob.camp);
        html += `<div class="prob-item">
            <div class="prob-item-label">
                <span>${escapeHtml(prob.role_name)} ${campBadge(prob.camp)}</span>
                <span>${(prob.probability * 100).toFixed(1)}%</span>
            </div>
            <div class="prob-bar"><div class="prob-bar-fill prob-${cls}" style="width:${prob.probability * 100}%"></div></div>
        </div>`;
    });
    html += '</div>';
    container.innerHTML = html;
}

// 刷新预测
async function refreshPredictions() {
    await api('POST', `/games/${gameId}/predictions/refresh`);
    await loadPredictions();
    showToast('预测已刷新', 'success');
}

// 阶段顺序定义（用于排序）
const PHASE_ORDER = {
    '夜间行动': 1,
    '警上发言': 2,
    '警徽投票': 3,
    '死讯公布': 4,
    '白天发言': 5,
    'PK发言': 6,
    '放逐投票': 7,
    '遗言': 8
};

// 渲染行为记录（按轮次+阶段分组，时间线样式）
function renderBehaviors(behaviors) {
    const container = document.getElementById('behavior-list');
    // 保存所有行为供筛选使用
    window._allBehaviors = behaviors;

    // 玩家筛选
    const filterPlayerId = document.getElementById('behavior-filter-player')?.value || '';
    let filtered = behaviors;
    if (filterPlayerId) {
        const pid = parseInt(filterPlayerId);
        filtered = behaviors.filter(b => b.actor_id === pid);
    }

    document.getElementById('behavior-count').textContent = `共 ${filtered.length} 条`;
    if (filtered.length === 0) {
        container.innerHTML = '<div class="empty-state"><p>暂无行为记录</p></div>';
        return;
    }

    // 按轮次分组
    const rounds = {};
    filtered.forEach(b => {
        const round = b.round_number || 0;  // 0表示未指定轮次
        if (!rounds[round]) rounds[round] = [];
        rounds[round].push(b);
    });

    // 按轮次排序
    const sortedRounds = Object.keys(rounds).map(Number).sort((a, b) => a - b);

    let html = '';
    let globalIndex = 1;  // 全局顺序编号

    sortedRounds.forEach(round => {
        const roundBehaviors = rounds[round];
        // 按阶段排序，阶段相同按创建时间排序
        roundBehaviors.sort((a, b) => {
            const phaseA = PHASE_ORDER[a.phase] || 99;
            const phaseB = PHASE_ORDER[b.phase] || 99;
            if (phaseA !== phaseB) return phaseA - phaseB;
            // 按创建时间排序
            return new Date(a.created_at) - new Date(b.created_at);
        });

        // 轮次标题
        const roundTitle = round === 0 ? '未指定轮次' : `第 ${round} 天`;
        html += `<div class="timeline-round">
            <div class="timeline-round-title">${roundTitle}</div>`;

        // 该轮的行为记录
        roundBehaviors.forEach(b => {
            const phaseInfo = b.phase || '';
            // 结果状态显示
            let resultStatusBadge = '';
            if (b.result_status === 'correct') {
                resultStatusBadge = '<span class="badge badge-good" title="行为结果正确">✓ 正确</span>';
            } else if (b.result_status === 'incorrect') {
                resultStatusBadge = '<span class="badge badge-bad" title="行为结果错误">✕ 错误</span>';
            }
            html += `<div class="timeline-item">
                <div class="timeline-dot"></div>
                <div class="timeline-content">
                    <div class="timeline-header">
                        <span class="timeline-index">#${globalIndex++}</span>
                        ${phaseInfo ? `<span class="badge badge-info">${escapeHtml(phaseInfo)}</span>` : ''}
                        ${resultStatusBadge}
                        ${b.actor_role_name ? `<span class="badge badge-good">声明:${escapeHtml(b.actor_role_name)}</span>` : ''}
                        ${b.actor_camp ? campBadge(b.actor_camp) : ''}
                    </div>
                    <div class="timeline-body">
                        <span class="behavior-actor">${escapeHtml(b.actor_name)}</span>
                        <span class="behavior-action">${escapeHtml(b.action_name)}</span>
                        ${b.target_name ? `<span class="behavior-target">→ ${escapeHtml(b.target_name)}</span>` : ''}
                        ${b.notes ? `<span class="behavior-notes" title="${escapeHtml(b.notes)}">📝</span>` : ''}
                    </div>
                    ${gameData.status === '进行中' ? `<span class="behavior-edit" onclick="editBehavior(${b.id})" title="编辑" style="cursor:pointer;color:#00f0ff;margin-right:8px;">✏️</span><span class="behavior-delete" onclick="deleteBehavior(${b.id})" title="删除">✕</span>` : ''}
                </div>
            </div>`;
        });

        html += '</div>';  // 结束timeline-round
    });

    container.innerHTML = html;
}

// 添加行为（批量）
async function addBehavior() {
    const actorId = document.getElementById('behavior-actor').value;
    if (!actorId) { showToast('请选择行为发起者', 'error'); return; }
    if (selectedActionIds.length === 0) { showToast('请至少选择一个行为', 'error'); return; }

    const data = {
        actor_id: parseInt(actorId),
        action_ids: selectedActionIds.map(id => parseInt(id))
    };
    const targetId = document.getElementById('behavior-target').value;
    const roleId = document.getElementById('behavior-role').value;
    const camp = document.getElementById('behavior-camp').value;
    const notes = document.getElementById('behavior-notes').value.trim();

    if (targetId) data.target_id = parseInt(targetId);
    if (roleId) data.actor_role_id = parseInt(roleId);
    if (camp) data.actor_camp = camp;
    // 自动使用当前游戏轮次和阶段
    if (currentGamePhase) {
        data.round_number = currentGamePhase.round;
        data.phase = currentGamePhase.phase;
    }
    if (notes) data.notes = notes;

    const result = await api('POST', `/games/${gameId}/behaviors/batch`, data);
    if (result) {
        const count = result.data ? result.data.created_count : selectedActionIds.length;
        showToast(`成功录入 ${count} 条行为`, 'success');
        // 只清空备注，保留行为发起者、行为目标、选中的行为、声明身份、声明阵营
        document.getElementById('behavior-notes').value = '';
        // 不重新加载整个页面，只刷新预测结果和行为记录
        await loadPredictions();
        // 重新加载行为记录
        const gameResult = await api('GET', '/games/' + gameId);
        if (gameResult && gameResult.data) {
            gameData = gameResult.data;
            renderBehaviors(gameData.behaviors || []);
        }
        // 重新加载系统推导事实
        await loadInferenceFacts();
    }
}

// 删除行为
async function deleteBehavior(id) {
    if (!confirmAction('确定删除这条行为记录吗？')) return;
    const result = await api('DELETE', '/behaviors/' + id);
    if (result) {
        showToast('行为已删除', 'success');
        await loadGame();
    }
}

// 添加玩家到对局（多选）
function showAddPlayerModal() {
    const list = document.getElementById('add-player-list');
    const addedIds = new Set(gamePlayers.map(gp => gp.player_id));

    if (allPlayers.length === 0) {
        list.innerHTML = '<div class="empty-state"><p>暂无玩家，请先去玩家管理页创建</p></div>';
        document.getElementById('add-player-modal').classList.add('show');
        return;
    }

    // 初始化临时勾选状态
    tempSelectedPlayers = {};
    // 清空搜索框
    document.getElementById('add-player-search').value = '';
    // 渲染玩家列表
    renderAddPlayerList(allPlayers, addedIds);
    updateSelectedCount();
    document.getElementById('add-player-modal').classList.add('show');
}

// 保存当前DOM中的临时勾选状态（搜索过滤前调用）
function saveTempSelectedState() {
    const checkboxes = document.querySelectorAll('#add-player-list input[type="checkbox"]:not(:disabled)');
    checkboxes.forEach(cb => {
        const playerId = parseInt(cb.value);
        if (!tempSelectedPlayers[playerId]) {
            tempSelectedPlayers[playerId] = { checked: false, seat_number: null };
        }
        tempSelectedPlayers[playerId].checked = cb.checked;
    });
    // 保存座位号
    const seatInputs = document.querySelectorAll('#add-player-list .seat-number-input');
    seatInputs.forEach(input => {
        const playerId = parseInt(input.dataset.playerId);
        if (!tempSelectedPlayers[playerId]) {
            tempSelectedPlayers[playerId] = { checked: false, seat_number: null };
        }
        tempSelectedPlayers[playerId].seat_number = input.value ? parseInt(input.value) : null;
    });
}

// 渲染玩家列表（可过滤）
function renderAddPlayerList(players, addedIds) {
    const list = document.getElementById('add-player-list');
    if (players.length === 0) {
        list.innerHTML = '<div class="empty-state"><p>没有找到匹配的玩家</p></div>';
        return;
    }
    let html = '';
    players.forEach(p => {
        const inGame = addedIds.has(p.id);
        // 获取临时勾选状态
        const tempState = tempSelectedPlayers[p.id];
        const isChecked = inGame ? true : (tempState && tempState.checked);
        // 获取座位号：优先使用临时状态，其次使用已在对局的座位号
        let seatValue = '';
        if (tempState && tempState.seat_number) {
            seatValue = tempState.seat_number;
        } else if (inGame) {
            const existingSeat = gamePlayers.find(gp => gp.player_id === p.id)?.seat_number;
            seatValue = existingSeat || '';
        }
        html += `<label style="display:flex;align-items:center;gap:8px;">
            <input type="checkbox" value="${p.id}" ${inGame ? 'checked disabled' : (isChecked ? 'checked' : '')} onchange="updateSelectedCount()">
            <span>${escapeHtml(p.name)}</span>
            <input type="number" class="seat-number-input" data-player-id="${p.id}" 
                value="${seatValue}" placeholder="座号" min="1" 
                style="width:60px;margin-left:auto;padding:4px 8px;font-size:13px;border:1px solid var(--border-color);border-radius:4px;background:var(--input-bg);color:var(--text-primary);">
            ${inGame ? '<span class="player-in-game">已在对局</span>' : ''}
        </label>`;
    });
    list.innerHTML = html;
}

// 搜索过滤玩家列表
function filterAddPlayerList() {
    // 搜索前先保存当前勾选状态
    saveTempSelectedState();
    const keyword = document.getElementById('add-player-search').value.trim().toLowerCase();
    const addedIds = new Set(gamePlayers.map(gp => gp.player_id));
    if (!keyword) {
        renderAddPlayerList(allPlayers, addedIds);
        updateSelectedCount();
        return;
    }
    const filtered = allPlayers.filter(p => matchByPinyin(p.name, keyword));
    renderAddPlayerList(filtered, addedIds);
    updateSelectedCount();
}

// 全选/全不选
function toggleAllPlayers(checked) {
    const checkboxes = document.querySelectorAll('#add-player-list input[type="checkbox"]:not(:disabled)');
    checkboxes.forEach(cb => { cb.checked = checked; });
    updateSelectedCount();
}

// 更新已选人数
function updateSelectedCount() {
    const checked = document.querySelectorAll('#add-player-list input[type="checkbox"]:checked:not(:disabled)');
    document.getElementById('selected-count').textContent = `已选 ${checked.length} 人`;
}

// 批量添加玩家到对局
async function addPlayerToGame() {
    // 最后保存一次状态
    saveTempSelectedState();
    // 从临时状态中获取所有勾选的玩家
    const addedIds = new Set(gamePlayers.map(gp => gp.player_id));
    const toAdd = [];
    for (const playerIdStr in tempSelectedPlayers) {
        const playerId = parseInt(playerIdStr);
        if (tempSelectedPlayers[playerId].checked && !addedIds.has(playerId)) {
            toAdd.push(playerId);
        }
    }

    if (toAdd.length === 0) {
        showToast('请至少选择一名玩家', 'error');
        return;
    }

    let successCount = 0;
    let failCount = 0;

    for (let i = 0; i < toAdd.length; i++) {
        const playerId = toAdd[i];
        // 从临时状态中获取座位号
        const seatNumber = tempSelectedPlayers[playerId]?.seat_number || null;
        const data = { player_id: playerId };
        if (seatNumber) data.seat_number = seatNumber;
        const result = await api('POST', `/games/${gameId}/players`, data);
        if (result) {
            successCount++;
        } else {
            failCount++;
        }
    }

    if (successCount > 0 || failCount === 0) {
        // 更新已在对局玩家的座位号（如果被修改了）
        const seatInputs = document.querySelectorAll('.seat-number-input');
        let seatUpdated = 0;
        for (const input of seatInputs) {
            const playerId = parseInt(input.dataset.playerId);
            const inGame = addedIds.has(playerId);
            if (!inGame) continue; // 只处理已在对局的玩家
            const existingSeat = gamePlayers.find(gp => gp.player_id === playerId)?.seat_number;
            const newSeat = input.value ? parseInt(input.value) : null;
            // 只有座位号发生变化时才更新
            if ((existingSeat || null) !== (newSeat || null)) {
                const result = await api('PUT', `/games/${gameId}/players/${playerId}/seat`, { seat_number: newSeat });
                if (result) seatUpdated++;
            }
        }
        let message = `成功添加 ${successCount} 名玩家`;
        if (seatUpdated > 0) message += `，更新 ${seatUpdated} 个座位号`;
        if (failCount > 0) message += `，${failCount} 名失败`;
        showToast(message, 'success');
        hideModal('add-player-modal');
        await loadGame();
    } else {
        showToast('添加失败，请重试', 'error');
    }
}

// 结束对局
async function finishGame() {
    if (!confirmAction('确定结束这局对局吗？结束后将不能再录入行为。')) return;
    const result = await api('POST', `/games/${gameId}/finish`);
    if (result) {
        showToast('对局已结束', 'success');
        await loadGame();
    }
}

// 显示确认对局模态框
async function showConfirmModal() {
    const container = document.getElementById('confirm-roles-list');
    
    // 获取当前版型的可用身份列表（含总数量）
    const result = await api('GET', `/games/${gameId}/available_roles`);
    let roleOptions = [];
    if (result && result.data && result.data.length > 0) {
        roleOptions = result.data;
    } else {
        // 降级：使用所有身份
        roleOptions = allRoles.map(r => ({
            id: r.id,
            name: r.name,
            camp: r.camp,
            total_count: 99,
            available_count: 99,
            available: true
        }));
    }
    
    // 跟踪每个身份已选择的数量
    let selectedCounts = {};
    roleOptions.forEach(r => {
        selectedCounts[r.id] = 0;
    });
    
    // 预填已设置的真实身份
    gamePlayers.forEach(gp => {
        if (gp.actual_role_id && selectedCounts[gp.actual_role_id] !== undefined) {
            selectedCounts[gp.actual_role_id]++;
        }
    });
    
    // 生成HTML
    let html = '';
    gamePlayers.forEach(gp => {
        const seat = gp.seat_number ? `${gp.seat_number}号 ` : '';
        html += `<div class="form-group">
            <label>${seat}${escapeHtml(gp.player_name)} 的真实身份</label>
            <select class="form-control confirm-role-select" data-player-id="${gp.player_id}" id="confirm-role-${gp.player_id}">
                <option value="">请选择身份</option>`;
        
        roleOptions.forEach(r => {
            const selected = gp.actual_role_id === r.id ? 'selected' : '';
            const remaining = r.total_count - selectedCounts[r.id];
            const isDisabled = remaining <= 0 && !selected;
            const disabledAttr = isDisabled ? 'disabled' : '';
            const displayText = `${escapeHtml(r.name)} (${r.camp}) - 剩余${remaining}个${isDisabled ? ' (已满)' : ''}`;
            html += `<option value="${r.id}" ${selected} ${disabledAttr}>${displayText}</option>`;
        });
        
        html += `</select></div>`;
    });
    container.innerHTML = html;
    
    // 为每个下拉框添加change事件，动态更新可用身份
    document.querySelectorAll('.confirm-role-select').forEach(select => {
        select.addEventListener('change', function() {
            const playerId = parseInt(this.dataset.playerId);
            const newRoleId = this.value ? parseInt(this.value) : null;
            const player = gamePlayers.find(gp => gp.player_id === playerId);
            const oldRoleId = player ? player.actual_role_id : null;
            
            // 更新已选择数量
            if (oldRoleId && selectedCounts[oldRoleId] !== undefined) {
                selectedCounts[oldRoleId]--;
            }
            if (newRoleId && selectedCounts[newRoleId] !== undefined) {
                selectedCounts[newRoleId]++;
            }
            
            // 更新player的actual_role_id
            if (player) {
                player.actual_role_id = newRoleId;
            }
            
            // 更新所有下拉框的选项
            document.querySelectorAll('.confirm-role-select').forEach(otherSelect => {
                const otherPlayerId = parseInt(otherSelect.dataset.playerId);
                const otherSelectedValue = otherSelect.value;
                const otherPlayer = gamePlayers.find(gp => gp.player_id === otherPlayerId);
                
                // 保留当前选中的值，重建选项
                let optionsHtml = '<option value="">请选择身份</option>';
                roleOptions.forEach(r => {
                    const isCurrentSelected = otherSelectedValue == r.id;
                    const remaining = r.total_count - selectedCounts[r.id];
                    const isDisabled = remaining <= 0 && !isCurrentSelected;
                    const disabledAttr = isDisabled ? 'disabled' : '';
                    const selectedAttr = isCurrentSelected ? 'selected' : '';
                    const displayText = `${escapeHtml(r.name)} (${r.camp}) - 剩余${remaining}个${isDisabled ? ' (已满)' : ''}`;
                    optionsHtml += `<option value="${r.id}" ${selectedAttr} ${disabledAttr}>${displayText}</option>`;
                });
                otherSelect.innerHTML = optionsHtml;
            });
        });
    });
    
    document.getElementById('confirm-modal').classList.add('show');
}

// 确认对局
async function confirmGame() {
    // 先设置所有玩家的真实身份
    for (const gp of gamePlayers) {
        const roleId = document.getElementById('confirm-role-' + gp.player_id).value;
        if (!roleId) {
            showToast(`请为 ${gp.player_name} 选择真实身份`, 'error');
            return;
        }
        await api('PUT', `/games/${gameId}/players/${gp.player_id}/role`, { actual_role_id: parseInt(roleId) });
    }
    // 确认对局
    const result = await api('POST', `/games/${gameId}/confirm`);
    if (result) {
        hideModal('confirm-modal');
        const score = result.data.score;
        showToast(`对局已确认！预测准确率: ${(score.accuracy*100).toFixed(1)}%`, 'success');
        // 显示打分结果
        document.getElementById('game-result').innerHTML = `
            <div style="background:#f0fdf4;padding:16px;border-radius:8px;border:1px solid #bbf7d0;">
                <h4 style="margin-bottom:8px;">📊 本局预测结果</h4>
                <p>准确率：<strong>${score.correct_count}/${score.total_players} = ${(score.accuracy*100).toFixed(1)}%</strong></p>
                <p style="font-size:13px;color:#666;">算法权重已更新，预测会越来越准确。</p>
            </div>`;
        await loadGame();
    }
}

// 查看打分
async function viewScores() {
    const result = await api('GET', `/games/${gameId}/scores`);
    const container = document.getElementById('scores-content');
    if (!result || !result.data) {
        container.innerHTML = '<p>暂无打分明细</p>';
    } else if (Array.isArray(result.data)) {
        container.innerHTML = '<p>暂无打分明细（对局确认后生成）</p>';
    } else {
        const d = result.data;
        let html = `<p style="margin-bottom:12px;">准确率：<strong>${d.correct_count}/${d.total_players} = ${(d.accuracy*100).toFixed(1)}%</strong></p>`;
        html += '<table class="table"><thead><tr><th>玩家</th><th>预测身份</th><th>真实身份</th><th>是否正确</th><th>置信度</th></tr></thead><tbody>';
        d.details.forEach(s => {
            html += `<tr>
                <td>${escapeHtml(s.player_name)}</td>
                <td>${escapeHtml(s.predicted_role_name || '-')}</td>
                <td>${escapeHtml(s.actual_role_name || '-')}</td>
                <td>${s.is_correct ? '<span style="color:#22c55e;">✅ 正确</span>' : '<span style="color:#ef4444;">❌ 错误</span>'}</td>
                <td>${(s.confidence*100).toFixed(1)}%</td>
            </tr>`;
        });
        html += '</tbody></table>';
        container.innerHTML = html;
    }
    document.getElementById('scores-modal').classList.add('show');
}

function hideModal(id) {
    document.getElementById(id).classList.remove('show');
}

// ============================================================
// 行为多选标签（逐级展开选择）
// ============================================================
let selectedActionIds = [];  // 已选中的行为ID列表
let currentActionPath = [];  // 当前导航路径，存储行为ID数组（如[一级ID, 二级ID]）
let actionMultiSelectInitialized = false;  // 标记是否已初始化（避免重复绑定事件）

function initActionMultiSelect() {
    const searchInput = document.getElementById('behavior-action-search');
    const tagsGrid = document.getElementById('action-tags-grid');
    if (!searchInput || !tagsGrid) return;

    // 只在第一次初始化时绑定事件，避免重复绑定
    if (!actionMultiSelectInitialized) {
        // 输入时实时过滤（搜索时重置路径，显示所有匹配结果）
        searchInput.addEventListener('input', (e) => {
            const keyword = e.target.value.trim().toLowerCase();
            if (keyword) {
                currentActionPath = [];  // 搜索时回到根目录
            }
            renderActionTags(keyword);
        });

        // 事件委托：点击标签
        tagsGrid.addEventListener('click', (e) => {
            // 点击展开箭头
            const expandBtn = e.target.closest('.action-expand-btn');
            if (expandBtn) {
                e.stopPropagation();
                const actionId = parseInt(expandBtn.dataset.id);
                currentActionPath.push(actionId);
                document.getElementById('behavior-action-search').value = '';
                renderActionTags('');
                return;
            }
            // 点击返回按钮
            const backBtn = e.target.closest('.action-back-btn');
            if (backBtn) {
                e.stopPropagation();
                currentActionPath.pop();
                renderActionTags('');
                return;
            }
            // 点击面包屑
            const crumb = e.target.closest('.breadcrumb-item');
            if (crumb) {
                e.stopPropagation();
                const level = parseInt(crumb.dataset.level);
                currentActionPath = currentActionPath.slice(0, level);
                renderActionTags('');
                return;
            }
            // 点击行为标签 = 选择/取消选择
            const tag = e.target.closest('.action-tag');
            if (!tag) return;
            const id = parseInt(tag.dataset.id);
            toggleAction(id);
        });

        actionMultiSelectInitialized = true;
    }

    // 每次都重新渲染标签（保留当前导航路径和选中状态）
    const currentKeyword = searchInput.value.trim().toLowerCase();
    renderActionTags(currentKeyword);
}

function renderActionTags(keyword) {
    const grid = document.getElementById('action-tags-grid');
    if (!grid) return;

    // 搜索模式：显示所有匹配的行为（不分级）
    if (keyword) {
        const filtered = allActions.filter(a =>
            a.name.toLowerCase().includes(keyword) ||
            (a.description && a.description.toLowerCase().includes(keyword))
        );
        if (filtered.length === 0) {
            grid.innerHTML = '<div class="empty-state"><p>未找到匹配的行为</p></div>';
            updateSelectedActionsInfo();
            return;
        }
        let html = '';
        filtered.forEach(a => {
            html += renderActionTagHtml(a, 0, false);
        });
        grid.innerHTML = html;
        updateSelectedActionsInfo();
        return;
    }

    // 逐级导航模式
    const currentParentId = currentActionPath.length > 0
        ? currentActionPath[currentActionPath.length - 1]
        : null;

    // 获取当前级别的行为
    const currentActions = allActions.filter(a => a.parent_id === currentParentId);

    if (currentActions.length === 0 && currentParentId === null) {
        grid.innerHTML = '<div class="empty-state"><p>暂无行为</p></div>';
        updateSelectedActionsInfo();
        return;
    }

    let html = '';

    // 面包屑导航（非根目录时显示）
    if (currentActionPath.length > 0) {
        html += '<div class="action-breadcrumb">';
        html += '<span class="action-back-btn" title="返回上一级">← 返回</span>';
        html += '<span class="breadcrumb-item" data-level="0">📁 根目录</span>';
        currentActionPath.forEach((actionId, index) => {
            const action = allActions.find(a => a.id === actionId);
            if (action) {
                html += '<span class="breadcrumb-sep">/</span>';
                html += `<span class="breadcrumb-item" data-level="${index + 1}">${escapeHtml(action.name)}</span>`;
            }
        });
        html += '</div>';
    }

    // 如果当前目录没有子行为，提示
    if (currentActions.length === 0) {
        html += '<div class="empty-state"><p>此目录下暂无子行为</p></div>';
    } else {
        // 渲染当前级别的行为
        currentActions.forEach(a => {
            const hasChildren = allActions.some(x => x.parent_id === a.id);
            html += renderActionTagHtml(a, currentActionPath.length, hasChildren);
        });
    }

    grid.innerHTML = html;
    updateSelectedActionsInfo();
}

// 渲染单个行为标签的HTML
function renderActionTagHtml(a, level, hasChildren) {
    const isSelected = selectedActionIds.includes(a.id);
    return `<div class="action-tag ${isSelected ? 'selected' : ''} ${level > 0 ? 'child-tag' : ''}" data-id="${a.id}">
        <span class="action-tag-name">${escapeHtml(a.name)}</span>
        ${hasChildren ? `<span class="action-expand-btn" data-id="${a.id}" title="查看子行为">›</span>` : ''}
        ${isSelected ? '<span class="action-tag-check">✓</span>' : ''}
    </div>`;
}

function toggleAction(id) {
    const index = selectedActionIds.indexOf(id);
    if (index >= 0) {
        selectedActionIds.splice(index, 1);
    } else {
        selectedActionIds.push(id);
    }
    renderActionTags(document.getElementById('behavior-action-search').value.trim().toLowerCase());
}

function updateSelectedActionsInfo() {
    const info = document.getElementById('selected-actions-info');
    if (info) {
        if (selectedActionIds.length === 0) {
            info.innerHTML = '<span>未选择行为</span>';
            info.className = 'selected-actions-info';
        } else {
            // 获取已选行为的名称
            const selectedNames = selectedActionIds.map(id => {
                const action = allActions.find(a => a.id === id);
                return action ? action.name : `未知行为(${id})`;
            });
            // 显示可删除的行为标签
            let html = '<span style="margin-right:8px;">已选 ' + selectedActionIds.length + ' 个：</span>';
            selectedActionIds.forEach((id, index) => {
                const action = allActions.find(a => a.id === id);
                const name = action ? action.name : `未知行为(${id})`;
                html += '<span class="selected-action-tag" style="display:inline-flex;align-items:center;gap:4px;padding:2px 8px;margin:2px;background:rgba(0,240,255,0.15);border:1px solid rgba(0,240,255,0.3);border-radius:12px;font-size:12px;">';
                html += '<span>' + escapeHtml(name) + '</span>';
                html += '<span onclick="removeSelectedAction(' + id + ')" style="cursor:pointer;color:#ef4444;font-weight:bold;margin-left:4px;" title="删除">✕</span>';
                html += '</span>';
            });
            // 添加一键清空按钮
            html += '<span onclick="clearSelectedActions()" style="cursor:pointer;color:#f59e0b;font-size:12px;margin-left:8px;text-decoration:underline;" title="一键清空">清空全部</span>';
            info.innerHTML = html;
            info.className = 'selected-actions-info has-selection';
            // 添加title属性，鼠标悬停显示全部
            info.title = '已选行为：' + selectedNames.join('、');
        }
    }
}

function removeSelectedAction(id) {
    const index = selectedActionIds.indexOf(id);
    if (index > -1) {
        selectedActionIds.splice(index, 1);
    }
    renderActionTags(document.getElementById('behavior-action-search').value.trim().toLowerCase());
}

function clearSelectedActions() {
    selectedActionIds = [];
    currentActionPath = [];
    document.getElementById('behavior-action-search').value = '';
    renderActionTags('');
}

// 展开/收起高级选项
function toggleAdvancedOptions() {
    const content = document.getElementById('advanced-content');
    const toggle = document.querySelector('.advanced-toggle');
    if (content.style.display === 'none') {
        content.style.display = 'block';
        toggle.classList.add('expanded');
    } else {
        content.style.display = 'none';
        toggle.classList.remove('expanded');
    }
}

// 平滑滚动到行为录入表单（手机端浮动按钮）
function scrollToBehaviorForm() {
    const card = document.getElementById('behavior-form-card');
    if (card) {
        card.scrollIntoView({ behavior: 'smooth', block: 'start' });
        // 滚动后短暂高亮表单
        card.style.transition = 'box-shadow 0.3s';
        card.style.boxShadow = '0 0 30px rgba(0, 240, 255, 0.4)';
        setTimeout(() => {
            card.style.boxShadow = '';
        }, 1500);
    }
}

// ============================================================
// 多情景假设推理
// ============================================================

// 显示情景管理模态框
async function showScenarioModal() {
    document.getElementById('new-scenario-name').value = '';
    editingScenarioId = null;
    document.getElementById('scenario-assignments-section').style.display = 'none';
    await loadScenarios();
    document.getElementById('scenario-modal').classList.add('show');
}

// 加载情景列表
async function loadScenarios() {
    const result = await api('GET', `/games/${gameId}/scenarios`);
    if (result && result.data) {
        scenarios = result.data;
        renderScenarioList();
        renderScenarioTabs();
    }
}

// 渲染情景列表（模态框中）
function renderScenarioList() {
    const container = document.getElementById('scenario-list');
    if (scenarios.length === 0) {
        container.innerHTML = '<div class="empty-state"><p>暂无情景，创建第一个情景开始多情景推理</p></div>';
        return;
    }
    let html = '';
    scenarios.forEach(s => {
        const assignmentCount = s.assignments ? s.assignments.length : 0;
        const isEditing = editingScenarioId === s.id;
        html += `<div class="scenario-item ${isEditing ? 'active' : ''}" onclick="selectScenarioForEdit(${s.id})">
            <div class="scenario-item-header">
                <span class="scenario-item-name">${escapeHtml(s.name)}</span>
                <span class="scenario-item-count">${assignmentCount}个假设</span>
            </div>
            ${s.description ? `<div class="scenario-item-desc">${escapeHtml(s.description)}</div>` : ''}
            <button class="btn btn-danger btn-sm" onclick="event.stopPropagation();deleteScenario(${s.id})" style="margin-top:8px;">删除</button>
        </div>`;
    });
    container.innerHTML = html;
}

// 渲染情景切换标签（预测结果区域）
function renderScenarioTabs() {
    const container = document.getElementById('scenario-tabs');
    if (!container) return;
    if (scenarios.length === 0) {
        container.style.display = 'none';
        return;
    }
    container.style.display = 'flex';
    let html = `<div class="scenario-tab ${currentScenarioId === '' ? 'active' : ''}" data-scenario-id="" onclick="switchScenario('')">综合预测</div>`;
    scenarios.forEach(s => {
        html += `<div class="scenario-tab ${currentScenarioId == s.id ? 'active' : ''}" data-scenario-id="${s.id}" onclick="switchScenario('${s.id}')">${escapeHtml(s.name)}</div>`;
    });
    container.innerHTML = html;
}

// 切换预测情景
async function switchScenario(scenarioId) {
    currentScenarioId = scenarioId;
    renderScenarioTabs();
    await loadPredictions();
    // 如果有选中的玩家，重新渲染其预测结果
    if (selectedPlayerId) {
        renderSelectedPlayerPrediction();
    }
}

// 创建新情景
async function createScenario() {
    const name = document.getElementById('new-scenario-name').value.trim();
    if (!name) {
        showToast('请输入情景名称', 'error');
        return;
    }
    const result = await api('POST', `/games/${gameId}/scenarios`, { name });
    if (result) {
        showToast('情景创建成功', 'success');
        document.getElementById('new-scenario-name').value = '';
        await loadScenarios();
        // 自动选中新创建的情景进行编辑
        selectScenarioForEdit(result.data.id);
    }
}

// 删除情景
async function deleteScenario(scenarioId) {
    if (!confirm('确定删除这个情景吗？')) return;
    const result = await api('DELETE', `/scenarios/${scenarioId}`);
    if (result) {
        showToast('情景已删除', 'success');
        if (currentScenarioId == scenarioId) {
            currentScenarioId = '';
        }
        if (editingScenarioId === scenarioId) {
            editingScenarioId = null;
            document.getElementById('scenario-assignments-section').style.display = 'none';
        }
        await loadScenarios();
        await loadPredictions();
    }
}

// 选择情景进行编辑
async function selectScenarioForEdit(scenarioId) {
    editingScenarioId = scenarioId;
    const scenario = scenarios.find(s => s.id === scenarioId);
    if (scenario) {
        document.getElementById('current-scenario-name').textContent = scenario.name;
    }
    document.getElementById('scenario-assignments-section').style.display = 'block';
    // 填充玩家和身份下拉框
    const playerSelect = document.getElementById('assignment-player');
    playerSelect.innerHTML = '<option value="">选择玩家</option>';
    gamePlayers.forEach(gp => {
        playerSelect.innerHTML += `<option value="${gp.player_id}">${escapeHtml(gp.player_name)}</option>`;
    });
    const roleOptions = document.getElementById('assignment-role-options');
    roleOptions.innerHTML = '';
    allRoles.forEach(r => {
        roleOptions.innerHTML += `<option value="${r.id}">${escapeHtml(r.name)} (${r.camp})</option>`;
    });
    renderScenarioList();
    // 玩家选择下拉框增加搜索功能
    setTimeout(() => {
        initSearchableSelect('assignment-player', '搜索玩家...');
    }, 50);
    await loadAssignments();
}

// 加载当前情景的假设身份
async function loadAssignments() {
    if (!editingScenarioId) return;
    const scenario = scenarios.find(s => s.id === editingScenarioId);
    if (scenario && scenario.assignments) {
        renderAssignmentList(scenario.assignments);
    }
}

// 渲染假设身份列表
function renderAssignmentList(assignments) {
    const container = document.getElementById('assignment-list');
    if (!assignments || assignments.length === 0) {
        container.innerHTML = '<div class="empty-state"><p>暂无假设身份，添加第一个假设</p></div>';
        return;
    }
    let html = '';
    assignments.forEach(a => {
        // 判断是阵营假设还是具体身份
        let roleDisplay = '';
        let badgeClass = 'badge-info';
        if (a.camp) {
            roleDisplay = `${a.camp}（阵营）`;
            badgeClass = a.camp === '好人' ? 'badge-success' : 'badge-danger';
        } else {
            roleDisplay = a.role_name;
        }
        html += `<div class="assignment-item">
            <span class="assignment-player">${escapeHtml(a.player_name)}</span>
            <span class="assignment-arrow">→</span>
            <span class="assignment-role badge ${badgeClass}">${escapeHtml(roleDisplay)}</span>
            <span class="assignment-confidence">置信度: ${(a.confidence * 100).toFixed(0)}%</span>
            <button class="btn btn-danger btn-sm" onclick="deleteAssignment(${a.id})">删除</button>
        </div>`;
    });
    container.innerHTML = html;
}

// 添加假设身份
async function addAssignment() {
    if (!editingScenarioId) {
        showToast('请先选择一个情景', 'error');
        return;
    }
    const playerId = document.getElementById('assignment-player').value;
    const roleValue = document.getElementById('assignment-role').value;
    const confidence = parseFloat(document.getElementById('assignment-confidence').value) || 0.9;
    if (!playerId || !roleValue) {
        showToast('请选择玩家和身份/阵营', 'error');
        return;
    }
    // 判断是阵营假设还是具体身份
    let roleId = null;
    let camp = null;
    if (roleValue.startsWith('camp:')) {
        camp = roleValue.substring(5);  // 去掉"camp:"前缀
    } else {
        roleId = parseInt(roleValue);
    }
    const result = await api('POST', `/scenarios/${editingScenarioId}/assignments`, {
        player_id: parseInt(playerId),
        role_id: roleId,
        camp: camp,
        confidence: confidence
    });
    if (result) {
        showToast('假设添加成功', 'success');
        await loadScenarios();
        // 保持当前编辑的情景
        selectScenarioForEdit(editingScenarioId);
    }
}

// 删除假设身份
async function deleteAssignment(assignmentId) {
    const result = await api('DELETE', `/scenario_assignments/${assignmentId}`);
    if (result) {
        showToast('假设身份已删除', 'success');
        await loadScenarios();
        selectScenarioForEdit(editingScenarioId);
    }
}

// 加载铁狼/铁好人
async function loadInvariantPlayers() {
    const banner = document.getElementById('invariant-players-banner');
    if (!banner || scenarios.length === 0) {
        if (banner) banner.style.display = 'none';
        return;
    }
    const result = await api('GET', `/games/${gameId}/invariant_players`);
    if (result && result.data) {
        const { iron_wolves, iron_goods } = result.data;
        if (iron_wolves.length === 0 && iron_goods.length === 0) {
            banner.style.display = 'none';
            return;
        }
        let html = '<div style="padding:10px 12px;border-radius:8px;font-size:13px;">';
        if (iron_wolves.length > 0) {
            html += `<div style="color:var(--neon-red);margin-bottom:6px;">🐺 铁狼（所有情景下狼人概率>90%）：${iron_wolves.map(w => escapeHtml(w.player_name)).join('、')}</div>`;
        }
        if (iron_goods.length > 0) {
            html += `<div style="color:var(--neon-green);">✨ 铁好人（所有情景下好人概率>90%）：${iron_goods.map(g => escapeHtml(g.player_name)).join('、')}</div>`;
        }
        html += '</div>';
        banner.innerHTML = html;
        banner.style.display = 'block';
    }
}

// ============================================================
// 玩家关系图与回溯推断（第二阶段）
// ============================================================

// 显示关系图模态框
async function showRelationshipModal() {
    // 填充回溯推断的玩家下拉框
    const playerSelect = document.getElementById('backtrack-player');
    playerSelect.innerHTML = '<option value="">选择玩家</option>';
    gamePlayers.forEach(gp => {
        playerSelect.innerHTML += `<option value="${gp.player_id}">${escapeHtml(gp.player_name)}</option>`;
    });
    // 清空之前的结果
    document.getElementById('relationship-list').innerHTML = '<div class="empty-state"><p>点击"重新提取关系"按钮加载</p></div>';
    document.getElementById('backtrack-result').innerHTML = '';
    document.getElementById('relationship-count').textContent = '';
    hideModal('relationship-modal');
    document.getElementById('relationship-modal').classList.add('show');
    // 玩家选择下拉框增加搜索功能
    setTimeout(() => {
        initSearchableSelect('backtrack-player', '搜索玩家...');
    }, 100);
}

// 提取关系
async function extractRelationships() {
    const result = await api('POST', `/games/${gameId}/relationships/extract`);
    if (result) {
        showToast(`成功提取 ${result.data.extracted_count} 条关系`, 'success');
        await loadRelationships();
    }
}

// 加载关系列表
async function loadRelationships() {
    const result = await api('GET', `/games/${gameId}/relationships`);
    if (result && result.data) {
        renderRelationshipList(result.data.edges);
        document.getElementById('relationship-count').textContent = `共 ${result.data.edges.length} 条关系`;
    }
}

// 渲染关系列表
function renderRelationshipList(edges) {
    const container = document.getElementById('relationship-list');
    if (!edges || edges.length === 0) {
        container.innerHTML = '<div class="empty-state"><p>暂无关系数据，请先录入有目标对象的行为</p></div>';
        return;
    }
    // 按玩家分组
    const bySource = {};
    edges.forEach(e => {
        if (!bySource[e.source]) bySource[e.source] = [];
        bySource[e.source].push(e);
    });
    let html = '';
    for (const sourceId in bySource) {
        const sourcePlayer = gamePlayers.find(gp => gp.player_id == sourceId);
        const sourceName = sourcePlayer ? sourcePlayer.player_name : `玩家${sourceId}`;
        html += `<div style="margin-bottom:12px;">
            <div style="font-weight:600;color:var(--neon-cyan);margin-bottom:6px;">${escapeHtml(sourceName)} 的关系：</div>`;
        bySource[sourceId].forEach(e => {
            const targetPlayer = gamePlayers.find(gp => gp.player_id == e.target);
            const targetName = targetPlayer ? targetPlayer.player_name : `玩家${e.target}`;
            const directionClass = e.direction > 0 ? 'badge-success' : 'badge-danger';
            const directionIcon = e.direction > 0 ? '🛡️' : '⚔️';
            html += `<div style="padding:6px 10px;background:rgba(15,23,42,0.5);border-radius:6px;margin-bottom:4px;display:flex;align-items:center;gap:8px;">
                <span class="badge ${directionClass}">${directionIcon} ${escapeHtml(e.type_name)}</span>
                <span>→</span>
                <span style="font-weight:600;">${escapeHtml(targetName)}</span>
                <span style="color:var(--text-muted);font-size:12px;margin-left:auto;">强度: ${(e.strength * 100).toFixed(0)}%</span>
            </div>`;
        });
        html += '</div>';
    }
    container.innerHTML = html;
}

// 运行回溯推断
async function runBacktrack() {
    const playerId = document.getElementById('backtrack-player').value;
    const camp = document.getElementById('backtrack-camp').value;
    if (!playerId) {
        showToast('请选择玩家', 'error');
        return;
    }
    const result = await api('POST', `/games/${gameId}/backtrack`, {
        player_id: parseInt(playerId),
        camp: camp
    });
    if (result) {
        renderBacktrackResult(result.data);
    }
}

// 渲染回溯推断结果
function renderBacktrackResult(data) {
    const container = document.getElementById('backtrack-result');
    const adjustments = data.adjustments || [];
    if (adjustments.length === 0) {
        container.innerHTML = '<div class="empty-state"><p>未发现可回溯的关系，请先录入更多有目标对象的行为</p></div>';
        return;
    }
    const confirmedPlayer = gamePlayers.find(gp => gp.player_id == data.confirmed_player_id);
    const confirmedName = confirmedPlayer ? confirmedPlayer.player_name : `玩家${data.confirmed_player_id}`;
    let html = `<div style="padding:12px;background:rgba(0,240,255,0.05);border-radius:8px;margin-bottom:12px;">
        <div style="font-weight:600;margin-bottom:8px;">回溯推断结果（确认 ${escapeHtml(confirmedName)} 是 ${data.confirmed_camp}）：</div>
        <div style="font-size:13px;color:var(--text-secondary);">发现 ${adjustments.length} 条修正建议</div>
    </div>`;
    adjustments.forEach(a => {
        const isWolfUp = a.adjustment === 'wolf_up';
        const badgeClass = isWolfUp ? 'badge-danger' : 'badge-success';
        const badgeText = isWolfUp ? '🐺 狼人概率↑' : '✨ 好人概率↑';
        html += `<div style="padding:10px 12px;background:rgba(15,23,42,0.5);border-radius:8px;margin-bottom:8px;border-left:3px solid ${isWolfUp ? 'var(--neon-red)' : 'var(--neon-green)'};">
            <div style="display:flex;align-items:center;gap:10px;margin-bottom:4px;">
                <span style="font-weight:600;">${escapeHtml(a.player_name)}</span>
                <span class="badge ${badgeClass}">${badgeText}</span>
                <span style="color:var(--text-muted);font-size:12px;margin-left:auto;">关系强度: ${(a.strength * 100).toFixed(0)}%</span>
            </div>
            <div style="font-size:13px;color:var(--text-secondary);">${escapeHtml(a.reason)}</div>
        </div>`;
    });
    container.innerHTML = html;
}


// ============================================================
// 游戏流程阶段控制
// ============================================================

// 加载当前阶段
async function loadCurrentPhase() {
    const result = await api('GET', '/games/' + gameId + '/phase');
    if (result && result.data) {
        const phase = result.data;
        currentGamePhase = phase;  // 保存到全局变量
        document.getElementById('current-phase-display').textContent =
            '第' + phase.round + '轮 ' + phase.display;
        // 显示投票权提示
        showVotingRightsHint(phase.phase);
    }
}

// 显示投票权提示
function showVotingRightsHint(phase) {
    // 移除已有的提示
    const existingHint = document.getElementById('voting-rights-hint');
    if (existingHint) existingHint.remove();

    let hintText = '';
    let hintColor = '';

    if (phase === '警徽投票') {
        // 计算可以投票的玩家（未上警的玩家）
        const canVote = gamePlayers.filter(gp => !gp.is_on_police && gp.is_alive !== false);
        const cannotVote = gamePlayers.filter(gp => gp.is_on_police && gp.is_alive !== false);
        hintText = `🗳️ 警徽投票：只有未上警的玩家可以投票。当前可投票 ${canVote.length} 人，上警不可投票 ${cannotVote.length} 人。`;
        hintColor = 'rgba(0, 240, 255, 0.1)';
    } else if (phase === '放逐投票') {
        // 计算可以投票的玩家（存活的玩家）
        const canVote = gamePlayers.filter(gp => gp.is_alive !== false);
        const cannotVote = gamePlayers.filter(gp => gp.is_alive === false);
        hintText = `🚪 放逐投票：只有存活的玩家可以投票。当前可投票 ${canVote.length} 人，已出局 ${cannotVote.length} 人。`;
        hintColor = 'rgba(239, 68, 68, 0.1)';
    } else if (phase === 'PK发言') {
        hintText = '⚔️ PK发言环节：平票后追加PK发言，PK台上的玩家不能投票。';
        hintColor = 'rgba(251, 191, 36, 0.1)';
    } else if (phase === '上警') {
        hintText = '🚔 上警环节：请点击"上警设置"按钮，选择上警的玩家。上警玩家不能投警徽票。';
        hintColor = 'rgba(168, 85, 247, 0.1)';
    }

    if (hintText) {
        const flowControl = document.getElementById('game-flow-control');
        if (flowControl) {
            const hint = document.createElement('div');
            hint.id = 'voting-rights-hint';
            hint.style.cssText = `
                margin-top: 12px;
                padding: 10px 12px;
                background: ${hintColor};
                border-radius: 6px;
                font-size: 13px;
                color: var(--text-primary);
                line-height: 1.5;
            `;
            hint.textContent = hintText;
            flowControl.appendChild(hint);
        }
    }
}

// 加载系统推导事实
async function loadInferenceFacts() {
    const result = await api('GET', '/games/' + gameId + '/logic_inference');
    const banner = document.getElementById('inference-facts-banner');
    const content = document.getElementById('inference-facts-content');
    
    if (!banner || !content) {
        return;
    }
    
    if (!result || !result.data) {
        banner.style.display = 'none';
        return;
    }
    
    const data = result.data;
    const confirmed = data.confirmed_identities || [];
    const updatedBehaviors = data.updated_behaviors || [];
    
    if (confirmed.length === 0 && updatedBehaviors.length === 0) {
        banner.style.display = 'none';
        return;
    }
    
    let html = '';
    
    // 已确认身份
    if (confirmed.length > 0) {
        html += '<div style="margin-bottom:10px;">';
        html += '<div style="font-size:12px;color:#22c55e;margin-bottom:6px;font-weight:600;">✅ 已确认身份（' + confirmed.length + '）</div>';
        confirmed.forEach(c => {
            const roleText = c.role_name || c.camp || '未知';
            const reasonText = c.reason ? '（' + escapeHtml(c.reason) + '）' : '';
            html += '<div style="font-size:12px;color:#cbd5e1;padding:3px 0;">• ' + escapeHtml(c.player_name) + ' → <strong style="color:#22c55e;">' + escapeHtml(roleText) + '</strong>' + reasonText + '</div>';
        });
        html += '</div>';
    }
    
    // 自动修正的行为
    if (updatedBehaviors.length > 0) {
        html += '<div style="margin-bottom:10px;">';
        html += '<div style="font-size:12px;color:#22c55e;margin-bottom:6px;font-weight:600;">🔄 行为自动修正（' + updatedBehaviors.length + '）</div>';
        updatedBehaviors.forEach(b => {
            const statusText = b.result_status === 'correct' ? '✅ 正确' : '❌ 错误';
            const statusColor = b.result_status === 'correct' ? '#22c55e' : '#ef4444';
            const targetText = b.target_name ? ' → ' + escapeHtml(b.target_name) : '';
            html += '<div style="font-size:12px;color:#cbd5e1;padding:3px 0;">• ' + escapeHtml(b.actor_name) + ' ' + escapeHtml(b.action_name) + targetText + ' → <strong style="color:' + statusColor + ';">' + statusText + '</strong></div>';
        });
        html += '</div>';
    }
    
    content.innerHTML = html;
    banner.style.display = 'block';
    // 显示数量
    const countEl = document.getElementById('inference-facts-count');
    if (countEl) {
        const total = confirmed.length + updatedBehaviors.length;
        countEl.textContent = `（共 ${total} 条）`;
    }
    // 保持内容折叠状态（默认折叠）
    content.style.display = 'none';
    const toggle = document.getElementById('inference-facts-toggle');
    if (toggle) toggle.textContent = '▼';
}

// 手动触发逻辑推理
async function runLogicInference() {
    showToast('正在运行逻辑推理...', 'info');
    const result = await api('POST', '/games/' + gameId + '/logic_inference/run');
    if (result) {
        const facts = result.data?.results?.derived_facts || [];
        showToast('逻辑推理完成，推导了' + facts.length + '条事实', 'success');
        await loadInferenceFacts();
        await loadPredictions();
    }
}

// 推进到下一阶段
async function advancePhase() {
    if (!confirm('确定推进到下一环节吗？')) return;
    const result = await api('POST', '/games/' + gameId + '/phase/advance', {});
    if (result) {
        showToast(result.message, 'success');
        await loadCurrentPhase();
    }
}

// 狼人自爆
async function wolfSelfExplode() {
    if (!confirm('确定狼人自爆，直接进入下一个黑夜吗？')) return;
    const result = await api('POST', '/games/' + gameId + '/phase/self_explode', {});
    if (result) {
        showToast(result.message, 'success');
        await loadCurrentPhase();
    }
}

// 显示阶段调整模态框
function showPhaseAdjustModal() {
    const currentText = document.getElementById('current-phase-display').textContent;
    const phaseSelect = document.getElementById('adjust-phase-select');
    const roundInput = document.getElementById('adjust-round-input');
    const match = currentText.match(/第(\d+)轮\s+(.+)/);
    if (match) {
        roundInput.value = match[1];
        const phaseName = match[2].replace(/[^\u4e00-\u9fa5]/g, '');
        for (let i = 0; i < phaseSelect.options.length; i++) {
            if (phaseSelect.options[i].value.indexOf(phaseName) >= 0 || phaseName.indexOf(phaseSelect.options[i].value) >= 0) {
                phaseSelect.value = phaseSelect.options[i].value;
                break;
            }
        }
    }
    hideModal('phase-adjust-modal');
    document.getElementById('phase-adjust-modal').classList.add('show');
}

// 确认阶段调整
async function confirmPhaseAdjust() {
    const phase = document.getElementById('adjust-phase-select').value;
    const round = parseInt(document.getElementById('adjust-round-input').value) || 1;
    const result = await api('PUT', '/games/' + gameId + '/phase', {
        phase: phase,
        round: round
    });
    if (result) {
        showToast(result.message, 'success');
        hideModal('phase-adjust-modal');
        await loadCurrentPhase();
    }
}


// ============================================================
// 确认身份（逻辑基点）
// ============================================================

// 显示确认身份模态框
async function showConfirmIdentityModal() {
    if (!selectedPlayerId) {
        showToast('请先选择一个玩家', 'error');
        return;
    }
    const player = allPlayers.find(p => p.id === selectedPlayerId);
    document.getElementById('confirm-identity-player-name').textContent = player ? player.name : '';

    // 获取可用身份列表（考虑版型配置和已确认数量）
    const result = await api('GET', '/games/' + gameId + '/available_roles');
    const roleSelect = document.getElementById('confirm-role-select');
    roleSelect.innerHTML = '';

    if (result && result.data && result.data.length > 0) {
        result.data.forEach(role => {
            const opt = document.createElement('option');
            opt.value = role.id;
            if (role.available) {
                opt.textContent = role.name + ' (' + role.camp + ') - 剩余' + role.available_count + '个';
            } else {
                opt.textContent = role.name + ' (' + role.camp + ') - 已满员';
                opt.disabled = true;
                opt.style.color = '#999';
            }
            roleSelect.appendChild(opt);
        });
    } else {
        // 降级：显示所有身份
        allRoles.forEach(role => {
            const opt = document.createElement('option');
            opt.value = role.id;
            opt.textContent = role.name + ' (' + role.camp + ')';
            roleSelect.appendChild(opt);
        });
    }

    hideModal('confirm-identity-modal');
    document.getElementById('confirm-identity-modal').classList.add('show');
}

// 切换确认类型字段
function toggleConfirmIdentityFields() {
    const type = document.getElementById('confirm-identity-type').value;
    document.getElementById('confirm-role-group').style.display = type === 'role' ? 'block' : 'none';
    document.getElementById('confirm-camp-group').style.display = type === 'camp' ? 'block' : 'none';
}

// 提交确认身份
async function submitConfirmIdentity() {
    if (!selectedPlayerId) return;
    const type = document.getElementById('confirm-identity-type').value;
    const reason = document.getElementById('confirm-reason-input').value.trim();
    const data = {
        player_id: selectedPlayerId,
        reason: reason
    };
    if (type === 'role') {
        data.role_id = parseInt(document.getElementById('confirm-role-select').value);
    } else {
        data.camp = document.getElementById('confirm-camp-select').value;
    }
    const result = await api('POST', '/games/' + gameId + '/confirmed_identities', data);
    if (result) {
        showToast(result.message, 'success');
        hideModal('confirm-identity-modal');
        document.getElementById('confirm-reason-input').value = '';
        await loadPredictions();
    }
}

// 加载确认身份列表（在预测结果中显示标记）
async function loadConfirmedIdentities() {
    const result = await api('GET', '/games/' + gameId + '/confirmed_identities');
    if (result && result.data) {
        return result.data;
    }
    return [];
}

// 删除确认身份
async function deleteConfirmedIdentity(identityId) {
    if (!confirm('确定删除这个确认身份吗？删除后预测结果会恢复正常计算。')) return;
    const result = await api('DELETE', '/confirmed_identities/' + identityId);
    if (result) {
        showToast(result.message, 'success');
        await loadPredictions();
    }
}


// ============================================================
// 棰勮█瀹舵煡楠屾帹瀵?

// ============================================================
// 预言家查验推导
// ============================================================

// 加载预言家查验推导信息
async function loadProphetInference() {
    const result = await api('GET', '/games/' + gameId + '/prophet_inference');
    if (result && result.data) {
        renderProphetInference(result.data);
    }
}

// 渲染预言家查验推导信息
function renderProphetInference(data) {
    const banner = document.getElementById('prophet-inference-banner');
    const content = document.getElementById('prophet-inference-content');
    const contradictionsDiv = document.getElementById('prophet-contradictions');
    const chainsDiv = document.getElementById('prophet-chains');

    const prophetClaims = data.prophet_claims || [];
    const contradictions = data.contradictions || [];
    const chains = data.chains || [];

    if (!prophetClaims || prophetClaims.length === 0) {
        banner.style.display = 'none';
        return;
    }
    banner.style.display = 'block';

    // 渲染起跳玩家和查验信息
    let html = '';
    prophetClaims.forEach(claim => {
        const prophetProb = (claim.prophet_probability * 100).toFixed(1);
        const confirmedBadge = claim.is_confirmed ? '<span class="badge badge-success" style="margin-left:8px;">已确认</span>' : '';
        html += '<div style="margin-bottom:12px;padding-bottom:12px;border-bottom:1px solid rgba(168,85,247,0.2);">';
        html += '<div style="font-weight:600;margin-bottom:6px;">' + escapeHtml(claim.player_name) + ' （预言家概率 ' + prophetProb + '%）' + confirmedBadge + '</div>';
        if (claim.checks && claim.checks.length > 0) {
            claim.checks.forEach(check => {
                const checkColor = check.check_type === '查杀' ? '#ef4444' : '#22c55e';
                html += '<div style="font-size:13px;color:#94a3b8;margin-left:12px;">';
                html += '<span style="color:' + checkColor + ';font-weight:600;">' + check.check_type + '</span> ';
                html += escapeHtml(check.target_name);
                if (check.round_number) {
                    html += ' <span style="color:#64748b;font-size:12px;">（第' + check.round_number + '轮）</span>';
                }
                html += '</div>';
            });
        } else {
            html += '<div style="font-size:13px;color:#64748b;margin-left:12px;">暂无查验信息</div>';
        }
        html += '</div>';
    });
    content.innerHTML = html;

    // 渲染矛盾信息
    if (contradictions.length > 0) {
        contradictionsDiv.style.display = 'block';
        let cHtml = '<div style="font-weight:600;color:#ef4444;margin-bottom:8px;">⚠️ 检测到矛盾</div>';
        contradictions.forEach(c => {
            cHtml += '<div style="font-size:13px;color:#fca5a5;margin-bottom:6px;padding:6px 8px;background:rgba(239,68,68,0.1);border-radius:4px;">';
            cHtml += escapeHtml(c.description);
            cHtml += '</div>';
        });
        contradictionsDiv.innerHTML = cHtml;
    } else {
        contradictionsDiv.style.display = 'none';
    }

    // 渲染查验链
    if (chains.length > 0) {
        chainsDiv.style.display = 'block';
        let chHtml = '<div style="font-weight:600;color:#f59e0b;margin-bottom:8px;">🔗 查验链分析</div>';
        chains.forEach(ch => {
            chHtml += '<div style="font-size:13px;color:#fcd34d;margin-bottom:8px;padding:8px;background:rgba(245,158,11,0.1);border-radius:4px;">';
            chHtml += '<div style="font-weight:600;margin-bottom:4px;">' + escapeHtml(ch.description) + '</div>';
            if (ch.logic) {
                chHtml += '<div style="color:#fde68a;font-size:12px;">💡 ' + escapeHtml(ch.logic) + '</div>';
            }
            chHtml += '</div>';
        });
        chainsDiv.innerHTML = chHtml;
    } else {
        chainsDiv.style.display = 'none';
    }
}


// ============================================================
// 编辑行为记录
// ============================================================

// 打开编辑行为模态框
async function editBehavior(behavior_id) {
    // 获取行为记录的详细信息
    const behavior = gameData.behaviors.find(b => b.id === behavior_id);
    if (!behavior) {
        showToast('行为记录不存在', 'error');
        return;
    }

    // 填充表单
    document.getElementById('edit-behavior-id').value = behavior_id;

    // 填充行为发起者
    const actorSelect = document.getElementById('edit-behavior-actor');
    actorSelect.innerHTML = '';
    allPlayers.forEach(p => {
        const opt = document.createElement('option');
        opt.value = p.id;
        opt.textContent = p.name;
        if (p.id === behavior.actor_id) opt.selected = true;
        actorSelect.appendChild(opt);
    });

    // 填充行为目标
    const targetSelect = document.getElementById('edit-behavior-target');
    targetSelect.innerHTML = '<option value="">无目标</option>';
    allPlayers.forEach(p => {
        const opt = document.createElement('option');
        opt.value = p.id;
        opt.textContent = p.name;
        if (p.id === behavior.target_id) opt.selected = true;
        targetSelect.appendChild(opt);
    });

    // 填充具体行为
    const actionSelect = document.getElementById('edit-behavior-action');
    actionSelect.innerHTML = '';
    allActions.forEach(a => {
        const opt = document.createElement('option');
        opt.value = a.id;
        opt.textContent = a.name;
        if (a.id === behavior.action_id) opt.selected = true;
        actionSelect.appendChild(opt);
    });

    // 填充声明身份
    const roleSelect = document.getElementById('edit-behavior-role');
    roleSelect.innerHTML = '<option value="">不声明</option>';
    allRoles.forEach(r => {
        const opt = document.createElement('option');
        opt.value = r.id;
        opt.textContent = r.name + ' (' + r.camp + ')';
        if (r.id === behavior.actor_role_id) opt.selected = true;
        roleSelect.appendChild(opt);
    });

    // 填充声明阵营
    document.getElementById('edit-behavior-camp').value = behavior.actor_camp || '';

    // 填充轮次和阶段
    document.getElementById('edit-behavior-round').value = behavior.round_number || '';
    document.getElementById('edit-behavior-phase').value = behavior.phase || '';

    // 填充备注
    document.getElementById('edit-behavior-notes').value = behavior.notes || '';

    // 填充结果状态
    document.getElementById('edit-behavior-result-status').value = behavior.result_status || 'unknown';

    // 显示模态框
    hideModal('edit-behavior-modal');
    document.getElementById('edit-behavior-modal').classList.add('show');
}

// 保存行为修改
async function saveBehaviorEdit() {
    const behavior_id = parseInt(document.getElementById('edit-behavior-id').value);
    const actor_id = parseInt(document.getElementById('edit-behavior-actor').value);
    const target_id = document.getElementById('edit-behavior-target').value;
    const action_id = parseInt(document.getElementById('edit-behavior-action').value);
    const actor_role_id = document.getElementById('edit-behavior-role').value;
    const actor_camp = document.getElementById('edit-behavior-camp').value;
    const round_number = document.getElementById('edit-behavior-round').value;
    const phase = document.getElementById('edit-behavior-phase').value;
    const notes = document.getElementById('edit-behavior-notes').value.trim();
    const result_status = document.getElementById('edit-behavior-result-status').value;

    if (!actor_id) {
        showToast('请选择行为发起者', 'error');
        return;
    }
    if (!action_id) {
        showToast('请选择具体行为', 'error');
        return;
    }

    const data = {
        actor_id: actor_id,
        action_id: action_id,
        result_status: result_status
    };
    if (target_id) data.target_id = parseInt(target_id);
    if (actor_role_id) data.actor_role_id = parseInt(actor_role_id);
    if (actor_camp) data.actor_camp = actor_camp;
    if (round_number) data.round_number = parseInt(round_number);
    if (phase) data.phase = phase;
    if (notes) data.notes = notes;

    const result = await api('PUT', '/behaviors/' + behavior_id, data);
    if (result) {
        showToast('行为记录更新成功', 'success');
        hideModal('edit-behavior-modal');
        // 刷新预测结果和行为记录
        await loadPredictions();
        const gameResult = await api('GET', '/games/' + gameId);
        if (gameResult && gameResult.data) {
            gameData = gameResult.data;
            renderBehaviors(gameData.behaviors || []);
        }
    }
}


// ============================================================
// 行为结果状态管理
// ============================================================

// 重新推测所有行为结果状态
async function reInferResultStatus() {
    if (!confirm('确定要根据已确认身份重新推测所有行为结果状态吗？')) {
        return;
    }
    showToast('正在重新推测行为结果状态...', 'info');
    const result = await api('POST', '/games/' + gameId + '/result_status/re_infer');
    if (result) {
        const count = result.data ? result.data.updated_count : 0;
        showToast(`重新推测完成，共更新 ${count} 条行为记录`, 'success');
        // 刷新预测结果和行为记录
        await loadPredictions();
        const gameResult = await api('GET', '/games/' + gameId);
        if (gameResult && gameResult.data) {
            gameData = gameResult.data;
            renderBehaviors(gameData.behaviors || []);
        }
    }
}

// 重置所有行为结果状态为未知
async function resetResultStatus() {
    if (!confirm('确定要重置所有行为结果状态为未知吗？')) {
        return;
    }
    showToast('正在重置行为结果状态...', 'info');
    const result = await api('POST', '/games/' + gameId + '/result_status/reset');
    if (result) {
        showToast('行为结果状态已重置为未知', 'success');
        // 刷新预测结果和行为记录
        await loadPredictions();
        const gameResult = await api('GET', '/games/' + gameId);
        if (gameResult && gameResult.data) {
            gameData = gameResult.data;
            renderBehaviors(gameData.behaviors || []);
        }
    }
}


// ============================================================
// 逻辑一致性与视角分析
// ============================================================

async function loadLogicAnalysis() {
    const result = await api('GET', '/games/' + gameId + '/logic_analysis');
    if (result && result.data) {
        renderLogicAnalysis(result.data);
    }
}

function renderLogicAnalysis(data) {
    const banner = document.getElementById('logic-analysis-banner');
    const content = document.getElementById('logic-analysis-content');
    const summary = document.getElementById('logic-analysis-summary');

    if (!banner || !content) return;

    const contradictions = data.contradictions || [];
    const information_leaks = data.information_leaks || [];
    const logic_chains = data.logic_chains || [];
    const player_suspicion = data.player_suspicion || {};
    const total = data.total_issues || 0;

    banner.style.display = 'block';
    if (total === 0) {
        summary.textContent = '未检测到明显问题';
        content.innerHTML = '<div style="padding:8px;color:#22c55e;font-size:13px;">✅ 当前未检测到立场矛盾、信息量溢出或可疑逻辑链条</div>';
        return;
    }

    const highSeverity = contradictions.filter(c => c.severity === 'high').length +
                         information_leaks.filter(l => l.severity === 'high').length +
                         logic_chains.filter(c => c.severity === 'high').length;
    summary.textContent = `共发现 ${total} 个问题（高风险 ${highSeverity} 个）`;

    let html = '';

    // 立场矛盾
    if (contradictions.length > 0) {
        html += '<div style="margin-bottom:12px;">';
        html += '<div style="font-weight:600;color:#ef4444;margin-bottom:6px;">⚠️ 立场矛盾（' + contradictions.length + '）</div>';
        contradictions.forEach(c => {
            const severityColor = c.severity === 'high' ? '#ef4444' : '#f59e0b';
            html += '<div style="padding:8px;background:rgba(239,68,68,0.08);border-radius:6px;margin-bottom:6px;border-left:3px solid ' + severityColor + ';">';
            html += '<div style="font-size:13px;">' + escapeHtml(c.description) + '</div>';
            html += '<div style="font-size:11px;color:#94a3b8;margin-top:4px;">第' + c.round + '轮 ' + (c.phase || '') + ' · ' + c.severity + '</div>';
            html += '</div>';
        });
        html += '</div>';
    }

    // 信息量溢出
    if (information_leaks.length > 0) {
        html += '<div style="margin-bottom:12px;">';
        html += '<div style="font-weight:600;color:#a855f7;margin-bottom:6px;">👁️ 信息量溢出/开视角（' + information_leaks.length + '）</div>';
        information_leaks.forEach(l => {
            const severityColor = l.severity === 'high' ? '#ef4444' : '#f59e0b';
            html += '<div style="padding:8px;background:rgba(168,85,247,0.08);border-radius:6px;margin-bottom:6px;border-left:3px solid ' + severityColor + ';">';
            html += '<div style="font-size:13px;">' + escapeHtml(l.description) + '</div>';
            html += '<div style="font-size:11px;color:#94a3b8;margin-top:4px;">第' + l.round + '轮 ' + (l.phase || '') + ' · ' + l.severity + '</div>';
            html += '</div>';
        });
        html += '</div>';
    }

    // 逻辑链条
    if (logic_chains.length > 0) {
        html += '<div>';
        html += '<div style="font-weight:600;color:#06b6d4;margin-bottom:6px;">🔗 可疑逻辑链条（' + logic_chains.length + '）</div>';
        logic_chains.forEach(c => {
            const severityColor = c.severity === 'high' ? '#ef4444' : '#f59e0b';
            html += '<div style="padding:8px;background:rgba(6,182,212,0.08);border-radius:6px;margin-bottom:6px;border-left:3px solid ' + severityColor + ';">';
            html += '<div style="font-size:13px;">' + escapeHtml(c.description) + '</div>';
            html += '</div>';
        });
        html += '</div>';
    }

    // 玩家嫌疑分数
    const suspicionEntries = Object.entries(player_suspicion).filter(([pid, score]) => score > 0);
    if (suspicionEntries.length > 0) {
        html += '<div style="margin-top:12px;padding-top:12px;border-top:1px solid rgba(255,255,255,0.1);">';
        html += '<div style="font-weight:600;color:#f59e0b;margin-bottom:6px;">🎯 玩家嫌疑分数（影响预测概率）</div>';
        suspicionEntries.sort((a, b) => b[1] - a[1]).forEach(([pid, score]) => {
            const player = predictions.find(x => x.player_id === parseInt(pid));
            const playerName = player ? player.player_name : `玩家${pid}`;
            html += '<div style="display:flex;justify-content:space-between;align-items:center;padding:4px 0;">';
            html += '<span style="font-size:13px;">' + escapeHtml(playerName) + '</span>';
            html += '<span style="font-size:13px;color:#f59e0b;font-weight:600;">' + score + ' 分</span>';
            html += '</div>';
        });
        html += '</div>';
    }

    content.innerHTML = html;
    // 保持内容折叠状态（默认折叠）
    content.style.display = 'none';
    const toggle = document.getElementById('logic-analysis-toggle');
    if (toggle) toggle.textContent = '▼';
}


// ============================================================
// 预测结果详细解释/教学模式
// ============================================================

async function showExplanationModal() {
    if (!selectedPlayerId) {
        showToast('请先选择一个玩家', 'warning');
        return;
    }

    const modal = document.getElementById('explanation-modal');
    const content = document.getElementById('explanation-content');
    const title = document.getElementById('explanation-title');

    if (!modal || !content) return;

    // 显示模态框
    modal.classList.add('show');
    content.innerHTML = '<div class="empty-state"><p>加载中...</p></div>';

    // 获取玩家名称
    const player = predictions.find(x => x.player_id === selectedPlayerId);
    if (player) {
        title.textContent = `📖 ${player.player_name} 的预测结果详细解释`;
    }

    // 加载解释数据
    const result = await api('GET', `/games/${gameId}/players/${selectedPlayerId}/explanation`);
    if (result && result.data) {
        renderExplanation(result.data);
    } else {
        content.innerHTML = '<div class="empty-state"><p>加载失败，请重试</p></div>';
    }
}

function renderExplanation(data) {
    const content = document.getElementById('explanation-content');
    if (!content) return;

    let html = '';

    // 行为列表
    const behaviors = data.behaviors || [];
    if (behaviors.length > 0) {
        html += '<div style="margin-bottom:20px;">';
        html += '<div style="font-weight:600;font-size:16px;margin-bottom:10px;color:var(--neon-cyan);">📋 该玩家的行为记录</div>';
        html += '<div style="display:flex;flex-direction:column;gap:8px;">';
        behaviors.forEach((b, index) => {
            const targetText = b.target_name ? ` → ${b.target_name}` : '';
            const roundText = b.round_number ? `第${b.round_number}轮` : '';
            const phaseText = b.phase || '';
            html += `<div style="padding:10px;background:rgba(0,240,255,0.05);border-radius:8px;border-left:3px solid var(--neon-cyan);">`;
            html += `<div style="display:flex;justify-content:space-between;align-items:center;">`;
            html += `<span><strong>#${index + 1}</strong> ${escapeHtml(b.action_name)}${targetText}</span>`;
            html += `<span style="font-size:12px;color:var(--text-secondary);">${roundText} ${phaseText}</span>`;
            html += `</div>`;
            if (b.notes) {
                html += `<div style="font-size:12px;color:var(--text-secondary);margin-top:4px;">📝 ${escapeHtml(b.notes)}</div>`;
            }
            html += `</div>`;
        });
        html += '</div></div>';
    }

    // 行为影响分析
    const behavior_analysis = data.behavior_analysis || [];
    if (behavior_analysis.length > 0) {
        html += '<div style="margin-bottom:20px;">';
        html += '<div style="font-weight:600;font-size:16px;margin-bottom:10px;color:#a855f7;">🔍 行为对身份的影响分析</div>';
        html += '<div style="display:flex;flex-direction:column;gap:10px;">';
        behavior_analysis.forEach(ba => {
            const affected = ba.affected_roles || [];
            if (affected.length === 0) return;

            html += `<div style="padding:12px;background:rgba(168,85,247,0.05);border-radius:8px;border:1px solid rgba(168,85,247,0.2);">`;
            html += `<div style="font-weight:600;margin-bottom:8px;">${escapeHtml(ba.action_name)} <span style="font-size:12px;color:var(--text-secondary);">(权重: ${ba.weight})</span></div>`;
            html += `<div style="display:flex;flex-wrap:wrap;gap:6px;">`;
            affected.forEach(ar => {
                const effectColor = ar.effect === 'positive' ? '#22c55e' : '#ef4444';
                const effectText = ar.effect === 'positive' ? '↑ 升高' : '↓ 降低';
                html += `<span style="padding:4px 10px;background:${effectColor}15;border:1px solid ${effectColor}40;border-radius:12px;font-size:12px;color:${effectColor};">`;
                html += `${escapeHtml(ar.role_name)} ${effectText}`;
                html += `</span>`;
            });
            html += `</div></div>`;
        });
        html += '</div></div>';
    }

    // 个性化统计
    if (data.personalized_stats && data.personalized_stats.length > 0) {
        html += '<div style="margin-bottom:20px;">';
        html += '<div style="font-weight:600;font-size:16px;margin-bottom:10px;color:#f59e0b;">📊 个性化行为统计</div>';
        html += '<div style="padding:12px;background:rgba(245,158,11,0.05);border-radius:8px;border:1px solid rgba(245,158,11,0.2);font-size:13px;">';
        html += '<p>系统已根据该玩家的历史对局数据，学习了其个人行为倾向。同样的行为，对不同玩家可能有不同的身份指示意义。</p>';
        // 使用count字段（数据库中的字段名），而不是sample_count
        const total_samples = data.personalized_stats.reduce((sum, s) => sum + (s.count || 0), 0);
        const total_games = data.personalized_stats.reduce((sum, s) => sum + (s.game_count || 0), 0);
        html += `<p style="margin-top:8px;"><strong>历史数据量：</strong>${total_samples} 条行为记录，涉及 ${total_games} 局对局</p>`;
        html += '</div></div>';
    }

    // 教学建议
    const suggestions = data.teaching_suggestions || [];
    if (suggestions.length > 0) {
        html += '<div style="margin-bottom:20px;">';
        html += '<div style="font-weight:600;font-size:16px;margin-bottom:10px;color:#22c55e;">🎓 教学建议</div>';
        html += '<div style="display:flex;flex-direction:column;gap:10px;">';
        suggestions.forEach(s => {
            const typeColors = {
                'info': '#3b82f6',
                'warning': '#f59e0b',
                'success': '#22c55e',
                'tip': '#a855f7'
            };
            const color = typeColors[s.type] || '#3b82f6';
            html += `<div style="padding:12px;background:${color}10;border-radius:8px;border-left:3px solid ${color};">`;
            html += `<div style="font-weight:600;color:${color};margin-bottom:4px;">${escapeHtml(s.title)}</div>`;
            html += `<div style="font-size:13px;line-height:1.6;">${escapeHtml(s.content)}</div>`;
            html += `</div>`;
        });
        html += '</div></div>';
    }

    // 如果没有任何数据
    if (behaviors.length === 0 && !data.personalized_stats && suggestions.length === 0) {
        html += '<div class="empty-state"><p>暂无详细解释数据</p></div>';
    }

    content.innerHTML = html;
}


// ============================================================
// 机器学习模型
// ============================================================

async function showMLModal() {
    const modal = document.getElementById('ml-modal');
    const content = document.getElementById('ml-content');

    if (!modal || !content) return;

    modal.classList.add('show');
    content.innerHTML = '<div class="empty-state"><p>加载中...</p></div>';

    // 加载模型状态
    const result = await api('GET', '/ml/status');
    if (result && result.data) {
        renderMLStatus(result.data);
    } else {
        content.innerHTML = '<div class="empty-state"><p>加载失败，请重试</p></div>';
    }
}

function renderMLStatus(status) {
    const content = document.getElementById('ml-content');
    if (!content) return;

    let html = '';

    // 模型状态概览
    html += '<div style="margin-bottom:20px;">';
    html += '<div style="font-weight:600;font-size:16px;margin-bottom:12px;color:var(--neon-cyan);">📊 模型状态</div>';
    html += '<div style="display:grid;grid-template-columns:repeat(3,1fr);gap:12px;">';
    html += `<div style="padding:16px;background:rgba(0,240,255,0.05);border-radius:8px;text-align:center;">
        <div style="font-size:24px;font-weight:700;color:var(--neon-cyan);">${status.game_count}</div>
        <div style="font-size:12px;color:var(--text-secondary);">已确认对局</div>
    </div>`;
    html += `<div style="padding:16px;background:rgba(168,85,247,0.05);border-radius:8px;text-align:center;">
        <div style="font-size:24px;font-weight:700;color:#a855f7;">${status.identity_count}</div>
        <div style="font-size:12px;color:var(--text-secondary);">已确认身份</div>
    </div>`;
    html += `<div style="padding:16px;background:rgba(34,197,94,0.05);border-radius:8px;text-align:center;">
        <div style="font-size:24px;font-weight:700;color:#22c55e;">${status.trained_models}</div>
        <div style="font-size:12px;color:var(--text-secondary);">已训练模型</div>
    </div>`;
    html += '</div></div>';

    // 训练状态
    html += '<div style="margin-bottom:20px;padding:16px;background:rgba(245,158,11,0.05);border-radius:8px;border:1px solid rgba(245,158,11,0.2);">';
    if (status.ready) {
        html += '<div style="color:#22c55e;font-weight:600;margin-bottom:8px;">✅ 数据充足，可以训练模型</div>';
        html += `<div style="font-size:13px;color:var(--text-secondary);margin-bottom:12px;">已确认身份 ${status.identity_count} 条，达到最少样本数 ${status.min_samples} 条。点击下方按钮开始训练模型。</div>`;
        html += '<button class="btn btn-primary" onclick="trainMLModels()" style="width:100%;">🚀 开始训练模型</button>';
    } else {
        html += '<div style="color:#f59e0b;font-weight:600;margin-bottom:8px;">⏳ 数据积累中</div>';
        html += `<div style="font-size:13px;color:var(--text-secondary);">已确认身份 ${status.identity_count} 条，还需要 ${status.min_samples - status.identity_count} 条才能开始训练模型（最少 ${status.min_samples} 条）。</div>`;
        html += `<div style="font-size:13px;color:var(--text-secondary);margin-top:8px;">在数据不足时，系统会使用贝叶斯算法进行预测。随着数据积累，ML模型会自动学习并优化预测。</div>`;
    }
    html += '</div>';

    // 模型说明和特征列表已隐藏（用户要求不显示）
    /*
    // 模型说明
    html += '<div style="margin-bottom:20px;">';
    html += '<div style="font-weight:600;font-size:16px;margin-bottom:10px;color:#a855f7;">📚 模型说明</div>';
    html += '<div style="padding:16px;background:rgba(168,85,247,0.05);border-radius:8px;font-size:13px;line-height:1.8;">';
    html += '<p><strong>算法：</strong>逻辑回归（Logistic Regression）</p>';
    html += '<p><strong>特征：</strong>从行为记录中提取' + (status.feature_count || 0) + '个特征（动态识别所有行为），包括行为类型、目标关系、轮次、阶段等</p>';
    html += '<p><strong>训练：</strong>使用已确认身份的对局数据进行监督学习</p>';
    html += '<p><strong>预测：</strong>ML模型与贝叶斯算法混合预测（几何平均），数据不足时回退到贝叶斯算法</p>';
    html += '<p><strong>优化：</strong>每局结束后自动更新模型，预测会越来越准确</p>';
    html += '</div></div>';

    // 特征列表（动态从数据库加载）
    html += '<div>';
    html += '<div style="font-weight:600;font-size:16px;margin-bottom:10px;color:#22c55e;">🔍 特征列表（共 ' + (status.feature_count || 0) + ' 个）</div>';
    html += '<div style="display:flex;flex-wrap:wrap;gap:6px;">';

    // 行为特征（动态加载）
    const all_actions = status.all_actions || [];
    all_actions.forEach(a => {
        html += `<span style="padding:4px 10px;background:rgba(34,197,94,0.1);border:1px solid rgba(34,197,94,0.2);border-radius:12px;font-size:11px;color:#22c55e;">${escapeHtml(a.name)}</span>`;
    });

    // 固定特征
    const fixed_features = [
        'has_target(有目标)', 'round_1(第一轮)', 'round_2(第二轮)', 'round_3_plus(第三轮+)',
        'phase_speech(发言阶段)', 'phase_vote(投票阶段)', 'attack_count(踩人次数)',
        'defend_count(保人次数)', 'behavior_count(行为总数)'
    ];
    fixed_features.forEach(f => {
        html += `<span style="padding:4px 10px;background:rgba(59,130,246,0.1);border:1px solid rgba(59,130,246,0.2);border-radius:12px;font-size:11px;color:#3b82f6;">${f}</span>`;
    });

    html += '</div></div>';
    */

    content.innerHTML = html;
}

async function trainMLModels() {
    const content = document.getElementById('ml-content');
    if (!content) return;

    content.innerHTML = '<div class="empty-state"><p>训练中，请稍候...</p></div>';

    const result = await api('POST', '/ml/train');
    if (result && result.data) {
        // 重新加载状态
        const statusResult = await api('GET', '/ml/status');
        if (statusResult && statusResult.data) {
            renderMLStatus(statusResult.data);
        }

        // 显示训练结果
        if (result.data.good && result.data.good.trained) {
            showToast(`训练完成！好人分类器准确率：${(result.data.good.accuracy * 100).toFixed(1)}%`, 'success');
        } else if (result.data.good) {
            showToast(result.data.good.message || '训练失败', 'warning');
        }
    } else {
        content.innerHTML = '<div class="empty-state"><p>训练失败，请重试</p></div>';
    }
}


// ============================================================
// 快捷录入功能
// ============================================================

// 辅助函数：通过行为名称查找行为ID
function findActionId(name) {
    const action = allActions.find(a => a.name === name);
    return action ? action.id : null;
}

// ============================================================
// 预言家起跳快捷录入
// ============================================================
function showProphetJumpModal() {
    const modal = document.getElementById('prophet-jump-modal');
    if (!modal) return;

    const actorSelect = document.getElementById('prophet-jump-actor');
    const targetSelect = document.getElementById('prophet-jump-target');
    const badge1Select = document.getElementById('prophet-jump-badge1');
    const badge2Select = document.getElementById('prophet-jump-badge2');

    const playerOptions = '<option value="">请选择玩家</option>' + 
        gamePlayers.map(p => `<option value="${p.player_id}">${escapeHtml(p.player_name)}</option>`).join('');

    actorSelect.innerHTML = playerOptions;
    targetSelect.innerHTML = playerOptions;
    badge1Select.innerHTML = '<option value="">不设置</option>' + gamePlayers.map(p => `<option value="${p.player_id}">${escapeHtml(p.player_name)}</option>`).join('');
    badge2Select.innerHTML = '<option value="">不设置</option>' + gamePlayers.map(p => `<option value="${p.player_id}">${escapeHtml(p.player_name)}</option>`).join('');

    document.getElementById('prophet-jump-check-type').value = 'gold';
    document.getElementById('prophet-jump-position').value = 'before';
    document.getElementById('prophet-jump-notes').value = '';

    updateProphetJumpPreview();
    modal.classList.add('show');
}

function updateProphetJumpPreview() {
    const checkType = document.getElementById('prophet-jump-check-type').value;
    const position = document.getElementById('prophet-jump-position').value;
    const positionMap = { 'before': '警前', 'after': '警后', 'below': '警下' };
    const checkTypeMap = { 'gold': '金水', 'check': '查杀' };
    const actionName = positionMap[position] + checkTypeMap[checkType];

    let preview = '1. 跳预言家\n2. ' + actionName;
    const badge1 = document.getElementById('prophet-jump-badge1').value;
    const badge2 = document.getElementById('prophet-jump-badge2').value;
    if (badge1 || badge2) {
        const badge1Name = badge1 ? (gamePlayers.find(p => p.player_id == badge1) || {}).player_name || '?' : '?';
        const badge2Name = badge2 ? (gamePlayers.find(p => p.player_id == badge2) || {}).player_name || '?' : '?';
        preview += '\n3. 警徽流：' + badge1Name + ' ' + badge2Name;
    }
    document.getElementById('prophet-jump-preview').textContent = preview;
}

async function submitProphetJump() {
    const actorId = document.getElementById('prophet-jump-actor').value;
    const checkType = document.getElementById('prophet-jump-check-type').value;
    const position = document.getElementById('prophet-jump-position').value;
    const targetId = document.getElementById('prophet-jump-target').value;
    const badge1 = document.getElementById('prophet-jump-badge1').value;
    const badge2 = document.getElementById('prophet-jump-badge2').value;
    const notes = document.getElementById('prophet-jump-notes').value;

    if (!actorId) { showToast('请选择预言家', 'warning'); return; }
    if (!targetId) { showToast('请选择查验目标', 'warning'); return; }

    const jumpProphetId = findActionId('跳预言家');
    const positionMap = { 'before': '警前', 'after': '警后', 'below': '警下' };
    const checkTypeMap = { 'gold': '金水', 'check': '查杀' };
    const checkActionName = positionMap[position] + checkTypeMap[checkType];
    const checkActionId = findActionId(checkActionName);

    if (!jumpProphetId) { showToast('未找到"跳预言家"行为', 'error'); return; }
    if (!checkActionId) { showToast('未找到"' + checkActionName + '"行为', 'error'); return; }

    const phase = currentGamePhase ? currentGamePhase.phase : null;
    const round = currentGamePhase ? currentGamePhase.round : 1;

    let fullNotes = notes;
    if (badge1 || badge2) {
        const badge1Name = badge1 ? (gamePlayers.find(p => p.player_id == badge1) || {}).player_name || '' : '';
        const badge2Name = badge2 ? (gamePlayers.find(p => p.player_id == badge2) || {}).player_name || '' : '';
        const badgeStr = ('警徽流 ' + badge1Name + ' ' + badge2Name).trim();
        fullNotes = fullNotes ? (fullNotes + '；' + badgeStr) : badgeStr;
    }

    const prophetRole = allRoles.find(r => r.name === '预言家');
    const prophetRoleId = prophetRole ? prophetRole.id : null;

    const actionIds = [jumpProphetId, checkActionId];
    const result = await api('POST', '/games/' + gameId + '/behaviors/batch', {
        actor_id: parseInt(actorId),
        action_ids: actionIds,
        target_id: parseInt(targetId),
        actor_role_id: prophetRoleId,
        round_number: round,
        phase: phase,
        notes: fullNotes,
        result_status: 'unknown'
    });

    if (result) {
        showToast('成功创建 ' + result.data.created_count + ' 条行为记录', 'success');
        hideModal('prophet-jump-modal');
        await loadBehaviors();
        await loadPredictions();
    } else {
        showToast('创建失败，请重试', 'error');
    }
}

// ============================================================
// 投票统计快捷录入
// ============================================================
function showVoteBatchModal() {
    const modal = document.getElementById('vote-batch-modal');
    if (!modal) return;
    document.getElementById('vote-batch-type').value = 'banish';
    renderVoteBatchList();
    modal.classList.add('show');
}

function renderVoteBatchList() {
    const list = document.getElementById('vote-batch-list');
    if (!list) return;

    const targetOptions = '<option value="">弃票</option>' + 
        gamePlayers.map(p => `<option value="${p.player_id}">${escapeHtml(p.player_name)}</option>`).join('');

    let html = '';
    gamePlayers.forEach(function(p, index) {
        html += '<div style="display:flex;align-items:center;gap:12px;padding:8px 0;border-bottom:1px solid rgba(255,255,255,0.05);">';
        html += '<div style="min-width:100px;font-weight:500;">' + (index + 1) + '. ' + escapeHtml(p.player_name) + '</div>';
        html += '<select class="form-control vote-batch-target" data-player-id="' + p.player_id + '" style="flex:1;">' + targetOptions + '</select>';
        html += '</div>';
    });

    list.innerHTML = html;
}

function clearAllVotes() {
    const selects = document.querySelectorAll('.vote-batch-target');
    selects.forEach(function(s) { s.value = ''; });
    showToast('已清空所有投票', 'info');
}

async function submitVoteBatch() {
    const voteType = document.getElementById('vote-batch-type').value;
    const voteTypeMap = { 'sheriff': '投警徽票', 'banish': '投放逐票' };
    const abandonActionName = '弃票';

    const voteActionId = findActionId(voteTypeMap[voteType]);
    const abandonActionId = findActionId(abandonActionName);

    if (!voteActionId) { showToast('未找到"' + voteTypeMap[voteType] + '"行为', 'error'); return; }

    const phase = currentGamePhase ? currentGamePhase.phase : null;
    const round = currentGamePhase ? currentGamePhase.round : 1;

    const selects = document.querySelectorAll('.vote-batch-target');
    let createdCount = 0;

    for (let i = 0; i < selects.length; i++) {
        const select = selects[i];
        const actorId = parseInt(select.dataset.playerId);
        const targetId = select.value;

        if (targetId) {
            const result = await api('POST', '/games/' + gameId + '/behaviors', {
                actor_id: actorId,
                action_id: voteActionId,
                target_id: parseInt(targetId),
                round_number: round,
                phase: phase,
                result_status: 'unknown'
            });
            if (result) createdCount++;
        } else if (abandonActionId) {
            const result = await api('POST', '/games/' + gameId + '/behaviors', {
                actor_id: actorId,
                action_id: abandonActionId,
                round_number: round,
                phase: phase,
                result_status: 'unknown'
            });
            if (result) createdCount++;
        }
    }

    showToast('成功创建 ' + createdCount + ' 条投票记录', 'success');
    hideModal('vote-batch-modal');
    await loadBehaviors();
    await loadPredictions();
}

// ============================================================
// 公布死讯快捷录入
// ============================================================
function showDeathInfoModal() {
    const modal = document.getElementById('death-info-modal');
    if (!modal) return;

    const victim1Select = document.getElementById('death-info-victim1');
    const victim2Select = document.getElementById('death-info-victim2');
    const victim3Select = document.getElementById('death-info-victim3');

    const playerOptions = '<option value="">请选择玩家</option>' + 
        gamePlayers.map(p => `<option value="${p.player_id}">${escapeHtml(p.player_name)}</option>`).join('');

    victim1Select.innerHTML = playerOptions;
    victim2Select.innerHTML = playerOptions;
    victim3Select.innerHTML = playerOptions;

    document.getElementById('death-info-type').value = 'single';
    document.getElementById('death-info-notes').value = '';
    updateDeathInfoFields();
    modal.classList.add('show');
}

function updateDeathInfoFields() {
    const deathType = document.getElementById('death-info-type').value;
    const victimsDiv = document.getElementById('death-info-victims');
    const victim2Group = document.getElementById('death-info-victim2-group');
    const victim3Group = document.getElementById('death-info-victim3-group');

    if (deathType === 'safe') {
        victimsDiv.style.display = 'none';
    } else {
        victimsDiv.style.display = 'block';
        victim2Group.style.display = (deathType === 'double' || deathType === 'triple') ? 'block' : 'none';
        victim3Group.style.display = (deathType === 'triple') ? 'block' : 'none';
    }
}

async function submitDeathInfo() {
    const deathType = document.getElementById('death-info-type').value;
    const notes = document.getElementById('death-info-notes').value;
    const deathTypeMap = { 'safe': null, 'single': '单死', 'double': '双死', 'triple': '三死' };
    const actionName = deathTypeMap[deathType];

    const phase = currentGamePhase ? currentGamePhase.phase : null;
    const round = currentGamePhase ? currentGamePhase.round : 1;

    if (deathType === 'safe') {
        showToast('平安夜已记录', 'success');
        hideModal('death-info-modal');
        return;
    }

    const actionId = findActionId(actionName);
    if (!actionId) { showToast('未找到"' + actionName + '"行为', 'error'); return; }

    const victim1 = document.getElementById('death-info-victim1').value;
    const victim2 = document.getElementById('death-info-victim2').value;
    const victim3 = document.getElementById('death-info-victim3').value;

    const victims = [];
    if (victim1) victims.push(parseInt(victim1));
    if (victim2) victims.push(parseInt(victim2));
    if (victim3) victims.push(parseInt(victim3));

    if (victims.length === 0) { showToast('请选择至少一个死者', 'warning'); return; }

    let createdCount = 0;
    for (let i = 0; i < victims.length; i++) {
        const victimId = victims[i];
        const result = await api('POST', '/games/' + gameId + '/behaviors', {
            actor_id: victimId,
            action_id: actionId,
            round_number: round,
            phase: phase,
            notes: notes,
            result_status: 'unknown'
        });
        if (result) createdCount++;
    }

    showToast('成功创建 ' + createdCount + ' 条死亡记录', 'success');
    hideModal('death-info-modal');
    await loadBehaviors();
    await loadPredictions();
}

// 为预言家起跳模态框的表单元素添加事件监听
document.addEventListener('DOMContentLoaded', function() {
    const checkTypeSelect = document.getElementById('prophet-jump-check-type');
    const positionSelect = document.getElementById('prophet-jump-position');
    const badge1Select = document.getElementById('prophet-jump-badge1');
    const badge2Select = document.getElementById('prophet-jump-badge2');

    if (checkTypeSelect) checkTypeSelect.addEventListener('change', updateProphetJumpPreview);
    if (positionSelect) positionSelect.addEventListener('change', updateProphetJumpPreview);
    if (badge1Select) badge1Select.addEventListener('change', updateProphetJumpPreview);
    if (badge2Select) badge2Select.addEventListener('change', updateProphetJumpPreview);
});


// ============================================================
// 女巫用药快捷录入（可选，仅女巫知晓）
// ============================================================
function showWitchPotionModal() {
    const modal = document.getElementById('witch-potion-modal');
    if (!modal) return;

    const antidoteSelect = document.getElementById('witch-antidote-target');
    const poisonSelect = document.getElementById('witch-poison-target');

    const playerOptions = '<option value="">请选择玩家</option>' + 
        gamePlayers.map(p => `<option value="${p.player_id}">${escapeHtml(p.player_name)}</option>`).join('');

    antidoteSelect.innerHTML = playerOptions;
    poisonSelect.innerHTML = playerOptions;

    document.getElementById('witch-potion-type').value = 'antidote';
    document.getElementById('witch-potion-notes').value = '';
    updateWitchPotionFields();

    modal.classList.add('show');
}

function updateWitchPotionFields() {
    const potionType = document.getElementById('witch-potion-type').value;
    const antidoteGroup = document.getElementById('witch-antidote-group');
    const poisonGroup = document.getElementById('witch-poison-group');

    if (potionType === 'antidote') {
        antidoteGroup.style.display = 'block';
        poisonGroup.style.display = 'none';
    } else if (potionType === 'poison') {
        antidoteGroup.style.display = 'none';
        poisonGroup.style.display = 'block';
    } else if (potionType === 'both') {
        antidoteGroup.style.display = 'block';
        poisonGroup.style.display = 'block';
    } else {
        antidoteGroup.style.display = 'none';
        poisonGroup.style.display = 'none';
    }
}

async function submitWitchPotion() {
    const potionType = document.getElementById('witch-potion-type').value;
    const antidoteTarget = document.getElementById('witch-antidote-target').value;
    const poisonTarget = document.getElementById('witch-poison-target').value;
    const notes = document.getElementById('witch-potion-notes').value;

    const phase = currentGamePhase ? currentGamePhase.phase : null;
    const round = currentGamePhase ? currentGamePhase.round : 1;

    let createdCount = 0;

    if (potionType === 'antidote' || potionType === 'both') {
        if (!antidoteTarget) {
            showToast('请选择解药救的玩家', 'warning');
            return;
        }
        const actionId = findActionId('使用解药');
        if (!actionId) {
            showToast('未找到"使用解药"行为，请先在行为库中添加', 'error');
            return;
        }
        const result = await api('POST', '/games/' + gameId + '/behaviors', {
            actor_id: parseInt(antidoteTarget),
            action_id: actionId,
            round_number: round,
            phase: phase,
            notes: notes,
            result_status: 'unknown'
        });
        if (result) createdCount++;
    }

    if (potionType === 'poison' || potionType === 'both') {
        if (!poisonTarget) {
            showToast('请选择毒药毒的玩家', 'warning');
            return;
        }
        const actionId = findActionId('使用毒药');
        if (!actionId) {
            showToast('未找到"使用毒药"行为，请先在行为库中添加', 'error');
            return;
        }
        const result = await api('POST', '/games/' + gameId + '/behaviors', {
            actor_id: parseInt(poisonTarget),
            action_id: actionId,
            round_number: round,
            phase: phase,
            notes: notes,
            result_status: 'unknown'
        });
        if (result) createdCount++;
    }

    if (potionType === 'none') {
        showToast('已记录女巫未用药', 'success');
        hideModal('witch-potion-modal');
        return;
    }

    showToast('成功创建 ' + createdCount + ' 条女巫用药记录', 'success');
    hideModal('witch-potion-modal');
    await loadBehaviors();
    await loadPredictions();
}

// ============================================================
// 猎人开枪快捷录入（公开信息）
// ============================================================
function showHunterShootModal() {
    const modal = document.getElementById('hunter-shoot-modal');
    if (!modal) return;

    const shooterSelect = document.getElementById('hunter-shooter');
    const targetSelect = document.getElementById('hunter-target');

    const playerOptions = '<option value="">请选择玩家</option>' + 
        gamePlayers.map(p => `<option value="${p.player_id}">${escapeHtml(p.player_name)}</option>`).join('');

    shooterSelect.innerHTML = playerOptions;
    targetSelect.innerHTML = playerOptions;

    document.getElementById('hunter-shoot-status').value = 'shoot';
    document.getElementById('hunter-shoot-notes').value = '';
    updateHunterShootFields();

    modal.classList.add('show');
}

function updateHunterShootFields() {
    const shootStatus = document.getElementById('hunter-shoot-status').value;
    const shooterGroup = document.getElementById('hunter-shooter-group');
    const targetGroup = document.getElementById('hunter-target-group');

    if (shootStatus === 'shoot') {
        shooterGroup.style.display = 'block';
        targetGroup.style.display = 'block';
    } else {
        shooterGroup.style.display = 'none';
        targetGroup.style.display = 'none';
    }
}

async function submitHunterShoot() {
    const shootStatus = document.getElementById('hunter-shoot-status').value;
    const shooterId = document.getElementById('hunter-shooter').value;
    const targetId = document.getElementById('hunter-target').value;
    const notes = document.getElementById('hunter-shoot-notes').value;

    const phase = currentGamePhase ? currentGamePhase.phase : null;
    const round = currentGamePhase ? currentGamePhase.round : 1;

    if (shootStatus === 'noshoot') {
        showToast('已记录猎人未开枪', 'success');
        hideModal('hunter-shoot-modal');
        return;
    }

    if (!shooterId) {
        showToast('请选择猎人（开枪者）', 'warning');
        return;
    }
    if (!targetId) {
        showToast('请选择开枪带走的玩家', 'warning');
        return;
    }

    const actionId = findActionId('猎人开枪');
    if (!actionId) {
        showToast('未找到"猎人开枪"行为，请先在行为库中添加', 'error');
        return;
    }

    const result = await api('POST', '/games/' + gameId + '/behaviors', {
        actor_id: parseInt(shooterId),
        action_id: actionId,
        target_id: parseInt(targetId),
        round_number: round,
        phase: phase,
        notes: notes,
        result_status: 'unknown'
    });

    if (result) {
        showToast('成功创建猎人开枪记录', 'success');
        hideModal('hunter-shoot-modal');
        await loadBehaviors();
        await loadPredictions();
    } else {
        showToast('创建失败，请重试', 'error');
    }
}

// ============================================================
// 守卫守护快捷录入（可选，仅守卫知晓）
// ============================================================
function showGuardProtectModal() {
    const modal = document.getElementById('guard-protect-modal');
    if (!modal) return;

    const targetSelect = document.getElementById('guard-target');

    const playerOptions = '<option value="">请选择玩家</option>' + 
        gamePlayers.map(p => `<option value="${p.player_id}">${escapeHtml(p.player_name)}</option>`).join('');

    targetSelect.innerHTML = playerOptions;

    document.getElementById('guard-protect-status').value = 'protect';
    document.getElementById('guard-protect-notes').value = '';
    updateGuardProtectFields();

    modal.classList.add('show');
}

function updateGuardProtectFields() {
    const protectStatus = document.getElementById('guard-protect-status').value;
    const targetGroup = document.getElementById('guard-target-group');

    if (protectStatus === 'protect') {
        targetGroup.style.display = 'block';
    } else {
        targetGroup.style.display = 'none';
    }
}

async function submitGuardProtect() {
    const protectStatus = document.getElementById('guard-protect-status').value;
    const targetId = document.getElementById('guard-target').value;
    const notes = document.getElementById('guard-protect-notes').value;

    const phase = currentGamePhase ? currentGamePhase.phase : null;
    const round = currentGamePhase ? currentGamePhase.round : 1;

    if (protectStatus === 'empty') {
        showToast('已记录守卫空守', 'success');
        hideModal('guard-protect-modal');
        return;
    }

    if (!targetId) {
        showToast('请选择守护的玩家', 'warning');
        return;
    }

    const actionId = findActionId('守卫守护');
    if (!actionId) {
        showToast('未找到"守卫守护"行为，请先在行为库中添加', 'error');
        return;
    }

    const result = await api('POST', '/games/' + gameId + '/behaviors', {
        actor_id: parseInt(targetId),
        action_id: actionId,
        round_number: round,
        phase: phase,
        notes: notes,
        result_status: 'unknown'
    });

    if (result) {
        showToast('成功创建守卫守护记录', 'success');
        hideModal('guard-protect-modal');
        await loadBehaviors();
        await loadPredictions();
    } else {
        showToast('创建失败，请重试', 'error');
    }
}


// ============================================================
// 玩家状态管理（上警、退水、死亡等）
// ============================================================

// 显示玩家状态右键菜单
function showPlayerStatusMenu(playerId, event) {
    // 移除已有的菜单
    const existingMenu = document.getElementById('player-status-context-menu');
    if (existingMenu) existingMenu.remove();

    const gp = gamePlayers.find(g => g.player_id === playerId);
    if (!gp) return;

    const menu = document.createElement('div');
    menu.id = 'player-status-context-menu';
    menu.style.cssText = `
        position: fixed;
        left: ${event.clientX}px;
        top: ${event.clientY}px;
        background: var(--card-bg);
        border: 1px solid var(--border-color);
        border-radius: 8px;
        padding: 8px 0;
        min-width: 180px;
        z-index: 10000;
        box-shadow: 0 4px 20px rgba(0,0,0,0.5);
    `;

    const playerName = gp.player_name || '玩家';
    const isAlive = gp.is_alive !== false;
    const isOnPolice = gp.is_on_police;
    const isRetired = gp.is_retired;

    let menuItems = `
        <div style="padding: 8px 16px;font-weight:600;color:var(--neon-cyan);border-bottom:1px solid var(--border-color);margin-bottom:4px;">${escapeHtml(playerName)} - 状态设置</div>
    `;

    // 上警/取消上警
    if (!isOnPolice) {
        menuItems += `<div style="padding: 8px 16px;cursor:pointer;" onmouseover="this.style.background='rgba(0,240,255,0.1)'" onmouseout="this.style.background='transparent'" onclick="updatePlayerStatus(${playerId}, {is_on_police: true}); hidePlayerStatusMenu();">🚔 设为上警</div>`;
    } else {
        menuItems += `<div style="padding: 8px 16px;cursor:pointer;" onmouseover="this.style.background='rgba(0,240,255,0.1)'" onmouseout="this.style.background='transparent'" onclick="updatePlayerStatus(${playerId}, {is_on_police: false}); hidePlayerStatusMenu();">🚫 取消上警</div>`;
    }

    // 退水/取消退水（只有上警玩家才能退水）
    if (isOnPolice && !isRetired) {
        menuItems += `<div style="padding: 8px 16px;cursor:pointer;" onmouseover="this.style.background='rgba(0,240,255,0.1)'" onmouseout="this.style.background='transparent'" onclick="updatePlayerStatus(${playerId}, {is_retired: true}); hidePlayerStatusMenu();">↩️ 退水</div>`;
    } else if (isRetired) {
        menuItems += `<div style="padding: 8px 16px;cursor:pointer;" onmouseover="this.style.background='rgba(0,240,255,0.1)'" onmouseout="this.style.background='transparent'" onclick="updatePlayerStatus(${playerId}, {is_retired: false}); hidePlayerStatusMenu();">↩️ 取消退水</div>`;
    }

    menuItems += `<div style="border-top:1px solid var(--border-color);margin:4px 0;"></div>`;

    // 死亡/复活
    if (isAlive) {
        menuItems += `<div style="padding: 8px 16px;cursor:pointer;" onmouseover="this.style.background='rgba(239,68,68,0.1)'" onmouseout="this.style.background='transparent'" onclick="updatePlayerStatus(${playerId}, {is_alive: false, death_type: 'night_death'}); hidePlayerStatusMenu();">💀 夜间死亡</div>`;
        menuItems += `<div style="padding: 8px 16px;cursor:pointer;" onmouseover="this.style.background='rgba(239,68,68,0.1)'" onmouseout="this.style.background='transparent'" onclick="updatePlayerStatus(${playerId}, {is_alive: false, death_type: 'day_vote'}); hidePlayerStatusMenu();">🗳️ 白天放逐</div>`;
    } else {
        menuItems += `<div style="padding: 8px 16px;cursor:pointer;" onmouseover="this.style.background='rgba(34,197,94,0.1)'" onmouseout="this.style.background='transparent'" onclick="updatePlayerStatus(${playerId}, {is_alive: true}); hidePlayerStatusMenu();">✨ 复活</div>`;
    }

    menuItems += `<div style="border-top:1px solid var(--border-color);margin:4px 0;"></div>`;
    menuItems += `<div style="padding: 8px 16px;cursor:pointer;color:#94a3b8;" onmouseover="this.style.background='rgba(0,240,255,0.1)'" onmouseout="this.style.background='transparent'" onclick="hidePlayerStatusMenu();">取消</div>`;

    menu.innerHTML = menuItems;
    document.body.appendChild(menu);

    // 点击其他地方关闭菜单
    setTimeout(() => {
        document.addEventListener('click', hidePlayerStatusMenu, { once: true });
    }, 10);
}

// 隐藏玩家状态菜单
function hidePlayerStatusMenu() {
    const menu = document.getElementById('player-status-context-menu');
    if (menu) menu.remove();
}

// 更新玩家状态
async function updatePlayerStatus(playerId, statusData) {
    try {
        const result = await api('PUT', `/games/${gameId}/players/${playerId}/status`, statusData);
        if (result && result.success) {
            // 更新本地gamePlayers数据
            const index = gamePlayers.findIndex(gp => gp.player_id === playerId);
            if (index !== -1 && result.data) {
                gamePlayers[index] = { ...gamePlayers[index], ...result.data };
            }
            // 重新渲染玩家书签
            renderPlayerBookmarks();
            // 如果当前选中的是这个玩家，重新渲染预测结果
            if (selectedPlayerId === playerId) {
                renderSelectedPlayerPrediction();
            }
            showToast('玩家状态已更新', 'success');
        }
    } catch (error) {
        showToast('更新玩家状态失败: ' + error.message, 'error');
    }
}

// 显示上警设置模态框
function showPoliceSetupModal() {
    const modal = document.getElementById('police-setup-modal');
    if (!modal) {
        // 动态创建模态框
        const modalHtml = `
        <div class="modal-overlay" id="police-setup-modal">
            <div class="modal" style="max-width:500px;">
                <div class="modal-title">上警设置</div>
                <p style="font-size:13px;color:#94a3b8;margin-bottom:16px;">请选择上警的玩家（警上玩家不能投警徽票）</p>
                <div id="police-setup-list" style="max-height:300px;overflow-y:auto;margin-bottom:16px;"></div>
                <div class="modal-footer">
                    <button class="btn btn-secondary" onclick="hideModal('police-setup-modal')">取消</button>
                    <button class="btn btn-primary" onclick="savePoliceSetup()">保存</button>
                </div>
            </div>
        </div>`;
        document.body.insertAdjacentHTML('beforeend', modalHtml);
    }

    // 渲染玩家列表
    const list = document.getElementById('police-setup-list');
    let html = '';
    const sortedPlayers = [...gamePlayers].sort((a, b) => {
        const seatA = a.seat_number;
        const seatB = b.seat_number;
        if (!seatA && !seatB) return 0;
        if (!seatA) return 1;
        if (!seatB) return -1;
        return seatA - seatB;
    });

    sortedPlayers.forEach(gp => {
        const isAlive = gp.is_alive !== false;
        const isChecked = gp.is_on_police;
        const seatLabel = gp.seat_number ? `${gp.seat_number}号 ` : '';
        html += `<label style="display:flex;align-items:center;gap:8px;padding:8px;border-bottom:1px solid rgba(255,255,255,0.05);${!isAlive ? 'opacity:0.5;' : ''}">
            <input type="checkbox" value="${gp.player_id}" ${isChecked ? 'checked' : ''} ${!isAlive ? 'disabled' : ''}>
            <span>${seatLabel}${escapeHtml(gp.player_name)}</span>
            ${!isAlive ? '<span style="color:#ef4444;font-size:12px;">(已死亡)</span>' : ''}
        </label>`;
    });
    list.innerHTML = html;

    showModal('police-setup-modal');
}

// 保存上警设置
async function savePoliceSetup() {
    const checkboxes = document.querySelectorAll('#police-setup-list input[type="checkbox"]:checked');
    const policePlayerIds = Array.from(checkboxes).map(cb => parseInt(cb.value));

    try {
        const result = await api('PUT', `/games/${gameId}/players/police`, { police_player_ids: policePlayerIds });
        if (result && result.success) {
            // 重新加载游戏数据
            await loadGame();
            hideModal('police-setup-modal');
            showToast('上警设置已保存', 'success');
        }
    } catch (error) {
        showToast('保存上警设置失败: ' + error.message, 'error');
    }
}
