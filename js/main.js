const STORAGE_KEY = "rackforge-plan";
const PLAN_ID_KEY = "rackforge-plan-id";
const LEGACY_STORAGE_KEYS = ["openrack-plan", "home-lab-rack-plan", "stef-rack-plan"];
const ICON_V = "57";

let planId = null;
let skipCloudSync = false;
let cloudSaveTimer = null;

const EQUIPMENT_TYPES = [
  { type: "server-1u", name: "1U Server", icon: "icons/server-1u.svg", height: 1, color: "#0076ce", powerW: 150 },
  { type: "server-2u", name: "2U Server", icon: "icons/server-2u.svg", height: 2, color: "#14a85e", powerW: 300 },
  { type: "server-4u", name: "4U Server", icon: "icons/server-4u.svg", height: 4, color: "#0d8a4a", powerW: 500 },
  { type: "switch-16", name: "16p Switch", icon: "icons/switch-16.svg", height: 1, color: "#3b9eff", powerW: 30 },
  { type: "switch-24", name: "24p Switch", icon: "icons/switch-24.svg", height: 1, color: "#3b9eff", powerW: 45 },
  { type: "switch-48", name: "48p Switch", icon: "icons/switch-48.svg", height: 1, color: "#3b9eff", powerW: 75 },
  { type: "router", name: "1U Router", icon: "icons/router.svg", height: 1, color: "#2563eb", powerW: 25 },
  { type: "nas-2u", name: "2U NAS", icon: "icons/nas-2u.svg", height: 2, color: "#a78bfa", powerW: 80 },
  { type: "nas-4u", name: "4U NAS", icon: "icons/nas-4u.svg", height: 4, color: "#7c3aed", powerW: 150 },
  { type: "patch-16", name: "16p Patch Panel", icon: "icons/patch-16.svg", height: 1, color: "#94a3b8", powerW: 0 },
  { type: "patch-24", name: "24p Patch Panel", icon: "icons/patch-24.svg", height: 1, color: "#94a3b8", powerW: 0 },
  { type: "patch-48", name: "48p Patch Panel", icon: "icons/patch-48.svg", height: 1, color: "#94a3b8", powerW: 0 },
  { type: "pdu", name: "1U PDU", icon: "icons/pdu.svg", height: 1, color: "#f59e0b", powerW: 0 },
  { type: "ups-2u", name: "2U UPS", icon: "icons/ups.svg", height: 2, color: "#d97706", powerW: 0 },
  { type: "kvm", name: "1U KVM", icon: "icons/kvm.svg", height: 1, color: "#06b6d4", powerW: 10 },
  { type: "blank", name: "1U Blanking", icon: "icons/blank.svg", height: 1, color: "#334155", powerW: 0 },
  { type: "blank-2u", name: "2U Blanking", icon: "icons/blank-2u.svg", height: 2, color: "#334155", powerW: 0 },
  { type: "blank-3u", name: "3U Blanking", icon: "icons/blank-3u.svg", height: 3, color: "#334155", powerW: 0 },
  { type: "blank-4u", name: "4U Blanking", icon: "icons/blank-4u.svg", height: 4, color: "#334155", powerW: 0 },
  { type: "blank-6u", name: "6U Blanking", icon: "icons/blank-6u.svg", height: 6, color: "#334155", powerW: 0 },
];

function escapeHtml(str) {
  return String(str ?? "").replace(/[&<>"']/g, (c) => ({
    "&": "&amp;",
    "<": "&lt;",
    ">": "&gt;",
    '"': "&quot;",
    "'": "&#39;",
  })[c]);
}

function iconImg(src, className, alt = "") {
  const url = `${src}?v=${ICON_V}`;
  return `<img src="${url}" class="${className}" alt="${escapeHtml(alt)}" loading="lazy" draggable="false">`;
}

function equipmentIcon(info, className) {
  if (info.custom) {
    return `<div class="${className} equip-icon--custom" style="--dev-color: ${info.color};" role="img" aria-label="${escapeHtml(info.name)}"></div>`;
  }
  return iconImg(info.icon, className, info.name);
}

let rackHeight = 25;
let devices = [];
let selectedType = null;
let selectedDeviceId = null;
let nextId = 1;
let dragDeviceId = null;
let currentRackName = "";
let powerBudgetW = 0;
let customTypes = [];
let currentPlanRole = "owner";

function isCustomType(type) {
  return typeof type === "string" && type.startsWith("custom:");
}

function parseDevices(raw) {
  return (raw || [])
    .map((d) => ({ ...d, type: normalizeDeviceType(d.type) }))
    .filter((d) => EQUIPMENT_TYPES.some((t) => t.type === d.type) || isCustomType(d.type));
}

function devicePowerW(device) {
  if (Number.isFinite(device.powerW) && device.powerW >= 0) return device.powerW;
  return typeInfo(device.type).powerW || 0;
}

function totalPowerW() {
  return devices.reduce((sum, d) => sum + devicePowerW(d), 0);
}

function typeInfo(type) {
  const normalized = normalizeDeviceType(type);
  if (isCustomType(normalized)) {
    const custom = customTypes.find((c) => `custom:${c.id}` === normalized);
    if (custom) {
      return {
        type: normalized,
        name: custom.name,
        color: custom.color,
        height: custom.height,
        powerW: custom.powerW,
        icon: null,
        custom: true,
      };
    }
    return {
      type: normalized,
      name: I18n.t("palette.unknownCustomType"),
      color: "#555555",
      height: 1,
      powerW: 0,
      icon: null,
      custom: true,
    };
  }
  const base = EQUIPMENT_TYPES.find((t) => t.type === normalized) || EQUIPMENT_TYPES[0];
  return { ...base, name: I18n.t(`equipment.${base.type}`) };
}

function isBlankType(type) {
  return type === "blank" || type.startsWith("blank-");
}

function blankNeighborBleed(device) {
  const topU = device.startU + device.height - 1;
  const neighborAbove = deviceAtU(topU + 1);
  const neighborBelow = deviceAtU(device.startU - 1);
  const bleedAbove = neighborAbove && isBlankType(neighborAbove.type) ? 2 : 4;
  const bleedBelow = neighborBelow && isBlankType(neighborBelow.type) ? 2 : 4;
  return { bleedAbove, bleedBelow };
}

