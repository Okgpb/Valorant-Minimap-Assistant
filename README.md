# Valorant Minimap Assistant - Real-time Enemy Ping Alerts

This is a real-time assistant for Valorant that automatically detects enemy symbol "?" on the minimap and highlights their location with a highly visible, blinking on-screen alert.

<img width="400" height="=390" alt="image" src="https://github.com/user-attachments/assets/8d53f389-20b4-4286-b4e4-2b67acc8cb9e" />



### ⚠️ Important Notes

1.  For best performance, it is recommended to set your game's display mode to **Windowed Fullscreen**.
2.  This tool has built-in presets for **2560x1600** and **2560x1440** resolutions. If you use a different resolution, you **must** use the **Custom** option to define your minimap's coordinates manually.

### ✨ Features

* **Auto Detection**: No manual operation needed. The program automatically detects enemy symbol using real-time color and shape analysis on the minimap.
* **Blinking Overlay Alert**: Displays a clear, blinking red dot overlay at the exact location of the detected threat to grab your attention.
* **High Accuracy**: Uses a two-frame verification system to minimize false positives from random visual noise.
* **Configurable GUI**: An intuitive interface to adjust detection sensitivity, resolution presets, scan interval, and other settings.
* **Multi-resolution Support**: Includes presets for common resolutions and a "Custom" mode for any screen size.
* **Debug Mode**: An optional mode to view the live image analysis and see what the program is detecting in real-time.


### 📝 Credits

* This program uses [OpenCV](https://opencv.org/) for image processing.
* Uses the [mss](https://python-mss.readthedocs.io/) library for efficient screen capturing.
* Built with [Python](https://www.python.org/) and the `tkinter` GUI toolkit.
