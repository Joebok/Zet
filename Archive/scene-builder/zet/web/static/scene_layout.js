import * as THREE from "three";
import { OrbitControls } from "three/addons/controls/OrbitControls.js";
import { TransformControls } from "three/addons/controls/TransformControls.js";
import { backgroundCrop, groundFrame, distanceForGroundJoin } from "./scene_layout_framing.js";

const dialog = document.querySelector("#scene-layout-dialog");
const canvas = document.querySelector("#scene-layout-canvas");
const status = document.querySelector("#scene-layout-status");
const warningBox = document.querySelector("#scene-layout-warnings");
const preview = document.querySelector("#scene-layout-preview");
const selector = document.querySelector("#scene-layout-element");
const cameraLock = document.querySelector("#scene-layout-camera-lock");
const migrationConfirm = document.querySelector("#scene-layout-migration-confirm");
const snapToggle = document.querySelector("#scene-layout-snap");
const INCH_M = 0.0254;
const FT_M = 0.3048;
const material = new THREE.MeshStandardMaterial({ color: 0x9ea8b1, roughness: 0.75, metalness: 0.03 });
const headMaterial = new THREE.MeshStandardMaterial({ color: 0xc5cbd0, roughness: 0.72 });
const faceMaterial = new THREE.MeshBasicMaterial({ color: 0x18232e });
const pawns = new Map();
let layout = null;
let elements = [];
let composition = { pawns: [], groups: [] };
let workspaceTarget = "main";
let workspaceParents = { main: "" };
const workspaceStates = new Map();
const groupDimensions = new Map();
let selectedId = "";
let lastPreviewRequest = 0;
let undoStack = [];
let redoStack = [];
let beforeDrag = "";
let viewMode = "stage";
let backgroundOptions = [];
let backgroundImage = null;
let backgroundSourceKey = "";
let imageRequest = 0;
let framingDrag = null;
let wheelSnapshot = "";
let wheelTimer = 0;
let sliderSnapshot = "";
let sourceTexture = null;
let framedTexture = null;
const framedCanvas = document.createElement("canvas");
let backdropSize = { width: 8, height: 4.5 };
const backgroundId = "__background";
const adjust = document.querySelector("#scene-layout-adjust");
const cameraFrame = document.querySelector("#scene-layout-camera-frame");
const backgroundControls = document.querySelector("#scene-layout-background-controls");

const renderer = new THREE.WebGLRenderer({ canvas, antialias: true, alpha: false });
renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2));
renderer.setClearColor(0x111922);
renderer.outputColorSpace = THREE.SRGBColorSpace;
const scene = new THREE.Scene();
scene.background = new THREE.Color(0x111922);
scene.add(new THREE.HemisphereLight(0xdde9f5, 0x303943, 2.1));
const keyLight = new THREE.DirectionalLight(0xffffff, 2.2);
keyLight.position.set(5, 9, 7);
scene.add(keyLight);
const editorCamera = new THREE.PerspectiveCamera(48, 1, 0.02, 2000);
editorCamera.layers.enable(1);
const renderCamera = new THREE.PerspectiveCamera(50, 16 / 9, .02, 2000);
const backgroundScene = new THREE.Scene();
const imageCamera = new THREE.OrthographicCamera(-1, 1, 1, -1, .1, 10);
imageCamera.position.z = 1;
const imageMaterial = new THREE.MeshBasicMaterial({ color: 0xffffff, depthTest: false, depthWrite: false });
const imageQuad = new THREE.Mesh(new THREE.PlaneGeometry(2, 2), imageMaterial);
imageQuad.visible = false;
backgroundScene.add(imageQuad);
const backdrop = new THREE.Group();
backdrop.name = "background-display";
scene.add(backdrop);
editorCamera.position.set(7, 6, 9);
const orbit = new OrbitControls(editorCamera, renderer.domElement);
orbit.target.set(0, 1, 0);
orbit.enableDamping = true;
orbit.dampingFactor = 0.08;
orbit.maxPolarAngle = Math.PI * 0.495;
const floor = new THREE.GridHelper(30.48, 100, 0x7893aa, 0x354653);
floor.position.y = 0;
scene.add(floor);
const axes = new THREE.AxesHelper(1.524);
scene.add(axes);
floor.layers.set(1);
axes.layers.set(1);
floor.position.y = .006;
const groundMesh = new THREE.Mesh(new THREE.PlaneGeometry(2000, 2000),
  new THREE.MeshBasicMaterial({ color: new THREE.Color(185 / 255, 176 / 255, 160 / 255).convertSRGBToLinear(), side: THREE.DoubleSide }));
groundMesh.name = "foreground-ground";
scene.add(groundMesh);
const contactShadows = new THREE.Group();
contactShadows.name = "ground-contact-shadows";
scene.add(contactShadows);
const shadowCanvas = document.createElement("canvas");
shadowCanvas.width = shadowCanvas.height = 64;
const shadowContext = shadowCanvas.getContext("2d");
const gradient = shadowContext.createRadialGradient(32, 32, 2, 32, 32, 32);
gradient.addColorStop(0, "rgba(0,0,0,.32)"); gradient.addColorStop(1, "rgba(0,0,0,0)");
shadowContext.fillStyle = gradient; shadowContext.fillRect(0, 0, 64, 64);
const shadowTexture = new THREE.CanvasTexture(shadowCanvas);
const cameraHelper = new THREE.Group();
scene.add(cameraHelper);
const transform = new TransformControls(editorCamera, renderer.domElement);
scene.add(transform.getHelper());
transform.setMode("translate");
transform.showY = false;
transform.addEventListener("dragging-changed", (event) => {
  orbit.enabled = !event.value;
  if (event.value) beforeDrag = JSON.stringify(layout);
  else if (beforeDrag && beforeDrag !== JSON.stringify(layout)) pushHistory(beforeDrag);
});
transform.addEventListener("objectChange", () => {
  if (!selectedId || !layout) return;
  const pawn = pawnData(selectedId);
  const object = pawns.get(selectedId);
  if (!pawn || !object) return;
  const step = snapToggle.checked ? parseImperial(document.querySelector("#scene-layout-grid").value) : 0;
  if (step > 0) {
    object.position.x = Math.round(object.position.x / step) * step;
    object.position.z = Math.round(object.position.z / step) * step;
  }
  pawn.position = [object.position.x, pawn.position[1], object.position.z];
  clampPawnToBackdrop(pawn);
  object.position.fromArray(pawn.position);
  if (dialog.dataset.transformMode === "rotate") {
    pawn.body_yaw = (-THREE.MathUtils.radToDeg(object.rotation.y) % 360 + 360) % 360;
    document.querySelector("#scene-layout-body-yaw").value = pawn.body_yaw;
  }
  document.querySelector("#scene-layout-y").value = formatImperial(pawn.position[1]);
  document.querySelector("#scene-layout-x").value = formatImperial(pawn.position[0]);
  document.querySelector("#scene-layout-z").value = formatImperial(pawn.position[2]);
  updateRotationDials();
  updateBackgroundDisplay();
  updateDirty();
  requestPreview();
});
const raycaster = new THREE.Raycaster();
const pointer = new THREE.Vector2();
let cameraFrustum = null;
let selectionOutline = null;
const rotationDials = new THREE.Group();
rotationDials.name = "rotation-dials";
rotationDials.visible = false;
scene.add(rotationDials);
const dialBands = [
  { kind: "head", radius: .62, color: 0x63c5da },
  { kind: "both", radius: .86, color: 0xb69aff },
  { kind: "body", radius: 1.1, color: 0xf6b34f },
].map(({ kind, radius, color }) => {
  const mesh = new THREE.Mesh(new THREE.RingGeometry(radius - .08, radius + .08, 96),
    new THREE.MeshBasicMaterial({ color, side: THREE.DoubleSide, transparent: true, opacity: .38, depthTest: false, depthWrite: false }));
  mesh.name = `dial-${kind}`;
  mesh.rotation.x = -Math.PI / 2;
  mesh.renderOrder = 10;
  mesh.userData.dialKind = kind;
  mesh.userData.radius = radius;
  const marker = new THREE.Mesh(new THREE.BoxGeometry(.05, .02, .16),
    new THREE.MeshBasicMaterial({ color, depthTest: false, depthWrite: false }));
  marker.renderOrder = 11;
  rotationDials.add(mesh, marker);
  return { kind, radius, mesh, marker };
});
let dialDrag = null;
const dialPlane = new THREE.Plane(new THREE.Vector3(0, 1, 0));
const dialPoint = new THREE.Vector3();

