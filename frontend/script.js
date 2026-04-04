const API_BASE = window.location.protocol === "file:"
    ? "http://localhost:5000/api"
    : `${window.location.origin}/api`;

let currentUser = null;
let authToken = localStorage.getItem("authToken") || "";

function showTab(tabId, button) {
    document.querySelectorAll(".tab-content").forEach((tab) => tab.classList.remove("active"));
    document.querySelectorAll(".tab-btn").forEach((btn) => btn.classList.remove("active"));
    document.getElementById(tabId).classList.add("active");
    if (button) {
        button.classList.add("active");
    }
}

document.getElementById("settings-threshold")?.addEventListener("input", function updateThreshold() {
    document.getElementById("threshold-value").textContent = this.value;
});

function splitInterests(value) {
    return value
        .split(",")
        .map((item) => item.trim())
        .filter(Boolean);
}

function getRegisterPayload() {
    return {
        login: document.getElementById("register-login").value.trim(),
        email: document.getElementById("register-email").value.trim(),
        password: document.getElementById("register-password").value,
        interests: splitInterests(document.getElementById("settings-interests").value),
        threshold: parseInt(document.getElementById("settings-threshold").value, 10),
    };
}

function getLoginPayload() {
    return {
        login: document.getElementById("login-identifier").value.trim(),
        password: document.getElementById("login-password").value,
    };
}

function getSettingsPayload() {
    return {
        interests: splitInterests(document.getElementById("settings-interests").value),
        threshold: parseInt(document.getElementById("settings-threshold").value, 10),
    };
}

function getAuthHeaders() {
    if (!authToken) {
        return {};
    }

    return {
        Authorization: `Bearer ${authToken}`,
    };
}

function ensureAuthorized() {
    if (!authToken || !currentUser) {
        showStatus("Сначала выполните вход в аккаунт.", "error");
        return false;
    }
    return true;
}

function setSessionState(message, isActive) {
    const stateNode = document.getElementById("session-state");
    stateNode.textContent = message;
    stateNode.className = isActive ? "session-state active" : "session-state";
}

function applyUserToUI(user) {
    currentUser = user;
    document.getElementById("register-login").value = user.login || "";
    document.getElementById("register-email").value = user.email || "";
    document.getElementById("settings-interests").value = (user.interests || []).join(", ");
    document.getElementById("settings-threshold").value = user.news_threshold || 6;
    document.getElementById("threshold-value").textContent = user.news_threshold || 6;
    document.getElementById("login-identifier").value = user.login || "";
    renderUserCard();
    setSessionState(`Вы вошли как ${user.login}`, true);
}

function renderUserCard() {
    const container = document.getElementById("user-info");
    if (!currentUser) {
        container.className = "account-card-body empty";
        container.textContent = "Вы ещё не вошли в аккаунт.";
        return;
    }

    container.className = "account-card-body";
    container.innerHTML = `
        <div class="account-grid">
            <div><span class="account-label">Логин</span><strong>${escapeHtml(currentUser.login || "-")}</strong></div>
            <div><span class="account-label">Email</span><strong>${escapeHtml(currentUser.email || "-")}</strong></div>
            <div><span class="account-label">Интересы</span><strong>${escapeHtml((currentUser.interests || []).join(", ") || "-")}</strong></div>
            <div><span class="account-label">Порог</span><strong>${escapeHtml(String(currentUser.news_threshold || 6))}</strong></div>
        </div>
    `;
}

function saveSession(token, user) {
    authToken = token;
    localStorage.setItem("authToken", token);
    if (user) {
        localStorage.setItem("userId", String(user.id));
        applyUserToUI(user);
    }
}

function clearSession() {
    authToken = "";
    currentUser = null;
    localStorage.removeItem("authToken");
    localStorage.removeItem("userId");
    document.getElementById("login-password").value = "";
    document.getElementById("register-password").value = "";
    renderUserCard();
    setSessionState("Вы не вошли в аккаунт", false);
}

async function handleApiResponse(response) {
    const rawText = await response.text();
    let data = {};

    try {
        data = rawText ? JSON.parse(rawText) : {};
    } catch {
        data = {};
    }

    if (!response.ok) {
        throw new Error(data.error || rawText || `Ошибка запроса (${response.status})`);
    }

    return data;
}

