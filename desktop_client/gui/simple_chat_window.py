"""
美化版简单对话窗口

提供美观的对话界面，支持：
- 主题配色
- 消息气泡
- 动画效果
- 输入框快捷键
- 聊天记录持久化和跨窗口同步
"""

import os
import time
import base64
from datetime import datetime
from typing import Optional, List, Callable, Set

from PySide6.QtCore import Qt, Signal, QTimer, QSize, QPropertyAnimation, QEasingCurve, QUrl
from PySide6.QtGui import QFont, QColor, QPixmap, QPainter, QBrush, QPen, QPainterPath, QIcon, QTextDocument
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QTextEdit, QPushButton, QScrollArea, QFrame,
    QSizePolicy, QGraphicsDropShadowEffect, QFileDialog,
    QTextBrowser, QSpacerItem, QMenu, QDialog,
    QGraphicsView, QGraphicsScene, QGraphicsPixmapItem,
    QApplication, QSlider
)
from PySide6.QtGui import QDesktopServices
from PySide6.QtMultimedia import QMediaPlayer, QAudioOutput

from .themes import theme_manager, Theme
from .markdown_utils import MarkdownUtils
from ..services import get_chat_history_manager, ChatMessage


def format_file_size(size_bytes: int) -> str:
    """格式化文件大小"""
    if size_bytes < 1024:
        return f"{size_bytes} B"
    elif size_bytes < 1024 * 1024:
        return f"{size_bytes / 1024:.1f} KB"
    elif size_bytes < 1024 * 1024 * 1024:
        return f"{size_bytes / (1024 * 1024):.1f} MB"
    else:
        return f"{size_bytes / (1024 * 1024 * 1024):.1f} GB"


