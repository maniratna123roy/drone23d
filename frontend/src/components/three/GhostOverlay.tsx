import { useEffect, useRef } from "react";
import * as THREE from "three";
import { useFrame } from "@react-three/fiber";
import { useSpatialStore } from "@/store/spatialStore";
import type { GhostObject } from "@/types/spatial";

/**
 * GhostOverlay
 *
 * Translucent holographic preview mesh for the natural language Edit Loop (Phase 7).
 *
 * Beginner Analogy:
 * Architectural tracing paper in 3D:
 * When you propose to raise a building by 40 meters, this renders a neon cyan/amber
 * holographic twin showing exactly where the new roof and walls will sit before
 * you commit the change to the permanent database.
 *
 * Design Decisions:
 * - Rendered in sceneRoot (Z-up coordinate frame, ground at z=0).
 * - Translucent wireframe/holographic styling so user sees both the original and proposed height.
 */

export function GhostOverlay() {
  const groupRef = useRef<THREE.Group>(null);
  const { ghostObjects } = useSpatialStore();

  useEffect(() => {
    if (!groupRef.current) return;

    // Clear existing ghost meshes
    while (groupRef.current.children.length > 0) {
      const child = groupRef.current.children[0] as THREE.Mesh;
      if (child.geometry) child.geometry.dispose();
      groupRef.current.remove(child);
    }

    if (!ghostObjects || ghostObjects.length === 0) return;

    ghostObjects.forEach((ghost: GhostObject) => {
      let geometry: THREE.BufferGeometry;
      let posX = 0;
      let posY = 0;
      let posZ = 0;

      const coords = ghost.footprint?.coordinates?.[0];
      if (Array.isArray(coords) && coords.length >= 3) {
        const shape = new THREE.Shape();
        shape.moveTo(coords[0][0], coords[0][1]);
        for (let i = 1; i < coords.length; i++) {
          shape.lineTo(coords[i][0], coords[i][1]);
        }
        // Extrude to the proposed new height
        geometry = new THREE.ExtrudeGeometry(shape, {
          depth: Math.max(1.0, ghost.newHeight),
          bevelEnabled: false,
        });
        posZ = ghost.elevationM || 0;
      } else {
        const w = Math.max(2.0, ghost.width);
        const d = Math.max(2.0, ghost.depth);
        const h = Math.max(1.0, ghost.newHeight);
        geometry = new THREE.BoxGeometry(w, d, h);
        posX = ghost.x;
        posY = ghost.z;
        posZ = (ghost.elevationM || 0) + h / 2.0;
      }

      // Neon cyan holographic material for preview
      const material = new THREE.MeshStandardMaterial({
        color: 0x06b6d4,
        emissive: 0x0891b2,
        emissiveIntensity: 0.7,
        transparent: true,
        opacity: 0.45,
        wireframe: true,
        depthWrite: false,
      });

      const mesh = new THREE.Mesh(geometry, material);
      mesh.position.set(posX, posY, posZ);
      mesh.name = `ghost-${ghost.id}`;

      // Also create an edge outline for crisp visual definition
      const edgesGeom = new THREE.EdgesGeometry(geometry);
      const lineMat = new THREE.LineBasicMaterial({
        color: 0x38bdf8,
        linewidth: 2,
        transparent: true,
        opacity: 0.85,
      });
      const wireframeLines = new THREE.LineSegments(edgesGeom, lineMat);
      mesh.add(wireframeLines);

      groupRef.current?.add(mesh);
    });
  }, [ghostObjects]);

  // Gentle pulse animation for the ghost preview
  useFrame((state) => {
    if (!groupRef.current || ghostObjects.length === 0) return;
    const time = state.clock.getElapsedTime();
    const pulse = 0.4 + 0.15 * Math.sin(time * 4.0);

    groupRef.current.children.forEach((child) => {
      const mesh = child as THREE.Mesh;
      const mat = mesh.material as THREE.MeshStandardMaterial;
      if (mat) {
        mat.opacity = pulse;
      }
    });
  });

  return <group ref={groupRef} name="ghostOverlay" />;
}
