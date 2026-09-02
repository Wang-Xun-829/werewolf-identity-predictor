// 通用功能

// 全局状态
let currentGameId = null;
let currentPlayerId = null;
let selectedActionIds = [];
let allIdentities = [];
let allPlayers = [];
let allActions = [];
let allSetups = [];

// 导航初始化
function initNavigation() {
    const navItems = document.querySelectorAll('.nav-item');
    navItems.forEach(item => {
        item.addEventListener('click', () => {
            const page = item.dataset.page;
            switchPage(page);
        });
    });
}

// 切换页面
function switchPage(page) {
    document.querySelectorAll('.nav-item').forEach(item => {
        item.classList.toggle('active', item.dataset.page === page);
    });
    document.querySelectorAll('.page').forEach(p => {
        p.classList.remove('active');
    });
    document.getElementById(`page-${page}`).classList.add('active');
    
    // 加载对应页面数据
    if (page === 'games') loadGames();
    else if (page === 'players') loadPlayers();
    else if (page === 'identities') loadIdentities();
    else if (page === 'actions') loadActions();
    else if (page === 'setups') loadSetups();
}

// 显示模态框
function showModal(title, content, footer = '') {
    const container = document.getElementById('modal-container');
    container.innerHTML = `
        <div class="modal-overlay" onclick="if(event.target === this) closeModal()">
            <div class="modal">
                <div class="modal-header">
                    <h3>${title}</h3>
                    <button class="modal-close" onclick="closeModal()">&times;</button>
                </div>
                <div class="modal-body">${content}</div>
                ${footer ? `<div class="modal-footer">${footer}</div>` : ''}
            </div>
        </div>
    `;
}

// 关闭模态框
function closeModal() {
    document.getElementById('modal-container').innerHTML = '';
}

// 显示提示
function showToast(message, type = 'success') {
    const container = document.getElementById('toast-container');
    if (!container) {
        // 如果没有toast容器，创建一个
        const newContainer = document.createElement('div');
        newContainer.id = 'toast-container';
        newContainer.className = 'toast-container';
        document.body.appendChild(newContainer);
    }
    
    const toast = document.createElement('div');
    toast.className = `toast ${type}`;
    
    toast.innerHTML = `
        <span class="toast-message">${message}</span>
    `;
    
    document.getElementById('toast-container').appendChild(toast);
    
    setTimeout(() => {
        toast.style.animation = 'slideInRight 0.3s ease reverse';
        setTimeout(() => {
            toast.remove();
        }, 300);
    }, 3000);
}

// 加载基础数据
async function loadBaseData() {
    const [identities, players, actions, setups] = await Promise.all([
        IdentityAPI.list(),
        PlayerAPI.list(),
        ActionAPI.list(),
        SetupAPI.list(),
    ]);
    allIdentities = identities || [];
    allPlayers = players || [];
    allActions = actions || [];
    allSetups = setups || [];
}

// ==================== 对局管理 ====================

async function loadGames() {
    const games = await GameAPI.list();
    const container = document.getElementById('games-list');
    
    // 始终显示表头和添加按钮，即使没有数据
    var html = `
        <div class="custom-table-container">
            <div class="table-header-row" style="display:flex;width:100%;">
                <div class="table-col" style="width:80px;min-width:80px;flex:0 0 80px;justify-content:center;text-align:center;">ID</div>
                <div class="table-col" style="flex:1;min-width:100px;justify-content:flex-start;text-align:left;">对局名称</div>
                <div class="table-col" style="width:120px;min-width:120px;flex:0 0 120px;justify-content:flex-start;text-align:left;">人数</div>
                <div class="table-col" style="width:100px;min-width:100px;flex:0 0 100px;justify-content:flex-start;text-align:left;">状态</div>
                <div class="table-col" style="width:120px;min-width:120px;flex:0 0 120px;justify-content:flex-end;text-align:right;">
                    <button class="btn btn-primary btn-small btn-add-game" style="margin:0;">+ 创建对局</button>
                </div>
            </div>
            <div class="table-body-container">
    `;
    
    if (!games || games.length === 0) {
        // 没有数据时显示空状态
        html += '<div class="empty-row" style="padding:40px;text-align:center;color:var(--text-muted);">暂无对局，点击右上角"创建对局"按钮创建</div>';
    } else {
        // 有数据时显示数据行
        games.forEach(game => {
            html += `
                <div class="table-data-row" onclick="openGameDetail(${game.id})" style="cursor: pointer;display:flex;width:100%;">
                    <div class="table-col" style="width:80px;min-width:80px;flex:0 0 80px;justify-content:center;text-align:center;">${game.id}</div>
                    <div class="table-col" style="flex:1;min-width:100px;justify-content:flex-start;text-align:left;">${game.name || '未命名对局'}</div>
                    <div class="table-col" style="width:120px;min-width:120px;flex:0 0 120px;justify-content:flex-start;text-align:left;">${game.player_count}人局</div>
                    <div class="table-col" style="width:100px;min-width:100px;flex:0 0 100px;justify-content:flex-start;text-align:left;">
                        <span class="card-status ${game.status === '已确认' ? 'status-confirmed' : 'status-active'}">${game.status}</span>
                    </div>
                    <div class="table-col" style="width:120px;min-width:120px;flex:0 0 120px;justify-content:flex-end;text-align:right;">
                        <button class="btn btn-small btn-danger" onclick="event.stopPropagation(); deleteGame(${game.id})">删除</button>
                    </div>
                </div>
            `;
        });
    }
    
    html += '</div></div>';
    container.innerHTML = html;
    
    // 绑定添加按钮事件
    var addBtn = container.querySelector('.btn-add-game');
    if (addBtn) {
        addBtn.addEventListener('click', showCreateGameModal);
    }
}

