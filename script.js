function resolveApiBase() {
    const localApiBase = "http://localhost:5000/api";
    const { protocol, hostname, port, origin } = window.location;
    const localHosts = new Set(["localhost", "127.0.0.1", "0.0.0.0", ""]);

    if (protocol === "file:") {
        return localApiBase;
    }

    if (localHosts.has(hostname) && port !== "5000") {
        return localApiBase;
    }

    return `${origin}/api`;
}

const API_BASE = window.__API_BASE__ || resolveApiBase();

function getReadableError(error) {
    const message = error?.message || "Неизвестная ошибка";

    if (message === "Failed to fetch" || message.includes("NetworkError")) {
        return `Не удалось подключиться к API (${API_BASE}). Проверь, что папка api загружена в htdocs.`;
    }

    return message;
}

const INTEREST_OPTIONS = [
    { value: "искусственный интеллект", label: "ИИ", hint: "модели, ассистенты", icon: "sparkles" },
    { value: "технологии", label: "Технологии", hint: "железо и софт", icon: "cpu" },
    { value: "стартапы", label: "Стартапы", hint: "новые продукты", icon: "rocket" },
    { value: "бизнес", label: "Бизнес", hint: "рынки и компании", icon: "briefcase-business" },
    { value: "безопасность", label: "Безопасность", hint: "киберриски", icon: "shield-check" },
    { value: "наука", label: "Наука", hint: "исследования", icon: "atom" },
    { value: "образование", label: "Образование", hint: "университеты", icon: "graduation-cap" },
    { value: "экономика", label: "Экономика", hint: "деньги и тренды", icon: "chart-no-axes-combined" },
    { value: "Россия", label: "Россия", hint: "локальная повестка", icon: "map" },
    { value: "мир", label: "Мир", hint: "международное", icon: "globe-2" },
    { value: "здоровье", label: "Здоровье", hint: "медицина", icon: "heart-pulse" },
    { value: "культура", label: "Культура", hint: "люди и события", icon: "gallery-vertical-end" },
];

const SOURCE_OPTIONS = [
    { value: "google-news", label: "Google News", hint: "общий поиск", icon: "G", tone: "#a6edf7" },
    { value: "tass", label: "ТАСС", hint: "tass.ru", icon: "T", tone: "#b8d7ff" },
    { value: "rbc", label: "РБК", hint: "rbc.ru", icon: "Р", tone: "#8ed7ff" },
    { value: "kommersant", label: "Ъ", hint: "kommersant.ru", icon: "Ъ", tone: "#e7edf0" },
    { value: "interfax", label: "Интерфакс", hint: "interfax.ru", icon: "I", tone: "#b7f5d0" },
    { value: "ria", label: "РИА", hint: "ria.ru", icon: "R", tone: "#a6c7ff" },
    { value: "vedomosti", label: "Ведомости", hint: "vedomosti.ru", icon: "В", tone: "#e0e5ea" },
    { value: "habr", label: "Habr", hint: "habr.com", icon: "H", tone: "#a6edf7" },
    { value: "vc", label: "VC", hint: "vc.ru", icon: "VC", tone: "#c0f0ff" },
    { value: "techcrunch", label: "TechCrunch", hint: "techcrunch.com", icon: "TC", tone: "#9df7b4" },
];

let currentUser = null;
let authToken = localStorage.getItem("authToken") || "";
let selectedInterests = new Set(["искусственный интеллект", "технологии", "стартапы"]);
let selectedSources = new Set(["google-news", "rbc", "habr"]);
let authMode = "login";
let statusTimer = null;

function icon(name) {
    return `<i data-lucide="${name}"></i>`;
}

function refreshIcons() {
    if (window.lucide) {
        window.lucide.createIcons();
    }
}

function toggleMenu(force) {
    const shouldOpen = typeof force === "boolean" ? force : !document.body.classList.contains("menu-open");
    document.body.classList.toggle("menu-open", shouldOpen);
    document.querySelector(".menu-trigger")?.setAttribute("aria-expanded", String(shouldOpen));
}

function closeMenu() {
    toggleMenu(false);
}

