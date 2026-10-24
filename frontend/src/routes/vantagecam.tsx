import { createFileRoute } from "@tanstack/react-router";
import { VantageCamPage } from "@/components/VantageCamPage";

export const Route = createFileRoute("/vantagecam")({
  head: () => ({
    meta: [
      { title: "VantageCam 3D Reconstruction — Drone Video to 3D Scene" },
      {
        name: "description",
        content:
          "Upload drone video and process through 10-stage pipeline: reconstruction, labeling, geometry extraction, export. Real-time progress tracking with downloadable 3D assets.",
      },
    ],
  }),
  component: VantageCamRoute,
});

function VantageCamRoute() {
  return <VantageCamPage />;
}
