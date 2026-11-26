"""
Turn a digital PDF into a realistic "scanned" PDF: every page becomes a
grayscale image with slight rotation, speckle noise, blur and JPEG
compression, and there is no text layer, so OCR has to do all the work.

usage: python make_scanned.py input.pdf output.pdf [--quality good|bad] [--seed N]
"""
import argparse
import io
import random

import numpy as np
import pypdfium2 as pdfium
from PIL import Image, ImageFilter

PROFILES = {
    # typical office scanner
    "good": dict(dpi=200, max_rotate=1.2, noise=10, blur=0.6, jpeg=60, contrast=0.92),
    # old fax / phone photo: low resolution, heavy noise
    "bad": dict(dpi=90, max_rotate=2.5, noise=38, blur=1.2, jpeg=25, contrast=0.75),
}


def scan_page(page, p, rng):
    img = page.render(scale=p["dpi"] / 72).to_pil().convert("L")

    # Paper isn't perfectly white and ink isn't perfectly black
    arr = np.asarray(img).astype(np.float32)
    arr = 255 - (255 - arr) * p["contrast"]
    arr = arr * rng.uniform(0.95, 1.0) + rng.uniform(0, 8)

    # Speckle noise, plus a few dark dust spots
    arr += np.random.default_rng(rng.randint(0, 10**6)).normal(0, p["noise"], arr.shape)
    img = Image.fromarray(np.clip(arr, 0, 255).astype(np.uint8))
    for _ in range(rng.randint(5, 25)):
        x, y = rng.randint(0, img.width - 1), rng.randint(0, img.height - 1)
        img.paste(rng.randint(0, 90), (x, y, x + rng.randint(1, 3), y + rng.randint(1, 3)))

    # Page fed slightly crooked
    img = img.rotate(rng.uniform(-p["max_rotate"], p["max_rotate"]), expand=False, fillcolor=245)
    img = img.filter(ImageFilter.GaussianBlur(p["blur"]))

    # JPEG artifacts, like a real scanner
    buf = io.BytesIO()
    img.save(buf, "JPEG", quality=p["jpeg"])
    return Image.open(io.BytesIO(buf.getvalue()))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("input")
    ap.add_argument("output")
    ap.add_argument("--quality", choices=PROFILES, default="good")
    ap.add_argument("--seed", type=int, default=7)
    args = ap.parse_args()

    p = PROFILES[args.quality]
    rng = random.Random(args.seed)
    pages = [scan_page(page, p, rng) for page in pdfium.PdfDocument(args.input)]
    pages[0].save(args.output, "PDF", save_all=True, append_images=pages[1:], resolution=p["dpi"])


if __name__ == "__main__":
    main()
