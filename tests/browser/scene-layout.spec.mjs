import { expect, test } from "@playwright/test";
import { restorePristineProjectState, restorePristineScene } from "./scene-fixtures.mjs";

const scene = "/api/stories/Alpha-Story/scenes/Opening-Scene";

test.beforeEach(async ({ page }) => {
  await restorePristineProjectState();
  await restorePristineScene(page, "Alpha-Story", "Opening-Scene");
});

async function observeLayoutScene(page) {
  await page.evaluate(async () => {
    const THREE = await import("/static/vendor/three/build/three.module.js");
    const beforeRender = THREE.Object3D.prototype.onBeforeRender;
    THREE.Object3D.prototype.onBeforeRender = function (renderer, scene, ...args) {
      window.layoutTestScene = scene;
      window.layoutTestCamera = args[0];
      return beforeRender.call(this, renderer, scene, ...args);
    };
  });
}

test("3D layout accepts imperial dimensions, shows body and head facing and saves pawns", async ({ page }, testInfo) => {
  test.setTimeout(60_000);
  const response = await page.request.get(`${scene}/builder?include_references=false`);
  expect(response.ok()).toBeTruthy();
  const data = (await response.json()).document.data;
  data.scene_elements = [{ id: "traveler", display_name: "Traveler", resource_type: "Scene-Only", element_type: "Character",
    fallback_visual_description: "A cloaked traveler", character: "Traveler", phase: "Adult", reference_images: [] }];
  data.placements = [{ id: "traveler_place", scene_element_id: "traveler", position_within_cell: "center", depth: "midground" }];
  const saved = await page.request.put(scene + "/builder", { data });
  expect(saved.ok(), await saved.text()).toBeTruthy();

  await page.goto("/?page=scenes&story_slug=Alpha-Story&scene_slug=Opening-Scene");
  await page.waitForFunction(() => document.body.dataset.dashboardReady === "true");
  await observeLayoutScene(page);
  await page.locator("#scene-builder-open").click();
  await expect(page.locator("#scene-builder-page")).toHaveClass(/active/);
  await page.locator("[data-layout-open]").click();
  await expect(page.locator("#scene-layout-dialog")).toBeVisible();
  await expect(page.locator(".scene-layout-facing-legend")).toContainText("Orange arrow: body faces this way");
  await expect(page.locator(".scene-layout-facing-legend")).toContainText("Blue arrow: head looks this way");
  await page.waitForFunction(() => window.layoutTestScene?.getObjectByName("traveler"));
  const direction = (name) => page.evaluate(async (name) => {
    const THREE = await import("/static/vendor/three/build/three.module.js");
    const arrow = window.layoutTestScene.getObjectByName("traveler").getObjectByName(name);
    const origin = arrow.getWorldPosition(new THREE.Vector3());
    return arrow.cone.getWorldPosition(new THREE.Vector3()).sub(origin).normalize().toArray().map((value) => Math.round(value * 1000) / 1000 || 0);
  }, name);
  const setAngle = async (id, value) => {
    await page.locator(id).fill(String(value));
    await page.locator(id).press("Tab");
  };
  for (const [yaw, expected] of [[0, [0, 0, -1]], [90, [1, 0, 0]], [180, [0, 0, 1]], [270, [-1, 0, 0]]]) {
    await setAngle("#scene-layout-body-yaw", yaw);
    await expect.poll(() => direction("body-direction")).toEqual(expected);
    await expect.poll(() => direction("head-direction")).toEqual(expected);
  }
  await setAngle("#scene-layout-body-yaw", 90);
  await setAngle("#scene-layout-head-yaw", -90);
  await setAngle("#scene-layout-head-pitch", 30);
  await expect.poll(() => direction("body-direction")).toEqual([1, 0, 0]);
  await expect.poll(() => direction("head-direction")).toEqual([0, .5, -.866]);
  await page.locator("#scene-layout-look-at").selectOption("camera");
  await setAngle("#scene-layout-head-pitch", 0);
  await expect(page.locator("#scene-layout-look-at")).toHaveValue("");
  await expect.poll(() => direction("head-direction")).toEqual([0, 0, 1]);
  await page.locator('[data-layout-view="front"]').click();
  const canvas = page.locator("#scene-layout-canvas");
  await canvas.hover();
  const viewDistance = () => page.evaluate(() => window.layoutTestCamera.position.length());
  const initialDistance = await viewDistance();
  await page.mouse.wheel(0, -1800);
  await expect.poll(viewDistance).toBeLessThan(initialDistance * .5);
  await page.locator('[data-layout-view="top"]').click();
  await page.locator("#scene-layout-dialog").screenshot({ path: testInfo.outputPath("pawn-facing-top.png") });
  await page.locator('[data-layout-view="front"]').click();
  await page.locator("#scene-layout-dialog").screenshot({ path: testInfo.outputPath("pawn-facing-front.png") });

  const height = page.locator("#scene-layout-height");
  await height.fill("5 ft 6 in");
  await height.press("Tab");
  const x = page.locator("#scene-layout-x");
  await x.fill("2 ft 3 in");
  await x.press("Tab");
  await page.locator("[data-layout-action=undo]").click();
  await page.locator("[data-layout-action=redo]").click();
  await page.locator("[data-layout-action=save]").click();
  await expect(page.locator("#scene-layout-dialog")).toBeHidden();

  const persisted = (await (await page.request.get(`${scene}/builder?include_references=false`)).json()).document.data.layout_3d;
  expect(persisted.version).toBe(3);
  expect(persisted.pawns).toHaveLength(1);
  expect(persisted.pawns[0].dimensions.height).toBeCloseTo(1.6764, 3);
  expect(persisted.pawns[0].position[0]).toBeCloseTo(0.6858, 3);
  expect(persisted.pawns[0].provisional_height).toBe(false);
  expect(persisted.pawns[0].body_yaw).toBe(90);
  expect(persisted.pawns[0].head_yaw).toBe(90);
  expect(persisted.pawns[0].head_pitch).toBe(0);
  expect(persisted.cameras[0].vertical_fov).toBe(50);
  expect(persisted.cameras[0].position).toEqual([0, 1.68, 8]);
});

