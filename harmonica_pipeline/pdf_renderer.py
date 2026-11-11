"""
Multi-Page DIN A4 Sheet Music & Druckbalken Renderer (Verovio + SVG Post-Processor + PyMuPDF).

Features:
  1. Paginates arbitrary-length Dual-System MusicXML scores into DIN A4 portrait pages
     (210mm x 297mm, scale=42) via Verovio.
  2. Injects authentic Rosenzopf Druckbalken (continuous horizontal solid black bar beneath
     the Griffschrift staff across all DRUCK measures) directly into the Verovio SVG geometry.
  3. Exports a print-ready 300-DPI multi-page DIN A4 PDF and per-page PNG/SVG files.
"""

import re
import xml.etree.ElementTree as ET
from pathlib import Path
import pymupdf
import resvg_py
import verovio

_PATH_LINE_RE = re.compile(r"M\s*(-?\d+(?:\.\d+)?)\s+(-?\d+(?:\.\d+)?)\s+L\s*(-?\d+(?:\.\d+)?)\s+(-?\d+(?:\.\d+)?)")


def inject_druckbalken_into_verovio_svg(
    svg_str: str,
    measure_directions: dict[int, str],
    start_measure_idx: int,
) -> tuple[str, int]:
    """
    Parses a single Verovio SVG page, locates the 2nd staff (Griffschrift) inside each
    <g class="measure">, extracts its exact horizontal span [x1, x2] and bottom line y_bottom,
    and injects a thick horizontal Rosenzopf Druckbalken for every measure where
    direction == "DRUCK".

    Returns (modified_svg_str, next_measure_idx).
    """
    ET.register_namespace("", "http://www.w3.org/2000/svg")
    ET.register_namespace("xlink", "http://www.w3.org/1999/xlink")
    root = ET.fromstring(svg_str)
    svg_ns = "{http://www.w3.org/2000/svg}"

    measures = [
        el for el in root.iter()
        if "measure" in el.attrib.get("class", "").split()
    ]

    curr_m = start_measure_idx
    prev_was_druck_on_line = False
    prev_y_bottom = None

    for m_el in measures:
        direction = measure_directions.get(curr_m, "DRUCK")
        curr_m += 1

        staffs = [
            el for el in m_el
            if "staff" in el.attrib.get("class", "").split()
        ]
        if len(staffs) < 2:
            staffs = [
                el for el in m_el.iter()
                if "staff" in el.attrib.get("class", "").split()
            ]
        if len(staffs) < 2:
            continue

        griff_staff = staffs[1]
        xs: list[float] = []
        ys: list[float] = []
        for child in griff_staff:
            if child.tag.endswith("path"):
                d_attr = child.attrib.get("d", "")
                m_match = _PATH_LINE_RE.search(d_attr)
                if m_match:
                    x1, y1, x2, y2 = map(float, m_match.groups())
                    if abs(y1 - y2) < 2.0:
                        xs.extend([x1, x2])
                        ys.append(y1)

        if not xs or len(ys) < 2:
            continue

        x_min, x_max = min(xs), max(xs)
        y_top, y_bottom = min(ys), max(ys)
        staff_space = (y_bottom - y_top) / 4.0 if y_bottom > y_top else 180.0

        # Detect system line wrap (y_bottom jumps down to next system)
        is_new_system_line = (prev_y_bottom is None) or (abs(y_bottom - prev_y_bottom) > staff_space * 2.0)
        if is_new_system_line:
            prev_was_druck_on_line = False
        prev_y_bottom = y_bottom

        if direction == "DRUCK":
            # Place thick Rosenzopf Druckbalken cleanly underneath the Bass Row-ID letters (B  b)
            y_bar = y_bottom + 4.45 * staff_space
            bar_height = max(58.0, 0.36 * staff_space)

            rect_el = ET.Element(
                f"{svg_ns}rect",
                {
                    "x": f"{x_min:.1f}",
                    "y": f"{y_bar:.1f}",
                    "width": f"{max(10.0, x_max - x_min):.1f}",
                    "height": f"{bar_height:.1f}",
                    "fill": "#111111",
                    "class": "rosenzopf-druckbalken",
                },
            )
            m_el.append(rect_el)

            # Add subtle "Druck" label at the start of a contiguous DRUCK section
            if not prev_was_druck_on_line:
                lbl_el = ET.Element(
                    f"{svg_ns}text",
                    {
                        "x": f"{x_min + 25:.1f}",
                        "y": f"{y_bar + bar_height + 1.15 * staff_space:.1f}",
                        "font-family": "Arial, sans-serif",
                        "font-size": f"{int(1.15 * staff_space)}px",
                        "font-weight": "bold",
                        "fill": "#222222",
                    },
                )
                lbl_el.text = "Druck"
                m_el.append(lbl_el)

            prev_was_druck_on_line = True
        else:
            prev_was_druck_on_line = False

    return ET.tostring(root, encoding="unicode"), curr_m


def render_musicxml_to_a4_pdf(
    xml_str: str,
    measure_directions: dict[int, str],
    output_pdf_path: Path,
    output_dir: Path,
    prefix: str = "06_full_polka",
    dpi: int = 300,
) -> list[Path]:
    """
    Renders a Dual-System MusicXML string into a multi-page DIN A4 PDF (with Rosenzopf
    Druckbalken injected into every page) and saves per-page PNG/SVG files.

    Returns list of generated PNG page paths.
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    tk = verovio.toolkit()
    tk.setOptions(
        {
            "pageWidth": 2100,
            "pageHeight": 2970,
            "scale": 40,
            "adjustPageHeight": False,
            "pageMarginTop": 100,
            "pageMarginBottom": 120,
            "pageMarginLeft": 100,
            "pageMarginRight": 100,
            "spacingSystem": 12,
            "spacingStaff": 10,
            "footer": "none",
        }
    )
    tk.loadData(xml_str)
    page_count = tk.getPageCount()

    # DIN A4 pixel dimensions at target DPI (210mm x 297mm = 8.2677" x 11.6929")
    px_width = int(round(8.2677 * dpi))
    px_height = int(round(11.6929 * dpi))

    # DIN A4 PDF point dimensions (72 pt/inch -> 595.28 x 841.89 pt)
    a4_pt_width = 595.28
    a4_pt_height = 841.89

    pdf_doc = pymupdf.open()
    png_paths: list[Path] = []
    curr_measure_idx = 1

    for page_idx in range(1, page_count + 1):
        raw_svg = tk.renderToSVG(page_idx)
        enhanced_svg, curr_measure_idx = inject_druckbalken_into_verovio_svg(
            raw_svg, measure_directions, start_measure_idx=curr_measure_idx
        )

        svg_path = output_dir / f"{prefix}_page{page_idx}.svg"
        svg_path.write_text(enhanced_svg, encoding="utf-8")

        png_bytes = resvg_py.svg_to_bytes(
            svg_path=str(svg_path),
            width=px_width,
            height=px_height,
            background="white",
        )
        png_path = output_dir / f"{prefix}_page{page_idx}.png"
        png_path.write_bytes(png_bytes)
        png_paths.append(png_path)

        pdf_page = pdf_doc.new_page(width=a4_pt_width, height=a4_pt_height)
        pdf_page.insert_image(pdf_page.rect, stream=png_bytes)

    pdf_doc.save(str(output_pdf_path), deflate=True)
    pdf_doc.close()
    return png_paths
