# 桌面整理与 GitHub 上传指引

只上传整理后的 `multilingual-wsd` 文件夹。原脚本与论文历史稿留在原位置，不应把整个上级工作目录直接上传。以下为首次发布与后续自行维护的操作指引；已有远程仓库时，可直接克隆后维护，无需再次创建。

## 移动到桌面

在 Finder 中找到本次交付的 `multilingual-wsd` 文件夹，先复制到桌面并核对文件，再决定是否删除原工作副本。需要直接移动时可剪切粘贴，桌面若已有同名文件夹，请先改名以免覆盖。

也可以在本文件夹的上级目录执行：

```bash
# 先确认桌面不存在同名目录，再执行移动
mv -n multilingual-wsd "$HOME/Desktop/"
cd "$HOME/Desktop/multilingual-wsd"
```

如果继续在原位置管理，则直接进入原文件夹，无须移动。以下命令均从仓库根目录执行。需要本机已有可用的 Git；若提示缺少命令行开发工具，请按系统提示安装后再继续。

## 发布前检查

阅读 [security_review.md](security_review.md)、[changes.md](changes.md) 与 [README](../README.md)。按作者实际授权核实 MIT 版权行、论文引用和导师要求的定稿内容。当前仓库有意声明接口和资源缺失；不要把它标注为一键可运行、复现成功或已验证全部论文结论。

本次选择纯源代码工具的文档定位，仅说明不附带历史实验结果文件。之后如补充新实验，应单独说明其真实输入、环境与运行时间。

## 初始化并审核暂存文件

```bash
git init
git branch -M main
git status --short --ignored
```

配置实际署名信息时可使用 GitHub 提供的隐私邮箱。提交作者名和邮箱会写入 Git 历史，不能依赖 `.gitignore` 隐藏它们。

```bash
git config user.name "YOUR_PUBLIC_AUTHOR_NAME"
git config user.email "YOUR_VERIFIED_OR_GITHUB_NOREPLY_EMAIL"
```

将上述占位值替换为自己的真实公开署名设置。首次提交采用明确路径：

```bash
git add README.md requirements.txt .gitignore LICENSE experiment_runner1_v2.py evaluation.py preflight.py docs tests data/README.md support_data/README.md resources/README.md FILE_MANIFEST.md
git diff --cached --stat
git diff --cached
```

逐项核对没有数据 CSV、缓存 JSON、密钥、模型接口私有配置、个人路径、论文历史稿或生成输出。`.gitignore` 只影响未跟踪文件，无法删除已经提交的敏感内容；如果密钥曾进入历史，应先撤销并更换密钥，再处理历史。

```bash
python -m unittest discover -s tests -v
git commit -m "Prepare multilingual WSD source release"
```

单元测试不调用模型；其临时结构用例不是科研数据或实验结果。缺失真实接口与资源时，`--check-only` 返回非零属于预期，不能伪称完整验证通过。

## 在 GitHub 创建并推送

1. 登录 GitHub，选择创建新仓库，名称可用 `multilingual-wsd`。
2. 简介可写：“多语言词义消歧的语义检索与自适应提示实验源代码工具；不附带历史实验结果文件。”
3. 选择实际需要的可见性。首次审核可先选 Private；公开前完成本页检查。
4. 创建空仓库，不自动添加 README、许可证或 gitignore，以免与本地文件冲突。
5. 将下面地址中的 `YOUR_USERNAME` 替换为真实账户名，按 GitHub 页面提供的认证方式推送。令牌只用于凭证管理，不写入远程 URL 或文件。

```bash
git remote add origin https://github.com/YOUR_USERNAME/multilingual-wsd.git
git push -u origin main
```

推送后在网页核对 README、许可证和文件列表；确认 `data/`、`support_data/`、`resources/` 只有说明文件，`outputs/` 与本地接口未被上传。根据实际仓库地址和经核实的论文信息补充引用章节。知识库存档只需单独导入 [knowledge_base.md](knowledge_base.md)。

## 上传前简短自检

- [ ] 执行代码与配置只含保留模型，导师要求的论文定稿已另行核对。
- [ ] 无密钥、个人绝对路径、私有接口、数据原文或未授权第三方资源。
- [ ] 无伪造结果、图表、运行日志或未经验证的复现结论。
- [ ] 接口、数据、候选缓存的缺项与版本未知状态已如实注明。
- [ ] 候选词典独立构建，评估集与示例库隔离，指标使用精确匹配。
- [ ] MIT 授权与版权归属、真实引用信息、提交邮箱及暂存文件已核实。
