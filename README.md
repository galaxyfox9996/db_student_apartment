# 学生公寓管理系统

一个基于 `Flask + MySQL / SQLite` 的学生公寓管理系统课程设计项目，覆盖学生住宿管理、维修申报、访客登记、公告发布、日志审计等核心业务。

这个仓库同时保留了两种使用方式：

- `MySQL 课程设计版`：用于展示数据库课程设计内容，包括表结构、触发器、函数、存储过程与事务设计。
- `SQLite 便携版`：用于打包发布和演示，不需要额外安装 MySQL，适合发给别人直接运行。

## 项目特点

- 三种角色权限：系统管理员、公寓管理员、学生
- 学生信息、公寓信息、房间信息统一管理
- 支持宿舍分配、住宿状态维护、房间容量控制
- 支持学生报修、公寓管理员处理维修申请
- 支持访客申请、登记、离校记录
- 支持公告发布，包含图片、文件、视频上传
- 支持系统日志记录与查询
- 同时提供 `MySQL` 版与 `SQLite` 版运行模式
- 支持 Windows 下打包为可分发的 SQLite 桌面版

## 技术栈

- Backend: `Flask`
- Database:
  - `MySQL + PyMySQL`
  - `SQLite` 兼容运行层
- Frontend: `HTML + Jinja2 + CSS`
- Packaging: `PyInstaller`

## 功能模块

### 系统管理员

- 学生信息管理
- 公寓管理员管理
- 公寓楼管理
- 房间管理
- 住宿分配
- 系统日志查看

### 公寓管理员

- 查看本人负责公寓的房间与学生信息
- 处理维修申报
- 登记和管理访客记录
- 发布和删除公告

### 学生

- 查看个人信息和住宿信息
- 提交维修申报
- 查看维修处理进度
- 申请访客并查看历史记录
- 查看公寓公告

## 项目结构

```text
dblab2/
├── app.py                         # Flask 主程序
├── config.py                      # 数据库配置
├── database.py                    # MySQL / SQLite 双模式适配层
├── run_mysql.py                   # MySQL 课程设计版启动入口
├── run_sqlite.py                  # SQLite 便携版启动入口
├── build_exe.bat                  # 生成 SQLite 发布版目录
├── build_release_zip.bat          # 生成 SQLite 发布版压缩包
├── templates/                     # 页面模板
├── static/                        # 静态资源
├── screenshots/                   # 系统截图
├── sql/                           # MySQL 建库、触发器、事务、函数、存储过程脚本
├── 打包发布说明.md                # Windows 打包与发布补充说明
└── 实验报告_学生公寓管理系统.md      # 课程设计文档
```

## 快速开始

### 1. 安装依赖

建议先创建虚拟环境，再安装依赖：

```powershell
python -m venv .venv
.\.venv\Scripts\activate
pip install -r requirements.txt
```

## 运行方式

### 方式一：MySQL 课程设计版


先准备 MySQL 数据库并导入 `sql/` 目录中的脚本，然后启动：

```powershell
.\.venv\Scripts\python.exe run_mysql.py
```

数据库配置文件：

- [config.py](config.py)

默认使用的数据库名：

- `student_apartment_system`

### 方式二：SQLite 便携版


```powershell
.\.venv\Scripts\python.exe run_sqlite.py
```

特点：

- 首次启动自动创建本地数据库文件 `student_apartment_system.db`
- 不需要安装 MySQL
- 与主要业务页面兼容

## 默认测试账号

SQLite 演示数据内置了以下账号：

| 角色 | 用户名 | 密码 |
|---|---|---|
| 系统管理员 | `admin` | `123456` |
| 公寓管理员 | `manager001` | `123456` |
| 学生 | `20260001` | `123456` |

## MySQL 数据库脚本

`sql/` 目录中包含课程设计所需的数据库脚本：

- `create_tables.sql`：建表脚本
- `insert_data.sql`：初始化数据
- `functions.sql`：函数
- `procedures.sql`：存储过程
- `transactions.sql`：事务相关过程
- `triggers.sql`：触发器

这部分主要用于课程设计展示与数据库实验内容说明。

## 打包发布

如果你只需要生成发给别人的 `SQLite` 版：

```powershell
.\build_release_zip.bat
```

生成结果：

```text
release\StudentApartmentSystemSQLite.zip
```

解压后运行：

```text
StudentApartmentSystemSQLite.exe
```

补充说明见：

- [打包发布说明.md](打包发布说明.md)

## 页面截图

部分界面截图位于 `screenshots/` 目录，例如：

- 登录页
- 管理员首页
- 学生首页
- 房间管理
- 住宿分配
- 维修处理
- 访客管理
- 系统日志

如果上传到 GitHub 后需要，我也可以继续帮你把这些截图整理成 README 展示图集。

## 课程设计说明

这个项目不仅是一个 Web 管理系统实现，同时也保留了数据库课程设计要求中的关键内容：

- 规范化表结构设计
- 角色权限划分
- 触发器
- 存储过程
- 函数
- 事务
- 日志审计

因此它既可以作为课程项目展示，也可以作为一个可运行的演示系统。

## 后续可扩展方向

- 宿舍换宿与退宿流程完善
- 数据统计图表展示
- 密码加密存储
- 更完整的异常提示与表单校验
- Docker 部署
- 公网访问与服务器部署

## License

本项目主要用于课程设计、学习与演示。
