# Python 依赖（装到 Pod 全局 /opt/venv，镜像由 Pod env 注入）

> **何时读**：改 requirements.txt / install.sh 的 pip 段时读。**依赖装到 Pod 镜像预置的全局 venv `/opt/venv`（已在 PATH 上）**，工程内**禁止** `python3 -m venv .venv`（`verify_no_venv_creation.sh` 会卡）。install.sh 里**不要**写 `-i` / `--trusted-host` 镜像参数（`verify_install_no_internet.sh` 会卡），内网镜像由 Pod env `PIP_INDEX_URL` / `PIP_TRUSTED_HOST` 注入。
>
> 本文从官方 `ai-demo-platform-guard-transform-skill/subapp-spec/CLAUDE.md` 拆分而来。

### 10.1 Python：依赖镜像由 Pod env 注入，**不要**写进 install.sh

```bash
# install.sh 里只能这么写（verify_install_no_internet.sh 强制）
python3 -m pip install --no-cache-dir -r requirements.txt
```

- ❌ **禁止**在 install.sh 的 `pip install` 行加 `-i ...` / `--index-url ...` / `--extra-index-url ...` / `--trusted-host ...`——`verify_install_no_internet.sh` 直接 FAIL
- ✅ 如需走内部镜像 `pypi.devops.xiaohongshu.com`，由 **Pod 启动环境** 注入 `PIP_INDEX_URL` / `PIP_TRUSTED_HOST`，pip 自动生效，交付物里完全看不到镜像 URL
- ✅ `python3` 走 PATH 解析到 Pod 镜像预置的 `/opt/venv/bin/python3`，把包装进全局 `/opt/venv` 的 site-packages；工程内**不再建** `.venv`（详见 `verify_no_venv_creation.sh`）

`requirements.txt` 里写的包绝大多数在内部 pypi 镜像里都已同步。需要 C 扩展（`thriftpy2` / `cffi` 等）平台镜像里也有预装 `gcc` + `python3-dev`，可直接编译。
