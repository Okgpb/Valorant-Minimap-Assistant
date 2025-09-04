import tkinter as tk
from tkinter import ttk, messagebox
import threading
import time
import cv2
import numpy as np
import mss
import traceback
import math
import platform

# 在Windows上设置进程DPI感知，以确保在高分屏+缩放环境下UI显示正常
if platform.system() == "Windows":
    try:
        import ctypes
        ctypes.windll.shcore.SetProcessDpiAwareness(2) 
    except Exception:
        try:
            ctypes.windll.user32.SetProcessDPIAware()
        except Exception:
            pass

# --- 应用程序文本库 ---
LANGUAGES = {
    'en': {
        'title': "Minimap Assistant v17.1",
        'lang_select_frame': "Language", 'map_settings_frame': "Minimap Position",
        'resolution_preset_label': "Preset:", 'custom_option': "Custom",
        'left_label': "Left (L):", 'top_label': "Top (T):", 'width_label': "Width (W):",
        'height_label': "Height (H):", 'sensitivity_frame': "Detection Sensitivity",
        'sensitivity_label': "Sensitivity (1-200%):", 'sensitivity_desc': "",
        'perf_frame': "Performance & Validation", 'interval_label': "Scan Interval (s):",
        'debug_check': "Enable Debug Mode (Show capture)", 'start_button': "Start Program",
        'stop_button': "Stop Program", 'error_title': "Input Error",
        'error_value_invalid': "Please enter valid numbers!",
        'error_sensitivity_range': "Sensitivity must be between 1 and 200.",
        'unknown_error': "Failed to start", 'status_confirm': "--- Settings confirmed, starting program ---",
        'status_map_area': "  Minimap Area:", 'status_sensitivity': "  Sensitivity:",
        'status_cancelled': "Program cancelled by user.", 'status_started': "--- Minimap Assistant Started ---",
        'status_stopped': "--- Minimap Assistant Stopped ---", 'status_switch_game': "You can now switch to the game window.",
        'status_runtime_error': "[Runtime Error] Detection thread encountered an issue:",
        'status_detector_stopped': "Detection thread stopped.", 'status_exit': "Program exited."
    },
    'zh': {
        'title': "小地图助手 v17.1",
        'lang_select_frame': "语言", 'map_settings_frame': "小地图位置设置",
        'resolution_preset_label': "分辨率预设:", 'custom_option': "自定义",
        'left_label': "左边距 (L):", 'top_label': "上边距 (T):", 'width_label': "宽度 (W):",
        'height_label': "高度 (H):", 'sensitivity_frame': "识别灵敏度",
        'sensitivity_label': "灵敏度 (1-200%):", 'sensitivity_desc': "",
        'perf_frame': "验证与性能参数", 'interval_label': "扫描间隔 (秒):",
        'debug_check': "开启调试模式 (显示识别过程图像)", 'start_button': "启动程序",
        'stop_button': "停止程序", 'error_title': "输入错误",
        'error_value_invalid': "请输入有效的数字！", 'error_sensitivity_range': "灵敏度必须在 1 到 200 之间。",
        'unknown_error': "启动失败", 'status_confirm': "--- 参数已确认, 程序启动 ---",
        'status_map_area': "  小地图区域:", 'status_sensitivity': "  灵敏度设定:",
        'status_cancelled': "Program cancelled by user.", 'status_started': "--- 小地图助手已启动 ---",
        'status_stopped': "--- 小地图助手已停止 ---", 'status_switch_game': "现在可以切换到游戏窗口了。",
        'status_runtime_error': "[运行时错误] 检测线程遇到问题:", 'status_detector_stopped': "检测线程已停止。",
        'status_exit': "程序已退出。"
    }
}