function updateRotationDials() {
  const pawn = pawnData();
  const object = pawns.get(selectedId);
  rotationDials.visible = viewMode === "stage" && adjust.value !== "background" && !!(pawn && object);
  if (!rotationDials.visible) return;
  rotationDials.position.copy(object.position);
  rotationDials.position.y += .025;
  rotationDials.scale.setScalar(Math.max(1, Math.max(pawn.dimensions.width, pawn.dimensions.depth) * .9));
  const hasHead = !!object.getObjectByName("head-facing");
  for (const band of dialBands) {
    band.mesh.visible = band.marker.visible = band.kind === "body" || hasHead;
    const yaw = THREE.MathUtils.degToRad(pawn.body_yaw + (band.kind === "head" ? pawn.head_yaw || 0 : 0));
    band.marker.position.set(Math.sin(yaw) * band.radius, .01, -Math.cos(yaw) * band.radius);
    band.marker.rotation.y = -yaw;
  }
  rotationDials.updateMatrixWorld(true);
}

function pointRay(event) {
  const bounds = canvas.getBoundingClientRect();
  pointer.set((event.clientX - bounds.left) / bounds.width * 2 - 1, -((event.clientY - bounds.top) / bounds.height) * 2 + 1);
  raycaster.setFromCamera(pointer, editorCamera);
}

function dialHit(event) {
  if (viewMode !== "stage" || adjust.value === "background") return null;
  if (!rotationDials.visible) return null;
  pointRay(event);
  // Keep the movement handles usable where they overlap a dial.
  transform.pointerHover(pointer);
  if (transform.mode === "translate" && transform.axis) return null;
  return raycaster.intersectObjects(dialBands.filter((band) => band.mesh.visible).map((band) => band.mesh), false)[0]?.object || null;
}

function dialAngle(event) {
  pointRay(event);
  dialPlane.constant = -rotationDials.position.y;
  if (!raycaster.ray.intersectPlane(dialPlane, dialPoint)) return null;
  const offset = dialPoint.sub(rotationDials.position);
  if (Math.hypot(offset.x, offset.z) < .01) return null;
  return Math.atan2(offset.x, -offset.z);
}

function highlightDial(kind = "") {
  for (const band of dialBands) band.mesh.material.opacity = band.kind === kind ? .78 : .38;
  canvas.style.cursor = dialDrag ? "grabbing" : kind ? "grab" : "";
}

function finishDialDrag(cancel = false) {
  if (!dialDrag) return;
  const drag = dialDrag;
  dialDrag = null;
  orbit.enabled = drag.orbitEnabled;
  transform.enabled = drag.transformEnabled;
  if (canvas.hasPointerCapture(drag.pointerId)) canvas.releasePointerCapture(drag.pointerId);
  if (cancel) {
    layout = JSON.parse(drag.snapshot);
    rebuildPawns();
  } else pushHistory(drag.snapshot);
  highlightDial();
  updateDirty();
  renderInspector();
  schedulePreview();
}

canvas.addEventListener("pointerdown", (event) => {
  if (event.button !== 0 || dialDrag || transform.dragging) return;
  const hit = dialHit(event);
  const angle = hit ? dialAngle(event) : null;
  if (angle === null) return;
  event.preventDefault();
  event.stopImmediatePropagation();
  const pawn = pawnData();
  dialDrag = { kind: hit.userData.dialKind, pointerId: event.pointerId, angle, delta: 0,
    bodyYaw: pawn.body_yaw, headYaw: pawn.head_yaw || 0, snapshot: JSON.stringify(layout),
    orbitEnabled: orbit.enabled, transformEnabled: transform.enabled };
  orbit.enabled = transform.enabled = false;
  canvas.setPointerCapture(event.pointerId);
  highlightDial(dialDrag.kind);
}, true);

canvas.addEventListener("pointermove", (event) => {
  if (!dialDrag) {
    if (!event.buttons && !transform.dragging) highlightDial(dialHit(event)?.userData.dialKind);
    return;
  }
  if (event.pointerId !== dialDrag.pointerId) return;
  event.preventDefault();
  event.stopImmediatePropagation();
  const angle = dialAngle(event);
  if (angle === null) return;
  // Accumulate small steps so crossing 0/360 does not jump or reverse.
  dialDrag.delta += THREE.MathUtils.radToDeg(Math.atan2(Math.sin(angle - dialDrag.angle), Math.cos(angle - dialDrag.angle)));
  dialDrag.angle = angle;
  if (Math.abs(dialDrag.delta) < .01) return;
  const pawn = pawnData();
  const wrap = (degrees) => ((Math.round(degrees * 100) % 36000 + 36000) % 36000) / 100;
  const delta = dialDrag.delta;
  pawn.body_yaw = wrap(dialDrag.bodyYaw + (dialDrag.kind === "head" ? 0 : delta));
  const headDelta = dialDrag.kind === "head" ? delta : dialDrag.kind === "body" ? -delta : 0;
  const object = pawns.get(selectedId);
  const head = object.getObjectByName("head-facing");
  if (head) pawn.head_yaw = Math.round((wrap(dialDrag.headYaw + headDelta + 180) - 180) * 100) / 100;
  pawn.look_at = "";
  object.rotation.y = -THREE.MathUtils.degToRad(pawn.body_yaw);
  if (head) head.rotation.y = -THREE.MathUtils.degToRad(pawn.head_yaw);
  document.querySelector("#scene-layout-body-yaw").value = Math.round(pawn.body_yaw * 100) / 100;
  document.querySelector("#scene-layout-head-yaw").value = Math.round(pawn.head_yaw * 100) / 100;
  document.querySelector("#scene-layout-look-at").value = "";
  updateRotationDials();
  updateDirty();
}, true);

for (const type of ["pointerup", "pointercancel"]) canvas.addEventListener(type, (event) => {
  if (!dialDrag || event.pointerId !== dialDrag.pointerId) return;
  event.stopImmediatePropagation();
  finishDialDrag(type === "pointercancel");
}, true);
canvas.addEventListener("lostpointercapture", (event) => { if (event.pointerId === dialDrag?.pointerId) finishDialDrag(); });
canvas.addEventListener("pointerleave", () => { if (!dialDrag) highlightDial(); });
dialog.addEventListener("close", () => finishDialDrag());

function parseImperial(raw) {
  const value = String(raw || "").trim();
  const number = String.raw`(\d+(?:\.\d+)?|\d+\s+\d+\s*\/\s*\d+|\d+\s*\/\s*\d+)`;
  const feetInches = new RegExp(String.raw`^\s*(-?\d+)\s*(?:ft|feet|foot|')\s*(${number})?\s*(?:in|inches|inch|")?\s*$`, "i").exec(value);
  const inchOnly = new RegExp(String.raw`^\s*(${number})\s*(?:in|inches|inch|")\s*$`, "i").exec(value);
  const parse = (part) => {
    if (part.includes("/")) {
      const [whole, numerator] = part.trim().split(/\s+/);
      if (numerator) return Number(whole) + Number(numerator.split("/")[0]) / Number(numerator.split("/")[1]);
      return Number(part.split("/")[0].trim()) / Number(part.split("/")[1].trim());
    }
    return Number(part);
  };
  if (feetInches) {
    const feet = Number(feetInches[1]);
    const sign = feet < 0 || /^\s*-/.test(value) ? -1 : 1;
    return (feet * 12 + sign * (feetInches[2] ? parse(feetInches[2]) : 0)) * INCH_M;
  }
  if (inchOnly) return parse(inchOnly[1]) * INCH_M;
  const direct = /^\s*(-?(?:\d+(?:\.\d+)?|\d+\s*\/\s*\d+))\s*$/.exec(value);
  if (direct) return parse(direct[1]) * FT_M;
  throw new Error(`Enter a dimension in feet and inches, such as 5 ft 8 in: ${value}`);
}

function formatImperial(meters) {
  const total = meters / INCH_M;
  const sign = total < 0 ? "-" : "";
  let ticks = Math.round(Math.abs(total) * 16);
  let feet = Math.floor(ticks / (12 * 16));
  ticks -= feet * 12 * 16;
  if (ticks >= 12 * 16) { feet += 1; ticks = 0; }
  const whole = Math.floor(ticks / 16);
  const sixteenths = ticks % 16;
  const fraction = sixteenths ? ` ${simplifyFraction(sixteenths, 16)}` : "";
  return `${sign}${feet} ft ${whole}${fraction} in`;
}

function simplifyFraction(top, bottom) {
  let a = top, b = bottom;
  while (b) [a, b] = [b, a % b];
  return `${top / a}/${bottom / a}`;
}

function current() { return window.zetSceneLayout?.current(); }
function pawnData(id = selectedId) { return layout?.pawns?.find((item) => item.element_id === id); }
function cameraData() { return layout?.cameras?.find((item) => item.id === layout.active_camera_id); }
function updateDirty() { window.zetSceneLayout?.setLayout(layout); }

function setInspectorValue(input, value) {
  if (input && document.activeElement !== input) input.value = value;
}

function pushHistory(snapshot = JSON.stringify(layout)) {
  if (!snapshot || snapshot === JSON.stringify(layout)) return;
  undoStack.push(snapshot);
  if (undoStack.length > 80) undoStack.shift();
  redoStack = [];
  updateHistoryButtons();
}