async function registerUser() {
    const payload = getRegisterPayload();
    if (!payload.login || !payload.password) {
        showStatus("Для регистрации заполните логин и пароль.", "error");
        return;
    }

    try {
        const response = await fetch(`${API_BASE}/auth/register`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(payload),
        });
        const data = await handleApiResponse(response);
        saveSession(data.token, data.user);
        showStatus("Регистрация прошла успешно. Аккаунт создан и вход выполнен автоматически.", "ok");
    } catch (error) {
        showStatus(error.message, "error");
    }
}

async function loginUser() {
    const payload = getLoginPayload();
    if (!payload.login || !payload.password) {
        showStatus("Для входа укажите логин или email и пароль.", "error");
        return;
    }

    try {
        const response = await fetch(`${API_BASE}/auth/login`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(payload),
        });
        const data = await handleApiResponse(response);
        saveSession(data.token, data.user);
        showStatus("Вход выполнен успешно.", "ok");
    } catch (error) {
        showStatus(error.message, "error");
    }
}

async function logoutUser() {
    clearSession();
    showStatus("Вы вышли из аккаунта.", "ok");
}

async function fetchNews() {
    if (!ensureAuthorized()) {
        return;
    }

    showStatus("Запрашиваю новости по интересам из базы...", "ok");
    try {
        const response = await fetch(`${API_BASE}/news/fetch`, {
            method: "POST",
            headers: {
                "Content-Type": "application/json",
                ...getAuthHeaders(),
            },
            body: JSON.stringify({}),
        });
        const data = await handleApiResponse(response);
        renderNews(data.news);
        showStatus(`Получено ${data.count} новостей.`, "ok");
    } catch (error) {
        showStatus(error.message, "error");
    }
}

function renderNews(newsList) {
    const container = document.getElementById("news-list");
    if (!newsList || newsList.length === 0) {
        container.className = "news-list empty-state";
        container.textContent = "Под ваши интересы новости пока не найдены.";
        return;
    }

    container.className = "news-list";
    container.innerHTML = newsList
        .map((news) => `
            <article class="news-item">
                <h3>${escapeHtml(news.title)}</h3>
                <div class="meta">
                    <span>Источник: ${escapeHtml(news.source || "Не указан")}</span>
                    <span>Категория: ${escapeHtml(news.category || "Общее")}</span>
                    <span>Дата: ${news.published_at ? new Date(news.published_at).toLocaleString("ru-RU") : "Неизвестно"}</span>
                    <span class="score">Важность: ${news.importance_score}/10</span>
                </div>
                <p class="summary">${escapeHtml(news.summary || "")}</p>
                <a href="${news.url}" target="_blank" rel="noopener noreferrer" class="btn-secondary inline-link">Открыть источник</a>
            </article>
        `)
        .join("");
}

async function getDigest() {
    if (!ensureAuthorized()) {
        return;
    }

    showStatus("Формирую сводку по новостям...", "ok");
    try {
        const response = await fetch(`${API_BASE}/users/me/digest`, {
            method: "GET",
            headers: getAuthHeaders(),
        });
        const data = await handleApiResponse(response);
        const digestNode = document.getElementById("digest-content");
        digestNode.className = "digest-content";
        digestNode.textContent = data.digest || "Сводка пока пуста.";
        showStatus(`Сводка готова. Использовано новостей: ${data.news_count}.`, "ok");
    } catch (error) {
        showStatus(error.message, "error");
    }
}

async function saveSettings() {
    if (!ensureAuthorized()) {
        return;
    }

    const payload = getSettingsPayload();
    try {
        const response = await fetch(`${API_BASE}/users/me/interests`, {
            method: "PUT",
            headers: {
                "Content-Type": "application/json",
                ...getAuthHeaders(),
            },
            body: JSON.stringify(payload),
        });
        const data = await handleApiResponse(response);
        applyUserToUI(data.user);
        showStatus("Интересы и порог сохранены в базе данных.", "ok");
    } catch (error) {
        showStatus(error.message, "error");
    }
}

// ===== TAB 5: AI НОВОСТИ =====

