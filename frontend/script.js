/**
 * IDO SKILLS News - Frontend JavaScript
 */

const API_BASE = 'http://localhost:5000/api';
let currentUserId = null;

// Переключение вкладок
function showTab(tabId) {
    document.querySelectorAll('.tab-content').forEach(tab => {
        tab.classList.remove('active');
    });
    document.querySelectorAll('.tab-btn').forEach(btn => {
        btn.classList.remove('active');
    });
    document.getElementById(tabId).classList.add('active');
    event.target.classList.add('active');
}

// Обновление значения порога
document.getElementById('threshold')?.addEventListener('input', function() {
    document.getElementById('threshold-value').textContent = this.value;
});

// Регистрация пользователя
async function registerUser() {
    const username = document.getElementById('username').value;
    const email = document.getElementById('email').value;
    const interests = document.getElementById('interests').value.split(',').map(s => s.trim());
    
    try {
        const response = await fetch(`${API_BASE}/users`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ username, email, interests })
        });
        
        if (response.ok) {
            const user = await response.json();
            currentUserId = user.id;
            localStorage.setItem('userId', user.id);
            document.getElementById('user-info').innerHTML = `
                <div class="status ok">✅ Пользователь зарегистрирован: ${user.username}</div>
            `;
            document.getElementById('user-info').classList.remove('hidden');
            showStatus('Пользователь успешно зарегистрирован!', 'ok');
        } else {
            showStatus('Ошибка регистрации', 'error');
        }
    } catch (error) {
        showStatus('Ошибка подключения к серверу', 'error');
        console.error(error);
    }
}

// Получение новостей
async function fetchNews() {
    if (!currentUserId) {
        showStatus('Сначала зарегистрируйтесь', 'error');
        return;
    }
    
    showStatus('Загрузка новостей...', 'ok');
    
    try {
        const response = await fetch(`${API_BASE}/news/fetch`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ user_id: currentUserId })
        });
        
        if (response.ok) {
            const data = await response.json();
            renderNews(data.news);
            showStatus(`Загружено ${data.count} новостей`, 'ok');
        } else {
            showStatus('Ошибка загрузки новостей', 'error');
        }
    } catch (error) {
        showStatus('Ошибка подключения к серверу', 'error');
        console.error(error);
    }
}

// Отображение новостей
function renderNews(newsList) {
    const container = document.getElementById('news-list');
    if (!newsList || newsList.length === 0) {
        container.innerHTML = '<p>Нет новостей для отображения</p>';
        return;
    }
    
    container.innerHTML = newsList.map(news => `
        <div class="news-item">
            <h3>${escapeHtml(news.title)}</h3>
            <div class="meta">
                <span>📁 ${escapeHtml(news.source || 'Неизвестно')}</span>
                <span>🕐 ${news.published_at ? new Date(news.published_at).toLocaleString('ru') : 'Неизвестно'}</span>
                <span class="score">⭐ Важность: ${news.importance_score}/10</span>
            </div>
            <a href="${news.url}" target="_blank" class="btn-primary">Читать оригинал</a>
        </div>
    `).join('');
}

// Получение сводки
async function getDigest() {
    if (!currentUserId) {
        showStatus('Сначала зарегистрируйтесь', 'error');
        return;
    }
    
    showStatus('Генерация сводки...', 'ok');
    
    try {
        const response = await fetch(`${API_BASE}/users/${currentUserId}/digest`);
        
        if (response.ok) {
            const data = await response.json();
            document.getElementById('digest-content').textContent = data.digest;
            showStatus(`Сводка сгенерирована (${data.news_count} новостей)`, 'ok');
        } else {
            showStatus('Ошибка генерации сводки', 'error');
        }
    } catch (error) {
        showStatus('Ошибка подключения к серверу', 'error');
        console.error(error);
    }
}

// Сохранение настроек
async function saveSettings() {
    if (!currentUserId) {
        showStatus('Сначала зарегистрируйтесь', 'error');
        return;
    }
    
    const threshold = document.getElementById('threshold').value;
    
    try {
        const response = await fetch(`${API_BASE}/users/${currentUserId}/interests`, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ 
                interests: document.getElementById('interests').value.split(',').map(s => s.trim()),
                threshold: parseInt(threshold)
            })
        });
        
        if (response.ok) {
            showStatus('Настройки сохранены', 'ok');
        } else {
            showStatus('Ошибка сохранения', 'error');
        }
    } catch (error) {
        showStatus('Ошибка подключения к серверу', 'error');
    }
}

// Утилита для экранирования HTML
function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

// Показ статуса
function showStatus(message, type) {
    const statusEl = document.getElementById('status');
    statusEl.textContent = message;
    statusEl.className = 'status ' + type;
    setTimeout(() => {
        statusEl.textContent = '';
        statusEl.className = 'status';
    }, 5000);
}

// Загрузка сохранённого пользователя при старте
document.addEventListener('DOMContentLoaded', function() {
    const savedUserId = localStorage.getItem('userId');
    if (savedUserId) {
        currentUserId = savedUserId;
        showStatus('Пользователь загружен из памяти', 'ok');
    }
});
