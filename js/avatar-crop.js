/** Profile photo crop / pan / zoom before upload. */
const CROP_VIEW = 280;
const CROP_OUTPUT = 256;

const cropState = {
  img: null,
  scale: 1,
  minScale: 1,
  maxScale: 3,
  offsetX: 0,
  offsetY: 0,
  dragging: false,
  dragStartX: 0,
  dragStartY: 0,
  dragOriginX: 0,
  dragOriginY: 0,
  onComplete: null,
  onCancel: null,
};

function clamp(value, min, max) {
  return Math.min(max, Math.max(min, value));
}

function validateImageFile(file) {
  if (!file || !file.type.startsWith("image/")) {
    throw new Error(I18n.t("settings.errors.invalidImage"));
  }
  if (file.size > 2 * 1024 * 1024) {
    throw new Error(I18n.t("settings.errors.imageTooLarge"));
  }
}

function loadImageFromFile(file) {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => {
      const img = new Image();
      img.onload = () => resolve(img);
      img.onerror = () => reject(new Error(I18n.t("settings.errors.invalidImage")));
      img.src = reader.result;
    };
    reader.onerror = () => reject(new Error(I18n.t("settings.errors.invalidImage")));
    reader.readAsDataURL(file);
  });
}

function fitCoverScale(img) {
  return Math.max(CROP_VIEW / img.width, CROP_VIEW / img.height);
}

function clampCropOffset() {
  if (!cropState.img) return;
  const w = cropState.img.width * cropState.scale;
  const h = cropState.img.height * cropState.scale;
  const maxX = Math.max(0, (w - CROP_VIEW) / 2);
  const maxY = Math.max(0, (h - CROP_VIEW) / 2);
  cropState.offsetX = clamp(cropState.offsetX, -maxX, maxX);
  cropState.offsetY = clamp(cropState.offsetY, -maxY, maxY);
}

function drawCropPreview() {
  const canvas = document.getElementById("avatar-crop-canvas");
  if (!canvas || !cropState.img) return;
  const ctx = canvas.getContext("2d");
  if (!ctx) return;

  ctx.clearRect(0, 0, CROP_VIEW, CROP_VIEW);
  ctx.save();
  ctx.translate(CROP_VIEW / 2 + cropState.offsetX, CROP_VIEW / 2 + cropState.offsetY);
  ctx.scale(cropState.scale, cropState.scale);
  ctx.drawImage(cropState.img, -cropState.img.width / 2, -cropState.img.height / 2);
  ctx.restore();
}

function syncZoomSlider() {
  const slider = document.getElementById("avatar-crop-zoom");
  if (!slider) return;
  slider.min = String(cropState.minScale);
  slider.max = String(cropState.maxScale);
  slider.value = String(cropState.scale);
}

function setCropScale(scale) {
  cropState.scale = clamp(scale, cropState.minScale, cropState.maxScale);
  clampCropOffset();
  syncZoomSlider();
  drawCropPreview();
}

function setCropOpen(open) {
  const modal = document.getElementById("avatar-crop-modal");
  if (!modal) return;
  modal.hidden = !open;
  document.body.classList.toggle("avatar-crop-open", open);
  if (open) {
    document.addEventListener("keydown", onCropEscape);
    document.getElementById("avatar-crop-save")?.focus();
  } else {
    document.removeEventListener("keydown", onCropEscape);
    endCropDrag();
  }
}

function onCropEscape(e) {
  if (e.key === "Escape") cancelAvatarCrop();
}

function exportCroppedDataUrl() {
  clampCropOffset();
  const canvas = document.createElement("canvas");
  canvas.width = CROP_OUTPUT;
  canvas.height = CROP_OUTPUT;
  const ctx = canvas.getContext("2d");
  if (!ctx || !cropState.img) {
    throw new Error(I18n.t("settings.errors.invalidImage"));
  }

  const ratio = CROP_OUTPUT / CROP_VIEW;
  ctx.save();
  ctx.translate(
    CROP_OUTPUT / 2 + cropState.offsetX * ratio,
    CROP_OUTPUT / 2 + cropState.offsetY * ratio
  );
  ctx.scale(cropState.scale * ratio, cropState.scale * ratio);
  ctx.drawImage(
    cropState.img,
    -cropState.img.width / 2,
    -cropState.img.height / 2
  );
  ctx.restore();
  return canvas.toDataURL("image/jpeg", 0.88);
}

function cancelAvatarCrop() {
  const onCancel = cropState.onCancel;
  cropState.onComplete = null;
  cropState.onCancel = null;
  cropState.img = null;
  setCropOpen(false);
  onCancel?.();
}