function save() {
  localStorage.setItem(
    STORAGE_KEY,
    JSON.stringify({ rackHeight, devices, nextId, powerBudgetW })
  );
  if (!skipCloudSync) scheduleCloudSave();
}

function setPlanInUrl(id) {
  const basePath = window.Routes?.APP || "/main";
  const url = new URL(location.href);
  if (window.Auth?.isLoggedIn()) {
    if (!url.searchParams.has("plan")) return;
    url.searchParams.delete("plan");
    url.pathname = basePath;
    history.replaceState(null, "", `${url.pathname}${url.search}${url.hash}`);
    return;
  }
  url.pathname = basePath;
  url.searchParams.set("plan", id);
  history.replaceState(null, "", url);
}

function apiFetch(url, options = {}) {
  const headers = { "Content-Type": "application/json", ...(options.headers || {}) };
  return fetch(url, { credentials: "include", ...options, headers });
}

function scheduleCloudSave() {
  if (!window.Auth?.isLoggedIn() && !planId) return;
  clearTimeout(cloudSaveTimer);
  cloudSaveTimer = setTimeout(() => {
    cloudSave().catch(() => {});
  }, 1500);
}

async function cloudSave() {
  const payload = { rackHeight, devices, nextId, name: currentRackName, powerBudgetW };
  const loggedIn = window.Auth?.isLoggedIn();
  const url = planId ? `/api/plans/${planId}` : loggedIn ? "/api/me/plans" : "/api/plans";
  const method = planId ? "PUT" : "POST";
  const res = await apiFetch(url, { method, body: JSON.stringify(payload) });
  if (!res.ok) {
    if (res.status === 403) {
      const err = await res.json().catch(() => null);
      if (err?.error === "rack_limit_reached") {
        const rackLimitError = new Error("rack limit reached");
        rackLimitError.rackLimit = err;
        throw rackLimitError;
      }
    }
    throw new Error("save failed");
  }
  const data = await res.json();
  if (!planId) {
    planId = data.id;
    localStorage.setItem(PLAN_ID_KEY, planId);
    setPlanInUrl(planId);
  }
}

async function loadAccountPlan() {
  const res = await apiFetch("/api/me/plans");
  if (!res.ok) throw new Error("load failed");
  const list = await res.json();
  if (!list.length) {
    const created = await apiFetch("/api/me/plans", {
      method: "POST",
      body: JSON.stringify({ rackHeight }),
    });
    if (!created.ok) throw new Error("create failed");
    const data = await created.json();
    await cloudLoad(data.id);
    return;
  }
  const cachedId = localStorage.getItem(PLAN_ID_KEY);
  const match = list.find((p) => p.id === cachedId) || list[0];
  await cloudLoad(match.id);
}

async function cloudLoad(id) {
  const res = await apiFetch(`/api/plans/${id}`);
  if (!res.ok) throw new Error("load failed");
  const data = await res.json();
  skipCloudSync = true;
  rackHeight = data.rackHeight || 25;
  devices = parseDevices(data.devices);
  nextId = data.nextId || 1;
  currentRackName = data.name || "Rack";
  powerBudgetW = data.powerBudgetW || 0;
  // Anonymous/guest mode never surfaces owner-only UI (the whole rack-switcher
  // toolbar is hidden unless logged in), so default to unrestricted there
  // regardless of what the server computed for this request.
  currentPlanRole = window.Auth?.isLoggedIn() ? data.role || "owner" : "owner";
  planId = id;
  localStorage.setItem(PLAN_ID_KEY, planId);
  document.getElementById("rack-height").value = String(rackHeight);
  save();
  skipCloudSync = false;
  setPlanInUrl(id);
  renderReadOnlyState();
}

async function loadMyRackList() {
  const select = document.getElementById("rack-switcher");
  const wrap = document.getElementById("rack-switcher-wrap");
  if (!select || !wrap || !window.Auth?.isLoggedIn()) return;
  const res = await apiFetch("/api/me/plans");
  if (!res.ok) return;
  const list = await res.json();
  select.innerHTML = "";
  for (const plan of list) {
    const opt = document.createElement("option");
    opt.value = plan.id;
    let label = plan.name || `Rack (${plan.rackHeight}U)`;
    if (plan.role && plan.role !== "owner") {
      label += ` · ${I18n.t("rackSwitcher.sharedBy", { owner: plan.ownerLabel || "?" })}`;
    }
    opt.textContent = label;
    if (plan.id === planId) opt.selected = true;
    select.appendChild(opt);
  }
  const newOpt = document.createElement("option");
  newOpt.value = "__new__";
  newOpt.textContent = I18n.t("rackSwitcher.new");
  select.appendChild(newOpt);
  wrap.hidden = false;
}

async function switchRack(value) {
  if (value === "__new__") {
    await createNewRack();
    return;
  }
  if (value === planId) return;
  try {
    await cloudLoad(value);
  } catch {
    /* ignore, list refresh below will restore correct selection */
  }
  renderPalette();
  renderRack();
  renderDetails();
  renderStats();
  renderInventory();
  updateHint();
  await loadMyRackList();
}

async function createNewRack() {
  const res = await apiFetch("/api/me/plans", {
    method: "POST",
    body: JSON.stringify({ rackHeight: Number(document.getElementById("rack-height").value) || 25 }),
  });
  if (res.status === 403) {
    const err = await res.json().catch(() => ({}));
    flashHint(I18n.t("rackSwitcher.limitReached", { limit: err.limit, tier: err.tier }));
    await loadMyRackList();
    return;
  }
  if (!res.ok) return;
  const data = await res.json();
  await cloudLoad(data.id);
  renderPalette();
  renderRack();
  renderDetails();
  renderStats();
  renderInventory();
  updateHint();
  await loadMyRackList();
}

async function renameRack() {
  if (!planId || currentPlanRole === "viewer") return;
  const name = prompt(I18n.t("rackSwitcher.renamePrompt"), currentRackName);
  if (name === null) return;
  const trimmed = name.trim();
  if (!trimmed || trimmed === currentRackName) return;
  currentRackName = trimmed;
  save();
  await loadMyRackList();
}

let historyPanelOpen = false;

