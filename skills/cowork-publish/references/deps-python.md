# Python 依赖（pypi.devops.xiaohongshu.com 内网镜像）

> **何时读**：改 requirements.txt / install.sh 的 pip 段时读。**Pod 无公网，必须走内网镜像** `pypi.devops.xiaohongshu.com`，install.sh 在 Linux Pod 上 venv 隔离装依赖（`.venv/bin/python` 绝对路径）。
>
> 本文从官方 `ai-demo-platform-guard-transform-skill/subapp-spec/CLAUDE.md` 拆分而来。

### 10.1 Python：`pypi.devops.xiaohongshu.com`

```bash
# install.sh 里
pip install --no-cache-dir -r requirements.txt \
  -i http://pypi.devops.xiaohongshu.com/simple/ \
  --trusted-host pypi.devops.xiaohongshu.com
```

`requirements.txt` 里能写的包必须在内部 pypi 镜像里有（绝大多数 PyPI 包都同步）。需要 C 扩展（`thriftpy2` / `cffi` 等）平台镜像里也有预装 `gcc` + `python3-dev`，可直接编译。