# --- 核心参数与预设 ---
RESOLUTION_PRESETS_T = {
    "2.5K (2560x1600 Fill)": {'left': 35, 'top': 70, 'width': 665, 'height': 665},
    "2K (2560x1400)": {'left': 30, 'top': 65, 'width': 600, 'height': 600},
}
SENSITIVITY_BOUNDS = { 'MIN_AREA_PIXELS':(4,7), 'MAX_AREA_PIXELS':(150,90), 'MIN_ASPECT_RATIO':(0.8,1.3), 'MAX_ASPECT_RATIO':(3.0,2.1), 'MIN_EXTENT':(0.15,0.28), 'MAX_EXTENT':(0.8,0.60), 'MIN_SOLIDITY':(0.25,0.38), 'MAX_SOLIDITY':(0.95,0.82) }
CONFIG = { 'MINI_MAP_ROI':{}, 'LOWER_ORANGE_RED_HSV':np.array([5,200,180]), 'UPPER_ORANGE_RED_HSV':np.array([15,255,255]), 'CONFIRMATION_TOLERANCE_PIXELS':15, 'MARKER_DURATION_MS':2500, 'MARKER_RADIUS':6, 'MARKER_COLOR':"#ff0000", 'SCAN_INTERVAL_S':0.2, 'DEBUG_MODE':False }

# --- 全局状态变量，用于线程间通信 ---
detected_points, previous_frame_points, lock, app_is_running = [], [], threading.Lock(), True


