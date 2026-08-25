// 库管理

let currentTab = 'roles';
let allRoles = [];  // 所有身份列表（用于版型配置）

document.addEventListener('DOMContentLoaded', async () => {
    await loadAllRolesForSetup();
    loadRoles();
});

// 加载所有身份（用于版型配置表单）
async function loadAllRolesForSetup() {
    const result = await api('GET', '/roles');
    if (result && result.data) {
        allRoles = result.data;
    }
}

function switchTab(tab) {
    currentTab = tab;
    ['roles', 'actions', 'setups'].forEach(t => {
        document.getElementById('tab-' + t).style.display = t === tab ? 'block' : 'none';
        const btn = document.getElementById('tab-' + t + '-btn');
        btn.className = t === tab ? 'btn btn-primary btn-sm' : 'btn btn-secondary btn-sm';
    });
    if (tab === 'roles') loadRoles();
    if (tab === 'actions') loadActions();
    if (tab === 'setups') loadSetups();
}

function hideModal(id) {
    document.getElementById(id).classList.remove('show');
}

// ========== 身份库 ==========
async function loadRoles() {
    const result = await api('GET', '/roles');
    const container = document.getElementById('roles-list');
    if (!result || !result.data || result.data.length === 0) {
        container.innerHTML = '<div class="empty-state"><p>暂无身份</p></div>';
        return;
    }
    let html = '<table class="table"><thead><tr>';
    html += '<th>ID</th><th>名称</th><th>阵营</th><th>描述</th><th>操作</th>';
    html += '</tr></thead><tbody>';
    result.data.forEach(r => {
        html += `<tr>
            <td>${r.id}</td>
            <td><strong>${escapeHtml(r.name)}</strong></td>
            <td>${campBadge(r.camp)}</td>
            <td>${escapeHtml(r.description || '-')}</td>
            <td class="actions">
                <button class="btn btn-secondary btn-sm" onclick='editRole(${JSON.stringify(r)})'>编辑</button>
                <button class="btn btn-danger btn-sm" onclick="deleteRole(${r.id})">删除</button>
            </td>
        </tr>`;
    });
    html += '</tbody></table>';
    container.innerHTML = html;
}

function showRoleModal() {
    document.getElementById('role-modal-title').textContent = '新增身份';
    document.getElementById('edit-role-id').value = '';
    document.getElementById('role-name').value = '';
    document.getElementById('role-camp').value = '好人';
    document.getElementById('role-desc').value = '';
    document.getElementById('role-modal').classList.add('show');
}

function editRole(r) {
    document.getElementById('role-modal-title').textContent = '编辑身份';
    document.getElementById('edit-role-id').value = r.id;
    document.getElementById('role-name').value = r.name;
    document.getElementById('role-camp').value = r.camp;
    document.getElementById('role-desc').value = r.description || '';
    document.getElementById('role-modal').classList.add('show');
}

async function saveRole() {
    const id = document.getElementById('edit-role-id').value;
    const data = {
        name: document.getElementById('role-name').value.trim(),
        camp: document.getElementById('role-camp').value,
        description: document.getElementById('role-desc').value.trim()
    };
    if (!data.name) { showToast('请输入身份名称', 'error'); return; }
    const result = id
        ? await api('PUT', '/roles/' + id, data)
        : await api('POST', '/roles', data);
    if (result) {
        showToast(id ? '身份已更新' : '身份已添加', 'success');
        hideModal('role-modal');
        await loadRoles();
    }
}

async function deleteRole(id) {
    if (!confirmAction('确定删除这个身份吗？')) return;
    const result = await api('DELETE', '/roles/' + id);
    if (result) { showToast('身份已删除', 'success'); await loadRoles(); }
}

