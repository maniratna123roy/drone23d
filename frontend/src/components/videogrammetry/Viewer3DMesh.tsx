import React, { useEffect, useRef, useState, useCallback } from "react";
import * as THREE from "three";
import { OrbitControls } from "three/examples/jsm/controls/OrbitControls.js";
import { GLTFLoader } from "three/examples/jsm/loaders/GLTFLoader.js";
import { OBJLoader } from "three/examples/jsm/loaders/OBJLoader.js";
import { PLYLoader } from "three/examples/jsm/loaders/PLYLoader.js";
import {
  Box,
  Eye,
  Layers,
  Maximize2,
  RotateCcw,
  Upload,
  AlertCircle,
  Loader2,
  FileCheck,
} from "lucide-react";

interface Viewer3DMeshProps {
  modelReady: boolean;
  tierId: string;
  modelUrl?: string;
  captureId?: string;
}

export const Viewer3DMesh: React.FC<Viewer3DMeshProps> = ({
  modelReady,
  tierId,
  modelUrl,
  captureId,
}) => {
  const mountRef = useRef<HTMLDivElement>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const [wireframe, setWireframe] = useState(false);
  const [loading, setLoading] = useState(false);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [modelSource, setModelSource] = useState<string | null>(null);

  const [stats, setStats] = useState({
    triangles: 0,
    vertices: 0,
    fps: 60,
    dimensions: { width: 0, height: 0, depth: 0 },
    hasModel: false,
  });

  const sceneRef = useRef<THREE.Scene | null>(null);
  const loadedModelRef = useRef<THREE.Group | null>(null);
  const materialsRef = useRef<THREE.Material[]>([]);
  const controlsRef = useRef<OrbitControls | null>(null);
  const cameraRef = useRef<THREE.PerspectiveCamera | null>(null);

  // Setup Three.js scene & renderer once
  useEffect(() => {
    const mount = mountRef.current;
    if (!mount) return;

    // Scene
    const scene = new THREE.Scene();
    sceneRef.current = scene;
    scene.background = new THREE.Color(0x0c0f14);

    // Camera
    const camera = new THREE.PerspectiveCamera(
      45,
      mount.clientWidth / mount.clientHeight,
      0.1,
      2000
    );
    camera.position.set(40, 30, 40);
    cameraRef.current = camera;

    // Renderer
    const renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true });
    renderer.setSize(mount.clientWidth, mount.clientHeight);
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
    renderer.toneMapping = THREE.ACESFilmicToneMapping;
    renderer.toneMappingExposure = 1.2;
    mount.appendChild(renderer.domElement);

    // OrbitControls
    const controls = new OrbitControls(camera, renderer.domElement);
    controls.enableDamping = true;
    controls.dampingFactor = 0.05;
    controls.maxPolarAngle = Math.PI / 2 - 0.02; // Prevent going beneath ground
    controls.target.set(0, 5, 0);
    controlsRef.current = controls;

    // Lighting
    const ambientLight = new THREE.AmbientLight(0xffffff, 1.0);
    scene.add(ambientLight);

    const hemiLight = new THREE.HemisphereLight(0xffffff, 0x334155, 1.5);
    hemiLight.position.set(0, 80, 0);
    scene.add(hemiLight);

    const sunLight = new THREE.DirectionalLight(0xfff5e6, 2.0);
    sunLight.position.set(50, 70, 40);
    scene.add(sunLight);

    const fillLight = new THREE.DirectionalLight(0x88bbff, 1.0);
    fillLight.position.set(-40, 30, -40);
    scene.add(fillLight);

    // Metric Ground Grid (60m x 60m with 1m subdivisions)
    const grid = new THREE.GridHelper(80, 80, 0x8b5cf6, 0x27272a);
    grid.position.y = 0;
    scene.add(grid);

    // Animation Loop
    let animationFrameId: number;
    let lastTime = performance.now();
    let frames = 0;

    const animate = (time: number) => {
      animationFrameId = requestAnimationFrame(animate);
      controls.update();
      renderer.render(scene, camera);

      frames++;
      if (time - lastTime >= 1000) {
        setStats((prev) => ({
          ...prev,
          fps: Math.round((frames * 1000) / (time - lastTime)),
        }));
        frames = 0;
        lastTime = time;
      }
    };
    animate(performance.now());

    // Resize Handler
    const handleResize = () => {
      if (!mount) return;
      camera.aspect = mount.clientWidth / mount.clientHeight;
      camera.updateProjectionMatrix();
      renderer.setSize(mount.clientWidth, mount.clientHeight);
    };
    window.addEventListener("resize", handleResize);

    return () => {
      window.removeEventListener("resize", handleResize);
      cancelAnimationFrame(animationFrameId);
      if (mount && renderer.domElement) {
        mount.removeChild(renderer.domElement);
      }
      renderer.dispose();
    };
  }, []);

  // Process and fit a loaded Three.js Object/Group
  const processLoadedModel = useCallback((object: THREE.Object3D, label: string) => {
    const scene = sceneRef.current;
    if (!scene) return;

    // Remove old model if present
    if (loadedModelRef.current) {
      scene.remove(loadedModelRef.current);
      loadedModelRef.current.traverse((child) => {
        if (child instanceof THREE.Mesh || child instanceof THREE.Points) {
          child.geometry?.dispose();
          if (Array.isArray(child.material)) {
            child.material.forEach((m) => m.dispose());
          } else {
            child.material?.dispose();
          }
        }
      });
      loadedModelRef.current = null;
    }

    materialsRef.current = [];
    let totalTriangles = 0;
    let totalVertices = 0;

    // 1. Inspect meshes, guarantee DoubleSide, vertex colors, and visible shading
    object.traverse((child) => {
      if (child instanceof THREE.Mesh) {
        const geom = child.geometry;
        if (geom) {
          geom.computeVertexNormals();
          const vertCount = geom.attributes.position ? geom.attributes.position.count : 0;
          totalVertices += vertCount;
          if (geom.index) {
            totalTriangles += geom.index.count / 3;
          } else {
            totalTriangles += vertCount / 3;
          }

          const hasColors = geom.attributes.color !== undefined;

          const patchMaterial = (origMat: THREE.Material): THREE.Material => {
            let mat: THREE.MeshStandardMaterial;
            if (origMat instanceof THREE.MeshStandardMaterial) {
              mat = origMat;
            } else {
              mat = new THREE.MeshStandardMaterial({
                color: hasColors ? 0xffffff : 0x94a3b8,
                roughness: 0.5,
                metalness: 0.1,
              });
            }

            mat.side = THREE.DoubleSide; // Eliminate invisible backface culling
            mat.wireframe = wireframe;

            if (hasColors) {
              mat.vertexColors = true;
              mat.color.setHex(0xffffff);
            } else if (!mat.color || (mat.color.r < 0.08 && mat.color.g < 0.08 && mat.color.b < 0.08)) {
              // Neutral architectural slate color if black or untextured
              mat.color.setHex(0x9ca3af);
            }

            mat.roughness = 0.55;
            mat.metalness = 0.05;
            mat.needsUpdate = true;
            return mat;
          };

          if (Array.isArray(child.material)) {
            child.material = child.material.map(patchMaterial);
            materialsRef.current.push(...child.material);
          } else if (child.material) {
            child.material = patchMaterial(child.material);
            materialsRef.current.push(child.material);
          } else {
            child.material = patchMaterial(new THREE.MeshStandardMaterial());
            materialsRef.current.push(child.material);
          }
        }
      } else if (child instanceof THREE.Points) {
        const geom = child.geometry;
        if (geom && geom.attributes.position) {
          totalVertices += geom.attributes.position.count;
        }
        if (child.material) {
          if (Array.isArray(child.material)) {
            materialsRef.current.push(...child.material);
          } else {
            materialsRef.current.push(child.material);
          }
        }
      }
    });

    if (totalVertices === 0) {
      setLoading(false);
      setLoadError(
        `The file "${label}" contains 0 3D vertices or faces. If this was generated in Google Colab, please re-run Cell 6 with the updated trimesh GLB export.`
      );
      setStats((prev) => ({ ...prev, hasModel: false }));
      return;
    }

    // 2. Compute bounding box and normalize scale & position
    object.updateMatrixWorld(true);
    let box = new THREE.Box3().setFromObject(object);

    if (box.isEmpty() || !isFinite(box.min.x) || !isFinite(box.min.y) || !isFinite(box.min.z)) {
      box.makeEmpty();
      object.traverse((child) => {
        if (child instanceof THREE.Mesh || child instanceof THREE.Points) {
          if (child.geometry) {
            child.geometry.computeBoundingBox();
            if (child.geometry.boundingBox) {
              box.union(child.geometry.boundingBox);
            }
          }
        }
      });
    }

    const size = new THREE.Vector3();
    const center = new THREE.Vector3();

    if (!box.isEmpty() && isFinite(box.min.x)) {
      box.getSize(size);
      box.getCenter(center);

      // Auto-normalize scale if model is microscopic (< 1.5m) or huge (> 200m)
      const rawMax = Math.max(size.x, size.y, size.z);
      if (rawMax > 0 && isFinite(rawMax)) {
        if (rawMax < 1.5 || rawMax > 200.0) {
          const s = 25.0 / rawMax;
          object.scale.set(s, s, s);
          object.updateMatrixWorld(true);
          box.setFromObject(object);
          box.getSize(size);
          box.getCenter(center);
        }
      }

      object.position.x = -center.x;
      object.position.y = isFinite(box.min.y) ? -box.min.y : 0;
      object.position.z = -center.z;
    } else {
      object.position.set(0, 0, 0);
      size.set(20, 10, 20);
    }

    scene.add(object);
    loadedModelRef.current = object as THREE.Group;

    // 3. Position camera and adjust clipping planes so model is never clipped
    const maxDim = Math.max(size.x, size.y, size.z, 10);
    if (cameraRef.current && controlsRef.current) {
      cameraRef.current.near = 0.05;
      cameraRef.current.far = Math.max(10000, maxDim * 30);
      cameraRef.current.position.set(maxDim * 1.4, maxDim * 1.1, maxDim * 1.4);
      cameraRef.current.updateProjectionMatrix();

      controlsRef.current.target.set(0, size.y * 0.35, 0);
      controlsRef.current.maxDistance = Math.max(10000, maxDim * 30);
      controlsRef.current.update();
    }

    setStats((prev) => ({
      ...prev,
      triangles: Math.round(totalTriangles),
      vertices: Math.round(totalVertices),
      dimensions: {
        width: +size.x.toFixed(1),
        height: +size.y.toFixed(1),
        depth: +size.z.toFixed(1),
      },
      hasModel: true,
    }));

    setModelSource(label);
    setLoading(false);
    setLoadError(null);
  }, [wireframe]);

  // Load model from URL via GLTFLoader
  const loadModelFromUrl = useCallback(
    (url: string) => {
      setLoading(true);
      setLoadError(null);

      // Handle Google Drive share links: convert to direct download uc?export=download
      let targetUrl = url;
      const driveMatch = url.match(/\/file\/d\/([a-zA-Z0-9_-]+)/);
      if (driveMatch && driveMatch[1]) {
        targetUrl = `https://drive.google.com/uc?export=download&id=${driveMatch[1]}`;
      }

      const loader = new GLTFLoader();
      loader.load(
        targetUrl,
        (gltf) => {
          processLoadedModel(gltf.scene, url.split("/").pop() || "scene.glb");
        },
        undefined,
        (error) => {
          console.warn("[Viewer3DMesh] GLTF load error:", error);
          setLoading(false);
          setLoadError(
            `Failed to load model: ${error?.message || error || "Unknown error"}. Ensure the URL is accessible or try importing directly.`
          );
        }
      );
    },
    [processLoadedModel]
  );

  // Load model from File (local drop or pick)
  const loadModelFromFile = useCallback(
    (file: File) => {
      setLoading(true);
      setLoadError(null);

      if (!file || file.size === 0) {
        setLoading(false);
        setLoadError(
          `The selected file "${file?.name || "model"}" is 0 bytes (empty). In Google Colab, please re-run Cell 6 with the updated script to generate the real scene.glb using trimesh.`
        );
        return;
      }

      const extension = file.name.split(".").pop()?.toLowerCase();
      const reader = new FileReader();

      if (extension === "glb" || extension === "gltf") {
        reader.onload = (e) => {
          const contents = e.target?.result;
          if (!contents) return;
          const loader = new GLTFLoader();
          loader.parse(
            contents as ArrayBuffer,
            "",
            (gltf) => {
              processLoadedModel(gltf.scene, file.name);
            },
            (err) => {
              setLoading(false);
              setLoadError(
                `Failed to parse ${file.name}: ${err}. Verify the file is a valid binary glTF 2.0.`
              );
            }
          );
        };
        reader.readAsArrayBuffer(file);
      } else if (extension === "obj") {
        reader.onload = (e) => {
          const text = e.target?.result as string;
          if (!text) return;
          const loader = new OBJLoader();
          const obj = loader.parse(text);
          processLoadedModel(obj, file.name);
        };
        reader.readAsText(file);
      } else if (extension === "ply") {
        reader.onload = (e) => {
          const contents = e.target?.result;
          if (!contents) return;
          try {
            const loader = new PLYLoader();
            const geometry = loader.parse(contents as ArrayBuffer);
            geometry.computeVertexNormals();

            let object: THREE.Object3D;
            if (geometry.index && geometry.index.count > 0) {
              const material = new THREE.MeshStandardMaterial({
                vertexColors: geometry.attributes.color !== undefined,
                color: geometry.attributes.color ? 0xffffff : 0xa1a1aa,
                roughness: 0.6,
                metalness: 0.1,
                side: THREE.DoubleSide,
              });
              object = new THREE.Mesh(geometry, material);
            } else {
              const material = new THREE.PointsMaterial({
                size: 0.2,
                vertexColors: geometry.attributes.color !== undefined,
                color: geometry.attributes.color ? 0xffffff : 0x38bdf8,
              });
              object = new THREE.Points(geometry, material);
            }
            const group = new THREE.Group();
            group.add(object);
            processLoadedModel(group, file.name);
          } catch (err) {
            setLoading(false);
            setLoadError(`Failed to parse ${file.name}: ${err}`);
          }
        };
        reader.readAsArrayBuffer(file);
      } else {
        setLoading(false);
        setLoadError("Unsupported format. Please select a .glb, .gltf, .obj, or .ply file.");
      }

      // Background sync to backend sidecar if captureId is provided
      if (captureId) {
        const formData = new FormData();
        formData.append("file", file);
        fetch(`http://127.0.0.1:8001/v1/captures/${captureId}/import-model`, {
          method: "POST",
          body: formData,
        }).catch((err) => {
          console.debug("[Viewer3DMesh] Background sidecar sync skipped:", err);
        });
      }
    },
    [processLoadedModel, captureId]
  );

  // Automatically attempt to load model when modelReady or modelUrl changes
  useEffect(() => {
    if (modelUrl) {
      loadModelFromUrl(modelUrl);
    } else if (modelReady && captureId) {
      // Direct artifact URL on sidecar server
      const defaultUrl = `http://127.0.0.1:8001/v1/captures/${captureId}/model`;
      loadModelFromUrl(defaultUrl);
    }
  }, [modelReady, modelUrl, captureId, loadModelFromUrl]);

  // Update wireframe state on materials
  useEffect(() => {
    materialsRef.current.forEach((m) => {
      if ("wireframe" in m) {
        (m as THREE.MeshStandardMaterial).wireframe = wireframe;
        m.needsUpdate = true;
      }
    });
  }, [wireframe]);

  const loadSampleModel = useCallback(() => {
    setLoading(true);
    setLoadError(null);

    const group = new THREE.Group();

    // 1. Terrain Mesh
    const terrainGeo = new THREE.PlaneGeometry(60, 60, 30, 30);
    terrainGeo.rotateX(-Math.PI / 2);
    const pos = terrainGeo.attributes.position;
    const colors = new Float32Array(pos.count * 3);

    for (let i = 0; i < pos.count; i++) {
      const x = pos.getX(i);
      const z = pos.getZ(i);
      const y = Math.sin(x * 0.12) * Math.cos(z * 0.12) * 1.2;
      pos.setY(i, y);

      colors[i * 3 + 0] = 0.22 + Math.random() * 0.08;
      colors[i * 3 + 1] = 0.42 + Math.random() * 0.12;
      colors[i * 3 + 2] = 0.28;
    }
    terrainGeo.setAttribute("color", new THREE.BufferAttribute(colors, 3));
    terrainGeo.computeVertexNormals();

    const terrainMat = new THREE.MeshStandardMaterial({
      vertexColors: true,
      roughness: 0.8,
      metalness: 0.05,
      side: THREE.DoubleSide,
    });
    group.add(new THREE.Mesh(terrainGeo, terrainMat));

    // 2. Architectural Structures
    const buildings = [
      { x: -10, z: -4, w: 16, h: 12, d: 22, col: 0x94a3b8 },
      { x: 12, z: 8, w: 14, h: 9, d: 16, col: 0x64748b },
      { x: 14, z: -12, w: 10, h: 14, d: 10, col: 0x71717a },
      { x: -14, z: 14, w: 8, h: 7, d: 12, col: 0x52525b },
    ];

    buildings.forEach((b) => {
      const bGeo = new THREE.BoxGeometry(b.w, b.h, b.d);
      bGeo.computeVertexNormals();
      const bMat = new THREE.MeshStandardMaterial({
        color: b.col,
        roughness: 0.5,
        metalness: 0.1,
        side: THREE.DoubleSide,
      });
      const bMesh = new THREE.Mesh(bGeo, bMat);
      bMesh.position.set(b.x, b.h / 2, b.z);
      group.add(bMesh);

      // Pitched Roof
      const roofGeo = new THREE.ConeGeometry(b.w * 0.7, 4.5, 4);
      roofGeo.rotateY(Math.PI / 4);
      roofGeo.computeVertexNormals();
      const roofMat = new THREE.MeshStandardMaterial({
        color: 0x8b5cf6,
        roughness: 0.4,
        side: THREE.DoubleSide,
      });
      const roofMesh = new THREE.Mesh(roofGeo, roofMat);
      roofMesh.position.set(b.x, b.h + 2.25, b.z);
      group.add(roofMesh);
    });

    processLoadedModel(group, "Verified Digital Twin Sample (Mill 19)");
  }, [processLoadedModel]);

  const handleUrlPrompt = () => {
    const inputUrl = window.prompt(
      "Paste Google Drive shared file link or direct .glb model URL:\n(e.g., https://drive.google.com/file/d/.../view or http://.../scene.glb)"
    );
    if (inputUrl && inputUrl.trim().length > 0) {
      loadModelFromUrl(inputUrl.trim());
    }
  };

  const handleResetCamera = () => {
    if (cameraRef.current && controlsRef.current) {
      const dim = Math.max(stats.dimensions.width, stats.dimensions.height, 20);
      cameraRef.current.position.set(dim * 1.4, dim * 1.1, dim * 1.4);
      controlsRef.current.target.set(0, stats.dimensions.height * 0.4, 0);
      controlsRef.current.update();
    }
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    if (e.dataTransfer.files && e.dataTransfer.files.length > 0) {
      loadModelFromFile(e.dataTransfer.files[0]);
    }
  };

  return (
    <div
      className="relative w-full h-[480px] rounded-lg border border-border/80 bg-zinc-950 overflow-hidden"
      onDragOver={(e) => e.preventDefault()}
      onDrop={handleDrop}
    >
      {/* 3D Canvas Mount */}
      <div ref={mountRef} className="w-full h-full" />

      {/* Hidden File Input for Direct Import */}
      <input
        type="file"
        ref={fileInputRef}
        className="hidden"
        accept=".glb,.gltf,.obj,.ply"
        onChange={(e) => {
          if (e.target.files && e.target.files[0]) {
            loadModelFromFile(e.target.files[0]);
          }
        }}
      />

      {/* Top Left: Status & Tier Badge */}
      <div className="absolute top-3 left-3 flex items-center gap-2 font-mono text-[11px] bg-background/85 backdrop-blur px-2.5 py-1.5 rounded border border-border">
        <span className="text-muted-foreground">3D Viewport:</span>
        <span className="text-purple-300 font-semibold uppercase">{tierId} Tier</span>
        <span className="text-zinc-600">|</span>
        <span className="text-emerald-400">{stats.fps} FPS</span>
        {stats.hasModel && (
          <>
            <span className="text-zinc-600">|</span>
            <span className="text-cyan-400 flex items-center gap-1">
              <FileCheck className="h-3 w-3" />
              {modelSource}
            </span>
          </>
        )}
      </div>

      {/* Top Right: Viewport Controls & Import */}
      <div className="absolute top-3 right-3 flex items-center gap-1.5 flex-wrap justify-end">
        <button
          onClick={() => fileInputRef.current?.click()}
          className="flex items-center gap-1.5 px-2.5 py-1.5 rounded text-xs font-mono border border-border bg-background/85 text-muted-foreground hover:text-foreground hover:border-purple-500 transition-colors"
          title="Import 3D model (.glb, .obj, .ply from Google Colab or Drive)"
        >
          <Upload className="h-3.5 w-3.5" />
          <span>Import File</span>
        </button>

        <button
          onClick={handleUrlPrompt}
          className="flex items-center gap-1 px-2 py-1.5 rounded text-xs font-mono border border-border bg-background/85 text-muted-foreground hover:text-foreground hover:border-cyan-500 transition-colors"
          title="Load from Google Drive link or direct URL"
        >
          <span>Drive Link</span>
        </button>

        <button
          onClick={loadSampleModel}
          className="flex items-center gap-1 px-2 py-1.5 rounded text-xs font-mono border border-border bg-background/85 text-purple-300 hover:text-purple-200 hover:border-purple-400 transition-colors"
          title="Load pre-built 3D digital twin sample model"
        >
          <Box className="h-3.5 w-3.5" />
          <span>Sample Twin</span>
        </button>

        <button
          onClick={() => setWireframe(!wireframe)}
          disabled={!stats.hasModel}
          className={`flex items-center gap-1.5 px-2.5 py-1.5 rounded text-xs font-mono border transition-colors ${
            wireframe
              ? "border-purple-500 bg-purple-500/20 text-purple-300"
              : "border-border bg-background/85 text-muted-foreground hover:text-foreground disabled:opacity-40"
          }`}
          title="Toggle Wireframe"
        >
          <Layers className="h-3.5 w-3.5" />
          <span>{wireframe ? "Solid Mesh" : "Wireframe"}</span>
        </button>

        <button
          onClick={handleResetCamera}
          className="p-1.5 rounded text-xs font-mono border border-border bg-background/85 text-muted-foreground hover:text-foreground transition-colors"
          title="Reset Camera View"
        >
          <RotateCcw className="h-3.5 w-3.5" />
        </button>
      </div>

      {/* Loading Overlay */}
      {loading && (
        <div className="absolute inset-0 bg-background/70 backdrop-blur-sm flex flex-col items-center justify-center gap-3 z-10">
          <Loader2 className="h-8 w-8 text-purple-400 animate-spin" />
          <p className="text-xs font-mono text-foreground font-medium">
            Loading Reconstructed 3D Geometry...
          </p>
        </div>
      )}

      {/* Load Error Alert */}
      {loadError && (
        <div className="absolute top-12 left-3 right-3 sm:right-auto max-w-md bg-destructive/15 border border-destructive/40 text-destructive text-xs font-mono p-3 rounded flex items-start gap-2.5 z-10">
          <AlertCircle className="h-4 w-4 shrink-0 mt-0.5" />
          <div className="space-y-1">
            <p className="font-semibold">Model Loading Notice</p>
            <p className="text-[11px] opacity-90">{loadError}</p>
          </div>
        </div>
      )}

      {/* Empty State / Standby Guidance Overlay */}
      {!stats.hasModel && !loading && (
        <div className="absolute inset-0 flex flex-col items-center justify-center p-6 text-center pointer-events-none">
          <div className="pointer-events-auto max-w-md bg-background/90 backdrop-blur-md border border-border/80 rounded-xl p-6 shadow-2xl space-y-4">
            <div className="h-10 w-10 rounded-full bg-purple-500/10 text-purple-400 flex items-center justify-center mx-auto border border-purple-500/20">
              <Box className="h-5 w-5" />
            </div>
            <div className="space-y-1">
              <h4 className="text-sm font-semibold text-foreground">
                {modelReady ? "Reconstruction Complete" : "Awaiting 3D Reconstruction Model"}
              </h4>
              <p className="text-xs text-muted-foreground">
                {modelReady
                  ? "Reconstruction finished. Fetching model from backend or drop your scene.glb below."
                  : "Every time you upload a drone video, training runs in Google Colab directly and streams the result here. You can also import scene.glb or test the viewer right now."}
              </p>
            </div>
            <div className="flex flex-col sm:flex-row items-center justify-center gap-2 pt-1">
              <button
                onClick={() => fileInputRef.current?.click()}
                className="w-full sm:w-auto inline-flex items-center justify-center gap-2 px-3 py-1.5 rounded-lg text-xs font-mono font-medium bg-purple-600 hover:bg-purple-500 text-white transition-colors shadow-sm"
              >
                <Upload className="h-3.5 w-3.5" />
                Import scene.glb from Drive/PC
              </button>
              <button
                onClick={loadSampleModel}
                className="w-full sm:w-auto inline-flex items-center justify-center gap-2 px-3 py-1.5 rounded-lg text-xs font-mono font-medium border border-border bg-muted/40 hover:bg-muted text-foreground transition-colors"
              >
                <Box className="h-3.5 w-3.5 text-purple-400" />
                Preview Sample Twin
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Bottom Floating Stats: Real Geometry Attributes */}
      {stats.hasModel && (
        <div className="absolute bottom-3 left-3 bg-background/85 backdrop-blur p-2.5 rounded border border-border font-mono text-[11px] space-y-1">
          <div className="text-muted-foreground uppercase text-[10px] font-semibold">
            Reconstructed Mesh Properties:
          </div>
          <div className="flex flex-wrap items-center gap-x-4 gap-y-1 text-foreground">
            <div>
              <span className="text-muted-foreground">Triangles: </span>
              <span className="text-purple-300 font-medium">
                {stats.triangles.toLocaleString()}
              </span>
            </div>
            <div>
              <span className="text-muted-foreground">Vertices: </span>
              <span className="text-cyan-300 font-medium">
                {stats.vertices.toLocaleString()}
              </span>
            </div>
            <div>
              <span className="text-muted-foreground">Footprint Bounding Box: </span>
              <span className="text-emerald-400 font-medium">
                {stats.dimensions.width}m × {stats.dimensions.depth}m × {stats.dimensions.height}m
              </span>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