function updateHistoryButtons() {
  dialog.querySelector('[data-layout-action="undo"]').disabled = !undoStack.length;
  dialog.querySelector('[data-layout-action="redo"]').disabled = !redoStack.length;
}

function checkpoint(action) {
  const before = JSON.stringify(layout);
  action();
  if (before !== JSON.stringify(layout)) pushHistory(before);
  updateDirty();
  rebuildPawns();
  renderInspector();
  requestPreview();
}

function makePawn(element, data) {
  const group = new THREE.Group();
  group.name = data.element_id;
  group.userData.elementId = data.element_id;
  const { width, height, depth } = data.dimensions;
  const box = element?.element_type === "Prop";
  const groupTarget = (current()?.data?.subscenes || []).find((target) => target.enabled && target.kind === "element" && target.anchor_element_id === element?.id);
  if (groupTarget) {
    group.userData.subsceneId = groupTarget.id;
    group.userData.group = true;
  } else if (box) {
    const mesh = new THREE.Mesh(new THREE.BoxGeometry(width, height, depth), material);
    mesh.position.y = height / 2;
    mesh.userData.elementId = data.element_id;
    group.add(mesh);
  } else {
    const torso = new THREE.Mesh(new THREE.CylinderGeometry(width * .17, width * .27, height * .43, 10), material);
    torso.position.y = height * .57;
    torso.userData.elementId = data.element_id;
    group.add(torso);
    const headRadius = Math.min(width * .21, height * .085, .17);
    const head = new THREE.Group();
    head.name = "head-facing";
    head.position.set(0, height * .88, 0);
    head.rotation.set(THREE.MathUtils.degToRad(data.head_pitch || 0), -THREE.MathUtils.degToRad(data.head_yaw || 0), 0, "YXZ");
    head.add(new THREE.Mesh(new THREE.SphereGeometry(headRadius, 16, 12), headMaterial));
    for (const side of [-1, 1]) {
      const eye = new THREE.Mesh(new THREE.SphereGeometry(headRadius * .13, 8, 8), faceMaterial);
      eye.position.set(side * headRadius * .35, headRadius * .2, -headRadius * .91);
      head.add(eye);
    }
    const nose = new THREE.Mesh(new THREE.ConeGeometry(headRadius * .2, headRadius * .65, 8), headMaterial);
    nose.rotation.x = -Math.PI / 2;
    nose.position.z = -headRadius * 1.15;
    head.add(nose);
    const gazeLength = Math.max(width * .7, headRadius * 3);
    const gaze = new THREE.ArrowHelper(new THREE.Vector3(0, 0, -1), new THREE.Vector3(0, 0, -headRadius * 1.5), gazeLength, 0x63c5da, gazeLength * .25, gazeLength * .16);
    gaze.name = "head-direction";
    head.add(gaze);
    group.add(head);
    for (const side of [-1, 1]) {
      const leg = new THREE.Mesh(new THREE.CylinderGeometry(width * .07, width * .075, height * .38, 8), material);
      leg.position.set(side * width * .095, height * .19, 0);
      leg.userData.elementId = data.element_id;
      group.add(leg);
      const arm = new THREE.Mesh(new THREE.CylinderGeometry(width * .055, width * .075, height * .35, 8), material);
      arm.position.set(side * width * .32, height * .58, 0);
      arm.rotation.z = -side * .12;
      arm.userData.elementId = data.element_id;
      group.add(arm);
    }
    const arrowLength = Math.max(width * 1.5, depth * .9, .45);
    const arrow = new THREE.ArrowHelper(new THREE.Vector3(0, 0, -1), new THREE.Vector3(0, height * .48, 0), arrowLength, 0xf6b34f, arrowLength * .3, arrowLength * .25);
    arrow.name = "body-direction";
    const shaft = new THREE.Mesh(new THREE.CylinderGeometry(arrowLength * .045, arrowLength * .045, arrowLength * .7, 8), arrow.cone.material);
    shaft.position.y = arrowLength * .35;
    arrow.add(shaft);
    group.add(arrow);
  }
  const label = makeLabel(element?.display_name || data.element_id, data.provisional_height);
  label.position.set(0, height + .18, 0);
  group.add(label);
  group.position.set(...data.position);
  // Stored yaw turns -Z toward +X, matching Look at and the camera preview.
  group.rotation.y = -THREE.MathUtils.degToRad(data.body_yaw);
  for (const child of [label, group.getObjectByName("body-direction"), group.getObjectByName("head-direction")]) {
    child?.traverse((node) => node.layers.set(1));
  }
  return group;
}

function makeLabel(text, provisional) {
  const element = document.createElement("canvas");
  const ctx = element.getContext("2d");
  ctx.font = "600 30px Segoe UI, sans-serif";
  const width = Math.ceil(ctx.measureText(text).width) + 24;
  element.width = width;
  element.height = 46;
  ctx.font = "600 30px Segoe UI, sans-serif";
  ctx.fillStyle = "rgba(12,18,24,.8)";
  ctx.fillRect(0, 0, width, 46);
  ctx.fillStyle = provisional ? "#ffcd7c" : "#ffffff";
  ctx.fillText(text, 12, 33);
  const texture = new THREE.CanvasTexture(element);
  const sprite = new THREE.Sprite(new THREE.SpriteMaterial({ map: texture, depthTest: false, transparent: true }));
  sprite.scale.set(Math.max(.6, text.length * .055), .24, 1);
  return sprite;
}

function rebuildPawns() {
  for (const pawn of pawns.values()) {
    scene.remove(pawn);
    pawn.traverse((node) => {
      node.geometry?.dispose();
      if (node.isSprite) { node.material.map?.dispose(); node.material.dispose(); }
    });
  }
  pawns.clear();
  groupDimensions.clear();
  const targetId = current()?.activeTarget || "main";
  const definitions = current()?.data?.subscenes || [];
  const layoutElements = new Map((layout?.pawns || []).map((item) => [item.element_id, elements.find((candidate) => candidate.id === item.element_id)]));
  const anchors = new Map((layout?.pawns || []).flatMap((item) => {
    const definition = definitions.find((target) => target.enabled && target.kind === "element" && target.anchor_element_id === item.element_id);
    return definition ? [[definition.id, item]] : [];
  }));
  for (const item of layout?.pawns || []) {
    const element = elements.find((candidate) => candidate.id === item.element_id);
    const object = makePawn(element, item);
    scene.add(object);
    pawns.set(item.element_id, object);
  }
  for (const [target, anchor] of anchors) {
    const root = pawns.get(anchor.element_id);
    if (!root) continue;
    const descendantTargets = new Set([target]);
    let changed = true;
    while (changed) {
      changed = false;
      for (const definition of definitions) {
        if (definition.kind !== "element" || descendantTargets.has(definition.id)) continue;
        const owner = elements.find((item) => item.id === definition.anchor_element_id)?.subscene_id || "main";
        if (descendantTargets.has(owner)) { descendantTargets.add(definition.id); changed = true; }
      }
    }
    const anchorYaw = anchor.body_yaw || 0;
    const groupMembers = composition.pawns.filter((pawn) => descendantTargets.has(pawn.subscene_id || ""));
    for (const pawn of groupMembers) {
      const element = elements.find((item) => item.id === pawn.element_id);
      if (!element) continue;
      const member = makePawn(element, pawn);
      member.name = `group-member-${pawn.element_id}`;
      const worldOffset = new THREE.Vector3(pawn.position[0] - anchor.position[0], pawn.position[1] - anchor.position[1], pawn.position[2] - anchor.position[2]);
      worldOffset.applyAxisAngle(new THREE.Vector3(0, 1, 0), THREE.MathUtils.degToRad(anchorYaw));
      member.position.copy(worldOffset);
      member.rotation.y = -THREE.MathUtils.degToRad(pawn.body_yaw - anchorYaw);
      root.add(member);
      member.traverse((node) => { node.userData.elementId = anchor.element_id; });
    }
    root.children.filter((item) => item.type === "Mesh").forEach((item) => { item.visible = false; });
    const bounds = new THREE.Box3();
    root.children.filter((item) => item.userData.elementId === anchor.element_id && item !== root.children.find((child) => child.isSprite)).forEach((item) => bounds.expandByObject(item));
    if (!bounds.isEmpty()) groupDimensions.set(anchor.element_id, bounds.getSize(new THREE.Vector3()));
    root.userData.groupDimensions = groupDimensions.get(anchor.element_id) || new THREE.Vector3();
  }
  updateCameraHelper();
  updateBackgroundDisplay();
  attachSelection();
}

function updateCameraHelper() {
  if (cameraFrustum) {
    scene.remove(cameraFrustum);
    cameraFrustum.geometry.dispose();
    cameraFrustum.material.dispose();
  }
  const camera = cameraData();
  if (!camera) return;
  const frustum = new THREE.PerspectiveCamera(camera.vertical_fov, sceneAspect(), .15, 30);
  frustum.position.fromArray(camera.position);
  frustum.lookAt(...camera.target);
  cameraFrustum = new THREE.CameraHelper(frustum);
  cameraFrustum.setColors(0x63c5da, 0x63c5da, 0x63c5da, 0x63c5da, 0x63c5da);
  cameraFrustum.layers.set(1);
  scene.add(cameraFrustum);
}

