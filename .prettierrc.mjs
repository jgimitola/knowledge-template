/**
 * @see https://prettier.io/docs/configuration
 * @type {import("prettier").Config}
 */
const config = {
  // Matches `.gitattributes` (`* text=auto eol=lf`) so formatting never rewrites line
  // endings git then reports as a spurious modification.
  endOfLine: 'lf',
  // Specs are hand-wrapped prose. Rewrapping every paragraph on every format would turn
  // one-line prose edits into whole-paragraph diffs.
  proseWrap: 'preserve',
};

export default config;
