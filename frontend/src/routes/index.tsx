import { createFileRoute } from "@tanstack/react-router";
import { Navbar } from "@/components/Navbar";
import { Applications } from "@/sections/Applications";
import { DigitalTwin } from "@/sections/DigitalTwin";
import { Editing } from "@/sections/Editing";
import { FinalCta } from "@/sections/FinalCta";
import { Hero } from "@/sections/Hero";
import { Pipeline } from "@/sections/Pipeline";
import { Reconstruction } from "@/sections/Reconstruction";
import { Semantic } from "@/sections/Semantic";
import { SpatialAI } from "@/sections/SpatialAI";
import { Technology } from "@/sections/Technology";

const TITLE = "Vantage — AI-Powered 3D Spatial Intelligence";
const DESCRIPTION =
  "Turn one drone pass into an interactive digital twin that can be measured, queried and explored with spatial AI.";

export const Route = createFileRoute("/")({
  head: () => ({
    meta: [
      { title: TITLE },
      { name: "description", content: DESCRIPTION },
      { property: "og:title", content: TITLE },
      { property: "og:description", content: DESCRIPTION },
      { property: "og:type", content: "website" },
      { name: "twitter:card", content: "summary_large_image" },
    ],
  }),
  component: Index,
});

function Index() {
  return (
    <main className="relative bg-background">
      <Navbar />
      <Hero />
      <Pipeline />
      <Reconstruction />
      <Semantic />
      <SpatialAI />
      <Editing />
      <DigitalTwin />
      <Applications />
      <Technology />
      <FinalCta />
    </main>
  );
}
