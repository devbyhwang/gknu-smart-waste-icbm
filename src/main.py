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
    parser.add_argument("--interval-ms", type=int, default=200)
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

    # 모델 경로를 현재 실행 경로/프로젝트 루트/src 기준으로 해석
    script_dir = os.path.dirname(os.path.abspath(__file__))
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