function showCreateGameModal() {
    const setupOptions = allSetups.map(s => `<option value="${s.id}">${s.name} (${s.player_count}人)</option>`).join('');
    
    showModal('创建对局', `
        <div class="form-group">
            <label>对局名称</label>
            <input type="text" id="new-game-name" placeholder="对局名称（可选）">
        </div>
        <div class="form-group">
            <label>选择版型</label>
            <select id="new-game-setup" onchange="autoFillPlayerCount()">
                <option value="">不指定版型</option>
                ${setupOptions}
            </select>
        </div>
        <div class="form-group">
            <label>玩家人数</label>
            <input type="number" id="new-game-count" value="12" min="3" max="20">
        </div>
    `, `
        <button class="btn btn-secondary" onclick="closeModal()">取消</button>
        <button class="btn btn-primary" onclick="createGame()">创建</button>
    `);
}

// 选择版型时自动填充玩家人数
function autoFillPlayerCount() {
    const setupId = document.getElementById('new-game-setup').value;
    if (setupId) {
        const setup = allSetups.find(s => s.id === parseInt(setupId));
        if (setup) {
            document.getElementById('new-game-count').value = setup.player_count;
        }
    }
}

async function createGame() {
    const name = document.getElementById('new-game-name').value;
    const setup_id = parseInt(document.getElementById('new-game-setup').value) || null;
    const player_count = parseInt(document.getElementById('new-game-count').value);
    
    const result = await GameAPI.create({ name, setup_id, player_count, players: [] });
    if (result && result.id) {
        closeModal();
        showToast('对局创建成功');
        openGameDetail(result.id);
    } else {
        showToast('创建失败', 'error');
        console.error('创建失败:', result);
    }
}

async function deleteGame(gameId) {
    if (!confirm('确定删除这个对局吗？所有相关数据都会被删除！')) return;
    await GameAPI.delete(gameId);
    showToast('对局已删除');
    loadGames();
}

// ==================== 玩家管理 ====================

async function loadPlayers() {
    const players = await PlayerAPI.list();
    allPlayers = players || [];
    const container = document.getElementById('players-list');
    
    // 始终显示表头和添加按钮，即使没有数据
    var html = `
        <div class="custom-table-container">
            <div class="table-header-row" style="display:flex;width:100%;">
                <div class="table-col" style="width:80px;min-width:80px;flex:0 0 80px;justify-content:center;text-align:center;">ID</div>
                <div class="table-col" style="width:180px;min-width:180px;flex:0 0 180px;justify-content:flex-start;text-align:left;">玩家名称</div>
                <div class="table-col" style="flex:1;min-width:200px;justify-content:flex-start;text-align:left;">备注</div>
                <div class="table-col" style="width:160px;min-width:160px;flex:0 0 160px;justify-content:flex-end;text-align:right;">
                    <button class="btn btn-primary btn-small btn-add-player" style="margin:0;">+ 添加玩家</button>
                </div>
            </div>
            <div class="table-body-container">
    `;
    
    if (allPlayers.length === 0) {
        // 没有数据时显示空状态
        html += '<div class="empty-row" style="padding:40px;text-align:center;color:var(--text-muted);">暂无玩家，点击右上角"添加玩家"按钮创建</div>';
    } else {
        // 有数据时显示数据行
        allPlayers.forEach(player => {
            html += `
                <div class="table-data-row" data-player-id="${player.id}" style="display:flex;width:100%;">
                    <div class="table-col" style="width:80px;min-width:80px;flex:0 0 80px;justify-content:center;text-align:center;">${player.id}</div>
                    <div class="table-col" style="width:180px;min-width:180px;flex:0 0 180px;justify-content:flex-start;text-align:left;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;" title="${player.name}">${player.name}</div>
                    <div class="table-col" style="flex:1;min-width:200px;justify-content:flex-start;text-align:left;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;color:var(--text-secondary);" title="${player.description || ''}">${player.description || '-'}</div>
                    <div class="table-col" style="width:160px;min-width:160px;flex:0 0 160px;justify-content:flex-end;text-align:right;">
                        <button class="btn btn-small btn-secondary btn-edit-player" style="margin-right:8px;">编辑</button>
                        <button class="btn btn-small btn-danger btn-delete-player">删除</button>
                    </div>
                </div>
            `;
        });
    }
    
    html += '</div></div>';
    container.innerHTML = html;
    
    // 绑定添加按钮事件
    var addBtn = container.querySelector('.btn-add-player');
    if (addBtn) {
        addBtn.addEventListener('click', showCreatePlayerModal);
    }
    
    // 事件委托：编辑和删除按钮
    container.querySelectorAll('.btn-edit-player').forEach(btn => {
        btn.addEventListener('click', function() {
            const row = this.closest('.table-data-row');
            const playerId = parseInt(row.dataset.playerId);
            const player = allPlayers.find(p => p.id === playerId);
            if (player) {
                editPlayer(player.id, player.name, player.description || '');
            }
        });
    });
    
    container.querySelectorAll('.btn-delete-player').forEach(btn => {
        btn.addEventListener('click', function() {
            const row = this.closest('.table-data-row');
            const playerId = parseInt(row.dataset.playerId);
            deletePlayer(playerId);
        });
    });
}