function setHistoryPanelOpen(open) {
  historyPanelOpen = open;
  const panel = document.getElementById("history-panel");
  const trigger = document.getElementById("btn-history-toggle");
  if (!panel || !trigger) return;
  panel.hidden = !open;
  if (open) {
    loadSnapshots();
    document.addEventListener("click", onHistoryOutsideClick);
    document.addEventListener("keydown", onHistoryEscape);
  } else {
    document.removeEventListener("click", onHistoryOutsideClick);
    document.removeEventListener("keydown", onHistoryEscape);
  }
}

function onHistoryOutsideClick(e) {
  const menu = document.getElementById("history-menu");
  if (menu && !menu.contains(e.target)) setHistoryPanelOpen(false);
}

function onHistoryEscape(e) {
  if (e.key === "Escape") setHistoryPanelOpen(false);
}

function formatSnapshotTime(iso) {
  try {
    const locale = I18n.getLang() === "nl" ? "nl-NL" : "en-US";
    return new Date(iso).toLocaleString(locale, { dateStyle: "medium", timeStyle: "short" });
  } catch {
    return iso;
  }
}

async function loadSnapshots() {
  const list = document.getElementById("history-list");
  if (!planId) {
    list.innerHTML = "";
    return;
  }
  const res = await apiFetch(`/api/plans/${planId}/snapshots`);
  if (!res.ok) {
    list.innerHTML = `<p class="history-panel__empty">${escapeHtml(I18n.t("history.loadError"))}</p>`;
    return;
  }
  const snapshots = await res.json();
  if (!snapshots.length) {
    list.innerHTML = `<p class="history-panel__empty">${escapeHtml(I18n.t("history.empty"))}</p>`;
    return;
  }
  list.innerHTML = snapshots
    .map(
      (s) => `
    <li class="history-item">
      <span class="history-item__meta">
        <span class="history-item__time">${escapeHtml(formatSnapshotTime(s.createdAt))}</span>
        <span class="history-item__count">${escapeHtml(I18n.t("history.deviceCount", { count: s.deviceCount }))}</span>
      </span>
      <button type="button" class="btn btn--ghost btn--sm" data-restore-snapshot="${s.id}">${escapeHtml(I18n.t("history.restore"))}</button>
    </li>`
    )
    .join("");
  list.querySelectorAll("[data-restore-snapshot]").forEach((btn) => {
    btn.addEventListener("click", () => restoreSnapshot(btn.dataset.restoreSnapshot));
  });
}

async function restoreSnapshot(snapshotId) {
  if (!planId || currentPlanRole === "viewer") return;
  if (!confirm(I18n.t("history.restoreConfirm"))) return;
  const res = await apiFetch(`/api/plans/${planId}/snapshots/${snapshotId}/restore`, {
    method: "POST",
  });
  if (!res.ok) return;
  const data = await res.json();
  skipCloudSync = true;
  rackHeight = data.rackHeight || 25;
  devices = parseDevices(data.devices);
  nextId = data.nextId || 1;
  currentRackName = data.name || "Rack";
  powerBudgetW = data.powerBudgetW || 0;
  document.getElementById("rack-height").value = String(rackHeight);
  save();
  skipCloudSync = false;
  renderPalette();
  renderRack();
  renderDetails();
  renderStats();
  renderInventory();
  updateHint();
  setHistoryPanelOpen(false);
  await loadMyRackList();
}

let sharePanelOpen = false;

function setSharePanelOpen(open) {
  if (currentPlanRole !== "owner") open = false;
  sharePanelOpen = open;
  const panel = document.getElementById("share-panel");
  const trigger = document.getElementById("btn-share-toggle");
  if (!panel || !trigger) return;
  panel.hidden = !open;
  if (open) {
    loadCollaborators();
    document.addEventListener("click", onShareOutsideClick);
    document.addEventListener("keydown", onShareEscape);
  } else {
    document.removeEventListener("click", onShareOutsideClick);
    document.removeEventListener("keydown", onShareEscape);
  }
}

function onShareOutsideClick(e) {
  const menu = document.getElementById("share-menu");
  if (menu && !menu.contains(e.target)) setSharePanelOpen(false);
}

function onShareEscape(e) {
  if (e.key === "Escape") setSharePanelOpen(false);
}

const ROLE_LABEL_KEYS = { viewer: "share.roleViewer", editor: "share.roleEditor" };

async function loadCollaborators() {
  const list = document.getElementById("share-list");
  if (!planId || currentPlanRole !== "owner") {
    list.innerHTML = "";
    return;
  }
  const res = await apiFetch(`/api/plans/${planId}/collaborators`);
  if (!res.ok) {
    list.innerHTML = `<p class="history-panel__empty">${escapeHtml(I18n.t("share.loadError"))}</p>`;
    return;
  }
  const collaborators = await res.json();
  if (!collaborators.length) {
    list.innerHTML = `<p class="history-panel__empty">${escapeHtml(I18n.t("share.empty"))}</p>`;
    return;
  }
  list.innerHTML = collaborators
    .map(
      (c) => `
    <li class="history-item">
      <span class="history-item__meta">
        <span class="history-item__time">${escapeHtml(c.label)}</span>
        <span class="history-item__count">${escapeHtml(I18n.t(ROLE_LABEL_KEYS[c.role] || "share.roleViewer"))}</span>
      </span>
      <button type="button" class="btn btn--ghost btn--sm" data-remove-collaborator="${c.id}">${escapeHtml(I18n.t("share.remove"))}</button>
    </li>`
    )
    .join("");
  list.querySelectorAll("[data-remove-collaborator]").forEach((btn) => {
    btn.addEventListener("click", () => removeCollaborator(btn.dataset.removeCollaborator));
  });
}

async function addCollaborator() {
  if (!planId || currentPlanRole !== "owner") return;
  const emailInput = document.getElementById("share-email");
  const roleSelect = document.getElementById("share-role");
  const email = emailInput.value.trim();
  const role = roleSelect.value;
  if (!email) {
    flashHint(I18n.t("share.emailRequired"));
    return;
  }
  const res = await apiFetch(`/api/plans/${planId}/collaborators`, {
    method: "POST",
    body: JSON.stringify({ email, role }),
  });
  if (res.status === 403) {
    const err = await res.json().catch(() => ({}));
    flashHint(I18n.t("share.limitReached", { limit: err.limit, tier: err.tier }));
    return;
  }
  if (res.status === 404) {
    flashHint(I18n.t("share.notFound"));
    return;
  }
  if (res.status === 409) {
    flashHint(I18n.t("share.alreadyShared"));
    return;
  }
  if (!res.ok) {
    flashHint(I18n.t("share.addError"));
    return;
  }
  emailInput.value = "";
  await loadCollaborators();
}