// ========== 行为库 ==========
async function loadActions() {
    const result = await api('GET', '/actions');
    const container = document.getElementById('actions-list');
    if (!result || !result.data || result.data.length === 0) {
        container.innerHTML = '<div class="empty-state"><p>暂无行为</p></div>';
        return;
    }
    // 保存所有行为列表，供父行为选择使用
    window._allActions = result.data;
    let html = '<table class="table"><thead><tr>';
    html += '<th>ID</th><th>名称</th><th>层级</th><th>默认权重</th><th>描述</th><th>操作</th>';
    html += '</tr></thead><tbody>';

    // 树形展示：先一级行为，再缩进显示子行为
    const parentToChildren = {};
    const rootActions = [];
    result.data.forEach(a => {
        if (a.parent_id) {
            if (!parentToChildren[a.parent_id]) parentToChildren[a.parent_id] = [];
            parentToChildren[a.parent_id].push(a);
        } else {
            rootActions.push(a);
        }
    });

    function renderActionRow(a, level) {
        const indent = level > 0 ? '&nbsp;&nbsp;&nbsp;&nbsp;'.repeat(level) + '└ ' : '';
        // 支持任意级别：一级、二级、三级、四级...
        const levelNames = ['一级', '二级', '三级', '四级', '五级', '六级', '七级', '八级'];
        const levelLabel = level < levelNames.length ? levelNames[level] : `${level + 1}级`;
        // 不同级别不同颜色
        const levelClass = level <= 5 ? `badge-level-${level}` : 'badge-level-other';
        html += `<tr class="${level > 0 ? 'child-action-row' : ''}">
            <td>${a.id}</td>
            <td>${indent}<strong>${escapeHtml(a.name)}</strong></td>
            <td><span class="badge ${levelClass}">${levelLabel}</span></td>
            <td>${a.default_weight}</td>
            <td>${escapeHtml(a.description || '-')}</td>
            <td class="actions">
                <button class="btn btn-secondary btn-sm" onclick='editAction(${JSON.stringify(a)})'>编辑</button>
                <button class="btn btn-danger btn-sm" onclick="deleteAction(${a.id})">删除</button>
            </td>
        </tr>`;
        // 递归渲染子行为
        const children = parentToChildren[a.id] || [];
        children.forEach(child => renderActionRow(child, level + 1));
    }

    rootActions.forEach(a => renderActionRow(a, 0));
    html += '</tbody></table>';
    container.innerHTML = html;
}

// 填充父行为下拉选择（支持任意级别，排除自己和自己的后代避免循环引用）
function populateParentSelect(excludeId) {
    const select = document.getElementById('action-parent');
    select.innerHTML = '<option value="">无（一级行为）</option>';

    // 构建id到行为的映射，用于查找后代
    const actionMap = {};
    (window._allActions || []).forEach(a => { actionMap[a.id] = a; });

    // 查找某个行为的所有后代（递归）
    function getDescendants(parentId) {
        const descendants = [];
        const children = (window._allActions || []).filter(a => a.parent_id === parentId);
        children.forEach(child => {
            descendants.push(child.id);
            descendants.push(...getDescendants(child.id));
        });
        return descendants;
    }

    // 需要排除的ID：自己 + 自己的所有后代
    const excludeIds = new Set();
    if (excludeId) {
        excludeIds.add(excludeId);
        getDescendants(excludeId).forEach(id => excludeIds.add(id));
    }

    // 显示所有行为（按层级缩进展示），排除自己和后代
    function renderOption(a, level) {
        if (excludeIds.has(a.id)) return;
        const indent = level > 0 ? '&nbsp;&nbsp;'.repeat(level) + '└ ' : '';
        select.innerHTML += `<option value="${a.id}">${indent}${escapeHtml(a.name)}</option>`;
        const children = (window._allActions || []).filter(x => x.parent_id === a.id);
        children.forEach(child => renderOption(child, level + 1));
    }

    const rootActions = (window._allActions || []).filter(a => !a.parent_id);
    rootActions.forEach(a => renderOption(a, 0));
}

