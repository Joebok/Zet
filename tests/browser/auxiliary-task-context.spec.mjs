import { expect, test } from "@playwright/test";
import { restorePristineProjectState } from "./scene-fixtures.mjs";

test.beforeEach(restorePristineProjectState);
const metadata = {configured:true,project_id:"project-aaaaaaaa",board_url:"http://127.0.0.1:8000/",zet_revision:"a".repeat(40)};
const png = Buffer.from("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+/QioAAAAASUVORK5CYII=", "base64");
const screenshot = {name:"screen.png",mimeType:"image/png",buffer:png};
const receipt = {task_id:"task-aaaaaaaa",board_url:"http://127.0.0.1:8000/?task_id=task-aaaaaaaa",created:true};

async function setup(page) {
  await page.route("**/api/tasks/config",route=>route.fulfill({json:metadata}));
  await page.route("**/api/universes",route=>route.fulfill({json:{selected_universe_id:"Moonsea",universes:[{universe_id:"Moonsea"},{universe_id:"Other"}]}}));
}
async function snapshot(page, button="#toolbar-create-task") {
  await page.locator(button).click();
  await expect(page.locator("#task-capture-submit")).toBeEnabled();
  return JSON.parse(await page.locator("#task-capture-context").textContent());
}
async function gateFixtures(page) {
  await setup(page);
  await page.route("**/api/gate-test-rig/catalog*",route=>route.fulfill({json:{pipelines:[{key:"body-reference",label:"Body Reference"}],views:["FRONT"],gates:{orientation:{}},gates_by_view:{FRONT:[{key:"orientation",prompt:"SECRET PROMPT",image_roles:["candidate"]}]}}}));
  await page.route("**/api/gate-test-data?*",route=>route.fulfill({json:{cases:[{case_id:"case-1",pipeline:"body-reference",gate:"orientation",view:"FRONT",expected:"PASS"}]}}));
  await page.route("**/api/gate-test-data/**/image/candidate*",route=>route.fulfill({body:png,contentType:"image/png"}));
  await page.route("**/api/gate-test-rig/tests",route=>route.fulfill({json:{tests:[{test_id:"test-1",name:"Saved test",pipeline:"body-reference",gate:"orientation",status:"COMPLETE"}]}}));
  const record={run_id:"run-1",pipeline:"body-reference",gate:"orientation",status:"COMPLETE",config:{model:"fixture",api:"generate",think:false},attempts:[{case_id:"case-1",view:"FRONT",expected:"PASS",status:"COMPLETE",actual:"PASS",result:"PASS",response:"SECRET RESPONSE"}]};
  await page.route("**/api/gate-test-rig/tests/test-1",route=>route.fulfill({json:record}));
  await page.route("**/api/gate-test-rig/runs/run-1",route=>route.fulfill({json:record}));
  await page.route("**/api/ai-controls/ollama-models",route=>route.fulfill({json:{models:[]}}));
}

test("overview reports its chosen slot and restores it without starting generation",async({page})=>{
  await setup(page);
  await page.route("**/api/local/character-overview",route=>route.fulfill({json:{rows:[{character:"Test",phase:"Adult",costumes:[{name:"Cloak",state:"IDLE",job_id:"job-1",pipeline:"head-image"}]}]}}));
  const writes=[];
  page.on("request",r=>{if(r.method()!=="GET")writes.push(r.url())});
  await page.goto("/local-character-overview?secret=EXCLUDED");
  const context=await snapshot(page,"[data-report-slot]");
  expect(context).toMatchObject({page_id:"local-character-overview",universe_id:"Moonsea",selections:{character:{id:"Test",state:"selected"},phase:{id:"Adult"},costume:{id:"Cloak"},run:{id:"job-1"},pipeline:{id:"head-image"}}});
  expect(context.source_url).not.toContain("secret");
  await page.goto(context.source_url);
  await expect(page.locator(".slot.task-context-selected")).toContainText("Cloak");
  expect((await snapshot(page)).selections.costume.id).toBe("Cloak");
  expect(writes).toEqual([]);
});