test("selected pawn dials turn body, head or both without moving the pawn or camera", async ({ page }, testInfo) => {
  const data = (await (await page.request.get(`${scene}/builder?include_references=false`)).json()).document.data;
  delete data.layout_3d;
  data.scene_elements = ["traveler", "companion"].map((id) => ({ id, display_name: id, resource_type: "Scene-Only", element_type: "Character",
    fallback_visual_description: "A traveler", character: id, phase: "Adult", reference_images: [] }));
  data.placements = data.scene_elements.map(({ id }) => ({ id: `${id}_place`, scene_element_id: id, position_within_cell: "center", depth: "midground" }));
  const saved = await page.request.put(scene + "/builder", { data });
  expect(saved.ok(), await saved.text()).toBeTruthy();
  await page.goto("/?page=scenes&story_slug=Alpha-Story&scene_slug=Opening-Scene");
  await page.waitForFunction(() => document.body.dataset.dashboardReady === "true");
  await observeLayoutScene(page);
  await page.locator("#scene-builder-open").click();
  await page.locator("[data-layout-open]").click();
  await expect(page.locator("#scene-layout-dialog")).toBeVisible();
  await page.waitForFunction(() => window.layoutTestScene?.getObjectByName("rotation-dials")?.visible);
  await page.locator("#scene-layout-z").fill("0 ft");
  await page.locator("#scene-layout-z").press("Tab");
  await page.locator("#scene-layout-body-yaw").fill("0");
  await page.locator("#scene-layout-body-yaw").press("Tab");
  await page.locator("#scene-layout-head-yaw").fill("25");
  await page.locator("#scene-layout-head-yaw").press("Tab");
  await page.locator('[data-layout-view="top"]').click();
  const canvas = page.locator("#scene-layout-canvas");
  await canvas.hover();
  const initialDistance = await page.evaluate(() => window.layoutTestCamera.position.length());
  await page.mouse.wheel(0, -1200);
  await expect.poll(() => page.evaluate(() => window.layoutTestCamera.position.length())).toBeLessThan(initialDistance * .65);

  const read = () => page.evaluate(() => {
    const layout = window.zetSceneLayout.current().data.layout_3d;
    return { pawn: structuredClone(layout.pawns[0]), cameras: structuredClone(layout.cameras), view: window.layoutTestCamera.position.toArray() };
  });
  const dialPoint = (kind, angle) => page.evaluate(async ({ kind, angle }) => {
    const THREE = await import("/static/vendor/three/build/three.module.js");
    const dials = window.layoutTestScene.getObjectByName("rotation-dials");
    const radius = dials.getObjectByName(`dial-${kind}`).userData.radius;
    const radians = THREE.MathUtils.degToRad(angle);
    const point = dials.localToWorld(new THREE.Vector3(Math.sin(radians) * radius, 0, -Math.cos(radians) * radius));
    point.project(window.layoutTestCamera);
    const bounds = document.querySelector("#scene-layout-canvas").getBoundingClientRect();
    return { x: bounds.left + (point.x + 1) * bounds.width / 2, y: bounds.top + (1 - point.y) * bounds.height / 2 };
  }, { kind, angle });
  const dragDial = async (kind, from, to, cancel = false) => {
    const start = await dialPoint(kind, from);
    await page.mouse.move(start.x, start.y);
    await expect(canvas).toHaveCSS("cursor", "grab");
    await page.mouse.down();
    await expect(canvas).toHaveCSS("cursor", "grabbing");
    for (let step = 1; step <= 12; step++) {
      const point = await dialPoint(kind, from + (to - from) * step / 12);
      await page.mouse.move(point.x, point.y);
    }
    if (cancel) await canvas.dispatchEvent("pointercancel", { pointerId: 1 });
    await page.mouse.up();
  };
  const initial = await read();
  await page.locator("#scene-layout-dialog").screenshot({ path: testInfo.outputPath("rotation-dials-before.png") });
  await dragDial("head", 40, 130);
  let state = await read();
  expect(state.pawn.body_yaw).toBeCloseTo(0, 0);
  expect(state.pawn.head_yaw).toBeCloseTo(115, 0);
  await page.locator('[data-layout-action="undo"]').click();
  expect((await read()).pawn.head_yaw).toBe(25);
  await page.locator('[data-layout-action="redo"]').click();
  expect((await read()).pawn.head_yaw).toBeCloseTo(115, 0);

  await dragDial("body", 40, 130);
  state = await read();
  expect(state.pawn.body_yaw).toBeCloseTo(90, 0);
  expect(state.pawn.head_yaw).toBeCloseTo(25, 0);
  // The middle dial crosses 360 degrees and keeps the head's relative yaw.
  await dragDial("both", 320, 410);
  state = await read();
  expect(state.pawn.body_yaw).toBeCloseTo(180, 0);
  expect(state.pawn.head_yaw).toBeCloseTo(25, 0);
  expect(state.pawn.position).toEqual(initial.pawn.position);
  expect(state.pawn.head_pitch).toBe(initial.pawn.head_pitch);
  expect(state.cameras).toEqual(initial.cameras);
  expect(state.view).toEqual(initial.view);
  await dragDial("head", 40, 130, true);
  expect((await read()).pawn).toEqual(state.pawn);
  await page.locator("#scene-layout-dialog").screenshot({ path: testInfo.outputPath("rotation-dials.png") });

  // A movement arrow remains draggable where it overlaps the rings.
  const moveHandle = await page.evaluate(async () => {
    const THREE = await import("/static/vendor/three/build/three.module.js");
    const controls = window.layoutTestScene.children.find((child) => child.isTransformControlsRoot).controls;
    const arrow = controls._gizmo.gizmo.translate.children.find((child) => {
      if (child.name !== "X" || child.geometry?.parameters?.radiusTop !== 0) return false;
      child.geometry.computeBoundingBox();
      return child.geometry.boundingBox.getCenter(new THREE.Vector3()).x > 0;
    });
    const point = arrow.localToWorld(arrow.geometry.boundingBox.getCenter(new THREE.Vector3())).project(window.layoutTestCamera);
    const bounds = document.querySelector("#scene-layout-canvas").getBoundingClientRect();
    return { x: bounds.left + (point.x + 1) * bounds.width / 2, y: bounds.top + (1 - point.y) * bounds.height / 2 };
  });
  await page.mouse.move(moveHandle.x, moveHandle.y);
  await page.mouse.down();
  await page.mouse.move(moveHandle.x + 50, moveHandle.y, { steps: 8 });
  await page.mouse.up();
  expect((await read()).pawn.position[0]).toBeGreaterThan(initial.pawn.position[0]);
  expect((await read()).pawn.body_yaw).toBeCloseTo(state.pawn.body_yaw, 1);
  await page.locator('[data-layout-action="undo"]').click();
  expect((await read()).pawn.position).toEqual(initial.pawn.position);

  await page.locator("#scene-layout-element").selectOption("companion");
  await page.locator("#scene-layout-x").fill("4 ft");
  await page.locator("#scene-layout-x").press("Tab");
  await expect.poll(() => page.evaluate(() => window.layoutTestScene.getObjectByName("rotation-dials").position.x)).toBeCloseTo(1.2192, 3);
  await page.locator('[data-layout-action="save"]').click();
  await expect(page.locator("#scene-layout-dialog")).toBeHidden();
  const persisted = (await (await page.request.get(`${scene}/builder?include_references=false`)).json()).document.data.layout_3d.pawns[0];
  expect(persisted.body_yaw).toBeCloseTo(180, 0);
  expect(persisted.head_yaw).toBeCloseTo(25, 0);
});

