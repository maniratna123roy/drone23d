import { useEffect, useMemo, useRef, useState } from "react";
import { useFrame, useThree } from "@react-three/fiber";
import * as THREE from "three";
import { projectGaussian, sortGaussiansBackToFront, type GaussianData } from "./gaussian-data";
import { semanticColor } from "./semantic-display";

interface SplatRendererProps {
  data: GaussianData;
  hiddenClasses?: readonly number[];
  semanticColors?: boolean;
  queryFilterActive?: boolean;
  visibleObjectBboxes?: readonly NonNullable<import("@/types/spatial").SpatialObject["splatBbox"]>[];
}

/** Real anisotropic Gaussians: source covariance -> projected ellipse -> depth-sorted alpha blending. */
export function SplatRenderer({
  data,
  hiddenClasses,
  semanticColors = false,
  queryFilterActive = false,
  visibleObjectBboxes = [],
}: SplatRendererProps) {
  const meshRef = useRef<THREE.Mesh>(null);
  const { invalidate, gl } = useThree();
  const [renderError, setRenderError] = useState<string | null>(null);
  useEffect(() => {
    const lost = () =>
      setRenderError("WebGL context was lost. Reload the page to restore the verified viewer");
    const previousShaderError = gl.debug.onShaderError;
    gl.debug.onShaderError = () =>
      setRenderError(
        "The browser could not compile the Gaussian shader. Check WebGL/hardware acceleration",
      );
    gl.domElement.addEventListener("webglcontextlost", lost);
    return () => {
      gl.domElement.removeEventListener("webglcontextlost", lost);
      gl.debug.onShaderError = previousShaderError;
    };
  }, [gl]);
  const resources = useMemo(() => {
    const geometry = new THREE.InstancedBufferGeometry();
    geometry.setAttribute(
      "position",
      new THREE.Float32BufferAttribute([-1, -1, 0, 1, -1, 0, 1, 1, 0, -1, 1, 0], 3),
    );
    geometry.setIndex([0, 1, 2, 0, 2, 3]);
    const center = new THREE.InstancedBufferAttribute(new Float32Array(data.count * 3), 3).setUsage(
      THREE.DynamicDrawUsage,
    );
    const axes = new THREE.InstancedBufferAttribute(new Float32Array(data.count * 4), 4).setUsage(
      THREE.DynamicDrawUsage,
    );
    const color = new THREE.InstancedBufferAttribute(new Float32Array(data.count * 4), 4).setUsage(
      THREE.DynamicDrawUsage,
    );
    geometry.setAttribute("splatCenter", center);
    geometry.setAttribute("splatAxes", axes);
    geometry.setAttribute("splatColor", color);
    geometry.instanceCount = 0;
    const material = new THREE.ShaderMaterial({
      vertexShader: `
        attribute vec3 splatCenter;
        attribute vec4 splatAxes;
        attribute vec4 splatColor;
        varying vec2 sigma;
        varying vec4 rgba;
        void main() {
          sigma = position.xy * 3.0;
          rgba = splatColor;
          vec2 offset = position.x * splatAxes.xy + position.y * splatAxes.zw;
          gl_Position = vec4(splatCenter.xy + offset, splatCenter.z, 1.0);
        }
      `,
      fragmentShader: `
        varying vec2 sigma;
        varying vec4 rgba;
        void main() {
          float radiusSquared = dot(sigma, sigma);
          if (radiusSquared > 9.0) discard;
          float alpha = min(0.99, rgba.a * exp(-0.5 * radiusSquared));
          if (alpha < 1.0 / 255.0) discard;
          gl_FragColor = vec4(rgba.rgb, alpha);
        }
      `,
      transparent: true,
      depthTest: false,
      depthWrite: false,
      blending: THREE.NormalBlending,
      // Exported RGB is already photograph/display encoded; do not relight or tone-map it.
      toneMapped: false,
    });
    return {
      geometry,
      material,
      center,
      axes,
      color,
      order: new Uint32Array(data.count),
      depths: new Float64Array(data.count),
      modelView: new THREE.Matrix4(),
      previousView: new THREE.Matrix4(),
      previousProjection: new THREE.Matrix4(),
      viewport: new THREE.Vector2(),
      projected: new Float64Array(7),
      width: 0,
      height: 0,
      initialized: false,
    };
  }, [data]);

  useEffect(() => {
    invalidate();
    return () => {
      resources.geometry.dispose();
      resources.material.dispose();
    };
  }, [resources, invalidate]);

  useEffect(() => {
    resources.initialized = false;
    invalidate();
  }, [hiddenClasses, semanticColors, queryFilterActive, visibleObjectBboxes, resources, invalidate]);

  useFrame(({ camera, gl }) => {
    const mesh = meshRef.current;
    if (!mesh || !(camera instanceof THREE.PerspectiveCamera)) return;
    camera.updateMatrixWorld();
    mesh.updateWorldMatrix(true, false);
    const r = resources;
    r.modelView.multiplyMatrices(camera.matrixWorldInverse, mesh.matrixWorld);
    gl.getDrawingBufferSize(r.viewport);
    const width = r.viewport.x,
      height = r.viewport.y;
    if (
      r.initialized &&
      r.previousView.equals(r.modelView) &&
      r.previousProjection.equals(camera.projectionMatrix) &&
      r.width === width &&
      r.height === height
    )
      return;
    r.previousView.copy(r.modelView);
    r.previousProjection.copy(camera.projectionMatrix);
    r.width = width;
    r.height = height;
    r.initialized = true;
    sortGaussiansBackToFront(data.positions, r.modelView.elements, r.order, r.depths);
    let visible = 0;
    for (const index of r.order) {
      if (hiddenClasses?.includes(data.classes[index]!)) continue;
      if (
        queryFilterActive &&
        data.classes[index] === 0 &&
        !visibleObjectBboxes.some(
          (bbox) =>
            data.positions[index * 3]! >= bbox.min_x &&
            data.positions[index * 3]! <= bbox.max_x &&
            data.positions[index * 3 + 1]! >= bbox.min_y &&
            data.positions[index * 3 + 1]! <= bbox.max_y &&
            data.positions[index * 3 + 2]! >= bbox.min_z &&
            data.positions[index * 3 + 2]! <= bbox.max_z,
        )
      ) continue;
      if (
        !projectGaussian(
          data,
          index,
          r.modelView.elements,
          camera.projectionMatrix.elements,
          width,
          height,
          camera.near,
          camera.far,
          r.projected,
        )
      )
        continue;
      r.center.setXYZ(visible, r.projected[0]!, r.projected[1]!, r.projected[2]!);
      r.axes.setXYZW(visible, r.projected[3]!, r.projected[4]!, r.projected[5]!, r.projected[6]!);
      const offset = index * 4;
      const tint = semanticColors ? semanticColor(data.classes[index]!) : null;
      r.color.setXYZW(
        visible,
        tint ? tint[0]! / 255 : data.colors[offset]!,
        tint ? tint[1]! / 255 : data.colors[offset + 1]!,
        tint ? tint[2]! / 255 : data.colors[offset + 2]!,
        data.colors[offset + 3]!,
      );
      visible++;
    }
    r.geometry.instanceCount = visible;
    r.center.needsUpdate = r.axes.needsUpdate = r.color.needsUpdate = true;
  });

  if (renderError) throw new Error(renderError);
  return (
    <mesh
      ref={meshRef}
      name="verifiedGaussianQuads"
      geometry={resources.geometry}
      material={resources.material}
      frustumCulled={false}
      dispose={null}
    />
  );
}
