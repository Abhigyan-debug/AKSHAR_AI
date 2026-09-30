// Marks which parts of what was heard differ from the target, for highlighting
// in the report. Works on grapheme clusters so a Devanagari matra stays with
// its consonant.

const segmenter = typeof Intl !== 'undefined' && 'Segmenter' in Intl ? new Intl.Segmenter(undefined, { granularity: 'grapheme' }) : null

export function graphemes(s: string): string[] {
  if (!segmenter) return [...s]
  return [...segmenter.segment(s)].map((x) => x.segment)
}

export interface Part {
  text: string
  same: boolean
}

/** Splits `heard` into parts that match the target (LCS) and parts that don't. */
export function diffHeard(target: string, heard: string): Part[] {
  const a = graphemes(target.toLowerCase())
  const bRaw = graphemes(heard)
  const b = bRaw.map((g) => g.toLowerCase())
  const n = a.length
  const m = b.length
  const dp: number[][] = Array.from({ length: n + 1 }, () => new Array<number>(m + 1).fill(0))
  for (let i = n - 1; i >= 0; i--)
    for (let j = m - 1; j >= 0; j--) dp[i][j] = a[i] === b[j] ? dp[i + 1][j + 1] + 1 : Math.max(dp[i + 1][j], dp[i][j + 1])

  const same = new Array<boolean>(m).fill(false)
  let i = 0
  let j = 0
  while (i < n && j < m) {
    if (a[i] === b[j]) {
      same[j] = true
      i++
      j++
    } else if (dp[i + 1][j] >= dp[i][j + 1]) i++
    else j++
  }

  const parts: Part[] = []
  bRaw.forEach((g, k) => {
    const last = parts[parts.length - 1]
    if (last && last.same === same[k]) last.text += g
    else parts.push({ text: g, same: same[k] })
  })
  return parts
}
