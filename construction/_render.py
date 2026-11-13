"""Rendering helpers shared by puzzle constructors."""

import io
import os
import numpy as np
import matplotlib.image as mimage
from matplotlib.backends.backend_agg import FigureCanvasAgg
from matplotlib.figure import Figure
try:
    from PIL import Image
except Exception:  # pragma: no cover
    Image = None

def _env_int(name: str, default: int) -> int:
    raw = os.environ.get(name)
    if raw is None:
        return default
    try:
        value = int(raw)
    except ValueError:
        return default
    return value if value > 0 else default


SQUARE_IMAGE_SIZE_PX = _env_int("PUZZLE_IMAGE_SIZE_PX", 768)
SQUARE_IMAGE_DPI = 100
EDGE_GUARD_RATIO = 0.003
TIGHT_BBOX_PAD_INCHES = 0.05


def save_square_figure(
    fig,
    output_path,
    size_px=None,
    dpi=SQUARE_IMAGE_DPI,
    vertical_shift_ratio=0.0,
    horizontal_shift_ratio=0.0,
):
    """Render a figure, pad to square, then save as fixed-size PNG."""
    if size_px is None:
        size_px = _env_int("PUZZLE_IMAGE_SIZE_PX", SQUARE_IMAGE_SIZE_PX)
    # Render via tight bounding box so tick labels/text near edges are not clipped.
    buf = io.BytesIO()
    fig.savefig(
        buf,
        format='png',
        dpi=fig.dpi,
        bbox_inches='tight',
        pad_inches=TIGHT_BBOX_PAD_INCHES,
    )
    buf.seek(0)
    rgba = mimage.imread(buf)
    if rgba.dtype != np.uint8:
        rgba = (np.clip(rgba, 0.0, 1.0) * 255.0).astype(np.uint8)
    if rgba.ndim == 2:
        rgba = np.stack([rgba, rgba, rgba, np.full_like(rgba, 255)], axis=-1)
    elif rgba.shape[-1] == 3:
        alpha = np.full((*rgba.shape[:2], 1), 255, dtype=np.uint8)
        rgba = np.concatenate([rgba, alpha], axis=-1)

    height, width = rgba.shape[:2]

    # Pad onto a square white background.
    # Keep the long side anchored (no shift), and center only along the short side.
    base_side = max(width, height)
    shift_px_y = int(round(base_side * max(0.0, float(vertical_shift_ratio))))
    shift_px_x = int(round(base_side * max(0.0, float(horizontal_shift_ratio))))
    inner_side = base_side
    if shift_px_y > 0 and height >= width:
        # Tall images have no spare vertical padding by default, so we extend the canvas.
        inner_side = max(inner_side, height + shift_px_y)
    if shift_px_x > 0 and width >= height:
        # Wide images have no spare horizontal padding by default, so we extend the canvas.
        inner_side = max(inner_side, width + shift_px_x)

    square = np.full((inner_side, inner_side, 4), 255, dtype=np.uint8)
    if height > width:
        # Tall image: horizontal center, vertical unchanged.
        top = 0
        left = (inner_side - width) // 2
    elif width > height:
        # Wide image: vertical center, horizontal unchanged.
        top = (inner_side - height) // 2
        left = 0
    else:
        top = 0
        left = 0

    if shift_px_y > 0:
        # Move content downward while keeping it fully inside the square canvas.
        top = min(top + shift_px_y, inner_side - height)
    if shift_px_x > 0:
        # Move content rightward while keeping it fully inside the square canvas.
        left = min(left + shift_px_x, inner_side - width)

    square[top:top + height, left:left + width] = rgba
    # Keep a tiny guard border to avoid edge-pixel clipping after resampling.
    edge_guard = max(1, int(round(base_side * EDGE_GUARD_RATIO)))
    side = inner_side + 2 * edge_guard
    guarded = np.full((side, side, 4), 255, dtype=np.uint8)
    guarded[edge_guard:edge_guard + inner_side, edge_guard:edge_guard + inner_side] = square

    # Resample to target pixel size.
    if Image is not None:
        img = Image.fromarray(guarded, mode='RGBA')
        if img.size != (size_px, size_px):
            img = img.resize((size_px, size_px), Image.Resampling.LANCZOS)
        bg = Image.new('RGBA', img.size, (255, 255, 255, 255))
        bg.alpha_composite(img)
        bg.convert('RGB').save(output_path, format='PNG')
        return

    out_fig = Figure(figsize=(size_px / float(dpi), size_px / float(dpi)), dpi=dpi, frameon=False)
    FigureCanvasAgg(out_fig)
    ax = out_fig.add_axes([0, 0, 1, 1])
    ax.axis("off")
    ax.imshow(guarded)
    ax.set_xlim(-0.5, side - 0.5)
    ax.set_ylim(side - 0.5, -0.5)
    out_fig.savefig(output_path, dpi=dpi)