function switchView(viewId) {
    if ((viewId === "feed" || viewId === "digest") && !authToken) {
        viewId = "account";
        showStatus("Войдите в аккаунт, чтобы открыть персональную ленту и сводку.", "error");
    }

    document.querySelectorAll(".view").forEach((view) => view.classList.remove("active"));
    document.querySelectorAll(".nav-button").forEach((btn) => btn.classList.remove("active"));

    document.getElementById(viewId)?.classList.add("active");
    const navButton = document.querySelector(`[data-view-button="${viewId}"]`);
    navButton?.classList.add("active");
    closeMenu();

    if (window.location.hash !== `#${viewId}`) {
        history.replaceState(null, "", `#${viewId}`);
    }

    window.scrollTo({ top: 0, behavior: "smooth" });
    if (viewId === "account") {
        renderAccountState();
    }
    initReveal();
    refreshIcons();
}

function splitInterests(value) {
    return String(value || "")
        .split(",")
        .map((item) => item.trim())
        .filter(Boolean);
}

function syncInterestsField() {
    const values = [...selectedInterests];
    const field = document.getElementById("settings-interests");
    const count = document.getElementById("interest-count");

    if (field) {
        field.value = values.join(", ");
    }
    if (count) {
        count.textContent = String(values.length);
    }
}

function syncSourceCount() {
    const count = document.getElementById("source-count");
    if (count) {
        count.textContent = String(selectedSources.size);
    }
}

function renderInterestPicker() {
    const container = document.getElementById("interest-picker");
    if (!container) {
        return;
    }

    container.innerHTML = INTEREST_OPTIONS.map((item) => {
        const active = selectedInterests.has(item.value);
        return `
            <button class="choice-option ${active ? "active" : ""}" type="button" onclick="toggleInterest('${escapeAttribute(item.value)}')">
                ${icon(item.icon)}
                <span>
                    <strong>${escapeHtml(item.label)}</strong>
                    <small>${escapeHtml(item.hint)}</small>
                </span>
                <span class="interest-check" aria-hidden="true"></span>
            </button>
        `;
    }).join("");

    syncInterestsField();
    refreshIcons();
}

function renderSourcePicker() {
    const container = document.getElementById("source-picker");
    if (!container) {
        return;
    }

    container.innerHTML = SOURCE_OPTIONS.map((item) => {
        const active = selectedSources.has(item.value);
        return `
            <button class="choice-option source-option ${active ? "active" : ""}" type="button" onclick="toggleSource('${escapeAttribute(item.value)}')">
                <span class="source-logo" style="--source-tone:${escapeAttribute(item.tone)}">${escapeHtml(item.icon)}</span>
                <span>
                    <strong>${escapeHtml(item.label)}</strong>
                    <small>${escapeHtml(item.hint)}</small>
                </span>
                <span class="interest-check" aria-hidden="true"></span>
            </button>
        `;
    }).join("");

    syncSourceCount();
    refreshIcons();
}

function hydrateInterests(values) {
    selectedInterests = new Set(values.filter(Boolean));
    renderInterestPicker();
}

function toggleInterest(value) {
    if (selectedInterests.has(value)) {
        selectedInterests.delete(value);
    } else {
        selectedInterests.add(value);
    }
    renderInterestPicker();
}

function toggleSource(value) {
    if (selectedSources.has(value)) {
        selectedSources.delete(value);
    } else {
        selectedSources.add(value);
    }
    renderSourcePicker();
}

function addCustomInterest() {
    const input = document.getElementById("custom-interest");
    const values = splitInterests(input?.value || "");
    values.forEach((value) => selectedInterests.add(value));
    if (input) {
        input.value = "";
    }
    renderInterestPicker();
}

function currentThreshold() {
    return Math.max(1, Math.min(10, parseInt(document.getElementById("settings-threshold")?.value || "6", 10) || 6));
}

function setAuthMode(mode) {
    authMode = mode === "register" ? "register" : "login";

    document.getElementById("auth-login-tab")?.classList.toggle("active", authMode === "login");
    document.getElementById("auth-register-tab")?.classList.toggle("active", authMode === "register");

    const loginForm = document.getElementById("login-form");
    const registerForm = document.getElementById("register-form");
    if (loginForm) {
        loginForm.hidden = authMode !== "login";
    }
    if (registerForm) {
        registerForm.hidden = authMode !== "register";
    }
}

