# 0037 - Manual scene text after rendering
Status: accepted (2026-10-29)

## Decision
Compose text locally with Pillow after artwork generation. Manually place boxes and straight tails; share appearance at universe/story level. Use the same renderer for preview and final output, preserving font size and reporting overflow. Restricted markup allows emphasis without executing HTML.

## Ownership and compatibility
Assembly entries are shared authored content; candidate geometries are independent. Render snapshots seed placement without baking lettering into model inputs. Confirmation binds text/style/geometry/source identity and publishes a distinct PNG. Locks protect confirmed revisions; original artwork and earlier revisions survive replacement. Old records remain unlettered. Finished-image consumers share a resolver rather than recomposing on reads.

## Consequences
Harmonization drift is handled by manual candidate confirmation. Later edits remain drafts until reconfirmed. Installed font availability is explicit; V1 uses approved Windows font families. No new dependency, AI request or legacy Scene Builder integration is introduced.
