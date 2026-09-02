// 对局页面逻辑

// 当前游戏数据（用于查找玩家ID等）
let currentGameData = null;

// 打开对局详情
async function openGameDetail(gameId) {
    currentGameId = gameId;
    currentPlayerId = null;
    selectedActionIds = [];
    currentGameData = null;
    
    await loadBaseData();
    
    // 切换到对局详情页面
    document.querySelectorAll('.page').forEach(p => p.classList.remove('active'));
    document.getElementById('page-game-detail').classList.add('active');
    
    // 加载对局信息
    const game = await GameAPI.get(gameId);
    document.getElementById('game-detail-title').textContent = game.name || '未命名对局';
    document.getElementById('current-phase').textContent = game.current_phase || '未开始';
    document.getElementById('current-round').textContent = `第${game.current_round || 1}轮`;
    
    // 加载玩家列表
    await loadGamePlayers();
    
    // 加载行为树
    await loadActionTree();
    
    // 加载行为记录
    await loadBehaviorRecords();
    
    // 加载预测结果
    await refreshPredictions();
    
    // 初始化高级分析标签
    initAnalysisTabs();
}

// 返回对局列表
function backToGames() {
    currentGameId = null;
    currentPlayerId = null;
    switchPage('games');
}

// 加载对局玩家列表
// 16个座位号对应的颜色
const SEAT_COLORS = [
    '#ff4444', '#ff8844', '#ffbb33', '#00C851',
    '#00bcd4', '#33b5e5', '#aa66cc', '#ff6699',
    '#cc0000', '#ff6600', '#ff8800', '#007E33',
    '#0097a7', '#0099cc', '#7b1fa2', '#c2185b'
];

// 神职身份列表
const GOD_ROLES = ['预言家', '女巫', '猎人', '守卫', '骑士', '白痴', '长老', '丘比特', '驯熊师', '禁言长老', '摄梦人', '魔术师'];

// 根据预测结果判断阵营倾向颜色
function getCampColorClass(predictions) {
    if (!predictions || Object.keys(predictions).length === 0) return '';
    
    const sorted = Object.entries(predictions).sort((a, b) => b[1] - a[1]);
    if (sorted.length === 0) return '';
    
    const [topIdentity, topProb] = sorted[0];
    
    // 阈值：超过15%才显示颜色（因为身份多，单身份概率可能不高）
    if (topProb < 0.15) return '';
    
    if (topIdentity.includes('狼') || topIdentity.includes('狼美人') || topIdentity.includes('狼王')) {
        return 'camp-wolf';
    } else if (GOD_ROLES.includes(topIdentity)) {
        return 'camp-god';
    } else {
        return 'camp-good';
    }
}

async function loadGamePlayers() {
    const game = await GameAPI.get(currentGameId);
    currentGameData = game;
    const container = document.getElementById('game-players-list');
    
    if (!game.players || game.players.length === 0) {
        container.innerHTML = '<p class="empty-text">暂无玩家</p>';
        return;
    }
    
    // 获取预测结果
    let predictionsData = {};
    let campData = {};
    try {
        const predResult = await GameAPI.getPredictions(currentGameId);
        console.log('预测结果原始数据:', predResult);
        if (predResult && predResult.predictions) {
            predResult.predictions.forEach(p => {
                predictionsData[p.player_id] = p.predictions || {};
                campData[p.player_id] = {
                    top_guess: p.top_guess,
                    confidence: p.confidence,
                    camp_prediction: p.camp_prediction
                };
                console.log(`玩家${p.player_id}的预测:`, p.top_guess, p.confidence, p.camp_prediction);
            });
        }
    } catch (e) {
        console.error('获取预测结果失败:', e);
    }
    
    // 按座位号排序（没有座位号的排后面）
    const sortedPlayers = [...game.players].sort((a, b) => {
        if (a.seat_number && b.seat_number) return a.seat_number - b.seat_number;
        if (a.seat_number) return -1;
        if (b.seat_number) return 1;
        return 0;
    });
    
    container.innerHTML = sortedPlayers.map(p => {
        // 直接使用后端返回的top_guess和camp_prediction判断阵营颜色
        let campClass = '';
        const campInfo = campData[p.player_id];
        if (campInfo && campInfo.top_guess && campInfo.confidence >= 0.15) {
            // 狼人阵营判断：camp_prediction为wolf 或者 top_guess包含"狼"
            const isWolf = campInfo.camp_prediction === 'wolf' || 
                          (campInfo.top_guess && campInfo.top_guess.includes('狼'));
            // 神职判断：top_guess在神职列表中
            const isGod = GOD_ROLES.includes(campInfo.top_guess);
            
            if (isWolf) {
                campClass = 'camp-wolf';
            } else if (isGod) {
                campClass = 'camp-god';
            } else if (campInfo.camp_prediction === 'good') {
                campClass = 'camp-good';
            }
        }
        // 内联样式 - 确保阵营背景颜色生效（不依赖CSS文件）
        let campStyle = '';
        if (campClass === 'camp-wolf') {
            campStyle = 'background-color: rgba(239, 83, 80, 0.18); border: 1px solid rgba(239, 83, 80, 0.4);';
        } else if (campClass === 'camp-god') {
            campStyle = 'background-color: rgba(255, 202, 40, 0.18); border: 1px solid rgba(255, 202, 40, 0.4);';
        } else if (campClass === 'camp-good') {
            campStyle = 'background-color: rgba(66, 165, 245, 0.18); border: 1px solid rgba(66, 165, 245, 0.4);';
        }
        
        // 状态 - 带文字的小圆圈
        let policeClass, policeText, policeTitle;
        if (p.is_on_police && !p.is_retired) {
            policeClass = 'dot-police';
            policeText = '警';
            policeTitle = '上警';
        } else if (p.is_on_police && p.is_retired) {
            policeClass = 'dot-retired';
            policeText = '退';
            policeTitle = '退水';
        } else {
            policeClass = 'dot-civilian';
            policeText = '投';
            policeTitle = '警下（有投票权）';
        }
        
        const aliveClass = p.is_alive ? 'dot-alive-small' : 'dot-dead-small';
        const aliveText = p.is_alive ? '活' : '亡';
        const aliveTitle = p.is_alive ? '存活' : '出局';
        
        // 警长标记
        const isSheriff = p.is_sheriff || false;
        const seatDisplay = isSheriff ? '👑' : (p.seat_number ? p.seat_number : '-');
        
        return `
        <div class="player-item ${currentPlayerId === p.player_id ? 'selected' : ''} ${campClass}" 
             style="${campStyle}"
             data-player-id="${p.player_id}"
             onclick="selectPlayer(${p.player_id})">
            <div class="player-seat-box ${isSheriff ? 'sheriff-seat' : ''}">
                ${seatDisplay}
            </div>
            <div class="player-name-main">${p.player_name || '未知玩家'}</div>
            <div class="player-status-dots">
                <span class="status-dot-text ${policeClass}" title="${policeTitle}">${policeText}</span>
                <span class="status-dot-text ${aliveClass}" title="${aliveTitle}">${aliveText}</span>
            </div>
            <div class="player-actions-col player-actions-outside" onclick="event.stopPropagation()">
                <button class="player-action-btn" onclick="showEditPlayerStatusModal(${p.player_id}, ${p.is_on_police || 'false'}, ${p.is_retired || 'false'}, ${p.is_alive || 'false'})" title="设置状态">⚙</button>
                <button class="player-action-btn" onclick="showEditSeatModal(${p.player_id}, ${p.seat_number || 'null'})" title="编辑座位">✎</button>
                <button class="player-action-btn btn-remove" onclick="removePlayerFromGame(${p.player_id})" title="移除玩家">✕</button>
            </div>
        </div>
    `}).join('');
    
    // 更新行为录入的玩家下拉框
    updatePlayerSelects(sortedPlayers);
}

