"""Headless plotting with a writable per-user temporary font cache."""
import os
from pathlib import Path
import tempfile

os.environ.setdefault("MPLCONFIGDIR", str(Path(tempfile.gettempdir()) / "quoteguard-matplotlib"))
import matplotlib
matplotlib.use("Agg")
from matplotlib import pyplot as plt
