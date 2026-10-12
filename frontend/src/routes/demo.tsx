import { createFileRoute } from "@tanstack/react-router";
import { SpatialTwinApp } from "@/components/SpatialTwinApp";

export const Route = createFileRoute("/demo")({
  head: () => ({
    meta: [
      { title: "Spatial Twin — Live Demo" },
      { name: "description", content: "3D digital twin with spatial AI" },
    ],
  }),
  component: Demo,
});

function Demo() {
  return (
    <div className="w-full h-screen overflow-hidden">
      <SpatialTwinApp />
    </div>
  );
}
