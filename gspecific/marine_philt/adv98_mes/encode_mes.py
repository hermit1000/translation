#!/usr/bin/env python3
"""Encode one Marine Philt MES from its info/lang translation documents."""

from gspecific.dob2.adv98_mes import encode_mes as _dob2_encode


# Marine Philt's dialogue window displays 27 characters per line.  The
# shared encoder removes a boundary space at the first cell of the next line;
# configure that shared routine locally without changing DOB2's 30-cell rule.
_dob2_encode.DISPLAY_LINE_CELLS = 28
main = _dob2_encode.main


if __name__ == "__main__":
    raise SystemExit(main())

