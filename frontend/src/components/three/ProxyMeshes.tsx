import { useEffect, useRef } from "react";
import { Html } from "@react-three/drei";
import * as THREE from "three";
import { useThree, useFrame } from "@react-three/fiber";
import { useSpatialStore } from "@/store/spatialStore";
import type { SpatialObject } from "@/types/spatial";

/**
 * ProxyMeshes
 *
 * Real 3D invisible/highlightable proxy meshes for click-to-inspect and query lighting.
 *
 * Beginner Analogy:
 * Invisible glass cases placed around each real building:
 * You cannot easily tap a cloud of 60,000 tiny floating dots with your mouse cursor,
 * so we place an exact invisible 3D glass box over every building. When you click,
 * the computer checks which glass box you touched, lights it up, and displays its specs.
 *
 * Design Decisions implemented:
 * - D8: Invisible proxy meshes extruded from GeoJSON footprints for raycasting, selection, and query highlighting.
 * - D11: Child of sceneRoot (Z-up coordinate frame, ground at z=0).
 */

export function ProxyMeshes() {
  const groupRef = useRef<THREE.Group>(null);
  const meshMapRef = useRef<Map<string, THREE.Mesh>>(new Map());
  const hoveredIdRef = useRef<string | null>(null);

  const {
    objects,
    selectedObjectId,
    setSelectedObjectId,
    setHoveredObjectId,
    highlightedObjectIds,
    queryFilterActive,
    layerVisibility,
    soloLayerId,
  } = useSpatialStore();

  const { camera, gl } = useThree();

  // 1. Build Extruded 3D Footprint Geometries
  useEffect(() => {
    if (!groupRef.current) return;

    // Clear existing meshes
    while (groupRef.current.children.length > 0) {
      const child = groupRef.current.children[0] as THREE.Mesh;
      if (child.geometry) child.geometry.dispose();
      groupRef.current.remove(child);
    }
    meshMapRef.current.clear();

    if (!objects || objects.length === 0) return;

    objects.forEach((obj: SpatialObject) => {
      let geometry: THREE.BufferGeometry;
      let posX = 0;
      let posY = 0;
      let posZ = 0;

      // Try creating exact extruded polygon from GeoJSON footprint
      const coords = obj.footprint?.coordinates?.[0];
      if (Array.isArray(coords) && coords.length >= 3) {
        const shape = new THREE.Shape();
        shape.moveTo(coords[0][0], coords[0][1]);
        for (let i = 1; i < coords.length; i++) {
          shape.lineTo(coords[i][0], coords[i][1]);
        }
        // Extrude along Z axis by height in meters
        geometry = new THREE.ExtrudeGeometry(shape, {
          depth: Math.max(1.0, obj.height),
          bevelEnabled: false,
        });
        posZ = obj.elevationM || 0;
      } else {
        // Fallback: Box geometry in scene frame (X, Y horizontal, Z up)
        const w = Math.max(2.0, obj.width);
        const d = Math.max(2.0, obj.depth);
        const h = Math.max(1.0, obj.height);
        geometry = new THREE.BoxGeometry(w, d, h);
        posX = obj.x;
        posY = obj.z; // In scene frame, Y is the other horizontal axis
        posZ = (obj.elevationM || 0) + h / 2.0;
      }

      // Default subtle translucent material (invisible to viewer, but raycastable)
      const material = new THREE.MeshStandardMaterial({
        color: 0x38bdf8,
        transparent: true,
        opacity: 0.05,
        roughness: 0.2,
        metalness: 0.1,
        depthWrite: false,
      });

      const mesh = new THREE.Mesh(geometry, material);
      mesh.position.set(posX, posY, posZ);
      mesh.userData = { objectId: obj.id, object: obj };
      mesh.name = `proxy-${obj.id}`;

      groupRef.current?.add(mesh);
      meshMapRef.current.set(obj.id, mesh);
    });
  }, [objects]);

  // 2. Click-to-Inspect Raycasting
  useEffect(() => {
    const canvas = gl.domElement;
    if (!canvas) return;

    const raycaster = new THREE.Raycaster();
    const mouse = new THREE.Vector2();
    let downPos = { x: 0, y: 0 };

    const handlePointerDown = (e: MouseEvent) => {
      downPos = { x: e.clientX, y: e.clientY };
    };

    const handleClick = (e: MouseEvent) => {
      // Only process left clicks
      if (e.button !== 0 || !groupRef.current) return;

      // If user was dragging to orbit/pan, ignore click
      const dragDist = Math.hypot(e.clientX - downPos.x, e.clientY - downPos.y);
      if (dragDist > 6) return;

      const rect = canvas.getBoundingClientRect();
      mouse.x = ((e.clientX - rect.left) / rect.width) * 2 - 1;
      mouse.y = -((e.clientY - rect.top) / rect.height) * 2 + 1;

      raycaster.setFromCamera(mouse, camera);
      const intersects = raycaster.intersectObjects(groupRef.current.children, true);

      if (intersects.length > 0 && intersects[0]) {
        const hitMesh = intersects[0].object as THREE.Mesh;
        const hitId = hitMesh.userData?.["objectId"];
        if (hitId) {
          console.log(`[ProxyMeshes] Selected structure #${hitId}`);
          setSelectedObjectId(hitId);
        }
      } else {
        // Clicked background -> deselect
        setSelectedObjectId(null);
      }
    };

    const handlePointerMove = (e: MouseEvent) => {
      if (!groupRef.current) return;
      const rect = canvas.getBoundingClientRect();
      mouse.x = ((e.clientX - rect.left) / rect.width) * 2 - 1;
      mouse.y = -((e.clientY - rect.top) / rect.height) * 2 + 1;

      raycaster.setFromCamera(mouse, camera);
      const intersects = raycaster.intersectObjects(groupRef.current.children, true);

      if (intersects.length > 0 && intersects[0]) {
        const hitMesh = intersects[0].object as THREE.Mesh;
          hoveredIdRef.current = hitMesh.userData?.["objectId"] || null;
          setHoveredObjectId(hoveredIdRef.current);
          canvas.style.cursor = "pointer";
      } else {
        hoveredIdRef.current = null;
        setHoveredObjectId(null);
        canvas.style.cursor = "default";
      }
    };

    canvas.addEventListener("mousedown", handlePointerDown);
    canvas.addEventListener("click", handleClick);
    canvas.addEventListener("mousemove", handlePointerMove);

    return () => {
      canvas.removeEventListener("mousedown", handlePointerDown);
      canvas.removeEventListener("click", handleClick);
      canvas.removeEventListener("mousemove", handlePointerMove);
    };
  }, [camera, gl, setHoveredObjectId, setSelectedObjectId]);

  // 3. Highlight & State Updates per Frame
  useFrame(() => {
    if (!groupRef.current) return;

    const isBuildingsVisible = soloLayerId
      ? soloLayerId === "buildings"
      : layerVisibility.buildings ?? true;

    meshMapRef.current.forEach((mesh, objectId) => {
      const mat = mesh.material as THREE.MeshStandardMaterial;
      if (!mat) return;

      if (!isBuildingsVisible) {
        mesh.visible = false;
        return;
      }
      mesh.visible = true;

      const isSelected = selectedObjectId === objectId;
      const isHighlighted = highlightedObjectIds.includes(objectId);
      const isHovered = hoveredIdRef.current === objectId;

      if (queryFilterActive && !isHighlighted) {
        mesh.visible = false;
        return;
      }

      if (isSelected) {
        // Bright cyan/blue selection glow
        mat.color.setHex(0x06b6d4);
        mat.emissive.setHex(0x0284c7);
        mat.emissiveIntensity = 0.8;
        mat.opacity = 0.45;
        mat.wireframe = false;
      } else if (isHighlighted) {
        // Query results: Radiant Golden/Amber Glow
        mat.color.setHex(0xf59e0b);
        mat.emissive.setHex(0xd97706);
        mat.emissiveIntensity = 0.9;
        mat.opacity = 0.55;
        mat.wireframe = false;
      } else if (isHovered) {
        // Hover state
        mat.color.setHex(0x38bdf8);
        mat.emissive.setHex(0x0284c7);
        mat.emissiveIntensity = 0.4;
        mat.opacity = 0.25;
        mat.wireframe = false;
      } else {
        // Default subtle state
        mat.color.setHex(0x38bdf8);
        mat.emissive.setHex(0x000000);
        mat.emissiveIntensity = 0.0;
        mat.opacity = 0.04;
        mat.wireframe = false;
      }
    });
  });

  return <group ref={groupRef} name="proxyMeshes" />;
}

