"""
Chat panel for configuring OCR-based chat triggers and actions.
"""
from __future__ import annotations
import logging
import time
from typing import Any
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QCheckBox, QGroupBox, QSpinBox, QLineEdit, QFileDialog,
    QDoubleSpinBox, QDialog, QTextEdit, QSizePolicy
)
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QImage, QPixmap

from ...core.config import ROI, ColorSpec
from ..components.advanced_roi_selector import AdvancedROISelector
from ..components.enhanced_color_editor import EnhancedColorEditor
from .teleport_panel import CoordinateSelector

logger = logging.getLogger('rspsbot.gui.panels.chat_panel')


class ChatPanel(QWidget):
    def __init__(self, config_manager, bot_controller, parent=None):
        super().__init__(parent)
        self._config = config_manager
        self._controller = bot_controller
        self._init_ui()

    def _init_ui(self):
        main = QVBoxLayout(self)

        # Enable
        en_group = QGroupBox("Chat Watcher")
        en_layout = QHBoxLayout(en_group)
        self.enable_cb = QCheckBox("Enable OCR chat triggers")
        self.enable_cb.setChecked(bool(self._config.get('chat_enabled', False)))
        self.enable_cb.toggled.connect(lambda v: self._config.set('chat_enabled', bool(v)))
        en_layout.addWidget(self.enable_cb)
        main.addWidget(en_group)

        # ROI
        roi_group = QGroupBox("Chat ROI")
        roi_layout = QVBoxLayout(roi_group)
        # Use the shared AdvancedROISelector widget; auto-save changes to config
        self.roi_selector = AdvancedROISelector(config_manager=self._config, parent=self, title='Chat ROI')
        # Load initial ROI from config if present
        try:
            roi = self._config.get_roi('chat_roi')
            if roi:
                self.roi_selector.set_roi(roi)
        except Exception:
            pass
        # Persist ROI updates immediately on change
        try:
            self.roi_selector.roiChanged.connect(lambda r: self._config.set('chat_roi', r))
        except Exception:
            pass
        roi_layout.addWidget(self.roi_selector)
        main.addWidget(roi_group)

        # OCR language + Poll interval
        poll_group = QGroupBox("OCR & Polling")
        poll_layout = QHBoxLayout(poll_group)
        poll_layout.addWidget(QLabel("OCR language (-l):"))
        self.lang_edit = QLineEdit()
        self.lang_edit.setPlaceholderText("eng or eng+por …")
        self.lang_edit.setText(str(self._config.get('chat_ocr_lang', 'eng')))
        self.lang_edit.textChanged.connect(lambda t: self._config.set('chat_ocr_lang', t or 'eng'))
        poll_layout.addWidget(self.lang_edit)
        poll_layout.addSpacing(16)
        poll_layout.addWidget(QLabel("Interval (ms):"))
        self.poll_spin = QSpinBox()
        self.poll_spin.setRange(100, 5000)
        self.poll_spin.setSingleStep(50)
        self.poll_spin.setValue(int(self._config.get('chat_poll_ms', 600)))
        self.poll_spin.valueChanged.connect(lambda v: self._config.set('chat_poll_ms', int(v)))
        poll_layout.addWidget(self.poll_spin)
        poll_layout.addStretch()
        main.addWidget(poll_group)

        # Actions config
        act_group = QGroupBox("Actions")
        act_layout = QVBoxLayout(act_group)
        # Prayer enable XY
        act_layout.addWidget(QLabel("Prayer enable coordinate:"))
        self.coord_sel = CoordinateSelector(self, self._config, self._controller)
        # Initialize with existing value if any
        try:
            xy = self._config.get('chat_prayer_enable_xy') or {'x': 0, 'y': 0}
            self.coord_sel.set_coordinate(int(xy.get('x', 0)), int(xy.get('y', 0)))
            self.coord_sel.coordinateSelected.connect(self._on_coord_selected)
        except Exception:
            pass
        act_layout.addWidget(self.coord_sel)

        # YBR tile color
        act_layout.addWidget(QLabel("'YOU BETTER RUN!' tile color:"))
        self.ybr_color = EnhancedColorEditor(self._config, 'chat_ybr_tile_color', title="YBR Tile Color")
        act_layout.addWidget(self.ybr_color)

        main.addWidget(act_group)

        # Text Colors (for line color verification)
        txt_group = QGroupBox("Text Colors (verification)")
        txt_layout = QVBoxLayout(txt_group)
        txt_layout.addWidget(QLabel("Used to verify the OCR line is rendered with the expected color; adjust if your client's font color differs."))
        self.col_prayer_dis = EnhancedColorEditor(self._config, 'chat_text_color_prayer_disabled', title="'Prayers disabled' text color")
        self.col_ybr_text = EnhancedColorEditor(self._config, 'chat_text_color_ybr', title="'YOU BETTER RUN!' text color")
        self.col_rebirth_dis = EnhancedColorEditor(self._config, 'chat_text_color_rebirth_disabled', title="'Rebirth disabled your prayers' text color")
        txt_layout.addWidget(self.col_prayer_dis)
        txt_layout.addWidget(self.col_ybr_text)
        txt_layout.addWidget(self.col_rebirth_dis)
        main.addWidget(txt_group)

        # Template verification settings
        tmpl_group = QGroupBox("Template verification (optional)")
        tmpl_layout = QVBoxLayout(tmpl_group)
        row0 = QHBoxLayout()
        self.tmpl_enable = QCheckBox("Enable template matching in addition to color verification")
        self.tmpl_enable.setChecked(bool(self._config.get('chat_template_enable', False)))
        self.tmpl_enable.toggled.connect(lambda v: self._config.set('chat_template_enable', bool(v)))
        row0.addWidget(self.tmpl_enable)
        row0.addStretch()
        tmpl_layout.addLayout(row0)

        row_thr = QHBoxLayout()
        row_thr.addWidget(QLabel("Template threshold:"))
        self.tmpl_thr = QDoubleSpinBox()
        self.tmpl_thr.setRange(0.0, 1.0)
        self.tmpl_thr.setSingleStep(0.01)
        self.tmpl_thr.setDecimals(2)
        self.tmpl_thr.setValue(float(self._config.get('chat_template_threshold', 0.7)))
        self.tmpl_thr.valueChanged.connect(lambda v: self._config.set('chat_template_threshold', float(v)))
        row_thr.addWidget(self.tmpl_thr)
        row_thr.addStretch()
        tmpl_layout.addLayout(row_thr)

        def make_path_row(label_text: str, key: str):
            row = QHBoxLayout()
            row.addWidget(QLabel(label_text))
            edit = QLineEdit()
            edit.setText(str(self._config.get(key) or ''))
            edit.textChanged.connect(lambda t: self._config.set(key, t))
            btn = QPushButton("Browse…")
            def on_browse():
                path, _ = QFileDialog.getOpenFileName(self, "Select template image", "", "Images (*.png *.jpg *.jpeg *.bmp)")
                if path:
                    edit.setText(path)
                    try:
                        self._config.set(key, path)
                    except Exception:
                        pass
            btn.clicked.connect(on_browse)
            row.addWidget(edit)
            row.addWidget(btn)
            return row

        tmpl_layout.addLayout(make_path_row("YOU BETTER RUN! template:", 'chat_template_ybr_path'))
        tmpl_layout.addLayout(make_path_row("Prayers disabled template:", 'chat_template_prayer_disabled_path'))
        tmpl_layout.addLayout(make_path_row("Rebirth disabled template:", 'chat_template_rebirth_disabled_path'))

        main.addWidget(tmpl_group)

        # Debug & Test
        dbg_group = QGroupBox("Debug & Test")
        dbg_layout = QVBoxLayout(dbg_group)
        # Color verification thresholds
        row_cv = QHBoxLayout()
        row_cv.addWidget(QLabel("Min ratio:"))
        self.cv_ratio = QDoubleSpinBox()
        self.cv_ratio.setRange(0.0, 1.0)
        self.cv_ratio.setDecimals(3)
        self.cv_ratio.setSingleStep(0.005)
        self.cv_ratio.setValue(float(self._config.get('chat_color_verify_min_ratio', 0.01)))
        self.cv_ratio.valueChanged.connect(lambda v: self._config.set('chat_color_verify_min_ratio', float(v)))
        row_cv.addWidget(self.cv_ratio)
        row_cv.addSpacing(12)
        row_cv.addWidget(QLabel("Min pixels:"))
        self.cv_pixels = QSpinBox()
        self.cv_pixels.setRange(0, 10000)
        self.cv_pixels.setSingleStep(1)
        self.cv_pixels.setValue(int(self._config.get('chat_color_verify_min_pixels', 15)))
        self.cv_pixels.valueChanged.connect(lambda v: self._config.set('chat_color_verify_min_pixels', int(v)))
        row_cv.addWidget(self.cv_pixels)
        row_cv.addStretch()
        dbg_layout.addLayout(row_cv)
        # Mask dilation row (separate for visibility)
        row_cv2 = QHBoxLayout()
        row_cv2.addWidget(QLabel("Mask dilate (iters):"))
        self.cv_dilate = QSpinBox()
        self.cv_dilate.setRange(0, 5)
        self.cv_dilate.setSingleStep(1)
        self.cv_dilate.setValue(int(self._config.get('chat_color_mask_dilate_iters', 0)))
        self.cv_dilate.valueChanged.connect(lambda v: self._config.set('chat_color_mask_dilate_iters', int(v)))
        row_cv2.addWidget(self.cv_dilate)
        row_cv2.addStretch()
        dbg_layout.addLayout(row_cv2)
        row_dbg = QHBoxLayout()
        self.debug_save_cb = QCheckBox("Save debug crops/masks to outputs/")
        self.debug_save_cb.setChecked(bool(self._config.get('chat_debug_save', False)))
        self.debug_save_cb.toggled.connect(lambda v: self._config.set('chat_debug_save', bool(v)))
        row_dbg.addWidget(self.debug_save_cb)
        row_dbg.addStretch()
        dbg_layout.addLayout(row_dbg)

        row_test = QHBoxLayout()
        self.test_btn = QPushButton("Test OCR & Mask Now")
        self.test_btn.clicked.connect(self._on_test_ocr)
        row_test.addWidget(self.test_btn)
        row_test.addStretch()
        dbg_layout.addLayout(row_test)
        main.addWidget(dbg_group)
        main.addStretch()

    def _on_coord_selected(self, x: int, y: int):
        try:
            self._config.set('chat_prayer_enable_xy', {'x': int(x), 'y': int(y)})
        except Exception as e:
            logger.error(f"Failed to save prayer coordinate: {e}")

    # ---------- Debug / Test OCR ----------
    def _cv_to_qpixmap(self, img):
        try:
            if img is None or img.size == 0:
                return QPixmap()
            if len(img.shape) == 2:
                h, w = img.shape
                qimg = QImage(img.data, w, h, w, QImage.Format_Grayscale8)
                return QPixmap.fromImage(qimg.copy())
            # Assume BGR
            rgb = img[:, :, ::-1]
            h, w, ch = rgb.shape
            bytes_per_line = ch * w
            qimg = QImage(rgb.data, w, h, bytes_per_line, QImage.Format_RGB888)
            return QPixmap.fromImage(qimg.copy())
        except Exception:
            return QPixmap()

    def _preprocess(self, img):
        import cv2
        import numpy as np
        try:
            gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        except Exception:
            gray = img
        clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
        gray = clahe.apply(gray)
        bw = cv2.adaptiveThreshold(gray, 255, cv2.ADAPTIVE_THRESH_MEAN_C, cv2.THRESH_BINARY, 41, 10)
        bw = cv2.morphologyEx(bw, cv2.MORPH_OPEN, np.ones((1, 1), np.uint8))
        return bw

    def _ocr_lines(self, img_bin):
        try:
            import pytesseract  # type: ignore
        except Exception:
            return []
        lang = str(self._config.get('chat_ocr_lang', 'eng') or 'eng')
        cfg = f"--oem 3 --psm 6 -l {lang}"
        try:
            txt = pytesseract.image_to_string(img_bin, config=cfg)
        except Exception:
            return []
        return [l.strip() for l in txt.splitlines() if l.strip()]

    def _ocr_line_boxes(self, img_bin):
        try:
            import pytesseract  # type: ignore
            from pytesseract import Output as TessOutput  # type: ignore
        except Exception:
            return []
        try:
            lang = str(self._config.get('chat_ocr_lang', 'eng') or 'eng')
            data = pytesseract.image_to_data(img_bin, output_type=TessOutput.DICT, config=f"-l {lang}")
        except Exception:
            return []
        n = int(data.get('level') and len(data['level']) or 0)
        if n == 0:
            return []
        lines = {}
        for i in range(n):
            conf = data.get('conf', ['-1'])[i]
            try:
                if conf is None or (isinstance(conf, str) and conf.strip() == "-1"):
                    continue
            except Exception:
                pass
            txt = data.get('text', [''])[i]
            if not txt or not str(txt).strip():
                continue
            key = (data.get('block_num', [0])[i], data.get('par_num', [0])[i], data.get('line_num', [0])[i])
            x = int(data.get('left', [0])[i]); y = int(data.get('top', [0])[i])
            w = int(data.get('width', [0])[i]); h = int(data.get('height', [0])[i])
            if key not in lines:
                lines[key] = {'text': str(txt), 'bbox': [x, y, x + w, y + h]}
            else:
                lines[key]['text'] += ' ' + str(txt)
                bx0, by0, bx1, by1 = lines[key]['bbox']
                lines[key]['bbox'] = [min(bx0, x), min(by0, y), max(bx1, x + w), max(by1, y + h)]
        out = []
        for v in lines.values():
            t = v['text'].strip().lower()
            x0, y0, x1, y1 = v['bbox']
            out.append((t, (x0, y0, max(1, x1 - x0), max(1, y1 - y0))))
        return out

    def _on_test_ocr(self):
        try:
            frame = None
            chat_roi = self._config.get_roi('chat_roi')
            if chat_roi is not None and hasattr(self._controller, 'capture_service') and self._controller.capture_service:
                frame = self._controller.capture_service.capture_region(chat_roi)
            if frame is None:
                logger.warning("No frame captured for Chat ROI; cannot run OCR test")
                return
            import cv2
            import numpy as np
            from ...core.detection.color_detector import build_mask
            from ...core.config import ColorSpec

            prep = self._preprocess(frame)
            lines = self._ocr_lines(prep)
            bboxes = self._ocr_line_boxes(prep)

            # Build log
            log_lines = ["OCR lines:"] + [f"- {ln}" for ln in lines]

            # Define patterns and color spec keys
            tests = [
                ("Your prayers have been disabled!", 'chat_text_color_prayer_disabled'),
                ("YOU BETTER RUN!", 'chat_text_color_ybr'),
                ("Rebirth Demon disabled your prayers", 'chat_text_color_rebirth_disabled'),
            ]
            matched_any = False
            show_crop = None
            show_mask = None
            # store suggested colors per pattern key
            suggestions = {}
            min_ratio = float(self._config.get('chat_color_verify_min_ratio', 0.03))
            min_pixels = int(self._config.get('chat_color_verify_min_pixels', 30))
            for pat, color_key in tests:
                pnorm = pat.strip().lower()
                # Check if present in any OCR line
                present = any(pnorm in (t or '') for (t, _b) in bboxes) or any(pnorm in ln.lower() for ln in lines)
                if not present:
                    log_lines.append(f"[NO MATCH] {pat}")
                    continue
                # find bbox
                bb = None
                for t, b in bboxes:
                    if pnorm in t:
                        bb = b
                        break
                # If no bbox, fall back to using entire ROI frame
                if bb is not None:
                    x, y, w, h = bb
                    x = max(0, min(frame.shape[1] - 1, x))
                    y = max(0, min(frame.shape[0] - 1, y))
                    w = max(1, min(frame.shape[1] - x, w))
                    h = max(1, min(frame.shape[0] - y, h))
                    roi = frame[y:y+h, x:x+w]
                else:
                    roi = frame

                spec = self._config.get_color_spec(color_key)
                if spec is None:
                    # No spec yet: compute a suggestion from ROI so user can apply it
                    try:
                        B = roi[:, :, 0].astype(np.int32)
                        G = roi[:, :, 1].astype(np.int32)
                        R = roi[:, :, 2].astype(np.int32)
                        m_red = (R > G + 25) & (R > B + 25)
                        m_blue = (B > G + 25) & (B > R + 25)
                        count_red = int(m_red.sum())
                        count_blue = int(m_blue.sum())
                        chosen = None
                        if count_red >= 12 or count_blue >= 12:
                            if count_red >= count_blue:
                                ys, xs = np.where(m_red)
                            else:
                                ys, xs = np.where(m_blue)
                            samples = roi[ys, xs, :]
                            med = np.median(samples, axis=0).astype(int).tolist()
                            sugg = (int(med[2]), int(med[1]), int(med[0]))
                            log_lines.append(f"[SUGGEST] {pat} text RGB ≈ {sugg} (channel-dominance) from {len(samples)} px (no spec set)")
                            chosen = sugg
                        if chosen is None:
                            gray_roi = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
                            _th, bin_inv = cv2.threshold(gray_roi, 0, 255, cv2.THRESH_BINARY_INV+cv2.THRESH_OTSU)
                            coords = np.column_stack(np.where(bin_inv > 0))
                            if coords.size > 0:
                                ys = coords[:, 0]; xs = coords[:, 1]
                                samples = roi[ys, xs, :]
                                med = np.median(samples, axis=0).astype(int).tolist()
                                sugg = (int(med[2]), int(med[1]), int(med[0]))
                                log_lines.append(f"[SUGGEST] {pat} text RGB ≈ {sugg} (otsu) from {len(samples)} px (no spec set)")
                                chosen = sugg
                        if chosen is not None:
                            if 'your prayers have been disabled!' in pnorm:
                                suggestions['chat_text_color_prayer_disabled'] = chosen
                            elif 'you better run!' in pnorm:
                                suggestions['chat_text_color_ybr'] = chosen
                            elif 'rebirth demon disabled your prayers' in pnorm:
                                suggestions['chat_text_color_rebirth_disabled'] = chosen
                        else:
                            log_lines.append(f"[SUGGEST] {pat}: could not compute a reliable color (no spec set)")
                    except Exception:
                        log_lines.append(f"[SUGGEST] {pat}: suggestion failed (no spec set)")
                    # keep a crop for preview
                    if show_crop is None:
                        show_crop = roi.copy()
                        show_mask = None
                    continue
                try:
                    mask, _contours = build_mask(roi, spec, step=1, precise=True, min_area=1)
                except Exception:
                    mask = None
                if mask is None or mask.size == 0:
                    log_lines.append(f"[FAIL] {pat} color mask empty")
                    # Suggest a text color using channel-dominance first (handles strong red/blue chat),
                    # then fall back to Otsu-based dark-pixel sampling.
                    try:
                        B = roi[:, :, 0].astype(np.int32)
                        G = roi[:, :, 1].astype(np.int32)
                        R = roi[:, :, 2].astype(np.int32)
                        # Channel-dominance masks
                        m_red = (R > G + 25) & (R > B + 25)
                        m_blue = (B > G + 25) & (B > R + 25)
                        count_red = int(m_red.sum())
                        count_blue = int(m_blue.sum())
                        chosen = None
                        if count_red >= 12 or count_blue >= 12:
                            if count_red >= count_blue:
                                ys, xs = np.where(m_red)
                            else:
                                ys, xs = np.where(m_blue)
                            samples = roi[ys, xs, :]
                            med = np.median(samples, axis=0).astype(int).tolist()
                            sugg = (int(med[2]), int(med[1]), int(med[0]))
                            log_lines.append(f"    suggested text RGB ≈ {sugg} (channel-dominance) from {len(samples)} px")
                            chosen = sugg
                        if chosen is None:
                            gray_roi = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
                            _th, bin_inv = cv2.threshold(gray_roi, 0, 255, cv2.THRESH_BINARY_INV+cv2.THRESH_OTSU)
                            coords = np.column_stack(np.where(bin_inv > 0))
                            if coords.size > 0:
                                ys = coords[:, 0]; xs = coords[:, 1]
                                samples = roi[ys, xs, :]
                                med = np.median(samples, axis=0).astype(int).tolist()
                                sugg = (int(med[2]), int(med[1]), int(med[0]))
                                log_lines.append(f"    suggested text RGB ≈ {sugg} (otsu) from {len(samples)} px")
                                chosen = sugg
                        if chosen is not None:
                            # Track per pattern key to allow apply button
                            if 'your prayers have been disabled!' in pnorm:
                                suggestions['chat_text_color_prayer_disabled'] = chosen
                            elif 'you better run!' in pnorm:
                                suggestions['chat_text_color_ybr'] = chosen
                            elif 'rebirth demon disabled your prayers' in pnorm:
                                suggestions['chat_text_color_rebirth_disabled'] = chosen
                        else:
                            log_lines.append("    could not compute a reliable suggested color")
                    except Exception:
                        pass
                    # Keep a reference ROI for saving
                    if show_crop is None:
                        show_crop = roi.copy()
                        show_mask = None
                    continue
                pos = int((mask > 0).sum())
                total = int(mask.size)
                ratio = (pos / float(total)) if total > 0 else 0.0
                ok = (ratio >= min_ratio) or (pos >= min_pixels)
                log_lines.append(f"[{'OK' if ok else 'FAIL'}] {pat} color pixels={pos} ratio={ratio:.3f}")
                # Apply optional dilation in test as well to match runtime behavior and help thin text
                try:
                    iters = int(self._config.get('chat_color_mask_dilate_iters', 0) or 0)
                    if iters > 0 and mask is not None and mask.size > 0:
                        kernel = np.ones((3, 3), np.uint8)
                        mask = cv2.dilate(mask, kernel, iterations=iters)
                        pos = int((mask > 0).sum())
                        total = int(mask.size)
                        ratio = (pos / float(total)) if total > 0 else 0.0
                        ok = (ratio >= min_ratio) or (pos >= min_pixels)
                        log_lines.append(f"    after dilate iters={iters} -> pixels={pos} ratio={ratio:.3f} -> {'OK' if ok else 'FAIL'}")
                except Exception:
                    pass
                # If still not ok, compute and expose a suggestion here too
                if not ok:
                    try:
                        B = roi[:, :, 0].astype(np.int32)
                        G = roi[:, :, 1].astype(np.int32)
                        R = roi[:, :, 2].astype(np.int32)
                        m_red = (R > G + 25) & (R > B + 25)
                        m_blue = (B > G + 25) & (B > R + 25)
                        count_red = int(m_red.sum())
                        count_blue = int(m_blue.sum())
                        chosen = None
                        if count_red >= 12 or count_blue >= 12:
                            if count_red >= count_blue:
                                ys, xs = np.where(m_red)
                            else:
                                ys, xs = np.where(m_blue)
                            samples = roi[ys, xs, :]
                            med = np.median(samples, axis=0).astype(int).tolist()
                            sugg = (int(med[2]), int(med[1]), int(med[0]))
                            log_lines.append(f"    suggested text RGB ≈ {sugg} (channel-dominance) from {len(samples)} px")
                            chosen = sugg
                        if chosen is None:
                            gray_roi = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
                            _th, bin_inv = cv2.threshold(gray_roi, 0, 255, cv2.THRESH_BINARY_INV+cv2.THRESH_OTSU)
                            coords = np.column_stack(np.where(bin_inv > 0))
                            if coords.size > 0:
                                ys = coords[:, 0]; xs = coords[:, 1]
                                samples = roi[ys, xs, :]
                                med = np.median(samples, axis=0).astype(int).tolist()
                                sugg = (int(med[2]), int(med[1]), int(med[0]))
                                log_lines.append(f"    suggested text RGB ≈ {sugg} (otsu) from {len(samples)} px")
                                chosen = sugg
                        if chosen is not None:
                            if 'your prayers have been disabled!' in pnorm:
                                suggestions['chat_text_color_prayer_disabled'] = chosen
                            elif 'you better run!' in pnorm:
                                suggestions['chat_text_color_ybr'] = chosen
                            elif 'rebirth demon disabled your prayers' in pnorm:
                                suggestions['chat_text_color_rebirth_disabled'] = chosen
                    except Exception:
                        pass

                # Optional template check
                if bool(self._config.get('chat_template_enable', False)):
                    # Pick template path
                    tkey = None
                    if 'you better run!' in pnorm:
                        tkey = 'chat_template_ybr_path'
                    elif 'your prayers have been disabled!' in pnorm:
                        tkey = 'chat_template_prayer_disabled_path'
                    elif 'rebirth demon disabled your prayers' in pnorm:
                        tkey = 'chat_template_rebirth_disabled_path'
                    tpath = self._config.get(tkey) if tkey else None
                    if tpath:
                        gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
                        tmpl = cv2.imread(tpath, cv2.IMREAD_GRAYSCALE)
                        if tmpl is not None and tmpl.size > 0 and gray.shape[0] >= tmpl.shape[0] and gray.shape[1] >= tmpl.shape[1]:
                            res = cv2.matchTemplate(gray, tmpl, cv2.TM_CCOEFF_NORMED)
                            _minV, maxV, _minL, _maxL = cv2.minMaxLoc(res)
                            thr = float(self._config.get('chat_template_threshold', 0.7))
                            ok_tmpl = maxV >= thr
                            log_lines.append(f"    template max={maxV:.3f} thr={thr} -> {'OK' if ok_tmpl else 'FAIL'}")
                            ok = ok and ok_tmpl
                        else:
                            log_lines.append("    template not usable (missing or larger than ROI)")
                # Record a representative crop/mask to allow saving, prefer first OK; else first with a mask
                if show_crop is None and (ok or mask is not None):
                    show_crop = roi.copy()
                    try:
                        show_mask = cv2.cvtColor(mask, cv2.COLOR_GRAY2BGR) if mask is not None else None
                    except Exception:
                        show_mask = None
                matched_any = matched_any or ok

            # Show dialog
            dlg = QDialog(self)
            dlg.setWindowTitle("Chat OCR Test Result")
            v = QVBoxLayout(dlg)
            log = QTextEdit()
            log.setReadOnly(True)
            log.setText("\n".join(log_lines + [f"\nResult: {'matched' if matched_any else 'false'}"]))
            v.addWidget(log)
            if show_crop is not None:
                row = QHBoxLayout()
                lbl1 = QLabel("Crop")
                pm1 = self._cv_to_qpixmap(show_crop)
                img1 = QLabel()
                img1.setPixmap(pm1)
                img1.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
                row.addWidget(lbl1)
                row.addWidget(img1)
                if show_mask is not None:
                    lbl2 = QLabel("Mask")
                    pm2 = self._cv_to_qpixmap(show_mask)
                    img2 = QLabel()
                    img2.setPixmap(pm2)
                    img2.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
                    row.addWidget(lbl2)
                    row.addWidget(img2)
                v.addLayout(row)
            # Apply suggestion buttons for any available suggested colors
            if suggestions:
                btn_row = QHBoxLayout()
                def make_apply_btn(label: str, key: str):
                    btn = QPushButton(label)
                    def _apply():
                        try:
                            r, g, b = suggestions[key]
                            spec = self._config.get_color_spec(key)
                            tol_rgb = int(getattr(spec, 'tol_rgb', 30)) if spec else 30
                            use_hsv = bool(getattr(spec, 'use_hsv', True)) if spec else True
                            tol_h = int(getattr(spec, 'tol_h', 12)) if spec else 12
                            tol_s = int(getattr(spec, 'tol_s', 60)) if spec else 60
                            tol_v = int(getattr(spec, 'tol_v', 60)) if spec else 60
                            self._config.set(key, {
                                'rgb': [int(r), int(g), int(b)],
                                'tol_rgb': tol_rgb,
                                'use_hsv': use_hsv,
                                'tol_h': tol_h,
                                'tol_s': tol_s,
                                'tol_v': tol_v,
                            })
                            human = {
                                'chat_text_color_prayer_disabled': "Prayers disabled",
                                'chat_text_color_ybr': "YOU BETTER RUN!",
                                'chat_text_color_rebirth_disabled': "Rebirth disabled",
                            }.get(key, key)
                            log_lines.append(f"Applied suggested color for {human} -> RGB=({r},{g},{b})")
                            log.setText("\n".join(log_lines + [f"\nResult: {'matched' if matched_any else 'false'}"]))
                        except Exception as e:
                            logger.error(f"Failed to apply suggested color for {key}: {e}")
                    btn.clicked.connect(_apply)
                    return btn
                if 'chat_text_color_prayer_disabled' in suggestions:
                    btn_row.addWidget(make_apply_btn("Apply 'Prayers disabled' color", 'chat_text_color_prayer_disabled'))
                if 'chat_text_color_ybr' in suggestions:
                    btn_row.addWidget(make_apply_btn("Apply 'YOU BETTER RUN!' color", 'chat_text_color_ybr'))
                if 'chat_text_color_rebirth_disabled' in suggestions:
                    btn_row.addWidget(make_apply_btn("Apply 'Rebirth disabled' color", 'chat_text_color_rebirth_disabled'))
                btn_row.addStretch()
                v.addLayout(btn_row)
            # Save debug artifacts (always for Test button to aid tuning)
            if show_crop is None:
                # Fallback: save the whole frame if nothing else captured
                show_crop = frame.copy()
                show_mask = None
            if show_crop is not None:
                try:
                    import os
                    outdir = self._config.get('debug_output_dir', 'outputs') or 'outputs'
                    os.makedirs(outdir, exist_ok=True)
                    ts = int(time.time() * 1000)
                    crop_path = os.path.join(outdir, f"chat_crop_test_{ts}.png")
                    cv2.imwrite(crop_path, show_crop)
                    if show_mask is not None:
                        mask_path = os.path.join(outdir, f"chat_mask_test_{ts}.png")
                        cv2.imwrite(mask_path, show_mask)
                    log_lines.append(f"Saved debug to {outdir} (ts={ts})")
                    log.setText("\n".join(log_lines + [f"\nResult: {'matched' if matched_any else 'false'}"]))
                except Exception:
                    pass

            dlg.resize(800, 600)
            dlg.exec_()
        except Exception as e:
            logger.error(f"Chat OCR test failed: {e}")
