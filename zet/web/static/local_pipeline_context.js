(() => {
  const STORAGE_KEY = "zet:last-character-phase";

  function fill(select, values, selected = "") {
    select.replaceChildren();
    for (const value of values) {
      const option = document.createElement("option");
      option.value = value;
      option.textContent = value;
      select.append(option);
    }
    if (values.includes(selected)) select.value = selected;
  }

  function fillPhases(select, context, character, preferredPhase = "") {
    const phases = context.phases_by_character?.[character] || [];
    const selected = phases.includes(preferredPhase) ? preferredPhase : phases[0] || "";
    fill(select, phases, selected);
    return phases;
  }

  async function initialize(characterSelect, phaseSelect) {
    const response = await fetch("/api/context");
    const context = await response.json().catch(() => ({}));
    if (!response.ok) throw new Error(context.detail || "Could not load character and phase options.");

    const characters = context.characters || [];
    let saved = {};
    try { saved = JSON.parse(localStorage.getItem(STORAGE_KEY) || "{}"); } catch (_) {}

    const character = characters.includes(saved.character)
      ? saved.character
      : characters.includes(context.default_character) ? context.default_character : characters[0] || "";
    fill(characterSelect, characters, character);

    const phases = context.phases_by_character?.[character] || [];
    const phase = phases.includes(saved.phase)
      ? saved.phase
      : phases.includes(context.default_phase) ? context.default_phase : phases[0] || "";
    fill(phaseSelect, phases, phase);
    return context;
  }

  window.ZetLocalPipelineContext = { fillPhases, initialize };
})();
