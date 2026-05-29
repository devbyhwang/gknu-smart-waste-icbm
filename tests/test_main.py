from src.main import _build_parser


def test_main_defaults_to_single_detection_max_count():
    args = _build_parser().parse_args([])
    assert args.max_count == 3
    assert args.interval_ms == 200
    assert args.imgsz == 320