async function removeCollaborator(collaboratorId) {
  if (!planId || currentPlanRole !== "owner") return;
  const res = await apiFetch(`/api/plans/${planId}/collaborators/${collaboratorId}`, {
    method: "DELETE",
  });
  if (!res.ok) return;
  await loadCollaborators();
}

function renderReadOnlyState() {
  const isOwner = currentPlanRole === "owner";
  const canEdit = currentPlanRole === "owner" || currentPlanRole === "editor";

  document.getElementById("share-menu").hidden = !isOwner;
  document.getElementById("btn-rack-delete").hidden = !isOwner;
  document.getElementById("btn-rack-rename").disabled = !canEdit;
  document.getElementById("btn-reset").disabled = !canEdit;
  document.getElementById("rack-height").disabled = !canEdit;
  document.getElementById("stat-power-wrap").disabled = !canEdit;
  document.getElementById("detail-label").disabled = !canEdit;
  document.getElementById("detail-power").disabled = !canEdit;
  document.getElementById("btn-remove").disabled = !canEdit;

  if (!isOwner) setSharePanelOpen(false);
}

function setPowerBudget() {
  if (currentPlanRole === "viewer") return;
  const raw = prompt(I18n.t("stats.powerBudgetPrompt"), powerBudgetW > 0 ? String(powerBudgetW) : "");
  if (raw === null) return;
  const trimmed = raw.trim();
  const parsed = trimmed === "" ? 0 : Number(trimmed);
  if (!Number.isFinite(parsed) || parsed < 0) return;
  powerBudgetW = Math.round(parsed);
  save();
  renderStats();
}

async function loadCustomTypes() {
  if (!window.Auth?.isLoggedIn()) return;
  const res = await apiFetch("/api/me/equipment-types");
  if (!res.ok) return;
  customTypes = await res.json();
  document.getElementById("palette-custom").hidden = false;
  renderPalette();
  renderRack();
  renderInventory();
  renderDetails();
}

async function createCustomType() {
  const name = document.getElementById("custom-type-name").value.trim();
  const height = Number(document.getElementById("custom-type-height").value);
  const color = document.getElementById("custom-type-color").value;
  const powerRaw = document.getElementById("custom-type-power").value.trim();
  const powerW = powerRaw === "" ? 0 : Number(powerRaw);

  if (!name) {
    flashHint(I18n.t("palette.customTypeNameRequired"));
    return;
  }
  if (!Number.isFinite(powerW) || powerW < 0) {
    flashHint(I18n.t("palette.customTypeInvalidPower"));
    return;
  }

  const res = await apiFetch("/api/me/equipment-types", {
    method: "POST",
    body: JSON.stringify({ name, height, color, powerW }),
  });
  if (res.status === 403) {
    const err = await res.json().catch(() => ({}));
    flashHint(I18n.t("palette.customTypeLimitReached", { limit: err.limit, tier: err.tier }));
    return;
  }
  if (!res.ok) {
    flashHint(I18n.t("palette.customTypeInvalid"));
    return;
  }
  document.getElementById("custom-type-name").value = "";
  document.getElementById("custom-type-power").value = "";
  document.getElementById("custom-type-form").hidden = true;
  await loadCustomTypes();
}

async function deleteCustomType(id) {
  if (!confirm(I18n.t("palette.deleteCustomTypeConfirm"))) return;
  const res = await apiFetch(`/api/me/equipment-types/${id}`, { method: "DELETE" });
  if (!res.ok) return;
  if (selectedType === `custom:${id}`) selectedType = null;
  await loadCustomTypes();
}

function textColorFor(bgColor) {
  const hex = (bgColor || "#334155").replace("#", "");
  if (hex.length !== 6) return "#ffffff";
  const r = parseInt(hex.slice(0, 2), 16);
  const g = parseInt(hex.slice(2, 4), 16);
  const b = parseInt(hex.slice(4, 6), 16);
  const luminance = (0.299 * r + 0.587 * g + 0.114 * b) / 255;
  return luminance > 0.6 ? "#0a0a0a" : "#ffffff";
}

function triggerDownload(url, filename) {
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  a.remove();
}

function exportRackPNG() {
  const uHeight = 26;
  const marginTop = 50;
  const marginBottom = 20;
  const marginLeft = 46;
  const marginRight = 16;
  const width = 640;
  const height = marginTop + rackHeight * uHeight + marginBottom;

  const canvas = document.createElement("canvas");
  const scale = 2;
  canvas.width = width * scale;
  canvas.height = height * scale;
  const ctx = canvas.getContext("2d");
  ctx.scale(scale, scale);

  ctx.fillStyle = "#0b1017";
  ctx.fillRect(0, 0, width, height);

  ctx.fillStyle = "#e8edf2";
  ctx.font = "bold 16px system-ui, sans-serif";
  ctx.fillText(`${currentRackName || "Rack"} · ${rackHeight}U`, marginLeft, 28);

  const rackLeft = marginLeft;
  const rackWidth = width - marginLeft - marginRight;

  for (let u = 1; u <= rackHeight; u++) {
    const y = marginTop + (rackHeight - u) * uHeight;
    ctx.strokeStyle = "#22303c";
    ctx.lineWidth = 1;
    ctx.strokeRect(rackLeft, y, rackWidth, uHeight);
    ctx.fillStyle = "#5b6b78";
    ctx.font = "9px monospace";
    ctx.fillText(String(u), rackLeft - 24, y + uHeight / 2 + 3);
  }

  const drawn = new Set();
  for (const device of devices) {
    if (drawn.has(device.id)) continue;
    drawn.add(device.id);
    const info = typeInfo(device.type);
    const topU = device.startU + device.height - 1;
    const y = marginTop + (rackHeight - topU) * uHeight;
    const h = device.height * uHeight;
    ctx.fillStyle = info.color || "#334155";
    ctx.fillRect(rackLeft + 1, y + 1, rackWidth - 2, h - 2);
    ctx.fillStyle = textColorFor(info.color);
    ctx.font = "bold 11px system-ui, sans-serif";
    const label = device.label || info.name;
    ctx.fillText(label, rackLeft + 8, y + h / 2 + 4, rackWidth - 90);
    ctx.font = "9px monospace";
    ctx.textAlign = "right";
    ctx.fillText(`U${device.startU}-U${topU}`, rackLeft + rackWidth - 8, y + h / 2 + 3);
    ctx.textAlign = "left";
  }

  const filename = `${(currentRackName || "rack").replace(/[^a-z0-9]+/gi, "-").toLowerCase()}.png`;
  canvas.toBlob((blob) => {
    const url = URL.createObjectURL(blob);
    triggerDownload(url, filename);
    setTimeout(() => URL.revokeObjectURL(url), 5000);
  });
}

