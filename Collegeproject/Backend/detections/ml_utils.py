"""
ML Utilities for running posture and face detection models
"""
import os
import sys
import cv2
import numpy as np
import joblib
from pathlib import Path
import threading
import logging

# Add Models directory to path
BASE_DIR = Path(__file__).resolve().parent.parent
MODELS_DIR = BASE_DIR / "Models"

# Initialize MediaPipe components with error handling
try:
    import mediapipe as mp
    
    # Check MediaPipe version
    mp_version = getattr(mp, '__version__', 'unknown')
    print(f"MediaPipe version: {mp_version}")
    
    # Try to access solutions module
    if not hasattr(mp, 'solutions'):
        raise AttributeError(
            f"MediaPipe {mp_version} does not have 'solutions' attribute. "
            f"This usually indicates a corrupted installation. "
            f"Try: pip uninstall mediapipe -y && pip install mediapipe==0.10.7"
        )
    
    mp_holistic = mp.solutions.holistic
    mp_face_detection = mp.solutions.face_detection
    mp_drawing = mp.solutions.drawing_utils
    
except ImportError as e:
    raise ImportError(
        f"Failed to import MediaPipe: {e}\n"
        f"Please install MediaPipe: pip install mediapipe==0.10.7"
    )
except AttributeError as e:
    raise AttributeError(
        f"MediaPipe installation appears corrupted: {e}\n"
        f"Try reinstalling:\n"
        f"  pip uninstall mediapipe -y\n"
        f"  pip install mediapipe==0.10.7\n"
        f"Or if using virtual environment:\n"
        f"  source .venv/bin/activate  # or env/bin/activate\n"
        f"  pip uninstall mediapipe -y\n"
        f"  pip install mediapipe==0.10.7"
    )

# Global variables for loaded models (singleton pattern)
_posture_model = None
_posture_encoder = None
_holistic = None
_face_detection = None


def load_posture_model():
    """Load the posture detection model and encoder (singleton)"""
    global _posture_model, _posture_encoder
    
    if _posture_model is None or _posture_encoder is None:
        model_path = MODELS_DIR / "ridge_model.pkl"
        encoder_path = MODELS_DIR / "label_encoder.pkl"
        
        if not model_path.exists() or not encoder_path.exists():
            raise FileNotFoundError(f"Model files not found in {MODELS_DIR}")
        
        _posture_model = joblib.load(model_path)
        _posture_encoder = joblib.load(encoder_path)
        print("Posture model loaded successfully")
    
    return _posture_model, _posture_encoder


def get_holistic_processor():
    """Get or create MediaPipe Holistic processor (singleton)"""
    global _holistic
    
    if _holistic is None:
        try:
            # Try with default settings first
            _holistic = mp_holistic.Holistic(
                static_image_mode=True,  # Use True for single image processing
                min_detection_confidence=0.5,
                min_tracking_confidence=0.5,
                model_complexity=1  # Use medium complexity (0=lite, 1=full, 2=heavy)
            )
        except Exception as e:
            # If that fails, try with minimal settings
            print(f"Warning: Failed to initialize Holistic with default settings: {e}")
            print("Attempting with minimal settings...")
            try:
                _holistic = mp_holistic.Holistic(
                    static_image_mode=True,
                    min_detection_confidence=0.3,
                    min_tracking_confidence=0.3,
                    model_complexity=0  # Use lite model
                )
            except Exception as e2:
                print(f"Error: Failed to initialize Holistic with minimal settings: {e2}")
                raise RuntimeError(
                    f"MediaPipe Holistic initialization failed. "
                    f"This may be due to:\n"
                    f"1. Incompatible MediaPipe version - try: pip install --upgrade mediapipe\n"
                    f"2. Missing model files - MediaPipe should download them automatically\n"
                    f"3. System compatibility issues\n"
                    f"Original error: {str(e2)}"
                )
    
    return _holistic


