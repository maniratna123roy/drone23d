# ---
# Spatial Twin: 3D Gaussian Splatting Cloud Training Script (Google Colab / Kaggle)
# Run with a GPU runtime (Runtime > Change runtime type > T4 GPU)
# ---

# [Cell 1: Environment Setup & Dependencies]
"""
!pip install -q torch torchvision --index-url https://download.pytorch.org/whl/cu121
!pip install -q ninja imageio plyfile tqdm open3d
# Install gsplat library from nerfstudio
!pip install -q gsplat
"""

import os
import sys
import torch
print(f"CUDA Available: {torch.cuda.is_available()}")
if torch.cuda.is_available():
    print(f"GPU: {torch.cuda.get_device_name(0)}")
    print(f"Total VRAM: {round(torch.cuda.get_device_properties(0).total_memory / (1024**3), 2)} GB")

# [Cell 2: Dataset Download / Preparation]
# Here we prepare the drone images and camera poses (e.g. Mill-19 sample or custom drone dataset)
DATA_DIR = "./data/drone_scene"
OUTPUT_DIR = "./output/splat_model"
os.makedirs(DATA_DIR, exist_ok=True)
os.makedirs(OUTPUT_DIR, exist_ok=True)

# [Cell 3: Training 3D Gaussian Splatting]
# Using gsplat simple trainer or gaussian-splatting
"""
!python -m gsplat.examples.simple_trainer \
    --data_dir {DATA_DIR} \
    --result_dir {OUTPUT_DIR} \
    --max_steps 7000 \
    --eval_steps 1000 \
    --save_steps 7000
"""

# [Cell 4: Export to point_cloud.ply]
print("Reconstruction complete! Download the resulting 'point_cloud.ply' from the output directory.")
print("Place it in your local spatial-twin project under 'output/mill/point_cloud.ply'.")
