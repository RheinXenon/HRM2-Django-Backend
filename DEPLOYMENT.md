

## 搭建环境

**确认pyenv是否安装好**

```
pyenv --version
```

**切换到文件目录**

```powershell
cd /root/RecruitmentSys/backend
```

**创建虚拟环境**（pyenv已经安装好对应版本的python解释器）

```
pyenv virtualenv 3.13.5 HRM2venv
```

**在项目目录中激活虚拟环境**

```
pyenv local HRM2venv
```

## 安装依赖

**安装项目依赖**

```
pip install -r requirements.txt
```

**补充安装`autogen`**

```
pip install autogen
```

**安装线程管理器`gunicorn`**

```powershell
pip install gunicorn
```

**配置环境变量配置**

```powershell
cp .env.example .env
```

**配置.env如下：**

```
# ==================== Django 基础配置 ====================
# 运行环境：development（开发，默认）、production（生产）、testing（测试）
DJANGO_ENV=production
# 密钥：用于加密签名，请设置一个复杂的随机字符串（必填）
DJANGO_SECRET_KEY=your-secret-key-here
# 调试模式：开发环境设为 True，生产环境务必设为 False
DJANGO_DEBUG=False
# 允许访问的域名：多个域名用逗号分隔
DJANGO_ALLOWED_HOSTS=localhost,127.0.0.1,121.41.114.99
```

不要忘记允许本地访问api！！！

## 部署数据库

**迁移数据库结构**

```
python manage.py migrate
```

> 有时候可能连不上数据库，需要显式指定数据库socket地址
>
> `.env`
>
> ```
> # 数据库主机地址
> # DB_HOST=localhost
> DB_HOST=/tmp/mysql.sock
> ```



## 配置Gunicorn进程

**测试运行Gunicorn（项目目录下）**

```
gunicorn --bind 0.0.0.0:5000 config.wsgi:application
```

测试成功，就停止进程。

#### 配置systemd服务：

**创建服务文件**

```powershell
sudo nano /etc/systemd/system/HRM2.service
```

**文件内容：**

```ini
[Unit]
Description=gunicorn daemon for HRM2 Project,created on 2025/12/07
After=network.target

[Service]
User=root
Group=root
WorkingDirectory=/root/RecruitmentSys/backend
ExecStart=/root/.pyenv/versions/HRM2venv/bin/gunicorn \
--access-logfile - \
--workers 3 \
--bind 0.0.0.0:5000 \
config.wsgi:application

Restart=always
RestartSec=3

[Install]
WantedBy=multi-user.target
```



**应用配置**

```
sudo systemctl daemon-reload
```

```
sudo systemctl start HRM2
```

**设置开机启动**

```
sudo systemctl enable HRM2
# Created symlink /etc/systemd/system/multi-user.target.wants/HRM2.service → /etc/systemd/system/HRM2.service.
```



# 配置Nginx

建立站点，根目录在前端打包的dist文件夹。

修改站点nginx配置，加入api反向代理设置

```nginx
	location ~ ^/(position-settings|resume-screening|video-analysis|final-recommend|interview-assist|media)/ {
        proxy_pass http://127.0.0.1:5000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        
        # 确保路径和查询参数完整传递
        proxy_redirect off;
    }
```

