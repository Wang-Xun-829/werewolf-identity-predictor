// 玩家管理

document.addEventListener('DOMContentLoaded', loadPlayers);

async function loadPlayers() {
    const result = await api('GET', '/players');
    const container = document.getElementById('player-list');
    if (!result || !result.data || result.data.length === 0) {
        container.innerHTML = `
            <div class="empty-state">
                <div class="empty-state-icon">👥</div>
                <p>暂无玩家，点击右上角"新增玩家"添加</p>
            </div>`;
        return;
    }
    let html = '<table class="table"><thead><tr>';
    html += '<th>ID</th><th>玩家名称</th><th>创建时间</th><th>操作</th>';
    html += '</tr></thead><tbody>';
    result.data.forEach(p => {
        html += `<tr>
            <td>${p.id}</td>
            <td><strong>${escapeHtml(p.name)}</strong></td>
            <td>${formatTime(p.created_at)}</td>
            <td class="actions">
                <button class="btn btn-secondary btn-sm" onclick="editPlayer(${p.id}, '${escapeHtml(p.name)}')">编辑</button>
                <button class="btn btn-danger btn-sm" onclick="deletePlayer(${p.id})">删除</button>
            </td>
        </tr>`;
    });
    html += '</tbody></table>';
    container.innerHTML = html;
}

function showAddPlayerModal() {
    document.getElementById('player-modal-title').textContent = '新增玩家';
    document.getElementById('edit-player-id').value = '';
    document.getElementById('player-name').value = '';
    document.getElementById('player-modal').classList.add('show');
}

function editPlayer(id, name) {
    document.getElementById('player-modal-title').textContent = '编辑玩家';
    document.getElementById('edit-player-id').value = id;
    document.getElementById('player-name').value = name;
    document.getElementById('player-modal').classList.add('show');
}

function hidePlayerModal() {
    document.getElementById('player-modal').classList.remove('show');
}

async function savePlayer() {
    const name = document.getElementById('player-name').value.trim();
    const id = document.getElementById('edit-player-id').value;
    if (!name) {
        showToast('请输入玩家名称', 'error');
        return;
    }
    let result;
    if (id) {
        result = await api('PUT', '/players/' + id, { name: name });
    } else {
        result = await api('POST', '/players', { name: name });
    }
    if (result) {
        showToast(id ? '玩家已更新' : '玩家已添加', 'success');
        hidePlayerModal();
        await loadPlayers();
    }
}

async function deletePlayer(id) {
    if (!confirmAction('确定要删除这个玩家吗？')) return;
    const result = await api('DELETE', '/players/' + id);
    if (result) {
        showToast('玩家已删除', 'success');
        await loadPlayers();
    }
}
