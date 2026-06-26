let currentUser = null;
let authMode = "login";
let accountPanelOpen = false;
let forgotResetEmail = "";
let googleAuthEnabled = false;
const FORGOT_EMAIL_KEY = "rackforge_forgot_email";

function forgotLoginEmail() {
  return forgotResetEmail || sessionStorage.getItem(FORGOT_EMAIL_KEY) || "";
}

function setForgotLoginEmail(value) {
  forgotResetEmail = value;
  if (value) sessionStorage.setItem(FORGOT_EMAIL_KEY, value);
  else sessionStorage.removeItem(FORGOT_EMAIL_KEY);
}

function normalizeResetCode(raw) {
  return String(raw || "").replace(/\D/g, "");
}

function isLoggedIn() {
  return currentUser !== null;
}

function apiFetch(url, options = {}) {
  const headers = { "Content-Type": "application/json", ...(options.headers || {}) };
  return fetch(url, { credentials: "include", ...options, headers });
}

function setAccountPanelOpen(open) {
  accountPanelOpen = open;
  const panel = document.getElementById("account-panel");
  const trigger = document.getElementById("btn-account");
  if (!panel || !trigger) return;
  panel.hidden = !open;
  trigger.setAttribute("aria-expanded", String(open));
  if (open) {
    void updateAllAvatars(currentUser);
    document.addEventListener("click", onAccountOutsideClick);
    document.addEventListener("keydown", onAccountEscape);
  } else {
    document.removeEventListener("click", onAccountOutsideClick);
    document.removeEventListener("keydown", onAccountEscape);
  }
}

function onAccountOutsideClick(e) {
  const menu = document.getElementById("auth-user");
  if (menu && !menu.contains(e.target)) setAccountPanelOpen(false);
}

function onAccountEscape(e) {
  if (e.key === "Escape") setAccountPanelOpen(false);
}

function usernameInitials(username) {
  if (!username) return "?";
  const parts = username.split(/[_-]+/).filter(Boolean);
  if (parts.length >= 2) {
    return `${parts[0][0] || ""}${parts[1][0] || ""}`.toUpperCase();
  }
  return username.slice(0, 2).toUpperCase();
}

const avatarBlobCache = new Map();

function pruneAvatarBlobCache(keepUrl = null) {
  for (const [key, blobUrl] of avatarBlobCache.entries()) {
    if (key !== keepUrl) {
      URL.revokeObjectURL(blobUrl);
      avatarBlobCache.delete(key);
    }
  }
}

async function resolveAvatarDisplaySrc(url) {
  if (!url) return null;
  if (url.startsWith("data:") || url.startsWith("blob:")) return url;
  if (avatarBlobCache.has(url)) return avatarBlobCache.get(url);
  try {
    const res = await fetch(new URL(url, location.origin).href, { credentials: "include" });
    if (!res.ok) return null;
    const blob = await res.blob();
    const blobUrl = URL.createObjectURL(blob);
    avatarBlobCache.set(url, blobUrl);
    return blobUrl;
  } catch {
    return null;
  }
}

function paintAvatarFace(faceEl, user, displaySrc) {
  if (!faceEl) return;
  const hasPhoto = !!displaySrc;
  faceEl.classList.toggle("account-avatar--photo", hasPhoto);
  if (hasPhoto) {
    faceEl.textContent = "";
    let img = faceEl.querySelector("img");
    if (!img) {
      img = document.createElement("img");
      img.alt = "";
      img.decoding = "async";
      faceEl.appendChild(img);
    }
    if (img.src !== displaySrc) img.src = displaySrc;
    return;
  }
  faceEl.querySelectorAll("img").forEach((img) => img.remove());
  faceEl.textContent = usernameInitials(user?.username);
}

async function renderAvatarElement(el, user, url) {
  if (!el) return;
  const avatarUrl = url ?? user?.avatarUrl ?? null;
  if (!avatarUrl) {
    paintAvatarFace(el, user, null);
    return;
  }
  if (avatarUrl.startsWith("data:")) {
    paintAvatarFace(el, user, avatarUrl);
    return;
  }
  const displaySrc = await resolveAvatarDisplaySrc(avatarUrl);
  paintAvatarFace(el, user, displaySrc);
}

