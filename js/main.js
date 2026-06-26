const STORAGE_KEY = "rackforge-plan";
const PLAN_ID_KEY = "rackforge-plan-id";
const LEGACY_STORAGE_KEYS = ["openrack-plan", "home-lab-rack-plan", "stef-rack-plan"];
const ICON_V = "49";

let planId = null;
let skipCloudSync = false;
let cloudSaveTimer = null;

const EQUIPMENT_TYPES = [
  { type: "server-1u", name: "1U Server", icon: "icons/server-1u.svg", height: 1, color: "#0076ce" },
  { type: "server-2u", name: "2U Server", icon: "icons/server-2u.svg", height: 2, color: "#14a85e" },
  { type: "server-4u", name: "4U Server", icon: "icons/server-4u.svg", height: 4, color: "#0d8a4a" },
  { type: "switch", name: "1U Switch", icon: "icons/switch.svg", height: 1, color: "#3b9eff" },
  { type: "router", name: "1U Router", icon: "icons/router.svg", height: 1, color: "#2563eb" },
  { type: "nas-2u", name: "2U NAS", icon: "icons/nas-2u.svg", height: 2, color: "#a78bfa" },
  { type: "nas-4u", name: "4U NAS", icon: "icons/nas-4u.svg", height: 4, color: "#7c3aed" },
  { type: "patch-16", name: "16p Patch Panel", icon: "icons/patch-16.svg", height: 1, color: "#94a3b8" },
  { type: "patch-24", name: "24p Patch Panel", icon: "icons/patch-24.svg", height: 1, color: "#94a3b8" },
  { type: "patch-48", name: "48p Patch Panel", icon: "icons/patch-48.svg", height: 1, color: "#94a3b8" },
  { type: "pdu", name: "1U PDU", icon: "icons/pdu.svg", height: 1, color: "#f59e0b" },
  { type: "ups-2u", name: "2U UPS", icon: "icons/ups.svg", height: 2, color: "#d97706" },
  { type: "kvm", name: "1U KVM", icon: "icons/kvm.svg", height: 1, color: "#06b6d4" },
  { type: "blank", name: "1U Blanking", icon: "icons/blank.svg", height: 1, color: "#334155" },
  { type: "blank-2u", name: "2U Blanking", icon: "icons/blank-2u.svg", height: 2, color: "#334155" },
  { type: "blank-3u", name: "3U Blanking", icon: "icons/blank-3u.svg", height: 3, color: "#334155" },
  { type: "blank-4u", name: "4U Blanking", icon: "icons/blank-4u.svg", height: 4, color: "#334155" },
  { type: "blank-6u", name: "6U Blanking", icon: "icons/blank-6u.svg", height: 6, color: "#334155" },
];

function iconImg(src, className, alt = "") {
  const url = `${src}?v=${ICON_V}`;
  return `<img src="${url}" class="${className}" alt="${alt}" loading="lazy" draggable="false">`;
}

let rackHeight = 25;
let devices = [];
let selectedType = null;
let selectedDeviceId = null;
let nextId = 1;

function typeInfo(type) {
  const base = EQUIPMENT_TYPES.find((t) => t.type === type) || EQUIPMENT_TYPES[0];
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
    JSON.stringify({ rackHeight, devices, nextId })
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
  const payload = { rackHeight, devices, nextId };

  if (window.Auth?.isLoggedIn()) {
    const res = await apiFetch("/api/me/plan", {
      method: "PUT",
      body: JSON.stringify(payload),
    });
    if (!res.ok) throw new Error("save failed");
    const data = await res.json();
    planId = data.id;
    localStorage.setItem(PLAN_ID_KEY, planId);
    setPlanInUrl(planId);
    return;
  }

  const url = planId ? `/api/plans/${planId}` : "/api/plans";
  const method = planId ? "PUT" : "POST";
  const res = await apiFetch(url, { method, body: JSON.stringify(payload) });
  if (!res.ok) throw new Error("save failed");
  const data = await res.json();
  if (!planId) {
    planId = data.id;
    localStorage.setItem(PLAN_ID_KEY, planId);
    setPlanInUrl(planId);
  }
}

async function loadAccountPlan() {
  const res = await apiFetch("/api/me/plan");
  if (res.status === 404) {
    await cloudSave();
    return;
  }
  if (!res.ok) throw new Error("load failed");
  const data = await res.json();
  skipCloudSync = true;
  rackHeight = data.rackHeight || 25;
  devices = (data.devices || []).filter((d) => EQUIPMENT_TYPES.some((t) => t.type === d.type));
  nextId = data.nextId || 1;
  planId = data.id;
  localStorage.setItem(PLAN_ID_KEY, planId);
  document.getElementById("rack-height").value = String(rackHeight);
  localStorage.setItem(STORAGE_KEY, JSON.stringify({ rackHeight, devices, nextId }));
  skipCloudSync = false;
  setPlanInUrl(planId);
}

