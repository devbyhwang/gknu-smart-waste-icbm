import argparse


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="EcoSort-AIoT runner")
    parser.add_argument("--model-path", default="yolov8n.pt")
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

    from .camera import CameraManager
    from .inference import InferenceEngine, WasteClassifier
    from .output_mgr import OutputM

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

    classifier = WasteClassifier(
        camera=cam,
        engine=engine,
        max_count=args.max_count,
        interval_ms=args.interval_ms,
        handler=handler,
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