async function updateAllAvatars(user, previewUrl = null) {
  const url = previewUrl ?? user?.avatarUrl ?? null;
  await Promise.all([
    renderAvatarElement(document.getElementById("account-avatar"), user, url),
    renderAvatarElement(document.getElementById("account-panel-avatar-face"), user, url),
  ]);
}



function updateAuthUI() {
  const user = document.getElementById("auth-user");
  const nameEl = document.getElementById("auth-user-name");
  const menuLabel = document.getElementById("account-menu-label");
  if (!user) return;
  user.hidden = !currentUser;
  if (!currentUser) setAccountPanelOpen(false);

  void updateAllAvatars(currentUser);

  if (nameEl && currentUser?.username) {
    nameEl.textContent = currentUser.username;
  } else if (nameEl) {
    nameEl.textContent = "";
  }

  if (menuLabel) {
    menuLabel.textContent = currentUser?.username || I18n.t("account.label");
  }
}

function isLoginRoute() {
  return window.Routes?.isLoginPage?.() || document.body?.dataset?.page === "login";
}

function isAppRoute() {
  return window.Routes?.isAppPage?.() || document.body?.dataset?.page === "main";
}

function goToLogin() {
  const target = window.Routes?.loginUrl?.() || "/login";
  if (location.pathname + location.search !== target) {
    location.replace(target);
  }
}

function goToApp() {
  const target = window.Routes?.appUrl?.() || "/main";
  if (location.pathname + location.search !== target) {
    location.replace(target);
  }
}

function setAppAccess(allowed) {
  if (isLoginRoute()) {
    if (allowed) {
      goToApp();
      return;
    }
    setForgotLoginEmail("");
    const reopenMode = authMode === "register" ? "register" : "login";
    setAuthMode(reopenMode);
    document.getElementById("auth-error").hidden = true;
    document.getElementById("auth-verify-notice").hidden = true;
    document.getElementById("auth-email")?.focus();
    return;
  }

  if (isAppRoute()) {
    if (!allowed) {
      goToLogin();
      return;
    }
    document.dispatchEvent(new CustomEvent("appready"));
    return;
  }

  const shell = document.getElementById("app-shell");
  const modal = document.getElementById("auth-modal");
  if (!modal && !allowed) {
    goToLogin();
    return;
  }
  document.body.classList.toggle("app-locked", !allowed);
  if (shell) shell.hidden = !allowed;
  if (modal) modal.hidden = allowed;
  if (!allowed) {
    setForgotLoginEmail("");
    const reopenMode = authMode === "register" ? "register" : "login";
    setAuthMode(reopenMode);
    document.getElementById("auth-error").hidden = true;
    document.getElementById("auth-verify-notice").hidden = true;
    document.getElementById("auth-email")?.focus();
  }
  if (allowed) {
    document.dispatchEvent(new CustomEvent("appready"));
  }
}

function updateGoogleAuthUI() {
  const btn = document.getElementById("auth-google-btn");
  const divider = document.getElementById("auth-google-divider");
  const show = googleAuthEnabled && (authMode === "login" || authMode === "register");
  if (btn) {
    btn.hidden = !show;
    if (show) {
      btn.href = `/api/auth/google?lang=${encodeURIComponent(I18n.getLang())}`;
    }
  }
  if (divider) divider.hidden = !show;
}

function setAuthEmailField(mode) {
  const label = document.getElementById("auth-email-label");
  const input = document.getElementById("auth-email");
  if (!label || !input) return;

  if (mode === "register") {
    label.textContent = I18n.t("auth.email");
    input.placeholder = "";
    input.removeAttribute("placeholder");
    return;
  }

  label.textContent = I18n.t("auth.loginOrEmail");
  input.placeholder = I18n.t("auth.loginOrEmailPlaceholder");
}