const CATEGORY_COLORS = {
    технологии:  { bg: "#e0f0ff", text: "#0a5fa8" },
    политика:    { bg: "#fde8e8", text: "#9b2020" },
    бизнес:      { bg: "#e6f9f0", text: "#1a6b45" },
    спорт:       { bg: "#fff3e0", text: "#b35c00" },
    наука:       { bg: "#ede8ff", text: "#4a1fa8" },
    здоровье:    { bg: "#e8f8f0", text: "#147a50" },
    развлечения: { bg: "#fde8fb", text: "#8b1a8b" },
    мир:         { bg: "#e8f0fd", text: "#1a3fa8" },
    образование: { bg: "#fdf3e8", text: "#8b5a00" },
    безопасность:{ bg: "#fde8e8", text: "#8b1a1a" },
    стартапы:    { bg: "#e8fdfc", text: "#0a6b65" },
    экономика:   { bg: "#f0fde8", text: "#3a6b1a" },
    общество:    { bg: "#f5f0e8", text: "#6b5a1a" },
};

function categoryBadge(category) {
    const cat = (category || "общество").toLowerCase();
    const colors = CATEGORY_COLORS[cat] || { bg: "#f0f0f0", text: "#555" };
    return `<span class="ai-category-badge" style="background:${colors.bg};color:${colors.text}">${escapeHtml(cat)}</span>`;
}

function importanceBar(score) {
    const s = Math.max(1, Math.min(10, parseInt(score, 10) || 6));
    const pct = s * 10;
    let color = "#1f6feb";
    if (s >= 8) color = "#16a34a";
    if (s <= 4) color = "#f59e0b";
    return `
        <div class="ai-importance" title="Важность ${s}/10">
            <div class="ai-importance-bar" style="width:${pct}%;background:${color}"></div>
            <span>${s}/10</span>
        </div>`;
}

function renderAiNews(newsList, { topic, saved, model } = {}) {
    const container = document.getElementById("ai-news-list");

    if (!newsList || newsList.length === 0) {
        container.innerHTML = `<div class="ai-empty">По теме «${escapeHtml(topic || "—")}» ничего не найдено.</div>`;
        return;
    }

    const headerHtml = `
        <div class="ai-results-header">
            <span class="ai-results-count">${newsList.length} новостей</span>
            ${saved > 0 ? `<span class="ai-saved-badge">+${saved} сохранено в БД</span>` : ""}
            <span class="ai-model-tag">${escapeHtml(model || "Gemini")}</span>
        </div>`;

    const cardsHtml = newsList.map((item) => {
        const pubDate = item.published_at
            ? (() => { try { return new Date(item.published_at).toLocaleString("ru-RU"); } catch { return item.published_at; } })()
            : "";

        return `
        <article class="ai-news-card">
            <div class="ai-news-card-top">
                ${categoryBadge(item.category)}
                ${importanceBar(item.importance_score)}
            </div>
            <h3 class="ai-news-title">${escapeHtml(item.title || "Без заголовка")}</h3>
            <p class="ai-news-summary">${escapeHtml(item.summary || "")}</p>
            <div class="ai-news-meta">
                ${item.source ? `<span class="ai-source">📰 ${escapeHtml(item.source)}</span>` : ""}
                ${pubDate ? `<span class="ai-date">🕐 ${pubDate}</span>` : ""}
            </div>
            ${item.url ? `<a href="${escapeHtml(item.url)}" target="_blank" rel="noopener noreferrer" class="ai-source-link">Открыть источник →</a>` : ""}
        </article>`;
    }).join("");

    container.innerHTML = headerHtml + `<div class="ai-cards-grid">${cardsHtml}</div>`;
}

async function fetchAiNews() {
    const topicInput = document.getElementById("ai-news-topic");
    const topic = (topicInput?.value || "").trim();
    const btn = document.getElementById("ai-news-btn");
    const statusEl = document.getElementById("ai-news-status");

    // Показываем статус загрузки
    statusEl.style.display = "flex";
    statusEl.className = "ai-status loading";
    statusEl.innerHTML = `
        <div class="ai-spinner"></div>
        <span>Gemini 2.0 ищет новости${topic ? ` по теме «${escapeHtml(topic)}»` : ""}…</span>`;

    document.getElementById("ai-news-list").innerHTML = "";
    if (btn) {
        btn.disabled = true;
        btn.textContent = "Загрузка…";
    }

    try {
        const response = await fetch(`${API_BASE}/ai-news`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ topic: topic || "новости" }),
        });
        const data = await handleApiResponse(response);

        statusEl.className = "ai-status done";
        statusEl.innerHTML = `✦ Готово: ${data.total} новостей, ${data.saved} новых сохранено в базу`;

        renderAiNews(data.news, {
            topic: data.topic,
            saved: data.saved,
            model: data.model,
        });

        showStatus(`AI нашёл ${data.total} новостей, ${data.saved} новых добавлено в БД.`, "ok");
    } catch (error) {
        statusEl.className = "ai-status error";
        statusEl.innerHTML = `⚠ ${escapeHtml(error.message)}`;
        document.getElementById("ai-news-list").innerHTML = "";
        showStatus(error.message, "error");
    } finally {
        if (btn) {
            btn.disabled = false;
            btn.textContent = "Найти новости";
        }
    }
}