function attachSelection() {
  const selected = pawns.get(selectedId);
  if (selected && viewMode === "stage" && adjust.value !== "background") transform.attach(selected);
  else transform.detach();
  if (selectionOutline) {
    scene.remove(selectionOutline);
    selectionOutline.geometry.dispose();
    selectionOutline.material.dispose();
    selectionOutline = null;
  }
  if (selected?.userData.group && viewMode === "stage") {
    selectionOutline = new THREE.BoxHelper(selected, 0x63c5da);
    selectionOutline.layers.set(1);
    scene.add(selectionOutline);
  }
  transform.setMode(dialog.dataset.transformMode || "translate");
  transform.showY = dialog.dataset.transformMode === "rotate";
  updateRotationDials();
}

function renderInspector() {
  const pawn = pawnData();
  const camera = cameraData();
  selector.replaceChildren(new Option("Background & foreground", backgroundId), ...(layout?.pawns || []).map((item) => {
    const element = elements.find((candidate) => candidate.id === item.element_id);
    return new Option(`${element?.display_name || item.element_id}${item.provisional_height ? " · height needed" : ""}`, item.element_id);
  }));
  selector.value = selectedId;
  const selectedElement = elements.find((item) => item.id === selectedId);
  const selectedGroup = (current()?.data?.subscenes || []).find((item) => item.enabled && item.kind === "element" && item.anchor_element_id === selectedId);
  const parentButton = dialog.querySelector('[data-layout-action="parent-workspace"]');
  const contentsButton = dialog.querySelector('[data-layout-action="edit-contents"]');
  parentButton.hidden = workspaceTarget === "main";
  contentsButton.hidden = !selectedGroup || workspaceTarget === selectedGroup.id;
  contentsButton.textContent = selectedGroup ? `Edit ${selectedGroup.name || "group"} contents` : "Edit contents";
  document.querySelector("#scene-layout-breadcrumb").textContent = workspaceTarget === "main" ? "Full Scene" : `Full Scene › ${(current()?.data?.subscenes || []).find((item) => item.id === workspaceTarget)?.name || workspaceTarget}`;
  document.querySelector("#scene-layout-title").textContent = workspaceTarget === "main" ? "3D Layout · Full Scene" : `3D Layout · ${(current()?.data?.subscenes || []).find((item) => item.id === workspaceTarget)?.name || workspaceTarget}`;
  const backgroundSelected = selectedId === backgroundId;
  const isGroup = Boolean(selectedGroup);
  backgroundControls.hidden = !backgroundSelected;
  document.querySelector("#scene-layout-size-controls").hidden = backgroundSelected;
  document.querySelector("#scene-layout-facing-controls").hidden = backgroundSelected || isGroup;
  for (const fieldset of dialog.querySelectorAll('.scene-layout-inspector > fieldset:not(#scene-layout-background-controls)')) fieldset.hidden = backgroundSelected;
  renderBackgroundInspector();
  if (pawn) {
    if (isGroup) {
      const dimensions = groupDimensions.get(selectedId) || new THREE.Vector3();
      for (const [id, value] of [["scene-layout-height", dimensions.y], ["scene-layout-occupied-height", dimensions.y], ["scene-layout-width", dimensions.x], ["scene-layout-depth", dimensions.z]]) {
        const input = document.getElementById(id); input.value = formatImperial(value); input.readOnly = true;
      }
      for (const id of ["scene-layout-height", "scene-layout-occupied-height", "scene-layout-width", "scene-layout-depth"]) document.getElementById(id).readOnly = true;
      status.textContent = `Subscene group · ${formatImperial(dimensions.x)} wide × ${formatImperial(dimensions.y)} high × ${formatImperial(dimensions.z)} deep. Member sizes stay fixed.`;
    } else {
      for (const id of ["scene-layout-height", "scene-layout-occupied-height", "scene-layout-width", "scene-layout-depth"]) document.getElementById(id).readOnly = false;
    const lookAt = document.querySelector("#scene-layout-look-at");
    lookAt.replaceChildren(new Option("Set facing manually", ""), new Option("Camera", "camera"),
      ...elements.filter((item) => item.id !== selectedId && item.element_type !== "Backdrop").map((item) => new Option(item.display_name || item.id, item.id)));
    for (const [axis, id] of [[0, "scene-layout-x"], [1, "scene-layout-y"], [2, "scene-layout-z"]]) {
      setInspectorValue(document.getElementById(id), formatImperial(pawn.position[axis]));
    }
    setInspectorValue(document.querySelector("#scene-layout-height"), formatImperial(pawn.stature_m));
    setInspectorValue(document.querySelector("#scene-layout-occupied-height"), formatImperial(pawn.dimensions.height));
    for (const dimension of ["width", "depth"]) setInspectorValue(document.getElementById(`scene-layout-${dimension}`), formatImperial(pawn.dimensions[dimension]));
    for (const [key, id] of [["body_yaw", "scene-layout-body-yaw"], ["head_yaw", "scene-layout-head-yaw"], ["head_pitch", "scene-layout-head-pitch"]]) {
      setInspectorValue(document.getElementById(id), pawn[key] || 0);
    }
    document.querySelector("#scene-layout-look-at").value = pawn.look_at || "";
    status.textContent = `${pawn.provisional_height ? "Provisional height — enter the measured height before rendering. " : ""}Stature ${formatImperial(pawn.stature_m)}; occupied ${formatImperial(pawn.dimensions.height)}.`;
    }
  } else status.textContent = adjust.value === "background"
    ? "Background: drag to frame; wheel to zoom. The crop stays fixed as the camera moves."
    : viewMode === "camera" ? `Camera: drag to ${adjust.value === "aim" ? "aim" : "move"}; wheel to dolly. The background crop stays fixed.`
      : "Choose Adjust background to drag and zoom the image, or use Camera view to compose the shot.";
  if (camera) {
    for (const point of ["position", "target"]) for (let axis = 0; axis < 3; axis += 1) {
      dialog.querySelector(`[data-camera-point="${point}"][data-axis="${axis}"]`).value = formatImperial(camera[point][axis]);
    }
    document.querySelector("#scene-layout-fov").value = camera.vertical_fov;
    document.querySelector("#scene-layout-lens").value = camera.vertical_fov;
  }
  const cameraInputs = dialog.querySelectorAll("[data-camera-point], #scene-layout-fov, #scene-layout-lens, [data-layout-action^='dolly-']");
  for (const input of cameraInputs) input.disabled = cameraLock.checked;
  dialog.querySelector('[data-layout-action="camera-from-view"]').disabled = cameraLock.checked;
  migrationConfirm.checked = !layout?.migration_review_required;
}

function fitRenderer() {
  const bounds = canvas.getBoundingClientRect();
  const width = Math.max(1, Math.floor(bounds.width));
  const height = Math.max(1, Math.floor(bounds.height));
  const size = renderer.getSize(new THREE.Vector2());
  if (size.x !== width || size.y !== height) renderer.setSize(width, height, false);
  editorCamera.aspect = width / height;
  editorCamera.updateProjectionMatrix();
  updateFrame();
}

function animate() {
  if (!dialog.open) return;
  requestAnimationFrame(animate);
  if (!dialDrag && orbit.enabled) orbit.update();
  const camera = editorCamera;
  for (const object of pawns.values()) object.children.forEach((child) => { if (child.isSprite) child.quaternion.copy(camera.quaternion); });
  selectionOutline?.update();
  renderer.setScissorTest(false);
  renderer.setViewport(0, 0, canvas.clientWidth, canvas.clientHeight);
  renderer.autoClear = true;
  if (viewMode === "stage") {
    scene.background = new THREE.Color(0x111922);
    renderer.render(scene, editorCamera);
  } else {
    scene.background = null;
    renderer.clear();
    const frame = frameBounds();
    renderer.setViewport(frame.x, frame.y, frame.width, frame.height);
    renderer.setScissor(frame.x, frame.y, frame.width, frame.height);
    renderer.setScissorTest(true);
    renderer.autoClear = false;
    syncRenderCamera();
    renderer.render(backgroundScene, imageCamera);
    renderer.clearDepth();
    renderer.render(scene, renderCamera);
  }
}

function updateCameraPoint(point, axis, value) {
  const camera = cameraData();
  if (!camera || cameraLock.checked) return;
  const meters = parseImperial(value);
  camera[point][axis] = meters;
  updateCameraHelper();
  updateDirty();
}