function exportRackPDF() {
  const view = document.getElementById("print-view");
  const uPct = 100 / rackHeight;
  const drawn = new Set();
  const deviceBlocks = [];
  for (const device of devices) {
    if (drawn.has(device.id)) continue;
    drawn.add(device.id);
    const info = typeInfo(device.type);
    const topU = device.startU + device.height - 1;
    const top = (rackHeight - topU) * uPct;
    const heightPct = device.height * uPct;
    const label = device.label || info.name;
    deviceBlocks.push(`
      <div class="print-device" style="top:${top}%; height:${heightPct}%; background:${info.color || "#334155"}; color:${textColorFor(info.color)};">
        <span>${escapeHtml(label)}</span>
        <span class="print-device__pos">U${device.startU}-U${topU}</span>
      </div>`);
  }

  const numbers = [];
  for (let u = 1; u <= rackHeight; u++) {
    numbers.push(`<div class="print-num" style="height:${uPct}%;">${u}</div>`);
  }

  const frameHeight = rackHeight * 18;
  view.innerHTML = `
    <h1>${escapeHtml(currentRackName || "Rack")} · ${rackHeight}U</h1>
    <div class="print-rack">
      <div class="print-nums" style="height:${frameHeight}px;">${numbers.reverse().join("")}</div>
      <div class="print-frame" style="height:${frameHeight}px;">${deviceBlocks.join("")}</div>
    </div>`;

  window.print();
}

async function deleteRack() {
  if (!planId || currentPlanRole !== "owner") return;
  if (!confirm(I18n.t("rackSwitcher.deletePrompt"))) return;
  const res = await apiFetch(`/api/plans/${planId}`, { method: "DELETE" });
  if (res.status === 409) {
    flashHint(I18n.t("rackSwitcher.cannotDeleteLast"));
    return;
  }
  if (!res.ok) return;
  planId = null;
  localStorage.removeItem(PLAN_ID_KEY);
  await loadAccountPlan();
  renderPalette();
  renderRack();
  renderDetails();
  renderStats();
  renderInventory();
  updateHint();
  await loadMyRackList();
}

function load() {
  try {
    let raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) {
      for (const key of LEGACY_STORAGE_KEYS) {
        raw = localStorage.getItem(key);
        if (raw) break;
      }
    }
    if (!raw) return;
    const data = JSON.parse(raw);
    rackHeight = data.rackHeight || 25;
    devices = parseDevices(data.devices);
    nextId = data.nextId || 1;
    powerBudgetW = data.powerBudgetW || 0;
    document.getElementById("rack-height").value = String(rackHeight);
    save();
  } catch {
    /* ignore corrupt data */
  }
}

function uRange(startU, height) {
  return Array.from({ length: height }, (_, i) => startU + i);
}

function isRangeFree(startU, height, excludeId = null) {
  if (startU < 1 || startU + height - 1 > rackHeight) return false;
  const wanted = new Set(uRange(startU, height));
  for (const d of devices) {
    if (d.id === excludeId) continue;
    for (const u of uRange(d.startU, d.height)) {
      if (wanted.has(u)) return false;
    }
  }
  return true;
}

function deviceAtU(u) {
  return devices.find((d) => u >= d.startU && u < d.startU + d.height);
}

function isTopOfDevice(u, device) {
  return u === device.startU + device.height - 1;
}

// Klik = onderste U; apparaat vult clickedU t/m clickedU+height-1 (blijft in rack).
function findPlacementStart(clickedU, height, excludeId = null) {
  if (clickedU < 1 || clickedU + height - 1 > rackHeight) return null;
  if (!isRangeFree(clickedU, height, excludeId)) return null;
  return clickedU;
}

function moveDevice(deviceId, clickedU) {
  if (currentPlanRole === "viewer") return false;
  const device = devices.find((d) => d.id === deviceId);
  if (!device) return false;

  const startU = findPlacementStart(clickedU, device.height, deviceId);
  if (startU == null) {
    flashHint(I18n.t("hints.wontFit"));
    return false;
  }
  if (startU === device.startU) return true;

  device.startU = startU;
  save();
  renderRack();
  renderStats();
  renderInventory();
  updateHint();
  return true;
}

function selectDevice(deviceId) {
  selectedDeviceId = deviceId;
  selectedType = null;
  renderPalette();
  renderRack();
  renderDetails();
  renderInventory();
  updateHint();
}

function clearPlacementPreview() {
  document
    .querySelectorAll(
      ".rack-u--preview, .rack-u--preview-anchor, .rack-u--blocked, .rack-u--move-preview, .rack-u--move-anchor"
    )
    .forEach((row) => {
      row.classList.remove(
        "rack-u--preview",
        "rack-u--preview-anchor",
        "rack-u--blocked",
        "rack-u--move-preview",
        "rack-u--move-anchor"
      );
    });
}

function paintRangePreview(rack, clickedU, height, startU, mode) {
  const previewCls = mode === "move" ? "rack-u--move-preview" : "rack-u--preview";
  const anchorCls = mode === "move" ? "rack-u--move-anchor" : "rack-u--preview-anchor";

  if (startU == null) {
    for (const u of uRange(clickedU, height)) {
      if (u > rackHeight) break;
      rack.querySelector(`[data-u="${u}"]`)?.classList.add("rack-u--blocked");
    }
    return;
  }

  for (const u of uRange(startU, height)) {
    const row = rack.querySelector(`[data-u="${u}"]`);
    if (!row) continue;
    row.classList.add(previewCls);
    if (u === clickedU) row.classList.add(anchorCls);
  }
}

