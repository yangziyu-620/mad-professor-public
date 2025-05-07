from PyQt6.QtWidgets import QWidget, QFrame, QLabel, QHBoxLayout, QVBoxLayout
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QPixmap, QIcon
from paths import get_asset_path
import re

class MessageBubble(QWidget):
    """
    单个消息气泡组件
    
    用于在聊天界面中显示用户或AI消息，气泡样式根据发送者不同而不同
    """
    def __init__(self, message, is_user=True, parent=None, regenerate_callback=None):
        """
        初始化消息气泡
        
        Args:
            message (str): 消息内容
            is_user (bool): 是否为用户消息，True为用户消息，False为AI消息
            parent: 父组件
            regenerate_callback: 重新生成消息的回调函数
        """
        super().__init__(parent)
        self.is_user = is_user
        self.message = message
        self.regenerate_callback = regenerate_callback
        self.init_ui()
        
    def init_ui(self):
        """初始化气泡UI"""
        # 主布局
        main_layout = QHBoxLayout(self)
        main_layout.setContentsMargins(5, 5, 5, 5)
        
        if self.is_user:
            self.setup_user_bubble(main_layout)
        else:
            self.setup_ai_bubble(main_layout)
    
    def setup_user_bubble(self, layout):
        """
        设置用户消息气泡
        
        Args:
            layout: 要添加气泡的布局
        """
        # 用户消息靠右
        layout.addStretch(10)  # 左侧弹性空间更大，确保消息靠右
        
        # 创建气泡及容器
        bubble_container, bubble = self.create_bubble(
            self.message,
            "userBubble",
            "#DCF8C6",  # 背景色
            "#B0F2B6",  # 边框色
            "#2C3E50",  # 文字色
            "15px 15px 0 15px"  # 圆角
        )
        
        # 创建头像
        avatar = self.create_avatar("user_avatar.svg")
        
        # 添加到布局
        layout.addWidget(bubble_container, 7)
        layout.addWidget(avatar)

        # 设置头像顶部对齐
        layout.setAlignment(avatar, Qt.AlignmentFlag.AlignTop)
    
    def setup_ai_bubble(self, layout):
        """
        设置AI消息气泡布局
        
        Args:
            layout: 要设置的布局
        """
        # 创建头像
        avatar = self.create_avatar("ai_avatar.svg")
        
        # 检查/think分隔符，支持/think或/think:，并分割内容
        think_match = re.search(r"/think:?", self.message, re.IGNORECASE)
        if think_match:
            split_idx = think_match.start()
            main_content = self.message[:split_idx].rstrip()
            think_content = self.message[think_match.end():].lstrip()
        else:
            main_content = self.message
            think_content = None
        
        # 创建气泡及容器（传递主内容和think内容）
        bubble_container, bubble = self.create_bubble(
            main_content,
            "aiBubble", 
            "#E3F2FD",  # 背景色
            "#BBDEFB",  # 边框色
            "#1A237E",  # 文字色
            "15px 15px 15px 0",  # 圆角
            think_content,  # think内容
            show_regenerate=True  # AI消息显示重新生成按钮
        )
        
        # 添加到布局
        layout.addWidget(avatar)
        layout.addWidget(bubble_container, 7)
        
        # 设置头像顶部对齐
        layout.setAlignment(avatar, Qt.AlignmentFlag.AlignTop)

    def create_bubble(self, message, object_name, bg_color, border_color, text_color, border_radius, think_content=None, show_regenerate=False):
        """
        创建消息气泡
        
        Args:
            message: 消息内容
            object_name: 气泡的对象名称
            bg_color: 背景颜色
            border_color: 边框颜色
            text_color: 文本颜色
            border_radius: 边框圆角
            think_content: /think部分内容（可选）
            show_regenerate: 是否显示重新生成按钮
        Returns:
            tuple: (气泡容器, 气泡)
        """
        # 创建气泡
        bubble = QFrame()
        bubble.setObjectName(object_name)
        bubble.setStyleSheet(f"""
            #{object_name} {{
                background-color: {bg_color};
                border: 1px solid {border_color};
                border-radius: {border_radius};
                padding: 8px;
                min-width: 200px;
                max-width: 550px;  /* 为AI消息设置更大的最大宽度 */
            }}
        """)
        
        # 创建容器（用于控制气泡大小比例并放置重新生成按钮）
        container = QWidget()
        container_layout = QHBoxLayout(container)
        container_layout.setContentsMargins(0, 0, 0, 0)
        container_layout.setSpacing(8)  # 增加气泡和按钮之间的间距
        
        # 气泡内布局
        bubble_layout = QVBoxLayout(bubble)
        bubble_layout.setContentsMargins(8, 8, 8, 8)
        
        # 消息文本
        msg_label = QLabel(message)
        msg_label.setWordWrap(True)
        msg_label.setStyleSheet(f"color: {text_color}; font-size: 14px;")
        msg_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        bubble_layout.addWidget(msg_label)
        
        # 如果有think内容，添加可展开/收起区域
        if think_content is not None:
            from PyQt6.QtWidgets import QPushButton
            self.think_label = QLabel(think_content)
            self.think_label.setWordWrap(True)
            self.think_label.setStyleSheet("color: #607D8B; font-size: 13px; background: #F5F7FA; border-radius: 6px; padding: 6px; margin-top: 8px;")
            self.think_label.setVisible(False)
            self.think_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)

            self.toggle_btn = QPushButton("显示推理过程")
            self.toggle_btn.setCheckable(True)
            self.toggle_btn.setStyleSheet("QPushButton { font-size: 12px; color: #1976D2; background: transparent; border: none; text-align: left; margin-top: 4px; } QPushButton:checked { color: #D32F2F; }")
            self.toggle_btn.setChecked(False)
            def toggle():
                if self.toggle_btn.isChecked():
                    self.think_label.setVisible(True)
                    self.toggle_btn.setText("收起推理过程")
                else:
                    self.think_label.setVisible(False)
                    self.toggle_btn.setText("显示推理过程")
            self.toggle_btn.clicked.connect(toggle)
            bubble_layout.addWidget(self.toggle_btn)
            bubble_layout.addWidget(self.think_label)
        
        # 添加气泡到容器布局
        container_layout.addWidget(bubble)
        
        # 如果是AI消息且需要显示重新生成按钮，将按钮添加到右侧
        if show_regenerate and self.regenerate_callback:
            from PyQt6.QtWidgets import QPushButton
            
            # 创建重新生成按钮（使用图标）- 完全圆形设计
            regenerate_button = QPushButton()
            regenerate_button.setIcon(QIcon(get_asset_path("refresh.svg")))
            regenerate_button.setToolTip("重新生成回答")
            regenerate_button.setFixedSize(36, 36)  # 稍微增大按钮尺寸
            regenerate_button.setStyleSheet("""
                QPushButton {
                    background-color: rgba(25, 118, 210, 0.1);
                    border: 1px solid rgba(25, 118, 210, 0.3);
                    border-radius: 18px;  /* 圆形按钮，半径为宽高的一半 */
                    padding: 4px;
                    margin-top: 5px;
                }
                QPushButton:hover {
                    background-color: rgba(25, 118, 210, 0.2);
                    border: 1px solid rgba(25, 118, 210, 0.5);
                }
                QPushButton:pressed {
                    background-color: rgba(25, 118, 210, 0.3);
                }
            """)
            regenerate_button.clicked.connect(self.regenerate_callback)
            
            # 添加到容器布局的右侧
            container_layout.addWidget(regenerate_button)
            container_layout.setAlignment(regenerate_button, Qt.AlignmentFlag.AlignTop)
        
        # 右侧添加弹性空间，对于用户消息不添加
        if object_name != "userBubble":
            container_layout.addStretch(3)
        
        return container, bubble
    
    def create_avatar(self, avatar_filename):
        """
        创建头像标签
        
        Args:
            avatar_filename: 头像文件名
            
        Returns:
            QLabel: 包含头像的标签
        """
        avatar = QLabel()
        avatar.setFixedSize(32, 32)
        avatar.setStyleSheet("border-radius: 16px;")
        
        # 获取头像路径并加载
        avatar_path = get_asset_path(avatar_filename)
        avatar.setPixmap(QPixmap(avatar_path).scaled(
            32, 32, 
            Qt.AspectRatioMode.KeepAspectRatio, 
            Qt.TransformationMode.SmoothTransformation
        ))
        
        return avatar
    