def get_face_detection_processor():
    """Get or create MediaPipe Face Detection processor (singleton)"""
    global _face_detection
    
    if _face_detection is None:
        try:
            _face_detection = mp_face_detection.FaceDetection(
                model_selection=1,  # 1 for full-range (better for multiple faces), 0 for short-range
                min_detection_confidence=0.5
            )
        except Exception as e:
            print(f"Error: Failed to initialize Face Detection: {e}")
            raise RuntimeError(
                f"MediaPipe Face Detection initialization failed. "
                f"This may be due to:\n"
                f"1. Incompatible MediaPipe version - try: pip install --upgrade mediapipe\n"
                f"2. Missing model files\n"
                f"Original error: {str(e)}"
            )
    
    return _face_detection


def flatten_landmarks(landmarks, target_count, use_visibility=False):
    """Flatten MediaPipe landmarks into (x,y,z,visibility) array"""
    data = []
    if landmarks:
        for lm in landmarks.landmark:
            data.extend([lm.x, lm.y, lm.z])
            data.append(lm.visibility if use_visibility and hasattr(lm, 'visibility') else 1.0)
        while len(data) < target_count * 4:
            data.extend([0, 0, 0, 1.0])
    else:
        data = [0] * (target_count * 4)
    return np.array(data[:target_count * 4])


def extract_posture_features(results):
    """Extract features from MediaPipe Holistic results"""
    # Face first
    face = flatten_landmarks(results.face_landmarks, 468, use_visibility=False)
    # Pose second
    pose = flatten_landmarks(results.pose_landmarks, 33, use_visibility=True)
    # Left hand
    left = flatten_landmarks(results.left_hand_landmarks, 21, use_visibility=False)
    # Right hand
    right = flatten_landmarks(results.right_hand_landmarks, 21, use_visibility=False)
    
    # Concatenate in the same order as dataset
    return np.concatenate([face, pose, left, right]).reshape(1, -1)


def detect_posture(image_array):
    """
    Detect posture from image array (numpy array in RGB format)
    
    Args:
        image_array: numpy array of image in RGB format (from cv2.imread or base64 decode)
    
    Returns:
        dict with 'posture_label' and 'confidence' (or None if no landmarks detected)
    """
    try:
        # Load models
        clf, le = load_posture_model()
        
        # Use singleton holistic processor
        holistic = get_holistic_processor()
        
        # Ensure image is in RGB format
        if len(image_array.shape) == 3:
            # If BGR, convert to RGB
            if image_array.dtype == np.uint8:
                rgb_image = cv2.cvtColor(image_array, cv2.COLOR_BGR2RGB)
            else:
                rgb_image = image_array
        else:
            raise ValueError("Image must be a 3-channel RGB image")
        
        # Process image
        results = holistic.process(rgb_image)
        
        # Extract features
        landmarks = extract_posture_features(results)
        
        # Only predict if we have valid landmarks
        if landmarks.sum() == 0:
            return None
        
        # Predict
        y_pred = clf.predict(landmarks)
        pred_class = le.inverse_transform(y_pred)[0]
        
        # Get confidence if model supports it
        confidence = None
        if hasattr(clf, 'predict_proba'):
            proba = clf.predict_proba(landmarks)[0]
            confidence = float(np.max(proba))
        
        return {
            'posture_label': pred_class,
            'confidence': confidence
        }
    
    except Exception as e:
        print(f"Error in detect_posture: {str(e)}")
        raise


def detect_faces(image_array):
    """
    Detect faces from image array (numpy array in RGB format)
    
    Args:
        image_array: numpy array of image in RGB format
    
    Returns:
        dict with 'face_count' and 'detections' list
    """
    try:
        # Get face detection processor
        face_detection = get_face_detection_processor()
        
        # Ensure image is in RGB format
        if len(image_array.shape) == 3:
            if image_array.dtype == np.uint8:
                rgb_image = cv2.cvtColor(image_array, cv2.COLOR_BGR2RGB)
            else:
                rgb_image = image_array
        else:
            raise ValueError("Image must be a 3-channel RGB image")
        
        # Process image
        results = face_detection.process(rgb_image)
        
        # Extract detection data
        detections_list = []
        if results.detections:
            for detection in results.detections:
                bbox = detection.location_data.relative_bounding_box
                detections_list.append({
                    'confidence': float(detection.score[0]),
                    'bbox': {
                        'x': float(bbox.xmin),
                        'y': float(bbox.ymin),
                        'width': float(bbox.width),
                        'height': float(bbox.height)
                    }
                })
        
        return {
            'face_count': len(detections_list),
            'detections': detections_list
        }
    
    except Exception as e:
        print(f"Error in detect_faces: {str(e)}")
        raise


