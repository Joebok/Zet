import {mountCandidateBoard, confirmCandidateDeletion} from "./candidate_board_component.js?v=20261112-queued-cancel";

(() => {
  const $ = (id) => document.getElementById(`character-container-${id}`);
  const pipelineLabels = {
    "body-reference": "Body Reference",
    "head-image-edit": "Head Image Edit", "character-assembly": "Character Assembly",
    "costume-dressing": "Costume Dressing",
  };
  const state = {pipeline: "", costume: "", view: "", detail: null, phaseSourceFile: null,
    timer: null, active: false, pollInFlight: false, request: 0, sourceRequest: 0, templateProposal: null, dressingDrafts: {},
    mutation: false, scope: null, controller: null, templateTimer: null,
    phaseChange: false, sourceScopeKey: "", aspectRatio: "2:3"};
  let sharedBoard = null;
  const sharedBoardHost = $("shared-board");
  const sharedDialogHost = $("dialog-host");

  const activeCandidateStates = new Set(["SUBMITTING", "QUEUED", "RUNNING", "DISPATCHING"]);
  const escape = (value) => String(value ?? "").replace(/[&<>"']/g,
    (char) => ({"&":"&amp;", "<":"&lt;", ">":"&gt;", '"':"&quot;", "'":"&#39;"}[char]));

  function query() {
    const params = new URLSearchParams(state.scope || {});
    if (state.pipeline === "costume-dressing" && state.costume) params.set("costume", state.costume);
    return params;
  }

  async function request(path, options = {}) {
    const signal = state.controller.signal;
    const response = await fetch(path, {headers: {"Content-Type": "application/json"}, ...options, signal});
    const data = await response.json().catch(() => ({}));
    signal.throwIfAborted();
    if (!response.ok) throw new Error(data.detail || `Request failed (${response.status}).`);
    return data;
  }

  function api(suffix = "") {
    return `/api/character-containers/${encodeURIComponent(state.pipeline)}${suffix}?${query()}`;
  }

  function apiAt(pipeline, phase) {
    const params = query();
    params.set("phase", phase);
    params.delete("costume");
    return `/api/character-containers/${encodeURIComponent(pipeline)}?${params}`;
  }

  function savedDressingSettings() {
    return state.detail?.sources?.dressing_settings?.[state.view] || {mode: "doll-dressing-ref", costume_reference_view: "FRONT"};
  }

  function show(message, error = false) {
    $("status").textContent = message;
    $("status").classList.toggle("error", error);
  }

  function stopPolling() {
    clearInterval(state.timer);
    state.timer = null;
  }

  function pageVisible() {
    return document.visibilityState === "visible" &&
      document.querySelector("#character-asset-container-page").classList.contains("active");
  }

  function activeOnScreen() { return state.active && pageVisible(); }

  function startPolling() {
    stopPolling();
    if (!pageVisible()) return;
    if (state.active && state.view && (state.detail?.boards?.[state.view]?.luna_review?.status === "RUNNING" ||
      state.detail?.boards?.[state.view]?.slots.some((id) => id &&
      activeCandidateStates.has(state.detail.boards[state.view].candidates[id]?.status)))) {
      state.timer = setInterval(() => { if (activeOnScreen()) void pollProgress(); }, 1500);
    }
  }

  async function loadDetail() {
    const sequence = ++state.request;
    const data = await request(api() + (state.view ? '&prompt_view=' + encodeURIComponent(state.view) : ''));
    if (sequence !== state.request || data.revision < (state.detail?.revision ?? -1)) return;
    state.detail = data;
    state.aspectRatio = data.render_settings?.aspect_ratio || (isHead() ? "1:1" : "2:3");
    if (state.view && !data.boards[state.view]) state.view = data.scope.views[0];
    render();
    if (!state.view && isHead()) void loadPhaseSourceCandidates();
  }

  async function pollProgress() {
    if (!activeOnScreen() || !state.view || !state.detail || state.pollInFlight || state.mutation || !state.timer) return;
    const url = api(`/views/${encodeURIComponent(state.view)}/progress`);
    const sequence = state.request;
    const signal = state.controller.signal;
    state.pollInFlight = true;
    try {
      const progress = await request(url);
      if (!pageVisible() || state.mutation || sequence !== state.request ||
          url !== api(`/views/${encodeURIComponent(state.view)}/progress`) ||
          progress.container_id !== state.detail?.container_id || progress.revision < state.detail.revision) return;
      const board = state.detail.boards[state.view];
      const previousReview = board.luna_review || {};
      const review = progress.luna_review || {};
      const reviewChanged = previousReview.status !== review.status ||
        previousReview.active_id !== review.active_id || previousReview.recorded_at !== review.recorded_at;
      if (reviewChanged) {
        board.luna_review = review;
        renderBoard();
      }
      if (!progress.active.length) {
        if (review.status !== "RUNNING") {
          stopPolling();
          await loadDetail();
        }
        return;
      }
      if (reviewChanged && review.status !== "RUNNING") {
        await loadDetail();
        return;
      }
      if (progress.slots.length !== board.slots.filter(Boolean).length ||
          progress.slots.some((slot) => board.slots[slot.slot - 1] !== slot.candidate_id)) {
        await loadDetail();
        return;
      }
      let changed = board.selected_id !== progress.selected_id;
      board.selected_id = progress.selected_id;
      state.detail.revision = progress.revision;
      for (const slot of progress.slots) {
        const candidate = board.candidates[slot.candidate_id];
        if (candidate.status === slot.status && !!candidate.image_path === slot.image &&
            (candidate.error || "") === slot.error && !!candidate.locked === slot.locked) continue;
        Object.assign(candidate, {status: slot.status, error: slot.error, locked: slot.locked, image_path: slot.image ? "available" : ""});
        changed = true;
      }
      if (changed) {
        renderBoard();
      }
    } catch (error) {
      if (sequence === state.request && pageVisible()) show(error.message, true);
    } finally {
      if (!signal.aborted) state.pollInFlight = false;
    }
  }

  function imageUrl(candidateId) {
    return comparisonImageUrl(state.view, candidateId);
  }

  function comparisonImageUrl(view, candidateId) {
    const quality = state.detail?.boards[view]?.candidates[candidateId]?.render_mode || "draft";
    return api(`/views/${encodeURIComponent(view)}/candidates/${encodeURIComponent(candidateId)}/image`) + `&quality=${encodeURIComponent(quality)}`;
  }

  function route(view = state.view) {
    const params = query();
    params.set("page", "character-asset-container");
    params.set("pipeline", state.pipeline);
    if (view) params.set("view", view);
    return `/?${params}`;
  }

  function syncRoute() {
    if (new URLSearchParams(location.search).get("page") === "character-asset-container") {
      history.replaceState({}, "", route());
    }
  }

  function navigate(view) {
    history.pushState({}, "", route(view));
    return activate(state.pipeline, {view, costume: state.costume, scope: state.scope, guidance: $("template-guidance").value});
  }

  function isHead() { return state.pipeline === "head-image-edit"; }

  function render() {
    const {scope, boards} = state.detail;
    $("title").textContent = `${pipelineLabels[state.pipeline]} · ${scope.character} · ${scope.phase}`;
    $("context").textContent = scope.costume || "";
    $("view-wrap").hidden = !state.view;
    const viewSelect = $("view");
    if (state.view && !viewSelect.options.length) {
      viewSelect.replaceChildren(...scope.views.map(view => new Option(view.replaceAll("_", " "), view)));
    }
    viewSelect.value = state.view;
    $("workspace").hidden = !state.view;
    $("prompt-preview-button").hidden = !state.view;
    $("prompt-preview-button").disabled = false;
    $("costume-wrap").hidden = state.pipeline !== "costume-dressing" || Boolean(state.view);
    $("outputs").hidden = Boolean(state.view);
    $("refresh").hidden = false;
    $("back").href = route("");
    renderAuthoring();
    if (state.view) renderBoard();
    else {
      $("outputs").innerHTML = scope.views.map(view => {
        const board = boards[view];
        const candidate = board.candidates[board.selected_id];
        const label = view.replaceAll("_", " ");
        const href = escape(route(view));
        const image = candidate?.image_path
          ? `<a href="${href}" data-container-view="${view}"><img loading="lazy" src="${escape(comparisonImageUrl(view, board.selected_id))}" alt="${escape(label)}"></a>`
          : '<div class="placeholder">No selected image</div>';
        return `<article class="narrative-slot character-container-output"><h3>${escape(label)}</h3>${image}
          ${candidate?.image_path ? `<p><span class="narrative-render-mode-pill ${candidate.render_mode === "final" ? "final" : "draft"}">${candidate.render_mode === "final" ? "Final" : "Draft"}</span> · ${candidate.locked ? "Locked" : "Selected"}</p>` : ""}
          <a href="${href}" data-container-view="${view}" class="image-card-text-control">Open ${escape(label)} Candidate Board</a></article>`;
      }).join("");
    }
    startPolling();
  }

  function renderBoard() {
    const board = state.detail.boards[state.view];

    const dressing = state.pipeline === "costume-dressing";
    $("dressing-settings").hidden = true;
    if (dressing && state.view !== "FRONT") {
      const saved = state.detail.sources?.dressing_settings?.[state.view];
      const defaults = {mode: "doll-dressing-ref", costume_reference_view: "FRONT"};
      const effective = saved || defaults;
      const draft = state.dressingDrafts[state.view] || effective;
      const mode = $("dressing-mode"), reference = $("dressing-reference");
      mode.value = draft.mode;
      reference.replaceChildren(new Option("Choose a different view", ""), ...state.detail.scope.views.filter(view => view !== state.view).map(view => {
        const item = state.detail.boards[view].candidates[state.detail.boards[view].selected_id];
        return new Option(`${view.replaceAll("_", " ")} · ${item?.image_path ? "selected" : "image not selected"}`, view);
      }));
      reference.value = draft.costume_reference_view || defaults.costume_reference_view;
      reference.disabled = mode.value === "doll-dressing-no-ref";
      $("save-dressing-settings").disabled = false;
      $("dressing-status").textContent = state.dressingDrafts[state.view]
        ? "Unsaved changes. Preview and Generate use saved settings."
        : saved ? `Saved mode: ${saved.mode}.` : "Default mode: Doll-dressing (w/ Ref), using FRONT. Save settings to keep this choice.";
    }
    const model = characterBoardModel(board);
    if (!sharedBoard) sharedBoard = mountCandidateBoard({boardHost:sharedBoardHost,dialogHost:sharedDialogHost},model,{
      onEdit:({field,value})=>{
        if(field==="aspect_ratio")state.aspectRatio=value;
        if(field==="reference_view")$("source-view").value=value;
        if(field==="costume_mode") { $("dressing-mode").value=value; state.dressingDrafts[state.view]={mode:value,costume_reference_view:$("dressing-reference").value}; }
        if(field==="costume_reference_view") { $("dressing-reference").value=value; state.dressingDrafts[state.view]={mode:$("dressing-mode").value,costume_reference_view:value}; }
      },
      onAction:characterBoardAction,
    });
    else sharedBoard.update(model);
  }

  const costumeModeLabels = {
    'doll-dressing-ref': 'Doll-dressing (w/ Ref)',
    'doll-dressing-no-ref': 'Doll-dressing (no Ref)',
    rotate: 'Rotate',
  };
  const readableToken = token => String(token || '').toLowerCase().replaceAll('3_4', '3/4')
    .replace(/[_-]/g, ' ').replace(/\b[a-z]/g, letter => letter.toUpperCase());

  function savedRenderSettings(view, request, inputs) {
    const saved = request.provenance || {};
    const pipeline = saved.pipeline || state.pipeline;
    const head = pipeline === 'head-image-edit';
    const dressing = pipeline === 'costume-dressing';
    const costume = saved.costume_settings || {};
    const costumeReference = inputs.find(input => ['batch_view_reference', 'costume_rotation_source', 'front_costume'].includes(input.role));
    const viewReference = inputs.find(input => ['body_reference_front_anchor', 'head_image_source'].includes(input.role));
    const rows = [['Aspect ratio', request.settings?.aspect_ratio]];
    if (dressing) {
      rows.push(['Costume Mode', costumeModeLabels[costume.mode] || readableToken(costume.mode)]);
      if (costumeReference) rows.push(['Costume Reference View', readableToken(costumeReference.view || costumeReference.source_view || costume.costume_reference_view)]);
    } else if (viewReference) {
      rows.push(['Reference view', readableToken(viewReference.view || viewReference.source_view)]);
    }
    if (head && view === 'FRONT' && typeof saved.apply_phase_change === 'boolean') {
      rows.push(['Apply phase change', saved.apply_phase_change ? 'Yes' : 'No']);
    }
    if (pipeline === 'character-assembly') rows.push(['Assembly Style Mode', readableToken(saved.assembly_style_mode)]);
    return rows.filter(([, value]) => value).map(([label, value]) => ({label, value}));
  }

  function candidateEvidence(view,id,item) {
    const request = item.render_request || {};
    const bindings = request.inputs || [];
    const inputs=bindings.map((input,index)=>({
      marker: bindings.length > 1 ? `<image${index + 1}>` : '',
      label: [input.role === 'batch_view_reference' ? 'Reference view' : input.label || readableToken(input.role) || `Reference ${index + 1}`,
        readableToken(input.view || input.source_view), readableToken(input.render_mode)].filter(Boolean).join(' · '),
      // Use a new URL for browsers that cached the old download response.
      url:`${api(`/views/${encodeURIComponent(view)}/candidates/${encodeURIComponent(id)}/inputs/${index+1}`)}&delivery=inline`,
    }));
    return {id,quality:item.render_mode,status:item.status,image:item.image_path?{url:comparisonImageUrl(view,id),label:`${view} slot ${item.slot}`,version:item.image_path}:null,
      thumbnail:item.image_path?{url:comparisonImageUrl(view,id),label:`${view} slot ${item.slot}`,version:item.image_path}:null,
      earlierPrompt:item.earlier_prompt,elapsedSeconds:item.render_duration_seconds,locked:Boolean(item.locked),prompt:item.prompt,
      negativePrompt:request.negative_prompt,inputs,renderSettings:savedRenderSettings(view,request,bindings),
      error:item.error,notices:item.source_change_fyi?["Saved source differs from current source."]:[],reviewable:true};
  }

  function characterBoardModel(board) {
    const dressing = state.pipeline === "costume-dressing";
    const slots=board.slots.map((id,index)=>{
      if(!id)return {key:String(index+1)};
      const item=board.candidates[id];
      const actions=[];
      const active=activeCandidateStates.has(item.status), selected=board.selected_id===id;
      const held=Object.values(board.candidates).some(other=>other!==item&&other.locked) ? "Unlock the current image first." : "";
      const add=(key,disabledReason="")=>actions.push({key,disabledReason});
      if(item.status==="PREPARED")actions.push({key:"submit",label:"Generate"});
      if(item.status==="FAILED")add("retry");
      const waiting=active ? "Wait for the render to finish." : "";
      const ready=waiting || (!item.image_path ? "Wait for a completed image." : "");
      if(!item.locked) add(selected?"unselect":"select",selected?(waiting||held):(ready||held));
      add(item.locked?"unlock":"lock",ready || held);
      add("clear",waiting || (item.locked ? "Unlock this image before clearing its slot." : ""));
      if(item.status==="COMPLETE"&&item.image_path)actions.push({key:"template-improve",label:"Improve template from this image",placement:["review"]});
      return {key:String(index+1),candidate:candidateEvidence(state.view,id,item),actions,renderActive:active,
        cancelAttempt:item.status === "QUEUED" && item.ask_id ? item.attempt_id : null};
    });
    const order=state.view==="FRONT"?["FRONT_LEFT_3_4","FRONT_RIGHT_3_4","LEFT_PROFILE","RIGHT_PROFILE"]:["FRONT"];
    const comparisons=Object.entries(state.detail.boards).filter(([view])=>view!==state.view).map(([view,other])=>{
      const id=other.selected_id,item=id&&other.candidates[id];if(!item?.image_path)return null;
      return {key:`${view}:${id}`,label:`${view.replaceAll("_"," ")} · Slot ${item.slot} · ${item.render_mode} · Selected`,role:"Selected view",image:{url:comparisonImageUrl(view,id),label:`${view} slot ${item.slot}`,version:item.image_path}};
    }).filter(Boolean).sort((a,b)=>(order.includes(a.key.split(":")[0])?order.indexOf(a.key.split(":")[0]):order.length)-(order.includes(b.key.split(":")[0])?order.indexOf(b.key.split(":")[0]):order.length));
    const luna=board.luna_review||{};
    const fields=[{key:"aspect_ratio",label:"Aspect ratio",type:"text",value:state.aspectRatio}];
    const renderBlock = phaseChangeBlock();
    const actions=[{key:"luna-review",label:"Luna Review",group:"luna",placement:["controls"]},
      {key:"stage-image-generation",label:"Stage in Image Generator",placement:["settings"],disabledReason:renderBlock}];
    if(["body-reference","head-image-edit"].includes(state.pipeline)&&state.view!=="FRONT") {
      const views=state.detail.scope.views.filter(view=>view!==state.view);
      fields.push({key:"reference_view",label:"Reference view",type:"select",value:$("source-view").value,options:views.map(view=>({value:view,label:view.replaceAll("_"," ")}))});
      actions.push({key:"save-view-source",label:"Save view recipe",group:"render",placement:["settings"]});
    }
    if(state.pipeline==="costume-dressing"&&state.view!=="FRONT") {
      const saved=state.detail.sources?.dressing_settings?.[state.view]||{mode:"doll-dressing-ref",costume_reference_view:"FRONT"};
      const draft=state.dressingDrafts[state.view]||saved;
      fields.push({key:"costume_mode",label:"Costume mode",type:"select",value:draft.mode,options:Object.entries(costumeModeLabels).map(([value,label])=>({value,label}))});
      fields.push({key:"costume_reference_view",label:"Costume reference view",type:"select",value:draft.costume_reference_view||"FRONT",options:state.detail.scope.views.filter(view=>view!==state.view).map(view=>({value:view,label:view.replaceAll("_"," ")}))});
      actions.push({key:"save-dressing-settings",label:"Save costume settings",group:"render",placement:["settings"]});
    }
    return {scope:{key:`${state.detail.container_id}:${state.view}`,title:pipelineLabels[state.pipeline],view:state.view},revision:state.detail.revision,slots,selectedId:board.selected_id,
      lunaReview:{status:luna.status,criteria:luna.prompt,error:luna.error,entries:Object.fromEntries((luna.entries||[]).map((entry,index)=>[entry.candidate_id,{rank:index+1,assessment:entry.review}]))},
      renderControls:{fields,fieldsLayout:dressing&&state.view!=="FRONT"?"inline":undefined,
        readiness:{draft:renderBlock,final:renderBlock},promptStatus:"",renderStatus:""},actions,comparisons,comparisonDefaults:comparisons[0]?[comparisons[0].key]:[]};
  }

  async function characterBoardAction(intent) {
    if (state.mutation) return {status:"cancelled"};
    if (["render-1","render-4","render-final-1","render-final-4","stage-image-generation"].includes(intent.key)) {
      const saved = state.detail.render_settings?.aspect_ratio || (isHead() ? "1:1" : "2:3");
      if (state.aspectRatio !== saved) {
        try {
          state.detail = await request(api("/render-settings"), {method:"PUT",
            body:JSON.stringify({aspect_ratio:state.aspectRatio,expected_revision:state.detail.revision})});
        } catch (error) {
          await loadDetail().catch(() => {});
          return {status:"error",message:error.message};
        }
      }
    }
    if (intent.key === "stage-image-generation") {
      const view = state.view, scope = api(), signal = state.controller.signal;
      const renderMode = state.detail.boards[view].candidates[state.detail.boards[view].selected_id]?.render_mode || "draft";
      await window.zetStageCharacterViewInImageGenerator(api(`/views/${encodeURIComponent(view)}/image-generation-stage`),
        false, () => !signal.aborted && scope === api() && view === state.view, false, false, renderMode, {
          aspect_ratio:state.aspectRatio, expected_revision:intent.revision,
          apply_phase_change:isHead() && view === "FRONT" && $("apply-phase-change").checked,
          costume_settings:savedDressingSettings(),
        });
      return {status:"success"};
    }
    if(intent.key==="save-view-source") {
      const views={...(state.detail.sources?.views||{}),[state.view]:$("source-view").value};
      await saveSource("views",views);return {status:"success",message:"View recipe saved."};
    }
    if(intent.key==="save-dressing-settings") {
      const source={view:state.view,mode:$("dressing-mode").value,costume_reference_view:$("dressing-reference").value};
      state.detail=await request(api("/sources/dressing_settings"),{method:"PUT",body:JSON.stringify({source,expected_revision:state.detail.revision})});
      delete state.dressingDrafts[state.view];await loadDetail();return {status:"success",message:"Costume settings saved."};
    }
    if(intent.key.startsWith("render-")) {
      return generate(intent.count,intent.mode,intent.revision);
    }
    if(intent.key==="preview-prompt") { await previewPrompt();return {status:"success",message:"Prompt preview updated."}; }
    if(intent.key==="luna-review") {
      state.mutation=true;
      try {
        const review=await request(api(`/views/${encodeURIComponent(state.view)}/luna-review`),{method:"POST",body:JSON.stringify({
          apply_phase_change:isHead() && state.view === "FRONT" && $("apply-phase-change").checked,
          assembly_style_mode:state.detail.sources?.assembly_style_mode || "",
          costume_settings:savedDressingSettings(),
        })});
        const board = state.detail.boards[state.view];
        board.luna_review = {...board.luna_review, ...review};
        renderBoard();
        startPolling();
        return {status:"success"};
      } finally { state.mutation=false; }
    }
    if(intent.key.startsWith("delete-")) {
      return bulkBoardAction(intent.key,intent.revision);
    }
    const view=state.view,board=state.detail?.boards?.[view],candidate=board?.candidates?.[intent.candidateId];
    if(intent.key.startsWith("regen-")) {
      const slot = Number(intent.slotKey);
      if (intent.revision !== state.detail.revision || board.slots[slot - 1] !== intent.expectedOccupant) {
        return {status:"error",message:"This slot changed. Refresh the board."};
      }
      return generate(1,intent.mode,intent.revision,{slot,expected_candidate_id:intent.expectedOccupant});
    }
    if(!candidate||String(candidate.slot)!==String(intent.slotKey)||intent.expectedOccupant!==intent.candidateId)return {status:"error",message:"This slot changed. Refresh the board."};
    if(intent.key==="template-improve") {
      history.pushState({},"",route(""));await activate(state.pipeline,{view:"",costume:state.costume,templateCandidate:`${view}:${candidate.candidate_id}`});return {status:"success",message:"Template Improvement opened."};
    }
    const payload={expected_revision:intent.revision,expected_candidate_id:intent.expectedOccupant,expected_attempt_id:intent.expectedAttempt};
    if(intent.key==="clear") {
      payload.confirm_selected=board.selected_id===candidate.candidate_id&&confirm("Clear the selected candidate from this board?");
      if(board.selected_id===candidate.candidate_id&&!payload.confirm_selected)return {status:"cancelled"};
      if(candidate.locked)return {status:"error",message:"Unlock the candidate before clearing its slot."};
    }
    const endpoint=intent.key==="submit"?`/views/${encodeURIComponent(view)}/candidates/${encodeURIComponent(candidate.candidate_id)}/submit`:`/views/${encodeURIComponent(view)}/candidates/${encodeURIComponent(candidate.candidate_id)}/${encodeURIComponent(intent.key)}`;
    state.mutation=true;
    try {
      const result=await request(api(endpoint),{method:"POST",body:JSON.stringify(payload)});
      if(result.revision<state.detail.revision)return {status:"cancelled"};
      state.detail=result;render();return {status:"success",message:intent.key==="lock"?"Locked and published.":intent.key==="cancel"?"Render cancelled.":"Candidate updated."};
    } catch (error) {
      if (intent.key === "cancel") {
        await request(api(`/views/${encodeURIComponent(view)}/progress`)).catch(() => {});
        await loadDetail().catch(() => {});
      }
      throw error;
    } finally { state.mutation=false; }
  }

  function renderAuthoring() {
    const detail = state.detail;
    if (!detail) return;
    const sources = detail.sources || {};
    const byMode = sources.phase_change_by_mode || {};
    const phaseSource = sources.phase_change ?? byMode.final ?? byMode.draft ?? {};
    const authoring = $("authoring");
    authoring.hidden = false;
    $("template-improvement").hidden = Boolean(state.view);
    $("edit-costume-template").hidden = state.pipeline !== "costume-dressing";
    renderTemplateChoices();
    $("phase-source").hidden = state.pipeline !== "head-image-edit";
    $("view-source").hidden = true;
    const phaseSelect = $("source-phase");
    const phases = Array.from(document.querySelector("#phase-select").options)
      .filter((option) => option.value && option.value !== detail.scope.phase);
    phaseSelect.replaceChildren(...phases.map((phase) => new Option(phase.textContent, phase.value)));
    phaseSelect.value = phases.some((phase) => phase.value === phaseSource.phase)
      ? phaseSource.phase : (phases[0]?.value || "");
    $("source-lock").hidden = !$("apply-phase-change").checked;
    $("source-phase").disabled = !$("apply-phase-change").checked;
    $("save-phase-source").disabled = !$("apply-phase-change").checked;

    const recipe = {...(sources.views || {})};
    const sourceView = $("source-view");
    const choices = detail.scope.views.filter((view) => view !== state.view);
    const options = choices.map((view) => new Option(view.replaceAll("_", " "), view));
    sourceView.replaceChildren(...options);
    sourceView.value = recipe[state.view] || "FRONT";
  }

  async function loadPhaseSourceCandidates() {
    const sequence = ++state.sourceRequest;
    const phase = $("source-phase").value;
    const pipeline = "head-image-edit";
    if (!phase) {
      $("phase-source-status").textContent = "Choose a source phase.";
      return;
    }
    $("phase-source-status").textContent = "Checking the current locked FRONT…";
    try {
      const data = await request(apiAt(pipeline, phase));
      if (sequence !== state.sourceRequest) return;
      const board = data.boards.FRONT;
      const candidate = board.slots.map((id) => id && board.candidates[id])
        .find((item) => item?.locked && item.inventory_asset_id);
      $("phase-source-status").textContent = candidate
        ? `Current source: locked FRONT · ${candidate.render_mode} · slot ${candidate.slot}`
        : "No locked, published FRONT yet. Save this phase and pipeline; new FRONT requests will wait until one is locked.";
    } catch (error) {
      if (sequence === state.sourceRequest) $("phase-source-status").textContent = error.message;
    }
  }

  async function saveSource(name, source, renderMode = "") {
    const status = $(name === "views" ? "view-source-status" : name === "phase_change" ? "phase-source-status" : "source-status");
    try {
      state.detail = await request(api(`/sources/${encodeURIComponent(name)}`), {
        method: "PUT", body: JSON.stringify({source, render_mode: renderMode,
          expected_revision: state.detail.revision}),
      });
      if (state.view) await loadDetail();
      else render();
      if (!state.view && isHead()) void loadPhaseSourceCandidates();
      status.textContent = "Reference choice saved for new requests.";
    } catch (error) { if (error.name !== "AbortError") status.textContent = error.message; }
  }

  function renderTemplateChoices() {
    if (!state.detail) return;
    const picker = $("template-candidate");
    const chosen = picker.value;
    const options = [new Option("Choose a finished candidate", "")];
    for (const [view, board] of Object.entries(state.detail.boards)) {
      for (const candidate of Object.values(board.candidates)) {
        if (candidate.status === "COMPLETE" && candidate.image_path && board.slots.includes(candidate.candidate_id)) {
          options.push(new Option(`${view.replaceAll("_", " ")} · slot ${candidate.slot} · ${candidate.render_mode}`,
            `${view}:${candidate.candidate_id}`));
        }
      }
    }
    picker.replaceChildren(...options); picker.value = chosen;
  }

  function updateTemplateMode() {
    $("template-candidate-wrap").hidden = $("template-mode").value !== "candidate";
  }

  function watchTemplateReview() {
    clearInterval(state.templateTimer); state.templateTimer = null;
    if (!state.active || state.view || !$("template-improvement").open ||
        state.templateProposal?.schema_version !== 2 || state.templateProposal.status !== "PROPOSING") return;
    state.templateTimer = setInterval(async () => {
      if (!state.active || state.view || !$("template-improvement").open) { clearInterval(state.templateTimer); state.templateTimer = null; return; }
      try {
        state.templateProposal = await request(api(`/template-proposals/${state.templateProposal.proposal_id}`));
        renderTemplateProposal();
        if (state.templateProposal.status !== "PROPOSING") { clearInterval(state.templateTimer); state.templateTimer = null; }
      } catch (error) { reportError(error); clearInterval(state.templateTimer); state.templateTimer = null; }
    }, 3000);
  }

  function renderTemplateProposal() {
    const host = $("template-proposal");
    const proposal = state.templateProposal;
    host.replaceChildren();
    host.hidden = !proposal;
    if (!proposal) return;
    if (proposal.schema_version === 2) {
      const heading = document.createElement("h3");
      heading.textContent = `Template review · ${proposal.status}`;
      host.append(heading);
      if (proposal.error) { const error = document.createElement("p");
        error.textContent = `${proposal.failure_stage ? `${proposal.failure_stage}: ` : ""}${proposal.error}`; host.append(error); }
      if (proposal.summary) { const summary = document.createElement("p"); summary.textContent = proposal.summary; host.append(summary); }
      if (proposal.rejected_findings?.length) {
        const details = document.createElement("details"); details.open = proposal.status === "FAILED";
        const title = document.createElement("summary");
        title.textContent = `${proposal.rejected_findings.length} rejected correction${proposal.rejected_findings.length === 1 ? "" : "s"}`;
        details.append(title);
        const list = document.createElement("ul");
        for (const rejected of proposal.rejected_findings) {
          const item = document.createElement("li");
          item.textContent = `Finding ${rejected.number} · ${rejected.source_id || "unknown source"}`
            + `${rejected.reported_views?.length ? ` · reported views: ${rejected.reported_views.join(", ")}` : ""}`
            + ` · ${(rejected.reasons || []).join(" ")}`;
          list.append(item);
        }
        details.append(list); host.append(details);
      }
      if (proposal.status === "REVIEW_READY" || proposal.status === "ACCEPTED") {
        const list = document.createElement("div");
        for (const finding of proposal.findings || []) {
          const label = document.createElement("label");
          const check = document.createElement("input"); check.type = "checkbox"; check.value = finding.id;
          check.checked = (proposal.selected_ids || []).includes(finding.id);
          check.disabled = proposal.status === "ACCEPTED";
          label.append(check, document.createTextNode(`${finding.source_id}${finding.section ? ` · ${finding.section}` : ""} · ${finding.views.join(", ")} · ${finding.rationale}`));
          const before = document.createElement("pre"); before.textContent = `Before\n${finding.before}`;
          const after = document.createElement("pre"); after.textContent = `After\n${finding.after}`;
          list.append(label, before, after);
        }
        if (!(proposal.findings || []).length) { const none = document.createElement("p"); none.textContent = "No changes suggested."; list.append(none); }
        host.append(list);
        if (proposal.status === "REVIEW_READY") {
          const review = document.createElement("button"); review.type = "button"; review.textContent = "Preview selected corrections";
          review.addEventListener("click", async () => {
            review.disabled = true;
            try {
              const ids = [...list.querySelectorAll("input:checked")].map(input => input.value);
              state.templateProposal = await request(api(`/template-proposals/${proposal.proposal_id}/decisions`),
                {method: "PUT", body: JSON.stringify({selected_ids: ids})});
              renderTemplateProposal();
            } catch (error) { reportError(error); review.disabled = false; }
          });
          host.append(review);
        }
        for (const diff of proposal.diffs || []) {
          const details = document.createElement("details");
          const summary = document.createElement("summary"); summary.textContent = `${diff.source_id} master → proposed`;
          const pre = document.createElement("pre"); pre.textContent = (diff.rows || []).map(row =>
            row.kind === "gap" ? "…" : `${row.master_line == null ? "" : `− ${row.master_text || ""}`}\n${row.proposed_line == null ? "" : `+ ${row.proposed_text || ""}`}`).join("\n");
          details.append(summary, pre); host.append(details);
        }
        if (proposal.previews) {
          const previews = document.createElement("details");
          const summary = document.createElement("summary"); summary.textContent = "Compiled prompt previews"; previews.append(summary);
          for (const item of proposal.previews) { const detail = document.createElement("details");
            const title = document.createElement("summary"); title.textContent = item.view;
            const pre = document.createElement("pre"); pre.textContent = item.prompt; detail.append(title, pre); previews.append(detail); }
          host.append(previews);
          if (proposal.status === "REVIEW_READY") {
            const accept = document.createElement("button"); accept.type = "button"; accept.textContent = "Accept selected corrections and save masters";
            list.addEventListener("change", () => { accept.disabled = true;
              accept.title = "Preview the changed selection before accepting."; });
            accept.addEventListener("click", async () => {
              if (!confirm("Save the selected corrections to the governing master templates?")) return;
              accept.disabled = true;
              try { state.templateProposal = await request(api(`/template-proposals/${proposal.proposal_id}/accept`),
                {method: "POST", body: JSON.stringify({confirm: true})}); renderTemplateProposal();
                show("Governing templates updated for future prompts."); }
              catch (error) { reportError(error); accept.disabled = false; }
            }); host.append(accept);
          }
        }
      }
      return;
    }
    const heading = document.createElement("h3");
    heading.textContent = `${proposal.status === "ACCEPTED" ? "Accepted template proposal" : "Template proposal"} · ${proposal.view} · ${proposal.render_mode}`;
    const summary = document.createElement("p"); summary.textContent = proposal.summary || "";
    const rationale = document.createElement("p"); rationale.textContent = proposal.rationale || "";
    const diff = document.createElement("pre"); diff.textContent = proposal.diff || "No changes proposed.";
    const compiled = document.createElement("details");
    const detailsSummary = document.createElement("summary"); detailsSummary.textContent = "Prompt preview with the proposed master";
    const prompt = document.createElement("pre"); prompt.textContent = proposal.compiled_prompt || "";
    compiled.append(detailsSummary, prompt);
    host.append(heading, summary, rationale, diff, compiled);
    if (proposal.status === "PROPOSED" && proposal.diff) {
      const accept = document.createElement("button");
      accept.type = "button"; accept.textContent = "Accept proposal and update Character.md";
      accept.addEventListener("click", async () => {
        if (!window.confirm("Save this reviewed proposal to the governing Character.md? It will affect new prompts only.")) return;
        accept.disabled = true;
        try {
          state.templateProposal = await request(api(`/template-proposals/${encodeURIComponent(proposal.proposal_id)}/accept`), {
            method: "POST", body: JSON.stringify({confirm: true}),
          });
          renderTemplateProposal();
          show("Character.md updated. Existing candidates keep their captured prompts and inputs.");
        } catch (error) { reportError(error); accept.disabled = false; }
      });
      host.append(accept);
    }
  }

  async function costumeOptions() {
    const data = await request(`/api/costumes?${query()}`);
    const select = $("costume");
    select.replaceChildren(new Option("Choose a costume", ""),
      ...data.costumes.map(costume => new Option(costume.name, costume.slug)));
    state.costume = data.costumes.find(costume =>
      costume.slug === state.costume || costume.name === state.costume)?.slug || "";
    select.value = state.costume;
  }

  function deactivate() {
    clearInterval(state.templateTimer); state.templateTimer = null;
    state.controller?.abort();
    state.request += 1;
    state.sourceRequest += 1;
    state.active = false;
    stopPolling();
    if (sharedBoard) { sharedBoard.dispose(); sharedBoard = null; }

  }

  async function activate(pipeline, options = {}) {
    const params = new URLSearchParams(location.search);
    const authoringWasOpen = $("authoring").open;
    deactivate();
    const controller = new AbortController();
    state.controller = controller;
    state.scope = options.scope || {
      character: document.querySelector("#character-select").value,
      phase: document.querySelector("#phase-select").value,
      universe_id: document.querySelector("#universe-select").value,
    };
    state.pipeline = pipeline || params.get("pipeline") || "body-reference";

    state.view = options.view ?? params.get("view") ?? "";
    state.dressingDrafts = {};
    state.costume = state.pipeline === "costume-dressing"
      ? options.costume ?? params.get("costume") ?? "" : "";
    const sourceScopeKey = JSON.stringify([state.scope.universe_id, state.scope.character,
      state.scope.phase, state.pipeline]);
    const sameSourceScope = state.sourceScopeKey === sourceScopeKey;
    if (!sameSourceScope) state.phaseChange = false;
    state.sourceScopeKey = sourceScopeKey;
    state.active = true;
    state.pollInFlight = false;
    state.mutation = false;
    state.detail = null;
    state.templateProposal = options.proposal || null;
    for (const id of ["outputs", "source-status", "phase-source-status", "prompt-text"]) $(id).replaceChildren();
    for (const id of ["workspace", "outputs", "authoring", "template-improvement", "prompt-preview", "refresh", "costume-wrap"]) $(id).hidden = true;
    $("authoring").open = sameSourceScope && authoringWasOpen;
    $("template-improvement").open = Boolean(options.proposal || options.templateCandidate);
    $("apply-phase-change").checked = state.phaseChange;
    $("phase-source-file").value = "";
    state.phaseSourceFile = null;
    $("template-guidance").value = options.guidance ?? "";
    $("prompt-preview-button").disabled = false;

    $("title").textContent = pipelineLabels[state.pipeline] || "Character Asset Container";
    $("context").textContent = "";
    $("view-wrap").hidden = true;
    $("view").replaceChildren();
    $("view-source-status").textContent = "";
    renderTemplateProposal();
    show("Loading Asset Container…");
    if (options.sync !== false) syncRoute();
    if (!state.scope.character || !state.scope.phase) {
      show("Choose a character and phase to open its Asset Container.");
      return;
    }
    try {
      if (state.pipeline === "costume-dressing") {
        $("costume").disabled = true;
        await costumeOptions();
        $("costume").disabled = false;
        if (!state.costume) {
          $("costume-wrap").hidden = false;
          syncRoute();
          show("Choose a costume to open its Asset Container.");
          return;
        }
      }
      await loadDetail();
      controller.signal.throwIfAborted();
      syncRoute();
      if (!state.view) {
        const sources = await request(api("/template-sources"));
        $("template-sources").replaceChildren(...sources.sources.map(source => {
          const label = document.createElement("label"); const input = document.createElement("input");
          input.type = "checkbox"; input.value = source.source_id; input.checked = true;
          label.append(input, document.createTextNode(` Improve ${source.source_id}`)); return label;
        }));
        const savedProposal = await request(api("/template-proposals"));
        if (!options.proposal) state.templateProposal = savedProposal.proposal;
        renderTemplateProposal();
        renderTemplateChoices();
        if (options.templateCandidate) { $("template-mode").value = "candidate";
          $("template-candidate").value = options.templateCandidate; updateTemplateMode(); }
        watchTemplateReview();
      }
      show("Container ready.");
    } catch (error) {
      if (!controller.signal.aborted) {
        $("costume").disabled = false;
        $("costume-wrap").hidden = state.pipeline !== "costume-dressing";
        show(error.message, true);
      }
    }
  }

  function phaseChangeBlock() {
    const frontSource = state.detail.sources?.phase_change ?? state.detail.sources?.phase_change_by_mode?.final ?? state.detail.sources?.phase_change_by_mode?.draft ?? {};
    if (isHead() && state.view === "FRONT" && $("apply-phase-change").checked
        && frontSource.kind !== "upload" && !frontSource.phase) {
      return "Phase Change requires an uploaded FRONT reference or a selected locked FRONT source.";
    }
    return "";
  }

  async function generate(count, renderMode, revision, replacement = {}) {
    if (state.mutation || !state.detail) return {status:"cancelled"};
    const reason = phaseChangeBlock();
    if (reason) return {status:"error",message:reason};
    const scope = api(), view = state.view, signal = state.controller.signal;
    const current = () => !signal.aborted && scope === api() && view === state.view;
    state.mutation = true;
    try {
      const result = await request(api(`/views/${encodeURIComponent(view)}/generate`), {
        method: "POST", body: JSON.stringify({count, render_mode: renderMode,
          aspect_ratio: state.aspectRatio, expected_revision: revision,
          apply_phase_change: isHead() && view === "FRONT" && $("apply-phase-change").checked,
          costume_settings: savedDressingSettings(), ...replacement}),
      });
      if (!current() || result.revision < state.detail.revision) return {status:"cancelled"};
      state.detail = result;
      render();
      return {status:"success",message:"Render slots updated."};
    } catch (error) {
      if (!current()) return {status:"cancelled"};
      await loadDetail().catch(() => {});
      return {status:"error",message:error.message};
    } finally {
      if (!signal.aborted) state.mutation = false;
    }
  }

  async function previewPrompt() {
    const signal = state.controller.signal;
    const button = $("prompt-preview-button");
    button.disabled = true;
    try {
      const preview = await request(api(`/views/${encodeURIComponent(state.view)}/prompt`), {
        method: "POST", body: JSON.stringify({apply_phase_change: isHead() && state.view === "FRONT" && $("apply-phase-change").checked,
          costume_settings: savedDressingSettings()}),
      });
      $("prompt-text").textContent = preview.prompt;
      $("prompt-references").replaceChildren(...preview.reference_inputs.map((input) => {
        const item = document.createElement("li");
        item.textContent = `${input.role || input.label || "Reference"}${input.render_mode ? ` · ${input.render_mode}` : ""}`;
        return item;
      }));
      $("prompt-preview").hidden = false;
      $("prompt-preview").open = true;
      show("Prompt compiled from current masters and selected references.");
    } catch (error) { reportError(error); }
    finally { if (!signal.aborted) button.disabled = false; }
  }

  async function bulkBoardAction(action, revision) {
    const scope = api(), view = state.view, signal = state.controller.signal;
    const current = () => !signal.aborted && scope === api() && view === state.view;
    const endpoint = `/views/${encodeURIComponent(view)}/${action}`;
    state.mutation = true;
    try {
      const preview = await request(api(endpoint + "/preview"), {method:"POST",body:"{}"});
      if (!current()) return {status:"cancelled"};
      if (preview.revision !== revision) throw new Error("The board changed. Refresh and review the deletion again.");
      const effects = preview.protected_effects.map(effect => ({...effect,
        preview_url:state.detail.boards[view].candidates[effect.candidate_id]?.image_path ? imageUrl(effect.candidate_id) : ""}));
      const approved = await confirmCandidateDeletion(action, `${pipelineLabels[state.pipeline]} · ${view}`,
        preview.candidates.map(item => item.slot), preview.active_slots, effects);
      if (approved === null || !current()) return {status:"cancelled"};
      const result = await request(api(endpoint), {method:"POST",body:JSON.stringify({
        confirmation_token:preview.confirmation_token,expected_revision:preview.revision,approved_effects:approved,
      })});
      if (!current()) return {status:"cancelled"};
      state.detail = result;
      render();
      return {status:"success",message:"Candidates updated."};
    } finally {
      if (!signal.aborted) state.mutation = false;
    }
  }
  $("prompt-preview-button").addEventListener("click", () => void previewPrompt());
  $("edit-template").addEventListener("click", async () => {
    const signal = state.controller.signal;
    try {
      const master = await request(api("/template"));
      await window.ZetSourceEditor.open({source_path: master.source_path,
        source_label: `Character.md · ${master.character} · ${master.phase}`, editable: true},
        (message) => show(message, true), signal);
    } catch (error) { reportError(error); }
  });
  $("edit-costume-template").addEventListener("click", async () => {
    try {
      const sources = await request(api("/template-sources"));
      const costume = sources.sources.find(source => source.kind === "costume");
      if (!costume) throw new Error("The governing Costume template is unavailable.");
      await window.ZetSourceEditor.open({source_path: costume.source_path,
        source_label: costume.source_id, editable: true}, (message) => show(message, true), state.controller.signal);
    } catch (error) { reportError(error); }
  });
  window.ZetModelPicker?.attach($("template-model"), {required: ["text"], allowDefault: true});
  $("template-mode").addEventListener("change", updateTemplateMode);
  $("template-improvement").addEventListener("toggle", watchTemplateReview);
  $("template-reload").addEventListener("click", async () => {
    try { state.templateProposal = (await request(api("/template-proposals"))).proposal;
      renderTemplateProposal(); watchTemplateReview(); }
    catch (error) { reportError(error); }
  });
  $("template-analyze").addEventListener("click", async () => {
    if (!state.detail) return;
    const button = $("template-analyze"); button.disabled = true;
    const mode = $("template-mode").value;
    const choice = $("template-candidate").value;
    if (mode === "candidate" && !choice) { $("template-status").textContent = "Choose a finished candidate."; button.disabled = false; return; }
    const [view, candidate_id] = mode === "candidate" ? choice.split(":") : ["", ""];
    try {
      state.templateProposal = await request(api("/template-reviews"), {method: "POST",
        body: JSON.stringify({mode, view, candidate_id, direction: $("template-guidance").value,
          model: $("template-model").value, expected_revision: state.detail.revision,
          source_ids: [...$("template-sources").querySelectorAll("input:checked")].map(input => input.value)})});
      $("template-status").textContent = "Analyzing templates…";
      renderTemplateProposal(); watchTemplateReview();
    } catch (error) { $("template-status").textContent = error.message; reportError(error); }
    finally { button.disabled = false; }
  });
  function refresh() {
    void loadDetail().then(pollProgress).catch(reportError);
  }
  function reportError(error) {
    if (error.name !== "AbortError") show(error.message, true);
  }
  $("refresh").addEventListener("click", refresh);
  $("view").addEventListener("change", (event) => void navigate(event.target.value));
  $("costume").addEventListener("change", () => void activate(state.pipeline, {costume: $("costume").value, view: state.view}));
  function followViewLink(event, link, view) {
    if (!link || event.button !== 0 || event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) return;
    event.preventDefault();
    void navigate(view);
  }
  $("back").addEventListener("click", event => followViewLink(event, $("back"), ""));
  $("outputs").addEventListener("click", event => {
    const link = event.target.closest("a[data-container-view]");
    followViewLink(event, link, link?.dataset.containerView);
  });
  $("source-phase").addEventListener("change", () => void loadPhaseSourceCandidates());
  $("apply-phase-change").addEventListener("change", () => {
    state.phaseChange = $("apply-phase-change").checked;
    $("source-lock").hidden = !$("apply-phase-change").checked;
    $("source-phase").disabled = !$("apply-phase-change").checked;
    $("save-phase-source").disabled = !$("apply-phase-change").checked;
    if ($("apply-phase-change").checked) void loadPhaseSourceCandidates();
    if (state.view === "FRONT") renderBoard();
    const frontSource = state.detail?.sources?.phase_change ?? state.detail?.sources?.phase_change_by_mode?.final ?? state.detail?.sources?.phase_change_by_mode?.draft ?? {};
    if (!$("head-render-mode").hidden && state.view === "FRONT") {
      const hasReference = frontSource.kind === "upload" || Boolean(frontSource.phase);
      $("head-render-mode").textContent = `FRONT render: ${hasReference ? "With FRONT reference" : "No FRONT reference"}${$("apply-phase-change").checked ? " · Phase Change" : " · No Phase Change"}${$("apply-phase-change").checked && !hasReference ? " — Phase Change requires a reference." : "."}`;
    }
  });
  const phaseSourcePaste = $("phase-source-paste");
  window.ZetImageInput.attach(phaseSourcePaste, $("phase-source-file"));
  $("phase-source-file").addEventListener("change", () => {
    state.phaseSourceFile = $("phase-source-file").files?.[0] || null;
    if (state.phaseSourceFile) $("phase-source-status").textContent = `Selected ${state.phaseSourceFile.name}. Upload to save it as the FRONT reference.`;
  });
  phaseSourcePaste.addEventListener("paste", (event) => {
    const file = Array.from(event.clipboardData?.items || []).map((item) => item.getAsFile()).find(Boolean);
    if (!file) return;
    event.preventDefault();
    state.phaseSourceFile = file;
    $("phase-source-status").textContent = `Pasted ${file.name || "image"}. Upload to save it as the FRONT reference.`;
  });
  $("dressing-mode").addEventListener("change", () => {
    state.dressingDrafts[state.view] = {mode: $("dressing-mode").value, costume_reference_view: $("dressing-reference").value};
    $("dressing-reference").disabled = $("dressing-mode").value === "doll-dressing-no-ref";
    $("dressing-status").textContent = "Unsaved changes. Preview and Generate use saved settings.";
  });
  $("dressing-reference").addEventListener("change", () => {
    state.dressingDrafts[state.view] = {mode: $("dressing-mode").value, costume_reference_view: $("dressing-reference").value};
    $("dressing-status").textContent = "Unsaved changes. Preview and Generate use saved settings.";
  });
  $("save-dressing-settings").addEventListener("click", async () => {
    const source = {view: state.view, mode: $("dressing-mode").value,
      costume_reference_view: $("dressing-reference").value};
    try {
      state.detail = await request(api("/sources/dressing_settings"), {method: "PUT",
        body: JSON.stringify({source, expected_revision: state.detail.revision})});
      delete state.dressingDrafts[state.view];
      render();
      $("dressing-status").textContent = `Saved ${source.mode} settings for ${state.view.replaceAll("_", " ")}.`;
    } catch (error) { if (error.name !== "AbortError") $("dressing-status").textContent = error.message; }
  });
  $("save-phase-source").addEventListener("click", () => {
    if (!$("apply-phase-change").checked) return;
    const source = {phase: $("source-phase").value};
    if (!source.phase) { $("phase-source-status").textContent = "Choose a source phase first."; return; }
    void saveSource("phase_change", source);
  });
  $("clear-phase-source").addEventListener("click", () =>
    void saveSource("phase_change", {}));
  $("upload-phase-source").addEventListener("click", async () => {
    const file = state.phaseSourceFile || $("phase-source-file").files?.[0];
    if (!file) { $("phase-source-status").textContent = "Choose or paste a PNG, JPEG, or WebP image first."; return; }
    const params = query();
    params.set("filename", file.name || "pasted-front.png");
    params.set("expected_revision", state.detail.revision);
    try {
      state.detail = await request(`/api/character-containers/${encodeURIComponent(state.pipeline)}/sources/phase-change-upload?${params}`, {
        method: "PUT", headers: {"Content-Type": file.type || "application/octet-stream"}, body: file,
      });
      $("phase-source-file").value = "";
      state.phaseSourceFile = null;
      render();
      $("phase-source-status").textContent = "Managed upload saved for new FRONT requests.";
    } catch (error) { if (error.name !== "AbortError") $("phase-source-status").textContent = error.message; }
  });
  $("save-view-source").addEventListener("click", () => {
    const views = {...(state.detail.sources?.views || {}), [state.view]: $("source-view").value};
    void saveSource("views", views);
  });
  document.addEventListener("visibilitychange", () => {
    if (!pageVisible()) { stopPolling(); return; }
    if (state.active && state.scope?.phase && (state.pipeline !== "costume-dressing" || state.costume)) refresh();
  });
  window.ZetCharacterAssetContainer = {
    pipeline() { return state.pipeline; },
    context() { return {pipeline: state.pipeline, costume: state.costume, view: state.view}; },
    activate,
    deactivate,
    refreshScope() { return activate(state.pipeline, {view: state.view, costume: state.costume}); },
  };
  if (document.querySelector("#character-asset-container-page")?.classList.contains("active")) {
    void activate(new URLSearchParams(location.search).get("pipeline"));
  }
})();