async function requestPreview() {
  const session = current();
  if (!layout || !session?.data || !dialog.open) return;
  const request = ++lastPreviewRequest;
  try {
    const response = await fetch(`/api/stories/${encodeURIComponent(session.storySlug)}/scenes/${encodeURIComponent(session.sceneSlug)}/builder/3d-layout/preview?target_id=${encodeURIComponent(workspaceTarget)}`, {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ ...session.data, layout_3d: layout }),
    });
    const result = await response.json();
    if (!response.ok) throw new Error(result.detail || "Camera preview failed.");
    if (request !== lastPreviewRequest) return;
    preview.src = `data:image/png;base64,${result.guidance_png_base64}`;
    preview.hidden = false;
    composition = result.composition || composition;
    workspaceParents = composition.parents || workspaceParents;
    rebuildPawns();
    renderInspector();
    backgroundOptions = result.background_options || [];
    renderBackgroundInspector();
    await loadBackground(result);
    if (request !== lastPreviewRequest) return;
    const details = [...(layout.migration_notices || []), ...(result.warnings || []), ...(result.provisional_elements || []).map((id) => `${id}: height is provisional.`)];
    if (result.migration_review_required) details.unshift("Imported placements are approximate. Review them and confirm before guided rendering.");
    warningBox.textContent = details.join("\n");
  } catch (error) {
    if (request === lastPreviewRequest) warningBox.textContent = error.message;
  }
}

let previewTimer = 0;
function schedulePreview() {
  window.clearTimeout(previewTimer);
  previewTimer = window.setTimeout(requestPreview, 180);
}

async function openLayout() {
  const session = current();
  if (!session?.data || !session.storySlug || !session.sceneSlug) return;
  try {
    {
      const targetId = session.activeTarget || "main";
      workspaceTarget = targetId;
      const response = await fetch(`/api/stories/${encodeURIComponent(session.storySlug)}/scenes/${encodeURIComponent(session.sceneSlug)}/builder/3d-layout/draft?target_id=${encodeURIComponent(targetId)}`, {
        method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(session.data),
      });
      const result = await response.json();
      if (!response.ok) throw new Error(result.detail || "Unable to initialize 3D layout.");
      layout = window.zetSceneLayout.drafts.get(targetId) || result.layout_3d;
      window.zetSceneLayout.setLayout(layout);
    }
    elements = session.data.scene_elements || [];
    selectedId = layout.pawns[0]?.element_id || backgroundId;
    viewMode = "stage";
    adjust.value = "camera";
    backgroundOptions = [];
    backgroundImage = null;
    backgroundSourceKey = "";
    imageRequest += 1;
    undoStack = [];
    redoStack = [];
    dialog.showModal();
    fitRenderer();
    rebuildPawns();
    renderInspector();
    setViewMode("stage");
    updateHistoryButtons();
    schedulePreview();
    animate();
  } catch (error) {
    window.alert(error.message);
  }
}

async function switchWorkspace(targetId, discard = false) {
  const session = current();
  if (!targetId || !session?.data) return;
  const previous = workspaceTarget;
  workspaceStates.set(previous, { selectedId, viewMode, undoStack: [...undoStack], redoStack: [...redoStack],
    editorPosition: editorCamera.position.toArray(), editorQuaternion: editorCamera.quaternion.toArray(), orbitTarget: orbit.target.toArray() });
  if (discard) window.zetSceneLayout.drafts.delete(previous);
  try {
    const response = await fetch(`/api/stories/${encodeURIComponent(session.storySlug)}/scenes/${encodeURIComponent(session.sceneSlug)}/builder/3d-layout/draft?target_id=${encodeURIComponent(targetId)}`, {
      method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(session.data),
    });
    const result = await response.json();
    if (!response.ok) throw new Error(result.detail || "Unable to open the requested layout.");
    workspaceTarget = targetId;
    window.zetSceneLayout.setActiveTarget(targetId);
    layout = window.zetSceneLayout.drafts.get(targetId) || result.layout_3d;
    window.zetSceneLayout.setLayout(layout);
    const restored = workspaceStates.get(targetId);
    selectedId = restored?.selectedId && layout.pawns.some((pawn) => pawn.element_id === restored.selectedId)
      ? restored.selectedId : layout.pawns[0]?.element_id || backgroundId;
    composition = { pawns: [], groups: [] };
    undoStack = restored?.undoStack || []; redoStack = restored?.redoStack || [];
    if (restored) {
      viewMode = restored.viewMode || "stage";
      editorCamera.position.fromArray(restored.editorPosition);
      editorCamera.quaternion.fromArray(restored.editorQuaternion);
      orbit.target.fromArray(restored.orbitTarget);
      editorCamera.updateProjectionMatrix();
    } else viewMode = "stage";
    rebuildPawns(); setViewMode(viewMode); renderInspector(); updateHistoryButtons(); schedulePreview();
  } catch (error) {
    window.alert(error.message);
    workspaceTarget = previous;
  }
}

dialog.addEventListener("click", async (event) => {
  const button = event.target.closest("button[data-layout-action]");
  if (!button) return;
  const action = button.dataset.layoutAction;
  if (action === "close") { dialog.close(); return; }
  if (action === "edit-contents") {
    const target = (current()?.data?.subscenes || []).find((item) => item.enabled && item.kind === "element" && item.anchor_element_id === selectedId);
    if (target) await switchWorkspace(target.id);
    return;
  }
  if (action === "parent-workspace") { await switchWorkspace(workspaceParents[workspaceTarget] || "main"); return; }
  if (action === "discard") { await switchWorkspace(workspaceTarget, true); return; }
  if (action === "move" || action === "rotate") {
    dialog.dataset.transformMode = action === "move" ? "translate" : "rotate";
    transform.setMode(dialog.dataset.transformMode);
    transform.showY = action === "rotate";
    attachSelection(); return;
  }
  if (action === "undo" && undoStack.length) {
    redoStack.push(JSON.stringify(layout)); layout = JSON.parse(undoStack.pop()); window.zetSceneLayout.setLayout(layout);
    rebuildPawns(); renderInspector(); updateHistoryButtons(); schedulePreview(); return;
  }
  if (action === "redo" && redoStack.length) {
    undoStack.push(JSON.stringify(layout)); layout = JSON.parse(redoStack.pop()); window.zetSceneLayout.setLayout(layout);
    rebuildPawns(); renderInspector(); updateHistoryButtons(); schedulePreview(); return;
  }
  if (action === "camera-from-view") {
    checkpoint(() => {
      const camera = cameraData();
      camera.position = editorCamera.position.toArray();
      camera.target = orbit.target.toArray();
      camera.vertical_fov = editorCamera.fov;
    });
    renderInspector();
  }
  if (action === "preview") await requestPreview();
  if (action === "save") {
    layout.migration_review_required = !migrationConfirm.checked;
    window.zetSceneLayout.setLayout(layout);
    const saved = await window.zetSceneLayout.save();
    if (saved) dialog.close();
  }
});

document.addEventListener("click", (event) => {
  if (event.target.closest("[data-layout-open]")) void openLayout();
});

document.addEventListener("change", (event) => {
  const target = event.target;
  if (target === selector) {
    selectedId = selector.value;
    adjust.value = selectedId === backgroundId ? "background" : "camera";
    updateInteractions();
    attachSelection(); renderInspector(); return;
  }
  if (target === cameraLock) { renderInspector(); return; }
  if (target === migrationConfirm && layout) {
    checkpoint(() => { layout.migration_review_required = !migrationConfirm.checked; });
    return;
  }
  const cameraPoint = target.closest("[data-camera-point]");
  if (cameraPoint) {
    try { checkpoint(() => updateCameraPoint(cameraPoint.dataset.cameraPoint, Number(cameraPoint.dataset.axis), cameraPoint.value)); }
    catch (error) { target.setCustomValidity(error.message); target.reportValidity(); }
    return;
  }
  if (target.id === "scene-layout-fov") {
    const fov = Number(target.value);
    if (fov < 5 || fov > 120) return;
    checkpoint(() => { cameraData().vertical_fov = fov; });
  }
  const facingKey = { "scene-layout-body-yaw": "body_yaw", "scene-layout-head-yaw": "head_yaw", "scene-layout-head-pitch": "head_pitch" }[target.id];
  if (facingKey && layout && pawnData()) {
    const angle = Number(target.value);
    if (!Number.isFinite(angle)) return;
    checkpoint(() => {
      pawnData()[facingKey] = angle;
      pawnData().look_at = "";
    });
  }
});

document.addEventListener("change", (event) => {
  const input = event.target;
  const axis = input.dataset.axis;
  const dimensionKind = input.dataset.layoutDimension;
  if (!layout || !dimensionKind || axis === undefined && dimensionKind === "position") return;
  try {
    checkpoint(() => {
      const pawn = pawnData();
      const meters = parseImperial(input.value);
      if (dimensionKind === "position") pawn.position[Number(axis)] = meters;
      else if (dimensionKind === "stature") {
        pawn.stature_m = meters;
        pawn.measurement_overrides = { ...(pawn.measurement_overrides || {}), height: formatImperial(meters) };
        pawn.provisional_height = false;
        pawn.measurement_source = "scene override";
        if (!pawn.measurement_overrides.occupied_height) pawn.dimensions.height = meters;
      } else if (dimensionKind === "occupied-height") {
        pawn.dimensions.height = meters;
        pawn.measurement_overrides = { ...(pawn.measurement_overrides || {}), occupied_height: formatImperial(meters) };
      } else {
        pawn.dimensions[input.dataset.dimension] = meters;
      }
      clampPawnToBackdrop(pawn);
    });
  } catch (error) {
    input.setCustomValidity(error.message); input.reportValidity();
  }
});

