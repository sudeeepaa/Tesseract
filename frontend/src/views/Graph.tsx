import React, { useState, useEffect, useRef, useMemo, useCallback } from 'react';
import ForceGraph2D from 'react-force-graph-2d';
import { Loader2, Share2, Info, RefreshCw, Eye, EyeOff } from 'lucide-react';
import { apiClient, GraphSnapshot, GraphNode } from '../api/client';
import { forceCollide } from 'd3-force';

function getNodeColor(type: string, status?: string): string {
  if (type === 'meeting') return '#3b82f6';
  if (type === 'decision') {
    if (status === 'under_review') return '#f59e0b';
    if (status === 'superseded') return '#dc2626';
    return '#10b981';
  }
  if (type === 'action_item') return '#f97316';
  if (type === 'entity') return '#8b5cf6';
  if (type === 'topic') return '#14b8a6';
  return '#6b7280';
}

const BTN: React.CSSProperties = {
  padding: '0.5rem 0.75rem', fontSize: '0.8rem', display: 'flex',
  alignItems: 'center', gap: '0.35rem', backgroundColor: 'rgba(15,19,26,0.9)',
  border: '1px solid var(--border-glass)', color: 'var(--text-primary)',
  borderRadius: 'var(--radius-sm)', cursor: 'pointer', transition: 'background-color 0.2s',
};

