const STORAGE_KEY = "rackforge-plan";
const PLAN_ID_KEY = "rackforge-plan-id";
const LEGACY_STORAGE_KEYS = ["openrack-plan", "home-lab-rack-plan", "stef-rack-plan"];
const ICON_V = "50";

let planId = null;
let skipCloudSync = false;
let cloudSaveTimer = null;

const EQUIPMENT_TYPES = [
  { type: "server-1u", name: "1U Server", icon: "icons/server-1u.svg", height: 1, color: "#0076ce" },
  { type: "server-2u", name: "2U Server", icon: "icons/server-2u.svg", height: 2, color: "#14a85e" },
  { type: "server-4u", name: "4U Server", icon: "icons/server-4u.svg", height: 4, color: "#0d8a4a" },
  { type: "switch-16", name: "16p Switch", icon: "icons/switch-16.svg", height: 1, color: "#3b9eff" },
  { type: "switch-24", name: "24p Switch", icon: "icons/switch-24.svg", height: 1, color: "#3b9eff" },
  { type: "switch-48", name: "48p Switch", icon: "icons/switch-48.svg", height: 1, color: "#3b9eff" },
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

const PORT_COUNTS = {
  "server-1u": 2,
  "server-2u": 2,
  "server-4u": 4,
  "switch-16": 16,
  "switch-24": 24,
  "switch-48": 48,
  switch: 24,
  router: 4,
  "nas-2u": 2,
  "nas-4u": 4,
  "patch-16": 16,
  "patch-24": 24,
  "patch-48": 48,
  pdu: 0,
  "ups-2u": 0,
  kvm: 0,
  blank: 0,
  "blank-2u": 0,
  "blank-3u": 0,
  "blank-4u": 0,
  "blank-6u": 0,
};

const CABLE_COLORS = [
  { value: "#1bdb7a", key: "green" },
  { value: "#3b9eff", key: "blue" },
  { value: "#a78bfa", key: "purple" },
  { value: "#f59e0b", key: "orange" },
  { value: "#94a3b8", key: "gray" },
  { value: "#ef4444", key: "red" },
];

let rackHeight = 25;
let devices = [];
let connections = [];
let selectedType = null;
let selectedDeviceId = null;
let detailsTab = "device";
let nextId = 1;
let cablingMapResizeTimer = null;

function parseDevices(raw) {
  return (raw || [])
    .map((d) => ({ ...d, type: normalizeDeviceType(d.type) }))
    .filter((d) => EQUIPMENT_TYPES.some((t) => t.type === d.type));
}

function typeInfo(type) {
  const normalized = normalizeDeviceType(type);
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

function devicePortCount(device) {
  return PORT_COUNTS[normalizeDeviceType(device.type)] ?? 0;
}

function devicesWithPorts() {
  return devices.filter((d) => devicePortCount(d) > 0);
}

function deviceDisplayName(device) {
  const info = typeInfo(device.type);
  return device.label || info.name;
}

function sanitizeConnections() {
  const deviceIds = new Set(devices.map((d) => d.id));
  connections = connections.filter((c) => {
    if (!deviceIds.has(c.fromDeviceId) || !deviceIds.has(c.toDeviceId)) return false;
    const fromDev = devices.find((d) => d.id === c.fromDeviceId);
    const toDev = devices.find((d) => d.id === c.toDeviceId);
    if (!fromDev || !toDev) return false;
    const fromMax = devicePortCount(fromDev);
    const toMax = devicePortCount(toDev);
    if (fromMax < 1 || toMax < 1) return false;
    if (c.fromPort < 1 || c.fromPort > fromMax || c.toPort < 1 || c.toPort > toMax) return false;
    return true;
  });
  const maxConnId = connections.reduce((m, c) => Math.max(m, c.id), 0);
  nextId = Math.max(nextId, maxConnId + 1);
}

function isPortUsed(deviceId, port, excludeId = null) {
  return connections.some(
    (c) =>
      c.id !== excludeId &&
      ((c.fromDeviceId === deviceId && c.fromPort === port) ||
        (c.toDeviceId === deviceId && c.toPort === port))
  );
}

function pruneConnectionsForDevice(deviceId) {
  connections = connections.filter(
    (c) => c.fromDeviceId !== deviceId && c.toDeviceId !== deviceId
  );
}

function save() {
  localStorage.setItem(
    STORAGE_KEY,
    JSON.stringify({ rackHeight, devices, connections, nextId })
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
  const payload = { rackHeight, devices, connections, nextId };

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
  devices = parseDevices(data.devices);
  connections = Array.isArray(data.connections) ? data.connections : [];
  nextId = data.nextId || 1;
  sanitizeConnections();
  planId = data.id;
  localStorage.setItem(PLAN_ID_KEY, planId);
  document.getElementById("rack-height").value = String(rackHeight);
  localStorage.setItem(STORAGE_KEY, JSON.stringify({ rackHeight, devices, connections, nextId }));
  skipCloudSync = false;
  setPlanInUrl(planId);
}

async function cloudLoad(id) {
  const res = await apiFetch(`/api/plans/${id}`);
  if (!res.ok) throw new Error("load failed");
  const data = await res.json();
  skipCloudSync = true;
  rackHeight = data.rackHeight || 25;
  devices = parseDevices(data.devices);
  connections = Array.isArray(data.connections) ? data.connections : [];
  nextId = data.nextId || 1;
  sanitizeConnections();
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
    devices = parseDevices(data.devices);
    connections = Array.isArray(data.connections) ? data.connections : [];
    nextId = data.nextId || 1;
    sanitizeConnections();
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
  renderCablingForm();
  renderCablingList();
  renderCablingMap();
  renderInventory();
  updateHint();
}

function switchDetailsTab(tab) {
  detailsTab = tab;
  const tabDevice = document.getElementById("tab-device");
  const tabCabling = document.getElementById("tab-cabling");
  const panelDevice = document.getElementById("panel-device");
  const panelCabling = document.getElementById("panel-cabling");

  const isDevice = tab === "device";
  tabDevice.classList.toggle("details-tab--active", isDevice);
  tabCabling.classList.toggle("details-tab--active", !isDevice);
  tabDevice.setAttribute("aria-selected", String(isDevice));
  tabCabling.setAttribute("aria-selected", String(!isDevice));
  panelDevice.hidden = !isDevice;
  panelCabling.hidden = isDevice;

  if (!isDevice) renderCablingForm();
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

const FACE_VIEW = { w: 440, h: 44 };

function svgPortPercent(cx, cy) {
  return { left: (cx / FACE_VIEW.w) * 100, top: (cy / FACE_VIEW.h) * 100 };
}

function gridPortPercent(port, originX, originY, cols, colStep, portW, rowStep, plugY) {
  const col = (port - 1) % cols;
  const row = Math.floor((port - 1) / cols);
  const cx = originX + col * colStep + portW / 2;
  const cy = originY + row * rowStep + plugY;
  return svgPortPercent(cx, cy);
}

function rowPortPercent(port, firstCx, stepCx, cy) {
  return svgPortPercent(firstCx + (port - 1) * stepCx, cy);
}

const LEGACY_TYPE_ALIASES = { switch: "switch-24" };

function normalizeDeviceType(type) {
  return LEGACY_TYPE_ALIASES[type] || type;
}

const FRONT_PORT_LAYOUTS = {
  "switch-16": (port) => gridPortPercent(port, 228, 13, 8, 13, 11, 12, 7),
  "switch-24": (port) => gridPortPercent(port, 168, 13, 12, 13, 11, 12, 7),
  "switch-48": (port) => gridPortPercent(port, 6, 10, 24, 17.4, 11, 12, 7),
  switch: (port) => gridPortPercent(port, 168, 13, 12, 13, 11, 12, 7),
  router: (port) => gridPortPercent(port, 178, 13, 8, 14, 12, 14, 7),
  "patch-16": (port) => rowPortPercent(port, 18.4, 26.9, 21),
  "patch-24": (port) => rowPortPercent(port, 13.9, 17.4, 19),
  "patch-48": (port) => {
    const col = (port - 1) % 24;
    const row = Math.floor((port - 1) / 24);
    const cx = 14.15 + col * 17.5;
    const cy = row === 0 ? 15.5 : 28.5;
    return svgPortPercent(cx, cy);
  },
};

function devicePortPlacement(type) {
  if (type.startsWith("server-") || type.startsWith("nas-")) return "rear";
  return "front";
}

function frontPortPosition(device, port, total) {
  const layout = FRONT_PORT_LAYOUTS[normalizeDeviceType(device.type)];
  if (layout) return layout(port, total);
  return { left: ((port - 0.5) / total) * 100, top: 72 };
}

function deviceLinkedPorts(deviceId) {
  const entries = [];
  connections.forEach((c) => {
    if (c.fromDeviceId === deviceId) {
      entries.push({ port: c.fromPort, color: c.color || CABLE_COLORS[0].value, connId: c.id });
    }
    if (c.toDeviceId === deviceId) {
      entries.push({ port: c.toPort, color: c.color || CABLE_COLORS[0].value, connId: c.id });
    }
  });
  const byPort = new Map();
  entries.forEach((e) => byPort.set(e.port, e));
  return [...byPort.values()].sort((a, b) => a.port - b.port);
}

function portDotMarkup(device, { port, color, connId }, placement, total) {
  const conn = connections.find((x) => x.id === connId);
  const title = conn?.label
    ? I18n.t("cabling.rackPortLabel", { port, label: conn.label })
    : I18n.t("cabling.rackPort", { port });
  let pos;
  if (placement === "rear") {
    const pct = ((port - 0.5) / total) * 100;
    pos = `top: ${pct}%; left: 50%`;
  } else {
    const { left, top } = frontPortPosition(device, port, total);
    pos = `left: ${left}%; top: ${top}%`;
  }
  const cls = placement === "rear" ? "rack-port rack-port--rear" : "rack-port rack-port--front";
  return `<span class="${cls}" data-port="${port}" data-placement="${placement}" data-conn="${connId}" style="--port-color: ${color}; ${pos}" title="${title}"></span>`;
}

function buildDevicePortParts(device) {
  const linked = deviceLinkedPorts(device.id);
  if (linked.length === 0) return { front: "", rear: "" };

  const total = devicePortCount(device);
  const placement = devicePortPlacement(device.type);
  const dots = linked.map((entry) => portDotMarkup(device, entry, placement, total)).join("");

  if (placement === "rear") {
    return {
      front: "",
      rear: `<div class="rack-device__rear" aria-hidden="true" title="${I18n.t("cabling.rearIo")}">
        <span class="rack-device__rear-tag">${I18n.t("cabling.rear")}</span>
        <div class="rack-device__ports rack-device__ports--rear">${dots}</div>
      </div>`,
    };
  }

  return {
    front: `<div class="rack-device__ports rack-device__ports--front" aria-hidden="true">${dots}</div>`,
    rear: "",
  };
}

function portAnchorInWrapper(deviceId, port, wrapperRect) {
  const row = document.querySelector(`[data-device="${deviceId}"]`);
  if (!row) return null;
  const dot = row.querySelector(`.rack-port[data-port="${port}"]`);
  if (dot) {
    const r = dot.getBoundingClientRect();
    return {
      x: r.left - wrapperRect.left + r.width / 2,
      y: r.top - wrapperRect.top + r.height / 2,
    };
  }

  const device = devices.find((d) => d.id === deviceId);
  const face = row.querySelector(".rack-device__faceplate");
  const rear = row.querySelector(".rack-device__rear");
  const target =
    device && devicePortPlacement(device.type) === "rear" && rear
      ? rear
      : face;
  if (!target) return null;
  const r = target.getBoundingClientRect();
  return {
    x: r.left - wrapperRect.left + (rear && target === rear ? r.width : r.width / 2),
    y: r.top - wrapperRect.top + r.height * 0.72,
  };
}

const CABLE_BAY_MIN = 14;
const CABLE_BAY_PER = 5;
const CABLE_BAY_MAX = 76;

function cableBayWidth(count) {
  if (count < 1) return 0;
  return Math.round(
    Math.min(CABLE_BAY_MAX, CABLE_BAY_MIN + Math.max(0, count - 1) * CABLE_BAY_PER)
  );
}

function rackCableBayMetrics(wrapperRect) {
  const bay = document.getElementById("rack-cable-bay");
  const rackEl = document.getElementById("rack");
  const railRight = document.getElementById("rail-right");
  if (!bay || !rackEl || !railRight) return null;

  const bayRect = bay.getBoundingClientRect();
  const rackRect = rackEl.getBoundingClientRect();
  const railRect = railRight.getBoundingClientRect();
  if (bayRect.width < 1) return null;

  return {
    left: bayRect.left - wrapperRect.left,
    right: bayRect.right - wrapperRect.left,
    center: bayRect.left - wrapperRect.left + bayRect.width / 2,
    width: bayRect.width,
    rackRight: rackRect.right - wrapperRect.left,
    railRight: railRect.right - wrapperRect.left,
    railLeft: railRect.left - wrapperRect.left,
  };
}

function assignCableLaneXs(entries, bay) {
  const pad = 3;
  const count = entries.length;
  if (count === 1) return [bay.center];

  const innerW = Math.max(bay.width - pad * 2, 4);
  const step = innerW / (count - 1);
  const start = bay.left + pad;
  return entries.map((_, idx) => start + idx * step);
}

function rackCablePath(from, to, laneX, bay) {
  const rackExit = bay.rackRight + 1;
  const railPass = bay.railRight + 1;

  let d = `M ${from.x} ${from.y}`;
  if (from.x < rackExit - 1) d += ` H ${rackExit}`;
  if (from.x < railPass - 1) d += ` H ${railPass}`;
  d += ` H ${laneX} V ${to.y} H ${railPass}`;
  if (to.x < rackExit - 1) d += ` H ${rackExit}`;
  d += ` H ${to.x}`;
  return d;
}

function renderRackCabling() {
  const wrapper = document.getElementById("rack-wrapper");
  const svg = document.getElementById("rack-cabling-svg");
  if (!wrapper || !svg) return;

  if (connections.length === 0) {
    wrapper.classList.remove("rack-wrapper--cabled");
    wrapper.style.removeProperty("--cable-bay-w");
    svg.innerHTML = "";
    return;
  }

  const cableCount = connections.length;
  wrapper.classList.add("rack-wrapper--cabled");
  wrapper.style.setProperty("--cable-bay-w", `${cableBayWidth(cableCount)}px`);

  requestAnimationFrame(() => {
    requestAnimationFrame(() => {
    const wrapperRect = wrapper.getBoundingClientRect();
    if (wrapperRect.width < 1 || wrapperRect.height < 1) return;

    const bay = rackCableBayMetrics(wrapperRect);
    if (!bay) return;

    svg.setAttribute("viewBox", `0 0 ${wrapperRect.width} ${wrapperRect.height}`);
    svg.innerHTML = "";

    const guideCount = Math.max(2, Math.min(cableCount + 1, 8));
    const guideStep = bay.width / (guideCount + 1);
    for (let g = 1; g <= guideCount; g++) {
      const gx = bay.left + guideStep * g;
      const guide = document.createElementNS("http://www.w3.org/2000/svg", "line");
      guide.setAttribute("x1", String(gx));
      guide.setAttribute("y1", "4");
      guide.setAttribute("x2", String(gx));
      guide.setAttribute("y2", String(wrapperRect.height - 4));
      guide.setAttribute("class", "rack-cable-bay__guide");
      svg.appendChild(guide);
    }

    const entries = connections
      .map((c) => {
        const from = portAnchorInWrapper(c.fromDeviceId, c.fromPort, wrapperRect);
        const to = portAnchorInWrapper(c.toDeviceId, c.toPort, wrapperRect);
        if (!from || !to) return null;
        return { c, from, to, midY: (from.y + to.y) / 2 };
      })
      .filter(Boolean)
      .sort((a, b) => a.midY - b.midY || a.c.id - b.c.id);

    const laneXs = assignCableLaneXs(entries, bay);

    entries.forEach((entry, idx) => {
      const { c, from, to } = entry;
      const laneX = laneXs[idx];
      const color = c.color || CABLE_COLORS[0].value;
      const path = document.createElementNS("http://www.w3.org/2000/svg", "path");
      path.setAttribute("d", rackCablePath(from, to, laneX, bay));
      path.setAttribute("stroke", color);
      path.setAttribute("stroke-opacity", "0.92");
      path.setAttribute("class", "rack-cable-line");
      if (c.label) path.setAttribute("aria-label", c.label);
      svg.appendChild(path);
    });
    });
  });
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
        const portParts = buildDevicePortParts(device);
        content = `
        <div class="rack-device" style="${deviceStyle}">
          <div class="rack-device__ear rack-device__ear--left" aria-hidden="true">${earHoles(span)}</div>
          <div class="rack-device__side rack-device__side--left" aria-hidden="true"></div>
          <div class="rack-device__faceplate">
            ${iconImg(info.icon, "rack-device__face", info.name)}
            ${portParts.front}
            <div class="rack-device__nameplate">
              <span class="rack-device__name">${label}</span>
              <span class="rack-device__meta">U${device.startU}–U${uEnd}</span>
            </div>
          </div>
          ${portParts.rear}
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
  renderRackCabling();
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
  renderCablingForm();
  renderCablingMap();
  updateHint();
}

function fillPortSelect(selectEl, deviceId) {
  const device = devices.find((d) => d.id === Number(deviceId));
  selectEl.innerHTML = "";
  if (!device) {
    selectEl.disabled = true;
    return;
  }
  const count = devicePortCount(device);
  if (count < 1) {
    selectEl.disabled = true;
    return;
  }
  selectEl.disabled = false;
  for (let p = 1; p <= count; p++) {
    const opt = document.createElement("option");
    opt.value = String(p);
    opt.textContent = isPortUsed(device.id, p)
      ? `${p} (${I18n.t("cabling.portUsed")})`
      : String(p);
    selectEl.appendChild(opt);
  }
}

function renderCablingForm() {
  const cabled = devicesWithPorts().sort((a, b) => b.startU - a.startU);
  const fromSel = document.getElementById("cable-from-device");
  const toSel = document.getElementById("cable-to-device");
  const fromPortSel = document.getElementById("cable-from-port");
  const toPortSel = document.getElementById("cable-to-port");
  const colorSel = document.getElementById("cable-color");

  const prevFrom = fromSel.value;
  const prevTo = toSel.value;

  const optionHtml = (d) => {
    const name = deviceDisplayName(d);
    return `<option value="${d.id}">U${d.startU} · ${name}</option>`;
  };

  if (cabled.length < 2) {
    fromSel.innerHTML = `<option value="">${I18n.t("cabling.needTwoDevices")}</option>`;
    toSel.innerHTML = fromSel.innerHTML;
    fromSel.disabled = true;
    toSel.disabled = true;
    fromPortSel.disabled = true;
    toPortSel.disabled = true;
  } else {
    fromSel.disabled = false;
    toSel.disabled = false;
    fromSel.innerHTML = cabled.map(optionHtml).join("");
    toSel.innerHTML = cabled.map(optionHtml).join("");

    if (prevFrom && cabled.some((d) => d.id === Number(prevFrom))) {
      fromSel.value = prevFrom;
    } else if (selectedDeviceId && cabled.some((d) => d.id === selectedDeviceId)) {
      fromSel.value = String(selectedDeviceId);
    }

    if (prevTo && cabled.some((d) => d.id === Number(prevTo))) {
      toSel.value = prevTo;
    } else {
      const alt = cabled.find((d) => d.id !== Number(fromSel.value));
      if (alt) toSel.value = String(alt.id);
    }

    if (fromSel.value === toSel.value) {
      const alt = cabled.find((d) => d.id !== Number(fromSel.value));
      if (alt) toSel.value = String(alt.id);
    }
  }

  if (!colorSel.dataset.ready) {
    colorSel.innerHTML = CABLE_COLORS.map(
      (c) => `<option value="${c.value}">${I18n.t(`cabling.colors.${c.key}`)}</option>`
    ).join("");
    colorSel.dataset.ready = "1";
  } else {
    colorSel.querySelectorAll("option").forEach((opt, i) => {
      const entry = CABLE_COLORS[i];
      if (entry) opt.textContent = I18n.t(`cabling.colors.${entry.key}`);
    });
  }

  fillPortSelect(fromPortSel, fromSel.value);
  fillPortSelect(toPortSel, toSel.value);
  renderCablingBulk();
}

function renderCablingBulk() {
  const section = document.getElementById("cabling-bulk");
  const switchSel = document.getElementById("bulk-switch");
  const patchSel = document.getElementById("bulk-patch");
  if (!section || !switchSel || !patchSel) return;

  const switches = devices
    .filter((d) => normalizeDeviceType(d.type) === "switch-48")
    .sort((a, b) => b.startU - a.startU);
  const patches = devices
    .filter((d) => d.type === "patch-24")
    .sort((a, b) => b.startU - a.startU);

  if (switches.length === 0 || patches.length === 0) {
    section.hidden = true;
    return;
  }

  section.hidden = false;
  const deviceOption = (d) => {
    const name = deviceDisplayName(d);
    return `<option value="${d.id}">U${d.startU} · ${name}</option>`;
  };

  const prevSwitch = switchSel.value;
  const prevPatch = patchSel.value;
  switchSel.innerHTML = switches.map(deviceOption).join("");
  patchSel.innerHTML = patches.map(deviceOption).join("");

  if (prevSwitch && switches.some((d) => d.id === Number(prevSwitch))) {
    switchSel.value = prevSwitch;
  } else if (selectedDeviceId && switches.some((d) => d.id === selectedDeviceId)) {
    switchSel.value = String(selectedDeviceId);
  }

  if (prevPatch && patches.some((d) => d.id === Number(prevPatch))) {
    patchSel.value = prevPatch;
  } else {
    const alt = patches.find((d) => d.id !== Number(switchSel.value));
    if (alt) patchSel.value = String(alt.id);
  }
}

function refreshCablingUI() {
  renderRack();
  renderCablingForm();
  renderCablingList();
  renderCablingMap();
}

function bulkConnectPatchPanel() {
  const switchId = Number(document.getElementById("bulk-switch").value);
  const patchId = Number(document.getElementById("bulk-patch").value);
  const switchDev = devices.find((d) => d.id === switchId);
  const patchDev = devices.find((d) => d.id === patchId);

  if (!switchDev || !patchDev) return;
  if (normalizeDeviceType(switchDev.type) !== "switch-48" || patchDev.type !== "patch-24") {
    flashHint(I18n.t("cabling.bulkInvalid"));
    return;
  }
  if (switchId === patchId) {
    flashHint(I18n.t("cabling.sameDevice"));
    return;
  }

  const color = document.getElementById("cable-color").value || CABLE_COLORS[0].value;
  let added = 0;
  let skipped = 0;

  for (let patchPort = 1; patchPort <= 24; patchPort++) {
    const switchPort = patchPort + 24;
    if (isPortUsed(switchId, switchPort) || isPortUsed(patchId, patchPort)) {
      skipped++;
      continue;
    }
    connections.push({
      id: nextId++,
      fromDeviceId: switchId,
      fromPort: switchPort,
      toDeviceId: patchId,
      toPort: patchPort,
      label: "",
      color,
    });
    added++;
  }

  if (added === 0) {
    flashHint(I18n.t("cabling.bulkNone"));
    return;
  }

  save();
  refreshCablingUI();

  if (skipped > 0) {
    flashHint(I18n.t("cabling.bulkPartial", { added, skipped }));
  } else {
    flashHint(I18n.t("cabling.bulkDone", { added }));
  }
}

function renderCablingList() {
  const list = document.getElementById("cabling-list");
  const empty = document.getElementById("cabling-list-empty");

  if (connections.length === 0) {
    list.innerHTML = "";
    empty.hidden = false;
    return;
  }

  empty.hidden = true;
  const sorted = [...connections].sort((a, b) => a.id - b.id);
  list.innerHTML = sorted
    .map((c) => {
      const fromDev = devices.find((d) => d.id === c.fromDeviceId);
      const toDev = devices.find((d) => d.id === c.toDeviceId);
      if (!fromDev || !toDev) return "";
      const color = c.color || CABLE_COLORS[0].value;
      const fromName = deviceDisplayName(fromDev);
      const toName = deviceDisplayName(toDev);
      const labelHtml = c.label
        ? `<span class="cabling-item__label">${c.label}</span>`
        : "";
      return `<li class="cabling-item" style="--cable-color: ${color}">
        <div class="cabling-item__body">
          <span class="cabling-item__route">${fromName} :${c.fromPort} → ${toName} :${c.toPort}</span>
          ${labelHtml}
        </div>
        <button type="button" class="cabling-item__remove" data-id="${c.id}" aria-label="${I18n.t("cabling.remove")}">×</button>
      </li>`;
    })
    .join("");

  list.querySelectorAll(".cabling-item__remove").forEach((btn) => {
    btn.addEventListener("click", () => removeConnection(Number(btn.dataset.id)));
  });
}

function drawCablingLines(conns, mapDevices) {
  const canvas = document.getElementById("cabling-map-canvas");
  const svg = document.getElementById("cabling-svg");
  if (!canvas || !svg) return;

  const rect = canvas.getBoundingClientRect();
  if (rect.width < 1 || rect.height < 1) return;

  svg.setAttribute("viewBox", `0 0 ${rect.width} ${rect.height}`);
  svg.innerHTML = "";

  const nodePos = {};
  mapDevices.forEach((d) => {
    const el = canvas.querySelector(`[data-id="${d.id}"]`);
    if (!el) return;
    const r = el.getBoundingClientRect();
    nodePos[d.id] = {
      x: r.left - rect.left + r.width / 2,
      y: r.top - rect.top + r.height / 2,
    };
  });

  conns.forEach((c) => {
    const from = nodePos[c.fromDeviceId];
    const to = nodePos[c.toDeviceId];
    if (!from || !to) return;
    const color = c.color || CABLE_COLORS[0].value;
    const midY = (from.y + to.y) / 2;
    const path = document.createElementNS("http://www.w3.org/2000/svg", "path");
    path.setAttribute("d", `M ${from.x} ${from.y} C ${from.x} ${midY}, ${to.x} ${midY}, ${to.x} ${to.y}`);
    path.setAttribute("fill", "none");
    path.setAttribute("stroke", color);
    path.setAttribute("stroke-width", "2");
    path.setAttribute("stroke-opacity", "0.8");
    svg.appendChild(path);
  });
}

function renderCablingMap() {
  const emptyEl = document.getElementById("cabling-map-empty");
  const canvasEl = document.getElementById("cabling-map-canvas");
  const countEl = document.getElementById("cabling-count");
  const nodesEl = document.getElementById("cabling-nodes");

  countEl.textContent = String(connections.length);

  if (connections.length === 0) {
    emptyEl.hidden = false;
    canvasEl.hidden = true;
    nodesEl.innerHTML = "";
    document.getElementById("cabling-svg").innerHTML = "";
    return;
  }

  emptyEl.hidden = true;
  canvasEl.hidden = false;

  const deviceIds = new Set();
  connections.forEach((c) => {
    deviceIds.add(c.fromDeviceId);
    deviceIds.add(c.toDeviceId);
  });

  const mapDevices = devices
    .filter((d) => deviceIds.has(d.id))
    .sort((a, b) => b.startU - a.startU);

  nodesEl.innerHTML = mapDevices
    .map((d) => {
      const info = typeInfo(d.type);
      const label = deviceDisplayName(d);
      const ports = devicePortCount(d);
      const linkCount = connections.filter(
        (c) => c.fromDeviceId === d.id || c.toDeviceId === d.id
      ).length;
      const active = d.id === selectedDeviceId ? " cabling-node--active" : "";
      return `<button type="button" class="cabling-node${active}" data-id="${d.id}" style="--node-color: ${info.color}">
        <span class="cabling-node__name">${label}</span>
        <span class="cabling-node__meta">${ports}p · ${linkCount}</span>
      </button>`;
    })
    .join("");

  nodesEl.querySelectorAll(".cabling-node").forEach((btn) => {
    btn.addEventListener("click", () => selectDevice(Number(btn.dataset.id)));
  });

  requestAnimationFrame(() => drawCablingLines(connections, mapDevices));
}

function addConnection(e) {
  e.preventDefault();
  const cabled = devicesWithPorts();
  if (cabled.length < 2) {
    flashHint(I18n.t("cabling.needTwoDevices"));
    return;
  }

  const fromDeviceId = Number(document.getElementById("cable-from-device").value);
  const toDeviceId = Number(document.getElementById("cable-to-device").value);
  const fromPort = Number(document.getElementById("cable-from-port").value);
  const toPort = Number(document.getElementById("cable-to-port").value);
  const label = document.getElementById("cable-label").value.trim().slice(0, 32);
  const color = document.getElementById("cable-color").value;

  if (!fromDeviceId || !toDeviceId || fromDeviceId === toDeviceId) {
    flashHint(I18n.t("cabling.sameDevice"));
    return;
  }

  const fromDev = devices.find((d) => d.id === fromDeviceId);
  const toDev = devices.find((d) => d.id === toDeviceId);
  if (!fromDev || !toDev) return;

  if (fromPort < 1 || fromPort > devicePortCount(fromDev) || toPort < 1 || toPort > devicePortCount(toDev)) {
    flashHint(I18n.t("cabling.invalidPort"));
    return;
  }

  if (isPortUsed(fromDeviceId, fromPort) || isPortUsed(toDeviceId, toPort)) {
    flashHint(I18n.t("cabling.portBusy"));
    return;
  }

  connections.push({
    id: nextId++,
    fromDeviceId,
    fromPort,
    toDeviceId,
    toPort,
    label,
    color,
  });

  document.getElementById("cable-label").value = "";
  save();
  refreshCablingUI();
}

function removeConnection(id) {
  connections = connections.filter((c) => c.id !== id);
  save();
  refreshCablingUI();
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
  pruneConnectionsForDevice(selectedDeviceId);
  devices = devices.filter((d) => d.id !== selectedDeviceId);
  selectedDeviceId = null;
  save();
  renderRack();
  renderDetails();
  renderStats();
  renderInventory();
  renderCablingForm();
  renderCablingList();
  renderCablingMap();
  updateHint();
}

function resetRack() {
  if (devices.length && !confirm(I18n.t("reset.confirm"))) return;
  devices = [];
  connections = [];
  selectedDeviceId = null;
  selectedType = null;
  save();
  renderPalette();
  renderRack();
  renderDetails();
  renderStats();
  renderInventory();
  renderCablingForm();
  renderCablingList();
  renderCablingMap();
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
  renderCablingForm();
  renderCablingList();
  renderCablingMap();
  switchDetailsTab(detailsTab);
  updateHint();

  document.getElementById("tab-device").addEventListener("click", () => switchDetailsTab("device"));
  document.getElementById("tab-cabling").addEventListener("click", () => switchDetailsTab("cabling"));
  document.getElementById("cabling-form").addEventListener("submit", addConnection);
  document.getElementById("btn-bulk-patch").addEventListener("click", bulkConnectPatchPanel);

  const cableFromDevice = document.getElementById("cable-from-device");
  const cableToDevice = document.getElementById("cable-to-device");
  cableFromDevice.addEventListener("change", () => {
    fillPortSelect(document.getElementById("cable-from-port"), cableFromDevice.value);
    if (cableFromDevice.value === cableToDevice.value) {
      const alt = devicesWithPorts().find((d) => d.id !== Number(cableFromDevice.value));
      if (alt) cableToDevice.value = String(alt.id);
      fillPortSelect(document.getElementById("cable-to-port"), cableToDevice.value);
    }
  });
  cableToDevice.addEventListener("change", () => {
    fillPortSelect(document.getElementById("cable-to-port"), cableToDevice.value);
    if (cableFromDevice.value === cableToDevice.value) {
      const alt = devicesWithPorts().find((d) => d.id !== Number(cableToDevice.value));
      if (alt) cableFromDevice.value = String(alt.id);
      fillPortSelect(document.getElementById("cable-from-port"), cableFromDevice.value);
    }
  });

  window.addEventListener("resize", () => {
    clearTimeout(cablingMapResizeTimer);
    cablingMapResizeTimer = setTimeout(() => {
      renderRackCabling();
      renderCablingMap();
    }, 150);
  });

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
    renderCablingForm();
    renderCablingList();
    renderCablingMap();
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
    renderCablingForm();
    renderCablingList();
    renderCablingMap();
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