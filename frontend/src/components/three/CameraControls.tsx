import { useEffect } from "react";
import * as THREE from "three";
import { useThree } from "@react-three/fiber";
import { OrbitControls } from "three/examples/jsm/controls/OrbitControls.js";
import type { VerifiedSceneManifest } from "@/types/spatial";

interface CameraControlsProps {
  sourceCamera: VerifiedSceneManifest["camera"];
  resetToken: number;
}

/** Start where a real source photograph was taken, with its real up direction and relative units. */
export function CameraControls({ sourceCamera, resetToken }: CameraControlsProps) {
  const { camera, gl, invalidate } = useThree();
  useEffect(() => {
    if (!(camera instanceof THREE.PerspectiveCamera)) return;
    // sceneRoot is identity for COLMAP_PHASE_A. Camera and Gaussians share exactly one frame.
    camera.position.fromArray(sourceCamera.position);
    camera.up.fromArray(sourceCamera.up).normalize();
    camera.fov = sourceCamera.fov_y_degrees;
    camera.near = sourceCamera.near;
    camera.far = sourceCamera.far;
    camera.updateProjectionMatrix();
    const controls = new OrbitControls(camera, gl.domElement);
    controls.target.fromArray(sourceCamera.target);
    controls.minDistance = sourceCamera.near;
    controls.maxDistance = sourceCamera.far;
    controls.enableDamping = false;
    controls.screenSpacePanning = true;
    controls.update();
    camera.updateMatrixWorld();
    const onChange = () => invalidate();
    controls.addEventListener("change", onChange);
    invalidate();
    return () => {
      controls.removeEventListener("change", onChange);
      controls.dispose();
    };
  }, [camera, gl, invalidate, sourceCamera, resetToken]);
  return null;
}
