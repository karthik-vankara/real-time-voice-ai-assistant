# Real-Time Voice Assistant - Troubleshooting & Issue Resolution Guide

**Last Updated:** March 5, 2026  
**System:** Real-time ASR→LLM→TTS Voice Assistant (OpenAI Integration)  
**Stack:** Python 3.13.2 (FastAPI), React 18.2 (TypeScript, Vite), Web Audio API

---

## Table of Contents
1. [Issue #1: TTS Audio Not Playing](#issue-1-tts-audio-not-playing)
2. [Issue #2: Audio Sounds Like Noise/Corrupted](#issue-2-audio-sounds-like-noisecorrupted)
3. [Issue #3: Audio Chunks Arriving Out of Order](#issue-3-audio-chunks-arriving-out-of-order)
4. [Issue #4: Transcription Returns Georgian Characters (Language Detection Failure)](#issue-4-transcription-returns-georgian-characters)
5. [Issue #5: Transcription Completely Wrong 3x Speed Mismatch](#issue-5-transcription-completely-wrong-3x-speed-mismatch)
6. [Issue #6: Incomplete Audio Playback 80% Truncated](#issue-6-incomplete-audio-playback-80-truncated)

---

## Issue #1: TTS Audio Not Playing

**Severity:** 🔴 CRITICAL - Core feature completely broken  
**Symptom:** Backend successfully generates audio from OpenAI TTS API and sends it to client, but UI shows no audio playback

**Root Cause Analysis:**
```
Backend sends binary MP3/AAC audio → Client receives base64-encoded chunks → 
Client attempts manual PCM decoding → Decoder cannot process compressed audio format
```

**Initial Hypothesis (WRONG):**
- Thought audio was corrupt
- Thought WebSocket transmission was broken
- Checked base64 encoding/decoding

**Actual Root Cause:**
Client was attempting manual PCM decoding on compressed MP3/AAC audio. The decoder expected raw 16-bit PCM samples but received compressed audio stream, resulting in garbage data or silence.

**Solution Implemented:**
Use browser's native Web Audio API `decodeAudioData()` instead of manual decoding.

**Code Fix:**
```typescript
// BEFORE (broken):
const pcmSamples = new Float32Array(audioBuffer);
// Manual decoding attempts...

// AFTER (working):
const audioCtx = new AudioContext();
audioCtx.decodeAudioData(
  compressedAudioBuffer,  // MP3/AAC binary data
  (decodedBuffer) => {
    const source = audioCtx.createBufferSource();
    source.buffer = decodedBuffer;
    source.connect(audioCtx.destination);
    source.start(0);
  },
  (error) => console.error('Decode error:', error)
);
```

**Files Modified:**
- `client/src/App.tsx` - Added Web Audio API decoding in useEffect

**Testing:**
- Sent request to OpenAI TTS API
- Verified audio now plays cleanly via speakers
- ✅ RESOLVED

**Key Learning:**
Never manually decode compressed audio formats. Browser APIs already provide optimized, hardware-accelerated decoding. Let native code handle it.

---

## Issue #2: Audio Sounds Like Noise/Corrupted

**Severity:** 🔴 CRITICAL - Audio is unintelligible  
**Symptom:** Audio playback works but sounds like white noise or heavily distorted gibberish

**Root Cause Analysis:**
```
OpenAI TTS returns MP3/AAC (compressed) → 
Manual decoder treats as raw PCM → 
Decompressed wrong → 
Plays back as noise
```

**Investigation Process:**
1. Checked backend TTS service - confirmed correct audio format selection
2. Tested with curl directly - OpenAI returns valid MP3 file
3. Checked base64 encoding - encoding/decoding working correctly
4. Audio was arriving, just being interpreted incorrectly

**Actual Root Cause:**
Same root cause as Issue #1. Client was interpreting MP3/AAC binary data as raw 16-bit PCM samples, causing the audio to play at completely wrong frequency content and sample rate interpretation.

**Solution:**
Use Web Audio API's native decompression (same as Issue #1)

**Code Evidence:**
```typescript
// Decompressing MP3/AAC requires the browser to know the format
// Manual decoding has no format information
const arrayBuffer = /* binary MP3 data */;

audioCtx.decodeAudioData(arrayBuffer, success, error);
// Browser automatically detects MP3/AAC and decompresses correctly
```

**Testing:**
- Verified audio sounds like natural speech
- High-quality audio with OpenAI voice: "alloy" → "nova"
- ✅ RESOLVED

**Key Learning:**
Audio format matters immensely. MP3/AAC are compressed formats requiring codec knowledge. Always use native browser APIs for decoding to ensure correct format handling.

---

## Issue #3: Audio Chunks Arriving Out of Order

**Severity:** 🟡 MAJOR - Audio quality severely degraded  
**Symptom:** Audio plays but sounds corrupted with pops, clicks, reversed sections, or completely wrong segments

**Root Cause Analysis:**
```
Backend sends chunks 0,1,2,3,4,... sequentially →
Network reorders packets (latency variation) →
Client receives: 0,2,1,4,3,5,... (out of order) →
Concatenates in arrival order instead of correct order →
Audio is corrupted
```

**Initial Implementation (BROKEN):**
```typescript
const audioChunks: string[] = [];
// ...
if (!audioChunks.includes(base64Chunk)) {
  audioChunks.push(base64Chunk);  // Simple array append
}
// Reconstruct: just concatenate in whatever order they arrived
const allAudio = audioChunks.join('');
```

**Problem with Initial Approach:**
- Array maintains insertion order (arrival order), not chunk index order
- `.includes()` check doesn't preserve sequence information
- No way to detect if chunks arrived out of sequence

**Solution Implemented:**
Use `Map<chunk_index, base64_data>` structure to preserve order by index.

**Code Fix:**
```typescript
// BEFORE (broken):
const audioChunks: string[] = [];
audioChunks.push(base64Chunk);

// AFTER (working):
const chunks = new Map<number, string>();
chunks.set(chunk_index, base64Chunk);

// Reconstruction maintains order:
const allBytes: number[] = [];
for (let i = 0; i <= maxIndex; i++) {
  const b64 = chunks.get(i);  // Retrieve by correct index
  if (!b64) console.warn(`Missing chunk ${i}`);
  // ... process chunk
}
```

**Files Modified:**
- `client/src/App.tsx` - Changed TTS chunk accumulation from array to Map

**WebSocket Payload Structure:**
```json
{
  "event_type": "tts_audio_chunk",
  "correlation_id": "abc123",
  "payload": {
    "audio_b64": "base64EncodedData",
    "chunk_index": 5,
    "is_last": false
  }
}
```

**Testing:**
- Created artificial network delay to trigger out-of-order arrival
- Verified chunks now reconstruct in correct order regardless of arrival sequence
- ✅ RESOLVED

**Key Learning:**
Network is unreliable. Always use explicit sequence indicators (index, sequence number) rather than relying on arrival order. Map/Dictionary structures excel at preserving order by key.

---

## Issue #4: Transcription Returns Georgian Characters

**Severity:** 🔴 CRITICAL - Transcription completely wrong  
**Symptom:** Speaking English ("Hey tell me about OpenAI") returns Georgian text in transcription result

**Root Cause Analysis:**
```
User speaks English → 
Whisper API receives audio →
No language parameter specified →
Whisper auto-detects language as Georgian (wrong) →
Returns Georgian text
```

**Investigation Process:**
1. Checked audio was capturing correctly - microphone working
2. Checked audio format - PCM 16-bit correct
3. Checked Whisper API response - language field showed "unknown"
4. Realized: language detection error, not audio quality issue

**Root Cause:**
OpenAI Whisper can auto-detect language, but detection is probabilistic. Without explicit language hint, it sometimes misidentifies English as other languages (especially with short utterances or accented speech). The Georgian characters suggested very wrong detection.

**Solution:**
Explicitly specify language parameter in Whisper API call.

**Code Fix:**
```python
# BEFORE (broken):
response = client.audio.transcriptions.create(
    model="whisper-1",
    file=wav_file,
    # No language parameter
)

# AFTER (working):
response = client.audio.transcriptions.create(
    model="whisper-1",
    file=wav_file,
    language="en"  # Force English
)
```

**Files Modified:**
- `src/services/asr.py` - Added `language="en"` parameter to Whisper API call

**Backend Code:**
```python
def transcribe_stream(self, audio_chunks: list[bytes]) -> str:
    # ... audio processing ...
    
    form_data = {
        'model': ('', 'whisper-1'),
        'file': ('audio.wav', wav_data),
        'language': ('', 'en'),  # REQUIRED: Force English
    }
    
    response = requests.post(
        'https://api.openai.com/v1/audio/transcriptions',
        files=form_data,
        headers=headers,
        timeout=30
    )
```

**Testing:**
- Tested with: "Hey tell me about OpenAI"
- Result: Correct English transcription ✅
- Tested multiple utterances - consistent English detection
- ✅ RESOLVED

**Key Learning:**
Always provide constraints when available. ML models like Whisper can auto-detect, but explicit hints significantly improve accuracy, especially for short utterances or edge cases.

---

## Issue #5: Transcription Completely Wrong - 3x Speed Mismatch

**Severity:** 🔴 CRITICAL - Transcription yields nonsense  
**Symptom:** Speaking "Hey tell me about OpenAI" returns "I don't like you to be here" (completely wrong content)

**Root Cause Analysis:**
```
User's Mac AudioContext runs at 48kHz (native sample rate) →
Audio recorder captures at 48kHz →
Client sends 48kHz PCM to backend →
Backend assumes 16kHz (standard Whisper rate) →
Audio plays 3x FASTER than recorded →
Speech becomes unrecognizable gibberish →
Transcription: completely wrong
```

**Investigation Process:**
1. Verified microphone capturing correctly - audio looks good
2. Verified backend receiving audio - chunks arriving
3. Verified Whisper API working - Georgian issue fixed
4. **New discovery:** Logs showed `AudioContext sampleRate: 48000Hz` but backend treating as `16000Hz`
5. Calculated: 48000/16000 = 3x speed difference!

**Root Cause:**
Different devices have different native AudioContext sample rates:
- macOS: Often 48kHz
- Linux: Often 48kHz  
- Windows: Often 44.1kHz
- Typical ASR expects: 16kHz

Client captured at native rate (assumed 16kHz) but didn't convert. Backend received 48kHz data interpreted as 16kHz = 3x speed.

**Solution:**
Implement client-side downsampling from device sample rate to 16kHz.

**Code Fix:**
```typescript
// BEFORE (broken):
function floatTo16BitPCM(floats: Float32Array): Uint8Array {
  // Direct conversion, no resampling
  const data = new Int16Array(floats.length);
  floats.forEach((f, i) => {
    data[i] = f < 0 ? f * 0x8000 : f * 0x7FFF;
  });
  return new Uint8Array(data.buffer);
}

// AFTER (working):
function downsample(input: Float32Array, ratio: number): Float32Array {
  const output = new Float32Array(Math.floor(input.length / ratio));
  for (let i = 0; i < output.length; i++) {
    output[i] = input[i * ratio];  // Take every nth sample
  }
  return output;
}

function recordAudio() {
  const audioCtx = new AudioContext();
  const downsampleRatio = audioCtx.sampleRate / 16000;
  
  processor.addEventListener('audioprocess', (event) => {
    const downsampledAudio = downsample(
      event.inputData.getChannelData(0),
      downsampleRatio
    );
    const pcm16 = floatTo16BitPCM(downsampledAudio);
    ws.send(pcm16);
  });
}
```

**Key Formula:**
```
downsample_ratio = audioContext.sampleRate / 16000

Example (Mac):
ratio = 48000 / 16000 = 3
Take every 3rd sample from 48kHz stream
Result: ~16kHz stream
```

**Files Modified:**
- `client/src/components/AudioRecorder.tsx` - Added `downsample()` function

**Diagnostics Added:**
```typescript
console.log(`🎤 Recording started - AudioContext sampleRate: ${audioContext.sampleRate}Hz`);
console.log(`Downsampling ratio: ${downsampleRatio}x (${audioContext.sampleRate}Hz → 16000Hz)`);
```

**Backend Diagnostics:**
```python
num_samples = len(audio_data) // 2  # 16-bit = 2 bytes per sample
duration_seconds = num_samples / 16000
print(f"ASR received {len(audio_data)} bytes ({num_samples} samples, {duration_seconds:.2f}s at 16kHz)")
```

**Testing:**
- Before: "I don't like you to be here"
- After: "Hey tell me about OpenAI" ✅ Perfect!
- Tested multiple utterances - all correct
- ✅ RESOLVED

**Key Learning:**
**Never assume sample rates.** Different devices have different native rates. Always query `audioContext.sampleRate` and normalize to expected rate before processing. This is THE critical bridge between browser and backend audio expectations.

---

## Issue #6: Incomplete Audio Playback - 80% Truncated

**Severity:** 🟡 MAJOR - User experience broken (responses incomplete)  
**Symptom:** Full 208-character response sent to TTS, but audio stops mid-word (~80% through)
- Expected: "...they conduct research on AI and share their findings openly with the world."
- Heard: "...they conduct research on AI and share" (missing last ~20%)

**Root Cause Analysis:**
```
Backend sends TTS chunks with is_last flag on FINAL chunk →
Last chunk arrives BEFORE intermediate chunks (network reordering) →
Client receives: chunk 0-17, 25(is_last=true) ←  MISSING 18-24
Client sees is_last=true and immediately starts decoding →
Missing chunks never arrive (already completed) →
Audio reconstructed without chunks 18-24 →
20% of audio missing
```

**Investigation Process:**
1. **Browser Console Logs:**
```
[TTS COMPLETE] Got is_last flag. Stored chunks: 19, maxIndex: 25
⚠️ Missing chunks: [18, 19, 20, 21, 22, 23, 24], present: [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 25]
```

2. **Observation:** Chunk 25 marked `is_last=true` but chunks 18-24 never arrived!

3. **Root Cause:** Race condition with out-of-order network delivery

**Initial Wrong Fix Attempt:**
Added 100ms delay after receiving `is_last=true` hoping late chunks would arrive. Didn't work because we were already marking as complete.

**Correct Solution:**
Don't mark as complete when `is_last` arrives. Instead:
1. Record which chunk is marked as `is_last` (final index)
2. Check if ALL chunks from 0 to that index have arrived
3. Only THEN decode and mark complete
4. Meanwhile, keep receiving any out-of-order chunks

**Code Fix:**
```typescript
// BEFORE (broken):
if (!session.isComplete && is_last) {
  session.isComplete = true;  // Mark complete immediately - WRONG!
  // Start decoding with possibly incomplete chunks
}

// AFTER (working):
if (!session.isComplete && is_last) {
  session.expectedFinalIndex = chunk_index;  // Remember: expected to go 0...N
  session.gotFinalFlag = true;  // Mark that we got is_last signal
  // DON'T mark isComplete yet!
}

// Check if we have ALL chunks
if (session.gotFinalFlag && !session.isComplete) {
  const missingChunks = [];
  for (let i = 0; i <= session.expectedFinalIndex; i++) {
    if (!session.chunks.has(i)) {
      missingChunks.push(i);
    }
  }
  
  if (missingChunks.length === 0) {
    // NOW we can decode (all chunks received)
    session.isComplete = true;
    decodeAudio();
  } else {
    // Still waiting for chunks
    console.log(`⏳ Waiting for chunks... Missing: [${missingChunks.join(', ')}]`);
  }
}
```

**Files Modified:**
- `client/src/App.tsx` - Updated TTS chunk processing logic

**New Session State Structure:**
```typescript
interface TtsSession {
  chunks: Map<number, string>;        // chunk_index → base64 data
  isComplete: boolean;                 // Ready to decode
  maxIndex: number;                    // Highest chunk index seen
  gotFinalFlag: boolean;               // Received is_last=true
  expectedFinalIndex?: number;         // Final chunk index (0-based)
}
```

**Testing:**
- Before: Audio stops at "and share" (80%)
- After: Full audio: "and share their findings openly with the world" (100%) ✅

**Console Logs Before Decoding:**
```
[TTS READY] All 26 chunks received (0-25). Starting decode...
[TTS DECODED] Total audio data: 45890 bytes, from 26 chunks
Audio decoded successfully: 26 chunks, 44.8KB
```

**Key Learning:**
Race conditions with out-of-order networks require explicit completion validation. Don't act on the "final" signal—instead, verify the precondition (all chunks) before acting. This is fundamental to reliable out-of-order delivery scenarios.

---

## Summary: Issue Patterns & Prevention Strategies

### Patterns Found:

| Pattern | Issues | Prevention |
|---------|--------|-----------|
| **Format Mismatches** | #1, #2 | Always know your data formats (PCM vs compressed). Use native APIs. |
| **Order Dependencies** | #3, #6 | Use explicit indexing. Never rely on arrival order in networks. |
| **Auto-Detection Failures** | #4 | Provide explicit hints/constraints when possible. |
| **Device Assumption** | #5 | Query device capabilities. Never assume standard values. |
| **Race Conditions** | #6 | Validate preconditions before action. Separate "signal received" from "ready to process". |

### Debugging Methodology:

1. **Isolate Layer:** Identify which layer fails (network, codec, format, logic)
2. **Verify Input:** Confirm upstream data is correct
3. **Add Diagnostics:** Log sample rates, chunk indices, format types
4. **Check Assumptions:** Find what you assumed incorrectly
5. **Test Edge Cases:** Out-of-order delivery, slow networks, different devices

### Architecture Lessons:

✅ **DO:**
- Query actual device capabilities instead of assuming
- Use sequence numbers/indices for network data
- Separate "signal received" from "ready to process"
- Implement proper diagnostics from day 1
- Use native browser APIs for complex tasks (Web Audio, decoding)

❌ **DON'T:**
- Assume standard rates/formats
- Rely on arrival order in networks
- Act on signals without validating preconditions
- Manually implement what native APIs already do
- Skip logging and diagnostics

---

## Tech Stack Reference

**Frontend:**
- React 18.2 + TypeScript
- Vite build system
- Web Audio API
- WebSocket (real-time bidirectional)

**Backend:**
- Python 3.13.2
- FastAPI
- OpenAI APIs (Whisper ASR, GPT3.5-turbo LLM, TTS)

**Key Integrations:**
- OpenAI Whisper: Speech-to-Text (English)
- OpenAI GPT-3.5-turbo: Conversational AI
- OpenAI TTS: Text-to-Speech (tts-1-hd, voice: nova)

---

## Quick Reference: Solutions Summary

| Issue | Root Cause | Fix |
|-------|-----------|-----|
| #1 Audio not playing | Manual PCM decode on MP3 | Use `audioCtx.decodeAudioData()` |
| #2 Audio is noise | Same as #1 | Use `audioCtx.decodeAudioData()` |
| #3 Chunks out of order | Array maintains arrival order | Use `Map<index, chunk>` |
| #4 Georgian transcription | Language auto-detection failed | Add `language="en"` parameter |
| #5 3x speed wrong | 48kHz treated as 16kHz | Implement client-side downsampling |
| #6 Audio 80% truncated | Decode before all chunks arrive | Wait for 100% chunks before decoding |

---

**Document Version:** 1.0  
**Last Updated:** March 5, 2026  
**Status:** All issues resolved ✅  
**System Stability:** Production ready
