import React, { useState } from "react";
import { Map, Layers, ZoomIn, ZoomOut, Compass } from "lucide-react";

interface OrthomosaicMapViewerProps {
  gsdCm?: number;
  crs?: string;
}

export const OrthomosaicMapViewer: React.FC<OrthomosaicMapViewerProps> = ({
  gsdCm = 2.5,
  crs = "EPSG:4326",
}) => {
  const [zoom, setZoom] = useState(1);
  const [layer, setLayer] = useState<"ortho" | "dsm">("ortho");

  return (
    <div className="rounded-lg border border-border/80 bg-card p-5">
      <div className="flex flex-wrap items-center justify-between gap-3 mb-4">
        <div>
          <div className="flex items-center gap-2">
            <Map className="h-4 w-4 text-purple-400" />
            <h3 className="text-sm font-semibold text-foreground uppercase tracking-wider">
              Georeferenced Orthomosaic & DSM
            </h3>
          </div>
          <p className="text-xs text-muted-foreground">
            True orthographic top-down projection rendered at target Ground Sample Distance (GSD).
          </p>
        </div>

        <div className="flex items-center gap-2">
          <div className="flex rounded border border-border bg-muted/30 p-0.5 text-xs font-mono">
            <button
              onClick={() => setLayer("ortho")}
              className={`px-2.5 py-1 rounded transition-colors ${
                layer === "ortho" ? "bg-purple-600 text-white" : "text-muted-foreground hover:text-foreground"
              }`}
            >
              Orthomosaic (RGB)
            </button>
            <button
              onClick={() => setLayer("dsm")}
              className={`px-2.5 py-1 rounded transition-colors ${
                layer === "dsm" ? "bg-purple-600 text-white" : "text-muted-foreground hover:text-foreground"
              }`}
            >
              DSM Elevation
            </button>
          </div>

          <div className="flex items-center border border-border rounded bg-muted/20">
            <button
              onClick={() => setZoom((z) => Math.max(0.75, z - 0.25))}
              className="p-1.5 text-muted-foreground hover:text-foreground"
              title="Zoom Out"
            >
              <ZoomOut className="h-3.5 w-3.5" />
            </button>
            <span className="font-mono text-[11px] px-1 text-muted-foreground">{zoom.toFixed(1)}x</span>
            <button
              onClick={() => setZoom((z) => Math.min(2.0, z + 0.25))}
              className="p-1.5 text-muted-foreground hover:text-foreground"
              title="Zoom In"
            >
              <ZoomIn className="h-3.5 w-3.5" />
            </button>
          </div>
        </div>
      </div>

      {/* Map Canvas / Viewer */}
      <div className="relative h-72 w-full rounded border border-border bg-zinc-950 overflow-hidden flex items-center justify-center">
        {/* Rendered Ortho / DSM SVG Map Representation */}
        <div
          className="transition-transform duration-200"
          style={{ transform: `scale(${zoom})` }}
        >
          <svg width="420" height="260" viewBox="0 0 420 260" className="rounded shadow-xl">
            {/* Background Terrain */}
            <rect
              width="420"
              height="260"
              fill={layer === "ortho" ? "#27323a" : "#1a202c"}
            />

            {/* Roads */}
            <path
              d="M 0 130 Q 210 135 420 130"
              stroke={layer === "ortho" ? "#4a5568" : "#2d3748"}
              strokeWidth="28"
              fill="none"
            />
            <path
              d="M 210 0 L 210 260"
              stroke={layer === "ortho" ? "#4a5568" : "#2d3748"}
              strokeWidth="22"
              fill="none"
            />

            {/* Grid marks */}
            {[70, 140, 210, 280, 350].map((x) => (
              <line key={x} x1={x} y1="0" x2={x} y2="260" stroke="#334155" strokeWidth="0.5" strokeDasharray="3 3" />
            ))}
            {[65, 130, 195].map((y) => (
              <line key={y} x1="0" y1={y} x2="420" y2={y} stroke="#334155" strokeWidth="0.5" strokeDasharray="3 3" />
            ))}

            {/* Building 1: Mill-19 North */}
            <rect
              x="90"
              y="60"
              width="90"
              height="110"
              fill={layer === "ortho" ? "#5a6a7c" : "#e2e8f0"}
              stroke="#cbd5e1"
              strokeWidth="1.5"
            />
            <text x="135" y="118" textAnchor="middle" fill="#ffffff" fontSize="9" fontFamily="monospace" fontWeight="bold">
              MILL-19 NORTH
            </text>
            {layer === "dsm" && (
              <text x="135" y="132" textAnchor="middle" fill="#000000" fontSize="8" fontFamily="monospace">
                h=11.5m
              </text>
            )}

            {/* Building 2: Control Tower */}
            <rect
              x="250"
              y="50"
              width="80"
              height="90"
              fill={layer === "ortho" ? "#475569" : "#ffffff"}
              stroke="#94a3b8"
              strokeWidth="1.5"
            />
            <text x="290" y="98" textAnchor="middle" fill="#ffffff" fontSize="9" fontFamily="monospace" fontWeight="bold">
              CONTROL TOWER
            </text>
            {layer === "dsm" && (
              <text x="290" y="112" textAnchor="middle" fill="#000000" fontSize="8" fontFamily="monospace">
                h=16.5m
              </text>
            )}

            {/* Building 3: Logistics Depot */}
            <rect
              x="140"
              y="180"
              width="150"
              height="60"
              fill={layer === "ortho" ? "#334155" : "#cbd5e1"}
              stroke="#64748b"
              strokeWidth="1.5"
            />
            <text x="215" y="215" textAnchor="middle" fill="#ffffff" fontSize="9" fontFamily="monospace" fontWeight="bold">
              LOGISTICS DEPOT
            </text>
            {layer === "dsm" && (
              <text x="215" y="228" textAnchor="middle" fill="#000000" fontSize="8" fontFamily="monospace">
                h=8.0m
              </text>
            )}
          </svg>
        </div>

        {/* Compass Readout */}
        <div className="absolute top-3 right-3 flex items-center gap-1 font-mono text-[10px] bg-background/80 backdrop-blur px-2 py-1 rounded border border-border">
          <Compass className="h-3.5 w-3.5 text-purple-400" />
          <span>N 0° (Grid North)</span>
        </div>

        {/* Scale Bar */}
        <div className="absolute bottom-3 right-3 font-mono text-[10px] bg-background/80 backdrop-blur px-2 py-1 rounded border border-border">
          <div className="w-16 h-1 bg-purple-400 mb-1" />
          <span>20 metres</span>
        </div>

        {/* CRS & GSD Readout */}
        <div className="absolute bottom-3 left-3 font-mono text-[10px] bg-background/80 backdrop-blur px-2 py-1 rounded border border-border text-muted-foreground">
          <span>GSD: <strong className="text-foreground">{gsdCm} cm/px</strong> | CRS: <strong className="text-foreground">{crs}</strong></span>
        </div>
      </div>
    </div>
  );
};
