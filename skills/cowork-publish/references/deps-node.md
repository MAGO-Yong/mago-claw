# Node 依赖（.npmrc 双路 registry）

> **何时读**：改 package.json / install.sh 的 npm 段时读。项目根 `.npmrc` 必须配双路 registry（`@xhs:registry=` 内网 / `registry=` npmmirror 公网镜像）。scaffold 已给好。
>
> 本文从官方 `ai-demo-platform-guard-transform-skill/subapp-spec/CLAUDE.md` 拆分而来。

### 10.2 Node：双路 `.npmrc`

```ini
# .npmrc（commit 进 zip 顶层）
@xhs:registry=http://npm.devops.xiaohongshu.com:7001
registry=http://registry.npmmirror.com
```

**注意**：等号后不能加引号（verifier 正则匹配会失败）。

```bash
# install.sh 里
npm ci --omit=dev      # 必须 ci 不是 install，靠 package-lock.json 保证可重现
```

`@xhs/*` 包走内部 npm；其它包走 npmmirror（公网镜像但平台 Pod 能访问）。
