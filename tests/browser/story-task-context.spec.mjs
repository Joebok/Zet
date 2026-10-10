import { expect, test } from "@playwright/test";

const metadata = {configured:true,project_id:"project-aaaaaaaa",board_url:"http://127.0.0.1:8000/",zet_revision:"a".repeat(40)};
const png = Buffer.from("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+/QioAAAAASUVORK5CYII=","base64");

async function capture(page, button = "#toolbar-create-task") {
  await page.locator(button).click();
  await expect(page.locator("#task-capture-submit")).toBeEnabled();
  return JSON.parse(await page.locator("#task-capture-context").textContent());
}

async function narrative(page, kind = "subscene") {
  await page.route("**/api/tasks/config",route=>route.fulfill({json:metadata}));
  const story = await (await page.request.post("/api/narrative/stories",{data:{title:"Task story"}})).json();
  const scene = await (await page.request.post(`/api/narrative/stories/${story.id}/scenes`,{data:{title:"Task scene"}})).json();
  const base = `/api/narrative/stories/${story.id}/scenes/${scene.id}`;
  const target = await (await page.request.post(`${base}/targets`,{data:{title:"Task target",kind}})).json();
  const targetBase = `${base}/targets/${target.id}`;
  const data = await (await page.request.get(targetBase)).json();
  data.candidates = {"report-image":{id:"report-image",slot:1,status:"COMPLETE",image:"test.png",prompt:"SECRET PROMPT",prompt_provenance:{}}};
  data.slots[0] = "report-image"; data.selected_id = "report-image";
  await page.route(`**${targetBase}`,route=>route.fulfill({json:data}));
  await page.route(`**${targetBase}/candidates/*/image?**`,route=>route.fulfill({body:png,contentType:"image/png"}));
  return {story,scene,target,data,url:`/narrative?story=${story.id}&scene=${scene.id}&target=${target.id}`,targetBase};
}

for (const kind of ["subscene","backdrop","assembly"]) {
  test(`Narrative ${kind} capture and candidate return use resolved IDs and labels`,async({page})=>{
    const item = await narrative(page,kind);
    await page.goto(item.url);
    await page.waitForFunction(()=>document.body.dataset.narrativeReady==="true");
    const snapshot = await capture(page);
    expect(snapshot.selections).toMatchObject({story:{state:"selected",id:item.story.id,label:"Task story"},
      scene:{state:"selected",id:item.scene.id,label:"Task scene"},render_target:{state:"selected",id:item.target.id,label:"Task target"},candidate:{state:"selected",id:"report-image"}});
    if(kind==="subscene") expect(snapshot.selections.subscene.id).toBe(item.target.id);
    else expect(snapshot.selections.subscene).toBeUndefined();
    expect(snapshot.selections.character).toBeUndefined();
    expect(JSON.stringify(snapshot)).not.toContain("SECRET PROMPT");
    await page.goto(snapshot.source_url);
    await expect(page.locator("#image-dialog")).toBeVisible();
    await expect(page.locator("#review-image")).toHaveAttribute("alt","Slot 1 candidate");
    const again = await capture(page,"#narrative-review-task");
    expect(again).toEqual(snapshot);
  });
}

test("Narrative task submission does not save the narrative document",async({page})=>{
  const item = await narrative(page);
  const writes = [];
  page.on("request",request=>{if(request.url().includes("/api/narrative/")&&request.method()!=="GET") writes.push(request.url());});
  await page.route("**/api/tasks",route=>route.fulfill({status:201,json:{task_id:"task-aaaaaaaa",created:true,board_url:"http://127.0.0.1:8000/?task_id=task-aaaaaaaa"}}));
  await page.goto(item.url);
  await page.waitForFunction(()=>document.body.dataset.narrativeReady==="true");
  await capture(page);
  await page.locator("#task-capture-title").fill("Narrative problem");
  await page.locator("#task-capture-submit").click();
  await expect(page.locator("#task-capture-ticket")).toBeVisible();
  expect(writes).toEqual([]);
});

test("Narrative missing target and universe remain accessible with an unavailable snapshot",async({page})=>{
  const item = await narrative(page);
  await page.goto(`/narrative?task_context=1&task_universe=Deleted&story=${item.story.id}&scene=${item.scene.id}&target=Deleted`);
  await expect(page.locator("#task-context-notice")).toContainText('universe "Deleted" is unavailable');
  await expect(page.locator("#narrative-root")).toContainText("Narrative selection unavailable");
  const snapshot = await capture(page);
  expect(snapshot.selections.render_target).toMatchObject({state:"unavailable",id:"Deleted"});
});

