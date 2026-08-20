// 通用工具函数

const API_BASE = '/api';

// API 请求封装
async function api(method, path, data = null) {
    const url = API_BASE + path;
    const options = {
        method: method,
        headers: { 'Content-Type': 'application/json' }
    };
    if (data) {
        options.body = JSON.stringify(data);
    }
    try {
        const resp = await fetch(url, options);
        const result = await resp.json();
        if (!resp.ok || result.success === false) {
            showToast(result.message || '请求失败', 'error');
            return null;
        }
        return result;
    } catch (e) {
        showToast('网络错误: ' + e.message, 'error');
        return null;
    }
}

// Toast 提示
function showToast(message, type = 'info') {
    const toast = document.getElementById('toast');
    if (!toast) return;
    toast.textContent = message;
    toast.className = 'toast show ' + type;
    setTimeout(() => {
        toast.className = 'toast';
    }, 3000);
}

// 确认对话框
function confirmAction(message) {
    return window.confirm(message);
}

// 格式化时间
function formatTime(datetime) {
    if (!datetime) return '-';
    const d = new Date(datetime);
    return d.toLocaleString('zh-CN', {
        month: '2-digit', day: '2-digit',
        hour: '2-digit', minute: '2-digit'
    });
}

// 获取阵营对应的样式类
function getCampClass(camp) {
    if (camp === '好人') return 'good';
    if (camp === '狼人') return 'wolf';
    if (camp === '第三方') return 'third';
    return 'neutral';
}

// 获取阵营标签HTML
function campBadge(camp) {
    const cls = getCampClass(camp);
    return `<span class="badge badge-${cls}">${camp || '-'}</span>`;
}

// 状态标签
function statusBadge(status) {
    const map = {
        '进行中': 'status-playing',
        '已结束': 'status-finished',
        '已确认': 'status-confirmed'
    };
    const cls = map[status] || '';
    return `<span class="${cls}">${status}</span>`;
}

// 转义HTML
function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}