function showCreatePlayerModal() {
    showModal('添加玩家', `
        <div class="form-group">
            <label class="form-label">玩家名称</label>
            <input type="text" id="new-player-name" class="form-input" placeholder="请输入玩家名称">
        </div>
        <div class="form-group">
            <label class="form-label">备注</label>
            <textarea id="new-player-description" class="form-textarea" placeholder="请输入玩家备注（可选）" rows="2"></textarea>
        </div>
    `, `
        <button class="btn btn-secondary" onclick="closeModal()">取消</button>
        <button class="btn btn-primary" onclick="createPlayer()">添加</button>
    `);
}

async function createPlayer() {
    const name = document.getElementById('new-player-name').value;
    const description = document.getElementById('new-player-description').value;
    if (!name) {
        showToast('请输入玩家名称', 'error');
        return;
    }
    const result = await PlayerAPI.create({ name, description });
    if (result && result.id) {
        closeModal();
        showToast('玩家添加成功');
        loadPlayers();
    } else {
        showToast('添加失败', 'error');
    }
}

function editPlayer(playerId, playerName, playerDescription) {
    showModal('编辑玩家', `
        <div class="form-group">
            <label class="form-label">玩家名称</label>
            <input type="text" id="edit-player-name" class="form-input" value="${playerName}">
        </div>
        <div class="form-group">
            <label class="form-label">备注</label>
            <textarea id="edit-player-description" class="form-textarea" rows="2">${playerDescription || ''}</textarea>
        </div>
    `, `
        <button class="btn btn-secondary" onclick="closeModal()">取消</button>
        <button class="btn btn-primary" onclick="savePlayer(${playerId})">保存</button>
    `);
}

async function savePlayer(playerId) {
    const name = document.getElementById('edit-player-name').value;
    const description = document.getElementById('edit-player-description').value;
    if (!name) {
        showToast('请输入玩家名称', 'error');
        return;
    }
    const result = await PlayerAPI.update(playerId, { name, description });
    if (result) {
        closeModal();
        showToast('玩家更新成功');
        loadPlayers();
    } else {
        showToast('更新失败', 'error');
    }
}

async function deletePlayer(playerId) {
    if (!confirm('确定删除这个玩家吗？')) return;
    await PlayerAPI.delete(playerId);
    showToast('玩家已删除');
    loadPlayers();
}

function searchPlayers() {
    const keyword = document.getElementById('player-search').value.toLowerCase();
    const filtered = allPlayers.filter(p => 
        p.name.toLowerCase().includes(keyword) ||
        (p.pinyin && p.pinyin.toLowerCase().includes(keyword)) ||
        (p.pinyin_initial && p.pinyin_initial.toLowerCase().includes(keyword))
    );
    const container = document.getElementById('players-list');
    if (!filtered || filtered.length === 0) {
        container.innerHTML = '<p class="empty-text">未找到匹配的玩家</p>';
        return;
    }
    container.innerHTML = `
        <div class="custom-table-container">
            <div class="table-header-row">
                <div class="table-col" style="width: 80px; justify-content: center; text-align: center;">ID</div>
                <div class="table-col" style="width: calc(100% - 80px - 160px); justify-content: flex-start; text-align: left;">玩家名称</div>
                <div class="table-col" style="width: 160px; justify-content: flex-end; text-align: right;">
                    <button class="btn btn-primary btn-small" onclick="showCreatePlayerModal()" style="margin: 0;">
                        <span class="btn-icon">+</span>添加玩家
                    </button>
                </div>
            </div>
            <div class="table-body-container">
                ${filtered.map(player => `
                    <div class="table-data-row">
                        <div class="table-col" style="width: 80px; justify-content: center; text-align: center;">${player.id}</div>
                        <div class="table-col" style="width: calc(100% - 80px - 160px); justify-content: flex-start; text-align: left;">${player.name}</div>
                        <div class="table-col" style="width: 160px; justify-content: flex-end; text-align: right;">
                            <button class="btn btn-small btn-secondary" onclick="editPlayer(${player.id}, '${player.name.replace(/'/g, "\\'")}')" style="margin-right: 8px;">编辑</button>
                            <button class="btn btn-small btn-danger" onclick="deletePlayer(${player.id})">删除</button>
                        </div>
                    </div>
                `).join('')}
            </div>
        </div>
    `;
}

// ==================== 身份管理 ====================

