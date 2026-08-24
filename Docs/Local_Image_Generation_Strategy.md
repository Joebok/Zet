# Local Image Generation Strategy

## Goal

Produce character and costume images locally with a repeatable workflow whose
accepted-image yield is high enough to be useful. Prompt wording is one control
variable, not the optimization target.

The canonical success question is:

> Would I use this image after no more than five minutes of cleanup?

`Config/Image_Quality_Rubric.json` makes that judgment auditable. A candidate
must pass identity, costume, anatomy, and composition gates; score at least 3/4
for identity and costume fidelity; and reach a weighted mean of 3/4. A workflow
is reasonably good when at least 25% of 16 candidates across four poses pass.
The threshold can be recalibrated after the first blinded review.

## Audit findings

- Hardware: RTX 5060 Ti with 16 GB VRAM, 26 GB system RAM.
- Corpus: 212 PNG assets. Tsaeytte has three age phases, multiple identity keys,
  eight-view body/head/character sets, and multiple eight-view costume sets.
- Models: 15 visible checkpoints spanning SD 1.5, SDXL, and Illustrious-derived
  families; SD 1.5 and SDXL pose ControlNets; SDXL IP-Adapter Plus; one LoRA.
- The most recent Prompt Evolution run used `perfectdeliberate_v90`, whose local
  metadata identifies it as Illustrious, through a profile labeled `sd15`.
- That run conditioned on DWPose/OpenPose only. Pose and broad silhouette were
  preserved, but appearance was not conditioned. All seeds changed the teal
  costume palette and several replaced the costume topology.
- Prompt Evolution then tried to correct those failures through text mutations.
  This asks the weakest control channel to recover information omitted by the
  workflow.
- No complete LoRA trainer is installed. `accelerate` and `diffusers` are
  present; PEFT/bitsandbytes and a supported training frontend are not.

## Strategy ranking

| Priority | Strategy | Expected value | Cost/risk | Decision |
|---|---|---:|---:|---|
| 1 | Fixed-prompt checkpoint and workflow search | High | Low | Run first |
| 2 | Appearance reference plus independent pose control | Very high | Medium | Primary workflow candidate |
| 3 | Low-denoise img2img for controlled variants | High for near-reference images | Low | Include as a bounded mode |
| 4 | IP-Adapter weight/timing search | High | Low | Automate with fixed seeds |
| 5 | Character/costume LoRA | Potentially high | Medium/high | Gate on dataset audit and baseline results |
| 6 | FaceID/PuLID/InstantID | Medium for identity, low for costume | Medium | Optional identity channel |
| 7 | Prompt mutation | Low after a sound recipe exists | Medium | Restrict to small A/B edits |
| 8 | Full checkpoint fine-tuning/DreamBooth | Unnecessary initially | High | Defer |

## Experimental loop

1. Freeze the initial prompt. Keep one set of benchmark seeds and poses.
2. Search recipe variables before text: checkpoint family, reference method,
   reference strength/timing, pose strength/timing, CFG, sampler, and denoise.
3. Render a coarse matrix with one image per condition. Eliminate conditions
   that fail any hard gate.
4. Render survivors across fixed and fresh seeds and four poses.
5. Present randomized contact sheets without settings or prompt history.
6. Record keep/reject, rubric scores, and one or more failure reasons.
7. Rank by acceptable yield, then cleanup time, then render time. Do not average
   a catastrophic identity or costume failure into an otherwise attractive
   score.
8. Change prompt wording only when the same semantic defect survives multiple
   seeds under an otherwise acceptable recipe.

Local vision models may prefilter obvious anatomy, crop, or subject-count
failures. They do not decide aesthetic acceptance. Human decisions are the
ground truth and become the calibration set for later automated ranking.

## First experiment

Use Tsaeytte / Adult / Canonical Adventure Gear / Front as the anchor because
the current failure corpus already exists.

### Stage A: recipe screening

- Freeze Prompt Evolution batch 0's initial prompt.
- Use the same two benchmark seeds for every condition.
- Compare representative checkpoints from three groups:
  `perfectdeliberate_v90`, `perfectdeliberate_ilAnime`,
  `waiNTRMIXIllustrious_v11`, `novaAnimeXL_ilV190`,
  `perfectdeliberate_XL`, and `dreamshaperXL_lightningDPMSDE`.
- Compare txt2img, pose-only, IP-Adapter-only, low-denoise img2img, and combined
  IP-Adapter plus pose control.
- For IP-Adapter, screen weights 0.35, 0.55, and 0.75 with end times 0.65 and
  0.85. For img2img, screen denoise 0.30, 0.45, and 0.60.

This is a fractional search, not the full Cartesian product. Start with one
checkpoint per family and promote only promising workflow/strength regions.

### Stage B: robustness

Render the best three conditions across eight fixed seeds and four distinct
poses. Apply the quality rubric blindly. Promote only a recipe with at least a
25% accepted yield and no systematic identity or costume failure.

### Stage C: scene generalization

Test the promoted recipe on a neutral reference image, a simple narrative pose,
and a two-character scene. A recipe that only reproduces the canonical front
view is a useful asset-variant mode, not the final scene workflow.