// 更新玩家选择下拉框 - 显示座位号
function updatePlayerSelects(players) {
    const playerSelect = document.getElementById('action-player');
    const targetSelect = document.getElementById('action-target');
    const declaredIdentitySelect = document.getElementById('action-declared-identity');
    
    const formatPlayer = (p) => {
        const seat = p.seat_number ? `[${p.seat_number}号] ` : '';
        return `${seat}${p.player_name}`;
    };
    
    playerSelect.innerHTML = players.map(p => 
        `<option value="${p.player_id}" ${currentPlayerId === p.player_id ? 'selected' : ''}>${formatPlayer(p)}</option>`
    ).join('');
    
    targetSelect.innerHTML = '<option value="">无</option>' + 
        players.map(p => `<option value="${p.player_id}">${formatPlayer(p)}</option>`).join('');
    
    declaredIdentitySelect.innerHTML = '<option value="">无</option>' +
        allIdentities.map(i => `<option value="${i.id}">${i.name}</option>`).join('');
}

// 选择玩家
async function selectPlayer(playerId) {
    currentPlayerId = playerId;
    document.getElementById('action-player').value = playerId;
    await loadGamePlayers();
    await loadPredictionForPlayer(playerId);
}

// 从对局中移除玩家
async function removePlayerFromGame(playerId) {
    // 获取玩家名字用于提示
    let playerName = '该玩家';
    if (currentGameData && currentGameData.players) {
        const player = currentGameData.players.find(p => p.player_id === playerId);
        if (player) playerName = player.player_name;
    }
    
    if (!confirm(`确定要将【${playerName}】从本局游戏中移除吗？`)) return;
    
    try {
        const result = await GameAPI.removePlayer(currentGameId, playerId);
        if (result && !result.detail) {
            showToast(`已将【${playerName}】从本局移除`);
            // 如果移除的是当前选中的玩家，清空选中
            if (currentPlayerId === playerId) {
                currentPlayerId = null;
                document.getElementById('prediction-result').innerHTML = '<p class="empty-text">点击左侧玩家查看预测结果</p>';
            }
            await loadGamePlayers();
        } else {
            showToast(result.detail || '移除失败', 'error');
        }
    } catch (error) {
        showToast('移除失败: ' + error.message, 'error');
    }
}

// 修改座位号弹窗
function showEditSeatModal(playerId, currentSeat) {
    // 获取玩家名字
    let playerName = '该玩家';
    if (currentGameData && currentGameData.players) {
        const player = currentGameData.players.find(p => p.player_id === playerId);
        if (player) playerName = player.player_name;
    }
    
    showModal(`修改座位号 - ${playerName}`, `
        <div class="form-group">
            <label>座位号</label>
            <input type="number" id="edit-seat-number" value="${currentSeat || ''}" placeholder="输入座位号，留空表示无座位">
        </div>
        <div style="font-size: 12px; color: var(--text-muted); margin-top: 8px;">
            修改后玩家列表将按座位号重新排序
        </div>
    `, `
        <button class="btn btn-secondary" onclick="closeModal()">取消</button>
        <button class="btn btn-primary" onclick="confirmEditSeat(${playerId})">确认修改</button>
    `);
}

// 确认修改座位号
async function confirmEditSeat(playerId) {
    const seatInput = document.getElementById('edit-seat-number');
    const seatNumber = parseInt(seatInput.value) || null;
    
    try {
        const result = await GameAPI.updatePlayer(currentGameId, playerId, { seat_number: seatNumber });
        if (result && !result.detail) {
            showToast('座位号修改成功');
            closeModal();
            await loadGamePlayers();
        } else {
            showToast(result.detail || '修改失败', 'error');
        }
    } catch (error) {
        showToast('修改失败: ' + error.message, 'error');
    }
}

// 显示编辑玩家状态弹窗
function showEditPlayerStatusModal(playerId, isOnPolice, isRetired, isAlive) {
    // 获取玩家名字
    let playerName = '该玩家';
    if (currentGameData && currentGameData.players) {
        const player = currentGameData.players.find(p => p.player_id === playerId);
        if (player) playerName = player.player_name;
    }
    
    showModal(`编辑玩家状态 - ${playerName}`, `
        <div class="form-group">
            <label style="display: flex; align-items: center; gap: 10px; cursor: pointer;">
                <input type="checkbox" id="edit-status-police" ${isOnPolice === true || isOnPolice === 'true' ? 'checked' : ''} style="width: 18px; height: 18px; cursor: pointer;">
                <span>上警</span>
            </label>
        </div>
        <div class="form-group">
            <label style="display: flex; align-items: center; gap: 10px; cursor: pointer;">
                <input type="checkbox" id="edit-status-retired" ${isRetired === true || isRetired === 'true' ? 'checked' : ''} style="width: 18px; height: 18px; cursor: pointer;">
                <span>退水</span>
            </label>
        </div>
        <div class="form-group">
            <label style="display: flex; align-items: center; gap: 10px; cursor: pointer;">
                <input type="checkbox" id="edit-status-alive" ${isAlive === true || isAlive === 'true' ? 'checked' : ''} style="width: 18px; height: 18px; cursor: pointer;">
                <span>存活</span>
            </label>
        </div>
        <div style="font-size: 12px; color: var(--text-muted); margin-top: 8px;">
            修改玩家的上警、退水和存活状态
        </div>
    `, `
        <button class="btn btn-secondary" onclick="closeModal()">取消</button>
        <button class="btn btn-primary" onclick="confirmEditPlayerStatus(${playerId})">确认修改</button>
    `);
}

// 确认修改玩家状态
async function confirmEditPlayerStatus(playerId) {
    const isOnPolice = document.getElementById('edit-status-police').checked;
    const isRetired = document.getElementById('edit-status-retired').checked;
    const isAlive = document.getElementById('edit-status-alive').checked;
    
    try {
        const result = await GameFlowAPI.updateStatus(currentGameId, playerId, {
            is_on_police: isOnPolice,
            is_retired: isRetired,
            is_alive: isAlive
        });
        if (result && result.success) {
            showToast('玩家状态修改成功');
            closeModal();
            await loadGamePlayers();
        } else {
            showToast(result.detail || '修改失败', 'error');
        }
    } catch (error) {
        showToast('修改失败: ' + error.message, 'error');
    }
}

// 展开的行为ID集合
let expandedActionIds = new Set();

// 加载行为树 - 级联选择形式
async function loadActionTree() {
    const actions = await ActionAPI.list();
    allActions = actions || [];
    const container = document.getElementById('action-tree');
    
    // 分类名称映射表（英文 → 中文）
    const categoryMap = {
        'IDENTITY_CLAIM': '身份声明',
        'STANCE_EXPRESSION': '立场表达',
        'IDENTITY_CONFLICT': '身份冲突',
        'VOTE_ACTION': '投票行为',
        'IDENTITY_CONFIRM': '身份确认',
        'OTHER': '其他',
        'EVENT': '事件',
        '身份声明': '身份声明',
        '立场表达': '立场表达',
        '身份冲突': '身份冲突',
        '投票行为': '投票行为',
        '身份确认': '身份确认',
        '其他': '其他',
        '事件': '事件'
    };
    
    // 分类显示顺序
    const categoryOrder = ['身份声明', '立场表达', '身份冲突', '投票行为', '身份确认', '事件', '其他'];
    
    // 按分类分组（只包含一级行为）
    const categories = {};
    actions.forEach(action => {
        if (action.parent_id) return; // 跳过非一级行为
        const rawCat = action.category || '其他';
        const cat = categoryMap[rawCat] || rawCat; // 翻译成中文
        if (!categories[cat]) categories[cat] = [];
        categories[cat].push(action);
    });
    
    // 按指定顺序排序分类
    const sortedCategories = Object.entries(categories).sort((a, b) => {
        const orderA = categoryOrder.indexOf(a[0]);
        const orderB = categoryOrder.indexOf(b[0]);
        if (orderA === -1 && orderB === -1) return a[0].localeCompare(b[0]);
        if (orderA === -1) return 1;
        if (orderB === -1) return -1;
        return orderA - orderB;
    });
    
    container.innerHTML = sortedCategories.map(([cat, actionList]) => `
        <div class="action-category">
            <div class="action-category-title">${cat}</div>
            <div class="action-options">
                ${actionList.map(action => renderActionTag(action, 1)).join('')}
            </div>
        </div>
    `).join('');
}

