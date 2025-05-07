from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QPushButton, 
                           QTextEdit, QScrollArea, QLabel, QFrame, QComboBox, QMenu)
from PyQt6.QtCore import Qt, QTimer, QSize, QPropertyAnimation, QEasingCurve
from PyQt6.QtGui import QIcon, QFont

# 导入自定义组件和工具类
from paths import get_asset_path
from ui.message_bubble import MessageBubble, LoadingBubble
from AI_manager import AIManager

class ChatWidget(QWidget):
    """
    AI对话框组件
    
    提供用户与AI助手进行对话的界面，包括消息显示、输入框和控制按钮
    """
    # 颜色常量定义
    COLOR_UNINIT = "#9E9E9E"  # 灰色：未初始化
    COLOR_INIT = "#2196F3"    # 蓝色：初始化完成未激活
    COLOR_ACTIVE = "#4CAF50"  # 绿色：激活待命
    COLOR_VAD = "#FFC107"     # 黄色：检测到语音活动
    COLOR_ERROR = "red"       # 红色：错误状态

    def __init__(self, parent=None):
        """初始化聊天组件"""
        super().__init__(parent)
        self.ai_controller = None  # AI控制器引用
        self.paper_controller = None  # 论文控制器引用
        self.loading_bubble = None  # 加载动画引用
        self.is_voice_active = False  # 语音功能是否激活
        
        # 初始化UI
        self.init_ui()
        
        # 界面显示后立即初始化语音功能
        QTimer.singleShot(500, self.init_voice_recognition)
        
    def set_ai_controller(self, ai_controller:AIManager):
        """设置AI控制器引用"""
        self.ai_controller = ai_controller
        # 连接AI控制器信号
        self.ai_controller.ai_response_ready.connect(self.on_ai_response_ready)
        self.ai_controller.ai_sentence_ready.connect(self.on_ai_sentence_ready)  
        self.ai_controller.voice_text_received.connect(self.on_voice_text_received)
        self.ai_controller.vad_started.connect(self.on_vad_started)
        self.ai_controller.vad_stopped.connect(self.on_vad_stopped)
        self.ai_controller.voice_error.connect(self.on_voice_error)
        self.ai_controller.voice_ready.connect(self.on_voice_ready)
        self.ai_controller.voice_device_switched.connect(self.on_device_switched)
        # 新增信号连接
        self.ai_controller.ai_generation_cancelled.connect(self.on_ai_generation_cancelled)
        self.ai_controller.chat_history_updated.connect(self.on_chat_history_updated)
        
        # 初始化模型选择器
        self.init_model_selector()
        
        # 初始化TTS按钮状态
        self.update_tts_button_state()
        
        # 保存当前活动请求ID
        self.active_request_id = None
    
    def set_paper_controller(self, paper_controller):
        """设置论文控制器引用"""
        self.paper_controller = paper_controller

    # 修改set_markdown_view方法
    def set_markdown_view(self, markdown_view):
        """设置Markdown视图引用"""
        self.markdown_view = markdown_view
        # 将markdown_view传递给AI管理器
        if self.ai_controller:
            self.ai_controller.markdown_view = markdown_view
            
    def init_ui(self):
        """初始化用户界面"""
        # 创建主布局
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        
        # 创建组件
        title_bar = self.create_title_bar()
        chat_container = self.create_chat_container()
        
        # 添加到主布局
        layout.addWidget(title_bar)
        layout.addWidget(chat_container)
    
    def create_title_bar(self):
        """
        创建聊天区域标题栏
        
        Returns:
            QFrame: 配置好的标题栏
        """
        # 标题栏
        title_bar = QFrame()
        title_bar.setObjectName("chatTitleBar")
        title_bar.setFixedHeight(36)  # 减小高度，使界面更紧凑
        title_bar.setStyleSheet("""
            #chatTitleBar {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, 
                             stop:0 #1565C0, stop:1 #0D47A1);
                border-top-left-radius: 8px;
                border-top-right-radius: 8px;
                color: white;
            }
        """)
        
        # 标题栏布局
        title_layout = QHBoxLayout(title_bar)
        title_layout.setContentsMargins(8, 0, 8, 0)  # 减小左右边距
        title_layout.setSpacing(8)  # 减小组件间距
        
        # 设置标题文本和字体
        title_font = QFont("Source Han Sans SC", 11, QFont.Weight.Bold)
        title_label = QLabel("你的导师")
        title_label.setFont(title_font)
        title_label.setStyleSheet("color: white; font-weight: bold;")
        title_label.setMinimumWidth(60)  # 减小最小宽度
        
        # 添加刷新按钮 - 优化对比度和细节
        self.refresh_button = QPushButton()
        self.refresh_button.setIcon(QIcon(get_asset_path("refresh.svg")))
        self.refresh_button.setToolTip("刷新界面")
        self.refresh_button.setFixedSize(30, 30)  # 减小按钮尺寸
        self.refresh_button.setIconSize(QSize(16, 16))  # 减小图标尺寸
        self.refresh_button.setStyleSheet("""
            QPushButton {
                background-color: rgba(255, 255, 255, 0.3);
                border: 1px solid rgba(255, 255, 255, 0.5);
                border-radius: 15px;
                padding: 3px;
            }
            QPushButton:hover {
                background-color: rgba(255, 255, 255, 0.5);
            }
            QPushButton:pressed {
                background-color: rgba(255, 255, 255, 0.6);
            }
        """)
        self.refresh_button.clicked.connect(self.refresh_ui)
        
        # 添加历史记录下拉菜单 - 减小宽度
        self.history_selector = QComboBox()
        self.history_selector.setFixedWidth(110)  # 减小宽度
        self.history_selector.setFixedHeight(24)  # 减小高度
        self.history_selector.setStyleSheet("""
            QComboBox {
                background-color: rgba(255, 255, 255, 0.25);
                color: white;
                border: 1px solid rgba(255, 255, 255, 0.4);
                border-radius: 4px;
                padding: 2px 5px;
                font-size: 12px;
            }
            QComboBox::drop-down {
                subcontrol-origin: padding;
                subcontrol-position: top right;
                width: 20px;
                border-left: 1px solid rgba(255, 255, 255, 0.4);
            }
            QComboBox QAbstractItemView {
                background-color: #2C3E50;
                color: white;
                selection-background-color: #34495E;
            }
        """)
        self.history_selector.addItem("选择历史记录")
        self.history_selector.currentIndexChanged.connect(self.on_history_selected)
        
        # 添加新对话按钮 - 统一样式
        self.new_chat_button = QPushButton("新对话")
        self.new_chat_button.setFixedWidth(85)
        self.new_chat_button.setFixedHeight(30)  # 固定高度
        self.new_chat_button.setStyleSheet("""
            QPushButton {
                background-color: rgba(255, 255, 255, 0.25);
                color: white;
                border: 1px solid rgba(255, 255, 255, 0.4);
                border-radius: 4px;
                padding: 2px 5px;
                font-size: 12px;
            }
            QPushButton:hover {
                background-color: rgba(255, 255, 255, 0.35);
            }
        """)
        self.new_chat_button.clicked.connect(self.start_new_chat)
        
        # 添加API提供商选择下拉框 - 统一风格
        self.provider_selector = QComboBox()
        self.provider_selector.setFixedWidth(140)  # 调整宽度
        self.provider_selector.setFixedHeight(30)  # 固定高度
        self.provider_selector.setStyleSheet("""
            QComboBox {
                background-color: rgba(255, 255, 255, 0.25);
                color: white;
                border: 1px solid rgba(255, 255, 255, 0.4);
                border-radius: 4px;
                padding: 2px 5px;
                font-size: 12px;
            }
            QComboBox::drop-down {
                subcontrol-origin: padding;
                subcontrol-position: top right;
                width: 20px;
                border-left: 1px solid rgba(255, 255, 255, 0.4);
            }
            QComboBox QAbstractItemView {
                background-color: #2C3E50;
                color: white;
                selection-background-color: #34495E;
            }
        """)
        
        # 添加模型选择下拉框 - 统一风格
        self.model_selector = QComboBox()
        self.model_selector.setFixedWidth(160)  # 增加宽度以显示更多内容
        self.model_selector.setFixedHeight(30)  # 固定高度
        self.model_selector.setStyleSheet("""
            QComboBox {
                background-color: rgba(255, 255, 255, 0.25);
                color: white;
                border: 1px solid rgba(255, 255, 255, 0.4);
                border-radius: 4px;
                padding: 2px 5px;
                font-size: 12px;
            }
            QComboBox::drop-down {
                subcontrol-origin: padding;
                subcontrol-position: top right;
                width: 20px;
                border-left: 1px solid rgba(255, 255, 255, 0.4);
            }
            QComboBox QAbstractItemView {
                background-color: #2C3E50;
                color: white;
                selection-background-color: #34495E;
            }
        """)
        
        title_layout.addWidget(title_label)
        title_layout.addWidget(self.refresh_button)
        title_layout.addStretch(1)
        title_layout.addWidget(self.history_selector)
        title_layout.addWidget(self.new_chat_button)
        title_layout.addWidget(self.provider_selector)
        title_layout.addWidget(self.model_selector)
        
        return title_bar
    
    def create_chat_container(self):
        """
        创建聊天内容容器
        
        Returns:
            QFrame: 配置好的聊天容器
        """
        # 聊天容器
        chat_container = QFrame()
        chat_container.setObjectName("chatContainer")
        chat_container.setStyleSheet("""
            #chatContainer {
                background-color: #E8EAF6;
                border-left: 1px solid #CFD8DC;
                border-right: 1px solid #CFD8DC;
                border-bottom: 1px solid #CFD8DC;
                border-bottom-left-radius: 12px;
                border-bottom-right-radius: 12px;
            }
        """)
        
        container_layout = QVBoxLayout(chat_container)
        container_layout.setContentsMargins(10, 10, 10, 10)
        
        # 创建消息显示区域
        self.scroll_area = self.create_chat_area()
        
        # 创建输入区域
        input_frame = self.create_input_area()
        
        # 添加到容器布局
        container_layout.addWidget(self.scroll_area, 1)
        container_layout.addWidget(input_frame)
        
        return chat_container
    
    def create_chat_area(self):
        """
        创建聊天消息区域
        
        Returns:
            QScrollArea: 配置好的消息滚动区域
        """
        # 创建滚动区域
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.scroll_area.setStyleSheet("""
            QScrollArea {
                background-color: #F5F7FA;
                border: none;
                border-radius: 0px;
            }
            QScrollBar:vertical {
                border: none;
                background-color: #F5F7FA;
                width: 12px;
                margin: 0px;
            }
            QScrollBar::handle:vertical {
                background-color: #C5CAE9;
                border-radius: 6px;
                min-height: 30px;
            }
            QScrollBar::handle:vertical:hover {
                background-color: #9FA8DA;
            }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
                height: 0px;
            }
            QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {
                background: none;
            }
        """)
        
        # 创建内容容器
        self.messages_container = QWidget()
        self.messages_container.setObjectName("messagesContainer")
        self.messages_container.setStyleSheet("""
            #messagesContainer {
                background-color: #F5F7FA;
                border-radius: 8px;
            }
        """)
        
        # 创建垂直布局用于存放消息
        self.messages_layout = QVBoxLayout(self.messages_container)
        self.messages_layout.setContentsMargins(15, 15, 15, 15)  # 增加边距
        self.messages_layout.setSpacing(15)  # 增加消息间距
        self.messages_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        
        # 添加弹性空间，使消息保持在顶部
        self.messages_layout.addStretch(1)
        
        # 设置滚动区域的内容
        self.scroll_area.setWidget(self.messages_container)
        
        return self.scroll_area

    def create_input_area(self):
        """
        创建消息输入区域
        
        Returns:
            QFrame: 配置好的输入区域框架
        """
        # 输入区域框架
        input_frame = QFrame()
        input_frame.setObjectName("inputFrame")
        input_frame.setStyleSheet("""
            #inputFrame {
                background-color: #FFFFFF;
                border: 1px solid #CFD8DC;
                border-radius: 12px;
                padding: 5px;
            }
        """)
        
        input_layout = QVBoxLayout(input_frame)
        input_layout.setContentsMargins(15, 15, 15, 15)  # 增加内边距
        input_layout.setSpacing(12)  # 增加间距
        
        # 创建文本输入框
        self.message_input = QTextEdit()
        self.message_input.setPlaceholderText("输入您对导师的问题...")
        self.message_input.setMinimumHeight(60)  # 设置最小高度
        self.message_input.setMaximumHeight(120)  # 增加最大高度
        self.message_input.setObjectName("messageInput")
        self.message_input.setStyleSheet("""
            #messageInput {
                border: none;
                background-color: #F5F7FA;
                border-radius: 10px;
                padding: 12px;  /* 增加内边距 */
                font-family: 'Source Han Sans SC', 'Segoe UI', sans-serif;
                font-size: 14px;  /* 增大字体 */
            }
        """)
        # 连接回车键发送功能
        self.message_input.installEventFilter(self)
        
        # 创建控制区容器
        control_container = QWidget()
        control_layout = QHBoxLayout(control_container)
        control_layout.setContentsMargins(0, 8, 0, 0)
        control_layout.setSpacing(15)  # 增加控件间距
        
        # 创建语音控制区
        voice_container = self.create_voice_container()
        
        # 创建发送按钮
        send_button = self.create_send_button()
        
        # 添加到控制布局
        control_layout.addWidget(voice_container)
        control_layout.addStretch(1)
        control_layout.addWidget(send_button)
        
        # 添加到主布局
        input_layout.addWidget(self.message_input)
        input_layout.addWidget(control_container)
        
        return input_frame
    
    def create_voice_container(self):
        """
        创建语音控制容器，包含状态指示灯、麦克风按钮和设备选择
        """
        # 创建容器
        voice_container = QWidget()
        voice_layout = QHBoxLayout(voice_container)
        voice_layout.setContentsMargins(0, 0, 0, 0)
        voice_layout.setSpacing(12)  # 增加间距
        
        # 状态指示灯 - 增大尺寸
        self.voice_status_indicator = QLabel()
        self.voice_status_indicator.setFixedSize(12, 12)  # 稍微增大
        self.voice_status_indicator.setStyleSheet("""
            background-color: #9E9E9E;
            border-radius: 6px;
            border: 1px solid rgba(0, 0, 0, 0.2);
        """)
        voice_layout.addWidget(self.voice_status_indicator)
        
        # 麦克风按钮 - 优化样式
        self.voice_button = self.create_voice_button()
        voice_layout.addWidget(self.voice_button)
        
        # 添加TTS开关按钮 - 统一样式
        self.tts_toggle_button = self.create_tts_toggle_button()
        voice_layout.addWidget(self.tts_toggle_button)
        
        # 创建可交互的设备选择组件 - 优化样式
        self.device_combo = QComboBox()
        self.device_combo.setFixedWidth(200)  # 增加宽度
        self.device_combo.setFixedHeight(32)  # 增加高度
        self.device_combo.setObjectName("deviceCombo")
        
        # 优化样式：修复三角形和添加下拉列表圆角
        self.device_combo.setStyleSheet("""
            QComboBox {
                border: 1px solid #C5CAE9;
                border-radius: 6px;
                padding: 4px 10px 4px 8px;
                background-color: white;
                color: #303F9F;
                font-size: 12px;
                selection-background-color: #E8EAF6;
            }
            QComboBox:hover {
                border: 1px solid #7986CB;
                background-color: #F5F7FA;
            }
            QComboBox:focus {
                border: 1px solid #3F51B5;
            }
            QComboBox::drop-down {
                subcontrol-origin: padding;
                subcontrol-position: center right;
                width: 16px;
                border-left: 1px solid #C5CAE9;
                border-top-right-radius: 5px;
                border-bottom-right-radius: 5px;
                background-color: #E8EAF6;
            }
            QComboBox::down-arrow {
                image: url(""" + get_asset_path("down_arrow.svg").replace("\\", "/") + """);
                width: 12px;
                height: 12px;
            }
            QComboBox QAbstractItemView {
                border: 1px solid #C5CAE9;
                selection-background-color: #E8EAF6;
                selection-color: #303F9F;
                background-color: white;
                border-radius: 5px;
                padding: 5px;
                outline: none;
            }
        """)
        
        # 连接信号
        self.device_combo.currentIndexChanged.connect(self.on_device_changed)
        voice_layout.addWidget(self.device_combo)
        
        return voice_container
    
    def create_voice_button(self):
        """
        创建语音按钮
        
        Returns:
            QPushButton: 配置好的语音按钮
        """
        voice_button = QPushButton()
        voice_button.setIcon(QIcon(get_asset_path("microphone.svg")))
        voice_button.setObjectName("voiceButton")
        voice_button.setFixedSize(36, 36)  # 增大按钮
        voice_button.setCursor(Qt.CursorShape.PointingHandCursor)
        voice_button.setToolTip("点击开启/关闭语音识别")
        voice_button.setIconSize(QSize(18, 18))  # 增大图标
        voice_button.setStyleSheet("""
            #voiceButton {
                background-color: #E3F2FD;
                border: 1px solid #BBDEFB;
                border-radius: 18px;
                padding: 5px;
            }
            #voiceButton:hover {
                background-color: #BBDEFB;
            }
        """)
        voice_button.clicked.connect(self.toggle_voice_detection)
        
        return voice_button
    
    def create_tts_toggle_button(self):
        """创建TTS开关按钮
        
        Returns:
            QPushButton: 配置好的TTS开关按钮
        """
        tts_button = QPushButton()
        tts_button.setIcon(QIcon(get_asset_path("sound_on.svg")))
        tts_button.setObjectName("ttsButton")
        tts_button.setFixedSize(36, 36)  # 增大按钮
        tts_button.setCursor(Qt.CursorShape.PointingHandCursor)
        tts_button.setToolTip("点击开启/关闭语音输出")
        tts_button.setIconSize(QSize(18, 18))  # 增大图标
        tts_button.setStyleSheet("""
            #ttsButton {
                background-color: #E3F2FD;
                border: 1px solid #BBDEFB;
                border-radius: 18px;
                padding: 5px;
            }
            #ttsButton:hover {
                background-color: #BBDEFB;
            }
        """)
        tts_button.clicked.connect(self.toggle_tts)
        
        return tts_button
    
    def create_send_button(self):
        """
        创建发送按钮
        
        Returns:
            QPushButton: 配置好的发送按钮
        """
        send_button = QPushButton("发送")
        send_button.setCursor(Qt.CursorShape.PointingHandCursor)
        send_button.setObjectName("sendButton")
        send_button.setFixedHeight(40)  # 进一步增加高度
        send_button.setMinimumWidth(110)  # 增加宽度
        
        # 美化发送按钮
        send_button.setStyleSheet("""
            #sendButton {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, 
                             stop:0 #303F9F, stop:1 #1A237E);
                color: white;
                border: none;
                border-radius: 10px;
                padding: 10px 24px;
                font-weight: bold;
                font-size: 15px;
            }
            #sendButton:hover {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, 
                             stop:0 #3949AB, stop:1 #303F9F);
            }
            #sendButton:pressed {
                background: #1A237E;
                padding-left: 26px;
                padding-top: 12px;
            }
        """)
        send_button.clicked.connect(self.send_message)
        
        return send_button
    
    def send_message(self):
        """
        发送用户消息
        
        获取输入框中的消息，创建用户消息气泡并清空输入框
        """
        message = self.message_input.toPlainText().strip()
        if message:
            # 清空输入框
            self.message_input.clear()
            
            # 处理消息并获取AI响应
            self.process_message(message)
    
    def process_message(self, message):
        """处理用户消息并获取AI响应"""
        if self.loading_bubble:
            self.loading_bubble.stop_animation()
            self.messages_layout.removeWidget(self.loading_bubble)
            self.loading_bubble.deleteLater()
            self.loading_bubble = None

        # 创建用户消息气泡，并设置合理的宽度
        user_bubble = MessageBubble(message, is_user=True)
        user_bubble.setMinimumWidth(300)  # 确保消息气泡有基本宽度
        user_bubble.setMaximumWidth(600)  # 但也不能太宽，影响阅读
        self.messages_layout.addWidget(user_bubble)
        self.scroll_to_bottom()

        # 如果有AI控制器，则使用AI控制器处理消息
        if self.ai_controller:
            # 如果已经有正在生成的响应或TTS正在播放，先取消它
            if self.ai_controller.is_busy():
                # 中止当前的AI生成和TTS播放
                self.ai_controller.cancel_current_response()
                
                # 如果尚未生成任何内容，检查是否需要合并问题
                if not self.ai_controller.accumulated_response and self.ai_controller.ai_chat:
                    history = self.ai_controller.ai_chat.conversation_history
                    if len(history) >= 1 and history[-1]["role"] == "user":
                        # 找到上一个用户问题
                        prev_question = history[-1]["content"]
                        # 合并问题
                        combined_question = f"{prev_question} {message}"
                        print(f"合并连续问题: '{combined_question}'")
                        
                        # 更新历史记录中的问题
                        history[-1]["content"] = combined_question
                        
                        # 更新message为合并后的问题
                        message = combined_question
            
            # 获取当前论文ID，如果有的话
            paper_id = None
            if self.paper_controller and self.paper_controller.current_paper:
                paper_id = self.paper_controller.current_paper.get('id')

            # 获取当前可见文本，如果有的话
            visible_content = None
            if hasattr(self, 'markdown_view') and self.markdown_view:
                visible_content = self.markdown_view.get_current_visible_text()
            
            # 显示加载动画
            self.loading_bubble = LoadingBubble()
            self.messages_layout.addWidget(self.loading_bubble)
            self.scroll_to_bottom()
            
            # 通过AI控制器获取AI响应，同时保存请求ID
            request_id = self.ai_controller.get_ai_response(message, paper_id, visible_content)
            self.active_request_id = request_id
        else:
            # 使用默认响应
            QTimer.singleShot(500, lambda: self.receive_ai_message(
                f"我已收到您的问题：{message}\n\nAI控制器未连接，无法获取具体响应。"))
    
    def receive_ai_message(self, message):
        """
        接收并显示AI消息
        
        Args:
            message: AI返回的消息内容
        """
        # 添加AI消息气泡，并设置合理的宽度
        ai_bubble = MessageBubble(message, is_user=False, regenerate_callback=self.regenerate_message)
        ai_bubble.setMinimumWidth(200)  # 确保消息气泡有基本宽度
        ai_bubble.setMaximumWidth(550)  # AI回答可能较长，给予更多空间
        self.messages_layout.addWidget(ai_bubble)
        
        # 保存最后一条用户消息，用于重新生成
        self.last_user_message = None
        if self.ai_controller and self.ai_controller.ai_chat and len(self.ai_controller.ai_chat.conversation_history) > 0:
            history = self.ai_controller.ai_chat.conversation_history
            for item in reversed(history):
                if item.get('role') == 'user':
                    self.last_user_message = item.get('content')
                    break
        
        # 滚动到底部
        QTimer.singleShot(100, self.scroll_to_bottom)
    
    def on_ai_sentence_ready(self, sentence, request_id):
        """处理单句AI响应"""
        # 如果请求ID不匹配当前活动请求，忽略这句话
        if request_id != self.active_request_id:
            print(f"忽略过时请求的句子: '{sentence[:20]}...' (请求ID: {request_id})")
            return
            
        # 如果有加载动画且这是第一个句子，移除加载动画
        if self.loading_bubble is not None:
            self.loading_bubble.stop_animation()
            self.messages_layout.removeWidget(self.loading_bubble)
            self.loading_bubble.deleteLater()
            self.loading_bubble = None
        
        # 显示单句回复
        ai_bubble = MessageBubble(sentence, is_user=False, regenerate_callback=self.regenerate_message)
        self.messages_layout.addWidget(ai_bubble)
        
        # 滚动到底部
        QTimer.singleShot(100, self.scroll_to_bottom)
    
    def on_ai_response_ready(self, response):
        """
        当完整AI响应准备好时调用（仅用于非流式响应或流式响应结束）
        
        对于流式响应，主要通过on_ai_sentence_ready处理
        """
        # 如果仍有加载动画，说明是非流式响应或没有分句成功，移除加载动画
        if self.loading_bubble is not None:
            self.loading_bubble.stop_animation()
            self.messages_layout.removeWidget(self.loading_bubble)
            self.loading_bubble.deleteLater()
            self.loading_bubble = None
            
            # 仅对于非流式响应，直接显示完整回复
            # 对于流式响应，所有消息已通过on_ai_sentence_ready单句显示，不需要再次显示
            if self.ai_controller and not self.ai_controller.ai_response_thread.use_streaming:
                self.receive_ai_message(response)
    
    def on_ai_generation_cancelled(self):
        """处理AI生成被取消的情况"""
        # 清理loading bubble
        if self.loading_bubble:
            self.loading_bubble.stop_animation()
            self.messages_layout.removeWidget(self.loading_bubble)
            self.loading_bubble.deleteLater()
            self.loading_bubble = None
        
        # 清除当前请求ID，因为请求已被取消
        self.active_request_id = None
    
    def scroll_to_bottom(self):
        """滚动到对话底部"""
        self.scroll_area.verticalScrollBar().setValue(
            self.scroll_area.verticalScrollBar().maximum()
        )
    
    def toggle_voice_detection(self):
        """显示语音录制状态变化"""
        if not self.ai_controller:
            return
        
        self.is_voice_active = not self.is_voice_active
        success = self.ai_controller.toggle_voice_detection(self.is_voice_active)
        
        # 更新UI状态
        if success and self.is_voice_active:
            # 绿色表示激活待命状态
            self.set_indicator_color(self.COLOR_ACTIVE)
            self.voice_button.setToolTip("点击停止语音输入")
            self.voice_button.setStyleSheet("""
                #voiceButton {
                    background-color: #303F9F;
                    border: 1px solid #1A237E;
                    border-radius: 13px;
                    padding: 3px;
                }
                #voiceButton:hover {
                    background-color: #3949AB;
                }
            """)
        else:
            self.is_voice_active = False  # 如果失败，重置状态
            # 蓝色表示初始化完成但未激活
            self.set_indicator_color(self.COLOR_INIT)
            self.voice_button.setToolTip("点击开始语音输入")
            self.voice_button.setStyleSheet("""
                #voiceButton {
                    background-color: #E3F2FD;
                    border: 1px solid #BBDEFB;
                    border-radius: 13px;
                    padding: 3px;
                }
                #voiceButton:hover {
                    background-color: #BBDEFB;
                }
            """)
    
    def set_indicator_color(self, color):
        """设置语音状态指示灯颜色"""
        self.voice_status_indicator.setStyleSheet(f"""
            background-color: {color}; 
            border-radius: 6px;
            border: 1px solid rgba(0, 0, 0, 0.2);
        """)
    
    def init_voice_recognition(self):
        """初始化语音识别"""
        if self.ai_controller:
            # 初始化前先设置为灰色，表示系统正在初始化
            self.set_indicator_color(self.COLOR_UNINIT)
            
            # 初始化设备列表
            self.refresh_devices()
            
            # 获取选中的设备ID
            device_id = self.get_selected_device_index()
            
            # 初始化AI管理器中的语音识别
            self.ai_controller.init_voice_recognition(device_id)
    
    def refresh_devices(self):
        """刷新设备列表"""
        if not self.ai_controller:
            return
            
        try:
            # 保存当前选择
            current_index = self.device_combo.currentIndex()
            current_device_id = self.device_combo.currentData() if current_index >= 0 else None
            
            # 清空并重新填充设备列表
            self.device_combo.clear()
            
            # 获取设备列表
            devices = self.ai_controller.get_voice_devices()
            for device_id, device_name in devices:
                self.device_combo.addItem(device_name, device_id)
            
            # 尝试恢复之前选择
            if current_device_id is not None:
                index = self.device_combo.findData(current_device_id)
                if index >= 0:
                    self.device_combo.setCurrentIndex(index)
                        
        except Exception as e:
            print(f"刷新设备列表失败: {str(e)}")
    
    def get_selected_device_index(self):
        """获取当前选择的设备索引"""
        index = self.device_combo.currentIndex()
        if index >= 0:
            return self.device_combo.itemData(index)
        return 1  # 默认设备索引
    
    def on_device_changed(self, index):
        """设备选择变更事件"""
        if index < 0 or not self.ai_controller:
            return
                
        device_id = self.device_combo.itemData(index)
        
        # 设置为灰色表示开始初始化
        self.set_indicator_color(self.COLOR_UNINIT)
        self.device_combo.setEnabled(False)
        
        # 切换设备
        success = self.ai_controller.switch_voice_device(device_id)
        if not success:  # 如果切换立即失败
            self.device_combo.setEnabled(True)
            self.set_indicator_color(self.COLOR_ERROR)
            QTimer.singleShot(2000, lambda: 
                self.set_indicator_color(self.COLOR_ACTIVE) if self.is_voice_active 
                else self.set_indicator_color(self.COLOR_INIT))
    
    def on_device_switched(self, success):
        """设备切换结果处理"""
        self.device_combo.setEnabled(True)
        
        if success:
            if self.is_voice_active:
                # 如果语音激活，恢复绿色
                self.set_indicator_color(self.COLOR_ACTIVE)
            else:
                # 如果语音未激活，恢复蓝色
                self.set_indicator_color(self.COLOR_INIT)
        else:
            # 错误时显示红色
            self.set_indicator_color(self.COLOR_ERROR)
            QTimer.singleShot(2000, lambda: 
                self.set_indicator_color(self.COLOR_ACTIVE) if self.is_voice_active 
                else self.set_indicator_color(self.COLOR_INIT))
    
    def on_voice_text_received(self, text):
        """接收到语音文本"""
        self.message_input.setText(text)
        # 自动发送
        self.send_message()
    
    def on_vad_started(self):
        """检测到语音活动开始"""
        if self.is_voice_active:
            # 变为黄色表示检测到语音活动
            self.set_indicator_color(self.COLOR_VAD)
    
    def on_vad_stopped(self):
        """检测到语音活动结束"""
        if self.is_voice_active:
            # 回到绿色表示激活待命状态
            self.set_indicator_color(self.COLOR_ACTIVE)
    
    def on_voice_error(self, error_message):
        """语音识别错误"""
        print(f"语音识别错误: {error_message}")
        self.set_indicator_color(self.COLOR_ERROR)
        QTimer.singleShot(2000, lambda: 
            self.set_indicator_color(self.COLOR_ACTIVE) if self.is_voice_active 
            else self.set_indicator_color(self.COLOR_INIT))
    
    def on_voice_ready(self):
        """语音识别准备就绪"""
        # 启用对话按钮
        self.voice_button.setEnabled(True)
        # 初始化完成后设置为蓝色待命状态
        self.set_indicator_color(self.COLOR_INIT)
    
    def eventFilter(self, obj, event):
        """
        事件过滤器，处理输入框按键事件
        
        当按下回车键且没有按下Shift键时发送消息，
        当按下Shift+回车时插入换行符
        
        Args:
            obj: 事件源对象
            event: 事件对象
            
        Returns:
            bool: 事件是否已处理
        """
        # 检查事件是否来自messageInput，且是键盘按下事件，且按键是回车
        if obj == self.message_input and event.type() == event.Type.KeyPress:
            if event.key() == Qt.Key.Key_Return and not event.modifiers() & Qt.KeyboardModifier.ShiftModifier:
                # 回车键按下且没有按下Shift键，触发发送消息
                self.send_message()
                return True  # 事件已处理
            elif event.key() == Qt.Key.Key_Return and event.modifiers() & Qt.KeyboardModifier.ShiftModifier:
                # Shift+回车，插入换行符
                return False  # 让QTextEdit处理这个事件
        
        # 其他事件交给父类处理
        return super().eventFilter(obj, event)
    
    def closeEvent(self, event):
        """窗口关闭事件处理"""
        # 不再需要手动处理voice_thread，由ai_manager负责清理
        # 如果有父类方法，调用它
        if hasattr(super(), 'closeEvent'):
            super().closeEvent(event)

    def init_model_selector(self):
        """初始化API提供商选择器和模型选择器"""
        if not hasattr(self, 'provider_selector') or not hasattr(self, 'model_selector') or not self.ai_controller:
            return
        
        # 清空之前的项目
        self.provider_selector.clear()
        self.model_selector.clear()
        
        # 获取所有提供商
        providers = self.ai_controller.get_available_providers()
        
        # 获取当前模型和提供商
        current_model = self.ai_controller.get_current_model()
        current_provider = self.ai_controller.get_current_provider()
        
        # 填充提供商选择器
        for provider_name, provider_display in providers.items():
            self.provider_selector.addItem(provider_display, provider_name)
        
        # 连接提供商选择器信号
        self.provider_selector.currentIndexChanged.connect(self.on_provider_changed)
        
        # 设置当前提供商
        if current_provider:
            # 查找当前提供商的索引
            for i in range(self.provider_selector.count()):
                if self.provider_selector.itemData(i) == current_provider:
                    self.provider_selector.setCurrentIndex(i)
                    break
        else:
            # 如果找不到当前提供商，选择第一个
            if self.provider_selector.count() > 0:
                self.on_provider_changed(0)

    def on_provider_changed(self, index):
        """处理提供商选择变化"""
        if index < 0 or not self.ai_controller:
            return
        
        # 获取选择的提供商名称
        provider_name = self.provider_selector.currentData()
        
        # 清空模型选择器
        self.model_selector.clear()
        
        # 获取当前模型
        current_model = self.ai_controller.get_current_model()
        current_name = current_model.get("name", "")
        current_id = self.ai_controller.get_current_model_id()
        
        # 获取该提供商下的所有模型
        provider_models = self.ai_controller.get_provider_models(provider_name)
        
        # 添加该提供商下的模型到模型选择器
        for model_id, description in provider_models.items():
            # 提取更简洁的模型名称显示
            display_name = self.get_simplified_model_name(description)
            self.model_selector.addItem(display_name, model_id)
            
            # 如果是当前模型，设置为当前选择项
            if model_id == current_id:
                self.model_selector.setCurrentText(display_name)
        
        # 连接模型选择器信号（如果尚未连接）
        try:
            self.model_selector.currentIndexChanged.disconnect(self.on_model_changed)
        except:
            pass
        self.model_selector.currentIndexChanged.connect(self.on_model_changed)
        
        # 如果当前没有选中的模型，选择第一个
        if self.model_selector.currentIndex() < 0 and self.model_selector.count() > 0:
            self.model_selector.setCurrentIndex(0)
            # 手动调用模型变更方法以确保切换到第一个模型
            self.on_model_changed(0)

    def get_simplified_model_name(self, full_description):
        """从完整描述中提取简洁的模型名称"""
        # 针对不同提供商的特殊处理
        if "DeepSeek" in full_description:
            if "0324" in full_description:
                return "DeepSeek-V3 0324"
            return "DeepSeek-V3"
        elif "Claude" in full_description:
            if "Sonnet" in full_description:
                return "Claude 3.5 Sonnet"
            return full_description
        elif "ChatGPT" in full_description or "GPT-" in full_description:
            if "mini" in full_description:
                return "GPT-4o-mini"
            return full_description
        elif "Grok" in full_description:
            return "Grok-3-beta"
        elif "QWQ" in full_description or "Qwen" in full_description:
            return "QWQ-32B"
        else:
            return full_description

    def on_model_changed(self, index):
        """处理模型选择变化"""
        if index < 0 or not self.ai_controller:
            return
            
        # 获取选择的模型名
        model_name = self.model_selector.currentData()
        
        # 切换前提示用户
        if self.ai_controller.is_busy():
            # 如果正在生成，提示用户等待完成
            self.receive_ai_message("正在切换到新模型，请稍候...")
            
        # 切换模型
        success = self.ai_controller.switch_model(model_name)
        
        if success:
            model_info = self.ai_controller.get_current_model()
            self.receive_ai_message(f"已切换至 {model_info.get('description', model_name)} 模型")
        else:
            self.receive_ai_message("切换模型失败")

    def toggle_tts(self):
        """切换TTS状态"""
        if not self.ai_controller:
            return
            
        # 获取当前状态并切换
        current_state = self.ai_controller.is_tts_enabled()
        new_state = not current_state
        
        # 更新AI控制器中的状态
        success = self.ai_controller.toggle_tts(new_state)
        
        # 更新UI显示
        if success:
            if new_state:
                # 启用TTS时显示音量图标
                self.tts_toggle_button.setIcon(QIcon(get_asset_path("sound_on.svg")))
                self.tts_toggle_button.setToolTip("点击关闭语音输出")
                self.tts_toggle_button.setStyleSheet("""
                    #ttsButton {
                        background-color: #303F9F;
                        border: 1px solid #1A237E;
                        border-radius: 18px;
                        padding: 5px;
                    }
                    #ttsButton:hover {
                        background-color: #3949AB;
                    }
                """)
                self.receive_ai_message("已启用语音输出")
            else:
                # 禁用TTS时显示静音图标
                self.tts_toggle_button.setIcon(QIcon(get_asset_path("sound_off.svg")))
                self.tts_toggle_button.setToolTip("点击开启语音输出")
                self.tts_toggle_button.setStyleSheet("""
                    #ttsButton {
                        background-color: #E3F2FD;
                        border: 1px solid #BBDEFB;
                        border-radius: 18px;
                        padding: 5px;
                    }
                    #ttsButton:hover {
                        background-color: #BBDEFB;
                    }
                """)
                self.receive_ai_message("已禁用语音输出")
                
    def update_tts_button_state(self):
        """根据AI控制器中的TTS状态更新按钮显示"""
        if not hasattr(self, 'tts_toggle_button') or not self.ai_controller:
            return
            
        try:
            tts_enabled = self.ai_controller.is_tts_enabled()
            
            if tts_enabled:
                # 启用状态
                self.tts_toggle_button.setIcon(QIcon(get_asset_path("sound_on.svg")))
                self.tts_toggle_button.setToolTip("点击关闭语音输出")
                self.tts_toggle_button.setStyleSheet("""
                    #ttsButton {
                        background-color: #303F9F;
                        border: 1px solid #1A237E;
                        border-radius: 18px;
                        padding: 5px;
                    }
                    #ttsButton:hover {
                        background-color: #3949AB;
                    }
                """)
            else:
                # 禁用状态
                self.tts_toggle_button.setIcon(QIcon(get_asset_path("sound_off.svg")))
                self.tts_toggle_button.setToolTip("点击开启语音输出")
                self.tts_toggle_button.setStyleSheet("""
                    #ttsButton {
                        background-color: #E3F2FD;
                        border: 1px solid #BBDEFB;
                        border-radius: 18px;
                        padding: 5px;
                    }
                    #ttsButton:hover {
                        background-color: #BBDEFB;
                    }
                """)
        except Exception as e:
            print(f"更新TTS按钮状态失败: {str(e)}")

    def on_paper_selected(self, paper_id):
        """处理论文选择事件，加载对应的聊天记录"""
        if self.ai_controller:
            # 更新历史记录下拉框
            self.update_history_selector(paper_id)
            
            # 加载最新的聊天记录
            self.load_latest_conversation(paper_id)
    
    def update_history_selector(self, paper_id=None):
        """更新历史记录选择器"""
        if not self.ai_controller:
            return
            
        # 清空当前选项
        self.history_selector.clear()
        self.history_selector.addItem("选择历史记录")
        
        # 获取指定论文的对话日期
        dates = self.ai_controller.get_conversation_dates(paper_id)
        
        # 添加日期到下拉框
        for date in dates:
            self.history_selector.addItem(date)
        
        # 禁用信号处理以防止触发事件
        self.history_selector.blockSignals(True)
        self.history_selector.setCurrentIndex(0)
        self.history_selector.blockSignals(False)
    
    def on_history_selected(self, index):
        """处理历史记录选择事件"""
        if index <= 0 or not self.ai_controller:
            return
            
        # 获取选择的日期
        date = self.history_selector.itemText(index)
        
        # 获取当前论文ID
        paper_id = None
        if self.paper_controller and self.paper_controller.current_paper:
            paper_id = self.paper_controller.current_paper.get('id')
        
        if not paper_id:
            return
            
        # 加载对话历史
        self.load_conversation(paper_id, date)
    
    def load_conversation(self, paper_id, date=None):
        """加载指定论文和日期的对话历史"""
        if not self.ai_controller:
            return
            
        # 清空消息区域
        self.clear_messages()
        
        # 加载对话历史
        success = self.ai_controller.load_conversation_history(paper_id, date)
        
        if success:
            # 显示对话历史
            self.display_conversation_history()
    
    def load_latest_conversation(self, paper_id):
        """加载最新的对话历史"""
        self.load_conversation(paper_id)
    
    def display_conversation_history(self):
        """显示当前对话历史"""
        if not self.ai_controller or not hasattr(self.ai_controller.ai_chat, 'conversation_history'):
            return
            
        # 获取对话历史
        conversation = self.ai_controller.ai_chat.conversation_history
        
        # 清空现有UI元素
        self.clear_messages()
        
        # 记录已处理的消息数量，避免重复处理
        processed_messages = []
        
        # 逐条显示消息
        for message in conversation:
            role = message.get('role')
            content = message.get('content')
            
            # 生成消息唯一标识（基于内容+角色）
            message_id = f"{role}:{content}"
            
            # 检查是否已处理过该消息
            if message_id in processed_messages:
                continue
                
            # 标记为已处理
            processed_messages.append(message_id)
            
            if role == 'user':
                # 显示用户消息
                user_bubble = MessageBubble(content, is_user=True)
                user_bubble.setMinimumWidth(300)
                user_bubble.setMaximumWidth(600)
                self.messages_layout.addWidget(user_bubble)
                
                # 保存最后一条用户消息，用于重新生成
                self.last_user_message = content
                
            elif role == 'assistant':
                # 显示AI消息 - 对于历史消息，仍然添加重新生成按钮
                ai_bubble = MessageBubble(content, is_user=False, regenerate_callback=self.regenerate_message)
                ai_bubble.setMinimumWidth(200)
                ai_bubble.setMaximumWidth(550)
                self.messages_layout.addWidget(ai_bubble)
        
    def clear_messages(self):
        """清空消息区域"""
        # 删除所有消息气泡
        while self.messages_layout.count():
            item = self.messages_layout.takeAt(0)
            widget = item.widget()
            if widget:
                widget.deleteLater()
        
        # 清空最后一条用户消息记录
        self.last_user_message = None

    def start_new_chat(self):
        """开始新的对话"""
        if not self.ai_controller:
            return
        
        # 获取当前论文ID
        paper_id = None
        if self.paper_controller and self.paper_controller.current_paper:
            paper_id = self.paper_controller.current_paper.get('id')
        
        if not paper_id:
            self.receive_ai_message("请先选择一篇论文")
            return
        
        # 清空消息区域
        self.clear_messages()
        
        # 开始新的对话
        success = self.ai_controller.start_new_conversation(paper_id)
        
        if success:
            self.receive_ai_message("已开始新的对话")
            
            # 更新历史记录下拉框
            self.update_history_selector(paper_id)

    def on_chat_history_updated(self, paper_id, date):
        """处理聊天记录更新事件"""
        # 获取当前论文ID
        current_paper_id = None
        if self.paper_controller and self.paper_controller.current_paper:
            current_paper_id = self.paper_controller.current_paper.get('id')
        
        # 如果更新的是当前论文的记录，更新历史记录下拉框
        if current_paper_id == paper_id:
            self.update_history_selector(paper_id)

    def regenerate_message(self):
        """重新生成AI回复"""
        # 如果没有最后一条用户消息，无法重新生成
        if not hasattr(self, 'last_user_message') or not self.last_user_message:
            # 查找最近的一条用户消息
            if self.ai_controller and self.ai_controller.ai_chat and len(self.ai_controller.ai_chat.conversation_history) > 0:
                history = self.ai_controller.ai_chat.conversation_history
                for item in reversed(history):
                    if item.get('role') == 'user':
                        self.last_user_message = item.get('content')
                        break
            
            if not self.last_user_message:
                print("无法重新生成：找不到上一条用户消息")
                return
        
        # 从消息历史中查找需要删除的内容 - 找到最后一组用户+AI消息
        if self.ai_controller and self.ai_controller.ai_chat and len(self.ai_controller.ai_chat.conversation_history) > 0:
            history = self.ai_controller.ai_chat.conversation_history
            last_user_index = -1
            last_ai_index = -1
            
            # 查找最后一个用户消息和之后的AI回复索引
            for i in range(len(history) - 1, -1, -1):
                if history[i].get('role') == 'user' and last_user_index == -1:
                    last_user_index = i
                elif history[i].get('role') == 'assistant' and i > last_user_index and last_ai_index == -1:
                    last_ai_index = i
                    break
            
            # 只删除最后一条AI消息
            if last_ai_index != -1:
                history.pop(last_ai_index)
        
        # 从UI中删除最后一个AI消息
        user_message_found = False
        for i in range(self.messages_layout.count() - 1, -1, -1):
            item = self.messages_layout.itemAt(i)
            widget = item.widget()
            if isinstance(widget, MessageBubble):
                if not widget.is_user and not user_message_found:
                    # 删除最后一个AI消息
                    self.messages_layout.removeWidget(widget)
                    widget.deleteLater()
                    break
                elif widget.is_user:
                    user_message_found = True
        
        # 添加加载动画
        self.loading_bubble = LoadingBubble()
        self.messages_layout.addWidget(self.loading_bubble)
        self.scroll_to_bottom()
        
        # 重新发送用户消息以获取新的回复
        if self.ai_controller:
            # 获取当前论文ID，如果有的话
            paper_id = None
            if self.paper_controller and self.paper_controller.current_paper:
                paper_id = self.paper_controller.current_paper.get('id')
            
            # 获取当前可见文本，如果有的话
            visible_content = None
            if hasattr(self, 'markdown_view') and self.markdown_view:
                visible_content = self.markdown_view.get_current_visible_text()
            
            # 使用强制重新生成标志，以避免合并问题
            message = self.last_user_message
            request_id = self.ai_controller.get_ai_response(message, paper_id, visible_content, force_regenerate=True)
            self.active_request_id = request_id

    def refresh_ui(self):
        """刷新UI界面，重新加载当前对话"""
        # 显示刷新提示
        self.show_refresh_toast()
        
        # 获取当前论文ID
        paper_id = None
        if self.paper_controller and self.paper_controller.current_paper:
            paper_id = self.paper_controller.current_paper.get('id')
        
        if not paper_id or not self.ai_controller:
            return
        
        # 备份当前选择的历史记录索引
        current_history_index = self.history_selector.currentIndex()
        
        # 清空消息区域
        self.clear_messages()
        
        # 如果已经选择了特定的历史记录，重新加载该记录
        if current_history_index > 0:
            date = self.history_selector.itemText(current_history_index)
            self.load_conversation(paper_id, date)
        else:
            # 否则加载最新的对话
            self.load_latest_conversation(paper_id)
        
    def show_refresh_toast(self):
        """显示刷新提示"""
        # 创建一个悬浮提示
        toast = QFrame(self)
        toast.setObjectName("refreshToast")
        toast.setStyleSheet("""
            #refreshToast {
                background-color: rgba(25, 118, 210, 0.9);
                border-radius: 20px;
                color: white;
                padding: 12px 24px;
            }
        """)
        toast_layout = QHBoxLayout(toast)
        toast_label = QLabel("正在刷新界面...")
        toast_label.setStyleSheet("color: white; font-weight: bold; font-size: 14px;")
        toast_layout.addWidget(toast_label)
        
        # 设置位置和大小
        toast.setFixedSize(toast.sizeHint())
        self.scroll_area.setEnabled(False)  # 临时禁用滚动区域防止交互
        
        # 计算居中位置
        x = (self.width() - toast.width()) // 2
        y = (self.height() - toast.height()) // 2
        toast.move(x, y)
        
        # 显示提示
        toast.show()
        
        # 设置定时器自动关闭提示
        QTimer.singleShot(800, lambda: [toast.deleteLater(), self.scroll_area.setEnabled(True)])