def base64_to_image(base64_string):
    """
    Convert base64 encoded image string to numpy array
    
    Args:
        base64_string: base64 encoded image (with or without data URL prefix)
    
    Returns:
        numpy array of image in BGR format (OpenCV format)
    """
    import base64
    
    # Remove data URL prefix if present
    if ',' in base64_string:
        base64_string = base64_string.split(',')[1]
    
    # Decode base64
    image_data = base64.b64decode(base64_string)
    
    # Convert to numpy array
    nparr = np.frombuffer(image_data, np.uint8)
    
    # Decode image
    image = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
    
    if image is None:
        raise ValueError("Could not decode image from base64 string")
    
    return image


# =========================================================
# Audio Processing for Multiple Speaker Detection
# =========================================================

# Global variables for audio models (singleton pattern)
_vad_model = None
_vad_utils = None
_target_sr = 16000
_overlap_threshold = 4.0  # Lowered from 5.0 to be more sensitive to overlapping voices
_similarity_threshold = 0.50 # Adjusted to 0.50: If similarity is below this, it's definitely NOT the user -> Multiple Speakers

# Global variables for emotion detection model (singleton pattern)
_emotion_model = None
_emotion_processor = None
_emotion_emotions = None


# Global variables for VAD model (singleton pattern)
_vad_model = None
_vad_utils = None
_vad_initialization_failed = False
_vad_lock = threading.Lock()

def load_vad_model():
    """Load Silero VAD model (singleton)"""
    global _vad_model, _vad_utils, _vad_initialization_failed
    
    if _vad_model is None and not _vad_initialization_failed:
        try:
            import torch
            import torchaudio # Explicit check for torchaudio
            _vad_model, utils = torch.hub.load(
                repo_or_dir='snakers4/silero-vad',
                model='silero_vad',
                force_reload=False
            )
            # Ensure model is on CPU
            _vad_model = _vad_model.to('cpu')
            _vad_model.eval()
            _vad_utils = utils
            print("VAD model loaded successfully")
        except Exception as e:
            _vad_initialization_failed = True
            print(f"CRITICAL ERROR: Failed to load VAD model: {e}")
            print("VAD features will be disabled until server restart.")
            return None, None
    
    return _vad_model, _vad_utils


def detect_speech_in_audio(audio_array, sampling_rate):
    """Detect if there is speech in the audio"""
    global _vad_lock
    try:
        import torch
        import numpy as np
        
        model, utils = load_vad_model()
        if model is None or utils is None:
            return False
            
        # SAFETY CHECK: Don't process extremely short or empty audio chunks
        if audio_array is None or len(audio_array) < 512:
            return False
            
        get_speech_timestamps = utils[0]
        
        # Convert numpy array to 1D if needed
        if isinstance(audio_array, np.ndarray):
            audio_array = audio_array.flatten()
            # Ensure it's float32
            if audio_array.dtype != np.float32:
                audio_array = audio_array.astype(np.float32)
        
        # Convert to tensor if needed and ensure it's on CPU
        if not isinstance(audio_array, torch.Tensor):
            audio_tensor = torch.from_numpy(np.asarray(audio_array, dtype=np.float32)).squeeze()
        else:
            # Clone if on CUDA to avoid modifying original
            if audio_array.is_cuda:
                audio_tensor = audio_array.clone().detach()
            else:
                audio_tensor = audio_array.detach().clone() if audio_array.requires_grad else audio_array
        
        # Ensure tensor is on CPU
        audio_tensor = audio_tensor.to('cpu')
        
        # Ensure tensor is contiguous and 1D
        if audio_tensor.dim() > 1:
            audio_tensor = audio_tensor.squeeze()
        elif audio_tensor.dim() == 0:
            audio_tensor = audio_tensor.unsqueeze(0)
        
        audio_tensor = audio_tensor.flatten().contiguous()
        
        if audio_tensor.dtype != torch.float32:
            audio_tensor = audio_tensor.float()

        # Thread-safe VAD execution
        with _vad_lock:
            # Silero VAD v4+ can maintain state; reset it for a clean detection
            if hasattr(model, 'reset_states'):
                model.reset_states()
            
            # Detect speech timestamps
            # Silero expects specific window sizes (multiple of 512 at 16kHz)
            # If the audio is not exactly a multiple, some versions fail in forward()
            # We can pad slightly if needed, but get_speech_timestamps usually handles it
            timestamps = get_speech_timestamps(audio_tensor, model, sampling_rate=sampling_rate)
        
        return len(timestamps) > 0
    except Exception as e:
        # Don't print massive tracebacks every second, just the error
        print(f"Error in speech detection: {str(e)[:100]}...") 
        return False


