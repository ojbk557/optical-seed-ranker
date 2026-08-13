from __future__ import annotations

from pathlib import Path
from typing import Any

SUPPORTED_LENGTH_UNIT = "mm"
EVEN_ASPHERE_TYPES = {"EVENASPH", "EVENASPHERE"}


def _float(value: str) -> float | None:
    try:
        return float(value)
    except ValueError:
        return None


def _scaled(value: float | None, scale_factor: float) -> float | None:
    if value is None:
        return None
    return round(value * scale_factor, 9)


def parse_zmx_prescription(path: str | Path) -> dict[str, Any]:
    """Parse the sequential prescription fields needed for seed inspection.

    This intentionally reads only a small, stable subset of the Zemax text format.
    Unknown records are ignored instead of being interpreted optimistically.
    """

    input_path = Path(path)
    if input_path.suffix.lower() != ".zmx":
        raise ValueError("only local .zmx sequential prescriptions are supported")

    system: dict[str, Any] = {}
    surfaces: list[dict[str, Any]] = []
    current: dict[str, Any] | None = None
    x_fields: list[float] = []
    y_fields: list[float] = []
    wavelengths_nm: list[float] = []
    field_count: int | None = None

    raw_bytes = input_path.read_bytes()
    if raw_bytes.startswith((b"\xff\xfe", b"\xfe\xff")):
        text = raw_bytes.decode("utf-16", errors="replace")
    else:
        text = raw_bytes.decode("utf-8", errors="replace")
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        parts = line.split()
        key = parts[0].upper()
        values = parts[1:]

        if key == "SURF" and values:
            current = {"surface": int(values[0])}
            surfaces.append(current)
            continue

        if current is None:
            if key == "NAME":
                system["name"] = line[4:].strip()
            elif key == "UNIT" and values:
                system["length_unit"] = values[0].lower()
            elif key == "ENPD" and values:
                system["entrance_pupil_diameter_mm"] = _float(values[0])
            elif key == "FTYP" and len(values) >= 3:
                parsed_count = _float(values[2])
                field_count = int(parsed_count) if parsed_count is not None else None
            elif key == "XFLN":
                x_fields = [number for value in values if (number := _float(value)) is not None]
            elif key == "YFLN":
                y_fields = [number for value in values if (number := _float(value)) is not None]
            elif key in {"WAVM", "WAVL"} and len(values) >= 2:
                wavelength_um = _float(values[1])
                if wavelength_um is not None:
                    wavelengths_nm.append(wavelength_um * 1000.0)
            continue

        if key == "TYPE" and values:
            current["type"] = values[0]
        elif key == "STOP":
            current["is_stop"] = True
        elif key == "CURV" and values:
            curvature = _float(values[0])
            current["curvature_per_mm"] = curvature
            current["radius_mm"] = (
                None if curvature in (None, 0.0) else 1.0 / curvature
            )
        elif key == "DISZ" and values:
            numeric_thickness = _float(values[0])
            if numeric_thickness is None:
                current["thickness_to_next"] = values[0].lower()
            else:
                current["thickness_to_next_mm"] = numeric_thickness
        elif key == "DIAM" and values:
            current["semi_diameter_mm"] = _float(values[0])
        elif key == "CONI" and values:
            current["conic"] = _float(values[0])
        elif key == "PARM" and len(values) >= 2:
            parameter_value = _float(values[1])
            current.setdefault("parameters", {})[values[0]] = parameter_value
        elif key == "GLAS" and values:
            current["glass"] = values[0]
            if values[0] == "___BLANK" and len(values) >= 5:
                current["model_refractive_index"] = _float(values[3])
                current["model_abbe_number"] = _float(values[4])

    if not surfaces:
        raise ValueError("the .zmx file contains no sequential surfaces")

    if field_count is not None:
        x_fields = x_fields[:field_count]
        y_fields = y_fields[:field_count]
    system["x_fields_deg"] = x_fields
    system["y_fields_deg"] = y_fields
    system["wavelengths_nm"] = sorted({round(value, 9) for value in wavelengths_nm})
    length_unit = system.get("length_unit")
    if length_unit != SUPPORTED_LENGTH_UNIT:
        raise ValueError(
            "only Zemax prescriptions with UNIT MM are supported; "
            f"found {length_unit or 'no UNIT record'}"
        )
    return {"system": system, "surfaces": surfaces}


