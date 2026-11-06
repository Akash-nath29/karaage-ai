// Validates LaTeX with KaTeX, using the same options the frontend renders with (PRD §11.5).
// stdin:  [{"tex": "x^2", "display": false}, ...]
// stdout: [null | "error message", ...] in the same order
// CommonJS on purpose: require() honours NODE_PATH, which the worker image uses to find KaTeX.
const katex = require("katex")

let input = ""
process.stdin.setEncoding("utf8")
process.stdin.on("data", (chunk) => (input += chunk))
process.stdin.on("end", () => {
  const results = JSON.parse(input).map(({ tex, display }) => {
    try {
      katex.renderToString(tex, { displayMode: Boolean(display), throwOnError: true, strict: "ignore", trust: false })
      return null
    } catch (e) {
      return String((e && e.message) || e).slice(0, 300)
    }
  })
  process.stdout.write(JSON.stringify(results))
})
