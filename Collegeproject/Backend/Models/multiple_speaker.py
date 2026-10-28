import torch
import sounddevice as sd
import numpy as np
import librosa
import scipy.signal as signal
from transformers import Wav2Vec2Processor, Wav2Vec2ForSequenceClassification

# ======================================================
# CONFIG & MODEL LOADING
# ======================================================
MODEL_DIR = "wav2vec2_emotion_final"
TARGET_SR = 16000
CHUNK = 0.8   # Increased for better Fourier analysis
OVERLAP_THRESHOLD = 5.0  # Increased to avoid false positives with single voice harmonics
SIMILARITY_THRESHOLD = 0.70 # Slightly lowered for better tolerance

print("Loading Silero VAD model...")
vad_model, utils = torch.hub.load(
    repo_or_dir='snakers4/silero-vad',
    model='silero_vad',
    force_reload=False
)
(get_speech_timestamps, _, _, _, _) = utils

print("Loading Speaker Identification model (Wav2Vec2)...")
processor = Wav2Vec2Processor.from_pretrained(MODEL_DIR)
# We reuse the emotion model's base for speaker features
model = Wav2Vec2ForSequenceClassification.from_pretrained(MODEL_DIR)
model.eval()

# Global state for diarization
reference_embedding = None

mic_sr = int(sd.query_devices(sd.default.device['input'], 'input')['default_samplerate'])
block_size = int(mic_sr * CHUNK)

print(f"Mic SR: {mic_sr}")
print("System Ready... (Speak to enroll your voice)\n")


# ======================================================
# HELPER FUNCTIONS
# ======================================================

def detect_speech(audio16):
    ts = get_speech_timestamps(torch.tensor(audio16), vad_model, sampling_rate=TARGET_SR)
    return len(ts) > 0


def harmonic_complexity(audio16):
    """Detect overlapping voices using harmonic peak density."""
    f, t, Zxx = signal.stft(audio16, TARGET_SR, nperseg=512)
    mag = np.abs(Zxx)
    spectrum = np.mean(mag, axis=1)
    peaks, _ = signal.find_peaks(spectrum, height=np.max(spectrum)*0.2, distance=20)
    return len(peaks)


def extract_embedding(audio16):
    """Extract speaker embedding using Wav2Vec2 base layers."""
    inputs = processor(audio16, sampling_rate=TARGET_SR, return_tensors="pt", padding=True)
    with torch.no_grad():
        outputs = model.wav2vec2(**inputs)
        # Global average pooling over time dimension
        embedding = outputs.last_hidden_state.mean(dim=1).numpy()[0]
    return embedding


def callback(indata, frames, time_info, status):
    global reference_embedding
    
    audio = indata[:, 0].astype(np.float32)
    audio16 = librosa.resample(audio, orig_sr=mic_sr, target_sr=TARGET_SR)

    # Energy check
    if np.mean(audio16**2) < 1e-5:
        return

    # Speech or not?
    if not detect_speech(audio16):
        return

    # Extract current voice fingerprint
    current_embedding = extract_embedding(audio16)
    
    # Measure harmonic peaks (for overlapping voices)
    h = harmonic_complexity(audio16)
    
    # Speaker identification logic
    if reference_embedding is None:
        reference_embedding = current_embedding
        print("👤 VOICE ENROLLED! Speak again to test verification.")
        return

    # Compare with reference using Cosine Similarity
    ref_norm = reference_embedding / (np.linalg.norm(reference_embedding) + 1e-6)
    curr_norm = current_embedding / (np.linalg.norm(current_embedding) + 1e-6)
    similarity = np.dot(ref_norm, curr_norm)
    
    is_same_speaker = similarity > SIMILARITY_THRESHOLD
    
    # Optimized logic:
    # 1. First check if it's mostly the enrolled speaker
    # 2. Then check if there's someone ELSE on top (Complexity)
    # 3. Or if it's just someone else entirely
    
    status_msg = ""
    if h > OVERLAP_THRESHOLD:
        status_msg = f"🚨 MULTIPLE VOICES DETECTED! (Complexity: {h:.2f}, Sim: {similarity:.2f})"
    elif not is_same_speaker:
        # If similarity is extremely low (<0.4), it's definitely someone else
        # If it's mid-range (0.4 - 0.7), it might be a weird recording or a similar voice
        if similarity < 0.45:
            status_msg = f"❌ UNKNOWN SPEAKER! (Similarity: {similarity:.2f})"
        else:
            status_msg = f"⚠️ WEAK VOICE MATCH (Similarity: {similarity:.2f})"
    else:
        status_msg = f"🟢 Verified Interviewee (Similarity: {similarity:.2f})"
        
    print(status_msg)


# ======================================================
# EXECUTION
# ======================================================
with sd.InputStream(callback=callback, channels=1, samplerate=mic_sr, blocksize=block_size):
    try:
        while True:
            sd.sleep(100)
    except KeyboardInterrupt:
        print("\nProgram terminated.")