def _scaled_surface_parameters(
    surface: dict[str, Any], scale_factor: float
) -> dict[str, float | None] | None:
    parameters = surface.get("parameters")
    if not parameters:
        return None
    surface_type = str(surface.get("type", "")).upper()
    if surface_type not in EVEN_ASPHERE_TYPES:
        if scale_factor != 1.0 and any(value not in (None, 0.0) for value in parameters.values()):
            raise ValueError(
                f"cannot safely scale parameters for Zemax surface type {surface_type!r}"
            )
        return dict(parameters)

    scaled: dict[str, float | None] = {}
    for parameter_number, value in parameters.items():
        if value is None:
            scaled[parameter_number] = None
            continue
        number = int(parameter_number)
        if number == 1:
            # PARM 1 is the conic constant for an Even Asphere and is dimensionless.
            scaled[parameter_number] = value
        else:
            radial_order = 2 * number - 2
            scaled[parameter_number] = value * scale_factor ** (1 - radial_order)
    return scaled


def prescription_payload(
    parsed: dict[str, Any], *, scale_factor: float = 1.0
) -> dict[str, Any]:
    """Return a compact prescription and element-region table."""

    surfaces = parsed["surfaces"]
    compact_surfaces: list[dict[str, Any]] = []
    element_regions: list[dict[str, Any]] = []

    by_number = {surface["surface"]: surface for surface in surfaces}
    for surface in surfaces:
        row: dict[str, Any] = {
            "surface": surface["surface"],
            "type": surface.get("type", "UNKNOWN"),
            "is_stop": bool(surface.get("is_stop", False)),
            "radius_mm": _scaled(surface.get("radius_mm"), scale_factor),
            "thickness_to_next_mm": _scaled(
                surface.get("thickness_to_next_mm"), scale_factor
            ),
            "semi_diameter_mm": _scaled(
                surface.get("semi_diameter_mm"), scale_factor
            ),
        }
        if "thickness_to_next" in surface:
            row["thickness_to_next"] = surface["thickness_to_next"]
        if surface.get("glass"):
            row["glass"] = surface["glass"]
        if surface.get("model_refractive_index") is not None:
            row["model_refractive_index"] = surface["model_refractive_index"]
        if surface.get("model_abbe_number") is not None:
            row["model_abbe_number"] = surface["model_abbe_number"]
        if surface.get("conic") not in (None, 0.0):
            row["conic"] = surface["conic"]
        scaled_parameters = _scaled_surface_parameters(surface, scale_factor)
        if scaled_parameters:
            row["parameters"] = scaled_parameters
        compact_surfaces.append(row)

        if surface.get("glass"):
            next_surface = by_number.get(surface["surface"] + 1, {})
            element_regions.append(
                {
                    "element_region": len(element_regions) + 1,
                    "front_surface": surface["surface"],
                    "back_surface": next_surface.get("surface"),
                    "medium": surface["glass"],
                    "model_refractive_index": surface.get(
                        "model_refractive_index"
                    ),
                    "model_abbe_number": surface.get("model_abbe_number"),
                    "front_radius_mm": _scaled(
                        surface.get("radius_mm"), scale_factor
                    ),
                    "back_radius_mm": _scaled(
                        next_surface.get("radius_mm"), scale_factor
                    ),
                    "center_thickness_mm": _scaled(
                        surface.get("thickness_to_next_mm"), scale_factor
                    ),
                    "cemented_to_next_region": bool(next_surface.get("glass")),
                }
            )

    return {
        "system": parsed["system"],
        "scale_factor": round(scale_factor, 9),
        "surface_count_including_object_and_image": len(compact_surfaces),
        "element_region_count_including_windows": len(element_regions),
        "element_regions": element_regions,
        "surfaces": compact_surfaces,
    }