async function loadIdentities() {
    const identities = await IdentityAPI.list();
    allIdentities = identities || [];
    const container = document.getElementById('identities-list');
    
    // 始终显示表头和添加按钮，即使没有数据
    var html = `
        <div class="custom-table-container">
            <div class="table-header-row" style="display:flex;width:100%;">
                <div class="table-col" style="width:80px;min-width:80px;flex:0 0 80px;justify-content:center;text-align:center;">ID</div>
                <div class="table-col" style="flex:1;min-width:100px;justify-content:flex-start;text-align:left;">身份名称</div>
                <div class="table-col" style="width:120px;min-width:120px;flex:0 0 120px;justify-content:flex-start;text-align:left;">阵营</div>
                <div class="table-col" style="width:100px;min-width:100px;flex:0 0 100px;justify-content:flex-start;text-align:left;">类型</div>
                <div class="table-col" style="width:160px;min-width:160px;flex:0 0 160px;justify-content:flex-end;text-align:right;">
                    <button class="btn btn-primary btn-small btn-add-identity" style="margin:0;">+ 添加身份</button>
                </div>
            </div>
            <div class="table-body-container">
    `;
    
    if (allIdentities.length === 0) {
        // 没有数据时显示空状态
        html += '<div class="empty-row" style="padding:40px;text-align:center;color:var(--text-muted);">暂无身份，点击右上角"添加身份"按钮创建</div>';
    } else {
        // 有数据时显示数据行
        allIdentities.forEach(identity => {
            html += `
                <div class="table-data-row" data-identity-id="${identity.id}" style="display:flex;width:100%;">
                    <div class="table-col" style="width:80px;min-width:80px;flex:0 0 80px;justify-content:center;text-align:center;">${identity.id}</div>
                    <div class="table-col identity-name" style="flex:1;min-width:100px;justify-content:flex-start;text-align:left;">${identity.name}</div>
                    <div class="table-col" style="width:120px;min-width:120px;flex:0 0 120px;justify-content:flex-start;text-align:left;">${identity.faction_name || '未知'}</div>
                    <div class="table-col" style="width:100px;min-width:100px;flex:0 0 100px;justify-content:flex-start;text-align:left;">${identity.faction_name === '好人' ? (identity.is_god ? '神职' : '平民') : '-'}</div>
                    <div class="table-col" style="width:160px;min-width:160px;flex:0 0 160px;justify-content:flex-end;text-align:right;">
                        <button class="btn btn-small btn-secondary btn-edit-identity" style="margin-right:8px;">编辑</button>
                        <button class="btn btn-small btn-danger btn-delete-identity">删除</button>
                    </div>
                </div>
            `;
        });
    }
    
    html += '</div></div>';
    container.innerHTML = html;
    
    // 事件委托：添加身份按钮
    var addBtn = container.querySelector('.btn-add-identity');
    if (addBtn) {
        addBtn.addEventListener('click', showCreateIdentityModal);
    }
    
    // 事件委托：编辑和删除按钮
    container.querySelectorAll('.btn-edit-identity').forEach(btn => {
        btn.addEventListener('click', function() {
            const row = this.closest('.table-data-row');
            const identityId = parseInt(row.dataset.identityId);
            const identity = allIdentities.find(i => i.id === identityId);
            if (identity) {
                editIdentity(identity.id, identity.name, identity.faction_id || 1, identity.is_god || false);
            }
        });
    });
    
    container.querySelectorAll('.btn-delete-identity').forEach(btn => {
        btn.addEventListener('click', function() {
            const row = this.closest('.table-data-row');
            const identityId = parseInt(row.dataset.identityId);
            deleteIdentity(identityId);
        });
    });
}

function showCreateIdentityModal() {
    const factionOptions = ['好人', '狼人', '第三方'].map((f, i) => `<option value="${i+1}">${f}</option>`).join('');
    
    showModal('添加身份', `
        <div class="form-group">
            <label class="form-label">身份名称</label>
            <input type="text" id="new-identity-name" class="form-input" placeholder="请输入身份名称">
        </div>
        <div class="form-group">
            <label class="form-label">所属阵营</label>
            <select id="new-identity-faction" class="form-select">
                ${factionOptions}
            </select>
        </div>
        <div class="form-group checkbox-group">
            <label class="checkbox-label">
                <input type="checkbox" id="new-identity-god" class="checkbox-input">
                <span class="checkbox-text">是否神职</span>
            </label>
        </div>
    `, `
        <button class="btn btn-secondary" onclick="closeModal()">取消</button>
        <button class="btn btn-primary" onclick="createIdentity()">添加</button>
    `);
}

async function createIdentity() {
    const name = document.getElementById('new-identity-name').value;
    const faction_id = parseInt(document.getElementById('new-identity-faction').value);
    const is_god = document.getElementById('new-identity-god').checked;
    
    if (!name) {
        showToast('请输入身份名称', 'error');
        return;
    }
    const result = await IdentityAPI.create({ name, faction_id, is_god });
    if (result && result.id) {
        closeModal();
        showToast('身份添加成功');
        loadIdentities();
    } else {
        showToast('添加失败', 'error');
    }
}

async function deleteIdentity(identityId) {
    if (!confirm('确定删除这个身份吗？')) return;
    await IdentityAPI.delete(identityId);
    showToast('身份已删除');
    loadIdentities();
}

function editIdentity(identityId, name, factionId, isGod) {
    const factionOptions = ['好人', '狼人', '第三方'].map((f, i) => `<option value="${i+1}" ${factionId === i+1 ? 'selected' : ''}>${f}</option>`).join('');
    
    showModal('编辑身份', `
        <div class="form-group">
            <label class="form-label">身份名称</label>
            <input type="text" id="edit-identity-name" class="form-input" value="${name}">
        </div>
        <div class="form-group">
            <label class="form-label">所属阵营</label>
            <select id="edit-identity-faction" class="form-select">
                ${factionOptions}
            </select>
        </div>
        <div class="form-group checkbox-group">
            <label class="checkbox-label">
                <input type="checkbox" id="edit-identity-god" class="checkbox-input" ${isGod ? 'checked' : ''}>
                <span class="checkbox-text">是否神职</span>
            </label>
        </div>
    `, `
        <button class="btn btn-secondary" onclick="closeModal()">取消</button>
        <button class="btn btn-primary" onclick="saveIdentity(${identityId})">保存</button>
    `);
}

async function saveIdentity(identityId) {
    const name = document.getElementById('edit-identity-name').value;
    const faction_id = parseInt(document.getElementById('edit-identity-faction').value);
    const is_god = document.getElementById('edit-identity-god').checked;
    
    if (!name) {
        showToast('请输入身份名称', 'error');
        return;
    }
    const result = await IdentityAPI.update(identityId, { name, faction_id, is_god });
    if (result) {
        closeModal();
        showToast('身份更新成功');
        loadIdentities();
    } else {
        showToast('更新失败', 'error');
    }
}