// 渲染单个行为标签（递归）
function renderActionTag(action, level) {
    const hasChildren = action.children && action.children.length > 0;
    const isExpanded = expandedActionIds.has(action.id);
    const isSelected = selectedActionIds.includes(action.id);
    
    let html = `
        <div class="action-item level-${level}">
            <span class="action-tag ${isSelected ? 'selected' : ''} ${hasChildren ? 'has-children' : ''}">
                ${hasChildren ? `<span class="action-arrow ${isExpanded ? 'expanded' : ''}" onclick="toggleActionExpand(${action.id}, event)">▶</span>` : ''}
                <span class="action-name" onclick="toggleActionSelect(${action.id}, event)">${action.name}</span>
            </span>
    `;
    
    // 如果有子行为且已展开，渲染子行为
    if (hasChildren && isExpanded) {
        html += `
            <div class="action-children">
                ${action.children.map(child => renderActionTag(child, level + 1)).join('')}
            </div>
        `;
    }
    
    html += '</div>';
    return html;
}

// 切换行为展开/折叠（点击箭头时调用）
function toggleActionExpand(actionId, event) {
    event.stopPropagation(); // 阻止事件冒泡，避免触发选中
    
    if (expandedActionIds.has(actionId)) {
        expandedActionIds.delete(actionId);
    } else {
        expandedActionIds.add(actionId);
    }
    
    loadActionTree();
}

// 切换行为选中状态（点击行为名称时调用）
function toggleActionSelect(actionId, event) {
    event.stopPropagation(); // 阻止事件冒泡
    
    const index = selectedActionIds.indexOf(actionId);
    if (index > -1) {
        selectedActionIds.splice(index, 1);
    } else {
        selectedActionIds.push(actionId);
    }
    
    // 检测是否选择了骑士决斗行为（ID=65），显示/隐藏决斗结果选择
    const knightDuelGroup = document.getElementById('knight-duel-result-group');
    if (knightDuelGroup) {
        if (selectedActionIds.includes(65)) {
            knightDuelGroup.style.display = 'block';
        } else {
            knightDuelGroup.style.display = 'none';
            // 清除已选择的决斗结果
            document.querySelectorAll('input[name="duel_result"]').forEach(radio => radio.checked = false);
        }
    }
    
    loadActionTree();
}

// 提交行为
async function submitActions() {
    if (selectedActionIds.length === 0) {
        showToast('请选择至少一个行为', 'error');
        return;
    }
    
    const playerId = parseInt(document.getElementById('action-player').value);
    const targetId = parseInt(document.getElementById('action-target').value) || null;
    const declaredIdentityId = parseInt(document.getElementById('action-declared-identity').value) || null;
    const notes = document.getElementById('action-notes').value;
    
    // 骑士决斗结果验证
    let duelResult = null;
    if (selectedActionIds.includes(65)) {
        const selectedDuelResult = document.querySelector('input[name="duel_result"]:checked');
        if (!selectedDuelResult) {
            showToast('请选择骑士决斗的结果', 'error');
            return;
        }
        if (!targetId) {
            showToast('骑士决斗必须选择被决斗的目标玩家', 'error');
            return;
        }
        duelResult = selectedDuelResult.value;
    }
    
    // 获取当前阶段
    const phase = document.getElementById('current-phase').textContent;
    const roundText = document.getElementById('current-round').textContent;
    const round = parseInt(roundText.replace(/[^0-9]/g, '')) || 1;
    
    const result = await GameAPI.createActionsBatch({
        game_id: currentGameId,
        player_id: playerId,
        target_player_id: targetId,
        action_type_ids: selectedActionIds,
        round_number: round,
        phase: phase,
        declared_identity_id: declaredIdentityId,
        notes: notes,
        duel_result: duelResult
    });
    
    if (Array.isArray(result)) {
        showToast(`成功录入${result.length}条行为`);
        selectedActionIds = [];
        document.getElementById('action-notes').value = '';
        await loadActionTree();
        await loadBehaviorRecords();
        await refreshPredictions();
        
        // 保持行为发出者不变
        document.getElementById('action-player').value = playerId;
        // 同时保持行为目标不变（如果有的话）
        if (targetId) {
            document.getElementById('action-target').value = targetId;
        }
    } else {
        showToast('录入失败', 'error');
    }
}

// 清空行为表单
function clearActionForm() {
    selectedActionIds = [];
    document.getElementById('action-target').value = '';
    document.getElementById('action-declared-identity').value = '';
    document.getElementById('action-notes').value = '';
    loadActionTree();
}

// 加载行为记录
async function loadBehaviorRecords() {
    const actions = await GameAPI.getActions(currentGameId);
    const container = document.getElementById('behavior-records-list');
    
    if (!actions || actions.length === 0) {
        container.innerHTML = '<p class="empty-text">暂无行为记录</p>';
        return;
    }
    
    container.innerHTML = actions.map((action, index) => `
        <div class="behavior-record-item">
            <span class="record-round">第${action.round_number}轮</span>
            <span class="record-action">
                <strong>${action.player_name}</strong>
                ${action.target_player_name ? ` → ${action.target_player_name}` : ''}
                : ${action.action_type_name}
                ${action.notes ? ` (${action.notes})` : ''}
            </span>
            <span class="record-result result-${action.result_status || 'unknown'}">
                ${action.result_status === 'correct' ? '正确' : action.result_status === 'incorrect' ? '错误' : '未知'}
            </span>
            <button class="btn btn-small" onclick="deleteAction(${action.id})">删除</button>
        </div>
    `).join('');
}

// 删除行为
async function deleteAction(actionId) {
    if (!confirm('确定删除这条行为记录吗？')) return;
    await GameAPI.deleteAction(actionId);
    showToast('删除成功');
    await loadBehaviorRecords();
    await refreshPredictions();
}

// 刷新预测（同时更新左侧玩家列表颜色和右侧预测结果）
async function refreshPredictions() {
    // 先重新加载玩家列表，更新阵营底色
    await loadGamePlayers();
    
    // 再更新右侧预测结果
    if (currentPlayerId) {
        await loadPredictionForPlayer(currentPlayerId);
    } else {
        document.getElementById('prediction-result').innerHTML = 
            '<p class="empty-text">点击左侧玩家查看预测结果</p>';
    }
}