function highlightPlacementPreview(clickedU) {
  clearPlacementPreview();
  const rack = document.getElementById("rack");

  if (dragDeviceId) {
    const device = devices.find((d) => d.id === dragDeviceId);
    if (!device) return;
    paintRangePreview(
      rack,
      clickedU,
      device.height,
      findPlacementStart(clickedU, device.height, device.id),
      "move"
    );
    return;
  }

  if (selectedDeviceId && !selectedType) {
    const device = devices.find((d) => d.id === selectedDeviceId);
    if (!device) return;
    paintRangePreview(
      rack,
      clickedU,
      device.height,
      findPlacementStart(clickedU, device.height, device.id),
      "move"
    );
    return;
  }

  if (!selectedType) return;
  const info = typeInfo(selectedType);
  paintRangePreview(
    rack,
    clickedU,
    info.height,
    findPlacementStart(clickedU, info.height),
    "place"
  );
}

function renderPalette() {
  const list = document.getElementById("palette-list");
  const builtIn = EQUIPMENT_TYPES.map(
    (eq) => `
    <button type="button" class="palette-item${selectedType === eq.type ? " palette-item--active" : ""}"
      data-type="${eq.type}" style="--eq-color: ${eq.color}">
      <span class="palette-item__icon">${equipmentIcon(eq, "eq-icon eq-icon--palette")}</span>
      <span class="palette-item__info">
        <span class="palette-item__name">${eq.name}</span>
        <span class="palette-item__meta">${eq.height}U</span>
      </span>
    </button>`
  );
  const custom = customTypes.map((eq) => {
    const type = `custom:${eq.id}`;
    return `
    <button type="button" class="palette-item palette-item--custom${selectedType === type ? " palette-item--active" : ""}"
      data-type="${type}" style="--eq-color: ${eq.color}">
      <span class="palette-item__icon">${equipmentIcon({ ...eq, custom: true }, "eq-icon eq-icon--palette")}</span>
      <span class="palette-item__info">
        <span class="palette-item__name">${escapeHtml(eq.name)}</span>
        <span class="palette-item__meta">${eq.height}U</span>
      </span>
      <button type="button" class="palette-item__remove" data-remove-custom="${eq.id}" data-i18n-attr="aria-label" data-i18n="palette.deleteCustomType" aria-label="Verwijderen">×</button>
    </button>`;
  });
  list.innerHTML = builtIn.join("") + custom.join("");

  list.querySelectorAll(".palette-item").forEach((btn) => {
    btn.addEventListener("click", (e) => {
      if (e.target.closest("[data-remove-custom]")) return;
      selectedType = btn.dataset.type;
      selectedDeviceId = null;
      renderPalette();
      renderRack();
      renderDetails();
      updateHint();
    });
  });

  list.querySelectorAll("[data-remove-custom]").forEach((btn) => {
    btn.addEventListener("click", (e) => {
      e.stopPropagation();
      deleteCustomType(btn.dataset.removeCustom);
    });
  });
}

function earHoles(span) {
  const slots = [];
  for (let u = 0; u < span; u++) {
    slots.push(
      '<div class="ear-u-holes">' +
        '<span class="ear-hole"></span>'.repeat(3) +
      "</div>"
    );
  }
  return slots.join("");
}

const LEGACY_TYPE_ALIASES = { switch: "switch-24" };

function normalizeDeviceType(type) {
  return LEGACY_TYPE_ALIASES[type] || type;
}

function renderRailHoles() {
  const slots = [];
  const nums = [];
  for (let u = rackHeight; u >= 1; u--) {
    slots.push(
      `<div class="rail-u-slot" data-u="${u}">${'<span class="rail-hole"></span>'.repeat(3)}</div>`
    );
    nums.push(`<div class="rack-num-slot" data-u="${u}">${u}</div>`);
  }
  const slotHtml = slots.join("");
  document.getElementById("rail-left").innerHTML = slotHtml;
  document.getElementById("rail-right").innerHTML = slotHtml;
  document.getElementById("rack-nums").innerHTML = nums.join("");
}