/** Renders the currently hovered building's measured attributes inside the 3D scene. */
export function HoveredObjectDetails() {
  const { hoveredObjectId, getSelectedObject } = useSpatialStore();
  const object = getSelectedObject();
  const hovered = useSpatialStore((state) => state.objects.find((item) => item.id === hoveredObjectId));
  if (!hovered || object?.id === hovered.id) return null;
  const volume = (hovered.areaM2 || hovered.width * hovered.depth) * hovered.height;
  return (
    <Html
      position={[hovered.x, hovered.elevationM + hovered.height, hovered.z]}
      center
      distanceFactor={12}
      zIndexRange={[20, 0]}
    >
      <div className="pointer-events-none min-w-44 rounded-lg border border-cyan-400/60 bg-slate-950/95 px-3 py-2 text-[10px] text-slate-100 shadow-xl backdrop-blur">
        <div className="mb-1 font-semibold text-cyan-300">{hovered.label}</div>
        <div className="grid grid-cols-2 gap-x-3 gap-y-0.5 font-mono">
          <span>Height</span><strong>{hovered.height.toFixed(1)} m</strong>
          <span>Length</span><strong>{hovered.width.toFixed(1)} m</strong>
          <span>Width</span><strong>{hovered.depth.toFixed(1)} m</strong>
          <span>Area</span><strong>{hovered.areaM2.toFixed(1)} m²</strong>
          <span>Volume</span><strong>{volume.toFixed(1)} m³</strong>
          <span>Region</span><strong>{hovered.region?.toUpperCase() || "—"}</strong>
        </div>
      </div>
    </Html>
  );
}
