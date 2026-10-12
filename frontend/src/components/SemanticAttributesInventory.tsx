import { useEffect, useState } from "react";
import { Building2, Navigation, Trees, Mountain, Ruler, ExternalLink, RefreshCw } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { useSpatialStore } from "@/store/spatialStore";
import { api, type ClassifiedAttributes } from "@/lib/api";

interface SemanticAttributesInventoryProps {
  initialAttributes?: ClassifiedAttributes | null;
  onInspectObject?: (id: string) => void;
  onRefresh?: () => void;
}

export function SemanticAttributesInventory({
  initialAttributes,
  onInspectObject,
  onRefresh,
}: SemanticAttributesInventoryProps) {
  const [data, setData] = useState<ClassifiedAttributes | null>(initialAttributes || null);
  const [loading, setLoading] = useState(false);
  const [activeCategory, setActiveCategory] = useState<"all" | "structures" | "roads" | "vegetation" | "terrain">("all");
  const { setSelectedObjectId } = useSpatialStore();

  const loadAttributes = async () => {
    setLoading(true);
    try {
      const res = await api.fetchClassifiedAttributes();
      setData(res);
    } catch (err) {
      console.warn("Failed to fetch classified attributes:", err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (initialAttributes) {
      setData(initialAttributes);
    } else {
      loadAttributes();
    }
  }, [initialAttributes]);

  const summary = data?.summary;
  const structures = data?.structures || [];
  const roads = data?.roads || [];
  const vegetation = data?.vegetation || [];
  const terrain = data?.terrain || [];

  const handleInspect = (id: string | number) => {
    const strId = String(id);
    setSelectedObjectId(strId);
    if (onInspectObject) {
      onInspectObject(strId);
    }
  };

  return (
    <div className="space-y-3.5 pt-2">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-1.5">
          <Ruler className="h-4 w-4 text-cyan-400" />
          <h3 className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
            Measured Physical Inventory
          </h3>
        </div>
        <button
          type="button"
          onClick={loadAttributes}
          disabled={loading}
          className="text-xs text-muted-foreground hover:text-cyan-300 flex items-center gap-1 transition-colors"
          title="Refresh physical measurements"
        >
          <RefreshCw className={`h-3 w-3 ${loading ? "animate-spin" : ""}`} />
          Sync
        </button>
      </div>

      {/* Category Filter Pills */}
      <div className="flex flex-wrap gap-1.5">
        <button
          type="button"
          onClick={() => setActiveCategory("all")}
          className={`px-2 py-1 rounded text-xs font-medium transition-colors ${
            activeCategory === "all"
              ? "bg-cyan-500/20 text-cyan-300 border border-cyan-500/40"
              : "bg-muted/40 text-muted-foreground hover:bg-muted/60"
          }`}
        >
          All Classes
        </button>
        <button
          type="button"
          onClick={() => setActiveCategory("structures")}
          className={`px-2 py-1 rounded text-xs font-medium flex items-center gap-1 transition-colors ${
            activeCategory === "structures"
              ? "bg-cyan-500/20 text-cyan-300 border border-cyan-500/40"
              : "bg-muted/40 text-muted-foreground hover:bg-muted/60"
          }`}
        >
          <Building2 className="h-3 w-3 text-cyan-400" />
          Buildings ({structures.length})
        </button>
        <button
          type="button"
          onClick={() => setActiveCategory("roads")}
          className={`px-2 py-1 rounded text-xs font-medium flex items-center gap-1 transition-colors ${
            activeCategory === "roads"
              ? "bg-amber-500/20 text-amber-300 border border-amber-500/40"
              : "bg-muted/40 text-muted-foreground hover:bg-muted/60"
          }`}
        >
          <Navigation className="h-3 w-3 text-amber-400" />
          Roads ({roads.length})
        </button>
        <button
          type="button"
          onClick={() => setActiveCategory("vegetation")}
          className={`px-2 py-1 rounded text-xs font-medium flex items-center gap-1 transition-colors ${
            activeCategory === "vegetation"
              ? "bg-emerald-500/20 text-emerald-300 border border-emerald-500/40"
              : "bg-muted/40 text-muted-foreground hover:bg-muted/60"
          }`}
        >
          <Trees className="h-3 w-3 text-emerald-400" />
          Vegetation ({vegetation.length})
        </button>
        <button
          type="button"
          onClick={() => setActiveCategory("terrain")}
          className={`px-2 py-1 rounded text-xs font-medium flex items-center gap-1 transition-colors ${
            activeCategory === "terrain"
              ? "bg-slate-500/20 text-slate-300 border border-slate-500/40"
              : "bg-muted/40 text-muted-foreground hover:bg-muted/60"
          }`}
        >
          <Mountain className="h-3 w-3 text-slate-400" />
          Terrain
        </button>
      </div>

      {/* Buildings & Structures Section */}
      {(activeCategory === "all" || activeCategory === "structures") && (
        <section className="space-y-2 rounded-lg border border-cyan-500/30 bg-cyan-950/10 p-3">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-1.5 text-xs font-semibold text-cyan-300">
              <Building2 className="h-4 w-4 text-cyan-400" />
              <span>Buildings & Structures (Class 0)</span>
            </div>
            <Badge variant="outline" className="text-[10px] font-mono border-cyan-500/40 text-cyan-300">
              {structures.length} Detected
            </Badge>
          </div>

          {summary?.structures_metrics && (
            <div className="grid grid-cols-4 gap-1.5 p-2 rounded bg-black/20 text-[11px] font-mono">
              <div>
                <span className="text-[9px] block text-muted-foreground">MAX HEIGHT</span>
                <span className="text-cyan-400 font-semibold">{summary.structures_metrics.max_height_m}m</span>
              </div>
              <div>
                <span className="text-[9px] block text-muted-foreground">AVG HEIGHT</span>
                <span>{summary.structures_metrics.avg_height_m}m</span>
              </div>
              <div>
                <span className="text-[9px] block text-muted-foreground">TOTAL FOOTPRINT</span>
                <span>{summary.structures_metrics.total_footprint_m2.toLocaleString()}m²</span>
              </div>
              <div>
                <span className="text-[9px] block text-muted-foreground">TOTAL VOL</span>
                <span>{summary.structures_metrics.total_volume_m3.toLocaleString()}m³</span>
              </div>
            </div>
          )}

          <div className="space-y-1.5 max-h-48 overflow-y-auto pr-1">
            {structures.map((s: any) => (
              <div
                key={s.id || s.building_id}
                className="flex items-center justify-between p-2 rounded border border-border/40 hover:border-cyan-500/50 bg-background/50 hover:bg-cyan-950/20 transition-all text-xs"
              >
                <div>
                  <div className="font-medium text-foreground flex items-center gap-1.5">
                    <span>{s.label || `Building #${s.id}`}</span>
                    {s.region && (
                      <span className="text-[9px] font-mono px-1 rounded bg-muted text-muted-foreground uppercase">
                        {s.region}
                      </span>
                    )}
                  </div>
                  <div className="text-[11px] font-mono text-muted-foreground flex gap-2.5 mt-0.5">
                    <span>H: <strong className="text-cyan-300">{s.height_m}m</strong></span>
                    <span>W: {s.width_m}m</span>
                    <span>D: {s.depth_m}m</span>
                    <span>Area: {s.area_m2}m²</span>
                    <span>Vol: {s.volume_m3}m³</span>
                  </div>
                </div>
                <Button
                  size="sm"
                  variant="ghost"
                  onClick={() => handleInspect(s.id || s.building_id)}
                  className="h-7 text-xs px-2 text-cyan-400 hover:text-cyan-200 hover:bg-cyan-900/30"
                  title="Inspect structure in 3D"
                >
                  <ExternalLink className="h-3 w-3" />
                </Button>
              </div>
            ))}
          </div>
        </section>
      )}

      {/* Roads & Sidewalks Section */}
      {(activeCategory === "all" || activeCategory === "roads") && (
        <section className="space-y-2 rounded-lg border border-amber-500/30 bg-amber-950/10 p-3">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-1.5 text-xs font-semibold text-amber-300">
              <Navigation className="h-4 w-4 text-amber-400" />
              <span>Roads & Corridors (Class 2)</span>
            </div>
            <Badge variant="outline" className="text-[10px] font-mono border-amber-500/40 text-amber-300">
              {roads.length > 0 ? "1 Corridor Network" : "No roads"}
            </Badge>
          </div>

          {roads.length > 0 ? (
            roads.map((r: any, idx: number) => (
              <div key={idx} className="space-y-1.5">
                <div className="grid grid-cols-3 gap-1.5 p-2 rounded bg-black/20 text-[11px] font-mono">
                  <div>
                    <span className="text-[9px] block text-muted-foreground">CORRIDOR LENGTH</span>
                    <span className="text-amber-400 font-semibold">{r.length_m} m</span>
                  </div>
                  <div>
                    <span className="text-[9px] block text-muted-foreground">AVG WIDTH</span>
                    <span className="text-amber-400 font-semibold">{r.width_m} m</span>
                  </div>
                  <div>
                    <span className="text-[9px] block text-muted-foreground">SURFACE AREA</span>
                    <span>{r.area_m2.toLocaleString()} m²</span>
                  </div>
                </div>
                <div className="flex items-center justify-between text-[11px] text-muted-foreground px-1 font-mono">
                  <span>Surface Elevation: {r.elevation_m}m</span>
                  <span>{r.splat_count?.toLocaleString()} Gaussians</span>
                </div>
              </div>
            ))
          ) : (
            <p className="text-xs text-muted-foreground py-2 text-center">
              No road surfaces identified in point cloud.
            </p>
          )}
        </section>
      )}

      {/* Vegetation & Trees Section */}
      {(activeCategory === "all" || activeCategory === "vegetation") && (
        <section className="space-y-2 rounded-lg border border-emerald-500/30 bg-emerald-950/10 p-3">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-1.5 text-xs font-semibold text-emerald-300">
              <Trees className="h-4 w-4 text-emerald-400" />
              <span>Vegetation & Canopy (Class 3)</span>
            </div>
            <Badge variant="outline" className="text-[10px] font-mono border-emerald-500/40 text-emerald-300">
              {vegetation.length > 0 ? "Greenery Identified" : "None"}
            </Badge>
          </div>

          {vegetation.length > 0 ? (
            vegetation.map((v: any, idx: number) => (
              <div key={idx} className="space-y-1.5">
                <div className="grid grid-cols-3 gap-1.5 p-2 rounded bg-black/20 text-[11px] font-mono">
                  <div>
                    <span className="text-[9px] block text-muted-foreground">CANOPY HEIGHT</span>
                    <span className="text-emerald-400 font-semibold">{v.canopy_height_m} m</span>
                  </div>
                  <div>
                    <span className="text-[9px] block text-muted-foreground">SPREAD WIDTH</span>
                    <span>{v.spread_width_m} m</span>
                  </div>
                  <div>
                    <span className="text-[9px] block text-muted-foreground">CANOPY AREA</span>
                    <span>{v.area_m2.toLocaleString()} m²</span>
                  </div>
                </div>
                <div className="flex items-center justify-between text-[11px] text-muted-foreground px-1 font-mono">
                  <span>Base Elevation: {v.elevation_m}m</span>
                  <span>{v.splat_count?.toLocaleString()} Gaussians</span>
                </div>
              </div>
            ))
          ) : (
            <p className="text-xs text-muted-foreground py-2 text-center">
              No canopy vegetation detected.
            </p>
          )}
        </section>
      )}

      {/* Terrain & Ground Section */}
      {(activeCategory === "all" || activeCategory === "terrain") && (
        <section className="space-y-2 rounded-lg border border-slate-500/30 bg-slate-950/10 p-3">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-1.5 text-xs font-semibold text-slate-300">
              <Mountain className="h-4 w-4 text-slate-400" />
              <span>Terrain & Ground Datum (Class 1)</span>
            </div>
            <Badge variant="outline" className="text-[10px] font-mono border-slate-500/40 text-slate-300">
              Ground Plane
            </Badge>
          </div>

          {terrain.length > 0 ? (
            terrain.map((t: any, idx: number) => (
              <div key={idx} className="space-y-1.5">
                <div className="grid grid-cols-2 gap-1.5 p-2 rounded bg-black/20 text-[11px] font-mono">
                  <div>
                    <span className="text-[9px] block text-muted-foreground">DATUM ELEVATION</span>
                    <span className="text-slate-300 font-semibold">{t.elevation_m} m</span>
                  </div>
                  <div>
                    <span className="text-[9px] block text-muted-foreground">SURFACE EXTENT</span>
                    <span>{t.area_m2.toLocaleString()} m²</span>
                  </div>
                </div>
                <div className="flex items-center justify-between text-[11px] text-muted-foreground px-1 font-mono">
                  <span>Ground Reference: Z = 0.00m Datum</span>
                  <span>{t.splat_count?.toLocaleString()} Gaussians</span>
                </div>
              </div>
            ))
          ) : (
            <p className="text-xs text-muted-foreground py-2 text-center">
              No ground terrain points detected.
            </p>
          )}
        </section>
      )}
    </div>
  );
}
