import { useMotionValueEvent, useScroll } from "motion/react";
import { useRef, type RefObject } from "react";

/**
 * Bridges a scroll MotionValue into a plain ref so `useFrame` inside a
 * three.js canvas can read it without re-rendering React.
 */
export function useScrollProgressRef(
  target: RefObject<HTMLElement | null>,
  offset: ["start start" | "start end" | "start center", "end start" | "end end" | "center start"] = [
    "start end",
    "end start",
  ],
) {
  const { scrollYProgress } = useScroll({ target, offset });
  const progress = useRef(0);
  useMotionValueEvent(scrollYProgress, "change", (v) => {
    progress.current = v;
  });
  return { progress, scrollYProgress };
}

export function useHydrated() {
  const ref = useRef(false);
  return ref;
}