async function saveAvatarCrop() {
  const saveBtn = document.getElementById("avatar-crop-save");
  if (saveBtn?.disabled) return;

  const onComplete = cropState.onComplete;
  const image = exportCroppedDataUrl();
  cropState.onComplete = null;
  cropState.onCancel = null;
  cropState.img = null;
  setCropOpen(false);

  if (!onComplete) return;
  if (saveBtn) saveBtn.disabled = true;
  try {
    await onComplete(image);
  } finally {
    if (saveBtn) saveBtn.disabled = false;
  }
}

function beginCropDrag(clientX, clientY) {
  if (!cropState.img) return;
  cropState.dragging = true;
  cropState.dragStartX = clientX;
  cropState.dragStartY = clientY;
  cropState.dragOriginX = cropState.offsetX;
  cropState.dragOriginY = cropState.offsetY;
  document.body.classList.add("avatar-crop-dragging");
}

function moveCropDrag(clientX, clientY) {
  if (!cropState.dragging) return;
  cropState.offsetX = cropState.dragOriginX + (clientX - cropState.dragStartX);
  cropState.offsetY = cropState.dragOriginY + (clientY - cropState.dragStartY);
  clampCropOffset();
  drawCropPreview();
}

function endCropDrag() {
  cropState.dragging = false;
  document.body.classList.remove("avatar-crop-dragging");
}

function onCropPointerDown(e) {
  if (!cropState.img) return;
  e.preventDefault();
  beginCropDrag(e.clientX, e.clientY);
  e.currentTarget.setPointerCapture?.(e.pointerId);
}

function onCropPointerMove(e) {
  if (!cropState.dragging) return;
  e.preventDefault();
  moveCropDrag(e.clientX, e.clientY);
}

function onCropPointerUp(e) {
  endCropDrag();
  e.currentTarget.releasePointerCapture?.(e.pointerId);
}

function bindCropDragSurface(el) {
  if (!el) return;
  el.addEventListener("pointerdown", onCropPointerDown);
  el.addEventListener("pointermove", onCropPointerMove);
  el.addEventListener("pointerup", onCropPointerUp);
  el.addEventListener("pointercancel", onCropPointerUp);

  el.addEventListener("mousedown", (e) => {
    if (e.button !== 0 || cropState.dragging) return;
    e.preventDefault();
    beginCropDrag(e.clientX, e.clientY);

    const onMouseMove = (ev) => {
      ev.preventDefault();
      moveCropDrag(ev.clientX, ev.clientY);
    };
    const onMouseUp = () => {
      endCropDrag();
      window.removeEventListener("mousemove", onMouseMove);
      window.removeEventListener("mouseup", onMouseUp);
    };
    window.addEventListener("mousemove", onMouseMove);
    window.addEventListener("mouseup", onMouseUp);
  });
}

function bindAvatarCropUI() {
  const canvas = document.getElementById("avatar-crop-canvas");
  const stage = document.getElementById("avatar-crop-stage");
  const slider = document.getElementById("avatar-crop-zoom");

  bindCropDragSurface(canvas);
  bindCropDragSurface(stage);

  slider?.addEventListener("input", (e) => {
    setCropScale(parseFloat(e.target.value));
  });

  const onWheel = (e) => {
    e.preventDefault();
    const factor = e.deltaY > 0 ? 0.92 : 1.08;
    setCropScale(cropState.scale * factor);
  };
  canvas?.addEventListener("wheel", onWheel, { passive: false });
  stage?.addEventListener("wheel", onWheel, { passive: false });

  document.getElementById("avatar-crop-cancel")?.addEventListener("click", cancelAvatarCrop);
  document.getElementById("avatar-crop-close")?.addEventListener("click", cancelAvatarCrop);
  document.getElementById("avatar-crop-backdrop")?.addEventListener("click", cancelAvatarCrop);
  document.getElementById("avatar-crop-save")?.addEventListener("click", () => {
    saveAvatarCrop().catch((err) => {
      document.dispatchEvent(
        new CustomEvent("avatarerror", { detail: { message: err.message } })
      );
    });
  });
}

function openAvatarCropModal(file, { onComplete, onCancel } = {}) {
  validateImageFile(file);
  return loadImageFromFile(file).then((img) => {
    cropState.img = img;
    cropState.minScale = fitCoverScale(img);
    cropState.maxScale = cropState.minScale * 4;
    cropState.scale = cropState.minScale * 1.2;
    cropState.offsetX = 0;
    cropState.offsetY = 0;
    cropState.onComplete = onComplete || null;
    cropState.onCancel = onCancel || null;
    clampCropOffset();
    syncZoomSlider();
    drawCropPreview();
    setCropOpen(true);
  });
}

document.addEventListener("DOMContentLoaded", bindAvatarCropUI);

window.AvatarCrop = {
  open: openAvatarCropModal,
  cancel: cancelAvatarCrop,
};