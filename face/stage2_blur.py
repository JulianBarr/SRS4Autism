# 依赖库: pip install opencv-python mediapipe numpy
import cv2
import numpy as np
import mediapipe as mp

def stage_2_facial_isolation(input_path: str, output_path: str):
    # 1. 读取图像
    img = cv2.imread(input_path)
    if img is None:
        raise ValueError(f"无法读取图像: {input_path}")
    h, w = img.shape[:2]

    # 2. 初始化 MediaPipe Face Mesh
    mp_face_mesh = mp.solutions.face_mesh
    with mp_face_mesh.FaceMesh(static_image_mode=True, max_num_faces=1) as face_mesh:
        results = face_mesh.process(cv2.cvtColor(img, cv2.COLOR_BGR2RGB))
        if not results.multi_face_landmarks:
            raise ValueError("未检测到人脸")
        
        landmarks = results.multi_face_landmarks[0].landmark

        # 提取区域特征点的坐标数组并计算凸包
        def get_hull_points(connections):
            indices = set([idx for pair in connections for idx in pair])
            pts = np.array([[(int(landmarks[i].x * w), int(landmarks[i].y * h))] for i in indices])
            return cv2.convexHull(pts)

        # 获取左右眉眼的凸包
        left_hull = get_hull_points(list(mp_face_mesh.FACEMESH_LEFT_EYE) + list(mp_face_mesh.FACEMESH_LEFT_EYEBROW))
        right_hull = get_hull_points(list(mp_face_mesh.FACEMESH_RIGHT_EYE) + list(mp_face_mesh.FACEMESH_RIGHT_EYEBROW))

        # 3. 创建遮罩并绘制保留区
        mask = np.zeros((h, w), dtype=np.uint8)
        cv2.fillConvexPoly(mask, left_hull, 255)
        cv2.fillConvexPoly(mask, right_hull, 255)

        # 4. 遮罩羽化过渡 (Feathering) - 动态自适应分辨率的核大小
        dilate_k = max(3, (w // 40) | 1)
        mask = cv2.dilate(mask, np.ones((dilate_k, dilate_k), np.uint8), iterations=2)
        
        feather_k = max(31, (w // 10) | 1)
        mask = cv2.GaussianBlur(mask, (feather_k, feather_k), 0)
        mask_3d = mask[:, :, np.newaxis] / 255.0

        # 5. 生成重度高斯模糊背景（强力遮挡嘴部与下半脸等动态干扰区）
        blur_k = max(51, (w // 5) | 1)
        blurred_bg = cv2.GaussianBlur(img, (blur_k, blur_k), 0)

        # 6. 图像Alpha融合并输出
        result = (img * mask_3d + blurred_bg * (1 - mask_3d)).astype(np.uint8)
        cv2.imwrite(output_path, result)

if __name__ == "__main__":
    # 使用示例：请确保同目录下存在 input.jpg 
    stage_2_facial_isolation("input.jpg", "output_stage2.jpg")
    pass
