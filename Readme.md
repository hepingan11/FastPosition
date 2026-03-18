# FastPosition 

## 项目概述

《FastPosition》是一款智能简历投递平台，旨在解决求职者获取职位信息难、简历定制耗时、投递流程繁琐等痛点。通过结合大模型分析与智能推荐算法，帮助用户快速匹配优质职位，实现一键优化简历并直达投递页面。

### 核心价值
- 🚀 **高效投递**：一键直达职位官网投递链接，告别繁琐的注册与填写流程
- 🧠 **智能分析**：利用大模型解析简历，精准匹配用户技能与职位需求
- 📊 **精准推荐**：基于算法推荐符合用户背景的优质职位
- 🔄 **简历优化**：AI一键优化简历，提升通过率
- 📦 **链接管理**：自定义管理公司招聘页面链接，实现批量爬取与更新

## 主要功能

### 1. 用户系统
- 注册/登录：基于JWT的安全认证机制
- 个人中心：管理个人信息与上传的简历

### 2. 简历管理
- 多格式上传：支持PDF、TXT等格式简历
- AI解析：自动提取个人技能、工作经历、项目经验等关键信息
- 简历优化：一键生成符合职位要求的定制化简历

### 3. 职位推荐
- 智能匹配：基于简历内容与职位JD的深度匹配
- 多维度筛选：按职位名称、工作地点、薪资范围等条件筛选
- 投递直达：点击职位链接直接跳转至官网投递页面

### 4. 公司链接管理
- CRUD操作：添加、编辑、删除公司招聘页面链接
- 批量爬取：一键爬取多个公司的最新职位信息
- 定时更新：自动同步公司招聘页面的职位变化

### 5. 数据管理
- 职位数据库：存储海量职位信息，支持快速检索
- 数据同步：定时更新各大招聘平台的职位数据

## 技术栈

### 后端
- **FastAPI**：高性能Python Web框架
- **SQLAlchemy**：ORM数据库工具
- **LangChain**：大模型应用开发框架
- **Ollama**：本地大模型部署
- **MySQL**：关系型数据库
- **JWT**：用户认证
- **bcrypt**：密码哈希
- **pymupdf**：PDF解析

### 前端
- **Vue3**：现代化前端框架
- **Element Plus**：UI组件库
- **Axios**：HTTP客户端
- **Vue Router**：路由管理

### 数据处理
- **Playwright**：网页爬取
- **BeautifulSoup4**：HTML解析
- **FAISS**：向量检索

## 项目结构

```
.
├── app/                 # 后端代码
│   ├── routers/        # API路由
│   ├── models/         # 数据库模型与Pydantic schemas
│   ├── services/       # 业务逻辑层
│   ├── database.py     # 数据库连接
│   ├── config.py       # 配置管理
│   └── main.py         # 应用入口
├── web/                # 前端代码
│   ├── src/
│   │   ├── views/      # 页面组件
│   │   ├── api/        # API接口封装
│   │   ├── utils/      # 工具函数
│   │   └── router/     # 路由配置
│   └── package.json
├── requirements.txt     # 后端依赖
├── .env                # 环境变量
└── .gitignore          # Git忽略配置
```

## 快速开始

### 1. 环境准备
- Python 3.10+
- Node.js 16+
- MySQL 8.0+
- Ollama 0.1.0+

### 2. 安装依赖

#### 后端
```bash
pip install -r requirements.txt
```

#### 前端
```bash
cd web
npm install
```

### 3. 配置环境变量

复制并修改 `.env` 文件：
```env
# 应用配置
APP_NAME="FastPosition"
APP_VERSION="1.0.0"
DEBUG=true

# 数据库配置
DATABASE_URL=mysql+mysqlconnector://root:123456@localhost:3306/susutou

# Ollama 配置
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=qwen3.5:4b
OLLAMA_EMBEDDING_MODEL=qwen3-embedding:0.6b
```

### 4. 启动服务

#### 后端
```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

#### 前端
```bash
cd web
npm run dev
```

### 5. 访问应用

- 前端地址：`http://localhost:5173`
- 后端API文档：`http://localhost:8000/docs`

## 核心流程

### 简历投递流程
1. **上传简历**：用户上传PDF或TXT格式简历
2. **AI分析**：大模型解析简历内容，提取关键信息
3. **职位匹配**：算法基于简历信息匹配推荐职位
4. **优化简历**：一键生成符合职位要求的定制化简历
5. **直达投递**：点击职位链接直接跳转至官网投递页面

### 数据获取流程
1. **手动添加**：用户手动添加公司招聘页面链接
2. **批量爬取**：系统自动爬取公司页面的职位信息
3. **定时更新**：定期同步公司职位数据，保持信息最新
4. **智能检索**：基于关键词与语义匹配快速查找职位

## API 接口

### 认证接口
- `POST /auth/register`：用户注册
- `POST /auth/login`：用户登录
- `GET /auth/me`：获取当前用户信息

### 简历接口
- `POST /resume/upload`：上传简历
- `GET /resume/list`：获取简历列表
- `DELETE /resume/{id}`：删除简历

### 职位接口
- `GET /positions/recommend`：获取推荐职位
- `GET /positions/search`：搜索职位

### 公司链接接口
- `GET /company-links`：获取公司链接列表
- `POST /company-links`：添加公司链接
- `PUT /company-links/{id}`：更新公司链接
- `DELETE /company-links/{id}`：删除公司链接
- `POST /company-links/batch-crawl`：批量爬取职位

## 数据库设计

### 核心表结构

#### users（用户表）
- `id`：主键
- `username`：用户名
- `email`：邮箱
- `hashed_password`：加密密码
- `create_at`：创建时间

#### resumes（简历表）
- `id`：主键
- `user_id`：关联用户ID
- `file_name`：文件名
- `content`：简历内容
- `parsed_info`：解析后的结构化信息
- `create_at`：创建时间

#### positions（职位表）
- `id`：主键
- `name`：职位名称
- `company`：公司名称
- `location`：工作地点
- `salary`：薪资范围
- `jd`：职位描述
- `link`：投递链接
- `source`：数据来源
- `create_at`：创建时间

#### company_links（公司链接表）
- `id`：主键
- `user_id`：关联用户ID
- `company_name`：公司名称
- `link`：招聘页面链接
- `type`：职位类型（校招/实习/社招）
- `create_at`：创建时间

## 未来规划

### 短期目标
- [ ] 支持更多简历格式（DOCX）
- [ ] 优化职位匹配算法
- [ ] 增加职位收藏功能
- [ ] 实现简历模板下载

### 中期目标
- [ ] 推出AI面试官功能
- [ ] 增加职位对比功能
- [ ] 支持多语言简历
- [ ] 实现简历自动投递

### 长期目标
- [ ] 构建职业发展分析系统
- [ ] 对接更多招聘平台
- [ ] 推出企业版服务
- [ ] 移动端APP开发

## 贡献指南

欢迎提交Issue和Pull Request！

### 开发规范
- 后端遵循PEP8规范
- 前端遵循Vue3官方规范
- 提交信息使用中文描述
- 新增功能需编写相应测试

## 许可证

MIT License
