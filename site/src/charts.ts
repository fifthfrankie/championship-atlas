import { esc } from "./util.js"

/** Cumulative points after each league match, this season against earlier ones. Pure SVG, no library. */
export function pointsChart(series: Record<string, number[]>, current: string, title: string): string {
  const labels = Object.keys(series).sort().reverse().slice(0, 3)   // current plus two earlier seasons
  const W = 640, H = 280, L = 40, R = 90, T = 14, B = 34
  const maxX = 46, maxY = Math.max(10, ...labels.flatMap((l) => series[l] ?? []))
  const yMax = Math.ceil(maxY / 10) * 10
  const x = (n: number) => L + ((W - L - R) * n) / maxX
  const y = (v: number) => T + (H - T - B) * (1 - v / yMax)
  const grid = []
  for (let v = 0; v <= yMax; v += yMax > 80 ? 20 : 10) grid.push(`<line x1="${L}" x2="${W - R}" y1="${y(v)}" y2="${y(v)}" class="g"/><text x="${L - 6}" y="${y(v) + 4}" text-anchor="end">${v}</text>`)
  for (let n = 0; n <= maxX; n += 10) grid.push(`<text x="${x(n)}" y="${H - 14}" text-anchor="middle">${n}</text>`)
  const lines = labels.map((l, i) => {
    const pts = (series[l] ?? []).map((v, k) => `${x(k + 1).toFixed(1)},${y(v).toFixed(1)}`)
    if (!pts.length) return ""
    const last = (series[l] ?? []).at(-1)!, lastX = x((series[l] ?? []).length)
    const cls = l === current ? "now" : i === 1 ? "prev1" : "prev2"
    return `<polyline points="${pts.join(" ")}" class="ln ${cls}" fill="none"/><text x="${lastX + 6}" y="${y(last) + 4}" class="lab ${cls}">${esc(l)}</text>`
  }).join("")
  const rows = [5, 10, 15, 20, 25, 30, 35, 40, 46].map((n) => `<tr><th scope="row">${n}</th>${labels.map((l) => `<td>${series[l]?.[n - 1] ?? "-"}</td>`).join("")}</tr>`).join("")
  return `<figure class="chart"><figcaption>${esc(title)}</figcaption>
<svg viewBox="0 0 ${W} ${H}" role="img" aria-label="${esc(title)}. Line chart; the table below has the same numbers." preserveAspectRatio="xMidYMid meet">
${grid.join("")}<text x="${(L + W - R) / 2}" y="${H - 1}" text-anchor="middle" class="ax">League matches played</text>
<text x="10" y="${T + 6}" class="ax">Points</text>${lines}</svg>
<details class="evidence"><summary>Show as a table</summary><div class="scroll" tabindex="0" role="region" aria-label="Scrollable table"><table><thead><tr><th scope="col" class="left">Matches played</th>${labels.map((l) => `<th scope="col">${esc(l)}</th>`).join("")}</tr></thead><tbody>${rows}</tbody></table></div></details></figure>`
}