function showActionModal() {
    document.getElementById('action-modal-title').textContent = '新增行为';
    document.getElementById('edit-action-id').value = '';
    document.getElementById('action-name').value = '';
    document.getElementById('action-weight').value = '1.0';
    document.getElementById('action-desc').value = '';
    // 重置语义属性
    document.getElementById('action-type').value = 'other';
    document.getElementById('action-certainty').value = 'probabilistic';
    document.getElementById('action-has-result').value = 'false';
    document.getElementById('action-determine').value = '';
    document.getElementById('action-trigger').value = '';
    document.getElementById('action-semantic-fields').style.display = 'none';
    populateParentSelect(null);
    document.getElementById('action-modal').classList.add('show');
}

function editAction(a) {
    document.getElementById('action-modal-title').textContent = '编辑行为';
    document.getElementById('edit-action-id').value = a.id;
    document.getElementById('action-name').value = a.name;
    document.getElementById('action-weight').value = a.default_weight;
    document.getElementById('action-desc').value = a.description || '';
    // 填充语义属性
    document.getElementById('action-type').value = a.action_type || 'other';
    document.getElementById('action-certainty').value = a.certainty || 'probabilistic';
    document.getElementById('action-has-result').value = a.has_result_status ? 'true' : 'false';
    document.getElementById('action-determine').value = a.determine_content || '';
    document.getElementById('action-trigger').value = a.trigger_condition || '';
    populateParentSelect(a.id);
    document.getElementById('action-parent').value = a.parent_id || '';
    document.getElementById('action-modal').classList.add('show');
}

async function saveAction() {
    const id = document.getElementById('edit-action-id').value;
    const parentId = document.getElementById('action-parent').value;
    const data = {
        name: document.getElementById('action-name').value.trim(),
        default_weight: parseFloat(document.getElementById('action-weight').value) || 1.0,
        description: document.getElementById('action-desc').value.trim(),
        parent_id: parentId ? parseInt(parentId) : null,
        // 语义属性
        action_type: document.getElementById('action-type').value,
        certainty: document.getElementById('action-certainty').value,
        has_result_status: document.getElementById('action-has-result').value === 'true',
        determine_content: document.getElementById('action-determine').value.trim() || null,
        trigger_condition: document.getElementById('action-trigger').value.trim() || null
    };
    if (!data.name) { showToast('请输入行为名称', 'error'); return; }
    const result = id
        ? await api('PUT', '/actions/' + id, data)
        : await api('POST', '/actions', data);
    if (result) {
        showToast(id ? '行为已更新' : '行为已添加', 'success');
        hideModal('action-modal');
        await loadActions();
    }
}

async function deleteAction(id) {
    if (!confirmAction('确定删除这个行为吗？')) return;
    const result = await api('DELETE', '/actions/' + id);
    if (result) { showToast('行为已删除', 'success'); await loadActions(); }
}

// ========== 版型库 ==========
async function loadSetups() {
    const result = await api('GET', '/setups');
    const container = document.getElementById('setups-list');
    if (!result || !result.data || result.data.length === 0) {
        container.innerHTML = '<div class="empty-state"><p>暂无版型</p></div>';
        return;
    }
    let html = '<table class="table"><thead><tr>';
    html += '<th>ID</th><th>名称</th><th>身份配置</th><th>描述</th><th>操作</th>';
    html += '</tr></thead><tbody>';
    result.data.forEach(s => {
        let configText = s.role_config;
        try {
            const obj = JSON.parse(s.role_config);
            configText = Object.entries(obj).map(([k,v]) => `${k}×${v}`).join('、');
        } catch(e) {}
        html += `<tr>
            <td>${s.id}</td>
            <td><strong>${escapeHtml(s.name)}</strong></td>
            <td style="font-size:12px;">${escapeHtml(configText)}</td>
            <td>${escapeHtml(s.description || '-')}</td>
            <td class="actions">
                <button class="btn btn-secondary btn-sm" onclick='editSetup(${JSON.stringify(s)})'>编辑</button>
                <button class="btn btn-danger btn-sm" onclick="deleteSetup(${s.id})">删除</button>
            </td>
        </tr>`;
    });
    html += '</tbody></table>';
    container.innerHTML = html;
}

