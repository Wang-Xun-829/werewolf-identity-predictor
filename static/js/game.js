// 对局详情页

const gameId = document.getElementById('game-id').value;
let gameData = null;
let allPlayers = [];
let allActions = [];
let allRoles = [];
let gamePlayers = [];
let predictions = [];
let selectedPlayerId = null;  // 当前选中的玩家ID（书签切换）

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
}

// 填充下拉选择框
function populateSelects() {
    const actorSelect = document.getElementById('behavior-actor');
    const targetSelect = document.getElementById('behavior-target');
    const actionSelect = document.getElementById('behavior-action');
    const roleSelect = document.getElementById('behavior-role');

    actorSelect.innerHTML = '<option value="">请选择发起者</option>';
    targetSelect.innerHTML = '<option value="">无目标</option>';
    gamePlayers.forEach(gp => {
        const seat = gp.seat_number ? `${gp.seat_number}号 ` : '';
        actorSelect.innerHTML += `<option value="${gp.player_id}">${seat}${escapeHtml(gp.player_name)}</option>`;
        targetSelect.innerHTML += `<option value="${gp.player_id}">${seat}${escapeHtml(gp.player_name)}</option>`;
    });

    // 行为选择使用 autocomplete 搜索框（不再用 select）
    initActionAutocomplete();

    roleSelect.innerHTML = '<option value="">不声明</option>';
    allRoles.forEach(r => {
        roleSelect.innerHTML += `<option value="${r.id}">${escapeHtml(r.name)} (${r.camp})</option>`;
    });
}

// 加载预测结果
async function loadPredictions() {
    const result = await api('GET', `/games/${gameId}/predictions`);
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
}

// 渲染玩家书签列表
function renderPlayerBookmarks() {
    const container = document.getElementById('players-bookmarks');
    let html = '';
    predictions.forEach(p => {
        const seat = gamePlayers.find(gp => gp.player_id === p.player_id)?.seat_number;
        const seatLabel = seat ? `${seat}号 ` : '';
        const isActive = p.player_id === selectedPlayerId;
        const topCamp = p.all_probabilities && p.all_probabilities[0] ? p.all_probabilities[0].camp : '';
        const topRoleCls = getCampClass(topCamp);
        html += `<div class="player-bookmark ${isActive ? 'active' : ''}" onclick="selectPlayer(${p.player_id})">
            <span class="bookmark-name">${seatLabel}${escapeHtml(p.player_name)}</span>
            <span class="bookmark-role badge badge-${topRoleCls}">${escapeHtml(p.top_role_name || '-')}</span>
        </div>`;
    });
    container.innerHTML = html;
}

// 切换选中玩家
function selectPlayer(playerId) {
    selectedPlayerId = playerId;
    renderPlayerBookmarks();
    renderSelectedPlayerPrediction();
}