test("Narrative missing candidate keeps the target open without changing selected images",async({page})=>{
  const item = await narrative(page);
  await page.goto(item.url+"&task_context=1&task_candidate=Deleted");
  await expect(page.locator("#task-context-notice")).toContainText('candidate "Deleted" is unavailable');
  await expect(page.locator("#narrative-root h1")).toContainText("Task target");
  await expect(page.locator("#image-dialog")).not.toBeVisible();
});

test("Narrative loading context freezes before target data arrives",async({page})=>{
  const item = await narrative(page);
  let release;
  const gate = new Promise(resolve=>{release=resolve;});
  await page.route(`**${item.targetBase}`,async route=>{await gate;await route.fulfill({json:item.data});});
  await page.goto(item.url);
  await expect(page.locator("#narrative-message")).toHaveText("Loading…");
  const snapshot = await capture(page);
  expect(snapshot.selections.render_target).toMatchObject({state:"loading",id:item.target.id});
  release();
  await page.waitForFunction(()=>document.body.dataset.narrativeReady==="true");
  expect(JSON.parse(await page.locator("#task-capture-context").textContent())).toEqual(snapshot);
});

async function main(page, pageName = "scene-builder", extra = "") {
  await page.route("**/api/tasks/config",route=>route.fulfill({json:metadata}));
  await page.goto(`/?page=${pageName}&story_slug=Alpha-Story&scene_slug=Opening-Scene&task_context=1${extra}`);
  await page.waitForFunction(()=>document.body.dataset.dashboardReady==="true");
  await expect(page.locator(`#${pageName}-page`)).toHaveClass(/active/);
}

test("main story context excludes unrelated character selections and restores scene",async({page})=>{
  await main(page,"scenes");
  const snapshot = await capture(page);
  expect(snapshot.selections.story).toMatchObject({state:"selected",id:"Alpha-Story",label:"Alpha Story"});
  expect(snapshot.selections.scene).toMatchObject({state:"selected",id:"Opening-Scene"});
  expect(snapshot.selections.character).toBeUndefined();
  await page.goto(snapshot.source_url);
  await expect(page.locator("#header-scene-select")).toHaveValue("Opening-Scene");
});

test("main builder restores subscene and editor element from its backend document",async({page})=>{
  await page.route("**/api/stories/Alpha-Story/scenes/Opening-Scene/builder?**",async route=>{
    const response = await route.fetch();
    const value = await response.json();
    value.document.data.subscenes = [{id:"report-target",name:"Report target",role:"character-group",color:"#668899",canvas_width:1024,canvas_height:1024}];
    value.document.data.scene_elements = [{id:"report-element",name:"Report element",kind:"prop",appearance:"SECRET SOURCE",reference_images:[]}];
    value.document.data.placements = [];
    await route.fulfill({json:value});
  });
  await main(page,"scene-builder","&render_target_id=report-target&task_element=report-element");
  const snapshot = await capture(page);
  expect(snapshot.selections.subscene).toMatchObject({state:"selected",id:"report-target",label:"Report target"});
  expect(snapshot.selections.editor_element).toMatchObject({state:"selected",id:"report-element",label:"Report element"});
  expect(JSON.stringify(snapshot)).not.toContain("SECRET SOURCE");
  await page.goto(snapshot.source_url);
  await expect.poll(()=>page.evaluate(()=>state.activeBuilderRenderTarget)).toBe("report-target");
  await expect.poll(()=>page.evaluate(()=>state.selectedBuilderElementId)).toBe("report-element");
});

test("main missing story, scene, and render target show restoration notices",async({page})=>{
  await main(page,"scene-builder","&render_target_id=Deleted");
  await expect(page.locator("#task-context-notice")).toContainText('render target "Deleted" is unavailable');
  await page.goto("/?page=scenes&task_context=1&story_slug=Deleted");
  await expect(page.locator("#task-context-notice")).toContainText('story "Deleted" is unavailable');
  await page.goto("/?page=scenes&task_context=1&story_slug=Alpha-Story&scene_slug=Deleted");
  await expect(page.locator("#task-context-notice")).toContainText('scene "Deleted" is unavailable');
});

