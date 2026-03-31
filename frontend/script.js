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

document.addEventListener("DOMContentLoaded", restoreSession);
