# RSPS Color Bot - Getting Started Instructions

This document provides step-by-step instructions to set up and run the RSPS Color Bot.

## 1. Setup

### Install Dependencies

First, install all required dependencies using pip:

```bash
pip install -r requirements.txt
```

This will install all necessary Python packages including PyQt5, OpenCV, NumPy, and other required libraries.

### Directory Structure

The bot has the following directory structure:
- `rspsbot/` - Core bot code
- `logs/` - Log files will be stored here
- `profiles/` - Bot configuration profiles will be stored here
- `stats/` - Statistics and performance data will be stored here
- `outputs/` - Output files and images will be stored here

## 2. Running the Bot

### Basic Usage

To run the bot with the graphical user interface:

```bash
python run.py
```

This will start the bot with the default configuration.

### Configuration

1. When the bot starts, go to the "Main" tab
2. Select the RuneScape window in the dropdown
3. Click on "Focus" to activate the window
4. Configure detection settings in the "Detection Settings" tab
5. Configure combat settings in the "Combat Settings" tab

### Saving and Loading Profiles

1. Go to the "Profiles" tab
2. Click "Save As" to save your current configuration
3. Give your profile a name
4. Use "Load" to load a saved profile

## 3. Advanced Features

### Enhanced Humanization

The bot includes advanced humanization features that make mouse and keyboard actions appear more human-like:

1. Go to the "Humanization" tab
2. Choose a personality profile or customize individual settings
3. Configure fatigue simulation for longer sessions

### Adaptive Detection

The bot includes adaptive detection algorithms that adjust to different game environments:

1. Go to the "Adaptive Detection" tab
2. Enable adaptive detection
3. Configure learning rate and exploration rate

## 4. Testing Features

You can test various features of the bot using the included test scripts:

- Test humanization: `python test_enhanced_humanization.py`
- Test adaptive detection: `python test_enhanced_adaptive_detection.py`
- Test integrated features: `python test_integrated_features.py`

## 5. Troubleshooting

### Common Issues

1. **GUI doesn't start**: Make sure PyQt5 is properly installed
2. **Detection not working**: Check that the game window is properly focused
3. **Mouse/keyboard actions not working**: Ensure you have proper permissions

### Logs

Check the `logs/` directory for detailed log files that can help diagnose issues.

## 6. Additional Resources

- See `README.md` for a general overview of the bot
- See `USER_GUIDE.md` for detailed usage instructions

## Disclaimer

This bot is intended for educational purposes and for use on private servers where botting is allowed. Use on official RuneScape servers is against the rules and can lead to a ban.