class LoadingBubble(QWidget):
    """
    显示加载动画的气泡组件
    
    用于在等待AI响应时显示动画效果
    """
    def __init__(self, parent=None):
        """初始化加载气泡"""
        super().__init__(parent)
        
        # 设置布局
        layout = QHBoxLayout(self)
        layout.setContentsMargins(5, 5, 5, 5)
        
        # 创建气泡框架
        bubble = QFrame()
        bubble.setObjectName("loadingBubble")
        bubble.setStyleSheet("""
            #loadingBubble {
                background-color: #E3F2FD;
                border: 1px solid #BBDEFB;
                border-radius: 15px 15px 15px 0;
                padding: 8px;
                min-width: 80px;
            }
        """)
        
        # 气泡内布局
        bubble_layout = QHBoxLayout(bubble)
        bubble_layout.setContentsMargins(10, 10, 10, 10)
        
        # 加载文本
        self.loading_label = QLabel("AI思考中")
        self.loading_label.setStyleSheet("color: #1A237E; font-size: 14px;")
        
        bubble_layout.addWidget(self.loading_label)
        layout.addWidget(bubble)
        layout.addStretch(1)
        
        # 设置动画计时器
        self.dots_count = 0
        self.animation_timer = QTimer(self)
        self.animation_timer.timeout.connect(self.update_animation)
        self.animation_timer.start(500)  # 每500ms更新一次
    
    def update_animation(self):
        """更新加载动画文本"""
        self.dots_count = (self.dots_count + 1) % 4
        dots = "." * self.dots_count
        self.loading_label.setText(f"AI思考中{dots}")
    
    def stop_animation(self):
        """停止动画"""
        self.animation_timer.stop()