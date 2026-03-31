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

document.getElementById("threshold")?.addEventListener("input", function updateThreshold() {
    document.getElementById("threshold-value").textContent = this.value;
});

function splitInterests(value) {
    return value
        .split(",")
        .map((item) => item.trim())
        .filter(Boolean);
}

function getPayloadFromForm() {
    return {
        login: document.getElementById("login").value.trim(),
        email: document.getElementById("email").value.trim(),
        password: document.getElementById("password").value,
        interests: splitInterests(document.getElementById("interests").value),
        threshold: parseInt(document.getElementById("threshold").value, 10),
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
        showStatus("Сначала войдите в аккаунт.", "error");
        return false;
    }
    return true;
}

function applyUserToForm(user) {
    currentUser = user;
    document.getElementById("login").value = user.login || "";
    document.getElementById("email").value = user.email || "";
    document.getElementById("interests").value = (user.interests || []).join(", ");
    document.getElementById("threshold").value = user.news_threshold || 6;
    document.getElementById("threshold-value").textContent = user.news_threshold || 6;
    renderUserCard();
}

function renderUserCard() {
    const container = document.getElementById("user-info");
    if (!currentUser) {
        container.classList.add("hidden");
        container.innerHTML = "";
        return;
    }

    container.innerHTML = `
        <div class="user-card-title">Аккаунт подключен</div>
        <div class="user-card-meta">
            <span>Логин: <strong>${escapeHtml(currentUser.login || "-")}</strong></span>
            <span>Email: <strong>${escapeHtml(currentUser.email || "-")}</strong></span>
            <span>Интересы: <strong>${escapeHtml((currentUser.interests || []).join(", ") || "-")}</strong></span>
        </div>
    `;
    container.classList.remove("hidden");
}

function saveSession(token, user) {
    authToken = token;
    localStorage.setItem("authToken", token);
    if (user) {
        localStorage.setItem("userId", String(user.id));
        applyUserToForm(user);
    }
}

function clearSession() {
    authToken = "";
    currentUser = null;
    localStorage.removeItem("authToken");
    localStorage.removeItem("userId");
    renderUserCard();
}

async function handleApiResponse(response) {
    const data = await response.json().catch(() => ({}));
    if (!response.ok) {
        throw new Error(data.error || "Ошибка запроса");
    }
    return data;
}

async function registerUser() {
    const payload = getPayloadFromForm();
    if (!payload.login || !payload.password) {
        showStatus("Укажите логин и пароль.", "error");
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
        showStatus("Регистрация прошла успешно.", "ok");
    } catch (error) {
        showStatus(error.message, "error");
    }
}

async function loginUser() {
    const payload = getPayloadFromForm();
    if (!payload.login || !payload.password) {
        showStatus("Введите логин и пароль.", "error");
        return;
    }

    try {
        const response = await fetch(`${API_BASE}/auth/login`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
                login: payload.login,
                password: payload.password,
            }),
        });
        const data = await handleApiResponse(response);
        saveSession(data.token, data.user);
        showStatus("Вход выполнен.", "ok");
    } catch (error) {
        showStatus(error.message, "error");
    }
}

async function logoutUser() {
    clearSession();
    showStatus("Сессия очищена.", "ok");
}

async function fetchNews() {
    if (!ensureAuthorized()) {
        return;
    }

    showStatus("Загрузка новостей...", "ok");
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
        showStatus(`Загружено ${data.count} новостей.`, "ok");
    } catch (error) {
        showStatus(error.message, "error");
    }
}

function renderNews(newsList) {
    const container = document.getElementById("news-list");
    if (!newsList || newsList.length === 0) {
        container.innerHTML = "<p>Нет новостей для отображения.</p>";
        return;
    }

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

    showStatus("Генерация сводки...", "ok");
    try {
        const response = await fetch(`${API_BASE}/users/me/digest`, {
            method: "GET",
            headers: getAuthHeaders(),
        });
        const data = await handleApiResponse(response);
        document.getElementById("digest-content").textContent = data.digest || "Сводка пока пуста.";
        showStatus(`Сводка создана на основе ${data.news_count} новостей.`, "ok");
    } catch (error) {
        showStatus(error.message, "error");
    }
}

async function saveSettings() {
    if (!ensureAuthorized()) {
        return;
    }

    const payload = getPayloadFromForm();
    try {
        const response = await fetch(`${API_BASE}/users/me/interests`, {
            method: "PUT",
            headers: {
                "Content-Type": "application/json",
                ...getAuthHeaders(),
            },
            body: JSON.stringify({
                interests: payload.interests,
                threshold: payload.threshold,
            }),
        });
        const data = await handleApiResponse(response);
        applyUserToForm(data.user);
        showStatus("Настройки сохранены в базе.", "ok");
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
    if (!authToken) {
        return;
    }

    try {
        const response = await fetch(`${API_BASE}/auth/me`, {
            method: "GET",
            headers: getAuthHeaders(),
        });
        const data = await handleApiResponse(response);
        applyUserToForm(data.user);
        showStatus("Сессия восстановлена.", "ok");
    } catch (error) {
        clearSession();
        showStatus("Сохраненная сессия истекла, войдите снова.", "error");
    }
}

document.addEventListener("DOMContentLoaded", restoreSession);
