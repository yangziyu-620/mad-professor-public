"""
内存监控工具

监控进程和系统的内存使用情况，提供内存泄漏检测和警告功能
"""

import os
import gc
import time
import psutil
import logging
from typing import Dict, List, Optional
from PyQt6.QtCore import QObject, QTimer, pyqtSignal

class MemoryMonitor(QObject):
    """内存监控器类"""
    
    # 信号定义
    memory_warning = pyqtSignal(str, float)  # 内存警告信号 (警告信息, 当前内存GB)
    memory_critical = pyqtSignal(str, float)  # 内存危险信号 (危险信息, 当前内存GB)
    memory_stats_updated = pyqtSignal(dict)  # 内存统计更新信号
    
    def __init__(self, warning_threshold_gb=2.0, critical_threshold_gb=4.0, monitor_interval=30):
        """
        初始化内存监控器
        
        Args:
            warning_threshold_gb: 内存警告阈值（GB）
            critical_threshold_gb: 内存危险阈值（GB）
            monitor_interval: 监控间隔（秒）
        """
        super().__init__()
        
        self.warning_threshold = warning_threshold_gb * 1024 * 1024 * 1024  # 转换为字节
        self.critical_threshold = critical_threshold_gb * 1024 * 1024 * 1024
        self.monitor_interval = monitor_interval
        
        # 获取当前进程
        self.process = psutil.Process(os.getpid())
        
        # 内存历史记录
        self.memory_history: List[Dict] = []
        self.max_history_length = 100  # 最多保留100条历史记录
        
        # 监控状态
        self.is_monitoring = False
        self.timer = QTimer()
        self.timer.timeout.connect(self._check_memory)
        
        # 上次警告时间（避免频繁警告）
        self.last_warning_time = 0
        self.last_critical_time = 0
        self.warning_cooldown = 60  # 警告冷却时间（秒）
        
        # 初始化日志
        logging.basicConfig(level=logging.INFO)
        self.logger = logging.getLogger(__name__)
        
    def start_monitoring(self):
        """开始内存监控"""
        if not self.is_monitoring:
            self.is_monitoring = True
            self.timer.start(self.monitor_interval * 1000)  # 转换为毫秒
            self.logger.info(f"内存监控已启动，间隔: {self.monitor_interval}秒")
            
    def stop_monitoring(self):
        """停止内存监控"""
        if self.is_monitoring:
            self.is_monitoring = False
            self.timer.stop()
            self.logger.info("内存监控已停止")
            
    def _check_memory(self):
        """检查内存使用情况"""
        try:
            stats = self.get_memory_stats()
            current_time = time.time()
            
            # 记录历史数据
            self._record_memory_history(stats)
            
            # 发送统计信息更新信号
            self.memory_stats_updated.emit(stats)
            
            # 检查警告阈值
            process_memory = stats['process']['memory_bytes']
            process_memory_gb = process_memory / (1024**3)
            
            # 检查危险阈值
            if process_memory > self.critical_threshold:
                if current_time - self.last_critical_time > self.warning_cooldown:
                    self.last_critical_time = current_time
                    warning_msg = f"进程内存使用过高: {process_memory_gb:.2f}GB (阈值: {self.critical_threshold/(1024**3):.2f}GB)"
                    self.logger.critical(warning_msg)
                    self.memory_critical.emit(warning_msg, process_memory_gb)
                    
                    # 尝试自动清理内存
                    self._emergency_memory_cleanup()
                    
            # 检查警告阈值
            elif process_memory > self.warning_threshold:
                if current_time - self.last_warning_time > self.warning_cooldown:
                    self.last_warning_time = current_time
                    warning_msg = f"进程内存使用较高: {process_memory_gb:.2f}GB (阈值: {self.warning_threshold/(1024**3):.2f}GB)"
                    self.logger.warning(warning_msg)
                    self.memory_warning.emit(warning_msg, process_memory_gb)
                    
        except Exception as e:
            self.logger.error(f"检查内存时出错: {str(e)}")
            
    def get_memory_stats(self) -> Dict:
        """
        获取详细的内存统计信息
        
        Returns:
            Dict: 包含系统、进程和GPU内存信息的字典
        """
        stats = {
            'timestamp': time.time(),
            'system': self._get_system_memory(),
            'process': self._get_process_memory(),
            'gpu': self._get_gpu_memory()
        }
        
        return stats
        
    def _get_system_memory(self) -> Dict:
        """获取系统内存信息"""
        memory = psutil.virtual_memory()
        
        return {
            'total_bytes': memory.total,
            'available_bytes': memory.available,
            'used_bytes': memory.used,
            'percentage': memory.percent,
            'total_gb': memory.total / (1024**3),
            'available_gb': memory.available / (1024**3),
            'used_gb': memory.used / (1024**3)
        }
        
    def _get_process_memory(self) -> Dict:
        """获取当前进程内存信息"""
        try:
            # 内存信息
            memory_info = self.process.memory_info()
            memory_percent = self.process.memory_percent()
            
            # 尝试获取更详细的内存信息
            try:
                memory_full_info = self.process.memory_full_info()
                uss = getattr(memory_full_info, 'uss', 0)  # Unique Set Size
                pss = getattr(memory_full_info, 'pss', 0)  # Proportional Set Size
            except (AttributeError, psutil.AccessDenied):
                uss = 0
                pss = 0
            
            return {
                'memory_bytes': memory_info.rss,  # Resident Set Size
                'memory_gb': memory_info.rss / (1024**3),
                'memory_percent': memory_percent,
                'virtual_memory_bytes': memory_info.vms,  # Virtual Memory Size
                'virtual_memory_gb': memory_info.vms / (1024**3),
                'unique_memory_bytes': uss,
                'unique_memory_gb': uss / (1024**3) if uss > 0 else 0,
                'proportional_memory_bytes': pss,
                'proportional_memory_gb': pss / (1024**3) if pss > 0 else 0,
                'pid': self.process.pid,
                'num_threads': self.process.num_threads()
            }
        except psutil.NoSuchProcess:
            return {
                'memory_bytes': 0,
                'memory_gb': 0,
                'memory_percent': 0,
                'virtual_memory_bytes': 0,
                'virtual_memory_gb': 0,
                'unique_memory_bytes': 0,
                'unique_memory_gb': 0,
                'proportional_memory_bytes': 0,
                'proportional_memory_gb': 0,
                'pid': 0,
                'num_threads': 0
            }
            
    def _get_gpu_memory(self) -> Dict:
        """获取GPU内存信息"""
        try:
            import torch
            if torch.cuda.is_available():
                device_count = torch.cuda.device_count()
                gpu_info = []
                
                for i in range(device_count):
                    allocated = torch.cuda.memory_allocated(i)
                    reserved = torch.cuda.memory_reserved(i)
                    total = torch.cuda.get_device_properties(i).total_memory
                    
                    gpu_info.append({
                        'device_id': i,
                        'device_name': torch.cuda.get_device_name(i),
                        'allocated_bytes': allocated,
                        'allocated_gb': allocated / (1024**3),
                        'reserved_bytes': reserved,
                        'reserved_gb': reserved / (1024**3),
                        'total_bytes': total,
                        'total_gb': total / (1024**3),
                        'free_bytes': total - reserved,
                        'free_gb': (total - reserved) / (1024**3),
                        'utilization_percent': (reserved / total) * 100 if total > 0 else 0
                    })
                
                return {
                    'available': True,
                    'device_count': device_count,
                    'devices': gpu_info
                }
            else:
                return {'available': False, 'device_count': 0, 'devices': []}
                
        except ImportError:
            return {'available': False, 'device_count': 0, 'devices': []}
        except Exception as e:
            self.logger.warning(f"获取GPU内存信息时出错: {str(e)}")
            return {'available': False, 'device_count': 0, 'devices': [], 'error': str(e)}
            
    def _record_memory_history(self, stats: Dict):
        """记录内存历史数据"""
        self.memory_history.append(stats)
        
        # 限制历史记录长度
        if len(self.memory_history) > self.max_history_length:
            self.memory_history.pop(0)
            
    def _emergency_memory_cleanup(self):
        """紧急内存清理"""
        self.logger.info("执行紧急内存清理...")
        
        try:
            # 强制垃圾回收
            collected = gc.collect()
            self.logger.info(f"垃圾回收清理了 {collected} 个对象")
            
            # 如果有GPU，清理GPU缓存
            try:
                import torch
                if torch.cuda.is_available():
                    torch.cuda.empty_cache()
                    torch.cuda.synchronize()
                    self.logger.info("已清理GPU缓存")
            except ImportError:
                pass
            except Exception as e:
                self.logger.warning(f"清理GPU缓存时出错: {str(e)}")
                
        except Exception as e:
            self.logger.error(f"紧急内存清理时出错: {str(e)}")
            
    def get_memory_report(self) -> str:
        """
        生成内存使用报告
        
        Returns:
            str: 内存使用报告
        """
        stats = self.get_memory_stats()
        
        report = ["=== 内存使用报告 ==="]
        report.append(f"时间: {time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(stats['timestamp']))}")
        report.append("")
        
        # 系统内存
        sys_mem = stats['system']
        report.append("【系统内存】")
        report.append(f"  总内存: {sys_mem['total_gb']:.2f} GB")
        report.append(f"  已使用: {sys_mem['used_gb']:.2f} GB ({sys_mem['percentage']:.1f}%)")
        report.append(f"  可用内存: {sys_mem['available_gb']:.2f} GB")
        report.append("")
        
        # 进程内存
        proc_mem = stats['process']
        report.append("【进程内存】")
        report.append(f"  物理内存: {proc_mem['memory_gb']:.2f} GB")
        report.append(f"  虚拟内存: {proc_mem['virtual_memory_gb']:.2f} GB")
        report.append(f"  内存占用率: {proc_mem['memory_percent']:.2f}%")
        report.append(f"  进程ID: {proc_mem['pid']}")
        report.append(f"  线程数: {proc_mem['num_threads']}")
        
        if proc_mem['unique_memory_gb'] > 0:
            report.append(f"  独占内存: {proc_mem['unique_memory_gb']:.2f} GB")
        if proc_mem['proportional_memory_gb'] > 0:
            report.append(f"  比例内存: {proc_mem['proportional_memory_gb']:.2f} GB")
        report.append("")
        
        # GPU内存
        gpu_mem = stats['gpu']
        if gpu_mem['available']:
            report.append("【GPU内存】")
            for device in gpu_mem['devices']:
                report.append(f"  设备 {device['device_id']} ({device['device_name']}):")
                report.append(f"    总显存: {device['total_gb']:.2f} GB")
                report.append(f"    已分配: {device['allocated_gb']:.2f} GB")
                report.append(f"    已保留: {device['reserved_gb']:.2f} GB")
                report.append(f"    可用显存: {device['free_gb']:.2f} GB")
                report.append(f"    使用率: {device['utilization_percent']:.1f}%")
        else:
            report.append("【GPU内存】")
            report.append("  GPU不可用或未安装PyTorch")
        
        report.append("")
        
        # 内存趋势（如果有历史数据）
        if len(self.memory_history) > 1:
            report.append("【内存趋势】")
            first = self.memory_history[0]
            current = self.memory_history[-1]
            
            mem_change = current['process']['memory_gb'] - first['process']['memory_gb']
            time_span = (current['timestamp'] - first['timestamp']) / 60  # 分钟
            
            report.append(f"  历史记录: {len(self.memory_history)} 条")
            report.append(f"  时间跨度: {time_span:.1f} 分钟")
            report.append(f"  内存变化: {mem_change:+.2f} GB")
            
            if time_span > 0:
                mem_rate = mem_change / time_span * 60  # GB/小时
                report.append(f"  变化速率: {mem_rate:+.2f} GB/小时")
        
        return "\n".join(report)
        
    def clear_history(self):
        """清空内存历史记录"""
        self.memory_history.clear()
        self.logger.info("内存历史记录已清空")
        
    def set_thresholds(self, warning_gb: float, critical_gb: float):
        """
        设置内存阈值
        
        Args:
            warning_gb: 警告阈值（GB）
            critical_gb: 危险阈值（GB）
        """
        self.warning_threshold = warning_gb * 1024 * 1024 * 1024
        self.critical_threshold = critical_gb * 1024 * 1024 * 1024
        self.logger.info(f"内存阈值已更新: 警告={warning_gb:.2f}GB, 危险={critical_gb:.2f}GB")
        
    def get_memory_summary(self) -> Dict:
        """
        获取内存使用摘要
        
        Returns:
            Dict: 内存摘要信息
        """
        stats = self.get_memory_stats()
        
        return {
            'process_memory_gb': stats['process']['memory_gb'],
            'system_memory_usage_percent': stats['system']['percentage'],
            'system_available_gb': stats['system']['available_gb'],
            'gpu_available': stats['gpu']['available'],
            'gpu_total_memory_gb': sum(d['total_gb'] for d in stats['gpu'].get('devices', [])),
            'gpu_used_memory_gb': sum(d['reserved_gb'] for d in stats['gpu'].get('devices', [])),
            'warning_threshold_gb': self.warning_threshold / (1024**3),
            'critical_threshold_gb': self.critical_threshold / (1024**3),
            'is_warning': stats['process']['memory_bytes'] > self.warning_threshold,
            'is_critical': stats['process']['memory_bytes'] > self.critical_threshold
        }