def format_duration(seconds: float) -> str:
    """格式化时长"""
    minutes = int(seconds // 60)
    secs = int(seconds % 60)
    return f"{minutes}:{secs:02d}"


class VoiceMessageWidget(QFrame):
    """语音消息组件 - 内置音频播放器"""
    
    play_requested = Signal(str)  # 发送音频路径（保留兼容性）
    
    def __init__(self, audio_path: str, duration: float = 0, parent=None):
        super().__init__(parent)
        self._audio_path = audio_path
        self._duration = duration  # 预设时长（秒）
        self._is_playing = False
        self._is_seeking = False  # 是否正在拖动进度条
        
        self.setObjectName("voiceMessage")
        
        # 初始化媒体播放器
        self._player = QMediaPlayer(self)
        self._audio_output = QAudioOutput(self)
        self._player.setAudioOutput(self._audio_output)
        self._audio_output.setVolume(1.0)
        
        # 连接播放器信号
        self._player.playbackStateChanged.connect(self._on_playback_state_changed)
        self._player.positionChanged.connect(self._on_position_changed)
        self._player.durationChanged.connect(self._on_duration_changed)
        self._player.errorOccurred.connect(self._on_error)
        
        # 加载音频文件
        if audio_path and os.path.exists(audio_path):
            self._player.setSource(QUrl.fromLocalFile(audio_path))
        
        # 布局
        layout = QHBoxLayout(self)
        layout.setContentsMargins(10, 8, 10, 8)
        layout.setSpacing(10)
        
        # 播放/暂停按钮
        self._play_btn = QPushButton("▶")
        self._play_btn.setObjectName("voicePlayBtn")
        self._play_btn.setFixedSize(36, 36)
        self._play_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._play_btn.clicked.connect(self._toggle_play)
        layout.addWidget(self._play_btn)
        
        # 进度条
        self._slider = QSlider(Qt.Orientation.Horizontal)
        self._slider.setObjectName("voiceSlider")
        self._slider.setMinimum(0)
        self._slider.setMaximum(1000)  # 使用1000作为精度
        self._slider.setValue(0)
        self._slider.setCursor(Qt.CursorShape.PointingHandCursor)
        self._slider.sliderPressed.connect(self._on_slider_pressed)
        self._slider.sliderReleased.connect(self._on_slider_released)
        self._slider.sliderMoved.connect(self._on_slider_moved)
        layout.addWidget(self._slider, 1)
        
        # 时间显示标签
        self._time_label = QLabel("0:00 / 0:00")
        self._time_label.setObjectName("voiceTimeLabel")
        self._time_label.setMinimumWidth(80)
        layout.addWidget(self._time_label)
        
        # 如果有预设时长，显示它
        if duration > 0:
            self._update_time_display(0, int(duration * 1000))
        
        self._apply_theme()
        theme_manager.register_callback(self._on_theme_changed)
        
    def _on_theme_changed(self, theme: Theme):
        self._apply_theme()
        
    def _apply_theme(self):
        t = theme_manager.current_theme
        c = t.colors
        
        self.setStyleSheet(f"""
            QFrame#voiceMessage {{
                background-color: {c.bg_secondary};
                border: 1px solid {c.border_light};
                border-radius: 12px;
                min-width: 220px;
            }}
            QFrame#voiceMessage:hover {{
                background-color: {c.bg_hover};
            }}
            QPushButton#voicePlayBtn {{
                background-color: {c.primary};
                color: white;
                border: none;
                border-radius: 18px;
                font-size: 14px;
                font-weight: bold;
            }}
            QPushButton#voicePlayBtn:hover {{
                background-color: {c.primary_dark};
            }}
            QPushButton#voicePlayBtn:pressed {{
                background-color: {c.primary_dark};
            }}
            QSlider#voiceSlider {{
                height: 20px;
            }}
            QSlider#voiceSlider::groove:horizontal {{
                border: none;
                height: 4px;
                background: {c.border_light};
                border-radius: 2px;
            }}
            QSlider#voiceSlider::handle:horizontal {{
                background: {c.primary};
                border: none;
                width: 12px;
                height: 12px;
                margin: -4px 0;
                border-radius: 6px;
            }}
            QSlider#voiceSlider::handle:horizontal:hover {{
                background: {c.primary_dark};
                width: 14px;
                height: 14px;
                margin: -5px 0;
                border-radius: 7px;
            }}
            QSlider#voiceSlider::sub-page:horizontal {{
                background: {c.primary};
                border-radius: 2px;
            }}
            QLabel#voiceTimeLabel {{
                color: {c.text_secondary};
                font-size: {t.font_size_small}px;
                background: transparent;
            }}
        """)
    
    def _toggle_play(self):
        """切换播放/暂停状态"""
        if self._player.playbackState() == QMediaPlayer.PlaybackState.PlayingState:
            self._player.pause()
        else:
            self._player.play()
    
    def _on_playback_state_changed(self, state):
        """播放状态变化"""
        if state == QMediaPlayer.PlaybackState.PlayingState:
            self._is_playing = True
            self._play_btn.setText("⏸")
        elif state == QMediaPlayer.PlaybackState.PausedState:
            self._is_playing = False
            self._play_btn.setText("▶")
        elif state == QMediaPlayer.PlaybackState.StoppedState:
            self._is_playing = False
            self._play_btn.setText("▶")
            # 播放完成后重置进度
            self._slider.setValue(0)
            self._update_time_display(0, self._player.duration())
    
    def _on_position_changed(self, position: int):
        """播放位置变化"""
        if not self._is_seeking:
            duration = self._player.duration()
            if duration > 0:
                slider_value = int((position / duration) * 1000)
                self._slider.setValue(slider_value)
            self._update_time_display(position, duration)
    
    def _on_duration_changed(self, duration: int):
        """音频时长变化"""
        self._update_time_display(self._player.position(), duration)
    
    def _on_error(self, error, error_string):
        """播放错误"""
        print(f"音频播放错误: {error_string}")
    
    def _on_slider_pressed(self):
        """滑块按下"""
        self._is_seeking = True
    
    def _on_slider_released(self):
        """滑块释放"""
        self._is_seeking = False
        duration = self._player.duration()
        if duration > 0:
            position = int((self._slider.value() / 1000) * duration)
            self._player.setPosition(position)
    
    def _on_slider_moved(self, value: int):
        """滑块移动"""
        duration = self._player.duration()
        if duration > 0:
            position = int((value / 1000) * duration)
            self._update_time_display(position, duration)
    
    def _update_time_display(self, position: int, duration: int):
        """更新时间显示"""
        pos_str = format_duration(position / 1000) if position >= 0 else "0:00"
        dur_str = format_duration(duration / 1000) if duration > 0 else "0:00"
        self._time_label.setText(f"{pos_str} / {dur_str}")
    
    def set_playing(self, playing: bool):
        """设置播放状态"""
        if playing:
            self._player.play()
        else:
            self._player.pause()
    
    def stop(self):
        """停止播放"""
        self._player.stop()
    
    def cleanup(self):
        """清理资源"""
        self._player.stop()
        self._player.setSource(QUrl())


class VideoMessageWidget(QFrame):
    """视频消息组件"""
    
    play_requested = Signal(str)  # 发送视频路径
    
    def __init__(self, video_path: str, thumbnail_path: str = "", duration: float = 0, parent=None):
        super().__init__(parent)
        self._video_path = video_path
        self._thumbnail_path = thumbnail_path
        self._duration = duration
        
        self.setObjectName("videoMessage")
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        
        # 缩略图容器
        self._thumbnail_container = QWidget()
        self._thumbnail_container.setFixedSize(200, 150)
        thumb_layout = QVBoxLayout(self._thumbnail_container)
        thumb_layout.setContentsMargins(0, 0, 0, 0)
        
        # 缩略图
        self._thumbnail_label = QLabel()
        self._thumbnail_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._thumbnail_label.setFixedSize(200, 150)
        
        if thumbnail_path and os.path.exists(thumbnail_path):
            pixmap = QPixmap(thumbnail_path)
            if not pixmap.isNull():
                scaled = pixmap.scaled(200, 150, Qt.AspectRatioMode.KeepAspectRatio,
                                       Qt.TransformationMode.SmoothTransformation)
                self._thumbnail_label.setPixmap(scaled)
        else:
            self._thumbnail_label.setText("🎬")
            self._thumbnail_label.setStyleSheet("font-size: 48px; background: #333;")
            
        thumb_layout.addWidget(self._thumbnail_label)
        layout.addWidget(self._thumbnail_container)
        
        # 播放按钮覆盖层
        self._play_overlay = QLabel("▶")
        self._play_overlay.setObjectName("videoPlayOverlay")
        self._play_overlay.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._play_overlay.setFixedSize(50, 50)
        # 将播放按钮居中放置在缩略图上
        self._play_overlay.setParent(self._thumbnail_container)
        self._play_overlay.move(75, 50)
        
        # 时长标签
        if duration > 0:
            self._duration_label = QLabel(format_duration(duration))
            self._duration_label.setObjectName("videoDuration")
            self._duration_label.setParent(self._thumbnail_container)
            self._duration_label.move(160, 130)
            
        self._apply_theme()
        theme_manager.register_callback(self._on_theme_changed)
        
    def _on_theme_changed(self, theme: Theme):
        self._apply_theme()
        
    def _apply_theme(self):
        t = theme_manager.current_theme
        c = t.colors
        
        self.setStyleSheet(f"""
            QFrame#videoMessage {{
                background-color: {c.bg_tertiary};
                border: 1px solid {c.border_light};
                border-radius: 8px;
            }}
            QLabel#videoPlayOverlay {{
                background-color: rgba(0, 0, 0, 0.6);
                color: white;
                border-radius: 25px;
                font-size: 24px;
            }}
            QLabel#videoDuration {{
                background-color: rgba(0, 0, 0, 0.7);
                color: white;
                padding: 2px 6px;
                border-radius: 4px;
                font-size: {t.font_size_small}px;
            }}
        """)
        
    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.play_requested.emit(self._video_path)
        super().mousePressEvent(event)


class FileMessageWidget(QFrame):
    """文件消息组件"""
    
    open_requested = Signal(str)  # 发送文件路径
    download_requested = Signal(str)  # 发送文件路径
    
    def __init__(self, file_path: str, file_name: str = "", file_size: int = 0, parent=None):
        super().__init__(parent)
        self._file_path = file_path
        self._file_name = file_name or os.path.basename(file_path)
        self._file_size = file_size
        
        self.setObjectName("fileMessage")
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        
        layout = QHBoxLayout(self)
        layout.setContentsMargins(10, 8, 10, 8)
        layout.setSpacing(10)
        
        # 文件图标
        self._icon_label = QLabel()
        self._icon_label.setFixedSize(40, 40)
        self._icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        # 根据文件扩展名选择图标
        ext = os.path.splitext(self._file_name)[1].lower()
        if ext in ['.pdf']:
            icon_text = "📄"
        elif ext in ['.doc', '.docx']:
            icon_text = "📝"
        elif ext in ['.xls', '.xlsx']:
            icon_text = "📊"
        elif ext in ['.ppt', '.pptx']:
            icon_text = "📽️"
        elif ext in ['.zip', '.rar', '.7z', '.tar', '.gz']:
            icon_text = "🗜️"
        elif ext in ['.txt', '.md', '.json', '.xml']:
            icon_text = "📃"
        elif ext in ['.py', '.js', '.ts', '.java', '.c', '.cpp', '.h']:
            icon_text = "💻"
        else:
            icon_text = "📁"
            
        self._icon_label.setText(icon_text)
        layout.addWidget(self._icon_label)
        
        # 文件信息
        info_layout = QVBoxLayout()
        info_layout.setContentsMargins(0, 0, 0, 0)
        info_layout.setSpacing(2)
        
        self._name_label = QLabel(self._file_name)
        self._name_label.setObjectName("fileName")
        self._name_label.setWordWrap(True)
        self._name_label.setMaximumWidth(200)
        info_layout.addWidget(self._name_label)
        
        if file_size > 0:
            self._size_label = QLabel(format_file_size(file_size))
            self._size_label.setObjectName("fileSize")
            info_layout.addWidget(self._size_label)
            
        layout.addLayout(info_layout)
        layout.addStretch()
        
        # 下载/打开按钮
        self._action_btn = QPushButton("📥")
        self._action_btn.setObjectName("fileActionBtn")
        self._action_btn.setFixedSize(32, 32)
        self._action_btn.setToolTip("打开文件")
        self._action_btn.clicked.connect(self._on_action_clicked)
        layout.addWidget(self._action_btn)
        
        self._apply_theme()
        theme_manager.register_callback(self._on_theme_changed)
        
    def _on_theme_changed(self, theme: Theme):
        self._apply_theme()
        
    def _apply_theme(self):
        t = theme_manager.current_theme
        c = t.colors
        
        self.setStyleSheet(f"""
            QFrame#fileMessage {{
                background-color: {c.bg_secondary};
                border: 1px solid {c.border_light};
                border-radius: 8px;
            }}
            QFrame#fileMessage:hover {{
                background-color: {c.bg_hover};
                border-color: {c.primary};
            }}
            QLabel {{
                background: transparent;
            }}
            QLabel#fileName {{
                color: {c.text_primary};
                font-size: {t.font_size_base}px;
                font-weight: bold;
            }}
            QLabel#fileSize {{
                color: {c.text_secondary};
                font-size: {t.font_size_small}px;
            }}
            QPushButton#fileActionBtn {{
                background-color: {c.primary};
                color: white;
                border: none;
                border-radius: 16px;
                font-size: 14px;
            }}
            QPushButton#fileActionBtn:hover {{
                background-color: {c.primary_dark};
            }}
        """)
        # 设置图标字体大小
        self._icon_label.setStyleSheet("font-size: 28px; background: transparent;")
        
    def _on_action_clicked(self):
        if os.path.exists(self._file_path):
            self.open_requested.emit(self._file_path)
        else:
            self.download_requested.emit(self._file_path)
            
    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._on_action_clicked()
        super().mousePressEvent(event)


class ClickableImageLabel(QLabel):
    """可点击的图片标签，支持点击放大和右键复制"""
    
    clicked = Signal()
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self._image_path = ""
        self._original_pixmap: Optional[QPixmap] = None
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.customContextMenuRequested.connect(self._show_context_menu)
            
    def setImagePath(self, path: str):
        """设置图片路径"""
        self._image_path = path
        
    def setOriginalPixmap(self, pixmap: QPixmap):
        """设置原始 pixmap（未缩放）"""
        self._original_pixmap = pixmap
                
    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit()
        super().mousePressEvent(event)
        
    def _show_context_menu(self, pos):
        """显示右键菜单"""
        menu = QMenu(self)
        
        # 应用主题样式
        t = theme_manager.current_theme
        c = t.colors
        menu.setStyleSheet(f"""
            QMenu {{
                background-color: {c.bg_primary};
                border: 1px solid {c.border_light};
                border-radius: 8px;
                padding: 4px;
            }}
            QMenu::item {{
                padding: 6px 16px;
                border-radius: 4px;
                color: {c.text_primary};
            }}
            QMenu::item:selected {{
                background-color: {c.bg_hover};
            }}
        """)
        
        copy_action = menu.addAction("📋 复制图片")
        copy_action.triggered.connect(self._copy_to_clipboard)
        
        view_action = menu.addAction("🔍 查看大图")
        view_action.triggered.connect(self._show_preview)
        
        menu.exec(self.mapToGlobal(pos))
        
    def _copy_to_clipboard(self):
        """复制图片到剪贴板"""
        pixmap = self._original_pixmap if self._original_pixmap else self.pixmap()
        if pixmap and not pixmap.isNull():
            clipboard = QApplication.clipboard()
            clipboard.setPixmap(pixmap)
            
    def _show_preview(self):
        """显示大图预览"""
        pixmap = self._original_pixmap if self._original_pixmap else self.pixmap()
        if pixmap and not pixmap.isNull():
            dialog = ImagePreviewDialog(pixmap, self._image_path, self.window())
            dialog.exec()


class ImagePreviewDialog(QDialog):
    """图片预览对话框"""
    
    def __init__(self, pixmap: QPixmap, image_path: str = "", parent=None):
        super().__init__(parent)
        self._pixmap = pixmap
        self._image_path = image_path
        
        self.setWindowTitle("图片预览")
        self.setModal(True)
        self.setMinimumSize(400, 300)
        
        # 设置窗口标志，确保对话框在最前面显示
        self.setWindowFlags(
            Qt.WindowType.Dialog |
            Qt.WindowType.WindowCloseButtonHint |
            Qt.WindowType.WindowTitleHint
        )
        
        # 计算合适的窗口大小和位置
        screen = QApplication.primaryScreen()
        dialog_width = 800
        dialog_height = 600
        
        if screen:
            screen_rect = screen.availableGeometry()
            # 窗口最大为屏幕的 80%
            max_w = int(screen_rect.width() * 0.8)
            max_h = int(screen_rect.height() * 0.8)
            
            img_w = pixmap.width()
            img_h = pixmap.height()
            
            # 如果图片比最大尺寸小，使用图片原尺寸加一点边距
            if img_w < max_w and img_h < max_h:
                dialog_width = min(img_w + 40, max_w)
                dialog_height = min(img_h + 80, max_h)
            else:
                dialog_width = max_w
                dialog_height = max_h
                
            self.resize(dialog_width, dialog_height)
            
            # 居中显示 - 使用 availableGeometry 确保在可见区域内
            center_x = screen_rect.x() + (screen_rect.width() - dialog_width) // 2
            center_y = screen_rect.y() + (screen_rect.height() - dialog_height) // 2
            self.move(center_x, center_y)
        else:
            self.resize(dialog_width, dialog_height)
        
        # 主布局
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        
        # 使用 QGraphicsView 显示图片，支持缩放
        self._scene = QGraphicsScene()
        self._view = QGraphicsView(self._scene)
        self._view.setDragMode(QGraphicsView.DragMode.ScrollHandDrag)
        self._view.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        self._view.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self._view.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        
        # 添加图片到场景
        self._pixmap_item = QGraphicsPixmapItem(pixmap)
        self._scene.addItem(self._pixmap_item)
        
        layout.addWidget(self._view, 1)
        
        # 底部按钮区
        btn_frame = QFrame()
        btn_layout = QHBoxLayout(btn_frame)
        btn_layout.setContentsMargins(12, 8, 12, 8)
        
        # 复制按钮
        copy_btn = QPushButton("📋 复制到剪贴板")
        copy_btn.clicked.connect(self._copy_to_clipboard)
        
        # 下载按钮
        download_btn = QPushButton("💾 下载图片")
        download_btn.clicked.connect(self._download_image)
        
        # 适应窗口按钮
        fit_btn = QPushButton("📐 适应窗口")
        fit_btn.clicked.connect(self._fit_to_window)
        
        # 原始大小按钮
        original_btn = QPushButton("1:1 原始大小")
        original_btn.clicked.connect(self._show_original_size)
        
        # 关闭按钮
        close_btn = QPushButton("关闭")
        close_btn.clicked.connect(self.close)
        
        btn_layout.addWidget(copy_btn)
        btn_layout.addWidget(download_btn)
        btn_layout.addWidget(fit_btn)
        btn_layout.addWidget(original_btn)
        btn_layout.addStretch()
        btn_layout.addWidget(close_btn)
        
        layout.addWidget(btn_frame)
        
        # 应用主题
        self._apply_theme()
        
        # 默认适应窗口显示
        QTimer.singleShot(50, self._fit_to_window)
        
    def _apply_theme(self):
        """应用主题样式"""
        t = theme_manager.current_theme
        c = t.colors
        
        self.setStyleSheet(f"""
            QDialog {{
                background-color: {c.bg_primary};
            }}
            QGraphicsView {{
                background-color: {c.bg_secondary};
                border: none;
            }}
            QPushButton {{
                background-color: {c.bg_secondary};
                color: {c.text_primary};
                border: 1px solid {c.border_light};
                border-radius: 6px;
                padding: 8px 16px;
                font-size: {t.font_size_base}px;
            }}
            QPushButton:hover {{
                background-color: {c.bg_hover};
            }}
        """)
        
    def _copy_to_clipboard(self):
        """复制图片到剪贴板"""
        clipboard = QApplication.clipboard()
        clipboard.setPixmap(self._pixmap)
        
    def _download_image(self):
        """下载图片到本地"""
        # 确定默认文件名
        default_name = "image.png"
        if self._image_path and os.path.exists(self._image_path):
            default_name = os.path.basename(self._image_path)
        
        # 打开保存对话框
        file_path, selected_filter = QFileDialog.getSaveFileName(
            self,
            "保存图片",
            default_name,
            "PNG 图片 (*.png);;JPEG 图片 (*.jpg *.jpeg);;所有文件 (*.*)"
        )
        
        if file_path:
            # 根据扩展名确定格式
            ext = os.path.splitext(file_path)[1].lower()
            if ext in ['.jpg', '.jpeg']:
                self._pixmap.save(file_path, "JPEG", 95)
            else:
                self._pixmap.save(file_path, "PNG")
        
    def _fit_to_window(self):
        """适应窗口显示"""
        self._view.fitInView(self._pixmap_item, Qt.AspectRatioMode.KeepAspectRatio)
        
    def _show_original_size(self):
        """显示原始大小"""
        self._view.resetTransform()
        
    def wheelEvent(self, event):
        """鼠标滚轮缩放"""
        factor = 1.15
        if event.angleDelta().y() > 0:
            self._view.scale(factor, factor)
        else:
            self._view.scale(1 / factor, 1 / factor)


class ChatTextBrowser(QTextBrowser):
    """自定义 QTextBrowser 以处理图片缩放和点击"""
    
    image_clicked = Signal(str)  # 发送图片路径信号
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setOpenExternalLinks(False)
        self._image_cache = {}  # 缓存图片路径用于点击
        self._original_pixmaps = {}  # 缓存原始图片用于预览
        
    def loadResource(self, resource_type, name):
        # QTextDocument.ResourceType.ImageResource = 2
        if resource_type == 2:
            url_str = name.toString()
            pixmap = QPixmap()
            file_path = ""
            
            # 处理 data URI
            if url_str.startswith("data:image"):
                try:
                    header, data = url_str.split(",", 1)
                    image_data = base64.b64decode(data)
                    pixmap.loadFromData(image_data)
                    file_path = url_str
                except Exception:
                    return super().loadResource(resource_type, name)
            else:
                # 处理文件路径
                if name.isLocalFile():
                    file_path = name.toLocalFile()
                elif url_str.startswith("file:///"):
                    # Windows: file:///C:/path -> C:/path
                    file_path = url_str[8:] if len(url_str) > 10 and url_str[9] == ':' else url_str[7:]
                else:
                    file_path = url_str
                    
                if os.path.exists(file_path):
                    pixmap = QPixmap(file_path)
                else:
                    return super().loadResource(resource_type, name)
            
            if not pixmap.isNull():
                # 缓存原始图片路径和原始图片
                self._image_cache[url_str] = file_path
                self._original_pixmaps[url_str] = pixmap.copy()
                
                # 计算最大宽度 - 气泡内容区最大宽度 380，减去 padding
                max_width = 320
                
                if pixmap.width() > max_width:
                    scaled = pixmap.scaledToWidth(max_width, Qt.TransformationMode.SmoothTransformation)
                    return scaled
                return pixmap
                
        return super().loadResource(resource_type, name)
    
    def get_original_pixmap(self, url_str: str) -> Optional[QPixmap]:
        """获取原始图片（未缩放）"""
        return self._original_pixmaps.get(url_str)
    
    def get_file_path(self, url_str: str) -> str:
        """获取图片文件路径"""
        return self._image_cache.get(url_str, url_str)
    
    def mousePressEvent(self, event):
        """处理鼠标点击事件，检测是否点击了图片"""
        if event.button() == Qt.MouseButton.LeftButton:
            # 获取点击位置的锚点
            anchor = self.anchorAt(event.pos())
            if anchor:
                # 检查是否是图片链接
                lower_anchor = anchor.lower()
                if any(lower_anchor.endswith(ext) for ext in ['.png', '.jpg', '.jpeg', '.gif', '.bmp', '.webp']) or \
                   anchor.startswith('data:image'):
                    self.image_clicked.emit(anchor)
                    event.accept()
                    return
        super().mousePressEvent(event)


class MessageBubble(QFrame):
    """美化版消息气泡"""
    
    def __init__(self, role: str, content: str, msg_type: str = "text", avatar_path: str = "", parent=None):
        super().__init__(parent)
        self.role = role
        self.msg_type = msg_type
        self._avatar_path = avatar_path  # 自定义头像路径
        self._avatar_pixmap: Optional[QPixmap] = None  # 缓存头像图片
        self._adjusting = False  # 防止 _adjust_size 重入
        self._last_height = 0  # 记录上次设置的高度
        
        self.setObjectName("messageBubble")
        
        # 设置大小策略 - 使用 Expanding 确保填充整个宽度
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)
        
        # 主布局
        self._main_layout = QHBoxLayout(self)
        self._main_layout.setContentsMargins(8, 4, 8, 4)
        self._main_layout.setSpacing(8)
        
        # 头像
        self._avatar_label = QLabel()
        self._avatar_label.setFixedSize(36, 36)
        self._avatar_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        # 加载自定义头像
        if avatar_path and os.path.exists(avatar_path):
            self._load_avatar(avatar_path)
        
        # 内容区域
        self._content_frame = QFrame()
        self._content_frame.setObjectName("bubbleContent")
        self._content_frame.setSizePolicy(QSizePolicy.Policy.Maximum, QSizePolicy.Policy.Minimum)
        content_layout = QVBoxLayout(self._content_frame)
        content_layout.setContentsMargins(12, 10, 12, 8)
        content_layout.setSpacing(4)
        
        # 消息内容
        self._raw_content = content
        self._last_render_time = 0
        self._render_timer = QTimer()
        self._render_timer.setSingleShot(True)
        self._render_timer.timeout.connect(self._perform_render)

        if msg_type == "image":
            self._content_widget = ClickableImageLabel()
            self._content_widget.setObjectName("imageContent")
            self._load_image(content)
            self._content_widget.clicked.connect(self._show_image_preview)
            content_layout.addWidget(self._content_widget)
        elif msg_type == "voice":
            # 语音消息：content 格式为 "path|duration" 或仅 "path"
            parts = content.split("|")
            audio_path = parts[0]
            duration = float(parts[1]) if len(parts) > 1 else 0
            self._content_widget = VoiceMessageWidget(audio_path, duration)
            self._content_widget.play_requested.connect(self._on_voice_play)
            content_layout.addWidget(self._content_widget)
        elif msg_type == "video":
            # 视频消息：content 格式为 "path|thumbnail|duration" 或仅 "path"
            parts = content.split("|")
            video_path = parts[0]
            thumbnail = parts[1] if len(parts) > 1 else ""
            duration = float(parts[2]) if len(parts) > 2 else 0
            self._content_widget = VideoMessageWidget(video_path, thumbnail, duration)
            self._content_widget.play_requested.connect(self._on_video_play)
            content_layout.addWidget(self._content_widget)
        elif msg_type == "file":
            # 文件消息：content 格式为 "path|name|size" 或仅 "path"
            parts = content.split("|")
            file_path = parts[0]
            file_name = parts[1] if len(parts) > 1 else ""
            file_size = int(parts[2]) if len(parts) > 2 else 0
            self._content_widget = FileMessageWidget(file_path, file_name, file_size)
            self._content_widget.open_requested.connect(self._on_file_open)
            self._content_widget.download_requested.connect(self._on_file_download)
            content_layout.addWidget(self._content_widget)
        else:
            self._content_widget = ChatTextBrowser()
            self._content_widget.setObjectName("textContent")
            self._content_widget.setOpenExternalLinks(False)
            self._content_widget.setReadOnly(True)
            # 完全禁用滚动条
            self._content_widget.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
            self._content_widget.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
            # 禁用框架以避免额外空间
            self._content_widget.setFrameShape(QFrame.Shape.NoFrame)
            self._content_widget.setFrameShadow(QFrame.Shadow.Plain)
            self._content_widget.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
            self._content_widget.setMinimumHeight(20)
            self._content_widget.anchorClicked.connect(self._on_link_clicked)
            self._content_widget.image_clicked.connect(self._on_image_clicked)
            self._update_markdown()
            self._content_widget.document().contentsChanged.connect(self._schedule_adjust_size)
            content_layout.addWidget(self._content_widget)
        
        # 时间标签
        self._time_label = QLabel(datetime.now().strftime("%H:%M"))
        self._time_label.setObjectName("timeLabel")
        content_layout.addWidget(self._time_label)
        
        # 根据角色布局 - 确保正确的两端对齐
        if role == "user":
            # 用户消息：右对齐 (弹性空间 + 内容 + 头像)
            # spacer 会尽可能扩展，将内容和头像推到右边
            spacer = QSpacerItem(0, 0, QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)
            self._main_layout.addItem(spacer)
            self._main_layout.addWidget(self._content_frame)
            self._main_layout.addWidget(self._avatar_label, 0, Qt.AlignmentFlag.AlignTop)
            self._time_label.setAlignment(Qt.AlignmentFlag.AlignRight)
        else:
            # AI 消息：左对齐 (头像 + 内容 + 弹性空间)
            # 头像和内容在左边，spacer 填充右边空间
            self._main_layout.addWidget(self._avatar_label, 0, Qt.AlignmentFlag.AlignTop)
            self._main_layout.addWidget(self._content_frame)
            spacer = QSpacerItem(0, 0, QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)
            self._main_layout.addItem(spacer)
            self._time_label.setAlignment(Qt.AlignmentFlag.AlignLeft)
        
        # 设置内容宽度限制 - 气泡根据内容自适应，最大380px
        self._content_frame.setMaximumWidth(380)
        self._content_frame.setMinimumWidth(60)
        
        self._apply_theme()
        theme_manager.register_callback(self._on_theme_changed)
        
    def _on_theme_changed(self, theme: Theme):
        self._apply_theme()
    
    def _load_avatar(self, avatar_path: str):
        """加载自定义头像图片"""
        if avatar_path and os.path.exists(avatar_path):
            pixmap = QPixmap(avatar_path)
            if not pixmap.isNull():
                # 缩放并裁剪为圆形
                size = 36
                # 先缩放到合适大小
                scaled = pixmap.scaled(
                    size, size,
                    Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                    Qt.TransformationMode.SmoothTransformation
                )
                # 裁剪为正方形
                if scaled.width() != scaled.height():
                    x = (scaled.width() - size) // 2
                    y = (scaled.height() - size) // 2
                    scaled = scaled.copy(x, y, size, size)
                self._avatar_pixmap = scaled
                return True
        
        # 如果路径无效或加载失败，清除缓存的 pixmap
        self._avatar_pixmap = None
        return False
    
    def set_avatar(self, avatar_path: str):
        """设置自定义头像"""
        self._avatar_path = avatar_path
        # 尝试加载头像，如果路径为空或加载失败，_load_avatar 返回 False
        # 但我们仍然需要调用 _apply_theme 来重置为默认头像（如果路径被清除）
        self._load_avatar(avatar_path)
        self._apply_theme()
        
    def _apply_theme(self):
        t = theme_manager.current_theme
        c = t.colors
        
        if self.role == "user":
            avatar_text = "👤"
            bubble_bg = c.bubble_user_bg
            bubble_text = c.bubble_user_text
            avatar_bg = c.primary
        else:
            avatar_text = "🤖"
            bubble_bg = c.bubble_ai_bg
            bubble_text = c.bubble_ai_text
            avatar_bg = c.bg_tertiary
        
        # 头像样式 - 支持自定义图片
        if self._avatar_pixmap and not self._avatar_pixmap.isNull():
            # 使用自定义头像（用户和AI消息都可以使用自定义头像）
            # 创建圆形遮罩
            rounded_pixmap = QPixmap(36, 36)
            rounded_pixmap.fill(Qt.GlobalColor.transparent)
            
            painter = QPainter(rounded_pixmap)
            painter.setRenderHint(QPainter.RenderHint.Antialiasing)
            
            # 绘制圆形裁剪路径
            path = QPainterPath()
            path.addEllipse(0, 0, 36, 36)
            painter.setClipPath(path)
            
            # 绘制头像
            painter.drawPixmap(0, 0, self._avatar_pixmap)
            painter.end()
            
            self._avatar_label.setPixmap(rounded_pixmap)
            self._avatar_label.setText("")
            self._avatar_label.setStyleSheet(f"""
                QLabel {{
                    background-color: transparent;
                    border-radius: 18px;
                    border: none;
                }}
            """)
        else:
            # 使用emoji头像
            self._avatar_label.setPixmap(QPixmap())  # 清除图片
            self._avatar_label.setText(avatar_text)
            self._avatar_label.setStyleSheet(f"""
                QLabel {{
                    background-color: {avatar_bg};
                    border-radius: 18px;
                    font-size: 18px;
                    border: none;
                }}
            """)
        
        # 气泡样式 - 根据角色使用不同的圆角
        if self.role == "user":
            self._content_frame.setStyleSheet(f"""
                QFrame#bubbleContent {{
                    background-color: {bubble_bg};
                    border-radius: 16px;
                    border: none;
                    border-top-right-radius: 4px;
                }}
            """)
        else:
            self._content_frame.setStyleSheet(f"""
                QFrame#bubbleContent {{
                    background-color: {bubble_bg};
                    border-radius: 16px;
                    border: 1px solid {c.border_light};
                    border-top-left-radius: 4px;
                }}
            """)
        
        # 文本内容样式
        if self.msg_type == "text":
            self._content_widget.setStyleSheet(f"""
                QTextBrowser {{
                    background: transparent;
                    border: none;
                    margin: 0;
                    padding: 0;
                    color: {bubble_text};
                    font-family: {t.font_family};
                    font-size: {t.font_size_base}px;
                    line-height: 1.5;
                    selection-background-color: {c.primary_light};
                }}
            """)
            self._update_markdown()
        else:
            self._content_widget.setStyleSheet(f"""
                QLabel {{
                    color: {bubble_text};
                    font-family: {t.font_family};
                    font-size: {t.font_size_base}px;
                    background: transparent;
                    border: none;
                }}
            """)
        
        # 时间标签样式
        time_color = "rgba(255,255,255,0.7)" if self.role == "user" else c.text_secondary
        self._time_label.setStyleSheet(f"""
            QLabel {{
                color: {time_color};
                font-size: {t.font_size_small - 1}px;
                background: transparent;
            }}
        """)
        
    def _load_image(self, image_path: str):
        try:
            if image_path.startswith("data:"):
                header, data = image_path.split(",", 1)
                image_data = base64.b64decode(data)
                pixmap = QPixmap()
                pixmap.loadFromData(image_data)
            else:
                pixmap = QPixmap(image_path)
                
            if not pixmap.isNull():
                # 保存原始 pixmap 用于预览和复制
                if isinstance(self._content_widget, ClickableImageLabel):
                    self._content_widget.setOriginalPixmap(pixmap)
                    self._content_widget.setImagePath(image_path)
                
                max_size = 300
                if pixmap.width() > max_size or pixmap.height() > max_size:
                    pixmap = pixmap.scaled(
                        max_size, max_size,
                        Qt.AspectRatioMode.KeepAspectRatio,
                        Qt.TransformationMode.SmoothTransformation
                    )
                self._content_widget.setPixmap(pixmap)
        except Exception as e:
            self._content_widget.setText(f"[图片加载失败: {e}]")
            
    def _show_image_preview(self):
        """显示图片预览"""
        if isinstance(self._content_widget, ClickableImageLabel):
            self._content_widget._show_preview()
            
    def play_voice(self):
        """播放语音消息"""
        if self.msg_type == "voice" and isinstance(self._content_widget, VoiceMessageWidget):
            self._content_widget.set_playing(True)

    def update_content(self, content: str):
        if self.msg_type == "text":
            self._raw_content = content
            current_time = time.time() * 1000
            if current_time - self._last_render_time < 50:
                if not self._render_timer.isActive():
                    self._render_timer.start(50)
            else:
                self._perform_render()
                
    def _perform_render(self):
        self._update_markdown()
        self._adjust_size()
        self._last_render_time = time.time() * 1000
            
    def _update_markdown(self):
        if self.msg_type == "text":
            html = MarkdownUtils.render(self._raw_content, self.role)
            self._content_widget.setHtml(html)
            # 在设置 HTML 后延迟调整大小
            QTimer.singleShot(20, self._adjust_size)
            
    def _schedule_adjust_size(self):
        """延迟调整大小，确保内容完全渲染"""
        if self.msg_type == "text" and not self._adjusting:
            # 使用短延迟确保 HTML 内容完全渲染
            QTimer.singleShot(10, self._adjust_size)
            
    def _adjust_size(self):
        if self.msg_type != "text":
            return
            
        # 防止重入
        if self._adjusting:
            return
        self._adjusting = True
        
        try:
            doc = self._content_widget.document()
            
            # 使用固定的内容宽度以确保一致性
            # 气泡最大宽度 380 - 左右padding(12+12=24) = 356
            available_width = 356
            doc.setTextWidth(available_width)
            
            # 强制文档重新布局
            doc.adjustSize()
            
            # 获取文档实际高度 - 使用多种方法确保准确性
            doc_height = 0
            
            # 方法1: 使用 documentLayout
            layout = doc.documentLayout()
            if layout:
                doc_size = layout.documentSize()
                doc_height = doc_size.height()
            
            # 方法2: 使用 document().size()
            if doc_height <= 0:
                doc_height = doc.size().height()
            
            # 方法3: 使用 idealWidth 计算的高度
            if doc_height <= 0:
                doc.setTextWidth(-1)  # 让文档自动计算宽度
                ideal_width = doc.idealWidth()
                doc.setTextWidth(min(ideal_width, available_width))
                doc_height = doc.size().height()
            
            # 确保最小高度
            if doc_height <= 0:
                doc_height = 24
            
            # 使用精确高度，不添加额外余量（因为 QTextBrowser 已包含内部边距）
            # 只添加少量余量以防止文本被截断
            # 增加余量以避免出现滚动条
            new_height = max(24, int(doc_height) + 12)
            
            # 只有当高度发生变化时才更新，避免无限循环
            if new_height != self._last_height:
                self._last_height = new_height
                
                # 阻止信号以避免触发更多的调整
                self._content_widget.blockSignals(True)
                self._content_widget.setFixedHeight(new_height)
                self._content_widget.blockSignals(False)
                
                # 更新内容框架和气泡大小
                self._content_frame.adjustSize()
                self.adjustSize()
                self.updateGeometry()
                
                # 通知父容器重新布局
                if self.parent():
                    self.parent().updateGeometry()
        finally:
            self._adjusting = False

    def resizeEvent(self, event):
        super().resizeEvent(event)
        # 移除 resizeEvent 中的调整逻辑，避免循环
        # _adjust_size 已经在内容变化时被调用

    def _on_image_clicked(self, image_url: str):
        """处理图片点击事件"""
        self._show_image_from_url(image_url)
    
    def _show_image_from_url(self, url_str: str):
        """从URL加载并显示图片预览"""
        try:
            pixmap = None
            file_path = url_str
            
            # 首先尝试从 ChatTextBrowser 的缓存中获取原始图片
            if isinstance(self._content_widget, ChatTextBrowser):
                pixmap = self._content_widget.get_original_pixmap(url_str)
                file_path = self._content_widget.get_file_path(url_str)
            
            # 如果缓存中没有，则重新加载
            if pixmap is None or pixmap.isNull():
                pixmap = QPixmap()
                if url_str.startswith('data:image'):
                    header, data = url_str.split(",", 1)
                    image_data = base64.b64decode(data)
                    pixmap.loadFromData(image_data)
                else:
                    # 处理文件路径
                    if url_str.startswith("file:///"):
                        file_path = url_str[8:] if len(url_str) > 10 and url_str[9] == ':' else url_str[7:]
                    
                    if os.path.exists(file_path):
                        pixmap = QPixmap(file_path)
                    elif os.path.exists(url_str):
                        pixmap = QPixmap(url_str)
                        file_path = url_str
            
            if pixmap is not None and not pixmap.isNull():
                # 使用顶层窗口作为父窗口，确保对话框正确显示
                parent_window = self.window()
                dialog = ImagePreviewDialog(pixmap, file_path, parent_window)
                dialog.exec()
        except Exception as e:
            print(f"Error showing image preview: {e}")
    
    def _on_voice_play(self, audio_path: str):
        """处理语音播放请求"""
        try:
            # 使用系统默认程序打开音频文件
            from PySide6.QtCore import QUrl
            QDesktopServices.openUrl(QUrl.fromLocalFile(audio_path))
        except Exception as e:
            print(f"播放语音失败: {e}")
            
    def _on_video_play(self, video_path: str):
        """处理视频播放请求"""
        try:
            # 使用系统默认程序打开视频文件
            from PySide6.QtCore import QUrl
            QDesktopServices.openUrl(QUrl.fromLocalFile(video_path))
        except Exception as e:
            print(f"播放视频失败: {e}")
            
    def _on_file_open(self, file_path: str):
        """处理文件打开请求"""
        try:
            from PySide6.QtCore import QUrl
            QDesktopServices.openUrl(QUrl.fromLocalFile(file_path))
        except Exception as e:
            print(f"打开文件失败: {e}")
            
    def _on_file_download(self, file_path: str):
        """处理文件下载请求"""
        # 如果文件不存在，可以触发下载逻辑
        print(f"文件不存在，需要下载: {file_path}")
            
    def _on_link_clicked(self, url):
        url_str = url.toString()
        # 检查是否是图片链接
        lower_url = url_str.lower()
        if any(lower_url.endswith(ext) for ext in ['.png', '.jpg', '.jpeg', '.gif', '.bmp', '.webp']) or \
           url_str.startswith('data:image'):
            # 显示图片预览
            self._show_image_from_url(url_str)
        else:
            QDesktopServices.openUrl(url)


