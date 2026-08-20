// 首页 - 对局列表

let setups = [];

// 页面加载
document.addEventListener('DOMContentLoaded', async () => {
    await loadSetups();
    await loadGames();
});

// 加载版型列表
async function loadSetups() {
    const result = await api('GET', '/setups');
    if (result) {
        setups = result.data;
        const select = document.getElementById('new-game-setup');
        setups.forEach(s => {
            const opt = document.createElement('option');
            opt.value = s.id;
            opt.textContent = s.name;
            select.appendChild(opt);
        });
    }
}

// 加载对局列表
async function loadGames() {
    const result = await api('GET', '/games');
    const container = document.getElementById('game-list');
    if (!result || !result.data || result.data.length === 0) {
        container.innerHTML = `
            <div class="empty-state">
                <div class="empty-state-icon">🎮</div>
                <p>暂无对局，点击右上角"新建对局"开始</p>
            </div>`;
        return;
    }
    let html = '<table class="table"><thead><tr>';
    html += '<th>ID</th><th>对局编号</th><th>版型</th><th>玩家数</th><th>状态</th><th>创建时间</th><th>操作</th>';
    html += '</tr></thead><tbody>';
    result.data.forEach(g => {
        html += `<tr>
            <td>${g.id}</td>
            <td><strong>${escapeHtml(g.game_code)}</strong></td>
            <td>${escapeHtml(g.setup_name || '-')}</td>
            <td>${g.player_count || '-'}</td>
            <td>${statusBadge(g.status)}</td>
            <td>${formatTime(g.created_at)}</td>
            <td class="actions">
                <a href="/game/${g.id}" class="btn btn-primary btn-sm">进入</a>
                <button class="btn btn-danger btn-sm" onclick="deleteGame(${g.id})">删除</button>
            </td>
        </tr>`;
    });
    html += '</tbody></table>';
    container.innerHTML = html;
}

// 显示新建对局模态框
function showCreateGameModal() {
    document.getElementById('create-game-modal').classList.add('show');
    document.getElementById('new-game-code').value = '';
    document.getElementById('new-game-count').value = '';
    document.getElementById('new-game-notes').value = '';
    document.getElementById('new-game-setup').value = '';
}

function hideCreateGameModal() {
    document.getElementById('create-game-modal').classList.remove('show');
}

// 创建对局
async function createGame() {
    const code = document.getElementById('new-game-code').value.trim();
    const setupId = document.getElementById('new-game-setup').value;
    const count = document.getElementById('new-game-count').value;
    const notes = document.getElementById('new-game-notes').value.trim();
    if (!code) {
        showToast('请输入对局编号', 'error');
        return;
    }
    const data = { game_code: code, notes: notes };
    if (setupId) data.setup_id = parseInt(setupId);
    if (count) data.player_count = parseInt(count);
    const result = await api('POST', '/games', data);
    if (result) {
        showToast('对局创建成功', 'success');
        hideCreateGameModal();
        await loadGames();
    }
}

// 删除对局
async function deleteGame(id) {
    if (!confirmAction('确定要删除这个对局吗？所有相关记录都会被删除。')) return;
    const result = await api('DELETE', '/games/' + id);
    if (result) {
        showToast('对局已删除', 'success');
        await loadGames();
    }
}
