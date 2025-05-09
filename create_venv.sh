#!/bin/bash

VENV_DIR=".venv"

# Check if the virtual environment directory already exists
if [ -d "$VENV_DIR" ]; then
  echo "Virtual environment '$VENV_DIR' already exists."
else
  echo "Creating virtual environment '$VENV_DIR'..."
  # Create the virtual environment using python3
  python3 -m venv "$VENV_DIR"
  if [ $? -eq 0 ]; then
    echo "Virtual environment created successfully."
    echo "To activate it, run: source $VENV_DIR/bin/activate"
  else
    echo "Failed to create virtual environment."
    exit 1
  fi
fi

exit 0 