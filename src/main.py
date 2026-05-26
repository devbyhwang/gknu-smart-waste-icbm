import argparse
import os


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="EcoSort-AIoT runner")
    parser.add_argument("--model-path", default="best.pt")
    parser.add_argument("--camera-index", type=int, default=0)
    parser.add_argument("--width", type=int, default=640)
    parser.add_argument("--height", type=int, default=480)
    parser.add_argument("--fps", type=int, default=15)
    parser.add_argument("--max-count", type=int, default=3)
    parser.add_argument("--interval-ms", type=int, default=500)
    parser.add_argument("--test-mode", action="store_true")
    parser.add_argument(
        "--test-dispatch",
        action="store_true",
        help="test-mode에서 실제 핸들러(OutputM) 액션까지 실행",
    )
    parser.add_argument("--window-name", default="EcoSort Test Monitor")
    return parser


def main(argv=None):
    args = _build_parser().parse_args(argv)

    try:
        from .camera import CameraManager
        from .inference import InferenceEngine, WasteClassifier
        from .output_mgr import OutputM
    except ImportError:
        from camera import CameraManager
        from inference import InferenceEngine, WasteClassifier
        from output_mgr import OutputM

    # best.pt 경로를 현재 스크립트 기준 절대 경로로 변환
    script_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.dirname(script_dir)
    if args.model_path == "best.pt" and not os.path.exists(args.model_path):
        # 현재 폴더에 없으면 프로젝트 루트에서 찾음
        alt_path = os.path.join(project_root, "best.pt")
        if os.path.exists(alt_path):
            args.model_path = alt_path
            print(f"[main] best.pt 경로: {args.model_path}")
        else:
            # src 폴더에 best.pt가 있으면 그대로 사용
            alt_src = os.path.join(script_dir, "best.pt")
            if os.path.exists(alt_src):
                args.model_path = alt_src
                print(f"[main] best.pt 경로: {args.model_path}")

    handler = None
    if not args.test_mode or args.test_dispatch:
        handler = OutputM()
        connect_bluetooth = getattr(handler.bluetooth, "connect", None)
        if callable(connect_bluetooth):
            connect_bluetooth()

    cam = CameraManager(
        index=args.camera_index,
        width=args.width,
        height=args.height,
        fps=args.fps,
    )
    engine = InferenceEngine(args.model_path)

    # img 폴더 경로도 스크립트 기준 절대 경로로
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
    if args.test_mode:
        classifier.run_test_mode(
            dispatch_results=args.test_dispatch,
            window_name=args.window_name,
        )
    else:
        classifier.run()


if __name__ == "__main__":
    main()