function setAuthMode(mode) {
  authMode = mode;
  const title = document.getElementById("auth-title");
  const subtitle = document.querySelector(".auth-gate__subtitle");
  const submit = document.getElementById("auth-submit");
  const switchText = document.getElementById("auth-switch-text");
  const toggle = document.getElementById("auth-toggle-mode");
  const password = document.getElementById("auth-password");
  const passwordWrap = document.getElementById("auth-password-wrap");
  const forgotWrap = document.getElementById("auth-forgot-wrap");
  const emailInput = document.getElementById("auth-email");
  const emailWrap = document.getElementById("auth-email-wrap");
  const codeWrap = document.getElementById("auth-reset-code-wrap");
  const codeInput = document.getElementById("auth-reset-code");
  const form = document.getElementById("auth-form");
  const usernameInput = document.getElementById("auth-username");
  const verifyNotice = document.getElementById("auth-verify-notice");
  if (!title || !submit) return;

  if (verifyNotice) verifyNotice.hidden = true;
  form?.classList.remove("auth-form--register", "auth-form--forgot", "auth-form--forgot-code");

  if (mode === "register") {
    title.textContent = I18n.t("auth.registerTitle");
    if (subtitle) subtitle.textContent = I18n.t("auth.subtitle");
    submit.textContent = I18n.t("auth.register");
    if (switchText) switchText.textContent = I18n.t("auth.hasAccount");
    if (toggle) toggle.textContent = I18n.t("auth.login");
    form?.setAttribute("autocomplete", "off");
    if (password) {
      password.autocomplete = "new-password";
      password.required = true;
      password.value = "";
    }
    if (passwordWrap) passwordWrap.hidden = false;
    if (forgotWrap) forgotWrap.hidden = true;
    if (emailWrap) emailWrap.hidden = false;
    if (codeWrap) codeWrap.hidden = true;
    if (emailInput) {
      emailInput.readOnly = false;
      emailInput.type = "email";
      emailInput.autocomplete = "off";
      emailInput.value = "";
    }
    if (codeInput) {
      codeInput.required = false;
      codeInput.value = "";
    }
    form?.classList.add("auth-form--register");
    if (usernameInput) {
      usernameInput.required = true;
      usernameInput.autocomplete = "off";
      usernameInput.value = "";
    }
    setAuthEmailField("register");
  } else if (mode === "forgot") {
    form?.removeAttribute("autocomplete");
    form?.classList.add("auth-form--forgot");
    title.textContent = I18n.t("auth.forgotTitle");
    if (subtitle) subtitle.textContent = I18n.t("auth.forgotSubtitle");
    submit.textContent = I18n.t("auth.forgotSubmit");
    if (switchText) switchText.textContent = "";
    if (toggle) toggle.textContent = I18n.t("auth.backToLogin");
    if (password) {
      password.required = false;
      password.value = "";
    }
    if (passwordWrap) passwordWrap.hidden = true;
    if (forgotWrap) forgotWrap.hidden = true;
    if (emailWrap) emailWrap.hidden = false;
    if (codeWrap) codeWrap.hidden = true;
    if (emailInput) {
      emailInput.readOnly = false;
      emailInput.type = "text";
      emailInput.autocomplete = "username";
    }
    if (codeInput) {
      codeInput.required = false;
      codeInput.value = "";
    }
    if (usernameInput) {
      usernameInput.required = false;
      usernameInput.value = "";
    }
    setAuthEmailField("forgot");
  } else if (mode === "forgot-code") {
    form?.removeAttribute("autocomplete");
    form?.classList.add("auth-form--forgot-code");
    title.textContent = I18n.t("auth.resetCodeTitle");
    if (subtitle) subtitle.textContent = I18n.t("auth.resetCodeSubtitle");
    submit.textContent = I18n.t("auth.resetCodeSubmit");
    if (switchText) switchText.textContent = "";
    if (toggle) toggle.textContent = I18n.t("auth.backToLogin");
    if (password) {
      password.required = false;
      password.value = "";
    }
    if (passwordWrap) passwordWrap.hidden = true;
    if (forgotWrap) forgotWrap.hidden = true;
    if (emailWrap) emailWrap.hidden = false;
    if (codeWrap) codeWrap.hidden = false;
    if (emailInput) {
      emailInput.readOnly = true;
      const savedEmail = forgotLoginEmail();
      if (savedEmail) emailInput.value = savedEmail;
    }
    if (codeInput) codeInput.required = true;
    if (usernameInput) {
      usernameInput.required = false;
      usernameInput.value = "";
    }
    setAuthEmailField("forgot-code");
  } else {
    title.textContent = I18n.t("auth.loginTitle");
    if (subtitle) subtitle.textContent = I18n.t("auth.subtitle");
    submit.textContent = I18n.t("auth.login");
    if (switchText) switchText.textContent = I18n.t("auth.noAccount");
    if (toggle) toggle.textContent = I18n.t("auth.register");
    form?.removeAttribute("autocomplete");
    if (password) {
      password.autocomplete = "current-password";
      password.required = true;
    }
    if (passwordWrap) passwordWrap.hidden = false;
    if (forgotWrap) forgotWrap.hidden = false;
    if (emailWrap) emailWrap.hidden = false;
    if (codeWrap) codeWrap.hidden = true;
    if (emailInput) {
      emailInput.readOnly = false;
      emailInput.type = "text";
      emailInput.autocomplete = "username";
    }
    if (codeInput) {
      codeInput.required = false;
      codeInput.value = "";
    }
    setForgotLoginEmail("");
    if (usernameInput) {
      usernameInput.required = false;
      usernameInput.value = "";
      usernameInput.autocomplete = "off";
    }
    setAuthEmailField("login");
  }
  updateGoogleAuthUI();
}

