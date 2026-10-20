import { createFileRoute } from "@tanstack/react-router";
import { OpenRouter3DApp } from "@/components/openrouter-3d/OpenRouter3DApp";

export const Route = createFileRoute("/openrouter-3d")({
  head: () => ({
    meta: [
      { title: "OpenRouter AI 3D — Multimodal Drone Video-to-3D Synthesis" },
      {
        name: "description",
        content:
          "Reconstruct 3D digital twins from drone video footage using OpenRouter Multimodal Vision models (Nemotron, Gemini, GPT-4o) with parametric geometry and binary glTF 2.0 export.",
      },
    ],
  }),
  component: OpenRouter3DRoute,
});

function OpenRouter3DRoute() {
  return <OpenRouter3DApp />;
}