# 全局内存监控器实例
_global_monitor: Optional[MemoryMonitor] = None

def get_global_monitor() -> MemoryMonitor:
    """获取全局内存监控器实例"""
    global _global_monitor
    if _global_monitor is None:
        _global_monitor = MemoryMonitor()
    return _global_monitor

def start_global_monitoring():
    """启动全局内存监控"""
    monitor = get_global_monitor()
    monitor.start_monitoring()
    return monitor

def stop_global_monitoring():
    """停止全局内存监控"""
    global _global_monitor
    if _global_monitor is not None:
        _global_monitor.stop_monitoring()

def get_quick_memory_info() -> str:
    """快速获取内存信息字符串"""
    monitor = get_global_monitor()
    stats = monitor.get_memory_stats()
    
    proc_mem = stats['process']['memory_gb']
    sys_mem = stats['system']['percentage']
    
    gpu_info = ""
    if stats['gpu']['available'] and stats['gpu']['devices']:
        gpu_mem = stats['gpu']['devices'][0]  # 只显示第一个GPU
        gpu_info = f", GPU: {gpu_mem['reserved_gb']:.1f}/{gpu_mem['total_gb']:.1f}GB"
    
    return f"内存: 进程 {proc_mem:.1f}GB, 系统 {sys_mem:.1f}%{gpu_info}"


if __name__ == "__main__":
    # 测试代码
    monitor = MemoryMonitor(warning_threshold_gb=1.0, critical_threshold_gb=2.0)
    print(monitor.get_memory_report()) 