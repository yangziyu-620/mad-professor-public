from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QPushButton, 
                           QListWidget, QListWidgetItem, QLabel, QFrame, QTreeWidget, QTreeWidgetItem,
                           QMenu, QInputDialog, QMessageBox)
from PyQt6.QtCore import Qt, QPropertyAnimation, QEasingCurve, pyqtSignal
from PyQt6.QtGui import QFont, QBrush, QColor

from ui.upload_widget import UploadWidget  # 导入上传文件窗口类

class SidebarWidget(QWidget):
    """可折叠侧边栏"""
    # 定义信号
    paper_selected = pyqtSignal(str)  # 论文选择信号，传递论文ID
    upload_file = pyqtSignal(str)  # 上传文件信号，传递文件路径（转发）
    pause_processing = pyqtSignal()  # 暂停处理信号（转发）
    resume_processing = pyqtSignal()  # 继续处理信号（转发）
    update_paper_field = pyqtSignal(str, str)  # 更新论文领域信号，传递论文ID和新领域
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.collapsed_width = 50
        self.expanded_width = 250  # 减小侧边栏宽度
        self.is_expanded = True
        self.setMaximumWidth(self.expanded_width)  # 设置最大宽度
        self.display_mode = "list"  # 添加显示模式：list或tree
        
        self.init_ui()
        
    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)  # 减少间距
        
        # 标题和折叠按钮
        header_frame = QFrame()
        header_frame.setObjectName("sidebarHeader")
        header_frame.setStyleSheet("""
            #sidebarHeader {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, 
                               stop:0 #1a237e, stop:1 #0d47a1);
                color: white;
                border-bottom: 1px solid #0a1855;
            }
        """)
        header_frame.setFixedHeight(40)  # 固定高度与其他标题栏一致
        
        header_layout = QHBoxLayout(header_frame)
        header_layout.setContentsMargins(10, 0, 10, 0)
        
        title_font = QFont("Source Han Sans SC", 11, QFont.Weight.Bold)
        self.title_label = QLabel("论文列表")
        self.title_label.setFont(title_font)
        self.title_label.setStyleSheet("color: white; font-weight: bold;")
        
        # 添加排序下拉框
        self.sort_button = QPushButton("按标题排序 ▼")
        self.sort_button.setStyleSheet("""
            QPushButton {
                border: none;
                color: white;
                background-color: transparent;
                font-size: 10px;
            }
            QPushButton:hover {
                background-color: rgba(255, 255, 255, 0.2);
                border-radius: 4px;
            }
        """)
        self.sort_button.setMaximumWidth(100)
        self.sort_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.sort_button.clicked.connect(self.toggle_sort_mode)
        self.sort_by_title = True  # 默认按标题排序
        
        # 添加视图切换按钮
        self.view_button = QPushButton("分类视图")
        self.view_button.setStyleSheet("""
            QPushButton {
                border: none;
                color: white;
                background-color: transparent;
                font-size: 10px;
            }
            QPushButton:hover {
                background-color: rgba(255, 255, 255, 0.2);
                border-radius: 4px;
            }
        """)
        self.view_button.setMaximumWidth(80)
        self.view_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.view_button.clicked.connect(self.toggle_view_mode)
        
        # 固定位置的折叠按钮容器
        button_container = QWidget()
        button_container.setFixedWidth(30)
        button_layout = QVBoxLayout(button_container)
        button_layout.setContentsMargins(0, 0, 0, 0)
        button_layout.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        
        self.toggle_button = QPushButton("<<")
        self.toggle_button.setMaximumWidth(30)
        self.toggle_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.toggle_button.setStyleSheet("""
            QPushButton {
                border: none;
                color: white;
                font-weight: bold;
                background-color: transparent;
            }
            QPushButton:hover {
                background-color: rgba(255, 255, 255, 0.2);
                border-radius: 4px;
            }
        """)
        self.toggle_button.clicked.connect(self.toggle_sidebar)
        
        button_layout.addWidget(self.toggle_button)
        
        # 排序按钮和折叠按钮布局
        tool_layout = QHBoxLayout()
        tool_layout.setContentsMargins(0, 0, 0, 0)
        tool_layout.addWidget(self.sort_button)
        tool_layout.addWidget(self.view_button)
        tool_layout.addStretch()
        
        header_layout.addWidget(self.title_label)
        header_layout.addLayout(tool_layout)
        header_layout.addWidget(button_container, 0, Qt.AlignmentFlag.AlignRight)
        
        # 论文列表容器
        list_container = QFrame()
        list_container.setObjectName("listContainer")
        list_container.setStyleSheet("""
            #listContainer {
                background-color: #f0f4f8;
            }
        """)
        list_layout = QVBoxLayout(list_container)
        list_layout.setContentsMargins(0, 0, 0, 0)
        
        # 论文列表
        self.paper_list = QListWidget()
        self.paper_list.setObjectName("paperList")
        self.paper_list.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.paper_list.setTextElideMode(Qt.TextElideMode.ElideRight)
        self.paper_list.setStyleSheet("""
            #paperList {
                background-color: #f0f4f8;
                border: none;
                outline: none;
            }
            #paperList QScrollBar:vertical {
                width: 0px;
                background: transparent;
            }
            #paperList QScrollBar:horizontal {
                height: 0px;
                background: transparent;
            }
            #paperList QScrollBar::handle:vertical,
            #paperList QScrollBar::add-line:vertical,
            #paperList QScrollBar::sub-line:vertical,
            #paperList QScrollBar::add-page:vertical,
            #paperList QScrollBar::sub-page:vertical {
                background: transparent;
                border: none;
            }
            QListWidget::item {
                padding: 12px;
                border-bottom: 1px solid #dbe2ef;
                color: #2c3e50;
                width: 100%;
            }
            QListWidget::item:selected {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, 
                               stop:0 #1a237e, stop:1 #283593);
                color: white;
                border-radius: 6px;
                margin: 2px 5px;
            }
            QListWidget::item:hover:!selected {
                background-color: #e3f2fd;
                border-radius: 6px;
                margin: 2px 5px;
            }
        """)
        
        # 论文树形视图（分类视图）
        self.paper_tree = QTreeWidget()
        self.paper_tree.setObjectName("paperTree")
        self.paper_tree.setHeaderHidden(True)
        self.paper_tree.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.paper_tree.setTextElideMode(Qt.TextElideMode.ElideRight)
        self.paper_tree.setStyleSheet("""
            #paperTree {
                background-color: #f0f4f8;
                border: none;
                outline: none;
            }
            #paperTree QScrollBar:vertical {
                width: 0px;
                background: transparent;
            }
            #paperTree QScrollBar:horizontal {
                height: 0px;
                background: transparent;
            }
            #paperTree QScrollBar::handle:vertical,
            #paperTree QScrollBar::add-line:vertical,
            #paperTree QScrollBar::sub-line:vertical,
            #paperTree QScrollBar::add-page:vertical,
            #paperTree QScrollBar::sub-page:vertical {
                background: transparent;
                border: none;
            }
            QTreeWidget::item {
                padding: 8px;
                border-bottom: 1px solid #dbe2ef;
                color: #2c3e50;
                width: 100%;
            }
            QTreeWidget::item:selected {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, 
                               stop:0 #1a237e, stop:1 #283593);
                color: white;
                border-radius: 6px;
                margin: 2px 5px;
            }
            QTreeWidget::item:hover:!selected {
                background-color: #e3f2fd;
                border-radius: 6px;
                margin: 2px 5px;
            }
            QTreeWidget::branch {
                background-color: transparent;
            }
        """)
        
        # 初始时，默认显示列表视图，隐藏树形视图
        self.paper_tree.setVisible(False)
        
        # 连接论文列表点击信号
        self.paper_list.itemClicked.connect(self.on_paper_item_clicked)
        self.paper_tree.itemClicked.connect(self.on_tree_item_clicked)
        
        # 设置右键菜单
        self.paper_list.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.paper_list.customContextMenuRequested.connect(self.show_list_context_menu)
        
        self.paper_tree.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.paper_tree.customContextMenuRequested.connect(self.show_tree_context_menu)
        
        list_layout.addWidget(self.paper_list)
        list_layout.addWidget(self.paper_tree)
        
        # 创建上传文件窗口
        self.upload_widget = UploadWidget()
        
        # 连接上传文件窗口的信号
        self.upload_widget.upload_file.connect(self.on_upload_file)
        self.upload_widget.pause_processing.connect(self.on_pause_processing)
        self.upload_widget.resume_processing.connect(self.on_resume_processing)
        
        # 添加到布局
        layout.addWidget(header_frame)
        layout.addWidget(list_container)
        layout.addWidget(self.upload_widget)
        
        self.setLayout(layout)
    
    def toggle_sidebar(self):
        """切换侧边栏展开/折叠状态"""
        self.is_expanded = not self.is_expanded
        
        target_width = self.expanded_width if self.is_expanded else self.collapsed_width
        
        # 创建动画
        self.animation = QPropertyAnimation(self, b"maximumWidth")
        self.animation.setDuration(300)
        self.animation.setStartValue(self.width())
        self.animation.setEndValue(target_width)
        self.animation.setEasingCurve(QEasingCurve.Type.InOutQuart)
        
        # 同时设置最小宽度
        self.min_anim = QPropertyAnimation(self, b"minimumWidth")
        self.min_anim.setDuration(300)
        self.min_anim.setStartValue(self.width())
        self.min_anim.setEndValue(target_width)
        self.min_anim.setEasingCurve(QEasingCurve.Type.InOutQuart)
        
        # 更新按钮文本
        if self.is_expanded:
            button_text = "<<"
        else:
            button_text = ">>"
        
        self.toggle_button.setText(button_text)
        
        # 显示/隐藏其他内容
        self.title_label.setVisible(self.is_expanded)
        self.paper_list.setVisible(self.is_expanded and self.display_mode == "list")
        self.paper_tree.setVisible(self.is_expanded and self.display_mode == "tree")
        self.upload_widget.setVisible(self.is_expanded)
        self.sort_button.setVisible(self.is_expanded)
        self.view_button.setVisible(self.is_expanded)
        
        # 如果正在折叠，且详情面板可见，先隐藏详情面板
        if not self.is_expanded:
            self.upload_widget.close_details_if_open()
        
        # 启动动画
        self.animation.start()
        self.min_anim.start()
    
    def toggle_sort_mode(self):
        """切换排序模式"""
        self.sort_by_title = not self.sort_by_title
        self.sort_button.setText("按标题排序 ▼" if self.sort_by_title else "按年份排序 ▼")
        # 重新加载论文列表
        if hasattr(self, 'last_papers_index'):
            self.load_papers(self.last_papers_index)
    
    def toggle_view_mode(self):
        """切换视图模式：列表视图和分类树形视图"""
        if self.display_mode == "list":
            self.display_mode = "tree"
            self.view_button.setText("列表视图")
            self.paper_list.setVisible(False)
            self.paper_tree.setVisible(True)
        else:
            self.display_mode = "list"
            self.view_button.setText("分类视图")
            self.paper_list.setVisible(True)
            self.paper_tree.setVisible(False)
        
        # 重新加载论文列表，应用当前视图模式
        if hasattr(self, 'last_papers_index'):
            self.load_papers(self.last_papers_index)
            
    def load_papers(self, papers_index):
        """加载论文索引到列表"""
        # 保存最后一次加载的论文列表，用于切换排序模式时重新加载
        self.last_papers_index = papers_index
        
        # 根据排序模式对论文列表排序
        if self.sort_by_title:
            # 按标题排序
            sorted_papers = sorted(
                papers_index,
                key=lambda p: (p.get('translated_title', '') or p.get('title', '') or p.get('id', ''))
            )
        else:
            # 按年份排序（从新到旧）
            current_year = 2025  # 设置一个较大的默认值作为无年份时的排序依据
            sorted_papers = sorted(
                papers_index,
                key=lambda p: p.get('year', self._extract_year(p.get('id', ''))),
                reverse=True
            )
        
        # 根据当前视图模式加载论文
        if self.display_mode == "list":
            self._load_list_view(sorted_papers)
        else:
            self._load_tree_view(sorted_papers)
    
    def _load_list_view(self, sorted_papers):
        """加载列表视图"""
        self.paper_list.clear()
        for paper in sorted_papers:
            item = QListWidgetItem()
            title = paper.get('translated_title', '') or paper.get('title', '') or paper.get('id', '')
            
            if not self.sort_by_title and paper.get('year'):
                title = f"[{paper.get('year')}] {title}"
            
            item.setText(title)
            item.setData(Qt.ItemDataRole.UserRole, paper)
            self.paper_list.addItem(item)
    
    def _load_tree_view(self, sorted_papers):
        """加载树形视图（按领域分类）"""
        self.paper_tree.clear()
        
        # 按领域对论文进行分组
        field_groups = {}
        for paper in sorted_papers:
            field = paper.get('field', '未分类')
            if field not in field_groups:
                field_groups[field] = []
            field_groups[field].append(paper)
        
        # 为每个领域创建一个树节点
        for field, papers in field_groups.items():
            field_item = QTreeWidgetItem(self.paper_tree)
            field_item.setText(0, field)
            field_item.setFlags(field_item.flags() | Qt.ItemFlag.ItemIsAutoTristate)
            
            # 设置领域标题的样式 - 加粗显示
            font = field_item.font(0)
            font.setBold(True)
            font.setPointSize(10)
            field_item.setFont(0, font)
            
            # 设置背景色
            field_item.setBackground(0, QBrush(QColor("#E3F2FD")))
            
            field_item.setExpanded(True)  # 默认展开所有分类
            
            # 添加该领域的所有论文
            for paper in papers:
                paper_item = QTreeWidgetItem(field_item)
                title = paper.get('translated_title', '') or paper.get('title', '') or paper.get('id', '')
                
                if not self.sort_by_title and paper.get('year'):
                    title = f"[{paper.get('year')}] {title}"
                
                paper_item.setText(0, title)
                paper_item.setData(0, Qt.ItemDataRole.UserRole, paper)
                
                # 为论文项添加左边距
                paper_item.setTextAlignment(0, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
    
    def _extract_year(self, paper_id):
        """从论文ID中提取年份，如果没有则返回默认值"""
        import re
        match = re.search(r'20\d{2}', paper_id)
        if match:
            return int(match.group(0))
        return 0
    
    def on_paper_item_clicked(self, item):
        """处理论文项点击事件，发出paper_selected信号"""
        paper = item.data(Qt.ItemDataRole.UserRole)
        if paper:
            self.paper_selected.emit(paper.get('id'))
            
    def on_tree_item_clicked(self, item, column):
        """处理树形视图项点击事件"""
        # 检查是否是论文项（而不是分类项）
        if item.parent() is not None:
            paper = item.data(0, Qt.ItemDataRole.UserRole)
            if paper:
                self.paper_selected.emit(paper.get('id'))
    
    def on_upload_file(self, file_path):
        """转发上传文件信号"""
        self.upload_file.emit(file_path)
    
    def on_pause_processing(self):
        """转发暂停处理信号"""
        self.pause_processing.emit()
    
    def on_resume_processing(self):
        """转发继续处理信号"""
        self.resume_processing.emit()
    
    def update_upload_status(self, file_name, stage, progress, pending_count):
        """更新上传状态"""
        self.upload_widget.update_upload_status(file_name, stage, progress, pending_count)
    
    def show_list_context_menu(self, position):
        """显示论文列表的右键菜单"""
        item = self.paper_list.itemAt(position)
        if item is None:
            return
            
        paper = item.data(Qt.ItemDataRole.UserRole)
        if not paper:
            return
            
        # 创建右键菜单
        context_menu = QMenu(self)
        
        # 添加编辑领域选项
        edit_field_action = context_menu.addAction("编辑领域分类")
        
        # 显示菜单并获取选择的操作
        action = context_menu.exec(self.paper_list.mapToGlobal(position))
        
        # 处理选择的操作
        if action == edit_field_action:
            self.edit_paper_field(paper)
    
    def show_tree_context_menu(self, position):
        """显示论文树形视图的右键菜单"""
        item = self.paper_tree.itemAt(position)
        if item is None:
            return
            
        # 只有论文项（不是分类项）才显示右键菜单
        if item.parent() is None:
            return
            
        paper = item.data(0, Qt.ItemDataRole.UserRole)
        if not paper:
            return
            
        # 创建右键菜单
        context_menu = QMenu(self)
        
        # 添加编辑领域选项
        edit_field_action = context_menu.addAction("编辑领域分类")
        
        # 显示菜单并获取选择的操作
        action = context_menu.exec(self.paper_tree.mapToGlobal(position))
        
        # 处理选择的操作
        if action == edit_field_action:
            self.edit_paper_field(paper)
    
    def edit_paper_field(self, paper):
        """编辑论文领域分类"""
        current_field = paper.get('field', '未分类')
        paper_id = paper.get('id', '')
        
        # 弹出输入对话框
        new_field, ok = QInputDialog.getText(
            self, 
            "编辑论文领域", 
            f"请输入论文「{paper.get('translated_title', '')}」的新领域分类：",
            text=current_field
        )
        
        # 用户点击确定且输入不为空时，发出更新信号
        if ok and new_field and new_field.strip() != '':
            self.update_paper_field.emit(paper_id, new_field.strip())
        elif ok and (not new_field or new_field.strip() == ''):
            QMessageBox.warning(self, "警告", "领域分类不能为空！", QMessageBox.StandardButton.Ok)