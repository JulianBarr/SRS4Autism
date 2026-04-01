import cv2
import numpy as np
import mediapipe as mp
from PIL import Image

# 1. 初始化 MediaPipe，必须开启 refine_landmarks 才能获取精准瞳孔
mp_face_mesh = mp.solutions.face_mesh.FaceMesh(
    static_image_mode=True, 
    refine_landmarks=True
)

def get_pupils(img_bgr):
    """提取双眼瞳孔中心的坐标"""
    h, w = img_bgr.shape[:2]
    res = mp_face_mesh.process(cv2.cvtColor(img_bgr, cv2.COLOR_BGR2RGB))
    if not res.multi_face_landmarks: 
        return None
    lm = res.multi_face_landmarks[0].landmark
    # 468: 右眼瞳孔中心 (画面左侧), 473: 左眼瞳孔中心 (画面右侧)
    return np.float32([[lm[468].x * w, lm[468].y * h], [lm[473].x * w, lm[473].y * h]])

def generate_aligned_gif(target_path, norm_path, output_path="aligned_toggle.gif"):
    # 2. 读取基准图 (均脸) 和 目标图 (爸爸)
    img_norm = cv2.imread(norm_path)
    img_target = cv2.imread(target_path)

    # 3. 提取双方的瞳孔坐标
    pts_norm = get_pupils(img_norm)
    pts_target = get_pupils(img_target)

    if pts_norm is None or pts_target is None:
        print("❌ 未能检测到瞳孔，请检查图片！")
        return

    # 4. 核心魔法：计算最优仿射变换矩阵 (只允许平移、缩放和旋转，不拉伸变形)
    M, _ = cv2.estimateAffinePartial2D(pts_target, pts_norm)

    # 5. 对目标图施加魔法，强行对齐到均脸的尺寸和位置
    h, w = img_norm.shape[:2]
    img_target_aligned = cv2.warpAffine(img_target, M, (w, h))

    # 6. 转为 PIL 格式并合成 GIF (0.5秒/帧)
    pil_norm = Image.fromarray(cv2.cvtColor(img_norm, cv2.COLOR_BGR2RGB))
    pil_target = Image.fromarray(cv2.cvtColor(img_target_aligned, cv2.COLOR_BGR2RGB))

    pil_norm.save(
        output_path, 
        save_all=True, 
        append_images=[pil_target], 
        duration=500, 
        loop=0
    )
    print(f"✅ 认知炸弹已生成！请打开查看：{output_path}")

if __name__ == '__main__':
    # 传入爸爸的护照照和中国男均脸
    generate_aligned_gif("passport_photo_zhouhui.jpeg", "average_chinese_man.png")