test("backdrop plane and camera view keep the background crop independent of dolly and lens", async ({ page }, testInfo) => {
  test.setTimeout(60_000);
  const errors = [];
  page.on("pageerror", (error) => errors.push(error.message));
  const data = (await (await page.request.get(`${scene}/builder?include_references=false`)).json()).document.data;
  data.setup.canvas.aspect_ratio = "8:5";
  data.subscenes = [];
  data.scene_elements = [
    { id: "traveler", display_name: "Traveler", resource_type: "Scene-Only", element_type: "Character",
      fallback_visual_description: "A cloaked traveler", reference_images: [] },
    { id: "arch", display_name: "Spire - Archway", resource_type: "Scene-Only", element_type: "Backdrop",
      fallback_visual_description: "A stone archway", reference_images: [{ tag: "{{SCENE:Beta-Story:Closing-Scene}}", primary_prompt_source: true }] },
  ];
  data.placements = data.scene_elements.map(({ id }) => ({ id: `${id}_place`, scene_element_id: id, position_within_cell: "center", depth: "midground" }));
  data.layout_3d = { version: 1, migration_review_required: false, pawns: [
    { element_id: "traveler", position: [0, 0, 0], body_yaw: 180, measurement_overrides: { height: "5 ft 8 in" } },
    { element_id: "arch", position: [0, 0, -6] },
  ] };
  const saved = await page.request.put(scene + "/builder", { data });
  expect(saved.ok(), await saved.text()).toBeTruthy();
  await page.goto("/?page=scenes&story_slug=Alpha-Story&scene_slug=Opening-Scene");
  await page.waitForFunction(() => document.body.dataset.dashboardReady === "true");
  await observeLayoutScene(page);
  await page.locator("#scene-builder-open").click();
  await page.locator("[data-layout-open]").click();
  await page.waitForFunction(() => window.layoutTestScene?.getObjectByName("background-plane"));
  const read = () => page.evaluate(() => structuredClone(window.zetSceneLayout.current().data.layout_3d));
  const initial = await read();
  expect(initial.version).toBe(3);
  expect(initial.pawns.map((pawn) => pawn.element_id)).toEqual(["traveler"]);
  const geometry = await page.evaluate(() => {
    const plane = window.layoutTestScene.getObjectByName("background-plane");
    return { type: plane.geometry.type, width: plane.geometry.parameters.width, height: plane.geometry.parameters.height };
  });
  expect(geometry.type).toBe("PlaneGeometry");
  const fraction = await page.evaluate(async () => {
    const { groundFrame } = await import("/static/scene_layout_framing.js");
    return groundFrame(window.zetSceneLayout.current().data.layout_3d).visible_fraction;
  });
  expect(geometry.width / geometry.height).toBeCloseTo((8 / 5) / fraction);
  await page.locator("#scene-layout-element").selectOption("__background");
  await expect(page.locator("#scene-layout-background-controls")).toBeVisible();
  await expect(page.locator("#scene-layout-width")).toBeHidden();
  const zoom = page.locator("#scene-layout-background-zoom");
  await zoom.evaluate((input) => { input.value = "2"; });
  await zoom.dispatchEvent("input");
  await zoom.dispatchEvent("change");
  await page.locator('[data-layout-mode="camera"]').click();
  await expect(page.locator("#scene-layout-camera-frame")).toBeVisible();
  await page.waitForFunction(() => window.layoutTestCamera?.fov === 50 && Math.abs(window.layoutTestCamera.aspect - 1.6) < .001);
  const canvas = page.locator("#scene-layout-canvas");
  const bounds = await canvas.boundingBox();
  const center = { x: bounds.x + bounds.width / 2, y: bounds.y + bounds.height / 2 };
  const beforeBackground = await read();
  await page.mouse.move(center.x, center.y);
  await page.mouse.down();
  await page.mouse.move(center.x + 50, center.y + 20, { steps: 5 });
  await page.mouse.up();
  const afterBackground = await read();
  expect(afterBackground.cameras[0].background_framing.center).not.toEqual(beforeBackground.cameras[0].background_framing.center);
  expect(afterBackground.cameras[0].position).toEqual(beforeBackground.cameras[0].position);
  await page.locator('[data-layout-action="undo"]').click();
  expect((await read()).cameras[0].background_framing).toEqual(beforeBackground.cameras[0].background_framing);
  await page.locator('[data-layout-action="redo"]').click();
  const selectedCrop = (await read()).cameras[0].background_framing;
  await page.locator("#scene-layout-adjust").selectOption("camera");
  await page.locator('[data-layout-action="dolly-in"]').click();
  const dolly = await read();
  expect(dolly.cameras[0].position[2]).toBeLessThan(initial.cameras[0].position[2]);
  expect(dolly.cameras[0].background_framing).toEqual(selectedCrop);
  expect(dolly.pawns).toEqual(initial.pawns);
  const lens = page.locator("#scene-layout-lens");
  await lens.evaluate((input) => { input.value = "35"; });
  await lens.dispatchEvent("input");
  await lens.dispatchEvent("change");
  expect((await read()).cameras[0].background_framing).toEqual(selectedCrop);
  await page.locator("#scene-layout-camera-lock").check();
  const locked = await read();
  await page.mouse.move(center.x, center.y);
  await page.mouse.wheel(0, -250);
  expect((await read()).cameras).toEqual(locked.cameras);
  await expect(page.locator('[data-layout-action="dolly-in"]')).toBeDisabled();
  await page.locator("#scene-layout-camera-lock").uncheck();
  // Cancel a camera movement without changing the saved crop or viewpoint.
  await page.mouse.down();
  await page.mouse.move(center.x + 30, center.y + 10, { steps: 3 });
  await canvas.dispatchEvent("pointercancel", { pointerId: 1 });
  await page.mouse.up();
  expect((await read()).cameras).toEqual(locked.cameras);
  await page.locator("#scene-layout-horizon").check();
  await expect(page.locator("#scene-layout-horizon-line")).toBeVisible();
  await page.locator("#scene-layout-dialog").screenshot({ path: testInfo.outputPath("background-camera.png") });
  await page.locator('[data-layout-action="save"]').click();
  await expect(page.locator("#scene-layout-dialog")).toBeHidden();
  await page.locator("[data-layout-open]").click();
  expect((await read()).cameras).toEqual(locked.cameras);
  await page.locator('[data-layout-action="background-reset"]').evaluate((button) => button.click());
  expect((await read()).cameras[0].background_framing.zoom).toBe(1);
  expect(errors).toEqual([]);
});

