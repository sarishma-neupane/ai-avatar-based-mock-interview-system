# =========================================================
# Import required libraries
# =========================================================
import cv2
import numpy as np
import joblib
import mediapipe as mp
mp_drawing = mp.solutions.drawing_utils

# =========================================================
# Load trained model + encoder
# =========================================================
try:
    clf = joblib.load("ridge_model.pkl")         # Make sure path is correct
    le = joblib.load("label_encoder.pkl")
except Exception as e:
    print(f"Error loading model or label encoder: {e}")
    exit(1)

# =========================================================
# Initialize MediaPipe Holistic
# =========================================================
mp_holistic = mp.solutions.holistic
holistic = mp_holistic.Holistic(static_image_mode=False)

# =========================================================
# Helper function (same as dataset creation)
# =========================================================
def flatten_landmarks(landmarks, target_count, use_visibility=False):
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

# =========================================================
# Extract landmarks in correct order: face → pose → left → right
# =========================================================
def extract_features(results):
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

# =========================================================
# Start webcam
# =========================================================
cap = cv2.VideoCapture(0)
if not cap.isOpened():
    print("Error: Could not open webcam.")
    holistic.close()
    exit(1)

print("🎥 Webcam started. Press 'q' to quit.")

try:
    while cap.isOpened():
        ret, frame = cap.read()
        if not ret:
            print("Error: Failed to read frame from webcam.")
            break

        # Convert BGR → RGB
        image = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        image.flags.writeable = False
        results = holistic.process(image)

        # Convert back to BGR
        image.flags.writeable = True
        image = cv2.cvtColor(image, cv2.COLOR_RGB2BGR)

        # Draw landmarks
        mp_drawing.draw_landmarks(image, results.pose_landmarks, mp_holistic.POSE_CONNECTIONS)
        mp_drawing.draw_landmarks(image, results.face_landmarks, mp_holistic.FACEMESH_TESSELATION)
        mp_drawing.draw_landmarks(image, results.left_hand_landmarks, mp_holistic.HAND_CONNECTIONS)
        mp_drawing.draw_landmarks(image, results.right_hand_landmarks, mp_holistic.HAND_CONNECTIONS)

        # Extract features
        landmarks = extract_features(results)

        # Debug: confirm feature length = 2172
        print("Feature vector length:", landmarks.shape[1])

        if landmarks.sum() != 0:
            # Predict
            y_pred = clf.predict(landmarks)
            pred_class = le.inverse_transform(y_pred)[0]

            # Format probabilities
            prob_text = f"Posture: {pred_class}"

            # Show predicted class
            cv2.putText(image, prob_text, (20, 40),
                        cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2)

        # Display
        cv2.imshow("Posture Detection - Ridge Classifier", image)

        # Quit on pressing 'q'
        if cv2.waitKey(1) & 0xFF == ord('q'):
            break
finally:
    cap.release()
    cv2.destroyAllWindows()
    holistic.close()