function escapeHtml(text) {
    const div = document.createElement("div");
    div.textContent = text;
    return div.innerHTML;
}

function showStatus(message, type) {
    const statusEl = document.getElementById("status");
    statusEl.textContent = message;
    statusEl.className = `status ${type}`;
}

async function restoreSession() {
    renderUserCard();
    setSessionState("Вы не вошли в аккаунт", false);

    if (!authToken) {
        return;
    }

    try {
        const response = await fetch(`${API_BASE}/auth/me`, {
            method: "GET",
            headers: getAuthHeaders(),
        });
        const data = await handleApiResponse(response);
        applyUserToUI(data.user);
        showStatus("Сессия восстановлена.", "ok");
    } catch (error) {
        clearSession();
        showStatus("Сохранённая сессия истекла. Выполните вход снова.", "error");
    }
}

const canvas = document.getElementById("neural-bg");
const ctx = canvas.getContext("2d");

let nodes = [];
const NODE_COUNT = 90;
const MAX_DIST = 120;

let mouse = { x: null, y: null };

function resize() {
    canvas.width = window.innerWidth;
    canvas.height = window.innerHeight;
}
resize();
window.addEventListener("resize", resize);

window.addEventListener("mousemove", (e) => {
    mouse.x = e.x;
    mouse.y = e.y;
});

class Node {
    constructor() {
        this.x = Math.random() * canvas.width;
        this.y = Math.random() * canvas.height;
        this.vx = (Math.random() - 0.5) * 0.6;
        this.vy = (Math.random() - 0.5) * 0.6;
    }

    move() {
        this.x += this.vx;
        this.y += this.vy;

        if (this.x < 0 || this.x > canvas.width) this.vx *= -1;
        if (this.y < 0 || this.y > canvas.height) this.vy *= -1;
    }

    draw() {
        ctx.beginPath();
        ctx.arc(this.x, this.y, 2, 0, Math.PI * 2);
        ctx.fillStyle = "rgba(31,111,235,0.7)";
        ctx.fill();
    }
}

function init() {
    nodes = [];
    for (let i = 0; i < NODE_COUNT; i++) {
        nodes.push(new Node());
    }
}
init();

function connect() {
    for (let i = 0; i < nodes.length; i++) {
        for (let j = i; j < nodes.length; j++) {
            let dx = nodes[i].x - nodes[j].x;
            let dy = nodes[i].y - nodes[j].y;
            let dist = Math.sqrt(dx * dx + dy * dy);

            if (dist < MAX_DIST) {
                ctx.strokeStyle = `rgba(31,111,235,${1 - dist / MAX_DIST})`;
                ctx.lineWidth = 1;
                ctx.beginPath();
                ctx.moveTo(nodes[i].x, nodes[i].y);
                ctx.lineTo(nodes[j].x, nodes[j].y);
                ctx.stroke();
            }
        }

        // связь с курсором
        if (mouse.x) {
            let dx = nodes[i].x - mouse.x;
            let dy = nodes[i].y - mouse.y;
            let dist = Math.sqrt(dx * dx + dy * dy);

            if (dist < 160) {
                ctx.strokeStyle = "rgba(255,140,0,0.6)";
                ctx.beginPath();
                ctx.moveTo(nodes[i].x, nodes[i].y);
                ctx.lineTo(mouse.x, mouse.y);
                ctx.stroke();
            }
        }
    }
}

function animate() {
    ctx.clearRect(0, 0, canvas.width, canvas.height);

    nodes.forEach((node) => {
        node.move();
        node.draw();
    });

    connect();

    requestAnimationFrame(animate);
}

animate();

document.addEventListener("DOMContentLoaded", restoreSession);