class PasteAwareTextEdit(QTextEdit):
    """支持图片粘贴的输入框"""
    
    image_pasted = Signal(str)
    enter_pressed = Signal()
    
    def canInsertFromMimeData(self, source):
        if source.hasImage():
            return True
        return QTextEdit.canInsertFromMimeData(self, source)
        
    def insertFromMimeData(self, source):
        if source.hasImage():
            image = source.imageData()
            if image:
                import tempfile
                with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f:
                    image.save(f.name, "PNG")
                self.image_pasted.emit(f.name)
            return
        QTextEdit.insertFromMimeData(self, source)
        
    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Return:
            if event.modifiers() == Qt.KeyboardModifier.ShiftModifier:
                QTextEdit.keyPressEvent(self, event)
            else:
                self.enter_pressed.emit()
                event.accept()
        else:
            QTextEdit.keyPressEvent(self, event)


class ChatInputWidget(QFrame):
    """美化版输入框组件"""
    
    send_requested = Signal(str)
    image_requested = Signal(str, str)
    screenshot_requested = Signal()
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("chatInput")
        
        self._attachment_path = None
        
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)
        
        # 附件预览区
        self._preview_frame = QFrame()
        self._preview_frame.setVisible(False)
        self._preview_frame.setStyleSheet("background-color: transparent;")
        preview_layout = QHBoxLayout(self._preview_frame)
        preview_layout.setContentsMargins(12, 4, 12, 4)
        
        self._preview_label = QLabel()
        self._preview_label.setFixedHeight(60)
        self._preview_label.setStyleSheet("border: 1px solid #ccc; border-radius: 4px;")
        
        self._remove_attachment_btn = QPushButton("×")
        self._remove_attachment_btn.setFixedSize(20, 20)
        self._remove_attachment_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._remove_attachment_btn.clicked.connect(self.clear_attachment)
        self._remove_attachment_btn.setStyleSheet("""
            QPushButton {
                background: rgba(0,0,0,0.5);
                color: white;
                border-radius: 10px;
                border: none;
            }
            QPushButton:hover { background: rgba(255,0,0,0.7); }
        """)
        
        preview_layout.addWidget(self._preview_label)
        preview_layout.addWidget(self._remove_attachment_btn)
        preview_layout.addStretch()
        
        main_layout.addWidget(self._preview_frame)
        
        # 输入控制区
        input_container = QFrame()
        layout = QHBoxLayout(input_container)
        layout.setContentsMargins(12, 8, 12, 8)
        layout.setSpacing(8)
        
        self._attach_btn = QPushButton("📎")
        self._attach_btn.setObjectName("attachBtn")
        self._attach_btn.setFixedSize(36, 36)
        self._attach_btn.setToolTip("添加图片")
        self._attach_btn.clicked.connect(self._on_attach_clicked)
        
        self._screenshot_btn = QPushButton("✂️")
        self._screenshot_btn.setObjectName("screenshotBtn")
        self._screenshot_btn.setFixedSize(36, 36)
        self._screenshot_btn.setToolTip("截图")
        self._screenshot_btn.clicked.connect(self.screenshot_requested.emit)
        
        self._input = PasteAwareTextEdit()
        self._input.setObjectName("messageInput")
        self._input.setPlaceholderText("输入消息，按 Enter 发送，Shift+Enter 换行...")
        self._input.setMinimumHeight(40)
        self._input.setMaximumHeight(150)
        self._input.setFixedHeight(40)
        self._input.image_pasted.connect(self.set_attachment)
        self._input.enter_pressed.connect(self._on_send)
        
        self._send_btn = QPushButton("发送")
        self._send_btn.setObjectName("sendBtn")
        self._send_btn.setFixedSize(60, 36)
        self._send_btn.clicked.connect(self._on_send)
        
        layout.addWidget(self._attach_btn)
        layout.addWidget(self._screenshot_btn)
        layout.addWidget(self._input, 1)
        layout.addWidget(self._send_btn)
        
        main_layout.addWidget(input_container)
        
        self._apply_theme()
        theme_manager.register_callback(self._on_theme_changed)
        self._input.textChanged.connect(self._adjust_input_height)
        
    def set_attachment(self, path: str):
        if not path or not os.path.exists(path):
            return
        self._attachment_path = path
        pixmap = QPixmap(path)
        if not pixmap.isNull():
            self._preview_label.setPixmap(pixmap.scaled(
                200, 60,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation
            ))
            self._preview_frame.setVisible(True)
            self._input.setFocus()
            
    def clear_attachment(self):
        self._attachment_path = None
        self._preview_frame.setVisible(False)

    def _adjust_input_height(self):
        doc_height = self._input.document().size().height()
        new_height = min(max(int(doc_height + 10), 40), 150)
        if new_height != self._input.height():
            self._input.setFixedHeight(new_height)
        
    def _on_theme_changed(self, theme: Theme):
        self._apply_theme()
        
    def _apply_theme(self):
        t = theme_manager.current_theme
        c = t.colors
        
        self.setStyleSheet(f"""
            QFrame#chatInput {{
                background-color: {c.bg_primary};
                border-top: 1px solid {c.border_light};
            }}
            
            QPushButton#attachBtn, QPushButton#screenshotBtn {{
                background-color: {c.bg_secondary};
                border: 1px solid {c.border_light};
                border-radius: 18px;
                font-size: 16px;
            }}
            QPushButton#attachBtn:hover, QPushButton#screenshotBtn:hover {{
                background-color: {c.bg_hover};
            }}
            
            QTextEdit#messageInput {{
                background-color: {c.bg_secondary};
                border: 1px solid {c.border_light};
                border-radius: {t.border_radius}px;
                padding: 8px 12px;
                font-family: {t.font_family};
                font-size: {t.font_size_base}px;
                color: {c.text_primary};
            }}
            QTextEdit#messageInput:focus {{
                border-color: {c.primary};
            }}
            
            QPushButton#sendBtn {{
                background-color: {c.primary};
                color: white;
                border: none;
                border-radius: {t.border_radius}px;
                font-weight: bold;
            }}
            QPushButton#sendBtn:hover {{
                background-color: {c.primary_dark};
            }}
            QPushButton#sendBtn:pressed {{
                background-color: {c.primary_dark};
            }}
        """)
        
    def _on_attach_clicked(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "选择图片",
            "",
            "图片文件 (*.png *.jpg *.jpeg *.gif *.bmp *.webp)"
        )
        if file_path:
            self.set_attachment(file_path)
            
    def _on_send(self):
        text = self._input.toPlainText().strip()
        
        if self._attachment_path:
            self.image_requested.emit(self._attachment_path, text)
            self.clear_attachment()
            self._input.clear()
            self._input.setFixedHeight(40)
        elif text:
            self.send_requested.emit(text)
            self._input.clear()
            self._input.setFixedHeight(40)
            
    def set_enabled(self, enabled: bool):
        self._input.setEnabled(enabled)
        self._send_btn.setEnabled(enabled)
        
    def focus_input(self):
        self._input.setFocus()
        
    def set_text(self, text: str):
        self._input.setPlainText(text)