// 加载指定玩家的预测结果
async function loadPredictionForPlayer(playerId) {
    const result = await GameAPI.getPredictions(currentGameId);
    const container = document.getElementById('prediction-result');
    
    if (!result.predictions || result.predictions.length === 0) {
        container.innerHTML = '<p class="empty-text">暂无预测数据</p>';
        return;
    }
    
    const playerPrediction = result.predictions.find(p => p.player_id === playerId);
    if (!playerPrediction) {
        container.innerHTML = '<p class="empty-text">该玩家暂无预测数据</p>';
        return;
    }
    
    const predictions = playerPrediction.predictions || {};
    const sorted = Object.entries(predictions).sort((a, b) => b[1] - a[1]);
    
    // 获取玩家座位号
    let seatNumber = '-';
    let playerCamp = '未知';
    if (currentGameData && currentGameData.players) {
        const playerInfo = currentGameData.players.find(p => p.player_id === playerId);
        if (playerInfo) {
            seatNumber = playerInfo.seat_number || '-';
            if (playerInfo.actual_identity_name) {
                playerCamp = playerInfo.actual_identity_name.includes('狼') ? '狼人' : '好人';
            }
        }
    }
    
    const topIdentity = sorted[0] ? sorted[0][0] : '未知';
    const topProb = sorted[0] ? sorted[0][1] : 0;
    const isTopWolf = topIdentity.includes('狼');
    const isTopGod = GOD_ROLES.includes(topIdentity);
    
    // 确定阵营显示文字和颜色类
    let campText = '疑似好人';
    let campClass = 'text-good';
    let avatarClass = 'avatar-good';
    if (isTopWolf) {
        campText = '疑似狼人';
        campClass = 'text-wolf';
        avatarClass = 'avatar-wolf';
    } else if (isTopGod) {
        campText = '疑似神职';
        campClass = 'text-god';
        avatarClass = 'avatar-god';
    }
    
    // 解析玩家名字，支持"Mr./Ms."+图标+ID的格式
    let titleText = 'Player';
    let titleIcon = '';
    let playerIdText = playerPrediction.player_name;
    
    const playerName = playerPrediction.player_name || '';
    if (playerName.startsWith('Mr.') || playerName.startsWith('mr.')) {
        titleText = 'Mr.';
        titleIcon = '♂';
        playerIdText = playerName.substring(3).trim();
    } else if (playerName.startsWith('Ms.') || playerName.startsWith('ms.')) {
        titleText = 'Ms.';
        titleIcon = '♀';
        playerIdText = playerName.substring(3).trim();
    }
    
    container.innerHTML = `
        <div class="player-profile-card">
            <!-- 档案头部 -->
            <div class="profile-header">
                <div class="profile-avatar ${avatarClass}">
                    <span class="avatar-seat">${seatNumber}</span>
                </div>
                <div class="profile-info">
                    <div class="profile-title">
                        <span class="title-text">${titleText}</span>
                        ${titleIcon ? `<span class="title-icon">${titleIcon}</span>` : ''}
                    </div>
                    <div class="profile-name">${playerIdText}</div>
                </div>
                <div class="profile-side-info">
                    <div class="side-info-camp ${campClass}">
                        ${campText}
                    </div>
                    <div class="side-info-confidence">
                        置信度 ${(topProb * 100).toFixed(0)}%
                    </div>
                </div>
            </div>
            
            <!-- 最可能身份 -->
            <div class="profile-top-identity">
                <div class="top-identity-label">最可能身份</div>
                <div class="top-identity-value ${campClass}">
                    ${topIdentity}
                </div>
            </div>
            
            <!-- 身份概率列表 -->
            <div class="profile-identities">
                <div class="identities-title">身份概率分析</div>
                ${sorted.map(([identity, prob], index) => {
                    const isWolf = identity.includes('狼');
                    const isGod = ['预言家', '女巫', '猎人', '守卫', '骑士', '白痴'].includes(identity);
                    const barClass = isWolf ? 'bar-wolf' : isGod ? 'bar-god' : 'bar-good';
                    const rankClass = index === 0 ? 'rank-top' : index === 1 ? 'rank-second' : index === 2 ? 'rank-third' : '';
                    return `
                        <div class="identity-item ${rankClass}">
                            <div class="identity-rank">${index + 1}</div>
                            <div class="identity-name">${identity}</div>
                            <div class="identity-bar-container">
                                <div class="identity-bar ${barClass}" style="width: ${prob * 100}%"></div>
                            </div>
                            <div class="identity-prob">${(prob * 100).toFixed(1)}%</div>
                        </div>
                    `;
                }).join('')}
            </div>
        </div>
    `;
}

// 更新行为结果状态
async function updateResultStatus() {
    const result = await GameAPI.updateResultStatus(currentGameId);
    showToast(`已更新${result.updated_count || 0}条行为的结果状态`);
    await loadBehaviorRecords();
    await refreshPredictions();
}

// 进入下一阶段
async function advancePhase() {
    const result = await GameFlowAPI.advancePhase(currentGameId);
    if (result.success) {
        document.getElementById('current-phase').textContent = result.phase;
        document.getElementById('current-round').textContent = `第${result.round}轮`;
        showToast('已进入下一阶段');
        
        // 如果进入警上发言阶段，自动弹出选择上警玩家的弹窗
        if (result.phase === '警上发言') {
            // 延迟一下，确保玩家列表已更新
            setTimeout(() => {
                // 检查是否已经有玩家上警
                const hasPolice = document.querySelector('.dot-police') !== null;
                if (!hasPolice) {
                    showPoliceSelectModal();
                }
            }, 500);
        }
    } else {
        showToast('操作失败', 'error');
    }
}

// 狼人自爆模态框
// 显示选择上警玩家弹窗
function showPoliceSelectModal() {
    const game = document.getElementById('game-players-list');
    const players = Array.from(game.querySelectorAll('.player-item')).map(item => {
        const name = item.querySelector('.player-name-main').textContent;
        const id = parseInt(item.getAttribute('data-player-id'));
        const seat = item.querySelector('.player-seat-box').textContent;
        const isOnPolice = item.querySelector('.dot-police') !== null;
        return { id, name, seat, isOnPolice };
    });
    
    showModal('警上发言 - 选择上警玩家', `
        <div class="form-group">
            <label>勾选上警的玩家（按座位号排序）</label>
            <div id="police-select-list" style="max-height: 350px; overflow-y: auto; border: 1px solid rgba(0,212,255,0.15); border-radius: 4px; padding: 10px;">
                ${players.map(p => `
                    <div class="police-select-item" data-player-id="${p.id}" style="display: flex; align-items: center; gap: 10px; padding: 8px 0; border-bottom: 1px solid rgba(0,212,255,0.06);">
                        <input type="checkbox" id="police-player-${p.id}" class="police-player-checkbox" ${p.isOnPolice ? 'checked' : ''} style="width: 18px; height: 18px; cursor: pointer;">
                        <span style="display: inline-block; width: 30px; height: 24px; line-height: 24px; text-align: center; background: linear-gradient(135deg, rgba(0,212,255,0.2), rgba(0,212,255,0.05)); border: 1px solid rgba(0,212,255,0.3); border-radius: 3px; font-size: 12px; color: #00d4ff; font-weight: 600;">${p.seat}</span>
                        <label for="police-player-${p.id}" style="flex: 1; cursor: pointer; font-size: 13px; color: var(--text-primary);">${p.name}</label>
                    </div>
                `).join('')}
            </div>
        </div>
        <div style="font-size: 12px; color: var(--text-muted); margin-top: 8px;">
            已选 <span id="police-selected-count">0</span> 名玩家上警
        </div>
    `, `
        <button class="btn btn-secondary" onclick="closeModal()">取消</button>
        <button class="btn btn-primary" onclick="confirmPoliceSelect()">确认上警名单</button>
    `);
    
    // 监听复选框变化，更新已选数量
    setTimeout(() => {
        document.querySelectorAll('.police-player-checkbox').forEach(cb => {
            cb.addEventListener('change', updatePoliceSelectedCount);
        });
        updatePoliceSelectedCount();
    }, 100);
}

// 更新已选上警玩家数量
function updatePoliceSelectedCount() {
    const count = document.querySelectorAll('.police-player-checkbox:checked').length;
    const el = document.getElementById('police-selected-count');
    if (el) el.textContent = count;
}

// 确认选择上警玩家
async function confirmPoliceSelect() {
    const checkedBoxes = document.querySelectorAll('.police-player-checkbox:checked');
    const playerIds = Array.from(checkedBoxes).map(cb => 
        parseInt(cb.id.replace('police-player-', ''))
    );
    
    try {
        const result = await GameFlowAPI.selectPolicePlayers(currentGameId, playerIds);
        if (result && result.success) {
            showToast(`已设置${playerIds.length}名玩家上警，进入警上发言阶段`);
            closeModal();
            document.getElementById('current-phase').textContent = result.phase || '警上发言';
            await loadGamePlayers();
        } else {
            showToast(result.detail || '操作失败', 'error');
        }
    } catch (error) {
        showToast('操作失败: ' + error.message, 'error');
    }
}

function showWolfExplodeModal() {
    const game = document.getElementById('game-players-list');
    showModal('狼人自爆', `
        <div class="form-group">
            <label>选择自爆玩家</label>
            <select id="explode-player">
                ${Array.from(game.querySelectorAll('.player-item')).map(item => {
                    const name = item.querySelector('.player-name-main').textContent;
                    const id = item.getAttribute('data-player-id');
                    return `<option value="${id}">${name}</option>`;
                }).join('')}
            </select>
        </div>
    `, `
        <button class="btn btn-secondary" onclick="closeModal()">取消</button>
        <button class="btn btn-danger" onclick="confirmWolfExplode()">确认自爆</button>
    `);
}

// 确认狼人自爆
async function confirmWolfExplode() {
    const playerId = parseInt(document.getElementById('explode-player').value);
    const result = await GameFlowAPI.wolfExplode(currentGameId, playerId);
    if (result.success) {
        closeModal();
        document.getElementById('current-phase').textContent = result.phase;
        document.getElementById('current-round').textContent = `第${result.round}轮`;
        showToast('玩家已自爆，进入下一黑夜');
        await loadGamePlayers();
        await loadBehaviorRecords();
    } else {
        showToast('操作失败', 'error');
    }
}

