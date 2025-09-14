# Integrating RSPS-bot-clean with VS Code

This guide will help you set up and run the RSPS-bot-clean project in Visual Studio Code.

## Prerequisites

Before starting, ensure you have:
1. Visual Studio Code installed
2. Python installed (3.8 or higher)

If you don't have these installed, please follow the first two steps from the previous guide:
1. Install Visual Studio Code from [https://code.visualstudio.com/](https://code.visualstudio.com/)
2. Install Python from [https://www.python.org/downloads/](https://www.python.org/downloads/) (remember to check "Add Python to PATH")

## Step 1: Open the Project in VS Code

1. Open Visual Studio Code
2. Click on "File" in the menu bar
3. Select "Open Folder..."
4. Navigate to the `RSPS-bot-clean` folder
5. Click "Select Folder"

## Step 2: Install Required Extensions

1. In VS Code, click the Extensions icon on the left sidebar (or press `Ctrl+Shift+X`)
2. Search for and install these extensions:
   - Python (by Microsoft)
   - Pylance (by Microsoft)

## Step 3: Set Up the Python Environment

1. Open the terminal in VS Code by pressing `Ctrl+`` ` (backtick) or going to Terminal → New Terminal
2. In the terminal, type: `python -m venv venv` and press Enter
3. Activate the virtual environment:
   - On Windows: `venv\Scripts\activate`
   - On Mac/Linux: `source venv/bin/activate`
4. Install the required packages by typing: `pip install -r requirements.txt` and pressing Enter

## Step 4: Configure Python Interpreter

1. Press `Ctrl+Shift+P` to open the command palette
2. Type "Python: Select Interpreter" and select it
3. Choose the interpreter that shows your project's venv path (should look like `./venv/Scripts/python.exe` on Windows)

## Step 5: Run the Bot

You have several options to run the bot:

### Option 1: Using the Startup Scripts (Easiest)
1. In the file explorer (left sidebar), find `start_bot.bat` (Windows) or `start_bot.sh` (Mac/Linux)
2. Double-click the appropriate file for your operating system

### Option 2: Direct Python Execution
1. Open the terminal in VS Code (`Ctrl+`` `)
2. Make sure your virtual environment is activated (you should see `(venv)` at the beginning of the command line)
3. Run the bot with: `python run.py`

### Option 3: From VS Code (Recommended for Development)
1. In the file explorer, open `run.py`
2. Press `Ctrl+F5` to run without debugging
3. Or right-click in the editor and select "Run Python File in Terminal"

## Step 6: Using the Bot

1. When the bot starts, you'll see a graphical interface
2. Follow the on-screen instructions to:
   - Select the area of your screen to monitor
   - Configure detection parameters
   - Set up humanization settings
   - Start the bot

## Project Structure

The `RSPS-bot-clean` directory contains:
- `run.py`: Main execution script
- `requirements.txt`: List of required Python packages
- `rspsbot/`: Main source code directory
- `README.md`: Project overview and setup instructions
- `USER_GUIDE.md`: Detailed usage instructions
- `INSTRUCTIONS.md`: Additional setup information
- `start_bot.bat`/`start_bot.sh`: Easy startup scripts
- `logs/`: Directory for log files
- `profiles/`: Directory for bot profiles
- `stats/`: Directory for statistics
- `outputs/`: Directory for output files

## Troubleshooting Common Issues

### If you get "Module not found" errors:
1. Make sure you installed the requirements with `pip install -r requirements.txt`
2. Check that you've selected the correct Python interpreter (Step 4)

### If the bot doesn't detect colors:
1. Make sure you've properly selected the screen area in the GUI
2. Check that your game is visible and not minimized
3. Verify that the color settings match what you're trying to detect

### If you get permission errors:
1. Try running VS Code as an administrator
2. On Windows, you might need to allow screen recording permissions in Settings → Privacy

## Additional Tips

1. **Save your work frequently**: Press `Ctrl+S` to save files
2. **Use the integrated terminal**: You can run all commands directly in VS Code's terminal
3. **Explore the file structure**: Use the explorer panel on the left to navigate files
4. **Access documentation**: Open `README.md` and `USER_GUIDE.md` to understand the bot's features

## Next Steps

1. Read `README.md` and `USER_GUIDE.md` to understand all bot features
2. Experiment with different settings in the GUI
3. Check the log files in the `logs/` folder if you encounter issues
4. Modify profiles in the `profiles/` folder to customize behavior

This clean version of the bot includes all the essential features without any development artifacts, making it easier to use for its intended purpose.