test("browser crop matches backend across frame aspects and edge clamps", async ({ page }) => {
  await page.goto("/?page=scenes&story_slug=Alpha-Story&scene_slug=Opening-Scene");
  const data = (await (await page.request.get(`${scene}/builder?include_references=false`)).json()).document.data;
  data.scene_elements = [{ id: "arch", display_name: "Archway", resource_type: "Scene-Only", element_type: "Backdrop",
    fallback_visual_description: "A stone arch", reference_images: [{ tag: "{{SCENE:Beta-Story:Closing-Scene}}" }] }];
  data.subscenes = []; data.placements = []; data.dialogue = []; data.interactions = [];
  data.setup.composition.left_to_right = [];
  for (const [aspect, framing] of [["1:1", { center: [.5, .5], zoom: 1 }], ["8:5", { center: [0, 1], zoom: 2 }],
    ["9:16", { center: [1, 0], zoom: .5 }]]) {
    data.setup.canvas.aspect_ratio = aspect;
    data.layout_3d = { version: 2, background: { kind: "element", element_id: "arch" },
      cameras: [{ id: "main", background_framing: framing }] };
    const response = await page.request.post(`${scene}/builder/3d-layout/preview`, { data });
    expect(response.ok(), await response.text()).toBeTruthy();
    const backend = (await response.json()).projection.background;
    expect(backend).toBeTruthy();
    const crop = await page.evaluate(async ({ backend, framing }) => {
      const { backgroundCrop } = await import("/static/scene_layout_framing.js");
      return backgroundCrop(backend.source_width, backend.source_height, backend.aspect, framing);
    }, { backend, framing });
    for (const key of ["left", "top", "width", "height", "zoom"]) expect(crop[key]).toBeCloseTo(backend.crop[key], 10);
    expect(crop.center).toEqual(backend.crop.center);
  }
});

