import { X, ChevronDown, Building2, Ruler, ChevronLeft, ChevronRight, ArrowLeft } from "lucide-react";
import { useSpatialStore } from "@/store/spatialStore";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";

/**
 * ObjectInspector
 *
 * Real-world Analogy:
 * Like the "Properties & Surveying Inspector" in BIM/CAD software (Revit, Civil 3D).
 * Provides exact physical dimensions (height, width, depth, area, volume, elevation, bbox)
 * for any classified building in the reconstructed 3D twin.
 */

export function ObjectInspector() {
  const { selectedObjectId, getSelectedObject, setSelectedObjectId, objects } =
    useSpatialStore();

  const object = getSelectedObject();
  const currentIndex = object ? objects.findIndex((o) => o.id === object.id) : -1;

  const handlePrev = () => {
    if (objects.length === 0) return;
    const nextIdx = (currentIndex - 1 + objects.length) % objects.length;
    setSelectedObjectId(objects[nextIdx].id);
  };

  const handleNext = () => {
    if (objects.length === 0) return;
    const nextIdx = (currentIndex + 1) % objects.length;
    setSelectedObjectId(objects[nextIdx].id);
  };

  // If no specific building is selected, show the interactive detected structures inventory
  if (!selectedObjectId || !object) {
    return (
      <Card className="w-80 max-h-96 overflow-y-auto border-border/80 shadow-md">
        <CardHeader className="pb-3 border-b border-border/40">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-1.5">
              <Building2 className="h-4 w-4 text-cyan-400" />
              <CardTitle className="text-sm font-semibold">Classified Buildings</CardTitle>
            </div>
            <Badge variant="outline" className="font-mono text-cyan-400 text-xs">
              {objects.length} structures
            </Badge>
          </div>
          <CardDescription className="text-xs">
            Select any structure below or click in the 3D viewer to inspect its physical dimensions.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-2 pt-3">
          {objects.length === 0 ? (
            <div className="text-center py-8 space-y-2">
              <Building2 className="h-8 w-8 text-muted-foreground/40 mx-auto" />
              <p className="text-xs text-muted-foreground">
                No structures loaded yet. Align ground or trigger extraction to inspect buildings.
              </p>
            </div>
          ) : (
            objects.map((obj) => {
              const vol = (obj.areaM2 || obj.width * obj.depth) * obj.height;
              return (
                <div
                  key={obj.id}
                  onClick={() => setSelectedObjectId(obj.id)}
                  className="p-2.5 rounded-lg border border-border/60 hover:border-cyan-500/60 hover:bg-cyan-950/20 cursor-pointer transition-all space-y-1.5 group"
                >
                  <div className="flex items-center justify-between">
                    <span className="font-medium text-xs text-foreground group-hover:text-cyan-300 transition-colors">
                      {obj.label}
                    </span>
                    <Badge variant="secondary" className="text-[10px] font-mono">
                      {obj.region?.toUpperCase() || "ZONE"}
                    </Badge>
                  </div>
                  <div className="grid grid-cols-4 gap-1 text-[11px] font-mono text-muted-foreground">
                    <div>
                      <span className="text-[9px] block text-cyan-400">HEIGHT</span>
                      {obj.height.toFixed(1)}m
                    </div>
                    <div>
                      <span className="text-[9px] block text-cyan-400">WIDTH</span>
                      {obj.width.toFixed(1)}m
                    </div>
                    <div>
                      <span className="text-[9px] block text-cyan-400">AREA</span>
                      {obj.areaM2.toFixed(0)}m²
                    </div>
                    <div>
                      <span className="text-[9px] block text-cyan-400">VOL</span>
                      {vol.toFixed(0)}m³
                    </div>
                  </div>
                </div>
              );
            })
          )}
        </CardContent>
      </Card>
    );
  }

  const volume = (object.areaM2 > 0 ? object.areaM2 : object.width * object.depth) * object.height;

  return (
    <Card className="w-80 max-h-96 overflow-y-auto border-border/80 shadow-md">
      <CardHeader className="pb-3 border-b border-border/40">
        <div className="flex items-center justify-between">
          <button
            type="button"
            onClick={() => setSelectedObjectId(null)}
            className="flex items-center gap-1 text-xs text-muted-foreground hover:text-cyan-300 transition-colors cursor-pointer"
            title="Return to buildings list"
          >
            <ArrowLeft className="h-3.5 w-3.5" /> All structures
          </button>
          <div className="flex items-center gap-1">
            {objects.length > 1 && (
              <>
                <button
                  type="button"
                  onClick={handlePrev}
                  className="h-6 w-6 inline-flex items-center justify-center rounded hover:bg-muted text-muted-foreground hover:text-foreground transition-colors"
                  title="Previous structure"
                >
                  <ChevronLeft className="h-3.5 w-3.5" />
                </button>
                <span className="text-[10px] font-mono text-muted-foreground">
                  {currentIndex + 1}/{objects.length}
                </span>
                <button
                  type="button"
                  onClick={handleNext}
                  className="h-6 w-6 inline-flex items-center justify-center rounded hover:bg-muted text-muted-foreground hover:text-foreground transition-colors"
                  title="Next structure"
                >
                  <ChevronRight className="h-3.5 w-3.5" />
                </button>
              </>
            )}
            <Button
              size="sm"
              variant="ghost"
              onClick={() => setSelectedObjectId(null)}
              className="h-6 w-6 p-0 ml-1"
            >
              <X className="h-3.5 w-3.5" />
            </Button>
          </div>
        </div>
        <div className="pt-1.5">
          <CardTitle className="text-sm font-semibold line-clamp-1">{object.label}</CardTitle>
          <CardDescription className="text-xs mt-0.5 font-mono">
            Database ID: #{object.id}
          </CardDescription>
        </div>
      </CardHeader>

      <CardContent className="space-y-4 pt-3">
        {/* Layer & Region badges */}
        <div className="flex items-center gap-2">
          <div>
            <p className="text-[10px] font-medium text-muted-foreground mb-0.5">Category</p>
            <Badge variant="outline" className="capitalize text-xs">
              {object.layer}
            </Badge>
          </div>
          {object.region && (
            <div>
              <p className="text-[10px] font-medium text-muted-foreground mb-0.5">Sector</p>
              <Badge variant="secondary" className="capitalize text-xs font-mono">
                {object.region.toUpperCase()}
              </Badge>
            </div>
          )}
          {object.version !== undefined && (
            <div>
              <p className="text-[10px] font-medium text-muted-foreground mb-0.5">State</p>
              <Badge variant="outline" className="text-xs font-mono">
                v{object.version} (Verified)
              </Badge>
            </div>
          )}
        </div>

        {/* Physical Measurements Grid */}
        <div className="rounded-lg bg-muted/40 p-3 border border-border/40">
          <div className="flex items-center gap-1.5 text-xs font-semibold text-cyan-300 mb-2">
            <Ruler className="h-3.5 w-3.5" />
            Physical Measured Attributes
          </div>
          <div className="grid grid-cols-2 gap-2.5">
            <div>
              <p className="text-[10px] font-medium text-muted-foreground">Height (h)</p>
              <p className="text-sm font-bold font-mono text-cyan-400">
                {object.height.toFixed(2)} m
              </p>
            </div>
            <div>
              <p className="text-[10px] font-medium text-muted-foreground">Footprint Area (A)</p>
              <p className="text-sm font-semibold font-mono text-foreground">
                {object.areaM2.toFixed(1)} m²
              </p>
            </div>
            <div>
              <p className="text-[10px] font-medium text-muted-foreground">Width (X span)</p>
              <p className="text-sm font-semibold font-mono text-foreground">
                {object.width.toFixed(2)} m
              </p>
            </div>
            <div>
              <p className="text-[10px] font-medium text-muted-foreground">Depth (Y span)</p>
              <p className="text-sm font-semibold font-mono text-foreground">
                {object.depth.toFixed(2)} m
              </p>
            </div>
            <div>
              <p className="text-[10px] font-medium text-muted-foreground">Estimated Volume (V)</p>
              <p className="text-sm font-semibold font-mono text-foreground">
                {volume.toFixed(1)} m³
              </p>
            </div>
            <div>
              <p className="text-[10px] font-medium text-muted-foreground">Base Elevation (Z)</p>
              <p className="text-sm font-semibold font-mono text-foreground">
                {object.elevationM.toFixed(2)} m
              </p>
            </div>
          </div>
        </div>

        {/* Bounding Box / Spatial Coordinates (PostGIS) */}
        <div className="border-t border-border/40 pt-3">
          <p className="text-xs font-medium text-muted-foreground mb-1.5 flex items-center justify-between">
            <span>Spatial Bounding Box (m)</span>
            {object.footprint?.coordinates?.[0] && (
              <span className="text-[10px] text-muted-foreground font-mono">
                {object.footprint.coordinates[0].length} polygon vertices
              </span>
            )}
          </p>
          {object.splatBbox ? (
            <div className="bg-muted/50 p-2.5 rounded font-mono text-[11px] space-y-1 border border-border/40">
              <div className="flex justify-between">
                <span className="text-muted-foreground">X (East/West):</span>
                <span>{object.splatBbox.min_x.toFixed(2)}m → {object.splatBbox.max_x.toFixed(2)}m</span>
              </div>
              <div className="flex justify-between">
                <span className="text-muted-foreground">Y (North/South):</span>
                <span>{object.splatBbox.min_y.toFixed(2)}m → {object.splatBbox.max_y.toFixed(2)}m</span>
              </div>
              <div className="flex justify-between">
                <span className="text-muted-foreground">Z (Elevation):</span>
                <span>{object.splatBbox.min_z.toFixed(2)}m → {object.splatBbox.max_z.toFixed(2)}m</span>
              </div>
            </div>
          ) : (
            <div className="bg-muted p-2 rounded font-mono text-xs space-y-1">
              <p>X: {object.x.toFixed(2)} m | Z: {object.z.toFixed(2)} m</p>
              <p>W: {object.width.toFixed(2)} m | D: {object.depth.toFixed(2)} m</p>
            </div>
          )}
        </div>
      </CardContent>
    </Card>
  );
}