// 添加玩家到对局模态框 - 批量添加
function showAddPlayerModal() {
    const gamePlayers = document.getElementById('game-players-list');
    const existingIds = Array.from(gamePlayers.querySelectorAll('.player-item')).map(item => 
        parseInt(item.getAttribute('data-player-id'))
    );
    const availablePlayers = allPlayers.filter(p => !existingIds.includes(p.id));
    
    if (availablePlayers.length === 0) {
        showToast('所有玩家都已在对局中', 'error');
        return;
    }
    
    showModal('批量添加玩家', `
        <div class="form-group">
            <label>搜索玩家</label>
            <input type="text" id="player-search" placeholder="输入玩家名字搜索..." oninput="filterPlayersForAdd()">
        </div>
        <div class="form-group">
            <label>选择玩家（勾选并填写座位号）</label>
            <div id="add-player-list" style="max-height: 300px; overflow-y: auto; border: 1px solid rgba(0,212,255,0.15); border-radius: 4px; padding: 10px;">
                ${availablePlayers.map(p => `
                    <div class="add-player-item" data-player-id="${p.id}" data-player-name="${p.name}" style="display: flex; align-items: center; gap: 10px; padding: 6px 0; border-bottom: 1px solid rgba(0,212,255,0.06);">
                        <input type="checkbox" id="add-player-${p.id}" class="add-player-checkbox" style="width: 16px; height: 16px; cursor: pointer;">
                        <label for="add-player-${p.id}" class="add-player-name" style="flex: 1; cursor: pointer; font-size: 13px; color: var(--text-primary);">${p.name}</label>
                        <input type="number" id="add-seat-${p.id}" placeholder="座位号" style="width: 80px; padding: 5px 8px; border: 1px solid rgba(0,212,255,0.2); border-radius: 3px; background: transparent; color: var(--text-primary); font-size: 12px;">
                    </div>
                `).join('')}
            </div>
        </div>
        <div style="font-size: 12px; color: var(--text-muted); margin-top: 8px;">
            已选 <span id="selected-player-count">0</span> 名玩家
        </div>
    `, `
        <button class="btn btn-secondary" onclick="closeModal()">取消</button>
        <button class="btn btn-primary" onclick="confirmAddPlayers()">批量添加</button>
    `);
    
    // 监听复选框变化，更新已选数量
    setTimeout(() => {
        document.querySelectorAll('.add-player-checkbox').forEach(cb => {
            cb.addEventListener('change', updateSelectedPlayerCount);
        });
    }, 100);
}

// 搜索过滤玩家
function filterPlayersForAdd() {
    const keyword = document.getElementById('player-search').value.trim().toLowerCase();
    document.querySelectorAll('.add-player-item').forEach(item => {
        // 从玩家名称标签获取文本，而不是从data属性（避免特殊字符问题）
        const nameEl = item.querySelector('.add-player-name');
        const name = nameEl ? nameEl.textContent.trim().toLowerCase() : '';
        if (!keyword || name.includes(keyword)) {
            item.style.display = 'flex';
        } else {
            item.style.display = 'none';
        }
    });
}

// 更新已选玩家数量
function updateSelectedPlayerCount() {
    const count = document.querySelectorAll('.add-player-checkbox:checked').length;
    document.getElementById('selected-player-count').textContent = count;
}

// 确认批量添加玩家
async function confirmAddPlayers() {
    const checkedBoxes = document.querySelectorAll('.add-player-checkbox:checked');
    if (checkedBoxes.length === 0) {
        showToast('请至少选择一名玩家', 'error');
        return;
    }
    
    let successCount = 0;
    let failCount = 0;
    for (const cb of checkedBoxes) {
        const playerId = parseInt(cb.id.replace('add-player-', ''));
        const seatNumber = parseInt(document.getElementById(`add-seat-${playerId}`).value) || null;
        try {
            const result = await GameAPI.addPlayer(currentGameId, { player_id: playerId, seat_number: seatNumber });
            // 成功添加时返回包含id的对象，失败时返回包含detail的错误对象
            if (result && result.id !== undefined) {
                successCount++;
            } else {
                failCount++;
                console.error('添加玩家失败:', result);
            }
        } catch (error) {
            failCount++;
            console.error('添加玩家异常:', error);
        }
    }
    
    closeModal();
    if (successCount > 0) {
        showToast(`成功添加${successCount}名玩家${failCount > 0 ? `，${failCount}名失败` : ''}`);
    } else {
        showToast(`添加失败${failCount}名玩家`, 'error');
    }
    await loadGamePlayers();
}

// 确认对局
async function confirmGame() {
    if (!confirm('确认对局结束吗？确认后将触发梯度下降学习。')) return;
    
    // 先让用户输入真实身份
    const game = await GameAPI.get(currentGameId);
    const identityOptions = allIdentities.map(i => `<option value="${i.id}">${i.name}</option>`).join('');
    
    const playersForm = game.players.map(p => `
        <div class="form-group" style="display: flex; gap: 10px; align-items: center;">
            <span style="min-width: 80px;">${p.player_name}</span>
            <select id="actual-identity-${p.player_id}" style="flex: 1;">
                <option value="">未知</option>
                ${identityOptions}
            </select>
        </div>
    `).join('');
    
    showModal('输入真实身份', `
        <p style="margin-bottom: 16px; color: var(--text-secondary); font-size: 13px;">
            请输入每位玩家的真实身份，确认后将触发梯度下降学习
        </p>
        ${playersForm}
    `, `
        <button class="btn btn-secondary" onclick="closeModal()">取消</button>
        <button class="btn btn-success" onclick="submitActualIdentities()">确认并开始学习</button>
    `);
}

// 提交真实身份
async function submitActualIdentities() {
    const game = await GameAPI.get(currentGameId);
    
    for (const p of game.players) {
        const identityId = parseInt(document.getElementById(`actual-identity-${p.player_id}`).value) || null;
        if (identityId) {
            // 更新game_players的actual_identity_id
            await fetch(`/api/games/${currentGameId}/players/${p.player_id}`, {
                method: 'PUT',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ actual_identity_id: identityId })
            });
        }
    }
    
    closeModal();
    const result = await GameAPI.confirm(currentGameId);
    if (result.success) {
        showToast('对局已确认，梯度下降学习已在后台启动');
        await loadGames();
    } else {
        showToast('确认失败', 'error');
    }
}

// 初始化高级分析标签
function initAnalysisTabs() {
    const tabs = document.querySelectorAll('.tab-btn');
    tabs.forEach(tab => {
        tab.addEventListener('click', () => {
            tabs.forEach(t => t.classList.remove('active'));
            tab.classList.add('active');
            loadAnalysisContent(tab.dataset.tab);
        });
    });
    loadAnalysisContent('prophet');
}