async function checkAuth() {
  try {
    const res = await apiFetch("/api/auth/me");
    if (res.ok) {
      const data = await res.json();
      currentUser = data.user;
    } else {
      currentUser = null;
    }
  } catch {
    currentUser = null;
  }
  if (currentUser?.lang && I18n.getLang() !== currentUser.lang) {
    I18n.setLang(currentUser.lang);
  }
  updateAuthUI();
  setAppAccess(!!currentUser);
  return currentUser;
}

async function syncLangToServer() {
  if (!isLoggedIn()) return;
  const res = await apiFetch("/api/me/lang", {
    method: "PUT",
    body: JSON.stringify({ lang: I18n.getLang() }),
  });
  if (res.ok) {
    const data = await res.json();
    if (data.user) {
      currentUser = data.user;
      updateAuthUI();
    }
  }
}

async function login(email, password) {
  const res = await apiFetch("/api/auth/login", {
    method: "POST",
    body: JSON.stringify({ email, password, lang: I18n.getLang() }),
  });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) {
    const key = res.status === 401 ? "auth.errors.invalid" : "auth.errors.generic";
    throw new Error(I18n.t(key));
  }
  currentUser = data.user;
  updateAuthUI();
  setAppAccess(true);
  document.dispatchEvent(new CustomEvent("authchange", { detail: { user: currentUser } }));
  return currentUser;
}

async function register(email, password, username) {
  const res = await apiFetch("/api/auth/register", {
    method: "POST",
    body: JSON.stringify({ email, password, username, lang: I18n.getLang() }),
  });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) {
    if (res.status === 409 && data.error?.includes("Username")) {
      throw new Error(I18n.t("auth.errors.usernameTaken"));
    }
    if (res.status === 409) throw new Error(I18n.t("auth.errors.emailTaken"));
    if (res.status === 400 && data.error?.includes("username")) {
      throw new Error(I18n.t("auth.errors.usernameInvalid"));
    }
    if (res.status === 400 && data.error?.includes("8")) throw new Error(I18n.t("auth.errors.password"));
    throw new Error(I18n.t("auth.errors.generic"));
  }
  currentUser = data.user;
  updateAuthUI();
  setAppAccess(true);
  document.dispatchEvent(new CustomEvent("authchange", { detail: { user: currentUser } }));
  showAuthNotice(I18n.t("auth.verificationSent", { email }));
  return currentUser;
}