function renderAccountState() {
    const authState = document.getElementById("account-auth-state");
    const profileState = document.getElementById("account-profile-state");
    const title = document.getElementById("account-title");
    const subtitle = document.getElementById("account-subtitle");

    const loggedIn = Boolean(currentUser && authToken);
    if (authState) {
        authState.hidden = loggedIn;
    }
    if (profileState) {
        profileState.hidden = !loggedIn;
    }

    if (title) {
        title.textContent = loggedIn ? "Профиль" : "Вход";
    }
    if (subtitle) {
        subtitle.textContent = loggedIn
            ? "Ваши интересы, порог важности и персональная новостная лента."
            : "Одна форма: выберите вход или регистрацию.";
    }

    if (!loggedIn) {
        setAuthMode(authMode);
    }
    renderUserCard();
    refreshIcons();
}

function getRegisterPayload() {
    return {
        login: document.getElementById("register-login").value.trim(),
        email: document.getElementById("register-email").value.trim(),
        password: document.getElementById("register-password").value,
        interests: [...selectedInterests],
        threshold: currentThreshold(),
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
        interests: [...selectedInterests],
        threshold: currentThreshold(),
    };
}

function getAuthHeaders() {
    return authToken ? { Authorization: `Bearer ${authToken}` } : {};
}

async function ensureAuthorized() {
    if (authToken && currentUser) {
        return true;
    }

    if (authToken && !currentUser) {
        const restored = await restoreSession({ silent: true });
        if (restored && currentUser) {
            return true;
        }
    }

    showStatus("Нужен вход в аккаунт.", "error");
    switchView("account");
    return false;
}

function setSessionState(message, isActive) {
    const stateNode = document.getElementById("session-state");
    if (!stateNode) {
        return;
    }
    stateNode.textContent = message;
    stateNode.className = isActive ? "session-pill active" : "session-pill";
}

function applyUserToUI(user) {
    currentUser = user;
    document.getElementById("settings-threshold").value = user.news_threshold || 6;
    document.getElementById("threshold-value").textContent = user.news_threshold || 6;
    hydrateInterests(user.interests || []);
    renderUserCard();
    renderAccountState();
    setSessionState(user.login ? `Вход: ${user.login}` : "Выполнен вход", true);
}