async function cloudLoad(id) {
  const res = await apiFetch(`/api/plans/${id}`);
  if (!res.ok) throw new Error("load failed");
  const data = await res.json();
  skipCloudSync = true;
  rackHeight = data.rackHeight || 25;
  devices = (data.devices || []).filter((d) => EQUIPMENT_TYPES.some((t) => t.type === d.type));
  nextId = data.nextId || 1;
  planId = id;
  localStorage.setItem(PLAN_ID_KEY, planId);
  document.getElementById("rack-height").value = String(rackHeight);
  save();
  skipCloudSync = false;
  setPlanInUrl(id);
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
    devices = (data.devices || []).filter((d) => EQUIPMENT_TYPES.some((t) => t.type === d.type));
    nextId = data.nextId || 1;
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
function findPlacementStart(clickedU, height) {
  if (clickedU < 1 || clickedU + height - 1 > rackHeight) return null;
  if (!isRangeFree(clickedU, height)) return null;
  return clickedU;
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
  document.querySelectorAll(".rack-u--preview, .rack-u--preview-anchor, .rack-u--blocked").forEach((row) => {
    row.classList.remove("rack-u--preview", "rack-u--preview-anchor", "rack-u--blocked");
  });
}

function highlightPlacementPreview(clickedU) {
  clearPlacementPreview();
  if (!selectedType) return;
  const info = typeInfo(selectedType);
  const startU = findPlacementStart(clickedU, info.height);
  const rack = document.getElementById("rack");
  if (startU == null) {
    for (const u of uRange(clickedU, info.height)) {
      if (u > rackHeight) break;
      rack.querySelector(`[data-u="${u}"]`)?.classList.add("rack-u--blocked");
    }
    return;
  }
  for (const u of uRange(startU, info.height)) {
    const row = rack.querySelector(`[data-u="${u}"]`);
    if (row) {
      row.classList.add("rack-u--preview");
      if (u === clickedU) row.classList.add("rack-u--preview-anchor");
    }
  }
}

function renderPalette() {
  const list = document.getElementById("palette-list");
  list.innerHTML = EQUIPMENT_TYPES.map(
    (eq) => `
    <button type="button" class="palette-item${selectedType === eq.type ? " palette-item--active" : ""}"
      data-type="${eq.type}" style="--eq-color: ${eq.color}">
      <span class="palette-item__icon">${iconImg(eq.icon, "eq-icon eq-icon--palette", eq.name)}</span>
      <span class="palette-item__info">
        <span class="palette-item__name">${eq.name}</span>
        <span class="palette-item__meta">${eq.height}U</span>
      </span>
    </button>`
  ).join("");

  list.querySelectorAll(".palette-item").forEach((btn) => {
    btn.addEventListener("click", () => {
      selectedType = btn.dataset.type;
      selectedDeviceId = null;
      renderPalette();
      renderRack();
      renderDetails();
      updateHint();
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
        <div class="rack-device rack-device--blank" style="${deviceStyle}">
          <div class="rack-device__face rack-device__face--blank" role="img" aria-label="${info.name}"></div>
        </div>`;
      } else {
        content = `
        <div class="rack-device" style="${deviceStyle}">
          <div class="rack-device__ear rack-device__ear--left" aria-hidden="true">${earHoles(span)}</div>
          <div class="rack-device__side rack-device__side--left" aria-hidden="true"></div>
          <div class="rack-device__faceplate">
            ${iconImg(info.icon, "rack-device__face", info.name)}
            <div class="rack-device__nameplate">
              <span class="rack-device__name">${label}</span>
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
      `<div class="${slotClass}" data-u="${u}" role="gridcell"${device && isTop ? ` data-device="${device.id}"` : ""}>${content}</div>`
    );
  }

  rack.innerHTML = rows.join("");

  if (selectedType) {
    const preview = typeInfo(selectedType);
    rack.style.setProperty("--preview-icon", `url("${preview.icon}?v=${ICON_V}")`);
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
  });

  rack.querySelectorAll(".rack-device").forEach((el) => {
    el.addEventListener("click", (e) => {
      e.stopPropagation();
      const deviceId = Number(el.closest("[data-device]")?.dataset.device);
      if (deviceId) selectDevice(deviceId);
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

  document.getElementById("detail-icon").innerHTML = iconImg(info.icon, "eq-icon eq-icon--detail", info.name);
  document.getElementById("detail-name").textContent = device.label || info.name;
  document.getElementById("detail-position").textContent =
    `U${device.startU} – U${device.startU + device.height - 1}`;
  document.getElementById("detail-height").textContent = `${device.height}U`;
  document.getElementById("detail-type").textContent = info.name;

  const labelInput = document.getElementById("detail-label");
  labelInput.value = device.label || "";
}

function renderStats() {
  const used = new Set();
  devices.forEach((d) => uRange(d.startU, d.height).forEach((u) => used.add(u)));

  document.getElementById("stat-used").textContent = used.size;
  document.getElementById("stat-free").textContent = rackHeight - used.size;
  document.getElementById("stat-devices").textContent = devices.length;
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
          <span class="inventory-item__icon">${iconImg(info.icon, "eq-icon eq-icon--inventory", info.name)}</span>
          <span class="inventory-item__text">
            <span class="inventory-item__name">${label}</span>
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
    hint.textContent = I18n.t("hints.editOrRemove");
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
  if (!selectedDeviceId) return;
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
  if (devices.length && !confirm(I18n.t("reset.confirm"))) return;
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
  document.getElementById("btn-remove").addEventListener("click", removeSelected);
  document.getElementById("detail-label").addEventListener("input", (e) => {
    const device = devices.find((d) => d.id === selectedDeviceId);
    if (!device) return;
    device.label = e.target.value;
    save();
    renderRack();
    renderInventory();
    document.getElementById("detail-name").textContent =
      device.label || typeInfo(device.type).name;
  });

  document.addEventListener("langchange", () => {
    renderPalette();
    renderRack();
    renderDetails();
    renderStats();
    renderInventory();
    updateHint();
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