test("main scene-batch return does not create a missing batch",async({page})=>{
  const methods = [];
  await page.route("**/api/stories/Alpha-Story/scenes/Opening-Scene/local-batches",route=>{
    methods.push(route.request().method()); return route.fulfill({json:{batches:[]}});
  });
  await main(page,"scene-batches","&batch=Deleted");
  await expect(page.locator("#task-context-notice")).toContainText('scene batch "Deleted" is unavailable');
  expect(methods).toEqual(["GET"]);
  const snapshot = await capture(page);
  expect(snapshot.selections.run).toMatchObject({state:"unavailable",id:"Deleted"});
});

test("scene cards on Batches capture story context instead of header character",async({page})=>{
  await page.route("**/api/tasks/config",route=>route.fulfill({json:metadata}));
  await page.route("**/api/local/batch-status",route=>route.fulfill({json:{groups:[{label:"Scene",batches:[{
    run_id:"scene-report",batch_name:"Scene report",pipeline:"scene",story_slug:"Alpha-Story",scene_slug:"Opening-Scene",status:"RUNNING"}]}]}}));
  await page.goto("/?page=local-batch-status");
  const snapshot = await capture(page,'[data-run-id="scene-report"] button');
  expect(snapshot.selections.story.id).toBe("Alpha-Story");
  expect(snapshot.selections.scene.id).toBe("Opening-Scene");
  expect(snapshot.selections.character).toBeUndefined();
});

test("main candidate return restores its source, filtered candidate, and import story",async({page})=>{
  await page.route("**/api/scene-candidate-sources",route=>route.fulfill({json:{sources:[
    {key:"first",label:"First",path:"SECRET PATH"},{key:"report-source",label:"Report source",path:"SECRET PATH"}]}}));
  await page.route("**/api/scene-candidates?**",route=>route.fulfill({json:{items:[
    {candidate_id:"other",title:"Other",source_key:"report-source",import_state:"new",fields:{}},
    {candidate_id:"report-candidate",title:"Report candidate",source_key:"report-source",import_state:"passed",fields:{Prompt:"SECRET PROMPT"}}]}}));
  await main(page,"scene-candidates","&task_source=report-source&task_candidate=report-candidate");
  await expect(page.locator("#scene-candidate-detail h2")).toHaveText("Report candidate");
  const snapshot = await capture(page);
  expect(snapshot.selections.candidate).toMatchObject({state:"selected",id:"report-candidate",label:"Report candidate"});
  expect(snapshot.selections.scene).toBeUndefined();
  expect(JSON.stringify(snapshot)).not.toContain("SECRET");
  await page.goto(snapshot.source_url);
  await expect(page.locator("#scene-candidate-source")).toHaveValue("report-source");
  await expect(page.locator("#scene-candidate-filter")).toHaveValue("passed");
  await expect(page.locator("#scene-candidate-detail h2")).toHaveText("Report candidate");
});

test("scene-batch candidate return restores the recorded batch and review image read-only",async({page})=>{
  const base = "/api/stories/Alpha-Story/scenes/Opening-Scene/local-batches";
  const run = await (await page.request.post(base,{data:{}})).json();
  const target = run.targets[0];
  const candidate = run.groups[target.target_id].candidates[0];
  candidate.status="COMPLETE"; candidate.image_path="fixture.png";
  run.groups[target.target_id].active_candidates=[candidate];
  const methods=[];
  await page.route(`**${base}`,route=>{methods.push(route.request().method());return route.fulfill({json:{batches:[{run_id:run.run_id}]}});});
  await page.route(`**${base}/${run.run_id}`,route=>route.fulfill({json:run}));
  await page.route(`**${base}/${run.run_id}/targets/*/candidates/*/image?**`,route=>route.fulfill({body:png,contentType:"image/png"}));
  await main(page,"scene-batches",`&batch=${run.run_id}&task_target=${target.target_id}&task_candidate=${candidate.candidate_id}`);
  await expect(page.locator("#scene-batch-review-dialog")).toBeVisible();
  const snapshot=await capture(page,"#scene-batch-review-task");
  expect(snapshot.selections).toMatchObject({run:{state:"selected",id:run.run_id},candidate:{state:"selected",id:candidate.candidate_id},render_target:{state:"selected",id:target.target_id}});
  expect(methods).toEqual(["GET"]);
  await page.goto(snapshot.source_url);
  await expect(page.locator("#scene-batch-review-dialog")).toBeVisible();
});

