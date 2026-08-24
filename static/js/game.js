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

// 通用模态框函数
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
            html += `<div class="timeline-item">
                <div class="timeline-dot"></div>
                <div class="timeline-content">
                    <div class="timeline-header">
                        <span class="timeline-index">#${globalIndex++}</span>
                        ${phaseInfo ? `<span class="badge badge-info">${escapeHtml(phaseInfo)}</span>` : ''}
                        ${b.actor_role_name ? `<span class="badge badge-good">声明:${escapeHtml(b.actor_role_name)}</span>` : ''}
                        ${b.actor_camp ? campBadge(b.actor_camp) : ''}
                    </div>
                    <div class="timeline-body">
                        <span class="behavior-actor">${escapeHtml(b.actor_name)}</span>
                        <span class="behavior-action">${escapeHtml(b.action_name)}</span>
                        ${b.target_name ? `<span class="behavior-target">→ ${escapeHtml(b.target_name)}</span>` : ''}
                        ${b.notes ? `<span class="behavior-notes" title="${escapeHtml(b.notes)}">📝</span>` : ''}
                    </div>
                    ${gameData.status === '进行中' ? `<span class="behavior-delete" onclick="deleteBehavior(${b.id})" title="删除">✕</span>` : ''}
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
        // 保存当前行为发起者的选择（重新加载后恢复）
        const savedActorId = document.getElementById('behavior-actor').value;
        // 清空表单（保留行为发起者）
        document.getElementById('behavior-notes').value = '';
        clearSelectedActions();
        // 重新加载
        await loadGame();
        // 恢复行为发起者的选择
        if (savedActorId) {
            setTimeout(() => {
                const actorSelect = document.getElementById('behavior-actor');
                if (actorSelect) {
                    actorSelect.value = savedActorId;
                    // 触发可搜索下拉框的显示更新
                    const display = actorSelect.nextElementSibling;
                    if (display && display.classList.contains('searchable-select')) {
                        const opt = actorSelect.querySelector(`option[value="${savedActorId}"]`);
                        if (opt) {
                            display.querySelector('.searchable-select-display').textContent = opt.textContent;
                        }
                    }
                }
            }, 100);
        }
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
            info.textContent = '未选择行为';
            info.className = 'selected-actions-info';
        } else {
            // 获取已选行为的名称
            const selectedNames = selectedActionIds.map(id => {
                const action = allActions.find(a => a.id === id);
                return action ? action.name : `未知行为(${id})`;
            });
            // 显示前3个，超过的用+N表示
            let displayText;
            if (selectedNames.length <= 3) {
                displayText = `已选 ${selectedActionIds.length} 个：${selectedNames.join('、')}`;
            } else {
                displayText = `已选 ${selectedActionIds.length} 个：${selectedNames.slice(0, 3).join('、')} 等`;
            }
            info.textContent = displayText;
            info.className = 'selected-actions-info has-selection';
            // 添加title属性，鼠标悬停显示全部
            info.title = `已选行为：${selectedNames.join('、')}`;
        }
    }
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
function showConfirmIdentityModal() {
    if (!selectedPlayerId) {
        showToast('请先选择一个玩家', 'error');
        return;
    }
    const player = allPlayers.find(p => p.id === selectedPlayerId);
    document.getElementById('confirm-identity-player-name').textContent = player ? player.name : '';
    // 填充身份下拉框
    const roleSelect = document.getElementById('confirm-role-select');
    roleSelect.innerHTML = '';
    allRoles.forEach(role => {
        const opt = document.createElement('option');
        opt.value = role.id;
        opt.textContent = role.name + ' (' + role.camp + ')';
        roleSelect.appendChild(opt);
    });
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
