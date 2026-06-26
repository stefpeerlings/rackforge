let resetToken = null;

function showResetState(state, message = "") {
  const loading = document.getElementById("reset-loading");
  const formCard = document.getElementById("reset-form-card");
  const success = document.getElementById("reset-success");
  const errorCard = document.getElementById("reset-error-card");
  const errorText = document.getElementById("reset-error-text");

  if (loading) loading.hidden = state !== "loading";
  if (formCard) formCard.hidden = state !== "form";
  if (success) success.hidden = state !== "success";
  if (errorCard) errorCard.hidden = state !== "error";
  if (errorText && state === "error") errorText.textContent = message;
}

async function validateResetToken(token) {
  const res = await fetch(`/api/auth/reset-password?token=${encodeURIComponent(token)}`, {
    credentials: "include",
  });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) {
    if (res.status === 400) return I18n.t("reset.errors.invalid");
    return data.error || I18n.t("reset.errors.invalid");
  }
  return null;
}

async function submitNewPassword(password) {
  const res = await fetch("/api/auth/reset-password", {
    method: "POST",
    credentials: "include",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ token: resetToken, password }),
  });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) {
    if (res.status === 400 && String(data.error || "").includes("8")) {
      throw new Error(I18n.t("auth.errors.password"));
    }
    if (res.status === 400) throw new Error(I18n.t("reset.errors.invalid"));
    throw new Error(I18n.t("reset.errors.failed"));
  }
}

function bindResetForm() {
  const form = document.getElementById("reset-form");
  const errEl = document.getElementById("reset-error");
  const submit = document.getElementById("reset-submit");

  form?.addEventListener("submit", async (e) => {
    e.preventDefault();
    if (errEl) errEl.hidden = true;

    const password = document.getElementById("reset-password")?.value || "";
    const confirm = document.getElementById("reset-password-confirm")?.value || "";

    if (password.length < 8) {
      if (errEl) {
        errEl.textContent = I18n.t("auth.errors.password");
        errEl.hidden = false;
      }
      return;
    }
    if (password !== confirm) {
      if (errEl) {
        errEl.textContent = I18n.t("reset.errors.mismatch");
        errEl.hidden = false;
      }
      return;
    }

    if (submit) submit.disabled = true;
    try {
      await submitNewPassword(password);
      history.replaceState(null, "", "/reset-password");
      showResetState("success");
    } catch (err) {
      if (errEl) {
        errEl.textContent = err.message || I18n.t("reset.errors.failed");
        errEl.hidden = false;
      }
    } finally {
      if (submit) submit.disabled = false;
    }
  });
}

async function initResetPasswordPage() {
  const params = new URLSearchParams(location.search);
  resetToken = params.get("token");

  if (!resetToken) {
    showResetState("error", I18n.t("reset.errors.invalid"));
    return;
  }

  showResetState("loading");
  const error = await validateResetToken(resetToken);
  if (error) {
    showResetState("error", error);
    return;
  }

  showResetState("form");
  bindResetForm();
  document.getElementById("reset-password")?.focus();
}

document.addEventListener("DOMContentLoaded", () => {
  document.addEventListener("langchange", () => I18n.apply());
  initResetPasswordPage();
});