test("Narrative capture fits a narrow viewport",async({page})=>{
  const item=await narrative(page);
  await page.setViewportSize({width:390,height:844});
  await page.goto(item.url);
  await page.waitForFunction(()=>document.body.dataset.narrativeReady==="true");
  await capture(page);
  expect(await page.locator("#task-capture-dialog").evaluate(node=>node.scrollWidth<=node.clientWidth)).toBe(true);
  await page.screenshot({path:"test-results/narrative-task-capture.png"});
});

test("missing recorded scene cannot initialize a batch on its fallback scene",async({page})=>{
  const methods=[];
  await page.route("**/api/stories/*/scenes/*/local-batches",route=>{
    methods.push(route.request().method()); return route.fulfill({json:{batches:[]}});
  });
  await page.route("**/api/tasks/config",route=>route.fulfill({json:metadata}));
  await page.goto("/?page=scene-batches&task_context=1&story_slug=Alpha-Story&scene_slug=Deleted&batch=Deleted");
  await expect(page.locator("#task-context-notice")).toContainText('scene "Deleted" is unavailable');
  await expect(page.locator("#task-context-notice")).toContainText("No batch was created");
  expect(methods).toEqual(["GET"]);
});

test("builder loading snapshot retains the requested render target",async({page})=>{
  await page.route("**/api/tasks/config",route=>route.fulfill({json:metadata}));
  let release;
  const gate=new Promise(resolve=>{release=resolve;});
  await page.route("**/api/stories/Alpha-Story/scenes/Opening-Scene/builder?**",async route=>{
    const response=await route.fetch();
    const data=await response.json();
    data.document.data.subscenes=[{id:"pending-target",name:"Pending target",role:"character-group",color:"#668899",canvas_width:1024,canvas_height:1024}];
    await gate;
    await route.fulfill({json:data});
  });
  await page.goto("/?page=scene-builder&task_context=1&story_slug=Alpha-Story&scene_slug=Opening-Scene&render_target_id=pending-target");
  await expect(page.locator("#scene-builder-page")).toHaveClass(/active/);
  const snapshot=await capture(page);
  expect(snapshot.selections.render_target).toMatchObject({state:"loading",id:"pending-target"});
  release();
  await page.waitForFunction(()=>document.body.dataset.dashboardReady==="true");
  expect(JSON.parse(await page.locator("#task-capture-context").textContent())).toEqual(snapshot);
});

test("Zine reports retain the selected document and restore it",async({page})=>{
  await page.route("**/api/zines",route=>route.fulfill({json:{zines:[{slug:"Other-Zine",title:"Other"},{slug:"Report-Zine",title:"Report Zine"}]}}));
  await page.route("**/api/zines/Report-Zine",route=>route.fulfill({json:{document:{zine:{slug:"Report-Zine"},metadata:{zine_name:"Report Zine",slots:{}},text:"SECRET DOCUMENT"}}}));
  await main(page,"zine","&task_zine=Report-Zine");
  const snapshot=await capture(page);
  expect(snapshot.selections.zine).toMatchObject({state:"selected",id:"Report-Zine",label:"Report Zine"});
  expect(JSON.stringify(snapshot)).not.toContain("SECRET DOCUMENT");
  await page.goto(snapshot.source_url);
  await expect(page.locator("#zine-editor-title")).toHaveText("Report Zine");
});

test("late scene-batch responses cannot replace the current report context",async({page})=>{
  const base="/api/stories/Alpha-Story/scenes/Opening-Scene/local-batches";
  const prototype=await(await page.request.post(base,{data:{}})).json();
  let lists=0, olderRequested=false, release;
  const gate=new Promise(resolve=>{release=resolve;});
  await page.route(`**${base}`,route=>route.fulfill({json:{batches:[{run_id:["current","older","latest"][lists++]}]}}));
  await page.route(`**${base}/*`,async route=>{
    const id=new URL(route.request().url()).pathname.split("/").at(-1);
    if(id==="older") {olderRequested=true;await gate;}
    await route.fulfill({json:{...prototype,run_id:id}});
  });
  await main(page,"scene-batches","&batch=current");
  await page.evaluate(()=>{void window.SceneBatches.open({story:"Alpha-Story",scene:"Opening-Scene"});});
  await expect.poll(()=>olderRequested).toBe(true);
  await page.evaluate(()=>window.SceneBatches.open({story:"Alpha-Story",scene:"Opening-Scene"}));
  const lateResponse=page.waitForResponse(response=>new URL(response.url()).pathname.endsWith("/older"));
  release();await lateResponse;
  const snapshot=await capture(page);
  expect(snapshot.selections.run).toMatchObject({state:"selected",id:"latest"});
});
