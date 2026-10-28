import cv2
import mediapipe as mp
import numpy as np

# Initialize MediaPipe Face Detection
mp_face_detection = mp.solutions.face_detection
mp_drawing = mp.solutions.drawing_utils

def detect_faces():
    # Initialize the camera
    cap = cv2.VideoCapture(0)
    
    if not cap.isOpened():
        print("Error: Could not open camera")
        return
    
    # Initialize face detection
    with mp_face_detection.FaceDetection(
        model_selection=0,  # 0 for short-range, 1 for full-range
        min_detection_confidence=0.5
    ) as face_detection:
        
        print("Camera opened successfully!")
        print("Press 'q' to quit")
        
        while True:
            # Read frame from camera
            ret, frame = cap.read()
            
            if not ret:
                print("Error: Failed to capture frame")
                break
            
            # Flip frame horizontally for mirror effect
            frame = cv2.flip(frame, 1)
            
            # Convert BGR to RGB (MediaPipe uses RGB)
            rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            
            # Process the frame and detect faces
            results = face_detection.process(rgb_frame)
            
            # Draw face detection annotations
            if results.detections:
                for detection in results.detections:
                    # Draw bounding box
                    mp_drawing.draw_detection(frame, detection)
                    
                    # Get bounding box coordinates
                    bbox = detection.location_data.relative_bounding_box
                    h, w, _ = frame.shape
                    x = int(bbox.xmin * w)
                    y = int(bbox.ymin * h)
                    width = int(bbox.width * w)
                    height = int(bbox.height * h)
                    
                    # Draw confidence score
                    confidence = detection.score[0]
                    cv2.putText(
                        frame,
                        f'Face: {confidence:.2f}',
                        (x, y - 10),
                        cv2.FONT_HERSHEY_SIMPLEX,
                        0.5,
                        (0, 255, 0),
                        2
                    )
                
                # Display face count
                face_count = len(results.detections)
                cv2.putText(
                    frame,
                    f'Faces Detected: {face_count}',
                    (10, 30),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    1,
                    (0, 255, 0),
                    2
                )
            else:
                cv2.putText(
                    frame,
                    'No faces detected',
                    (10, 30),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    1,
                    (0, 0, 255),
                    2
                )
            
            # Display the frame
            cv2.imshow('Multi-Face Detection', frame)
            
            # Break loop on 'q' key press
            if cv2.waitKey(1) & 0xFF == ord('q'):
                break
    
    # Release resources
    cap.release()
    cv2.destroyAllWindows()
    print("Camera released. Goodbye!")

if __name__ == "__main__":
    detect_faces()