def harmonic_complexity(audio_array, sampling_rate):
    """Detect overlapping voices using harmonic peak density"""
    try:
        import scipy.signal as signal
        
        # Short-time Fourier transform
        f, t, Zxx = signal.stft(audio_array, sampling_rate, nperseg=512)
        mag = np.abs(Zxx)
        
        # Sum spectrum across time (gives frequency energy)
        spectrum = np.mean(mag, axis=1)
        
        # Detect harmonic peaks
        peaks, _ = signal.find_peaks(
            spectrum, 
            height=np.max(spectrum) * 0.15, # Lowered from 0.2 to catch subtle overlapping voices
            distance=20
        )
        
        return len(peaks)
    except Exception as e:
        print(f"Error in harmonic complexity calculation: {e}")
        return 0


def extract_speaker_embedding(audio_array, sampling_rate):
    """
    Extract speaker embedding from audio using Wav2Vec2 model.
    Reuses the emotion model for efficiency.
    """
    try:
        import torch
        import numpy as np
        
        # Load model (reusing emotion model)
        model, processor, _ = load_emotion_model()
        if model is None or processor is None:
            return None
            
        # Preprocess
        inputs = processor(audio_array, sampling_rate=sampling_rate, return_tensors="pt", padding=True)
        inputs = {k: v.to('cpu') for k, v in inputs.items()}
        
        with torch.inference_mode():
            # Ensure model is on CPU
            model = model.to('cpu')
            # Pass through wav2vec2 base model
            outputs = model.wav2vec2(**inputs)
            # Global mean pooling over the time dimension
            embedding = outputs.last_hidden_state.mean(dim=1).cpu().numpy()[0]
            
        return embedding
    except Exception as e:
        print(f"Error extracting speaker embedding: {e}")
        return None


