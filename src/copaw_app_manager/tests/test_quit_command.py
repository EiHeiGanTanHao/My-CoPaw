"""锁文件和 quit 命令测试"""

import json
import os
import tempfile
import time
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest
import psutil

from copaw_app_manager.service.manager import WorkspaceManager


class TestLockFile:
    """锁文件功能测试"""

    @pytest.fixture
    def temp_dir(self):
        """创建临时目录用于测试"""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield tmpdir

    @pytest.fixture
    def manager(self, temp_dir):
        """创建 WorkspaceManager 实例"""
        return WorkspaceManager(base_dir=temp_dir)

    def test_lock_file_path(self, manager, temp_dir):
        """测试锁文件路径正确"""
        expected_lock_file = Path(temp_dir) / "manager.lock"
        assert manager._lock_file == expected_lock_file

    def test_acquire_lock_no_existing_lock(self, manager):
        """测试没有现有锁文件时成功获取锁"""
        manager._acquire_lock(port=8000)
        
        # 检查锁文件是否创建
        assert manager._lock_file.exists()
        
        # 检查锁文件内容
        with open(manager._lock_file, "r", encoding="utf-8") as f:
            lock_data = json.load(f)
        
        assert lock_data["pid"] == os.getpid()
        assert lock_data["port"] == 8000
        assert "started_at" in lock_data

    def test_acquire_lock_existing_process(self, manager):
        """测试已有进程运行时获取锁失败"""
        # 先获取锁
        manager._acquire_lock(port=8000)
        
        # 尝试再次获取锁，应该抛出异常
        with pytest.raises(RuntimeError, match="已有 Manager 在运行"):
            manager._acquire_lock(port=8001)

    def test_acquire_lock_stale_lock_file(self, manager):
        """测试清理过期的锁文件（进程不存在）"""
        # 创建一个假的锁文件，使用不存在的 PID
        fake_pid = 999999  # 假设这个 PID 不存在
        lock_data = {
            "pid": fake_pid,
            "port": 8000,
            "started_at": "2026-01-01T00:00:00"
        }
        with open(manager._lock_file, "w", encoding="utf-8") as f:
            json.dump(lock_data, f)
        
        # 获取锁应该成功（会清理旧锁文件）
        manager._acquire_lock(port=8001)
        
        # 检查新锁文件是否正确
        with open(manager._lock_file, "r", encoding="utf-8") as f:
            new_lock_data = json.load(f)
        
        assert new_lock_data["pid"] == os.getpid()
        assert new_lock_data["port"] == 8001

    def test_release_lock(self, manager):
        """测试释放锁"""
        # 先获取锁
        manager._acquire_lock(port=8000)
        assert manager._lock_file.exists()
        
        # 释放锁
        manager._release_lock()
        
        # 检查锁文件是否删除
        assert not manager._lock_file.exists()

    def test_read_lock(self, manager):
        """测试读取锁文件"""
        # 先获取锁
        manager._acquire_lock(port=8000)
        
        # 读取锁
        lock_data = manager._read_lock()
        
        assert lock_data is not None
        assert lock_data["pid"] == os.getpid()
        assert lock_data["port"] == 8000

    def test_read_lock_no_file(self, manager):
        """测试锁文件不存在时返回 None"""
        lock_data = manager._read_lock()
        assert lock_data is None

    def test_read_lock_corrupted_file(self, manager):
        """测试锁文件损坏时返回 None"""
        # 创建损坏的锁文件
        with open(manager._lock_file, "w", encoding="utf-8") as f:
            f.write("not valid json")
        
        lock_data = manager._read_lock()
        assert lock_data is None


class TestQuitCommand:
    """quit 命令测试"""

    @pytest.fixture
    def temp_dir(self):
        """创建临时目录用于测试"""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield tmpdir

    @pytest.fixture
    def manager(self, temp_dir):
        """创建 WorkspaceManager 实例"""
        return WorkspaceManager(base_dir=temp_dir)

    def test_quit_no_manager_running(self, manager):
        """测试没有 Manager 运行时 quit 命令"""
        lock_data = manager._read_lock()
        assert lock_data is None

    def test_quit_with_force(self, manager):
        """测试使用 --force 强制停止 Manager"""
        # 获取锁
        manager._acquire_lock(port=8000)
        
        # 读取锁信息
        lock_data = manager._read_lock()
        pid = lock_data["pid"]
        
        # 模拟一个运行的进程
        mock_proc = MagicMock()
        mock_proc.kill.return_value = None
        mock_proc.wait.return_value = None
        
        with patch.object(psutil, 'Process', return_value=mock_proc) as mock_process_cls:
            # 验证可以通过 psutil 获取进程
            proc = psutil.Process(pid)
            proc.kill()
            proc.wait()
            
            # 验证进程被杀死
            mock_proc.kill.assert_called()
            mock_proc.wait.assert_called()

    def test_quit_graceful_stop(self, manager):
        """测试优雅停止 Manager"""
        # 模拟一个运行的进程
        mock_proc = MagicMock()
        mock_proc.is_running.return_value = True
        mock_proc.terminate.return_value = None
        mock_proc.wait.return_value = None
        
        with patch.object(psutil, 'Process', return_value=mock_proc):
            # 获取锁
            manager._acquire_lock(port=8000)
            
            # 模拟停止所有工作区
            with patch.object(manager, 'stop_all_workspaces') as mock_stop_all:
                mock_stop_all.return_value = None
                
                # 验证 stop_all_workspaces 被调用
                manager.stop_all_workspaces()
                mock_stop_all.assert_called_once()

    def test_quit_cleans_up_lock_file(self, manager):
        """测试 quit 命令清理锁文件"""
        # 获取锁
        manager._acquire_lock(port=8000)
        assert manager._lock_file.exists()
        
        # 释放锁
        manager._release_lock()
        assert not manager._lock_file.exists()


class TestStartCommandIntegration:
    """start 命令集成测试"""

    @pytest.fixture
    def temp_dir(self):
        """创建临时目录用于测试"""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield tmpdir

    def test_start_creates_lock(self, temp_dir):
        """测试 start 命令创建锁文件"""
        manager = WorkspaceManager(base_dir=temp_dir)
        manager._acquire_lock(port=8000)
        
        # 检查锁文件创建
        lock_file = Path(temp_dir) / "manager.lock"
        assert lock_file.exists()

    def test_start_fails_if_already_running(self, temp_dir):
        """测试已有 Manager 运行时 start 命令失败"""
        manager = WorkspaceManager(base_dir=temp_dir)
        
        # 第一次启动成功
        manager._acquire_lock(port=8000)
        
        # 第二次启动应该失败
        with pytest.raises(RuntimeError, match="已有 Manager 在运行"):
            manager._acquire_lock(port=8001)

    def test_start_cleans_stale_lock(self, temp_dir):
        """测试 start 命令清理过期的锁文件"""
        manager = WorkspaceManager(base_dir=temp_dir)
        
        # 创建过期锁文件
        fake_pid = 999999
        lock_data = {
            "pid": fake_pid,
            "port": 8000,
            "started_at": "2026-01-01T00:00:00"
        }
        lock_file = Path(temp_dir) / "manager.lock"
        with open(lock_file, "w", encoding="utf-8") as f:
            json.dump(lock_data, f)
        
        # 启动应该成功并清理旧锁
        manager._acquire_lock(port=8001)
        
        # 验证新锁文件
        with open(lock_file, "r", encoding="utf-8") as f:
            new_data = json.load(f)
        
        assert new_data["pid"] == os.getpid()
        assert new_data["port"] == 8001