// 渲染版型身份配置列表
function renderSetupRoleList(configData) {
    const container = document.getElementById('setup-config-list');
    if (!allRoles || allRoles.length === 0) {
        container.innerHTML = '<div class="empty-state"><p>暂无身份，请先在身份库添加</p></div>';
        return;
    }

    let html = '';
    allRoles.forEach(role => {
        const count = configData && configData[role.name] ? configData[role.name] : 0;
        const campCls = getCampClass(role.camp);
        const hasCount = count > 0;
        html += `<div class="setup-role-item ${hasCount ? 'has-count' : ''}">
            <span class="setup-role-name">
                <span class="setup-role-camp badge badge-${campCls}">${escapeHtml(role.camp || '-')}</span>
                ${escapeHtml(role.name)}
            </span>
            <input type="number" class="setup-role-count ${hasCount ? 'has-value' : ''}"
                   data-role="${escapeHtml(role.name)}" value="${count}" min="0" max="20"
                   oninput="onSetupCountChange(this)">
        </div>`;
    });
    container.innerHTML = html;
    updateSetupTotalCount();
}

// 数量输入变化时更新样式和总人数
function onSetupCountChange(input) {
    const count = parseInt(input.value) || 0;
    const item = input.closest('.setup-role-item');
    if (count > 0) {
        item.classList.add('has-count');
        input.classList.add('has-value');
    } else {
        item.classList.remove('has-count');
        input.classList.remove('has-value');
    }
    updateSetupTotalCount();
}

// 更新版型总人数显示
function updateSetupTotalCount() {
    const inputs = document.querySelectorAll('.setup-role-count');
    let total = 0;
    inputs.forEach(input => {
        total += parseInt(input.value) || 0;
    });
    document.getElementById('setup-total-count').textContent = `共 ${total} 人`;
}

// 从表单收集身份配置JSON
function collectSetupConfig() {
    const inputs = document.querySelectorAll('.setup-role-count');
    const config = {};
    inputs.forEach(input => {
        const count = parseInt(input.value) || 0;
        if (count > 0) {
            config[input.dataset.role] = count;
        }
    });
    return JSON.stringify(config);
}

function showSetupModal() {
    document.getElementById('setup-modal-title').textContent = '新增版型';
    document.getElementById('edit-setup-id').value = '';
    document.getElementById('setup-name').value = '';
    document.getElementById('setup-desc').value = '';
    // 默认配置：预女猎白
    const defaultConfig = {"狼人":4,"预言家":1,"女巫":1,"猎人":1,"白痴":1,"平民":4};
    renderSetupRoleList(defaultConfig);
    document.getElementById('setup-modal').classList.add('show');
}

function editSetup(s) {
    document.getElementById('setup-modal-title').textContent = '编辑版型';
    document.getElementById('edit-setup-id').value = s.id;
    document.getElementById('setup-name').value = s.name;
    document.getElementById('setup-desc').value = s.description || '';
    // 解析已有JSON配置并回填
    let configData = {};
    try {
        configData = JSON.parse(s.role_config);
    } catch(e) {
        configData = {};
    }
    renderSetupRoleList(configData);
    document.getElementById('setup-modal').classList.add('show');
}

async function saveSetup() {
    const id = document.getElementById('edit-setup-id').value;
    const config = collectSetupConfig();
    const configObj = JSON.parse(config);
    if (Object.keys(configObj).length === 0) {
        showToast('请至少为一个身份设置数量', 'error');
        return;
    }
    const data = {
        name: document.getElementById('setup-name').value.trim(),
        role_config: config,
        description: document.getElementById('setup-desc').value.trim()
    };
    if (!data.name) { showToast('请输入版型名称', 'error'); return; }
    const result = id
        ? await api('PUT', '/setups/' + id, data)
        : await api('POST', '/setups', data);
    if (result) {
        showToast(id ? '版型已更新' : '版型已添加', 'success');
        hideModal('setup-modal');
        await loadSetups();
    }
}

async function deleteSetup(id) {
    if (!confirmAction('确定删除这个版型吗？')) return;
    const result = await api('DELETE', '/setups/' + id);
    if (result) { showToast('版型已删除', 'success'); await loadSetups(); }
}
