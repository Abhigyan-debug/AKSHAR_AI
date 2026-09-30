// Teacher token (from POST /api/auth/login). Kept in sessionStorage so it goes
// away when the tab closes; storage can be unavailable (private mode), so every
// access is guarded and the in-memory copy still works.

const KEY = 'akshar.teacher'
let memory: { token: string; exp: number } | null = null

function read(): { token: string; exp: number } | null {
  if (memory) return memory
  try {
    const raw = sessionStorage.getItem(KEY)
    memory = raw ? JSON.parse(raw) : null
  } catch {
    memory = null
  }
  return memory
}

export function getToken(): string | null {
  const t = read()
  if (!t) return null
  if (t.exp * 1000 <= Date.now()) {
    signOut()
    return null
  }
  return t.token
}

export function setToken(token: string, exp: number): void {
  memory = { token, exp }
  try {
    sessionStorage.setItem(KEY, JSON.stringify(memory))
  } catch {
    /* in-memory only */
  }
}

export function signOut(): void {
  memory = null
  try {
    sessionStorage.removeItem(KEY)
  } catch {
    /* ignore */
  }
}