def detect_multiple_speakers(audio_array, sampling_rate, reference_embedding=None):
    """
    Detect multiple speakers in audio chunk
    
    Args:
        audio_array: numpy array of audio data (float32, mono)
        sampling_rate: sampling rate of the audio
        reference_embedding: list of floats (optional) - the reference speaker embedding
    
    Returns:
        dict with:
            - has_speech: bool
            - is_multiple_speakers: bool
            - is_interviewee: bool
            - current_embedding: list (returned only if no reference provided)
            - harmonic_complexity: int
            - confidence: float (0-1)
    """
    # OPTIMIZED THRESHOLDS
    _target_sr = 16000
    _similarity_threshold = 0.50  # Lowered from 0.60 to be more forgiving to the main speaker
    _overlap_threshold = 4        # Harmonic complexity threshold for overlaps
    
    try:
        # Resample to 16kHz if needed
        if sampling_rate != _target_sr:
            import librosa
            audio_resampled = librosa.resample(
                audio_array, 
                orig_sr=sampling_rate, 
                target_sr=_target_sr
            )
        else:
            audio_resampled = audio_array
        
        # Energy check
        energy = np.mean(audio_resampled ** 2)
        if energy < 1e-5:
            return {
                'has_speech': False,
                'is_multiple_speakers': False,
                'is_interviewee': True,
                'harmonic_complexity': 0,
                'confidence': 0.0
            }
        
        # Speech detection
        has_speech = detect_speech_in_audio(audio_resampled, _target_sr)
        if not has_speech:
            return {
                'has_speech': False,
                'is_multiple_speakers': False,
                'is_interviewee': True,
                'harmonic_complexity': 0,
                'confidence': 0.0
            }
        
        # Measure harmonic complexity
        h = harmonic_complexity(audio_resampled, _target_sr)
        
        # NEW: Speaker Identification via Embeddings
        current_embedding = extract_speaker_embedding(audio_resampled, _target_sr)
        is_interviewee = True
        similarity = 1.0
        
        if reference_embedding is not None and current_embedding is not None:
            # Calculate cosine similarity
            ref = np.array(reference_embedding)
            curr = np.array(current_embedding)
            
            # Normalize
            ref_norm = ref / (np.linalg.norm(ref) + 1e-6)
            curr_norm = curr / (np.linalg.norm(curr) + 1e-6)
            
            similarity = float(np.dot(ref_norm, curr_norm))
            # Refined threshold for "same speaker"
            is_interviewee = similarity > _similarity_threshold
            print(f"Speaker Similarity: {similarity:.4f} (is_interviewee: {is_interviewee})")
        
        # Determine if multiple speakers
        # 1. High harmonic complexity (overlapping peaks)
        # 2. OR if it is NOT the interviewee (Unknown Speaker = Intruder = Multiple People effectively)
        # 3. Or if primary voice doesn't match and similarity is mid-range (mixed)
        is_multiple = h > _overlap_threshold
        
        if not is_interviewee:
             # FIXED: If it is NOT the interviewee, we flag it as multiple speakers (unauthorized presence)
             is_multiple = True
        
        if not is_interviewee and similarity > 0.45 and similarity < 0.65: 
            # This range often indicates a mix of the reference voice and something else
            is_multiple = True
        
        # Calculate confidence
        confidence = min(h / 30.0, 1.0) if is_multiple else similarity
        
        result = {
            'has_speech': True,
            'is_multiple_speakers': is_multiple,
            'is_interviewee': is_interviewee,
            'harmonic_complexity': int(h),
            'confidence': float(confidence),
            'similarity': similarity
        }
        
        # Return embedding if this is the first speech (for enrollment)
        # Only enroll if we strongly believe it's a valid single speaker or just starting
        if reference_embedding is None:
            # Only auto-enroll if complexity is low (clean audio)
            if h <= _overlap_threshold + 2:
                 result['current_embedding'] = current_embedding.tolist() if current_embedding is not None else None
            
        return result
    
    except Exception as e:
        print(f"Error in multiple speaker detection: {e}")
        return {
            'has_speech': False,
            'is_multiple_speakers': False,
            'is_interviewee': True, # Default to true on error to avoid false positives
            'harmonic_complexity': 0,
            'confidence': 0.0,
            'error': str(e)
        }


# =========================================================
# Emotion Detection Functions
# =========================================================

# Global variables for emotion detection model (singleton pattern)
_emotion_model = None
_emotion_processor = None
_emotion_emotions = None
_emotion_initialization_failed = False

def load_emotion_model():
    """Load Wav2Vec2 emotion detection model (singleton)"""
    global _emotion_model, _emotion_processor, _emotion_emotions, _emotion_initialization_failed
    
    if _emotion_model is None and not _emotion_initialization_failed:
        try:
            from transformers import Wav2Vec2Processor, Wav2Vec2ForSequenceClassification
            import torch
            from pathlib import Path
            
            MODEL_DIR = MODELS_DIR / "wav2vec2_emotion_final"
            
            if not MODEL_DIR.exists():
                raise FileNotFoundError(f"Emotion model directory not found: {MODEL_DIR}")
            
            print("Loading emotion detection model...")
            
            # Disable torch.compile during model loading
            import os
            original_env = os.environ.get('TORCH_COMPILE_DISABLE', None)
            os.environ['TORCH_COMPILE_DISABLE'] = '1'
            
            try:
                _emotion_processor = Wav2Vec2Processor.from_pretrained(str(MODEL_DIR))
                # FORCE device_map=None to prevent accelerate from creating meta tensors
                # FORCE low_cpu_mem_usage=False to ensure immediate loading to CPU RAM
                _emotion_model = Wav2Vec2ForSequenceClassification.from_pretrained(
                    str(MODEL_DIR), 
                    device_map=None, 
                    low_cpu_mem_usage=False
                )
                
                # Explicitly move model to CPU
                _emotion_model = _emotion_model.to('cpu')
                _emotion_model.eval()
                
                # Ensure model is not compiled
                if hasattr(_emotion_model, '_orig_mod'):
                    _emotion_model = _emotion_model._orig_mod
                
                _emotion_emotions = list(_emotion_model.config.id2label.values())
                print(f"Emotion model loaded! Detecting {len(_emotion_emotions)} emotions: {_emotion_emotions}")
            finally:
                # Restore environment
                if original_env is None:
                    os.environ.pop('TORCH_COMPILE_DISABLE', None)
                else:
                    os.environ['TORCH_COMPILE_DISABLE'] = original_env
        except Exception as e:
            _emotion_initialization_failed = True
            print(f"CRITICAL ERROR: Failed to load Emotion model: {e}")
            print("Emotion logic will return NEUTRAL until server restart.")
            _emotion_emotions = ['neutral']
            return None, None, _emotion_emotions
    
    return _emotion_model, _emotion_processor, _emotion_emotions