function renderRack() {
  const rack = document.getElementById("rack");
  const rows = [];

  for (let u = rackHeight; u >= 1; u--) {
    const device = deviceAtU(u);
    const isTop = device && isTopOfDevice(u, device);
    const info = device ? typeInfo(device.type) : null;

    let slotClass = "rack-u";
    let content = "";

    // Anchor on hoogste U; groeit naar beneden — kan niet boven U25 uitsteken.
    if (device && isTop) {
      slotClass += " rack-u--filled";
      if (device.id === selectedDeviceId) slotClass += " rack-u--selected";
      if (isBlankType(device.type)) {
        slotClass += " rack-u--blank-slot";
      }
      const label = device.label || info.name;
      const span = device.height;
      const uEnd = device.startU + device.height - 1;
      let heightCalc = `calc(${span} * var(--u-h) + ${span - 1} * var(--u-gap))`;
      let blankTop = "";
      if (isBlankType(device.type)) {
        const { bleedAbove, bleedBelow } = blankNeighborBleed(device);
        heightCalc = `calc(${span} * var(--u-h) + ${span - 1} * var(--u-gap) + ${bleedAbove + bleedBelow}px)`;
        blankTop = ` top: -${bleedAbove}px;`;
      }
      const deviceStyle = `--dev-color: ${info.color}; --span: ${span}; --u-end: ${uEnd}; height: ${heightCalc};${blankTop}`;
      if (isBlankType(device.type)) {
        content = `
        <div class="rack-device rack-device--blank" style="${deviceStyle}" draggable="true" data-device-id="${device.id}">
          <div class="rack-device__face rack-device__face--blank" role="img" aria-label="${info.name}"></div>
        </div>`;
      } else {
        content = `
        <div class="rack-device" style="${deviceStyle}" draggable="true" data-device-id="${device.id}">
          <div class="rack-device__ear rack-device__ear--left" aria-hidden="true">${earHoles(span)}</div>
          <div class="rack-device__side rack-device__side--left" aria-hidden="true"></div>
          <div class="rack-device__faceplate rack-device__faceplate--${normalizeDeviceType(device.type)}">
            ${equipmentIcon(info, "rack-device__face")}
            <div class="rack-device__nameplate">
              <span class="rack-device__name">${escapeHtml(label)}</span>
              <span class="rack-device__meta">U${device.startU}–U${uEnd}</span>
            </div>
          </div>
          <div class="rack-device__side rack-device__side--right" aria-hidden="true"></div>
          <div class="rack-device__ear rack-device__ear--right" aria-hidden="true">${earHoles(span)}</div>
        </div>`;
      }
    } else if (device) {
      if (isBlankType(device.type)) {
        slotClass += " rack-u--blank-slot rack-u--part";
      } else {
        slotClass += " rack-u--part";
      }
      content = "";
    } else if (selectedType) {
      slotClass += " rack-u--placeable";
    }

    rows.push(
      `<div class="${slotClass}" data-u="${u}" role="gridcell"${device ? ` data-device="${device.id}"` : ""}>${content}</div>`
    );
  }

  rack.innerHTML = rows.join("");

  if (selectedType) {
    const preview = typeInfo(selectedType);
    const previewBg = preview.custom
      ? `linear-gradient(135deg, ${preview.color}, transparent)`
      : `url("${preview.icon}?v=${ICON_V}")`;
    rack.style.setProperty("--preview-icon", previewBg);
    rack.style.setProperty("--preview-h", String(preview.height));
  } else {
    rack.style.removeProperty("--preview-icon");
    rack.style.removeProperty("--preview-h");
  }

  rack.querySelectorAll(".rack-u").forEach((row) => {
    const u = Number(row.dataset.u);
    row.addEventListener("click", () => onRackClick(u));
    row.addEventListener("mouseenter", () => highlightPlacementPreview(u));
    row.addEventListener("mouseleave", clearPlacementPreview);
    row.addEventListener("dragover", (e) => {
      if (!dragDeviceId) return;
      e.preventDefault();
      e.dataTransfer.dropEffect = "move";
      highlightPlacementPreview(u);
    });
    row.addEventListener("drop", (e) => {
      if (!dragDeviceId) return;
      e.preventDefault();
      const id = dragDeviceId;
      dragDeviceId = null;
      clearPlacementPreview();
      moveDevice(id, u);
    });
  });

  rack.querySelectorAll(".rack-device").forEach((el) => {
    const deviceId = Number(el.dataset.deviceId);

    el.addEventListener("click", (e) => {
      e.stopPropagation();
      if (deviceId) selectDevice(deviceId);
    });

    el.addEventListener("dragstart", (e) => {
      if (selectedType) {
        e.preventDefault();
        return;
      }
      dragDeviceId = deviceId;
      selectedDeviceId = deviceId;
      selectedType = null;
      e.dataTransfer.effectAllowed = "move";
      e.dataTransfer.setData("text/plain", String(deviceId));
      el.classList.add("rack-device--dragging");
      renderPalette();
      updateHint();
    });

    el.addEventListener("dragend", () => {
      dragDeviceId = null;
      clearPlacementPreview();
      renderRack();
      renderDetails();
      renderInventory();
      updateHint();
    });
  });

  renderRailHoles();
}

function onRackClick(u) {
  const existing = deviceAtU(u);
  if (existing) {
    selectDevice(existing.id);
    return;
  }
  if (currentPlanRole === "viewer") return;

  if (selectedDeviceId && !selectedType) {
    moveDevice(selectedDeviceId, u);
    return;
  }

  if (!selectedType) {
    flashHint(I18n.t("hints.chooseFirst"));
    return;
  }

  const info = typeInfo(selectedType);
  const startU = findPlacementStart(u, info.height);
  if (startU == null) {
    flashHint(I18n.t("hints.wontFit"));
    return;
  }

  devices.push({
    id: nextId++,
    type: selectedType,
    startU,
    height: info.height,
    label: "",
  });

  save();
  renderRack();
  renderStats();
  renderInventory();
  updateHint();
}

function renderDetails() {
  const empty = document.getElementById("details-empty");
  const content = document.getElementById("details-content");
  const device = devices.find((d) => d.id === selectedDeviceId);

  if (!device) {
    empty.hidden = false;
    content.hidden = true;
    return;
  }

  const info = typeInfo(device.type);
  empty.hidden = true;
  content.hidden = false;

  document.getElementById("detail-icon").innerHTML = equipmentIcon(info, "eq-icon eq-icon--detail");
  document.getElementById("detail-name").textContent = device.label || info.name;
  document.getElementById("detail-position").textContent =
    `U${device.startU} – U${device.startU + device.height - 1}`;
  document.getElementById("detail-height").textContent = `${device.height}U`;
  document.getElementById("detail-type").textContent = info.name;

  const labelInput = document.getElementById("detail-label");
  labelInput.value = device.label || "";

  const powerInput = document.getElementById("detail-power");
  powerInput.value = Number.isFinite(device.powerW) ? device.powerW : "";
  powerInput.placeholder = String(info.powerW || 0);
}

function renderStats() {
  const used = new Set();
  devices.forEach((d) => uRange(d.startU, d.height).forEach((u) => used.add(u)));

  document.getElementById("stat-used").textContent = used.size;
  document.getElementById("stat-free").textContent = rackHeight - used.size;
  document.getElementById("stat-devices").textContent = devices.length;

  const power = totalPowerW();
  const powerEl = document.getElementById("stat-power");
  const powerStat = document.getElementById("stat-power-wrap");
  powerEl.textContent = powerBudgetW > 0 ? `${power} / ${powerBudgetW} W` : `${power} W`;
  powerStat.classList.toggle("rack-stat--warn", powerBudgetW > 0 && power > powerBudgetW);
}

function renderInventory() {
  const list = document.getElementById("inventory-list");

  if (devices.length === 0) {
    list.innerHTML = `<li class="inventory-empty">${I18n.t("inventory.empty")}</li>`;
    return;
  }

  const sorted = [...devices].sort((a, b) => b.startU - a.startU);
  list.innerHTML = sorted
    .map((d) => {
      const info = typeInfo(d.type);
      const label = d.label || info.name;
      return `<li>
        <button type="button" class="inventory-item${d.id === selectedDeviceId ? " inventory-item--active" : ""}" data-id="${d.id}">
          <span class="inventory-item__icon">${equipmentIcon(info, "eq-icon eq-icon--inventory")}</span>
          <span class="inventory-item__text">
            <span class="inventory-item__name">${escapeHtml(label)}</span>
            <span class="inventory-item__meta">U${d.startU} · ${d.height}U</span>
          </span>
        </button>
      </li>`;
    })
    .join("");

  list.querySelectorAll(".inventory-item").forEach((btn) => {
    btn.addEventListener("click", () => selectDevice(Number(btn.dataset.id)));
  });
}