// ==================== 行为管理 ====================

async function loadActions() {
    const actions = await ActionAPI.list();
    allActions = actions || [];
    const container = document.getElementById('actions-list');
    if (!actions || actions.length === 0) {
        container.innerHTML = '<p class="empty-text">暂无行为</p>';
        return;
    }
    
    // 构建行为树并按层级排序
    const actionMap = {};
    actions.forEach(a => {
        actionMap[a.id] = {...a, children: []};
    });
    
    const rootActions = [];
    actions.forEach(a => {
        if (a.parent_id && actionMap[a.parent_id]) {
            actionMap[a.parent_id].children.push(actionMap[a.id]);
        } else {
            rootActions.push(actionMap[a.id]);
        }
    });
    
    // 扁平化排序（父行为在前，子行为在后）
    const sortedActions = [];
    function flatten(action, level) {
        sortedActions.push({...action, level});
        if (action.children) {
            action.children.forEach(child => flatten(child, level + 1));
        }
    }
    rootActions.forEach(a => flatten(a, 0));
    
    // 表头和内容拆成两个独立部分，彻底避免列宽对齐问题
    container.innerHTML = `
        <div class="custom-table-container">
            <!-- 表头部分 -->
            <div class="table-header-row">
                <div class="table-col col-id" style="justify-content: center; text-align: center;">ID</div>
                <div class="table-col col-name" style="justify-content: flex-start; text-align: left;">名称</div>
                <div class="table-col col-level" style="justify-content: flex-start; text-align: left;">层级</div>
                <div class="table-col col-weight" style="justify-content: flex-start; text-align: left;">默认权重</div>
                <div class="table-col col-desc" style="justify-content: flex-start; text-align: left;">描述</div>
                <div class="table-col col-actions" style="justify-content: flex-end; text-align: right;">
                    <button class="btn btn-primary btn-small" onclick="showCreateActionModal()" style="margin: 0;">
                        <span class="btn-icon">+</span>添加行为
                    </button>
                </div>
            </div>
            <!-- 内容部分 -->
            <div class="table-body-container">
                ${sortedActions.map(action => {
                    const levelLabel = action.level === 0 ? '一级' : action.level === 1 ? '二级' : '三级';
                    const levelClass = action.level === 0 ? 'level-1' : action.level === 1 ? 'level-2' : 'level-3';
                    const indent = action.level * 24;
                    const treePrefix = action.level > 0 ? '<span style="color: var(--text-muted); margin-right: 8px; font-family: monospace; font-weight: bold;">└─</span>' : '';
                    const rowBg = action.level === 1 ? 'rgba(139, 92, 246, 0.05)' : action.level === 2 ? 'rgba(0, 212, 255, 0.04)' : 'transparent';
                    return `
                        <div class="table-data-row ${action.level > 0 ? 'child-row level-' + action.level : ''}" 
                             style="background: ${rowBg};"
                             data-action-id="${action.id}"
                             onmouseover="this.style.background='rgba(139, 92, 246, 0.08)'"
                             onmouseout="this.style.background='${rowBg}'">
                            <div class="table-col col-id" style="justify-content: center; text-align: center;">${action.id}</div>
                            <div class="table-col col-name" style="justify-content: flex-start; text-align: left; padding-left: ${16 + indent}px;">${treePrefix}${action.name}</div>
                            <div class="table-col col-level" style="justify-content: flex-start; text-align: left;"><span class="level-badge ${levelClass}">${levelLabel}</span></div>
                            <div class="table-col col-weight" style="justify-content: flex-start; text-align: left;">${action.default_weight || action.weight || 1.0}</div>
                            <div class="table-col col-desc" style="justify-content: flex-start; text-align: left; color: var(--text-secondary);">${action.description || '-'}</div>
                            <div class="table-col col-actions" style="justify-content: flex-start; text-align: left;">
                                <button class="btn btn-small btn-secondary btn-edit-action" style="margin-right: 8px;">编辑</button>
                                <button class="btn btn-small btn-danger btn-delete-action">删除</button>
                            </div>
                        </div>
                    `;
                }).join('')}
            </div>
        </div>
    `;
    
    // 使用事件委托处理编辑和删除按钮，避免特殊字符导致的HTML解析错误
    container.querySelectorAll('.btn-edit-action').forEach(btn => {
        btn.addEventListener('click', function() {
            const row = this.closest('.table-data-row');
            const actionId = parseInt(row.dataset.actionId);
            const action = allActions.find(a => a.id === actionId);
            if (action) {
                editAction(action.id, action.name, action.parent_id, action.category || '其他', action.default_weight || action.weight || 1.0, action.has_result_status || false, action.description || '');
            }
        });
    });
    
    container.querySelectorAll('.btn-delete-action').forEach(btn => {
        btn.addEventListener('click', function() {
            const row = this.closest('.table-data-row');
            const actionId = parseInt(row.dataset.actionId);
            deleteAction(actionId);
        });
    });
}

