# -*- coding: utf-8 -*-
"""pytest conftest：把 agent/ 加入 sys.path（自定义组件按 agent 为根导入）。"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
