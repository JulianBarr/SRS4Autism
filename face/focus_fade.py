import cv2
import numpy as np
import mediapipe as mp
from PIL import Image

mp_face_mesh = mp.solutions.face_mesh.FaceMesh(static_image_mode=True, refine_landmarks=True)

def get_landmarks_and_pupils(img_bgr):
    h, w = img_bgr.shape[:2]
    res = mp_face_mesh.process(cv2.cvtColor(img_bgr, cv2.COLOR_BGR2RGB))
    if not res.multi_face_landmarks: return None, None
    lm = res.multi_face_landmarks[0].landmark
    pupils = np.float32([[lm[468].x * w, lm[468].y * h], [lm[473].x * w, lm[473].y * h]])
    return lm, pupils

def apply_spotlight(img, landmarks, h, w):
    """给眉毛打上聚光灯，其余部分压暗"""
    mask = np.zeros((h, w), dtype=np.uint8)
    
    # 提取左右眉毛的轮廓外围节点
    left_eyebrow = [70, 63, 105, 66, 107, 55, 65, 52, 53, 46]
    right_eyebrow = [300, 293, 334, 296, 336, 285, 295, 282, 283, 276]
    
    left_pts = np.array([[(int(landmarks[i].x * w), int(landmarks[i].y * h))] for i in left_eyebrow])
    right_pts = np.array([[(int(landmarks[i].x * w), int(landmarks[i].y * h))] for i in right_eyebrow])
    
    # 在遮罩上画出眉毛区域并极度向外膨胀扩大光圈
    cv2.fillConvexPoly(mask, cv2.convexHull(left_pts), 255)
    cv2.fillConvexPoly(mask, cv2.convexHull(right_pts), 255)
    mask = cv2.dilate(mask, np.ones((w//10, w//10), np.uint8), iterations=1)
    mask = cv2.GaussianBlur(mask, (99, 99), 0) # 柔和边缘
    
    # 图像融合：聚光灯区域保持原亮度，其余区域降低至 30% 亮度
    mask_3d = mask[:, :, np.newaxis] / 255.0
    dimmed_img = img * 0.3
    focused_img = (img * mask_3d + dimmed_img * (1 - mask_3d)).astype(np.uint8)
    return focused_img

def generate_spotlight_fade(target_path, norm_path, output_path="spotlight_fade.gif"):
    img_norm = cv2.imread(norm_path)
    img_target = cv2.imread(target_path)

    lm_norm, pts_norm = get_landmarks_and_pupils(img_norm)
    lm_target, pts_target = get_landmarks_and_pupils(img_target)

    if pts_norm is None or pts_target is None:
        print("❌ 未能检测到人脸")
        return

    # 1. 仿射变换对齐目标图
    M, _ = cv2.estimateAffinePartial2D(pts_target, pts_norm)
    h, w = img_norm.shape[:2]
    img_target_aligned = cv2.warpAffine(img_target, M, (w, h))
    
    # 重新获取对齐后目标图的 landmarks 以便打光
    lm_target_aligned, _ = get_landmarks_and_pupils(img_target_aligned)

    # 2. 分别给均脸和对齐后的爸爸脸打上“眉毛聚光灯”
    focus_norm = apply_spotlight(img_norm, lm_norm, h, w)
    focus_target = apply_spotlight(img_target_aligned, lm_target_aligned, h, w)

    # 3. 生成平滑淡入淡出帧 (Alpha Blending)
    frames = []
    num_steps = 15 # 步数越多越丝滑
    
    # 均脸 -> 爸爸脸
    for alpha in np.linspace(0, 1, num_steps):
        blended = cv2.addWeighted(focus_target, alpha, focus_norm, 1 - alpha, 0)
        frames.append(Image.fromarray(cv2.cvtColor(blended, cv2.COLOR_BGR2RGB)))
        
    # 爸爸脸停留几帧
    frames.extend([frames[-1]] * 5)
    
    # 爸爸脸 -> 均脸
    for alpha in np.linspace(1, 0, num_steps):
        blended = cv2.addWeighted(focus_target, alpha, focus_norm, 1 - alpha, 0)
        frames.append(Image.fromarray(cv2.cvtColor(blended, cv2.COLOR_BGR2RGB)))
        
    # 均脸停留几帧
    frames.extend([frames[-1]] * 5)

    # 4. 保存 GIF (每帧 100 毫秒，整体非常舒缓)
    frames[0].save(output_path, save_all=True, append_images=frames[1:], duration=100, loop=0)
    print(f"✅ 聚光灯渐变图已生成！请查看：{output_path}")

if __name__ == '__main__':
    generate_spotlight_fade("passport_photo_zhouhui.jpeg", "average_chinese_man.png")
