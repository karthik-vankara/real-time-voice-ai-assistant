import { jsx as _jsx, jsxs as _jsxs, Fragment as _Fragment } from "react/jsx-runtime";
import { useState, useRef } from 'react';
export function AudioRecorder({ ws }) {
    const [isRecording, setIsRecording] = useState(false);
    const [recordingTime, setRecordingTime] = useState(0);
    const mediaRecorderRef = useRef(null);
    const timerRef = useRef(null);
    const startRecording = async () => {
        try {
            const stream = await navigator.mediaDevices.getUserMedia({
                audio: {
                    sampleRate: 16000,
                    channelCount: 1,
                },
            });
            const mediaRecorder = new MediaRecorder(stream, {
                mimeType: 'audio/webm;codecs=opus',
            });
            mediaRecorder.ondataavailable = (event) => {
                if (event.data.size > 0 && ws?.isConnected()) {
                    const reader = new FileReader();
                    reader.onload = () => {
                        const arrayBuffer = reader.result;
                        const uint8Array = new Uint8Array(arrayBuffer);
                        ws.sendAudio(uint8Array);
                    };
                    reader.readAsArrayBuffer(event.data);
                }
            };
            mediaRecorderRef.current = mediaRecorder;
            mediaRecorder.start(100); // Send chunks every 100ms
            setIsRecording(true);
            setRecordingTime(0);
            timerRef.current = setInterval(() => {
                setRecordingTime((prev) => prev + 1);
            }, 1000);
        }
        catch (error) {
            console.error('Failed to start recording:', error);
            alert('Microphone access denied or not available');
        }
    };
    const stopRecording = () => {
        if (mediaRecorderRef.current && isRecording) {
            mediaRecorderRef.current.stop();
            mediaRecorderRef.current.stream.getTracks().forEach((track) => track.stop());
            setIsRecording(false);
            if (timerRef.current) {
                clearInterval(timerRef.current);
            }
        }
    };
    const formatTime = (seconds) => {
        const mins = Math.floor(seconds / 60);
        const secs = seconds % 60;
        return `${mins}:${secs.toString().padStart(2, '0')}`;
    };
    return (_jsxs("div", { className: "bg-slate-800 border border-slate-700 rounded-lg p-6", children: [_jsx("h2", { className: "text-lg font-semibold mb-4", children: "Audio Input" }), _jsxs("div", { className: "space-y-4", children: [isRecording && (_jsx("div", { className: "bg-slate-900 border border-red-500 rounded p-3", children: _jsxs("p", { className: "text-sm text-red-400 font-medium flex items-center gap-2", children: [_jsx("span", { className: "inline-block w-2 h-2 bg-red-500 rounded-full animate-pulse" }), "Recording: ", formatTime(recordingTime)] }) })), _jsx("button", { onClick: isRecording ? stopRecording : startRecording, className: `w-full px-4 py-3 rounded font-medium transition flex items-center justify-center gap-2 ${isRecording
                            ? 'bg-red-600 hover:bg-red-700 text-white'
                            : 'bg-green-600 hover:bg-green-700 text-white'}`, children: isRecording ? (_jsx(_Fragment, { children: _jsx("span", { children: "\u23F9 Stop Recording" }) })) : (_jsx(_Fragment, { children: _jsx("span", { children: "\uD83C\uDFA4 Start Recording" }) })) }), _jsx("div", { className: "bg-slate-900 rounded p-3", children: _jsx("p", { className: "text-xs text-slate-400", children: "\uD83D\uDCDD Speak into your microphone. Audio will be sent to the server for processing. Events will appear in real-time on the right panel." }) })] })] }));
}
