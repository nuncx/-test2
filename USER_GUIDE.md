# RSPS Color Bot v3 - User Guide

## Introduction

Welcome to RSPS Color Bot v3, an advanced color detection bot for RuneScape Private Servers. This guide will help you get started with the bot and explain its features and settings.

## Table of Contents

1. [Installation](#installation)
2. [Getting Started](#getting-started)
3. [Main Interface](#main-interface)
4. [Detection Settings](#detection-settings)
5. [Combat Settings](#combat-settings)
6. [Teleport Settings](#teleport-settings)
7. [Potion Settings](#potion-settings)
8. [Instance Settings](#instance-settings)
9. [Statistics](#statistics)
10. [Profiles](#profiles)
11. [Logs & Debugging](#logs--debugging)
12. [Troubleshooting](#troubleshooting)
13. [FAQ](#faq)

## Installation

### System Requirements

- Windows, macOS, or Linux operating system
- Python 3.8 or higher
- 4GB RAM minimum (8GB recommended)
- Screen resolution of 1280x720 or higher

### Installation Steps

1. **Install Python**:
   - Download and install Python 3.8 or higher from [python.org](https://www.python.org/downloads/)
   - Make sure to check "Add Python to PATH" during installation

2. **Download the Bot**:
   - Clone the repository: `git clone https://github.com/yourusername/RSPS-color-bot-v3.git`
   - Or download the ZIP file and extract it

3. **Install Dependencies**:
   - Open a terminal/command prompt
   - Navigate to the bot directory: `cd RSPS-color-bot-v3`
   - Install required packages: `pip install -r requirements.txt`

4. **Run the Bot**:
   - Start the bot: `python run.py`
   - For debug mode: `python run.py --debug`

## Getting Started

### Quick Start Guide

1. **Launch the Bot**:
   - Run `python run.py` from the bot directory

2. **Select Game Window**:
   - In the "Main" tab, select your RuneScape window from the dropdown

3. **Configure Detection**:
   - Go to the "Detection Settings" tab
   - Set up tile and monster colors (see [Detection Settings](#detection-settings))

4. **Set Combat Options**:
   - Go to the "Combat Settings" tab
   - Configure combat preferences (see [Combat Settings](#combat-settings))

5. **Start the Bot**:
   - Return to the "Main" tab
   - Click the "Start" button

6. **Monitor Progress**:
   - Watch the status bar for updates
   - Check the "Statistics" tab for performance metrics
   - View logs in the "Logs & Debug" tab

### First-Time Setup

For first-time users, we recommend:

1. **Run in Debug Mode**:
   - Start with `python run.py --debug` for detailed logging

2. **Use Default Profile**:
   - Start with the default profile to understand basic functionality

3. **Test in Safe Areas**:
   - Begin testing in low-risk areas with few players

4. **Start with Short Sessions**:
   - Run the bot for short periods initially to ensure proper configuration

## Main Interface

The main interface consists of:

- **Control Buttons**: Start, Pause, and Stop buttons at the top
- **Tab Navigation**: Access different settings and features
- **Status Bar**: Shows current status, runtime, and monster count

### Control Buttons

- **Start**: Begin bot operation (changes to "Resume" when paused)
- **Pause**: Temporarily halt bot operation
- **Stop**: Completely stop the bot

### Status Bar

- **Status**: Current bot status (Ready, Running, Paused, etc.)
- **Runtime**: Total running time in hours:minutes:seconds
- **Monster Count**: Number of monsters killed in current session

## Detection Settings

The Detection Settings tab allows you to configure how the bot detects tiles and monsters.

### General Settings

- **Scan Interval**: Time between scans (seconds)
- **Search Step**: Pixel step size for scanning (higher = faster but less accurate)
- **Detect Tiles**: Enable/disable tile detection
- **Detect Monsters**: Enable/disable monster detection
- **Use Precise Mode**: Enable for more accurate but slower detection

### Tile Settings

- **Minimum Area**: Minimum pixel area for tile detection
- **Tile Color**: Configure the color used for detecting walkable tiles

### Monster Settings

- **Minimum Area**: Minimum pixel area for monster detection
- **Around Tile Radius**: Distance to search around tiles for monsters
- **Monster Scan Step**: Pixel step size for monster scanning
- **Enable Monster Full Fallback**: Fall back to full screen scan if no monsters found

### Colors Tab

- **Tile Color**: Configure the RGB/HSV values for tile detection
- **Monster Colors**: Add, edit, or remove monster colors

### ROI Tab

- **Search Region of Interest**: Define a specific screen area for detection
- **ROI Selector**: Visual tool to select the region of interest

## Combat Settings

The Combat Settings tab allows you to configure combat behavior.

### General Combat Settings

- **Combat Style**: Select combat style (Melee, Ranged, Magic)
- **Attack Delay**: Delay between attacks (seconds)
- **Health Threshold**: Health percentage to trigger healing
- **Safe Mode**: Enable to retreat when health is low

### Combat Detection

- **Combat Detection Method**: Choose how to detect combat status
- **Combat Timeout**: Time to wait before considering combat ended (seconds)
- **Auto Retaliate**: Enable/disable auto retaliate detection

## Teleport Settings

The Teleport Settings tab allows you to configure emergency teleports and location teleports.

### Emergency Teleport

- **Enable Emergency Teleport**: Enable/disable emergency teleport
- **Health Threshold**: Health percentage to trigger emergency teleport
- **Teleport Method**: Select teleport method (Item, Spell, Tab)
- **Teleport Key**: Hotkey for teleport spell/item

### Location Teleports

- **Teleport Locations**: Configure teleport locations
- **Add Location**: Add a new teleport location
- **Edit Location**: Modify existing teleport location
- **Remove Location**: Delete a teleport location

## Potion Settings

The Potion Settings tab allows you to configure automatic potion usage.

### Potion Configuration

- **Enable Auto Potions**: Enable/disable automatic potion usage
- **Potion Types**: Configure different potion types
- **Potion Slots**: Set inventory slots for potions
- **Potion Thresholds**: Set thresholds for using potions

### Boost Settings

- **Enable Boosts**: Enable/disable combat boosts
- **Boost Types**: Configure different boost types
- **Boost Intervals**: Set intervals for reapplying boosts

## Instance Settings

The Instance Settings tab allows you to configure instance-related features.

### Instance Entry

- **Enable Auto Instance**: Enable/disable automatic instance entry
- **Instance Entry Point**: Configure instance entry point
- **Entry Method**: Select entry method (Portal, NPC, Object)

### Aggro Settings

- **Enable Aggro Potion**: Enable/disable aggro potion usage
- **Aggro Potion Slot**: Set inventory slot for aggro potion
- **Aggro Duration**: Set duration of aggro effect (minutes)

## Statistics

The Statistics tab provides performance metrics and session data.

### Session Statistics

- **Current Session**: Statistics for current session
- **Monster Kills**: Number of monsters killed
- **Kill Rate**: Kills per hour
- **Runtime**: Total runtime
- **Teleports Used**: Number of teleports used
- **Potions Used**: Number of potions used

### Historical Data

- **Previous Sessions**: Data from previous sessions
- **Performance Trends**: Graphs showing performance over time
- **Export Data**: Export statistics to CSV or JSON

## Profiles

The Profiles tab allows you to save and load configuration profiles.

### Profile Management

- **Save Profile**: Save current configuration as a profile
- **Load Profile**: Load a saved profile
- **Delete Profile**: Remove a saved profile
- **Import/Export**: Import or export profiles to/from files

## Logs & Debugging

The Logs & Debug tab provides detailed logging information.

### Log Viewer

- **Log Level**: Filter logs by severity level
- **Log Search**: Search for specific log entries
- **Auto-scroll**: Automatically scroll to newest logs
- **Save Logs**: Save logs to file for troubleshooting

### Debug Tools

- **Debug Mode**: Enable/disable detailed debugging
- **Screenshot**: Take screenshot of game window
- **Test Detection**: Test detection settings on current screen
- **Memory Usage**: Monitor bot memory usage

## Troubleshooting

### Common Issues

#### Bot Not Detecting Colors Correctly

- Ensure your game brightness settings match your configuration
- Try adjusting the RGB/HSV tolerance values
- Use the color picker tool to select colors directly from the game

#### Bot Not Clicking Accurately

- Check if your game window is positioned correctly
- Ensure the game window is in focus
- Try recalibrating the mouse coordinates

#### High CPU Usage

- Increase the scan interval
- Increase the search step value
- Define a smaller region of interest (ROI)

#### Bot Stops Unexpectedly

- Check the logs for error messages
- Ensure your computer doesn't go to sleep
- Verify that the game client remains stable

### Getting Help

- Check the [FAQ](#faq) section
- Review detailed logs in the "Logs & Debug" tab
- Join our Discord server for community support
- Submit an issue on GitHub for technical problems

## FAQ

### General Questions

**Q: Is this bot safe to use?**
A: This bot is designed for educational purposes and for use on private servers where botting is allowed. Use on official RuneScape servers is against the rules and can result in a ban.

**Q: Can I run multiple instances of the bot?**
A: Yes, you can run multiple instances, but each requires significant system resources. Ensure your computer can handle the load.

**Q: Does the bot work with all RSPS clients?**
A: The bot should work with most RSPS clients, but some customized clients may require additional configuration.

### Technical Questions

**Q: Why is color detection not working?**
A: Color detection depends on consistent game rendering. Factors like game brightness, graphics settings, and monitor calibration can affect detection. Use the color picker tool to select colors directly from your game.

**Q: How can I improve bot performance?**
A: Increase scan interval, use larger search steps, define a smaller ROI, close unnecessary applications, and ensure your computer meets the recommended system requirements.

**Q: Can I use custom scripts with this bot?**
A: The bot architecture supports custom modules. Check the developer documentation for information on creating custom scripts.

**Q: How do I update the bot?**
A: Pull the latest changes from the repository or download the newest release. Your profiles and settings should be preserved during updates.

---

Thank you for using RSPS Color Bot v3! We hope this guide helps you get the most out of the bot. For further assistance, please join our community Discord server or submit an issue on GitHub.