// 加载分析内容
async function loadAnalysisContent(tab) {
    const container = document.getElementById('analysis-content');
    
    if (tab === 'prophet') {
        const result = await ProphetAPI.getAnalysis(currentGameId);
        const data = result.data || {};
        container.innerHTML = `
            <h4 style="margin-bottom: 16px;">综合逻辑分析</h4>
            
            ${data.determined_facts && data.determined_facts.length > 0 ? `
                <div style="margin-bottom: 16px; padding: 12px; background: rgba(34, 197, 94, 0.1); border-left: 3px solid var(--accent-success); border-radius: 4px;">
                    <strong style="color: var(--accent-success);">确定性事实 (100%确定):</strong>
                    <ul style="margin-top: 8px; padding-left: 20px;">
                        ${data.determined_facts.map(f => `<li style="margin-bottom: 4px; color: var(--text-primary);">${f.description}</li>`).join('')}
                    </ul>
                </div>
            ` : ''}
            
            ${data.derived_facts && data.derived_facts.length > 0 ? `
                <div style="margin-bottom: 16px; padding: 12px; background: rgba(59, 130, 246, 0.1); border-left: 3px solid var(--accent-cyan); border-radius: 4px;">
                    <strong style="color: var(--accent-cyan);">推导事实:</strong>
                    <ul style="margin-top: 8px; padding-left: 20px;">
                        ${data.derived_facts.map(f => `<li style="margin-bottom: 4px; color: var(--text-primary);">${f.description} ${f.confidence ? `<span style="color: var(--text-muted); font-size: 12px;">(置信度: ${Math.round(f.confidence * 100)}%)</span>` : ''}</li>`).join('')}
                    </ul>
                </div>
            ` : '<p style="color: var(--text-muted); margin-bottom: 16px;">暂无推导事实</p>'}
            
            ${data.common_wolves && data.common_wolves.length > 0 ? `
                <div style="margin-bottom: 16px; padding: 12px; background: rgba(239, 68, 68, 0.1); border-left: 3px solid var(--accent-danger); border-radius: 4px;">
                    <strong style="color: var(--accent-danger);">公共狼 (所有视角都认为是狼，80%+):</strong>
                    <div style="margin-top: 8px;">
                        ${data.common_wolves.map(w => `<span class="action-tag selected" style="margin-right: 8px; background: rgba(239, 68, 68, 0.2);">${w.player_name}</span>`).join('')}
                    </div>
                </div>
            ` : ''}
            
            ${data.warnings && data.warnings.length > 0 ? `
                <div style="margin-bottom: 16px; padding: 12px; background: rgba(245, 158, 11, 0.1); border-left: 3px solid var(--accent-warning); border-radius: 4px;">
                    <strong style="color: var(--accent-warning);">逻辑警告 / 嫌疑点:</strong>
                    <ul style="margin-top: 8px; padding-left: 20px;">
                        ${data.warnings.map(w => `<li style="margin-bottom: 4px; color: var(--text-primary);">${w.description} ${w.confidence ? `<span style="color: var(--text-muted); font-size: 12px;">(置信度: ${Math.round(w.confidence * 100)}%)</span>` : ''}</li>`).join('')}
                    </ul>
                </div>
            ` : ''}
            
            ${data.contradictions && data.contradictions.length > 0 ? `
                <div style="margin-bottom: 16px; padding: 12px; background: rgba(168, 85, 247, 0.1); border-left: 3px solid var(--accent-purple); border-radius: 4px;">
                    <strong style="color: var(--accent-purple);">矛盾点:</strong>
                    <ul style="margin-top: 8px; padding-left: 20px;">
                        ${data.contradictions.map(c => `<li style="margin-bottom: 4px; color: var(--text-primary);">${c.description}</li>`).join('')}
                    </ul>
                </div>
            ` : ''}
            
            ${data.bilateral_analysis && data.bilateral_analysis.length > 0 ? `
                <div style="margin-bottom: 16px;">
                    <strong style="color: var(--text-glow);">双边分析 (分别假设各预言家为真):</strong>
                    ${data.bilateral_analysis.map(p => `
                        <div style="margin-top: 8px; padding: 10px; background: var(--bg-secondary); border-radius: 6px;">
                            <div style="margin-bottom: 6px;"><strong>${p.prophet_name}</strong> 视角:</div>
                            <div style="font-size: 13px; color: var(--text-secondary);">
                                狼坑 (${p.wolf_count}只): ${p.wolf_pit_names.join('、') || '无'}
                            </div>
                        </div>
                    `).join('')}
                </div>
            ` : ''}
        `;
    } else if (tab === 'wolfpit') {
        const result = await WolfPitAPI.getAnalysis(currentGameId);
        const data = result.data || {};
        container.innerHTML = `
            <h4 style="margin-bottom: 12px;">狼坑分析</h4>
            ${data.common_wolves && data.common_wolves.length > 0 ? `
                <div style="margin-bottom: 16px;">
                    <strong>公共狼（多个约束交集）:</strong>
                    <div style="margin-top: 8px;">
                        ${data.common_wolves.map(w => `<span class="action-tag selected" style="margin-right: 8px;">${w.player_name}</span>`).join('')}
                    </div>
                </div>
            ` : '<p style="color: var(--text-muted); margin-bottom: 16px;">暂无公共狼</p>'}
            ${data.insufficient_detection ? `
                <div style="padding: 12px; background: var(--bg-secondary); border-radius: 8px; margin-bottom: 16px;">
                    <strong>狼坑检测:</strong>
                    <p style="margin-top: 8px; font-size: 13px;">
                        已找到 ${data.insufficient_detection.found_wolves} 只狼，还差 ${data.insufficient_detection.remaining_wolves} 只
                    </p>
                    ${data.insufficient_detection.suggestion ? `<p style="margin-top: 8px; font-size: 13px; color: var(--accent-warning);">${data.insufficient_detection.suggestion}</p>` : ''}
                </div>
            ` : ''}
            <button class="btn btn-small btn-primary" onclick="showAddConstraintModal()">+ 添加狼坑约束</button>
        `;
    } else if (tab === 'confirmed') {
        const result = await ConfirmedIdentityAPI.list(currentGameId);
        container.innerHTML = `
            <h4 style="margin-bottom: 12px;">确认身份（逻辑基点）</h4>
            ${result && result.length > 0 ? `
                <div style="margin-bottom: 16px;">
                    ${result.map(ci => `
                        <div style="padding: 8px 12px; background: var(--bg-secondary); border-radius: 6px; margin-bottom: 8px; display: flex; justify-content: space-between; align-items: center;">
                            <span><strong>${ci.player_name}</strong>: ${ci.identity_name || ci.camp_only} ${ci.reason ? `(${ci.reason})` : ''}</span>
                            <button class="btn btn-small" onclick="deleteConfirmedIdentity(${ci.id})">删除</button>
                        </div>
                    `).join('')}
                </div>
            ` : '<p style="color: var(--text-muted); margin-bottom: 16px;">暂无确认身份</p>'}
            <button class="btn btn-small btn-primary" onclick="showAddConfirmedIdentityModal()">+ 确认身份</button>
        `;
    }
}

// 添加狼坑约束模态框
function showAddConstraintModal() {
    const game = document.getElementById('game-players-list');
    const playerOptions = Array.from(game.querySelectorAll('.player-item')).map(item => {
        const name = item.querySelector('.player-name-main').textContent;
        const id = item.getAttribute('data-player-id');
        return `<option value="${id}">${name}</option>`;
    }).join('');
    
    showModal('添加狼坑约束', `
        <div class="form-group">
            <label>选择玩家（按住Ctrl多选）</label>
            <select id="constraint-players" multiple style="height: 120px;">
                ${playerOptions}
            </select>
        </div>
        <div class="form-group">
            <label>狼人数</label>
            <input type="number" id="constraint-wolf-count" value="1" min="1">
        </div>
        <div class="form-group">
            <label>描述（可选）</label>
            <input type="text" id="constraint-desc" placeholder="例如：3/4/5里出2狼">
        </div>
    `, `
        <button class="btn btn-secondary" onclick="closeModal()">取消</button>
        <button class="btn btn-primary" onclick="confirmAddConstraint()">添加</button>
    `);
}

// 确认添加狼坑约束
async function confirmAddConstraint() {
    const playerSelect = document.getElementById('constraint-players');
    const playerIds = Array.from(playerSelect.selectedOptions).map(o => parseInt(o.value));
    const wolfCount = parseInt(document.getElementById('constraint-wolf-count').value);
    const desc = document.getElementById('constraint-desc').value;
    
    if (playerIds.length === 0) {
        showToast('请选择至少一个玩家', 'error');
        return;
    }
    
    const result = await WolfPitAPI.createConstraint(currentGameId, {
        game_id: currentGameId,
        player_ids: playerIds,
        wolf_count: wolfCount,
        description: desc
    });
    
    if (result.id) {
        closeModal();
        showToast('约束添加成功');
        loadAnalysisContent('wolfpit');
    } else {
        showToast('添加失败', 'error');
    }
}