## Recommended ComfyUI workflow

Use separate information channels:

```text
checkpoint + optional LoRA
        |
        +-- text conditioning: requested scene and only essential attributes
        +-- appearance reference: IP-Adapter image or image set
        +-- identity reference: FaceID/PuLID when needed
        +-- pose/view reference: DWPose or depth ControlNet
        +-- optional regional mask: character/costume isolation
        |
      sampler -> decode -> optional face/hand detail pass -> candidate
```

The appearance image and pose image must be independently selectable. Reusing
one image for both is valid for a canonical-view fidelity test, but prevents new
poses. Use image batches or embedding averaging for multi-view appearance
references rather than stacking many full-strength adapters.

## LoRA feasibility

### Character LoRA

Feasible. Tsaeytte has enough raw images to curate roughly 20-40 useful images
per age phase, including head, upper-body, and full-body views. Do not train on
all files automatically: turnaround sheets, diagnostics, near-duplicates,
cropped derivatives, and visibly inconsistent images would teach their defects.

Train age phases as separate concepts initially. A shared character token plus
age tokens can be tested later only if cross-age identity is a requirement.

### Costume LoRA

Feasible but data-limited per outfit. Most complete outfits have eight canonical
views, which is enough for a small proof of concept but prone to memorizing the
neutral pose and background. Improve it with curated crops, transparent or
varied backgrounds, and captions that name garment topology while excluding
pose/view from the costume token.

Separate identity and costume LoRAs are preferred. They can be mixed at render
time and are easier to diagnose than one LoRA that entangles person, outfit,
pose, and studio background.

### Training gate

Start LoRA work only after:

1. a compatible target checkpoint family wins the recipe screen;
2. the curated set passes duplicate and consistency review;
3. captions and holdout images exist; and
4. a supported local trainer is installed.

Use 10-20% of views as holdouts. Compare the LoRA against IP-Adapter on unseen
poses using the same prompt, seeds, and rubric. Reject a LoRA that merely copies
training poses or improves identity while reducing costume fidelity.

## Automation target

The durable replacement for Prompt Evolution is a Recipe Lab:

- immutable experiment manifest;
- explicit checkpoint-family compatibility;
- fixed prompt, seeds, references, and pose set;
- parameter matrix with coarse-to-fine expansion;
- local queue execution and metadata capture;
- randomized contact-sheet review;
- rubric decisions and failure tags;
- ranked recipes by accepted yield and cost;
- resumable runs and promotion of a winning recipe.

Prompt Evolution can remain as a final, bounded semantic repair step after the
Recipe Lab has selected a stable generation recipe.

## Live experiment findings

Experiments are stored under
`Zet_Library/Pipelines/Image_Recipe_Lab/Tsaeytte_Adult_Canonical_Adventure_Gear`.

- `screen_001`: scene-prompt IP-Adapter only. Rejected. It recovered the teal
  palette but the scene costume source omitted lower-garment details and the
  adapter copied reference composition into some backgrounds.
- `screen_002`: unchanged Prompt Evolution initial prompt with separate
  IP-Adapter appearance and DWPose/SDXL ControlNet channels. This was the first
  material improvement: all six candidates retained the intended outfit family
  instead of replacing it with an unrelated dress.
- `screen_003`: three checkpoint families across three fixed seeds at appearance
  weight 0.45. All nine retained the core palette, blouse, overskirt, leggings,
  boots, full-body framing, and elf identity. Exact face/hair, lip color, and
  overskirt topology still vary.
- `screen_004`: six additional installed checkpoints. TastyRice Magic on Paper
  and Animagine were promoted; the others were rejected for flat style, costume
  drift, or framing failure.
- `screen_005`: the two promoted checkpoints across three seeds. Both are
  seed-stable enough for human calibration. TastyRice is more semi-realistic;
  Animagine preserves the full outfit more consistently but is more anime-like.
- `pose_validation.png`: the same two recipes at Front, Front-Left 3/4,
  Front-Right 3/4, and Left Profile. The front costume image remains the
  appearance source while separate Body-Reference images drive pose. All eight
  renders preserve the outfit family and requested view; TastyRice remains more
  painterly and Animagine keeps darker hair and stronger costume consistency.

The local 8.8B vision prefilter took 173 seconds for its first downscaled pair
and rejected it for identity/costume deviations. This is useful as an optional
asynchronous finalist check, but too slow for the default generation loop on
the current GPU. Human keep/reject decisions remain required.

## Baseline decision

TastyRice Magic on Paper SDXL is the default checkpoint for single-character
illustrated renders. The default local render backend is ComfyUI with the
IP-Adapter preview profile. PerfectDeliberate remains available as a Stable
Matrix fallback, and Animagine remains an optional comparison checkpoint.

The dashboard exposes the validated recipe under **Tools → Single Character
Lab**. Select a locked Costume-Dressing image, select the matching
Body-Reference pose, choose the number of images, and generate. TastyRice,
reference weight 0.45, and the SDXL IP-Adapter + OpenPose ControlNet workflow
are selected by default. Runs execute in the background and remain available
in the page's run history.
