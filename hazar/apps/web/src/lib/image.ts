/** Client-side photo preparation: downscale, recompress, and simple quality checks before upload. */

export const MAX_EDGE = 2400;
export const MIN_LONG_EDGE = 1200;
export const DARK_THRESHOLD = 60; // mean luma 0-255
export const MAX_UPLOAD_BYTES = 10 * 1024 * 1024;

export type QualityWarning = "dark" | "small" | "tooLarge";

export function targetSize(width: number, height: number, maxEdge = MAX_EDGE): { width: number; height: number } {
  const scale = Math.min(1, maxEdge / Math.max(width, height));
  return { width: Math.round(width * scale), height: Math.round(height * scale) };
}

/** Mean luma (Rec. 601) over RGBA pixels, sampling every `step`-th pixel. */
export function meanLuma(rgba: Uint8ClampedArray, step = 16): number {
  let sum = 0;
  let n = 0;
  for (let i = 0; i < rgba.length; i += 4 * step) {
    sum += 0.299 * rgba[i] + 0.587 * rgba[i + 1] + 0.114 * rgba[i + 2];
    n++;
  }
  return n ? sum / n : 0;
}

export function assessQuality(width: number, height: number, luma: number): QualityWarning[] {
  const warnings: QualityWarning[] = [];
  if (luma < DARK_THRESHOLD) warnings.push("dark");
  if (Math.max(width, height) < MIN_LONG_EDGE) warnings.push("small");
  return warnings;
}

export type PreparedFile = { blob: Blob; name: string; previewUrl: string | null; warnings: QualityWarning[] };

/**
 * Images: downscale to MAX_EDGE and re-encode as JPEG, which also strips EXIF (incl. location).
 * A PNG that needs no downscaling is sent unchanged (no EXIF to strip; keeps screenshots lossless).
 * PDFs pass through.
 */
export async function prepareFile(file: File): Promise<PreparedFile> {
  if (file.type === "application/pdf") {
    return { blob: file, name: file.name, previewUrl: null, warnings: file.size > MAX_UPLOAD_BYTES ? ["tooLarge"] : [] };
  }
  const bitmap = await createImageBitmap(file);
  const { width, height } = targetSize(bitmap.width, bitmap.height);
  const canvas = document.createElement("canvas");
  canvas.width = width;
  canvas.height = height;
  const ctx = canvas.getContext("2d");
  if (!ctx) throw new Error("canvas unavailable");
  ctx.drawImage(bitmap, 0, 0, width, height);
  const luma = meanLuma(ctx.getImageData(0, 0, width, height).data);
  const blob = await new Promise<Blob>((resolve, reject) =>
    canvas.toBlob((b) => (b ? resolve(b) : reject(new Error("encode failed"))), "image/jpeg", 0.85),
  );
  const warnings = assessQuality(bitmap.width, bitmap.height, luma);
  const keepOriginal =
    file.type === "image/png" && width === bitmap.width && height === bitmap.height && file.size <= MAX_UPLOAD_BYTES;
  const out = keepOriginal ? file : blob;
  if (out.size > MAX_UPLOAD_BYTES) warnings.push("tooLarge");
  return {
    blob: out,
    name: keepOriginal ? "photo.png" : "photo.jpg",
    previewUrl: URL.createObjectURL(out),
    warnings,
  };
}
