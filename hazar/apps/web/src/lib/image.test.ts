import { describe, expect, it } from "vitest";
import { assessQuality, meanLuma, targetSize } from "./image";

describe("targetSize", () => {
  it("keeps small images", () => expect(targetSize(1000, 800)).toEqual({ width: 1000, height: 800 }));
  it("scales the long edge down", () => expect(targetSize(4000, 3000)).toEqual({ width: 2400, height: 1800 }));
  it("handles portrait", () => expect(targetSize(3000, 6000)).toEqual({ width: 1200, height: 2400 }));
});

describe("quality", () => {
  const pixels = (v: number) => new Uint8ClampedArray(Array.from({ length: 64 * 4 }, (_, i) => (i % 4 === 3 ? 255 : v)));
  it("measures luma", () => {
    expect(meanLuma(pixels(0), 1)).toBe(0);
    expect(Math.round(meanLuma(pixels(200), 1))).toBe(200);
  });
  it("flags dark and small photos", () => {
    expect(assessQuality(3000, 2000, 150)).toEqual([]);
    expect(assessQuality(3000, 2000, 30)).toEqual(["dark"]);
    expect(assessQuality(800, 600, 150)).toEqual(["small"]);
  });
});