dialog.querySelectorAll("[data-layout-view]").forEach((button) => button.addEventListener("click", () => {
  setViewMode("stage");
  const target = orbit.target.clone();
  const distance = Math.max(3, editorCamera.position.distanceTo(target));
  const view = button.dataset.layoutView;
  if (view === "top") editorCamera.position.set(target.x, target.y + distance, target.z + .001);
  else if (view === "front") editorCamera.position.set(target.x, target.y + 1, target.z + distance);
  else if (view === "side") editorCamera.position.set(target.x + distance, target.y + 1, target.z);
  else editorCamera.position.set(target.x + distance * .58, target.y + distance * .45, target.z + distance * .68);
  editorCamera.lookAt(target); orbit.update();
}));

dialog.addEventListener("change", (event) => {
  const input = event.target;
  if (input.id === "scene-layout-grid") {
    try { floor.userData.snapMeters = parseImperial(input.value); input.setCustomValidity(""); }
    catch (error) { input.setCustomValidity(error.message); input.reportValidity(); }
  }
  if (input.id === "scene-layout-look-at") {
    const pawn = pawnData();
    if (!pawn) return;
    checkpoint(() => {
      pawn.look_at = input.value;
      let destination;
      if (input.value === "camera") destination = cameraData().position;
      else if (input.value) destination = pawnData(input.value)?.position;
      if (destination) {
        const origin = pawn.position;
        const yaw = THREE.MathUtils.radToDeg(Math.atan2(destination[0] - origin[0], -(destination[2] - origin[2])));
        pawn.head_yaw = ((yaw - pawn.body_yaw + 540) % 360) - 180;
      }
    });
    renderInspector();
  }
});

for (const button of dialog.querySelectorAll("[data-layout-view]")) button.addEventListener("click", (event) => event.preventDefault());

selector.addEventListener("change", () => { selectedId = selector.value; attachSelection(); renderInspector(); });
canvas.addEventListener("pointerdown", (event) => {
  if (viewMode !== "stage" || adjust.value === "background") return;
  if (transform.dragging) return;
  pointRay(event);
  const intersects = raycaster.intersectObjects([...pawns.values()].flatMap((item) => item.children), true);
  if (intersects.length) {
    let node = intersects[0].object;
    while (node && !node.userData.elementId) node = node.parent;
    if (node?.userData.elementId) { selectedId = node.userData.elementId; selector.value = selectedId; attachSelection(); renderInspector(); }
  }
});
cameraLock.addEventListener("change", renderInspector);
window.addEventListener("resize", () => { if (dialog.open) fitRenderer(); });
window.addEventListener("keydown", (event) => {
  if (!dialog.open || !(event.ctrlKey || event.metaKey)) return;
  if (event.key.toLowerCase() === "z") {
    event.preventDefault();
    const button = dialog.querySelector(`[data-layout-action="${event.shiftKey ? "redo" : "undo"}"]`);
    if (!button.disabled) button.click();
  } else if (event.key.toLowerCase() === "y") {
    event.preventDefault();
    const button = dialog.querySelector('[data-layout-action="redo"]');
    if (!button.disabled) button.click();
  }
});

function sceneAspect() {
  const parts = (current()?.data?.setup?.canvas?.aspect_ratio || "16:9").split(":").map(Number);
  const ratio = parts[0] / parts[1];
  return Number.isFinite(ratio) && ratio > 0 ? ratio : 16 / 9;
}

function backgroundFraming() { return cameraData()?.background_framing; }
function cropData() {
  const fraction = layout ? groundFrame(layout).visible_fraction : 1;
  return backgroundImage ? backgroundCrop(backgroundImage.width, backgroundImage.height, sceneAspect() / Math.max(.001, fraction), backgroundFraming()) : null;
}

function frameBounds() {
  const width = Math.min(canvas.clientWidth, canvas.clientHeight * sceneAspect());
  const height = width / sceneAspect();
  return { x: (canvas.clientWidth - width) / 2, y: (canvas.clientHeight - height) / 2, width, height };
}

function syncRenderCamera() {
  const camera = cameraData();
  if (!camera) return;
  renderCamera.position.fromArray(camera.position);
  renderCamera.lookAt(...camera.target);
  renderCamera.fov = camera.vertical_fov;
  renderCamera.aspect = sceneAspect();
  renderCamera.far = Math.max(2000, groundFrame(layout).distance_m * 2 || 2000);
  renderCamera.updateProjectionMatrix();
  renderCamera.updateMatrixWorld();
  updateFrame();
}

function updateFrame() {
  const frame = frameBounds();
  cameraFrame.hidden = viewMode !== "camera";
  Object.assign(cameraFrame.style, { left: `${frame.x}px`, top: `${frame.y}px`, width: `${frame.width}px`, height: `${frame.height}px` });
  const line = document.querySelector("#scene-layout-horizon-line");
  const camera = cameraData();
  if (!camera) return;
  const forward = new THREE.Vector3().fromArray(camera.target).sub(new THREE.Vector3().fromArray(camera.position)).normalize();
  const horizontal = Math.hypot(forward.x, forward.z);
  const y = (1 + forward.y / Math.max(horizontal, .00001) / Math.tan(THREE.MathUtils.degToRad(camera.vertical_fov / 2))) / 2;
  line.hidden = !document.querySelector("#scene-layout-horizon").checked || y < 0 || y > 1;
  line.style.top = `${y * 100}%`;
  const joinLine = document.querySelector("#scene-layout-ground-join-line");
  const ground = groundFrame(layout);
  joinLine.hidden = !ground.enabled || ground.join_y <= 0 || ground.join_y >= 1;
  joinLine.style.top = `${ground.visible_fraction * 100}%`;
}

function setViewMode(mode) {
  finishFramingDrag(true);
  finishWheel();
  viewMode = mode;
  dialog.dataset.viewMode = mode;
  for (const button of dialog.querySelectorAll("[data-layout-mode]")) button.setAttribute("aria-pressed", String(button.dataset.layoutMode === mode));
  updateInteractions();
  syncRenderCamera();
  renderInspector();
  fitRenderer();
}

function updateInteractions() {
  orbit.enabled = viewMode === "stage" && adjust.value !== "background";
  transform.enabled = orbit.enabled;
  if (!orbit.enabled) transform.detach();
  attachSelection();
  canvas.style.cursor = adjust.value === "background" || viewMode === "camera" ? "grab" : "auto";
  dialog.querySelector(".scene-layout-facing-legend").hidden = viewMode !== "stage" || selectedId === backgroundId;
}

function sourceMatches(selected, source) {
  return selected && source && Object.entries(selected).every(([key, value]) => source[key] === value);
}

function renderBackgroundInspector() {
  const sourceSelector = document.querySelector("#scene-layout-background-source");
  sourceSelector.replaceChildren(new Option("No background", ""), ...backgroundOptions.map((item, index) => new Option(item.label, String(index))));
  const index = backgroundOptions.findIndex((item) => sourceMatches(layout?.background, item.source));
  if (layout?.background && index < 0) {
    sourceSelector.add(new Option("Selected source unavailable", "missing"));
    sourceSelector.value = "missing";
  } else sourceSelector.value = index < 0 ? "" : String(index);
  const framing = backgroundFraming() || { center: [.5, .5], zoom: 1 };
  document.querySelector("#scene-layout-background-zoom").value = framing.zoom;
  document.querySelector("#scene-layout-background-x").value = framing.center[0];
  document.querySelector("#scene-layout-background-y").value = framing.center[1];
  const ground = layout ? groundFrame(layout) : { enabled: true, join_min: 0, join_max: 1, visible_fraction: .5 };
  document.querySelector("#scene-layout-ground-enabled").checked = ground.enabled;
  document.querySelector("#scene-layout-ground-surface").value = layout?.ground?.surface || "Ground surface matching the setting";
  const join = document.querySelector("#scene-layout-ground-join");
  join.min = ground.join_min ?? 0; join.max = ground.join_max ?? 1; join.value = ground.visible_fraction;
  join.disabled = !ground.enabled || ground.join_max <= ground.join_min;
  dialog.querySelector('[data-layout-action="ground-align"]').disabled = !ground.enabled;
}

