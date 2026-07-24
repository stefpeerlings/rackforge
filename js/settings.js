const SETTINGS_KEY = "rackforge-settings";

const DEFAULT_SETTINGS = {
  autoCloudSync: true,
};

let settings = { ...DEFAULT_SETTINGS };

function isSettingsPage() {
  return document.body.dataset.page === "settings" || !!document.getElementById("settings-page");
}

function loadSettings() {
  try {
    const raw = localStorage.getItem(SETTINGS_KEY);
    if (!raw) return;
    const data = JSON.parse(raw);
    if (typeof data.autoCloudSync === "boolean") {
      settings.autoCloudSync = data.autoCloudSync;
    }
  } catch {
    /* ignore corrupt data */
  }
}

function persistSettings() {
  localStorage.setItem(SETTINGS_KEY, JSON.stringify(settings));
  document.dispatchEvent(new CustomEvent("settingschange", { detail: { ...settings } }));
}

function getSetting(key) {
  return settings[key];
}

function setSetting(key, value) {
  settings[key] = value;
  persistSettings();
}

function clearAccountFormMessages() {
  const err = document.getElementById("settings-account-error");
  const ok = document.getElementById("settings-account-success");
  if (err) err.hidden = true;
  if (ok) ok.hidden = true;
}

function updateEmailStatus(user) {
  const bar = document.getElementById("settings-email-status");
  const textEl = document.getElementById("settings-email-status-text");
  const resendBtn = document.getElementById("btn-resend-verify");
  if (!bar || !textEl) return;

  if (!user) {
    bar.hidden = true;
    return;
  }

  bar.hidden = false;
  bar.classList.remove("settings-verify--ok", "settings-verify--warn", "settings-verify--pending");

  if (user.pendingEmail) {
    bar.classList.add("settings-verify--pending");
    textEl.textContent = I18n.t("settings.pendingEmail", { email: user.pendingEmail });
    if (resendBtn) {
      resendBtn.hidden = false;
      resendBtn.disabled = false;
    }
    return;
  }

  if (user.emailVerified) {
    bar.classList.add("settings-verify--ok");
    textEl.textContent = I18n.t("settings.emailVerified");
    if (resendBtn) {
      resendBtn.hidden = true;
      resendBtn.disabled = true;
    }
    return;
  }

  bar.classList.add("settings-verify--warn");
  textEl.textContent = I18n.t("settings.emailUnverified");
  if (resendBtn) {
    resendBtn.hidden = false;
    resendBtn.disabled = false;
  }
}

function userHasPassword(user) {
  return user?.hasPassword === true;
}

const TIER_DISPLAY_NAMES = { community: "Community", pro: "Pro", enterprise: "Enterprise" };

function updateLicenseLine(user) {
  const el = document.getElementById("settings-license-line");
  if (!el) return;
  const license = user?.license;
  if (!license) {
    el.textContent = "—";
    return;
  }
  const tier = TIER_DISPLAY_NAMES[license.tier] || license.tier;
  el.textContent =
    license.maxRacks === null
      ? I18n.t("settings.licenseUnlimited", { tier })
      : I18n.t("settings.licenseLimited", { tier, limit: license.maxRacks });
}

function syncSettingsUI() {
  if (!isSettingsPage()) return;

  const usernameEl = document.getElementById("settings-username");
  const emailInput = document.getElementById("settings-email");
  const passwordInput = document.getElementById("settings-password");
  const passwordWrap = document.getElementById("settings-password-wrap");
  const passwordHint = document.getElementById("settings-password-hint");
  const newPasswordInput = document.getElementById("settings-new-password");
  const confirmPasswordInput = document.getElementById("settings-confirm-password");
  const langSelect = document.getElementById("lang-select");

  if (langSelect) langSelect.value = I18n.getLang();

  const user = window.Auth?.getUser();
  const hasPassword = userHasPassword(user);
  if (usernameEl) usernameEl.textContent = user?.username || "—";
  if (emailInput) emailInput.value = user?.email || "";
  if (passwordWrap) passwordWrap.hidden = !hasPassword;
  if (passwordInput) {
    passwordInput.required = hasPassword;
    passwordInput.value = "";
  }
  if (passwordHint) {
    passwordHint.textContent = hasPassword
      ? I18n.t("settings.passwordHint")
      : I18n.t("settings.googlePasswordHint");
  }
  if (newPasswordInput) newPasswordInput.value = "";
  if (confirmPasswordInput) confirmPasswordInput.value = "";
  updateEmailStatus(user);
  updateLicenseLine(user);
  clearAccountFormMessages();
  syncDeleteAccountModal();
}

