### AI Avatar-Based Mock Interview System

A multi-modal AI platform that evaluates candidates during mock interviews by analyzing body language, processing speech emotion, transcribing audio, scoring answer accuracy via LLM/NLP components, and rendering an interactive AI avatar. 

###  System Architecture (5 Core Modules)

* **1. Posture & Gesture Analytics Module**
Uses MediaPipe Holistic and a Ridge Classifier to extract 2,172 landmark vectors across ~6,000 video frames, classifying candidate posture (*Appropriate, Cheating, Defensive*) with **98% test accuracy**.
* **2. Speech Emotion Recognition Module**
Features a fine-tuned Wav2Vec2 transformer model trained on a 2,800-sample audio dataset to recognize and analyze emotional contexts across **7 distinct classes**.
* **3. Audio Transcription (Speech-to-Text) Module**
Processes live audio streams, handles resampling data steps, and accurately transcribes spoken candidate responses into structured text strings for evaluation.
* **4. LLM Q&A & Semantic Evaluation Module**
Employs SBERT (Sentence-BERT) and a cosine-similarity comparison engine to score transcribed answers against evaluation matrices and generate automated feedback.
* **5. Interactive AI Avatar & Frontend Interface Module**
Integrates the gesture, speech, and textual modules into a unified graphical user interface featuring an AI avatar that interacts dynamically with the candidate.