test("using the stage view as camera retains foreground, contacts and the saved ground join", async ({ page }, testInfo) => {
  test.setTimeout(60_000);
  const errors = [];
  page.on("pageerror", (error) => errors.push(error.message));
  const data = (await (await page.request.get(`${scene}/builder?include_references=false`)).json()).document.data;
  data.subscenes = []; data.dialogue = []; data.interactions = [];
  data.setup.canvas.aspect_ratio = "16:9";
  data.setup.composition.left_to_right = [];
  data.scene_elements = [
    { id: "traveler", display_name: "Traveler", resource_type: "Scene-Only", element_type: "Character",
      fallback_visual_description: "A traveler", reference_images: [] },
    { id: "arch", display_name: "Archway", resource_type: "Scene-Only", element_type: "Backdrop",
      fallback_visual_description: "A stone archway", reference_images: [{ tag: "{{SCENE:Beta-Story:Closing-Scene}}" }] },
  ];
  data.placements = data.scene_elements.map(({ id }) => ({ id: `${id}_place`, scene_element_id: id, position_within_cell: "center", depth: "midground" }));
  data.layout_3d = { version: 2, pawns: [{ element_id: "traveler", position: [0, 0, 0], body_yaw: 180,
    measurement_overrides: { height: "5 ft 8 in" } }] };
  const saved = await page.request.put(scene + "/builder", { data });
  expect(saved.ok(), await saved.text()).toBeTruthy();
  await page.goto("/?page=scenes&story_slug=Alpha-Story&scene_slug=Opening-Scene");
  await page.waitForFunction(() => document.body.dataset.dashboardReady === "true");
  await observeLayoutScene(page);
  await page.locator("#scene-builder-open").click();
  await page.locator("[data-layout-open]").click();
  await page.waitForFunction(() => window.layoutTestScene?.getObjectByName("background-plane"));
  const read = () => page.evaluate(() => structuredClone(window.zetSceneLayout.current().data.layout_3d));
  const actors = (await read()).pawns;
  await page.locator('[data-layout-view="front"]').click();
  await page.locator('[data-layout-action="camera-from-view"]').click();
  await page.locator('[data-layout-mode="camera"]').click();
  await page.locator("#scene-layout-element").selectOption("__background");
  await page.locator("#scene-layout-ground-surface").fill("a stone path");
  await page.locator("#scene-layout-ground-surface").press("Tab");
  await page.locator('[data-layout-action="ground-align"]').click();
  await expect(page.locator("#scene-layout-ground-join-line")).toBeVisible();
  const ground = await page.evaluate(async () => {
    const { groundFrame } = await import("/static/scene_layout_framing.js");
    const layout = window.zetSceneLayout.current().data.layout_3d;
    const floor = window.layoutTestScene.getObjectByName("foreground-ground");
    return { ...groundFrame(layout), meshVisible: floor.visible, cameraLayer: floor.layers.test(window.layoutTestCamera.layers),
      contacts: window.layoutTestScene.getObjectByName("ground-contact-shadows").children.length };
  });
  expect(ground.meshVisible).toBe(true); expect(ground.cameraLayer).toBe(true); expect(ground.contacts).toBe(1);
  const preview = await page.request.post(`${scene}/builder/3d-layout/preview`, { data: { ...data, layout_3d: await read() } });
  expect(preview.ok(), await preview.text()).toBeTruthy();
  const backend = (await preview.json()).projection.ground;
  for (const key of ["distance_m", "join_y", "visible_fraction", "join_min", "join_max"]) expect(ground[key]).toBeCloseTo(backend[key], 8);
  // Sample the actual WebGL canvas after a render, below the join and away from the actor.
  const pixel = await page.evaluate(() => new Promise((resolve) => requestAnimationFrame(() => {
    const source = document.querySelector("#scene-layout-canvas");
    const canvas = document.createElement("canvas"); canvas.width = source.width; canvas.height = source.height;
    const context = canvas.getContext("2d"); context.drawImage(source, 0, 0);
    const frame = document.querySelector("#scene-layout-camera-frame").getBoundingClientRect();
    const bounds = source.getBoundingClientRect();
    const x = (frame.left - bounds.left + frame.width * .1) * source.width / bounds.width;
    const y = (frame.top - bounds.top + frame.height * .9) * source.height / bounds.height;
    resolve(Array.from(context.getImageData(x, y, 1, 1).data).slice(0, 3));
  })));
  for (let index = 0; index < 3; index++) expect(pixel[index]).toBeCloseTo([185, 176, 160][index], -1);
  const join = page.locator("#scene-layout-ground-join");
  const before = (await read()).cameras[0].ground_distance_m;
  await join.evaluate((input) => { input.value = String((Number(input.min) + Number(input.max)) / 2); input.dispatchEvent(new Event("input", { bubbles: true })); input.dispatchEvent(new Event("change", { bubbles: true })); });
  expect((await read()).cameras[0].ground_distance_m).not.toBeCloseTo(before);
  await page.locator('[data-layout-action="undo"]').click();
  expect((await read()).cameras[0].ground_distance_m).toBeCloseTo(before);
  await page.locator('[data-layout-action="redo"]').click();
  const persisted = await read();
  expect(persisted.pawns).toEqual(actors);
  await page.locator("#scene-layout-dialog").screenshot({ path: testInfo.outputPath("camera-foreground.png") });
  await page.locator('[data-layout-action="save"]').click();
  await expect(page.locator("#scene-layout-dialog")).toBeHidden();
  await page.locator("[data-layout-open]").click();
  expect((await read()).ground).toEqual(persisted.ground);
  expect((await read()).cameras).toEqual(persisted.cameras);
  await page.locator("#scene-layout-element").selectOption("__background");
  await page.locator("#scene-layout-ground-enabled").uncheck();
  await page.locator('[data-layout-mode="camera"]').click();
  await page.waitForFunction(() => !window.layoutTestScene.getObjectByName("foreground-ground").visible);
  expect(errors).toEqual([]);
});

