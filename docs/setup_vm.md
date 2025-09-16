# RSPS Color Bot — VM Setup Guide

This guide walks you through creating a Windows VM, tuning it for input/detection reliability, and running the bot smoothly.

## Downloads (Official)

- VMware Workstation Player (free for personal use):
  - https://www.vmware.com/products/workstation-player.html
- Microsoft Windows ISO (choose one):
  - Windows 10 ISO (Media Creation Tool): https://www.microsoft.com/software-download/windows10
  - Windows 11 ISO (Media Creation Tool/ISO): https://www.microsoft.com/software-download/windows11
  - Windows 11 Evaluation ISO (90 days): https://learn.microsoft.com/windows/deployment/evaluate-windows-client

Optional tools inside the VM:
- Git for Windows: https://git-scm.com/download/win
- Python (3.11+): https://www.python.org/downloads/windows/
- Visual Studio Code: https://code.visualstudio.com/
- Tesseract OCR (if using OCR features): https://github.com/UB-Mannheim/tesseract/wiki

## Create the VM

1) New VM in VMware Player → I will install the operating system later → select the Windows ISO
2) Hardware:
   - CPUs: 2–4 cores
   - Memory: 6–8 GB (4–6 GB on low-RAM hosts)
   - Disk: 40–60 GB (split into multiple files, grow as needed)
   - Display: Enable 3D acceleration
   - Network: NAT (default) or Bridged if you need LAN access

## Install Windows + Tools

1) Complete Windows OOBE and run Windows Update fully
2) In Player menu: Player → Manage → Install VMware Tools → Reboot when done
3) Set display scaling to 100% and a single 1920x1080 monitor for stable input mapping

Screenshots: replace placeholders with your own after setup.
- docs/images/vmware_player_new_vm.png
- docs/images/windows_oobe.png
- docs/images/vmware_tools_install.png

## Tune Windows for Reliability

- Display: 100% scaling; single 1080p monitor
- Power: High Performance plan; disable sleep/screensaver
- UAC/Admin: Run both game and bot as the same user, not elevated
- Game window: Keep visible (not minimized) and avoid background throttling

## Prepare the Environment

You can use the provided one-click `start_bot.bat` at the repo root. It will:
- Create `.venv` automatically if missing
- Install `requirements.txt` on first launch
- Start the app

If you want to do it manually:
- py -3.11 -m venv .venv
- .venv\\Scripts\\activate
- pip install -r requirements.txt
- python run.py

## First Run Checklist

- Open Instance Mode tabs
- Configure HP ROI and color via the zoomable pickers
- Set Aggro timer and click coordinates; use Test Click
- Set Token/Teleport coordinates, Post-Teleport HP wait, and Max Teleport Retries
- Save a Profile so settings persist

## Troubleshooting Tips

- If clicks don’t fire, ensure the VM window and the game are focused and not elevated
- If detection is noisy, re-pick HP ROI/color and adjust min pixels in Instance Mode
- If logs feel spammy, tune `instance_status_log_interval` (config)
- Performance: prefer 2–4 vCPUs, keep 3D acceleration, and confirm VMware Tools is installed

## Optional: Snapshot Baseline

After everything works, create a VM snapshot so you can roll back quickly before experiments.
