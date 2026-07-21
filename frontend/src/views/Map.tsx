import React, { useState, useEffect, useRef, useMemo, useCallback } from 'react';
import ForceGraph2D from 'react-force-graph-2d';
import { Loader2, RefreshCw, X, Eye, EyeOff } from 'lucide-react';
import { forceCollide } from 'd3-force';
import { apiClient, GraphSnapshot, GraphNode } from '../api/client';
import { EmptyState } from '../components/ui';

const COLORS: Record<string, string> = {
  meeting: '#4b83e0', decision: '#2f9268', under_review: '#c98a2a',
  superseded: '#c9564b', action_item: '#d98b3f', entity: '#8b6fd6', topic: '#3aa6a0',
};
const LEGEND: [string, string][] = [
  [COLORS.meeting, 'Meeting'], [COLORS.decision, 'Decision (active)'],
  [COLORS.under_review, 'Under review'], [COLORS.superseded, 'Replaced'],
  [COLORS.action_item, 'Task'], [COLORS.entity, 'Person / thing'], [COLORS.topic, 'Topic'],
];

function nodeColor(type: string, status?: string): string {
  if (type === 'decision') return COLORS[status || ''] || COLORS.decision;
  return COLORS[type] || '#8a8a84';
}

export const MapView: React.FC = () => {
  const [snapshot, setSnapshot] = useState<GraphSnapshot | null>(null);
  const [loading, setLoading] = useState(true);
  const [selected, setSelected] = useState<GraphNode | null>(null);
  const [showLegend, setShowLegend] = useState(true);

  const hoveredRef = useRef<any>(null);
  const graphRef = useRef<any>();
  const containerRef = useRef<HTMLDivElement>(null);
  const [dim, setDim] = useState({ width: 800, height: 560 });
  const zoomedRef = useRef(false);
  const forcedRef = useRef(false);

  useEffect(() => {
    (async () => {
      try { setSnapshot(await apiClient.getGraph()); }
      catch { /* */ } finally { setLoading(false); }
    })();
  }, []);

  useEffect(() => {
    if (!containerRef.current) return;
    const ro = new ResizeObserver((entries) => {
      for (const e of entries) {
        const { width, height } = e.contentRect;
        if (width > 0 && height > 0) setDim({ width, height });
      }
    });
    ro.observe(containerRef.current);
    return () => ro.disconnect();
  }, [loading]);

  useEffect(() => {
    if (!snapshot || forcedRef.current) return;
    const id = setTimeout(() => {
      if (!graphRef.current) return;
      forcedRef.current = true;
      graphRef.current.d3Force('charge').strength(-480);
      graphRef.current.d3Force('link').distance(88);
      graphRef.current.d3Force('collide', forceCollide((n: any) => (n.type === 'meeting' ? 22 : 16)).iterations(2));
      zoomedRef.current = false;
    }, 50);
    return () => clearTimeout(id);
  }, [snapshot]);

  const data = useMemo(() => {
    if (!snapshot) return { nodes: [], links: [] };
    const nodes = snapshot.nodes.map((n) => ({
      ...n, val: n.type === 'meeting' ? 6 : n.type === 'decision' ? 5 : 4,
      color: nodeColor(n.type, n.properties?.status),
    }));
    const ids = new Set(nodes.map((n) => n.id));
    const links = snapshot.edges.filter((e) => ids.has(e.source) && ids.has(e.target))
      .map((e) => ({ source: e.source, target: e.target, type: e.type, superseded: e.superseded }));
    return { nodes, links };
  }, [snapshot]);

  const onNodeClick = useCallback((node: any) => {
    setSelected(node as GraphNode);
    graphRef.current?.centerAt(node.x, node.y, 700);
    graphRef.current?.zoom(2.4, 700);
  }, []);
  const onHover = useCallback((node: any) => {
    hoveredRef.current = node ?? null;
    document.body.style.cursor = node ? 'pointer' : 'default';
  }, []);
  const onEngineStop = useCallback(() => {
    if (!zoomedRef.current && graphRef.current) { zoomedRef.current = true; graphRef.current.zoomToFit(600, 60); }
  }, []);

  const nodeCanvas = useCallback((node: any, ctx: CanvasRenderingContext2D, gs: number) => {
    const isSel = selected?.id === node.id;
    const isHov = hoveredRef.current?.id === node.id;
    ctx.beginPath(); ctx.arc(node.x, node.y, 5, 0, 2 * Math.PI, false);
    ctx.fillStyle = node.color; ctx.fill();
    if (isSel || isHov) { ctx.strokeStyle = isSel ? '#fff' : 'rgba(255,255,255,0.55)'; ctx.lineWidth = 2 / gs; ctx.stroke(); }
    if (gs >= 2.4 || isSel || isHov) {
      const raw = node.label ? String(node.label) : '';
      const txt = raw.length > 22 ? raw.slice(0, 19) + '…' : raw;
      const fs = 11 / gs; ctx.font = `${fs}px sans-serif`; ctx.textAlign = 'center'; ctx.textBaseline = 'middle';
      const tw = ctx.measureText(txt).width, px = 4 / gs, py = 2 / gs, bw = tw + px * 2, bh = fs + py * 2;
      const bx = node.x - bw / 2, by = node.y + 10 / gs - bh / 2;
      ctx.fillStyle = 'rgba(20,22,28,0.9)'; ctx.strokeStyle = 'rgba(255,255,255,0.14)'; ctx.lineWidth = 1 / gs;
      ctx.beginPath();
      if (ctx.roundRect) ctx.roundRect(bx, by, bw, bh, 3 / gs); else ctx.rect(bx, by, bw, bh);
      ctx.fill(); ctx.stroke();
      ctx.fillStyle = '#fff'; ctx.fillText(txt, node.x, node.y + 10 / gs);
    }
  }, [selected]);

  const linkColor = useCallback((l: any) => l.type === 'SUPERSEDES' ? COLORS.under_review : l.type === 'CONTRADICTS' ? COLORS.superseded : 'rgba(150,150,150,0.35)', []);
  const linkDash = useCallback((l: any) => l.type === 'SUPERSEDES' ? [4, 4] : l.type === 'CONTRADICTS' ? [2, 2] : undefined, []);

  return (
    <div style={{ padding: '24px 26px 26px', display: 'flex', flexDirection: 'column', gap: 14, height: 'calc(100vh - 49px)' }}>
      <header>
        <div className="page-eyebrow">Relationships</div>
        <h1 className="page-title" style={{ fontSize: 22 }}>How everything connects</h1>
        <p className="page-lead" style={{ fontSize: 13.5 }}>Meetings, decisions, people, and tasks — and how newer decisions replace older ones. Click any dot for details.</p>
      </header>

      {loading ? (
        <div className="card" style={{ flex: 1, display: 'grid', placeItems: 'center' }}>
          <div className="col" style={{ alignItems: 'center', gap: 10 }}>
            <Loader2 size={30} className="spin" color="var(--accent)" />
            <span className="muted">Loading the map…</span>
          </div>
        </div>
      ) : !snapshot || snapshot.nodes.length === 0 ? (
        <EmptyState title="Nothing to map yet" children={<>Add a meeting and the relationships will appear here.</>} />
      ) : (
        <div style={{ display: 'grid', gridTemplateColumns: selected ? '3fr 1.4fr' : '1fr', gap: 16, flex: 1, overflow: 'hidden' }}>
          <div ref={containerRef} className="card" style={{ position: 'relative', overflow: 'hidden', background: '#131417' }}>
            {showLegend && (
              <div style={{ position: 'absolute', top: 12, left: 12, zIndex: 10, display: 'flex', flexDirection: 'column', gap: 6, background: 'rgba(20,22,28,0.86)', padding: 11, borderRadius: 8, fontSize: 12, color: '#e9e9e7', pointerEvents: 'none' }}>
                {LEGEND.map(([c, l]) => (
                  <div key={l} className="row" style={{ gap: 8 }}>
                    <span style={{ width: 9, height: 9, borderRadius: '50%', background: c, flex: 'none' }} />{l}
                  </div>
                ))}
              </div>
            )}
            <div style={{ position: 'absolute', top: 12, right: 12, zIndex: 10, display: 'flex', gap: 8 }}>
              <button className="btn btn-sm" style={{ background: 'rgba(20,22,28,0.86)', color: '#e9e9e7', border: '1px solid rgba(255,255,255,0.12)' }} onClick={() => setShowLegend((s) => !s)}>
                {showLegend ? <EyeOff size={14} /> : <Eye size={14} />}{showLegend ? 'Hide key' : 'Show key'}
              </button>
              <button className="btn btn-sm" style={{ background: 'rgba(20,22,28,0.86)', color: '#e9e9e7', border: '1px solid rgba(255,255,255,0.12)' }} onClick={() => graphRef.current?.zoomToFit(600, 50)}>
                <RefreshCw size={14} /> Fit
              </button>
            </div>
            <ForceGraph2D ref={graphRef} width={dim.width} height={dim.height} graphData={data}
              nodeRelSize={6} nodeCanvasObject={nodeCanvas}
              linkColor={linkColor} linkLineDash={linkDash} linkWidth={(l: any) => (l.superseded ? 1.5 : 2)}
              linkDirectionalArrowLength={(l: any) => (l.type === 'SUPERSEDES' ? 6 : 0)} linkDirectionalArrowRelPos={0.5}
              onNodeClick={onNodeClick} onNodeHover={onHover} cooldownTicks={200} onEngineStop={onEngineStop}
              nodePointerAreaPaint={(node: any, color: string, ctx: CanvasRenderingContext2D) => {
                ctx.fillStyle = color; ctx.beginPath(); ctx.arc(node.x, node.y, 8, 0, 2 * Math.PI, false); ctx.fill();
              }} />
          </div>

          {selected && (
            <div className="card card-pad stack-sm" style={{ overflowY: 'auto' }}>
              <div className="between">
                <span className="pill pill-gray">{selected.type.replace(/_/g, ' ')}</span>
                <button className="icon-btn" onClick={() => setSelected(null)}><X size={16} /></button>
              </div>
              <div style={{ fontWeight: 600, fontSize: 15 }}>{selected.label}</div>
              {Object.entries(selected.properties || {})
                .filter(([k, v]) => v && !['id', 'label', 'type'].includes(k))
                .map(([k, v]) => (
                  <div key={k} className="col" style={{ gap: 1 }}>
                    <span className="muted" style={{ fontSize: 11.5, textTransform: 'capitalize' }}>{k.replace(/_/g, ' ')}</span>
                    <span style={{ fontSize: 13.5 }}>{typeof v === 'object' ? JSON.stringify(v) : String(v).replace(/_/g, ' ')}</span>
                  </div>
                ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
};
