import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import ForceGraph2D from 'react-force-graph-2d';
import businessApi from '../utils/api';

const DEFAULT_HOPS = 2;
const DEFAULT_DIRECTION = 'both';

function useDebouncedValue(value, delayMs = 250) {
  const [debounced, setDebounced] = useState(value);
  useEffect(() => {
    const timer = window.setTimeout(() => setDebounced(value), delayMs);
    return () => window.clearTimeout(timer);
  }, [value, delayMs]);
  return debounced;
}

export default function VBMappSubgraphExplorer({
  initialCenterUri = '',
  className = '',
  style,
}) {
  const graphRef = useRef(null);
  const [centerUri, setCenterUri] = useState(initialCenterUri);
  const [hops, setHops] = useState(DEFAULT_HOPS);
  const [direction, setDirection] = useState(DEFAULT_DIRECTION);
  const [searchInput, setSearchInput] = useState('');
  const [nodeOptions, setNodeOptions] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [graphData, setGraphData] = useState({ nodes: [], links: [] });
  const debouncedSearch = useDebouncedValue(searchInput, 300);

  const loadSubgraph = useCallback(async (focusUri, maxHops, dir) => {
    if (!focusUri) return;
    setLoading(true);
    setError('');
    try {
      const response = await businessApi.get('/api/graph/subgraph', {
        params: {
          center_uri: focusUri,
          max_hops: maxHops,
          direction: dir,
        },
      });
      setGraphData({
        nodes: response.data?.nodes || [],
        links: response.data?.links || [],
      });
    } catch (err) {
      const message =
        err?.response?.data?.detail || err?.message || 'Failed to load subgraph';
      setError(String(message));
      setGraphData({ nodes: [], links: [] });
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    if (!centerUri) return;
    loadSubgraph(centerUri, hops, direction);
  }, [centerUri, hops, direction, loadSubgraph]);

  useEffect(() => {
    if (!debouncedSearch) {
      setNodeOptions([]);
      return;
    }
    let cancelled = false;
    const runSearch = async () => {
      try {
        const response = await businessApi.get('/api/graph/nodes', {
          params: { q: debouncedSearch, limit: 20 },
        });
        if (!cancelled) {
          setNodeOptions(response.data?.items || []);
        }
      } catch (_err) {
        if (!cancelled) {
          setNodeOptions([]);
        }
      }
    };
    runSearch();
    return () => {
      cancelled = true;
    };
  }, [debouncedSearch]);

  useEffect(() => {
    const fg = graphRef.current;
    if (!fg || graphData.nodes.length === 0) return;
    fg.d3ReheatSimulation();
    window.requestAnimationFrame(() => {
      fg.zoomToFit(600, 40);
    });
  }, [graphData]);

  const handleNodeClick = useCallback((node) => {
    const next = node?.uri || node?.id;
    if (!next || next === centerUri) return;
    setCenterUri(next);
    setSearchInput(node.label || next);
  }, [centerUri]);

  const selectedOption = useMemo(
    () => nodeOptions.find((item) => item.uri === centerUri),
    [nodeOptions, centerUri]
  );

  return (
    <div className={`flex h-[720px] w-full gap-4 ${className}`} style={style}>
      <aside className="w-80 shrink-0 rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
        <h3 className="mb-3 text-base font-semibold text-slate-800">VB-MAPP Subgraph Explorer</h3>

        <label className="mb-1 block text-sm font-medium text-slate-700">Focal Node</label>
        <input
          list="vbmapp-node-suggestions"
          value={searchInput}
          onChange={(e) => setSearchInput(e.target.value)}
          placeholder="Search URI or label..."
          className="mb-2 w-full rounded-md border border-slate-300 px-3 py-2 text-sm outline-none ring-blue-500 focus:ring-2"
        />
        <datalist id="vbmapp-node-suggestions">
          {nodeOptions.map((item) => (
            <option key={item.uri} value={item.uri}>
              {item.label}
            </option>
          ))}
        </datalist>

        <button
          type="button"
          onClick={() => setCenterUri(searchInput.trim())}
          disabled={!searchInput.trim() || loading}
          className="mb-4 w-full rounded-md bg-blue-600 px-3 py-2 text-sm font-medium text-white disabled:cursor-not-allowed disabled:bg-slate-400"
        >
          Explore Node
        </button>

        <div className="mb-4">
          <label className="mb-1 block text-sm font-medium text-slate-700">
            Hops: <span className="font-semibold">{hops}</span>
          </label>
          <input
            type="range"
            min={1}
            max={4}
            value={hops}
            onChange={(e) => setHops(Number(e.target.value))}
            className="w-full"
          />
        </div>

        <div className="mb-4">
          <label className="mb-1 block text-sm font-medium text-slate-700">Direction</label>
          <select
            value={direction}
            onChange={(e) => setDirection(e.target.value)}
            className="w-full rounded-md border border-slate-300 px-3 py-2 text-sm"
          >
            <option value="both">both</option>
            <option value="forward">forward</option>
            <option value="backward">backward</option>
          </select>
        </div>

        <div className="rounded-md bg-slate-50 p-3 text-xs text-slate-600">
          <div className="mb-1 font-semibold text-slate-700">Current Focus</div>
          <div className="break-all">{selectedOption?.label || centerUri || 'Not selected'}</div>
        </div>

        {error ? <p className="mt-3 text-sm text-red-600">{error}</p> : null}
      </aside>

      <section className="relative min-w-0 flex-1 rounded-xl border border-slate-200 bg-white">
        {loading ? (
          <div className="absolute inset-0 z-10 flex items-center justify-center bg-white/70 text-sm text-slate-700">
            Loading subgraph...
          </div>
        ) : null}
        <ForceGraph2D
          ref={graphRef}
          graphData={graphData}
          width={900}
          height={720}
          nodeRelSize={6}
          nodeLabel={(node) => `${node.label}\n${node.uri}`}
          nodeCanvasObject={(node, ctx, globalScale) => {
            const label = node.label || node.id;
            const isCenter = node.is_center || node.uri === centerUri;
            const fontSize = isCenter ? 15 / globalScale : 11 / globalScale;
            ctx.font = `${isCenter ? 700 : 500} ${fontSize}px Sans-Serif`;
            const textWidth = ctx.measureText(label).width;
            const bckgDimensions = [textWidth + 8, fontSize + 6];

            ctx.fillStyle = isCenter ? 'rgba(37, 99, 235, 0.95)' : 'rgba(15, 23, 42, 0.8)';
            ctx.beginPath();
            ctx.arc(node.x, node.y, isCenter ? 8 : 5, 0, 2 * Math.PI, false);
            ctx.fill();

            ctx.fillStyle = isCenter ? 'rgba(219, 234, 254, 0.95)' : 'rgba(241, 245, 249, 0.95)';
            ctx.fillRect(
              node.x + 6,
              node.y - bckgDimensions[1] / 2,
              bckgDimensions[0],
              bckgDimensions[1]
            );

            ctx.textAlign = 'left';
            ctx.textBaseline = 'middle';
            ctx.fillStyle = '#0f172a';
            ctx.fillText(label, node.x + 10, node.y);
          }}
          linkDirectionalArrowLength={5}
          linkDirectionalArrowRelPos={1}
          linkDirectionalParticles={1}
          linkDirectionalParticleWidth={1.5}
          linkColor={() => '#94a3b8'}
          linkWidth={1.5}
          cooldownTicks={120}
          onNodeClick={handleNodeClick}
          onEngineStop={() => graphRef.current?.zoomToFit(500, 40)}
        />
      </section>
    </div>
  );
}
