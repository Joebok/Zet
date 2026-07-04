# AI Prompt Review

Implement functionality to have Prompt_Review an AI task to run through the proxy

##

Use qwen3.5:9b-instruct as the model. Should be a config option if we want to change later.

We will send the Final_Image_Prompt.md along with the instructions below. Based on the instructions, we should expect a pass or fail and if a fail, then a reason.

If we get a pass, then pass the prompt_review and send to render.

If we get a fail, fail it and put the summary where it can be inspected. I think that a prompt fail already goes to an error condition and we can put the summary in for the error message.

If python can't determine the answer, then we also need to error out and probably save the full response for diagnosis.

The prompt instructions below should be a shared resource, so store in a file in the right place so I can edit it as we try it out.

## Prompt_Review instructions to local AI

You are a validator for image-generation prompts.

Your task is NOT to improve, rewrite, or optimize the prompt.

Your task is ONLY to detect problems that should be corrected before the prompt is sent to an image model.

Ignore harmless repetition.

Ignore references to other images, assume they will all be provided.

Treat repeated instructions as acceptable if they reinforce the same requirement.

Return EXACTLY this format:

RESULT: PASS or FAIL

CATEGORY: NONE | TEMPLATE | CONTRADICTION | AMBIGUITY | STALE_TEXT | MISSING_INFORMATION | OTHER

SUMMARY: One sentence, maximum 25 words.

Rules:

PASS means:
- No clear contradictions.
- No stale text from another template.
- No ambiguous instructions likely to confuse an image model.

FAIL means one or more of the above exists.

If a blatent contradtion is found, report FAIL immediately, no further analysis is required.

If multiple problems exist, report only on the first one detected.

Do NOT explain your reasoning.

Do NOT rewrite the prompt.

Do NOT output markdown.

Do NOT output anything except the three required lines.

When checking the prompt, look for:

• contradictory clothing instructions
• contradictory orientation or camera-view instructions
• contradictory body/head authority instructions
• contradictory pose instructions
• contradictory framing instructions
• contradictory character age or phase
• contradictory species
• contradictory equipment or costume instructions
• instructions that both require and forbid the same thing
• unresolved placeholders
• TODO markers
• template instructions that were never replaced
• references to the wrong character, age, outfit, or phase
• instructions referring to assets that do not exist
• left/right inconsistencies
• front/back inconsistencies
• profile/three-quarter inconsistencies
• body/head view mismatches
• statements that cannot all be true simultaneously

Do NOT fail for:

• repeated wording
• emphasis
• redundant reminders
• multiple negative instructions expressing the same rule
• style preferences
• prompt length

If uncertain, return PASS.

Now validate the following prompt.

========================

{{FINAL_IMAGE_PROMPT}}

========================

## Sample output

I ran against several prompts and got responses like:

RESULT: FAIL
CATEGORY: CONTRADICTION
SUMMARY: Clothing instructions contradict between neutral tan fitment and specific colored garments (orange shirt/blue jeans).

RESULT: PASS
CATEGORY: NONE
SUMMARY: Prompt contains no unresolved placeholders, contradictory asset references, or conflicting instructions for generation model execution.

## Processing Results

If the AI review returns Pass, advance the job just like a human review proces that accepts the promt.

If the AI review return FAIL, then the pipeline should remain at PROMPT_REVIEW but the actor should be changed to Human. The AI summary should be somewhere easily found. 