def preprocess_audio_for_emotion(audio_array, sampling_rate=16000):
    """
    Preprocess audio for emotion detection (matches training distribution)
    
    Args:
        audio_array: numpy array of audio data (float32, mono)
        sampling_rate: sampling rate of the audio
    
    Returns:
        preprocessed audio array
    """
    import numpy as np
    from scipy.signal import butter, lfilter
    import librosa
    
    TARGET_SR = 16000
    FRAME = 1  # seconds
    TARGET_RMS = 0.1
    
    # Resample to 16kHz if needed
    if sampling_rate != TARGET_SR:
        audio_array = librosa.resample(audio_array, orig_sr=sampling_rate, target_sr=TARGET_SR)
    
    audio = audio_array.flatten().astype(np.float32)
    
    # Bandpass filter (100-3400 Hz)
    def butter_bandpass(lowcut, highcut, fs, order=4):
        nyq = 0.5 * fs
        low = lowcut / nyq
        high = highcut / nyq
        b, a = butter(order, [low, high], btype='band')
        return b, a
    
    b, a = butter_bandpass(100, 3400, TARGET_SR)
    audio = lfilter(b, a, audio)
    
    # Trim silence (less aggressive - only remove very quiet parts)
    # Use top_db=20 instead of 25 to be less aggressive
    if len(audio) > 0:
        audio_trimmed, _ = librosa.effects.trim(audio, top_db=20)
        # Only use trimmed if it didn't remove too much
        if len(audio_trimmed) >= len(audio) * 0.3:  # Keep if at least 30% remains
            audio = audio_trimmed
    
    # Normalize RMS
    rms = np.sqrt(np.mean(audio**2))
    if rms > 1e-6:
        audio = audio * (TARGET_RMS / rms)
    
    # Pitch normalization
    try:
        audio = librosa.effects.pitch_shift(audio, sr=TARGET_SR, n_steps=-1.5)
    except Exception as e:
        print(f"Pitch shift skipped: {e}")
        pass # use audio as is
    
    # Match length
    target_len = int(FRAME * TARGET_SR)
    if len(audio) > target_len:
        audio = audio[:target_len]
    else:
        pad_len = target_len - len(audio)
        audio = np.pad(audio, (0, pad_len))
    
    return audio


