import cv2

def scan_cameras():
    print("开始扫描 Mac 的摄像头接口...")
    working_ports = []
    
    # 暴力扫描 0 到 5 号接口
    for i in range(6):
        cap = cv2.VideoCapture(i)
        if cap.isOpened():
            ret, frame = cap.read()
            if ret:
                print(f"✅ 找到可用摄像头，ID 为: {i}")
                working_ports.append(i)
            cap.release()
        else:
            print(f"❌ ID {i} 无法打开")
            
    print(f"\n扫描结束。请把你刚才代码里的 CAM_LEFT 和 CAM_RIGHT 改成这几个数字: {working_ports}")

if __name__ == "__main__":
    scan_cameras()
