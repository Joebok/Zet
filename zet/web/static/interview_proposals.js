export function renderProposalComparison(row, escape, oldLabel = "Old") {
  return `<div class="narrative-proposal-comparison"><section><h4>${escape(oldLabel)}</h4><pre>${escape(row.old)}</pre></section><section><h4>New</h4><pre>${escape(row.text)}</pre></section></div>`;
}
