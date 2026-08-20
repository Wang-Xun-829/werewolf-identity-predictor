// 库管理

let currentTab = 'roles';

document.addEventListener('DOMContentLoaded', () => {
    loadRoles();
});

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
    let html = '<table class="table"><thead><tr>';
    html += '<th>ID</th><th>名称</th><th>默认权重</th><th>描述</th><th>操作</th>';
    html += '</tr></thead><tbody>';
    result.data.forEach(a => {
        html += `<tr>
            <td>${a.id}</td>
            <td><strong>${escapeHtml(a.name)}</strong></td>
            <td>${a.default_weight}</td>
            <td>${escapeHtml(a.description || '-')}</td>
            <td class="actions">
                <button class="btn btn-secondary btn-sm" onclick='editAction(${JSON.stringify(a)})'>编辑</button>
                <button class="btn btn-danger btn-sm" onclick="deleteAction(${a.id})">删除</button>
            </td>
        </tr>`;
    });
    html += '</tbody></table>';
    container.innerHTML = html;
}

function showActionModal() {
    document.getElementById('action-modal-title').textContent = '新增行为';
    document.getElementById('edit-action-id').value = '';
    document.getElementById('action-name').value = '';
    document.getElementById('action-weight').value = '1.0';
    document.getElementById('action-desc').value = '';
    document.getElementById('action-modal').classList.add('show');
}

function editAction(a) {
    document.getElementById('action-modal-title').textContent = '编辑行为';
    document.getElementById('edit-action-id').value = a.id;
    document.getElementById('action-name').value = a.name;
    document.getElementById('action-weight').value = a.default_weight;
    document.getElementById('action-desc').value = a.description || '';
    document.getElementById('action-modal').classList.add('show');
}

async function saveAction() {
    const id = document.getElementById('edit-action-id').value;
    const data = {
        name: document.getElementById('action-name').value.trim(),
        default_weight: parseFloat(document.getElementById('action-weight').value) || 1.0,
        description: document.getElementById('action-desc').value.trim()
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

function showSetupModal() {
    document.getElementById('setup-modal-title').textContent = '新增版型';
    document.getElementById('edit-setup-id').value = '';
    document.getElementById('setup-name').value = '';
    document.getElementById('setup-config').value = '{"狼人":4,"预言家":1,"女巫":1,"猎人":1,"白痴":1,"平民":4}';
    document.getElementById('setup-desc').value = '';
    document.getElementById('setup-modal').classList.add('show');
}

function editSetup(s) {
    document.getElementById('setup-modal-title').textContent = '编辑版型';
    document.getElementById('edit-setup-id').value = s.id;
    document.getElementById('setup-name').value = s.name;
    document.getElementById('setup-config').value = s.role_config;
    document.getElementById('setup-desc').value = s.description || '';
    document.getElementById('setup-modal').classList.add('show');
}

async function saveSetup() {
    const id = document.getElementById('edit-setup-id').value;
    const config = document.getElementById('setup-config').value.trim();
    try { JSON.parse(config); } catch(e) { showToast('身份配置不是有效的JSON格式', 'error'); return; }
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