export const GraphView: React.FC = () => {
  const [snapshot, setSnapshot] = useState<GraphSnapshot | null>(null);
  const [loading, setLoading] = useState(true);
  const [selectedNode, setSelectedNode] = useState<GraphNode | null>(null);
  const [showLegend, setShowLegend] = useState(true);

  // Hover is stored in a REF, not state. This means hover changes do NOT
  // trigger a re-render, so ForceGraph2D never sees a new graphData object
  // and never restarts the simulation.
  const hoveredNodeRef = useRef<any>(null);

  const graphRef = useRef<any>();
  const containerRef = useRef<HTMLDivElement>(null);
  const [dimensions, setDimensions] = useState({ width: 800, height: 600 });
  const hasZoomedRef = useRef(false);
  const forcesAppliedRef = useRef(false);

  useEffect(() => {
    (async () => {
      try { setSnapshot(await apiClient.getGraph()); }
      catch (e) { console.error('Graph fetch failed:', e); }
      finally { setLoading(false); }
    })();
  }, []);

  useEffect(() => {
    if (!containerRef.current) return;
    const ro = new ResizeObserver(entries => {
      for (const e of entries) {
        const { width, height } = e.contentRect;
        if (width > 0 && height > 0) setDimensions({ width, height });
      }
    });
    ro.observe(containerRef.current);
    return () => ro.disconnect();
  }, []);

  // Apply d3 forces ONCE after snapshot loads.
  // Never call d3ReheatSimulation here — let the graph warm up naturally.
  useEffect(() => {
    if (!snapshot || forcesAppliedRef.current) return;
    const id = setTimeout(() => {
      if (!graphRef.current) return;
      forcesAppliedRef.current = true;
      graphRef.current.d3Force('charge').strength(-500);
      graphRef.current.d3Force('link').distance(90);
      graphRef.current.d3Force(
        'collide',
        forceCollide((n: any) => (n.type === 'meeting' ? 22 : 16)).iterations(2)
      );
      hasZoomedRef.current = false;
    }, 50);
    return () => clearTimeout(id);
  }, [snapshot]);

  // CRITICAL: useMemo ensures graphData is the SAME object across renders
  // unless the snapshot actually changes. Without this, every state update
  // (even hoveredNode) creates a new object and restarts the simulation.
  const formattedData = useMemo(() => {
    if (!snapshot) return { nodes: [], links: [] };
    const nodes = snapshot.nodes.map(n => ({
      ...n,
      val: n.type === 'meeting' ? 6 : n.type === 'decision' ? 5 : 4,
      color: getNodeColor(n.type, n.properties?.status),
    }));
    const ids = new Set(nodes.map(n => n.id));
    const links = snapshot.edges
      .filter(e => ids.has(e.source) && ids.has(e.target))
      .map(e => ({ source: e.source, target: e.target, type: e.type, superseded: e.superseded }));
    return { nodes, links };
  }, [snapshot]);

  const handleNodeClick = useCallback((node: any) => {
    setSelectedNode(node as GraphNode);
    graphRef.current?.centerAt(node.x, node.y, 800);
    graphRef.current?.zoom(2.5, 800);
  }, []);

  // Hover handler writes to REF only — zero re-render
  const handleNodeHover = useCallback((node: any) => {
    hoveredNodeRef.current = node ?? null;
    document.body.style.cursor = node ? 'pointer' : 'default';
  }, []);

  const handleResetView = useCallback(() => graphRef.current?.zoomToFit(600, 50), []);

  const handleEngineStop = useCallback(() => {
    if (!hasZoomedRef.current && graphRef.current) {
      hasZoomedRef.current = true;
      graphRef.current.zoomToFit(600, 60);
    }
  }, []);

  // nodeCanvasObject only recreates when selectedNode changes (NOT on hover)
  const nodeCanvasObject = useCallback(
    (node: any, ctx: CanvasRenderingContext2D, gs: number) => {
      const isSel = selectedNode?.id === node.id;
      const isHov = hoveredNodeRef.current?.id === node.id;
      const label = gs >= 2.5 || isSel || isHov;

      ctx.beginPath();
      ctx.arc(node.x, node.y, 5, 0, 2 * Math.PI, false);
      ctx.fillStyle = node.color;
      ctx.fill();

      if (isSel || isHov) {
        ctx.strokeStyle = isSel ? '#fff' : 'rgba(255,255,255,0.55)';
        ctx.lineWidth = 2 / gs;
        ctx.stroke();
      }

      if (label) {
        const raw = node.label ? String(node.label) : '';
        const txt = raw.length > 22 ? raw.slice(0, 19) + '…' : raw;
        const fs = 11 / gs;
        ctx.font = `${fs}px sans-serif`;
        ctx.textAlign = 'center';
        ctx.textBaseline = 'middle';
        const tw = ctx.measureText(txt).width;
        const px = 4 / gs, py = 2 / gs;
        const bw = tw + px * 2, bh = fs + py * 2;
        const bx = node.x - bw / 2, by = node.y + 10 / gs - bh / 2;
        ctx.fillStyle = 'rgba(10,15,28,0.88)';
        ctx.strokeStyle = isSel ? '#3b82f6' : isHov ? 'rgba(255,255,255,0.35)' : 'rgba(255,255,255,0.12)';
        ctx.lineWidth = 1 / gs;
        ctx.beginPath();
        if (ctx.roundRect) ctx.roundRect(bx, by, bw, bh, 3 / gs);
        else ctx.rect(bx, by, bw, bh);
        ctx.fill(); ctx.stroke();
        ctx.fillStyle = isSel || isHov ? '#fff' : 'rgba(255,255,255,0.88)';
        ctx.fillText(txt, node.x, node.y + 10 / gs);
      }
    },
    [selectedNode]
  );

  const linkWidth   = useCallback((l: any) => (l.superseded ? 1.5 : 2), []);
  const linkDash    = useCallback((l: any) => l.type === 'SUPERSEDES' ? [4,4] : l.type === 'CONTRADICTS' ? [2,2] : undefined, []);
  const linkColor   = useCallback((l: any) => l.type === 'SUPERSEDES' ? '#f59e0b' : l.type === 'CONTRADICTS' ? '#ef4444' : 'rgba(255,255,255,0.15)', []);
  const linkArrow   = useCallback((l: any) => (l.type === 'SUPERSEDES' ? 6 : 0), []);

  const getStatus = (n: GraphNode) => n.properties?.status || '';
  const getSrc    = (n: GraphNode) => n.properties?.meeting_id || n.properties?.source_meeting_id || '';
  const getOwner  = (n: GraphNode) => n.properties?.owner || n.properties?.assignee || '';

  if (loading) return (
    <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', height: '50vh', gap: '1rem' }}>
      <style>{`@keyframes spin{100%{transform:rotate(360deg)}}`}</style>
      <Loader2 size={40} color="var(--primary)" style={{ animation: 'spin 2s linear infinite' }} />
      <span style={{ color: 'var(--text-secondary)' }}>Loading graph model…</span>
    </div>
  );

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem', height: 'calc(100vh - 120px)' }}>
      <div>
        <h2 style={{ fontSize: '1.75rem', marginBottom: '0.25rem', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
          <Share2 color="var(--secondary)" size={28} /> Knowledge Graph Visualization
        </h2>
        <p style={{ color: 'var(--text-secondary)', fontSize: '0.95rem' }}>
          Explore meeting lineage, active decisions, and relationships dynamically. Click any node to view metadata.
        </p>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: selectedNode ? '3.5fr 1.5fr' : '1fr', gap: '1.5rem', flex: 1, overflow: 'hidden' }}>
        <div ref={containerRef} className="glass-panel"
          style={{ position: 'relative', overflow: 'hidden', borderRadius: 'var(--radius-lg)', backgroundColor: 'rgba(5,7,10,0.95)', width: '100%', height: '100%' }}>

          {showLegend && (
            <div style={{ position: 'absolute', top: '1rem', left: '1rem', zIndex: 10, display: 'flex', flexDirection: 'column', gap: '0.45rem', backgroundColor: 'rgba(15,19,26,0.9)', padding: '0.75rem', borderRadius: 'var(--radius-sm)', border: '1px solid var(--border-glass)', fontSize: '0.8rem', pointerEvents: 'none' }}>
              {(['#3b82f6,Meeting','#10b981,Active Decision','#f59e0b,Decision Under Review','#dc2626,Superseded Decision','#f97316,Action Item','#8b5cf6,Entity','#14b8a6,Topic'] as string[]).map(row => {
                const [c, l] = row.split(',');
                return (
                  <div key={l} style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                    <span style={{ width: 10, height: 10, borderRadius: '50%', backgroundColor: c, display: 'inline-block', flexShrink: 0 }} />
                    <span>{l}</span>
                  </div>
                );
              })}
            </div>
          )}

          <div style={{ position: 'absolute', top: '1rem', right: '1rem', zIndex: 10, display: 'flex', gap: '0.5rem' }}>
            <button style={BTN} onClick={() => setShowLegend(p => !p)}
              onMouseEnter={e => (e.currentTarget.style.backgroundColor = 'rgba(30,41,59,0.9)')}
              onMouseLeave={e => (e.currentTarget.style.backgroundColor = 'rgba(15,19,26,0.9)')}>
              {showLegend ? <EyeOff size={14} /> : <Eye size={14} />}
              {showLegend ? 'Hide Legend' : 'Show Legend'}
            </button>
            <button style={BTN} onClick={handleResetView}
              onMouseEnter={e => (e.currentTarget.style.backgroundColor = 'rgba(30,41,59,0.9)')}
              onMouseLeave={e => (e.currentTarget.style.backgroundColor = 'rgba(15,19,26,0.9)')}>
              <RefreshCw size={14} /> Reset View
            </button>
          </div>

          <ForceGraph2D
            ref={graphRef}
            width={dimensions.width}
            height={dimensions.height}
            graphData={formattedData}
            nodeLabel=""
            nodeRelSize={6}
            linkWidth={linkWidth}
            linkLineDash={linkDash}
            linkColor={linkColor}
            linkDirectionalArrowLength={linkArrow}
            linkDirectionalArrowRelPos={0.5}
            onNodeClick={handleNodeClick}
            onNodeHover={handleNodeHover}
            cooldownTicks={200}
            onEngineStop={handleEngineStop}
            nodeCanvasObject={nodeCanvasObject}
            nodePointerAreaPaint={(node: any, color, ctx) => {
              ctx.fillStyle = color;
              ctx.beginPath();
              ctx.arc(node.x, node.y, 8, 0, 2 * Math.PI, false);
              ctx.fill();
            }}
          />
        </div>

        {selectedNode && (
          <div className="glass-panel" style={{ padding: '1.5rem', display: 'flex', flexDirection: 'column', gap: '1.25rem', overflowY: 'auto' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <h3 style={{ fontSize: '1.2rem', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                <Info size={18} /> Node Properties
              </h3>
              <button onClick={() => setSelectedNode(null)} style={{ background: 'none', border: 'none', color: 'var(--text-secondary)', cursor: 'pointer', fontSize: '1.2rem', lineHeight: 1 }}>
                &times;
              </button>
            </div>

            <div style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem', backgroundColor: 'rgba(0,0,0,0.2)', padding: '1rem', borderRadius: 'var(--radius-sm)' }}>
              {([
                ['TYPE', selectedNode.type.replace(/_/g, ' ')],
                ['ID', selectedNode.id],
                ['LABEL', selectedNode.label],
                ...(getStatus(selectedNode) ? [['STATUS', getStatus(selectedNode).replace(/_/g, ' ')]] : []),
                ...(getSrc(selectedNode) ? [['SOURCE MEETING', getSrc(selectedNode)]] : []),
                ...(getOwner(selectedNode) ? [['OWNER / ASSIGNEE', getOwner(selectedNode)]] : []),
              ] as [string, string][]).map(([k, v]) => (
                <div key={k}>
                  <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)', fontWeight: 600, textTransform: 'uppercase' }}>{k}</span>
                  <p style={{ fontSize: '0.9rem', color: 'var(--text-primary)', fontFamily: k === 'ID' || k === 'SOURCE MEETING' ? 'var(--font-mono)' : undefined, textTransform: k === 'TYPE' || k === 'STATUS' ? 'capitalize' : undefined, lineHeight: 1.4 }}>{v}</p>
                </div>
              ))}
            </div>

            <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
              <h4 style={{ fontSize: '0.9rem', color: 'var(--text-secondary)', borderBottom: '1px solid var(--border-glass)', paddingBottom: '0.25rem' }}>Additional Attributes</h4>
              {(() => {
                const core = ['id','label','type','status','owner','assignee','meeting_id','source_meeting_id'];
                const rest = Object.entries(selectedNode.properties).filter(([k]) => !core.includes(k));
                if (!rest.length) return <p style={{ fontSize: '0.8rem', color: 'var(--text-muted)', fontStyle: 'italic' }}>No additional attributes.</p>;
                return rest.map(([k, v]) => (
                  <div key={k} style={{ display: 'flex', flexDirection: 'column', gap: '0.15rem' }}>
                    <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)', fontWeight: 600, textTransform: 'uppercase' }}>{k.replace(/_/g, ' ')}</span>
                    <span style={{ fontSize: '0.85rem', color: 'var(--text-primary)', wordBreak: 'break-word', fontFamily: k.toLowerCase().includes('id') ? 'var(--font-mono)' : undefined }}>
                      {typeof v === 'object' ? JSON.stringify(v) : String(v)}
                    </span>
                  </div>
                ));
              })()}
            </div>
          </div>
        )}
      </div>
    </div>
  );
};
