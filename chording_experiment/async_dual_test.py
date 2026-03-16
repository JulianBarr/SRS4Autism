import cv2
import time

def main():
    # 假设 0 是 Mac 自带，1 是你的外接 OV9281
    CAM_MAC_ID = 0
    CAM_EXT_ID = 1

    print("启动非对称双摄通道...")
    cap_mac = cv2.VideoCapture(CAM_MAC_ID)
    cap_ext = cv2.VideoCapture(CAM_EXT_ID)

    # 核心防卡死秘籍：把缓冲区缩小到 1，丢弃来不及处理的积压帧
    cap_mac.set(cv2.CAP_PROP_BUFFERSIZE, 1)
    cap_ext.set(cv2.CAP_PROP_BUFFERSIZE, 1)

    # 给外部工业摄像头 (OV9281) 打鸡血
    if cap_ext.isOpened():
        cap_ext.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*'MJPG'))
        cap_ext.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
        cap_ext.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)
        cap_ext.set(cv2.CAP_PROP_FPS, 120)

    # Mac 摄像头保持默认，或者随便给个基础分辨率
    if cap_mac.isOpened():
        cap_mac.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
        cap_mac.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)

    if not cap_mac.isOpened() or not cap_ext.isOpened():
        print("❌ 摄像头未能成功双开，请检查 ID 配置。")
        return

    print("✅ 稳定通道建立成功！按 'q' 退出。")
    prev_frame_time = 0

    while True:
        # 抓取画面
        ret_m, frame_m = cap_mac.read()
        ret_e, frame_e = cap_ext.read()

        if not ret_m or not ret_e:
            continue

        # 计算主循环 FPS
        new_frame_time = time.time()
        fps = int(1 / (new_frame_time - prev_frame_time)) if (new_frame_time - prev_frame_time) > 0 else 0
        prev_frame_time = new_frame_time

        # 在画面上打字 (注意 Mac 画面通常是有色彩的，OV9281 可能是黑白的)
        cv2.putText(frame_m, f"Mac Cam | Loop FPS: {fps}", (30, 50), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 0, 255), 2)
        cv2.putText(frame_e, f"OV9281 | Loop FPS: {fps}", (30, 50), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2)

        # 统一缩放后拼接
        frame_m_resized = cv2.resize(frame_m, (640, 360))
        frame_e_resized = cv2.resize(frame_e, (640, 360))

        # ⚠️ 如果 OV9281 是纯灰度图 (单通道)，Mac 是彩色图 (三通道)，直接拼接会报错
        # 兜底转换：强制把两边都转成 BGR 彩色通道格式再拼
        if len(frame_m_resized.shape) == 2:
            frame_m_resized = cv2.cvtColor(frame_m_resized, cv2.COLOR_GRAY2BGR)
        if len(frame_e_resized.shape) == 2:
            frame_e_resized = cv2.cvtColor(frame_e_resized, cv2.COLOR_GRAY2BGR)

        combined_frame = cv2.hconcat([frame_m_resized, frame_e_resized])

        cv2.imshow("CUMA Asymmetric Dual Vision", combined_frame)

        if cv2.waitKey(1) & 0xFF == ord('q'):
            break

    cap_mac.release()
    cap_ext.release()
    cv2.destroyAllWindows()

if __name__ == "__main__":
    main()