async function loadBackground(result) {
  const info = result.projection?.background;
  if (!info || !result.background_source_png_base64) {
    backgroundImage = null;
    backgroundSourceKey = "";
    imageRequest += 1;
    updateBackgroundDisplay();
    return;
  }
  if (!sourceMatches(layout.background, info.source)) return;
  // Save the exact image selected during migration, even if its primary-reference flag later changes.
  layout.background = structuredClone(info.source);
  updateDirty();
  const key = JSON.stringify(info.source) + info.source_sha256;
  if (key === backgroundSourceKey && backgroundImage) { updateBackgroundDisplay(); return; }
  const request = ++imageRequest;
  const loaded = new Image();
  loaded.src = `data:image/png;base64,${result.background_source_png_base64}`;
  await loaded.decode();
  if (request !== imageRequest || !dialog.open || !sourceMatches(layout.background, info.source)) return;
  backgroundImage = loaded;
  backgroundSourceKey = key;
  sourceTexture?.dispose();
  framedTexture?.dispose();
  sourceTexture = new THREE.Texture(loaded);
  sourceTexture.colorSpace = THREE.SRGBColorSpace;
  sourceTexture.needsUpdate = true;
  framedTexture = new THREE.CanvasTexture(framedCanvas);
  framedTexture.colorSpace = THREE.SRGBColorSpace;
  imageMaterial.map = framedTexture;
  imageMaterial.needsUpdate = true;
  updateBackgroundDisplay();
}

function updateBackgroundDisplay() {
  updateGroundDisplay();
  for (const child of [...backdrop.children]) {
    child.geometry?.dispose();
    child.material?.dispose();
    backdrop.remove(child);
  }
  const source = backgroundOptions.find((item) => sourceMatches(layout?.background, item.source))?.source;
  if (backgroundImage && (!layout?.background || (source && !backgroundSourceKey.startsWith(JSON.stringify(source))))) backgroundImage = null;
  const ground = groundFrame(layout);
  const fraction = ground.visible_fraction;
  imageQuad.visible = !!backgroundImage && fraction > 0;
  imageQuad.scale.y = fraction;
  imageQuad.position.y = 1 - fraction;
  const crop = cropData();
  if (!crop) return;
  // Uncovered parts of the frame are neutral areas for generation to extend.
  cameraData().background_framing = { center: crop.center, zoom: crop.zoom };
  framedCanvas.width = 1024;
  framedCanvas.height = Math.max(1, Math.min(2048, Math.round(1024 / (sceneAspect() / Math.max(.001, fraction)))));
  const context = framedCanvas.getContext("2d");
  context.fillStyle = "#d7dddf";
  context.fillRect(0, 0, framedCanvas.width, framedCanvas.height);
  context.drawImage(backgroundImage, -crop.left / crop.width * framedCanvas.width, -crop.top / crop.height * framedCanvas.height,
    framedCanvas.width / crop.width, framedCanvas.height / crop.height);
  framedTexture.needsUpdate = true;
  const camera = cameraData();
  const forward = new THREE.Vector3(...camera.target).sub(new THREE.Vector3(...camera.position)).normalize();
  const cosine = Math.hypot(forward.x, forward.z);
  const tangent = Math.tan(THREE.MathUtils.degToRad(camera.vertical_fov / 2));
  const height = ground.enabled ? Math.max(1, Math.min(10000, camera.position[1] + ground.distance_m *
    (forward.y + cosine * tangent) / Math.max(.001, cosine - forward.y * tangent))) : 4.5;
  const width = height * sceneAspect() / Math.max(.001, fraction);
  backdropSize = { width, height };
  const horizontal = new THREE.Vector3(camera.target[0] - camera.position[0], 0, camera.target[2] - camera.position[2]).normalize();
  if (horizontal.lengthSq() < .001) horizontal.set(0, 0, -1);
  const distance = ground.distance_m;
  backdrop.position.set(camera.position[0] + horizontal.x * distance, height / 2, camera.position[2] + horizontal.z * distance);
  backdrop.rotation.y = Math.atan2(-horizontal.x, -horizontal.z);
  const plane = new THREE.Mesh(new THREE.PlaneGeometry(width, height), new THREE.MeshBasicMaterial({ map: framedTexture, side: THREE.DoubleSide }));
  plane.name = "background-plane";
  backdrop.add(plane);
  const border = new THREE.LineSegments(new THREE.EdgesGeometry(plane.geometry), new THREE.LineBasicMaterial({ color: 0xf6b34f }));
  border.position.z = .01;
  backdrop.add(border);
  if (adjust.value === "background") {
    const overflow = new THREE.Mesh(new THREE.PlaneGeometry(width / crop.width, height / crop.height),
      new THREE.MeshBasicMaterial({ map: sourceTexture, side: THREE.DoubleSide, transparent: true, opacity: .22, depthWrite: false }));
    overflow.position.set((.5 - crop.center[0]) * width / crop.width, (crop.center[1] - .5) * height / crop.height, -.02);
    backdrop.add(overflow);
  }
  backdrop.traverse((node) => node.layers.set(1));
  backdrop.updateMatrixWorld(true);
}

function stageImagePoint(event) {
  pointRay(event);
  raycaster.layers.enable(1);
  const plane = backdrop.getObjectByName("background-plane");
  if (!plane) return null;
  const hit = raycaster.intersectObject(plane, false)[0];
  return hit?.uv ? { x: hit.uv.x, y: 1 - hit.uv.y } : null;
}

function gesturePoint(event) {
  if (viewMode === "stage") return backgroundImage ? stageImagePoint(event) : null;
  const bounds = canvas.getBoundingClientRect();
  const frame = frameBounds();
  const fraction = adjust.value === "background" ? Math.max(.001, groundFrame(layout).visible_fraction) : 1;
  return { x: (event.clientX - bounds.left - frame.x) / frame.width, y: (event.clientY - bounds.top - frame.y) / (frame.height * fraction) };
}

function refreshFraming() {
  updateCameraHelper();
  updateBackgroundDisplay();
  renderInspector();
  updateDirty();
  schedulePreview();
}

function dolly(distance) {
  const camera = cameraData();
  if (!camera || cameraLock.checked) return;
  const direction = new THREE.Vector3(...camera.target).sub(new THREE.Vector3(...camera.position)).normalize().multiplyScalar(distance);
  camera.position = new THREE.Vector3(...camera.position).add(direction).toArray();
  camera.target = new THREE.Vector3(...camera.target).add(direction).toArray();
}

function finishFramingDrag(cancel = false) {
  if (!framingDrag) return;
  const drag = framingDrag;
  framingDrag = null;
  if (cancel) layout = JSON.parse(drag.snapshot);
  else pushHistory(drag.snapshot);
  if (canvas.hasPointerCapture(drag.pointerId)) canvas.releasePointerCapture(drag.pointerId);
  updateInteractions();
  refreshFraming();
}

function finishWheel() {
  window.clearTimeout(wheelTimer);
  if (wheelSnapshot) { pushHistory(wheelSnapshot); wheelSnapshot = ""; updateDirty(); schedulePreview(); }
}

canvas.addEventListener("pointerdown", (event) => {
  if (!layout || event.button !== 0) return;
  if (viewMode === "stage" && adjust.value !== "background") {
    pointRay(event);
    raycaster.layers.enable(1);
    const objects = [...pawns.values(), ...(backdrop.getObjectByName("background-plane") ? [backdrop.getObjectByName("background-plane")] : [])];
    const hit = raycaster.intersectObjects(objects, true)[0];
    if (hit?.object.name !== "background-plane") return;
    selectedId = backgroundId; adjust.value = "background";
    updateInteractions(); renderInspector();
  }
  event.preventDefault(); event.stopImmediatePropagation();
  finishWheel();
  if (adjust.value !== "background" && cameraLock.checked) return;
  const point = gesturePoint(event);
  if (!point || point.x < 0 || point.x > 1 || point.y < 0 || point.y > 1) return;
  if (adjust.value === "background" && !backgroundImage) return;
  framingDrag = { pointerId: event.pointerId, snapshot: JSON.stringify(layout), point,
    crop: cropData(), camera: structuredClone(cameraData()), mode: adjust.value };
  canvas.setPointerCapture(event.pointerId);
  canvas.style.cursor = "grabbing";
}, true);

