Goal:
Implement a lightweight Zine Maker feature for Zet.

Purpose:
The tool takes existing Zet image reference tags, resolves them to image files, scales/crops them into zine page panels, arranges them into a printable 8-panel folded-zine layout, adds faint fold/cut panel guides, previews the result, and saves a PNG plus simple JSON metadata.

Important:
The source images are the valuable artifacts. The zine PNG is derived and regenerable. Do not add protection, drift warnings, hashing, special lifecycle metadata, or logging.

Zine storage:
Create Assets/Zines if it does not exist.

Each zine should live in its own folder:
Assets/Zines/<zine-slug>/<zine-slug>.png
Assets/Zines/<zine-slug>/<zine-slug>.json

Use the existing Zet filename sanitization pattern:
replace illegal filename characters with "-".

Do not allow creating a new zine if a zine folder with the same sanitized name already exists.
Editing an existing zine may overwrite its own PNG and JSON.

Zine page model:
A zine has exactly 8 panels:
Front
Page 1
Page 2
Page 3
Page 4
Page 5
Page 6
Back

There is no Page 7.

Output format:
PNG only.

Page size:
Each individual page panel is 1275 px wide by 1650 px tall.

Final output size:
5100 px wide by 3300 px tall.

Image scaling:
Use center cover-crop only.
Scale each source image until it fully covers the target rectangle, then center crop the excess.
No crop adjustment UI.
No face detection.
No crop anchors.

Spread behavior:
Front and Back never use spreads.

The only supported spread pairs are:
Page 1 + Page 2
Page 3 + Page 4
Page 5 + Page 6

Use blank even-numbered pages to indicate spread mode:
If Page 2 is blank, use the Page 1 image as a spread across Page 1 + Page 2.
If Page 4 is blank, use the Page 3 image as a spread across Page 3 + Page 4.
If Page 6 is blank, use the Page 5 image as a spread across Page 5 + Page 6.

For spread images:
Scale and center-crop the source image to 2550 px wide by 1650 px tall.
Split it into two 1275 x 1650 halves.
The lower-numbered page gets the left half.
The higher-numbered page gets the right half.

Final print layout:
Top row:
Page 6, Page 5, Page 4, Page 3

Bottom row:
Back, Front, Page 1, Page 2

Before inserting top-row pages, rotate Page 6, Page 5, Page 4, and Page 3 by 180 degrees.

Image reference resolution:
Use Zet's existing image reference resolver. The user will enter tags such as:
{{AUX:person:freydis}}
{{ASSET:Tsaeytte:Adult:31}}

Each nonblank tag should resolve to one unique image file.
Store the image tags in the JSON, not raw resolved filenames.

Regenerate / refresh behavior:
When the user clicks Refresh or Regenerate:
1. Load the zine JSON.
2. Resolve the image tags fresh.
3. Rebuild the zine PNG.
4. Overwrite the existing zine PNG.
5. Refresh the preview.

Do not warn if the source images changed. That is intended.

Guides:
Add faint panel boundary guides by default.
Draw vertical guide lines at:
x = 1275
x = 2550
x = 3825

Draw horizontal guide line at:
y = 1650

Use a faint gray guide color, for example RGB (190, 190, 190), with a narrow line width.
Make guide drawing easy to disable in code, but default to enabled.

JSON metadata:
Use a simple JSON file like:

{
  "zine_name": "My Zine Name",
  "zine_slug": "My-Zine-Name",
  "output_image": "My-Zine-Name.png",
  "slots": {
    "front": "{{ASSET:Tsaeytte:Adult:31}}",
    "page_1": "{{ASSET:Tsaeytte:Adult:32}}",
    "page_2": "",
    "page_3": "{{ASSET:Tsaeytte:Adult:33}}",
    "page_4": "",
    "page_5": "{{AUX:person:freydis}}",
    "page_6": "",
    "back": "{{ASSET:Tsaeytte:Adult:34}}"
  },
  "guides": {
    "enabled": true
  }
}

No created_at or updated_at metadata needed.

Validation:
Zine name is required.
Front is required.
Page 1 is required.
Page 3 is required.
Page 5 is required.
Back is required.
Page 2, Page 4, and Page 6 may be blank to indicate spread mode from the previous odd-numbered page.
All nonblank image tags must resolve to one image file.
All resolved files must be readable images.
The same image reference may be used more than once.
Do not allow a new zine to use the same sanitized name as an existing zine.

UI:
Add a Zine Maker area.

The list view should show existing zines from Assets/Zines.
When a zine is selected, show a scaled preview of the actual print layout.
Hook the preview into the same click-to-full-screen image behavior used elsewhere in Zet.

Selected zine actions:
Edit
Refresh / Regenerate
Delete

Create/edit form fields:
Zine name
Front
Page 1
Page 2
Page 3
Page 4
Page 5
Page 6
Back

For Page 2, Page 4, and Page 6, show helper text:
Leave blank to use the previous page image as a two-page spread.

Recommended implementation functions:
cover_crop(image, target_w, target_h)
make_spread_pages(image)
build_page_images(slots, resolve_image_tag)
assemble_zine(page_images, guides_enabled=True)
draw_guides(canvas)
save_zine(metadata, zines_dir)
load_zine_metadata(json_path)
list_zines(zines_dir)
regenerate_zine(json_path)

Suggested implementation order:
1. Build the reusable Python zine assembly module.
2. Add a test/debug mode that creates labeled placeholder pages to verify layout and rotation.
3. Add list existing zines UI.
4. Add create/edit form.
5. Add preview/save/refresh integration.

Success criteria:
A zine can be created from 8 single image references.
A zine can be created with Page 1 spanning Page 1+2, Page 3 spanning Page 3+4, and Page 5 spanning Page 5+6 by leaving Page 2, Page 4, or Page 6 blank.
The final PNG is exactly 5100 x 3300.
The JSON can be reloaded to regenerate the PNG.
Refresh overwrites the existing PNG without warnings.
The preview shows the actual print layout scaled down.
Clicking preview uses the existing full-screen image viewer.
Faint panel guide lines are visible on the output.
The top row pages are rotated 180 degrees.