test("gate data captures a case and frozen context survives selection changes",async({page})=>{
  await gateFixtures(page);
  await page.goto("/gate-test-data");
  const context=await snapshot(page,"[data-report-case]");
  expect(context.selections).toMatchObject({pipeline:{id:"body-reference",label:"Body Reference"},gate:{id:"orientation"},test_case:{id:"case-1",label:"FRONT"}});
  expect(JSON.stringify(context)).not.toContain("SECRET");
  await page.locator("#task-capture-close").click();
  await page.locator("#refresh").click();
  expect(await snapshot(page)).toEqual(context);
  await page.evaluate(()=>localStorage.removeItem("zet.task-draft.v1"));
  await page.goto(context.source_url);
  await expect(page.locator(".case.task-context-selected")).toBeVisible();
  expect((await snapshot(page)).selections.test_case.state).toBe("selected");
});

test("rig saved test and result capture restore only through reads",async({page})=>{
  await gateFixtures(page);
  const writes=[];page.on("request",r=>{if(r.method()!=="GET")writes.push(r.url())});
  await page.goto("/gate-test-rig?task_context=1&task_universe=Other&test_id=test-1&case_id=case-1");
  await expect(page.locator(".result.task-context-selected")).toBeVisible();
  const context=await snapshot(page,".result [data-task-report]");
  expect(context).toMatchObject({page_id:"gate-test-rig",universe_id:"Other",selections:{run:{state:"selected",id:"run-1"},gate:{id:"orientation"},test_case:{id:"case-1"}}});
  expect(JSON.stringify(context)).not.toContain("SECRET");
  expect(new URL(context.source_url).searchParams.get("test_id")).toBe("test-1");
  expect(writes).toEqual([]);
});

test("missing auxiliary references produce notices while opening the page",async({page})=>{
  await gateFixtures(page);
  await page.goto("/gate-test-data?task_context=1&task_universe=Deleted&pipeline=deleted&gate=deleted&case_id=deleted");
  await expect(page.locator("#task-context-notice")).toContainText("unavailable");
  await expect(page.locator("[data-report-case]")).toBeVisible();
  const context=await snapshot(page);
  expect(context.selections.test_case).toMatchObject({state:"unavailable",id:"deleted"});
});

test("screenshots survive interrupted uploads and intake retries with the same report",async({page})=>{
  await setup(page);
  let fail=true;const uploads=[],reports=[];
  await page.route("**/api/tasks/attachments",route=>{
    uploads.push(route.request().postDataJSON());
    return fail?route.fulfill({status:504,json:{detail:"Upload timed out"}}):route.fulfill({status:200,json:{attachment_id:"attachment-"+"a".repeat(32),filename:"screen.png",content_type:"image/png",created:false}});
  });
  await page.route("**/api/tasks",route=>{
    reports.push(route.request().postDataJSON());
    return reports.length===1?route.fulfill({status:503,json:{detail:"Intake unavailable"}}):route.fulfill({status:201,json:receipt});
  });
  await page.goto("/local-character-overview");
  await snapshot(page);
  await page.locator("#task-capture-title").fill("Preview bug");
  await page.locator("#task-capture-files").setInputFiles(screenshot);
  await expect(page.locator("#task-capture-screenshots img")).toBeVisible();
  await page.locator("#task-capture-submit").click();
  await expect(page.locator("#task-capture-status")).toContainText("Upload timed out");
  expect(reports).toHaveLength(0);
  fail=false;
  await page.reload();await snapshot(page);
  await page.locator("#task-capture-submit").click();
  await expect(page.locator("#task-capture-status")).toContainText("Intake unavailable");
  await expect(page.getByRole("button",{name:"Remove",exact:true})).toBeDisabled();
  await page.reload();await snapshot(page);
  await page.locator("#task-capture-submit").click();
  await expect(page.locator("#task-capture-ticket")).toBeVisible();
  expect(uploads).toHaveLength(2);
  expect(uploads[0]).toEqual(uploads[1]);
  expect(reports[0]).toEqual(reports[1]);
  expect(reports[0].request_id).toBe(uploads[0].request_id);
  expect(reports[0].attachment_ids).toEqual(["attachment-"+"a".repeat(32)]);
  expect(JSON.stringify(reports)).not.toContain("content_base64");
});

