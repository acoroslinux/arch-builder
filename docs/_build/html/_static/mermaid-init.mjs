import mermaid from 'https://cdn.jsdelivr.net/npm/mermaid@11/dist/mermaid.esm.min.mjs';

function convertMermaidBlocks() {
  const blocks = document.querySelectorAll('.highlight-mermaid, div.highlight-mermaid, .code.mermaid');

  blocks.forEach((block) => {
    const pre = block.querySelector('pre');
    if (!pre) {
      return;
    }

    const text = pre.textContent?.trim();
    if (!text) {
      return;
    }

    const mermaidPre = document.createElement('pre');
    mermaidPre.className = 'mermaid';
    mermaidPre.textContent = text;
    block.replaceWith(mermaidPre);
  });

  document.querySelectorAll('pre.mermaid').forEach((pre) => {
    pre.textContent = pre.textContent?.trim() || '';
  });
}

async function renderMermaid() {
  convertMermaidBlocks();
  mermaid.initialize({
    startOnLoad: false,
    securityLevel: 'loose',
    theme: 'neutral',
    flowchart: { useMaxWidth: true, htmlLabels: true },
  });

  await mermaid.run({ querySelector: '.mermaid' });
}

if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', () => {
    renderMermaid();
  });
} else {
  renderMermaid();
}