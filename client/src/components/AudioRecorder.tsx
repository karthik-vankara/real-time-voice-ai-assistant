import { useState, useRef } from 'react'
import { WebSocketClient } from '../services/websocket'

interface AudioRecorderProps {
  ws: WebSocketClient | null
}

export function AudioRecorder({ ws }: AudioRecorderProps) {
  const [isRecording, setIsRecording] = useState(false)
  const [recordingTime, setRecordingTime] = useState(0)
  const mediaRecorderRef = useRef<MediaRecorder | null>(null)
  const timerRef = useRef<ReturnType<typeof setInterval> | null>(null)

  const startRecording = async () => {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({
        audio: {
          sampleRate: 16000,
          channelCount: 1,
        },
      })

      const mediaRecorder = new MediaRecorder(stream, {
        mimeType: 'audio/webm;codecs=opus',
      })

      mediaRecorder.ondataavailable = (event) => {
        if (event.data.size > 0 && ws?.isConnected()) {
          const reader = new FileReader()
          reader.onload = () => {
            const arrayBuffer = reader.result as ArrayBuffer
            const uint8Array = new Uint8Array(arrayBuffer)
            ws.sendAudio(uint8Array)
          }
          reader.readAsArrayBuffer(event.data)
        }
      }

      mediaRecorderRef.current = mediaRecorder
      mediaRecorder.start(100) // Send chunks every 100ms
      setIsRecording(true)
      setRecordingTime(0)

      timerRef.current = setInterval(() => {
        setRecordingTime((prev) => prev + 1)
      }, 1000)
    } catch (error) {
      console.error('Failed to start recording:', error)
      alert('Microphone access denied or not available')
    }
  }

  const stopRecording = () => {
    if (mediaRecorderRef.current && isRecording) {
      mediaRecorderRef.current.stop()
      mediaRecorderRef.current.stream.getTracks().forEach((track) => track.stop())
      setIsRecording(false)

      if (timerRef.current) {
        clearInterval(timerRef.current)
      }
    }
  }

  const formatTime = (seconds: number) => {
    const mins = Math.floor(seconds / 60)
    const secs = seconds % 60
    return `${mins}:${secs.toString().padStart(2, '0')}`
  }

  return (
    <div className="bg-slate-800 border border-slate-700 rounded-lg p-6">
      <h2 className="text-lg font-semibold mb-4">Audio Input</h2>

      <div className="space-y-4">
        {isRecording && (
          <div className="bg-slate-900 border border-red-500 rounded p-3">
            <p className="text-sm text-red-400 font-medium flex items-center gap-2">
              <span className="inline-block w-2 h-2 bg-red-500 rounded-full animate-pulse" />
              Recording: {formatTime(recordingTime)}
            </p>
          </div>
        )}

        <button
          onClick={isRecording ? stopRecording : startRecording}
          className={`w-full px-4 py-3 rounded font-medium transition flex items-center justify-center gap-2 ${
            isRecording
              ? 'bg-red-600 hover:bg-red-700 text-white'
              : 'bg-green-600 hover:bg-green-700 text-white'
          }`}
        >
          {isRecording ? (
            <>
              <span>⏹ Stop Recording</span>
            </>
          ) : (
            <>
              <span>🎤 Start Recording</span>
            </>
          )}
        </button>

        <div className="bg-slate-900 rounded p-3">
          <p className="text-xs text-slate-400">
            📝 Speak into your microphone. Audio will be sent to the server for processing. Events
            will appear in real-time on the right panel.
          </p>
        </div>
      </div>
    </div>
  )
}
