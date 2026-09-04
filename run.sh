#!/bin/bash
cd "$(dirname "$0")"
exec env -u PYTHONPATH -u PYTHONHOME -u VIRTUAL_ENV \
  .venv/bin/uvicorn fencer_schedules.app:app --host 0.0.0.0 --port 8765