function showCreateActionModal() {
    const parentOptions = allActions.map(a => `<option value="${a.id}">${a.name}</option>`).join('');
    const categoryOptions = ['身份声明', '站边表态', '查验结果', '投票行为', '技能使用', '其他'].map(c => `<option value="${c}">${c}</option>`).join('');
    
    showModal('添加行为', `
        <div class="form-group">
            <label class="form-label">行为名称</label>
            <input type="text" id="new-action-name" class="form-input" placeholder="请输入行为名称">
        </div>
        <div class="form-group">
            <label class="form-label">父行为（可选，用于多级分类）</label>
            <select id="new-action-parent" class="form-select">
                <option value="">无（作为一级行为）</option>
                ${parentOptions}
            </select>
        </div>
        <div class="form-group">
            <label class="form-label">分类</label>
            <select id="new-action-category" class="form-select">
                ${categoryOptions}
            </select>
        </div>
        <div class="form-group">
            <label class="form-label">默认权重</label>
            <input type="number" id="new-action-weight" class="form-input" value="1.0" step="0.1" min="0.1" max="10">
        </div>
        <div class="form-group">
            <label class="form-label">行为描述</label>
            <textarea id="new-action-description" class="form-textarea" placeholder="请输入行为描述（可选）" rows="3"></textarea>
        </div>
        <div class="form-group checkbox-group">
            <label class="checkbox-label">
                <input type="checkbox" id="new-action-result-status" class="checkbox-input">
                <span class="checkbox-text">有结果状态（保对/保错等）</span>
            </label>
        </div>
    `, `
        <button class="btn btn-secondary" onclick="closeModal()">取消</button>
        <button class="btn btn-primary" onclick="createAction()">添加</button>
    `);
}

async function createAction() {
    const name = document.getElementById('new-action-name').value;
    const parent_id = parseInt(document.getElementById('new-action-parent').value) || null;
    const category = document.getElementById('new-action-category').value;
    const default_weight = parseFloat(document.getElementById('new-action-weight').value);
    const description = document.getElementById('new-action-description').value;
    const has_result_status = document.getElementById('new-action-result-status').checked;
    
    if (!name) {
        showToast('请输入行为名称', 'error');
        return;
    }
    const result = await ActionAPI.create({ name, parent_id, category, default_weight, description, has_result_status });
    if (result && result.id) {
        closeModal();
        showToast('行为添加成功');
        loadActions();
    } else {
        showToast('添加失败', 'error');
    }
}

async function deleteAction(actionId) {
    if (!confirm('确定删除这个行为吗？')) return;
    await ActionAPI.delete(actionId);
    showToast('行为已删除');
    loadActions();
}

function editAction(actionId, name, parentId, category, defaultWeight, hasResultStatus, description) {
    const parentOptions = allActions.map(a => `<option value="${a.id}" ${parentId === a.id ? 'selected' : ''}>${a.name}</option>`).join('');
    const categoryOptions = ['身份声明', '站边表态', '查验结果', '投票行为', '技能使用', '其他'].map(c => `<option value="${c}" ${category === c ? 'selected' : ''}>${c}</option>`).join('');
    const descValue = description || '';
    
    showModal('编辑行为', `
        <div class="form-group">
            <label class="form-label">行为名称</label>
            <input type="text" id="edit-action-name" class="form-input" value="${name}">
        </div>
        <div class="form-group">
            <label class="form-label">父行为（可选）</label>
            <select id="edit-action-parent" class="form-select">
                <option value="">无（作为一级行为）</option>
                ${parentOptions}
            </select>
        </div>
        <div class="form-group">
            <label class="form-label">分类</label>
            <select id="edit-action-category" class="form-select">
                ${categoryOptions}
            </select>
        </div>
        <div class="form-group">
            <label class="form-label">默认权重</label>
            <input type="number" id="edit-action-weight" class="form-input" value="${defaultWeight}" step="0.1" min="0.1" max="10">
        </div>
        <div class="form-group">
            <label class="form-label">行为描述</label>
            <textarea id="edit-action-description" class="form-textarea" rows="3">${descValue}</textarea>
        </div>
        <div class="form-group checkbox-group">
            <label class="checkbox-label">
                <input type="checkbox" id="edit-action-result-status" class="checkbox-input" ${hasResultStatus ? 'checked' : ''}>
                <span class="checkbox-text">有结果状态（保对/保错等）</span>
            </label>
        </div>
    `, `
        <button class="btn btn-secondary" onclick="closeModal()">取消</button>
        <button class="btn btn-primary" onclick="saveAction(${actionId})">保存</button>
    `);
}

async function saveAction(actionId) {
    const name = document.getElementById('edit-action-name').value;
    const parent_id = parseInt(document.getElementById('edit-action-parent').value) || null;
    const category = document.getElementById('edit-action-category').value;
    const default_weight = parseFloat(document.getElementById('edit-action-weight').value);
    const description = document.getElementById('edit-action-description').value;
    const has_result_status = document.getElementById('edit-action-result-status').checked;
    
    if (!name) {
        showToast('请输入行为名称', 'error');
        return;
    }
    const result = await ActionAPI.update(actionId, { name, parent_id, category, default_weight, description, has_result_status });
    if (result) {
        closeModal();
        showToast('行为更新成功');
        loadActions();
    } else {
        showToast('更新失败', 'error');
    }
}

// ==================== 版型管理 ====================