async function verifyEmailToken(token) {
  const res = await apiFetch(`/api/auth/verify-email?token=${encodeURIComponent(token)}`);
  const data = await res.json().catch(() => ({}));
  if (!res.ok) {
    if (res.status === 409) throw new Error(I18n.t("auth.errors.emailTaken"));
    if (res.status === 400) throw new Error(I18n.t("auth.errors.verifyInvalid"));
    throw new Error(I18n.t("auth.errors.verifyFailed"));
  }
  if (data.user && currentUser?.id === data.user.id) {
    currentUser = data.user;
    updateAuthUI();
    document.dispatchEvent(new CustomEvent("authchange", { detail: { user: currentUser } }));
  }
  return data;
}

async function requestPasswordReset(email) {
  const res = await apiFetch("/api/auth/forgot-password", {
    method: "POST",
    body: JSON.stringify({ email, lang: I18n.getLang() }),
  });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) {
    if (res.status === 404 && data.error === "Email not registered") {
      throw new Error(I18n.t("auth.errors.emailNotFound"));
    }
    if (res.status === 400) throw new Error(I18n.t("auth.errors.invalidEmail"));
    if (res.status === 503) throw new Error(I18n.t("auth.errors.resetEmailFailed"));
    throw new Error(I18n.t("auth.errors.generic"));
  }
  return data;
}

async function verifyResetCode(email, code) {
  const res = await apiFetch("/api/auth/verify-reset-code", {
    method: "POST",
    body: JSON.stringify({ email, code }),
  });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) {
    if (res.status === 400) {
      const err = data.error || "";
      if (err === "Invalid email") throw new Error(I18n.t("auth.errors.emailNotFound"));
      if (err === "Invalid reset code") throw new Error(I18n.t("auth.errors.resetCodeFormat"));
      throw new Error(I18n.t("auth.errors.resetCodeInvalid"));
    }
    throw new Error(I18n.t("auth.errors.generic"));
  }
  return data;
}

async function resendVerification() {
  const res = await apiFetch("/api/auth/resend-verification", {
    method: "POST",
    body: JSON.stringify({ lang: I18n.getLang() }),
  });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) {
    if (res.status === 503) throw new Error(I18n.t("settings.errors.emailSendFailed"));
    if (res.status === 400) throw new Error(I18n.t("settings.errors.nothingToVerify"));
    throw new Error(I18n.t("settings.errors.generic"));
  }
  return data.email;
}

function showAuthNotice(message) {
  const errEl = document.getElementById("auth-error");
  const okEl = document.getElementById("auth-verify-notice");
  if (errEl) errEl.hidden = true;
  if (okEl) {
    okEl.textContent = message;
    okEl.hidden = false;
  }
}

async function uploadAvatarImage(image) {
  await updateAllAvatars(currentUser, image);
  const res = await apiFetch("/api/me/avatar", {
    method: "PUT",
    body: JSON.stringify({ image }),
  });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) {
    await updateAllAvatars(currentUser);
    if (res.status === 400) throw new Error(I18n.t("settings.errors.invalidImage"));
    throw new Error(I18n.t("settings.errors.generic"));
  }
  pruneAvatarBlobCache(data.user?.avatarUrl || null);
  currentUser = data.user;
  updateAuthUI();
  document.dispatchEvent(new CustomEvent("authchange", { detail: { user: currentUser } }));
  return currentUser;
}

async function removeAvatar() {
  const res = await apiFetch("/api/me/avatar", { method: "DELETE" });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(I18n.t("settings.errors.generic"));
  pruneAvatarBlobCache();
  currentUser = data.user;
  updateAuthUI();
  document.dispatchEvent(new CustomEvent("authchange", { detail: { user: currentUser } }));
  return currentUser;
}

function openAvatarFilePicker() {
  const input = document.getElementById("avatar-file-input");
  if (!input) return;
  input.value = "";
  input.click();
}

async function handleAvatarFileSelected(file) {
  if (!file || !window.AvatarCrop) return;
  await AvatarCrop.open(file, {
    onComplete: async (image) => {
      await uploadAvatarImage(image);
      document.dispatchEvent(new CustomEvent("avatarsaved"));
    },
  });
}

