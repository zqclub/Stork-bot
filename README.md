# Stork-bot
1️⃣ 安装插件
➤ 下载Chrome扩展：https://chrome.google.com/webstore/detail/stork/knnliglhgkmlblppdejchidfihjnockl
➤ 必填邀请码：WH4QKCVVF2

2️⃣ 开启验证，截图留证
✔️ 登录后，在设置中打开“数据验证”
✔️ 进入 “推荐”页面，完整截图

3️⃣ 提交证明
➤ 加入官方Discord：http://discord.gg/storkoracle 
➤ 在 #stork-verify 频道上传截图，申请 “Alpha测试者”身份
➤ 保持数据验证开启！后续靠它赚积分换奖励！

## 使用说明
### 克隆存储库：
```bash
git clone https://github.com/zqclub/Stork-bot.git
cd Stork-bot
```
### 依赖安装：
```bash

pip install pycognito requests colorama urllib3
```
如果使用 SOCKS 代理，还需安装：
bash
```bash
pip install urllib3[socks]
```
## 文件配置
脚本需要以下配置文件，放在与脚本相同的目录下：
1.accounts.txt
格式：email:password，每行一个账户。

示例：
```bash
user1@example.com:password123
user2@example.com:securepass456
```
2.proxies.txt（可选）
格式：每行一个代理地址，支持 HTTP 或 SOCKS。

示例：
```bash
http://127.0.0.1:8080
socks5://127.0.0.1:1080
```
3.tokens.txt（自动生成）
脚本运行时会自动创建和管理此文件，用于存储认证令牌。

无需手动创建，首次运行会生成空文件。

## 运行步骤
确保文件准备就绪
创建并编辑 accounts.txt，至少添加一个账户。

如果使用代理，创建并编辑 proxies.txt。

运行脚本
在终端中执行以下命令：
```bash
python3 bot.py
```



