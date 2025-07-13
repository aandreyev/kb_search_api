#!/bin/bash

# Script to find and install all requirements.txt files in the project.
# This approach is dynamic and will automatically install dependencies
# for any new service directories containing a requirements.txt file.

set -e  # Exit on any error

# Get the root directory of the project
ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "🚀 Installing all requirements.txt files from the project..."
echo "========================================================"

# Check if a virtual environment exists and activate it
VENV_PATH="$ROOT_DIR/.venv"
if [ -d "$VENV_PATH" ]; then
    echo "🐍 Activating virtual environment..."
    source "$VENV_PATH/bin/activate"
    echo "✅ Virtual environment activated."
else
    echo "⚠️  No virtual environment found at '$VENV_PATH'."
    echo "   Consider running ./create_venv.sh first."
    echo "   Continuing with system Python, which may have unintended side effects."
    sleep 2 # Pause for user to read the warning
fi

# Use find to locate all requirements.txt files, excluding the .venv directory
# and then loop through them to install.
echo ""
echo "🔍 Searching for all requirements.txt files..."

# The `find` command searches for files named 'requirements.txt'.
# `-not -path "./.venv/*"` excludes the virtual environment directory.
# The `while` loop reads each found path line by line.
find "$ROOT_DIR" -type f -name "requirements.txt" -not -path "$VENV_PATH/*" | while read -r requirements_file; do
    # Get the directory containing the requirements.txt file
    dir=$(dirname "$requirements_file")
    
    echo ""
    echo "--------------------------------------------------------"
    echo "📦 Found requirements in: $dir"
    echo "--------------------------------------------------------"
    
    # Temporarily change to the directory to run pip install
    (
        echo "Installing dependencies from $requirements_file..."
        cd "$dir" || exit
        
        # Run pip install, capturing output for better error reporting
        if pip install -r requirements.txt; then
            echo "✅ Successfully installed requirements from $dir"
        else
            echo "❌ Failed to install requirements from $dir"
            exit 1 # Exit the subshell with an error
        fi
    )
    # Check if the subshell command failed
    if [ $? -ne 0 ]; then
        echo "❌ An error occurred during installation. Aborting."
        exit 1
    fi
done

echo ""
echo "========================================================"
echo "🎉 All requirements have been successfully installed!"
echo "========================================================"
echo ""
echo "💡 Note: If you primarily use Docker for development,"
echo "   these dependencies are also installed within the containers during the build process." 