function bindAvatarPicker() {
  const input = document.getElementById("avatar-file-input");
  input?.addEventListener("change", async (e) => {
    const file = e.target.files?.[0];
    if (!file) return;
    try {
      await handleAvatarFileSelected(file);
    } catch (err) {
      document.dispatchEvent(
        new CustomEvent("avatarerror", { detail: { message: err.message } })
      );
    }
  });

  const panelAvatarBtn = document.getElementById("account-panel-avatar");
  panelAvatarBtn?.addEventListener("click", (e) => {
    e.preventDefault();
    e.stopPropagation();
    openAvatarFilePicker();
  });
  panelAvatarBtn?.addEventListener("mousedown", (e) => {
    e.stopPropagation();
  });
}

async function updateAccount(email, password, newPassword = "") {
  const res = await apiFetch("/api/me/account", {
    method: "PUT",
    body: JSON.stringify({ email, password, newPassword, lang: I18n.getLang() }),
  });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) {
    if (res.status === 401) throw new Error(I18n.t("settings.errors.invalidPassword"));
    if (res.status === 409) throw new Error(I18n.t("auth.errors.emailTaken"));
    if (res.status === 400 && data.error?.includes("email")) {
      throw new Error(I18n.t("settings.errors.invalidEmail"));
    }
    if (res.status === 400 && data.error?.includes("8")) {
      throw new Error(I18n.t("settings.errors.passwordShort"));
    }
    if (res.status === 503) throw new Error(I18n.t("settings.errors.emailSendFailed"));
    throw new Error(I18n.t("settings.errors.generic"));
  }
  currentUser = data.user;
  updateAuthUI();
  document.dispatchEvent(new CustomEvent("authchange", { detail: { user: currentUser } }));
  return data;
}

async function logout() {
  setAccountPanelOpen(false);
  await apiFetch("/api/auth/logout", { method: "POST" }).catch(() => {});
  pruneAvatarBlobCache();
  currentUser = null;
  updateAuthUI();
  document.dispatchEvent(new CustomEvent("authchange", { detail: { user: null } }));
  goToLogin();
}

async function deleteAccount(password) {
  const res = await apiFetch("/api/me/account/delete", {
    method: "POST",
    body: JSON.stringify({ password }),
  });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) {
    const err = data.error || "";
    if (err === "Invalid password") {
      throw new Error(I18n.t("settings.errors.invalidPassword"));
    }
    if (res.status === 400 && err === "Password required") {
      throw new Error(I18n.t("settings.errors.invalidPassword"));
    }
    if (res.status === 401 && err === "Not authenticated") {
      throw new Error(I18n.t("auth.errors.generic"));
    }
    if (res.status === 404) throw new Error(I18n.t("settings.errors.deleteUnavailable"));
    throw new Error(I18n.t("settings.errors.deleteFailed"));
  }
  setAccountPanelOpen(false);
  pruneAvatarBlobCache();
  currentUser = null;
  updateAuthUI();
  document.dispatchEvent(new CustomEvent("authchange", { detail: { user: null } }));
  goToLogin();
  return data;
}

function bindLangSelects() {
  const gate = document.getElementById("lang-select-gate");
  const accountLang = document.getElementById("lang-select");
  if (!gate) return;

  gate.addEventListener("change", (e) => I18n.setLang(e.target.value));
  accountLang?.addEventListener("change", (e) => I18n.setLang(e.target.value));

  document.addEventListener("langchange", () => {
    gate.value = I18n.getLang();
    if (accountLang) accountLang.value = I18n.getLang();
    syncLangToServer().catch(() => {});
  });
}

function bindAccountMenu() {
  document.getElementById("btn-account")?.addEventListener("click", (e) => {
    e.stopPropagation();
    setAccountPanelOpen(!accountPanelOpen);
  });

  document.getElementById("btn-logout")?.addEventListener("click", () => {
    setAccountPanelOpen(false);
    logout();
  });
}

