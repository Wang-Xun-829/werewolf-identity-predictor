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

// ============================================================
// 可搜索下拉框组件
// ============================================================
/**
 * 把普通的select元素转换成可搜索的下拉框
 * @param {string} selectId - select元素的ID
 * @param {string} placeholder - 搜索框占位符
 */
function initSearchableSelect(selectId, placeholder = '搜索...') {
    const select = document.getElementById(selectId);
    if (!select || select.dataset.searchable === 'true') return;

    select.dataset.searchable = 'true';
    select.style.display = 'none';

    // 创建容器
    const wrapper = document.createElement('div');
    wrapper.className = 'searchable-select';
    wrapper.style.position = 'relative';

    // 创建显示框
    const display = document.createElement('div');
    display.className = 'searchable-select-display';
    display.style.cssText = `
        padding: 8px 12px;
        border: 1px solid var(--border-color, #334155);
        border-radius: 6px;
        background: var(--input-bg, rgba(15,23,42,0.6));
        color: var(--text-primary, #e2e8f0);
        cursor: pointer;
        min-height: 20px;
        font-size: 14px;
    `;
    display.textContent = placeholder;

    // 创建下拉面板
    const dropdown = document.createElement('div');
    dropdown.className = 'searchable-select-dropdown';
    dropdown.style.cssText = `
        position: absolute;
        top: 100%;
        left: 0;
        right: 0;
        background: var(--card-bg, #1e293b);
        border: 1px solid var(--border-color, #334155);
        border-radius: 6px;
        margin-top: 4px;
        z-index: 1000;
        display: none;
        max-height: 250px;
        overflow-y: auto;
        box-shadow: 0 4px 12px rgba(0,0,0,0.3);
    `;

    // 创建搜索框
    const searchInput = document.createElement('input');
    searchInput.type = 'text';
    searchInput.placeholder = placeholder;
    searchInput.style.cssText = `
        width: 100%;
        padding: 8px 12px;
        border: none;
        border-bottom: 1px solid var(--border-color, #334155);
        background: transparent;
        color: var(--text-primary, #e2e8f0);
        font-size: 14px;
        outline: none;
        box-sizing: border-box;
    `;

    // 创建选项列表
    const optionsList = document.createElement('div');
    optionsList.className = 'searchable-select-options';

    dropdown.appendChild(searchInput);
    dropdown.appendChild(optionsList);
    wrapper.appendChild(display);
    wrapper.appendChild(dropdown);
    select.parentNode.insertBefore(wrapper, select.nextSibling);

    // 渲染选项
    function renderOptions(filter = '') {
        optionsList.innerHTML = '';
        const options = select.querySelectorAll('option');
        let hasVisible = false;
        options.forEach(opt => {
            const text = opt.textContent;
            const value = opt.value;
            // 空值选项也显示（如"无目标"），但搜索时不匹配空值
            if (filter && value && !matchByPinyin(text, filter)) return;
            if (filter && !value) return; // 搜索时隐藏空值选项
            hasVisible = true;
            const item = document.createElement('div');
            item.style.cssText = `
                padding: 8px 12px;
                cursor: pointer;
                font-size: 14px;
                color: var(--text-primary, #e2e8f0);
            `;
            item.textContent = text;
            item.dataset.value = value;
            item.addEventListener('mouseenter', () => {
                item.style.background = 'rgba(0,240,255,0.1)';
            });
            item.addEventListener('mouseleave', () => {
                item.style.background = 'transparent';
            });
            item.addEventListener('click', () => {
                select.value = value;
                display.textContent = text;
                dropdown.style.display = 'none';
                select.dispatchEvent(new Event('change'));
            });
            optionsList.appendChild(item);
        });
        if (!hasVisible) {
            optionsList.innerHTML = '<div style="padding:12px;color:var(--text-muted);text-align:center;">无匹配结果</div>';
        }
    }

    // 显示/隐藏下拉框
    display.addEventListener('click', (e) => {
        e.stopPropagation();
        const isOpen = dropdown.style.display === 'block';
        // 关闭所有其他下拉框
        document.querySelectorAll('.searchable-select-dropdown').forEach(d => d.style.display = 'none');
        if (!isOpen) {
            dropdown.style.display = 'block';
            searchInput.value = '';
            renderOptions();
            setTimeout(() => searchInput.focus(), 50);
        }
    });

    // 搜索
    searchInput.addEventListener('input', (e) => {
        renderOptions(e.target.value);
    });

    // 点击外部关闭
    document.addEventListener('click', (e) => {
        if (!wrapper.contains(e.target)) {
            dropdown.style.display = 'none';
        }
    });

    // 同步外部修改select的值
    const originalSetValue = Object.getOwnPropertyDescriptor(window.HTMLSelectElement.prototype, 'value').set;
    Object.defineProperty(select, 'value', {
        get() { return this.getAttribute('value') || this.options[this.selectedIndex]?.value || ''; },
        set(v) {
            originalSetValue.call(this, v);
            const opt = this.querySelector(`option[value="${v}"]`);
            if (opt) display.textContent = opt.textContent;
        }
    });

    // 初始化显示
    if (select.value) {
        const opt = select.querySelector(`option[value="${select.value}"]`);
        if (opt) display.textContent = opt.textContent;
    }

    return { select, wrapper, display, dropdown, renderOptions };
}


