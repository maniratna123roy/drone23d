import { Eye, EyeOff, Layers } from "lucide-react";
import { useSpatialStore } from "@/store/spatialStore";
import type { LayerId } from "@/types/spatial";
import { Button } from "@/components/ui/button";
import { Slider } from "@/components/ui/slider";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";

/**
 * LayerControls
 *
 * UI panel for controlling layer visibility and opacity.
 * Allows users to toggle buildings, terrain, roads, vegetation on/off.
 *
 * Analogy: Like turning on/off different architectural drawings in CAD.
 */

const LAYERS: Array<{ id: LayerId; label: string; color: string }> = [
  { id: "buildings", label: "Buildings", color: "bg-blue-500" },
  { id: "terrain", label: "Terrain", color: "bg-green-600" },
  { id: "roads", label: "Roads", color: "bg-gray-500" },
  { id: "vegetation", label: "Vegetation", color: "bg-green-400" },
  { id: "infrastructure", label: "Infrastructure", color: "bg-yellow-600" },
];

export function LayerControls() {
  const {
    layerVisibility,
    toggleLayer,
    setLayerOpacity,
    layerOpacity,
    soloLayerId,
    setSoloLayer,
  } = useSpatialStore();

  return (
    <Card className="w-80">
      <CardHeader className="pb-3">
        <div className="flex items-center gap-2">
          <Layers className="h-5 w-5" />
          <CardTitle>Layer Controls</CardTitle>
        </div>
        <CardDescription>Toggle visibility and adjust opacity</CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        {/* Solo mode controls */}
        <div className="space-y-2 border-b pb-4">
          <p className="text-sm font-medium">Solo Mode</p>
          {soloLayerId && (
            <Button
              size="sm"
              variant="secondary"
              onClick={() => setSoloLayer(null)}
              className="w-full"
            >
              Clear Solo Mode
            </Button>
          )}
          {!soloLayerId && (
            <p className="text-xs text-muted-foreground">No solo layer active</p>
          )}
        </div>

        {/* Layer toggles */}
        <div className="space-y-3">
          {LAYERS.map((layer) => {
            const isVisible = layerVisibility[layer.id];
            const isSolo = soloLayerId === layer.id;
            const opacity = layerOpacity[layer.id];

            return (
              <div key={layer.id} className="space-y-2">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <div className={`h-3 w-3 rounded ${layer.color}`} />
                    <label className="text-sm font-medium">{layer.label}</label>
                  </div>

                  <div className="flex gap-1">
                    {/* Visibility toggle */}
                    <Button
                      size="sm"
                      variant={isVisible ? "default" : "outline"}
                      onClick={() => toggleLayer(layer.id)}
                      className="h-8 w-8 p-0"
                      title={isVisible ? "Hide" : "Show"}
                    >
                      {isVisible ? (
                        <Eye className="h-4 w-4" />
                      ) : (
                        <EyeOff className="h-4 w-4" />
                      )}
                    </Button>

                    {/* Solo button */}
                    <Button
                      size="sm"
                      variant={isSolo ? "default" : "outline"}
                      onClick={() => setSoloLayer(isSolo ? null : layer.id)}
                      className="h-8 px-2 text-xs"
                      title="Solo this layer"
                    >
                      S
                    </Button>
                  </div>
                </div>

                {/* Opacity slider */}
                {isVisible && !isSolo && (
                  <div className="px-2">
                    <Slider
                      value={[opacity]}
                      onValueChange={(val) =>
                        setLayerOpacity(layer.id, val[0] ?? 1.0)
                      }
                      min={0}
                      max={1}
                      step={0.05}
                      className="h-2"
                    />
                    <p className="text-xs text-muted-foreground mt-1">
                      Opacity: {Math.round(opacity * 100)}%
                    </p>
                  </div>
                )}
              </div>
            );
          })}
        </div>
      </CardContent>
    </Card>
  );
}