// 添加确认身份模态框
function showAddConfirmedIdentityModal() {
    const game = document.getElementById('game-players-list');
    const playerOptions = Array.from(game.querySelectorAll('.player-item')).map(item => {
        const name = item.querySelector('.player-name-main').textContent;
        const id = item.getAttribute('data-player-id');
        return `<option value="${id}">${name}</option>`;
    }).join('');
    
    const identityOptions = allIdentities.map(i => `<option value="${i.id}">${i.name}</option>`).join('');
    
    showModal('确认身份', `
        <div class="form-group">
            <label>选择玩家</label>
            <select id="confirmed-player">${playerOptions}</select>
        </div>
        <div class="form-group">
            <label>确认身份</label>
            <select id="confirmed-identity">
                <option value="">未知</option>
                ${identityOptions}
            </select>
        </div>
        <div class="form-group">
            <label>仅确认阵营（可选）</label>
            <select id="confirmed-camp">
                <option value="">不指定</option>
                <option value="good">好人</option>
                <option value="wolf">狼人</option>
                <option value="third_party">第三方</option>
            </select>
        </div>
        <div class="form-group">
            <label>原因（可选）</label>
            <input type="text" id="confirmed-reason" placeholder="例如：自爆、单边预言家">
        </div>
    `, `
        <button class="btn btn-secondary" onclick="closeModal()">取消</button>
        <button class="btn btn-primary" onclick="confirmAddConfirmedIdentity()">确认</button>
    `);
}

// 确认添加确认身份
async function confirmAddConfirmedIdentity() {
    const playerId = parseInt(document.getElementById('confirmed-player').value);
    const identityId = parseInt(document.getElementById('confirmed-identity').value) || null;
    const campOnly = document.getElementById('confirmed-camp').value || null;
    const reason = document.getElementById('confirmed-reason').value;
    
    const result = await ConfirmedIdentityAPI.create(currentGameId, {
        game_id: currentGameId,
        player_id: playerId,
        identity_id: identityId,
        camp_only: campOnly,
        reason: reason
    });
    
    if (result.id) {
        closeModal();
        showToast('身份确认成功');
        loadAnalysisContent('confirmed');
        await refreshPredictions();
    } else {
        showToast('确认失败', 'error');
    }
}

// 删除确认身份
async function deleteConfirmedIdentity(id) {
    if (!confirm('确定删除这条确认身份吗？')) return;
    await ConfirmedIdentityAPI.delete(id);
    showToast('删除成功');
    loadAnalysisContent('confirmed');
    await refreshPredictions();
}

// ==================== 快速投票输入 ====================

// 快速投票数据
let quickVoteRows = [];
let currentVoteType = 'banish'; // 'police' = 警徽投票, 'banish' = 放逐投票

// 从DOM获取玩家列表
function getPlayersFromDOM() {
    const game = document.getElementById('game-players-list');
    if (!game) return [];
    return Array.from(game.querySelectorAll('.player-item')).map(item => {
        const player_name = item.querySelector('.player-name-main').textContent;
        const player_id = parseInt(item.getAttribute('data-player-id'));
        const seatText = item.querySelector('.player-seat-box').textContent;
        const seat_number = seatText && seatText !== '👑' && !isNaN(parseInt(seatText)) ? parseInt(seatText) : null;
        const is_alive = item.querySelector('.dot-alive-small') !== null;
        const is_on_police = item.querySelector('.dot-police') !== null; // 上警玩家（粉色"警"）
        const is_retired = item.querySelector('.dot-retired') !== null; // 退水玩家（红色"退"）
        return { player_id, player_name, seat_number, is_alive, is_on_police, is_retired };
    });
}

// 显示快速投票弹窗
function showQuickVoteModal() {
    // 获取当前存活的玩家列表
    const allPlayers = getPlayersFromDOM();
    const alivePlayers = allPlayers.filter(p => p.is_alive);
    
    if (alivePlayers.length === 0) {
        showToast('没有存活的玩家', 'error');
        return;
    }
    
    // 初始化一行
    quickVoteRows = [{ voters: [], target: null }];
    currentVoteType = 'banish'; // 默认放逐投票
    
    renderQuickVoteTypeSelect(alivePlayers);
}

// 渲染投票类型选择
function renderQuickVoteTypeSelect(alivePlayers) {
    showModal('快速投票 - 选择类型', `
        <div style="padding: 20px 0;">
            <div style="font-size: 14px; color: var(--text-primary); margin-bottom: 16px;">请选择投票类型：</div>
            <div style="display: flex; gap: 16px;">
                <button class="btn btn-primary" onclick="startQuickVote('police')" style="flex: 1; padding: 20px;">
                    <div style="font-size: 16px; font-weight: 600; margin-bottom: 4px;">警徽投票</div>
                    <div style="font-size: 12px; opacity: 0.8;">仅警下存活玩家可投票</div>
                </button>
                <button class="btn btn-primary" onclick="startQuickVote('banish')" style="flex: 1; padding: 20px;">
                    <div style="font-size: 16px; font-weight: 600; margin-bottom: 4px;">放逐投票</div>
                    <div style="font-size: 12px; opacity: 0.8;">所有存活玩家均可投票</div>
                </button>
            </div>
        </div>
    `, `
        <button class="btn btn-secondary" onclick="closeModal()">取消</button>
    `);
}

// 开始快速投票
function startQuickVote(voteType) {
    currentVoteType = voteType;
    const eligiblePlayers = getEligibleVoters();
    
    if (eligiblePlayers.length === 0) {
        showToast('没有可投票的玩家', 'error');
        return;
    }
    
    quickVoteRows = [{ voters: [], target: null }];
    renderQuickVoteModal(eligiblePlayers);
}

// 获取当前投票类型下可投票的玩家
function getEligibleVoters() {
    const allPlayers = getPlayersFromDOM();
    if (currentVoteType === 'police') {
        // 警徽投票：只有警下（没有上警，也没有退水）的存活玩家可以投票
        return allPlayers.filter(p => p.is_alive && !p.is_on_police && !p.is_retired);
    } else {
        // 放逐投票：所有存活玩家均可投票
        return allPlayers.filter(p => p.is_alive);
    }
}

// 渲染快速投票弹窗
function renderQuickVoteModal(alivePlayers) {
    const title = currentVoteType === 'police' ? '警徽投票 - 快速录入' : '放逐投票 - 快速录入';
    const playerOptions = alivePlayers.map(p => 
        `<option value="${p.player_id}">${p.seat_number ? p.seat_number + '号 ' : ''}${p.player_name}</option>`
    ).join('');
    
    const rowsHtml = quickVoteRows.map((row, index) => {
        // 计算已经在前面行中被选择的投票玩家ID集合
        const usedVoterIds = new Set();
        for (let i = 0; i < index; i++) {
            quickVoteRows[i].voters.forEach(id => usedVoterIds.add(id));
        }
        
        // 当前行可用的投票玩家：排除前面行已使用的，但保留当前行已选择的
        const availableVoters = alivePlayers.filter(p => 
            !usedVoterIds.has(p.player_id) || row.voters.includes(p.player_id)
        );
        
        return `
        <div class="quick-vote-row" data-row-index="${index}" style="display: flex; gap: 10px; align-items: flex-start; margin-bottom: 12px; padding: 12px; border: 1px solid rgba(0,212,255,0.15); border-radius: 6px; background: rgba(0,212,255,0.02);">
            <div style="flex: 1;">
                <div style="font-size: 12px; color: var(--text-muted); margin-bottom: 6px;">投票玩家（可多选）</div>
                <div class="quick-vote-voters" style="max-height: 120px; overflow-y: auto; border: 1px solid rgba(0,212,255,0.1); border-radius: 4px; padding: 8px;">
                    ${availableVoters.map(p => `
                        <label style="display: flex; align-items: center; gap: 8px; padding: 4px 0; cursor: pointer; font-size: 13px;">
                            <input type="checkbox" class="quick-vote-voter" data-row="${index}" data-player="${p.player_id}" ${row.voters.includes(p.player_id) ? 'checked' : ''} style="width: 16px; height: 16px; cursor: pointer;">
                            <span>${p.seat_number ? p.seat_number + '号' : ''} ${p.player_name}</span>
                        </label>
                    `).join('')}
                </div>
            </div>
            <div style="width: 180px;">
                <div style="font-size: 12px; color: var(--text-muted); margin-bottom: 6px;">被投目标</div>
                <select class="quick-vote-target" data-row="${index}" style="width: 100%; padding: 8px; border: 1px solid rgba(0,212,255,0.2); border-radius: 4px; background: var(--bg-secondary); color: var(--text-primary); font-size: 13px;">
                    <option value="">请选择</option>
                    ${playerOptions}
                </select>
            </div>
            <div style="display: flex; align-items: center; padding-top: 20px;">
                <button class="btn btn-small btn-danger" onclick="removeVoteRow(${index})" style="padding: 6px 10px;">删除</button>
            </div>
        </div>
    `}).join('');
    
    showModal(title, `
        <div style="margin-bottom: 12px;">
            <button class="btn btn-small btn-secondary" onclick="addVoteRow()">+ 添加一行</button>
            <span style="font-size: 12px; color: var(--text-muted); margin-left: 10px;">未在任何行中投票的玩家将自动记为弃票</span>
        </div>
        <div id="quick-vote-rows-container">
            ${rowsHtml}
        </div>
    `, `
        <button class="btn btn-secondary" onclick="closeModal()">取消</button>
        <button class="btn btn-primary" onclick="previewVoteResult()">预览结果</button>
    `);
    
    // 监听变化
    setTimeout(() => {
        document.querySelectorAll('.quick-vote-voter').forEach(cb => {
            cb.addEventListener('change', updateQuickVoteData);
        });
        document.querySelectorAll('.quick-vote-target').forEach(sel => {
            sel.addEventListener('change', updateQuickVoteData);
        });
    }, 100);
}