async function resendVerificationFromSettings() {
  const errEl = document.getElementById("settings-account-error");
  const okEl = document.getElementById("settings-account-success");
  clearAccountFormMessages();
  try {
    const email = await Auth.resendVerification();
    if (okEl) {
      okEl.textContent = I18n.t("settings.verificationResent", { email });
      okEl.hidden = false;
    }
    updateEmailStatus(Auth.getUser());
  } catch (err) {
    if (errEl) {
      errEl.textContent = err.message || I18n.t("settings.errors.generic");
      errEl.hidden = false;
    }
  }
}

async function saveAccountSettings(e) {
  e.preventDefault();
  clearAccountFormMessages();

  const email = document.getElementById("settings-email")?.value.trim() || "";
  const password = document.getElementById("settings-password")?.value || "";
  const newPassword = document.getElementById("settings-new-password")?.value || "";
  const confirmPassword = document.getElementById("settings-confirm-password")?.value || "";
  const submit = document.getElementById("settings-account-save");
  const errEl = document.getElementById("settings-account-error");
  const okEl = document.getElementById("settings-account-success");
  const user = window.Auth?.getUser();

  if (!user) return;

  const hasPassword = userHasPassword(user);
  const emailChanged = email !== user.email;
  const passwordChanged = newPassword.length > 0 || confirmPassword.length > 0;

  if (!emailChanged && !passwordChanged) {
    if (errEl) {
      errEl.textContent = I18n.t("settings.errors.noChanges");
      errEl.hidden = false;
    }
    return;
  }

  if (hasPassword && passwordChanged && !password) {
    if (errEl) {
      errEl.textContent = I18n.t("settings.errors.invalidPassword");
      errEl.hidden = false;
    }
    return;
  }

  if (passwordChanged) {
    if (newPassword.length < 8) {
      if (errEl) {
        errEl.textContent = I18n.t("settings.errors.passwordShort");
        errEl.hidden = false;
      }
      return;
    }
    if (newPassword !== confirmPassword) {
      if (errEl) {
        errEl.textContent = I18n.t("settings.errors.passwordMismatch");
        errEl.hidden = false;
      }
      return;
    }
  }

  submit.disabled = true;
  try {
    const data = await Auth.updateAccount(email, password, passwordChanged ? newPassword : "");
    if (okEl) {
      let message = I18n.t("settings.accountSaved");
      if (data.verificationSent) {
        message = I18n.t("settings.verificationSent", {
          email: data.pendingEmail || email,
        });
      } else if (emailChanged && passwordChanged) {
        message = I18n.t("settings.accountSavedBoth");
      } else if (passwordChanged) {
        message = I18n.t("settings.passwordSaved");
      }
      okEl.textContent = message;
      okEl.hidden = false;
    }
    document.getElementById("settings-password").value = "";
    document.getElementById("settings-new-password").value = "";
    document.getElementById("settings-confirm-password").value = "";
    const emailField = document.getElementById("settings-email");
    if (emailField) emailField.value = Auth.getUser()?.email || email;
    updateEmailStatus(Auth.getUser());
  } catch (err) {
    if (errEl) {
      errEl.textContent = err.message || I18n.t("settings.errors.generic");
      errEl.hidden = false;
    }
  } finally {
    submit.disabled = false;
  }
}

function syncDeleteAccountModal() {
  const user = window.Auth?.getUser();
  const hasPassword = userHasPassword(user);
  const wrap = document.getElementById("delete-account-password-wrap");
  const hintEl = document.getElementById("delete-account-confirm-hint");
  const passwordInput = document.getElementById("delete-account-password");

  if (wrap) wrap.hidden = !hasPassword;
  if (passwordInput) {
    passwordInput.required = hasPassword;
    passwordInput.value = "";
  }
  if (hintEl) {
    hintEl.textContent = hasPassword
      ? I18n.t("settings.deleteAccountPasswordHint")
      : I18n.t("settings.deleteAccountGoogleHint");
  }
}

