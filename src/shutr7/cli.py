"""Command-line interface for shutr7."""

from __future__ import annotations

import json
import sys

import click

from .camera import CameraInfo, CanonR7, ShutterInfo
from .ptp.constants import CANON_R7_PRODUCT_ID, CANON_R7_SHUTTER_LIFE, CANON_VENDOR_ID
from .ptp.transport import USBTransportError


@click.group()
@click.version_option(package_name="shutr7")
def main() -> None:
    """shutr7 - Canon R7 Shutter Count Tool.

    Extract shutter count from your Canon R7 camera over USB.
    """
    pass


@main.command()
@click.option("--json", "output_json", is_flag=True, help="Output in JSON format")
@click.option(
    "--vendor-id",
    type=str,
    default=None,
    help="USB vendor ID (hex, e.g., 0x04a9)",
)
@click.option(
    "--product-id",
    type=str,
    default=None,
    help="USB product ID (hex, e.g., 0x32f7)",
)
@click.option(
    "--shutter-life",
    type=int,
    default=CANON_R7_SHUTTER_LIFE,
    help=f"Shutter life expectancy (default: {CANON_R7_SHUTTER_LIFE})",
)
def count(
    output_json: bool,
    vendor_id: str | None,
    product_id: str | None,
    shutter_life: int,
) -> None:
    """Get the camera's shutter count."""
    vid = int(vendor_id, 16) if vendor_id else CANON_VENDOR_ID
    pid = int(product_id, 16) if product_id else CANON_R7_PRODUCT_ID

    try:
        with CanonR7(vendor_id=vid, product_id=pid, shutter_life=shutter_life) as camera:
            shutter_info = camera.get_shutter_count()
            camera_info = camera.get_camera_info()

            if output_json:
                _output_json(shutter_info, camera_info)
            else:
                _output_text(shutter_info, camera_info)

    except USBTransportError as e:
        click.echo(f"Error: {e}", err=True)
        click.echo("\nTroubleshooting:", err=True)
        click.echo("  1. Ensure the Canon R7 is connected via USB", err=True)
        click.echo("  2. Set camera to PTP mode (not Mass Storage)", err=True)
        click.echo("  3. Check USB permissions (may need udev rules on Linux)", err=True)
        click.echo("  4. Close any other apps using the camera (EOS Utility, etc.)", err=True)
        sys.exit(1)
    except RuntimeError as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)


def _output_json(shutter_info: ShutterInfo, camera_info: CameraInfo) -> None:
    """Output results in JSON format."""
    data = {
        "camera": {
            "manufacturer": camera_info.manufacturer,
            "model": camera_info.model,
            "firmware_version": camera_info.firmware_version,
        },
        "shutter": {
            "mechanical_count": shutter_info.mechanical_count,
            "total_count": shutter_info.total_count,
            "life_expectancy": shutter_info.life_expectancy,
            "remaining": shutter_info.remaining,
            "percentage_used": round(shutter_info.percentage_used, 2),
        },
    }
    click.echo(json.dumps(data, indent=2))


def _output_text(shutter_info: ShutterInfo, camera_info: CameraInfo) -> None:
    """Output results in human-readable format."""
    click.echo(f"Camera: {camera_info.manufacturer} {camera_info.model}")
    click.echo(f"Firmware: {camera_info.firmware_version}")
    click.echo()
    click.echo(f"Mechanical Shutter: <= {shutter_info.mechanical_count:,}")
    click.echo(f"Total Actuations:   <= {shutter_info.total_count:,}")
    click.echo()
    click.echo(f"Life Expectancy: {shutter_info.life_expectancy:,}")
    click.echo(f"Remaining: ~{shutter_info.remaining:,} ({shutter_info.percentage_remaining:.1f}%)")

    bar_width = 40
    filled = int(bar_width * shutter_info.percentage_used / 100)
    click.echo(f"Usage: [{'#' * filled}{'-' * (bar_width - filled)}] {shutter_info.percentage_used:.1f}%")


@main.command()
@click.option(
    "--vendor-id",
    type=str,
    default=None,
    help="USB vendor ID (hex, e.g., 0x04a9)",
)
@click.option(
    "--product-id",
    type=str,
    default=None,
    help="USB product ID (hex, e.g., 0x32f7)",
)
def debug(vendor_id: str | None, product_id: str | None) -> None:
    """Dump all camera properties (for debugging)."""
    from .ptp.canon import CanonEOSProtocol
    from .ptp.transport import USBTransport

    vid = int(vendor_id, 16) if vendor_id else CANON_VENDOR_ID
    pid = int(product_id, 16) if product_id else CANON_R7_PRODUCT_ID

    try:
        with USBTransport(vendor_id=vid, product_id=pid) as transport:
            protocol = CanonEOSProtocol(transport)
            protocol.initialize_eos_session()

            events = protocol.get_event()
            click.echo(f"Found {len(events)} properties:\n")

            for event in sorted(events, key=lambda e: e.property_code):
                if isinstance(event.value, int):
                    click.echo(f"  {event.property_code:#06x}: {event.value}")
                else:
                    click.echo(f"  {event.property_code:#06x}: {event.value.hex()}")

            protocol.close_session()

    except USBTransportError as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)


@main.command()
@click.option(
    "--vendor-id",
    type=str,
    default=None,
    help="USB vendor ID (hex, e.g., 0x04a9)",
)
@click.option(
    "--product-id",
    type=str,
    default=None,
    help="USB product ID (hex, e.g., 0x32f7)",
)
def info(vendor_id: str | None, product_id: str | None) -> None:
    """Show camera connection information."""
    vid = int(vendor_id, 16) if vendor_id else CANON_VENDOR_ID
    pid = int(product_id, 16) if product_id else CANON_R7_PRODUCT_ID

    try:
        with CanonR7(vendor_id=vid, product_id=pid) as camera:
            info = camera.get_camera_info()
            click.echo(f"Connected: {info.manufacturer} {info.model}")
            click.echo(f"Firmware: {info.firmware_version}")
    except USBTransportError as e:
        click.echo(f"Not connected: {e}", err=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
