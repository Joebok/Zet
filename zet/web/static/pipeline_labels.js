window.ZetPipelineLabel = (value) => ({
  "head-image": "Head-Image (Construct)",
  "head-image-edit": "Head-Image (Edit)",
  "head-image edit": "Head-Image (Edit)",
  "local-head-image": "Head-Image (Construct)",
  "local-head-image-edit": "Head-Image (Edit)",
  "local_head_image": "Head-Image (Construct)",
  "local_head_image_edit": "Head-Image (Edit)",
})[String(value || "").toLowerCase()] || value;

// Apply only to human-readable status and error messages, never raw IDs or paths.
window.ZetPipelineMessage = (value) => String(value || "")
  .replace(/(?<![\w./\\-])(?:local[- ])?head[- ]image(?:[- ]edit)?\b(?!\s*\(|[\w/\\-]|\.[\w])/gi,
    match => /edit$/i.test(match) ? "Head-Image (Edit)" : "Head-Image (Construct)");
