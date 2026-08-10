Image 1 is the reference. Image 2 is candidate seed {{SEED}}.

Answer each visible binary question independently:

{{CHECKLIST_QUESTIONS}}

Return true only when the condition is clearly visible. Return false when it is false. Return null when occlusion or image ambiguity prevents a reliable decision. Ignore pose, expression, composition, framing, lighting, and background unless the question explicitly concerns one of them.

Return exactly one JSON object and no surrounding prose:
{"checklist":[{"number":1,"result":false,"confidence":0,"evidence":"concise visible evidence"}]}

Return every numbered question in order. Do not return scores, aggregate judgments, or prompt suggestions.
