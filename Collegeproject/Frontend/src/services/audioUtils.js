/**
 * Audio Utility functions for recording and encoding WAV
 */

/**
 * Convert Float32Array of audio data to Int16Array (PCM)
 * @param {Float32Array} float32Array 
 * @returns {Int16Array}
 */
const convertFloat32ToInt16 = (float32Array) => {
    const l = float32Array.length;
    const buffer = new Int16Array(l);
    for (let i = 0; i < l; i++) {
        // Clamp values to [-1, 1] then multiply by 32767
        const s = Math.max(-1, Math.min(1, float32Array[i]));
        buffer[i] = s < 0 ? s * 0x8000 : s * 0x7FFF;
    }
    return buffer;
};

/**
 * Encode raw audio samples to WAV format
 * @param {Float32Array} samples - Audio samples
 * @param {number} sampleRate - Sampling rate
 * @returns {Blob} WAV file blob
 */
const encodeWAV = (samples, sampleRate) => {
    const buffer = new ArrayBuffer(44 + samples.length * 2);
    const view = new DataView(buffer);

    // RIFF identifier
    writeString(view, 0, 'RIFF');
    // RIFF chunk length
    view.setUint32(4, 36 + samples.length * 2, true);
    // WAVE identifier
    writeString(view, 8, 'WAVE');
    // fmt chunk identifier
    writeString(view, 12, 'fmt ');
    // fmt chunk length
    view.setUint32(16, 16, true);
    // Sample format (1 is PCM)
    view.setUint16(20, 1, true);
    // Channel count
    view.setUint16(22, 1, true);
    // Sample rate
    view.setUint32(24, sampleRate, true);
    // Byte rate (sampleRate * blockAlign)
    view.setUint32(28, sampleRate * 2, true);
    // Block align (channelCount * bytesPerSample)
    view.setUint16(32, 2, true);
    // Bits per sample
    view.setUint16(34, 16, true);
    // data chunk identifier
    writeString(view, 36, 'data');
    // data chunk length
    view.setUint32(40, samples.length * 2, true);

    // Write PCM samples
    const pcm = convertFloat32ToInt16(samples);
    const len = pcm.length;
    for (let i = 0; i < len; i++) {
        view.setInt16(44 + i * 2, pcm[i], true);
    }

    return new Blob([view], { type: 'audio/wav' });
};

const writeString = (view, offset, string) => {
    for (let i = 0; i < string.length; i++) {
        view.setUint8(offset + i, string.charCodeAt(i));
    }
};

/**
 * Record audio from stream for a specific duration and return as base64 WAV
 * @param {MediaStream} stream - Source stream
 * @param {number} durationMs - Duration in milliseconds
 * @param {AudioContext} [existingContext] - Optional persistent AudioContext to reuse
 * @returns {Promise<string>} Base64 encoded WAV without prefix
 */
// ... (helper functions remain same)

/**
 * Record audio from stream for a specific duration and return as base64 WAV
 * @param {MediaStream} stream - Source stream
 * @param {number} durationMs - Duration in milliseconds
 * @param {AudioContext} [existingContext] - Optional persistent AudioContext to reuse
 * @returns {Promise<string>} Base64 encoded WAV without prefix
 */
export const recordAudioAsWav = (stream, durationMs, existingContext = null) => {
    return new Promise((resolve, reject) => {
        if (!stream) {
            reject(new Error("No stream provided"));
            return;
        }

        const startRecording = async () => {
            try {
                // Fix: Do not force sampleRate to 16000 to avoid DOMException on mismatch
                const audioContext = existingContext || new (window.AudioContext || window.webkitAudioContext)();
                const targetSampleRate = audioContext.sampleRate;

                // Ensure context is running
                if (audioContext.state === 'suspended') {
                    await audioContext.resume();
                }

                const source = audioContext.createMediaStreamSource(stream);

                // Create processor
                // bufferSize, inputChannels, outputChannels
                const processor = audioContext.createScriptProcessor(4096, 1, 1);
                const chunks = [];

                processor.onaudioprocess = (e) => {
                    const inputData = e.inputBuffer.getChannelData(0);
                    // Clone the data because inputBuffer is reused
                    chunks.push(new Float32Array(inputData));
                };

                source.connect(processor);
                processor.connect(audioContext.destination);

                // Stop recording after duration
                setTimeout(() => {
                    // Disconnect to stop processing
                    source.disconnect();
                    processor.disconnect();

                    // Only close if we created it locally
                    if (!existingContext) {
                        audioContext.close();
                    }

                    if (chunks.length === 0) {
                        reject(new Error("No audio data captured"));
                        return;
                    }

                    // Merge chunks
                    const totalLength = chunks.reduce((acc, chunk) => acc + chunk.length, 0);
                    const mergedSamples = new Float32Array(totalLength);
                    let offset = 0;
                    for (const chunk of chunks) {
                        mergedSamples.set(chunk, offset);
                        offset += chunk.length;
                    }

                    // Encode to WAV using the ACTUAL sample rate
                    // The backend (Librosa/Mellotron/etc) should handle resampling if needed
                    const wavBlob = encodeWAV(mergedSamples, targetSampleRate); // Use context rate

                    const reader = new FileReader();
                    reader.readAsDataURL(wavBlob);
                    reader.onloadend = () => {
                        const base64 = reader.result.split(',')[1];
                        resolve(base64);
                    };
                }, durationMs);

            } catch (err) {
                reject(err);
            }
        };

        startRecording();
    });
};