test("free backdrop fitting, locked actor boundary and group preview match the full-scene guide", async ({ page }) => {
  test.setTimeout(60_000);
  const data = (await (await page.request.get(`${scene}/builder?include_references=false`)).json()).document.data;
  data.setup.canvas.aspect_ratio = "16:9"; data.setup.composition.left_to_right = [];
  data.dialogue = []; data.interactions = [];
  data.subscenes = [{ id: "boys", kind: "element", enabled: true, name: "Boys", anchor_element_id: "group" }];
  data.scene_elements = [
    { id: "traveler", display_name: "Traveler", resource_type: "Scene-Only", element_type: "Character", fallback_visual_description: "A traveler", reference_images: [] },
    { id: "arch", display_name: "Arch", resource_type: "Scene-Only", element_type: "Backdrop", fallback_visual_description: "A stone arch", reference_images: [{ tag: "{{SCENE:Beta-Story:Closing-Scene}}" }] },
    { id: "group", display_name: "Boys", resource_type: "Scene-Only", element_type: "Prop", fallback_visual_description: "Three schoolboys", reference_images: [] },
    ...["red", "blond", "dark"].map(id => ({ id, display_name: id, element_type: "Character", resource_type: "Scene-Only", subscene_id: "boys", fallback_visual_description: "A schoolboy", reference_images: [] })),
  ];
  data.placements = data.scene_elements.map(({ id }) => ({ id: `${id}_place`, scene_element_id: id, position_within_cell: "center", depth: "midground" }));
  data.layout_3d = { version: 2, cameras: [{ id: "main", ground_distance_m: 16 }], pawns: [
    { element_id: "traveler", position: [0, 0, 0], measurement_overrides: { height: "5 ft 8 in" } },
    { element_id: "group", position: [0, 0, -3], dimensions: { width: 1.2, height: 1, depth: .3 } },
    ...["red", "blond", "dark"].map((id, index) => ({ element_id: id, position: [index - 1, 0, -3] })),
  ] };
  const saved = await page.request.put(scene + "/builder", { data }); expect(saved.ok(), await saved.text()).toBeTruthy();
  await page.goto("/?page=scenes&story_slug=Alpha-Story&scene_slug=Opening-Scene");
  await page.waitForFunction(() => document.body.dataset.dashboardReady === "true"); await observeLayoutScene(page);
  await page.locator("#scene-builder-open").click(); await page.locator("[data-layout-open]").click();
  await page.waitForFunction(() => window.layoutTestScene?.getObjectByName("background-plane"));
  await page.locator("#scene-layout-element").selectOption("__background");
  await page.locator('[data-layout-action="background-fit"]').click();
  const read = () => page.evaluate(() => structuredClone(window.zetSceneLayout.current().data.layout_3d));
  expect((await read()).cameras[0].background_framing.zoom).toBeLessThan(1);
  const zoom = page.locator("#scene-layout-background-zoom");
  await zoom.evaluate(input => { input.value = ".25"; input.dispatchEvent(new Event("input", { bubbles: true })); input.dispatchEvent(new Event("change", { bubbles: true })); });
  await page.locator('[data-layout-mode="camera"]').click();
  const groups = await page.evaluate(() => ({ children: window.layoutTestScene.getObjectByName("group").children.filter(child => child.name.startsWith("group-member-")).length,
    childVisible: window.layoutTestScene.getObjectByName("group").children.some(child => child.name === "group-member-red" && child.children.some(grandchild => grandchild.layers.test(window.layoutTestCamera.layers))) }));
  expect(groups.children).toBe(3); expect(groups.childVisible).toBe(true);
  const response = await page.request.post(`${scene}/builder/3d-layout/preview`, { data: { ...data, layout_3d: await read() } });
  expect(response.ok(), await response.text()).toBeTruthy();
  const preview = await response.json();
  expect(preview.projection.background.extension_regions.length).toBeGreaterThan(0);
  expect(preview.projection.subjects.map(subject => subject.element_id).sort()).toEqual(["group", "traveler"]);
  await page.locator('[data-layout-mode="stage"]').click(); await page.locator("#scene-layout-element").selectOption("traveler");
  const plane = await page.evaluate(() => window.layoutTestScene.getObjectByName("background-display").position.toArray());
  const camera = (await read()).cameras[0];
  await page.locator("#scene-layout-z").fill("-100 ft"); await page.locator("#scene-layout-z").press("Tab");
  const clamped = await read();
  expect(clamped.pawns[0].position[2]).toBeGreaterThan(-8);
  expect(clamped.cameras[0]).toEqual(camera);
  expect(await page.evaluate(() => window.layoutTestScene.getObjectByName("background-display").position.toArray())).toEqual(plane);
  await page.locator('[data-layout-action="undo"]').click(); expect((await read()).pawns[0].position).toEqual([0, 0, 0]);
  await page.locator('[data-layout-action="redo"]').click();
  const final = await read(); await page.locator('[data-layout-action="save"]').click();
  await expect(page.locator("#scene-layout-dialog")).toBeHidden(); await page.locator("[data-layout-open]").click();
  expect((await read()).cameras[0].background_framing).toEqual(final.cameras[0].background_framing);
  expect((await read()).pawns[0].position).toEqual(final.pawns[0].position);
});