function renderUserCard() {
    const container = document.getElementById("user-info");
    if (!container) {
        return;
    }

    if (!currentUser) {
        container.className = "user-summary empty";
        container.textContent = "";
        return;
    }

    container.className = "user-summary";
    container.innerHTML = `
        <div class="user-grid">
            <div><span>Логин</span><strong>${escapeHtml(currentUser.login || "-")}</strong></div>
            <div><span>Email</span><strong>${escapeHtml(currentUser.email || "-")}</strong></div>
            <div><span>Интересы</span><strong>${escapeHtml((currentUser.interests || []).join(", ") || "-")}</strong></div>
            <div><span>Порог важности</span><strong>${escapeHtml(String(currentUser.news_threshold || 6))}/10</strong></div>
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
    const loginPassword = document.getElementById("login-password");
    const registerPassword = document.getElementById("register-password");
    if (loginPassword) {
        loginPassword.value = "";
    }
    if (registerPassword) {
        registerPassword.value = "";
    }
    renderUserCard();
    renderAccountState();
    setSessionState("Не выполнен вход", false);
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
        showStatus("Для регистрации нужен логин и пароль.", "error");
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
        showStatus("Аккаунт создан. Вход выполнен.", "ok");
        switchView("account");
    } catch (error) {
        showStatus(error.message, "error");
    }
}

async function loginUser() {
    const payload = getLoginPayload();
    if (!payload.login || !payload.password) {
        showStatus("Укажите логин или email и пароль.", "error");
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
        showStatus("Вход выполнен.", "ok");
        switchView("account");
    } catch (error) {
        showStatus(error.message, "error");
    }
}

async function logoutUser() {
    clearSession();
    showStatus("Вы вышли из аккаунта.", "ok");
    switchView("account");
}

async function fetchNews() {
    if (!(await ensureAuthorized())) {
        return;
    }

    showStatus("Обновляю ленту.", "ok");
    try {
        const response = await fetch(`${API_BASE}/news/fetch`, {
            method: "POST",
            headers: {
                "Content-Type": "application/json",
                ...getAuthHeaders(),
            },
            body: JSON.stringify({ threshold: currentThreshold() }),
        });
        const data = await handleApiResponse(response);
        renderNews(data.news, document.getElementById("news-list"));
        showStatus(`Получено ${data.count} персональных новостей от ${data.threshold || currentThreshold()}/10.`, "ok");
    } catch (error) {
        showStatus(error.message, "error");
    }
}

function renderNews(newsList, container = document.getElementById("news-list")) {
    if (!container) {
        return;
    }

    const threshold = currentThreshold();
    const visibleNews = (newsList || []).filter((news) => {
        const score = parseInt(news.importance_score, 10) || 0;
        return score >= threshold;
    });

    if (visibleNews.length === 0) {
        container.className = "news-stream empty-state";
        container.textContent = `По выбранным интересам пока нет новостей с важностью от ${threshold}/10. Попробуйте снизить порог или добавить больше интересов.`;
        return;
    }

    container.className = "news-stream";
    container.innerHTML = visibleNews.map(newsRow).join("");
    initReveal();
    refreshIcons();
}

function newsRow(news) {
    const published = news.published_at
        ? new Date(news.published_at).toLocaleString("ru-RU")
        : "Дата неизвестна";
    const score = Math.max(1, Math.min(10, parseInt(news.importance_score, 10) || 6));
    const sourceUrl = news.url ? `
        <a href="${escapeAttribute(news.url)}" target="_blank" rel="noopener noreferrer" class="source-link">
            <span>Источник</span>${icon("arrow-up-right")}
        </a>
    ` : "";

    return `
        <article class="news-row" data-reveal>
            <div>
                <h3>${escapeHtml(news.title || "Без заголовка")}</h3>
                <p class="news-summary">${escapeHtml(news.summary || "")}</p>
                <div class="news-meta">
                    <span>${escapeHtml(news.source || "Источник не указан")}</span>
                    <span>${escapeHtml(news.category || "Общее")}</span>
                    <span>${published}</span>
                    ${sourceUrl}
                </div>
            </div>
            <div class="score-ring">${score}</div>
        </article>
    `;
}

async function getDigest() {
    if (!(await ensureAuthorized())) {
        return;
    }

    showStatus("Собираю сводку.", "ok");
    try {
        const response = await fetch(`${API_BASE}/users/me/digest?threshold=${encodeURIComponent(currentThreshold())}`, {
            method: "GET",
            headers: getAuthHeaders(),
        });
        const data = await handleApiResponse(response);
        const digestNode = document.getElementById("digest-content");
        digestNode.className = "digest-sheet";
        digestNode.textContent = data.digest || "Сводка пока пустая.";
        digestNode.classList.add("visible");
        showStatus(`Сводка готова. Использовано новостей: ${data.news_count}, порог ${data.threshold || currentThreshold()}/10.`, "ok");
    } catch (error) {
        showStatus(error.message, "error");
    }
}

async function saveSettings() {
    if (!(await ensureAuthorized())) {
        return;
    }

    const payload = getSettingsPayload();
    if (!payload.interests.length) {
        showStatus("Выберите хотя бы один интерес.", "error");
        return;
    }

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
        showStatus("Интересы сохранены.", "ok");
    } catch (error) {
        showStatus(error.message, "error");
    }
}

function renderAiNews(newsList, { topic, saved, model, threshold, foundTotal } = {}) {
    const container = document.getElementById("ai-news-list");
    if (!container) {
        return;
    }

    const effectiveThreshold = threshold || currentThreshold();
    const visibleNews = (newsList || []).filter((news) => {
        const score = parseInt(news.importance_score, 10) || 0;
        return score >= effectiveThreshold;
    });

    if (visibleNews.length === 0) {
        const thresholdText = ` с важностью ${effectiveThreshold}/10`;
        const foundText = Number.isFinite(Number(foundTotal)) ? ` Найдено до фильтра: ${foundTotal}.` : "";
        container.innerHTML = `<div class="empty-state">По теме «${escapeHtml(topic || "новости")}» нет новостей${thresholdText}.${foundText} Попробуйте снизить важность или расширить источники.</div>`;
        return;
    }

    const headerHtml = `
        <div class="ai-results-head" data-reveal>
            <strong>${visibleNews.length} новостей</strong>
            <span>порог ${effectiveThreshold}/10</span>
            <span>${saved || 0} сохранено в базе</span>
            <span>${escapeHtml(model || "AI")}</span>
        </div>
    `;

    container.innerHTML = headerHtml + visibleNews.map(newsRow).join("");
    initReveal();
    refreshIcons();
}

async function fetchAiNews() {
    const topicInput = document.getElementById("ai-news-topic");
    const topic = (topicInput?.value || "").trim();
    const button = document.getElementById("ai-news-btn");
    const statusEl = document.getElementById("ai-news-status");

    statusEl.hidden = false;
    statusEl.className = "inline-status";
    statusEl.textContent = topic ? `Ищу новости по теме «${topic}».` : "Ищу новости дня.";
    document.getElementById("ai-news-list").innerHTML = "";

    if (button) {
        button.disabled = true;
    }

    try {
        const response = await fetch(`${API_BASE}/ai-news`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
                topic: topic || "новости",
                sources: [...selectedSources],
                threshold: currentThreshold(),
            }),
        });
        const data = await handleApiResponse(response);

        statusEl.className = "inline-status ok";
        statusEl.textContent = data.total > 0
            ? `Готово: ${data.total} новостей с важностью от ${data.threshold || currentThreshold()}/10.`
            : `Нет новостей с важностью от ${data.threshold || currentThreshold()}/10.`;
        renderAiNews(data.news, {
            topic: data.topic,
            saved: data.saved,
            model: data.model,
            threshold: data.threshold,
            foundTotal: data.found_total,
        });
        showStatus(data.total > 0 ? `Найдено ${data.total} новостей.` : "Под текущий порог важности новости не прошли.", data.total > 0 ? "ok" : "error");
    } catch (error) {
        const readableError = getReadableError(error);
        statusEl.className = "inline-status error";
        statusEl.textContent = readableError;
        showStatus(readableError, "error");
    } finally {
        if (button) {
            button.disabled = false;
        }
    }
}

function escapeHtml(text) {
    const div = document.createElement("div");
    div.textContent = text ?? "";
    return div.innerHTML;
}

function escapeAttribute(text) {
    return String(text ?? "")
        .replace(/&/g, "&amp;")
        .replace(/"/g, "&quot;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;");
}

function showStatus(message, type = "") {
    const statusEl = document.getElementById("status");
    if (!statusEl) {
        return;
    }

    window.clearTimeout(statusTimer);
    statusEl.textContent = message;
    statusEl.className = `toast visible ${type}`;
    statusTimer = window.setTimeout(() => {
        statusEl.className = "toast";
    }, 3600);
}

async function restoreSession(options = {}) {
    renderUserCard();
    setSessionState("Не выполнен вход", false);

    if (!authToken) {
        renderAccountState();
        return false;
    }

    try {
        const response = await fetch(`${API_BASE}/auth/me`, {
            method: "GET",
            headers: getAuthHeaders(),
        });
        const data = await handleApiResponse(response);
        applyUserToUI(data.user);
        return true;
    } catch {
        clearSession();
        if (!options.silent) {
            showStatus("Сессия истекла. Выполните вход снова.", "error");
        }
        return false;
    }
}

function initReveal() {
    const nodes = document.querySelectorAll("[data-reveal]:not(.visible)");
    if (!("IntersectionObserver" in window)) {
        nodes.forEach((node) => node.classList.add("visible"));
        return;
    }

    const observer = new IntersectionObserver((entries) => {
        entries.forEach((entry) => {
            if (entry.isIntersecting) {
                entry.target.classList.add("visible");
                observer.unobserve(entry.target);
            }
        });
    }, { threshold: 0.12 });

    nodes.forEach((node) => observer.observe(node));
}

function boot() {
    document.body.classList.add("ready");
    renderInterestPicker();
    renderSourcePicker();
    setAuthMode("login");
    renderAccountState();
    refreshIcons();
    initReveal();
    restoreSession();

    const initialView = window.location.hash.replace("#", "");
    if (["search", "feed", "digest", "account"].includes(initialView)) {
        history.replaceState(null, "", window.location.pathname + window.location.search);
        switchView(initialView);
        window.setTimeout(() => window.scrollTo({ top: 0, behavior: "auto" }), 80);
    }

    document.getElementById("settings-threshold")?.addEventListener("input", function updateThreshold() {
        document.getElementById("threshold-value").textContent = this.value;
    });

    document.getElementById("custom-interest")?.addEventListener("keydown", (event) => {
        if (event.key === "Enter") {
            event.preventDefault();
            addCustomInterest();
        }
    });

    document.addEventListener("keydown", (event) => {
        if (event.key === "Escape") {
            closeMenu();
        }
    });

    document.addEventListener("click", (event) => {
        if (!document.body.classList.contains("menu-open")) {
            return;
        }

        const target = event.target;
        if (target.closest(".menu-panel") || target.closest(".menu-trigger")) {
            return;
        }

        closeMenu();
    });
}

document.addEventListener("DOMContentLoaded", boot);
