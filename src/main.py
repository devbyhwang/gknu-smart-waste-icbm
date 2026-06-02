import argparse
import os
import sys


def _build_parser() -> argparse.ArgumentParser:
    # 실행할 때 바꿀 수 있는 카메라/모델 설정값을 한곳에서 받는다.
    parser = argparse.ArgumentParser(description="EcoSort-AIoT runner")
    parser.add_argument("--model-path", default="best.pt")
    parser.add_argument("--camera-index", type=int, default=0)
    parser.add_argument("--width", type=int, default=640)
    parser.add_argument("--height", type=int, default=480)
    parser.add_argument("--fps", type=int, default=15)
    parser.add_argument("--max-count", type=int, default=3)
    parser.add_argument("--interval-ms", type=int, default=200)
    parser.add_argument("--conf-thres", type=float, default=0.1, help="YOLO confidence threshold")
    parser.add_argument("--imgsz", type=int, default=320, help="YOLO inference image size")
    parser.add_argument("--device", default="cpu", help="YOLO inference device (e.g. cpu, 0)")
    return parser


def main(argv=None):
    args = _build_parser().parse_args(argv)

    # src 안에서 직접 실행해도 로컬 모듈 import가 되도록 경로를 보정한다.
    script_dir = os.path.dirname(os.path.abspath(__file__))
    if script_dir not in sys.path:
        sys.path.insert(0, script_dir)

    from camera import CameraManager
    from inference import InferenceEngine, WasteClassifier
    from output_mgr import OutputM

    # 모델 경로는 실행 위치가 달라도 찾을 수 있게 프로젝트 루트와 src를 같이 확인한다.
    project_root = os.path.dirname(script_dir)
    if not os.path.isabs(args.model_path) and not os.path.exists(args.model_path):
        candidates = [
            os.path.join(project_root, args.model_path),
            os.path.join(script_dir, args.model_path),
        ]
        for candidate in candidates:
            if os.path.exists(candidate):
                args.model_path = candidate
                print(f"[main] model 경로: {args.model_path}")
                break

    handler = OutputM(enable_sensor_polling=False)
    connect_bluetooth = getattr(handler.bluetooth, "connect", None)
    if callable(connect_bluetooth):
        # BLE는 실패해도 화면/모터 동작은 계속 진행한다.
        connect_bluetooth()

    cam = CameraManager(
        index=args.camera_index,
        width=args.width,
        height=args.height,
        fps=args.fps,
    )
    engine = InferenceEngine(
        args.model_path,
        conf_thres=args.conf_thres,
        imgsz=args.imgsz,
        device=args.device,
    )

    # 화면 표시용 이미지 폴더도 실행 위치와 상관없이 찾는다.
    img_dir = os.path.join(project_root, "img")
    if not os.path.exists(img_dir):
        img_dir = os.path.join(script_dir, "img")

    classifier = WasteClassifier(
        camera=cam,
        engine=engine,
        max_count=args.max_count,
        interval_ms=args.interval_ms,
        handler=handler,
        img_dir=img_dir,
    )
    classifier.run()


if __name__ == "__main__":
    main()
