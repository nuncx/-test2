# Cleanup Implementation Plan

## Overview

This document provides a step-by-step plan to remove unused features from the RSPS Color Bot v3 codebase.

---

## Files to Remove

### 1. Core Modules (Unused)
```bash
rm rspsbot/core/modules/teleport.py
rm rspsbot/core/modules/potion.py
rm rspsbot/core/modules/instance.py
```

### 2. GUI Panels (Non-functional)
```bash
rm rspsbot/gui/panels/teleport_panel.py
rm rspsbot/gui/panels/potion_panel.py
rm rspsbot/gui/panels/instance_panel.py
```

**Total removed:** ~88 KB of unused code

---

## Files to Replace

### 1. Main Window
```bash
# Backup original
cp rspsbot/gui/main_window.py rspsbot/gui/main_window_original.py

# Replace with cleaned version
cp rspsbot/gui/main_window_cleaned.py rspsbot/gui/main_window.py
```

**Changes:**
- Removed imports for teleport, potion, instance panels
- Removed 3 tab initializations
- Removed related code
- **Result:** 6 functional tabs instead of 9

### 2. Bot Controller
```bash
# Backup original
cp rspsbot/core/state/__init__.py rspsbot/core/state/__init___original.py

# Replace with cleaned version
cp rspsbot/core/state/bot_controller_cleaned.py rspsbot/core/state/__init__.py
```

**Changes:**
- Removed teleport_manager initialization
- Removed potion_manager initialization
- Removed instance_manager initialization
- Removed unused event types (TELEPORT_USED, POTION_USED, etc.)
- Removed unused event handlers
- Removed unused statistics (teleport_count, potion_count, etc.)
- **Result:** Cleaner, more focused bot controller

---

## Configuration Cleanup

### Remove Unused Config Keys

Edit `rspsbot/core/config/__init__.py` and remove these keys from `_get_default_config()`:

```python
# REMOVE THESE:
"teleport_locations": [],
"emergency_teleport_hotkey": "ctrl+h",
"return_teleport_hotkey": "ctrl+t",
"potion_locations": [],
"boost_locations": [],
"instance_token_location": None,
"instance_teleport_location": None,
"aggro_potion_location": None,
"aggro_effect_roi": None,
"aggro_effect_color": asdict(ColorSpec((255, 0, 0))),
"aggro_duration": 300,
"no_monster_timeout": 180,
"camera_adjust_interval": 10,
"emergency_teleport_threshold": 60
```

---

## Testing Checklist

After cleanup, verify:

### 1. Bot Starts Successfully
```bash
python run.py
```
- [ ] No import errors
- [ ] GUI loads correctly
- [ ] 6 tabs visible (not 9)

### 2. Core Functionality Works
- [ ] Window selection works
- [ ] Detection settings work
- [ ] Combat settings work
- [ ] Bot starts/stops/pauses
- [ ] Monster detection works
- [ ] Monster clicking works
- [ ] Statistics update correctly

### 3. Profiles Work
- [ ] Can save profile
- [ ] Can load profile
- [ ] No errors about missing keys

### 4. No Errors in Logs
- [ ] Check logs for import errors
- [ ] Check logs for missing attribute errors
- [ ] Check logs for config key errors

---

## Rollback Plan

If issues occur, restore original files:

```bash
# Restore main window
cp rspsbot/gui/main_window_original.py rspsbot/gui/main_window.py

# Restore bot controller
cp rspsbot/core/state/__init___original.py rspsbot/core/state/__init__.py

# Restore modules (if deleted)
git checkout rspsbot/core/modules/teleport.py
git checkout rspsbot/core/modules/potion.py
git checkout rspsbot/core/modules/instance.py

# Restore panels (if deleted)
git checkout rspsbot/gui/panels/teleport_panel.py
git checkout rspsbot/gui/panels/potion_panel.py
git checkout rspsbot/gui/panels/instance_panel.py
```

---

## Migration Guide for Users

### For Existing Users

**Good News:** No migration needed! The cleanup only removes non-functional features.

**What Changes:**
- 3 GUI tabs removed (Teleport, Potion, Instance)
- Unused config keys removed
- Code is cleaner and faster

**What Stays the Same:**
- All functional features work exactly as before
- Detection settings unchanged
- Combat settings unchanged
- Profiles still work
- Statistics still work

### Updating Existing Profiles

If you have existing profiles with unused keys, they will be ignored (no errors).

Optionally, clean up profiles manually:

```python
# Remove these keys from your .json profile files:
- teleport_locations
- emergency_teleport_hotkey
- return_teleport_hotkey
- potion_locations
- boost_locations
- instance_token_location
- instance_teleport_location
- aggro_potion_location
- aggro_effect_roi
- aggro_effect_color
- aggro_duration
- no_monster_timeout
- camera_adjust_interval
- emergency_teleport_threshold
```

---

## Documentation Updates

### 1. README.md

Remove mentions of:
- Teleport system
- Potion system
- Instance system

Update feature list to reflect actual functionality.

### 2. USER_GUIDE.md

Remove sections about:
- Teleport configuration
- Potion configuration
- Instance configuration

### 3. Configuration Guide

Remove documentation for unused config keys.

---

## Benefits After Cleanup

### Code Quality
- ✅ **-88 KB** of unused code removed
- ✅ **-3 non-functional GUI tabs** removed
- ✅ **-12 unused config keys** removed
- ✅ **Cleaner codebase** easier to maintain

### User Experience
- ✅ **Less confusion** - only functional features shown
- ✅ **Faster startup** - fewer imports
- ✅ **Clearer GUI** - 6 tabs instead of 9
- ✅ **Better documentation** - matches actual functionality

### Performance
- ✅ **Slightly faster startup** - fewer modules to import
- ✅ **Less memory** - unused managers not initialized
- ✅ **Cleaner logs** - no warnings about unused features

---

## Timeline

### Phase 1: Preparation (5 minutes)
- [x] Create backup of original files
- [x] Create cleaned versions
- [x] Document changes

### Phase 2: Implementation (10 minutes)
- [ ] Remove unused module files
- [ ] Remove unused panel files
- [ ] Replace main_window.py
- [ ] Replace bot controller
- [ ] Clean up configuration

### Phase 3: Testing (15 minutes)
- [ ] Test bot startup
- [ ] Test core functionality
- [ ] Test profile save/load
- [ ] Check logs for errors

### Phase 4: Documentation (10 minutes)
- [ ] Update README
- [ ] Update user guide
- [ ] Create migration notes
- [ ] Update changelog

**Total Time:** ~40 minutes

---

## Approval Required

Before proceeding with cleanup, confirm:

1. ✅ **Remove unused features?** (teleport, potion, instance)
2. ✅ **Remove non-functional GUI tabs?**
3. ✅ **Clean up configuration?**
4. ❓ **Implement OCR system?** (currently doesn't exist)

---

## Next Steps

**Waiting for user approval to:**
1. Execute the cleanup
2. Test the changes
3. Commit to repository
4. Update documentation

**Alternative:** If user wants to keep unused features for future use, we can:
1. Mark them as "experimental" or "disabled"
2. Add warnings in GUI
3. Document that they're not functional
4. Keep code but hide GUI tabs

---

**Status:** ✅ Ready to Execute (Awaiting User Approval)