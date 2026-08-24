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

    // 行为选择使用多选标签
    initActionMultiSelect();

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
        const canRemove = gameData && gameData.status === '进行中';
        html += `<div class="player-bookmark ${isActive ? 'active' : ''}" onclick="selectPlayer(${p.player_id})">
            <span class="bookmark-name">${seatLabel}${escapeHtml(p.player_name)}</span>
            <span style="display:flex;align-items:center;gap:6px;">
                <span class="bookmark-role badge badge-${topRoleCls}">${escapeHtml(p.top_role_name || '-')}</span>
                ${canRemove ? `<span class="bookmark-remove" onclick="event.stopPropagation(); removePlayerFromGame(${p.player_id}, '${escapeHtml(p.player_name)}')" title="移除玩家">✕</span>` : ''}
            </span>
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
    const round = document.getElementById('behavior-round').value;
    const phase = document.getElementById('behavior-phase').value;
    const notes = document.getElementById('behavior-notes').value.trim();

    if (targetId) data.target_id = parseInt(targetId);
    if (roleId) data.actor_role_id = parseInt(roleId);
    if (camp) data.actor_camp = camp;
    if (round) data.round_number = parseInt(round);
    if (phase) data.phase = phase;
    if (notes) data.notes = notes;

    const result = await api('POST', `/games/${gameId}/behaviors/batch`, data);
    if (result) {
        const count = result.data ? result.data.created_count : selectedActionIds.length;
        showToast(`成功录入 ${count} 条行为`, 'success');
        // 清空表单
        document.getElementById('behavior-notes').value = '';
        clearSelectedActions();
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

// 添加玩家到对局（多选）
function showAddPlayerModal() {
    const list = document.getElementById('add-player-list');
    const addedIds = new Set(gamePlayers.map(gp => gp.player_id));

    if (allPlayers.length === 0) {
        list.innerHTML = '<div class="empty-state"><p>暂无玩家，请先去玩家管理页创建</p></div>';
        document.getElementById('add-player-modal').classList.add('show');
        return;
    }

    let html = '';
    allPlayers.forEach(p => {
        const inGame = addedIds.has(p.id);
        html += `<label>
            <input type="checkbox" value="${p.id}" ${inGame ? 'checked disabled' : ''} onchange="updateSelectedCount()">
            <span>${escapeHtml(p.name)}</span>
            ${inGame ? '<span class="player-in-game">已在对局</span>' : ''}
        </label>`;
    });
    list.innerHTML = html;
    updateSelectedCount();
    document.getElementById('add-player-modal').classList.add('show');
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
    const checked = document.querySelectorAll('#add-player-list input[type="checkbox"]:checked:not(:disabled)');
    if (checked.length === 0) {
        showToast('请至少选择一名玩家', 'error');
        return;
    }

    const addedIds = new Set(gamePlayers.map(gp => gp.player_id));
    const toAdd = Array.from(checked).map(cb => parseInt(cb.value)).filter(id => !addedIds.has(id));

    if (toAdd.length === 0) {
        showToast('选中的玩家都已在对局中', 'info');
        return;
    }

    let successCount = 0;
    let failCount = 0;

    for (let i = 0; i < toAdd.length; i++) {
        const data = { player_id: toAdd[i] };
        const result = await api('POST', `/games/${gameId}/players`, data);
        if (result) {
            successCount++;
        } else {
            failCount++;
        }
    }

    if (successCount > 0) {
        showToast(`成功添加 ${successCount} 名玩家${failCount > 0 ? `，${failCount} 名失败` : ''}`, 'success');
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
// 行为多选标签（Multi-Select Tags）
// ============================================================
let selectedActionIds = [];  // 已选中的行为ID列表

function initActionMultiSelect() {
    const searchInput = document.getElementById('behavior-action-search');
    const tagsGrid = document.getElementById('action-tags-grid');
    if (!searchInput || !tagsGrid) return;

    // 输入时实时过滤
    searchInput.addEventListener('input', (e) => {
        renderActionTags(e.target.value.trim().toLowerCase());
    });

    // 事件委托：点击标签选中/取消选中
    tagsGrid.addEventListener('click', (e) => {
        const tag = e.target.closest('.action-tag');
        if (!tag) return;
        const id = parseInt(tag.dataset.id);
        toggleAction(id);
    });

    // 初始渲染
    renderActionTags('');
}

function renderActionTags(keyword) {
    const grid = document.getElementById('action-tags-grid');
    // 过滤：匹配行为名称或描述
    const filtered = keyword
        ? allActions.filter(a =>
            a.name.toLowerCase().includes(keyword) ||
            (a.description && a.description.toLowerCase().includes(keyword))
        )
        : allActions;

    if (filtered.length === 0) {
        grid.innerHTML = '<div class="empty-state"><p>未找到匹配的行为</p></div>';
        return;
    }

    // 构建父子关系，树形展示
    const parentToChildren = {};
    const rootActions = [];
    filtered.forEach(a => {
        if (a.parent_id && filtered.find(x => x.id === a.parent_id)) {
            if (!parentToChildren[a.parent_id]) parentToChildren[a.parent_id] = [];
            parentToChildren[a.parent_id].push(a);
        } else {
            rootActions.push(a);
        }
    });

    let html = '';
    function renderActionTag(a, level) {
        const isSelected = selectedActionIds.includes(a.id);
        const hasChildren = parentToChildren[a.id] && parentToChildren[a.id].length > 0;
        const indent = level > 0 ? 'style="margin-left:' + (level * 16) + 'px;"' : '';
        html += `<div class="action-tag ${isSelected ? 'selected' : ''} ${level > 0 ? 'child-tag' : ''}" data-id="${a.id}" ${indent}>
            <span class="action-tag-name">${hasChildren ? '📁 ' : ''}${escapeHtml(a.name)}</span>
            ${isSelected ? '<span class="action-tag-check">✓</span>' : ''}
        </div>`;
        // 递归渲染子行为
        const children = parentToChildren[a.id] || [];
        children.forEach(child => renderActionTag(child, level + 1));
    }

    rootActions.forEach(a => renderActionTag(a, 0));
    grid.innerHTML = html;
    updateSelectedActionsInfo();
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
        info.textContent = `已选 ${selectedActionIds.length} 个行为`;
        info.className = `selected-actions-info ${selectedActionIds.length > 0 ? 'has-selection' : ''}`;
    }
}

function clearSelectedActions() {
    selectedActionIds = [];
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
