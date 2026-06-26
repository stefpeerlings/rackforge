function showVerifyState(state, message = "") {
  const loading = document.getElementById("verify-loading");
  const success = document.getElementById("verify-success");
  const error = document.getElementById("verify-error");
  const errorText = document.getElementById("verify-error-text");

  if (loading) loading.hidden = state !== "loading";
  if (success) success.hidden = state !== "success";
  if (error) error.hidden = state !== "error";
  if (errorText && state === "error") errorText.textContent = message;
}

function verifyErrorMessage(res, data) {
  if (res.status === 409) return I18n.t("auth.errors.emailTaken");
  if (res.status === 400) return I18n.t("auth.errors.verifyInvalid");
  if (data?.error) return data.error;
  return I18n.t("auth.errors.verifyFailed");
}

async function runEmailVerification() {
  const params = new URLSearchParams(location.search);
  const token = params.get("token") || params.get("verify-email");

  if (!token) {
    showVerifyState("error", I18n.t("auth.errors.verifyInvalid"));
    return;
  }

  showVerifyState("loading");

  try {
    const res = await fetch(`/api/auth/verify-email?token=${encodeURIComponent(token)}`, {
      credentials: "include",
    });
    const data = await res.json().catch(() => ({}));

    if (!res.ok) {
      showVerifyState("error", verifyErrorMessage(res, data));
      return;
    }

    history.replaceState(null, "", "/verify-email");
    showVerifyState("success");
  } catch {
    showVerifyState("error", I18n.t("auth.errors.verifyFailed"));
  }
}

document.addEventListener("DOMContentLoaded", () => {
  document.addEventListener("langchange", () => I18n.apply());
  runEmailVerification();
});