def detect_emotion(audio_array, sampling_rate=16000):
    """
    Detect emotion from audio array
    
    Args:
        audio_array: numpy array of audio data (float32, mono)
        sampling_rate: sampling rate of the audio
    
    Returns:
        dict with:
            - dominant_emotion: str
            - emotion_probabilities: dict mapping emotion names to probabilities
            - confidence: float (confidence of dominant emotion)
            - has_speech: bool
    """
    try:
        import torch
        
        # NEW: Integrate Silero VAD for better gating
        # Check if audio has speech using VAD
        has_speech = detect_speech_in_audio(audio_array, sampling_rate)
        if not has_speech:
            return {
                'dominant_emotion': 'neutral',
                'emotion_probabilities': {},
                'confidence': 0.0,
                'has_speech': False,
                'error': 'No speech detected'
            }
        
        # Check minimum length (at least 0.3 seconds of audio for some models)
        if len(audio_array) < int(0.3 * sampling_rate):
            return {
                'dominant_emotion': 'neutral',
                'emotion_probabilities': {},
                'confidence': 0.0,
                'has_speech': False,
                'error': 'Audio too short'
            }
        
        # Load model
        model, processor, emotions = load_emotion_model()
        if model is None or processor is None:
            return {
                'dominant_emotion': 'neutral',
                'emotion_probabilities': {},
                'confidence': 0.0,
                'error': 'Emotion model failed to load'
            }
        
        # Preprocess audio
        processed_audio = preprocess_audio_for_emotion(audio_array, sampling_rate)
        
        # Check if processed audio still has content (trimming might have removed everything)
        processed_energy = np.mean(processed_audio ** 2)
        if processed_energy < 1e-6:
            return {
                'dominant_emotion': 'neutral',
                'emotion_probabilities': {},
                'confidence': 0.0,
                'error': 'Processed audio too quiet'
            }
        
        # Predict
        inputs = processor(processed_audio, sampling_rate=16000, return_tensors="pt", padding=True)
        
        # Ensure inputs are on CPU
        inputs = {k: v.to('cpu') for k, v in inputs.items()}
        
        # Disable torch.compile/dynamo to avoid meta device issues
        import os
        import torch._dynamo
        
        # Save original environment and config
        original_env = os.environ.get('TORCH_COMPILE_DISABLE', None)
        os.environ['TORCH_COMPILE_DISABLE'] = '1'
        
        # Disable dynamo compilation
        original_disable = getattr(torch._dynamo.config, 'disable', False)
        original_suppress = getattr(torch._dynamo.config, 'suppress_errors', False)
        torch._dynamo.config.disable = True
        torch._dynamo.config.suppress_errors = True
        
        try:
            # Use torch.inference_mode() which is more restrictive than no_grad()
            # and ensures no autograd/compilation
            with torch.inference_mode():
                # Ensure model is in eval mode
                model.eval()
                # Ensure model and all buffers are on CPU
                model = model.to('cpu')
                
                # Run inference
                logits = model(**inputs).logits
        finally:
            # Restore original config
            if original_env is None:
                os.environ.pop('TORCH_COMPILE_DISABLE', None)
            else:
                os.environ['TORCH_COMPILE_DISABLE'] = original_env
            torch._dynamo.config.disable = original_disable
            torch._dynamo.config.suppress_errors = original_suppress
        
        # Soften predictions with temperature
        TEMP = 0.9
        logits = logits / TEMP
        probs = torch.softmax(logits, dim=-1).numpy()[0]
        
        # Map emotion names to frontend expected names (normalize emotion labels)
        emotion_mapping = {
            'fearful': 'fear',
            'surprised': 'surprise',
            'calm': 'neutral'  # Map calm to neutral for consistency
        }
        
        # Create emotion probabilities dictionary with normalized names
        emotion_probs = {}
        for emotion, prob in zip(emotions, probs):
            normalized_name = emotion_mapping.get(emotion, emotion)
            # If multiple emotions map to same normalized name, take the max probability
            if normalized_name in emotion_probs:
                emotion_probs[normalized_name] = max(emotion_probs[normalized_name], float(prob))
            else:
                emotion_probs[normalized_name] = float(prob)
        
        # Get dominant emotion from normalized probabilities (more accurate after merging)
        dominant_emotion = max(emotion_probs.items(), key=lambda x: x[1])[0]
        confidence = emotion_probs[dominant_emotion]
        
        # Print all emotion probabilities for debugging
        print(f"\n=== Emotion Detection Results ===")
        print(f"Dominant emotion (normalized): {dominant_emotion}")
        print(f"Confidence: {confidence:.4f}")
        print("All probabilities (normalized):")
        for emotion, prob in sorted(emotion_probs.items(), key=lambda x: x[1], reverse=True):
            print(f"  {emotion}: {prob:.4f}")
        print("===============================\n")
        
        # Only filter out extremely low confidence predictions (below 0.1)
        # With 8 emotion classes, random chance is ~0.125, so 0.1 is very low
        # Trust the model's predictions for anything above this threshold
        if confidence < 0.1:
            # Low confidence, but don't force to 0.0, show what we have or a minimum baseline
            print(f"⚠️ Low confidence ({confidence:.4f}), still reporting detected emotion")
            confidence = max(confidence, 0.05) # Minimum baseline for display
        else:
            # Confidence is reasonable, trust the model's prediction
            print(f"✅ Accepting emotion: {dominant_emotion} with confidence {confidence:.4f}")
        
        try:
            with open("C:/Users/ittra/OneDrive/Desktop/Collegeproject/Backend/debug_emotion.txt", "w") as f:
                f.write(f"SUCCESS: {dominant_emotion} with confidence {confidence}\n")
        except:
            pass

        return {
            'dominant_emotion': dominant_emotion,
            'emotion_probabilities': emotion_probs,
            'confidence': float(confidence),
            'has_speech': True
        }
    
    except Exception as e:
        import traceback
        err_msg = traceback.format_exc()
        try:
            with open("C:/Users/ittra/OneDrive/Desktop/Collegeproject/Backend/debug_emotion.txt", "w") as f:
                f.write(f"ERROR: {e}\n{err_msg}\n")
        except:
            pass
        return {
            'dominant_emotion': 'neutral',
            'emotion_probabilities': {},
            'confidence': 0.0,
            'error': str(e)
        }


