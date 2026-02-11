/**
 * UI Audit Mode — overflow scanner.
 * Activated via ?audit=1 query param.
 * Creates a fixed overlay panel showing overflow offender count
 * and marks offending elements with red dashed borders.
 */

const SELECTORS = [
  'table',
  '.card-premium',
  'header',
  '[class*="flex"]',
  '[class*="grid"]',
  'h1',
  'h2',
  'h3',
] as const;

const OVERFLOW_EXCLUDE = [
  'overflow-x-auto',
  'overflow-y-auto',
  'overflow-auto',
  'overflow-scroll',
];

const TOLERANCE = 1; // px — subpixel rounding tolerance

const BADGE_ATTR = 'data-audit-badge';

interface AuditFinding {
  element: HTMLElement;
  overflowX: number;
  overflowY: number;
  selector: string;
}

function isExcluded(el: HTMLElement): boolean {
  return OVERFLOW_EXCLUDE.some(cls => el.classList.contains(cls));
}

function checkOverflow(el: HTMLElement): { overflowX: number; overflowY: number } | null {
  const overflowX = el.scrollWidth - el.clientWidth;
  const overflowY = el.scrollHeight - el.clientHeight;

  if (overflowX > TOLERANCE || overflowY > TOLERANCE) {
    return { overflowX, overflowY };
  }
  return null;
}

function createBadge(): HTMLDivElement {
  const badge = document.createElement('div');
  badge.textContent = 'OVERFLOW';
  badge.style.cssText = `
    position: absolute;
    top: 2px;
    right: 2px;
    background: rgba(255, 0, 0, 0.85);
    color: white;
    font-size: 9px;
    font-weight: 900;
    padding: 2px 6px;
    border-radius: 4px;
    z-index: 99999;
    pointer-events: none;
    text-transform: uppercase;
    letter-spacing: 0.1em;
    font-family: monospace;
  `;
  return badge;
}

function createPanel(): HTMLDivElement {
  const panel = document.createElement('div');
  panel.id = 'ui-audit-panel';
  panel.style.cssText = `
    position: fixed;
    bottom: 16px;
    right: 16px;
    background: rgba(0, 0, 0, 0.9);
    color: #f3f4f6;
    padding: 12px 16px;
    border-radius: 12px;
    font-family: 'Roboto Mono', monospace;
    font-size: 12px;
    z-index: 100000;
    border: 1px solid rgba(255, 0, 0, 0.3);
    min-width: 200px;
    backdrop-filter: blur(8px);
  `;
  panel.innerHTML = `
    <div style="font-size:10px;text-transform:uppercase;letter-spacing:0.2em;color:rgba(255,91,110,0.8);font-weight:900;margin-bottom:6px;">
      UI Audit Mode
    </div>
    <div id="audit-count" style="font-size:20px;font-weight:900;">0 overflows</div>
    <div id="audit-route" style="font-size:10px;color:rgba(255,255,255,0.5);margin-top:4px;"></div>
  `;
  document.body.appendChild(panel);
  return panel;
}

function markElement(el: HTMLElement): void {
  const computed = getComputedStyle(el);
  if (computed.position === 'static') {
    el.style.position = 'relative';
  }
  el.style.outline = '2px dashed red';
  el.style.outlineOffset = '-2px';
  const badge = createBadge();
  badge.setAttribute(BADGE_ATTR, 'true');
  el.appendChild(badge);
}

function clearMarks(): void {
  document.querySelectorAll(`[${BADGE_ATTR}]`).forEach(b => b.remove());
  document.querySelectorAll<HTMLElement>('[style*="outline: 2px dashed red"]').forEach(el => {
    el.style.outline = '';
    el.style.outlineOffset = '';
  });
}

function runScan(): AuditFinding[] {
  clearMarks();
  const findings: AuditFinding[] = [];
  const selectorString = SELECTORS.join(', ');
  const elements = document.querySelectorAll<HTMLElement>(selectorString);

  elements.forEach(el => {
    if (isExcluded(el)) return;

    const overflow = checkOverflow(el);
    if (overflow) {
      let matchedSelector = 'unknown';
      for (const sel of SELECTORS) {
        if (el.matches(sel)) {
          matchedSelector = sel;
          break;
        }
      }

      findings.push({
        element: el,
        overflowX: overflow.overflowX,
        overflowY: overflow.overflowY,
        selector: matchedSelector,
      });

      markElement(el);
    }
  });

  return findings;
}

function updatePanel(panel: HTMLDivElement, findings: AuditFinding[]): void {
  const countEl = panel.querySelector('#audit-count');
  const routeEl = panel.querySelector('#audit-route');
  if (countEl) {
    const n = findings.length;
    countEl.textContent = `${n} overflow${n !== 1 ? 's' : ''}`;
    (countEl as HTMLElement).style.color = n > 0 ? '#ff5b6e' : '#2ee59d';
  }
  if (routeEl) {
    routeEl.textContent = window.location.pathname;
  }
}

function logFindings(findings: AuditFinding[]): void {
  const route = window.location.pathname;
  if (findings.length === 0) {
    console.log(`%c[UI Audit] ${route}: No overflows detected`, 'color: #2ee59d; font-weight: bold;');
    return;
  }

  console.group(`%c[UI Audit] ${route}: ${findings.length} overflow(s)`, 'color: #ff5b6e; font-weight: bold;');
  findings.forEach((f, i) => {
    console.log(
      `  ${i + 1}. <${f.element.tagName.toLowerCase()}> (${f.selector}) — overflowX: ${f.overflowX}px, overflowY: ${f.overflowY}px`,
      f.element
    );
  });
  console.groupEnd();
}

export function initAuditMode(): (() => void) | undefined {
  const params = new URLSearchParams(window.location.search);
  if (params.get('audit') !== '1') return undefined;

  console.log(
    '%c[UI Audit] Audit mode activated',
    'color: #fbbf24; font-weight: bold; font-size: 14px;'
  );

  const panel = createPanel();

  // Initial scan after a brief delay for layout
  const initialTimeout = setTimeout(() => {
    const findings = runScan();
    updatePanel(panel, findings);
    logFindings(findings);
  }, 500);

  // ResizeObserver for ongoing monitoring
  const resizeObserver = new ResizeObserver(() => {
    const findings = runScan();
    updatePanel(panel, findings);
    logFindings(findings);
  });

  resizeObserver.observe(document.body);

  // MutationObserver to catch SPA route changes
  const mutationObserver = new MutationObserver(() => {
    const findings = runScan();
    updatePanel(panel, findings);
    logFindings(findings);
  });
  mutationObserver.observe(document.body, { childList: true, subtree: true });

  // Cleanup function
  return () => {
    clearTimeout(initialTimeout);
    resizeObserver.disconnect();
    mutationObserver.disconnect();
    clearMarks();
    panel.remove();
  };
}
