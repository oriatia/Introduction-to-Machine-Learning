import { defineConfig, globalIgnores } from "eslint/config";
import nextVitals from "eslint-config-next/core-web-vitals";
import nextTs from "eslint-config-next/typescript";

// Every user-facing string lives in locales/he.json (CLAUDE.md principle 6).
const noHardcodedStrings = {
  files: ["src/**/*.tsx"],
  ignores: ["src/**/*.test.tsx"],
  rules: {
    "react/jsx-no-literals": ["error", { noStrings: true, ignoreProps: true, allowedStrings: ["·", "—", "*"] }],
  },
};

// Attribute text (aria-label, placeholder, ...) must also come from he.json, and RTL-first:
// physical left/right utilities break the Hebrew layout. Use start/end, ms/me, ps/pe.
const restrictedSyntax = {
  files: ["src/**/*.tsx"],
  rules: {
    "no-restricted-syntax": [
      "error",
      {
        selector:
          "JSXAttribute[name.name=/^(aria-label|aria-description|placeholder|title|alt)$/] > Literal[value=/\\p{L}/u]",
        message: "User-facing attribute text must come from locales/he.json via next-intl.",
      },
      {
        selector:
          "Literal[value=/(^|\\s)(-?(ml|mr|pl|pr|left|right)-|text-left|text-right|rounded-[lr]-|border-[lr]-)/]",
        message: "Use logical utilities (ms/me, ps/pe, start/end, text-start/text-end) for RTL.",
      },
    ],
  },
};

export default defineConfig([
  ...nextVitals,
  ...nextTs,
  noHardcodedStrings,
  restrictedSyntax,
  globalIgnores([".next/**", "out/**", "build/**", "next-env.d.ts", "playwright-report/**", "test-results/**"]),
]);