class SimpleChatWindow(QWidget):
    """美化版对话窗口"""
    
    message_sent = Signal(str)
    image_sent = Signal(str, str)
    closed = Signal()
    screenshot_requested = Signal(str)
    
    def __init__(self, api_client=None, config=None, parent=None):
        super().__init__(parent)
        self.api_client = api_client
        self._config = config
        self._user_avatar_path = ""  # 用户头像路径
        self._bot_avatar_path = ""   # Bot头像路径
        self._messages: List[MessageBubble] = []
        self._current_ai_bubble: Optional[MessageBubble] = None
        self._current_ai_message_id: str = ""  # 当前流式响应的消息ID
        
        # 已显示消息ID集合，用于避免重复显示
        self._displayed_message_ids: Set[str] = set()
        
        # 聊天记录管理器
        self._chat_history = get_chat_history_manager()
        
        # 从配置中加载头像路径
        if config:
            if hasattr(config, 'appearance'):
                appearance = getattr(config, 'appearance')
                # 加载用户头像
                if hasattr(appearance, 'user_avatar_path'):
                    self._user_avatar_path = appearance.user_avatar_path or ""
                elif isinstance(appearance, dict) and 'user_avatar_path' in appearance:
                    self._user_avatar_path = appearance.get('user_avatar_path', '') or ""
                # 加载Bot头像
                if hasattr(appearance, 'bot_avatar_path'):
                    self._bot_avatar_path = appearance.bot_avatar_path or ""
                elif isinstance(appearance, dict) and 'bot_avatar_path' in appearance:
                    self._bot_avatar_path = appearance.get('bot_avatar_path', '') or ""
                # 如果bot_avatar_path为空，尝试使用旧的avatar_path作为后备
                if not self._bot_avatar_path:
                    if hasattr(appearance, 'avatar_path'):
                        self._bot_avatar_path = appearance.avatar_path or ""
                    elif isinstance(appearance, dict) and 'avatar_path' in appearance:
                        self._bot_avatar_path = appearance.get('avatar_path', '') or ""
        
        self.setWindowTitle("AstrBot 对话")
        self.setMinimumSize(500, 650)
        self.resize(520, 720)
        
        self.setWindowFlags(
            Qt.WindowType.Window |
            Qt.WindowType.WindowCloseButtonHint |
            Qt.WindowType.WindowMinimizeButtonHint
        )
        
        self._init_ui()
        self._apply_theme()
        theme_manager.register_callback(self._on_theme_changed)
        
        # 连接聊天记录管理器的信号
        self._chat_history.message_added.connect(self._on_history_message_added)
        self._chat_history.message_updated.connect(self._on_history_message_updated)
        self._chat_history.messages_cleared.connect(self._on_history_cleared)
        self._chat_history.history_loaded.connect(self._on_history_loaded)
        
        # 加载历史记录
        self._load_history()
        
    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        
        self._title_bar = self._create_title_bar()
        layout.addWidget(self._title_bar)
        
        self._scroll_area = QScrollArea()
        self._scroll_area.setObjectName("messageArea")
        self._scroll_area.setWidgetResizable(True)
        self._scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        
        self._message_container = QWidget()
        self._message_container.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        self._message_layout = QVBoxLayout(self._message_container)
        self._message_layout.setContentsMargins(16, 16, 16, 16)
        self._message_layout.setSpacing(12)
        self._message_layout.addStretch()
        
        self._scroll_area.setWidget(self._message_container)
        layout.addWidget(self._scroll_area, 1)
        
        self._input_widget = ChatInputWidget()
        self._input_widget.send_requested.connect(self._on_send_message)
        self._input_widget.image_requested.connect(self._on_image_send)
        self._input_widget.screenshot_requested.connect(self._on_screenshot)
        layout.addWidget(self._input_widget)

    def set_attachment(self, path: str):
        self._input_widget.set_attachment(path)
        self.show_and_focus()

    def set_input_text(self, text: str):
        self._input_widget.set_text(text)

    def _on_image_send(self, image_path: str, text: str = ""):
        if os.path.exists(image_path):
            self.add_user_message(image_path, "image")
            if text:
                self.add_user_message(text, "text")
            self.image_sent.emit(image_path, text)
        
    def _create_title_bar(self) -> QFrame:
        title_bar = QFrame()
        title_bar.setObjectName("titleBar")
        title_bar.setFixedHeight(50)
        
        layout = QHBoxLayout(title_bar)
        layout.setContentsMargins(16, 0, 16, 0)
        
        icon_label = QLabel("🤖")
        icon_label.setObjectName("titleIcon")
        
        title_label = QLabel("AstrBot 对话")
        title_label.setObjectName("titleText")
        
        theme_btn = QPushButton("🎨")
        theme_btn.setObjectName("themeBtn")
        theme_btn.setFixedSize(32, 32)
        theme_btn.setToolTip("切换主题")
        theme_btn.clicked.connect(self._show_theme_menu)
        
        clear_btn = QPushButton("🗑️")
        clear_btn.setObjectName("clearBtn")
        clear_btn.setFixedSize(32, 32)
        clear_btn.setToolTip("清空对话")
        clear_btn.clicked.connect(self._clear_messages)
        
        layout.addWidget(icon_label)
        layout.addWidget(title_label)
        layout.addStretch()
        layout.addWidget(theme_btn)
        layout.addWidget(clear_btn)
        
        return title_bar
        
    def _show_theme_menu(self):
        menu = QMenu(self)
        t = theme_manager.current_theme
        c = t.colors
        
        menu.setStyleSheet(f"""
            QMenu {{
                background-color: {c.bg_primary};
                border: 1px solid {c.border_light};
                border-radius: 8px;
                padding: 6px;
            }}
            QMenu::item {{
                padding: 8px 16px;
                border-radius: 4px;
                color: {c.text_primary};
            }}
            QMenu::item:selected {{
                background-color: {c.bg_hover};
            }}
        """)
        
        for theme_name, display_name in theme_manager.get_theme_names():
            action = menu.addAction(display_name)
            action.triggered.connect(lambda checked, n=theme_name: theme_manager.set_theme(n))
            
        menu.exec(self.sender().mapToGlobal(self.sender().rect().bottomLeft()))
        
    def _on_theme_changed(self, theme: Theme):
        self._apply_theme()
        
    def _apply_theme(self):
        t = theme_manager.current_theme
        c = t.colors
        
        self.setStyleSheet(f"""
            QWidget {{
                background-color: {c.bg_primary};
                font-family: {t.font_family};
            }}
            
            QFrame#titleBar {{
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 {c.primary}, stop:1 {c.primary_dark});
                border: none;
            }}
            
            QLabel#titleIcon {{
                font-size: 22px;
                background: transparent;
            }}
            
            QLabel#titleText {{
                font-size: {t.font_size_large}px;
                font-weight: bold;
                color: white;
                background: transparent;
            }}
            
            QPushButton#themeBtn, QPushButton#clearBtn {{
                background-color: rgba(255,255,255,0.2);
                border: none;
                border-radius: 16px;
                font-size: 14px;
            }}
            QPushButton#themeBtn:hover, QPushButton#clearBtn:hover {{
                background-color: rgba(255,255,255,0.3);
            }}
            
            QScrollArea#messageArea {{
                background-color: {c.bg_primary};
                border: none;
            }}
            
            /* 消息区域内部容器 */
            QScrollArea#messageArea > QWidget > QWidget {{
                background-color: {c.bg_primary};
            }}
            
            QScrollBar:vertical {{
                background-color: transparent;
                width: 6px;
                margin: 4px 2px;
            }}
            QScrollBar::handle:vertical {{
                background-color: {c.border_base};
                border-radius: 3px;
                min-height: 30px;
            }}
            QScrollBar::handle:vertical:hover {{
                background-color: {c.text_secondary};
            }}
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical,
            QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{
                background: transparent;
                height: 0px;
            }}
        """)
        
    def _load_history(self):
        """加载聊天历史记录"""
        # 尝试从文件加载
        self._chat_history.load_from_file()
        
        # 显示已有的消息
        messages = self._chat_history.get_messages()
        for msg in messages:
            self._display_message_from_history(msg)
    
    def _display_message_from_history(self, msg: ChatMessage):
        """从历史记录中显示消息（不会再次添加到历史记录）"""
        if msg.id in self._displayed_message_ids:
            return  # 已经显示过了
        
        self._displayed_message_ids.add(msg.id)
        
        # 根据消息类型创建气泡
        avatar_path = self._user_avatar_path if msg.role == "user" else self._bot_avatar_path
        bubble = MessageBubble(msg.role, msg.content, msg.msg_type, avatar_path=avatar_path)
        bubble.message_id = msg.id
        
        self._message_layout.insertWidget(self._message_layout.count() - 1, bubble)
        self._messages.append(bubble)
    
    def _on_history_message_added(self, msg: ChatMessage):
        """处理历史记录管理器发出的消息添加信号"""
        # 如果消息已经显示过，忽略
        if msg.id in self._displayed_message_ids:
            return
        
        # 显示消息
        self._display_message_from_history(msg)
        self._scroll_to_bottom()
        
        # 检查是否需要自动播放语音
        if msg.role == "assistant" and msg.msg_type == "voice":
            should_play = False
            if self._config:
                if hasattr(self._config, 'voice') and hasattr(self._config.voice, 'auto_play_voice'):
                     should_play = self._config.voice.auto_play_voice
                elif isinstance(self._config, dict):
                     if 'voice' in self._config:
                         should_play = self._config['voice'].get('auto_play_voice', False)
                     else:
                         should_play = self._config.get('auto_play_voice', False)

            if should_play and self._messages:
                last_bubble = self._messages[-1]
                # 再次确认 ID 匹配，防止意外播放了错误的消息
                if getattr(last_bubble, 'message_id', None) == msg.id:
                     last_bubble.play_voice()
    
    def _on_history_message_updated(self, message_id: str, new_content: str):
        """处理历史记录管理器发出的消息更新信号"""
        # 如果是当前正在流式响应的消息，更新气泡内容
        if message_id == self._current_ai_message_id and self._current_ai_bubble:
            self._current_ai_bubble.update_content(new_content)
            self._scroll_to_bottom()
    
    def _on_history_cleared(self):
        """处理历史记录清除信号"""
        # 清空所有显示的消息
        for bubble in self._messages:
            bubble.deleteLater()
        self._messages.clear()
        self._displayed_message_ids.clear()
        self._current_ai_bubble = None
        self._current_ai_message_id = ""
    
    def _on_history_loaded(self):
        """处理历史记录加载完成信号"""
        # 清空当前显示
        for bubble in self._messages:
            bubble.deleteLater()
        self._messages.clear()
        self._displayed_message_ids.clear()
        
        # 重新加载显示
        messages = self._chat_history.get_messages()
        for msg in messages:
            self._display_message_from_history(msg)
        
        self._scroll_to_bottom()
        
    def _on_send_message(self, text: str):
        self.add_user_message(text)
        self.message_sent.emit(text)
        
    def _on_screenshot(self):
        self.screenshot_requested.emit("chat")
        
    def _clear_messages(self):
        """清空所有消息（同时清空历史记录）"""
        self._chat_history.clear_history()
        # 清空操作会通过信号触发 _on_history_cleared
        
    def set_user_avatar(self, avatar_path: str):
        """设置用户头像路径并刷新显示"""
        self._user_avatar_path = avatar_path
        self._refresh_avatars("user")
        
    def set_bot_avatar(self, avatar_path: str):
        """设置Bot头像路径并刷新显示"""
        self._bot_avatar_path = avatar_path
        self._refresh_avatars("assistant")
        
    def set_ai_avatar(self, avatar_path: str):
        """设置AI头像路径（兼容旧接口）"""
        self.set_bot_avatar(avatar_path)

    def _refresh_avatars(self, role: str):
        """刷新指定角色的头像"""
        avatar_path = self._user_avatar_path if role == "user" else self._bot_avatar_path
        for bubble in self._messages:
            if bubble.role == role:
                bubble.set_avatar(avatar_path)
        
    def add_user_message(self, content: str, msg_type: str = "text"):
        """添加用户消息（通过历史记录管理器）"""
        # 通过历史记录管理器添加，会触发信号自动显示
        self._chat_history.add_message(
            role="user",
            content=content,
            msg_type=msg_type
        )
        
    def add_ai_message(self, content: str, msg_type: str = "text"):
        """添加 AI 消息（完整消息，通过历史记录管理器）
        
        如果当前有未完成的流式响应，会先完成它再添加新消息。
        这可以避免消息重复的问题。
        """
        # 如果有正在进行的流式响应，更新它而不是创建新消息
        if self._current_ai_message_id and self._current_ai_bubble:
            # 更新现有消息
            self._chat_history.update_message(self._current_ai_message_id, content)
            self._current_ai_bubble.update_content(content)
            self.finish_ai_response()
            self._scroll_to_bottom()
            return
        
        # 没有进行中的流式响应，正常添加新消息
        # 依赖 message_added 信号更新 UI，避免重复添加
        self._chat_history.add_message(
            role="assistant",
            content=content,
            msg_type=msg_type
        )
        
    def start_ai_response(self):
        """开始 AI 响应（流式响应的开始）
        
        此方法仅设置状态，不创建占位消息。
        实际消息将在第一次调用 update_ai_response() 时创建。
        这可以避免显示空的 "..." 占位消息。
        """
        # 只设置状态，不创建消息
        # 消息将在第一次 update_ai_response 时创建
        self._current_ai_message_id = ""
        self._current_ai_bubble = None
        
    def update_ai_response(self, content: str):
        """更新 AI 响应内容（流式响应）"""
        # 如果还没有创建消息，先创建
        if not self._current_ai_message_id:
            msg = self._chat_history.add_message(
                role="assistant",
                content=content,
                msg_type="text"
            )
            self._current_ai_message_id = msg.id
            
            # 查找对应的气泡
            # 注意：add_message 会触发信号，UI 应该已经通过 _display_message_from_history 更新
            # 我们只需要找到对应的气泡对象
            for bubble in reversed(self._messages):
                if getattr(bubble, 'message_id', None) == msg.id:
                    self._current_ai_bubble = bubble
                    break
        else:
            # 更新已有消息
            self._chat_history.update_message(self._current_ai_message_id, content)
            if self._current_ai_bubble:
                self._current_ai_bubble.update_content(content)
        
        self._scroll_to_bottom()
        
    def update_ai_message(self, content: str):
        """更新 AI 消息内容（旧接口兼容）"""
        self.update_ai_response(content)
            
    def finish_ai_response(self):
        """完成 AI 响应"""
        # 保存最终内容
        if self._current_ai_message_id and self._current_ai_bubble:
            final_content = self._current_ai_bubble._raw_content if hasattr(self._current_ai_bubble, '_raw_content') else ""
            if final_content:
                self._chat_history.update_message(self._current_ai_message_id, final_content)
        
        self._current_ai_bubble = None
        self._current_ai_message_id = ""
        
        # 确保保存
        self._chat_history.save_to_file()
            
    def finish_ai_message(self):
        """完成 AI 消息（旧接口兼容）"""
        self.finish_ai_response()
        
    def add_error_message(self, content: str):
        """添加错误消息（通过历史记录管理器）"""
        error_content = f"❌ {content}"
        self._chat_history.add_message(
            role="assistant",
            content=error_content,
            msg_type="text",
            metadata={"is_error": True}
        )
        
    def _scroll_to_bottom(self):
        QTimer.singleShot(50, lambda: self._scroll_area.verticalScrollBar().setValue(
            self._scroll_area.verticalScrollBar().maximum()
        ))
        
    def show_and_focus(self):
        self.show()
        self.raise_()
        self.activateWindow()
        self._input_widget.focus_input()
        
    def closeEvent(self, event):
        self.closed.emit()
        event.accept()