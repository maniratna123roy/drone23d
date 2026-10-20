import React from "react";
import { Check, ShieldAlert, Cpu, Sparkles } from "lucide-react";

export interface TierOption {
  id: string;
  name: string;
  description: string;
  frameBudget: number;
  resolution: string;
  dynamicMasks: boolean;
  retries: number;
  triangleBudget: string;
  intendedOutput: string;
}

export const TIER_OPTIONS: TierOption[] = [
  {
    id: "lite",
    name: "Lite",
    description: "Fast preview for rapid reconnaissance and coarse mesh checks.",
    frameBudget: 200,
    resolution: "1080p",
    dynamicMasks: false,
    retries: 0,
    triangleBudget: "50k tris",
    intendedOutput: "Quick 3D preview, coarse mesh",
  },
  {
    id: "standard",
    name: "Standard",
    description: "Balanced operational documentation tier for engineering inspections.",
    frameBudget: 400,
    resolution: "4K",
    dynamicMasks: false,
    retries: 1,
    triangleBudget: "250k tris",
    intendedOutput: "Operational docs, textured mesh",
  },
  {
    id: "premium",
    name: "Premium",
    description: "High-fidelity measurement-grade mesh with dynamic-object masking.",
    frameBudget: 700,
    resolution: "4K to 8K",
    dynamicMasks: true,
    retries: 2,
    triangleBudget: "750k tris",
    intendedOutput: "Measurement-grade mesh, point cloud",
  },
  {
    id: "premium_advanced",
    name: "Premium Advanced",
    description: "Survey-grade reconstruction with scene tiling, 8K textures, and automatic redo loop.",
    frameBudget: 1500,
    resolution: "8K tiled",
    dynamicMasks: true,
    retries: 3,
    triangleBudget: "2.0M tris",
    intendedOutput: "Maximum detail, sub-cm orthomosaic",
  },
];

interface TierSelectorProps {
  selectedTier: string;
  onSelectTier: (tierId: string) => void;
  disabled?: boolean;
}

export const TierSelector: React.FC<TierSelectorProps> = ({
  selectedTier,
  onSelectTier,
  disabled = false,
}) => {
  return (
    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-3">
      {TIER_OPTIONS.map((tier) => {
        const isSelected = selectedTier === tier.id;
        return (
          <button
            key={tier.id}
            type="button"
            disabled={disabled}
            onClick={() => onSelectTier(tier.id)}
            className={`flex flex-col text-left p-3.5 rounded-lg border transition-all ${
              isSelected
                ? "border-purple-500 bg-purple-500/10 shadow-lg shadow-purple-500/10"
                : "border-border/60 bg-muted/20 hover:border-border hover:bg-muted/40"
            } ${disabled ? "opacity-60 cursor-not-allowed" : "cursor-pointer"}`}
          >
            <div className="flex items-center justify-between w-full mb-1.5">
              <span className="font-semibold text-xs tracking-wide text-foreground uppercase">
                {tier.name}
              </span>
              {isSelected && (
                <span className="flex h-4 w-4 items-center justify-center rounded-full bg-purple-500 text-white">
                  <Check className="h-2.5 w-2.5" />
                </span>
              )}
            </div>

            <p className="text-[11px] text-muted-foreground line-clamp-2 mb-3">
              {tier.description}
            </p>

            <div className="mt-auto space-y-1.5 pt-2 border-t border-border/40 font-mono text-[10px]">
              <div className="flex justify-between text-muted-foreground">
                <span>Budget:</span>
                <span className="text-foreground">~{tier.frameBudget} frames</span>
              </div>
              <div className="flex justify-between text-muted-foreground">
                <span>Resolution:</span>
                <span className="text-foreground">{tier.resolution}</span>
              </div>
              <div className="flex justify-between text-muted-foreground">
                <span>Dynamic Masks:</span>
                <span className={tier.dynamicMasks ? "text-emerald-400" : "text-muted-foreground"}>
                  {tier.dynamicMasks ? "Enabled (AI)" : "Off"}
                </span>
              </div>
              <div className="flex justify-between text-muted-foreground">
                <span>QA Retries:</span>
                <span className="text-foreground">Up to {tier.retries} redo(s)</span>
              </div>
              <div className="flex justify-between text-muted-foreground">
                <span>Detail Budget:</span>
                <span className="text-purple-300">{tier.triangleBudget}</span>
              </div>
            </div>
          </button>
        );
      })}
    </div>
  );
};