// ============================================================
// 拼音搜索辅助函数
// ============================================================

/**
 * 获取中文文本的拼音全拼（不带声调）
 * @param {string} text - 中文文本
 * @returns {string} 拼音全拼，如 "wang xun"
 */
function getPinyinFull(text) {
    if (!text) return '';
    try {
        if (typeof pinyin !== 'undefined') {
            return pinyin(text, { toneType: 'none', type: 'string' }).toLowerCase();
        }
    } catch (e) {
        // pinyin库未加载时返回空
    }
    return '';
}

/**
 * 获取中文文本的拼音首字母
 * @param {string} text - 中文文本
 * @returns {string} 拼音首字母，如 "w x"
 */
function getPinyinInitials(text) {
    if (!text) return '';
    try {
        if (typeof pinyin !== 'undefined') {
            return pinyin(text, { pattern: 'first', toneType: 'none', type: 'string' }).toLowerCase();
        }
    } catch (e) {
        // pinyin库未加载时返回空
    }
    return '';
}

/**
 * 检查文本是否匹配关键词（支持中文、拼音全拼、拼音首字母）
 * @param {string} text - 要检查的文本（如玩家名称）
 * @param {string} keyword - 搜索关键词
 * @returns {boolean} 是否匹配
 */
function matchByPinyin(text, keyword) {
    if (!text || !keyword) return false;
    
    const textLower = text.toLowerCase();
    const keywordLower = keyword.toLowerCase().trim();
    
    if (!keywordLower) return true;
    
    // 1. 中文直接包含匹配
    if (textLower.includes(keywordLower)) return true;
    
    // 2. 拼音全拼匹配（支持带空格和不带空格）
    const pinyinFull = getPinyinFull(text);
    if (pinyinFull) {
        const pinyinFullNoSpace = pinyinFull.replace(/\s+/g, '');
        if (pinyinFull.includes(keywordLower) || pinyinFullNoSpace.includes(keywordLower)) {
            return true;
        }
    }
    
    // 3. 拼音首字母匹配（支持带空格和不带空格）
    const pinyinInitials = getPinyinInitials(text);
    if (pinyinInitials) {
        const pinyinInitialsNoSpace = pinyinInitials.replace(/\s+/g, '');
        if (pinyinInitials.includes(keywordLower) || pinyinInitialsNoSpace.includes(keywordLower)) {
            return true;
        }
    }
    
    return false;
}