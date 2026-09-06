#!/usr/bin/env python3
"""Encode Marine Philt MES using the shared DOB2-compatible record adapter."""

from gspecific.dob2.adv98_mes.encode_mes import main as encode_main


def main() -> int:
    # Existing boundary convention: 28 denotes a 27-cell display line.
    return encode_main(width=28, speaker_repairs=False)


if __name__ == "__main__":
    raise SystemExit(main())
