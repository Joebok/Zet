export function renderProposalComparison(row, escape, oldLabel = "Old") {
  return `<div class="narrative-proposal-comparison"><section><h4>${escape(oldLabel)}</h4><pre>${escape(row.old)}</pre></section><section><h4>New</h4><pre>${escape(row.text)}</pre></section></div>`;
}

export function renderProposalDecisions(id, label, choices, selected, escape) {
  const name = `proposal-${id}`;
  return `<fieldset class="proposal-decision-group"><legend>${escape(label)}</legend>${choices.map(choice =>
    `<label><input type="radio" name="${escape(name)}" data-proposal="${escape(id)}" data-proposal-choice="${escape(choice)}" value="${escape(choice)}" ${selected === choice ? "checked" : ""}>${escape(choice)}</label>`).join("")}</fieldset>`;
}

export function renderProposalAcceptance(id, label, accepted, escape) {
  return `<label class="proposal-acceptance"><input type="checkbox" data-proposal="${escape(id)}" ${accepted ? "checked" : ""}>Accept this suggested change: ${escape(label)}</label>`;
}