// 渲染选中玩家的详细预测结果
function renderSelectedPlayerPrediction() {
    const card = document.getElementById('selected-player-prediction-card');
    const container = document.getElementById('selected-player-prediction');
    const nameEl = document.getElementById('selected-player-name');
    const topRoleEl = document.getElementById('selected-player-top-role');

    const p = predictions.find(x => x.player_id === selectedPlayerId);
    if (!p) {
        card.style.display = 'none';
        return;
    }

    card.style.display = 'block';
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

// 渲染行为记录
function renderBehaviors(behaviors) {
    const container = document.getElementById('behavior-list');
    document.getElementById('behavior-count').textContent = `共 ${behaviors.length} 条`;
    if (behaviors.length === 0) {
        container.innerHTML = '<div class="empty-state"><p>暂无行为记录</p></div>';
        return;
    }
    let html = '';
    behaviors.forEach(b => {
        const roundInfo = b.round_number ? `D${b.round_number}` : '';
        const phaseInfo = b.phase || '';
        const meta = [roundInfo, phaseInfo].filter(Boolean).join(' ');
        html += `<div class="behavior-item">
            <span class="behavior-actor">${escapeHtml(b.actor_name)}</span>
            <span class="behavior-action">${escapeHtml(b.action_name)}</span>
            <span class="behavior-target">${b.target_name ? '→ ' + escapeHtml(b.target_name) : ''}</span>
            ${b.actor_role_name ? `<span class="badge badge-info">声明:${escapeHtml(b.actor_role_name)}</span>` : ''}
            ${b.actor_camp ? campBadge(b.actor_camp) : ''}
            <span class="behavior-meta">${meta}</span>
            ${gameData.status === '进行中' ? `<span class="behavior-delete" onclick="deleteBehavior(${b.id})" title="删除">✕</span>` : ''}
        </div>`;
    });
    container.innerHTML = html;
}

// 添加行为
async function addBehavior() {
    const actorId = document.getElementById('behavior-actor').value;
    const actionId = document.getElementById('behavior-action').value;
    if (!actorId) { showToast('请选择行为发起者', 'error'); return; }
    if (!actionId) { showToast('请选择具体行为', 'error'); return; }

    const data = {
        actor_id: parseInt(actorId),
        action_id: parseInt(actionId)
    };
    const targetId = document.getElementById('behavior-target').value;
    const roleId = document.getElementById('behavior-role').value;
    const camp = document.getElementById('behavior-camp').value;
    const round = document.getElementById('behavior-round').value;
    const phase = document.getElementById('behavior-phase').value;
    const notes = document.getElementById('behavior-notes').value.trim();

    if (targetId) data.target_id = parseInt(targetId);
    if (roleId) data.actor_role_id = parseInt(roleId);
    if (camp) data.actor_camp = camp;
    if (round) data.round_number = parseInt(round);
    if (phase) data.phase = phase;
    if (notes) data.notes = notes;

    const result = await api('POST', `/games/${gameId}/behaviors`, data);
    if (result) {
        showToast('行为已录入', 'success');
        // 清空表单部分字段
        document.getElementById('behavior-notes').value = '';
        document.getElementById('behavior-action-input').value = '';
        document.getElementById('behavior-action').value = '';
        // 重新加载
        await loadGame();
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

// 添加玩家到对局
function showAddPlayerModal() {
    const select = document.getElementById('add-player-select');
    const addedIds = new Set(gamePlayers.map(gp => gp.player_id));
    const available = allPlayers.filter(p => !addedIds.has(p.id));
    if (available.length === 0) {
        showToast('所有玩家都已添加，或请先去玩家管理页创建玩家', 'info');
        return;
    }
    select.innerHTML = '<option value="">请选择玩家</option>';
    available.forEach(p => {
        select.innerHTML += `<option value="${p.id}">${escapeHtml(p.name)}</option>`;
    });
    document.getElementById('add-player-seat').value = '';
    document.getElementById('add-player-modal').classList.add('show');
}

async function addPlayerToGame() {
    const playerId = document.getElementById('add-player-select').value;
    const seat = document.getElementById('add-player-seat').value;
    if (!playerId) { showToast('请选择玩家', 'error'); return; }
    const data = { player_id: parseInt(playerId) };
    if (seat) data.seat_number = parseInt(seat);
    const result = await api('POST', `/games/${gameId}/players`, data);
    if (result) {
        showToast('玩家已添加', 'success');
        hideModal('add-player-modal');
        await loadGame();
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
function showConfirmModal() {
    const container = document.getElementById('confirm-roles-list');
    let html = '';
    gamePlayers.forEach(gp => {
        const seat = gp.seat_number ? `${gp.seat_number}号 ` : '';
        html += `<div class="form-group">
            <label>${seat}${escapeHtml(gp.player_name)} 的真实身份</label>
            <select class="form-control" id="confirm-role-${gp.player_id}">
                <option value="">请选择身份</option>`;
        allRoles.forEach(r => {
            const selected = gp.actual_role_id === r.id ? 'selected' : '';
            html += `<option value="${r.id}" ${selected}>${escapeHtml(r.name)} (${r.camp})</option>`;
        });
        html += `</select></div>`;
    });
    container.innerHTML = html;
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
// 行为搜索自动补全（Autocomplete）
// ============================================================
let actionAutocompleteState = {
    selectedIndex: -1,
    filteredActions: []
};

function initActionAutocomplete() {
    const input = document.getElementById('behavior-action-input');
    const dropdown = document.getElementById('action-dropdown');
    if (!input || !dropdown) return;

    // 聚焦时显示所有行为（按字母排序）
    input.addEventListener('focus', () => {
        renderActionDropdown('');
        dropdown.classList.add('show');
    });

    // 输入时实时过滤
    input.addEventListener('input', (e) => {
        const keyword = e.target.value.trim().toLowerCase();
        renderActionDropdown(keyword);
        dropdown.classList.add('show');
        // 用户重新输入时清空已选中的隐藏值
        document.getElementById('behavior-action').value = '';
    });

    // 键盘导航（上下箭头选择、回车确认、ESC关闭）
    input.addEventListener('keydown', (e) => {
        const items = dropdown.querySelectorAll('.autocomplete-item');
        if (e.key === 'ArrowDown') {
            e.preventDefault();
            actionAutocompleteState.selectedIndex = Math.min(
                actionAutocompleteState.selectedIndex + 1,
                items.length - 1
            );
            updateActiveItem(items);
        } else if (e.key === 'ArrowUp') {
            e.preventDefault();
            actionAutocompleteState.selectedIndex = Math.max(
                actionAutocompleteState.selectedIndex - 1,
                0
            );
            updateActiveItem(items);
        } else if (e.key === 'Enter') {
            e.preventDefault();
            if (actionAutocompleteState.selectedIndex >= 0 && items[actionAutocompleteState.selectedIndex]) {
                items[actionAutocompleteState.selectedIndex].click();
            }
        } else if (e.key === 'Escape') {
            dropdown.classList.remove('show');
        }
    });

    // 点击输入框外部时关闭下拉
    document.addEventListener('click', (e) => {
        if (!e.target.closest('#action-autocomplete')) {
            dropdown.classList.remove('show');
        }
    });

    // 事件委托：点击下拉项时选中（避免内联onclick的引号冲突）
    dropdown.addEventListener('click', (e) => {
        const item = e.target.closest('.autocomplete-item');
        if (!item) return;
        const id = parseInt(item.dataset.id);
        const name = item.dataset.name;
        const index = parseInt(item.dataset.index);
        selectAction(id, name, index);
    });
}

function renderActionDropdown(keyword) {
    const dropdown = document.getElementById('action-dropdown');
    // 过滤：匹配行为名称或描述
    const filtered = keyword
        ? allActions.filter(a =>
            a.name.toLowerCase().includes(keyword) ||
            (a.description && a.description.toLowerCase().includes(keyword))
        )
        : allActions;

    actionAutocompleteState.filteredActions = filtered;
    actionAutocompleteState.selectedIndex = -1;

    if (filtered.length === 0) {
        dropdown.innerHTML = '<div class="autocomplete-empty">未找到匹配的行为，可去库管理页新增</div>';
        return;
    }

    let html = '';
    filtered.forEach((a, index) => {
        html += `<div class="autocomplete-item" data-id="${a.id}" data-name="${escapeHtml(a.name)}" data-index="${index}">
            <strong>${escapeHtml(a.name)}</strong>
            ${a.description ? `<div class="item-desc">${escapeHtml(a.description)}</div>` : ''}
        </div>`;
    });
    dropdown.innerHTML = html;
}

function selectAction(id, name, index) {
    document.getElementById('behavior-action').value = id;
    document.getElementById('behavior-action-input').value = name;
    document.getElementById('action-dropdown').classList.remove('show');
    actionAutocompleteState.selectedIndex = index;
}

function updateActiveItem(items) {
    items.forEach((item, i) => {
        item.classList.toggle('active', i === actionAutocompleteState.selectedIndex);
    });
    // 自动滚动到选中项
    const active = items[actionAutocompleteState.selectedIndex];
    if (active) {
        active.scrollIntoView({ block: 'nearest' });
    }
}
