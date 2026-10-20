import { createFileRoute } from "@tanstack/react-router";
import { VideogrammetryApp } from "@/components/videogrammetry/VideogrammetryApp";

export const Route = createFileRoute("/videogrammetry")({
  head: () => ({
    meta: [
      { title: "Videogrammetry Approach — Continuous Video-to-3D Sidecar" },
      {
        name: "description",
        content:
          "Continuous drone-video-to-3D reconstruction modeled after Skyebrowse. Produces metric polygon mesh, point cloud, and georeferenced orthomosaic with automated AI quality gate.",
      },
    ],
  }),
  component: VideogrammetryRoute,
});

function VideogrammetryRoute() {
  return <VideogrammetryApp />;
}