def base64_to_audio(base64_string, sampling_rate=16000):
    """
    Convert base64 encoded audio string to numpy array
    Supports both WAV and WebM formats
    
    Args:
        base64_string: base64 encoded audio (WAV or WebM format)
        sampling_rate: expected sampling rate (used for WebM conversion)
    
    Returns:
        tuple: (audio_array, actual_sampling_rate)
    """
    import base64
    import io
    import wave
    
    # Remove data URL prefix if present
    if ',' in base64_string:
        base64_string = base64_string.split(',')[1]
    
    # Decode base64
    audio_data = base64.b64decode(base64_string)
    
    # Try to detect format by checking magic bytes
    audio_io = io.BytesIO(audio_data)
    
    # Check if it's WAV (starts with 'RIFF')
    if audio_data[:4] == b'RIFF':
        try:
            with wave.open(audio_io, 'rb') as wav_file:
                frames = wav_file.getnframes()
                sample_rate = wav_file.getframerate()
                channels = wav_file.getnchannels()
                sample_width = wav_file.getsampwidth()
                
                # Read audio data
                audio_bytes = wav_file.readframes(frames)
                
                # Convert to numpy array
                if sample_width == 1:
                    dtype = np.uint8
                    audio_array = np.frombuffer(audio_bytes, dtype=dtype).astype(np.float32) / 128.0 - 1.0
                elif sample_width == 2:
                    dtype = np.int16
                    audio_array = np.frombuffer(audio_bytes, dtype=dtype).astype(np.float32) / 32768.0
                elif sample_width == 4:
                    dtype = np.int32
                    audio_array = np.frombuffer(audio_bytes, dtype=dtype).astype(np.float32) / 2147483648.0
                else:
                    raise ValueError(f"Unsupported sample width: {sample_width}")
                
                # Convert to mono if stereo
                if channels == 2:
                    audio_array = audio_array.reshape(-1, 2).mean(axis=1)
                elif channels > 2:
                    audio_array = audio_array.reshape(-1, channels).mean(axis=1)
            
            return audio_array, sample_rate
        except Exception as e:
            raise ValueError(f"Failed to decode WAV audio: {e}")
    
    # If not WAV, try WebM/Opus (requires pydub and ffmpeg)
    else:
        try:
            from pydub import AudioSegment
            from pydub.utils import which
            
            # Check if ffmpeg is available
            if not which("ffmpeg"):
                raise RuntimeError(
                    "WebM audio format requires ffmpeg. "
                    "Install it: brew install ffmpeg (macOS) or apt-get install ffmpeg (Linux)"
                )
            
            # Load WebM audio
            audio_segment = AudioSegment.from_file(audio_io, format="webm")
            
            # Convert to mono and set sample rate
            audio_segment = audio_segment.set_channels(1)
            audio_segment = audio_segment.set_frame_rate(sampling_rate)
            
            # Convert to numpy array
            audio_array = np.array(audio_segment.get_array_of_samples(), dtype=np.float32)
            audio_array = audio_array / 32768.0  # Normalize to [-1, 1]
            
            return audio_array, sampling_rate
            
        except ImportError:
            raise RuntimeError(
                "WebM audio format requires pydub. Install it: pip install pydub"
            )
        except Exception as e:
            raise ValueError(f"Failed to decode WebM audio: {e}")