test("subscene members edit in local coordinates and return to their unchanged parent placement", async ({ page }) => {
  const data = (await (await page.request.get(`${scene}/builder?include_references=false`)).json()).document.data;
  data.subscenes = [{ id: "pair", kind: "element", enabled: true, name: "Pair", anchor_element_id: "pair-anchor" }];
  data.scene_elements = [
    { id: "outside", display_name: "Outside", resource_type: "Scene-Only", element_type: "Character", fallback_visual_description: "A person", reference_images: [] },
    { id: "pair-anchor", display_name: "Pair", resource_type: "Scene-Only", element_type: "Prop", fallback_visual_description: "Two people", reference_images: [] },
    { id: "member", display_name: "Member", resource_type: "Scene-Only", element_type: "Character", subscene_id: "pair", fallback_visual_description: "A person", reference_images: [] },
  ];
  data.placements = data.scene_elements.map(({ id }) => ({ id: `${id}_place`, scene_element_id: id, position_within_cell: "center", depth: "midground" }));
  data.layout_3d = { version: 2, cameras: [{ id: "main", position: [0, 1.7, 12], target: [0, 1, 0] }], pawns: [
    { element_id: "outside", position: [-2, 0, 0], measurement_overrides: { height: "5 ft" } },
    { element_id: "pair-anchor", position: [4, 0, -2], body_yaw: 90, dimensions: { width: 1, height: 1, depth: .3 } },
    { element_id: "member", position: [5, 0, -2], measurement_overrides: { height: "5 ft 6 in" } },
  ] };
  const saved = await page.request.put(scene + "/builder", { data }); expect(saved.ok(), await saved.text()).toBeTruthy();
  await page.goto("/?page=scenes&story_slug=Alpha-Story&scene_slug=Opening-Scene");
  await page.waitForFunction(() => document.body.dataset.dashboardReady === "true"); await observeLayoutScene(page);
  await page.locator("#scene-builder-open").click(); await page.locator("[data-layout-open]").click();
  await expect(page.locator("#scene-layout-dialog")).toBeVisible();
  await expect.poll(() => page.evaluate(() => window.layoutTestScene?.getObjectByName("pair-anchor")?.children.filter(child => child.name.startsWith("group-member-")).length)).toBe(1);
  await page.locator("#scene-layout-element").selectOption("pair-anchor");
  await expect(page.locator('[data-layout-action="edit-contents"]')).toBeVisible();
  await page.locator('[data-layout-action="edit-contents"]').click();
  await expect(page.locator("#scene-layout-breadcrumb")).toHaveText("Full Scene › Pair");
  await page.locator("#scene-layout-element").selectOption("member");
  await page.locator("#scene-layout-x").fill("2 ft"); await page.locator("#scene-layout-x").press("Tab");
  await expect.poll(() => page.evaluate(() => window.zetSceneLayout.current().layout.pawns.find(pawn => pawn.element_id === "member").position[0])).toBeCloseTo(.6096, 3);
  await page.locator('[data-layout-action="undo"]').click();
  await expect.poll(() => page.evaluate(() => window.zetSceneLayout.current().layout.pawns.find(pawn => pawn.element_id === "member").position[0])).toBeCloseTo(0, 3);
  await page.locator('[data-layout-action="redo"]').click();
  await expect.poll(() => page.evaluate(() => window.zetSceneLayout.current().layout.pawns.find(pawn => pawn.element_id === "member").position[0])).toBeCloseTo(.6096, 3);
  await page.locator('[data-layout-action="parent-workspace"]').click();
  await expect(page.locator("#scene-layout-breadcrumb")).toHaveText("Full Scene");
  await expect(page.locator('[data-layout-action="undo"]')).toBeDisabled();
  const parentPose = await page.evaluate(() => structuredClone(window.zetSceneLayout.current().layout.pawns.find(pawn => pawn.element_id === "pair-anchor").position));
  expect(parentPose).toEqual([4, 0, -2]);
  await page.locator("#scene-layout-element").selectOption("pair-anchor");
  await page.locator('[data-layout-action="edit-contents"]').click();
  await expect.poll(() => page.evaluate(() => window.zetSceneLayout.current().layout.pawns.find(pawn => pawn.element_id === "member").position[0])).toBeCloseTo(.6096, 3);
  await page.locator('[data-layout-action="save"]').click(); await expect(page.locator("#scene-layout-dialog")).toBeHidden();
  const persisted = (await (await page.request.get(`${scene}/builder?include_references=false`)).json()).document.data;
  expect(persisted.subscenes.find(target => target.id === "pair").layout_3d.pawns.find(pawn => pawn.element_id === "member").position[0]).toBeCloseTo(.6096, 3);
  expect(persisted.layout_3d.pawns.find(pawn => pawn.element_id === "pair-anchor").position).toEqual([4, 0, -2]);
});
