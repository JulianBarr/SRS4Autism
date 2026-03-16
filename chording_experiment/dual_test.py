import cv2
import time

def main():
    # ⚠️ Mac 的摄像头玄学：0 通常是自带的 FaceTime 摄像头
    # 所以你的两个 USB 摄像头大概率是 1 和 2。如果报错，试试 1和3，或者 2和3。
    CAM_LEFT_ID = 1
    CAM_RIGHT_ID = 2

    print(f"正在强行唤醒摄像头 {CAM_LEFT_ID} 和 {CAM_RIGHT_ID}...")
    cap_left = cv2.VideoCapture(CAM_LEFT_ID)
    cap_right = cv2.VideoCapture(CAM_RIGHT_ID)

    # 暴力注入高帧率和分辨率指令 (OV9281 的强项)
    for cap in [cap_left, cap_right]:
        if cap.isOpened():
            cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*'MJPG'))
            cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
            cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)
            cap.set(cv2.CAP_PROP_FPS, 120)

    if not cap_left.isOpened() or not cap_right.isOpened():
        print("❌ 灾难：未能同时打开两个摄像头！")
        print("排查建议：1. 检查 USB 供电/Hub。 2. 修改代码里的 CAM_LEFT_ID 和 CAM_RIGHT_ID。")
        return

    print("✅ 方舟双摄通道已建立！按键盘 'q' 键退出。")

    prev_frame_time = 0

    while True:
        ret_l, frame_l = cap_left.read()
        ret_r, frame_r = cap_right.read()

        if not ret_l or not ret_r:
            continue

        # 计算并实时显示帧率 (FPS)
        new_frame_time = time.time()
        fps = int(1 / (new_frame_time - prev_frame_time)) if (new_frame_time - prev_frame_time) > 0 else 0
        prev_frame_time = new_frame_time

        # 在左右画面打上标签
        cv2.putText(frame_l, f"Left Cam | FPS: {fps}", (30, 50), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2)
        cv2.putText(frame_r, f"Right Cam | FPS: {fps}", (30, 50), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2)

        # 缩小一半拼在一起，防止 720P*2 撑爆你的屏幕
        frame_l_resized = cv2.resize(frame_l, (640, 360))
        frame_r_resized = cv2.resize(frame_r, (640, 360))
        combined_frame = cv2.hconcat([frame_l_resized, frame_r_resized])

        cv2.imshow("CUMA Dual Vision Hardcore Test", combined_frame)

        if cv2.waitKey(1) & 0xFF == ord('q'):
            break

    cap_left.release()
    cap_right.release()
    cv2.destroyAllWindows()

if __name__ == "__main__":
    main()
