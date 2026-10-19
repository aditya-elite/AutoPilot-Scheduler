import { useEffect, useRef } from 'react'

/**
 * Connects to the backend's /ws/schedule channel and invokes
 * `onMessage` for every push event (e.g. a re-optimization
 * completing). Auto-reconnects with backoff if the connection drops.
 */
export function useScheduleSocket(onMessage) {
  const retryRef = useRef(1000)
  const onMessageRef = useRef(onMessage)

  useEffect(() => {
    onMessageRef.current = onMessage
  }, [onMessage])

  useEffect(() => {
    let socket
    let cancelled = false

    function connect() {
      const protocol = window.location.protocol === 'https:' ? 'wss' : 'ws'
      socket = new WebSocket(`${protocol}://${window.location.host}/ws/schedule`)

      socket.onopen = () => {
        retryRef.current = 1000
      }
      socket.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data)
          onMessageRef.current?.(data)
        } catch {
          /* ignore malformed frames */
        }
      }
      socket.onclose = () => {
        if (cancelled) return
        setTimeout(connect, retryRef.current)
        retryRef.current = Math.min(retryRef.current * 1.5, 15000)
      }
    }

    connect()
    return () => {
      cancelled = true
      socket?.close()
    }
  }, [])
}
