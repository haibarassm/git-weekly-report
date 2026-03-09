"""测试运行器"""
import unittest
import sys
from pathlib import Path

# 添加项目根目录到路径
sys.path.insert(0, str(Path(__file__).parent.parent))

# 导入测试模块
from tests import test_git_utils, test_llm_client, test_config


def run_tests():
    """运行所有测试"""
    # 创建测试套件
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()

    # 添加测试模块
    suite.addTests(loader.loadTestsFromModule(test_git_utils))
    suite.addTests(loader.loadTestsFromModule(test_llm_client))
    suite.addTests(loader.loadTestsFromModule(test_config))

    # 运行测试
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)

    # 返回测试结果
    return 0 if result.wasSuccessful() else 1


if __name__ == '__main__':
    sys.exit(run_tests())
