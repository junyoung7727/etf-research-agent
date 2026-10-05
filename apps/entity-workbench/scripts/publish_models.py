"""Validate definitions and publish a local dashboard revision."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from backend.yaml_models import publish

if __name__ == '__main__':
    publish()
