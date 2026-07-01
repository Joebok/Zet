#!/usr/bin/env python3
"""Compatibility wrapper for the backend-neutral local image proxy worker."""

from local_image_proxy_worker import main


if __name__ == "__main__":
    raise SystemExit(main())
