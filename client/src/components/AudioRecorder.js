import { jsx as _jsx, jsxs as _jsxs, Fragment as _Fragment } from "react/jsx-runtime";
import { useState, useRef } from 'react';
export function AudioRecorder({ ws }) {
    const [isRecording, setIsRecording] = useState(false);
    const [recordingTime, setRecordingTime] = useState(0);
    const audioContextRef = useRef(null);
    const processorRef = useRef(null);
    const streamRef = useRef(null);
    const timerRef = useRef(null);
    // Convert float32 audio to 16-bit PCM
    const floatTo16BitPCM = (floats) => {
        // Log input properties
        console.log(`📊 Input floats: length=${floats.length}, byteLength=${floats.byteLength}`);
        // Ensure we have even number of samples (should always be 4096)
        const numSamples = floats.length;
        // Create Int16Array - this will have numSamples elements, each 2 bytes
        const pcm = new Int16Array(numSamples);
        for (let i = 0; i < numSamples; i++) {
            const s = Math.max(-1, Math.min(1, floats[i]));
            pcm[i] = s < 0 ? s * 0x8000 : s * 0x7fff;
        }
        console.log(`📊 Int16Array created: length=${pcm.length}, byteLength=${pcm.byteLength}`);
        // Create Uint8Array view from the ArrayBuffer
        // This should always be numSamples * 2 bytes (even)
        const uint8Data = new Uint8Array(pcm.buffer);
        const expectedBytes = numSamples * 2;
        const actualBytes = uint8Data.byteLength;
        console.log(`📊 Uint8Array created: byteLength=${actualBytes} (expected ${expectedBytes})`);
        console.log(`✅ Status: ${actualBytes % 2 === 0 ? 'EVEN (valid)' : 'ODD (invalid)'}`);
        if (actualBytes !== expectedBytes) {
            console.error(`❌ Length mismatch! Expected ${expectedBytes}, got ${actualBytes}`);
            throw new Error(`PCM encoding: byte length mismatch (expected ${expectedBytes}, got ${actualBytes})`);
        }
        if (actualBytes % 2 !== 0) {
            console.error(`❌ CRITICAL: ODD byte length ${actualBytes}!`);
            throw new Error(`PCM encoding produced ODD-length data: ${actualBytes} bytes`);
        }
        return uint8Data;
    };
    const startRecording = async () => {
        try {
            const stream = await navigator.mediaDevices.getUserMedia({
                audio: {
                    sampleRate: { ideal: 16000 },
                    channelCount: 1,
                    echoCancellation: true,
                    noiseSuppression: true,
                },
            });
            streamRef.current = stream;
            // Create Web Audio API context
            const audioContext = new (window.AudioContext || window.webkitAudioContext)();
            audioContextRef.current = audioContext;
            const source = audioContext.createMediaStreamSource(stream);
            // Create ScriptProcessor for raw audio chunks
            const processor = audioContext.createScriptProcessor(4096, 1, 1);
            processor.onaudioprocess = (event) => {
                const inputData = event.inputBuffer.getChannelData(0);
                const pcmData = floatTo16BitPCM(inputData);
                if (ws?.isConnected()) {
                    ws.sendAudio(pcmData);
                }
            };
            processorRef.current = processor;
            source.connect(processor);
            processor.connect(audioContext.destination);
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
        if (isRecording) {
            // Stop audio context
            if (processorRef.current) {
                processorRef.current.disconnect();
                processorRef.current = null;
            }
            if (audioContextRef.current) {
                audioContextRef.current.close();
                audioContextRef.current = null;
            }
            // Stop media stream
            if (streamRef.current) {
                streamRef.current.getTracks().forEach((track) => track.stop());
                streamRef.current = null;
            }
            setIsRecording(false);
            if (timerRef.current) {
                clearInterval(timerRef.current);
            }
            // Send end_of_utterance signal to trigger pipeline processing
            console.log('🎤 Recording stopped, sending end_of_utterance signal');
            ws?.sendControl('end_of_utterance');
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