async function loadSetups() {
    const setups = await SetupAPI.list();
    allSetups = setups || [];
    const container = document.getElementById('setups-list');
    
    // 始终显示表头和添加按钮，即使没有数据
    var html = '' +
        '<div class="custom-table-container">' +
            '<div class="table-header-row" style="display:flex;width:100%;">' +
                '<div class="table-col" style="width:80px;min-width:80px;flex:0 0 80px;justify-content:center;text-align:center;">序号</div>' +
                '<div class="table-col" style="width:180px;min-width:180px;flex:0 0 180px;justify-content:flex-start;text-align:left;">版型名称</div>' +
                '<div class="table-col" style="width:80px;min-width:80px;flex:0 0 80px;justify-content:flex-start;text-align:left;">人数</div>' +
                '<div class="table-col" style="flex:1;min-width:300px;justify-content:flex-start;text-align:left;">身份配置</div>' +
                '<div class="table-col" style="width:140px;min-width:140px;flex:0 0 140px;justify-content:flex-end;text-align:right;">' +
                    '<button type="button" class="btn btn-primary btn-small btn-add-setup" style="margin:0;">+ 添加版型</button>' +
                '</div>' +
            '</div>' +
            '<div class="table-body-container">';
    
    if (allSetups.length === 0) {
        // 没有数据时显示空状态
        html += '<div class="empty-row" style="padding:40px;text-align:center;color:var(--text-muted);">暂无版型，点击右上角"添加版型"按钮创建</div>';
    } else {
        // 有数据时显示数据行
        for (var i = 0; i < allSetups.length; i++) {
            var setup = allSetups[i];
            var rowNumber = i + 1; // 序号，从1开始
            var identityText = '-';
            if (setup.identities && setup.identities.length > 0) {
                var parts = [];
                for (var j = 0; j < setup.identities.length; j++) {
                    var ident = setup.identities[j];
                    parts.push(ident.identity_name + '×' + ident.count);
                }
                identityText = parts.join(' · ');
            }
            html += '' +
                '<div class="table-data-row" data-setup-id="' + setup.id + '" style="display:flex;width:100%;">' +
                    '<div class="table-col" style="width:80px;min-width:80px;flex:0 0 80px;justify-content:center;text-align:center;">' + rowNumber + '</div>' +
                    '<div class="table-col setup-name" style="width:180px;min-width:180px;flex:0 0 180px;justify-content:flex-start;text-align:left;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;" title="' + setup.name + '">' + setup.name + '</div>' +
                    '<div class="table-col" style="width:80px;min-width:80px;flex:0 0 80px;justify-content:flex-start;text-align:left;">' + setup.player_count + '人局</div>' +
                    '<div class="table-col" style="flex:1;min-width:300px;justify-content:flex-start;text-align:left;white-space:normal;word-break:break-all;line-height:1.5;">' + identityText + '</div>' +
                    '<div class="table-col" style="width:140px;min-width:140px;flex:0 0 140px;justify-content:flex-end;text-align:right;">' +
                        '<button type="button" class="btn btn-small btn-secondary btn-edit-setup" style="margin-right:8px;">编辑</button>' +
                        '<button type="button" class="btn btn-small btn-danger btn-delete-setup">删除</button>' +
                    '</div>' +
                '</div>';
        }
    }
    
    html += '</div></div>';
    container.innerHTML = html;
    
    // 绑定添加按钮事件
    var addBtn = container.querySelector('.btn-add-setup');
    if (addBtn) {
        addBtn.addEventListener('click', showCreateSetupModal);
    }
    
    // 事件委托：在容器上监听点击，判断是编辑还是删除按钮
    container.addEventListener('click', function(e) {
        var editBtn = e.target.closest('.btn-edit-setup');
        var deleteBtn = e.target.closest('.btn-delete-setup');
        
        if (editBtn) {
            var row = editBtn.closest('.table-data-row');
            if (row) {
                var setupId = parseInt(row.dataset.setupId);
                var setup = allSetups.find(function(s) { return s.id === setupId; });
                if (setup) {
                    editSetup(setup.id, setup.name, setup.player_count, setup.identities || []);
                }
            }
        }
        
        if (deleteBtn) {
            var row2 = deleteBtn.closest('.table-data-row');
            if (row2) {
                var setupId2 = parseInt(row2.dataset.setupId);
                deleteSetup(setupId2);
            }
        }
    });
}

// 页面加载时绑定静态添加按钮的点击事件（兼容旧代码）
document.addEventListener('DOMContentLoaded', function() {
    // 版型库添加按钮
    var addSetupBtn = document.getElementById('btn-add-setup-static');
    if (addSetupBtn) {
        addSetupBtn.addEventListener('click', showCreateSetupModal);
    }
    
    // 对局管理创建按钮
    var addGameBtn = document.getElementById('btn-add-game-static');
    if (addGameBtn) {
        addGameBtn.addEventListener('click', showCreateGameModal);
    }
});

async function showCreateSetupModal() {
    // 动态加载最新的身份库数据
    try {
        const identities = await IdentityAPI.list();
        allIdentities = identities || [];
    } catch (e) {
        console.error('加载身份库失败:', e);
    }
    
    showModal('添加版型', `
        <div class="form-group">
            <label class="form-label">版型名称</label>
            <input type="text" id="new-setup-name" class="form-input" placeholder="请输入版型名称">
        </div>
        <div class="form-group">
            <label class="form-label">玩家人数</label>
            <input type="number" id="new-setup-count" class="form-input" value="12" min="3" max="20">
        </div>
        <div class="form-group">
            <label class="form-label">身份配置</label>
            <div id="new-setup-identities" class="identity-config-list">
            </div>
            <button type="button" class="btn btn-small btn-secondary" style="margin-top:10px;width:100%;" onclick="addIdentityRow('new-setup-identities')">+ 添加身份</button>
        </div>
    `, `
        <button class="btn btn-secondary" onclick="closeModal()">取消</button>
        <button class="btn btn-primary" onclick="createSetup()">添加</button>
    `);
    
    // 默认添加一个身份配置行
    addIdentityRow('new-setup-identities');
}

