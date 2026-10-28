import numpy as np
import sounddevice as sd
import librosa
import torch
from scipy.signal import butter, lfilter
from transformers import Wav2Vec2Processor, Wav2Vec2ForSequenceClassification
import time

# ======================================================
# CONFIG
# ======================================================
MODEL_DIR = "wav2vec2_emotion_final"
SR = 16000
FRAME = 1.3                   # match training audio length (~1–2 sec)
LISTEN_TIME = 5
TEMP = 0.9                      # soften predictions
TARGET_RMS = 0.1                # match training loudness

print("Loading models...")
processor = Wav2Vec2Processor.from_pretrained(MODEL_DIR)
model = Wav2Vec2ForSequenceClassification.from_pretrained(MODEL_DIR)
model.eval()
EMOTIONS = list(model.config.id2label.values())

# Load VAD model
vad_model, utils = torch.hub.load(
    repo_or_dir='snakers4/silero-vad',
    model='silero_vad',
    force_reload=False
)
(get_speech_timestamps, _, _, _, _) = utils

print("Models loaded!")

# ======================================================
# PREPROCESSING FUNCTIONS
# ======================================================

def butter_bandpass(lowcut, highcut, fs, order=4):
    nyq = 0.5 * fs
    low = lowcut / nyq
    high = highcut / nyq
    b, a = butter(order, [low, high], btype='band')
    return b, a

def bandpass_filter(data, lowcut=100, highcut=3400, fs=16000):
    b, a = butter_bandpass(lowcut, highcut, fs)
    return lfilter(b, a, data)

def normalize_rms(audio, target_rms=TARGET_RMS):
    rms = np.sqrt(np.mean(audio**2))
    if rms < 1e-6:
        return audio
    return audio * (target_rms / rms)

def trim_silence(audio):
    trimmed, _ = librosa.effects.trim(audio, top_db=25)
    return trimmed

def pitch_normalize(audio):
    return librosa.effects.pitch_shift(audio, sr=SR, n_steps=-1.5)

def match_length(audio, target_len=FRAME*SR):
    target_len = int(target_len)
    if len(audio) > target_len:
        return audio[:target_len]
    pad_len = target_len - len(audio)
    return np.pad(audio, (0, pad_len))

def preprocess_audio(audio):
    audio = audio.flatten().astype(np.float32)

    # * EXACT MATCH TO TRAINING DISTRIBUTION *
    audio = bandpass_filter(audio)
    audio = trim_silence(audio)
    audio = normalize_rms(audio)
    audio = pitch_normalize(audio)
    audio = match_length(audio)

    return audio

def predict(audio):
    inputs = processor(audio, sampling_rate=SR, return_tensors="pt", padding=True)

    with torch.no_grad():
        logits = model(inputs.input_values).logits

    logits = logits / TEMP  # soften confidence
    probs = torch.softmax(logits, dim=-1).numpy()[0]
    return probs

def has_speech(audio):
    """Check if audio contains speech using VAD."""
    # Silero VAD expects 16kHz
    tensor_audio = torch.from_numpy(audio.flatten()).float()
    timestamps = get_speech_timestamps(tensor_audio, vad_model, sampling_rate=SR)
    return len(timestamps) > 0

# ======================================================
# MAIN LOOP
# ======================================================

print("\n--- STANDALONE EMOTION DETECTION ---")
input("Press Enter to start emotion detection (Start only after Gemini finishes the question)...")

print("\n🎤 Speak now... (Listening for {} seconds)\n".format(LISTEN_TIME))
start = time.time()
history = []

while time.time() - start < LISTEN_TIME:
    raw = sd.rec(int(FRAME * SR), samplerate=SR, channels=1, dtype="float32")
    sd.wait()
    
    # Check for speech before processing/predicting
    if not has_speech(raw):
        print("🔇 Silence detected, skipping frame...")
        continue

    processed = preprocess_audio(raw)
    probs = predict(processed)
    history.append(probs)

    print("\n--- Frame Prediction ---")
    for e, p in zip(EMOTIONS, probs):
        print(f"{e:10}: {p*100:.2f}%")

# ======================================================
# FINAL OUTPUT
# ======================================================
if history:
    final = np.mean(history, axis=0)
    dom = EMOTIONS[np.argmax(final)]

    print("\n===============================")
    print("📊 FINAL AVERAGE EMOTION")
    print("===============================")
    for e, p in zip(EMOTIONS, final):
        print(f"{e:10}: {p*100:.2f}%")

    print("\n🧠 Dominant Emotion:", dom.upper())
    print("===============================\n")
else:
    print("\n===============================")
    print("🔇 NO SPEECH DETECTED")
    print("===============================\n")

