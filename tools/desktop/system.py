"""System metrics forwarder for backward compatibility."""
from tools.desktop.system.telemetry import get_system_metrics, system_info

__all__ = ["get_system_metrics", "system_info"]
