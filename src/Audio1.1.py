try:
    from .hardware import *  # noqa: F401,F403
except ImportError:
    from hardware import *  # type: ignore # noqa: F401,F403
