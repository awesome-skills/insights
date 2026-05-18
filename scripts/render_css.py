"""Inline CSS for the rendered HTML report.

Kept in its own module so `render.py` stays focused on Python rendering logic.
The CSS is intentionally a single string (no preprocessor, no minifier) — the
report is a single-file HTML that anyone can save / share / view offline.
"""

CSS = """
* { box-sizing: border-box; margin: 0; padding: 0; }
body { font-family: -apple-system, BlinkMacSystemFont, 'Inter', 'PingFang SC', sans-serif;
       background: #f8fafc; color: #334155; line-height: 1.65; padding: 48px 24px; }
.container { max-width: 860px; margin: 0 auto; }
h1 { font-size: 30px; font-weight: 700; color: #0f172a; margin-bottom: 8px; }
h2 { font-size: 20px; font-weight: 600; color: #0f172a; margin-top: 44px; margin-bottom: 14px; }
.subtitle { color: #64748b; font-size: 14px; margin-bottom: 24px; }
.share-warning { background: #fff7ed; border: 1px solid #fdba74; border-radius: 8px;
                 color: #9a3412; font-size: 12.5px; line-height: 1.55;
                 padding: 10px 12px; margin: 0 0 22px 0; }
.share-warning strong { color: #7c2d12; }
.nav-toc { display: flex; flex-wrap: wrap; gap: 8px; margin: 20px 0 28px 0; padding: 14px;
           background: white; border-radius: 8px; border: 1px solid #e2e8f0; }
.nav-toc a { font-size: 12px; color: #64748b; text-decoration: none; padding: 6px 10px;
             border-radius: 6px; background: #f1f5f9; transition: all .15s; }
.nav-toc a:hover { background: #e2e8f0; color: #334155; }
.stats-row { display: flex; gap: 20px; margin-bottom: 32px; padding: 18px 0;
             border-top: 1px solid #e2e8f0; border-bottom: 1px solid #e2e8f0; flex-wrap: wrap; }
.stat { text-align: center; min-width: 90px; }
.stat-value { font-size: 22px; font-weight: 700; color: #0f172a; }
.stat-label { font-size: 11px; color: #64748b; text-transform: uppercase; letter-spacing: 0.5px; }
.exec-summary { background: #fffdf7; border: 1px solid #d6b16a; border-radius: 14px;
                padding: 22px; margin: 10px 0 28px 0; box-shadow: 0 10px 30px rgba(120, 83, 22, .06); }
.exec-kicker { font-size: 11px; color: #8a5a12; font-weight: 700; letter-spacing: .12em;
               text-transform: uppercase; margin-bottom: 8px; }
.exec-headline { font-size: 23px; line-height: 1.25; color: #1f2937; font-weight: 750; margin-bottom: 8px; }
.exec-one { font-size: 14px; color: #6b4f1d; margin-bottom: 16px; }
.change-card { border-top: 1px solid #ead9b3; padding-top: 14px; margin-top: 14px; }
.change-title { font-size: 15px; font-weight: 700; color: #0f172a; margin-bottom: 6px; }
.change-meta { font-size: 13px; color: #475569; line-height: 1.55; margin-bottom: 5px; }
.change-action { font-size: 13px; color: #075985; background: #f0f9ff; border: 1px solid #bae6fd;
                 border-radius: 7px; padding: 8px 10px; margin-top: 8px; }
.priority-list { background: white; border: 1px solid #dbe4ef; border-radius: 12px; padding: 16px; margin-bottom: 18px; }
.priority-intro { font-size: 13.5px; color: #475569; margin-bottom: 12px; }
.priority-item { display: grid; grid-template-columns: 42px 1fr; gap: 12px; padding: 12px 0;
                 border-top: 1px solid #eef2f7; }
.priority-item:first-of-type { border-top: none; padding-top: 0; }
.priority-rank { width: 34px; height: 34px; border-radius: 50%; background: #0f172a; color: white;
                 display: flex; align-items: center; justify-content: center; font-weight: 700; font-size: 14px; }
.priority-name { font-weight: 700; color: #0f172a; font-size: 15px; margin-bottom: 4px; }
.priority-tags { font-size: 11px; color: #64748b; margin-bottom: 4px; }
.priority-detail { font-size: 13px; color: #475569; line-height: 1.55; }
.score-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(145px, 1fr)); gap: 10px; margin: 12px 0 18px; }
.score-card { background: #fff; border: 1px solid #e2e8f0; border-radius: 10px; padding: 12px; }
.score-value { font-size: 24px; font-weight: 750; color: #0f172a; }
.score-dim { font-size: 13px; font-weight: 700; color: #334155; margin-bottom: 4px; }
.score-note { font-size: 12px; color: #64748b; line-height: 1.45; }
.at-a-glance { background: linear-gradient(135deg, #fef3c7 0%, #fde68a 100%);
               border: 1px solid #f59e0b; border-radius: 12px; padding: 18px 22px; margin-bottom: 28px; }
.glance-title { font-size: 16px; font-weight: 700; color: #92400e; margin-bottom: 12px; }
.glance-section { font-size: 14px; color: #78350f; line-height: 1.65; margin-bottom: 10px; }
.glance-section strong { color: #92400e; }
.project-area { background: white; border: 1px solid #e2e8f0; border-radius: 8px;
                padding: 14px 16px; margin-bottom: 10px; }
.area-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 6px; }
.area-name { font-weight: 600; font-size: 15px; color: #0f172a; }
.area-count { font-size: 12px; color: #64748b; background: #f1f5f9; padding: 2px 8px; border-radius: 4px; }
.area-desc { font-size: 13.5px; color: #475569; line-height: 1.55; }
.narrative { background: white; border: 1px solid #e2e8f0; border-radius: 8px;
             padding: 18px; margin-bottom: 16px; }
.narrative p { margin-bottom: 10px; font-size: 14px; color: #475569; line-height: 1.7; }
.key-insight { background: #f0fdf4; border: 1px solid #bbf7d0; border-radius: 8px;
               padding: 10px 14px; margin-top: 10px; font-size: 13.5px; color: #166534; }
.section-intro { font-size: 13.5px; color: #64748b; margin-bottom: 14px; }
.big-win { background: #f0fdf4; border: 1px solid #bbf7d0; border-radius: 8px;
           padding: 14px; margin-bottom: 10px; }
.big-win-title { font-weight: 600; font-size: 15px; color: #166534; margin-bottom: 6px; }
.big-win-desc { font-size: 13.5px; color: #15803d; line-height: 1.55; }
.friction-category { background: #fef2f2; border: 1px solid #fca5a5; border-radius: 8px;
                     padding: 14px; margin-bottom: 12px; }
.friction-title { font-weight: 600; font-size: 15px; color: #991b1b; margin-bottom: 6px; }
.friction-desc { font-size: 13.5px; color: #7f1d1d; margin-bottom: 8px; }
.friction-examples { margin: 0 0 0 18px; font-size: 13px; color: #334155; }
.friction-examples li { margin-bottom: 4px; }
.claude-md-section { background: #eff6ff; border: 1px solid #bfdbfe; border-radius: 8px;
                     padding: 14px; margin-bottom: 16px; }
.claude-md-section h3 { font-size: 14px; font-weight: 600; color: #1e40af; margin: 0 0 10px 0; }
.claude-md-item { padding: 10px 0; border-bottom: 1px solid #dbeafe; }
.claude-md-item:last-child { border-bottom: none; }
.cmd-code { background: white; padding: 8px 12px; border-radius: 4px; font-size: 12.5px;
            color: #1e40af; border: 1px solid #bfdbfe; font-family: ui-monospace, monospace;
            display: block; white-space: pre-wrap; word-break: break-word; }
.cmd-why { font-size: 12px; color: #64748b; padding-top: 6px; }
.feature-card, .pattern-card, .horizon-card { border-radius: 8px; padding: 14px; margin-bottom: 10px; }
.feature-card { background: #f0fdf4; border: 1px solid #86efac; }
.pattern-card { background: #f0f9ff; border: 1px solid #7dd3fc; }
.horizon-card { background: linear-gradient(135deg, #faf5ff 0%, #f5f3ff 100%);
                border: 1px solid #c4b5fd; }
.feature-title, .pattern-title, .horizon-title { font-weight: 600; font-size: 15px;
                                                 color: #0f172a; margin-bottom: 6px; }
.horizon-title { color: #5b21b6; }
.feature-oneliner, .pattern-summary { font-size: 13.5px; color: #475569; margin-bottom: 6px; }
.feature-why, .pattern-detail, .horizon-possible { font-size: 13px; color: #334155; line-height: 1.55; }
.copyable-prompt, .example-code, .feature-code { background: #f8fafc; padding: 10px 12px;
                                                 border-radius: 4px; font-family: ui-monospace, monospace;
                                                 font-size: 12px; color: #334155; border: 1px solid #e2e8f0;
                                                 white-space: pre-wrap; line-height: 1.5; margin-top: 8px;
                                                 overflow-x: auto; }
.prompt-label { font-size: 11px; font-weight: 600; text-transform: uppercase;
                color: #64748b; margin-top: 8px; margin-bottom: 4px; }
.chart-card { background: white; border: 1px solid #e2e8f0; border-radius: 8px; padding: 14px; margin-bottom: 14px; }
.charts-row { display: grid; grid-template-columns: 1fr 1fr; gap: 16px; margin: 16px 0; }
.chart-title { font-size: 12px; font-weight: 600; color: #64748b;
               text-transform: uppercase; margin-bottom: 10px; letter-spacing: .5px; }
.bar-row { display: flex; align-items: center; margin-bottom: 5px; }
.bar-label { width: 110px; font-size: 11.5px; color: #475569; flex-shrink: 0;
             overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.bar-track { flex: 1; height: 6px; background: #f1f5f9; border-radius: 3px; margin: 0 8px; }
.bar-fill { height: 100%; border-radius: 3px; background: #6366f1; }
.bar-fill.c1 { background: #6366f1; } /* indigo */
.bar-fill.c2 { background: #10b981; } /* emerald */
.bar-fill.c3 { background: #f59e0b; } /* amber */
.bar-fill.c4 { background: #8b5cf6; } /* violet */
.bar-fill.c5 { background: #0891b2; } /* cyan */
.bar-fill.c6 { background: #f43f5e; } /* rose */
.bar-fill.c7 { background: #65a30d; } /* lime */
.bar-fill.c8 { background: #0284c7; } /* sky */
.bar-value { width: 36px; font-size: 11px; font-weight: 500; color: #64748b; text-align: right; }
.fun-ending { background: linear-gradient(135deg, #fdf2f8 0%, #fce7f3 100%);
              border: 1px solid #f9a8d4; border-radius: 12px; padding: 16px 20px; margin-top: 28px; }
.fun-headline { font-weight: 700; color: #9d174d; font-size: 15px; margin-bottom: 6px; }
.fun-detail { font-size: 13px; color: #831843; line-height: 1.55; }
@media (max-width: 720px) { .charts-row { grid-template-columns: 1fr; } body { padding: 24px 16px; } }
@media print {
  body { background: white; padding: 0; }
  .nav-toc { display: none; }
  /* Preserve coloured backgrounds so that friction / win / exec-summary cards
     remain semantically distinguishable in printed / saved-as-PDF reports.
     Without this the browser strips backgrounds and the report flattens to a
     monochrome text wall. */
  * { -webkit-print-color-adjust: exact; print-color-adjust: exact; }
  .at-a-glance, .project-area, .narrative, .big-win, .friction-category,
  .feature-card, .pattern-card, .horizon-card, .claude-md-section, .chart-card,
  .exec-summary, .fun-ending { page-break-inside: avoid; }
}
"""
