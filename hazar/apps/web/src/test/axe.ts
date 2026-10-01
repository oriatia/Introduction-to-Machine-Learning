import axe from "axe-core";

/** Runs axe on a rendered container and returns violation ids (color contrast is not computable in jsdom). */
export async function axeViolations(container: Element): Promise<string[]> {
  const results = await axe.run(container, {
    runOnly: { type: "tag", values: ["wcag2a", "wcag2aa", "wcag21a", "wcag21aa"] },
  });
  return results.violations.map((v) => `${v.id}: ${v.nodes.map((n) => n.html).join(" | ")}`);
}
