import itertools
import time

from src.hardware import DisplayC
from src.models import WasteType


SAMPLE_LEVELS = [
    {
        WasteType.CAN: 0.10,
        WasteType.PLASTIC: 0.45,
        WasteType.GLASS: 0.80,
        WasteType.PAPER: 1.00,
    },
    {
        WasteType.CAN: 0.35,
        WasteType.PLASTIC: 0.60,
        WasteType.GLASS: 0.72,
        WasteType.PAPER: 0.20,
    },
    {
        WasteType.CAN: None,
        WasteType.PLASTIC: 0.82,
        WasteType.GLASS: 0.18,
        WasteType.PAPER: 0.55,
    },
]


def main():
    display = DisplayC()
    labels = [WasteType.CAN, WasteType.PLASTIC, WasteType.GLASS, WasteType.PAPER]

    for label, levels in zip(itertools.cycle(labels), itertools.cycle(SAMPLE_LEVELS)):
        full_bins = {bin_type for bin_type, level in levels.items() if level is not None and level >= 0.8}
        display.showClassificationStatus(
            label,
            confidence=0.92,
            fill_levels=levels,
            full_bins=full_bins,
        )
        time.sleep(2)


if __name__ == "__main__":
    main()
