# To Do items

Pipeline Viewer - list of all pipelines (friendly names), click to see list of files, click file to see contents or image. -

Comic Panel Create. Specify overall aspect ratio (default 8.5x11) and panel divisions. Select images to place, have zoom and crop controls for assembly.

Augmented prompt for left-right read on scenes; incorporate depth.

Setting up HTTPS://

Age-Adjuster Pipeline

Head Generation Pipeline

Species Template add/edit

Head-Fitment:

Recommended correction

For this particular fitment prompt, I would remove nearly all descriptive face-generation language and replace it with a strict source-rendering lock such as:

SOURCE RENDERING LOCK
Preserve the complete visible rendering of the Character Head source above the jawline as closely as possible. This includes not only identity and feature geometry, but also apparent age, facial maturity, skin texture, fine lines, under-eye structure, cheek hollowing, eyelid weight, nasolabial definition, mouth-area texture, asymmetry, shading, brushwork, and surface detail.

Do not beautify, idealize, smooth, rejuvenate, cosmetically lift, or anime-stylize the facial anatomy. Do not enlarge or round the eyes, narrow the jaw, soften the cheeks, simplify the eyelids, smooth the skin, reduce facial lines, or replace mature facial planes with youthful ones.

The source image already represents the correct canonical character, age phase, hairstyle, and rendering style. Do not reinterpret it from the textual character description. The text is validation only and must not override visible source details.

I would also change:

“art-style conversion if required”

to:

“No art-style conversion is required when the Character Head source already uses the canonical style. Preserve its existing rendering finish.”

In this case, the original head source already appears to be in the intended painterly semi-realistic fantasy style. Calling for conversion was unnecessary and gave the model permission to repaint and simplify it.