function updateHint() {
  const hint = document.getElementById("placement-hint");
  if (selectedDeviceId) {
    hint.textContent = I18n.t("hints.moveOrEdit");
  } else if (selectedType) {
    hint.textContent = I18n.t("hints.clickToPlace");
  } else {
    hint.textContent = I18n.t("hints.selectLeft");
  }
}

function flashHint(msg) {
  const hint = document.getElementById("placement-hint");
  const prev = hint.textContent;
  hint.textContent = msg;
  hint.classList.add("rack-hint--warn");
  setTimeout(() => {
    hint.textContent = prev;
    hint.classList.remove("rack-hint--warn");
    updateHint();
  }, 2000);
}

function removeSelected() {
  if (!selectedDeviceId || currentPlanRole === "viewer") return;
  devices = devices.filter((d) => d.id !== selectedDeviceId);
  selectedDeviceId = null;
  save();
  renderRack();
  renderDetails();
  renderStats();
  renderInventory();
  updateHint();
}

function resetRack() {
  if (currentPlanRole === "viewer") return;
  if (devices.length && !confirm(I18n.t("rack.resetConfirm"))) return;
  devices = [];
  selectedDeviceId = null;
  selectedType = null;
  save();
  renderPalette();
  renderRack();
  renderDetails();
  renderStats();
  renderInventory();
  updateHint();
}

function changeRackHeight(h) {
  if (currentPlanRole === "viewer") {
    document.getElementById("rack-height").value = String(rackHeight);
    return;
  }
  const newH = Number(h);
  const maxU = devices.reduce((m, d) => Math.max(m, d.startU + d.height - 1), 0);
  if (maxU > newH) {
    flashHint(I18n.t("hints.rackTooSmall", { maxU }));
    document.getElementById("rack-height").value = String(rackHeight);
    return;
  }
  rackHeight = newH;
  save();
  renderRack();
  renderStats();
}

async function init() {
  document.getElementById("year").textContent = new Date().getFullYear();

  await Auth.checkAuth();

  const urlPlan = new URLSearchParams(location.search).get("plan");
  if (urlPlan) {
    try {
      await cloudLoad(urlPlan);
    } catch {
      load();
      planId = null;
      localStorage.removeItem(PLAN_ID_KEY);
      flashHint(I18n.t("cloud.loadError"));
    }
  } else if (Auth.isLoggedIn()) {
    try {
      load();
      await loadAccountPlan();
      await loadMyRackList();
      await loadCustomTypes();
    } catch {
      load();
    }
  } else {
    load();
    planId = localStorage.getItem(PLAN_ID_KEY);
  }

  if (!selectedType) selectedType = EQUIPMENT_TYPES[0].type;
  renderPalette();
  renderRack();
  renderDetails();
  renderStats();
  renderInventory();
  updateHint();

  document.getElementById("rack-height").addEventListener("change", (e) => {
    changeRackHeight(e.target.value);
  });

  document.getElementById("btn-reset").addEventListener("click", resetRack);
  document.getElementById("rack-switcher").addEventListener("change", (e) => {
    switchRack(e.target.value);
  });
  document.getElementById("btn-rack-rename").addEventListener("click", renameRack);
  document.getElementById("btn-rack-delete").addEventListener("click", deleteRack);
  document.getElementById("btn-history-toggle").addEventListener("click", (e) => {
    e.stopPropagation();
    setHistoryPanelOpen(!historyPanelOpen);
  });
  document.getElementById("btn-share-toggle").addEventListener("click", (e) => {
    e.stopPropagation();
    setSharePanelOpen(!sharePanelOpen);
  });
  document.getElementById("share-form").addEventListener("submit", (e) => {
    e.preventDefault();
    addCollaborator();
  });
  document.getElementById("stat-power-wrap").addEventListener("click", setPowerBudget);
  document.getElementById("btn-custom-type-toggle").addEventListener("click", () => {
    const form = document.getElementById("custom-type-form");
    form.hidden = !form.hidden;
  });
  document.getElementById("custom-type-form").addEventListener("submit", (e) => {
    e.preventDefault();
    createCustomType();
  });
  document.getElementById("btn-export-png").addEventListener("click", exportRackPNG);
  document.getElementById("btn-export-pdf").addEventListener("click", exportRackPDF);
  document.getElementById("btn-remove").addEventListener("click", removeSelected);
  document.getElementById("detail-label").addEventListener("input", (e) => {
    if (currentPlanRole === "viewer") return;
    const device = devices.find((d) => d.id === selectedDeviceId);
    if (!device) return;
    device.label = e.target.value;
    save();
    renderRack();
    renderInventory();
    document.getElementById("detail-name").textContent =
      device.label || typeInfo(device.type).name;
  });
  document.getElementById("detail-power").addEventListener("input", (e) => {
    if (currentPlanRole === "viewer") return;
    const device = devices.find((d) => d.id === selectedDeviceId);
    if (!device) return;
    const raw = e.target.value.trim();
    if (raw === "") {
      delete device.powerW;
    } else {
      const parsed = Number(raw);
      if (Number.isFinite(parsed) && parsed >= 0) device.powerW = Math.round(parsed);
    }
    save();
    renderStats();
  });

  document.addEventListener("langchange", () => {
    renderPalette();
    renderRack();
    renderDetails();
    renderStats();
    renderInventory();
    updateHint();
    loadMyRackList();
  });

  document.addEventListener("authchange", async () => {
    if (!Auth.isLoggedIn()) return;
    try {
      await loadAccountPlan();
    } catch {
      await cloudSave().catch(() => {});
    }
    renderRack();
    renderDetails();
    renderStats();
    renderInventory();
    updateHint();
    await loadMyRackList();
    await loadCustomTypes();
  });
}

let appStarted = false;

function startApp() {
  if (appStarted || !Auth.isLoggedIn()) return;
  appStarted = true;
  init();
}

document.addEventListener("authready", startApp);
document.addEventListener("appready", startApp);