canvas.addEventListener("pointermove", (event) => {
  if (!framingDrag || event.pointerId !== framingDrag.pointerId) return;
  event.preventDefault(); event.stopImmediatePropagation();
  const point = gesturePoint(event);
  if (!point) return;
  const drag = framingDrag;
  const dx = point.x - drag.point.x;
  const dy = point.y - drag.point.y;
  const camera = cameraData();
  if (drag.mode === "background") {
    camera.background_framing = { zoom: drag.crop.zoom,
      center: [drag.crop.center[0] - dx * drag.crop.width, drag.crop.center[1] - dy * drag.crop.height] };
  } else {
    const original = drag.camera;
    const position = new THREE.Vector3(...original.position);
    const target = new THREE.Vector3(...original.target);
    const forward = target.clone().sub(position);
    const distance = forward.length();
    forward.normalize();
    const right = new THREE.Vector3().crossVectors(forward, new THREE.Vector3(0, 1, 0)).normalize();
    const up = new THREE.Vector3().crossVectors(right, forward).normalize();
    if (drag.mode === "aim") {
      const yaw = Math.atan2(forward.x, -forward.z) + dx * Math.PI;
      const pitch = THREE.MathUtils.clamp(Math.asin(forward.y) - dy * Math.PI / 2, -Math.PI * .49, Math.PI * .49);
      const direction = new THREE.Vector3(Math.sin(yaw) * Math.cos(pitch), Math.sin(pitch), -Math.cos(yaw) * Math.cos(pitch));
      camera.target = position.addScaledVector(direction, distance).toArray();
    } else {
      const span = 2 * distance * Math.tan(THREE.MathUtils.degToRad(original.vertical_fov / 2));
      const movement = right.multiplyScalar(-dx * span * sceneAspect()).add(up.multiplyScalar(dy * span));
      camera.position = position.add(movement).toArray();
      camera.target = target.add(movement).toArray();
    }
  }
  refreshFraming();
}, true);

for (const type of ["pointerup", "pointercancel"]) canvas.addEventListener(type, (event) => {
  if (!framingDrag || event.pointerId !== framingDrag.pointerId) return;
  event.preventDefault(); event.stopImmediatePropagation();
  finishFramingDrag(type === "pointercancel");
}, true);
canvas.addEventListener("lostpointercapture", () => finishFramingDrag(true));
canvas.addEventListener("wheel", (event) => {
  if (!layout || (viewMode === "stage" && adjust.value !== "background")) return;
  event.preventDefault(); event.stopImmediatePropagation();
  if (framingDrag || (adjust.value !== "background" && cameraLock.checked)) return;
  if (adjust.value === "background" && !backgroundImage) return;
  if (!wheelSnapshot) wheelSnapshot = JSON.stringify(layout);
  if (adjust.value === "background") backgroundFraming().zoom *= Math.exp(-event.deltaY * .001);
  else dolly(-event.deltaY * .002);
  refreshFraming();
  window.clearTimeout(wheelTimer);
  wheelTimer = window.setTimeout(finishWheel, 250);
}, { capture: true, passive: false });

for (const button of dialog.querySelectorAll("[data-layout-mode]")) button.addEventListener("click", () => setViewMode(button.dataset.layoutMode));
adjust.addEventListener("change", () => {
  finishFramingDrag(true); finishWheel();
  if (adjust.value === "background") selectedId = backgroundId;
  updateInteractions(); updateBackgroundDisplay(); renderInspector();
});
document.querySelector("#scene-layout-horizon").addEventListener("change", updateFrame);
document.querySelector("#scene-layout-background-source").addEventListener("change", (event) => {
  if (event.target.value === "missing") return;
  finishWheel();
  imageRequest += 1;
  backgroundImage = null;
  backgroundSourceKey = "";
  checkpoint(() => {
    layout.background = event.target.value === "" ? null : structuredClone(backgroundOptions[Number(event.target.value)].source);
    cameraData().background_framing = { center: [.5, .5], zoom: 1 };
  });
});

for (const input of dialog.querySelectorAll("#scene-layout-background-controls input[type=range], #scene-layout-lens")) {
  input.addEventListener("input", () => {
    if (!layout || (input.id === "scene-layout-lens" && cameraLock.checked)) return;
    finishWheel();
    if (!sliderSnapshot) sliderSnapshot = JSON.stringify(layout);
    const value = Number(input.value);
    if (input.id === "scene-layout-lens") cameraData().vertical_fov = value;
    else if (input.id === "scene-layout-ground-join") {
      const ground = groundFrame(layout);
      cameraData().ground_distance_m = Math.max(ground.minimum_distance_m, Math.min(1000, distanceForGroundJoin(cameraData(), value)));
    } else if (input.id.endsWith("zoom")) backgroundFraming().zoom = value;
    else backgroundFraming().center[input.id.endsWith("-x") ? 0 : 1] = value;
    refreshFraming();
  });
  input.addEventListener("change", () => {
    pushHistory(sliderSnapshot); sliderSnapshot = ""; schedulePreview();
  });
  input.addEventListener("pointercancel", () => {
    if (sliderSnapshot) { layout = JSON.parse(sliderSnapshot); sliderSnapshot = ""; refreshFraming(); }
  });
}

dialog.addEventListener("click", (event) => {
  const action = event.target.closest("[data-layout-action]")?.dataset.layoutAction;
  if (action === "background-reset") checkpoint(() => { cameraData().background_framing = { center: [.5, .5], zoom: 1 }; });
  if (action === "background-fit" && backgroundImage) checkpoint(() => {
    const aspect = sceneAspect() / Math.max(.001, groundFrame(layout).visible_fraction);
    const imageAspect = backgroundImage.width / backgroundImage.height;
    cameraData().background_framing = { center: [.5, .5], zoom: Math.max(.05, Math.min(1, aspect / imageAspect, imageAspect / aspect) * .98) };
  });
  if (action === "dolly-in" || action === "dolly-out") checkpoint(() => dolly(action === "dolly-in" ? FT_M : -FT_M));
  if (action === "ground-align" && layout.ground.enabled) checkpoint(() => {
    cameraData().ground_distance_m = Math.max(10, ...layout.pawns.map((pawn) => {
      const ground = groundFrame(layout);
      return new THREE.Vector3(...pawn.position).sub(new THREE.Vector3(...cameraData().position)).dot(new THREE.Vector3(...ground.forward)) + 5;
    }));
    backgroundFraming().center[1] = 1;
  });
});
dialog.addEventListener("click", (event) => {
  if (event.target.closest("[data-layout-action]")) finishWheel();
}, true);
dialog.addEventListener("close", () => {
  finishFramingDrag(true); finishWheel(); imageRequest += 1; lastPreviewRequest += 1;
});
window.addEventListener("keydown", (event) => {
  if (dialog.open && event.key === "Escape" && framingDrag) { event.preventDefault(); finishFramingDrag(true); }
}, true);
new ResizeObserver(() => { if (dialog.open) fitRenderer(); }).observe(canvas);

function updateGroundDisplay() {
  if (!layout) return;
  const ground = groundFrame(layout);
  groundMesh.visible = ground.enabled;
  contactShadows.visible = ground.enabled;
  for (const shadow of [...contactShadows.children]) { shadow.geometry.dispose(); shadow.material.dispose(); contactShadows.remove(shadow); }
  if (!ground.enabled) return;
  const camera = cameraData();
  const direction = new THREE.Vector3(...ground.forward);
  const depth = ground.distance_m + 2000;
  groundMesh.scale.set(Math.max(1, ground.distance_m / 200), depth / 2000, 1);
  groundMesh.rotation.set(-Math.PI / 2, Math.atan2(-direction.x, -direction.z), 0, "YXZ");
  groundMesh.position.set(camera.position[0] + direction.x * (ground.distance_m - 2000) / 2, 0,
    camera.position[2] + direction.z * (ground.distance_m - 2000) / 2);
  for (const pawn of layout.pawns) {
    const element = elements.find((item) => item.id === pawn.element_id);
    const grouped = (current()?.data?.subscenes || []).some((target) => target.enabled && target.kind === "element" && target.id === element?.subscene_id);
    if (pawn.position[1] < -.01) continue;
    const shadow = new THREE.Mesh(new THREE.PlaneGeometry(Math.max(.4, pawn.dimensions.width * 1.5), Math.max(.4, pawn.dimensions.depth * 2)),
      new THREE.MeshBasicMaterial({ map: shadowTexture, transparent: true, depthWrite: false, opacity: 1 / (1 + pawn.position[1]) }));
    shadow.rotation.x = -Math.PI / 2;
    shadow.position.set(pawn.position[0], .008, pawn.position[2]);
    shadow.name = `contact-shadow-${pawn.element_id}`;
    if (grouped) shadow.layers.set(1);
    contactShadows.add(shadow);
  }
}

document.querySelector("#scene-layout-ground-enabled").addEventListener("change", (event) => {
  checkpoint(() => { layout.ground.enabled = event.target.checked; });
});
document.querySelector("#scene-layout-ground-surface").addEventListener("change", (event) => {
  checkpoint(() => { layout.ground.surface = event.target.value.trim() || "Ground surface matching the setting"; });
});

function clampPawnToBackdrop(pawn) {
  if (!layout.background || !pawn) return;
  const boundary = groundFrame(layout);
  const direction = new THREE.Vector3(...boundary.forward);
  const position = new THREE.Vector3(...pawn.position);
  const depth = position.clone().sub(new THREE.Vector3(...cameraData().position)).dot(direction);
  const margin = Math.max(pawn.dimensions.width, pawn.dimensions.depth) / 2 + .02;
  if (depth + margin > boundary.distance_m) {
    position.addScaledVector(direction, boundary.distance_m - margin - depth);
    pawn.position = position.toArray();
  }
}