// 更新快速投票数据
function updateQuickVoteData() {
    const alivePlayers = getPlayersFromDOM().filter(p => p.is_alive);
    quickVoteRows = [];
    
    document.querySelectorAll('.quick-vote-row').forEach(row => {
        const rowIndex = parseInt(row.getAttribute('data-row-index'));
        const voters = Array.from(row.querySelectorAll('.quick-vote-voter:checked')).map(cb => 
            parseInt(cb.getAttribute('data-player'))
        );
        const target = parseInt(row.querySelector('.quick-vote-target').value) || null;
        quickVoteRows.push({ voters, target });
    });
}

// 添加一行
function addVoteRow() {
    updateQuickVoteData();
    quickVoteRows.push({ voters: [], target: null });
    const eligiblePlayers = getEligibleVoters();
    renderQuickVoteModal(eligiblePlayers);
}

// 删除一行
function removeVoteRow(index) {
    updateQuickVoteData();
    quickVoteRows.splice(index, 1);
    if (quickVoteRows.length === 0) {
        quickVoteRows.push({ voters: [], target: null });
    }
    const eligiblePlayers = getEligibleVoters();
    renderQuickVoteModal(eligiblePlayers);
}

// 预览投票结果
function previewVoteResult() {
    updateQuickVoteData();
    
    const alivePlayers = getEligibleVoters();
    const allVoterIds = new Set();
    const voteMap = {}; // target_id -> [voter_ids]
    const errors = [];
    
    // 检查每一行
    quickVoteRows.forEach((row, index) => {
        if (row.voters.length === 0) {
            errors.push(`第${index + 1}行：没有选择投票玩家`);
        }
        if (!row.target) {
            errors.push(`第${index + 1}行：没有选择被投目标`);
        }
        if (row.voters.length > 0 && row.target) {
            if (!voteMap[row.target]) voteMap[row.target] = [];
            row.voters.forEach(vid => {
                if (allVoterIds.has(vid)) {
                    const voter = alivePlayers.find(p => p.player_id === vid);
                    errors.push(`玩家${voter ? voter.player_name : vid}重复投票`);
                } else {
                    allVoterIds.add(vid);
                    voteMap[row.target].push(vid);
                }
            });
        }
    });
    
    if (errors.length > 0) {
        showToast(errors[0], 'error');
        return;
    }
    
    // 计算弃票玩家
    const abstainPlayers = alivePlayers.filter(p => !allVoterIds.has(p.player_id));
    
    // 渲染预览
    const previewHtml = `
        <div style="margin-bottom: 16px;">
            <h4 style="color: var(--text-primary); margin-bottom: 12px;">投票结果预览</h4>
            ${Object.entries(voteMap).map(([targetId, voterIds]) => {
                const target = alivePlayers.find(p => p.player_id === parseInt(targetId));
                const voters = voterIds.map(vid => {
                    const v = alivePlayers.find(p => p.player_id === vid);
                    return v ? `${v.seat_number ? v.seat_number + '号' : ''}${v.player_name}` : '未知';
                }).join('、');
                return `
                    <div style="padding: 10px; margin-bottom: 8px; border: 1px solid rgba(0,212,255,0.15); border-radius: 4px; background: rgba(0,212,255,0.03);">
                        <div style="font-weight: 600; color: #00d4ff; margin-bottom: 4px;">
                            ${target ? (target.seat_number ? target.seat_number + '号 ' : '') + target.player_name : '未知'} 
                            <span style="font-size: 12px; color: var(--text-muted); font-weight: normal;">(${voterIds.length}票)</span>
                        </div>
                        <div style="font-size: 13px; color: var(--text-secondary);">投票玩家：${voters}</div>
                    </div>
                `;
            }).join('')}
            ${abstainPlayers.length > 0 ? `
                <div style="padding: 10px; margin-bottom: 8px; border: 1px solid rgba(158,158,158,0.3); border-radius: 4px; background: rgba(158,158,158,0.05);">
                    <div style="font-weight: 600; color: #9e9e9e; margin-bottom: 4px;">
                        弃票玩家 <span style="font-size: 12px; font-weight: normal;">(${abstainPlayers.length}人)</span>
                    </div>
                    <div style="font-size: 13px; color: var(--text-secondary);">
                        ${abstainPlayers.map(p => `${p.seat_number ? p.seat_number + '号' : ''}${p.player_name}`).join('、')}
                    </div>
                </div>
            ` : ''}
        </div>
        <div style="font-size: 12px; color: var(--text-muted);">
            确认以上信息无误后点击"确认录入"，如有错误请点击"返回修改"
        </div>
    `;
    
    const resultTitle = currentVoteType === 'police' ? '警徽投票 - 结果确认' : '放逐投票 - 结果确认';
    showModal(resultTitle, previewHtml, `
        <button class="btn btn-secondary" onclick="backToVoteEdit()">返回修改</button>
        <button class="btn btn-primary" onclick="confirmVoteInput()">确认录入</button>
    `);
}

// 返回投票编辑
function backToVoteEdit() {
    const eligiblePlayers = getEligibleVoters();
    renderQuickVoteModal(eligiblePlayers);
}

// 确认投票录入
async function confirmVoteInput() {
    try {
        const alivePlayers = getEligibleVoters();
        const allVoterIds = new Set();
        const voteActions = [];
        
        // 获取当前轮次和阶段
        const phase = document.getElementById('current-phase').textContent;
        const roundText = document.getElementById('current-round').textContent;
        const round = parseInt(roundText.replace(/[^0-9]/g, '')) || 1;
        
        // 构建投票行为
        quickVoteRows.forEach(row => {
            if (row.voters.length > 0 && row.target) {
                row.voters.forEach(vid => {
                    if (!allVoterIds.has(vid)) {
                        allVoterIds.add(vid);
                        voteActions.push({
                            player_id: vid,
                            target_player_id: row.target,
                            action_type_ids: [currentVoteType === 'police' ? 30 : 33], // 30=投警徽票, 33=投放逐票
                            round_number: round,
                            phase: phase,
                            notes: '快速投票录入'
                        });
                    }
                });
            }
        });
        
        // 弃票玩家
        const abstainPlayers = alivePlayers.filter(p => !allVoterIds.has(p.player_id));
        abstainPlayers.forEach(p => {
            voteActions.push({
                player_id: p.player_id,
                target_player_id: null,
                action_type_ids: [12], // 弃票
                round_number: round,
                phase: phase,
                notes: '快速投票录入-弃票'
            });
        });
        
        // 批量录入
        let successCount = 0;
        for (const action of voteActions) {
            const result = await GameAPI.createActionsBatch({
                game_id: currentGameId,
                ...action
            });
            if (Array.isArray(result)) {
                successCount += result.length;
            }
        }
        
        closeModal();
        showToast(`成功录入${successCount}条投票记录`);
        
        // 刷新数据
        await loadBehaviorRecords();
        await refreshPredictions();
        
    } catch (error) {
        showToast('录入失败: ' + error.message, 'error');
    }
}
