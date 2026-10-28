#!/bin/bash
# Quick fix script for MediaPipe installation issues

echo "🔧 Fixing MediaPipe installation..."

# Activate virtual environment if it exists
if [ -d ".venv" ]; then
    echo "Activating .venv..."
    source .venv/bin/activate
elif [ -d "env" ]; then
    echo "Activating env..."
    source env/bin/activate
fi

# Uninstall MediaPipe
echo "Uninstalling MediaPipe..."
pip uninstall mediapipe -y

# Clear pip cache
echo "Clearing pip cache..."
pip cache purge

# Reinstall MediaPipe 0.10.7 (stable version)
echo "Installing MediaPipe 0.10.7..."
pip install mediapipe==0.10.7

# Verify installation
echo ""
echo "Verifying installation..."
python3 -c "import mediapipe as mp; print(f'✓ MediaPipe {mp.__version__} installed successfully'); print(f'✓ Has solutions: {hasattr(mp, \"solutions\")}')" 2>&1

echo ""
echo "✅ Done! Try running: python3 manage.py runserver"