function setDeleteAccountModalOpen(open) {
  const modal = document.getElementById("delete-account-modal");
  const passwordInput = document.getElementById("delete-account-password");
  const errEl = document.getElementById("delete-account-error");
  if (!modal) return;
  modal.hidden = !open;
  if (errEl) errEl.hidden = true;
  if (open) {
    syncDeleteAccountModal();
    const user = window.Auth?.getUser();
    const hasPassword = userHasPassword(user);
    if (hasPassword && passwordInput) passwordInput.focus();
  } else if (passwordInput) {
    passwordInput.value = "";
  }
}

async function confirmDeleteAccount() {
  await Auth.checkAuth();
  const user = window.Auth?.getUser();
  const hasPassword = userHasPassword(user);
  const password = hasPassword
    ? document.getElementById("delete-account-password")?.value || ""
    : "";
  const confirmBtn = document.getElementById("delete-account-confirm");
  const errEl = document.getElementById("delete-account-error");
  if (hasPassword && !password) {
    if (errEl) {
      errEl.textContent = I18n.t("settings.errors.invalidPassword");
      errEl.hidden = false;
    }
    return;
  }

  if (errEl) errEl.hidden = true;
  if (confirmBtn) confirmBtn.disabled = true;
  try {
    await Auth.deleteAccount(password);
    setDeleteAccountModalOpen(false);
    location.href = window.Routes?.LOGIN || "/login";
  } catch (err) {
    if (errEl) {
      errEl.textContent = err.message || I18n.t("settings.errors.generic");
      errEl.hidden = false;
    }
  } finally {
    if (confirmBtn) confirmBtn.disabled = false;
  }
}

function bindDeleteAccountUI() {
  const openBtn = document.getElementById("btn-delete-account");
  const closeBtn = document.getElementById("delete-account-close");
  const cancelBtn = document.getElementById("delete-account-cancel");
  const confirmBtn = document.getElementById("delete-account-confirm");
  const backdrop = document.getElementById("delete-account-backdrop");
  const passwordInput = document.getElementById("delete-account-password");

  openBtn?.addEventListener("click", () => {
    void Auth.checkAuth().then(() => setDeleteAccountModalOpen(true));
  });
  closeBtn?.addEventListener("click", () => setDeleteAccountModalOpen(false));
  cancelBtn?.addEventListener("click", () => setDeleteAccountModalOpen(false));
  backdrop?.addEventListener("click", () => setDeleteAccountModalOpen(false));
  confirmBtn?.addEventListener("click", () => void confirmDeleteAccount());
  passwordInput?.addEventListener("keydown", (e) => {
    if (e.key === "Enter") {
      e.preventDefault();
      void confirmDeleteAccount();
    }
  });

  document.addEventListener("keydown", (e) => {
    const modal = document.getElementById("delete-account-modal");
    if (e.key === "Escape" && modal && !modal.hidden) setDeleteAccountModalOpen(false);
  });
}

function bindSettingsPageUI() {
  document.getElementById("settings-account-form")?.addEventListener("submit", saveAccountSettings);
  document.getElementById("btn-resend-verify")?.addEventListener("click", resendVerificationFromSettings);
  bindDeleteAccountUI();
}

function initSettings() {
  loadSettings();

  if (!isSettingsPage()) return;

  bindSettingsPageUI();
  document.addEventListener("authready", () => syncSettingsUI());
  document.addEventListener("authchange", () => syncSettingsUI());
  document.addEventListener("langchange", () => syncSettingsUI());
}

window.Settings = {
  get: getSetting,
  set: setSetting,
  open: () => {
    location.href = "/settings";
  },
  close: () => {
    if (isSettingsPage()) location.href = window.Routes?.APP || "/main";
  },
  isOpen: () => isSettingsPage(),
};

document.addEventListener("DOMContentLoaded", initSettings);