// 添加身份配置行
function addIdentityRow(containerId, identityId, count) {
    var container = document.getElementById(containerId);
    if (!container) return;
    
    var identityOptions = allIdentities.map(i => 
        `<option value="${i.id}" ${identityId === i.id ? 'selected' : ''}>${i.name}</option>`
    ).join('');
    
    var row = document.createElement('div');
    row.className = 'identity-config-row';
    row.innerHTML = `
        <select class="form-select identity-select" style="flex:1;">
            <option value="">请选择身份</option>
            ${identityOptions}
        </select>
        <input type="number" class="form-input identity-count" style="width:80px;margin-left:10px;" value="${count || 1}" min="1" max="20" placeholder="数量">
        <button type="button" class="btn btn-small btn-danger identity-remove" style="margin-left:10px;" onclick="this.parentElement.remove()">删除</button>
    `;
    container.appendChild(row);
}

// 获取身份配置列表
function getIdentityConfig(containerId) {
    var container = document.getElementById(containerId);
    if (!container) return [];
    
    var identities = [];
    var rows = container.querySelectorAll('.identity-config-row');
    for (var i = 0; i < rows.length; i++) {
        var select = rows[i].querySelector('.identity-select');
        var countInput = rows[i].querySelector('.identity-count');
        if (select && select.value && countInput) {
            var identityId = parseInt(select.value);
            var count = parseInt(countInput.value);
            if (identityId && count > 0) {
                var identity = allIdentities.find(function(ident) { return ident.id === identityId; });
                identities.push({
                    identity_id: identityId,
                    identity_name: identity ? identity.name : '',
                    count: count
                });
            }
        }
    }
    return identities;
}

async function createSetup() {
    const name = document.getElementById('new-setup-name').value;
    const player_count = parseInt(document.getElementById('new-setup-count').value);
    const identities = getIdentityConfig('new-setup-identities');
    
    if (!name) {
        showToast('请输入版型名称', 'error');
        return;
    }
    const result = await SetupAPI.create({ name, player_count, identities });
    if (result && result.id) {
        closeModal();
        showToast('版型添加成功');
        loadSetups();
    } else {
        showToast('添加失败', 'error');
    }
}

async function deleteSetup(setupId) {
    // 查找版型名称用于提示
    var setupName = '该版型';
    if (allSetups && allSetups.length > 0) {
        var setup = allSetups.find(function(s) { return s.id === setupId; });
        if (setup) setupName = setup.name;
    }
    
    // 使用自定义模态框确认删除
    showModal('删除版型', `
        <div style="padding: 10px 0;">
            <p style="color: var(--text-secondary); line-height: 1.6; margin: 0;">
                确定要删除版型 <strong style="color: var(--accent-danger);">【${setupName}】</strong> 吗？
            </p>
            <p style="color: var(--text-muted); font-size: 12px; margin-top: 12px; margin-bottom: 0;">
                删除后无法恢复，使用该版型的对局数据不会受影响。
            </p>
        </div>
    `, `
        <button type="button" class="btn btn-secondary" onclick="closeModal()">取消</button>
        <button type="button" class="btn btn-danger" onclick="confirmDeleteSetup(${setupId})">确认删除</button>
    `);
}

// 确认删除版型
async function confirmDeleteSetup(setupId) {
    try {
        await SetupAPI.delete(setupId);
        closeModal();
        showToast('版型已删除');
        loadSetups();
    } catch (error) {
        showToast('删除失败: ' + error.message, 'error');
    }
}

async function editSetup(setupId, name, playerCount, identities) {
    // 动态加载最新的身份库数据
    try {
        const latestIdentities = await IdentityAPI.list();
        allIdentities = latestIdentities || [];
    } catch (e) {
        console.error('加载身份库失败:', e);
    }
    
    showModal('编辑版型', `
        <div class="form-group">
            <label class="form-label">版型名称</label>
            <input type="text" id="edit-setup-name" class="form-input" value="${name}">
        </div>
        <div class="form-group">
            <label class="form-label">玩家人数</label>
            <input type="number" id="edit-setup-count" class="form-input" value="${playerCount}" min="3" max="20">
        </div>
        <div class="form-group">
            <label class="form-label">身份配置</label>
            <div id="edit-setup-identities" class="identity-config-list">
            </div>
            <button type="button" class="btn btn-small btn-secondary" style="margin-top:10px;width:100%;" onclick="addIdentityRow('edit-setup-identities')">+ 添加身份</button>
        </div>
    `, `
        <button class="btn btn-secondary" onclick="closeModal()">取消</button>
        <button class="btn btn-primary" onclick="saveSetup(${setupId})">保存</button>
    `);
    
    // 加载现有的身份配置
    var existingIdentities = identities || [];
    for (var i = 0; i < existingIdentities.length; i++) {
        var ident = existingIdentities[i];
        addIdentityRow('edit-setup-identities', ident.identity_id || ident.id, ident.count);
    }
    
    // 如果没有身份配置，默认添加一个空行
    if (existingIdentities.length === 0) {
        addIdentityRow('edit-setup-identities');
    }
}

async function saveSetup(setupId) {
    const name = document.getElementById('edit-setup-name').value;
    const player_count = parseInt(document.getElementById('edit-setup-count').value);
    const identities = getIdentityConfig('edit-setup-identities');
    
    if (!name) {
        showToast('请输入版型名称', 'error');
        return;
    }
    const result = await SetupAPI.update(setupId, { name, player_count, identities });
    if (result) {
        closeModal();
        showToast('版型更新成功');
        loadSetups();
    } else {
        showToast('更新失败', 'error');
    }
}
