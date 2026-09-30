import { api, ApiError, type Tap } from '../api'

// Uploads clips one at a time in the background so the child moves straight to
// the next item. Network/server failures are retried; 4xx errors are not (they
// would fail again) and are reported instead.

interface Job {
  sessionId: number
  itemId: string
  blob: Blob
  filename: string
  liveTap?: Tap
  attempts: number
}

type Listener = (s: QueueStatus) => void
export interface QueueStatus {
  pending: number
  failed: { itemId: string; message: string }[]
}

const MAX_ATTEMPTS = 4

export class UploadQueue {
  private jobs: Job[] = []
  private running = false
  private failed: QueueStatus['failed'] = []
  private listeners = new Set<Listener>()
  private idleWaiters: (() => void)[] = []

  add(job: Omit<Job, 'attempts'>) {
    this.jobs.push({ ...job, attempts: 0 })
    this.emit()
    void this.run()
  }

  subscribe(fn: Listener): () => void {
    this.listeners.add(fn)
    fn(this.status())
    return () => this.listeners.delete(fn)
  }

  status(): QueueStatus {
    return { pending: this.jobs.length, failed: [...this.failed] }
  }

  /** Resolves once every queued clip has been uploaded or has failed for good. */
  whenIdle(): Promise<void> {
    if (!this.jobs.length && !this.running) return Promise.resolve()
    return new Promise((resolve) => this.idleWaiters.push(resolve))
  }

  private emit() {
    const s = this.status()
    this.listeners.forEach((fn) => fn(s))
  }

  private async run() {
    if (this.running) return
    this.running = true
    while (this.jobs.length) {
      const job = this.jobs[0]
      try {
        await api.uploadAudio(job.sessionId, job.itemId, job.blob, job.filename, job.liveTap)
        this.jobs.shift()
      } catch (err) {
        job.attempts += 1
        const clientError = err instanceof ApiError && err.status >= 400 && err.status < 500
        if (clientError || job.attempts >= MAX_ATTEMPTS) {
          this.jobs.shift()
          this.failed.push({ itemId: job.itemId, message: err instanceof Error ? err.message : String(err) })
        } else {
          await new Promise((r) => setTimeout(r, 1000 * 2 ** job.attempts))
        }
      }
      this.emit()
    }
    this.running = false
    this.emit()
    this.idleWaiters.splice(0).forEach((fn) => fn())
  }
}