function bindAuthUI() {
  bindAccountMenu();
  bindAvatarPicker();

  document.getElementById("auth-toggle-mode")?.addEventListener("click", () => {
    if (authMode === "forgot" || authMode === "forgot-code") setAuthMode("login");
    else setAuthMode(authMode === "login" ? "register" : "login");
    document.getElementById("auth-error").hidden = true;
    document.getElementById("auth-verify-notice").hidden = true;
  });

  document.getElementById("auth-forgot-link")?.addEventListener("click", () => {
    setForgotLoginEmail("");
    setAuthMode("forgot");
    document.getElementById("auth-error").hidden = true;
    document.getElementById("auth-verify-notice").hidden = true;
    document.getElementById("auth-email")?.focus();
  });

  document.getElementById("auth-form")?.addEventListener("submit", async (e) => {
    e.preventDefault();
    const email = document.getElementById("auth-email").value.trim();
    const password = document.getElementById("auth-password").value;
    const username = document.getElementById("auth-username")?.value.trim() || "";
    const submit = document.getElementById("auth-submit");
    submit.disabled = true;
    document.getElementById("auth-error").hidden = true;
    document.getElementById("auth-verify-notice").hidden = true;
    try {
      if (authMode === "forgot") {
        const data = await requestPasswordReset(email);
        setForgotLoginEmail(data.email || email);
        const mailTarget = data.email || email;
        showAuthNotice(I18n.t("auth.forgotSent", { email: mailTarget }));
        setAuthMode("forgot-code");
        document.getElementById("auth-reset-code")?.focus();
      } else if (authMode === "forgot-code") {
        const code = normalizeResetCode(document.getElementById("auth-reset-code")?.value);
        const login = forgotLoginEmail() || email;
        const data = await verifyResetCode(login, code);
        setForgotLoginEmail("");
        location.href = `/reset-password?token=${encodeURIComponent(data.resetToken)}`;
      } else if (authMode === "register") {
        await register(email, password, username);
      } else {
        await login(email, password);
      }
    } catch (err) {
      const errEl = document.getElementById("auth-error");
      if (errEl) {
        errEl.textContent = err.message || I18n.t("auth.errors.generic");
        errEl.hidden = false;
      }
    } finally {
      submit.disabled = false;
    }
  });

  document.addEventListener("langchange", () => {
    setAuthMode(authMode);
    updateGoogleAuthUI();
  });
}

function handleVerifyEmailParam() {
  const params = new URLSearchParams(location.search);
  const token = params.get("verify-email");
  if (!token) return;
  location.replace(`/verify-email?token=${encodeURIComponent(token)}`);
}

function handleGoogleAuthParam() {
  const params = new URLSearchParams(location.search);
  const err = params.get("google_error");
  if (!err) return;
  const errEl = document.getElementById("auth-error");
  if (!errEl) return;
  let message = I18n.t("auth.errors.googleFailed");
  if (err === "access_denied") message = I18n.t("auth.errors.googleCancelled");
  else if (err === "unavailable") message = I18n.t("auth.errors.googleUnavailable");
  errEl.textContent = message;
  errEl.hidden = false;
  params.delete("google_error");
  const next = `${location.pathname}${params.toString() ? `?${params}` : ""}${location.hash}`;
  history.replaceState(null, "", next);
}

async function loadAuthProviders() {
  try {
    const res = await apiFetch("/api/auth/providers");
    if (res.ok) {
      const data = await res.json();
      googleAuthEnabled = !!data.google;
    }
  } catch {
    googleAuthEnabled = false;
  }
  updateGoogleAuthUI();
}

async function initAuth() {
  setAuthMode("login");
  bindAuthUI();
  bindLangSelects();
  handleGoogleAuthParam();
  await handleVerifyEmailParam();
  await loadAuthProviders();
  await checkAuth();
  document.dispatchEvent(new CustomEvent("authready"));
}

window.Auth = {
  isLoggedIn,
  checkAuth,
  login,
  register,
  logout,
  deleteAccount,
  updateAccount,
  uploadAvatarImage,
  removeAvatar,
  openAvatarFilePicker,
  renderAvatarElement,
  updateAllAvatars,
  verifyEmailToken,
  resendVerification,
  apiFetch,
  getUser: () => currentUser,
  setAccountPanelOpen,
};

document.addEventListener("DOMContentLoaded", initAuth);