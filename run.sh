#!/bin/bash
cd "$(dirname "$0")"
exec env -u PYTHONPATH -u PYTHONHOME -u VIRTUAL_ENV \
  .venv/bin/uvicorn fencer_schedules.app:app --host 127.0.0.1 --port 8765