test("paste adds optional screenshots and invalid files leave the draft editable",async({page})=>{
  await setup(page);await page.goto("/gate-test-data");await snapshot(page);
  await page.locator("#task-capture-paste").evaluate((node,encoded)=>{
    const bytes=Uint8Array.from(atob(encoded),c=>c.charCodeAt(0));
    const data=new DataTransfer();data.items.add(new File([bytes],"pasted.png",{type:"image/png"}));
    node.dispatchEvent(new ClipboardEvent("paste",{bubbles:true,clipboardData:data}));
  },png.toString("base64"));
  await expect(page.locator("#task-capture-screenshots li")).toHaveCount(1);
  await page.locator("#task-capture-files").setInputFiles({name:"unsafe.svg",mimeType:"image/svg+xml",buffer:Buffer.from("<svg/>")});
  await expect(page.locator("#task-capture-status")).toContainText("PNG, JPEG, or WebP");
  await expect(page.locator("#task-capture-screenshots li")).toHaveCount(1);
  await page.getByRole("button",{name:"Remove",exact:true}).click();
  await expect(page.locator("#task-capture-screenshots li")).toHaveCount(0);
  await expect(page.locator("#task-capture-title")).toBeEnabled();
});

test("screenshot limits and browser quota failure keep one in-memory frozen draft",async({page})=>{
  await setup(page);
  await page.goto("/local-character-overview");await snapshot(page);
  await page.locator("#task-capture-files").setInputFiles({...screenshot,name:"large.png",buffer:Buffer.alloc(5*1024*1024+1)});
  await expect(page.locator("#task-capture-status")).toContainText("at most 5 MiB");
  await page.locator("#task-capture-files").setInputFiles(Array.from({length:5},(_,i)=>({...screenshot,name:`screen-${i}.png`})));
  await expect(page.locator("#task-capture-status")).toContainText("at most four");
  await page.evaluate(()=>{
    const set=Storage.prototype.setItem;
    Storage.prototype.setItem=function(key,value){if(key==="zet.task-draft.v1")throw new Error("Quota");return set.call(this,key,value)};
  });
  await page.locator("#task-capture-files").setInputFiles(screenshot);
  await expect(page.locator("#task-capture-status")).toContainText("keep this tab open");
  await page.locator("#task-capture-title").fill("In memory with screenshot");
  await page.locator("#task-capture-close").click();await snapshot(page);
  await expect(page.locator("#task-capture-screenshots li")).toHaveCount(1);
  await expect(page.locator("#task-capture-title")).toHaveValue("In memory with screenshot");
});

test("image generation review captures result identifiers without copying prompts or images",async({page})=>{
  await setup(page);
  await page.route("**/fixture.png",route=>route.fulfill({body:png,contentType:"image/png"}));
  await page.goto("/?page=image-generation");
  await page.waitForFunction(()=>document.body.dataset.dashboardReady==="true");
  await page.evaluate(()=>{
    imageGenerationSlots[0]={requestId:"report-job",index:0};
    imageGenerationJobs.set("report-job",{prompt:"SECRET PROMPT",negative_prompt:"SECRET NEGATIVE",status:"COMPLETE",images:[{index:0,url:"/fixture.png"}]});
    openImageGenerationReview(0);
  });
  const context=await snapshot(page,"#image-generation-review-task");
  expect(context).toMatchObject({page_id:"image-generation",selections:{run:{id:"report-job"},candidate:{id:"report-job:0"}}});
  expect(JSON.stringify(context)).not.toContain("SECRET");
  expect(JSON.stringify(context)).not.toContain("fixture.png");
});