class SettingsWindow(tk.Tk):
    """主设置窗口，同时作为程序的控制器"""
    def __init__(self):
        super().__init__()
        self.resizable(False, False)
        self.protocol("WM_DELETE_WINDOW", self._on_closing)
        
        self.is_running = False
        self.detector_thread = None
        self.overlay = None
        self.current_lang = 'en'
        
        self.entries, self.roi_entries = {}, {}
        self.string_vars = { 'res_preset': tk.StringVar() }
        self.control_widgets = []

        main_frame = ttk.Frame(self, padding=5)
        main_frame.pack(fill="both", expand=True)
        self._create_widgets(main_frame)
        self._update_ui_language()
        self._on_resolution_change()

    def _create_widgets(self, parent):
        lang_frame = ttk.LabelFrame(parent, padding=4)
        lang_frame.pack(fill='x', pady=1)
        self.lang_frame = lang_frame
        self.lang_combo = ttk.Combobox(lang_frame, values=["English", "中文"], state="readonly", width=10)
        self.lang_combo.set("English")
        self.lang_combo.pack(side='left', padx=3)
        self.lang_combo.bind("<<ComboboxSelected>>", self._on_language_change)
        
        self.map_frame = ttk.LabelFrame(parent, padding=4)
        self.map_frame.pack(fill="x", pady=1)
        self.map_frame.columnconfigure(1, weight=1)
        self.map_frame.columnconfigure(3, weight=1)
        self.res_label = ttk.Label(self.map_frame)
        self.res_label.grid(row=0, column=0, sticky="w", padx=3, pady=(0,2))
        self.res_combo = ttk.Combobox(self.map_frame, state="readonly", textvariable=self.string_vars['res_preset'])
        self.res_combo.grid(row=0, column=1, columnspan=3, sticky="we", padx=3, pady=(0,2))
        self.res_combo.bind("<<ComboboxSelected>>", self._on_resolution_change)
        self.control_widgets.append(self.res_combo)
        self.ui_map_labels = { k: ttk.Label(self.map_frame) for k in ['left', 'top', 'width', 'height'] }
        self.ui_map_labels['left'].grid(row=1, column=0, sticky="w", padx=3, pady=1)
        self.ui_map_labels['top'].grid(row=1, column=2, sticky="w", padx=3, pady=1)
        self.ui_map_labels['width'].grid(row=2, column=0, sticky="w", padx=3, pady=1)
        self.ui_map_labels['height'].grid(row=2, column=2, sticky="w", padx=3, pady=1)
        for i, key in enumerate(['left', 'top', 'width', 'height']):
            entry = ttk.Entry(self.map_frame, width=10)
            entry.grid(row=(1 + i // 2), column=(1 + (i % 2) * 2), sticky="we", padx=3, pady=1)
            self.roi_entries[key] = entry
            self.control_widgets.append(entry)

        self.sens_frame = ttk.LabelFrame(parent, padding=4)
        self.sens_frame.pack(fill="x", pady=1)
        self.sens_label = ttk.Label(self.sens_frame)
        self.sens_label.pack(side="left", padx=(3,2))
        self.sensitivity_spinbox = ttk.Spinbox(self.sens_frame, from_=1, to=200, width=8)
        self.sensitivity_spinbox.set("100")
        self.sensitivity_spinbox.pack(side="left", padx=2)
        self.control_widgets.append(self.sensitivity_spinbox)
        self.sens_desc_label = ttk.Label(self.sens_frame)
        self.sens_desc_label.pack(side="left", padx=(2,3))
        
        self.perf_frame = ttk.LabelFrame(parent, padding=4)
        self.perf_frame.pack(fill="x", pady=1)
        self.interval_label = ttk.Label(self.perf_frame)
        self.interval_label.grid(row=1, column=0, sticky="w", padx=3, pady=1)
        entry = ttk.Entry(self.perf_frame, width=10)
        entry.grid(row=1, column=1, sticky="w", padx=3, pady=1)
        self.entries['SCAN_INTERVAL_S'] = entry
        self.control_widgets.append(entry)

        self.debug_var = tk.BooleanVar(value=CONFIG['DEBUG_MODE'])
        self.debug_check = ttk.Checkbutton(parent, variable=self.debug_var)
        self.debug_check.pack(pady=3)
        self.control_widgets.append(self.debug_check)
        self.toggle_button = ttk.Button(parent, command=self._toggle_detector)
        self.toggle_button.pack(pady=5, ipady=3, fill='x', padx=5)

    def _update_ui_language(self):
        s = LANGUAGES[self.current_lang]
        self.title(s['title'])
        self.geometry("400x440")
        
        self.lang_frame.config(text=s['lang_select_frame'])
        self.map_frame.config(text=s['map_settings_frame'])
        self.res_label.config(text=s['resolution_preset_label'])
        self.res_combo_values = list(RESOLUTION_PRESETS_T.keys()) + [s['custom_option']]
        self.res_combo.config(values=self.res_combo_values)
        if not self.string_vars['res_preset'].get(): self.string_vars['res_preset'].set(self.res_combo_values[0])
        self.ui_map_labels['left'].config(text=s['left_label'])
        self.ui_map_labels['top'].config(text=s['top_label'])
        self.ui_map_labels['width'].config(text=s['width_label'])
        self.ui_map_labels['height'].config(text=s['height_label'])
        self.sens_frame.config(text=s['sensitivity_frame'])
        self.sens_label.config(text=s['sensitivity_label'])
        self.sens_desc_label.config(text=s['sensitivity_desc'])
        self.perf_frame.config(text=s['perf_frame'])
        self.interval_label.config(text=s['interval_label'])
        self.debug_check.config(text=s['debug_check'])
        self.toggle_button.config(text=s['stop_button'] if self.is_running else s['start_button'])
        for key, entry in self.entries.items():
             if not entry.get(): entry.insert(0, str(CONFIG[key]))

    def _on_language_change(self, event=None):
        selection = self.lang_combo.get()
        self.current_lang = 'zh' if selection == "中文" else 'en'
        self._update_ui_language()
        self._on_resolution_change()

    def _on_resolution_change(self, event=None):
        selection = self.string_vars['res_preset'].get()
        is_custom = (selection == LANGUAGES[self.current_lang]['custom_option'])
        for key, entry in self.roi_entries.items():
            entry.config(state="normal")
            if not is_custom:
                preset_key = next((k for k in RESOLUTION_PRESETS_T if k == selection), None)
                params = RESOLUTION_PRESETS_T.get(preset_key, {})
                entry.delete(0, tk.END)
                if params: entry.insert(0, str(params[key]))
                entry.config(state="disabled")

    def _calculate_sensitivity_params(self, percentage):
        progress = (percentage - 1) / 199.0
        params = {}
        for key, (loose_val, strict_val) in SENSITIVITY_BOUNDS.items():
            val = loose_val + progress * (strict_val - loose_val)
            params[key] = int(val) if isinstance(loose_val, int) else round(val, 3)
        return params

    def _set_controls_state(self, state):
        for widget in self.control_widgets:
            widget.config(state=state)
        self.lang_combo.config(state="readonly")

    def _toggle_detector(self):
        s = LANGUAGES[self.current_lang]
        if self.is_running:
            # --- Stop Logic ---
            global app_is_running
            app_is_running = False
            if self.detector_thread: self.detector_thread.join(timeout=1)
            if self.overlay: self.overlay.destroy(); self.overlay = None
            self.is_running = False
            self.toggle_button.config(text=s['start_button'])
            self._set_controls_state("normal")
            self._on_resolution_change()
            print(f"\n{s['status_stopped']}\n")
        else:
            # --- Start Logic ---
            try:
                sensitivity_val = int(self.sensitivity_spinbox.get())
                if not 1 <= sensitivity_val <= 200: raise ValueError(s['error_sensitivity_range'])
                CONFIG.update(self._calculate_sensitivity_params(sensitivity_val))
                CONFIG['MINI_MAP_ROI'] = {k: int(e.get()) for k, e in self.roi_entries.items()}
                for k, e in self.entries.items(): CONFIG[k] = float(e.get()) if '.' in e.get() else int(e.get())
                CONFIG['DEBUG_MODE'] = self.debug_var.get()
                CONFIG['lang'] = self.current_lang
                
                self.is_running = True
                app_is_running = True
                self.toggle_button.config(text=s['stop_button'])
                self._set_controls_state("disabled")
                
                self.overlay = OverlayWindow(self, CONFIG) 
                self.detector_thread = threading.Thread(target=run_detector, args=(CONFIG,), daemon=True)
                self.detector_thread.start()
                self._update_overlay_loop()
                
                print(s['status_confirm']); print(f"{s['status_map_area']} {CONFIG['MINI_MAP_ROI']}"); print(f"{s['status_sensitivity']} {sensitivity_val}%"); print(s['status_switch_game'])
            except ValueError as e: messagebox.showerror(s['error_title'], f"{s['error_value_invalid']}\n{e}")
            except Exception as e: messagebox.showerror(s['unknown_error'], f"{e}")

    def _update_overlay_loop(self):
        if not self.is_running: return
        with lock:
            points_to_draw = list(detected_points)
            detected_points.clear()
        if self.overlay and self.overlay.winfo_exists():
            for x, y in points_to_draw:
                self.overlay.draw_marker(x, y)
        self.after(100, self._update_overlay_loop)

    def _on_closing(self):
        if self.is_running:
            self._toggle_detector()
        self.destroy()


class OverlayWindow(tk.Toplevel):
    """一个用于绘制标记的、透明的、可穿透点击的全屏子窗口"""
    def __init__(self, parent, cfg):
        super().__init__(parent)
        self.cfg = cfg
        self.blinking_markers = {} 

        self.overrideredirect(True)
        self.geometry(f"{self.winfo_screenwidth()}x{self.winfo_screenheight()}+0+0")
        self.wm_attributes("-topmost", True)
        self.wm_attributes("-disabled", True)
        self.wm_attributes("-transparentcolor", "white")
        
        self.canvas = tk.Canvas(self, bg='white', highlightthickness=0)
        self.canvas.pack(fill="both", expand=True)

    def draw_marker(self, x, y):
        r = self.cfg['MARKER_RADIUS']
        marker_id = self.canvas.create_oval(x-r, y-r, x+r, y+r, fill=self.cfg['MARKER_COLOR'], outline="", state='normal')
        self._blink_marker(marker_id)

    def _blink_marker(self, marker_id):
        if not self.canvas.winfo_exists() or marker_id not in self.canvas.find_all():
            if marker_id in self.blinking_markers:
                del self.blinking_markers[marker_id]
            return

        current_state = self.canvas.itemcget(marker_id, "state")
        new_state = 'hidden' if current_state == 'normal' else 'normal'
        self.canvas.itemconfigure(marker_id, state=new_state)

        # 递归调用以创建闪烁循环
        blink_timer_id = self.after(100, lambda: self._blink_marker(marker_id))
        
        if marker_id not in self.blinking_markers:
            # 为新标记设置一个总生命周期的删除定时器
            delete_timer_id = self.after(self.cfg['MARKER_DURATION_MS'], lambda: self._stop_blinking_and_delete(marker_id))
            self.blinking_markers[marker_id] = {'blink': blink_timer_id, 'delete': delete_timer_id}
        else:
            self.blinking_markers[marker_id]['blink'] = blink_timer_id

    def _stop_blinking_and_delete(self, marker_id):
        if marker_id in self.blinking_markers:
            self.after_cancel(self.blinking_markers[marker_id]['blink'])
            del self.blinking_markers[marker_id]
        
        if self.canvas.winfo_exists() and marker_id in self.canvas.find_all():
            self.canvas.delete(marker_id)


def _is_valid_contour(contour, cfg):
    """通过一系列几何特征检查，判断轮廓是否为有效标记"""
    # 面积：过滤噪点或过大区域
    area = cv2.contourArea(contour)
    if not (cfg['MIN_AREA_PIXELS'] < area < cfg['MAX_AREA_PIXELS']): return False
    
    # 宽高比：标记通常是瘦高形状
    x, y, w, h = cv2.boundingRect(contour)
    if w == 0 or h == 0: return False
    if not (cfg['MIN_ASPECT_RATIO'] < float(h)/w < cfg['MAX_ASPECT_RATIO']): return False

    # 填充率与坚实度：确保形状饱满，不是分散的色块
    if not (cfg['MIN_EXTENT'] < area/(w*h) < cfg['MAX_EXTENT']): return False
    hull = cv2.convexHull(contour)
    hull_area = cv2.contourArea(hull)
    if hull_area == 0: return False
    if not (cfg['MIN_SOLIDITY'] < area/hull_area < cfg['MAX_SOLIDITY']): return False
    
    return True

def run_detector(cfg):
    """后台检测线程的主函数，负责截图与图像分析"""
    global detected_points, previous_frame_points, app_is_running
    TEXT, roi = LANGUAGES[cfg.get('lang', 'en')], cfg['MINI_MAP_ROI']
    
    # 创建圆形蒙版以忽略小地图的角落
    mask = np.zeros((roi['height'], roi['width']), np.uint8)
    cv2.circle(mask, (roi['width']//2, roi['height']//2), min(roi['width']//2, roi['height']//2), 255, -1)
    
    with mss.mss() as sct:
        while app_is_running:
            try:
                img = np.array(sct.grab(roi))
                
                img_masked = cv2.bitwise_and(img, img, mask=mask)
                hsv = cv2.cvtColor(img_masked, cv2.COLOR_BGR2HSV)
                red_mask = cv2.inRange(hsv, cfg['LOWER_ORANGE_RED_HSV'], cfg['UPPER_ORANGE_RED_HSV'])
                contours, _ = cv2.findContours(red_mask, cv2.RETR_TREE, cv2.CHAIN_APPROX_SIMPLE)
                
                current_pts = []
                for c in contours:
                    if _is_valid_contour(c, cfg):
                        M = cv2.moments(c)
                        if M["m00"] != 0:
                            cx = int(M["m10"]/M["m00"])
                            cy = int(M["m01"]/M["m00"])
                            current_pts.append((roi['left'] + cx, roi['top'] + cy))
                
                # 双重确认机制：比较当前帧与上一帧的检测点，以减少误报
                confirmed_pts = []
                for p1 in current_pts:
                    for p2 in previous_frame_points:
                        if math.sqrt((p1[0]-p2[0])**2 + (p1[1]-p2[1])**2) < cfg['CONFIRMATION_TOLERANCE_PIXELS']:
                            confirmed_pts.append(p1)
                            break
                            
                with lock:
                    detected_points = confirmed_pts
                
                previous_frame_points = current_pts
                
                if cfg['DEBUG_MODE']:
                    dbg_img = img.copy()
                    for p in current_pts: cv2.circle(dbg_img, (p[0]-roi['left'], p[1]-roi['top']), 10, (0,255,255), 1)
                    for p in confirmed_pts: cv2.circle(dbg_img, (p[0]-roi['left'], p[1]-roi['top']), 12, (255,0,0), 2)
                    cv2.imshow("Debug", dbg_img)
                    if cv2.waitKey(1) & 0xFF == ord('q'):
                        app_is_running = False 
                
                time.sleep(cfg['SCAN_INTERVAL_S'])

            except Exception as e: 
                print(f"{TEXT['status_runtime_error']} {e}")
                traceback.print_exc()
                time.sleep(1)

    if cfg['DEBUG_MODE']:
        cv2.destroyAllWindows()
    print(TEXT['status_detector_stopped'])

def main():
    """程序主入口"""
    app = SettingsWindow()
    app.mainloop()
    print(LANGUAGES.get(app.current_lang, LANGUAGES['en'])['status_exit'])

if __name__ == "__main__":
    main()